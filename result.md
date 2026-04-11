# `settings.debug` 配置分析及修改方案

## 问题背景

仿真运行时后端日志洪水般输出，主要是大量 SQLAlchemy SQL 语句及参数（包含 8760 小时数组，每条参数 ~100KB）。

## `settings.debug` 当前影响范围

| 使用位置 | 代码 | 作用 |
|----------|------|------|
| `database.py` (async engine) | `echo=settings.debug` | SQLAlchemy 打印每条 SQL + 参数到日志 |
| `database.py` (sync engine) | `echo=settings.debug` | 同上（同步引擎，Celery/后台任务用） |
| `main.py` | `level=DEBUG if settings.debug else INFO` | 控制全局日志级别 |

**当前默认值：`debug: bool = True`**

## 分析：把 `debug` 改为 `False` 是否更好？

### 不建议直接改为 `False` 的原因

1. **`debug=True` 对开发有用**  
   - `main.py` 中 `debug=True` 使全局日志级别为 `DEBUG`  
   - 开发阶段需要看到 EnergyPlus 运行信息、Redis 连接状态、任务调度日志等  
   - 如果改为 `False`，这些有用的调试信息也会消失

2. **真正的问题是 SQL echo 对仿真场景不合适**  
   - 仿真任务频繁写入进度（每个 zone 完成一次 SELECT+UPDATE+COMMIT）  
   - 保存结果时 UPDATE 参数包含 ≥100KB 的 JSON 数组  
   - 前端轮询每 3 秒触发一次 SELECT  
   - 这些 SQL 日志是"信噪比极低"的噪音

3. **`debug` 应该控制"应用行为"，不该控制"基础设施日志"**  
   - SQL echo 属于极端诊断工具（排查 ORM 问题时才用）  
   - 日常开发根本不需要看每条 SQL  

## 采用的方案：解耦 SQL echo

**新增 `sql_echo` 配置，与 `debug` 分离：**

```python
# config.py
class Settings(BaseSettings):
    debug: bool = True       # 控制应用日志级别（DEBUG / INFO）
    sql_echo: bool = False   # 控制 SQLAlchemy SQL 日志（默认关闭）

# database.py
engine = create_async_engine(url, echo=settings.sql_echo, ...)
sync_engine = create_engine(url, echo=settings.sql_echo, ...)
```

### 使用方式

| 场景 | 配置 | 效果 |
|------|------|------|
| 日常开发 | `debug=True, sql_echo=False` (默认) | 看得到应用级 DEBUG 日志，不刷屏 SQL |
| 排查 ORM 问题 | `debug=True, sql_echo=True` | 临时打开看 SQL |
| 生产环境 | `debug=False, sql_echo=False` | 只显示 INFO+，无 SQL |

**开启 SQL echo 的方式：**  
在 `.env` 文件或环境变量中设置：
```env
SQL_ECHO=true
```

## 额外的日志治理措施

`main.py` 还添加了以下配置，作为双重保险：
```python
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)   # 抑制轮询 HTTP 请求日志
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)  # 即使 echo=True 也不刷屏
logging.getLogger("aiosqlite").setLevel(logging.WARNING)          # 抑制 aiosqlite 内部日志
```

## 结论

| 方案 | 推荐度 | 说明 |
|------|--------|------|
| 改 `debug=False` | ❌ 不推荐 | 一刀切，丢失有用的应用调试日志 |
| 新增 `sql_echo=False` | ✅ 已采用 | 精确解耦，按需开启，默认不刷屏 |
| 删除 `echo` 参数 | 🔶 可接受 | 但丧失了需要时开启的灵活性 |
