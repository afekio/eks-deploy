#!/usr/bin/env bash
# ============================================================================
# deploy.sh - one-command deployment of the full main-app stack via Helm.
# ----------------------------------------------------------------------------
# Steps:
#   1. (optional) sync values from Terraform outputs  -> values-from-tf.yaml
#   2. install platform operators (CloudNativePG + ingress-nginx)
#   3. install the main-app umbrella chart (frontend, backend, auth, db, ingress)
#
# Usage:
#   ./deploy.sh                # full deploy, sync from Terraform
#   ./deploy.sh --no-tf-sync   # skip Terraform sync (use committed values only)
#   ./deploy.sh --app-only     # skip platform operators, deploy app chart only
# ============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
CHART_DIR="${SCRIPT_DIR}/main-app"
PLATFORM_DIR="${SCRIPT_DIR}/platform"
RELEASE="main-app"
NAMESPACE="main-app"

TF_SYNC=true
INSTALL_PLATFORM=true

for arg in "$@"; do
  case "$arg" in
    --no-tf-sync) TF_SYNC=false ;;
    --app-only)   INSTALL_PLATFORM=false ;;
    *) echo "Unknown option: $arg" >&2; exit 1 ;;
  esac
done

for cmd in helm kubectl; do
  command -v "$cmd" >/dev/null 2>&1 || { echo "ERROR: '$cmd' not found in PATH" >&2; exit 1; }
done

# ── 1. Sync values from Terraform (optional) ────────────────────────────────
VALUE_ARGS=(-f "${CHART_DIR}/values.yaml")
if [[ "${TF_SYNC}" == "true" ]]; then
  echo "==> Syncing values from Terraform..."
  "${SCRIPT_DIR}/sync-values-from-tf.sh"
  VALUE_ARGS+=(-f "${SCRIPT_DIR}/values-from-tf.yaml")
elif [[ -f "${SCRIPT_DIR}/values-from-tf.yaml" ]]; then
  VALUE_ARGS+=(-f "${SCRIPT_DIR}/values-from-tf.yaml")
fi

# ── 2. Platform operators (prerequisites) ───────────────────────────────────
if [[ "${INSTALL_PLATFORM}" == "true" ]]; then
  echo "==> Installing platform operators..."
  helm repo add cnpg https://cloudnative-pg.github.io/charts >/dev/null 2>&1 || true
  helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx >/dev/null 2>&1 || true
  helm repo update >/dev/null

  helm upgrade --install cnpg cnpg/cloudnative-pg \
    --namespace cnpg-system --create-namespace \
    -f "${PLATFORM_DIR}/cnpg-operator-values.yaml" --wait

  helm upgrade --install ingress-nginx ingress-nginx/ingress-nginx \
    --namespace ingress-nginx --create-namespace \
    -f "${PLATFORM_DIR}/ingress-nginx-values.yaml" --wait
fi

# ── 3. Application umbrella chart ───────────────────────────────────────────
echo "==> Deploying main-app umbrella chart..."
helm upgrade --install "${RELEASE}" "${CHART_DIR}" \
  --namespace "${NAMESPACE}" --create-namespace \
  "${VALUE_ARGS[@]}"

echo "==> Done. Ingress entrypoint:"
kubectl get svc -n ingress-nginx ingress-nginx-controller \
  -o jsonpath='{.status.loadBalancer.ingress[0].hostname}{"\n"}' 2>/dev/null || true
