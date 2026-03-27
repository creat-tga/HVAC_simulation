# 前端更新后端与数据库兼容性分析

## 一、变更概览

前端对建筑分区（`BuildingZone`）进行了以下重大更新：

| 变更项 | 新增字段 | 类型 |
|--------|---------|------|
| 分区层高 | `floor_height` | `number` |
| 温度设定 | `temperature` | `ParamConfig`（固定/分时段） |
| 相对湿度设定 | `relative_humidity` | `ParamConfig`（固定/分时段） |
| 日程模型重构 | `DaySchedule` | 日期范围+星期+小时+单值 |

## 二、后端各层现状与是否需要更新

### 2.1 数据库模型层 (`backend/app/models/building.py`)

**现状**：
```python
zones: Mapped[list | None] = mapped_column(JSON, nullable=True)
```

**结论：不需要修改** ✅

`zones` 列使用 `JSON` 类型存储，SQLite/PostgreSQL 的 JSON 列接受任意 JSON 结构。无论前端传入的 zone 对象包含多少字段（`floor_height`、`temperature`、`relative_humidity` 等），都可以直接序列化为 JSON 存储。**无需数据库迁移**。

### 2.2 Pydantic 模式层 (`backend/app/schemas/building.py`)

**现状**：已在之前的会话中更新过。当前包含：

```python
class DaySchedule(BaseModel):
    name: str
    start_month: int    # 新格式
    start_day: int      # 新格式
    end_month: int      # 新格式
    end_day: int        # 新格式
    days: list[int]
    hours: list[int]    # 新格式（原为 slots: TimeSlot[]）
    value: float        # 新格式（单值）

class BuildingZone(BaseModel):
    name: str
    area: float
    floor_height: float = 3.5              # ← 有默认值
    wall_u_value: float
    ...
    temperature: ParamConfig = ParamConfig(mode="fixed", fixed_value=26)       # ← 有默认值
    relative_humidity: ParamConfig = ParamConfig(mode="fixed", fixed_value=50) # ← 有默认值
```

**结论：已更新，本次做了兼容性修复** ✅

本次将 `floor_height`、`temperature`、`relative_humidity` 设为**带默认值的字段**（`float = 3.5`、`ParamConfig = ...`），确保数据库中已有的旧数据（不含这些字段）在反序列化时不会报 Pydantic 校验错误。

### 2.3 服务层 (`backend/app/services/building_service.py`)

**现状**：
```python
# 创建
building = Building(project_id=project_id, **data.model_dump())

# 更新
for key, value in data.model_dump(exclude_unset=True).items():
    setattr(building, key, value)
```

**结论：不需要修改** ✅

- `model_dump()` 将 Pydantic 模型（包括嵌套的 `BuildingZone` → `ParamConfig` → `DaySchedule`）递归序列化为 Python `dict`/`list`
- SQLAlchemy 的 `JSON` 列自动将 `dict`/`list` 存为 JSON 字符串
- 读取时 `JSON` 列自动反序列化为 `dict`/`list`，再由 `BuildingResponse` 的 `model_config = {"from_attributes": True}` 将其映射为 Pydantic 模型

### 2.4 路由层 (`backend/app/routers/buildings.py`)

**结论：不需要修改** ✅

路由使用 `BuildingCreate`/`BuildingUpdate` 作为请求体类型，`BuildingResponse` 作为响应类型。这些 schema 已正确包含 `zones: list[BuildingZone] | None` 字段，zones 内部结构的变更对路由层透明。

## 三、数据库迁移需求

**不需要迁移** ✅

原因：
1. `zones` 列类型为 `JSON`，不是关系型的独立表/列
2. JSON 列是**无模式（schema-less）**的，新增的 `floor_height`、`temperature`、`relative_humidity` 字段只是 JSON 对象内部属性的变化
3. 旧数据不含新字段 → Pydantic 用默认值填充（`floor_height=3.5`, `temperature=固定26℃`, `humidity=固定50%`）
4. 新数据包含新字段 → 直接存储为 JSON

## 四、数据兼容矩阵

| 场景 | 前端 | 后端 Schema | 数据库 | 是否兼容 |
|------|------|------------|--------|---------|
| 新建分区（含所有新字段） | ✅ 发送完整 zone | ✅ 校验通过 | ✅ JSON 存储 | ✅ |
| 读取旧数据（无新字段） | ✅ `normalizeZone()` 填充默认值 | ✅ Pydantic 默认值 | ✅ 原样读取 | ✅ |
| 旧前端写、新后端读 | — | ✅ 默认值填充 | ✅ | ✅ |
| 新前端写、旧后端读 | — | ❌ 旧 schema 不识别新字段 | ✅ JSON 不变 | ⚠️ 需要后端同步更新 |

## 五、总结

| 层级 | 是否需要更新 | 说明 |
|------|-------------|------|
| 数据库模型 | ❌ 不需要 | JSON 列，无模式约束 |
| 数据库迁移 | ❌ 不需要 | 无表结构变化 |
| Pydantic Schema | ✅ 已更新 | 新增字段+默认值保证向后兼容 |
| 服务层 | ❌ 不需要 | `model_dump()` 自动处理嵌套结构 |
| 路由层 | ❌ 不需要 | Schema 变更对路由透明 |

**核心设计优势**：采用 `JSON` 列存储 zones 的架构决策，使得前端数据模型的迭代（新增字段、修改嵌套结构）无需数据库迁移，只需保证 Schema 层有合理的默认值即可。
