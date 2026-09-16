#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly SCRIPT_DIR
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
readonly REPO_ROOT
readonly CHART_PATH="${REPO_ROOT}/deploy/helm/star-warehouse-ai"

NAMESPACE="${NAMESPACE:-star-warehouse-ai}"
RELEASE_NAME="${RELEASE_NAME:-star-warehouse-ai}"
VALUES_FILE="${VALUES_FILE:-${CHART_PATH}/values-demo.yaml}"
RUNTIME_SECRET="${RUNTIME_SECRET:-star-warehouse-ai-runtime}"
TLS_SECRET="${TLS_SECRET:-star-warehouse-ai-tls}"
PUBLIC_HOST="${PUBLIC_HOST:-}"
IMAGE_REPOSITORY="${IMAGE_REPOSITORY:-ghcr.io/netking250/star-warehouse-ai}"
IMAGE_DIGEST="${IMAGE_DIGEST:-}"
IMAGE_REVISION="${IMAGE_REVISION:-}"
TIMEOUT="${TIMEOUT:-10m}"
ALLOW_MUTABLE_DEMO_IMAGE="${ALLOW_MUTABLE_DEMO_IMAGE:-false}"
IMAGE_TAG="${IMAGE_TAG:-local}"

fail() {
  printf 'deploy-k3s: %s\n' "$1" >&2
  exit 1
}

for command_name in kubectl helm; do
  command -v "${command_name}" >/dev/null 2>&1 || fail "required command not found: ${command_name}"
done

[[ "${NAMESPACE}" =~ ^[a-z0-9]([-a-z0-9]*[a-z0-9])?$ ]] || fail "invalid Kubernetes namespace"
[[ "${RELEASE_NAME}" =~ ^[a-z0-9]([-a-z0-9]*[a-z0-9])?$ ]] || fail "invalid Helm release name"
[[ -f "${VALUES_FILE}" ]] || fail "values file not found: ${VALUES_FILE}"
[[ -n "${PUBLIC_HOST}" ]] || fail "PUBLIC_HOST is required"

kubectl cluster-info >/dev/null
kubectl get namespace "${NAMESPACE}" >/dev/null 2>&1 || kubectl create namespace "${NAMESPACE}"

kubectl get secret "${RUNTIME_SECRET}" --namespace "${NAMESPACE}" >/dev/null 2>&1 \
  || fail "required runtime Secret ${RUNTIME_SECRET} is missing in namespace ${NAMESPACE}"

required_secret_keys=(
  POSTGRES_PASSWORD
  POSTGRES_RUNTIME_PASSWORD
  POSTGRES_MAINTENANCE_PASSWORD
  REDIS_PASSWORD
  QDRANT_API_KEY
  CELERY_BROKER_URL
  CELERY_RESULT_BACKEND
  SECRET_KEY
  OPENAI_API_KEY
  DASHSCOPE_API_KEY
)

if [[ "${VALUES_FILE}" == *values-demo.yaml ]]; then
  required_secret_keys+=(RABBITMQ_USER RABBITMQ_PASSWORD)
fi

# Go-template variables must reach kubectl literally.
# shellcheck disable=SC2016
available_secret_keys="$(kubectl get secret "${RUNTIME_SECRET}" --namespace "${NAMESPACE}" \
  -o go-template='{{range $key, $value := .data}}{{$key}}{{"\n"}}{{end}}')"

for secret_key in "${required_secret_keys[@]}"; do
  grep -Fxq "${secret_key}" <<<"${available_secret_keys}" \
    || fail "required key ${secret_key} is missing from Secret ${RUNTIME_SECRET}"
  encoded_value="$(kubectl get secret "${RUNTIME_SECRET}" --namespace "${NAMESPACE}" \
    -o "jsonpath={.data.${secret_key}}")"
  if [[ -z "${encoded_value}" && "${secret_key}" != "OPENAI_API_KEY" && "${secret_key}" != "DASHSCOPE_API_KEY" ]]; then
    fail "required key ${secret_key} is empty in Secret ${RUNTIME_SECRET}"
  fi
done

kubectl get secret "${TLS_SECRET}" --namespace "${NAMESPACE}" >/dev/null 2>&1 \
  || fail "required TLS Secret ${TLS_SECRET} is missing in namespace ${NAMESPACE}"

helm_args=(
  upgrade
  --install
  "${RELEASE_NAME}"
  "${CHART_PATH}"
  --namespace "${NAMESPACE}"
  --values "${VALUES_FILE}"
  --atomic
  --wait
  --wait-for-jobs
  --timeout "${TIMEOUT}"
  --set-string "secretRef.name=${RUNTIME_SECRET}"
  --set-string "demoInfrastructure.secretRefName=${RUNTIME_SECRET}"
  --set-string "ingress.host=${PUBLIC_HOST}"
  --set-string "ingress.tls.secretName=${TLS_SECRET}"
  --set-string "config.CORS_ORIGINS=[\\\"https://${PUBLIC_HOST}\\\"]"
  --set-string "config.OIDC_REDIRECT_URI=https://${PUBLIC_HOST}/api/v1/oidc/callback"
  --set-string "image.repository=${IMAGE_REPOSITORY}"
)

if [[ -n "${IMAGE_DIGEST}" ]]; then
  [[ "${IMAGE_DIGEST}" =~ ^sha256:[a-f0-9]{64}$ ]] || fail "IMAGE_DIGEST must be a sha256 digest"
  helm_args+=(--set-string "image.digest=${IMAGE_DIGEST}" --set-string image.tag=)
elif [[ "${ALLOW_MUTABLE_DEMO_IMAGE}" == "true" ]]; then
  [[ "${IMAGE_TAG}" != "latest" ]] || fail "latest is forbidden even for the explicit demo override"
  helm_args+=(
    --set-string "image.tag=${IMAGE_TAG}"
    --set image.allowMutableTag=true
  )
else
  fail "IMAGE_DIGEST is required; set ALLOW_MUTABLE_DEMO_IMAGE=true only for a local image smoke"
fi

if [[ -n "${IMAGE_REVISION}" ]]; then
  helm_args+=(--set-string "image.buildRevision=${IMAGE_REVISION}")
fi

helm "${helm_args[@]}"

for component in api worker maintenance-worker scheduler outbox; do
  deployment="${RELEASE_NAME}-${component}"
  if kubectl get deployment "${deployment}" --namespace "${NAMESPACE}" >/dev/null 2>&1; then
    kubectl rollout status "deployment/${deployment}" --namespace "${NAMESPACE}" --timeout "${TIMEOUT}"
  fi
done

kubectl get service "${RELEASE_NAME}" --namespace "${NAMESPACE}" >/dev/null
kubectl get ingress "${RELEASE_NAME}" --namespace "${NAMESPACE}" >/dev/null
helm status "${RELEASE_NAME}" --namespace "${NAMESPACE}"

printf 'Deployment completed. Verify HTTPS health at https://%s/health after DNS resolves.\n' "${PUBLIC_HOST}"
