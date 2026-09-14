# Environment Variable Reference

`.env.example` is the canonical runnable local template. Copy it to the ignored `.env`
file and replace placeholders; never commit real credentials. Application settings are
defined only in `app/core/config.py`. This page classifies the contract and documents
variables owned by Compose, tests, monitoring, and the frontend.

## Required application inputs

These fields have no application default. They must be present in `.env` or the process
environment, although an individual provider key may be empty when another provider is used.

| Area | Variables |
| --- | --- |
| API | `API_V1_STR` |
| PostgreSQL | `POSTGRES_SERVER`, `POSTGRES_PORT`, `POSTGRES_DB`, migration `POSTGRES_USER` / `POSTGRES_PASSWORD`, `POSTGRES_RUNTIME_USER` / `POSTGRES_RUNTIME_PASSWORD`, `POSTGRES_MAINTENANCE_USER` / `POSTGRES_MAINTENANCE_PASSWORD`, `DB_CAPABILITY` |
| Redis | `REDIS_HOST`, `REDIS_PORT`, `REDIS_PASSWORD` |
| Qdrant | `QDRANT_API_KEY` |
| Models | `OPENAI_BASE_URL`, `OPENAI_API_KEY`, `DASHSCOPE_API_KEY`, `RERANK_BASE_URL` |
| Celery | `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND` |
| Security | `SECRET_KEY`, `ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES` |

For a usable local application, configure at least one real model provider credential.
Use a unique PostgreSQL password and `SECRET_KEY` outside an isolated local workstation.

## Infrastructure roles and canonical URLs

```dotenv
POSTGRES_SERVER=localhost
POSTGRES_PORT=5432
POSTGRES_DB=knowledge_base
POSTGRES_USER=postgres
POSTGRES_PASSWORD=<migration-admin-secret>
POSTGRES_RUNTIME_USER=star_warehouse_app
POSTGRES_RUNTIME_PASSWORD=<runtime-secret>
POSTGRES_MAINTENANCE_USER=star_warehouse_ops
POSTGRES_MAINTENANCE_PASSWORD=<maintenance-secret>
DB_CAPABILITY=runtime

REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0

QDRANT_URL=http://localhost:6333
QDRANT_COLLECTION_NAME=knowledge_chunks

RABBITMQ_USER=star_warehouse_ai
RABBITMQ_PASSWORD=dev-rabbitmq-password
CELERY_BROKER_URL=amqp://star_warehouse_ai:dev-rabbitmq-password@localhost:5672//
CELERY_RESULT_BACKEND=redis://:devpassword@localhost:6379/0
```

RabbitMQ is the Celery broker. Redis is used for cache/session/rate-limit/lock/checkpoint
state and may remain the result backend; it is not the task broker. The RabbitMQ value above
is an explicit local-development default, not a production credential.

Inside `docker-compose.yaml`, service-to-service values override host addresses with `db`,
`redis`, `rabbitmq`, and `qdrant`. Host processes use `localhost` and the documented host
ports.

## Optional application settings

Defaults and example values live in `.env.example`. The groups below are the inventory of
optional application-owned settings.

| Area | Variables |
| --- | --- |
| Identity and naming | `PROJECT_NAME`, `SERVICE_NAME`, `ALERT_DEDUP_PREFIX`, `ENVIRONMENT`, `LOCAL_BOOTSTRAP_TENANT_ID` |
| Database roles/pool | `DB_CAPABILITY`, `DB_POOL_SIZE`, `DB_MAX_OVERFLOW`, `DB_POOL_RECYCLE`, `DB_POOL_TIMEOUT`, `DB_CONNECT_TIMEOUT`, `DB_STATEMENT_TIMEOUT` |
| Redis pool/circuit | `REDIS_DB`, `REDIS_MAX_CONNECTIONS`, `REDIS_SOCKET_TIMEOUT`, `REDIS_SOCKET_CONNECT_TIMEOUT`, `REDIS_HEALTH_CHECK_INTERVAL`, `REDIS_RETRY_ON_TIMEOUT`, `REDIS_SOCKET_KEEPALIVE`, `REDIS_CIRCUIT_BREAKER_FAILURE_THRESHOLD`, `REDIS_CIRCUIT_BREAKER_RECOVERY_TIMEOUT`, `REDIS_CIRCUIT_BREAKER_HALF_OPEN_MAX_CALLS` |
| Cache and shadow tests | `CACHE_TTL_INTENT`, `INTENT_CACHE_VERSION`, `CACHE_TTL_PROFILE`, `CACHE_TTL_RETRIEVAL`, `CACHE_TTL_DB_CONFIG`, `SHADOW_TESTING_ENABLED`, `SHADOW_SAMPLE_RATE` |
| Qdrant | `QDRANT_URL`, `QDRANT_COLLECTION_NAME`, `QDRANT_TIMEOUT`, `QDRANT_RETRIES` |
| Models | `LLM_MODEL`, `EMBEDDING_MODEL`, `EMBEDDING_DIM`, `RERANK_MODEL`, `REWRITE_MODEL`, `RERANK_TIMEOUT`, `REWRITE_TIMEOUT`, `REWRITE_CACHE_TTL_SECONDS`, `FASTEMBED_CACHE_PATH` |
| Business adapters | `BUSINESS_ADAPTER_MODE`, `BUSINESS_API_BASE_URL`, `BUSINESS_API_TOKEN`, `BUSINESS_API_ALLOW_INSECURE_HTTP`, `BUSINESS_API_TIMEOUT_SECONDS`, `BUSINESS_API_MAX_RETRIES`, `BUSINESS_API_CIRCUIT_FAILURE_THRESHOLD`, `BUSINESS_API_CIRCUIT_RECOVERY_SECONDS` |
| OIDC/JWT | `OIDC_ENABLED`, `OIDC_PROVIDER_NAME`, `OIDC_ISSUER`, `OIDC_CLIENT_ID`, `OIDC_CLIENT_SECRET`, `OIDC_REDIRECT_URI`, `OIDC_ALLOWED_ALGORITHMS`, `OIDC_LINK_VERIFIED_EMAIL`, `OIDC_STATE_TTL_SECONDS`, `OIDC_METADATA_CACHE_SECONDS`, `OIDC_CLOCK_SKEW_SECONDS`, `OIDC_TIMEOUT_SECONDS`, `OIDC_ALLOW_INSECURE_HTTP`, `JWT_ISSUER`, `JWT_AUDIENCE` |
| Web/API | `ENABLE_OPENAPI_DOCS`, `CORS_ORIGINS`, `WEBSOCKET_HEARTBEAT_INTERVAL`, `WEBSOCKET_RECONNECT_TIMEOUT`, `STATUS_POLLING_INTERVAL`, `CHAT_STREAM_TIMEOUT_SECONDS` |
| Retrieval | `RETRIEVER_DENSE_TOPK`, `RETRIEVER_SPARSE_TOPK`, `RETRIEVER_RRF_K`, `RETRIEVER_FINAL_TOPK`, `RETRIEVER_MULTI_QUERY`, `RETRIEVER_MULTI_QUERY_N` |
| Confidence | All `CONFIDENCE__*` entries in `.env.example` |
| Graph and policy | `MAX_ROUTER_ITERATIONS`, `MAX_EVALUATOR_RETRIES`, `CONFIDENCE_RETRY_THRESHOLD`, `FUNCTION_CALLING_THRESHOLD`, `HIGH_RISK_REFUND_AMOUNT`, `MEDIUM_RISK_REFUND_AMOUNT`, `REFUND_DEADLINE_DAYS`, `NON_REFUNDABLE_CATEGORIES`, `NEGATIVE_WORDS`, `URGENT_WORDS`, `POSITIVE_WORDS` |
| Memory/context | `MEMORY_RETENTION_DAYS`, `MEMORY_CONTEXT_TOKEN_BUDGET`, `HISTORY_CONTEXT_TOKEN_BUDGET`, `COMPACTION_THRESHOLD`, `VECTOR_MEMORY_SCORE_THRESHOLD`, `OBSERVATION_MASKING_MAX_CHARS`, `AGENT_CONFIG_CACHE_TTL`, `CHECKPOINT_SCHEMA_VERSION` |
| Compliance lifecycle | `RETENTION_EXECUTION_ENABLED`, `RETENTION_BATCH_LIMIT`, `RETENTION_TENANT_BATCH_LIMIT` |
| Outbox relay | `OUTBOX_BATCH_SIZE`, `OUTBOX_POLL_INTERVAL_SECONDS`, `OUTBOX_LEASE_SECONDS`, `OUTBOX_RETRY_BASE_SECONDS`, `OUTBOX_RETRY_MAX_SECONDS` |
| Notifications | `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM_EMAIL`, `ALERT_ADMIN_EMAILS`, `ALERT_CSAT_THRESHOLD`, `ALERT_COMPLAINT_WINDOW_HOURS`, `ALERT_COMPLAINT_MAX` |
| Observability | `LOG_FORMAT`, `OTEL_EXPORTER_OTLP_ENDPOINT`, `PROMETHEUS_ENABLED`, `PROMETHEUS_URL`, `TEMPO_URL`, `GRAFANA_URL`, `SERVICE_HEALTH_URL`, `ALERT_TRANSFER_RATE_THRESHOLD`, `ALERT_CONFIDENCE_THRESHOLD`, `ALERT_LATENCY_MS_THRESHOLD` |
| Local storage | `KNOWLEDGE_UPLOAD_DIR` |
| LangSmith | `LANGCHAIN_TRACING_V2`, `LANGSMITH_API_KEY`, `LANGSMITH_PROJECT`, `LANGSMITH_OTEL_ENABLED`, `LANGSMITH_CELERY_TRACING` |

Pydantic list values such as `CORS_ORIGINS`, `ALERT_ADMIN_EMAILS`, and
`NON_REFUNDABLE_CATEGORIES` use JSON array syntax.

## Compose and monitoring-only variables

These are consumed by Compose or provisioned monitoring configuration, not by
`app.core.config.Settings`.

| Variables | Scope |
| --- | --- |
| `RABBITMQ_USER`, `RABBITMQ_PASSWORD` | Local RabbitMQ container and Compose-built broker URLs |
| `KEYCLOAK_DEMO_ADMIN`, `KEYCLOAK_DEMO_ADMIN_PASSWORD`, `KEYCLOAK_DEMO_CLIENT_SECRET`, `KEYCLOAK_DEMO_USER_PASSWORD` | Optional `identity` profile only; all defaults are DEV-ONLY |
| `GRAFANA_ADMIN_USER`, `GRAFANA_ADMIN_PASSWORD`, `GRAFANA_ROOT_URL` | Optional local Grafana container |
| `ALERT_EMAIL_FROM`, `ALERT_WEBHOOK_URL`, `PAGERDUTY_INTEGRATION_KEY`, `SLACK_WEBHOOK_URL` | Monitoring notification/provisioning configuration |

Do not use the local Grafana/RabbitMQ defaults in a shared or production environment.

## Frontend-only variables

`frontend/.env.example` is authoritative for Vite inputs:

- `VITE_API_BASE_URL`
- `VITE_WS_URL`
- `VITE_GRAFANA_URL`
- `VITE_APP_TITLE`

## Test-only variables and isolation

`tests/_db_config.py` applies safe defaults before importing the application:

| Variable | Test behavior |
| --- | --- |
| `TEST_DATABASE_URL` | Optional explicit test PostgreSQL URL; its database name must begin with `test_` |
| `POSTGRES_DB` | Automatically prefixed with `test_` when necessary |
| `REDIS_DB` | Forced to DB 15 |
| `QDRANT_COLLECTION_NAME` | Forced to a process-scoped `test_star_warehouse_ai_*` collection |
| `NO_PROXY`, `no_proxy` | Existing bypass entries are preserved and loopback hosts (`localhost`, `127.0.0.1`, `::1`) are added before application imports so host-process Qdrant traffic stays local |
| `CELERY_BROKER_URL` | Forced to `memory://` for generic tests |
| `CELERY_RESULT_BACKEND` | Forced to `cache+memory://` for generic tests |
| `T04_RABBITMQ_URL` | Enables real broker tests only when it selects a vhost beginning with `test_` |
| `T08_KEYCLOAK_ISSUER`, `T08_KEYCLOAK_CLIENT_SECRET`, `T08_KEYCLOAK_USER_PASSWORD` | Enables the optional real Keycloak discovery/JWKS/signed-token identity test |
| `TEST_LLM_MODEL` | Optional low-cost model override for explicitly marked real-LLM tests |

Tests never require `FLUSHALL`; Redis cleanup must stay inside the selected test DB or a
run-scoped namespace. The generic Redis fixture remains on DB 15. The RedisVL-backed
`redis_checkpointer` fixture uses DB 0 because Redis Search rejects index creation on nonzero
databases, but supplies run-scoped checkpoint and checkpoint-write index/key prefixes and drops
only those indexes during teardown. Qdrant cleanup is limited to test collections; Compose
container processes continue to use the `qdrant` service endpoint while host tests use their
configured local endpoint.

## Production-only requirements

Production configuration is injected by the deployment platform, not committed in an env
file. At minimum:

- replace every local/default password and API-key placeholder;
- set `ENVIRONMENT=production` and `ENABLE_OPENAPI_DOCS=False`;
- set explicit HTTPS origins in `CORS_ORIGINS`;
- do not expose PostgreSQL, Redis, RabbitMQ management, or Qdrant publicly;
- use managed secret storage as described by the accepted deployment decisions.

The production deployment pipeline and reference manifests are roadmap work; this document
does not claim they are already implemented.

## Derived and deprecated names

| Name | Status | Replacement or explanation |
| --- | --- | --- |
| `DATABASE_URL` | Derived, not an input | Built from runtime or maintenance credentials selected by `DB_CAPABILITY` |
| `SYNC_DATABASE_URL` | Derived, not an input | Sync equivalent of the selected application database capability |
| `MIGRATION_DATABASE_URL` | Derived, not an input | Built only from migration/admin `POSTGRES_USER` and `POSTGRES_PASSWORD` |
| `REDIS_URL` | Derived, not an input | Built from `REDIS_HOST`, `REDIS_PORT`, `REDIS_DB`, and `REDIS_PASSWORD` |
| Redis-valued `CELERY_BROKER_URL` | Deprecated | Use the RabbitMQ AMQP URL; `memory://` is allowed only in the explicit test profile |
| `SQLALCHEMY_POOL_SIZE` | Unsupported legacy name | Use `DB_POOL_SIZE` |
| `PAGERDUTY_SERVICE_KEY` | Deprecated monitoring name | Use `PAGERDUTY_INTEGRATION_KEY` |
| `REDIS_POOL_SIZE` | Removed unused name | Use `REDIS_MAX_CONNECTIONS` |
| `REDIS_CIRCUIT_FAILURE_THRESHOLD` | Removed unused name | Use `REDIS_CIRCUIT_BREAKER_FAILURE_THRESHOLD` |
| `REDIS_CIRCUIT_RECOVERY_TIMEOUT` | Removed unused name | Use `REDIS_CIRCUIT_BREAKER_RECOVERY_TIMEOUT` |
| `OIDC_USERINFO_URL` | Removed unsafe compatibility name | Use issuer discovery with `OIDC_ISSUER`; UserInfo-only email matching is not authentication |

Normal databases fail configuration when the selected runtime or maintenance credentials are
missing; only databases explicitly prefixed `test_` may reuse the administrative login for legacy
fixture setup.

Before removing or renaming any variable, search the full repository, including Compose,
CI, scripts, frontend configuration, and monitoring templates.
