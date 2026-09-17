# Dependency Failure Recovery

Use this runbook with the T17 dashboards/logs/traces and the T19 deployment. It describes recovery,
not permission to mutate an environment. Confirm the exact cluster, namespace, incident owner, and
data owner before any restart or scale action. T20 fault commands are limited to disposable
`t20-*` namespaces.

## PostgreSQL unavailable

Detect with database error/pool metrics, `/health` degradation, pod events, and correlated API or
worker logs. Stop mutating traffic if false success is suspected. Verify the database pod/service or
managed-service status, storage attachment, and credentials; do not loop infinitely or increase the
pool. Restore connectivity, wait for bounded pool recovery, verify `alembic current --check-heads`,
perform one tenant-scoped read and mutation, and confirm no transaction reported success while
absent. If storage/data integrity is uncertain, stop and follow the DR runbook instead of restarting
repeatedly.

## RabbitMQ unavailable

Inspect Outbox publish failures, pending count/oldest age, relay logs, broker readiness, and queue
depth. Do not mark pending events delivered, purge queues, or delete the broker volume. Restore the
broker, confirm exchanges/queues, resume the relay, and observe Outbox plus ready/unacked depth reach
a stable state. Validate receipt uniqueness for protected work. The guarantee is at-least-once with
idempotent protected effects, never global exactly-once.

## Worker unavailable

Inspect worker readiness/logs, RabbitMQ ready/unacked messages, and task outcome metrics. Restore or
replace the worker without changing ACK settings. Verify unfinished protected work is redelivered,
one completed receipt exists per stable identity, the durable effect occurs once, and the queue
drains. Escalate if a committed message is unrecoverable or the effect duplicates.

## Outbox backlog

Correlate pending count, oldest age, delivery attempts/failures, relay readiness, and RabbitMQ
health. Preserve PostgreSQL rows. Restore the relay or broker, wait a bounded interval, and verify
the same event/idempotency identities publish and settle. Never edit status to `PUBLISHED` manually.
An increasing backlog after dependency recovery is `ASYNC_RECOVERY_FAILURE` evidence.

## Redis unavailable

Redis owns cache, revocation/rate-limit state, provider-circuit coordination, locks, transient
checkpoints, and an optional result backend—not durable business truth. Expect feature-specific
failure or bounded fail-open behavior only where T14 explicitly accepts it. Restore Redis, verify
pool connections and namespace health, require reauthentication if session/revocation certainty is
lost, and confirm PostgreSQL business state is intact. Never restore business facts from Redis.

## Qdrant unavailable

Do not return invented retrieval success. Preserve PostgreSQL knowledge/structured-memory records
and retained knowledge source files. Restore Qdrant, then use the accepted tenant-scoped indexing or
reconciliation path and compare deterministic record/point identities. Core auth/order operations
should recover independently where their contracts do not require Qdrant. Missing source files are
a durable-data incident, not a vector-store repair.

## Provider outage

Use logical-request and provider-attempt metrics plus normalized T14 logs. Do not call real
providers during T20. Confirm retry/attempt/deadline bounds, ordered fallback, circuit state, and
one terminal outcome. A visible streaming delta forbids provider switching. Redis circuit-store
failure may allow only the already accepted bounded attempt; it must not create an unbounded retry.

## Telemetry outage

An optional Collector/backend outage must not roll back or block a business transaction. Confirm
export retry/queue bounds, restore the sink, and verify new telemetry. Absence of telemetry is not
evidence that the business operation failed or succeeded; use PostgreSQL/receipt truth.

## Escalation

Stop recovery and preserve evidence for any lost committed data, duplicate durable effect,
cross-tenant visibility, false-success terminal state, unrecoverable Outbox row, or unbounded
retry/memory/backlog. Do not proceed to another injected failure after any such finding.
