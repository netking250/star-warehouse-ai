# P-UAT-02A-FIX - Knowledge Upload / Worker Storage Repair

## Status

- Task: `P-UAT-02A-FIX`.
- Status: `AWAITING_ACCEPTANCE`.
- Execution stage: `EXTERNAL_ACCEPTANCE_PENDING`.
- Branch: `fix/knowledge-worker-storage`.
- Base: `origin/main` at `5d84b034513e79557c6ad9ce9fb819832034352f`.
- P-UAT-01: externally reported `PASS_WITH_NOTES`.

## Reproduction

- Real API upload returned document `3` and outbox/Celery task identity
  `42d2b16b-2d93-4037-a0b0-130c3ea88ec4`.
- PostgreSQL persisted
  `uploads/knowledge/tenant/default/128cfb2edc6340798f54b78077163432.txt`.
- The API container read the 91-byte sentinel and SHA-256
  `f711c8c1705cac8f028b5b44b077f3d0f0e9afe193f360b1376b7ce8c154fd0b`.
- The tenant worker could not stat the same relative reference and raised `FileNotFoundError`.
- Docker inspection showed only the source-code bind mount on both processes and no shared upload
  volume. The document ended `failed` after bounded retries.
- Classification: `LOCAL_VOLUME_NOT_SHARED` plus `STORAGE_ADAPTER_CONTRACT_BUG`.

## Frozen scope

Repair the local/demo upload-to-worker storage boundary using one tenant-aware canonical storage
contract and one shared Compose named volume for the processes that read or clean knowledge source
objects. Persist stable object keys rather than host/container-local absolute paths. Keep production
S3-compatible object storage explicitly future/not active, and keep Qdrant derived/rebuildable.

## Verification plan

1. Add one failing storage-contract regression, then implement the minimum local adapter.
2. Add focused worker ingestion, missing-object/final-state, re-sync/delete, tenant-isolation, and
   Compose mount/config regressions as vertical TDD slices.
3. Run focused Ruff, Ruff format check, ty, and selected pytest only.
4. Recreate a fresh isolated Compose demo, upload the required sentinel through the real Admin/API
   flow, and prove worker read, terminal success, chunk count, Qdrant points, and tenant metadata.
5. Record evidence, commit once, and leave the branch clean at `AWAITING_ACCEPTANCE`.

## Result

- Added a tenant-aware source-object Port and local/demo filesystem adapter with stable logical
  keys, namespace validation, atomic writes, deterministic missing-object errors, and idempotent
  deletion.
- API upload and workers now share `/app/uploads/knowledge` through `knowledge_uploads`; the image
  pre-creates the mountpoint as writable by non-root `appuser`. Maintenance receives the mount for
  retention; scheduler and relay do not.
- Worker ingestion resolves source bytes through the canonical adapter before replacing derived
  vectors. Bounded retry now reports `pending` before the final attempt and terminal `failed` after
  the final attempt.
- Admin deletion and retention remove tenant-scoped Qdrant points and source bytes before metadata.
- Focused verification: pytest `30/30`, Ruff PASS, format PASS, ty PASS, Compose config PASS.
- Fresh real Compose proof: upload HTTP 200; document `1`; task
  `40068d5f-c0da-4ccb-acbd-8f064c5168b8` `SUCCESS`; one chunk and one Qdrant point with tenant
  `default`; identical API/worker SHA-256
  `d9403452220caa77f389353062ce9548a32701ba52ec9519b0516811540ff109`; re-sync `SUCCESS`; second
  synchronized document deletion left zero metadata, source object, and Qdrant points.
- Production object storage remains not active; Docker named-volume durability is local/demo only.

## Explicit non-goals

No migration, Grafana/Help/UI repair, prompt/model quality work, AWS/k3s production deployment,
PITR, production object-store recovery claim, or broad backend regression.
