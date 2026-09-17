#!/usr/bin/env sh
set -eu

: "${PGHOST:?PGHOST is required}"
: "${PGPORT:?PGPORT is required}"
: "${PGUSER:?PGUSER is required}"
: "${PGDATABASE:?PGDATABASE is required}"
: "${PGPASSWORD:?PGPASSWORD is required}"
: "${BACKUP_DIRECTORY:?BACKUP_DIRECTORY is required}"
: "${BACKUP_ENVIRONMENT_ID:?BACKUP_ENVIRONMENT_ID is required}"
: "${BACKUP_RETENTION_DAYS:?BACKUP_RETENTION_DAYS is required}"

ready_attempts="${BACKUP_DB_READY_ATTEMPTS:-60}"
case "${ready_attempts}" in
  '' | *[!0-9]*)
    printf 't20-backup: BACKUP_DB_READY_ATTEMPTS must be a positive integer\n' >&2
    exit 1
    ;;
esac
attempt=1
until pg_isready --quiet; do
  if [ "${attempt}" -ge "${ready_attempts}" ]; then
    printf 't20-backup: PostgreSQL did not become ready after %s attempts\n' "${ready_attempts}" >&2
    exit 1
  fi
  attempt=$((attempt + 1))
  sleep 2
done

case "${BACKUP_ENVIRONMENT_ID}" in
  prod | production | */prod | */production)
    printf 't20-backup: production-like environment IDs are forbidden by this demo job\n' >&2
    exit 1
    ;;
esac

case "${BACKUP_RETENTION_DAYS}" in
  '' | *[!0-9]*)
    printf 't20-backup: BACKUP_RETENTION_DAYS must be a positive integer\n' >&2
    exit 1
    ;;
esac

if [ "${BACKUP_RETENTION_DAYS}" -lt 1 ]; then
  printf 't20-backup: BACKUP_RETENTION_DAYS must be at least 1\n' >&2
  exit 1
fi

umask 077
mkdir -p "${BACKUP_DIRECTORY}"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
artifact="${PGDATABASE}-${timestamp}.dump"
temporary="${BACKUP_DIRECTORY}/.${artifact}.partial"
target="${BACKUP_DIRECTORY}/${artifact}"
metadata="${target}.metadata.json"
checksum="${target}.sha256"

cleanup() {
  rm -f "${temporary}"
}
trap cleanup EXIT HUP INT TERM

pg_dump \
  --format=custom \
  --no-owner \
  --file "${temporary}"
test -s "${temporary}"
pg_restore --list "${temporary}" >/dev/null
alembic_revision="$(psql --no-align --tuples-only --command 'SELECT version_num FROM alembic_version')"
mv "${temporary}" "${target}"
(
  cd "${BACKUP_DIRECTORY}"
  sha256sum "$(basename "${target}")" > "$(basename "${checksum}")"
)

{
  printf '{\n'
  printf '  "timestamp": "%s",\n' "${timestamp}"
  printf '  "application_version": "%s",\n' "${APPLICATION_VERSION:-unknown}"
  printf '  "image_revision": "%s",\n' "${APPLICATION_REVISION:-unknown}"
  printf '  "alembic_revision": "%s",\n' "${alembic_revision}"
  printf '  "database_identifier": "%s/%s",\n' "${BACKUP_ENVIRONMENT_ID}" "${PGDATABASE}"
  printf '  "backup_type": "postgresql-logical-custom"\n'
  printf '}\n'
} > "${metadata}"

find "${BACKUP_DIRECTORY}" -type f -mtime "+${BACKUP_RETENTION_DAYS}" \
  \( -name '*.dump' -o -name '*.metadata.json' -o -name '*.sha256' \) -delete

printf 't20-backup: artifact=%s metadata=%s checksum=%s\n' \
  "${target}" "${metadata}" "${checksum}"
