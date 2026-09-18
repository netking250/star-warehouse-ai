FROM node:22-slim AS frontend-builder
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./frontend/
ARG NPM_VERSION=11.9.0
RUN npm install --global "npm@${NPM_VERSION}" \
    && cd frontend \
    && npm ci
COPY frontend/ ./frontend/
RUN cd frontend && npm run build

FROM python:3.12-slim

ARG BUILD_VERSION=5.0.0
ARG VCS_REF=unknown
ARG BUILD_TIMESTAMP=unknown
ARG SOURCE_REPOSITORY=https://github.com/netking250/star-warehouse-ai

LABEL org.opencontainers.image.title="Star Warehouse AI" \
      org.opencontainers.image.description="Star Warehouse AI customer-service platform" \
      org.opencontainers.image.version="${BUILD_VERSION}" \
      org.opencontainers.image.revision="${VCS_REF}" \
      org.opencontainers.image.created="${BUILD_TIMESTAMP}" \
      org.opencontainers.image.source="${SOURCE_REPOSITORY}"

# Apply current distribution security updates before installing the application.
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get upgrade -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd -r appgroup && useradd -r -g appgroup appuser

# Install uv
# Pin uv version for reproducible builds. Update manually after testing.
COPY --from=ghcr.io/astral-sh/uv:0.6.5@sha256:562193a4a9d398f8aedddcb223e583da394ee735de36b5815f8f1d22cb49be15 /uv /bin/uv

# Set working directory
WORKDIR /app

# Copy dependency files first for layer caching
COPY pyproject.toml uv.lock README.md ./

# Sync dependencies (no dev packages)
RUN uv sync --frozen --no-dev

# Copy application code
COPY app/ ./app/
COPY alembic.ini ./
COPY migrations/ ./migrations/
COPY data/ ./data/
COPY scripts/ ./scripts/
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

RUN mkdir -p /app/uploads/knowledge \
    && chown -R appuser:appgroup /app
USER appuser

# Ensure the virtual environment is on PATH
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH=/app

# Default command (overridden by Docker Compose services)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
