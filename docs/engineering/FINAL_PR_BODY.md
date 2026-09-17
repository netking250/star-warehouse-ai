# Final Pull Request Body Draft (Prepared; Do Not Submit Yet)

> Local T21 implementation evidence is complete and the branch is ready for external acceptance.
> Hosted PR checks, trusted GHCR publication, provenance attestation, and merge remain pending.
> This draft must not be used to claim hosted or production evidence that has not run.

## T14-T21 scope

This PR consolidates the accepted T14-T20 enterprise-hardening work and T21 final integration,
deterministic evaluation, portfolio evidence, and readiness documentation on the long-lived
`feat/t14-t21-enterprise-hardening` branch. It preserves the modular-monolith boundary and adds no
new business feature, provider dependency, migration, live cloud deployment, release, PR, or merge.

## Architecture

- PostgreSQL is authoritative for tenant and conversation state; RLS, explicit tenant context, and
  application filters provide defense in depth.
- Redis is ephemeral cache/checkpoint/result infrastructure, Qdrant is derived and rebuildable, and
  RabbitMQ is the durable secondary broker behind the PostgreSQL transactional Outbox.
- API, tenant worker, maintenance worker, scheduler, and outbox relay are independently deployable
  process boundaries within one modular monolith.

## Tenant/security model

Tenant-owned requests and tasks use resolver-bound context, transaction-local PostgreSQL tenant
binding, least-privilege runtime/maintenance roles, and namespaced Redis/Qdrant/local-storage
selectors. The browser uses an HttpOnly application-auth cookie, in-memory CSRF, exact trusted
origins, and credential-free WebSocket URLs. Browser requests send no Bearer header, persist no auth
token, and carry no WebSocket query credential; transport guards reject such inputs.

## Async/outbox architecture

State-changing work commits a sanitized task envelope with business state through the transactional
Outbox, then a separate relay publishes to RabbitMQ. Celery workers consume with explicit tenant/task
context, bounded retry/DLQ behavior, and idempotent receipts. The design is at-least-once; global
exactly-once delivery is not claimed.

## AI gateway/failure policy

The provider-neutral Model Gateway normalizes OpenAI, DashScope, and Mock capabilities. T14 owns the
separate bounded retry, ordered fallback, circuit, and safe-degradation policy. Unsafe failures
return structured errors rather than fabricated content. The deterministic T21 evaluation uses no
real provider and makes no live-model linguistic-quality claim.

## Observability

Trace, correlation, task, tenant-safe, queue, and receipt metadata cross API, Outbox, relay, and
worker boundaries. T17 evidence covers 27 metric families, three dashboards, 11 alert rules, and
structured logging; an external production telemetry backend is not claimed.

## CI/supply chain

The protected CI graph retains five attributable gate families: `Brand & docs`, `Backend quality`,
`Backend tests`, `Frontend`, and `Docker smoke`. PR defaults are read-only, checkout credentials do
not persist, and untrusted PRs cannot publish images or create attestations. Trusted `main` and
version-tag runs alone can publish the scanned immutable image to GHCR and attest the image/SBOM.

## Helm/k3s

The canonical chart consumes immutable production image digests, references Secrets without rendering
plain secret values, and keeps workloads non-privileged without host networking, host PID, host paths,
or cluster-admin. The migration Job is the sole `alembic upgrade head` owner; API, worker, scheduler,
and relay workloads only run `alembic current --check-heads`. T19 disposable k3s runtime evidence
remains separate from T21's final 42-resource static render validation.

## Performance

T20's bounded disposable runs averaged 14.46 requests/second with mean p50/p95/p99 of
112.39/412.85/604.75 ms; the two-minute run completed 1,707 requests. These are local bounded
measurements, not production capacity, HA, SLA, or long-soak evidence.

## Backup/restore/DR

T20 demonstrated guarded logical PostgreSQL backup, fresh-target restore, tenant/RLS and async
invariants, and approximately 665 seconds of disposable local RTO. RPO is the latest completed
logical backup. PITR is not implemented, object-storage runtime recovery was not exercised, and
live AWS recovery was not performed.

## Test evidence

- Backend full regression completed with `1848` collected, `1810` passed, `1` historical
  nondeterministic chat timeout failure, `0` errors, `37` skipped, and `81.93%` coverage. The failure
  is `tests/test_chat_api.py::test_chat_timeout_after_answer_closes_without_error`, classified
  `NON_REPRODUCIBLE_PREVIOUS_FAILURE` after T21 `5/5`, T20 `4/5`, and protected `origin/main` `4/5`
  control results with no failing-path code change. No T21 feature regression was demonstrated.
- Frontend frozen install, format check, lint, TypeScript typecheck, Vitest (`12` files, `51` tests),
  and build passed. The meaningful browser suite reported `6/6` tests passed across login, logout,
  401/403 handling, protected routes, T15 transport, and T16 console flows; the Windows Vite runner
  required termination only after test completion during teardown.
- Detached clean-checkout Docker build, dependency startup, migration/role setup, and health passed.
  The image ran as `appuser`, contained no developer residue or `.env`, and used only synthetic
  provider configuration.
- Helm lint/template/schema, strict kubeconform (`42` valid resources), ShellCheck, route inventory
  (`126` HTTP, `2` WebSocket, `0` unclassified), and the bounded final security review passed.
- Provider-free offline evaluation is reused at `12/12` scenarios, with no real provider.

## Known baseline debt

The OpenAI SDK cold-start and Celery fresh-process import timing debts remain historical baseline
limitations. The chat timeout failure above is a separate historical nondeterministic chat-stream
flake and is not the OpenAI/Celery debt.

## Known limitations

Hosted PR proof, trusted GHCR publication proof, provenance/attestation proof, public VM/DNS/
public-CA proof, object-storage runtime recovery, live AWS deployment, and long-soak evidence remain
pending or unperformed. Kubernetes `emptyDir` is not production-safe durable storage. PITR is not
implemented, and production capacity is not claimed. The T18 dependency/image vulnerability baseline
remains visible. See [`KNOWN_LIMITATIONS.md`](KNOWN_LIMITATIONS.md) for the canonical list.

## Verification instructions

1. Review the current state, roadmap, decisions, active T21 plan, execution log, evidence index, and
   known-limitations register.
2. Confirm the five protected hosted check names and their read-only PR defaults in
   `.github/workflows/ci.yml`.
3. Review `.github/workflows/supply-chain.yml` to confirm that image publication and image/SBOM
   attestation are guarded to trusted `main`/version-tag pushes.
4. After external acceptance and the final hosted PR flow only, inspect the trusted image digest,
   GHCR publication, SBOM, and provenance attestation before making release claims.
