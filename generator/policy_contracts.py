"""Independent prepared-intent review ledger and fixed privilege behavior expectations.

This is a review aid, never deployment authority. Fixture observations and model confidence cannot clear it.
"""
import hashlib
import html
import json
import pathlib
import re
import shutil
import subprocess

GEN = pathlib.Path(__file__).resolve().parent
CONTRACT = GEN / "contracts/requirements.json"


def evaluate(scenario, intent, spec, decisions, out, handoffs=None):
    import generate as g
    import decider_agent as da
    import yaml
    contract = json.loads(CONTRACT.read_text())[scenario]
    bound = (hashlib.sha256(intent.encode()).hexdigest() == contract["intent_sha256"]
             and spec["namespace"] == contract["namespace"]
             and [c["id"] for c in spec["clauses"]] == [r["id"] for r in contract["requirements"]]
             and [c["text"].strip().rstrip(".") for c in spec["clauses"]]
                 == [c.strip().rstrip(".") for c in da.split_clauses(intent)])
    clauses = da.split_clauses(intent)
    requirements = contract["requirements"] if bound else [
        {"id": index, "text": text, "controls": [], "layer": "unreviewed",
         "review": "Write and independently review a requirement contract for this actual intent; prepared mappings do not apply."}
        for index, text in enumerate(clauses, 1)
    ]
    ledger = []
    for requirement in requirements:
        clause = next((c for c in spec["clauses"] if c["id"] == requirement["id"]), {})
        text = clauses[requirement["id"] - 1]
        matching_text = clause.get("text", "").strip().rstrip(".") == text.strip().rstrip(".")
        control = clause.get("control") if matching_text else None
        decision = decisions[requirement["id"] - 1] if len(decisions) >= requirement["id"] else {}
        if not bound:
            status = "UNBOUND_INTENT_REQUIRES_NEW_CONTRACT"
        elif decision.get("escalated"):
            status = "MODEL_ABSTAINED"
        elif control not in requirement["controls"]:
            status = "UNEXPECTED_CONTROL_MAPPING"
        elif control in ("process", "not_implementable"):
            status = "HUMAN_DISPOSITION_REQUIRED"
        elif control in g.NO_POLICY:
            status = "OTHER_ENFORCEMENT_LAYER_REQUIRED"
        elif not spec["controls"].get(control, {}).get("enabled") or not (out / "policies" / (g.POLICY_FILE[control] + ".yaml")).exists():
            status = "REQUIRED_POLICY_MISSING"
        else:
            status = "POLICY_GENERATED_REVIEW_REQUIRED"
        ledger.append({**requirement, "text": text, "selected_control": control, "status": status, "disposition": None})

    unmatched_spec_clauses = [c for c in spec["clauses"] if not any(
        c["id"] == i and c["text"].strip().rstrip(".") == text.strip().rstrip(".")
        for i, text in enumerate(clauses, 1))]

    tests = out / "tests"
    tests.mkdir(parents=True, exist_ok=True)
    (tests / "README.md").write_text(
        "# Independent behavior checks\n\nThe fixed privilege checks cover six Pod CREATE behaviors only. "
        "They do not test networking, RBAC, debug subresources, existing workloads or exception cleanup. "
        "Run `kyverno test tests/` when kyverno-test.yaml is present. A passing check does not authorize deployment.\n")
    behavior = {"status": "NOT_COVERED", "passed": False, "scope": "six fixed Pod CREATE privilege expectations"}
    required_privilege = bound and any("deny_privilege_escalation" in r["controls"] for r in contract["requirements"])
    privilege = out / "policies/deny-privilege-escalation.yaml"
    if privilege.exists():
        shutil.copyfile(GEN / "contracts/privilege-resources.yaml", tests / "resources.yaml")
        suite = yaml.safe_load((GEN / "contracts/privilege-test.yaml").read_text())
        suite["policies"] = ["../policies/deny-privilege-escalation.yaml"]
        suite["resources"] = ["resources.yaml"]
        # Expectations remain presenter-authored; the model cannot edit them.
        (tests / "kyverno-test.yaml").write_text(yaml.safe_dump(suite, sort_keys=False))
        try:
            run = subprocess.run(["kyverno", "test", str(tests)], capture_output=True, text=True, timeout=30)
            log = re.sub(r"\x1b\[[0-9;]*m", "", run.stdout + run.stderr)
            (tests / "result.txt").write_text(log)
            passed = run.returncode == 0 and "6 tests passed and 0 tests failed" in log
            actions = (yaml.safe_load(privilege.read_text()) or {}).get("spec", {}).get("validationActions")
            if passed and actions != ["Deny"]:
                # The six checks pass in Audit or Warn too; a policy that only reports does not block anything.
                behavior.update(status="PASS_BUT_NOT_ENFORCING", passed=False, validation_actions=actions)
            else:
                behavior.update(status="PASS" if passed else "FAIL", passed=passed)
        except (OSError, subprocess.TimeoutExpired):
            behavior.update(status="TOOL_UNAVAILABLE_OR_TIMEOUT", passed=False)
    elif required_privilege:
        behavior.update(status="REQUIRED_POLICY_MISSING", passed=False)

    problems = [r for r in ledger if r["status"] in (
        "UNBOUND_INTENT_REQUIRES_NEW_CONTRACT", "MODEL_ABSTAINED", "UNEXPECTED_CONTROL_MAPPING", "REQUIRED_POLICY_MISSING")]
    blocked = not bound or bool(problems) or behavior["status"] in ("FAIL", "PASS_BUT_NOT_ENFORCING", "REQUIRED_POLICY_MISSING", "TOOL_UNAVAILABLE_OR_TIMEOUT")
    review = {"status": "INCOMPLETE_PROPOSAL" if blocked else "REVIEW_REQUIRED", "promotion_allowed": False,
              "contract_bound": bound, "requirements_contract_sha256": hashlib.sha256(CONTRACT.read_bytes()).hexdigest(),
              "requirements": ledger, "unmatched_spec_clauses": unmatched_spec_clauses, "independent_behavior": behavior,
              # Decisions the model was not confident enough to make (dependency allowances kept open, blocked
              # workloads, exception requests). They do not change the status, but they must be visible here.
              "human_handoffs": list(handoffs or []), "human_handoff_count": len(handoffs or []),
              "reason": "A human must resolve each requirement, dependency allowance and exception request; no deployment authority is granted."}
    (out / "readiness.json").write_text(json.dumps(review, indent=2) + "\n")
    return review


def pr_section(review):
    def cell(value):
        return html.escape(str(value)).replace("\\", "\\\\").replace("|", "\\|").replace("\r", " ").replace("\n", " ")

    lines = ["", "## Independent review status", "", f"**{review['status']} — promotion is not authorized.**", "",
             "| Requirement | Actual intent | Enforcement layer | Review status |", "|---|---|---|---|"]
    lines += [f"| {r['id']} | {cell(r.get('text', 'Not recorded'))} | {r['layer']} | {r['status']} |" for r in review["requirements"]]
    if not review["contract_bound"]:
        lines += ["", "The actual intent is unbound. Every input requirement needs a new independently reviewed contract; prepared enforcement mappings do not apply."]
    if review.get("unmatched_spec_clauses"):
        lines += ["", "### Proposal clauses that do not match the actual input", "",
                  "| Clause | Proposal text | Proposed control |", "|---|---|---|"]
        lines += [f"| {cell(c['id'])} | {cell(c['text'])} | {cell(c.get('control'))} |" for c in review["unmatched_spec_clauses"]]
    lines += ["", f"Fixed privilege behavior checks: **{review['independent_behavior']['status']}**.", "",
              "See readiness.json for outstanding dispositions and tests/ for the independent expectations. "
              "Passing current-workload simulation does not establish complete containment.", ""]
    return "\n".join(lines)
