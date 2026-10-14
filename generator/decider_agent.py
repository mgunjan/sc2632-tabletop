#!/usr/bin/env python3
"""
The policy agent, built on a decision model (Strands Decider, a Jev-style "pick one of these options" model).

Division of labour, on purpose:
  - the MODEL does the one judgement call: which control (if any) each sentence of the intent asks for,
    with a reliability score. Below the threshold it does not guess: the clause is escalated to a human.
  - CODE fills every value (namespace, registry, service account) from the intent and the workload list,
    and never invents exceptions: whatever the policies block shows up in the admission report, and a
    human gives it an owner and an expiry (Round 2).
  - the COMPILER and the TESTS check the result (generate.py --from-spec ... --spec-meta ...).

  python3 generator/decider_agent.py --scenario a --decider http://127.0.0.1:8000 --out /tmp/spec-a.json
  python3 generator/generate.py --scenario a --from-spec /tmp/spec-a.json --spec-meta /tmp/spec-a.meta.json

The model picks from a fixed list and has no deployment authority. A wrong pick can omit a required control
or propose an inappropriate restriction. Admission observations alone cannot prove complete intent coverage.

Server: Strands Decider (Apache 2.0), `strands-decider serve <model> --port 8000`; scripts/decider-up.sh on a Mac.
--replay reads a recorded run (the *.meta.json written by --out) instead of calling the model, and says so.
"""
import argparse, collections, datetime, hashlib, json, pathlib, re, sys, time, urllib.request

GEN = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(GEN))
from decision_contract import parse_answer, threshold as valid_threshold

# One line per option. The definitions are the prompt: they say what admission can and cannot see.
CONTROLS = {
    "egress_profile": "restrict which workloads, namespaces or destinations a workload may connect to (east-west or outbound traffic)",
    "deny_privilege_escalation": "stop containers running privileged, gaining more privileges than they start with, or running as root",
    "restrict_registry": "allow container images only from an approved registry, or block images from public registries",
    "restrict_api_access": "limit a workload's credentials, secrets or permissions on the Kubernetes API (needs RBAC; admission alone cannot)",
    "deny_sa_token_for_agent_sidecars": "stop an AI agent or assistant sidecar from using the Pod's Kubernetes identity (its service account token)",
    "deny_agent_mutation_outside_namespace": "stop an AI agent from changing workloads outside its own namespace",
    "require_ticket_on_agent_changes": "require a ticket or change reference on changes an AI agent makes",
    "audit_replica_surge": "flag sudden large increases in a workload's replica count",
    "process": "how or when to roll out or time-box the change (staging, expiries, not disrupting service), not what to allow",
    "not_implementable": "something admission control cannot see or enforce: reads, tool calls inside an application, runtime behaviour, people",
}
QUESTION = {"control": {"type": "choice", "instructions": "Which option does `clause` ask for? Read it in the context of `intent`.",
                        "criteria": CONTROLS}}
DEFAULT_MODEL = "StrandsAgents/strands-decider-2B-qwen3.5-v1-2610"


def split_clauses(intent):
    return [c.strip() for c in re.split(r"(?<=[.!?])\s+", intent.strip()) if c.strip()]


def _state(clause, intent):
    return f"clause: {clause}\nintent: {intent.strip()}"


def parse_choice(resp):
    """Server response -> (choice, confidence, probabilities) or (None, 0, {}) if unreadable."""
    return parse_answer(resp, "control", CONTROLS, allow_direct=True, infer_choice=True)


def ask(url, clause, intent, timeout=60):
    body = {"state": _state(clause, intent), "questions": QUESTION}
    req = urllib.request.Request(f"{url}/v1/systemone", data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    t0 = time.monotonic()
    with urllib.request.urlopen(req, timeout=timeout) as r:
        out = json.loads(r.read())
    out.setdefault("client_ms", round((time.monotonic() - t0) * 1000, 1))
    return out


def healthy(url, timeout=3):
    """True when a Decider server answers /health within `timeout` seconds."""
    try:
        with urllib.request.urlopen(f"{url}/health", timeout=timeout) as r:
            return r.status == 200
    except Exception:  # noqa: BLE001
        return False


def decide(intent, url, threshold, asker=ask):
    out = []
    for c in split_clauses(intent):
        try:
            raw = asker(url, c, intent)
        except Exception as e:  # noqa: BLE001 — an unreachable model escalates, it never guesses
            raw = {"error": f"{type(e).__name__}: {e}"}
        pick, conf, pr = parse_choice(raw)
        out.append({"text": c, "choice": pick, "confidence": round(conf, 4), "probabilities": pr,
                    "escalated": pick is None or conf < threshold, "raw": raw})
    return out


# ---------------------------------------------------------------------- deterministic filling

def inventory(fixtures):
    import yaml
    return [d for d in yaml.safe_load_all(pathlib.Path(fixtures).read_text()) if d]


def fill_spec(decisions, intent, docs):
    """Turn the model's per-clause choices into a GuardrailSpec. Every value comes from the intent text or the
    workload list; nothing here is decided by the model. Escalated clauses enable nothing."""
    nss = collections.Counter(d["metadata"]["namespace"] for d in docs)
    m = re.search(r"\b([a-z0-9][a-z0-9-]*) namespace\b", intent)
    namespace = m.group(1) if m else nss.most_common(1)[0][0]
    clauses, controls = [], {}
    for i, d in enumerate(decisions, 1):
        if d["escalated"]:
            clauses.append({"id": i, "text": d["text"][:500], "control": "not_implementable",
                            "note": f"ESCALATED to a human: the model was not confident enough (best guess {d['choice']}, {d['confidence']:.2f})."[:500]})
            continue
        ch = d["choice"]
        ctl = "not_implementable" if ch == "process" else ch
        note = {"process": "Rollout or time-boxing: handled by the staged rollout and exception expiries.",
                "not_implementable": "Admission control cannot see or enforce this.",
                "restrict_api_access": "Needs RBAC changes; admission alone cannot do it."}.get(ch)
        cl = {"id": i, "text": d["text"][:500], "control": ctl}
        if note: cl["note"] = note
        clauses.append(cl)
        if ctl in ("not_implementable",):
            continue
        if ctl == "egress_profile":
            profs = sorted({x["metadata"].get("labels", {}).get("trustfall.example/egress-profile") for x in docs} - {None})
            controls[ctl] = {"enabled": True, "approved_profiles": profs or ["none"], "in_intent": True}
        elif ctl == "restrict_registry":
            hosts = collections.Counter(c["image"].split("/")[0] for x in docs if x["kind"] == "Pod" for c in x["spec"]["containers"])
            controls[ctl] = {"enabled": True, "registry": hosts.most_common(1)[0][0] if hosts else "registry.local", "in_intent": True}
        elif ctl == "restrict_api_access":
            controls[ctl] = {"enabled": False, "in_intent": True, "note": "Requires RBAC and ServiceAccount changes beyond admission control."}
        elif ctl in ("deny_agent_mutation_outside_namespace", "require_ticket_on_agent_changes"):
            am = re.search(r"\bthe ([a-z]+(?:[ -][a-z]+)?) (?:agent|bot)\b", intent.lower())
            agent = (am.group(1).split()[-1] + "-agent") if am else "agent"
            c = {"enabled": True, "in_intent": True, "agent_serviceaccount": f"system:serviceaccount:{namespace}:{agent}"}
            if ctl == "deny_agent_mutation_outside_namespace": c["home_namespace"] = namespace
            controls[ctl] = c
        elif ctl == "audit_replica_surge":
            reps = [x["spec"].get("replicas", 1) for x in docs if x["kind"] != "Pod"]
            controls[ctl] = {"enabled": True, "in_intent": True, "threshold": max(2 * max(reps or [1]), 2)}
        else:   # deny_privilege_escalation, deny_sa_token_for_agent_sidecars
            controls[ctl] = {"enabled": True, "in_intent": True}
    return {"namespace": namespace, "clauses": clauses, "controls": controls, "exceptions": [],
            "rollout": ["Audit", "Warn", "Deny"]}


SHORT = {"egress_profile": "limit who it can talk to", "deny_privilege_escalation": "no privileged / root containers",
         "restrict_registry": "approved registry only", "restrict_api_access": "limit its Kubernetes API access (RBAC)",
         "deny_sa_token_for_agent_sidecars": "no Kubernetes identity for the agent sidecar",
         "deny_agent_mutation_outside_namespace": "agent changes stay in its namespace",
         "require_ticket_on_agent_changes": "ticket on every agent change", "audit_replica_surge": "flag replica surges",
         "process": "rollout plan, not a policy", "not_implementable": "admission cannot enforce this"}


def show(decisions, out=sys.stdout):
    for d in decisions:
        if d["escalated"]:
            tag, what = "ESCALATE", f"to a human (best guess: {d['choice']})"
        else:
            tag, what = "        ", f"{d['choice']}: {SHORT.get(d['choice'], '')}"
        out.write(f"   {d['confidence']:.2f} {tag} \"{d['text'][:58]}{'…' if len(d['text']) > 58 else ''}\"\n")
        out.write(f"                 -> {what}\n")


def main():
    import generate as g
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", choices=g.SCENARIOS, default="a")
    ap.add_argument("--intent"); ap.add_argument("--intent-file")
    ap.add_argument("--decider", default="http://127.0.0.1:8000")
    ap.add_argument("--model", default=DEFAULT_MODEL, help="recorded in provenance only; the server decides what runs")
    ap.add_argument("--threshold", type=valid_threshold, default=0.6, help="below this reliability score a clause goes to a human")
    ap.add_argument("--replay", help="a recorded *.meta.json: reuse its decisions instead of calling the model")
    ap.add_argument("--out", required=True, help="spec JSON path; <out-stem>.meta.json gets the provenance")
    ap.add_argument("--quiet", action="store_true", help="no table on stdout")
    a = ap.parse_args()
    sc = g.SCENARIOS[a.scenario]
    intent = a.intent or pathlib.Path(a.intent_file or g.GEN / f"intent-{a.scenario}.txt").read_text()
    if a.replay:
        rec = json.loads(pathlib.Path(a.replay).read_text())
        recorded = rec["decisions"]
        if [d["text"] for d in recorded] != split_clauses(intent) or rec.get("intent_sha256") != hashlib.sha256(intent.encode()).hexdigest():
            sys.exit("replay: the recording was made for a different intent")
        if rec.get("question_sha256") != hashlib.sha256(json.dumps(QUESTION, sort_keys=True).encode()).hexdigest() or rec.get("threshold") != a.threshold:
            sys.exit("replay: questions or threshold differ from the recording")
        decisions = []
        for row in recorded:
            choice, confidence, probabilities = parse_choice(row.get("raw"))
            decisions.append({**row, "choice": choice, "confidence": round(confidence, 4), "probabilities": probabilities,
                              "escalated": choice is None or confidence < a.threshold})
        model = rec["model"] + " (REPLAYED from " + pathlib.Path(a.replay).name + ")"
    else:
        decisions, model = decide(intent, a.decider, a.threshold), f"decider:{a.model}"
    spec = fill_spec(decisions, intent, inventory(sc["dir"] / sc["fixtures"]))
    g.validate_spec(spec)
    out = pathlib.Path(a.out); out.write_text(json.dumps(spec, indent=2) + "\n")
    served = sorted({d["raw"].get("model") for d in decisions if isinstance(d.get("raw"), dict) and d["raw"].get("model")})
    meta = {"model": model, "served_model": served, "agent": "generator/decider_agent.py", "threshold": a.threshold,
            "intent_sha256": hashlib.sha256(intent.encode()).hexdigest(),
            "question_sha256": hashlib.sha256(json.dumps(QUESTION, sort_keys=True).encode()).hexdigest(),
            "recorded_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
            "decisions": decisions}
    out.with_suffix(".meta.json").write_text(json.dumps(meta, indent=2) + "\n")
    if not a.quiet:
        show(decisions)
    if all(d["escalated"] for d in decisions):
        sys.exit(3)   # nothing decided: the caller must not present this as an agent result


if __name__ == "__main__":
    main()
