# Quick Start

The canonical local workflow is documented in the root [`README.md`](../../README.md). From a fresh clone:

```bash
cp .env.example .env
# Replace password/SECRET_KEY placeholders, configure LOCAL_BOOTSTRAP_* identities,
# and add a real model/embedding provider key in the ignored .env file.
./start_docker.sh
```

The script builds the stack, migrates PostgreSQL with Alembic, provisions and verifies least-privilege roles, reconciles persisted local/UAT records, indexes repository knowledge, starts all runtime roles, and runs non-secret full-stack verification.

Default endpoints:

- Customer: <http://localhost:8000/app>
- Admin: <http://localhost:8000/admin>
- Health: <http://localhost:8000/health>
- RabbitMQ management: <http://localhost:15672>

Credentials come only from `LOCAL_BOOTSTRAP_*` variables in `.env`. For host-process development, isolated ports, troubleshooting, and safe restart guidance, continue with [Local Development](./local-development.md).
