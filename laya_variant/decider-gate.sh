#!/usr/bin/env bash
# Run Strands Decider through the pre-registered Laya gate, natively on this Mac. One command:
#   ./laya_variant/decider-gate.sh
# First run: creates ~/.venvs/decider, installs strands-decider (+ scikit-learn for the baselines) and downloads the
# model from Hugging Face (about 4 GB). Then: starts the server on :8000, runs the gate on gold + scenario, stops it.
# Output: runs/decider/REPORT.md, report.json and the raw responses (decider-*-recording.jsonl).
set -euo pipefail
cd "$(dirname "$0")/.."
MODEL="${DECIDER_MODEL:-StrandsAgents/strands-decider-2B-hobson-v19}"
VENV="${DECIDER_VENV:-$HOME/.venvs/decider}"
[ -x "$VENV/bin/python" ] || python3 -m venv "$VENV"
"$VENV/bin/pip" install -q --upgrade pip
"$VENV/bin/pip" install -q strands-decider scikit-learn numpy pyyaml
mkdir -p runs/decider
"$VENV/bin/strands-decider" serve "$MODEL" --port 8000 > runs/decider/server.log 2>&1 &
SRV=$!; trap 'kill $SRV 2>/dev/null' EXIT
echo "waiting for the Decider server (first run downloads the model)..."
for _ in $(seq 1 600); do
  curl -s -o /dev/null -m 2 -X POST localhost:8000/v1/systemone -H 'content-type: application/json' \
    -d '{"state":"ping","questions":{"q":{"type":"noul","instructions":"Is this a test?"}}}' && break; sleep 2
done
"$VENV/bin/python" laya_variant/evaluate.py --splits gold,scenario --decider-url http://localhost:8000 --workers 2 --temperature-scale --out runs/decider
echo; echo "Done: runs/decider/REPORT.md"
