# 本地开发环境搭建

本页是本地开发的权威分步流程。完整 Docker 启动优先使用根目录
`./start_docker.sh`；以下步骤用于在宿主机运行后端、worker 和前端。

## 1. Install dependencies

```bash
uv sync --frozen
cd frontend && npm ci && cd ..
```

需要 Python 3.12+、uv、Node.js 22+、Docker Engine 和 Docker Compose。

## 2. Configure the environment

```bash
cp .env.example .env
```

替换 PostgreSQL/RabbitMQ/`SECRET_KEY` 占位值，并至少配置一个模型提供商密钥。
变量的分类和所有权见[环境变量参考](../reference/environment-variables.md)。

## 3. Start local infrastructure

```bash
docker compose up -d --wait db redis rabbitmq qdrant
uv run alembic upgrade head
```

RabbitMQ 是 Celery broker；Redis 是缓存、会话/撤销、限流、锁、checkpoint 及可选
result backend。基础设施端口只绑定到 host loopback。

## 4. Run application roles

在独立终端运行：

```bash
# API
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Worker（等待 PostgreSQL/Redis/RabbitMQ/Qdrant 就绪）
./start_worker.sh

# Scheduler / Beat
uv run celery -A app.celery_app beat --loglevel=info

# Transactional outbox relay
uv run python -m app.outbox

# Frontend
cd frontend && npm run dev
```

不要把 worker 与 Beat 合并为默认开发命令；它们是独立运行角色。

## 5. Verify

```bash
# Backend quality
uv run ruff check app tests
uv run ruff format --check app tests
uv run ty check --error-on-warning app tests

# Backend tests (full gate; use only when the task requires it)
uv run pytest --cov=app --cov-fail-under=75

# Frontend
cd frontend
npm run format:check
npm run lint
npm run test
npm run build
npm run test:e2e
```

后端测试在导入应用前强制使用 `test_` PostgreSQL、Redis DB 15、进程级 Qdrant
collection 和内存 Celery transport。真实 RabbitMQ 集成测试只允许 `test_` vhost。

## Local endpoints

- API: <http://localhost:8000>
- OpenAPI: <http://localhost:8000/docs> when enabled
- Customer/Admin static builds: <http://localhost:8000/app> and <http://localhost:8000/admin>
- Vite: <http://localhost:5173> and <http://localhost:5173/admin.html>
