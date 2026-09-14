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
3. Apply `alembic upgrade head` and initialize missing bundled vector data.
4. Start independent `celery_worker`, `celery_scheduler`, `outbox_relay`, and `app` roles.
5. Wait for <http://localhost:8000/health>.

For host-process development, follow the
[local development guide](../../tutorials/local-development.md).
