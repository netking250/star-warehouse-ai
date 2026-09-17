#!/usr/bin/env bash
set -euo pipefail

NAMESPACE="${NAMESPACE:-}"
RELEASE_NAME="${RELEASE_NAME:-star-warehouse-ai}"
TARGET_ENVIRONMENT="${TARGET_ENVIRONMENT:-}"
T20_DESTRUCTIVE_CONFIRM="${T20_DESTRUCTIVE_CONFIRM:-NO}"
ACTION="${1:-}"
TIMEOUT="${TIMEOUT:-5m}"

fail() {
  printf 't20-failure: %s\n' "$1" >&2
  exit 1
}

command -v kubectl >/dev/null 2>&1 || fail "required command not found: kubectl"

[[ "${T20_DESTRUCTIVE_CONFIRM}" == "YES_DISPOSABLE_ONLY" ]] \
  || fail "T20_DESTRUCTIVE_CONFIRM=YES_DISPOSABLE_ONLY is required"
[[ -n "${TARGET_ENVIRONMENT}" ]] || fail "TARGET_ENVIRONMENT is required"
[[ "${NAMESPACE}" =~ ^t20-[a-z0-9]([-a-z0-9]*[a-z0-9])?$ ]] \
  || fail "NAMESPACE must be an explicit disposable t20-* namespace"
[[ "${RELEASE_NAME}" =~ ^[a-z0-9]([-a-z0-9]*[a-z0-9])?$ ]] \
  || fail "invalid RELEASE_NAME"

normalized_target="$(printf '%s' "${TARGET_ENVIRONMENT}" | tr '[:upper:]' '[:lower:]')"
case "${normalized_target}" in
  prod | production | *-prod | prod-* | *-production | production-*)
    fail "production-like targets are forbidden"
    ;;
esac

kubectl get namespace "${NAMESPACE}" >/dev/null
printf 't20-failure: context=%s namespace=%s action=%s production_touched=NO\n' \
  "$(kubectl config current-context)" "${NAMESPACE}" "${ACTION}"

delete_one_pod() {
  component="$1"
  pod_name="$(kubectl get pod --namespace "${NAMESPACE}" \
    --selector "app.kubernetes.io/instance=${RELEASE_NAME},app.kubernetes.io/component=${component}" \
    --output jsonpath='{.items[0].metadata.name}')"
  [[ -n "${pod_name}" ]] || fail "no pod found for component ${component}"
  kubectl delete pod "${pod_name}" --namespace "${NAMESPACE}" --wait=false
}

scale_deployment() {
  component="$1"
  replicas="$2"
  kubectl scale deployment "${RELEASE_NAME}-${component}" \
    --namespace "${NAMESPACE}" --replicas "${replicas}"
  if [[ "${replicas}" != "0" ]]; then
    kubectl rollout status "deployment/${RELEASE_NAME}-${component}" \
      --namespace "${NAMESPACE}" --timeout "${TIMEOUT}"
  fi
}

scale_statefulset() {
  component="$1"
  replicas="$2"
  kubectl scale statefulset "${RELEASE_NAME}-${component}" \
    --namespace "${NAMESPACE}" --replicas "${replicas}"
  if [[ "${replicas}" != "0" ]]; then
    kubectl rollout status "statefulset/${RELEASE_NAME}-${component}" \
      --namespace "${NAMESPACE}" --timeout "${TIMEOUT}"
  fi
}

case "${ACTION}" in
  restart-api) delete_one_pod api ;;
  restart-worker) delete_one_pod worker ;;
  restart-scheduler) delete_one_pod scheduler ;;
  restart-relay) delete_one_pod outbox ;;
  pause-worker) scale_deployment worker 0 ;;
  resume-worker) scale_deployment worker 1 ;;
  pause-relay) scale_deployment outbox 0 ;;
  resume-relay) scale_deployment outbox 1 ;;
  outage-postgresql) scale_statefulset postgres 0 ;;
  restore-postgresql) scale_statefulset postgres 1 ;;
  outage-redis) scale_statefulset redis 0 ;;
  restore-redis) scale_statefulset redis 1 ;;
  outage-rabbitmq) scale_statefulset rabbitmq 0 ;;
  restore-rabbitmq) scale_statefulset rabbitmq 1 ;;
  outage-qdrant) scale_statefulset qdrant 0 ;;
  restore-qdrant) scale_statefulset qdrant 1 ;;
  *)
    fail "action must be restart-{api,worker,scheduler,relay}, pause/resume-{worker,relay}, or outage/restore-{postgresql,redis,rabbitmq,qdrant}"
    ;;
esac

printf 't20-failure: action=%s completed; run bounded recovery checks before the next injection\n' \
  "${ACTION}"
