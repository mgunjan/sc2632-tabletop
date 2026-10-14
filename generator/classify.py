#!/usr/bin/env python3
"""
Independent typed checks with Laya — a second, small model that the generator does not see.

Laya (convaiinnovations/laya, Apache-2.0) is an open reproduction of TypeSafe's Jev approach:
a ModernBERT-large encoder with a decision head that answers typed questions (choice / yes-no)
about a piece of text in one forward pass, with a probability per answer.

Three checks, each at a point where a HUMAN wrote free text:

  1. intent     — Does the intent ask for network / identity / workload-security / supply-chain /
                  agent-behaviour controls? Compared against what the generator produced:
                  "intent asks for identity; no identity control was generated" is a finding.
  2. exception  — Is the exception's reason concrete, is its scope tight, does its TTL fit,
                  does it touch the suspect workload? Produces a triage: routine / review / refuse.
  3. input      — (agent scenarios B, C) Does the text the agent consumed — a customer ticket,
                  a Slack message — contain instructions aimed at the AI rather than a request?
                  Uses Laya's own guard preset questions.

Rules this module holds itself to:
  - The generator never sees these results. They are an independent second opinion.
  - Nothing here blocks anything. Findings go in the PR for a human.
  - Laya's model card says it ships over-confident and needs calibration on your data. We have
    none, so probabilities are shown as indicative and every result is labelled UNCALIBRATED.
  - If Laya isn't installed or the weights can't be fetched, results say "not run" and why.
    No result is ever fabricated.

Usage:
  python3 generator/classify.py --scenario b                 # all checks for scenario B
  python3 generator/classify.py --scenario b --check input   # just the input guard
  python3 generator/classify.py --text "..." --check input   # ad hoc
"""
import argparse, json, pathlib, sys, time

ROOT = pathlib.Path(__file__).resolve().parent.parent
GEN = ROOT / "generator"
MODEL_ID = "convaiinnovations/laya"
DEFAULT_MODE = "labels_ab"  # noul rendering; see laya_variant/questions.py and upstream issue #156
YES = 0.5  # threshold on P(true) for a yes/no answer

# ------------------------------------------------------------------ question sets
# One definition, shared with laya_variant/ (training labels, calibration, evaluation).
sys.path.insert(0, str(ROOT / "laya_variant"))
from questions import INTENT_Q, EXCEPTION_Q, INPUT_Q, render, strip_private, p_true, NOUL_MODES  # noqa: E402

# Which generator controls satisfy which intent family. An empty set means admission control
# cannot implement it at all — asking for it is always a finding, pointing at where it lives.
FAMILY_CONTROLS = {
    "asks_network": {"egress_profile"},
    "asks_identity": {"deny_sa_token_for_agent_sidecars", "restrict_api_access", "deny_agent_mutation_outside_namespace"},
    "asks_workload_security": {"deny_privilege_escalation"},
    "asks_supply_chain": {"restrict_registry"},
    # Agent behaviour = what the agent may DO. Taking its token away is identity, not behaviour —
    # so in Scenario B an intent that asks for a tool allow-list is correctly reported as a gap.
    "asks_agent_behaviour": {"deny_agent_mutation_outside_namespace", "require_ticket_on_agent_changes"},
    "asks_evidence": set(),
    "asks_runtime_detection": set(),
}
OUTSIDE_ADMISSION = {
    "asks_evidence": "evidence capture is an ordered procedure, not an admission rule — see quarantine/capture-evidence.sh",
    "asks_runtime_detection": "runtime detection is Falco's job, not admission's — see runtime/",
}

SCENARIO_DIRS = {"a": "a-compromised-library", "b": "b-sidecar-agent", "c": "c-rogue-ops-agent"}
INCIDENT = {
    "a": "payments-api opened connections to namespaces it has never contacted; credentials suspected compromised.",
    "b": "The support-assistant sidecar in payments-api is calling tools outside its manifest; payments-api is suspected compromised.",
    "c": "The ops agent patched deployments outside its namespace after a Slack message; the agent's actions are suspect.",
}

# ------------------------------------------------------------------ engine

class Engine:
    """Wraps laya.load(); records why it could not run instead of pretending.

    `model_id` is a hub id or a local checkpoint directory (e.g. a laya_variant/ training run);
    `subfolder` picks a checkpoint inside a bundled repo ("typed-decisions", "multilingual").
    Answers are normalised so a yes/no question always reads as {"type": "noul", "noul": P(yes)},
    whatever rendering the model was asked in.
    """
    def __init__(self, model_id=MODEL_ID, device=None, agent=None, subfolder=None, mode=None):
        self.model_id, self.subfolder, self.agent, self.error = model_id, subfolder, agent, None
        self.mode = mode or DEFAULT_MODE
        if agent is not None:
            return
        try:
            import laya
            t = time.time()
            self.agent = laya.load(model_id, device=device, subfolder=subfolder)
            self.load_s = round(time.time() - t, 1)
            # A checkpoint trained here knows the rendering it was trained with; use that.
            self.mode = mode or self.variant.get("mode") or DEFAULT_MODE
        except Exception as e:  # ImportError, network, auth — all reported, none hidden
            self.error = f"{type(e).__name__}: {str(e).splitlines()[0][:200]}"

    @property
    def variant(self):
        cfg = getattr(self.agent, "cfg", None) or {}
        return cfg.get("trustfall_variant", {}) if isinstance(cfg, dict) else {}

    @property
    def calibrated(self):
        return bool(self.variant.get("calibrated"))

    def ask(self, state, questions):
        if self.agent is None:
            return None, None
        qs = render(questions, self.mode)
        t = time.perf_counter()
        r = self.agent.predict(state, strip_private(qs))
        ms = round((time.perf_counter() - t) * 1000, 1)
        out = {}
        for q, a in r["answers"].items():
            if qs.get(q, {}).get("_was_noul"):
                out[q] = {**a, "type": "noul", "noul": p_true(a)}
            else:
                out[q] = a
        return out, ms

def _yes(a):
    return a["noul"] >= YES

def _meta(engine, ms):
    v = engine.variant
    note = ("Calibrated on this repo's held-out cal split; see laya_variant/REPORT.md for what that does and does not mean."
            if engine.calibrated else
            "Uncalibrated. Laya's base checkpoints are near chance zero-shot on typed decisions and ship over-confident; "
            "probabilities are indicative only.")
    return {"model": engine.model_id + (f":{engine.subfolder}" if engine.subfolder else ""), "latency_ms": ms,
            "calibrated": engine.calibrated, "mode": engine.mode,
            "variant": {k: v.get(k) for k in ("repo_sha", "question_set", "data_manifest_sha", "selected_epoch") if k in v} or None,
            "note": note}

# ------------------------------------------------------------------ checks

def check_intent(engine, intent: str, spec: dict):
    ans, ms = engine.ask({"intent": intent.strip()}, INTENT_Q)
    if ans is None:
        return {"status": "not run", "reason": engine.error}
    enabled = {k for k, v in spec["controls"].items() if v.get("enabled")}
    declared = {cl["control"] for cl in spec["clauses"]}
    findings = []
    for fam, ctrls in FAMILY_CONTROLS.items():
        if fam not in ans:
            continue
        if _yes(ans[fam]) and fam in OUTSIDE_ADMISSION:
            findings.append({"family": fam.replace("asks_", ""), "p_yes": ans[fam]["noul"],
                             "finding": "intent asks for this; " + OUTSIDE_ADMISSION[fam]})
        elif _yes(ans[fam]) and not (ctrls & enabled):
            marked = sorted(ctrls & declared) or [c for c in declared if c == "not_implementable"]
            findings.append({
                "family": fam.replace("asks_", ""),
                "p_yes": ans[fam]["noul"],
                "finding": "intent asks for this; no generated policy addresses it"
                           + (" (the generator marked a clause not-implemented — check it's this one)" if marked else ""),
            })
    for fam, ctrls in FAMILY_CONTROLS.items():
        if fam not in ans:
            continue
        extra = sorted(c for c in ctrls & enabled if not spec["controls"][c].get("in_intent", True))
        if extra and not _yes(ans[fam]):
            findings.append({"family": fam.replace("asks_", ""), "p_yes": ans[fam]["noul"],
                             "finding": f"generated {extra} but intent does not ask for {fam.replace('asks_', '')} (the generator also flagged this as unasked)"})
    return {"status": "ok", **_meta(engine, ms),
            "answers": {k: (v["noul"] if v["type"] == "noul" else {"choice": v["choice"], "probabilities": v["probabilities"]}) for k, v in ans.items()},
            "findings": findings}

def triage(ans):
    """Typed answers -> routine / human-review / refuse-under-Q1. A rule a reviewer can read,
    not a model output: the model answers the questions, this decides what they add up to.
    Questions missing from `ans` (an older checkpoint, a stub) are skipped, not assumed."""
    reasons, g = [], ans.get
    if g("concrete_need") and not _yes(ans["concrete_need"]): reasons.append("reason is not a concrete dependency")
    if g("owner_accountable") and not _yes(ans["owner_accountable"]): reasons.append("owner is not clearly accountable")
    if g("scope") and ans["scope"]["choice"] == "broad": reasons.append("scope is broad")
    if g("ttl_fit") and ans["ttl_fit"]["choice"] == "long": reasons.append("TTL looks longer than the reason needs")
    if g("touches_suspect") and _yes(ans["touches_suspect"]): reasons.append("applies to the suspect workload")
    if g("authority_unverified") and _yes(ans["authority_unverified"]): reasons.append("relies on an approval that is not recorded")
    if g("echoes_agent_input") and _yes(ans["echoes_agent_input"]): reasons.append("repeats what the agent read from an untrusted source")
    suspect = "applies to the suspect workload" in reasons
    if ("repeats what the agent read from an untrusted source" in reasons or len(reasons) >= 3
            or (suspect and ("scope is broad" in reasons or "relies on an approval that is not recorded" in reasons))):
        return "refuse-under-Q1", reasons
    return ("human-review" if reasons else "routine"), reasons

def check_exceptions(engine, spec: dict, scenario: str):
    if not spec["exceptions"]:
        return {"status": "ok", "exceptions": [], "note": "no exceptions requested"}
    out = []
    for ex in spec["exceptions"]:
        ex = {"requested_by": "platform-ops", "approvals": [], **ex}
        ans, ms = engine.ask({"exception": ex, "incident": INCIDENT[scenario], "agent_inputs": _agent_inputs(scenario)}, EXCEPTION_Q)
        if ans is None:
            return {"status": "not run", "reason": engine.error}
        verdict, reasons = triage(ans)
        out.append({"workload": ex["workload"], "control": ex["control"], "latency_ms": ms, "triage": verdict, "reasons": reasons,
                    "answers": {k: (v["noul"] if v["type"] == "noul" else v["choice"]) for k, v in ans.items()}})
    return {"status": "ok", **_meta(engine, None), "exceptions": out}

def _agent_inputs(scenario):
    d = ROOT / "scenarios" / SCENARIO_DIRS[scenario] / "inputs"
    return [f.read_text() for f in sorted(d.glob("*.txt"))] if d.exists() else []

def check_inputs(engine, scenario: str):
    d = ROOT / "scenarios" / SCENARIO_DIRS[scenario] / "inputs"
    if not d.exists():
        return {"status": "ok", "inputs": [], "note": "no agent inputs in this scenario"}
    out = []
    for f in sorted(d.glob("*.txt")):
        ans, ms = engine.ask({"channel": "chat" if f.name.startswith("slack") else "email", "text": f.read_text()}, INPUT_Q)
        if ans is None:
            return {"status": "not run", "reason": engine.error}
        flags = [k for k, v in ans.items() if _yes(v)]
        out.append({"file": f.name, "latency_ms": ms, "flagged": flags, "p": {k: v["noul"] for k, v in ans.items()}})
    return {"status": "ok", **_meta(engine, None), "inputs": out}

def classify(scenario: str, intent: str, spec: dict, engine=None, checks=("intent", "exception", "input")):
    engine = engine or Engine()
    res = {"engine": {"model": engine.model_id, "subfolder": engine.subfolder, "mode": engine.mode,
                      "calibrated": engine.calibrated, "loaded": engine.agent is not None, "error": engine.error}}
    if "intent" in checks: res["intent"] = check_intent(engine, intent, spec)
    if "exception" in checks: res["exception"] = check_exceptions(engine, spec, scenario)
    if "input" in checks: res["input"] = check_inputs(engine, scenario)
    return res

# ------------------------------------------------------------------ PR section

def pr_section(res) -> str:
    eng = res["engine"]
    name = eng["model"] + (f":{eng['subfolder']}" if eng.get("subfolder") else "")
    cal = ("**Calibrated** on this repo's held-out split — see `laya_variant/REPORT.md` for accuracy on held-out templates."
           if eng.get("calibrated") else "**Uncalibrated** — probabilities are indicative.")
    L = ["## Independent check — Laya (a second model the generator never sees)", "",
         f"> Small open encoder classifier (`{name}`, an open reproduction of TypeSafe's Jev approach).",
         f"> {cal} Nothing here blocks; it tells the reviewer where to look.", ""]
    if not res["engine"]["loaded"]:
        return "\n".join(L + [f"**Not run.** {res['engine']['error']}",
                              "", "Run `python3 generator/classify.py --scenario <a|b|c>` on a machine that can reach Hugging Face.", ""])
    i = res.get("intent", {})
    if i.get("status") == "ok":
        L += [f"**Intent coverage** ({i['latency_ms']} ms)", ""]
        if i["findings"]:
            L += ["| Family | P(asks) | Finding |", "|---|---|---|"] + [f"| {f['family']} | {f['p_yes']:.2f} | {f['finding']} |" for f in i["findings"]]
        else:
            L.append("No disagreement between the intent and the generated controls.")
        L.append("")
    e = res.get("exception", {})
    if e.get("status") == "ok" and e.get("exceptions"):
        L += ["**Exception triage**", "", "| Workload | Triage | Why |", "|---|---|---|"]
        L += [f"| `{x['workload']}` | **{x['triage']}** | {'; '.join(x['reasons']) or '—'} |" for x in e["exceptions"]]
        L.append("")
    g = res.get("input", {})
    if g.get("status") == "ok" and g.get("inputs"):
        L += ["**What the agent read**", "", "| Input | Flags | ms |", "|---|---|---|"]
        L += [f"| `{x['file']}` | {', '.join(x['flagged']) or 'none'} | {x['latency_ms']} |" for x in g["inputs"]]
        L.append("")
    return "\n".join(L) + "\n"

# ------------------------------------------------------------------ CLI

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", choices=SCENARIO_DIRS)
    ap.add_argument("--check", choices=["intent", "exception", "input", "all"], default="all")
    ap.add_argument("--text", help="ad hoc text for --check input or intent")
    ap.add_argument("--device")
    ap.add_argument("--model", default=MODEL_ID, help="hub id or local checkpoint dir (e.g. a laya_variant run)")
    ap.add_argument("--subfolder", help='checkpoint inside a bundled repo, e.g. "typed-decisions"')
    ap.add_argument("--mode", choices=NOUL_MODES, help="yes/no rendering (default: the checkpoint's own, else labels_ab)")
    ap.add_argument("--out", help="write JSON here")
    a = ap.parse_args()
    eng = Engine(a.model, device=a.device, subfolder=a.subfolder, mode=a.mode)
    if a.text:
        if a.check == "intent":
            ans, ms = eng.ask({"intent": a.text}, INTENT_Q)
        else:
            ans, ms = eng.ask({"channel": "unknown", "text": a.text}, INPUT_Q)
        res = {"engine": {"loaded": eng.agent is not None, "error": eng.error}, "latency_ms": ms, "answers": ans}
    else:
        if not a.scenario:
            sys.exit("--scenario or --text required")
        spec = json.loads((GEN / f"spec-{a.scenario}.json").read_text())
        intent = (GEN / f"intent-{a.scenario}.txt").read_text()
        checks = ("intent", "exception", "input") if a.check == "all" else (a.check,)
        res = classify(a.scenario, intent, spec, eng, checks)
    s = json.dumps(res, indent=2)
    if a.out:
        pathlib.Path(a.out).write_text(s + "\n")
    print(s)

if __name__ == "__main__":
    main()
