# Engineering Evidence Index

| Claim | Stage | Evidence | Limitation |
| --- | --- | --- | --- |
| Tenant identity and isolation | T07, T20 | Resolver-bound context, PostgreSQL RLS tests, namespaced Redis/Qdrant/storage; restore validation included tenant checks | Disposable/local evidence; not a public-cloud tenancy certification |
| Trusted task delivery | T08, T09 | Task envelopes, transactional outbox, concurrent relay, RabbitMQ worker receipts and recovery tests | At-least-once delivery requires idempotent consumers |
| Secure browser transport | T10, T15 | HttpOnly cookie, session-bound CSRF, exact-origin validation, logout and WebSocket transport tests | No independent penetration test |
| Conversation correctness | T12 | PostgreSQL-authoritative turn/run lifecycle, cancellation, ordered events, recovery, idempotency tests | No production workload claim |
| Model routing and failure | T13, T14, T21 | Provider-neutral gateway tests; bounded retry/fallback/degradation tests; 12 provider-free workflow scenarios with 12/12 pass | Mock evaluation is not live-model quality evidence; OpenAI, Celery, and historical chat-stream timing debts remain |
| Authorization and compliance | T11, T16, T21 | Route inventory, current-state RBAC, approval/separation-of-duties, deterministic denial/approval scenarios | Human operating-process maturity is not certified |
| Observability | T17 | Shared API/outbox/worker trace; 27 metric families, three dashboards, 11 alert rules | No long production retention or on-call history |
| CI and supply chain | T18 | Five protected check families; secret/dependency/image scans; 255-component SBOM; trusted publish/attest workflow | Hosted PR, GHCR publication, and attestation proof remain pending; findings remain visible |
| Kubernetes deployment | T19, T21 | T19 38-resource disposable k3s install/upgrade/rollback plus T21 final 42-resource Helm lint/template/schema/kubeconform/ShellCheck validation | Public VM/DNS/CA and live AWS were not proven |
| Performance and backpressure | T20 | Three bounded load runs plus 1,707-request two-minute run; explicit pool/backpressure policy | Not capacity planning, HA, or a long soak |
| Backup and recovery | T20 | Guarded logical backup; independent fresh-target restore around 665 seconds; post-restore tenant and async checks | Latest-backup RPO only; no PITR or object-store runtime recovery |
| Deterministic workflow evaluation | T21 | Versioned 12-scenario synthetic dataset and non-zero regression command | Objective contracts only; linguistic quality is optional/manual live-model work |
| Final integration readiness | T21 | Backend aggregate evidence, locked frontend/browser gates, clean-checkout Docker smoke, 126 application HTTP policy routes with 0 unclassified, final 42-resource Helm render, security spot check, and CI graph review | Hosted PR, trusted GHCR publication, attestation, and external cloud proof remain pending |

Stage-level commands and raw-result summaries remain in
[PROJECT_STATE](../engineering/PROJECT_STATE.md), the
[execution log](../engineering/EXECUTION_LOG.md), and completed
[execution plans](../exec-plans/completed/). These records are evidence of this repository's tests,
not claims of external certification or production operating history.
