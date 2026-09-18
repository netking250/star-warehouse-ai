# Tenant Boundary

This document is the operational source of truth for tenant identity, application-layer
isolation, infrastructure namespaces, and the T07 PostgreSQL RLS inventory.

## Identity and status

- The canonical tenant identifier is the case-sensitive `Tenant.id` string already stored in
  `tenant_id` columns. It is 1–64 ASCII letters, digits, underscores, or hyphens, begins with an
  alphanumeric character, and is never empty.
- Request and worker paths resolve the trusted identifier through `TenantResolver`, validate the
  `Tenant` row and status, and bind a complete `TenantContext`.
- `ACTIVE` permits normal access. `SUSPENDED` permits explicit read mode only and rejects new
  business/background work. `DISABLED` rejects every mode.
- A missing or unknown tenant fails closed. `default` is only the configured local/test/bootstrap
  tenant; it is not a production missing-identity fallback.
- Maintenance work uses `SystemContext`. It does not impersonate a tenant.

## PostgreSQL RLS and database roles

- `app.current_tenant_id` is the single PostgreSQL tenant setting. SQLAlchemy binds it with
  transaction-local `set_config(..., true)` and explicitly writes an empty value when no tenant is
  bound, preventing pooled connections from inheriting a prior tenant.
- `POSTGRES_USER` / `POSTGRES_PASSWORD` are migration and role-provisioning credentials.
  `POSTGRES_RUNTIME_*` selects the normal API/tenant-worker login, and
  `POSTGRES_MAINTENANCE_*` selects the separately deployed outbox/maintenance login.
- Both logins are hardened `NOSUPERUSER NOBYPASSRLS NOINHERIT` roles and switch per transaction to
  fixed non-login capability roles. Tenant-owned tables use `ENABLE` plus `FORCE ROW LEVEL
  SECURITY`, so table ownership alone is not a bypass.
- Runtime access always requires `tenant_id = app.current_tenant_id`. The maintenance capability
  may scan across tenants only when the database tenant setting is absent; if a maintenance
  operation binds a tenant, the same tenant predicate applies.
- Application `SUPER_ADMIN` is unrelated to the PostgreSQL maintenance capability and cannot
  select it. Compose runs tenant work and maintenance queues in separate worker processes.

## Resource namespaces

| Resource | Tenant boundary | System/global boundary |
|---|---|---|
| PostgreSQL ORM | Loader criteria for reads; tenant predicates for bulk update/delete; flush-time ownership and relationship checks | Explicit operational APIs or `skip_tenant_scope` inside reviewed infrastructure only |
| Redis | `{environment}:tenant:{tenant_id}:{scope}:{key}` through `TenantNamespace` | `{environment}:system:{scope}:{key}` through `TenantNamespace.system()` |
| Qdrant | Shared environment collection; every payload, query, and delete uses `app.retrieval.tenant_boundary` | Collection creation/recreation is bootstrap infrastructure, never tenant business work |
| Local knowledge files | Persist key `tenant/{tenant_id}/{object}`; the canonical adapter resolves it below the configured root | No global business-object prefix; Compose shares one local/demo named volume only with API and workers that require source bytes |
| Object storage/S3 | **NOT CURRENTLY ACTIVE** — no production object-storage Port or tenant-owned S3 objects exist | Define a tenant-aware Port before first use |

Tenant identifiers are intentionally not Prometheus labels. Use structured logs and traces for
tenant drill-down; resolution and cross-tenant failures log event code, tenant, operation, and
resource type without tokens, PII, or request payloads.

## Tenant-owned model inventory for T07

`TenantScopedModel` is the standard application guard (`ORM guard` below). Outbox and receipt rows
are tenant-owned but use reviewed operational seams because relays and recovery scans cross tenant
partitions. T07 must add RLS as a second layer without weakening these application guards.

Every row retains its T06 application guard. `FORCED / ALL` means revision `a5b6c7d8e9f0`
enables and forces RLS and supplies one `FOR ALL` policy with both `USING` and `WITH CHECK`.

| Table | Tenant column/type | Existing tenant index | Existing tenant-local constraint | RLS status |
|---|---|---|---|---|
| `users` | `tenant_id VARCHAR(64)` | `ix_users_tenant_id` | `uq_users_tenant_username`; `uq_users_tenant_email` | FORCED / ALL |
| `external_identities` | `tenant_id VARCHAR(64)` | `ix_external_identities_tenant_id` | global `uq_external_identities_issuer_subject` | FORCED / ALL via T08 revision `b6c7d8e9f0a1` |
| `authorization_audit_events` | `tenant_id VARCHAR(64)` | `ix_authorization_audit_events_tenant_id` | — | FORCED / ALL via T09 revision `c7d8e9f0a1b2` |
| `compliance_audit_events` | `tenant_id VARCHAR(64)` | `ix_compliance_audit_events_tenant_id` | — | FORCED / ALL via T11 revision `d8e9f0a1b2c3` |
| `approval_requests` | `tenant_id VARCHAR(64)` | `ix_approval_requests_tenant_id` | — | FORCED / ALL via T11 revision `d8e9f0a1b2c3` |
| `sensitive_export_artifacts` | `tenant_id VARCHAR(64)` | `ix_sensitive_export_artifacts_tenant_id` | `uq_sensitive_export_approval` | FORCED / ALL via T11 revision `d8e9f0a1b2c3` |
| `orders` | `tenant_id VARCHAR(64)` | `ix_orders_tenant_id` | `uq_orders_tenant_order_sn` | FORCED / ALL |
| `refund_applications` | `tenant_id VARCHAR(64)` | `ix_refund_applications_tenant_id` | — | FORCED / ALL |
| `complaint_tickets` | `tenant_id VARCHAR(64)` | `ix_complaint_tickets_tenant_id` | — | FORCED / ALL |
| `message_cards` | `tenant_id VARCHAR(64)` | `ix_message_cards_tenant_id` | `uq_message_cards_logical_message` via T12 | FORCED / ALL |
| `conversations` | `tenant_id VARCHAR(64)` | `ix_conversations_tenant_id` | `uq_conversations_identity` | FORCED / ALL via T12 revision `e9f0a1b2c3d4` |
| `conversation_turns` | `tenant_id VARCHAR(64)` | `ix_conversation_turns_tenant_id` | `uq_conversation_turns_identity`; `uq_conversation_turns_submission` | FORCED / ALL via T12 revision `e9f0a1b2c3d4` |
| `conversation_runs` | `tenant_id VARCHAR(64)` | `ix_conversation_runs_tenant_id` | `uq_conversation_runs_identity`; `uq_conversation_runs_attempt` | FORCED / ALL via T12 revision `e9f0a1b2c3d4` |
| `conversation_runtime_events` | `tenant_id VARCHAR(64)` | `ix_conversation_runtime_events_tenant_id` | `uq_runtime_events_identity`; `uq_runtime_events_sequence`; `uq_runtime_events_key` | FORCED / ALL via T12 revision `e9f0a1b2c3d4` |
| `conversation_tool_executions` | `tenant_id VARCHAR(64)` | `ix_conversation_tool_executions_tenant_id` | `uq_tool_executions_identity`; `uq_tool_executions_idempotency` | FORCED / ALL via T12 revision `e9f0a1b2c3d4` |
| `knowledge_documents` | `tenant_id VARCHAR(64)` | `ix_knowledge_documents_tenant_id` | — | FORCED / ALL |
| `user_profiles` | `tenant_id VARCHAR(64)` | `ix_user_profiles_tenant_id` | — | FORCED / ALL |
| `user_preferences` | `tenant_id VARCHAR(64)` | `ix_user_preferences_tenant_id` | — | FORCED / ALL |
| `interaction_summaries` | `tenant_id VARCHAR(64)` | `ix_interaction_summaries_tenant_id` | — | FORCED / ALL |
| `user_facts` | `tenant_id VARCHAR(64)` | `ix_user_facts_tenant_id` | — | FORCED / ALL |
| `agent_configs` | `tenant_id VARCHAR(64)` | `ix_agent_configs_tenant_id` | `uq_agent_configs_tenant_name` | FORCED / ALL |
| `routing_rules` | `tenant_id VARCHAR(64)` | `ix_routing_rules_tenant_id` | — | FORCED / ALL |
| `agent_config_versions` | `tenant_id VARCHAR(64)` | `ix_agent_config_versions_tenant_id` | — | FORCED / ALL |
| `agent_config_audit_logs` | `tenant_id VARCHAR(64)` | `ix_agent_config_audit_logs_tenant_id` | — | FORCED / ALL |
| `experiments` | `tenant_id VARCHAR(64)` | `ix_experiments_tenant_id` | — | FORCED / ALL |
| `experiment_variants` | `tenant_id VARCHAR(64)` | `ix_experiment_variants_tenant_id` | — | FORCED / ALL |
| `experiment_assignments` | `tenant_id VARCHAR(64)` | `ix_experiment_assignments_tenant_id` | — | FORCED / ALL |
| `experiment_metrics` | `tenant_id VARCHAR(64)` | `ix_experiment_metrics_tenant_id` | — | FORCED / ALL |
| `confidence_audits` | `tenant_id VARCHAR(64)` | `ix_confidence_audits_tenant_id` | — | FORCED / ALL |
| `message_feedbacks` | `tenant_id VARCHAR(64)` | `ix_message_feedbacks_tenant_id` | — | FORCED / ALL |
| `quality_scores` | `tenant_id VARCHAR(64)` | `ix_quality_scores_tenant_id` | — | FORCED / ALL |
| `shadow_test_results` | `tenant_id VARCHAR(64)` | `ix_shadow_test_results_tenant_id` | — | FORCED / ALL |
| `adversarial_test_runs` | `tenant_id VARCHAR(64)` | `ix_adversarial_test_runs_tenant_id` | — | FORCED / ALL |
| `graph_execution_logs` | `tenant_id VARCHAR(64)` | `ix_graph_execution_logs_tenant_id` | — | FORCED / ALL |
| `graph_node_logs` | `tenant_id VARCHAR(64)` | `ix_graph_node_logs_tenant_id` | — | FORCED / ALL |
| `supervisor_decisions` | `tenant_id VARCHAR(64)` | `ix_supervisor_decisions_tenant_id` | — | FORCED / ALL |
| `multi_intent_decision_logs` | `tenant_id VARCHAR(64)` | `ix_multi_intent_decision_logs_tenant_id` | — | FORCED / ALL |
| `prompt_effect_reports` | `tenant_id VARCHAR(64)` | `ix_prompt_effect_reports_tenant_id` | — | FORCED / ALL |
| `audit_logs` | `tenant_id VARCHAR(64)` | `ix_audit_logs_tenant_id` | — | FORCED / ALL |
| `pii_audit_logs` | `tenant_id VARCHAR(64)` | `ix_pii_audit_logs_tenant_id` | — | FORCED / ALL |
| `review_tickets` | `tenant_id VARCHAR(64)` | `ix_review_tickets_tenant_id` | — | FORCED / ALL |
| `reviewer_metrics` | `tenant_id VARCHAR(64)` | `ix_reviewer_metrics_tenant_id` | — | FORCED / ALL |
| `token_usage_logs` | `tenant_id VARCHAR(64)` | `ix_token_usage_logs_tenant_id` | — | FORCED / ALL |
| `optimization_suggestions` | `tenant_id VARCHAR(64)` | `ix_optimization_suggestions_tenant_id` | — | FORCED / ALL |
| `alert_rules` | `tenant_id VARCHAR(64)` | `ix_alert_rules_tenant_id` | — | FORCED / ALL |
| `alert_events` | `tenant_id VARCHAR(64)` | `ix_alert_events_tenant_id` | — | FORCED / ALL |
| `alert_notifications` | `tenant_id VARCHAR(64)` | `ix_alert_notifications_tenant_id` | — | FORCED / ALL |
| `outbox_events` | `tenant_id VARCHAR(64)` | `ix_outbox_events_tenant_id` | `uq_outbox_events_tenant_idempotency` | FORCED / ALL |
| `task_execution_receipts` | `tenant_id VARCHAR(64)` | `ix_task_execution_receipts_tenant_id` | `uq_task_execution_receipts_identity` | FORCED / ALL |

## Global/system inventory

| Table/resource | Classification | Notes |
|---|---|---|
| `tenants` | Global identity registry | Resolver must query without tenant ORM scope |
| `alembic_version` | System metadata | Migration framework only |
| Qdrant collection schema | System/bootstrap | Collections are environment-scoped; points are tenant-owned |
| Redis maintenance scans | System maintenance | Must use `all_tenant_key_pattern`; targeted cleanup rebuilds each tenant key |

There are no currently ambiguous SQLModel tables. The T07 catalog plus the additive T08, T09,
T11, and T12 inventories must cover the SQLModel tenant inventory; the catalog guard fails if any
listed table loses RLS, FORCE, `USING`, or `WITH CHECK` protection.
