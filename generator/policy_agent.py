#!/usr/bin/env python3
"""
The policy agent: a decide -> act -> observe loop that turns a security intent into a pull request.

  python3 generator/policy_agent.py --scenario a                 # model at http://127.0.0.1:8000, cluster if reachable
  python3 generator/policy_agent.py --scenario a --replay REC    # re-run every tool, with the model's recorded answers

What it does, in order (the harness fixes the order; the MODEL makes every decision; the TOOLS are real):
  1. map the intent      for each sentence, which guardrail does it ask for?          (model, per sentence)
  2. look                what is running in the namespace now?                        (kubectl, or the fixtures)
  3. dependencies        for each egress profile in use: a known dependency to keep?  (model, per profile)
  4. write               fill the values, render the policies                         (code + templates)
  5. test                kyverno apply against the running Pods                       (kyverno CLI)
  6. blocked?            for each workload the policies would block:                  (model, per workload)
                           allow_and_retest -> change the policy and go back to 4 (at most 3 rounds)
                           request_exception -> a request in the PR; a HUMAN gives it an owner and an expiry
                           block_is_intended -> keep the block
  7. open the PR         policies, admission results, exception requests, every decision and its confidence

Every unreadable or below-threshold answer goes to a human. The agent has no deployment authority and never
grants exceptions. Wrong choices can omit controls or widen proposed dependency allowances. Fixed tests and
an independent requirement ledger accompany the proposal; promotion always requires human review.

Model: Strands Decider (Apache 2.0) behind `strands-decider serve` (scripts/decider-up.sh).
"""
import argparse, collections, datetime, hashlib, json, pathlib, subprocess, sys, tempfile, time, urllib.request

GEN = pathlib.Path(__file__).resolve().parent
ROOT = GEN.parent
sys.path.insert(0, str(GEN))
import decider_agent as da  # noqa: E402
import generate as g  # noqa: E402
from decision_contract import parse_answer, score, threshold as valid_threshold

DEP_Q = {"type": "choice",
         "instructions": "The intent is in `intent`. `profile` is an egress profile that workloads in the namespace use today, "
                         "and `used_by` lists them. Should the new egress policy keep allowing this profile?",
         "criteria": {"preserve": "keep allowing it: it is one of the namespace's known service dependencies",
                      "deny": "stop allowing it: it is east-west traffic the intent asks to deny"}}
BLOCK_Q = {"type": "choice",
           "instructions": "The intent is in `intent`. A policy we just wrote would block `workload`; `reason` is the admission "
                           "message. What should happen?",
           "criteria": {"allow_and_retest": "the policy is wrong for this workload: its traffic is a known dependency the "
                                            "intent says to preserve, so change the policy to allow it and test again",
                        "request_exception": "the workload has to keep running for now but should not be allowed for good: "
                                             "ask a human for a time-boxed exception with an owner and an expiry",
                        "block_is_intended": "blocking this workload is what the intent asks for"}}
QUESTIONS_SHA = hashlib.sha256(json.dumps([da.QUESTION, DEP_Q, BLOCK_Q], sort_keys=True).encode()).hexdigest()
IGNORED_PROFILES = {"quarantined", "missing"}   # set by Quarantine Mode, or no label: not dependencies to judge
MAX_ROUNDS = 3


def call(url, state, question, timeout=60):
    body = {"state": state, "questions": {"q": question}}
    req = urllib.request.Request(f"{url}/v1/systemone", data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    t0 = time.monotonic()
    with urllib.request.urlopen(req, timeout=timeout) as r:
        out = json.loads(r.read())
    out["client_ms"] = round((time.monotonic() - t0) * 1000, 1)
    return out


def parse(resp, options):
    choice, confidence, _ = parse_answer(resp, "q", options)
    return choice, confidence


class Recorded:
    """Answers from a recorded run, in order. Refuses if the agent asks something it was not asked then."""
    def __init__(self, path):
        self.recording = json.loads(pathlib.Path(path).read_text())
        self.calls = self.recording["calls"]
        self.i = 0

    def bind(self, scenario, intent, threshold):
        rec = self.recording
        if rec.get("scenario") != scenario or rec.get("intent_sha256") != hashlib.sha256(intent.encode()).hexdigest():
            raise RuntimeError("replay: scenario or intent differs from the recording")
        if rec.get("questions_sha256") != QUESTIONS_SHA or rec.get("threshold") != threshold:
            raise RuntimeError("replay: questions or threshold differs from the recording")

    def finish(self):
        if self.i != len(self.calls):
            raise RuntimeError("replay: not all recorded calls were consumed")

    def __call__(self, url, state, question):
        if self.i >= len(self.calls):
            raise RuntimeError("replay: the agent asked more questions than the recording holds")
        c = self.calls[self.i]; self.i += 1
        if c["state_sha256"] != hashlib.sha256(state.encode()).hexdigest():
            raise RuntimeError(f"replay: question {self.i} differs from the recording (the cluster or the intent changed)")
        return c["response"]


# ---------------------------------------------------------------------------------------------- tools

def observe(sc, live):
    """Tool: what runs in the namespace. Live Pods (kubectl) when asked and reachable, else the scenario fixtures."""
    fixtures = sc["dir"] / sc["fixtures"]
    if live and sc["kind"] == "Pod":
        try:
            p = subprocess.run(["kubectl", "-n", "payments", "get", "pods", "-o", "json", "--request-timeout=5s"],
                               capture_output=True, text=True, timeout=10)
            if p.returncode == 0:
                docs = []
                for it in json.loads(p.stdout)["items"]:
                    md = it["metadata"]
                    if md.get("deletionTimestamp") or md.get("labels", {}).get("trustfall.example/probe"):
                        continue
                    docs.append({"apiVersion": "v1", "kind": "Pod",
                                 "metadata": {k: md[k] for k in ("name", "namespace", "labels", "annotations") if k in md},
                                 "spec": {k: v for k, v in it["spec"].items() if k in ("containers", "initContainers", "volumes",
                                          "securityContext", "serviceAccountName", "automountServiceAccountToken", "hostNetwork", "hostPID")}})
                if docs:
                    import yaml
                    f = pathlib.Path(tempfile.mkdtemp()) / "running-pods.yaml"
                    f.write_text(yaml.safe_dump_all(docs, sort_keys=True))
                    return docs, f, "live cluster"
        except (OSError, subprocess.SubprocessError, ValueError):
            pass
    return da.inventory(fixtures), fixtures, "scenario fixtures"


def spec_ns(docs):
    return collections.Counter(d['metadata'].get('namespace', '?') for d in docs).most_common(1)[0][0]


def workload_of(doc):
    return doc["metadata"].get("labels", {}).get("app") or doc["metadata"]["name"]


def write(spec, out):
    """Tool: render the policies (templates) into out/policies. Returns {policy name: action}."""
    import yaml
    pol = out / "policies"
    for f in pol.glob("*.yaml"):
        f.unlink()
    pol.mkdir(parents=True, exist_ok=True)
    policies = g.render_policies(spec, spec["rollout"][-1])
    for name, text in policies.items():
        (pol / name).write_text(text)
    return {n[:-5]: yaml.safe_load(t)["spec"]["validationActions"][0] for n, t in policies.items()}


def test(out, action_of, resources, userinfo):
    """Tool: kyverno apply the written policies against the running Pods."""
    return g.outcomes(g.simulate(out / "policies", resources, None, userinfo), action_of)


# ---------------------------------------------------------------------------------------------- agent

class Agent:
    def __init__(self, scenario, intent, url, threshold, live, out, asker=call, echo=print, expected_model=None):
        self.sc, self.scenario, self.intent, self.url, self.th = g.SCENARIOS[scenario], scenario, intent, url, threshold
        self.live, self.out, self.asker, self.echo = live, out, asker, echo
        self.th = score(threshold)
        self.expected_model = expected_model
        if isinstance(asker, Recorded):
            asker.bind(scenario, intent, self.th)
        self.calls, self.trace, self.escalations, self.requests, self.accepted = [], [], [], [], []
        self.n = 0

    def step(self, what, detail=""):
        self.n += 1
        self.trace.append({"step": self.n, "what": what, "detail": detail})
        self.echo(f"   agent ▸ {what:<22} {detail}")

    def decide(self, question, state, about):
        try:
            resp = self.asker(self.url, state, question)
        except Exception as e:  # noqa: BLE001 — an unreachable or unreadable model escalates, never guesses
            if isinstance(e, RuntimeError) and str(e).startswith("replay:"):
                raise
            resp = {"error": f"{type(e).__name__}: {e}"}
        choice, conf = parse(resp, question["criteria"])
        if self.expected_model and (not isinstance(resp, dict) or resp.get("model") != self.expected_model):
            raise RuntimeError("model identity differs from the evaluated candidate")
        self.calls.append({"about": about, "state_sha256": hashlib.sha256(state.encode()).hexdigest(), "response": resp,
                           "choice": choice, "confidence": round(conf, 4)})
        if choice is None or conf < self.th:
            self.escalations.append({"about": about, "best_guess": choice, "confidence": round(conf, 4)})
            return None, conf
        return choice, conf

    def run(self):
        out = self.out
        if out.exists() and any(out.iterdir()):
            raise RuntimeError("output already contains evidence; choose a fresh directory")
        out.mkdir(parents=True, exist_ok=True)
        userinfo = (self.sc["dir"] / self.sc["userinfo"]) if self.sc["userinfo"] else None

        # 1. map the intent: one decision per sentence
        decisions = []
        for clause in da.split_clauses(self.intent):
            ch, conf = self.decide(da.QUESTION["control"], da._state(clause, self.intent), f"sentence: {clause}")
            last = self.calls[-1]
            decisions.append({"text": clause, "choice": ch if ch else last["choice"], "confidence": round(conf, 4),
                              "escalated": ch is None})
        picked = [("?" if d["escalated"] else d["choice"]) for d in decisions]
        self.step("map the intent", f"{len(decisions)} sentences -> " + ", ".join(picked))
        da.show(decisions, out=_Echo(self.echo))

        # 2. look at what is running
        docs, resources, source = observe(self.sc, self.live)
        self.step("look at what's running", f"{len({workload_of(d) for d in docs})} workloads in {spec_ns(docs)} ({source})")
        spec = da.fill_spec(decisions, self.intent, docs)
        if not any(c.get("enabled") for c in spec["controls"].values()):
            self.step("stop", "no sentence maps to a guardrail it can write: handing the intent to a human")
            return self.open_pr(spec, [], source, decisions)

        # 3. egress dependencies: one decision per profile in use
        if "egress_profile" in spec["controls"]:
            users = collections.defaultdict(list)
            for d in docs:
                p = d["metadata"].get("labels", {}).get("trustfall.example/egress-profile", "missing")
                if p not in IGNORED_PROFILES and workload_of(d) not in users[p]:
                    users[p].append(workload_of(d))
            keep, said = [], []
            for p in sorted(users):
                st = f"intent: {self.intent.strip()}\nprofile: {p}\nused_by: {', '.join(users[p])}"
                ch, conf = self.decide(DEP_Q, st, f"egress profile {p}")
                if ch != "deny":     # preserve, or unsure: keep it allowed (nothing breaks) and flag it for a human
                    keep.append(p)
                said.append(f"{p} {ch or 'ASK A HUMAN'} {conf:.2f}")
            spec["controls"]["egress_profile"]["approved_profiles"] = keep or ["none"]
            self.step("decide dependencies", " · ".join(said))

        # 4-6. write, test, react
        rows, handled = [], set()
        for rnd in range(1, MAX_ROUNDS + 1):
            g.validate_spec(spec)
            action_of = write(spec, out)
            self.step("write policies", ", ".join(sorted(action_of)) + (f" (round {rnd})" if rnd > 1 else ""))
            rows = test(out, action_of, resources, userinfo)
            byw = {d["metadata"]["name"]: workload_of(d) for d in docs}
            blocked = sorted({(byw.get(r["workload"].split("/")[1], r["workload"]), r["policy"], r["message"])
                              for r in rows if r["result"].startswith("WOULD")})
            new = [b for b in blocked if (b[0], b[1]) not in handled]
            self.step("test on running pods", ("; ".join(f"{w} WOULD BLOCK ({p})" for w, p, _ in new)) or "nothing would be blocked")
            if not new:
                break
            changed = False
            for w, p, msg in new:
                handled.add((w, p))
                st = f"intent: {self.intent.strip()}\nworkload: {w}\npolicy: {p}\nreason: {msg[:300]}"
                ch, conf = self.decide(BLOCK_Q, st, f"blocked {w} by {p}")
                if ch == "allow_and_retest" and p == g.POLICY_FILE["egress_profile"]:
                    prof = next((d["metadata"].get("labels", {}).get("trustfall.example/egress-profile") for d in docs if workload_of(d) == w), None)
                    if prof and prof not in spec["controls"]["egress_profile"]["approved_profiles"]:
                        spec["controls"]["egress_profile"]["approved_profiles"].append(prof); changed = True
                    self.step(f"decide: {w}", f"allow_and_retest {conf:.2f} -> allow profile '{prof}', test again")
                elif ch == "allow_and_retest":
                    # only an egress profile can be widened by the agent; anything else needs a person
                    self.requests.append({"workload": w, "policy": p, "reason": msg, "confidence": round(conf, 4),
                                          "note": "agent wanted to allow it; only a human can widen this policy"})
                    self.step(f"decide: {w}", f"allow {conf:.2f} -> not the agent's call for {p}: exception request")
                elif ch == "request_exception":
                    self.requests.append({"workload": w, "policy": p, "reason": msg, "confidence": round(conf, 4)})
                    self.step(f"decide: {w}", f"request_exception {conf:.2f} -> needs a human owner and expiry")
                elif ch == "block_is_intended":
                    self.accepted.append({"workload": w, "policy": p, "confidence": round(conf, 4)})
                    self.step(f"decide: {w}", f"block_is_intended {conf:.2f}")
                else:
                    self.requests.append({"workload": w, "policy": p, "reason": msg, "confidence": round(conf, 4),
                                          "note": "model unsure: a human decides"})
                    self.step(f"decide: {w}", f"unsure ({conf:.2f}) -> a human decides")
            if not changed:
                break
        return self.open_pr(spec, rows, source, decisions)

    def open_pr(self, spec, rows, source, decisions):
        out = self.out
        if isinstance(self.asker, Recorded):
            self.asker.finish()
        g.validate_spec(spec)
        # Both compiler and agent use the same stage renderer. No exception is granted here.
        g.write_policy_artifacts(spec, out)
        import policy_contracts
        review = policy_contracts.evaluate(self.scenario, self.intent, spec, decisions, out)
        self.step("write local review proposal", f"{out.name}/PR.md: {len(self.requests)} exception request(s), "
                                       f"{len(self.escalations)} item(s) for a human")
        (out / "spec.json").write_text(json.dumps(spec, indent=2) + "\n")
        served = sorted({c["response"].get("model") for c in self.calls if isinstance(c["response"], dict) and c["response"].get("model")})
        prov = {"agent": "generator/policy_agent.py", "model": served or ["none answered"], "threshold": self.th,
                "questions_sha256": QUESTIONS_SHA, "intent_sha256": hashlib.sha256(self.intent.encode()).hexdigest(),
                "tested_against": source, "source_kind": "fixtures" if source == "scenario fixtures" else "live", "steps": len(self.trace), "model_calls": len(self.calls),
                "spec_sha256": hashlib.sha256(json.dumps(spec, sort_keys=True).encode()).hexdigest(),
                "review_status": review["status"], "promotion_allowed": False}
        (out / "provenance.json").write_text(json.dumps(prov, indent=2) + "\n")
        body = g.pr_body(self.sc, spec, rows, rows, prov, self.intent)
        body += policy_contracts.pr_section(review)
        import control_library
        body += control_library.pr_section(json.loads((out/'control-review.json').read_text()))
        extra = ["## What the agent did", "", "| Step | What | Detail |", "|---|---|---|"]
        extra += [f"| {t['step']} | {t['what']} | {t['detail']} |" for t in self.trace]
        extra += ["", "## Exception requests (the agent cannot grant these: a human sets owner and expiry, or says no)", ""]
        extra += ([f"- `{r['workload']}` blocked by `{r['policy']}` (confidence {r['confidence']:.2f}){': ' + r['note'] if r.get('note') else ''}"
                   for r in self.requests] or ["None."])
        extra += ["", "## Handed to a human (model below the threshold)", ""]
        extra += ([f"- {e['about']} (best guess {e['best_guess']}, {e['confidence']:.2f})" for e in self.escalations] or ["None."])
        body = body.replace("## Rollout plan", "\n".join(extra) + "\n\n## Rollout plan", 1)
        (out / "PR.md").write_text(body)
        (out / "admission-report.json").write_text(json.dumps({"without_exceptions": rows, "with_exceptions": rows}, indent=2) + "\n")
        rec = {"recorded_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
               "scenario": self.scenario, "intent_sha256": prov["intent_sha256"], "questions_sha256": QUESTIONS_SHA,
               "threshold": self.th, "model": served, "tested_against": source, "trace": self.trace, "requests": self.requests,
               "escalations": self.escalations, "accepted_blocks": self.accepted, "calls": self.calls, "readiness": review}
        (out / "agent-run.json").write_text(json.dumps(rec, indent=2) + "\n")
        return rec


class _Echo:
    def __init__(self, f): self.f, self.buf = f, ""
    def write(self, s):
        self.buf += s
        while "\n" in self.buf:
            line, self.buf = self.buf.split("\n", 1); self.f(line)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", choices=g.SCENARIOS, default="a")
    ap.add_argument("--intent"); ap.add_argument("--intent-file")
    ap.add_argument("--decider", default="http://127.0.0.1:8000")
    ap.add_argument("--threshold", type=valid_threshold, default=0.6)
    ap.add_argument("--expected-model", help="refuse a server whose response identity differs from the evaluated candidate")
    ap.add_argument("--fixtures", action="store_true", help="test against the scenario fixtures, not the live cluster")
    ap.add_argument("--replay", help="an agent-run.json: re-run every tool with the model's recorded answers")
    ap.add_argument("--out", default=None, help="directory for the PR (default output/agent-<scenario>-<time>)")
    a = ap.parse_args()
    intent = a.intent or pathlib.Path(a.intent_file or GEN / f"intent-{a.scenario}.txt").read_text()
    out = pathlib.Path(a.out or ROOT / "output" / ("agent-" + a.scenario + "-" + datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")))
    asker = call
    if a.replay:
        asker = Recorded(a.replay)
        rec = json.loads(pathlib.Path(a.replay).read_text())
        if rec["questions_sha256"] != QUESTIONS_SHA or rec["intent_sha256"] != hashlib.sha256(intent.encode()).hexdigest():
            sys.exit("replay: the recording was made with different questions or a different intent")
    try:
        agent = Agent(a.scenario, intent, a.decider, a.threshold, not a.fixtures, out, asker=asker, expected_model=a.expected_model)
        rec = agent.run()
    except RuntimeError as e:
        sys.exit(str(e))
    if a.replay:
        rec["replayed_from"] = a.replay
        (out / "agent-run.json").write_text(json.dumps(rec, indent=2) + "\n")
    if not any(isinstance(c["response"], dict) and c["response"].get("answers") for c in rec["calls"]):
        sys.exit(3)   # the model answered nothing: not an agent result


if __name__ == "__main__":
    main()
