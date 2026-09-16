# Deployment Profiles

This is the canonical entry point for running Star Warehouse AI outside local development. The
application remains one modular monolith packaged as one image and run as independently scalable
API, Celery worker, maintenance worker, scheduler, and transactional-outbox relay processes.

## Profiles

| Profile | Purpose | Data services | Evidence level |
| --- | --- | --- | --- |
| Docker Compose | Local development | Local PostgreSQL, Redis, RabbitMQ, and Qdrant | Implemented local profile |
| k3s + Helm | Low-cost public demo | Single-node in-cluster demo dependencies with PVCs, or operator-supplied endpoints | Implemented chart; real-VM proof is recorded separately |
| AWS reference | Production design reference | RDS PostgreSQL, ElastiCache-compatible Redis, Amazon MQ for RabbitMQ, and managed/self-hosted Qdrant | Reference architecture, not live AWS evidence |

The Helm chart is [`deploy/helm/star-warehouse-ai`](../../deploy/helm/star-warehouse-ai). It does
not clone source, install dependencies, or build an image on the cluster host.

## Local Docker Compose

```bash
cp .env.example .env
# Replace local placeholders before starting.
./start_docker.sh
```

Canonical Compose is `docker-compose.yaml`. Infrastructure host ports are loopback-only; this is
not the production topology. The optional T17 monitoring stack remains separately managed by
`docker-compose.monitoring.yml` and `scripts/deploy-monitoring.sh`.

## Image and registry contract

GHCR is the canonical reference registry: `ghcr.io/netking250/star-warehouse-ai`. Pull requests
build and scan but never publish. On a trusted `main` or `v*` tag push, the supply-chain workflow
uploads the exact scanned image archive to a trusted publication job, publishes `sha-<commit>` and
optionally the immutable release tag, records the registry digest, and attests that digest. It
never publishes `latest`.

Production Helm rendering requires `image.digest=sha256:<64 hex characters>`. A tag-only local
override is available only when `productionMode=false` and `image.allowMutableTag=true`. The k3s
deployment script requires `IMAGE_DIGEST` unless the operator explicitly opts into the local
mutable-image smoke switch. The Dockerfile's OCI source, version, and revision labels plus the pod
revision annotation answer which source commit is running.

Hosted GHCR publication and attestation must be proven by the final trusted T21 run. T19 does not
publish an image from this feature branch.

## Required runtime Secret

The chart never creates a production Secret and never renders secret values. Create the Secret
out of band. For k3s, enable k3s secrets encryption at rest before storing credentials and verify
its status using the operator-controlled k3s procedure. Kubernetes base64 encoding alone is not
encryption.

Required keys in `star-warehouse-ai-runtime`:

| Key | Classification | Required behavior |
| --- | --- | --- |
| `POSTGRES_PASSWORD` | Core | Migration/role-provisioning database credential |
| `POSTGRES_RUNTIME_PASSWORD` | Core | NO BYPASSRLS API and tenant-worker credential |
| `POSTGRES_MAINTENANCE_PASSWORD` | Core | Explicit maintenance/relay credential |
| `REDIS_PASSWORD` | Core | Redis authentication |
| `QDRANT_API_KEY` | Core | Qdrant authentication; may be demo-scoped |
| `CELERY_BROKER_URL` | Core | RabbitMQ URL with URL-encoded credentials |
| `CELERY_RESULT_BACKEND` | Core | Redis result-backend URL |
| `SECRET_KEY` | Core | Unique high-entropy application signing secret |
| `RABBITMQ_USER`, `RABBITMQ_PASSWORD` | Demo infrastructure only | In-cluster RabbitMQ bootstrap |
| `OPENAI_API_KEY`, `DASHSCOPE_API_KEY` | Feature-dependent | May be empty for infrastructure smoke; never placed in ConfigMap |
| `OIDC_CLIENT_SECRET` | Feature-dependent | Required only when OIDC is enabled |
| `BUSINESS_API_TOKEN`, `SMTP_PASSWORD`, `LANGSMITH_API_KEY` | Feature-dependent | Required only for the corresponding integration |

The current settings model expects the two provider key names even when their values are empty.
An empty value supports health, login, deployment, and other provider-free smoke; it does not make
AI chat functional. Mock-provider unit/evaluation paths remain credential-free, but the production
composition root does not select the Mock adapter.

Create a local ignored `.env.k3s.local` with mode `0600`, then create the Secret without putting
values in shell arguments:

```bash
kubectl --namespace star-warehouse-ai create secret generic star-warehouse-ai-runtime \
  --from-env-file=.env.k3s.local \
  --dry-run=client -o yaml | kubectl apply -f -
```

Delete the local file securely after use according to operator policy. For production, use AWS
Secrets Manager plus External Secrets (or an equivalent approved provider) to create the same
Kubernetes Secret keys. Secret rotations require an explicit workload restart because the chart
does not hash or expose Secret values in pod annotations.

Private registries are supported through `image.pullSecrets`; credentials stay in a referenced
Kubernetes image-pull Secret.

## Migration ownership

One revision-scoped Kubernetes Job is the only migration owner. It uses the same immutable
application image as the workloads, executes `alembic upgrade head`, provisions the configured
NO BYPASSRLS runtime/maintenance roles, grants those two logins read-only access to the migration
status table, and fails the Helm operation if any step fails. Every
new workload has a non-mutating `alembic current --check-heads` init check, so it cannot become
Ready before the release Job reaches the current head. API pods never run migrations. The Job is
bounded by an active deadline and Kubernetes-managed retry budget; Helm's `--wait-for-jobs`
preserves failure visibility.

An application rollback deploys a prior schema-compatible image/chart revision. `helm rollback`
does not run `alembic downgrade`, delete PVCs, or restore a database snapshot. Formal backup,
restore, RPO/RTO, and disaster-recovery evidence belongs to T20.

## Configuration and browser security

Non-secret settings are in the chart ConfigMap; credentials come from `secretRef.name`. Production
sets secure cookies, exact HTTPS CORS origin(s), HTTPS OIDC redirect, no insecure OIDC transport,
and disabled OpenAPI docs. Do not use wildcard CORS. The browser continues to use the HttpOnly
session cookie and in-memory CSRF value; it does not store a bearer token or put one in a WebSocket
URL. Public browser connections therefore use `https` and `wss`, and WebSocket Origin validation
sees the configured public origin.

The API command trusts forwarded headers from the cluster ingress. Limit direct network reachability
to the ClusterIP service so untrusted clients cannot supply proxy headers directly.

## Ingress and TLS

Only the API has a Kubernetes Service. PostgreSQL, Redis, RabbitMQ, Qdrant, and T17 operational
interfaces are cluster-internal. The k3s profile reuses its default Traefik controller; it does not
install a second controller. Traefik supports WebSocket upgrades and streaming by default. Keep
the controller's bounded response timeouts longer than the accepted 45-second application stream
timeout when changing cluster defaults. The public Ingress enumerates application, static, API,
WebSocket, and health paths instead of routing a catch-all prefix, so `/metrics` remains reachable
through the ClusterIP service for Prometheus but is not Internet-routed.

The production-reference values show ingress-nginx settings that disable response buffering for
SSE, permit 20 MiB request bodies, and set bounded 120-second read/send timeouts. Controller-
specific annotations can be replaced for an AWS Load Balancer Controller deployment. Do not add
an ingress rate limit that conflicts with application policy.

TLS is a Secret reference, never a committed key. Provision `star-warehouse-ai-tls` manually,
through cert-manager, or through the chosen AWS ingress/ACM integration. HTTP-only rendering is
for isolated local chart tests; `productionMode=true` refuses an ingress without TLS.

## Probes, shutdown, and resources

- API startup checks `/health`; readiness parses the body and requires core PostgreSQL, Redis, and
  Qdrant dependencies to be healthy; liveness checks only the serving socket. Model-provider
  availability is not part of readiness or liveness.
- Worker, maintenance worker, scheduler, and relay liveness checks verify their PID 1 process.
  They do not expose fake HTTP servers or restart on a transient dependency failure.
- API receives a five-second pre-stop drain and 45-second termination window. Celery workers use a
  300-second window aligned with the existing hard task limit. Scheduler and relay receive 30
  seconds; the relay already handles SIGTERM through its stop event.
- Resource requests/limits are conservative starter values only. They are not measured production
  capacity. T20 owns load and capacity evidence.

All application containers run non-root with RuntimeDefault seccomp, no privilege escalation, and
all Linux capabilities dropped. Their root filesystems are read-only; bounded `emptyDir` volumes
cover `/tmp`, model cache, and transient uploads. Service-account token automounting is disabled,
and the chart creates no Role, ClusterRole, or binding.

## Observability

Set `config.OTEL_EXPORTER_OTLP_ENDPOINT` to the T17 Collector gRPC endpoint. Each process overrides
`OTEL_SERVICE_NAME` with a bounded API/worker/maintenance/scheduler/outbox identity. Structured
logs remain on stdout/stderr, Prometheus metrics remain on the API `/metrics` endpoint, and no
second monitoring stack is installed by the chart. See the
[observability runbook](../runbooks/observability.md).

## Stateful-data boundary

The demo dependencies use PVCs and are never deleted by deployment scripts. They are not backups
or production HA. The application still has an accepted local-upload compatibility path and no
active S3 object-store adapter; the chart mounts transient upload storage only. The AWS reference
maps the future tenant-scoped object-store Port to S3, but does not falsely claim current upload
durability. Do not enable multi-replica knowledge uploads until that application contract is
implemented and verified. T20 owns backup/restore testing, not this chart.

## Validation and rollout history

```bash
./scripts/validate-helm.sh
helm history star-warehouse-ai --namespace star-warehouse-ai
helm status star-warehouse-ai --namespace star-warehouse-ai
kubectl rollout status deployment/star-warehouse-ai-api --namespace star-warehouse-ai
```

`validate-helm.sh` lints and renders default, demo, and production-reference profiles; exercises
missing-digest and forbidden-`latest` failures; performs client-side Kubernetes validation; and
scans manifests for privileged/host access, cluster-admin, plaintext Secret objects, and public
infrastructure exposure. It does not contact a cloud provider or rebuild an image.

See the [k3s deployment guide](k3s-deployment.md) and
[deployment architecture](../explanation/architecture/deployment.md) for installation and AWS
mapping.
