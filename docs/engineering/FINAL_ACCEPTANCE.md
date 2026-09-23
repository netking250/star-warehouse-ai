# Final Acceptance Baseline

## 1. Final repository baseline

PR [#15](https://github.com/netking250/star-warehouse-ai/pull/15) merged through protected
rebase at `2026-09-23T09:37:32Z`. The accepted main commit is
`f852a8f2ce0f82fa6157d8bd72b0d1a1f8a1da40`, with one Alembic head,
`f0a1b2c3d4e5`. The package remains `5.0.0`; V1.2 names a project change
baseline, not a new semantic release. PROJECT-CLOSEOUT-01 reconciles documents
and awaits its own external acceptance.

## 2. Architecture acceptance

**IMPLEMENTED and TESTED:** A FastAPI modular monolith with independently runnable
API, workers, scheduler, and outbox relay; PostgreSQL-authoritative business and
conversation state; explicit request/task tenant context; PostgreSQL RLS;
transactional outbox; RabbitMQ/Celery delivery with idempotent receipts; a
provider-neutral Model Gateway and bounded failure policy; retrieval, memory,
observability, and human refund approval boundaries. The [decisions](DECISIONS.md)
and [architecture guide](../explanation/architecture/final-system-view.md) define
the accepted design. At-least-once delivery is not global exactly-once delivery.

## 3. Product UAT

**VALIDATED:** P-UAT-03 passed 30/30 cases on the frozen synthetic real-provider
Bailian corpus, all on the first attempt: knowledge 6/6, paraphrase 4/4,
no-answer 4/4, multi-turn 4/4, tool/workflow 4/4, approval/handoff 2/2,
security/tenant 4/4, and general UX 2/2. Average usability was 4.10/5.
The measured hard gates were zero cross-thread/user/tenant leaks, unauthorized
side effects, material no-answer hallucinations, system-prompt or secret
disclosures, and approval bypasses. This corpus does not establish universal
model accuracy. See the [execution log](EXECUTION_LOG.md).

## 4. UI V1.1

**IMPLEMENTED and VALIDATED:** CR-UI-01 was accepted: UI-01/02/03
`PASS_WITH_NOTES`, UI-04 `PASS`. The final Light/Dark design system includes
Star Warehouse identity, a branded opening, eight-page Admin redesign, Customer
login/chat, responsive/mobile behavior, reduced motion, accessibility fixes,
and corrected frontend copy without a new animation/design runtime dependency.
Apple was visual inspiration only; no affiliation is claimed.

## 5. Bootstrap V1.2

**IMPLEMENTED and VALIDATED:** CR-PROJECT-02 was accepted. `./start_docker.sh`
uses Alembic-authoritative schema and least-privilege database roles, then runs
the guarded local bootstrap. Disposable verification proved persisted synthetic
tenant/accounts/orders/business records, Qdrant indexing, Redis ephemeral-state
and RabbitMQ/Celery/outbox paths, Customer/Admin login, tenant/RLS/cross-user
isolation, a second bootstrap without duplication, and restart persistence.
These are local/UAT records, not real customer data. Hosted Docker smoke separately
covers image build, migration, roles, API startup, and health; it does not run the
complete business-data bootstrap.

## 6. Hosted CI

**TESTED on accepted main:** Brand & docs, Backend quality, Backend tests,
Frontend, and Docker smoke all succeeded. Backend: 1,957 collected; 1,920
passed; zero failed or errors; 37 skipped; 81.85% coverage. Quality passed
lockfile, exactly one Alembic head (`f0a1b2c3d4e5`), Ruff, format, and ty.
Frontend unit tests passed 63/63. Playwright succeeded with 13 normal passes
and one test passing on retry after transient browser-console 502 responses.

## 7. Security and tenant controls

**IMPLEMENTED and TESTED:** Resolver-bound context, tenant-filtered application
queries, transaction-local PostgreSQL RLS, least-privilege roles, authorization
and refund approval, HttpOnly session cookie, session-bound CSRF, exact origins,
and tenant-safe async envelopes. These controls have test evidence; they are not
an independent certification or proof that the system is fully secure.

## 8. Supply chain

**VALIDATED on trusted main:** Secret, dependency, image, critical-policy,
SBOM, publication, provenance, and Python/JavaScript CodeQL jobs succeeded.
The blocking image policy found zero CRITICAL findings, 81 HIGH findings, 37
with known fixes; CVE-2026-63374 was absent. Nine frontend dependency HIGH
findings remain recorded. The trusted image is
`ghcr.io/netking250/star-warehouse-ai:sha-f852a8f2ce0f82fa6157d8bd72b0d1a1f8a1da40` at
`sha256:fcdf1953843618d23509f32aa5c0e805e97fd5439d5fc384989cbf4fff9429d1`.
Its OCI revision matches main. CycloneDX JSON 1.6 lists 255 components; SBOM
file SHA-256 is `8d9b1a54d1c0154e2356f1100f1cae29e84193bed5ca693cb318714b4474e995`.
The supply-chain artifact archive SHA-256 is
`44cf06693fe65d9656167f3c6fd18a88ff5286c70bc774f058d62d01a502b990`,
with 14-day retention. Trusted SLSA provenance succeeded; its image subject
digest equals the published digest above. PR publication/provenance stayed skipped.

## 9. Deployment evidence

**VALIDATED:** A disposable k3s install/upgrade/rollback and final 42-resource
Helm render; bounded local load and guarded logical backup/fresh-target restore.
**REFERENCE ONLY:** AWS architecture and production Helm values.
**NOT DEPLOYED:** Live production, AWS, public VM/DNS/certificate, or real
customer data. Trusted GHCR artifact publication is not a production deployment.

## 10. Known limitations

The [limitation register](KNOWN_LIMITATIONS.md) records HIGH vulnerability debt,
the retrying frontend E2E test, bounded UAT scope, incomplete tracking-number
proof in a later smoke, and absent production SLA, long soak, PITR, production
S3, and public infrastructure evidence.

## 11. Evidence links

Start with the [roadmap](ROADMAP.md), [append-only execution log](EXECUTION_LOG.md),
[completed plans](../exec-plans/completed/), [portfolio evidence index](../portfolio/EVIDENCE_INDEX.md),
[case study](../portfolio/CASE_STUDY.md), and [interview guide](../interview/ENGINEERING_GUIDE.md).

## Branch and release closeout inventory

No branch or release was deleted or created by this closeout. Rebase changed
commit IDs, so the content checks below compare each source tip tree with its
accepted rebased main milestone, not only `git branch --merged`.

| Branch | Tip | Accepted main tree match | Cleanup candidate after external acceptance |
| --- | --- | --- | --- |
| `feat/ui-v1.1-enterprise-visual` | `edfd5577b9ca9ccc3ef6c5ea20b971b1e4c6727e` | `4c923b2` tree matches (`099547e1…`) | Yes; UI V1.1 content is integrated |
| `chore/v1.2-bootstrap-docs` | `c2ea39d5ac943dd6bcdc8a49f8a58486076c1e05` | Final main tree matches (`d35d654b…`) | Yes; PR #15 merged |
| `fix/uat03-runtime-side-effects` | `fd655194fb58b04fc4d6467df9845d33f53fa76d` | `0a502933` tree matches (`a76e85e2…`) | Yes; PR #13 merged |

The existing `v5.0.0` tag remains the package-version convention. No V1.2
release tag or GitHub release was created. The stable integration anchor is
the accepted main SHA plus its immutable GHCR commit tag and digest.
