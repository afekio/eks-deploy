#!/usr/bin/env bash
# ============================================================================
# destroy.sh - full teardown of the main-app stack deployed via Helm.
# ----------------------------------------------------------------------------
# Deletes, in the correct order and waiting at each stage:
#   1. the main-app application Helm release (frontend/backend/auth/db/ingress)
#   2. the CloudNativePG cluster + its PVCs/PVs (finalizers handled)
#   3. the EFS StorageClass
#   4. the platform operators (ingress-nginx, CloudNativePG)
#   5. the namespaces (force-finalized if stuck in Terminating)
#   6. (optional) the CloudNativePG CRDs
#
# It force-removes finalizers and force-deletes stuck pods/PVCs/namespaces so a
# half-deleted / "Terminating" cluster gets fully cleaned up.
#
# Does NOT touch Terraform or any AWS infrastructure (EFS, S3, IAM, EKS itself).
#
# Usage:
#   ./destroy.sh              # asks for confirmation
#   ./destroy.sh -y           # no confirmation
#   ./destroy.sh -y --keep-operators   # keep cnpg + ingress-nginx installed
#   ./destroy.sh -y --keep-crds        # keep CloudNativePG CRDs
# ============================================================================
set -uo pipefail

# ── Config ──────────────────────────────────────────────────────────────────
APP_RELEASE="main-app"
APP_NS="main-app"
INGRESS_RELEASE="ingress-nginx"
INGRESS_NS="ingress-nginx"
CNPG_RELEASE="cnpg"
CNPG_NS="cnpg-system"
STORAGECLASS="efs-sc"
CNPG_CLUSTER="app-postgres"

TIMEOUT="${TIMEOUT:-180}"          # per-stage wait timeout (seconds)
ASSUME_YES=false
KEEP_OPERATORS=false
KEEP_CRDS=false

for arg in "$@"; do
  case "$arg" in
    -y|--yes)         ASSUME_YES=true ;;
    --keep-operators) KEEP_OPERATORS=true ;;
    --keep-crds)      KEEP_CRDS=true ;;
    -h|--help)        grep '^#' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "Unknown option: $arg" >&2; exit 1 ;;
  esac
done

# ── Helpers ─────────────────────────────────────────────────────────────────
log() { echo -e "\033[1;36m==>\033[0m $*"; }
sub() { echo "    $*"; }

for cmd in kubectl helm; do
  command -v "$cmd" >/dev/null 2>&1 || { echo "ERROR: '$cmd' not found in PATH" >&2; exit 1; }
done

# Remove metadata.finalizers from every resource of a type in a namespace.
clear_finalizers() {
  local type="$1"; local ns="${2:-}"
  local -a nsflag=(); [[ -n "$ns" ]] && nsflag=(-n "$ns")
  local name
  for name in $(kubectl get "$type" "${nsflag[@]}" -o name 2>/dev/null); do
    kubectl patch "$name" "${nsflag[@]}" --type=merge \
      -p '{"metadata":{"finalizers":null}}' >/dev/null 2>&1 || true
  done
}

# Force-delete every pod in a namespace (grace 0), then clear PVC finalizers.
force_clear_namespace_content() {
  local ns="$1"
  kubectl get ns "$ns" >/dev/null 2>&1 || return 0
  sub "Force-deleting pods in ${ns}..."
  kubectl delete pods --all -n "$ns" --grace-period=0 --force >/dev/null 2>&1 || true
  sub "Clearing PVC finalizers in ${ns}..."
  clear_finalizers pvc "$ns"
  kubectl delete pvc --all -n "$ns" --grace-period=0 --force >/dev/null 2>&1 || true
}

# Wait until a named resource is gone (returns 0 when gone, 1 on timeout).
wait_gone() {
  local desc="$1"; shift
  local elapsed=0
  while kubectl get "$@" >/dev/null 2>&1; do
    if (( elapsed >= TIMEOUT )); then
      echo; sub "timeout waiting for ${desc}"; return 1
    fi
    sleep 5; elapsed=$((elapsed+5)); printf '.'
  done
  echo; sub "${desc} is gone."
  return 0
}

# Force a namespace out of "Terminating" by clearing its finalizers.
force_finalize_namespace() {
  local ns="$1"
  kubectl get ns "$ns" >/dev/null 2>&1 || return 0
  sub "Force-finalizing namespace ${ns}..."
  kubectl get ns "$ns" -o json 2>/dev/null \
    | python3 -c "import sys,json; d=json.load(sys.stdin); d.setdefault('spec',{})['finalizers']=[]; sys.stdout.write(json.dumps(d))" \
    | kubectl replace --raw "/api/v1/namespaces/${ns}/finalize" -f - >/dev/null 2>&1 || true
}

delete_namespace() {
  local ns="$1"
  kubectl get ns "$ns" >/dev/null 2>&1 || { sub "namespace ${ns} already gone."; return 0; }
  log "Deleting namespace ${ns}..."
  kubectl delete ns "$ns" --wait=false >/dev/null 2>&1 || true
  force_clear_namespace_content "$ns"
  if ! wait_gone "namespace ${ns}" ns "$ns"; then
    force_finalize_namespace "$ns"
    wait_gone "namespace ${ns}" ns "$ns" || sub "namespace ${ns} still present - check manually."
  fi
}

helm_uninstall() {
  local release="$1"; local ns="$2"
  if helm status "$release" -n "$ns" >/dev/null 2>&1; then
    log "Uninstalling Helm release '${release}' (ns ${ns})..."
    helm uninstall "$release" -n "$ns" --wait --timeout "${TIMEOUT}s" >/dev/null 2>&1 \
      || helm uninstall "$release" -n "$ns" >/dev/null 2>&1 || true
    sub "release '${release}' uninstalled."
  else
    sub "Helm release '${release}' not found (skipping)."
  fi
}

# ── Confirmation ────────────────────────────────────────────────────────────
if [[ "$ASSUME_YES" != "true" ]]; then
  echo "This will DELETE the entire main-app deployment from the current cluster:"
  echo "  - Helm releases: ${APP_RELEASE}$( [[ "$KEEP_OPERATORS" == true ]] || echo ", ${INGRESS_RELEASE}, ${CNPG_RELEASE}" )"
  echo "  - Namespaces:    ${APP_NS}$( [[ "$KEEP_OPERATORS" == true ]] || echo ", ${INGRESS_NS}, ${CNPG_NS}" )"
  echo "  - StorageClass:  ${STORAGECLASS} + released efs PVs"
  echo "  (Terraform / AWS infrastructure is NOT touched.)"
  read -r -p "Type 'yes' to continue: " ans
  [[ "$ans" == "yes" ]] || { echo "Aborted."; exit 1; }
fi

CTX="$(kubectl config current-context 2>/dev/null || echo unknown)"
log "Target cluster context: ${CTX}"

# ── 1. Application release ──────────────────────────────────────────────────
# Delete the CNPG cluster first while the operator is still alive so its
# finalizer can be processed cleanly.
if kubectl get cluster "${CNPG_CLUSTER}" -n "${APP_NS}" >/dev/null 2>&1; then
  log "Deleting CloudNativePG cluster '${CNPG_CLUSTER}'..."
  kubectl delete cluster "${CNPG_CLUSTER}" -n "${APP_NS}" --wait=false >/dev/null 2>&1 || true
  if ! wait_gone "cluster ${CNPG_CLUSTER}" cluster "${CNPG_CLUSTER}" -n "${APP_NS}"; then
    clear_finalizers cluster "${APP_NS}"
    wait_gone "cluster ${CNPG_CLUSTER}" cluster "${CNPG_CLUSTER}" -n "${APP_NS}" || true
  fi
fi

helm_uninstall "${APP_RELEASE}" "${APP_NS}"

# ── 2. Leftover PVCs / released PVs in the app namespace ────────────────────
if kubectl get ns "${APP_NS}" >/dev/null 2>&1; then
  log "Cleaning leftover PVCs in ${APP_NS}..."
  clear_finalizers pvc "${APP_NS}"
  kubectl delete pvc --all -n "${APP_NS}" --grace-period=0 --force >/dev/null 2>&1 || true
fi

log "Deleting released PVs bound to ${STORAGECLASS}..."
for pv in $(kubectl get pv -o jsonpath="{range .items[?(@.spec.storageClassName==\"${STORAGECLASS}\")]}{.metadata.name}{'\n'}{end}" 2>/dev/null); do
  sub "PV ${pv}"
  kubectl patch pv "$pv" --type=merge -p '{"metadata":{"finalizers":null}}' >/dev/null 2>&1 || true
  kubectl delete pv "$pv" --grace-period=0 --force >/dev/null 2>&1 || true
done

# ── 3. StorageClass ─────────────────────────────────────────────────────────
if kubectl get sc "${STORAGECLASS}" >/dev/null 2>&1; then
  log "Deleting StorageClass ${STORAGECLASS}..."
  kubectl delete sc "${STORAGECLASS}" --ignore-not-found >/dev/null 2>&1 || true
fi

# ── 4. Platform operators ───────────────────────────────────────────────────
if [[ "$KEEP_OPERATORS" != "true" ]]; then
  helm_uninstall "${INGRESS_RELEASE}" "${INGRESS_NS}"
  helm_uninstall "${CNPG_RELEASE}" "${CNPG_NS}"
fi

# ── 5. Namespaces ───────────────────────────────────────────────────────────
delete_namespace "${APP_NS}"
if [[ "$KEEP_OPERATORS" != "true" ]]; then
  delete_namespace "${INGRESS_NS}"
  delete_namespace "${CNPG_NS}"
fi

# ── 6. CRDs (optional) ──────────────────────────────────────────────────────
if [[ "$KEEP_OPERATORS" != "true" && "$KEEP_CRDS" != "true" ]]; then
  log "Deleting CloudNativePG CRDs..."
  for crd in $(kubectl get crd -o name 2>/dev/null | grep 'cnpg.io'); do
    sub "$crd"
    kubectl delete "$crd" --ignore-not-found >/dev/null 2>&1 || true
  done
fi

log "Teardown complete."
kubectl get ns 2>/dev/null | grep -E "${APP_NS}|${INGRESS_NS}|${CNPG_NS}" \
  && log "NOTE: some namespaces still listed above (may finish terminating shortly)." \
  || log "All target namespaces removed."
