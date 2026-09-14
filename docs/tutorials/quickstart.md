# 快速开始

根 [`README.md`](../../README.md) 是开发者入口；本教程给出最短的 Docker 本地启动路径。

## Requirements

- Docker Engine and Docker Compose
- 一个可用的 OpenAI-compatible 或 DashScope 模型密钥

## Start the full local stack

```bash
cp .env.example .env
# 替换占位密码、SECRET_KEY，并配置 OPENAI_API_KEY 或 DASHSCOPE_API_KEY。
./start_docker.sh
```

脚本会构建镜像，启动 PostgreSQL、Redis、RabbitMQ 和 Qdrant，执行 Alembic 迁移，
按需初始化向量数据，然后启动 API、Celery worker、Celery scheduler 和 outbox relay。

访问地址：

- API/Health: <http://localhost:8000/health>
- Customer UI: <http://localhost:8000/app>
- Admin UI: <http://localhost:8000/admin>
- RabbitMQ management: <http://localhost:15672>

需要直接运行 Python/Node 进程时，继续阅读[本地开发环境](./local-development.md)。

## Next steps

- [Environment variables](../reference/environment-variables.md)
- [Architecture](../explanation/architecture/README.md)
- [Operations](../runbooks/README.md)
