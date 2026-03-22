# HVAC_simulation

这是 HVAC_simulation 项目的仓库根说明文档。下面包含开发环境准备与启动脚本（适用于从 GitHub 克隆到新设备后的快速上手）。

## 前置条件
- Python 3.12
- Node.js >= 18
- pnpm
- `uv` (项目中用于管理后端依赖与运行，本项目文档中使用 `uv` 命令)

建议在系统上安装 Git、Python、Node 与 pnpm，并在虚拟环境中运行后端。

---

## 后端（Backend）
位置：`backend/`

1. 安装 & 同步依赖：

```bash
cd backend
uv sync
```

2. 数据库迁移（如有）：

```bash
cd backend
uv run alembic upgrade head
```

3. 启动开发服务器（热重载）：

```bash
cd backend
uv run uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

4. 运行后端测试：

```bash
cd backend
uv run pytest
```

---

## 前端（Frontend）
位置：`frontend/`

1. 安装依赖：

```bash
cd frontend
pnpm install
```

2. 启动开发服务器：

```bash
cd frontend
pnpm run dev
```

3. 构建生产包：

```bash
cd frontend
pnpm run build
```

4. 若包含单元测试：

```bash
cd frontend
pnpm run test:unit
```

---

## 常见问题
- 若后端出现依赖或 Python 环境问题，确保使用 Python 3.12 并在虚拟环境中执行 `uv sync`。
- 若前端启动失败，删除 `node_modules` 并重新 `pnpm install`。

---

## 下一步建议
- 若希望我在当前机器上验证启动脚本，我可以尝试运行后端/前端并反馈日志。
- 可选：我可以为项目添加 Docker 支持或生成更详细的运行与部署文档。

---

文件位置： [README.md](README.md)