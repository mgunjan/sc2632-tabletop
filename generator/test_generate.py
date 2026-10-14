"""
End-to-end test of the generator's MODEL path, with a mock Ollama server standing in for the
model. Proves the request is well-formed (schema-constrained, temperature 0, fixed seed) and
that a model response flows through templates -> kyverno -> PR -> provenance.

It does NOT test a real model's quality — that's what running against Ollama is for.
It DOES test the failure the real model will eventually produce: a response that isn't valid
for the schema must stop the pipeline, not generate policies from garbage.

Run: python3 generator/test_generate.py
"""
import http.server, json, pathlib, subprocess, sys, tempfile, threading

GEN = pathlib.Path(__file__).parent
ROOT = GEN.parent

class MockOllama(http.server.BaseHTTPRequestHandler):
    reply = None          # dict to return as message.content (or a raw string)
    seen = []             # captured request bodies
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        MockOllama.seen.append(body)
        content = MockOllama.reply if isinstance(MockOllama.reply, str) else json.dumps(MockOllama.reply)
        out = json.dumps({"model": "mock-model:1b", "message": {"role": "assistant", "content": content},
                          "eval_count": 123, "total_duration": 456}).encode()
        self.send_response(200); self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(out))); self.end_headers(); self.wfile.write(out)
    def log_message(self, *a): pass

def serve():
    srv = http.server.HTTPServer(("127.0.0.1", 0), MockOllama)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_port}"

def run_gen(host, out, scenario="b"):
    return subprocess.run([sys.executable, str(GEN / "generate.py"), "--scenario", scenario, "--model", "mock-model:1b",
                           "--ollama", host, "--out", str(out), "--no-classify"], capture_output=True, text=True, timeout=300)

def test_model_path_end_to_end():
    MockOllama.reply = json.loads((GEN / "spec-b.json").read_text()); MockOllama.seen = []
    srv, host = serve()
    with tempfile.TemporaryDirectory() as d:
        p = run_gen(host, d)
        assert p.returncode == 0, p.stderr
        req = MockOllama.seen[0]
        assert req["format"]["title"] == "GuardrailSpec", "schema must constrain the model"
        assert req["options"]["temperature"] == 0.0 and req["options"]["seed"] == 0
        assert "support-agent" in req["messages"][1]["content"], "fixture inventory must reach the model"
        run = next(pathlib.Path(d).iterdir())
        prov = json.loads((run / "provenance.json").read_text())
        assert prov["model"] == "mock-model:1b" and prov["seed"] == 0 and len(prov["prompt_sha256"]) == 64
        pr = (run / "PR.md").read_text()
        assert "WOULD BLOCK" in pr and "payments/payments-api" in pr
        assert sorted(x.name for x in (run / "policies").iterdir()) == [
            "deny-sa-token-for-agent-sidecars.yaml", "restrict-egress-profile.yaml", "restrict-image-registry.yaml"]
    srv.shutdown()

def test_model_output_violating_schema_is_rejected():
    bad = json.loads((GEN / "spec-b.json").read_text())
    bad["controls"]["egress_profile"]["approved_profiles"] = ["db", "anything; rm -rf /"]  # pattern violation
    MockOllama.reply = bad; MockOllama.seen = []
    srv, host = serve()
    with tempfile.TemporaryDirectory() as d:
        p = run_gen(host, d)
        assert p.returncode != 0, "a schema-invalid model response must stop the pipeline"
        assert "schema" in (p.stderr + p.stdout).lower()
        assert not any(pathlib.Path(d).glob("*/policies/*.yaml")), "no policies may be written from invalid output"
    srv.shutdown()

def test_cel_injection_via_model_output_is_rejected():
    # Model-supplied strings are pasted into CEL. A quote would rewrite the policy's logic:
    #   object.spec.containers.all(c, c.image.startsWith('x' || true || ''))  -> always true.
    for field, value in [("registry", "x' || true || '"), ("registry", "evil.io/') || c.image.startsWith('")]:
        bad = json.loads((GEN / "spec-b.json").read_text())
        bad["controls"]["restrict_registry"][field] = value
        MockOllama.reply = bad; MockOllama.seen = []
        srv, host = serve()
        with tempfile.TemporaryDirectory() as d:
            p = run_gen(host, d)
            assert p.returncode != 0 and "does not match" in p.stderr, (value, p.stderr)
            assert not any(pathlib.Path(d).glob("*/policies/*.yaml"))
        srv.shutdown()
    bad = json.loads((GEN / "spec-c.json").read_text())
    bad["controls"]["deny_agent_mutation_outside_namespace"]["agent_serviceaccount"] = "x' || '1' == '1"
    MockOllama.reply = bad
    srv, host = serve()
    with tempfile.TemporaryDirectory() as d:
        p = run_gen(host, d, scenario="c")
        assert p.returncode != 0 and "agent_serviceaccount" in p.stderr
    srv.shutdown()

def test_model_output_that_is_not_json_is_rejected():
    MockOllama.reply = "Sure! Here is your policy:\n```yaml\nkind: ClusterPolicy\n```"; MockOllama.seen = []
    srv, host = serve()
    with tempfile.TemporaryDirectory() as d:
        p = run_gen(host, d)
        assert p.returncode != 0
        assert not any(pathlib.Path(d).glob("*/policies/*.yaml"))
    srv.shutdown()

def test_model_cannot_enable_unasked_control_past_audit():
    # Even if the model claims in_intent=false but asks for Deny rollout, an unasked control stays Audit.
    spec = json.loads((GEN / "spec-b.json").read_text())
    assert spec["controls"]["restrict_registry"]["in_intent"] is False
    MockOllama.reply = spec; MockOllama.seen = []
    srv, host = serve()
    with tempfile.TemporaryDirectory() as d:
        assert run_gen(host, d).returncode == 0
        reg = next(pathlib.Path(d).glob("*/policies/restrict-image-registry.yaml")).read_text()
        assert "- Audit" in reg and "- Deny" not in reg
    srv.shutdown()

if __name__ == "__main__":
    import inspect
    fns = [f for n, f in sorted(globals().items()) if n.startswith("test_") and inspect.isfunction(f)]
    for f in fns:
        f(); print("ok ", f.__name__)
    print(f"{len(fns)} passed")
