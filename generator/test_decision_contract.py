"""Malformed model decisions must abstain through both original runtime parsers."""
import unittest
import decider_agent as da
import policy_agent as pa
from decision_contract import score


class DecisionContractTests(unittest.TestCase):
    def test_bad_confidence_abstains(self):
        for value in (float("nan"), float("inf"), -0.1, 1.1, "not-a-number", None, True, [], {}):
            with self.subTest(value=value):
                answer = {"choice": "process", "confidence": value}
                self.assertIsNone(da.parse_choice({"answers": {"control": answer}})[0])
                self.assertIsNone(pa.parse({"answers": {"q": answer}}, da.CONTROLS)[0])

    def test_bad_shapes_abstain(self):
        for answers in (None, [], "bad", 4, {"control": []}, {"q": "bad"}):
            self.assertIsNone(da.parse_choice({"answers": answers})[0])
            self.assertIsNone(pa.parse({"answers": answers}, da.CONTROLS)[0])
        for choice in ([], {}, True):
            answer = {"choice": choice, "confidence": 0.9}
            self.assertIsNone(pa.parse({"answers": {"q": answer}}, da.CONTROLS)[0])

    def test_probability_validation(self):
        for value in (float("nan"), "bad", 2, None):
            answer = {"choice": "process", "confidence": 0.9, "probabilities": {"process": value}}
            self.assertIsNone(da.parse_choice({"answers": {"control": answer}})[0])
            self.assertIsNone(pa.parse({"answers": {"q": answer}}, da.CONTROLS)[0])
        answer = {"choice": "allow_everything", "confidence": 0.99, "probabilities": {"process": 0.99}}
        self.assertIsNone(da.parse_choice({"answers": {"control": answer}})[0])

    def test_valid_boundaries_and_alias(self):
        for value in (0, 1, 0.6):
            answer = {"choice": "process", "answer_confidence": value}
            self.assertEqual(da.parse_choice({"answers": {"control": answer}})[:2], ("process", value))
            self.assertEqual(pa.parse({"answers": {"q": answer}}, da.CONTROLS), ("process", value))

    def test_threshold_is_bounded(self):
        for value in (float("nan"), float("inf"), -1, 2, True):
            with self.assertRaises(ValueError):
                score(value)


if __name__ == "__main__":
    unittest.main()
