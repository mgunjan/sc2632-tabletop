#!/usr/bin/env bash
# Evidence BEFORE containment. Run this before applying quarantine/q2/ or quarantine/q3/.
#
# Usage: ./quarantine/capture-evidence.sh <namespace> <pod> [container]
#
# What it captures, in order of volatility (most volatile first):
#   1. A container checkpoint (CRIU) via the kubelet Checkpoint API, if the node's
#      CRI supports it. KEP-2008. Works on CRI-O; containerd support depends on
#      version and CRIU being installed on the node. If unsupported, step 1 is
#      skipped and the script says so — it does NOT silently continue as if it worked.
#   2. Process list, open sockets, environment, and mounts from inside the container
#      (via an ephemeral debug container, so nothing in the suspect is executed).
#   3. Container logs (current + previous), Pod spec, events, and the node's name.
#   4. Relabel the Pod as suspect + quarantined so Q2/Q3 NetworkPolicies select it.
#
# Everything lands in ./evidence/<timestamp>-<ns>-<pod>/ with a SHA-256 manifest.
# Copy that directory OFF the cluster host before you do anything else.
set -euo pipefail

NS="${1:?namespace}"
POD="${2:?pod}"
CTR="${3:-}"
TS="$(date -u +%Y%m%dT%H%M%SZ)"
OUT="evidence/${TS}-${NS}-${POD}"
mkdir -p "$OUT"

# Redact secret-looking env values before anything touches disk. Runs locally with awk so it
# works the same on macOS and Linux and never depends on tools inside the suspect's image.
redact() {
  awk '{ l = toupper($0)
         if (l ~ /^[A-Z0-9_]*(TOKEN|SECRET|PASSWORD|PASSWD|API_KEY|PRIVATE_KEY|CREDENTIAL)[A-Z0-9_]*=/) {
           sub(/=.*/, "=<redacted>") }
         print }'
}

log() { printf '[%s] %s\n' "$(date -u +%H:%M:%S)" "$*" | tee -a "$OUT/capture.log"; }

log "Evidence capture for $NS/$POD -> $OUT"
MISSING=()   # evidence we tried to take and did not get; reported at the end, never hidden

# Preflight: a Pod that is gone or terminating yields empty logs and a failed debug container,
# and the script would otherwise hash those error messages and call it evidence. (Found live:
# a Pod picked from a list was already being evicted.)
PHASE="$(kubectl -n "$NS" get pod "$POD" -o jsonpath='{.status.phase}{"/"}{.metadata.deletionTimestamp}' 2>&1)"
case "$PHASE" in
  Running/) ;;
  Running/*) log "ABORT: $NS/$POD is terminating ($PHASE); capture from another replica or its node"; exit 3 ;;
  *) log "ABORT: $NS/$POD is not Running ($PHASE)"; exit 3 ;;
esac

NODE="$(kubectl -n "$NS" get pod "$POD" -o jsonpath='{.spec.nodeName}')"
[ -z "$CTR" ] && CTR="$(kubectl -n "$NS" get pod "$POD" -o jsonpath='{.spec.containers[0].name}')"
log "node=$NODE container=$CTR"

# 1. Checkpoint (KEP-2008). Requires feature gate ContainerCheckpoint on the kubelet
#    and a CRI that implements it. Uses the kubelet API via the API server proxy.
log "1/4 checkpoint attempt via kubelet API"
#    It is a POST, so `kubectl create --raw` (kubectl get --raw can only GET). The caller needs
#    RBAC for nodes/proxy. Verify once on your cluster before relying on it in an incident.
if kubectl create --raw "/api/v1/nodes/${NODE}/proxy/checkpoint/${NS}/${POD}/${CTR}" -f /dev/null \
     > "$OUT/checkpoint-response.json" 2> "$OUT/checkpoint-error.txt"; then
  log "    checkpoint requested; archive path is in checkpoint-response.json (on the node)"
else
  log "    checkpoint NOT available on this node/CRI (see checkpoint-error.txt). Continuing without it."
fi

# 2. Live state via ephemeral debug container. Read-only observation; nothing is
#    executed inside the suspect's process tree. Two things to know, both seen live:
#    - `kubectl debug` without --attach returns as soon as the container is CREATED; its output
#      only exists in that container's log. So: create, wait for it to finish, read its log.
#    - The debug container is itself a write to the Pod: it is recorded permanently in
#      spec.ephemeralContainers and cannot be removed. That is the evidence footprint; it is
#      why this step comes after the checkpoint and why pod.yaml is captured after it.
log "2/4 live state via ephemeral debug container"
DBG="evidence-$(date +%s)"
if kubectl -n "$NS" debug "$POD" --container="$DBG" --image="${DEBUG_IMAGE:-busybox:1.36}" --target="$CTR" \
     --profile=general -- sh -c '
    echo "== ps"; ps -o pid,ppid,user,etime,args
    echo "== netstat"; netstat -tulpan 2>/dev/null || cat /proc/net/tcp /proc/net/udp
    echo "== env (pid 1)"; tr "\0" "\n" < /proc/1/environ 2>/dev/null
    echo "== mounts"; cat /proc/1/mounts
    echo "== cwd"; ls -la /proc/1/cwd 2>/dev/null
  ' > "$OUT/debug-create.txt" 2>&1; then
  for _ in $(seq 1 30); do
    st="$(kubectl -n "$NS" get pod "$POD" -o jsonpath="{.status.ephemeralContainerStatuses[?(@.name=='$DBG')].state.terminated.reason}" 2>/dev/null)"
    [ -n "$st" ] && break; sleep 2
  done
  kubectl -n "$NS" logs "$POD" -c "$DBG" 2>&1 | redact > "$OUT/live-state.txt"
  grep -q '^== ps' "$OUT/live-state.txt" || { log "    debug container produced no output"; MISSING+=("live-state"); }
else
  log "    debug container could not be created (see debug-create.txt)"; MISSING+=("live-state")
fi

# 3. Logs, spec, events
log "3/4 logs, spec, events"
kubectl -n "$NS" logs "$POD" -c "$CTR" --timestamps > "$OUT/logs-current.txt" 2>&1 \
  || { log "    current logs NOT captured (see logs-current.txt)"; MISSING+=("logs-current"); }
# No previous container is normal (the container has not restarted); not a gap.
kubectl -n "$NS" logs "$POD" -c "$CTR" --timestamps --previous > "$OUT/logs-previous.txt" 2>&1 || true
kubectl -n "$NS" get pod "$POD" -o yaml > "$OUT/pod.yaml"
kubectl -n "$NS" get events --field-selector "involvedObject.name=${POD}" -o yaml > "$OUT/events.yaml" || true
kubectl get node "$NODE" -o yaml > "$OUT/node.yaml" || true

# 4. Mark the suspect so Q2/Q3 NetworkPolicies select it, and take it out of Service rotation
#    (Services that select trustfall.example/in-rotation=true stop routing to it; its ReplicaSet keeps it). This is the FIRST control
#    that touches the Pod, and it happens only after steps 1–3.
log "4/4 label suspect (trustfall.example/suspect=true, egress-profile=quarantined, in-rotation=false)"
kubectl -n "$NS" label pod "$POD" trustfall.example/suspect=true trustfall.example/egress-profile=quarantined trustfall.example/in-rotation=false --overwrite \
  | tee -a "$OUT/capture.log"

# Integrity manifest — sealed LAST. Nothing is written into $OUT after this line, so the
# manifest stays valid; the closing messages go to the terminal only.
log "sealing: SHA256SUMS over every file in $OUT"
( cd "$OUT" && find . -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 shasum -a 256 > SHA256SUMS 2>/dev/null \
  || find . -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS )
echo "done. $(wc -l < "$OUT/SHA256SUMS" | tr -d ' ') files hashed in $OUT/SHA256SUMS"
if [ ${#MISSING[@]} -gt 0 ]; then
  echo "INCOMPLETE: not captured: ${MISSING[*]}. The manifest seals what IS there; decide before containing whether that is enough."
  exit 4
fi
echo "NEXT: copy $OUT off this host (verify with: cd $OUT && shasum -a 256 -c SHA256SUMS), then kubectl apply -f quarantine/q2/"
