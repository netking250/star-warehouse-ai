# CI/CD and software supply chain

T18 establishes the delivery-trust baseline for Star Warehouse AI. It keeps the accepted CI
families attributable and adds security/supply-chain analysis without creating a deployment
platform. T19 owns Helm, k3s, AWS, and registry consumption.

## Gate architecture

`.github/workflows/ci.yml` remains the protected-main quality pipeline with five separate jobs:

1. **Brand & docs** — canonical identity and local documentation links.
2. **Backend quality** — frozen uv environment, lockfile integrity, single Alembic head, Ruff, and
   ty.
3. **Backend tests** — isolated PostgreSQL/Redis/Qdrant services, migrations, the existing
   `pytest --cov=app --cov-fail-under=75` gate, and bounded JUnit/coverage artifacts.
4. **Frontend** — Node 22, npm 11.9.0, frozen `package-lock.json` installation, format, lint,
   Vitest, TypeScript/build, and focused Chromium E2E.
5. **Docker smoke** — production image build, non-root/metadata checks, migration, and API health.

Evaluation, monitoring-as-code, and performance remain separate workflows. Existing job names and
the backend coverage threshold are unchanged.

## Workflow trust boundary

All workflows default to `contents: read`; checkouts disable credential persistence. There is no
`pull_request_target`, and pull-request jobs do not receive repository, environment, provider, or
registry secrets. PR verification can build and scan locally but cannot publish an image or receive
trusted attestation permissions.

The trusted provenance job runs only after a successful image/SBOM job on a push to `main` or a
version tag. It grants only `id-token: write`, `attestations: write`, and the read permissions
needed to download the same-run artifact. It attests the generated CycloneDX SBOM with GitHub's
native build-provenance action. Registry publication and image signing are deliberately deferred to
the T19/release boundary; no signing private key is stored in the repository.

## Deterministic inputs

- Python is explicitly selected as 3.12; uv is explicitly selected as 0.6.5 and the existing
  third-party setup action is pinned to commit `e58605a9b6da7c637471fab8847a5e5a6b8df081` (v5).
- Backend installs use `uv sync --frozen` and `uv lock --check`; scans export the locked graph with
  `uv export --frozen --all-groups --no-emit-project` so the local editable application package is
  not handed to pip-audit as a hash-constrained wheel requirement.
- Node is explicitly selected as 22 and the frontend declares `npm@11.9.0`; CI pins that npm
  version before `npm ci`. `package-lock.json` remains authoritative.
- PR dependency caches are disabled. Trusted push/scheduled runs may use uv/npm dependency caches
  keyed by their lockfiles. No cache contains `.env`, credentials, test databases, tenant data, or
  generated secrets.
- Base/runtime Docker image tags remain in the repository's supported update stream and are covered
  by the existing Docker smoke plus Dependabot's Docker ecosystem. The uv image is already pinned
  by digest in the Dockerfile; no blind digest pinning was added for every Compose service image.

## Security and supply-chain analysis

`.github/workflows/supply-chain.yml` runs on pull requests, `main` pushes, version tags, and manual
trusted execution:

- Gitleaks scans the checked-out repository with redacted SARIF output. It never prints discovered
  values. The scan uses `--no-git` so deleted historical design documents containing synthetic
  examples do not create a permanent false-positive gate; the current tracked checkout remains
  covered. The only allowlisted value is the exact non-secret `sk-test` provider placeholder used
  by CI fixtures.
- `pip-audit` scans the exported uv lock graph (excluding only the local editable project itself)
  and `npm audit` scans the frontend lockfile. The commands do not update either lockfile. npm
  critical findings and image critical findings block. pip-audit 2.9.0's JSON output does not carry
  severity, so its records are retained for advisory-specific review rather than being given a
  fabricated severity; a clearly critical shipped-runtime advisory identified during review is a
  release blocker. Existing high/non-critical findings remain visible as warnings and
  machine-readable artifacts so they cannot be mistaken for a clean baseline. Registry/tool
  failures without a valid report are scanner failures. The PR-only Dependency Review gate blocks
  new high/critical dependency deltas.
- The built application image is scanned by Trivy. Critical findings block. High findings, whether
  or not a fixed version is known, remain visible in the report as warnings while the existing
  lockfile/base-image baseline is remediated. No finding is silently suppressed. The runtime image
  applies current Debian security updates before the application is copied in, and the scan itself
  runs from an image archive without granting a third-party scanner Docker-socket access.
- Syft generates one canonical CycloneDX JSON SBOM from the built image. The workflow validates
  that it parses, declares CycloneDX, and contains components.
- Image metadata records repository, commit SHA, ref, workflow/run identity, image ID, image user,
  and OCI revision label. It contains no tokens, credentials, customer data, or provider secrets.

The PR-only Dependency Review action checks dependency deltas at high severity with no comment/write
permission. CodeQL runs in the trusted `main`/scheduled workflow with narrowly scoped
`security-events: write`; it is intentionally not executed from untrusted PR code.

## Artifacts and retention

Security reports, SBOM, image metadata, backend JUnit XML, and coverage XML are uploaded as
short-lived artifacts with 14-day retention. Reports are machine-readable and attributable to the
workflow run. `.env`, provider credentials, database dumps, raw tenant data, and local runtime
state are not uploaded.

## Trusted image publication boundary

T19 extends the trusted boundary without changing pull-request permissions. Only a push to
`main` or a `v*` tag preserves the exact image archive that passed the image scan. A separate job
with narrowly scoped `packages: write`, `id-token: write`, and `attestations: write` loads that
archive, authenticates to GHCR with the ephemeral workflow token, and publishes
`ghcr.io/netking250/star-warehouse-ai:sha-<commit>`. A version-tag run also publishes that version
tag. The workflow never publishes `latest` and never accepts personal registry credentials.

The job records `repository@sha256:digest`, attests that container digest, and exports the immutable
reference as a short-retention artifact for Helm. k3s/EKS consume the digest; they never rebuild the
source. Hosted publication and attestation execution are intentionally left for the trusted T21
main/version-tag proof.

## Local reproduction

Run the same deterministic checks from a clean checkout:

```bash
uv lock --check
uv sync --frozen
uv run ruff check app tests
uv run ruff format --check app tests
uv run ty check --error-on-warning app tests
cd frontend && npm ci && npm run format:check && npm run lint && npm run test && npm run build
```

Docker build/smoke and the scanner containers additionally require Docker and network access to
their versioned tool images. The full backend regression remains the final hosted PR gate; the two
known OpenAI SDK and Celery fresh-process timing sensitivities are baseline debt and are not hidden
or changed by T18.

## T21 hosted-CI acceptance

The integration branch intentionally has no intermediate PR. Before the final T21 PR, verify in
GitHub that the five existing checks plus the T18 security checks are green for an actual untrusted
PR, that no PR job receives a secret or trusted write permission, that the Dependency Review and
CodeQL platform features are available, and that a trusted `main`/version-tag run records both the
native SBOM attestation and published-container digest attestation. Branch protection itself is not
changed by T18; the final required-check set must be reviewed against the actual check names at T21.
