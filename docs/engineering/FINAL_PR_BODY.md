# Final Pull Request Body Draft (Blocked, Not Ready to Submit)

> T21 has not passed final integration. Do not use this body to open a PR until the recorded
> `TEST_ENVIRONMENT` blocker is cleared and every omitted final gate is completed.

## Summary

This PR consolidates T14-T21 enterprise hardening on the long-lived
`feat/t14-t21-enterprise-hardening` branch. It preserves the modular monolith while finalizing model
failure policy, secure browser transport, enterprise authorization/compliance UI, cross-runtime
observability, supply-chain controls, digest-pinned Helm/k3s deployment, bounded performance and
logical recovery evidence, and deterministic offline workflow evaluation.

## Architecture and security

- PostgreSQL-authoritative tenant/conversation state with RLS and resolver-bound namespaces.
- Transactional Outbox to RabbitMQ/Celery with explicit task context and idempotent receipts.
- HttpOnly browser session, session-bound CSRF, exact origins, and no WebSocket query token.
- Provider-neutral Model Gateway separated from bounded retry/fallback/degradation policy.
- One Helm migration Job; immutable production image references; secret references, not values.
- Read-only untrusted PR permissions; trusted main/tag-only image publication and attestation.

## Evidence to review

- T14: 1,819 collected; 1,780 passed; two documented timing-baseline failures; 37 skipped; 81.62%
  coverage.
- T17: shared API/outbox/worker trace; 27 metric families; three dashboards; 11 alert rules.
- T18: 255-component SBOM and recorded secret/dependency/image scan results.
- T19: 38 rendered resources plus disposable k3s install/upgrade/rollback evidence.
- T20: bounded average 14.46 requests/second; mean p50/p95/p99
  112.39/412.85/604.75 ms; 1,707-request two-minute run; independent logical restore around 665s.
- T21: final backend/frontend/Docker/Helm/route/migration/security results are recorded in the T21
  execution plan and execution log; provider-free offline evaluation passes 12/12 scenarios.

## Reviewer verification

1. Inspect the final system view, evidence index, known limitations, and accepted decisions.
2. Confirm the five protected hosted check families: `Brand & docs`, `Backend quality`,
   `Backend tests`, `Frontend`, and `Docker smoke`.
3. Run `uv run python -m app.evaluation.offline --dataset data/offline_workflow_eval_v1.jsonl`.
4. Review supply-chain results separately; PRs must not receive package-write or attestation
   authority.
5. After merge only, verify the trusted digest publication, SBOM, GHCR result, and provenance
   attestation before making hosted-release claims.

## Known limitations

OpenAI cold-start and Celery fresh-process import timing debt remain. Vulnerability findings remain
visible. Hosted protected-PR, GHCR, and attestation evidence is pending. Public VM/DNS/CA,
object-storage runtime recovery, PITR, live AWS, long soak, and production capacity/HA were not
proven. See `docs/engineering/KNOWN_LIMITATIONS.md` for the canonical wording.
