#!/usr/bin/env python3
"""The learned baselines and the Ollama baseline, without a real model: a fake Ollama answers over HTTP.
Checks the parts that could silently lie: answer parsing, a failed row counted as wrong, stated
confidence kept raw for calibration, predictors running in parallel, and the gate's arithmetic."""
import http.server, json, pathlib, sys, threading

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent / "generator"))
import baselines, evaluate  # noqa: E402
import build_dataset  # noqa: E402
from questions import QUESTION_SETS  # noqa: E402

PASSED = []
def ok(m): PASSED.append(m); print("ok -", m)

calls = []
class Fake(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        calls.append(body)
        text = body["messages"][0]["content"]
        if "FAILME" in text:
            self.send_response(500); self.end_headers(); return
        schema = body["format"]["properties"]
        ans = {}
        for q, s in schema.items():
            a = s["properties"]["answer"]
            ans[q] = {"answer": True if a["type"] == "boolean" else a["enum"][0], "confidence": 0.3 if q == "prompt_injection" else 0.9}
        out = json.dumps({"message": {"content": json.dumps(ans)}}).encode()
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(out)

srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Fake)
threading.Thread(target=srv.serve_forever, daemon=True).start()
url = f"http://127.0.0.1:{srv.server_address[1]}"

name, predict, meta = baselines.ollama_predictor("fake", url, workers=3, timeout=5)
states = [{"channel": "email", "text": "please reverse the double charge"}, {"channel": "chat", "text": "FAILME"}]
rows = predict("input", states)
assert all(c["options"]["temperature"] == 0 and c["options"]["num_ctx"] == 8192 and c["format"]["required"] for c in calls)
r0, r1 = rows
pi = r0["prompt_injection"]
assert pi["keys"][max(range(2), key=lambda i: pi["p"][i])] == "true", "a stated answer with low confidence must stay the answer"
assert pi["conf"] == 0.3, "stated confidence is kept raw so ECE measures it"
assert all(v["conf"] == 0.0 for v in r1.values()) and meta["stats"]["failed_rows"] == 1
ok("ollama baseline: schema-constrained, temperature 0, answer kept, raw confidence, failed row counted not hidden")

# Hermetic fixture construction: a clean checkout has no ignored data/*.jsonl.
# Keep the repository's existing evaluation data and manifest untouched.
fixture_data = build_dataset.build(n=600, seed=7)
rows_tr = [r for r in fixture_data['train'] if r['task'] == 'input']
for mk in (baselines.tfidf_lr_predictor, baselines.tfidf_knn_predictor):
    n, pr, _ = mk(rows_tr)
    out = pr("input", states)
    q = next(iter(out[0]))
    assert abs(sum(out[0][q]["p"]) - 1) < 1e-6 and set(out[0]) <= set(QUESTION_SETS["input"])
ok("tf-idf LR and kNN predict every trainable question with normalised probabilities")

# Strands Decider: a fake /v1/systemone answers in the laya/Jev shape; one question is unreadable on purpose
dcalls = []
class FakeDecider(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        dcalls.append(body)
        ans = {}
        for q, qd in body["questions"].items():
            if q == "jailbreak":
                ans[q] = {"weird": 1}
            elif qd["type"] == "noul":
                ans[q] = {"type": "noul", "noul": 0.9, "answer_confidence": 0.9}
            else:
                ks = list(qd["criteria"]); ans[q] = {"type": "choice", "probabilities": {k: (0.7 if i == 0 else 0.3 / (len(ks) - 1)) for i, k in enumerate(ks)}, "answer_confidence": 0.7}
        out = json.dumps({"answers": ans}).encode()
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(out)
dsrv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), FakeDecider)
threading.Thread(target=dsrv.serve_forever, daemon=True).start()
_, dpred, dmeta = baselines.decider_predictor(f"http://127.0.0.1:{dsrv.server_address[1]}", workers=2, timeout=5)
drows = dpred("input", states)
assert dcalls and set(dcalls[0]["questions"]) == set(QUESTION_SETS["input"]) and isinstance(dcalls[0]["state"], str)
pi = drows[0]["prompt_injection"]; assert pi["keys"][max(range(2), key=lambda i: pi["p"][i])] == "true" and pi["conf"] == 0.9
assert drows[0]["jailbreak"]["conf"] == 0.0 and dmeta["stats"]["unreadable_answers"] == 2 and dmeta["stats"]["failed_rows"] == 0
_, dpred2, _ = baselines.decider_predictor(f"http://127.0.0.1:{dsrv.server_address[1]}", workers=1, timeout=5)
ex = [r['state'] for r in fixture_data['gold'] if r['task'] == 'exception'][:1]
sc = dpred2("exception", ex)[0]["scope"]; assert sc["keys"][max(range(len(sc["p"])), key=lambda i: sc["p"][i])] == "single"
ok("decider: our typed questions go over unchanged; noul and choice answers parsed; an unreadable answer is counted, not guessed")

# temperature scaling: an overconfident predictor (0.97 on everything, right 60% of the time) gets T > 1 and an honest confidence
keys = ["false", "true"]
pairs = [({"p": [0.03, 0.97], "keys": keys, "was_noul": True, "conf": 0.97}, i % 5 < 3) for i in range(100)]
T = evaluate.fit_temperature(pairs)
sp = evaluate._scaled(pairs[0][0], T)
assert T > 1.5 and 0.5 < sp["conf"] < 0.7 and sp["p"].index(max(sp["p"])) == 1, (T, sp)
ok(f"temperature scaling: overconfident 0.97 at 60% accuracy -> T={T}, confidence {sp['conf']:.2f}; the answer itself is unchanged")

p, a, b = evaluate._mcnemar([1] * 12 + [0] * 2, [0] * 12 + [1] * 2)
assert (a, b) == (12, 2) and 0.01 < p < 0.02
assert evaluate._mcnemar([1, 0], [1, 0])[0] == 1.0
ok("exact McNemar: 12 vs 2 discordant gives p ~ 0.013; identical predictions give 1.0")
print(f"{len(PASSED)} passed")
