# Local Development

This is the canonical fresh-clone guide. It supports exactly two workflows: the verified full Docker stack and host developer mode backed by Docker infrastructure.

## Prerequisites

- Git.
- Docker Engine with Docker Compose v2 (Docker Desktop is supported).
- Bash for the canonical full-stack script.
- For host development: Python 3.12, [uv](https://docs.astral.sh/uv/), Node.js 22, and npm 11.
- A DashScope/Bailian or OpenAI runtime credential for AI chat. Repository knowledge embedding is configured separately with `EMBEDDING_API_KEY` or falls back to `DASHSCOPE_API_KEY`.

### Windows and WSL

Use WSL 2 with Docker Desktop WSL integration for `./start_docker.sh`. Keep the checkout in a filesystem with acceptable bind-mount performance. PowerShell users can run host commands directly, but the examples below use Bash environment-variable syntax; the PowerShell equivalent is `$env:NAME="value"`.

Do not run `docker compose down -v` against an existing developer project. Normal stops and restarts preserve PostgreSQL, Qdrant, RabbitMQ, Redis, and knowledge-upload volumes.

## Configure the Environment

```bash
cp .env.example .env
```

`.env` is ignored. Replace all password and `SECRET_KEY` placeholders. For the persisted local/UAT dataset, keep:

```dotenv
ENVIRONMENT=development
LOCAL_BOOTSTRAP_ENABLED=true
```

Set the tenant name, usernames, emails, and passwords through the `LOCAL_BOOTSTRAP_*` variables. The Python bootstrap contains no password defaults and never logs password values.

For the validated DashScope-compatible API shape:

```dotenv
MODEL_DASHSCOPE_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
EMBEDDING_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
RERANK_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
DASHSCOPE_API_KEY=<your-untracked-key>
```

See the [environment reference](../reference/environment-variables.md) for ownership and sensitivity.

## Workflow A: Full Docker Local Stack

From the repository root:

```bash
./start_docker.sh
```

The command performs this contract in order:

1. Validate the configured Compose project.
2. Build the application image and start healthy PostgreSQL, Redis, RabbitMQ, and Qdrant services.
3. Run `alembic upgrade head`, prove exactly one head, and run `alembic current --check-heads`.
4. Provision and connect through the runtime and maintenance PostgreSQL login roles.
5. Reconcile the guarded local/UAT PostgreSQL dataset and ingest repository knowledge/product sources into Qdrant.
6. Start the API, tenant worker, maintenance worker, Beat scheduler, and outbox relay.
7. Verify API/UI health, both browser logins, session restoration/logout, tenant and user isolation, admin APIs, Redis, Qdrant retrieval, and one outbox → RabbitMQ → Celery → receipt flow.

Default URLs:

- Customer: <http://localhost:8000/app>
- Admin: <http://localhost:8000/admin>
- Health: <http://localhost:8000/health>
- OpenAPI: <http://localhost:8000/docs> when enabled
- RabbitMQ management: <http://localhost:15672>

Use the configured `LOCAL_BOOTSTRAP_CUSTOMER_*` and `LOCAL_BOOTSTRAP_ADMIN_*` credentials. They are synthetic development identities, not production users.

### Isolated Disposable Project

The script accepts a different ignored env file and Compose project/host ports, which is useful for destructive acceptance without touching normal development volumes:

```bash
COMPOSE_PROJECT_NAME=star-warehouse-disposable \
ENV_FILE=.env.disposable \
APP_HOST_PORT=18080 \
./start_docker.sh
```

Put the alternate host ports in `.env.disposable` as well. Never reuse a normal project name or its volumes for destructive checks. The startup script derives the exact local browser origin from `APP_HOST_PORT`; set `CORS_ORIGINS` explicitly only when additional trusted origins are required.

## Workflow B: Host Developer Mode

Install locked dependencies:

```bash
uv sync --frozen
cd frontend && npm ci && cd ..
```

Start only infrastructure:

```bash
docker compose up -d --wait db redis rabbitmq qdrant
```

Prepare the authoritative schema, database roles, persisted local/UAT data, and derived indexes:

```bash
uv run alembic upgrade head
uv run alembic current --check-heads
uv run python -m app.core.database_roles
uv run python -m scripts.bootstrap_local_data
```

Start each runtime role in its own terminal:

```bash
# API
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Tenant worker: critical and default queues
./start_worker.sh

# Maintenance worker
DB_CAPABILITY=maintenance uv run celery -A app.celery_app worker \
  --loglevel=info --concurrency=2 --pool=solo --queues=maintenance

# Scheduler
uv run celery -A app.celery_app beat --loglevel=info

# Transactional outbox relay
DB_CAPABILITY=maintenance uv run python -m app.outbox

# Vite customer/admin development server
cd frontend && npm run dev
```

Host endpoints are API <http://localhost:8000>, Vite customer <http://localhost:5173>, and Vite admin <http://localhost:5173/admin.html>.

After the roles are running, execute the same non-secret verification used by Docker startup:

```bash
uv run python -m scripts.verify_local_stack --api-base-url http://localhost:8000
```

## Database and Data Bootstrap

Alembic is the only schema authority; application startup does not use `SQLModel.metadata.create_all()` for production schema creation. `scripts.bootstrap_local_data` is the one canonical local data command. It refuses production, requires explicit enablement, owns one coherent tenant dataset, and is safe to run twice.

Historical `scripts/seed_data.py`, `scripts/initialize_vector_data.py`, and
`scripts/seed_product_catalog.py` names remain thin compatibility wrappers only. Do not use them in
new documentation or automation.

## Provider Setup

Runtime chat routes can target OpenAI or DashScope through `MODEL_ROUTES`. Embeddings use `EMBEDDING_BASE_URL`, `EMBEDDING_API_KEY`, `EMBEDDING_MODEL`, and `EMBEDDING_DIM`. Reranking uses the `RERANK_*` group.

The Mock provider remains test/evaluation-only. A missing paid chat-provider key does not invalidate migration, role, authentication, or database tests, but semantic chat/retrieval smoke requires a working configured provider. Real-provider tests remain opt-in:

```bash
RUN_REAL_LLM_TESTS=true uv run pytest -m requires_llm
```

## Verification and Tests

Run cheap focused checks before broad gates:

```bash
uv run ruff format --check app tests
uv run ruff check app tests
uv run ty check --error-on-warning app tests
uv run pytest tests/bootstrap tests/auth tests/authorization tests/tools tests/retrieval -q

cd frontend
npm run format:check
npm run lint
npm run test
npm run build
npm run test:e2e
```

The full backend CI gate is:

```bash
uv run pytest --cov=app --cov-fail-under=75
```

Tests use their own `test_` PostgreSQL database, Redis DB/namespace, Qdrant collection, and deterministic model doubles. They do not depend on local bootstrap rows.

## Optional Monitoring

Follow the [observability runbook](../runbooks/observability.md) to start `docker-compose.monitoring.yml`. The default loopback UIs are Grafana `:3000`, Prometheus `:9090`, and Alertmanager `:9093`.

## Troubleshooting

### Bootstrap refuses to run

Confirm `ENVIRONMENT` is not `production`, `LOCAL_BOOTSTRAP_ENABLED=true`, all identity fields are non-empty, usernames differ, and passwords are at least 12 characters.

### Host PostgreSQL cannot connect

Use `POSTGRES_SERVER=127.0.0.1` if the host resolves `localhost` to an unavailable IPv6 path. Inside Compose, services always use `db`.

### Knowledge is empty or retrieval verification fails

Check Qdrant health, the embedding endpoint/key, `KNOWLEDGE_UPLOAD_DIR`, worker logs, and tenant payloads. Re-run only the idempotent canonical bootstrap:

```bash
uv run python -m scripts.bootstrap_local_data
```

Do not insert vectors manually. Qdrant is rebuilt through the supported ingestion path.

### Async receipt times out

Check RabbitMQ health, the `critical` worker queue, outbox relay logs, configured broker URL, `outbox_events`, and `task_execution_receipts`. RabbitMQ carries tasks; PostgreSQL retains the durable event and receipt.

### Port collision

Set the corresponding `APP_HOST_PORT`, `POSTGRES_HOST_PORT`, `REDIS_HOST_PORT`, `RABBITMQ_HOST_PORT`, `RABBITMQ_MANAGEMENT_HOST_PORT`, `QDRANT_HTTP_HOST_PORT`, or `QDRANT_GRPC_HOST_PORT` in an alternate env file/project.

## Stop, Restart, and Reset

Safe stop/restart commands preserve volumes:

```bash
docker compose stop
docker compose start
```

There is intentionally no default destructive reset command. To obtain an empty state, create a new explicitly named disposable Compose project and env file. Removing volumes is permitted only after you have verified the exact disposable project name and intentionally confirmed that its data can be lost.
