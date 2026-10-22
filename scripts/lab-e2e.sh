#!/usr/bin/env bash
# End-to-end on a LIVE cluster (after ./lab/setup.sh). Proves on a real API server, a real CNI
# and a real kubelet what the offline suites cannot:
#
#   admission (Kyverno)  ·  NetworkPolicy enforcement  ·  evidence capture against a kubelet
#   the Q2 -> Q3 network interaction  ·  the PDB + Q3 capacity stall  ·  the ephemeral-container gap
#
#   ./lab/setup.sh && ./scripts/lab-e2e.sh
#
# Bash 3.2 compatible (stock macOS): no mapfile, no GNU-only flags.
#
# Every check either passes or fails. Nothing is silently skipped: a probe that cannot run is a
# FAIL, because "skipped" is how the previous version of this script hid a NetworkPolicy test
# behind Q2's registry rule (the probe used docker.io's busybox, Q2 refused it, the test skipped).
set -uo pipefail
cd "$(dirname "$0")/.." || exit 2
FAIL=0; KNOWN=0
pass()  { printf '  \033[32mPASS\033[0m %s\n' "$1"; }
fail()  { printf '  \033[31mFAIL\033[0m %s\n' "$1"; FAIL=1; }
known() { printf '  \033[33mGAP \033[0m %s\n' "$1"; KNOWN=$((KNOWN+1)); }   # documented limitation, asserted to still exist
expect_refused() {
  local d=$1; shift
  if out=$("$@" 2>&1); then fail "$d — was ADMITTED: $out"
  elif grep -qiE "denied|policy|refused|violation|quarantine" <<<"$out"; then pass "$d"
  else fail "$d — failed for another reason: $out"; fi
}
# expect_refused_by <description> <pattern naming the refusing control> <cmd...>: a refusal only counts if
# the message names the control we are testing, not just any policy (review, Sep 28: checks that can't fail).
expect_refused_by() {
  local d=$1 pat=$2; shift 2
  if out=$("$@" 2>&1); then fail "$d — was ADMITTED: $out"
  elif grep -qiE "$pat" <<<"$out"; then pass "$d"
  else fail "$d — refused, but not by the control under test (wanted /$pat/): $out"; fi
}
expect_admitted() { local d=$1; shift; if out=$("$@" 2>&1); then pass "$d"; else fail "$d — refused: $out"; fi; }
A=scenarios/a-compromised-library
NS=payments

# Fixture extraction requires PyYAML. Fail before reset/mutation rather than running
# admission tests with empty input and reporting a cascade of unrelated failures.
if ! python3 -c 'import yaml' >/dev/null 2>&1; then
  echo "PREFLIGHT: python3 needs PyYAML. Activate .venv-session (see REHEARSAL.md) before running the live checks."
  exit 2
fi

kubectl get ns $NS >/dev/null 2>&1 || { echo "run ./lab/setup.sh first"; exit 2; }
# shellcheck source=../lab/lib-guard.sh
source lab/lib-guard.sh; lab_guard   # only on a disposable lab cluster: this scales the policy engine to zero
echo "commit $(git rev-parse --short HEAD 2>/dev/null || echo unknown)$(git diff --quiet 2>/dev/null || echo ' +uncommitted changes') · $(kubectl version 2>/dev/null | grep -i server | head -1) · $(kyverno version 2>/dev/null | head -1)"

# ------------------------------------------------------------------ reset to Q0
echo "Resetting to Q0..."
kubectl -n kyverno scale deploy kyverno-admission-controller --replicas=1 >/dev/null 2>&1   # in case a previous run stopped mid-way
kubectl delete -f quarantine/q3/ --ignore-not-found >/dev/null 2>&1
kubectl delete -f quarantine/q2/ --ignore-not-found >/dev/null 2>&1
kubectl delete -f quarantine/q1/ --ignore-not-found >/dev/null 2>&1
# Fully qualified: with Kyverno's legacy kyverno.io/v2 CRD also installed, plain `policyexception`
# resolves to the LEGACY group, and runbooks that say "kubectl get policyexception" look in the
# wrong place (seen live). Our exceptions are policies.kyverno.io.
PX=policyexceptions.policies.kyverno.io
kubectl -n $NS delete $PX --all --ignore-not-found >/dev/null 2>&1
kubectl -n $NS delete pod -l '!tier' --ignore-not-found --wait=true >/dev/null 2>&1
kubectl -n $NS delete deploy/payments-api --ignore-not-found --wait=true >/dev/null 2>&1
kubectl -n $NS delete pod -l tier=api --ignore-not-found --wait=true >/dev/null 2>&1
kubectl -n $NS delete events --field-selector reason=FailedCreate --ignore-not-found >/dev/null 2>&1   # so the Q3 event check sees only this run
kubectl delete $PX -A -l trustfall.example/e2e-stray=true --ignore-not-found >/dev/null 2>&1
kubectl apply -f network/payments-baseline-networkpolicies.yaml >/dev/null
# Preflight: every admission check below assumes Kyverno is answering. When it isn't (seen live:
# the node garbage-collected the admission controller's image while it was scaled to zero, and the
# pull then failed), Kyverno's rules silently don't run and the run reports a dozen confusing FAILs.
# Stop here with the real cause instead.
if ! kubectl -n kyverno rollout status deploy/kyverno-admission-controller --timeout=120s >/dev/null 2>&1; then
  echo "PREFLIGHT: Kyverno's admission controller is not Ready, so no Kyverno rule would run."
  kubectl -n kyverno get pods -l app.kubernetes.io/component=admission-controller 2>&1 | sed 's/^/  /'
  echo "  Fix that first (kubectl -n kyverno describe pod -l app.kubernetes.io/component=admission-controller)."
  exit 2
fi
kubectl wait --for=condition=Ready validatingpolicies.policies.kyverno.io --all --timeout=120s >/dev/null 2>&1 || true
sleep 3

pod_yaml() {
  python3 - "$1" "$2" <<'EOF'
import sys, yaml
for d in yaml.safe_load_all(open(sys.argv[1])):
    if d and d["metadata"]["name"] == sys.argv[2]:
        print(yaml.safe_dump(d)); break
EOF
}
apply_pod() { pod_yaml "$A/fixtures/payments-workloads.yaml" "$1" | kubectl apply -f - ; }
reach() {  # reach <pod> <url> -> 0 if an HTTP response came back
  kubectl -n $NS exec "$1" -- wget -q -T 3 -O- "$2" >/dev/null 2>&1
}
reach_eventually() {  # a NEW Pod's allow rules take a moment to be programmed; blocks are checked once
  for _ in 1 2 3 4 5 6; do reach "$1" "$2" && return 0; sleep 3; done; return 1
}
tcp() {  # tcp <pod> <host> <port> [ns] -> 0 if a TCP connection opened (busybox nc)
  kubectl -n "${4:-$NS}" exec "$1" -- sh -c "nc -w 3 $2 $3 </dev/null >/dev/null 2>&1"
}
resolves() { kubectl -n $NS exec "$1" -- nslookup -timeout=2 -retry=1 postgres.database.svc.cluster.local >/dev/null 2>&1; }
DNS_IP="$(kubectl -n kube-system get svc kube-dns -o jsonpath='{.spec.clusterIP}')"

for ns in database hr-sync inventory observability storage; do
  kubectl -n $ns rollout status deploy --timeout=90s >/dev/null 2>&1 || { fail "target in $ns not Ready — re-run ./lab/setup.sh"; }
done

echo; echo "Q0 baseline — admission   [CSF PR.PS-01 · PSS Baseline]"
expect_admitted "payments-api (profile db) is admitted"             apply_pod payments-api
expect_admitted "monitoring-agent (profile monitoring) is admitted" apply_pod monitoring-agent
expect_refused  "backup-job (profile storage) is REFUSED"           apply_pod backup-job
expect_admitted "report-runner (docker.io image) admitted — registry rule is Audit" apply_pod report-runner
expect_admitted "payments-api Deployment (3 replicas) + PDB minAvailable 2" kubectl apply -f lab/payments-deployment.yaml
kubectl -n $NS rollout status deploy/payments-api --timeout=120s >/dev/null 2>&1 \
  && pass "all 3 replicas Ready" || fail "payments-api replicas not Ready (stand-in images loaded? ./lab/images/build.sh)"
R=(); while IFS= read -r line; do [ -n "$line" ] && R+=("$line"); done < <(kubectl -n $NS get pods -l tier=api -o jsonpath='{range .items[*]}{.metadata.name}{"\n"}{end}')
[ ${#R[@]} -ge 3 ] || { fail "need 3 replicas, have ${#R[@]}"; echo "LAB E2E: FAILURES ABOVE"; exit 1; }

echo; echo "Q0 baseline — NetworkPolicy is enforced (real CNI, real Pods)"
# Positive control first: from a namespace with no NetworkPolicy every target answers, so a "cannot reach"
# below means the policy blocked it, not that the target was down (review, Sep 28).
kubectl -n default run ctl-probe --image=registry.trustfall.internal/platform/lab-target:1 --restart=Never >/dev/null 2>&1 || true
kubectl -n default wait --for=condition=Ready pod/ctl-probe --timeout=60s >/dev/null 2>&1
ctl_ok=1; for t in "hr-sync.hr-sync 8080" "inventory.inventory 8080" "kubernetes.default.svc 443" "postgres.database 5432"; do
  set -- $t; tcp ctl-probe "$1" "$2" default || { ctl_ok=0; fail "positive control: an unrestricted Pod cannot reach $1:$2 — the checks below would prove nothing"; }
done; [ $ctl_ok = 1 ] && pass "positive control: an unrestricted Pod reaches hr-sync, inventory, the API server and the database"
reach_eventually "${R[0]}" http://postgres.database:5432/ && pass "profile db reaches database:5432" || fail "profile db cannot reach database:5432"
tcp "${R[0]}" hr-sync.hr-sync 8080         && fail "profile db reached hr-sync — NOT enforced" || pass "profile db cannot reach hr-sync"
tcp "${R[0]}" inventory.inventory 8080     && fail "profile db reached inventory"              || pass "profile db cannot reach inventory"
tcp "${R[0]}" kubernetes.default.svc 443   && fail "profile db reached the API server"        || pass "profile db cannot reach the API server"

echo; echo "Exception — time-boxed, and only from payments"
# An exception created OUTSIDE payments must not exempt payments Pods (Kyverno's exceptionNamespace=payments).
stray=$(sed -e 's/namespace: payments/namespace: default/' -e 's/name: backup-job-egress-storage/name: stray-backup-job/' $A/exceptions/backup-job-egress-storage.yaml)
kubectl apply -f - <<<"$stray" >/dev/null 2>&1 && kubectl -n default label $PX stray-backup-job trustfall.example/e2e-stray=true >/dev/null 2>&1; sleep 3
expect_refused_by "an exception created outside payments is ignored: backup-job still REFUSED" "egress|profile" apply_pod backup-job
kubectl -n default delete $PX stray-backup-job --ignore-not-found >/dev/null 2>&1
expect_admitted "exception for backup-job is created"             kubectl apply -f $A/exceptions/backup-job-egress-storage.yaml
sleep 3
expect_admitted "backup-job is now admitted under the exception"  apply_pod backup-job
ttl=$(kubectl -n $NS get $PX backup-job-egress-storage -o jsonpath='{.metadata.labels.cleanup\.kyverno\.io/ttl}')
[ "$ttl" = 24h ] && pass "exception carries cleanup TTL ($ttl)" || fail "exception TTL label missing"

echo; echo "Q1 Freeze   [CSF RS.MA-02 · RS.MA-04 · PR.AA-05: the override is identity-checked]"
expect_admitted "declare Q1"                                      kubectl apply -f quarantine/q1/
sleep 3
qfix=$(python3 -c "import yaml; d=[x for x in yaml.safe_load_all(open('$A/fixtures/quarantine-q1-exceptions.yaml')) if x]; print(yaml.safe_dump(d[0]))")
icok=$(python3 -c "import yaml; d=[x for x in yaml.safe_load_all(open('$A/fixtures/quarantine-q1-exceptions.yaml')) if x]; print(yaml.safe_dump(d[1]))")
expect_refused_by "quick-fix exception (no owner/TTL/override) is REFUSED by the Q1 exception freeze" "Quarantine Q1" kubectl apply -f - <<<"$qfix"
IC="--as=ic@trustfall.example --as-group=trustfall:incident-commanders --as-group=system:authenticated"
DEV="--as=dev@trustfall.example --as-group=trustfall:developers --as-group=system:authenticated"
expect_refused_by "a developer who copies the IC override annotation is REFUSED (identity, not just annotation)" "Quarantine Q1" kubectl $DEV apply -f - <<<"$icok"
expect_admitted "incident commander's exception is admitted"      kubectl $IC apply -f - <<<"$icok"
# The freeze is enforced by the platform, not asked of the agent (cf. Replit/SaaStr, July 2025).
kubectl apply -f lab/ops-agent-legacy-rbac.yaml >/dev/null
AGENT=--as=system:serviceaccount:agents:ops-agent
reps=$(kubectl -n $NS get deploy payments-api -o jsonpath='{.spec.replicas}')
out=$(kubectl $AGENT -n $NS scale deploy payments-api --replicas=$((reps+1)) --dry-run=server 2>&1) \
  && fail "Q1: the ops agent scaled payments-api during the freeze: $out" \
  || { grep -q "agents are frozen" <<<"$out" && pass "Q1: the ops agent is REFUSED by the freeze itself (its RBAC would allow it)" || fail "Q1 agent freeze: refused for another reason: $out"; }
expect_admitted "Q1: a human's change still goes through during the freeze" \
  kubectl $IC -n $NS annotate deploy payments-api trustfall.example/q1-check=ok --overwrite --dry-run=server

echo; echo "Evidence before containment — capture-evidence.sh against a real kubelet   [CSF RS.AN-07]"
S1=${R[0]}; S2=${R[1]}; CLEAN=${R[2]}
EV=$(mktemp -d)
( cd "$EV" && "$OLDPWD/quarantine/capture-evidence.sh" $NS "$S1" api ) > "$EV/out.txt" 2>&1; rc=$?
dir=$(ls -d "$EV"/evidence/*/ 2>/dev/null | head -1)
[ $rc = 0 ] && pass "capture completed (exit 0)" || fail "capture exit $rc: $(tail -3 "$EV/out.txt")"
grep -q '^== ps' "$dir/live-state.txt" 2>/dev/null && pass "live process list captured via ephemeral debug container" || fail "no live state captured"
grep -qE "started|heartbeat" "$dir/logs-current.txt" 2>/dev/null && pass "container logs captured" || fail "logs not captured"
( cd "$dir" && { sha256sum -c --quiet SHA256SUMS 2>/dev/null || shasum -a 256 -c --quiet SHA256SUMS 2>/dev/null; } ) && pass "SHA256SUMS verifies" || fail "hash manifest does not verify"
if grep -q "checkpoint requested" "$EV/out.txt"; then pass "kubelet checkpoint taken (CRIU present on this node)"
else known "no memory checkpoint: $(head -c 160 "$dir/checkpoint-error.txt" | tr '\n' ' ')"; fi
[ "$(kubectl -n $NS get pod "$S1" -o jsonpath='{.metadata.labels.trustfall\.example/suspect}')" = true ] && pass "suspect relabelled LAST" || fail "suspect not relabelled"
[ -n "$(kubectl -n $NS get pod "$S1" -o jsonpath='{.spec.ephemeralContainers[*].name}')" ] \
  && pass "the debug container is recorded permanently in the Pod spec (the evidence footprint)" || fail "no ephemeral container recorded"

echo; echo "Q2 Constrain   [CSF RS.MI-01 · D3FEND Network Isolation, DNS Allowlisting, Executable Allowlisting]"
expect_admitted "declare Q2 (admission + network)" kubectl apply -f quarantine/q2/
sleep 3
reach "$S1" http://postgres.database:5432/    && fail "suspect still reaches the database" || pass "suspect is DNS-only: database unreachable"
resolves "$S1"                                 && pass "suspect still resolves DNS (Q2 allows it)" || fail "suspect lost DNS at Q2"
tcp "$S1" "$DNS_IP" 53                        && pass "suspect can open the TCP/53 DNS fallback path" || fail "suspect lost TCP/53 DNS fallback at Q2"
reach "$CLEAN" http://postgres.database:5432/ && pass "clean replica still reaches the database (payroll continues)" || fail "clean replica lost the database"
kubectl -n gateway run gw-probe --image=registry.trustfall.internal/platform/lab-target:1 --restart=Never >/dev/null 2>&1 || true
kubectl -n gateway wait --for=condition=Ready pod/gw-probe --timeout=60s >/dev/null 2>&1
ip_s=$(kubectl -n $NS get pod "$S1" -o jsonpath='{.status.podIP}'); ip_c=$(kubectl -n $NS get pod "$CLEAN" -o jsonpath='{.status.podIP}')
kubectl -n gateway exec gw-probe -- wget -q -T 3 -O- "http://$ip_c:8443/" >/dev/null 2>&1 && pass "gateway reaches a clean replica on 8443" || fail "gateway cannot reach clean replica"
kubectl -n gateway exec gw-probe -- wget -q -T 3 -O- "http://$ip_s:8443/" >/dev/null 2>&1 && fail "gateway still sends traffic to the DNS-only suspect" || pass "gateway ingress to the suspect is closed"
sleep 2
eps=$(kubectl -n $NS get endpointslices -l kubernetes.io/service-name=payments-api -o jsonpath='{.items[*].endpoints[*].targetRef.name}')
grep -q "$S1" <<<"$eps" && fail "suspect is still a Service endpoint (in-cluster callers would be routed to it and time out)" \
                      || pass "suspect is out of the Service endpoints (in-rotation=false), and still running"
grep -q "$CLEAN" <<<"$eps" && pass "clean replica is still a Service endpoint" || fail "clean replica dropped out of the Service"
[ "$(kubectl -n $NS get deploy payments-api -o jsonpath='{.status.replicas}')" = 3 ] \
  && pass "the ReplicaSet still owns the suspect: no replacement spawned" || fail "ReplicaSet replica count changed"
sidecar_pod() {  # sidecar_pod <init|native> : an approved app container plus a docker.io init container
  local rp=""; [ "$1" = native ] && rp=',"restartPolicy":"Always"'
  printf '{"apiVersion":"v1","kind":"Pod","metadata":{"name":"q2-%s-probe","namespace":"payments","labels":{"trustfall.example/egress-profile":"none"}},"spec":{"initContainers":[{"name":"side","image":"docker.io/library/busybox:1.36","command":["true"]%s,"securityContext":{"allowPrivilegeEscalation":false}}],"containers":[{"name":"app","image":"registry.trustfall.internal/platform/lab-target:1","securityContext":{"allowPrivilegeEscalation":false}}]}}' "$1" "$rp"
}
expect_refused_by "a docker.io INIT container is REFUSED under Q2 (every container the Pod starts is checked)" "only images from" \
  kubectl create --dry-run=server -f - <<<"$(sidecar_pod init)"
expect_refused_by "a docker.io NATIVE SIDECAR (initContainer, restartPolicy Always) is REFUSED under Q2" "only images from" \
  kubectl create --dry-run=server -f - <<<"$(sidecar_pod native)"
DEVL="--as=dev@trustfall.example --as-group=trustfall:developers --as-group=system:authenticated"
ICL="--as=ic@trustfall.example --as-group=trustfall:incident-commanders --as-group=system:authenticated"
expect_refused_by "a developer removing the suspect label is REFUSED (the containment is labels; they are protected)" "only an incident commander" \
  kubectl $DEVL -n $NS label pod "$S1" trustfall.example/suspect- --dry-run=server
expect_refused_by "a developer putting the suspect back into Service rotation is REFUSED" "only an incident commander" \
  kubectl $DEVL -n $NS label pod "$S1" trustfall.example/in-rotation=true --overwrite --dry-run=server
expect_admitted "the incident commander can lift it (the staged way back)" \
  kubectl $ICL -n $NS label pod "$S1" trustfall.example/in-rotation=true --overwrite --dry-run=server
expect_admitted "a developer can still tighten (add a label) on the suspect" \
  kubectl $DEVL -n $NS label pod "$S1" trustfall.example/e2e-note=checked --overwrite --dry-run=server
expect_refused "a new docker.io Pod is REFUSED under Q2" \
  kubectl -n $NS run q2-probe --image=docker.io/library/busybox:1.36 --labels=trustfall.example/egress-profile=none \
    --overrides='{"spec":{"containers":[{"name":"q2-probe","image":"docker.io/library/busybox:1.36","securityContext":{"allowPrivilegeEscalation":false}}]}}'
expect_admitted "relabel report-runner (non-compliant image) under Q2's Deny" \
  kubectl -n $NS label pod report-runner trustfall.example/suspect=true trustfall.example/egress-profile=quarantined --overwrite
# Admission policies match `pods`; `kubectl debug` writes `pods/ephemeralcontainers`. Q2 now
# covers the subresource (quarantine/q2/ephemeral-containers.yaml) for containers a request ADDS.
expect_refused_by "kubectl debug with a docker.io image is REFUSED under Q2 (subresource covered)" "debug containers in payments must use an image from" \
  kubectl -n $NS debug "$CLEAN" --image=docker.io/library/busybox:1.36 --profile=general -- true
expect_refused_by "a PRIVILEGED debug container (--profile=sysadmin) is REFUSED, even with the approved image" "privileged debug" \
  kubectl -n $NS debug "$CLEAN" --image=registry.trustfall.internal/platform/debug:1 --profile=sysadmin -- true
expect_admitted "kubectl debug with the approved debug image is admitted, even on a Pod that already has an old debug container" \
  kubectl -n $NS debug "$S1" --image=registry.trustfall.internal/platform/debug:1 --profile=general -- true

echo; echo "Q3 Isolate — the network step needs a label; Q3 blocks replacement capacity under the PDB   [CSF RS.MI-01 · D3FEND Isolate, not Evict]"
expect_admitted "declare Q3" kubectl apply -f quarantine/q3/
sleep 3
ovr='{"apiVersion":"v1","kind":"Pod","metadata":{"generateName":"ovr-","namespace":"payments","labels":{"trustfall.example/egress-profile":"none","trustfall.example/probe":"true"},"annotations":{"trustfall.example/quarantine-override":"incident-commander"}},"spec":{"containers":[{"name":"p","image":"registry.trustfall.internal/platform/lab-target:1","securityContext":{"allowPrivilegeEscalation":false}}]}}'
expect_refused  "Q3: the override annotation from a developer is REFUSED" kubectl $DEV create -f - <<<"$ovr"
expect_admitted "Q3: the same Pod from the incident commander is admitted" kubectl $IC create -f - <<<"$ovr"
kubectl -n $NS delete pod -l trustfall.example/probe=true --ignore-not-found --wait=false >/dev/null 2>&1
resolves "$S1" && pass "Q3 applied but suspect not yet labelled isolated: DNS still works (NetworkPolicies only add allows)" \
               || fail "expected Q2's DNS allow to still apply before the isolated label"
kubectl -n $NS label pod "$S1" trustfall.example/isolated=true --overwrite >/dev/null; sleep 2
resolves "$S1" && fail "isolated suspect still resolves DNS" || pass "isolated suspect loses DNS too — Q3 deny-all now actually holds"
tcp "$S1" "$DNS_IP" 53 && fail "isolated suspect can still open TCP/53 to DNS" || pass "isolated suspect also loses TCP/53 DNS access"
# Second suspect found (same image). Evidence first, then try to evict both.
( cd "$EV" && DEBUG_IMAGE=registry.trustfall.internal/platform/debug:1 "$OLDPWD/quarantine/capture-evidence.sh" $NS "$S2" api ) > "$EV/out2.txt" 2>&1 \
  && pass "evidence captured on suspect 2 under Q3 with the approved debug image" || fail "evidence capture on suspect 2 under Q3: $(tail -2 "$EV/out2.txt")"
evict() { printf '{"apiVersion":"policy/v1","kind":"Eviction","metadata":{"name":"%s","namespace":"%s"}}' "$1" $NS > "$EV/ev.json"
          kubectl create --raw "/api/v1/namespaces/$NS/pods/$1/eviction" -f "$EV/ev.json" 2>&1; }
out=$(evict "$S1"); grep -qE '"code":201|Success' <<<"$out" && pass "evict suspect 1: allowed by the PDB (3 → 2)" || fail "evict suspect 1: $out"
sleep 8
fc=$(kubectl -n $NS get events --field-selector reason=FailedCreate -o jsonpath='{.items[*].message}')
grep -qi "quarantine q3" <<<"$fc" && pass "replacement Pod REFUSED by Q3 — the ReplicaSet cannot restore capacity" || fail "no Q3 FailedCreate event: $fc"
out=$(evict "$S2"); grep -qi "disruption budget" <<<"$out" && pass "evict suspect 2: PDB refuses voluntary disruption at minAvailable until capacity is restored" || fail "evict suspect 2: $out"
[ -n "$(kubectl -n $NS get pod "$S1" -o jsonpath='{.metadata.deletionTimestamp}' 2>/dev/null)" ] || ! kubectl -n $NS get pod "$S1" >/dev/null 2>&1 \
  && pass "…and evicting suspect 1 is destroying it — only the evidence captured beforehand survives" \
  || fail "suspect 1 is not being deleted after eviction"


echo; echo "Guard the guardrail — the agent, the scale subresource, and the policy engine itself   [ATT&CK v19 T1685 · CSF PR.AA-05]"
kubectl delete -f quarantine/q3/ --ignore-not-found >/dev/null 2>&1
kubectl apply -f lab/ops-agent-legacy-rbac.yaml -f scenarios/c-rogue-ops-agent/policies/deny-agent-mutation-outside-namespace.yaml >/dev/null
kubectl delete -f guard/protect-the-guardrail.yaml --ignore-not-found >/dev/null 2>&1
sleep 5
AGENT=--as=system:serviceaccount:agents:ops-agent
kubectl apply -f quarantine/q1/freeze-agent-changes.yaml >/dev/null; sleep 3
out=$(kubectl $AGENT -n kyverno scale deploy kyverno-admission-controller --replicas=0 --dry-run=server 2>&1) \
  && fail "Q1 declared, guard removed: the agent could scale Kyverno to 0: $out" \
  || { grep -q "agents are frozen" <<<"$out" && pass "Q1 declared, guard removed: the native freeze still stops the agent switching Kyverno off" || fail "freeze vs Kyverno scale: $out"; }
# Lift the Q1 agent freeze ("Monday"): the next checks test Scenario C's own policy and the unguarded engine.
kubectl delete -f quarantine/q1/freeze-agent-changes.yaml --ignore-not-found >/dev/null 2>&1
sleep 3
reps=$(kubectl -n $NS get deploy payments-api -o jsonpath='{.spec.replicas}')
expect_refused "the agent's PATCH of payments-api outside its namespace is REFUSED" kubectl $AGENT -n $NS patch deploy payments-api -p "{\"spec\":{\"replicas\":$((reps+1))}}"
expect_refused "agent uses kubectl scale (deployments/scale subresource) — now covered" kubectl $AGENT -n $NS scale deploy payments-api --replicas=$((reps+1))
# Kyverno never sees its own namespace or kube-system (resourceFilters), so Scenario C's rule cannot stop the agent
# changing kube-system: RBAC is the real control there. Asserted, so the claim stays true.
if out=$(kubectl $AGENT -n kube-system annotate deploy coredns trustfall.example/e2e=probe --overwrite --dry-run=server 2>&1); then
  known "Kyverno skips kube-system: the agent's legacy role can change coredns and Scenario C's rule never sees it (RBAC is the control)"
else pass "kube-system change by the agent was refused: $out"; fi
vw_before=$(kubectl get validatingwebhookconfigurations -l webhook.kyverno.io/managed-by=kyverno --no-headers 2>/dev/null | wc -l)
if kubectl $AGENT -n kyverno scale deploy kyverno-admission-controller --replicas=0 >/dev/null 2>&1; then
  sleep 25
  vw_after=$(kubectl get validatingwebhookconfigurations -l webhook.kyverno.io/managed-by=kyverno --no-headers 2>/dev/null | wc -l)
  if kubectl -n $NS run killswitch-probe --image=docker.io/library/busybox:1.36 --restart=Never --labels=trustfall.example/egress-profile=none >/dev/null 2>&1; then
    known "without a guard: the agent scaled Kyverno to 0, Kyverno removed its own webhooks ($vw_before -> $vw_after), and a docker.io Pod was admitted into payments. Every Kyverno admission rule was gone (NetworkPolicies still held), with no error or refusal"
  else fail "expected the kill-switch to open admission (webhooks $vw_before -> $vw_after)"; fi
  kubectl -n $NS delete pod killswitch-probe --ignore-not-found --wait=false >/dev/null 2>&1
  kubectl -n kyverno scale deploy kyverno-admission-controller --replicas=1 >/dev/null
  kubectl -n kyverno rollout status deploy/kyverno-admission-controller --timeout=180s >/dev/null
  for _ in $(seq 1 30); do [ "$(kubectl get validatingwebhookconfigurations -l webhook.kyverno.io/managed-by=kyverno --no-headers 2>/dev/null | wc -l)" -ge "$vw_before" ] && break; sleep 3; done
else fail "setup: the agent could not scale Kyverno even without the guard (RBAC?)"; fi
kubectl apply -f guard/protect-the-guardrail.yaml >/dev/null; sleep 5
expect_refused "with the in-API-server guard: the agent can no longer scale Kyverno to 0" \
  kubectl $AGENT -n kyverno scale deploy kyverno-admission-controller --replicas=0

echo
kubectl -n gateway delete pod gw-probe --ignore-not-found --wait=false >/dev/null 2>&1
kubectl -n default delete pod ctl-probe --ignore-not-found --wait=false >/dev/null 2>&1
rm -rf "$EV"
if [ $FAIL -eq 0 ]; then echo "LAB E2E: ALL PASSED ($KNOWN documented gaps confirmed)"; else echo "LAB E2E: FAILURES ABOVE"; fi
exit $FAIL
