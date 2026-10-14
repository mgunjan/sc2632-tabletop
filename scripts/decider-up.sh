#!/usr/bin/env bash
# The policy agent's model, on this laptop: Strands Decider (Apache 2.0, github.com/strands-labs/strands-decider).
#   ./scripts/decider-up.sh          install if needed, start the server, wait until it answers
#   ./scripts/decider-up.sh eval     ... then run the pre-registered eval (generator/decider_eval.py) and record
#                                    the demo agent's run (generator/recordings/agent-demo-a.json)
#   ./scripts/decider-up.sh status | stop
# First run downloads about 5 GB (the 2B checkpoint plus its Qwen3.5-2B base) into ~/.cache/huggingface and
# can take 10-30 minutes. After one successful start it runs offline (HF_HUB_OFFLINE=1): conference Wi-Fi not needed.
# Memory: about 5 GB while serving (bf16 on Apple-silicon MPS). Bash 3.2 safe.
set -u
cd "$(dirname "$0")/.." || exit 2
REF=0ac22a97e584f3ccf87cc9b8cc5fdbad57cdf534          # strands-decider commit, 2026-10-09 (adds the v1-2610 model)
MODEL=${DECIDER_MODEL:-StrandsAgents/strands-decider-2B-qwen3.5-v1-2610}
PORT=${DECIDER_PORT:-8000}; URL="http://127.0.0.1:$PORT"
VENV=.venv-decider; LOG=lab/.decider.log; PIDF=lab/.decider.pid; CACHED=lab/.decider-cached
up() { curl -fsS -m 3 "$URL/health" >/dev/null 2>&1; }

case "${1:-start}" in
  status) if up; then echo "Decider answering at $URL ($(curl -s -m 3 "$URL/health"))"; exit 0; else echo "Decider not answering at $URL"; exit 1; fi ;;
  stop)   [ -f "$PIDF" ] && kill "$(cat "$PIDF")" 2>/dev/null; rm -f "$PIDF"; echo "stopped"; exit 0 ;;
  start|eval) ;;
  *) echo "usage: $0 [start|eval|status|stop]"; exit 2 ;;
esac

if ! up; then
  # Python 3.10 or newer (the macOS system python3 is 3.9: brew install python@3.12)
  PY=
  for p in python3.13 python3.12 python3.11 python3.10 python3; do
    command -v "$p" >/dev/null 2>&1 || continue
    "$p" -c 'import sys; sys.exit(sys.version_info < (3, 10))' 2>/dev/null && { PY=$p; break; }
  done
  [ -n "$PY" ] || { echo "need Python 3.10+: brew install python@3.12"; exit 2; }
  if [ ! -x "$VENV/bin/strands-decider" ]; then
    echo "installing strands-decider @ ${REF:0:7} into $VENV (torch is the big part, a few minutes)"
    "$PY" -m venv "$VENV" || exit 2
    "$VENV/bin/pip" install -q --upgrade pip
    "$VENV/bin/pip" install -q "strands-decider @ https://github.com/strands-labs/strands-decider/archive/$REF.tar.gz" -r requirements.txt \
      || { echo "install failed"; exit 2; }
  fi
  DEV=cpu; [ "$(uname -s)/$(uname -m)" = "Darwin/arm64" ] && DEV=mps
  [ -f "$CACHED" ] && export HF_HUB_OFFLINE=1      # weights already on disk: never touch the network again
  echo "starting: strands-decider serve $MODEL --device $DEV --port $PORT  (log: $LOG)"
  nohup "$VENV/bin/strands-decider" serve "$MODEL" --device "$DEV" --port "$PORT" >>"$LOG" 2>&1 &
  echo $! >"$PIDF"
  t=0
  until up; do
    kill -0 "$(cat "$PIDF")" 2>/dev/null || { echo "server exited:"; tail -n 25 "$LOG"; exit 1; }
    sleep 5; t=$((t + 5))
    [ $((t % 60)) -eq 0 ] && echo "  still loading (${t}s; first run downloads ~5 GB) ... $(tail -n 1 "$LOG" | cut -c1-100)"
    [ $t -ge 2400 ] && { echo "gave up after 40 min; see $LOG"; exit 1; }
  done
  : >"$CACHED"
fi
# warm up (the first request of a length is slower), then report one real answer and its latency
w=$(curl -fsS -m 60 "$URL/v1/systemone" -H 'content-type: application/json' \
  -d '{"state":"Prevent privilege escalation by workloads in the payments namespace.","questions":{"q":{"type":"noul","instructions":"Is this a security requirement?"}}}' 2>&1) \
  || { echo "server up but the warm-up call failed: $w"; exit 1; }
echo "Decider answering at $URL: $w" | cut -c1-200

if [ "${1:-start}" = eval ]; then
  command -v kyverno >/dev/null 2>&1 || { echo "the agent tests its policies with the kyverno CLI: install 1.19.1 first (tabletop/DRY-RUN.md, step 0)"; exit 2; }
  "$VENV/bin/python" generator/decider_eval.py --decider "$URL" --label "$(uname -s | tr 'A-Z' 'a-z')-$(uname -m)"; rc=$?
  # Publish only the recording bound to a passing evaluation, never a fresh unbound run.
  if [ "$rc" -eq 0 ]; then
    if rec=$("$VENV/bin/python" generator/demo_gate.py --offline --decider "$URL" --recording-only); then
      cp "$rec" generator/recordings/agent-demo-a.json && echo "recorded: generator/recordings/agent-demo-a.json"
    else rc=1; fi
  fi
  exit $rc
fi
