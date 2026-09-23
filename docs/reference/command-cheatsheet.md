# 常用命令速查表

## Full local stack

```bash
./start_docker.sh
docker compose ps
docker compose logs -f app
```

## Host-process development

```bash
uv sync --frozen
docker compose up -d --wait db redis rabbitmq qdrant
uv run alembic upgrade head
uv run alembic current --check-heads
uv run python -m app.core.database_roles
uv run python -m scripts.bootstrap_local_data
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
./start_worker.sh
DB_CAPABILITY=maintenance uv run celery -A app.celery_app worker --loglevel=info --concurrency=2 --pool=solo --queues=maintenance
uv run celery -A app.celery_app beat --loglevel=info
DB_CAPABILITY=maintenance uv run python -m app.outbox
cd frontend && npm ci && npm run dev
```

## Tests and quality

```bash
uv run ruff check app tests
uv run ruff format --check app tests
uv run ty check --error-on-warning app tests
uv run pytest --cov=app --cov-fail-under=75

cd frontend
npm run format:check
npm run lint
npm run test
npm run build
npm run test:e2e
```

## Database

```bash
uv run alembic upgrade head
uv run alembic heads
uv run alembic current --check-heads
uv run python -m app.core.database_roles
uv run python -m scripts.bootstrap_local_data
uv run alembic revision --autogenerate -m "description"
```

## Optional monitoring

```bash
docker compose -f docker-compose.monitoring.yml config
./scripts/deploy-monitoring.sh
```
