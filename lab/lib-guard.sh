# shellcheck shell=bash
# Sourced, not run. A safety rail for every script that changes the cluster kubectl points at.
#
#   source lab/lib-guard.sh; lab_guard     # exits 3 unless this is a lab cluster
#
# A lab cluster is one that carries the marker ConfigMap kube-public/trustfall-lab, which
# lab/setup.sh creates as its last step. TRUSTFALL_LAB_OK=1 overrides the check (for a lab you
# built by hand; prefer creating the marker instead:
#   kubectl -n kube-public create configmap trustfall-lab --from-literal=created-by=manual).
# Bash 3.2 compatible (stock macOS).

LAB_GUARD_MSG="This script changes the cluster kubectl points at (it scales the policy engine to zero, deletes Pods). Run it only on a disposable lab cluster created by lab/setup.sh."

# lab_marker_present: true if this is a lab cluster (marker present, or the override is set).
# Never exits; preflight.sh uses it to report instead of stopping.
lab_marker_present() {
  [ "${TRUSTFALL_LAB_OK:-}" = 1 ] && return 0
  # raw GET: one request, no API discovery round-trips
  kubectl --request-timeout=5s get --raw /api/v1/namespaces/kube-public/configmaps/trustfall-lab >/dev/null 2>&1
}

# lab_guard: refuse to continue (exit 3) unless lab_marker_present.
lab_guard() {
  lab_marker_present && return 0
  local ctx
  ctx=$(kubectl config current-context 2>/dev/null || echo '?')
  {
    echo "REFUSED: no lab marker (ConfigMap kube-public/trustfall-lab) on kubectl context '$ctx'."
    echo "$LAB_GUARD_MSG"
    echo "If this IS a disposable lab cluster: kubectl -n kube-public create configmap trustfall-lab --from-literal=created-by=manual"
    echo "(or set TRUSTFALL_LAB_OK=1 for this run)."
  } >&2
  exit 3
}
