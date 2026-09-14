# Compliance Lifecycle Operations Runbook

These are application engineering procedures, not legal-response or certification playbooks.

## Retention job failure

- **Symptom:** `retention_runs_total{result="failure"}` increases, a task fails, or a structured
  `Retention execution failed` event appears.
- **Inspect:** identify dataset, correlation ID, maintenance worker health, database error, and the
  kill-switch; run the authorized dry-run for the affected tenant.
- **Safe immediate action:** set `RETENTION_EXECUTION_ENABLED=false` and restart maintenance workers
  if scope is uncertain; preserve dry-run capability.
- **Do not:** issue table-wide DELETE, grant BYPASSRLS, treat application SUPER_ADMIN as maintenance
  authority, scan an entire object bucket, or edit a released migration.
- **Recovery:** correct the narrow policy/storage failure, validate the same bounded dry-run,
  re-enable through configuration change control, and retry one batch.
- **Preserve:** task/correlation IDs, policy version, dry-run IDs/counts, metrics, database error,
  worker logs, and configuration-change evidence.

## Sensitive export stuck or failed

- **Symptom:** an approval remains APPROVED without an artifact, export errors, or export-failure
  metrics rise.
- **Inspect:** approval ID/status/expiry, operation hash, requester current authorization, artifact
  row, correlation ID, and transaction error; never print artifact content.
- **Safe immediate action:** retry identical parameters while authority remains valid; the unique
  approval-to-artifact key makes this idempotent.
- **Do not:** change filters, copy CSV content into logs/tickets, manually mark EXECUTED, disable RLS,
  or create a cross-tenant download path.
- **Recovery:** request a new approval after expiry or filter change; retry a rolled-back transaction
  with the original hash after repair.
- **Preserve:** approval/artifact IDs, hashes, statuses, timestamps, counts, errors, and correlations.

## Approval stuck or expired

- **Symptom:** PENDING exceeds 15 minutes or a decision/execution reports expiry.
- **Inspect:** timestamps, requester/approver IDs, tenant, operation hash, and current capability.
- **Safe immediate action:** let authority fail closed and request a new exact operation if needed.
- **Do not:** extend timestamps in SQL, self-approve, reuse across tenants, or restore revoked roles.
- **Recovery:** reject obsolete valid requests or create/approve a replacement through normal APIs.
- **Preserve:** approval ID, decision audit, correlation, current-role evidence, and operation hash.

## Audit write failure

- **Symptom:** `audit_write_failures_total` rises or a sensitive transaction rolls back.
- **Inspect:** database availability, INSERT privilege, RLS tenant binding, immutable trigger state,
  transaction error, and correlation ID.
- **Safe immediate action:** stop the sensitive action, restore append behavior, and retry the whole
  transaction after repair.
- **Do not:** report success, disable immutability, grant runtime mutation, or store credentials/full
  payloads as substitute evidence.
- **Recovery:** validate a harmless runtime append and that UPDATE/DELETE remain denied, then retry.
- **Preserve:** sanitized error, event type/outcome/reason, tenant reference, correlation, database
  role/catalog evidence, and rollback evidence.

## Accidental retention scope concern / emergency stop

- **Symptom:** dry-run IDs/counts exceed expectation, the tenant/dataset is wrong, or object paths
  fail the tenant-root guard.
- **Inspect:** disable execution first; compare policy, tenant context, cutoff, bounded IDs, storage
  root, migration state, and recent audit events.
- **Safe immediate action:** set `RETENTION_EXECUTION_ENABLED=false`, recycle maintenance workers,
  and leave the rest of the application available.
- **Do not:** delete more data to correct scope, remove evidence, mutate audit rows, grant cross-tenant
  privileges, or restore over a live database without an incident plan.
- **Recovery:** verify backups and affected IDs, correct the narrow handler, test on a disposable
  database, and re-enable only after reviewed dry-run evidence.
- **Preserve:** logs/metrics, dry-run and processed IDs, configuration history, database/object
  evidence, backups, and operator timeline.
