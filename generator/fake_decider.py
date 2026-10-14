"""TEST ONLY. A scripted stand-in for `strands-decider serve`, in the server's real wire shape
(strands_decider/schema.py at 0ac22a9). It is not a model: every answer is scripted. Used by the tests to check the
plumbing; it never produces a recording, and recordings name the model that served them."""
import http.server, json, pathlib, threading

GEN = pathlib.Path(__file__).resolve().parent
GOLD = {}
for _s in "abc":
    for _c in json.loads((GEN / f"spec-{_s}.json").read_text())["clauses"]:
        GOLD[_c["text"].rstrip(".")] = _c["control"]
MODEL = "FAKE-scripted-not-a-model"


def start(script=None):
    """script: {"sentence": {text: [choice, conf]}, "dep": {profile: [...]}, "block": {workload: [...]}, "default_conf": x}
    Returns (url, calls, server)."""
    script = script if script is not None else {}
    calls = []

    class F(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a): pass

        def do_GET(self):
            self.send_response(200 if self.path == "/health" else 404); self.end_headers(); self.wfile.write(b'{"status":"ok"}')

        def do_POST(self):
            b = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            calls.append(b)
            key, q = next(iter(b["questions"].items()))
            crit, st = q["criteria"], b["state"]
            if "preserve" in crit:
                prof = st.split("profile: ")[1].split("\n")[0]
                pick, conf = script.get("dep", {}).get(prof, ["preserve", 0.9])
            elif "allow_and_retest" in crit:
                w = st.split("workload: ")[1].split("\n")[0]
                pick, conf = script.get("block", {}).get(w, ["request_exception", 0.77])
            else:
                cl = st.split("\n")[0].removeprefix("clause: ").rstrip(".")
                pick, conf = script.get("sentence", {}).get(cl, [GOLD.get(cl, "not_implementable"), script.get("default_conf", 0.93)])
            pr = {k: (conf if k == pick else (1 - conf) / max(1, len(crit) - 1)) for k in crit}
            out = {"model": MODEL, "answers": {key: {"type": "choice", "choice": pick, "probabilities": pr, "confidence": conf}},
                   "usage": {"input_tokens": 0, "output_tokens": 1}}
            body = json.dumps(out).encode()
            self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(body)

    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), F)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return f"http://127.0.0.1:{srv.server_address[1]}", calls, srv
