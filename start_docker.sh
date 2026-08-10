#!/usr/bin/env bash
# Start the complete application stack in Docker, including WSL-safe container recreation.

set -Eeuo pipefail

if [[ ! -f .env ]]; then
  echo "Missing .env. Copy .env.example to .env and configure it first."
  exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "Docker Compose is unavailable. Start Docker Desktop and enable WSL integration."
  exit 1
fi

echo "Building the application images..."
docker compose build app celery_worker

echo "Starting PostgreSQL, Redis, and Qdrant..."
docker compose up -d --wait db redis qdrant

echo "Applying database migrations..."
docker compose run --rm --no-deps app alembic upgrade head

echo "Recreating application containers to refresh WSL bind mounts..."
docker compose up -d --force-recreate --no-deps celery_worker app

echo "Waiting for the API health endpoint..."
for attempt in {1..90}; do
  if curl --fail --silent --show-error --max-time 5 http://localhost:8000/health >/dev/null; then
    echo "E-commerce Smart Agent is ready."
    docker compose ps
    echo "Customer UI: http://localhost:8000/app"
    echo "Admin UI:    http://localhost:8000/admin"
    echo "API docs:    http://localhost:8000/docs"
    exit 0
  fi
  sleep 1
done

echo "The API did not become healthy. Recent application logs:"
docker compose logs --tail=100 app
exit 1
