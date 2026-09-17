#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly SCRIPT_DIR
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
readonly REPO_ROOT
readonly K6_SCRIPT="${REPO_ROOT}/performance/k6/t20.js"

TARGET_ENVIRONMENT="${TARGET_ENVIRONMENT:-}"
BASE_URL="${BASE_URL:-}"
T20_PROFILE="${T20_PROFILE:-SMOKE}"
T20_HEAVY_OPT_IN="${T20_HEAVY_OPT_IN:-NO}"
K6_IMAGE="${K6_IMAGE:-grafana/k6:0.57.0}"
REPORT_DIR="${REPORT_DIR:-${REPO_ROOT}/reports/t20}"

fail() {
  printf 't20-load: %s\n' "$1" >&2
  exit 1
}

[[ -n "${TARGET_ENVIRONMENT}" ]] || fail "TARGET_ENVIRONMENT is required"
[[ -n "${BASE_URL}" ]] || fail "BASE_URL is required"

normalized_target="$(printf '%s' "${TARGET_ENVIRONMENT}" | tr '[:upper:]' '[:lower:]')"
case "${normalized_target}" in
  prod | production | *-prod | prod-* | *-production | production-*)
    fail "production-like targets are forbidden"
    ;;
esac

case "${T20_PROFILE}" in
  SMOKE) ;;
  BASELINE | SOAK_SHORT)
    [[ "${T20_HEAVY_OPT_IN}" == "YES" ]] \
      || fail "${T20_PROFILE} requires T20_HEAVY_OPT_IN=YES"
    [[ -n "${T20_USERNAME:-}" ]] || fail "T20_USERNAME is required"
    [[ -n "${T20_PASSWORD:-}" ]] || fail "T20_PASSWORD is required"
    [[ -n "${T20_TENANT_ID:-}" ]] || fail "T20_TENANT_ID is required"
    ;;
  *) fail "unsupported T20_PROFILE: ${T20_PROFILE}" ;;
esac

mkdir -p "${REPORT_DIR}"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
summary_path="${REPORT_DIR}/${normalized_target}-${T20_PROFILE}-${timestamp}.json"

export BASE_URL T20_PROFILE
if command -v k6 >/dev/null 2>&1; then
  k6 run --summary-export "${summary_path}" "${K6_SCRIPT}"
elif command -v docker >/dev/null 2>&1; then
  docker run --rm \
    --add-host host.docker.internal:host-gateway \
    --volume "${REPO_ROOT}/performance/k6:/work:ro" \
    --volume "${REPORT_DIR}:/reports" \
    --env BASE_URL \
    --env T20_PROFILE \
    --env T20_USERNAME \
    --env T20_PASSWORD \
    --env T20_TENANT_ID \
    "${K6_IMAGE}" run \
    --summary-export "/reports/$(basename "${summary_path}")" \
    /work/t20.js
else
  fail "k6 or Docker is required"
fi

printf 't20-load: profile=%s target=%s summary=%s\n' \
  "${T20_PROFILE}" "${TARGET_ENVIRONMENT}" "${summary_path}"
