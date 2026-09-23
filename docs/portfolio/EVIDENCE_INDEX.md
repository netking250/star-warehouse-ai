# Engineering Evidence Index

Canonical baseline: [Final Acceptance](../engineering/FINAL_ACCEPTANCE.md), accepted
main `f852a8f2ce0f82fa6157d8bd72b0d1a1f8a1da40`. The [roadmap](../engineering/ROADMAP.md)
has final task states; the [execution log](../engineering/EXECUTION_LOG.md) and
[completed plans](../exec-plans/completed/) preserve stage-level commands and results.

| Reviewer topic | Direct repository evidence | Claim boundary |
| --- | --- | --- |
| Architecture | [Decisions](../engineering/DECISIONS.md), [final system view](../explanation/architecture/final-system-view.md), [T21 plan](../exec-plans/completed/T21.md) | Modular-monolith reference implementation |
| Tenant context and PostgreSQL RLS | [Tenancy design](../architecture/TENANCY.md), [T07 plan](../exec-plans/completed/T07.md) | Implemented and tested; no cloud certification |
| Identity, auth, browser security | [Identity](../architecture/ENTERPRISE_IDENTITY.md), [authorization](../architecture/AUTHORIZATION.md), [secure session](../architecture/SECURE_BROWSER_SESSION.md) | No independent penetration test |
| Outbox, RabbitMQ, Celery, idempotency | [Outbox](../explanation/architecture/transactional-outbox.md), [task runtime](../explanation/architecture/task-runtime.md), [reliable Celery](../explanation/architecture/reliable-celery.md) | At-least-once delivery |
| Durable conversation, memory, multi-turn | [Conversation plan](../exec-plans/completed/T12.md), [memory flow](../explanation/architecture/system-flows/memory-loading.md), [UAT FIX-4B](../exec-plans/completed/P-UAT-03-FIX-4B.md) | Tested scoped state/continuation contracts |
| Model Gateway and failure policy | [Gateway](../explanation/architecture/model-gateway.md), [T13](../exec-plans/completed/T13.md), [T14](../exec-plans/completed/T14.md) | Bounded retry/fallback/circuit behavior |
| RAG, retrieval, and knowledge | [Policy RAG flow](../explanation/architecture/system-flows/policy-rag.md), [knowledge sync](../explanation/architecture/system-flows/knowledge-sync.md), [P-UAT-02-FIX](../exec-plans/completed/P-UAT-02-FIX.md) | Real Qdrant local/UAT evidence |
| Refund approval boundary | [Refund audit flow](../explanation/architecture/system-flows/refund-audit.md), [UAT FIX-3](../exec-plans/completed/P-UAT-03-FIX-3.md) | Human approval required before side effect |
| Real-provider product UAT | [Final acceptance](../engineering/FINAL_ACCEPTANCE.md#3-product-uat), [execution log](../engineering/EXECUTION_LOG.md) | 30/30 first attempt on frozen synthetic Bailian corpus only |
| UI V1.1 | [UI-04 plan](../exec-plans/completed/UI-04.md), [roadmap](../engineering/ROADMAP.md#v11-enterprise-visual-experience-upgrade) | Accepted visual/responsive/accessibility evidence |
| Fresh V1.2 bootstrap | [Bootstrap plan](../exec-plans/completed/V1.2-BOOTSTRAP-01.md), [final acceptance](../engineering/FINAL_ACCEPTANCE.md#5-bootstrap-v12) | Disposable full bootstrap, second run, restart; synthetic data |
| Main CI and Docker smoke | [CI design](../explanation/architecture/ci-quality.md), [final acceptance](../engineering/FINAL_ACCEPTANCE.md#6-hosted-ci) | 1,920 backend pass, 63 unit pass, one Playwright retry; Docker smoke excludes business bootstrap |
| Container security and dependency debt | [Supply-chain guide](../how-to-guides/ci-supply-chain.md), [known limitations](../engineering/KNOWN_LIMITATIONS.md) | Zero CRITICAL under policy; 81 HIGH image findings, 9 frontend HIGH |
| SBOM, trusted GHCR, SLSA provenance | [Final acceptance](../engineering/FINAL_ACCEPTANCE.md#8-supply-chain), [T18 plan](../exec-plans/completed/T18.md) | CycloneDX 1.6/255 components; provenance subject matches published digest |
| Observability | [Observability design](../explanation/architecture/observability.md), [T17 plan](../exec-plans/completed/T17.md) | No production retention or on-call history |
| Helm/k3s and AWS reference | [Deployment design](../explanation/architecture/deployment.md), [k3s guide](../how-to-guides/k3s-deployment.md), [T19 plan](../exec-plans/completed/T19.md) | Disposable k3s validated; AWS reference only |
| Performance and disaster recovery | [Performance guide](../how-to-guides/performance-resilience.md), [DR runbook](../runbooks/disaster-recovery.md), [T20 plan](../exec-plans/completed/T20.md) | Bounded runs and logical restore; no production SLA/PITR |
| Limitations and claim scope | [Known limitations](../engineering/KNOWN_LIMITATIONS.md), [case study](CASE_STUDY.md) | No live production, customers, or universal AI-quality claim |

The immutable image digest, SBOM hashes, and provenance match are recorded in
[Final Acceptance](../engineering/FINAL_ACCEPTANCE.md#8-supply-chain). These are
repository and hosted-workflow results, not external certification or evidence
of production-scale operation.
