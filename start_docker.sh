#!/usr/bin/env bash
# Start the complete local application stack with persisted development/UAT data.

set -Eeuo pipefail

ENV_FILE="${ENV_FILE:-.env}"
COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-star-warehouse-ai}"
APP_HOST_PORT="${APP_HOST_PORT:-8000}"
RABBITMQ_MANAGEMENT_HOST_PORT="${RABBITMQ_MANAGEMENT_HOST_PORT:-15672}"
export APP_ENV_FILE="$ENV_FILE"
export CORS_ORIGINS="${CORS_ORIGINS:-[\"http://localhost:${APP_HOST_PORT}\",\"http://localhost:5173\"]}"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing $ENV_FILE. Copy .env.example to .env and configure it first."
  exit 1
fi

dc() {
  docker compose --project-name "$COMPOSE_PROJECT_NAME" --env-file "$ENV_FILE" "$@"
}

if ! dc version >/dev/null 2>&1; then
  echo "Docker Compose is unavailable. Start Docker Desktop and enable WSL integration."
  exit 1
fi

if ! dc config --quiet; then
  echo "Docker Compose configuration is invalid. Check .env and docker-compose.yaml."
  exit 1
fi

echo "Building the application images..."
dc build app celery_worker celery_maintenance celery_scheduler outbox_relay

echo "Starting PostgreSQL, Redis, RabbitMQ, and Qdrant..."
dc up -d --wait db redis rabbitmq qdrant

echo "Applying database migrations..."
dc run --rm --no-deps app alembic upgrade head

echo "Verifying the single Alembic head and current revision..."
head_output="$(dc run --rm --no-deps app alembic heads)"
head_count="$(printf '%s\n' "$head_output" | grep -c '(head)')"
if [[ "$head_count" -ne 1 ]]; then
  echo "Expected exactly one Alembic head, found $head_count."
  printf '%s\n' "$head_output"
  exit 1
fi
dc run --rm --no-deps app alembic current --check-heads

echo "Provisioning and verifying least-privilege PostgreSQL runtime roles..."
dc run --rm --no-deps app python -m app.core.database_roles

echo "Creating or reconciling persisted local/UAT data and derived vector indexes..."
dc run --rm --no-deps app python -m scripts.bootstrap_local_data

echo "Recreating application containers to refresh WSL bind mounts..."
dc up -d --force-recreate --no-deps celery_worker celery_maintenance celery_scheduler outbox_relay app

echo "Waiting for the API health endpoint..."
for attempt in {1..90}; do
  if curl --fail --silent --show-error --max-time 5 "http://localhost:${APP_HOST_PORT}/health" >/dev/null; then
    echo "Verifying persisted data, tenant boundaries, login sessions, vector retrieval, and async delivery..."
    dc run --rm --no-deps app python -m scripts.verify_local_stack \
      --api-base-url http://app:8000 --browser-origin "http://localhost:${APP_HOST_PORT}"
    echo "Star Warehouse AI is ready."
    dc ps
    echo "Customer UI: http://localhost:${APP_HOST_PORT}/app"
    echo "Admin UI:    http://localhost:${APP_HOST_PORT}/admin"
    echo "Health:      http://localhost:${APP_HOST_PORT}/health"
    echo "RabbitMQ:    http://localhost:${RABBITMQ_MANAGEMENT_HOST_PORT}"
    if grep -Eq '^ENABLE_OPENAPI_DOCS=(True|true|1)$' "$ENV_FILE"; then
      echo "API docs:    http://localhost:${APP_HOST_PORT}/docs"
    fi
    exit 0
  fi
  sleep 1
done

echo "The API did not become healthy. Recent application logs:"
dc logs --tail=100 app
exit 1
