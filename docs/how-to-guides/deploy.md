# Deployment Profiles

本页是部署边界的权威入口。当前仓库可直接执行的是本地 Docker Compose profile；
公开 demo 的 k3s/Helm 和 AWS EKS production reference 是已接受的目标架构，不能在实现和
验证完成前描述为现有能力。

## Local Docker Compose (implemented)

```bash
cp .env.example .env
# Replace local placeholders before starting.
./start_docker.sh
```

Canonical Compose: `docker-compose.yaml`.

| Service | Responsibility |
| --- | --- |
| `db` | PostgreSQL primary relational store |
| `redis` | Cache/session/rate-limit/lock/checkpoint state and optional result backend |
| `rabbitmq` | Celery broker |
| `qdrant` | Vector index |
| `app` | FastAPI and built frontend |
| `celery_worker` | Async execution |
| `celery_scheduler` | Beat scheduling |
| `outbox_relay` | PostgreSQL outbox publication boundary |

Docker Compose uses service discovery names inside its network and project-scoped container
names. PostgreSQL, Redis, RabbitMQ, Qdrant, and local monitoring ports bind to loopback;
the API remains exposed on port 8000.

## Optional local monitoring (implemented)

```bash
docker compose -f docker-compose.monitoring.yml config
./scripts/deploy-monitoring.sh
```

This separate Compose file is intentional because the monitoring stack has its own lifecycle.
It provisions Prometheus/Mimir, Grafana, Loki/Promtail, Tempo, the OpenTelemetry Collector, and
Alertmanager with loopback-only host ports. Set `OTEL_EXPORTER_OTLP_ENDPOINT` to
`http://host.docker.internal:4317` in the application `.env` before starting API/worker roles if
you want container traces to reach the Collector. Prometheus scrapes the API `/metrics` endpoint;
logs are collected from container stdout. The local alert receivers are no-op sinks and contain no
external notification credentials.

The canonical Grafana dashboards are **Platform / API Health**, **Async / Outbox / Worker**, and
**AI / Conversation Runtime**. Use the T17 [observability runbook](../runbooks/observability.md)
for alert triage and metrics → logs → traces correlation.

## Demo and production reference (planned)

Accepted architecture decisions target:

- low-cost k3s/Helm for a public demo profile;
- AWS EKS plus managed PostgreSQL, Redis, object storage, and secret management as a
  production reference.

Those manifests and delivery gates belong to later roadmap tasks. Do not treat local Compose
as a production topology. See [ADR-015 and ADR-016](../engineering/DECISIONS.md).

## Non-local checklist

- Replace every local/default credential; never commit `.env`.
- Set `ENABLE_OPENAPI_DOCS=False` and explicit HTTPS `CORS_ORIGINS`.
- Do not publish database, Redis, RabbitMQ management, Qdrant, or monitoring admin ports.
- Run Alembic forward migrations; never rewrite released revisions.
- Operate API, worker, scheduler, and outbox relay as independent runtime roles.
