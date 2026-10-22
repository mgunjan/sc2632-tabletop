#!/usr/bin/env bash
# Tests capture-evidence.sh against a fake kubectl that logs every call.
# Asserts the property that matters: NOTHING touches the suspect until evidence is on disk,
# the relabel is the last cluster call, the manifest hashes every file, and a missing
# checkpoint is reported, not faked.
#
# Run: ./quarantine/test_capture_evidence.sh
set -uo pipefail
cd "$(dirname "$0")/.." || exit 2
REPO=$(pwd)
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
FAILS=0
ok()   { printf '  ok   %s\n' "$1"; }
bad()  { printf '  FAIL %s\n' "$1"; FAILS=$((FAILS+1)); }

# ---- fake kubectl: records calls; checkpoint behaviour set by FAKE_CHECKPOINT=ok|unsupported
mkdir -p "$T/bin"
cat > "$T/bin/kubectl" <<'EOF'
#!/usr/bin/env bash
echo "kubectl $*" >> "$CALLS"
case "$*" in
  *"jsonpath={.status.phase}"*)               echo -n "${FAKE_PHASE:-Running/}" ;;
  *"ephemeralContainerStatuses"*)             echo -n "Completed" ;;
  *"jsonpath={.spec.nodeName}"*)              echo -n "node-b" ;;
  *"jsonpath={.spec.containers[0].name}"*)    echo -n "api" ;;
  *"get --raw"*"checkpoint"*) echo "error: checkpoint must be a POST" >&2; exit 1 ;;   # the old bug
  *"create --raw /api/v1/nodes/"*"/checkpoint/"*)
      if [ "${FAKE_CHECKPOINT:-unsupported}" = ok ]; then echo '{"items":["/var/lib/kubelet/checkpoints/x.tar"]}'
      else echo 'the server could not find the requested resource' >&2; exit 1; fi ;;
  *" debug "*)  echo "Targeting container \"api\". Defaulting debug container name to evidence-1." ;;   # real kubectl: creates, prints nothing useful
  *" logs "*"-c evidence-"*)  printf '== ps\nPID PPID USER ARGS\n1 0 app /app/payments-api\n42 1 app /tmp/.x/agent\n== env (pid 1)\nAPI_TOKEN=sk-live-9f8e7d\nDB_PASSWORD=hunter2\nstripe_secret_key=sk_abc\nAWS_ACCESS_KEY_ID=AKIAFAKEKEY_FOR_TESTS\nDATABASE_URL=postgres://user:pass@example.invalid/db\nSERVICE_ENDPOINT=https://internal.example.invalid\nPATH=/usr/bin\nLANG=C\n' ;;
  *" logs "*"--previous"*) echo "previous container not found" >&2; exit 1 ;;
  *" logs "*) [ "${FAKE_LOGS:-ok}" = fail ] && { echo 'Get "https://10.0.0.5:10250/containerLogs/...": EOF' >&2; exit 1; }
              echo "2026-10-26T09:14:02Z GET /refunds 200" ;;
  *" get pod "*"-o yaml"*)  echo "kind: Pod" ;;
  *" get events "*) echo "items: []" ;;
  *" get node "*)   echo "kind: Node" ;;
  *" label pod "*)  echo "pod/payments-api labeled" ;;
esac
EOF
chmod +x "$T/bin/kubectl"

run() {  # $1 = checkpoint mode
  export CALLS="$T/calls-$1" FAKE_CHECKPOINT="$1"; : > "$CALLS"
  ( cd "$T" && mkdir -p "run-$1" && cd "run-$1" && PATH="$T/bin:$PATH" bash "$REPO/quarantine/capture-evidence.sh" payments payments-api ) > "$T/out-$1" 2>&1
  echo $?
}

echo "capture-evidence.sh"
for mode in unsupported ok; do
  rc=$(run "$mode")
  calls="$T/calls-$mode"; outdir=$(ls -d "$T/run-$mode"/evidence/*/ 2>/dev/null | head -1)
  [ "$rc" = 0 ] && ok "[$mode] exits 0" || { bad "[$mode] exit $rc"; cat "$T/out-$mode"; continue; }
  [ -n "$outdir" ] && ok "[$mode] evidence directory created" || { bad "[$mode] no evidence dir"; continue; }

  # Evidence must be private on disk and clearly identified as sensitive.
  dir_mode=$(python3 -c 'import pathlib,sys; print(oct(pathlib.Path(sys.argv[1]).stat().st_mode & 0o777))' "$outdir")
  root_mode=$(python3 -c 'import pathlib,sys; print(oct(pathlib.Path(sys.argv[1]).stat().st_mode & 0o777))' "$T/run-$mode/evidence")
  file_mode=$(python3 -c 'import pathlib,sys; print(oct(pathlib.Path(sys.argv[1]).stat().st_mode & 0o777))' "$outdir/SENSITIVITY.txt")
  [ "$dir_mode" = 0o700 ] && [ "$root_mode" = 0o700 ] && [ "$file_mode" = 0o600 ] \
    && ok "[$mode] evidence root/bundle are 700 and files are 600" \
    || bad "[$mode] evidence permissions root=$root_mode bundle=$dir_mode file=$file_mode"
  grep -q 'CLASSIFICATION: RAW-SENSITIVE INCIDENT EVIDENCE' "$outdir/SENSITIVITY.txt" \
    && grep -q 'No other artifact is sanitized' "$outdir/SENSITIVITY.txt" \
    && ok "[$mode] raw-sensitive custody label is included" || bad "[$mode] sensitivity label missing or inaccurate"

  # Ordering: the relabel must be the LAST kubectl call, after every read.
  last=$(tail -1 "$calls")
  [[ "$last" == *" label pod payments-api trustfall.example/suspect=true trustfall.example/egress-profile=quarantined trustfall.example/in-rotation=false"* ]] \
    && ok "[$mode] relabel is the last cluster call" || bad "[$mode] last call was: $last"
  lbl_line=$(grep -n " label pod " "$calls" | cut -d: -f1); first_read=$(grep -n " logs \| debug \|checkpoint" "$calls" | head -1 | cut -d: -f1)
  [ -n "$lbl_line" ] && [ "$first_read" -lt "$lbl_line" ] && ok "[$mode] evidence reads happen before the relabel" || bad "[$mode] ordering"
  # Two writes to the Pod, and only two: the debug container (an observer, recorded permanently
  # in spec.ephemeralContainers) and the relabel. The debug container comes first.
  [ "$(grep -c " label " "$calls")" = 1 ] && [ "$(grep -c " debug " "$calls")" = 1 ] \
    && ok "[$mode] exactly two writes: one debug container, one relabel" || bad "[$mode] writes: $(grep -c ' label \| debug ' "$calls")"
  dbg_line=$(grep -n " debug " "$calls" | cut -d: -f1); spec_line=$(grep -n " get pod payments-api -o yaml" "$calls" | cut -d: -f1)
  [ "$dbg_line" -lt "$spec_line" ] && ok "[$mode] pod.yaml captured after the debug container (records the footprint)" || bad "[$mode] pod.yaml before debug"
  ! grep -q " delete \| drain \| scale \| exec " "$calls" && ok "[$mode] no delete/drain/scale/exec" || bad "[$mode] destructive call made"

  # Integrity manifest covers every file.
  nfiles=$(find "$outdir" -type f ! -name SHA256SUMS | wc -l)
  nsums=$(wc -l < "$outdir/SHA256SUMS")
  [ "$nfiles" = "$nsums" ] && ok "[$mode] SHA256SUMS covers all $nfiles files" || bad "[$mode] $nsums sums for $nfiles files"
  ( cd "$outdir" && sha256sum -c --quiet SHA256SUMS 2>/dev/null || shasum -a 256 -c --quiet SHA256SUMS ) && ok "[$mode] hashes verify" || bad "[$mode] hash mismatch"

  # Secrets redacted in live state.
  ! grep -q "sk-live-9f8e7d\|hunter2\|sk_abc\|AKIAFAKEKEY_FOR_TESTS\|postgres://user:pass\|https://internal.example.invalid" "$outdir/live-state.txt" \
    && grep -q 'AWS_ACCESS_KEY_ID=<redacted>' "$outdir/live-state.txt" \
    && grep -q 'DATABASE_URL=<redacted>' "$outdir/live-state.txt" \
    && grep -q 'SERVICE_ENDPOINT=<redacted>' "$outdir/live-state.txt" \
    && ok "[$mode] non-allowlisted environment values, including cloud IDs and URLs, redacted" \
    || bad "[$mode] environment value leaked or allowlist contract failed"
  grep -q "PATH=/usr/bin" "$outdir/live-state.txt" && grep -q 'LANG=C' "$outdir/live-state.txt" \
    && ok "[$mode] explicit safe environment allowlist kept" || bad "[$mode] safe allowlist missing"
done

# Preflight and completeness — both found on a live cluster, not by this harness.
export CALLS="$T/calls-term" FAKE_PHASE="Running/2026-10-26T09:14:00Z"; : > "$CALLS"
( cd "$T" && mkdir -p run-term && cd run-term && PATH="$T/bin:$PATH" bash "$REPO/quarantine/capture-evidence.sh" payments payments-api ) > "$T/out-term" 2>&1; rc=$?
[ $rc = 3 ] && ! grep -q " label \| debug " "$CALLS" && ok "terminating Pod: abort (exit 3) before any write" || bad "terminating Pod: rc=$rc"
unset FAKE_PHASE
export CALLS="$T/calls-nolog" FAKE_LOGS=fail; : > "$CALLS"
( cd "$T" && mkdir -p run-nolog && cd run-nolog && PATH="$T/bin:$PATH" bash "$REPO/quarantine/capture-evidence.sh" payments payments-api ) > "$T/out-nolog" 2>&1; rc=$?
[ $rc = 4 ] && grep -q "INCOMPLETE: not captured: logs-current" "$T/out-nolog" && ok "logs unreachable: sealed but reported INCOMPLETE (exit 4)" || bad "logs unreachable: rc=$rc"
unset FAKE_LOGS

# Checkpoint honesty
grep -q "checkpoint NOT available" "$T/out-unsupported" && ok "[unsupported] says checkpoint NOT available" || bad "[unsupported] did not report missing checkpoint"
grep -q "checkpoint requested" "$T/out-ok" && ok "[ok] reports checkpoint requested" || bad "[ok] checkpoint not reported"
grep -q "create --raw /api/v1/nodes/node-b/proxy/checkpoint/payments/payments-api/api" "$T/calls-ok" \
  && ok "checkpoint is a POST via create --raw to the right node/pod/container" || bad "checkpoint call malformed"

echo
[ $FAILS = 0 ] && echo "capture-evidence: all passed" || echo "capture-evidence: $FAILS failed"
exit $FAILS
