#!/usr/bin/env python3
"""
Intent -> GuardrailSpec (model) -> Kyverno policies (templates) -> simulated admission
(kyverno apply) -> reviewable PR body (markdown).

The model's only job is to fill generator/schema.json. Everything after that is
deterministic. The test gate, not the model, is the trust anchor.

Usage:
  # with a local model via Ollama (structured output, temperature 0, fixed seed)
  python3 generator/generate.py --scenario b --model qwen3-coder:30b

  # without a model (CI, rehearsal, or reproducing a frozen run)
  python3 generator/generate.py --scenario a --from-spec generator/spec-a.json

Scenarios: a (compromised library), b (prompt-injected sidecar agent), c (rogue ops agent).
Outputs land in output/<run-id>/ : spec.json, policies/, exceptions/, rollout/,
admission-report.json, PR.md, provenance.json.
"""
import argparse, datetime, hashlib, json, pathlib, subprocess, sys, urllib.request
import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
GEN = ROOT / "generator"

SCENARIOS = {
    "a": {"title": "Compromised library in payments-api", "dir": ROOT / "scenarios/a-compromised-library",
          "fixtures": "fixtures/payments-workloads.yaml", "userinfo": None, "kind": "Pod"},
    "b": {"title": "Prompt-injected support-assistant sidecar", "dir": ROOT / "scenarios/b-sidecar-agent",
          "fixtures": "fixtures/payments-workloads.yaml", "userinfo": None, "kind": "Pod"},
    "c": {"title": "Rogue ops agent after a poisoned Slack message", "dir": ROOT / "scenarios/c-rogue-ops-agent",
          "fixtures": "fixtures/deployment-patches.yaml", "userinfo": "userinfo/ops-agent.yaml", "kind": "Deployment"},
}

POLICY_FILE = {
    "egress_profile": "restrict-egress-profile",
    "deny_privilege_escalation": "deny-privilege-escalation",
    "restrict_registry": "restrict-image-registry",
    "deny_sa_token_for_agent_sidecars": "deny-sa-token-for-agent-sidecars",
    "deny_agent_mutation_outside_namespace": "deny-agent-mutation-outside-namespace",
    "require_ticket_on_agent_changes": "require-ticket-on-agent-changes",
    "audit_replica_surge": "audit-replica-surge",
}

# ----------------------------------------------------------------------------- model

SYSTEM_PROMPT = """You are a policy compiler front-end for Kubernetes admission control.
You read a security intent written by a human and produce ONLY a JSON object that
conforms to the provided schema. You do not write YAML. You do not invent controls
the schema does not offer. Rules:
- Split the intent into numbered clauses. Map each clause to exactly one control,
  or to "not_implementable" with a note saying why (reads are invisible to admission;
  application-layer behaviour such as tool allow-lists is invisible to admission).
- A control you enable that is NOT asked for by any clause must have in_intent=false.
- restrict_api_access cannot be fully implemented by admission policy alone
  (it needs RBAC changes); set enabled=false, in_intent=true, and explain in note.
- Propose an exception for every fixture workload that the enabled controls would
  block, with a named owner and a ttl_hours. Never propose an exception for a
  workload that would not be blocked.
- rollout is always ["Audit","Warn","Deny"] unless the intent forbids staging."""

def fixture_inventory(path: pathlib.Path) -> str:
    docs = [d for d in yaml.safe_load_all(path.read_text()) if d]
    lines = []
    for d in docs:
        m = d["metadata"]
        lbl, ann = m.get("labels", {}), m.get("annotations", {})
        if d["kind"] == "Pod":
            s = d["spec"]
            imgs = ", ".join(c["image"] for c in s["containers"])
            lines.append(f"- Pod {m['name']} (ns={m['namespace']}, labels={lbl}, automountServiceAccountToken={s.get('automountServiceAccountToken', 'unset')}, images={imgs})")
        else:
            lines.append(f"- {d['kind']} {m['name']} (ns={m['namespace']}, replicas={d['spec'].get('replicas')}, annotations={ann})")
    return "\n".join(lines)

def call_ollama(intent: str, fixtures: pathlib.Path, model: str, host: str, seed: int, temperature: float):
    schema = json.loads((GEN / "schema.json").read_text())
    user = f"INTENT:\n{intent.strip()}\n\nWORKLOADS IN SCOPE:\n{fixture_inventory(fixtures)}\n\nProduce the GuardrailSpec JSON."
    body = {"model": model,
            "messages": [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user}],
            "format": schema, "stream": False,
            "options": {"temperature": temperature, "seed": seed, "num_ctx": 8192}}
    req = urllib.request.Request(f"{host}/api/chat", data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=900) as r:
        resp = json.load(r)
    spec = json.loads(resp["message"]["content"])
    meta = {"model": resp.get("model", model), "seed": seed, "temperature": temperature,
            "prompt_sha256": hashlib.sha256((SYSTEM_PROMPT + user).encode()).hexdigest(),
            "eval_count": resp.get("eval_count"), "total_duration_ns": resp.get("total_duration")}
    return spec, meta

# ---------------------------------------------------------------------- validation
# The model's output is untrusted input to a policy compiler. Ollama's structured output is a
# decoding constraint, not a guarantee — and some fields are pasted into CEL expressions, where
# a stray quote would rewrite a policy's logic. So: validate against the schema, every time,
# before any template runs. A spec supplied with --from-spec is validated the same way.

class SpecInvalid(Exception):
    pass

def validate_spec(spec):
    try:
        import jsonschema
    except ImportError:
        raise SpecInvalid("jsonschema is required to validate the spec (pip install jsonschema)")
    schema = json.loads((GEN / "schema.json").read_text())
    errors = sorted(jsonschema.Draft202012Validator(schema).iter_errors(spec), key=lambda e: list(e.path))
    if errors:
        lines = [f"  {'/'.join(map(str, e.path)) or '(root)'}: {e.message}" for e in errors[:10]]
        raise SpecInvalid("spec does not conform to generator/schema.json — refusing to generate policies:\n" + "\n".join(lines))
    # Cross-field checks the schema can't express.
    enabled = {k for k, v in spec["controls"].items() if v.get("enabled")}
    for ex in spec["exceptions"]:
        if ex["control"] not in enabled:
            raise SpecInvalid(f"exception for {ex['workload']} targets control '{ex['control']}', which is not enabled")
    return spec

# ------------------------------------------------------------------------- templates
# Policies are dicts dumped with PyYAML: deterministic, no string templating.

def _dump(obj) -> str:
    return yaml.safe_dump(obj, sort_keys=False, width=200, allow_unicode=True)

def _meta(name, clause, stage, title, category, severity, note=""):
    ann = {"guardrails.trustfall.example/intent-clause": str(clause), "guardrails.trustfall.example/rollout-stage": stage,
           "policies.kyverno.io/title": title, "policies.kyverno.io/category": category, "policies.kyverno.io/severity": severity}
    if note:
        ann["guardrails.trustfall.example/generator-note"] = note
    return {"name": name, "annotations": ann}

IMG_CHANGED = "request.operation == 'CREATE' || oldObject == null || object.spec.containers.map(c, c.image) != oldObject.spec.containers.map(c, c.image)"

def _pods(ns, extra_conditions=None, ops=("CREATE", "UPDATE")):
    # Checks on immutable Pod-spec fields pass ops=("CREATE",): evaluating them on UPDATE would
    # refuse label changes (including quarantine relabels) on Pods that predate the policy.
    return {"matchConstraints": {"resourceRules": [{"apiGroups": [""], "apiVersions": ["v1"], "operations": list(ops), "resources": ["pods"]}]},
            "matchConditions": [{"name": f"{ns}-namespace-only", "expression": f"object.metadata.namespace == '{ns}'"}] + (extra_conditions or [])}

def _workloads(conditions=None, subresources=False):
    # `kubectl scale` writes the deployments/scale SUBRESOURCE, which a rule on `deployments` never
    # sees. Found live: the agent's 3 -> 12 scale-up sailed through when done with `kubectl scale`.
    res = ["deployments", "statefulsets", "daemonsets"] + (["deployments/scale", "statefulsets/scale"] if subresources else [])
    return {"matchConstraints": {"resourceRules": [{"apiGroups": ["apps"], "apiVersions": ["v1"], "operations": ["CREATE", "UPDATE"], "resources": res}]},
            **({"matchConditions": conditions} if conditions else {})}

def _vp(meta, action, match, body):
    return _dump({"apiVersion": "policies.kyverno.io/v1", "kind": "ValidatingPolicy", "metadata": meta,
                  "spec": {"validationActions": [action], **match, **body}})

def t_egress(ns, c, action, clause):
    profiles = c["approved_profiles"]
    return _vp(_meta(POLICY_FILE["egress_profile"], clause, action.lower(), f"Restrict egress profile in {ns}", "Network", "high"), action, _pods(ns), {
        "variables": [{"name": "profile", "expression": "object.metadata.?labels[?'trustfall.example/egress-profile'].orValue('missing')"},
                      {"name": "approved", "expression": "[" + ", ".join(f"'{p}'" for p in profiles) + "]"}],
        # 'quarantined' is always admissible: strictly more restrictive, set by capture-evidence.sh.
        "validations": [{"expression": "variables.profile in variables.approved || variables.profile == 'quarantined'",
                         "messageExpression": f"\"Pod \" + object.metadata.name + \" in {ns} must carry label trustfall.example/egress-profile with one of {', '.join(profiles)}. Found: '\" + variables.profile + \"'. Need another profile? Open a PolicyException with an owner and a TTL.\"",
                         "message": f"Pod in {ns} must carry an approved trustfall.example/egress-profile label."}]})

def t_privesc(ns, c, action, clause):
    return _vp(_meta(POLICY_FILE["deny_privilege_escalation"], clause, action.lower(), f"Deny privilege escalation in {ns}", "Pod Security", "high"), action, _pods(ns, ops=("CREATE",)), {
        "variables": [{"name": "allContainers", "expression": "object.spec.containers + object.spec.?initContainers.orValue([])"}],
        "validations": [{"expression": "variables.allContainers.all(c, c.?securityContext.?privileged.orValue(false) == false)", "message": "Privileged containers are not allowed."},
                        {"expression": "variables.allContainers.all(c, c.?securityContext.?allowPrivilegeEscalation.orValue(true) == false)", "message": "Every container must set securityContext.allowPrivilegeEscalation: false."}]})

def t_registry(ns, c, action, clause):
    note = "" if c["in_intent"] else "Added beyond stated intent. Reviewer must accept or remove."
    return _vp(_meta(POLICY_FILE["restrict_registry"], clause, action.lower(), f"Restrict image registry in {ns}", "Supply Chain", "medium", note), action,
               _pods(ns, [{"name": "create-or-image-changed", "expression": IMG_CHANGED}]), {
        "validations": [{"expression": f"object.spec.containers.all(c, c.image.startsWith('{c['registry']}/'))", "message": f"Images in {ns} must come from {c['registry']}."}]})

def t_sa_token(ns, c, action, clause):
    lbl = c.get("sidecar_label", "trustfall.example/agent-sidecar")
    return _vp(_meta(POLICY_FILE["deny_sa_token_for_agent_sidecars"], clause, action.lower(), "Agent sidecars may not mount the ServiceAccount token", "Identity", "high"), action,
               _pods(ns, [{"name": "has-agent-sidecar", "expression": f"object.metadata.?labels[?'{lbl}'].orValue('false') == 'true'"}], ops=("CREATE",)), {
        "validations": [{"expression": "object.spec.?automountServiceAccountToken.orValue(true) == false",
                         "messageExpression": "\"Pod \" + object.metadata.name + \" runs an agent sidecar and must set spec.automountServiceAccountToken: false.\"",
                         "message": "Pods with an agent sidecar must set automountServiceAccountToken: false."}]})

def t_agent_mutation(ns, c, action, clause):
    sa, home = c["agent_serviceaccount"], c["home_namespace"]
    return _vp(_meta(POLICY_FILE["deny_agent_mutation_outside_namespace"], clause, action.lower(), f"Agent may not mutate workloads outside {home}", "Agent Governance", "high",
                     "Authorization expressed as admission. Backstop for an RBAC fix, not a replacement."), action,
               _workloads([{"name": "requester-is-agent", "expression": f"request.?userInfo.?username.orValue('') == '{sa}'"}], subresources=True), {
        "validations": [{"expression": f"object.metadata.namespace == '{home}'",
                         "messageExpression": f"\"{sa.split(':')[-1]} may not modify \" + object.kind + \" \" + object.metadata.namespace + \"/\" + object.metadata.name + \": outside the {home} namespace.\"",
                         "message": f"The agent may only mutate workloads in {home}."}]})

def t_ticket(ns, c, action, clause):
    sa, key = c["agent_serviceaccount"], c.get("annotation", "trustfall.example/ticket")
    return _vp(_meta(POLICY_FILE["require_ticket_on_agent_changes"], clause, action.lower(), "Agent changes must reference a ticket", "Agent Governance", "medium"), action,
               _workloads([{"name": "requester-is-agent", "expression": f"request.?userInfo.?username.orValue('') == '{sa}'"}]), {
        "validations": [{"expression": f"object.metadata.?annotations[?'{key}'].orValue('') != ''",
                         "messageExpression": f"\"agent changed \" + object.metadata.namespace + \"/\" + object.metadata.name + \" without a {key} annotation.\"",
                         "message": f"Changes made by the agent must carry a {key} annotation."}]})

def t_replica_surge(ns, c, action, clause):
    note = "" if c["in_intent"] else "Added beyond stated intent. Reviewer must accept or remove."
    n = c["threshold"]
    return _vp(_meta(POLICY_FILE["audit_replica_surge"], clause, action.lower(), f"Audit replica counts above {n}", "Capacity", "low", note), action,
               {"matchConstraints": {"resourceRules": [{"apiGroups": ["apps"], "apiVersions": ["v1"], "operations": ["CREATE", "UPDATE"], "resources": ["deployments", "deployments/scale"]}]}}, {
        "validations": [{"expression": f"object.spec.?replicas.orValue(1) <= {n}",
                         "messageExpression": f"object.metadata.namespace + \"/\" + object.metadata.name + \" has \" + string(object.spec.replicas) + \" replicas (audit threshold {n}).\"",
                         "message": f"Deployment replica count exceeds the audit threshold of {n}."}]})

TEMPLATES = {"egress_profile": t_egress, "deny_privilege_escalation": t_privesc, "restrict_registry": t_registry,
             "deny_sa_token_for_agent_sidecars": t_sa_token, "deny_agent_mutation_outside_namespace": t_agent_mutation,
             "require_ticket_on_agent_changes": t_ticket, "audit_replica_surge": t_replica_surge}

# A clause the reviewer should know about but that never becomes a policy.
NO_POLICY = {"restrict_api_access", "not_implementable"}

def render_policies(spec, action):
    ns, ctrls = spec["namespace"], spec["controls"]
    clause_of = {cl["control"]: str(cl["id"]) for cl in spec["clauses"]}
    out = {}
    for key, c in ctrls.items():
        if key in NO_POLICY or not c.get("enabled"):
            continue
        # A control the intent didn't ask for never goes past Audit in the generated set.
        a = "Audit" if not c.get("in_intent") else action
        # Intent said "starts at Warn" for ticket annotations; honour the stage floor.
        if key == "require_ticket_on_agent_changes" and action == "Deny":
            a = "Warn"
        out[POLICY_FILE[key] + ".yaml"] = TEMPLATES[key](ns, c, a, clause_of.get(key, "none"))
    return out

def exception_yaml(ns, ex, kind):
    return _dump({"apiVersion": "policies.kyverno.io/v1", "kind": "PolicyException",
                  "metadata": {"name": f"{ex['workload']}-{ex['control'].replace('_', '-')}", "namespace": ns,
                               "labels": {"cleanup.kyverno.io/ttl": f"{ex['ttl_hours']}h"},
                               "annotations": {"trustfall.example/owner": ex["owner"], "trustfall.example/reason": ex["reason"]}},
                  "spec": {"policyRefs": [{"name": POLICY_FILE[ex["control"]], "kind": "ValidatingPolicy"}],
                           "matchConditions": [{"name": f"{ex['workload']}-only",
                                                "expression": f"object.metadata.namespace == '{ns}' && object.metadata.name.startsWith('{ex['workload']}')"}]}})

# --------------------------------------------------------------------- simulation

def write_policy_artifacts(spec, out):
    """Write the deterministic policy/stage portion shared by compiler and agent."""
    for stage in [None, *spec["rollout"]]:
        directory = out / "policies" if stage is None else out / "rollout" / stage.lower()
        directory.mkdir(parents=True, exist_ok=True)
        for old in directory.glob("*.yaml"):
            old.unlink()
        for name, text in render_policies(spec, stage or spec["rollout"][-1]).items():
            (directory / name).write_text(text)
    import control_library
    control_library.review(spec, out)


def simulate(policy_dir, fixtures, exception_dir, userinfo):
    cmd = ["kyverno", "apply", str(policy_dir), "--resource", str(fixtures), "--policy-report", "--output-format", "json"]
    if userinfo:
        cmd += ["--userinfo", str(userinfo)]
    if exception_dir:
        for f in sorted(exception_dir.glob("*.yaml")):
            cmd += ["--exception", str(f)]
    p = subprocess.run(cmd, capture_output=True, text=True)
    start = p.stdout.find("{")
    if start < 0:
        sys.exit(f"kyverno apply produced no report (exit {p.returncode}):\n{p.stderr}")
    return json.loads(p.stdout[start:])

def outcomes(report, action_of, with_exceptions=False):
    # "skip" means the rule did not apply to that workload. Only in the with-exceptions run can
    # it mean an exception matched; without exceptions, calling it one misleads the reader.
    rows = []
    for r in report["results"]:
        res = r["resources"][0]
        act = action_of.get(r["policy"], "Deny")
        raw = r["result"]
        skip = "SKIPPED (exception)" if with_exceptions else "N/A (rule does not apply)"
        label = ("PASS" if raw == "pass" else skip if raw == "skip"
                 else "WOULD BLOCK" if act == "Deny" else "WARN (admitted with warning)" if act == "Warn"
                 else "AUDIT (admitted, reported)")
        rows.append({"workload": f"{res['namespace']}/{res['name']}", "policy": r["policy"], "action": act, "result": label,
                     "message": "" if raw in ("pass", "skip") else r.get("message", "")})
    return sorted(rows, key=lambda x: (x["workload"], x["policy"]))

# ---------------------------------------------------------------------- PR body

def pr_body(sc, spec, rows, rows_ex, prov, intent):
    ns = spec["namespace"]
    L = [f"# Guardrails for `{ns}` — {sc['title']}", "",
         "> Generated by `generator/generate.py`. The model filled a schema; templates wrote the YAML;",
         "> `kyverno apply` produced the admission results below. **Review the clause mapping first.**", "",
         "## Intent", "", f"> {intent.strip()}", "",
         "## Clause → control mapping", "", "| # | Clause | Control | Status |", "|---|---|---|---|"]
    for cl in spec["clauses"]:
        ctrl = cl["control"]
        c = spec["controls"].get(ctrl, {})
        if ctrl == "not_implementable":
            status = f"⚠️ Not a policy — {cl.get('note', '')}"
        elif not c.get("enabled"):
            status = f"❌ **NOT IMPLEMENTED** — {cl.get('note') or c.get('note', '')}"
        else:
            status = "✅ policy generated" + (f" — {cl['note']}" if cl.get("note") else "")
        L.append(f"| {cl['id']} | {cl['text']} | `{ctrl}` | {status} |")
    extras = [k for k, v in spec["controls"].items() if v.get("enabled") and not v.get("in_intent")]
    if extras:
        L += ["", "**⚠️ Controls added beyond the intent (Audit only; reviewer must accept or remove):** " + ", ".join(f"`{e}`" for e in extras)]
    L += ["", "## Policies in this PR", ""]
    for k, v in spec["controls"].items():
        if v.get("enabled") and k not in NO_POLICY:
            L.append(f"- `{POLICY_FILE[k]}` — in intent: {'yes' if v.get('in_intent') else '**no**'}")
    who = " (evaluated as the agent's ServiceAccount)" if sc["userinfo"] else ""
    L += ["", f"## Simulated admission{who}, no exceptions", "", "| Workload | Policy | Action | Result |", "|---|---|---|---|"]
    for r in rows:
        L.append(f"| `{r['workload']}` | `{r['policy']}` | {r['action']} | **{r['result']}** |")
    blocked = sorted({r["workload"] for r in rows if r["result"].startswith("WOULD")})
    L += ["", (f"**{len(blocked)} would be blocked at next admission:** " + ", ".join(f"`{b}`" for b in blocked)) if blocked else "**Nothing would be blocked.**"]
    if spec["exceptions"]:
        L += ["", "## Exception requests (time-boxed)", "", "| Workload | Control | Owner | TTL | Reason |", "|---|---|---|---|---|"]
        for ex in spec["exceptions"]:
            L.append(f"| `{ex['workload']}` | `{ex['control']}` | {ex['owner']} | **{ex['ttl_hours']}h** | {ex['reason']} |")
        L += ["", "### Simulated admission with exceptions applied", "", "| Workload | Policy | Result |", "|---|---|---|"]
        for r in rows_ex:
            if r["result"] != "PASS":
                L.append(f"| `{r['workload']}` | `{r['policy']}` | **{r['result']}** |")
    L += ["", "## Rollout plan", "", "| Stage | validationActions | Effect |", "|---|---|---|"]
    effect = {"Audit": "Admitted; violation recorded in PolicyReport", "Warn": "Admitted; warning returned to the client", "Deny": "Rejected at admission"}
    for i, st in enumerate(spec["rollout"], 1):
        L.append(f"| {i} | `{st}` | {effect[st]} |")
    L += ["", "Promotion between stages is a human decision. Files for each stage are in `rollout/`.", "",
          "## Reviewer checklist", "",
          "- [ ] Every intent clause is either implemented or explicitly marked not implemented",
          "- [ ] No control was added beyond the intent without a reason to keep it",
          "- [ ] Every WOULD BLOCK on a legitimate workload has an exception with an owner and a TTL",
          "- [ ] The TTL is short enough for the incident and someone is awake when it expires",
          "- [ ] The rollout stage matches the incident: is Audit acceptable during an active compromise?",
          "", "## Provenance", "", "```json", json.dumps(prov, indent=2), "```"]
    return "\n".join(L) + "\n"

# -------------------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", choices=SCENARIOS, default="a")
    ap.add_argument("--intent"); ap.add_argument("--intent-file")
    ap.add_argument("--from-spec", help="skip the model; use this GuardrailSpec JSON")
    ap.add_argument("--spec-meta", help="provenance JSON written by the agent that produced --from-spec (e.g. decider_agent.py)")
    ap.add_argument("--model", default="qwen3-coder:30b"); ap.add_argument("--ollama", default="http://localhost:11434")
    ap.add_argument("--seed", type=int, default=0); ap.add_argument("--temperature", type=float, default=0.0)
    ap.add_argument("--out", default=str(ROOT / "output"))
    ap.add_argument("--no-classify", action="store_true", help="skip the independent Laya check")
    a = ap.parse_args()

    sc = SCENARIOS[a.scenario]
    fixtures = sc["dir"] / sc["fixtures"]
    userinfo = (sc["dir"] / sc["userinfo"]) if sc["userinfo"] else None
    intent = a.intent or pathlib.Path(a.intent_file or GEN / f"intent-{a.scenario}.txt").read_text()

    try:
        if a.from_spec:
            spec = json.loads(pathlib.Path(a.from_spec).read_text())
            meta = {"model": "none (spec supplied)", "spec_source": a.from_spec}
            if a.spec_meta:
                m = json.loads(pathlib.Path(a.spec_meta).read_text())
                meta = {**m, "spec_source": a.from_spec}
        else:
            spec, meta = call_ollama(intent, fixtures, a.model, a.ollama, a.seed, a.temperature)
        validate_spec(spec)
    except json.JSONDecodeError as e:
        sys.exit(f"model output is not JSON — refusing to generate policies: {e}")
    except SpecInvalid as e:
        sys.exit(str(e))

    run_id = f"{a.scenario}-" + datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = pathlib.Path(a.out) / run_id
    (out / "policies").mkdir(parents=True); (out / "exceptions").mkdir(); (out / "rollout").mkdir()
    (out / "spec.json").write_text(json.dumps(spec, indent=2) + "\n")

    policies = render_policies(spec, spec["rollout"][-1])
    write_policy_artifacts(spec, out)
    for ex in spec["exceptions"]:
        (out / "exceptions" / f"{ex['workload']}-{ex['control']}.yaml").write_text(exception_yaml(spec["namespace"], ex, sc["kind"]))

    action_of = {name[:-5]: yaml.safe_load(text)["spec"]["validationActions"][0] for name, text in policies.items()}
    rows = outcomes(simulate(out / "policies", fixtures, None, userinfo), action_of)
    rows_ex = outcomes(simulate(out / "policies", fixtures, out / "exceptions", userinfo), action_of, True) if spec["exceptions"] else rows
    (out / "admission-report.json").write_text(json.dumps({"without_exceptions": rows, "with_exceptions": rows_ex}, indent=2) + "\n")

    kv = subprocess.run(["kyverno", "version"], capture_output=True, text=True).stdout.strip().splitlines()[0]
    prov = {**meta, "scenario": a.scenario, "run_id": run_id, "kyverno": kv,
            "intent_sha256": hashlib.sha256(intent.encode()).hexdigest(),
            "spec_sha256": hashlib.sha256(json.dumps(spec, sort_keys=True).encode()).hexdigest(),
            "fixtures_sha256": hashlib.sha256(fixtures.read_bytes()).hexdigest()}
    (out / "provenance.json").write_text(json.dumps(prov, indent=2) + "\n")
    body = pr_body(sc, spec, rows, rows_ex, prov, intent)
    import control_library
    body += control_library.pr_section(json.loads((out/'control-review.json').read_text()))
    if not a.no_classify:
        # Independent second opinion. Runs AFTER the spec exists; the generator never sees it.
        sys.path.insert(0, str(GEN))
        import classify
        cls = classify.classify(a.scenario, intent, spec)
        (out / "classification.json").write_text(json.dumps(cls, indent=2) + "\n")
        body = body.replace("## Rollout plan", classify.pr_section(cls) + "\n## Rollout plan", 1)
        prov["classifier"] = {"model": classify.MODEL_ID, "loaded": cls["engine"]["loaded"], "error": cls["engine"]["error"]}
        (out / "provenance.json").write_text(json.dumps(prov, indent=2) + "\n")
    (out / "PR.md").write_text(body)
    print(f"wrote {out}")
    print(f"  blocked without exceptions: {sorted({r['workload'] for r in rows if r['result'].startswith('WOULD')})}")

if __name__ == "__main__":
    main()
