#!/usr/bin/env bash
set -euo pipefail

NAMESPACE="${NAMESPACE:-}"
RELEASE_NAME="${RELEASE_NAME:-star-warehouse-ai}"
TARGET_ENVIRONMENT="${TARGET_ENVIRONMENT:-}"

fail() {
  printf 't20-backup-now: %s\n' "$1" >&2
  exit 1
}

command -v kubectl >/dev/null 2>&1 || fail "kubectl is required"
[[ -n "${TARGET_ENVIRONMENT}" ]] || fail "TARGET_ENVIRONMENT is required"
[[ "${NAMESPACE}" =~ ^t20-[a-z0-9]([-a-z0-9]*[a-z0-9])?$ ]] \
  || fail "NAMESPACE must be an explicit disposable t20-* namespace"

normalized_target="$(printf '%s' "${TARGET_ENVIRONMENT}" | tr '[:upper:]' '[:lower:]')"
case "${normalized_target}" in
  prod | production | *-prod | prod-* | *-production | production-*)
    fail "production-like targets are forbidden"
    ;;
esac

cronjob="${RELEASE_NAME}-backup"
job="${RELEASE_NAME}-backup-manual-$(date -u +%Y%m%d%H%M%S)"
kubectl get cronjob "${cronjob}" --namespace "${NAMESPACE}" >/dev/null
kubectl create job "${job}" --from "cronjob/${cronjob}" --namespace "${NAMESPACE}"
kubectl wait --for=condition=complete "job/${job}" --namespace "${NAMESPACE}" --timeout=15m
kubectl logs "job/${job}" --namespace "${NAMESPACE}"
pod="$(kubectl get pod --namespace "${NAMESPACE}" --selector "job-name=${job}" \
  --output jsonpath='{.items[0].metadata.name}')"
printf 't20-backup-now: production_touched=NO job=%s pod=%s\n' "${job}" "${pod}"
