#!/usr/bin/env python3
"""policy_agent.py, the decide -> act -> observe loop, against a scripted stand-in server (fake_decider.py).
Real tools throughout: templates, jsonschema, the kyverno CLI on the Scenario A fixtures. No model runs here."""
import json, pathlib, subprocess, sys, tempfile

GEN = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(GEN))
import fake_decider, policy_agent as pa  # noqa: E402

PASSED = []
def ok(m): PASSED.append(m); print("ok -", m)
INTENT = (GEN / "intent-a.txt").read_text()

def run(script, **kw):
    url, calls, srv = fake_decider.start(script)
    out = pathlib.Path(tempfile.mkdtemp()) / "pr"
    lines = []
    try:
        rec = pa.Agent("a", INTENT, url, 0.6, False, out, echo=lines.append, **kw).run()
    finally:
        srv.shutdown()
    return rec, out, lines, calls

# 1. storage judged new traffic -> backup-job blocked -> the agent asks for an exception, it does not grant one
rec, out, lines, calls = run({"dep": {"storage": ["deny", 0.81]}})
assert (out / "policies/deny-privilege-escalation.yaml").exists() and (out / "policies/restrict-egress-profile.yaml").exists()
assert [r["workload"] for r in rec["requests"]] == ["backup-job"] and not (out / "exceptions").exists()
assert json.loads((out / "spec.json").read_text())["exceptions"] == []
pr = (out / "PR.md").read_text()
assert "## What the agent did" in pr and "`backup-job` blocked by `restrict-egress-profile`" in pr and "Restrict the compromised" in pr
assert [t["what"] for t in rec["trace"]] == ["map the intent", "look at what's running", "decide dependencies", "write policies",
                                             "test on running pods", "decide: backup-job", "write local review proposal"]
ok("blocked workload: the agent tests, sees backup-job would break, and files an exception REQUEST (no PolicyException written)")

# 2. allow_and_retest: the agent changes its own policy and tests again; round 2 blocks nothing
rec, out, lines, _ = run({"dep": {"storage": ["deny", 0.81]}, "block": {"backup-job": ["allow_and_retest", 0.83]}})
whats = [t["what"] for t in rec["trace"]]
assert whats.count("write policies") == 2 and whats.count("test on running pods") == 2 and not rec["requests"]
assert "storage" in json.loads((out / "spec.json").read_text())["controls"]["egress_profile"]["approved_profiles"]
assert rec["trace"][-2]["detail"] == "nothing would be blocked"
ok("observe -> act again: allow_and_retest widens only the agent's own egress list, re-writes, re-tests, nothing blocked")

# 3. block_is_intended: kept as a block, no request
rec, out, _, _ = run({"dep": {"storage": ["deny", 0.81]}, "block": {"backup-job": ["block_is_intended", 0.9]}})
assert not rec["requests"] and rec["accepted_blocks"][0]["workload"] == "backup-job"
ok("block_is_intended: the block stays, recorded for the reviewer")

# 4. unsure everywhere it matters: nothing acted on, everything goes to a human
rec, out, _, _ = run({"dep": {"storage": ["deny", 0.4]}, "sentence": {"Prevent privilege escalation by workloads in that namespace": ["deny_privilege_escalation", 0.3]}})
assert not (out / "policies/deny-privilege-escalation.yaml").exists()
assert "storage" in json.loads((out / "spec.json").read_text())["controls"]["egress_profile"]["approved_profiles"], "unsure keeps traffic allowed"
abouts = " ".join(e["about"] for e in rec["escalations"])
assert "Prevent privilege escalation" in abouts and "egress profile storage" in abouts
ok("below the threshold: the privilege sentence writes no policy, an unsure profile stays allowed, both go to a human")

# 5. model unreachable: the loop still ends in a PR, every decision handed to a human, exit 3 from the CLI
r = subprocess.run([sys.executable, str(GEN / "policy_agent.py"), "--scenario", "a", "--fixtures", "--decider", "http://127.0.0.1:9",
                    "--out", str(pathlib.Path(tempfile.mkdtemp()) / "pr")], capture_output=True, text=True)
assert r.returncode == 3 and "no sentence maps to a guardrail" in r.stdout, (r.returncode, r.stdout[-500:], r.stderr[-500:])
ok("model down: the agent writes nothing, says so, hands the intent to a human (exit 3)")

# 6. replay: every tool re-runs with the recorded answers; a changed question is refused
rec, out, _, _ = run({"dep": {"storage": ["deny", 0.81]}})
out2 = pathlib.Path(tempfile.mkdtemp()) / "pr"
rec2 = pa.Agent("a", INTENT, "http://127.0.0.1:9", 0.6, False, out2, asker=pa.Recorded(out / "agent-run.json"), echo=lambda *_: None).run()
assert [t["detail"] for t in rec2["trace"][:-1]] == [t["detail"] for t in rec["trace"][:-1]]
assert (out2 / "policies/deny-privilege-escalation.yaml").read_text() == (out / "policies/deny-privilege-escalation.yaml").read_text()
try:
    pa.Agent("a", INTENT.replace("payments", "billing"), "x", 0.6, False, pathlib.Path(tempfile.mkdtemp()) / "pr",
             asker=pa.Recorded(out / "agent-run.json"), echo=lambda *_: None).run()
    raise AssertionError("replay accepted a different intent")
except RuntimeError as e:
    assert "differs from the recording" in str(e)
ok("replay: same decisions, same policies, tools re-run; a recording can't answer a different question")

# 7. an answer outside the options is unreadable, never acted on
url, calls, srv = fake_decider.start({"dep": {"storage": ["delete_namespace", 0.99]}})
rec = pa.Agent("a", INTENT, url, 0.6, False, pathlib.Path(tempfile.mkdtemp()) / "pr", echo=lambda *_: None).run(); srv.shutdown()
assert any(e["about"] == "egress profile storage" and e["best_guess"] is None for e in rec["escalations"])
ok("an answer outside the offered options is treated as no answer and handed to a human")

# The artifact contract is complete enough to review, but never silently authorizes promotion.
assert (out / "provenance.json").exists() and (out / "readiness.json").exists()
for stage in ("audit", "warn", "deny"):
    assert (out / "rollout" / stage / "deny-privilege-escalation.yaml").exists()
review = json.loads((out / "readiness.json").read_text())
assert review["independent_behavior"]["passed"] and review["promotion_allowed"] is False
assert review["status"] == "REVIEW_REQUIRED"
assert any(r["status"] == "OTHER_ENFORCEMENT_LAYER_REQUIRED" for r in review["requirements"])
ok("agent writes stage policies, provenance, fixed behavior tests and a review ledger; RBAC handover still prevents automatic promotion")

# A confidently wrong 'process' answer can omit privilege: a quiet admission report must not clear it.
rec, out, _, _ = run({"sentence": {"Prevent privilege escalation by workloads in that namespace": ["process", 0.99]}})
assert rec["readiness"]["status"] == "INCOMPLETE_PROPOSAL"
assert rec["readiness"]["independent_behavior"]["status"] == "REQUIRED_POLICY_MISSING"
assert not rec["readiness"]["promotion_allowed"]
ok("confident under-enforcement is visibly incomplete even when current fixtures are not blocked")

# Model abstention stays a review obligation, including with no policies at all.
rec, out, _, _ = run({"default_conf": 0.1})
assert not list((out / "policies").glob("*.yaml"))
assert rec["readiness"]["status"] == "INCOMPLETE_PROPOSAL"
assert all(r["status"] == "MODEL_ABSTAINED" for r in rec["readiness"]["requirements"])
ok("all-abstain output retains a complete unresolved requirement ledger")

# Replay binding happens before calls; partial consumption cannot create a valid proposal.
rec, out, _, _ = run({})
for change in ({"threshold": 0.7}, {"scenario": "b"}, {"intent_sha256": "changed"}, {"questions_sha256": "changed"}):
    path = pathlib.Path(tempfile.mkdtemp()) / "recording.json"
    path.write_text(json.dumps({**rec, **change}))
    try:
        pa.Agent("a", INTENT, "x", 0.6, False, path.parent / "pr", asker=pa.Recorded(path))
        raise AssertionError("replay accepted a changed contract")
    except RuntimeError:
        pass
path = pathlib.Path(tempfile.mkdtemp()) / "recording.json"
path.write_text(json.dumps({**rec, "calls": [*rec["calls"], rec["calls"][-1]]}))
try:
    pa.Agent("a", INTENT, "x", 0.6, False, path.parent / "pr", asker=pa.Recorded(path), echo=lambda *_: None).run()
    raise AssertionError("replay ignored trailing calls")
except RuntimeError as error:
    assert "not all" in str(error)
ok("replay binds scenario, intent, questions and threshold, and refuses unused recorded calls")

try:
    run({}, expected_model="different-evaluated-model")
    raise AssertionError("agent accepted an unevaluated model identity")
except RuntimeError as error:
    assert "model identity differs" in str(error)
ok("a server changing model identity cannot continue the evaluated proposal path")
print(f"{len(PASSED)} passed")
