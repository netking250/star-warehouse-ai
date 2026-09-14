# Compliance Lifecycle Engineering Controls

This document describes engineering controls supporting data lifecycle and audit requirements. It
does not assert legal compliance or regulatory certification. Retention periods below are
configurable DEV/DEMO defaults, not externally validated legal requirements.

## Control flow

Production datasets are registered in `app.compliance.classification.DATASET_POLICIES`. Each entry
declares ownership, tenant key, sensitivity evidence, handling classification, retention category,
deletion strategy, export policy, and audit requirement. A structural test compares every SQLModel
production table to this registry so a new table cannot remain silently unclassified.

Retention is tenant-by-tenant and selects only rows older than the dataset cutoff (or whose explicit
expiry timestamp is old), ordered deterministically, with a bounded batch. Dry-run returns eligible
IDs without mutation. Destructive execution requires `RETENTION_EXECUTION_ENABLED=true`; scheduled
execution additionally requires the independently deployed maintenance database capability. No
migration deletes historical data.

The existing local knowledge upload is the only active external object store. Its lifecycle deletes
only the path beneath the trusted current-tenant upload root, treats an already-missing object as an
idempotent success, and then deletes metadata in the caller-owned transaction. S3/presigned URLs are
not active and are not claimed.

`authorization_audit_events` and `compliance_audit_events` are append-only to normal runtime and
application SUPER_ADMIN access. PostgreSQL privileges and triggers reject raw UPDATE/DELETE; T11
retains these audit datasets indefinitely and introduces no audit purge capability. Compliance
events contain actor, tenant, action, target reference, timestamp, correlation, outcome, reason,
and small sanitized metadata—not credentials, full records, or exported content.

## Canonical inventory summary

The registry classifies every production PostgreSQL table plus active Qdrant, Redis, local-file,
and bundled-data stores. Evidence comes from model fields and actual writers/readers, not names:

- Identity and user profile tables contain direct account/personal fields and are RESTRICTED.
- Orders, refunds, complaints, conversations, feedback, memory, review, and selected execution logs
  carry user-linked or free-text business data and are CONFIDENTIAL or RESTRICTED.
- Configuration, aggregate metrics, task receipts, and framework metadata contain operational data
  but no demonstrated direct personal fields and are INTERNAL.
- Immutable audit evidence is RESTRICTED because event references expose security activity even
  though raw credentials and payloads are prohibited.
- Bundled public seed content is PUBLIC; tenant knowledge and memory vector points remain
  CONFIDENTIAL derived data.

Enabled cleanup defaults are 365 days for messages, feedback, and local knowledge uploads; 90 days
is recorded for memory categories but their existing tombstone/vector-consistency workflows are not
automatically enabled until a safe end-to-end handler owns them. Sensitive export artifacts become
unavailable after 15 minutes and are eligible for physical cleanup after the configured lifecycle
window. Business, identity, approval, and audit evidence is retained until an externally validated
policy is supplied.

## Sensitive feedback export

Feedback CSV contains user/thread identifiers and free-text comments, so the classification policy
requires approval. An ANALYST or SERVICE_SUPERVISOR may request an exact filtered export. A different
AUDITOR (or other currently authorized holder of `exports.approve`) may approve or reject it. The
approval binds tenant, operation type, requester, and canonical filter hash; expires after 15
minutes; and can create only one artifact. Execution re-enters T09 current-state authorization, so
role revocation takes effect immediately. Retrying the same execution returns the same unexpired
artifact; changed filters, another tenant/requester, rejection, or expiry fail closed.

Approval state, decision audit, export artifact creation, execution state, and execution outcome
audit share caller-owned database transactions. The synchronous bounded export does not add a
broker/outbox boundary. Export content is stored only in the short-lived tenant-owned artifact and
is never copied to audit or logs.

## Operational configuration

- `RETENTION_EXECUTION_ENABLED`: emergency stop for destructive execution; dry-run is unaffected.
- `RETENTION_BATCH_LIMIT`: maximum rows per tenant/dataset batch.
- `RETENTION_TENANT_BATCH_LIMIT`: maximum tenants selected by one scheduled pass.
- Scheduled task: `compliance.run_retention_daily` on the existing `maintenance` queue.

Prometheus labels are limited to stable operation, dataset, and result vocabularies. Tenant IDs,
user IDs, email addresses, and resource IDs are deliberately excluded.
