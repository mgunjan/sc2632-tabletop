"""A permissive/missing policy must fail independent behavior or coverage despite quiet fixtures."""
import json
from pathlib import Path
import tempfile
import unittest
import yaml
import generate as compiler
import policy_contracts as contracts


class PolicyContractTests(unittest.TestCase):
    def evaluate(self, scenario="a", mutate=None, intent=None):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        out = Path(directory.name)
        spec = json.loads((compiler.GEN / f"spec-{scenario}.json").read_text())
        compiler.write_policy_artifacts(spec, out)
        if mutate:
            mutate(out, spec)
        actual_intent = intent if intent is not None else (compiler.GEN / f"intent-{scenario}.txt").read_text()
        return contracts.evaluate(scenario, actual_intent, spec, [], out)

    def test_reference_is_reviewable_and_manual(self):
        for scenario in "abc":
            with self.subTest(scenario=scenario):
                review = self.evaluate(scenario)
                self.assertEqual(review["status"], "REVIEW_REQUIRED")
                self.assertFalse(review["promotion_allowed"])
                self.assertTrue(review["contract_bound"])
                self.assertTrue(all(r["disposition"] is None for r in review["requirements"]))
                if scenario == "a":
                    self.assertTrue(review["independent_behavior"]["passed"])

    def test_permissive_policy_fails_the_negative_expectations(self):
        def permissive(out, spec):
            path = out / "policies/deny-privilege-escalation.yaml"
            policy = yaml.safe_load(path.read_text())
            for validation in policy["spec"]["validations"]:
                validation["expression"] = "true"
            path.write_text(yaml.safe_dump(policy))
        review = self.evaluate(mutate=permissive)
        self.assertEqual(review["independent_behavior"]["status"], "FAIL")
        self.assertEqual(review["status"], "INCOMPLETE_PROPOSAL")
        self.assertFalse(review["promotion_allowed"])

    def test_audit_only_privilege_policy_is_not_enforcing(self):
        # The six checks pass in Audit too; reporting is not blocking.
        def audit_only(out, spec):
            path = out / "policies/deny-privilege-escalation.yaml"
            policy = yaml.safe_load(path.read_text())
            policy["spec"]["validationActions"] = ["Audit"]
            path.write_text(yaml.safe_dump(policy))
        review = self.evaluate(mutate=audit_only)
        self.assertEqual(review["independent_behavior"]["status"], "PASS_BUT_NOT_ENFORCING")
        self.assertEqual(review["status"], "INCOMPLETE_PROPOSAL")

    def test_human_handoffs_are_recorded_in_the_ledger(self):
        directory = tempfile.TemporaryDirectory(); self.addCleanup(directory.cleanup)
        out = Path(directory.name)
        spec = json.loads((compiler.GEN / "spec-a.json").read_text())
        compiler.write_policy_artifacts(spec, out)
        handoffs = [{"kind": "escalation", "about": "egress profile storage", "best_guess": "deny", "confidence": 0.44}]
        review = contracts.evaluate("a", (compiler.GEN / "intent-a.txt").read_text(), spec, [], out, handoffs=handoffs)
        self.assertEqual(review["human_handoff_count"], 1)
        saved = json.loads((out / "readiness.json").read_text())
        self.assertEqual(saved["human_handoffs"][0]["about"], "egress profile storage")
        self.assertFalse(saved["promotion_allowed"])

    def test_missing_policy_is_not_a_green_contract(self):
        review = self.evaluate(mutate=lambda out, spec: (out / "policies/deny-privilege-escalation.yaml").unlink())
        self.assertEqual(review["independent_behavior"]["status"], "REQUIRED_POLICY_MISSING")
        self.assertEqual(review["requirements"][1]["status"], "REQUIRED_POLICY_MISSING")

    def test_new_intent_or_namespace_requires_new_contract(self):
        for review in (self.evaluate(intent="Prevent privilege escalation everywhere."),
                       self.evaluate(mutate=lambda out, spec: spec.update(namespace="other")),
                       self.evaluate(mutate=lambda out, spec: spec["clauses"][0].update(text="A different requirement"))):
            self.assertFalse(review["contract_bound"])
            self.assertEqual(review["status"], "INCOMPLETE_PROPOSAL")
            self.assertFalse(review["promotion_allowed"])

    def test_added_requirement_is_visible_even_when_the_proposal_omits_it(self):
        original = (compiler.GEN / "intent-a.txt").read_text().strip()
        added = "Preserve required monitoring access"
        review = self.evaluate(intent=original + " " + added + ".")
        self.assertEqual(len(review["requirements"]), 5)
        last = review["requirements"][-1]
        self.assertEqual(last["text"].rstrip("."), added)
        self.assertIsNone(last["selected_control"])
        self.assertEqual(last["status"], "UNBOUND_INTENT_REQUIRES_NEW_CONTRACT")
        self.assertTrue(all(r["layer"] == "unreviewed" for r in review["requirements"]))
        self.assertEqual(review["status"], "INCOMPLETE_PROPOSAL")
        self.assertIn(added, contracts.pr_section(review))

    def test_replaced_intent_cannot_inherit_prepared_control_meanings(self):
        review = self.evaluate(intent="Keep monitoring available.")
        self.assertEqual(len(review["requirements"]), 1)
        self.assertEqual(review["requirements"][0]["layer"], "unreviewed")
        self.assertIsNone(review["requirements"][0]["selected_control"])
        self.assertEqual(len(review["unmatched_spec_clauses"]), 4)
        self.assertFalse(review["promotion_allowed"])

    def test_empty_intent_is_incomplete_even_without_ledger_rows(self):
        review = self.evaluate(intent="")
        self.assertEqual(review["requirements"], [])
        self.assertFalse(review["contract_bound"])
        self.assertEqual(review["status"], "INCOMPLETE_PROPOSAL")
        self.assertFalse(review["promotion_allowed"])


if __name__ == "__main__":
    unittest.main()
