# RabbitMQ and Reliable Celery

T04 makes RabbitMQ the Celery broker. Redis remains available for cache, session/revocation, rate limits, short-lived coordination, and an optional Celery result backend; it is not the task broker. The verified runtime versions are Celery 5.6.3, Kombu 5.6.2, and RabbitMQ 3.13.

## Delivery Flow and Queues

```text
business transaction -> outbox -> relay -> RabbitMQ -> Celery worker
                                            |
                                            +-> critical.dlq
```

`critical` carries protected refund workflows and required knowledge indexing, `default` carries ordinary work, and `maintenance` carries system schedules. Workers do not consume `critical.dlq`; it retains persistent, sanitized terminal evidence for explicit operator tooling. The DLQ includes task/envelope identity, tenant, idempotency, correlation/trace, attempt, and a bounded failure code/reason without logging the full payload.

## Protected Consumer Transaction

For database-local critical handlers, `consume_db_task` validates the trusted `TaskEnvelope`, binds tenant and trace context, takes a PostgreSQL transaction advisory lock on `(tenant_id, handler, idempotency_key)`, and performs the business effect plus `COMPLETED` receipt in one transaction. A completed duplicate returns the stored result and does not replay the business effect. A `PROCESSING` receipt has an expiring lease, so stale work can be reclaimed rather than skipped forever.

Transient failures use bounded exponential backoff with deterministic jitter and a finite task retry limit. Validation, tenant, unsupported-state, and other classified permanent failures do not loop. Exhausted or permanent messages publish terminal evidence to RabbitMQ's DLQ before the original delivery returns successfully. If DLQ publication fails, the original delivery is rejected with requeue enabled so terminal intent is not silently lost.

Critical refund tasks use late acknowledgement, worker-loss rejection/redelivery, prefetch one, time limits, and failure/timeout acknowledgement disabled. Other tasks retain narrower policies rather than inheriting these settings globally.

## Guarantees and External Providers

- Business data plus outbox event: atomic PostgreSQL transaction.
- Outbox publication: at-least-once.
- Protected database-local handler: duplicate-safe for the stable receipt identity.
- Global exactly-once: not claimed.

An external provider call can still complete immediately before a worker crash. If the provider accepts an idempotency key, adapters must pass the stable envelope key. Where a provider has no idempotency facility, the truthful guarantee remains an at-least-once request with best-available deduplication; duplicate external effects remain possible.

RabbitMQ credentials come from environment configuration. Compose binds AMQP and the management UI to loopback for local development only; production must not publish the management port.
