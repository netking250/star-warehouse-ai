# Project Structure

This page describes stable repository boundaries rather than duplicating every file.

```text
star-warehouse-ai/
├── AGENTS.md                    Repository rules and workflow routing
├── README.md                    Canonical developer entry point
├── .env.example                Canonical local environment template
├── docker-compose.yaml         Canonical local application stack
├── docker-compose.monitoring.yml  Optional local observability stack
├── Dockerfile                  Shared application image
├── start_docker.sh             Canonical full-stack startup
├── start_worker.sh             Host-process worker startup
├── app/                        Backend modular monolith and runtime roles
│   ├── api/                    FastAPI transport
│   ├── graph/ agents/ tools/   Conversation orchestration and domain tools
│   ├── services/ adapters/     Application services and business-system ports
│   ├── task_runtime/ outbox/   Trusted async context and reliable publication
│   ├── memory/ retrieval/      PostgreSQL-authoritative memory and Qdrant index
│   ├── core/                   Configuration, tenancy, database, Redis, security
│   └── observability/ tasks/   Telemetry and Celery handlers
├── frontend/                   React customer and admin applications
├── tests/                      Backend test suite and isolated fixtures
├── migrations/                 Immutable Alembic revision history
├── scripts/                    Seed, evaluation, monitoring, and maintenance tools
├── data/                       Intentional seed/evaluation datasets
└── docs/
    ├── architecture/           Structural guardrails and focused boundaries
    ├── engineering/            Current state, roadmap, decisions, execution log
    ├── exec-plans/             Active/completed task plans
    ├── tutorials/              Learning-oriented workflows
    ├── how-to-guides/          Task-oriented guides
    ├── explanation/            Architecture and concept explanations
    ├── reference/              Stable reference material
    └── runbooks/               Operations entry points
```

Use the nearest nested `AGENTS.md` before changing a scoped package. The root README and
[`docs/README.md`](../README.md) provide the maintained navigation rather than a generated
full tree.
