# Architecture Decision Ledger

This ledger records the accepted architecture baseline for the enterprise-hardening phase. Entries are append-only. If a decision changes, add a new entry with `Supersedes: ADR-xxx`; do not rewrite the historical entry.

The existing [`docs/reference/adr.md`](../reference/adr.md) contains earlier product architecture decisions (ADR-001 through ADR-003). Those decisions remain historical context. This ledger records the additional enterprise baseline and its target-state constraints.

## ADR-004 — Modular Monolith and Deployment Boundaries

- **Date:** 2026-09-11
- **Status:** ACCEPTED
- **Supersedes:** None.
- **Context:** The system needs independently operable runtime roles without the cost and risk of a full microservice split.
- **Decision:** Keep a Modular Monolith. API, Celery Worker, Scheduler/Beat, and Outbox Relay are independent deployment boundaries that may scale, configure, monitor, restart, and release independently.
- **Reason:** Preserve local module cohesion and a practical migration path while making operational boundaries demonstrable.
- **Consequences:** Modules require explicit seams and contracts; deployment separation must not become accidental distributed coupling.

## ADR-005 — Progressive Refactoring and Frozen Business Scope

- **Date:** 2026-09-11
- **Status:** ACCEPTED
- **Supersedes:** None.
- **Context:** The existing platform is substantial, so a rewrite or broad feature expansion would increase risk and dilute the portfolio goal.
- **Decision:** Use seam-first, incremental refactoring: establish a stable seam, connect existing code, test, migrate, and narrow legacy responsibilities. Add only capabilities required by the Golden Path; do not introduce CRM, marketing, supply-chain, or unrelated business modules.
- **Reason:** Improve enterprise verifiability without a Big Bang rewrite or scope drift.
- **Consequences:** Temporary compatibility layers are expected and must be documented and tested.

## ADR-006 — Shared-Database Multi-Tenancy

- **Date:** 2026-09-11
- **Status:** ACCEPTED
- **Supersedes:** None.
- **Context:** All business and memory data must be isolated across tenants while retaining a manageable deployment model.
- **Decision:** Use a shared database and shared schema with `tenant_id`, ORM tenant filtering, PostgreSQL Row-Level Security, explicit `TenantContext`, Celery context propagation, Redis tenant namespaces, Qdrant tenant filters, and tenant-scoped object storage paths.
- **Reason:** Defense in depth across application, database, queue, cache, vector, and object-storage boundaries.
- **Consequences:** Tenant context is mandatory at every boundary; missing context is a fail-closed error.

## ADR-007 — Identity and Authorization Separation

- **Date:** 2026-09-11
- **Status:** ACCEPTED
- **Supersedes:** None.
- **Context:** Enterprise access requires both local accounts and federated identity, while identity proof and permissions have different lifecycles.
- **Decision:** Support Local Account and OIDC. Bind federated identities by `issuer + subject`; allow Keycloak as a demo IdP. Keep Authentication, Authorization, and TenantContext distinct. Use RBAC, scopes, tenant membership, route-level authorization policy, session revocation, and audit.
- **Reason:** Make access decisions explicit, testable, and tenant-aware.
- **Consequences:** Every protected route and task entry point must declare the authorization context it needs.

## ADR-008 — Secure Browser Session Boundary

- **Date:** 2026-09-11
- **Status:** ACCEPTED
- **Supersedes:** None.
- **Context:** Browser tokens must not be exposed to script storage or URL logs.
- **Decision:** Use `HttpOnly`, `Secure`, `SameSite` cookies for browser sessions. Add CSRF protection and Origin validation for sensitive operations. Do not use localStorage JWTs or WebSocket URL tokens as the target design.
- **Reason:** Reduce token exfiltration and replay exposure at the browser and transport boundary.
- **Consequences:** Login, logout, refresh, SSE, and WebSocket flows need explicit cookie and CSRF handling.

## ADR-009 — Transactional Outbox and RabbitMQ Async Boundary

- **Date:** 2026-09-11
- **Status:** ACCEPTED
- **Supersedes:** The Redis-as-Celery-broker direction described by older architecture documentation, for the production target only.
- **Context:** Direct post-commit task dispatch can lose side effects when the process fails between database commit and queue publish.
- **Decision:** Use PostgreSQL transaction → Transactional Outbox → Outbox Relay → RabbitMQ → Celery → Idempotency Guard → Task Handler. Redis remains for cache, session/revocation, rate limit, distributed lock, short-lived state, and circuit state.
- **Reason:** Make durable business state and asynchronous delivery recoverable and observable.
- **Consequences:** Relay state, retry, duplicate delivery, and dead-letter handling become first-class concerns. Existing Redis-based local behavior must be migrated deliberately.

## ADR-010 — Explicit Trusted Task Context

- **Date:** 2026-09-11
- **Status:** ACCEPTED
- **Supersedes:** Implicit HTTP ContextVar propagation across Celery process boundaries.
- **Context:** Process boundaries do not preserve request-local context safely.
- **Decision:** Every async task uses an explicit Task Context/Task Envelope containing `tenant_id`, `user_id`, `correlation_id`, `trace_id`, `idempotency_key`, and sanitized payload. The worker validates and rebinds it before handling.
- **Reason:** Prevent tenant leakage, preserve traceability, and support idempotent retries.
- **Consequences:** Task APIs and tests must reject missing or unsafe context; raw request PII must not enter task payloads.

## ADR-011 — Unified Model Gateway

- **Date:** 2026-09-11
- **Status:** ACCEPTED
- **Supersedes:** Direct provider calls spread across agents, for the target architecture.
- **Context:** Provider fallback, cost, policy, and tracing cannot be governed reliably when calls are distributed.
- **Decision:** Route all model calls through a Model Gateway. OpenAI is primary, DashScope is the real fallback, and a Mock Provider serves tests, CI, evaluation, load tests, and fault injection. The gateway owns routing, timeout, retry, fallback, circuit breaker, provider health, token/cost tracking, tracing, audit, and tenant policy.
- **Reason:** Centralize reliability, governance, and evidence.
- **Consequences:** Agents depend on a gateway seam; provider-specific behavior is isolated behind it.

## ADR-012 — Compliance Lifecycle Controls

- **Date:** 2026-09-11
- **Status:** ACCEPTED
- **Supersedes:** None.
- **Context:** PII and sensitive operational data need a demonstrable lifecycle, not only ingress filtering.
- **Decision:** Implement classify → redact → process → store → retain → export → erase → audit, including PII audit, retention, export, erasure, immutable audit, and sensitive-operation confirmation/approval. Describe these as engineering controls; do not claim GDPR, SOC2, or ISO27001 certification.
- **Reason:** Make data handling auditable and truthful.
- **Consequences:** Storage, task payloads, logs, export, deletion, and runbooks need lifecycle evidence.

## ADR-013 — Combined AI Evaluation Strategy

- **Date:** 2026-09-11
- **Status:** ACCEPTED
- **Supersedes:** None.
- **Context:** AI quality cannot be established by a single metric or a single judge.
- **Decision:** Maintain a versioned evaluation dataset covering intent, routing, retrieval, groundedness, tool correctness, safety, PII, latency, token, and cost. Compare baseline and candidate with deterministic evaluators, LLM-as-a-Judge, and human sample review; use the result as a CI gate.
- **Reason:** Combine repeatability, semantic coverage, and human oversight.
- **Consequences:** Dataset versions, evaluator versions, thresholds, and evidence must be tracked.

## ADR-014 — Correlated Observability

- **Date:** 2026-09-11
- **Status:** ACCEPTED
- **Supersedes:** None.
- **Context:** The Golden Path crosses HTTP, model, database, outbox, queue, worker, and human approval boundaries.
- **Decision:** Correlate `request_id`, `trace_id`, `tenant_id`, `conversation_id`, `task_id`, `outbox_event_id`, and `provider_request_id`. Measure RED metrics, queue depth, task age, outbox lag, DLQ, provider health, token/cost, SLO, error budget, alerts, runbooks, and incident evidence.
- **Reason:** Make cross-boundary behavior diagnosable and interview-demonstrable.
- **Consequences:** Correlation identifiers must be carried explicitly and redacted safely.

## ADR-015 — Demo and Production Deployment Profiles

- **Date:** 2026-09-11
- **Status:** ACCEPTED
- **Supersedes:** None.
- **Context:** A low-cost public demo and a production reference have different operational constraints.
- **Decision:** Use Docker Compose locally. Use a low-cost cloud VM with k3s and a Helm demo profile for the public demo. Use AWS EKS with RDS PostgreSQL, ElastiCache Redis, S3, Secrets Manager, load balancing, and OTel/monitoring as the production reference. Treat demo topology as distinct from production topology.
- **Reason:** Keep the demo runnable while documenting an enterprise scaling path.
- **Consequences:** Profiles must be explicit; demo evidence must not be presented as production HA.

## ADR-016 — Supply Chain and Secret Handling Target

- **Date:** 2026-09-11
- **Status:** ACCEPTED
- **Supersedes:** None.
- **Context:** Delivery must protect source, dependencies, images, and runtime credentials.
- **Decision:** Target PR quality gates, backend/frontend/integration/evaluation tests, SAST, secret and dependency scans, Docker build, SBOM, image scan/signing, staging smoke/E2E, approval, production health verification, and rollback. Keep local secrets in `.env.example` guidance only; use GitHub Environment/OIDC in CI, encrypted k3s secrets for demo, and AWS Secrets Manager plus External Secrets in production.
- **Reason:** Make delivery and secret controls verifiable without committing credentials.
- **Consequences:** The target pipeline is broader than the current CI and must be implemented by later tasks.

## ADR-017 — Expand/Backfill/Contract Database Evolution

- **Date:** 2026-09-11
- **Status:** ACCEPTED
- **Supersedes:** Any destructive reset approach for enterprise changes.
- **Context:** Enterprise schema changes must preserve data and support compatibility during rollout.
- **Decision:** Keep the existing Alembic history and use Expand → Backfill → Compatibility → Switch → Contract. Never delete and recreate the database to avoid migration work.
- **Reason:** Support rollback, staged deployment, and data safety.
- **Consequences:** Migration plans require compatibility windows and verification evidence.

## ADR-018 — Frontend Extension and High-Fidelity Business Sandboxes

- **Date:** 2026-09-11
- **Status:** ACCEPTED
- **Supersedes:** None.
- **Context:** The current frontend and business adapters are valuable working assets, but the Golden Path needs enterprise evidence.
- **Decision:** Extend the existing frontend with an Enterprise Console for Overview, AI, Operations, Security, and Compliance. Do not comprehensively rewrite the frontend. Use high-fidelity sandbox adapters for order, inventory, logistics, CRM-like dependencies, and other external business systems; they must simulate latency, timeout, 401, 429, 500, missing data, not found, and duplicate requests.
- **Reason:** Preserve the current product while making failure and control paths demonstrable.
- **Consequences:** New UI and adapter work must remain within the frozen business scope.

## ADR-019 — Explicit Non-Goals

- **Date:** 2026-09-11
- **Status:** ACCEPTED
- **Supersedes:** None.
- **Context:** Enterprise hardening can expand indefinitely without explicit boundaries.
- **Decision:** Do not proactively introduce full microservices, Kafka, multi-region, commercial SaaS billing, SCIM, complex SAML federation, four or five model providers, vLLM/GPU inference, full SOC2/ISO27001 certification, a full frontend rewrite, many new agents, Argo CD, or complete GitOps. These require a future explicit Change Request.
- **Reason:** Protect delivery focus and keep claims evidence-based.
- **Consequences:** Requests outside this boundary must be documented before implementation.

## ADR-020 — Disaster Recovery and Restore Verification

- **Date:** 2026-09-11
- **Status:** ACCEPTED
- **Supersedes:** None.
- **Context:** The public demo and production reference need credible recovery evidence while operating at different topology and cost levels.
- **Decision:** The Demo profile requires real automated backups and a Restore Test. The Production Reference requires high availability (HA) and point-in-time recovery (PITR), with explicitly defined RPO and RTO targets. Both profiles require a Restore Runbook and recovery verification evidence. Demo and Production may use different topologies and cost tiers.
- **Reason:** Make recoverability demonstrable without presenting a low-cost demo as production-grade infrastructure.
- **Consequences:** Later disaster-recovery work must produce backup, restore, RPO/RTO, runbook, and recovery-verification evidence for the relevant profile.

## ADR-021 — Architecture Guardrails and Evidence-Bound Enterprise Claims

- **Date:** 2026-09-11
- **Status:** ACCEPTED
- **Supersedes:** None.
- **Context:** Continuous task-by-task hardening can create duplicate seams, reverse dependencies, expand known debt, or let documentation claims outrun implementation.
- **Decision:** Use [`docs/architecture/ARCHITECTURE_GUARDRAILS.md`](../architecture/ARCHITECTURE_GUARDRAILS.md) as the structural rule source for T02–T21. New and changed code follows inward source dependencies, explicit async/tenant/transaction boundaries, provider Ports, non-fail-open trust decisions, immutable released migrations, and real-seam tests. Enterprise claims require implementation, test, and recorded evidence; otherwise they are labeled target, reference architecture, planned, or partial.
- **Reason:** Keep progressive modular-monolith refactoring reviewable, enforceable, and truthful without introducing a heavy architecture framework.
- **Consequences:** Confirmed legacy violations remain mapped `CURRENT_DEBT` until their owning task and may not spread. Structural changes must update guardrails and scoped `AGENTS.md` only when the rule or local workflow materially changes.

## ADR-022 — PostgreSQL-Authoritative Structured Memory

- **Date:** 2026-09-12
- **Status:** ACCEPTED
- **Supersedes:** The direct PostgreSQL/Qdrant summary dual-write behavior; it does not supersede ADR-009 or ADR-010.
- **Context:** A Qdrant upsert could succeed after a PostgreSQL flush and before the database transaction later rolled back, leaving a vector with no authoritative record.
- **Decision:** PostgreSQL is the source of truth for structured memory and Qdrant is a derived index. A memory command writes the structured record or tombstone and a minimal versioned Outbox event in one database transaction. The reliable consumer reloads authoritative content by tenant and memory ID, then applies a stable-ID Qdrant upsert or delete. Duplicate external execution is allowed and safe; stale versions are ignored. No distributed transaction or global exactly-once guarantee is claimed.
- **Reason:** Preserve atomic business intent while allowing Qdrant outages, retries, duplicate delivery, and reconciliation without orphaning authoritative state.
- **Consequences:** Structured-memory writers must not call Qdrant directly. Events contain identity/version/operation rather than memory text. Reads retain PostgreSQL memory and explicitly mark vector recall degraded when Qdrant fails. Conversation-turn vector writes remain a documented compatibility path outside structured-memory commands.
