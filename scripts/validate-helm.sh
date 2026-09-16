#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly SCRIPT_DIR
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
readonly REPO_ROOT
readonly CHART_PATH="${REPO_ROOT}/deploy/helm/star-warehouse-ai"
readonly TEST_DIGEST="sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
TEMP_DIR="$(mktemp -d)"
readonly TEMP_DIR
trap 'rm -rf "${TEMP_DIR}"' EXIT

for command_name in helm kubeconform; do
  command -v "${command_name}" >/dev/null 2>&1 || {
    printf 'validate-helm: required command not found: %s\n' "${command_name}" >&2
    exit 1
  }
done

helm lint "${CHART_PATH}"
helm lint "${CHART_PATH}" --values "${CHART_PATH}/values-demo.yaml"
helm lint "${CHART_PATH}" \
  --values "${CHART_PATH}/values-production.yaml" \
  --set-string "image.digest=${TEST_DIGEST}"

helm template star-warehouse-ai "${CHART_PATH}" \
  --namespace star-warehouse-ai > "${TEMP_DIR}/default.yaml"
helm template star-warehouse-ai "${CHART_PATH}" \
  --namespace star-warehouse-ai \
  --values "${CHART_PATH}/values-demo.yaml" > "${TEMP_DIR}/demo.yaml"
helm template star-warehouse-ai "${CHART_PATH}" \
  --namespace star-warehouse-ai \
  --values "${CHART_PATH}/values-production.yaml" \
  --set-string "image.digest=${TEST_DIGEST}" > "${TEMP_DIR}/production.yaml"

kubeconform \
  -strict \
  -summary \
  -kubernetes-version 1.30.0 \
  "${TEMP_DIR}/default.yaml" \
  "${TEMP_DIR}/demo.yaml" \
  "${TEMP_DIR}/production.yaml"

if helm template star-warehouse-ai "${CHART_PATH}" \
  --values "${CHART_PATH}/values-production.yaml" >/dev/null 2>&1; then
  printf 'validate-helm: production rendering unexpectedly accepted a missing digest\n' >&2
  exit 1
fi

if helm template star-warehouse-ai "${CHART_PATH}" \
  --set-string image.tag=latest >/dev/null 2>&1; then
  printf 'validate-helm: rendering unexpectedly accepted the latest tag\n' >&2
  exit 1
fi

if grep -Eiq 'privileged:[[:space:]]*true|hostNetwork:[[:space:]]*true|hostPID:[[:space:]]*true|hostPath:|cluster-admin|image:.*:latest' "${TEMP_DIR}"/*.yaml; then
  printf 'validate-helm: forbidden manifest security pattern detected\n' >&2
  exit 1
fi

if grep -Eiq 'kind:[[:space:]]*Secret|POSTGRES_PASSWORD:|SECRET_KEY:|OPENAI_API_KEY:' "${TEMP_DIR}"/*.yaml; then
  printf 'validate-helm: rendered manifest contains a Secret object or secret key material\n' >&2
  exit 1
fi

grep -q 'automountServiceAccountToken: false' "${TEMP_DIR}/production.yaml"
grep -q 'runAsNonRoot: true' "${TEMP_DIR}/production.yaml"
grep -q 'allowPrivilegeEscalation: false' "${TEMP_DIR}/production.yaml"
grep -q 'alembic upgrade head' "${TEMP_DIR}/production.yaml"
grep -q 'alembic current' "${TEMP_DIR}/production.yaml"

printf 'Helm lint, rendering, client validation, failure checks, and static security checks passed.\n'
