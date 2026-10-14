#!/usr/bin/env python3
"""decider_agent.py against a fake Strands Decider that answers in the server's real wire shape
(strands_decider/schema.py at 0ac22a9: ChoiceAnswer = choice, probabilities, confidence). No model runs here:
this checks the plumbing, not the model. The model is judged by decider_eval.py on real runs."""
import http.server, json, pathlib, subprocess, sys, tempfile, threading

GEN = pathlib.Path(__file__).resolve().parent
ROOT = GEN.parent
sys.path.insert(0, str(GEN))
import decider_agent as da  # noqa: E402

PASSED = []
def ok(m): PASSED.append(m); print("ok -", m)

# what the reference specs say each sentence asks for (hand-written; the fake answers with these)
GOLD = {}
for s in "abc":
    for c in json.loads((GEN / f"spec-{s}.json").read_text())["clauses"]:
        GOLD[c["text"].rstrip(".")] = c["control"]
LOW = set()     # sentences the fake answers with low confidence
calls = []

class Fake(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_GET(self):
        self.send_response(200 if self.path == "/health" else 404); self.end_headers(); self.wfile.write(b'{"status":"ok"}')
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        calls.append(body)
        q = body["questions"]["control"]
        assert q["type"] == "choice" and set(q["criteria"]) == set(da.CONTROLS)
        clause = body["state"].split("\n")[0].removeprefix("clause: ").rstrip(".")
        pick = GOLD.get(clause, "not_implementable")
        conf = 0.35 if clause in LOW else 0.93
        pr = {k: (conf if k == pick else (1 - conf) / (len(da.CONTROLS) - 1)) for k in da.CONTROLS}
        out = {"model": "strands-decider-2B-qwen3.5-v1-2610",
               "answers": {"control": {"type": "choice", "choice": pick, "probabilities": pr, "confidence": conf}},
               "usage": {"input_tokens": 400, "output_tokens": 1}}
        b = json.dumps(out).encode()
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(b)

srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Fake)
threading.Thread(target=srv.serve_forever, daemon=True).start()
url = f"http://127.0.0.1:{srv.server_address[1]}"
tmp = pathlib.Path(tempfile.mkdtemp())

def agent(*args):
    return subprocess.run([sys.executable, str(GEN / "decider_agent.py"), "--decider", url, *args], capture_output=True, text=True)

def generate(scn, spec):
    return subprocess.run([sys.executable, str(GEN / "generate.py"), "--scenario", scn, "--from-spec", str(spec),
                           "--spec-meta", str(spec.with_suffix(".meta.json")), "--out", str(tmp / "gen"), "--no-classify"],
                          capture_output=True, text=True)

assert da.healthy(url) and not da.healthy("http://127.0.0.1:9", timeout=1)
ok("health check: a live server answers, a dead port does not")

pick, conf, pr = da.parse_choice({"answers": {"control": {"type": "choice", "choice": "process", "probabilities": {"process": 0.8, "x": 0.2}, "confidence": 0.71}}})
assert (pick, conf) == ("process", 0.71) and "x" not in pr
assert da.parse_choice({"answers": {"control": {"type": "choice", "choice": "allow_everything", "confidence": 0.99}}})[0] is None
assert da.parse_choice({"error": "URLError"})[0] is None
ok("parse: the server's real answer shape is read; an option outside the list, or an error, is unreadable, not guessed")

# a correct, confident model: every scenario compiles, and A writes the privilege policy the demo enforces
for s in "abc":
    spec = tmp / f"spec-{s}.json"
    r = agent("--scenario", s, "--out", str(spec))
    assert r.returncode == 0, r.stderr
    sp = json.loads(spec.read_text())
    ref = json.loads((GEN / f"spec-{s}.json").read_text())
    assert [c["control"] for c in sp["clauses"]] == [c["control"] for c in ref["clauses"]]
    assert sp["exceptions"] == [], "the agent never writes exceptions"
    g = generate(s, spec)
    assert g.returncode == 0, g.stderr[-800:]
    run = sorted((tmp / "gen").glob(f"{s}-*"))[-1]
    meta = json.loads((spec.with_suffix(".meta.json")).read_text())
    assert meta["served_model"] == ["strands-decider-2B-qwen3.5-v1-2610"] and len(meta["decisions"]) == len(sp["clauses"])
    if s == "a":
        assert (run / "policies/deny-privilege-escalation.yaml").exists()
        assert "deny_privilege_escalation" in r.stdout and "ESCALATE" not in r.stdout
ok("confident, correct answers: A, B and C compile through generate.py; A writes deny-privilege-escalation; no exceptions invented")

# an unsure answer goes to a human and enables nothing
LOW.add("Prevent privilege escalation by workloads in that namespace")
spec = tmp / "spec-a-low.json"
r = agent("--scenario", "a", "--out", str(spec))
sp = json.loads(spec.read_text())
assert r.returncode == 0 and "ESCALATE" in r.stdout and "deny_privilege_escalation" not in sp["controls"]
assert sp["clauses"][1]["control"] == "not_implementable" and "ESCALATED" in sp["clauses"][1]["note"]
ok("below the threshold: the sentence is escalated to a human and its guardrail is not written")

# every sentence unsure -> exit 3, so the demo can't present an empty result as the agent's
r = agent("--intent", "Prevent privilege escalation by workloads in that namespace.", "--scenario", "a", "--out", str(tmp / "x.json"))
assert r.returncode == 3, (r.returncode, r.stderr)
LOW.clear()
ok("all sentences escalated: exit 3, nothing to present as an agent result")

# server down: escalated, never guessed
r = subprocess.run([sys.executable, str(GEN / "decider_agent.py"), "--decider", "http://127.0.0.1:9", "--scenario", "a",
                    "--out", str(tmp / "down.json")], capture_output=True, text=True)
assert r.returncode == 3 and json.loads((tmp / "down.json").read_text())["controls"] == {}
ok("server down: every sentence escalates, no guardrail written")

# replay: same spec, labelled as a replay, refused for a different intent
spec = tmp / "spec-a.json"
r = agent("--scenario", "a", "--replay", str(spec.with_suffix(".meta.json")), "--out", str(tmp / "rep.json"))
assert r.returncode == 0 and json.loads((tmp / "rep.json").read_text()) == json.loads(spec.read_text())
assert "REPLAYED" in json.loads((tmp / "rep.meta.json").read_text())["model"]
r = agent("--intent", "Something else entirely.", "--replay", str(spec.with_suffix(".meta.json")), "--out", str(tmp / "rep2.json"))
assert r.returncode != 0 and "different intent" in r.stderr
ok("replay: identical spec, provenance says REPLAYED, and a recording can't be reused for another intent")

# the eval runner: real wire shape in, gates out. The fake knows only the reference specs, so paraphrases miss.
import fake_decider  # noqa: E402
url2, _, srv2 = fake_decider.start({"dep": {"storage": ["deny", 0.81]}})
r = subprocess.run([sys.executable, str(GEN / "decider_eval.py"), "--decider", url2, "--outdir", str(tmp / "rec"), "--label", "fake"],
                   capture_output=True, text=True)
srv2.shutdown()
summ = json.loads(next((tmp / "rec").glob("*.summary.json")).read_text())
rows = [json.loads(l) for l in next((tmp / "rec").glob("*.jsonl")).read_text().splitlines()]
assert r.returncode == 0 and summ["gates"]["G1_demo"]["pass"] and summ["gates"]["G2_core"]["pass"], r.stdout[-1500:]
assert not summ["gates"]["G3_all"]["pass"] and summ["gates"]["G3_all"]["confident_miss"] > 0
assert len(rows) == 4 * 5 + 11 + 16 + 4 and summ["served_model"] == [fake_decider.MODEL]
assert summ["gates"]["G1_demo"]["agent_runs"]["pass"] and summ["gates"]["G1_demo"]["agent_runs"]["identical_decisions"]
assert len(json.loads(next((tmp / "rec").glob("*.agent-runs.json")).read_text())) == 5
assert len(summ["config_sha256"]) == 64 and len(summ["hostile"]) == 4
r = subprocess.run([sys.executable, str(GEN / "decider_eval.py"), "--decider", "http://127.0.0.1:9", "--outdir", str(tmp / "rec2")],
                   capture_output=True, text=True)
assert r.returncode != 0 and "no Decider server" in r.stderr
ok("eval runner: every call recorded with the served model, gates computed, a confident miss counted, the whole agent run 5x; refuses to run without a server")

# the options can only add restrictions: none of them loosens anything
assert not any(w in " ".join(da.CONTROLS).lower() for w in ("allow all", "disable", "remove", "exempt"))
ok("the option list contains no loosening choice")
print(f"{len(PASSED)} passed")
