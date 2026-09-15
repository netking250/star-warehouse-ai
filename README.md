# Star Warehouse AI

> 星仓 AI 智能客服 — an enterprise-oriented AI customer-service and agent platform for commerce workflows.

[![CI](https://github.com/netking250/star-warehouse-ai/actions/workflows/ci.yml/badge.svg)](https://github.com/netking250/star-warehouse-ai/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/Python-3.12%2B-3776AB)
![React](https://img.shields.io/badge/React-19-61DAFB)
![Version](https://img.shields.io/badge/version-5.0.0-06B6D4)

## Project Overview

Star Warehouse AI is a full-stack, multi-tenant AI customer-service system. It combines
domain agents, business tools, hybrid retrieval, durable conversation state, human review,
safety controls, evaluation, and observability in one modular-monolith repository. The project
is designed to demonstrate enterprise engineering controls truthfully; it does not claim a
compliance certification or production service-level guarantee.

The customer application supports conversational commerce workflows, while the administration
application exposes operational, agent, knowledge, feedback, and analytics capabilities.

## Core Architecture

| Component | Implemented responsibility |
| --- | --- |
| FastAPI | HTTP, SSE, WebSocket, authentication, administration, and runtime APIs |
| PostgreSQL | Authoritative relational state, durable conversations, transactional outbox, and forced tenant RLS |
| Redis | Cache, browser-session revocation, rate limits, locks, and short-lived/checkpoint state |
| RabbitMQ + Celery | Brokered asynchronous work with separate tenant and maintenance worker roles |
| Qdrant | Tenant-filtered knowledge and derived memory vector indexes |
| LangGraph | Agent workflow implementation behind the Conversation Runtime boundary |
| React 19 | Customer and administration frontends |
| OpenTelemetry stack | Correlated tracing, metrics, logs, dashboards, and local alerting support |

The application remains a modular monolith. The API, tenant worker, maintenance worker,
scheduler, and outbox relay are independently operable runtime roles, not separate business
microservices.

## Architecture Layers

- **Conversation Runtime** owns PostgreSQL-authoritative conversations, turns, runs, ordered
  events, idempotency, cancellation, recovery, and the executor boundary. LangGraph remains an
  internal implementation detail.
- **Model Gateway** exposes provider-neutral requests, responses, streaming, capabilities, and
  configured use-case routes. T13 performs one selected-provider attempt; the T14 feature branch
  adds the bounded retry, ordered fallback, circuit, and explicitly marked degradation policy.
- **Provider adapters** isolate OpenAI, DashScope, and deterministic Mock behavior from agents and
  application services. Ordinary tests use mocks or fake transports.
- **Async infrastructure** persists critical task intent through PostgreSQL and the transactional
  outbox before RabbitMQ/Celery delivery. Task envelopes carry trusted tenant, user,
  correlation, trace, and idempotency context.
- **Tenant and security boundaries** combine explicit tenant resolution, ORM filtering,
  PostgreSQL RLS, least-privilege database roles, current-state authorization, HttpOnly browser
  sessions, CSRF/origin checks, and lifecycle-oriented compliance controls.

See the [architecture decisions](docs/engineering/DECISIONS.md) and
[architecture guardrails](docs/architecture/ARCHITECTURE_GUARDRAILS.md) for the accepted baseline.

## Quick Start with Docker

Requirements: Docker Engine, Docker Compose, and credentials for the configured model route.

```bash
git clone https://github.com/netking250/star-warehouse-ai.git
cd star-warehouse-ai
cp .env.example .env
# Replace local placeholders and configure the selected model provider.
./start_docker.sh
```

`start_docker.sh` is the canonical full-stack startup path. It starts PostgreSQL, Redis,
RabbitMQ, and Qdrant; applies Alembic migrations; provisions database roles; initializes bundled
vector data when required; and recreates the application runtime containers.

Local endpoints:

- Customer UI: <http://localhost:8000/app>
- Admin UI: <http://localhost:8000/admin>
- Health: <http://localhost:8000/health>
- OpenAPI: <http://localhost:8000/docs> when `ENABLE_OPENAPI_DOCS=True`
- RabbitMQ management: <http://localhost:15672>

Infrastructure host ports are loopback-only. Docker Compose is the local deployment profile, not
the production reference topology.

## Local Development

Install dependencies:

```bash
uv sync --frozen
cd frontend && npm ci && cd ..
cp .env.example .env
```

Start dependencies and initialize PostgreSQL:

```bash
docker compose up -d --wait db redis rabbitmq qdrant
uv run alembic upgrade head
uv run python -m app.core.database_roles
```

Run roles in separate terminals as needed:

```bash
# API
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Tenant worker
./start_worker.sh

# Maintenance worker, with POSTGRES_MAINTENANCE_* credentials
DB_CAPABILITY=maintenance uv run celery -A app.celery_app worker --loglevel=info --queues=maintenance

# Scheduler
uv run celery -A app.celery_app beat --loglevel=info

# Transactional outbox relay
uv run python -m app.outbox

# Frontend development server
cd frontend && npm run dev
```

The frontend development server runs at <http://localhost:5173>. The
[local development guide](docs/tutorials/local-development.md) covers the complete workflow.

## Tests

Canonical backend checks:

```bash
uv run ruff check app tests
uv run ruff format --check app tests
uv run ty check --error-on-warning app tests
uv run pytest --cov=app --cov-fail-under=75
```

Canonical frontend checks:

```bash
cd frontend
npm run format:check
npm run lint
npm run test
npm run build
npm run test:e2e
```

Ordinary backend tests are hermetic with respect to public model providers: they use the Mock
adapter or fake transports and do not require real OpenAI or DashScope calls. Real-provider tests
are marked `requires_llm` and run only when valid credentials are present **and**
`RUN_REAL_LLM_TESTS=1` is explicitly set.

The backend suite also enforces a `test_` PostgreSQL database, Redis DB 15, process-scoped Qdrant
collections, and in-memory Celery transports by default. Real RabbitMQ integration tests require
a dedicated vhost whose name starts with `test_`.

## Environment

Copy [.env.example](.env.example) to `.env` and replace its local placeholders. Never commit
`.env` or real credentials. Application settings are loaded only through `app/core/config.py`.

Migration/role provisioning uses `POSTGRES_*`; tenant runtimes use `POSTGRES_RUNTIME_*`; the
outbox and scheduled maintenance roles use separate `POSTGRES_MAINTENANCE_*` credentials.
RabbitMQ is the Celery broker; Redis may remain the result backend but is not the broker.

The [environment reference](docs/reference/environment-variables.md) identifies application,
Compose, test, monitoring, and frontend ownership.

## Repository Structure

```text
app/                    FastAPI backend, agents, runtime, gateway, services, and workers
frontend/               React customer and administration applications
tests/                  Backend unit, integration, evaluation, safety, and runtime tests
migrations/             Immutable Alembic revision history
deploy/                 Deployment reference assets and local identity-provider profile
scripts/                Seed, evaluation, monitoring, smoke, and maintenance utilities
docs/                   Architecture, engineering state, guides, references, and runbooks
data/                    Bundled policy, product, and evaluation seed data
docker-compose.yaml     Canonical local application stack
```

Optional monitoring uses `docker-compose.monitoring.yml` and the Prometheus, Grafana,
Alertmanager, Loki, Promtail, Tempo, OpenTelemetry Collector, and Mimir configuration directories.

## Project Status

- Current release: `5.0.0`.
- Enterprise-hardening milestones T-INIT through T13 are externally accepted `PASS`; T14 is
  externally accepted `PASS_WITH_NOTES` with two deferred protected-main baseline test debts.
- T13 delivers the Dynamic Model Gateway with OpenAI, DashScope, and Mock adapters.
- T14 (AI Failure Policy) is complete on the long-lived
  `feat/t14-t21-enterprise-hardening` branch; T15 Frontend Transport is `IN_PROGRESS / VERIFY_PENDING`.
- T14-T21 use one integration branch with targeted stage verification and one final PR after T21;
  see the [current project state](docs/engineering/PROJECT_STATE.md) for the workflow and debt policy.

Detailed milestone evidence remains in the engineering state documents rather than this project
introduction.

## Documentation

- [Documentation center](docs/README.md)
- [Current project state](docs/engineering/PROJECT_STATE.md)
- [Enterprise-hardening roadmap](docs/engineering/ROADMAP.md)
- [Accepted architecture decisions](docs/engineering/DECISIONS.md)
- [Architecture explanations](docs/explanation/architecture/README.md)
- [Local development guide](docs/tutorials/local-development.md)
- [Deployment guide](docs/how-to-guides/deploy.md)
- [Environment reference](docs/reference/environment-variables.md)
- [Operations runbooks](docs/runbooks/README.md)

Contributors and coding agents should read [AGENTS.md](AGENTS.md) before changing the repository.
