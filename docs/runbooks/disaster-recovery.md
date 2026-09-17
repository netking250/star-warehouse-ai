# Backup, Restore, and Disaster Recovery

This runbook separates the tested low-cost demo procedure from the production reference. A
single-node k3s demo can restart pods but does not provide node-level HA. The production reference
requires a managed multi-node/zone design and PITR evidence before any HA, RPO, RTO, or SLA claim.

## Recovery responsibilities

| System | Classification | Recovery responsibility |
| --- | --- | --- |
| PostgreSQL | `SOURCE_OF_TRUTH` | Logical demo backup/restore; production managed snapshots/WAL/PITR. Includes business, tenancy, conversation, audit/compliance, receipt, and Outbox state. |
| Local knowledge uploads | `SOURCE_OF_TRUTH` when used | Back up and restore tenant-prefixed source bytes with PostgreSQL metadata. The T19 demo currently mounts transient `emptyDir`, so durable upload claims are forbidden. |
| External object storage | not currently active | Future encrypted/versioned provider storage behind a tenant-aware Port; no T20 bucket exists. |
| Qdrant | `DERIVED_REBUILDABLE` | Reindex from PostgreSQL and retained source files; snapshots are optional acceleration, not canonical truth. |
| Redis | `EPHEMERAL` | Restart/repopulate; active sessions may be invalidated. Never use as a business restore source. |
| RabbitMQ | `DURABLE_SECONDARY` | Restore broker service, then relay/reconcile PostgreSQL Outbox work. Do not claim exactly-once. |

## Backup creation and integrity

The demo values enable one daily CronJob with `concurrencyPolicy: Forbid`. It uses `pg_dump` custom
format without source ownership while preserving ACLs and writes to a dedicated backup PVC, not
the PostgreSQL data PVC. Every
artifact has JSON metadata (UTC timestamp, application/image revision, Alembic revision, database
identifier, backup type) and SHA-256. The job verifies non-empty output and `pg_restore --list`
before publishing the final filename. Its seven-day demo retention is an operational test default,
not a legal or production policy.

Trigger a bounded manual backup only in an explicit disposable namespace:

```bash
NAMESPACE=t20-implement \
TARGET_ENVIRONMENT=t20-local \
./scripts/t20-backup-now.sh
```

Review the job log and copy the `.dump`, `.metadata.json`, and `.sha256` files into an access-
controlled temporary operator directory. Never commit backups. Production storage should use
encrypted, access-controlled, versioned off-host object storage with a reviewed lifecycle and
restore monitoring; repository credentials must never be embedded in artifacts or metadata.

## Decision to restore

Restore only when authoritative PostgreSQL is lost/corrupt or a recovery drill was explicitly
approved. Confirm:

1. incident/drill identifier and operator;
2. source backup metadata, checksum, completion time, and expected data-loss window;
3. a new isolated target—never the source database;
4. application writes stopped or redirected;
5. compatible application image and migration head;
6. runtime/maintenance credentials available outside Git;
7. retained knowledge-source bytes available if knowledge uploads were used.

Abort if the target exists, checksum/list validation fails, the source identity is ambiguous, the
required image/migration is unavailable, or the environment cannot prove tenant isolation.

## Fresh-target restore

Run `scripts/t20-postgres-restore.sh` from a trusted PostgreSQL 16 client environment with `PGHOST`,
`PGPORT`, `PGUSER`, and `PGPASSWORD` set for the new disposable server. The target must be a new
lowercase `t20_*` database.

```bash
TARGET_ENVIRONMENT=t20-restore \
T20_DESTRUCTIVE_CONFIRM=YES_DISPOSABLE_ONLY \
SOURCE_DATABASE_ID=t20-source/star_warehouse_ai \
RESTORE_TARGET_DB=t20_restore_20260917 \
BACKUP_ARTIFACT=/secure-temp/star_warehouse_ai-20260917T120000Z.dump \
./scripts/t20-postgres-restore.sh
```

After `pg_restore` succeeds:

The restore command first creates or hardens the fixed non-login capability-role shells. It then
preserves archive ACLs and, for older archives created without ACLs, reconstructs only the grants
for tables named by accepted RLS policies plus the tenant catalog and sequences. Login roles and
passwords remain the canonical deployment provisioner's responsibility.

1. point the canonical T19 migration Job at the restored database;
2. run `alembic upgrade head` and `python -m app.core.database_roles` through that Job;
3. require `alembic current --check-heads` and head `e9f0a1b2c3d4`;
4. verify runtime and maintenance logins are `NOSUPERUSER`, `NOBYPASSRLS`, and hold only their
   fixed capability role;
5. start API, worker, scheduler, and relay against the restored target;
6. validate deterministic tenant/user/order relationships and audit/compliance sentinels—not just
   table counts;
7. set transaction-local tenant A and verify its records, then set tenant B and prove tenant A is
   invisible through the runtime login;
8. restore retained local knowledge bytes before reindexing Qdrant; if no upload fixture exists,
   record object recovery as N/A with the active-storage limitation;
9. restore RabbitMQ and let the relay recover pending work; verify receipt/idempotency semantics and
   a drained backlog;
10. run authenticated health/business smoke and record service-ready time.

Do not use `alembic downgrade`, restore over the source, grant `BYPASSRLS`, purge broker queues, or
copy Redis as authoritative data.

## RTO, RPO, and PITR claims

- Demo RTO: measure from restore start through database restore, migration/role provisioning,
  application readiness, tenant isolation, business invariant, and async recovery. Report it only
  as `measured restore-and-service recovery time in the T20 disposable environment`.
- Demo RPO: the completion time of the selected logical backup. Changes after it are not recovered.
- Demo PITR: `NOT IMPLEMENTED`; the logical backup does not archive WAL.
- Production reference: RDS/Aurora PostgreSQL-compatible Multi-AZ plus encrypted automated backups,
  WAL/PITR, cross-failure-domain recovery, restore testing, and independently monitored off-host
  copies are the target. Business owners must approve explicit production RPO/RTO before launch;
  the repository currently claims neither and T20 creates no AWS resources.

## Rollback, cleanup, and escalation

If validation fails, keep the source and failed target isolated, stop application writes, preserve
logs/metadata/checksums, and escalate as `RESTORE_FAILURE`, `RESTORE_ISOLATION_FAILURE`, or
`DR_RECOVERY_FAILURE`. Do not promote a partially validated target. Cleanup is a separate explicit
action limited to the exact disposable cluster/database/artifact directory; report what was
removed and whether it was recoverable.
