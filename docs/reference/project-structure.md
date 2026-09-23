# Project Structure

This page describes stable boundaries rather than duplicating every file.

```text
star-warehouse-ai/
├── AGENTS.md                    Repository rules and workflow routing
├── README.md                    Reviewer and developer entry point
├── .env.example                Canonical local environment template
├── docker-compose.yaml         Canonical local application stack
├── docker-compose.monitoring.yml  Optional observability stack
├── start_docker.sh             Canonical full-stack startup and verification
├── start_worker.sh             Host tenant-worker startup
├── app/
│   ├── api/                    FastAPI transport
│   ├── bootstrap/              Guarded local/UAT data reconciliation
│   ├── graph/ agents/ tools/   Conversation orchestration and domain tools
│   ├── services/ adapters/     Application services and business-system ports
│   ├── conversation/           Durable conversation lifecycle
│   ├── task_runtime/ outbox/   Trusted async context, publication, and receipts
│   ├── memory/ retrieval/      PostgreSQL-authoritative memory and Qdrant index
│   ├── storage/                Tenant-aware source-object boundary
│   ├── model_gateway/          Provider-neutral model routing
│   ├── core/                   Configuration, tenancy, database, Redis, security
│   └── observability/ tasks/   Telemetry and Celery handlers
├── frontend/                   React customer and admin applications
├── tests/                      Hermetic backend/integration/policy tests
├── migrations/                 Immutable Alembic revision history
├── scripts/                    Bootstrap, verification, evaluation, and operations
├── data/                       Repository knowledge/product sources and evaluation data
├── deploy/helm/                k3s and production-reference chart
└── docs/
    ├── architecture/           Structural guardrails
    ├── engineering/            State, roadmap, decisions, and execution log
    ├── exec-plans/             Active and completed task plans
    ├── tutorials/              Learning-oriented workflows
    ├── how-to-guides/          Task-oriented guides
    ├── explanation/            Architecture and concept explanations
    ├── reference/              Stable reference material
    └── runbooks/               Operations procedures
```

Use the nearest nested `AGENTS.md` before changing a scoped package. [`README.md`](../../README.md) and [`docs/README.md`](../README.md) are the maintained navigation entry points.
