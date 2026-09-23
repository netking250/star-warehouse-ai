# Startup Flow

```mermaid
flowchart LR
    C[Docker Compose] --> P[(PostgreSQL)]
    C --> R[(Redis)]
    C --> M[(RabbitMQ)]
    C --> Q[(Qdrant)]
    P --> A[FastAPI]
    R --> A
    Q --> A
    M --> W[Celery worker]
    P --> O[Outbox relay]
    O --> M
    S[Celery scheduler] --> M
    A --> H[/health]
```

The canonical complete local flow is `./start_docker.sh`:

1. Build the shared application image.
2. Start and wait for `db`, `redis`, `rabbitmq`, and `qdrant`.
3. Apply `alembic upgrade head`, verify the single current head, and provision/connect through
   the runtime and maintenance database roles.
4. Run the production-guarded, idempotent `scripts.bootstrap_local_data` reconciliation for
   persisted local/UAT business data, source objects, and derived Qdrant indexes.
5. Start independent tenant worker, maintenance worker, scheduler, outbox relay, and API roles.
6. Verify health, browser logins, RLS/user ownership, Redis, known Qdrant retrieval, and the
   PostgreSQL outbox → RabbitMQ → Celery → task-receipt flow.

For host-process development, follow the
[local development guide](../../tutorials/local-development.md).
