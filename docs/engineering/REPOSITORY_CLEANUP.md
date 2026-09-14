# Repository Cleanup Matrix

M01 classifies repository cleanup candidates using only `KEEP`, `MERGE`, `DELETE`, and
`REVIEW`. Deletion required evidence of no references, a canonical replacement, generated
artifact status, or Git-preserved obsolete history. `REVIEW` items were not deleted.

## Working Tree Baseline

- Branch: `main`; recovery HEAD: `bf0d5b9`.
- The worktree already contained extensive uncommitted T00–T06 changes. M01 preserved them
  and did not reset, checkout, stash, delete, or commit unrelated work.
- T06 remains `NEEDS_EVIDENCE / VERIFY_PENDING`; T07 remains `NOT_STARTED`.

## Final Cleanup Matrix

| Item | Classification | Evidence | Action |
| --- | --- | --- | --- |
| `AGENTS.md`, `docs/engineering/`, `docs/exec-plans/` | KEEP | Protected project execution memory | Retained; M01 lifecycle/evidence appended |
| `migrations/versions/` | KEEP | Released Alembic history is immutable | Retained unchanged by M01 |
| `docker-compose.yaml` | KEEP | Used by startup, CI, tests, and docs | Canonical local application Compose |
| `docker-compose.monitoring.yml` | KEEP | Used by monitoring CI and deployment script; separate lifecycle is intentional | Canonical optional local monitoring Compose |
| Root `Dockerfile` | KEEP | Default application image used by Compose and CI | Retained as the only Dockerfile |
| `Dockerfile.save` | DELETE | No runtime/script/CI/doc consumer; truncated invalid copy; root Dockerfile supersedes it | Deleted |
| `start.sh` | DELETE | Stale duplicate omitted RabbitMQ, scheduler, and outbox; full Docker and documented manual flows replace it | References migrated; deleted |
| `celery_worker.py` | DELETE | Only copied into the image; never executed; canonical Celery CLI/Compose service replaces it | Docker/tooling references removed; deleted |
| Root README and developer workflow docs | MERGE | Multiple startup paths disagreed on services and commands | README is the concise entry; quickstart/local-dev/deploy/cheatsheet link to one workflow |
| Fixed Compose `container_name` values | MERGE | Active callers use Compose service names; fixed global names caused cross-checkout conflicts | Removed from both Compose files; service-oriented commands retained |
| Compose host ports | MERGE | Infrastructure needs host access for local development but not public exposure | PostgreSQL/Redis/RabbitMQ/Qdrant/monitoring bind loopback; API remains on host port 8000 |
| RabbitMQ credentials and broker descriptions | MERGE | T04/ADR-009 establish RabbitMQ; Compose previously warned on an unset password and active docs still named Redis | Added explicit local default; updated Compose, README, architecture, operations, and reference docs |
| `.env.example` and environment reference | MERGE | Application, Compose, test, monitoring, and frontend variables were mixed and incomplete | `.env.example` is runnable canonical input; reference classifies ownership, scope, derived, and deprecated names |
| Duplicate Redis settings in `app/core/config.py` | DELETE | First definitions were overwritten in the same class; two legacy circuit names had zero consumers | Removed shadowed/unused definitions; effective defaults preserved |
| Test infrastructure | MERGE | PostgreSQL was protected, but Redis defaulted to DB 0 and CI named Redis as broker | Tests force Redis DB 15, process-scoped Qdrant, memory Celery transports, and `test_` RabbitMQ vhosts |
| CI broker/environment values | MERGE | Generic CI does not need a real broker, but its Redis URL contradicted runtime truth | Uses explicit test `memory://`; Docker smoke starts RabbitMQ |
| Monitoring PagerDuty variable | MERGE | `PAGERDUTY_SERVICE_KEY` and `PAGERDUTY_INTEGRATION_KEY` named one semantic value | Standardized active config/scripts on `PAGERDUTY_INTEGRATION_KEY` |
| Monitoring deployment script | MERGE | Supported both Compose v1/v2 command paths while project requirements use Compose v2 | Uses one quoted `docker compose` command array |
| Shell line endings | MERGE | Tracked `.sh` files had CRLF/mixed worktree endings and failed Bash parsing | Added `*.sh text eol=lf`, normalized scripts, and passed `bash -n` |
| Python/pytest/Ruff/ty configuration | KEEP | `pyproject.toml` is the single active backend tool source | Retained; removed only deleted-script exclusion |
| ESLint/Prettier/TypeScript/Vite/Vitest configs | KEEP | One config per tool; app/node and Vite/Vitest files serve distinct consumers | Retained |
| Evaluation files with `v1`/`v2` names | KEEP | Versioned datasets/generator are intentional test assets, not backups | Retained |
| `app/api/v1/` | KEEP | Active versioned API package with runtime routes | Retained |
| `docs/roadmap-star-warehouse-ai.md`, `docs/reference/adr.md` | KEEP | Root protocol explicitly retains them as product/history context | Retained and authority/supersession clarified |
| `docs/explanation/monitoring-unification-plan.md` | KEEP | Linked design background with unique content | Retained and labeled historical, not operational truth |
| Local caches, coverage, virtualenv, dependencies, builds | KEEP | Generated, untracked, and ignored; no generated artifact is tracked | Kept locally; ignore coverage verified |
| Local `uploads/` | REVIEW | Untracked runtime/user data may be user-owned | Not deleted; added ignore rule |
| `docs/plans/phase-1-monitoring-unification-plan.md` | REVIEW | Unlinked but contains unique historical implementation detail | Labeled historical; not deleted |
| `docs/research/industry-best-practices-gap-analysis.md` | REVIEW | Unlinked research may contain unique rationale | Labeled historical; not deleted |
| `docs/explanation/upgrade-plan-2026.md` | REVIEW | Referenced by historical monitoring material and may contain unique product planning | Labeled historical; not deleted |
| `.claude/`, `.opencode/`, `.serena/` | REVIEW | User/editor/agent tooling cannot be proven obsolete | Retained; only the broken `.claude` startup command was corrected |

## Port Model

| Service | Container Port | Host Port | Needed From Host? |
| --- | ---: | ---: | --- |
| PostgreSQL | 5432 | 127.0.0.1:5432 | Yes — local migrations/debug/tests |
| Redis | 6379 | 127.0.0.1:6379 | Yes — local development/debug/tests |
| RabbitMQ AMQP | 5672 | 127.0.0.1:5672 | Yes — local worker/integration work |
| RabbitMQ Management | 15672 | 127.0.0.1:15672 | Optional local operations |
| Qdrant HTTP/gRPC | 6333/6334 | 127.0.0.1:6333/6334 | Yes — local indexing/debug/tests |
| API/Web | 8000 | 0.0.0.0:8000 | Yes — application entry point; intentionally unchanged |

Monitoring ports 3000, 9090, 9093, 3100, 3200, 4317, 4318, 13133, and 9009 are
loopback-only in the optional monitoring Compose file.

## Removed

- `Dockerfile.save`: invalid unreferenced Git-preserved historical copy.
- `start.sh`: incomplete duplicate startup implementation.
- `celery_worker.py`: unexecuted legacy wrapper.

## Consolidated

1. Developer startup and test commands into README plus focused linked guides.
2. Application/monitoring Compose naming and local port exposure.
3. RabbitMQ broker truth, local credentials, and documentation.
4. Application/Compose/frontend/test/monitoring environment ownership.
5. Redis config definitions and explicit database selection.
6. PostgreSQL/Redis/Qdrant/RabbitMQ/Celery test isolation.
7. CI test transports and Docker smoke dependencies.
8. Current architecture/operations/deployment documentation authority.
9. PagerDuty monitoring variable naming.
10. Monitoring deployment on Compose v2.
11. LF line endings for executable shell scripts.

## Kept Intentionally

- Both Compose files: one application stack and one independently operated monitoring stack.
- Every Alembic revision and intentional evaluation/fixture dataset.
- Historical ADR/product roadmap files required by project memory.
- Current linked monitoring design background, clearly labeled historical.
- One backend config source (`pyproject.toml`) and distinct frontend tool configs.

## REVIEW

- `uploads/` — local user/runtime data; ignored, never deleted.
- `docs/plans/phase-1-monitoring-unification-plan.md` — unique historical plan content.
- `docs/research/industry-best-practices-gap-analysis.md` — unique historical research.
- `docs/explanation/upgrade-plan-2026.md` — unique historical product plan.
- `.claude/`, `.opencode/`, `.serena/` — user tooling with uncertain deletion safety.

The runtime smoke also found external legacy `ecommerce_*` containers occupying host ports
5432, 6379, 6333/6334, and 8000. They are outside the current Compose project and were not
stopped or deleted.

## Canonical Sources

| Area | Canonical source |
| --- | --- |
| Root project intro | `README.md` |
| Local development | `docs/tutorials/local-development.md` |
| Compose | `docker-compose.yaml`; optional monitoring in `docker-compose.monitoring.yml` |
| Environment variables | `.env.example`, classified by `docs/reference/environment-variables.md` |
| Architecture | `docs/engineering/DECISIONS.md`, `docs/architecture/ARCHITECTURE_GUARDRAILS.md`, then `docs/explanation/architecture/` |
| Deployment | `docs/how-to-guides/deploy.md` |
| Testing | `AGENTS.md`, `tests/AGENTS.md`, `docs/tutorials/local-development.md` |
| Security | `AGENTS.md` security rules and `docs/engineering/DECISIONS.md` |
| Operations | `docs/runbooks/README.md` |
| Project state | `docs/engineering/PROJECT_STATE.md`, `docs/engineering/ROADMAP.md` |

## Verification Evidence

- Both Compose files parse with `docker compose ... config --quiet`.
- Focused repository/config tests: 24 passed.
- Focused Ruff and ty checks pass; shell scripts pass `bash -n`.
- All 151 application settings inputs are represented in `.env.example`; the nine extra
  entries are intentionally Compose/monitoring-owned.
- YAML parsing passed for both Compose files, all four workflows, and Alertmanager config.
- Project identity and repository-local Markdown links pass.
- `git diff --check` passes.
- Standard infrastructure startup was attempted. RabbitMQ became healthy and Compose DNS
  resolved `rabbitmq`; PostgreSQL/Redis/Qdrant could not bind standard host ports because
  unrelated legacy containers already own them. No external container or volume was changed.
