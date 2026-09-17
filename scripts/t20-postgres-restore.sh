#!/usr/bin/env bash
set -euo pipefail

BACKUP_ARTIFACT="${BACKUP_ARTIFACT:-}"
RESTORE_TARGET_DB="${RESTORE_TARGET_DB:-}"
SOURCE_DATABASE_ID="${SOURCE_DATABASE_ID:-}"
TARGET_ENVIRONMENT="${TARGET_ENVIRONMENT:-}"
T20_DESTRUCTIVE_CONFIRM="${T20_DESTRUCTIVE_CONFIRM:-NO}"

fail() {
  printf 't20-restore: %s\n' "$1" >&2
  exit 1
}

for command_name in psql createdb pg_restore sha256sum; do
  command -v "${command_name}" >/dev/null 2>&1 \
    || fail "required command not found: ${command_name}"
done

[[ "${T20_DESTRUCTIVE_CONFIRM}" == "YES_DISPOSABLE_ONLY" ]] \
  || fail "T20_DESTRUCTIVE_CONFIRM=YES_DISPOSABLE_ONLY is required"
[[ -n "${TARGET_ENVIRONMENT}" ]] || fail "TARGET_ENVIRONMENT is required"
[[ -n "${SOURCE_DATABASE_ID}" ]] || fail "SOURCE_DATABASE_ID is required"
[[ -n "${RESTORE_TARGET_DB}" ]] || fail "RESTORE_TARGET_DB is required"
[[ "${RESTORE_TARGET_DB}" =~ ^t20_[a-z0-9_]+$ ]] \
  || fail "RESTORE_TARGET_DB must start with t20_ and contain lowercase letters, digits, or underscores"

normalized_target="$(printf '%s' "${TARGET_ENVIRONMENT}" | tr '[:upper:]' '[:lower:]')"
case "${normalized_target}" in
  prod | production | *-prod | prod-* | *-production | production-*)
    fail "production-like targets are forbidden"
    ;;
esac

[[ -f "${BACKUP_ARTIFACT}" ]] || fail "backup artifact does not exist"
[[ -s "${BACKUP_ARTIFACT}" ]] || fail "backup artifact is empty"
[[ -f "${BACKUP_ARTIFACT}.metadata.json" ]] || fail "backup metadata is missing"
[[ -f "${BACKUP_ARTIFACT}.sha256" ]] || fail "backup checksum is missing"
[[ "${SOURCE_DATABASE_ID}" != "${RESTORE_TARGET_DB}" ]] \
  || fail "restore target must differ from the source database"

(
  cd "$(dirname "${BACKUP_ARTIFACT}")"
  sha256sum --check "$(basename "${BACKUP_ARTIFACT}.sha256")"
)
pg_restore --list "${BACKUP_ARTIFACT}" >/dev/null

if psql --dbname postgres --no-align --tuples-only \
  --command "SELECT 1 FROM pg_database WHERE datname = '${RESTORE_TARGET_DB}'" | grep -Fxq 1; then
  fail "restore target already exists; this script never overwrites a database"
fi

# RLS policies in the logical archive name these fixed, non-login capability
# roles. PostgreSQL global roles are not part of a per-database pg_dump, so a
# fresh cluster must have the safe role shells before pg_restore creates those
# policies. Login roles and passwords remain the deployment provisioner's job.
psql --dbname postgres --set ON_ERROR_STOP=1 --command "
DO \$\$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'star_warehouse_runtime') THEN
    CREATE ROLE star_warehouse_runtime NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'star_warehouse_maintenance') THEN
    CREATE ROLE star_warehouse_maintenance NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS;
  END IF;
END
\$\$;
ALTER ROLE star_warehouse_runtime NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS;
ALTER ROLE star_warehouse_maintenance NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS;
"

start_epoch="$(date +%s)"
createdb "${RESTORE_TARGET_DB}"
if ! pg_restore \
  --exit-on-error \
  --no-owner \
  --dbname "${RESTORE_TARGET_DB}" \
  "${BACKUP_ARTIFACT}"; then
  printf 't20-restore: restore failed; target %s was created and requires explicit operator cleanup\n' \
    "${RESTORE_TARGET_DB}" >&2
  exit 1
fi

# Older logical archives may predate ACL preservation. Rebuild only the
# accepted RLS capability grants from the restored policy inventory; do not
# grant application roles blanket access to unrelated tables.
psql --dbname "${RESTORE_TARGET_DB}" --set ON_ERROR_STOP=1 --command "
GRANT USAGE ON SCHEMA public TO star_warehouse_runtime, star_warehouse_maintenance;
GRANT SELECT ON TABLE public.tenants TO star_warehouse_runtime, star_warehouse_maintenance;
GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA public TO star_warehouse_runtime, star_warehouse_maintenance;
DO \$\$
DECLARE
  protected_table record;
BEGIN
  FOR protected_table IN
    SELECT DISTINCT schemaname, tablename
    FROM pg_policies
    WHERE 'star_warehouse_runtime' = ANY(roles)
       OR 'star_warehouse_maintenance' = ANY(roles)
  LOOP
    EXECUTE format(
      'GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE %I.%I TO star_warehouse_runtime, star_warehouse_maintenance',
      protected_table.schemaname,
      protected_table.tablename
    );
  END LOOP;
END
\$\$;
"
end_epoch="$(date +%s)"

revision="$(psql --dbname "${RESTORE_TARGET_DB}" --no-align --tuples-only \
  --command 'SELECT version_num FROM alembic_version')"
printf 't20-restore: target=%s alembic=%s restore_seconds=%s\n' \
  "${RESTORE_TARGET_DB}" "${revision}" "$((end_epoch - start_epoch))"
printf 't20-restore: run the normal migration and role-provisioning mechanism before application validation\n'
