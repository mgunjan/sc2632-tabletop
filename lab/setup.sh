#!/usr/bin/env bash
# One-command lab.
#   Laptop (Docker Desktop):   ./lab/setup.sh                   # k3d cluster "trustfall"
#   Linux host / NUC:          RUNTIME=k3s ./lab/setup.sh       # an existing native k3s
# Needs: kubectl, helm, docker; plus k3d for the laptop path. kyverno CLI for the offline suites.
# k3s enforces NetworkPolicy out of the box. kind's default CNI does not.
#
# KYVERNO_MANIFEST=path/to/install.yaml skips helm and applies a local manifest instead (the
# air-gapped path; see lab/README.md "No network at the venue").
# Bash 3.2 / BSD userland safe (stock macOS). Its last step marks the cluster as a lab
# (ConfigMap kube-public/trustfall-lab), which the destructive tabletop scripts require.
set -euo pipefail
cd "$(dirname "$0")/.."
CLUSTER="${CLUSTER:-trustfall}"
RUNTIME="${RUNTIME:-k3d}"
# The k3s node image, pinned to what the lab results were recorded on (k3s v1.33.4). Keep in step
# with lab/offline-bundle.sh, which pre-pulls the same image.
K3S_IMAGE="${K3S_IMAGE:-rancher/k3s:v1.33.4-k3s1}"
# Verified against the official chart index on 2026-10-12: chart 3.9.1 ships app v1.19.1.
KYVERNO_CHART="${KYVERNO_CHART:-3.9.1}"
KYVERNO_APP_VERSION="${KYVERNO_APP_VERSION:-1.19.1}"
SCENARIO="${SCENARIO:-a}"          # a or b: which scenario's policies and workloads to load
case "$SCENARIO" in a) S=scenarios/a-compromised-library ;; b) S=scenarios/b-sidecar-agent ;;
  *) echo "SCENARIO must be a or b (C is evaluated offline: kyverno test scenarios/c-rogue-ops-agent/tests/)"; exit 2 ;; esac

case "$RUNTIME" in k3d|k3s) ;; *) echo "RUNTIME must be k3d or k3s"; exit 2 ;; esac
source lab/lib-guard.sh
if [ "$RUNTIME" = k3d ]; then
  new_cluster=
  if k3d cluster get "$CLUSTER" >/dev/null 2>&1; then
    # Read the named context before switching. Never bootstrap over an unrelated existing cluster.
    kubectl --context "k3d-$CLUSTER" --request-timeout=5s get --raw /api/v1/namespaces/kube-public/configmaps/trustfall-lab >/dev/null 2>&1 \
      || { echo "REFUSED: existing k3d cluster $CLUSTER has no accessible lab marker. Choose a fresh CLUSTER name." >&2; exit 3; }
    echo "cluster $CLUSTER exists (reusing it; k3d cluster delete $CLUSTER for a fresh one)"
  else
    # k3d accepts port zero but writes :0 into kubeconfig, even when Docker chose a real port.
    # Choose an available concrete port before cluster creation; keep the API bound to loopback.
    api_port="${LAB_API_PORT:-}"
    if [ -z "$api_port" ]; then
      api_port=$(python3 -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1", 0)); print(s.getsockname()[1]); s.close()')
    fi
    [[ "$api_port" =~ ^[1-9][0-9]{0,4}$ ]] && [ "$api_port" -le 65535 ] \
      || { echo "LAB_API_PORT must be between 1 and 65535" >&2; exit 2; }
    # A failure here is fatal (set -e): nothing below makes sense without the cluster.
    k3d cluster create "$CLUSTER" --image "$K3S_IMAGE" --servers 1 --agents 2 --wait --api-port "127.0.0.1:$api_port" \
      --k3s-arg "--disable=traefik@server:0"
    new_cluster=1
  fi
  # Never rely on whatever context kubectl happened to point at.
  kubectl config use-context "k3d-$CLUSTER" >/dev/null
  if [ -n "$new_cluster" ]; then
    # Ownership marker allows recovery after an interrupted install; no existing cluster is bootstrapped.
    kubectl -n kube-public create configmap trustfall-lab --from-literal=created-by=lab/setup.sh \
      --dry-run=client -o yaml | kubectl apply -f - >/dev/null
  fi
else
  # Native k3s setup must be explicitly marked as a lab (or the existing deliberate override used).
  lab_guard
fi

for ns in payments database observability storage gateway inventory hr-sync agents; do
  kubectl create namespace "$ns" --dry-run=client -o yaml | kubectl apply -f - >/dev/null
done

kubectl apply -f lab/rbac-humans.yaml >/dev/null   # IC and developer groups (the lab impersonates them)

# Stand-in images for every fixture, loaded straight into the cluster (no registry).
RUNTIME="$RUNTIME" CLUSTER="$CLUSTER" ./lab/images/build.sh

if [ -n "${KYVERNO_MANIFEST:-}" ]; then
  # Air-gapped path: images come from the local Docker cache (lab/offline-bundle.sh), not a registry.
  if [ "$RUNTIME" = k3d ] && [ -f lab/.bundle/kyverno-images.txt ]; then
    # shellcheck disable=SC2046
    k3d image import -c "$CLUSTER" $(cat lab/.bundle/kyverno-images.txt)
  fi
  # The release manifest ships with PolicyExceptions OFF (--enablePolicyException=false), and
  # that flag gates the CEL policies.kyverno.io PolicyException too. Every exception in this repo
  # would be silently ignored. Found on the first live install.
  # (awk, not sed: inserting a line with "\n" in a sed replacement is GNU-only.)
  awk '{
    sub(/--enablePolicyException=false/, "--enablePolicyException=true"); print
    if ($0 ~ /^ *- --enablePolicyException=true/) { ind = $0; sub(/-.*/, "", ind); print ind "- --exceptionNamespace=payments" }
  }' "$KYVERNO_MANIFEST" | kubectl apply --server-side -f - >/dev/null
  kubectl -n kyverno rollout status deploy --timeout=300s
else
  helm repo add kyverno https://kyverno.github.io/kyverno/ >/dev/null 2>&1 || true
  helm repo update >/dev/null
  app=$(helm show chart kyverno/kyverno --version "$KYVERNO_CHART" | awk '/^appVersion:/{gsub(/"|\047/, "", $2); sub(/^v/, "", $2); print $2; exit}')
  [ "$app" = "$KYVERNO_APP_VERSION" ] || { echo "REFUSED: chart $KYVERNO_CHART has app $app; expected $KYVERNO_APP_VERSION." >&2; exit 2; }
  helm upgrade --install kyverno kyverno/kyverno -n kyverno --create-namespace --wait --version "$KYVERNO_CHART" \
    --set admissionController.replicas=1 --set backgroundController.replicas=1 \
    --set cleanupController.replicas=1 --set reportsController.replicas=1 \
    --set features.policyExceptions.enabled=true --set-string 'features.policyExceptions.namespace=payments'
  # ^ PolicyExceptions are OFF by default (chart and release manifest alike); without these two
  #   lines every exception in this repo is ignored and the e2e exception checks fail.
  #   Only exceptions in payments count: an exception created in any other namespace would exempt payments
  #   Pods and skip Q1's exception freeze (review, Sep 28). Every exception in this repo lives in payments.
fi

# Things to reach, and the ServiceAccounts the fixtures name
# remove bare-Pod targets left by earlier versions of this script (exact names; Deployment Pods have suffixes)
for t in database/postgres hr-sync/hr-sync inventory/inventory observability/otel-collector storage/object-store; do
  kubectl -n "${t%/*}" delete pod "${t#*/}" --ignore-not-found >/dev/null 2>&1 || true
done
kubectl apply -f lab/targets.yaml >/dev/null
for ns in database hr-sync inventory observability storage; do kubectl -n "$ns" rollout status deploy --timeout=120s >/dev/null; done

# Baseline (Q0)
kubectl apply -f network/payments-baseline-networkpolicies.yaml >/dev/null
kubectl apply -f "$S/policies/" >/dev/null
wait_validating_policies >/dev/null || exit 2
kubectl apply -f exceptions/cleanup-policy-exceptions-rbac.yaml >/dev/null
kubectl apply -f exceptions/expire-policy-exceptions.yaml >/dev/null
# Guard the guardrail: a native (in-API-server) policy so nobody but Kyverno and platform admins
# can scale Kyverno to zero — which would make it delete its own webhooks. Needs Kubernetes >= 1.30.
kubectl apply -f guard/protect-the-guardrail.yaml >/dev/null

# Mark this cluster as a disposable lab. tabletop/consequences/*.sh (via lab/lib-guard.sh) refuse to
# run against any cluster without this marker. Idempotent.
kubectl -n kube-public create configmap trustfall-lab --from-literal=created-by=lab/setup.sh \
  --dry-run=client -o yaml | kubectl apply -f - >/dev/null

echo
echo "Lab up (runtime $RUNTIME, scenario $SCENARIO, context $(kubectl config current-context)). Marked as a lab: kube-public/trustfall-lab."
echo "  ./scripts/lab-e2e.sh      # everything below, asserted (scenario a)"
echo "Or step through by hand:"
echo "  kubectl apply -f $S/fixtures/payments-workloads.yaml    # backup-job is refused at admission"
echo "  kubectl apply -f lab/payments-deployment.yaml           # 3 replicas + PDB minAvailable 2"
echo "  kubectl apply -f quarantine/q1/"
echo "  ./quarantine/capture-evidence.sh payments <pod>"
echo "  kubectl apply -f quarantine/q2/"
