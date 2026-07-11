# HVAC_simulation

这是 HVAC_simulation 项目的仓库根说明文档。下面包含开发环境准备与启动脚本（适用于从 GitHub 克隆到新设备后的快速上手）。

## 前置条件
- Python 3.12
- Node.js >= 18
- pnpm
- `uv` (项目中用于管理后端依赖与运行，本项目文档中使用 `uv` 命令)
- Redis（可选，用于 Celery 异步任务队列）

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

## Redis & Celery（可选）

项目支持两种仿真任务执行模式：
- **In-process 模式**（默认）：无需 Redis/Celery，仿真任务在 FastAPI 进程内以 asyncio 后台协程运行。适用于开发和单用户场景。
- **Celery 模式**：通过 Redis + Celery worker 将仿真任务分发到独立进程执行。适用于多用户并发、生产部署场景。

系统会自动检测 Redis 是否可用以及 Celery worker 是否在线，如果没有启动则自动回退到 in-process 模式，无需手动切换。

### 启动 Redis

**Windows（使用 Docker）**：
```bash
docker run -d --name redis -p 6379:6379 redis:latest
```

**Linux / macOS**：
```bash
# Ubuntu/Debian
sudo apt install redis-server
sudo systemctl start redis

# macOS (Homebrew)
brew install redis
brew services start redis
```

验证 Redis 是否运行：
```bash
redis-cli ping
# 应返回 PONG
```

### 启动 Celery Worker

Redis 启动后，在单独的终端中运行 Celery worker：

**Windows**：
```bash
cd backend
uv run celery -A app.celery_app:celery_app worker --loglevel=info --pool=solo
```

> Windows 上必须使用 `--pool=solo`，因为 Windows 不支持 Celery 默认的 prefork 进程池。

**Linux / macOS**：
```bash
cd backend
uv run celery -A app.celery_app:celery_app worker --loglevel=info
```

Linux/macOS 默认使用 `prefork` 进程池，支持多进程并行处理任务。可通过 `--concurrency` 参数指定 worker 数量：

```bash
# 使用 4 个 worker 进程
uv run celery -A app.celery_app:celery_app worker --loglevel=info --concurrency=4
```

也可以使用 `systemd` 将 Celery worker 注册为系统服务（生产部署推荐）：

```ini
# /etc/systemd/system/hvac-celery.service
[Unit]
Description=HVAC Simulation Celery Worker
After=redis.service

[Service]
Type=forking
User=www-data
WorkingDirectory=/path/to/backend
ExecStart=/path/to/uv run celery -A app.celery_app:celery_app worker --loglevel=info --concurrency=4
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable hvac-celery
sudo systemctl start hvac-celery
```

### 完整的开发环境启动顺序

**Windows**：
```bash
# 终端 1：Redis（如使用 Docker）
docker run -d --name redis -p 6379:6379 redis:latest

# 终端 2：Celery Worker
cd backend
uv run celery -A app.celery_app:celery_app worker --loglevel=info --pool=solo

# 终端 3：FastAPI 后端
cd backend
uv run uvicorn main:app --reload --host 0.0.0.0 --port 8000

# 终端 4：Vue 前端
cd frontend
pnpm run dev
```

**Linux / macOS**：
```bash
# 终端 1：Redis
sudo systemctl start redis  # 或 docker run -d --name redis -p 6379:6379 redis:latest

# 终端 2：Celery Worker
cd backend
uv run celery -A app.celery_app:celery_app worker --loglevel=info --concurrency=4

# 终端 3：FastAPI 后端
cd backend
uv run uvicorn main:app --reload --host 0.0.0.0 --port 8000

# 终端 4：Vue 前端
cd frontend
pnpm run dev
```

### 环境变量配置

在 `backend/.env` 中可配置 Redis 连接地址（默认为 `redis://localhost:6379/0`）：

```env
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
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

## multiSystem 真实能耗仿真接入

系统方案页面的能耗仿真由平台后端统一编排，并调用独立的 `multiSystem` 计算服务。浏览器不直接访问计算服务。

1. 在 `multiSystem/.env` 中设置 `SERVER_PORT=8010`，启动计算服务。
2. 在本项目 `backend/.env` 中设置 `MULTISYSTEM_BASE_URL=http://127.0.0.1:8010`。
3. 执行数据库迁移：

```powershell
cd backend
uv run alembic upgrade head
```

4. 重新同步设备库，使水泵曲线、冷却塔性能系数和主机类型进入数据库：

```powershell
uv run python ..\scripts\seed_equipment.py
```

生产环境必须配置至少 32 位随机 `SECRET_KEY`。首次创建管理员时可临时配置 `BOOTSTRAP_ADMIN_USERNAME` 与 `BOOTSTRAP_ADMIN_PASSWORD`；管理员创建或密码轮换成功后应立即移除这两个变量。

当前负荷结果只保存建筑总逐时负荷，因此真实能耗计算暂支持一个负荷分组；多负荷分组会返回明确校验错误，避免静默按面积估算。
