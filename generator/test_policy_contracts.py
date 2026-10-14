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
        return contracts.evaluate(scenario, intent or (compiler.GEN / f"intent-{scenario}.txt").read_text(), spec, [], out)

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


if __name__ == "__main__":
    unittest.main()
