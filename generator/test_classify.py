"""
Wiring tests for classify.py. These use a STUB agent with scripted answers — they test the
comparison, triage, and PR-rendering logic, NOT Laya's accuracy. Laya's real behaviour is
measured by running classify.py against the model (see tabletop/DRY-RUN.md §3).

Run: python3 -m pytest generator/test_classify.py -q   (or: python3 generator/test_classify.py)
"""
import json, pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import classify

GEN = pathlib.Path(__file__).parent

def noul(p): return {"type": "noul", "noul": p, "confidence": max(p, 1 - p), "action": {}}
def choice(c, keys): return {"type": "choice", "choice": c, "probabilities": {k: (0.8 if k == c else 0.1) for k in keys}, "confidence": 0.7, "action": {}}

class Stub:
    """Scripted answers keyed by question id. Not a model."""
    def __init__(self, script): self.script = script
    def predict(self, state, questions):
        return {"answers": {q: self.script[q] for q in questions if q in self.script}}

def spec(s): return json.loads((GEN / f"spec-{s}.json").read_text())
def intent(s): return (GEN / f"intent-{s}.txt").read_text()

def test_intent_gap_is_reported_when_identity_asked_but_not_generated():
    # Scenario A: intent clause 3 asks for API-access restriction; the generator leaves it NOT IMPLEMENTED.
    eng = classify.Engine(agent=Stub({
        "asks_network": noul(0.9), "asks_identity": noul(0.85), "asks_workload_security": noul(0.8),
        "asks_supply_chain": noul(0.1), "asks_agent_behaviour": noul(0.1), "asks_evidence": noul(0.1),
        "admission_sufficient": choice("partly", ["fully", "partly", "not"])}))
    r = classify.check_intent(eng, intent("a"), spec("a"))
    fams = {f["family"] for f in r["findings"]}
    assert "identity" in fams                      # asked, not generated
    assert "supply_chain" in fams                  # generated (registry), not asked
    assert "network" not in fams and "workload_security" not in fams

def test_no_findings_when_intent_and_controls_agree():
    eng = classify.Engine(agent=Stub({
        "asks_network": noul(0.1), "asks_identity": noul(0.1), "asks_workload_security": noul(0.1),
        "asks_supply_chain": noul(0.1), "asks_agent_behaviour": noul(0.9), "asks_evidence": noul(0.1),
        "admission_sufficient": choice("partly", ["fully", "partly", "not"])}))
    s = spec("c"); s["controls"]["audit_replica_surge"]["enabled"] = False
    assert classify.check_intent(eng, intent("c"), s)["findings"] == []

def test_scenario_b_tool_allowlist_gap_is_reported():
    # B's intent asks to limit the agent's tools; admission can't, so nothing is generated. That must surface.
    eng = classify.Engine(agent=Stub({
        "asks_network": noul(0.9), "asks_identity": noul(0.9), "asks_workload_security": noul(0.1),
        "asks_supply_chain": noul(0.1), "asks_agent_behaviour": noul(0.9), "asks_evidence": noul(0.1),
        "admission_sufficient": choice("partly", ["fully", "partly", "not"])}))
    fams = {f["family"] for f in classify.check_intent(eng, intent("b"), spec("b"))["findings"]}
    assert "agent_behaviour" in fams and "identity" not in fams

def test_exception_on_suspect_workload_needs_review():
    # Scenario B: the exception is for payments-api itself.
    eng = classify.Engine(agent=Stub({
        "concrete_need": noul(0.8), "owner_accountable": noul(0.9),
        "scope": choice("pattern", ["single", "pattern", "broad"]),
        "ttl_fit": choice("long", ["short", "matched", "long"]),
        "touches_suspect": noul(0.9)}))
    r = classify.check_exceptions(eng, spec("b"), "b")
    x = r["exceptions"][0]
    assert x["workload"] == "payments-api"
    assert x["triage"] == "human-review"
    assert "applies to the suspect workload" in x["reasons"]

def test_vague_broad_exception_is_refused_under_q1():
    ans = {"concrete_need": noul(0.2), "owner_accountable": noul(0.3),
           "scope": choice("broad", ["single", "pattern", "broad"]),
           "ttl_fit": choice("matched", ["short", "matched", "long"]), "touches_suspect": noul(0.1)}
    verdict, reasons = classify.triage(ans)
    assert verdict == "refuse-under-Q1" and len(reasons) == 3

def test_input_guard_reads_scenario_inputs_and_reports_flags():
    eng = classify.Engine(agent=Stub({"prompt_injection": noul(0.9), "jailbreak": noul(0.2),
                                      "requests_sensitive_data": noul(0.8), "requests_privilege_change": noul(0.1)}))
    r = classify.check_inputs(eng, "b")
    files = {x["file"] for x in r["inputs"]}
    assert files == {"ticket-88213-injected.txt", "ticket-88190-benign.txt"}
    assert all("prompt_injection" in x["flagged"] for x in r["inputs"])  # stub flags everything; wiring only

def test_not_run_is_reported_not_fabricated():
    eng = classify.Engine(agent=None); eng.agent = None; eng.error = "ProxyError: 403 Forbidden"
    r = classify.classify("b", intent("b"), spec("b"), eng)
    assert r["intent"]["status"] == "not run" and "403" in r["intent"]["reason"]
    sec = classify.pr_section(r)
    assert "Not run." in sec and "403" in sec

def test_agent_exception_that_echoes_its_input_is_refused():
    # The agent's own exception reason repeats the injected ticket: refuse under Q1, whatever else looks fine.
    ans = {"concrete_need": noul(0.9), "owner_accountable": noul(0.9),
           "scope": choice("single", ["single", "pattern", "broad"]), "ttl_fit": choice("matched", ["short", "matched", "long"]),
           "touches_suspect": noul(0.1), "authority_unverified": noul(0.1), "echoes_agent_input": noul(0.9)}
    verdict, reasons = classify.triage(ans)
    assert verdict == "refuse-under-Q1" and reasons == ["repeats what the agent read from an untrusted source"]

def test_unrecorded_approval_on_suspect_workload_is_refused():
    ans = {"concrete_need": noul(0.9), "owner_accountable": noul(0.9),
           "scope": choice("single", ["single", "pattern", "broad"]), "ttl_fit": choice("matched", ["short", "matched", "long"]),
           "touches_suspect": noul(0.9), "authority_unverified": noul(0.8), "echoes_agent_input": noul(0.1)}
    assert classify.triage(ans)[0] == "refuse-under-Q1"
    ans["touches_suspect"] = noul(0.1)
    assert classify.triage(ans)[0] == "human-review"   # same claim, clean workload: a human checks it

def test_evidence_and_runtime_asks_point_outside_admission():
    eng = classify.Engine(agent=Stub({
        "asks_network": noul(0.1), "asks_identity": noul(0.1), "asks_workload_security": noul(0.1),
        "asks_supply_chain": noul(0.1), "asks_agent_behaviour": noul(0.9), "asks_evidence": noul(0.9),
        "asks_runtime_detection": noul(0.8), "admission_sufficient": choice("partly", ["fully", "partly", "not"])}))
    s = spec("c"); s["controls"]["audit_replica_surge"]["enabled"] = False
    f = {x["family"]: x["finding"] for x in classify.check_intent(eng, intent("c"), s)["findings"]}
    assert "capture-evidence.sh" in f["evidence"] and "runtime/" in f["runtime_detection"]

def test_choice_ab_rendering_is_read_back_as_p_yes():
    # A checkpoint asked in choice_ab mode answers {"A": p_yes, "B": p_no}; classify must see noul-shaped P(yes).
    class ChoiceStub:
        def predict(self, state, questions):
            assert all(q["type"] == "choice" and set(q["criteria"]) == {"A", "B"} for q in questions.values())
            return {"answers": {k: {"type": "choice", "choice": "A", "probabilities": {"A": 0.83, "B": 0.17}} for k in questions}}
    eng = classify.Engine(agent=ChoiceStub(), mode="choice_ab")
    ans, _ = eng.ask({"channel": "email", "text": "x"}, classify.INPUT_Q)
    assert all(a["type"] == "noul" and abs(a["noul"] - 0.83) < 1e-9 for a in ans.values())

if __name__ == "__main__":
    import inspect
    fns = [f for n, f in sorted(globals().items()) if n.startswith("test_") and inspect.isfunction(f)]
    for f in fns:
        f(); print("ok ", f.__name__)
    print(f"{len(fns)} passed")
