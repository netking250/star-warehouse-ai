# T00 Baseline Evidence

Date: 2026-09-11
Base Git HEAD: `bf0d5b9`
Environment: Windows PowerShell; Python 3.12.10; uv 0.6.5; Node v22.23.2; npm 10.9.8.

This record contains commands actually executed during T00 and its authorized fixes. Historical failures are separated from the current gate state.

## Results

| Area | Command | Result | Evidence |
| --- | --- | --- | --- |
| Backend install | `uv sync --frozen` | PASS | Audited 170 packages. |
| Identity/docs CI check | `python scripts/check_project_identity.py` | PASS | `Project identity is consistent: Star Warehouse AI v5.0.0`. |
| Pytest discovery | Formal full test entry point | PASS | 1533 tests collected from this repository. |
| Limiter regression | `uv run pytest --noconftest tests/core/test_limiter.py::test_limiter_initializes_with_the_application_utf8_env_file_present -q` | PASS | 1 passed. |
| Ruff | `uv run ruff check app tests` | PASS | All checks passed. |
| Backend format | `uv run ruff format --check app tests` | PASS | 348 files already formatted. |
| Type check | `uv run ty check --error-on-warning app tests` | PASS | All checks passed. |
| Application import | `uv run python -c "import app.main; print('application import: PASS')"` | PASS | Application import completed. |
| Formal backend CI tests and coverage | `uv run pytest --cov=app --cov-fail-under=75` | PASS | 1533 passed, 0 failed, 0 skipped; total coverage 79.43% (required 75%). |
| Frontend install | `npm --prefix frontend ci` | PASS | Added 488 packages. |
| Frontend format | `npm --prefix frontend run format:check` | PASS | The standard formatter normalized the 95 previously failing files; all files now match. |
| Frontend lint | `npm --prefix frontend run lint` | PASS | Exit code 0. |
| Frontend unit tests | `npm --prefix frontend run test` | PASS | 4 test files and 11 tests passed. |
| Frontend production build | `npm --prefix frontend run build` | PASS | Vite production build completed in 14.92 seconds. |
| Alembic graph | `uv run alembic heads` and `uv run alembic history --verbose` | PASS | One head: `b7c6d5e4f3a2`; history is readable. |
| Alembic runtime | `uv run alembic heads`; empty DB `uv run alembic upgrade head`; `uv run alembic current` | PASS | One head and current revision `b7c6d5e4f3a2`; a fresh PostgreSQL database upgraded from empty. |
| Docker and Compose | `docker version`; `docker compose version`; project Compose config/build | PASS | Docker Engine 29.4.3 and Compose 5.1.3 are available; the 4.37 MB context builds; both Compose configurations validate. |
| Runtime smoke | Project Compose startup, service health, HTTP health endpoint | PASS | PostgreSQL, Redis, Qdrant, worker, and API started healthy; `GET /health` returned HTTP 200 with all three dependencies connected. |

## T00 Tooling Fix

Initial pytest collection failed before tests ran because SlowAPI independently opened the UTF-8 root `.env` with Starlette's Windows-default codec, causing `UnicodeDecodeError` under GBK. Application settings already use UTF-8 through `app.core.config`; the limiter now explicitly points SlowAPI to tracked ASCII-only `app/core/slowapi.env`. The focused regression passes, and collection now reports 1531 tests. This change is limited to baseline reproducibility and does not alter business behavior.

The initial Docker build transferred approximately 230 MB because no `.dockerignore` existed. The tracked T00 `.dockerignore` excludes local environments, dependency directories, caches, secrets, tests, documentation, and generated artifacts that are not used by the existing Dockerfile; the rebuilt context measured 4.37 MB.

## Migration Repair

`053eaa2f0a66` creates `message_feedbacks`, but `3a9f8e7b2c1d` originally branched from `v4_2_confidence_trigger` and attempted to alter that table before creation. The merge descendant `c61a28a53622` also repeated the same feedback-column operations and the `experiment_metrics` creation already owned by its ancestors.

The repair retains every revision ID and the complete history: `3a9f8e7b2c1d` now follows `053eaa2f0a66`, and `c61a28a53622` no longer repeats ancestor-owned DDL. This is data-safe for valid existing databases: a database already at head executes nothing, and a database at the repaired boundary receives only additive nullable columns and indexes.

Fresh-database inspection confirmed the 11 expected `message_feedbacks` columns, including `category`, `agent_type`, `confidence_score`, and `tenant_id`, plus indexes for agent type, category, tenant, thread, and user.

## Failures and Blockers

| Classification | Finding | T00 impact |
| --- | --- | --- |
| KNOWN_BASELINE_FAILURE (tooling) | None after the authorized standard frontend formatting pass. | Frontend format, lint, unit tests, and build all pass. |
| CURRENT T00 BLOCKER | None. | All required T00 gates pass and await external acceptance. |
| ENVIRONMENT | No current Docker/service availability blocker. | Project runtime evidence was collected using temporary non-conflicting host ports because unrelated user containers occupied the default ports. |
| TEST-INFRASTRUCTURE WARNING | Pytest could not write its cache due workspace permissions. | Non-fatal; collection and focused regression completed. |
| KNOWN NON-BLOCKING MIGRATION ISSUE | Optional downgrade from head reaches a pre-existing enum cleanup defect in `4a0032131db6`. | Does not affect the required empty-database forward upgrade; no out-of-scope migration was changed. |

## Current Status

T00 is `AWAITING_ACCEPTANCE`. T01 remains `NOT_STARTED`.
