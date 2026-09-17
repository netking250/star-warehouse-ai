# T20 Performance and Resilience Validation

This guide runs bounded, environment-qualified checks against the canonical T19 deployment. It is
not a production capacity certification. All destructive examples require a disposable `t20-*`
namespace and the Mock provider or provider-free paths; never supply real OpenAI or DashScope keys.

## Safety preflight

Record these facts before every run:

```text
production touched = NO
persistent developer data touched = NO
cluster/namespace = <explicit disposable identifiers>
database = <explicit disposable identifier>
cleanup owner = <operator>
```

Then inspect, rather than assume, the target:

```bash
kubectl config current-context
kubectl get namespace t20-implement
kubectl get pods,pvc -n t20-implement
```

Do not continue if the context, namespace, Secret, storage class, or data ownership is ambiguous.
The scripts reject `prod`/`production` names and fault injection additionally requires a `t20-*`
namespace plus `T20_DESTRUCTIVE_CONFIRM=YES_DISPOSABLE_ONLY`.

## Load profiles

The only concurrent HTTP load framework is k6, pinned by the wrapper to `grafana/k6:0.57.0` when a
local binary is unavailable. The default is deliberately small.

```bash
TARGET_ENVIRONMENT=t20-local \
BASE_URL=http://127.0.0.1:18000 \
./scripts/t20-run-load.sh

TARGET_ENVIRONMENT=t20-local \
BASE_URL=http://127.0.0.1:18000 \
T20_PROFILE=BASELINE \
T20_HEAVY_OPT_IN=YES \
T20_TENANT_ID=demo \
T20_USERNAME=t20_load \
T20_PASSWORD='<disposable-secret>' \
./scripts/t20-run-load.sh
```

Run `BASELINE` three times without changing replicas, data, resources, or host conditions. Compare
request rate, failure rate, p50, p95, and p99 from ignored `reports/t20/` summaries. A repeatable,
large change requires investigation; no latency value in this guide is a contractual SLA. The
`SOAK_SHORT` profile is three VUs for two minutes and is only a smoke for obvious monotonic growth.

### Dataset

Use synthetic tenant-local users and representative orders/conversations. The IMPLEMENT evidence
records exact counts. Do not use copied customer data or create millions of rows. Login occurs once
per k6 run; steady traffic exercises `/health` and authenticated `/api/v1/me`. This measures the
HTTP/authentication/database/Redis path, not external model latency.

## Measurements

Capture the existing T17 signals before, during, and after each bounded run:

| Concern | Existing signal or query |
| --- | --- |
| HTTP throughput/errors/latency | `http_requests_total`, `http_request_duration_seconds` and k6 summary |
| API/worker CPU and memory | `kubectl top pod -n <namespace>` when Metrics Server is available; otherwise container stats |
| Database pool/query pressure | `database_pool_*`, `database_query_duration_seconds`, `database_errors_total` |
| Outbox | `outbox_events_pending`, `outbox_event_oldest_age_seconds`, delivery attempts/latency/failures |
| Worker | bounded `celery_task_events_total`; RabbitMQ ready/unacked message counts |
| Conversation | run lifecycle/duration/terminal counters |
| AI Mock | logical request duration/count and provider attempt duration/count |
| Correlation | T17 JSON `correlation_id`, returned `X-Trace-ID`, and matching trace when the sink is available |

Record process/container memory before, peak, and after the two-minute short soak. The only valid
passing statement is `NO_OBVIOUS_LEAK`; a short soak cannot prove leak freedom. Do not increase pool
sizes, worker concurrency, replicas, timeouts, or limits to improve a disposable score.

## Async and backpressure procedure

Use one accepted T03/T04 transaction that creates a protected Outbox event. Keep the worker active
and pause only the relay for a bounded burst:

```bash
NAMESPACE=t20-implement TARGET_ENVIRONMENT=t20-local \
T20_DESTRUCTIVE_CONFIRM=YES_DISPOSABLE_ONLY \
./scripts/t20-inject-failure.sh pause-relay
```

Create the deterministic synthetic transactions, record Outbox pending count/oldest age, then
resume the relay and observe RabbitMQ ready/unacked depth plus receipt completion:

```bash
NAMESPACE=t20-implement TARGET_ENVIRONMENT=t20-local \
T20_DESTRUCTIVE_CONFIRM=YES_DISPOSABLE_ONLY \
./scripts/t20-inject-failure.sh resume-relay
```

The gate passes only when committed event identities are preserved, the backlog drains, protected
receipt uniqueness prevents duplicate durable effects, and no Outbox row is falsely marked
published while RabbitMQ is unavailable. At-least-once publication may duplicate an attempt; it
must not duplicate the protected database effect.

## Deterministic failure matrix

Inject one row at a time under low bounded traffic, restore it, wait no longer than the documented
timeout, and verify recovery before starting the next row.

| Scenario | Injection | Expected degradation | Required recovery evidence |
| --- | --- | --- | --- |
| API pod | `restart-api` | With one replica, brief unavailability is expected; two replicas may continue | replacement Ready, bounded traffic resumes |
| Worker | `restart-worker` with queued protected work | unacknowledged work remains recoverable/redeliverable | one durable business effect, receipt completed, queue drained |
| Scheduler | `restart-scheduler` | schedules pause briefly; singleton only | exactly one scheduler Ready; no HA claim |
| Relay | `pause-relay` | business commit succeeds; Outbox backlog/age rises | `resume-relay`, published backlog drains |
| PostgreSQL | `outage-postgresql` | explicit API/worker database errors; no success | `restore-postgresql`, pool reconnects, invariant remains |
| Redis | `outage-redis` | cache/session/rate-limit/circuit/checkpoint features may fail or degrade | restart, pool recovers; no business-data corruption |
| RabbitMQ | `outage-rabbitmq` | relay failure/retry visible; Outbox remains pending | broker returns, publication resumes, receipts remain unique |
| Qdrant | `outage-qdrant` | retrieval/memory recall errors or explicit degradation; no fake retrieval success | restart/reindex path works; unrelated core operations recover |
| Mock provider | focused T14 integration scenario | bounded retry/fallback/circuit/degradation | one logical terminal outcome; finite provider attempts |
| Telemetry sink | stop only disposable/optional sink | business transaction continues; exporter queue/retry bounded | sink returns and telemetry resumes |

Use `restore-*` immediately after each dependency outage. The wrapper never deletes namespaces,
PVCs, queues, databases, or cloud resources. See [Dependency Failure Recovery](../runbooks/dependency-failures.md).

## Evidence recording

Record the runtime/cluster versions, allocated host CPU/RAM, pod replicas/requests/limits, exact
dataset, profile, three summaries, resource samples, failure timestamps, recovery timestamps, and
cleanup. Commit only the concise summary in the active T20 plan; raw dumps, logs, credentials, and
k6 JSON remain outside Git.

## Measured T20 IMPLEMENT baseline

This is an environment-specific baseline, not a production capacity statement. It was measured on
2026-09-17 in disposable single-node k3d `5.9.0` / k3s `v1.35.5+k3s1`, with one API replica, one
tenant worker, one maintenance worker, one singleton scheduler, and one singleton relay. The node
had 7.38 GiB available to Docker. The synthetic dataset contained two tenants, two users, 125
orders, 10 conversations/runs, 20 runtime events, and two PII-audit sentinels.

| Run | Requests | Requests/s | Success | p50 | p95 | p99 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| BASELINE 1 | 537 | 14.57 | 100% | 115.34 ms | 333.25 ms | 543.89 ms |
| BASELINE 2 | 547 | 14.41 | 100% | 108.90 ms | 475.32 ms | 717.85 ms |
| BASELINE 3 | 527 | 14.42 | 100% | 112.94 ms | 429.99 ms | 552.52 ms |

Mean throughput was 14.46 requests/s with 0.5% coefficient of variation. Mean p50/p95/p99 were
112.39/412.85/604.75 ms; p95/p99 coefficients of variation were 14.4%/13.2%. `SOAK_SHORT`
completed 1,707 requests in two minutes at 13.71 requests/s with zero HTTP failures and
109.14/185.64/451.60 ms p50/p95/p99. Node samples were 29-128% CPU and 2.24-2.32 GiB resident use;
post-load PostgreSQL used 9/100 server connections (one runtime idle and two maintenance idle).
The bounded run showed `NO_OBVIOUS_LEAK`; it is not formal leak proof.

The failure drill produced 10 pending Outbox events with the relay paused and five RabbitMQ
`critical` messages with the worker paused. Every one completed after recovery, receipt keys stayed
unique, and the queue/backlog drained to zero. A three-event broker outage left all rows non-
published until RabbitMQ returned. PostgreSQL, Redis, and Qdrant outages were visible through
degraded health or explicit request failure and recovered after the dependency returned.

The logical backup was restored into a fresh disposable PostgreSQL target after the source
namespace and PVCs were deleted. The first drill correctly exposed non-portable checksum paths and
missing restored ACLs; the corrected procedure was repeated into another fresh database and passed
checksum, archive listing, fixed-role, RLS, application login, tenant isolation (100 tenant-A rows,
zero tenant-B visibility, 25 tenant-B rows), business/audit invariants, and post-restore Outbox
processing. Database restore took 6 seconds; restore through API readiness took approximately 80
seconds in this disposable environment. The tested RPO is the selected completed logical backup;
PITR is not implemented.
