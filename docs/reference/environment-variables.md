# Environment Variable Reference

[`app/core/config.py`](../../app/core/config.py) defines application settings. [`.env.example`](../../.env.example) is the canonical runnable local template; copy it to ignored `.env`, replace placeholders, and never commit real credentials.

Labels used below:

- **Required local core**: needed by the canonical local workflow.
- **Optional**: has a safe default or is feature-specific.
- **Development-only**: must not be used as a production credential/control.
- **Production-sensitive**: inject from approved secret storage outside local development.

## Required Local Core

| Variables | Classification | Purpose |
| --- | --- | --- |
| `ENVIRONMENT` | Required; production-sensitive | Selects environment safety policy; local bootstrap refuses `production` |
| `API_V1_STR` | Required | API prefix, normally `/api/v1` |
| `POSTGRES_*` credentials | Required; production-sensitive | Migration owner plus runtime and maintenance logins |
| `REDIS_PASSWORD` | Required; production-sensitive | Redis authentication |
| `QDRANT_API_KEY` | Required by current settings; production-sensitive | Qdrant authentication |
| `RABBITMQ_USER`, `RABBITMQ_PASSWORD`, `CELERY_BROKER_URL` | Required; production-sensitive | RabbitMQ and Celery transport |
| `CELERY_RESULT_BACKEND` | Required; production-sensitive | Optional Redis-backed task results |
| `SECRET_KEY` | Required; production-sensitive | JWT/session and CSRF signing |
| One runtime model key | Feature-dependent; production-sensitive | `OPENAI_API_KEY` or `DASHSCOPE_API_KEY` for real chat |

Provider keys may be empty for provider-free health/auth/database tests. Semantic chat and real embedding/retrieval require a valid configured provider.

## PostgreSQL

| Variables | Required | Notes |
| --- | --- | --- |
| `POSTGRES_SERVER`, `POSTGRES_PORT`, `POSTGRES_DB` | Yes | Host processes use loopback; Compose overrides the server to `db` |
| `POSTGRES_USER`, `POSTGRES_PASSWORD` | Yes | Migration and role-provisioning owner; application traffic must not use it |
| `POSTGRES_RUNTIME_USER`, `POSTGRES_RUNTIME_PASSWORD` | Yes | API/tenant-worker `NO BYPASSRLS` login |
| `POSTGRES_MAINTENANCE_USER`, `POSTGRES_MAINTENANCE_PASSWORD` | Yes | Explicit maintenance/outbox login |
| `DB_CAPABILITY` | Yes | `runtime` or `maintenance`; controls which least-privilege login is selected |
| `DB_POOL_SIZE`, `DB_MAX_OVERFLOW`, `DB_POOL_RECYCLE`, `DB_POOL_TIMEOUT` | Optional | Async pool controls |
| `DB_CONNECT_TIMEOUT`, `DB_STATEMENT_TIMEOUT` | Optional | Connection and statement bounds |
| `POSTGRES_HOST_PORT` | Development-only | Compose loopback host mapping; container port stays `5432` |

`DATABASE_URL`, `SYNC_DATABASE_URL`, and `MIGRATION_DATABASE_URL` are derived settings, not input variables.

## Redis

| Variables | Required | Notes |
| --- | --- | --- |
| `REDIS_HOST`, `REDIS_PORT`, `REDIS_DB`, `REDIS_PASSWORD` | Yes | Cache, session revocation, rate limits, locks, carts, and checkpoints |
| `REDIS_MAX_CONNECTIONS`, `REDIS_SOCKET_TIMEOUT`, `REDIS_SOCKET_CONNECT_TIMEOUT` | Optional | Pool/network limits |
| `REDIS_HEALTH_CHECK_INTERVAL`, `REDIS_RETRY_ON_TIMEOUT`, `REDIS_SOCKET_KEEPALIVE` | Optional | Connection behavior |
| `REDIS_CIRCUIT_BREAKER_FAILURE_THRESHOLD`, `REDIS_CIRCUIT_BREAKER_RECOVERY_TIMEOUT`, `REDIS_CIRCUIT_BREAKER_HALF_OPEN_MAX_CALLS` | Optional | Circuit policy |
| `REDIS_HOST_PORT` | Development-only | Compose loopback mapping |

Redis is ephemeral runtime state, not the source of truth for users, orders, knowledge metadata, outbox events, or task receipts.

## RabbitMQ and Async Runtime

| Variables | Required | Notes |
| --- | --- | --- |
| `RABBITMQ_USER`, `RABBITMQ_PASSWORD` | Local Compose | Creates the local broker account |
| `CELERY_BROKER_URL` | Yes | AMQP URL; URL-encode special characters |
| `CELERY_RESULT_BACKEND` | Yes | May use Redis; RabbitMQ remains the broker |
| `OUTBOX_BATCH_SIZE`, `OUTBOX_POLL_INTERVAL_SECONDS` | Optional | Relay throughput/polling |
| `OUTBOX_LEASE_SECONDS`, `OUTBOX_RETRY_BASE_SECONDS`, `OUTBOX_RETRY_MAX_SECONDS` | Optional | Relay lease/retry policy |
| `RABBITMQ_HOST_PORT`, `RABBITMQ_MANAGEMENT_HOST_PORT` | Development-only | Loopback AMQP/UI mappings |

## Qdrant and Knowledge

| Variables | Required | Notes |
| --- | --- | --- |
| `QDRANT_URL`, `QDRANT_API_KEY` | Yes | Derived vector/search service |
| `QDRANT_COLLECTION_NAME`, `QDRANT_TIMEOUT`, `QDRANT_RETRIES` | Optional | Collection and client policy |
| `KNOWLEDGE_UPLOAD_DIR` | Optional | Tenant-scoped local source-object compatibility store |
| `QDRANT_HTTP_HOST_PORT`, `QDRANT_GRPC_HOST_PORT` | Development-only | Loopback mappings |

Qdrant points are always generated through the knowledge/product ingestion path. Do not seed arbitrary vectors.

## Model Gateway and Retrieval

| Variables | Required | Notes |
| --- | --- | --- |
| `OPENAI_API_KEY`, `MODEL_OPENAI_BASE_URL`, `OPENAI_BASE_URL` | Provider-specific | OpenAI-compatible runtime route |
| `DASHSCOPE_API_KEY`, `MODEL_DASHSCOPE_BASE_URL` | Provider-specific | DashScope/Bailian runtime route |
| `MODEL_ROUTES` | Optional | Ordered, capability-declared restart-on-change route configuration |
| `MODEL_GATEWAY_DEFAULT_TIMEOUT_SECONDS` | Optional | Default gateway timeout |
| `EMBEDDING_BASE_URL`, `EMBEDDING_API_KEY`, `EMBEDDING_MODEL`, `EMBEDDING_DIM` | Knowledge | Dense embedding configuration; dedicated key falls back to `DASHSCOPE_API_KEY` |
| `RERANK_BASE_URL`, `RERANK_MODEL`, `RERANK_TIMEOUT` | Retrieval | Reranker endpoint/model |
| `REWRITE_MODEL`, `REWRITE_TIMEOUT`, `REWRITE_CACHE_TTL_SECONDS` | Retrieval | Query rewrite behavior |
| `RETRIEVER_DENSE_TOPK`, `RETRIEVER_SPARSE_TOPK`, `RETRIEVER_RRF_K`, `RETRIEVER_FINAL_TOPK` | Optional | Hybrid retrieval bounds |
| `RETRIEVER_MULTI_QUERY`, `RETRIEVER_MULTI_QUERY_N` | Optional | Multi-query mode |
| `FASTEMBED_CACHE_PATH` | Optional | Local model cache location |
| `RUN_REAL_LLM_TESTS`, `REAL_LLM_TEST_ROUTE` | Test opt-in | Paid/network test gate; false by default |

The proven Beijing compatible-mode base URL is:

```text
https://dashscope.aliyuncs.com/compatible-mode/v1
```

The `MODEL_FAILURE_*` variables in `.env.example` define bounded retry, deadline, circuit, and degradation behavior. They are server policy, not request overrides.

## Security and Browser Session

| Variables | Required | Notes |
| --- | --- | --- |
| `SECRET_KEY`, `ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES` | Yes | Token/session signing and lifetime |
| `BROWSER_AUTH_COOKIE_NAME`, `BROWSER_AUTH_COOKIE_SECURE`, `BROWSER_AUTH_COOKIE_SAMESITE` | Yes | HttpOnly browser transport |
| `BROWSER_POST_LOGIN_REDIRECT_PATH` | Optional | Browser redirect |
| `JWT_ISSUER`, `JWT_AUDIENCE` | Yes | Token audience controls |
| `CORS_ORIGINS` | Yes | JSON array of exact trusted browser origins |
| `ENABLE_OPENAPI_DOCS` | Optional | Must be false in production |

Production requires secure cookies, HTTPS origins, a unique high-entropy secret, and disabled OpenAPI unless explicitly approved.

## Local Bootstrap

Every variable in this group is **development-only**. None may silently create identities in production.

| Variable | Required when enabled | Purpose |
| --- | --- | --- |
| `LOCAL_BOOTSTRAP_ENABLED` | Yes | Explicit opt-in; must be `true` |
| `LOCAL_BOOTSTRAP_TENANT_ID`, `LOCAL_BOOTSTRAP_TENANT_NAME` | Yes | Local/UAT tenant identity |
| `LOCAL_BOOTSTRAP_CUSTOMER_USERNAME`, `LOCAL_BOOTSTRAP_CUSTOMER_PASSWORD`, `LOCAL_BOOTSTRAP_CUSTOMER_EMAIL` | Yes | Customer bootstrap identity |
| `LOCAL_BOOTSTRAP_ADMIN_USERNAME`, `LOCAL_BOOTSTRAP_ADMIN_PASSWORD`, `LOCAL_BOOTSTRAP_ADMIN_EMAIL` | Yes | Operator bootstrap identity |

Passwords must be at least 12 characters, are hashed through the real user model, and are never logged. The bootstrap refuses `ENVIRONMENT=production` even if enabled.

## Optional OIDC

`OIDC_ENABLED`, `OIDC_PROVIDER_NAME`, `OIDC_ISSUER`, `OIDC_CLIENT_ID`, `OIDC_CLIENT_SECRET`, `OIDC_REDIRECT_URI`, `OIDC_ALLOWED_ALGORITHMS`, `OIDC_LINK_VERIFIED_EMAIL`, `OIDC_STATE_TTL_SECONDS`, `OIDC_METADATA_CACHE_SECONDS`, `OIDC_CLOCK_SKEW_SECONDS`, `OIDC_TIMEOUT_SECONDS`, and `OIDC_ALLOW_INSECURE_HTTP` control enterprise identity.

`KEYCLOAK_DEMO_*` variables are development-only Compose inputs for the optional `identity` profile. They are not production defaults.

## Business, Graph, Memory, and Compliance

| Group | Variables |
| --- | --- |
| Business adapters | `BUSINESS_ADAPTER_MODE`, `BUSINESS_API_BASE_URL`, `BUSINESS_API_TOKEN`, `BUSINESS_API_ALLOW_INSECURE_HTTP`, `BUSINESS_API_TIMEOUT_SECONDS`, `BUSINESS_API_MAX_RETRIES`, `BUSINESS_API_CIRCUIT_FAILURE_THRESHOLD`, `BUSINESS_API_CIRCUIT_RECOVERY_SECONDS` |
| Cache/shadow | `CACHE_TTL_*`, `INTENT_CACHE_VERSION`, `SHADOW_TESTING_ENABLED`, `SHADOW_SAMPLE_RATE` |
| Graph/policy | `MAX_ROUTER_ITERATIONS`, `MAX_EVALUATOR_RETRIES`, `CONFIDENCE_RETRY_THRESHOLD`, `FUNCTION_CALLING_THRESHOLD`, `HIGH_RISK_REFUND_AMOUNT`, `MEDIUM_RISK_REFUND_AMOUNT`, `REFUND_DEADLINE_DAYS`, `NON_REFUNDABLE_CATEGORIES` |
| Confidence | all `CONFIDENCE__*` variables in `.env.example` |
| Memory/context | `MEMORY_RETENTION_DAYS`, `MEMORY_CONTEXT_TOKEN_BUDGET`, `HISTORY_CONTEXT_TOKEN_BUDGET`, `COMPACTION_THRESHOLD`, `VECTOR_MEMORY_SCORE_THRESHOLD`, `OBSERVATION_MASKING_MAX_CHARS`, `AGENT_CONFIG_CACHE_TTL`, `CHECKPOINT_SCHEMA_VERSION` |
| Compliance | `RETENTION_EXECUTION_ENABLED`, `RETENTION_BATCH_LIMIT`, `RETENTION_TENANT_BATCH_LIMIT` |
| Chat/WebSocket | `CHAT_STREAM_TIMEOUT_SECONDS`, `WEBSOCKET_HEARTBEAT_INTERVAL`, `WEBSOCKET_RECONNECT_TIMEOUT`, `STATUS_POLLING_INTERVAL` |

Pydantic list values use JSON array syntax.

## Observability and Notifications

| Group | Variables |
| --- | --- |
| OpenTelemetry/logging | `LOG_FORMAT`, `OTEL_EXPORTER_OTLP_ENDPOINT`, `OTEL_SERVICE_NAME` |
| Prometheus/Grafana | `PROMETHEUS_ENABLED`, `PROMETHEUS_URL`, `TEMPO_URL`, `GRAFANA_URL`, `GRAFANA_ROOT_URL`, `GRAFANA_ADMIN_USER`, `GRAFANA_ADMIN_PASSWORD` |
| LangSmith | `LANGCHAIN_TRACING_V2`, `LANGSMITH_API_KEY`, `LANGSMITH_PROJECT`, `LANGSMITH_OTEL_ENABLED`, `LANGSMITH_CELERY_TRACING` |
| Alerting | `ALERT_*`, `SMTP_*`, `PAGERDUTY_INTEGRATION_KEY`, `SLACK_WEBHOOK_URL`, `SERVICE_HEALTH_URL` |

Monitoring passwords, webhook URLs, API tokens, and provider keys are production-sensitive.

## Compose Host Ports and Alternate Env Files

These are development orchestration inputs, not application settings:

- `APP_HOST_PORT`
- `POSTGRES_HOST_PORT`
- `REDIS_HOST_PORT`
- `RABBITMQ_HOST_PORT`
- `RABBITMQ_MANAGEMENT_HOST_PORT`
- `QDRANT_HTTP_HOST_PORT`
- `QDRANT_GRPC_HOST_PORT`
- `ENV_FILE` for `start_docker.sh`; it is exported to Compose as `APP_ENV_FILE`
- `COMPOSE_PROJECT_NAME` for an isolated set of containers and volumes

All default infrastructure mappings are loopback-only.

## Frontend-Only Variables

[`frontend/.env.example`](../../frontend/.env.example) owns `VITE_API_BASE_URL`, `VITE_WS_URL`,
`VITE_GRAFANA_URL`, and `VITE_APP_TITLE`. It also documents the server-side, development-only
`DEV_API_PROXY_TARGET` override used when the host API does not listen on port 8000.

## Test Isolation

[`tests/_db_config.py`](../../tests/_db_config.py) applies test-safe settings before application import:

- PostgreSQL database names must start with `test_`.
- Redis uses DB 15 or run-scoped namespaces.
- Qdrant uses a process-scoped test collection.
- Generic Celery tests use in-memory broker/results.
- Real RabbitMQ tests require an explicitly isolated `test_` vhost.
- Real model tests require explicit `RUN_REAL_LLM_TESTS=true`.

Local/UAT bootstrap data is never a unit-test dependency.

## Deprecated or Derived Names

| Name | Status | Replacement |
| --- | --- | --- |
| `DATABASE_URL`, `SYNC_DATABASE_URL`, `MIGRATION_DATABASE_URL`, `REDIS_URL` | Derived | Configure their component variables |
| Redis-valued `CELERY_BROKER_URL` | Deprecated | Use RabbitMQ AMQP; `memory://` is test-only |
| `SQLALCHEMY_POOL_SIZE` | Unsupported legacy | `DB_POOL_SIZE` |
| `PAGERDUTY_SERVICE_KEY` | Deprecated | `PAGERDUTY_INTEGRATION_KEY` |
| `REDIS_POOL_SIZE` | Removed | `REDIS_MAX_CONNECTIONS` |
| `REDIS_CIRCUIT_FAILURE_THRESHOLD` | Removed | `REDIS_CIRCUIT_BREAKER_FAILURE_THRESHOLD` |
| `REDIS_CIRCUIT_RECOVERY_TIMEOUT` | Removed | `REDIS_CIRCUIT_BREAKER_RECOVERY_TIMEOUT` |
| `OIDC_USERINFO_URL` | Removed unsafe compatibility | Issuer discovery through `OIDC_ISSUER` |

Before deleting or renaming any variable, search application code, Compose, CI, scripts, frontend configuration, monitoring, and deployment templates.
