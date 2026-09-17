# Operations Runbooks

This directory is the canonical operations entry point for currently documented response
procedures. It does not claim production readiness, 24x7 staffing, or completed disaster
recovery controls.

- [Alert response](./alert-response.md) — alert triage and escalation workflow.
- [Incident response](./incident-response.md) — incident roles, severity, containment, and recovery.
- [Compliance lifecycle](./compliance-lifecycle.md) — retention, approval/export, audit-write,
  and emergency-stop response.
- [Troubleshooting](../how-to-guides/troubleshoot.md) — local service and dependency checks.
- [Local monitoring](../how-to-guides/deploy.md#optional-local-monitoring-implemented) — optional Compose profile and service boundaries.

- [Observability](./observability.md) - T17 metrics, logs, traces, alerts, and correlation response.
- [Dependency failure recovery](./dependency-failures.md) - PostgreSQL, RabbitMQ, worker, Outbox,
  Redis, Qdrant, provider, and telemetry degradation/recovery.
- [Backup, restore, and disaster recovery](./disaster-recovery.md) - data criticality, guarded
  logical backup/restore, tenant validation, async recovery, and truthful RTO/RPO/PITR claims.
- [Performance and resilience validation](../how-to-guides/performance-resilience.md) - bounded k6
  profiles, measurements, backpressure, fault matrix, and evidence procedure.

Current implementation/evidence status is recorded in
[`docs/engineering/PROJECT_STATE.md`](../engineering/PROJECT_STATE.md). Accepted operational
targets are recorded in [`docs/engineering/DECISIONS.md`](../engineering/DECISIONS.md).
