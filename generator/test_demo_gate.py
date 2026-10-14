"""Synthetic eligibility fixtures test refusal paths; no model result is produced."""
import copy
import datetime as dt
import hashlib
import json
import pathlib
import tempfile
import unittest
from unittest.mock import patch
import contextlib
import io
import os
import yaml
import decider_agent as da
import decider_eval as evaluation
import demo_gate as gate
import policy_agent as pa


class DemoGateTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.folder = pathlib.Path(self.directory.name)
        self.path = self.folder / "synthetic.summary.json"
        self.model = "unit-test-identity-contract-only"
        self.now = dt.datetime.now(dt.timezone.utc)
        config = yaml.safe_load((gate.GEN / "decider-eval.yaml").read_text())
        self.rows = []
        for item in evaluation.load_items(config):
            choice = item["control"] or "process"
            self.rows.append({**{k: item[k] for k in ("set", "id", "text", "control")},
                              "repeat": item.get("repeat"), "ok": item.get("ok", []),
                              "must_be_confident": item.get("must_be_confident", False),
                              "choice": choice, "confidence": 0.9, "served_model": self.model,
                              "verdict": evaluation.judge(item, choice, 0.9, config["threshold"])})
        self.runs = [{"finished": True, "privilege_policy": True, "independent_privilege_pass": True,
                      "served_model": [self.model], "decisions": [["test", "process", 0.9]]} for _ in range(config["repeats"])]
        self.replay = {"scenario": "a", "intent_sha256": gate.sha(gate.GEN / "intent-a.txt"),
                       "questions_sha256": pa.QUESTIONS_SHA, "threshold": 0.6,
                       "model": [self.model], "tested_against": "scenario fixtures", "calls": []}
        self.summary = {"demo_live_allowed": True, "served_model": [self.model], "gates": evaluation.gates(self.rows, 0.6),
                        "config_sha256": gate.sha(gate.GEN / "decider-eval.yaml"), "threshold": 0.6,
                        "runtime_fingerprints": gate.fingerprints(), "host": gate.host(),
                        "decider_url": "http://127.0.0.1:8000", "recorded_at": self.now.isoformat()}
        self.save()

    def save(self):
        files = {"decisions": "synthetic.jsonl", "agent_runs": "synthetic.agent-runs.json", "demo_replay": "synthetic.demo-replay.json"}
        (self.folder / files["decisions"]).write_text("".join(json.dumps(r) + "\n" for r in self.rows))
        (self.folder / files["agent_runs"]).write_text(json.dumps(self.runs))
        (self.folder / files["demo_replay"]).write_text(json.dumps(self.replay))
        self.summary["evidence"] = {kind: {"file": name, "sha256": gate.sha(self.folder / name)} for kind, name in files.items()}
        self.path.write_text(json.dumps(self.summary))

    def result(self, **kwargs):
        return gate.check(self.path, now=self.now, **kwargs)

    def test_bound_evidence_and_live_identity(self):
        self.assertTrue(self.result(offline=True)["allowed"])
        probe = lambda *a, **k: {"model": self.model, "answers": {"control": {"choice": "egress_profile", "confidence": 0.9}}}
        self.assertTrue(self.result(probe=probe)["allowed"])
        self.assertFalse(self.result(probe=lambda *a, **k: {"model": "another-model"})["allowed"])

    def test_summary_health_or_pass_flag_is_insufficient(self):
        self.summary["gates"]["G1_demo"]["pass"] = False
        self.save()
        self.assertFalse(self.result(offline=True)["allowed"])

    def test_changed_code_or_host_or_threshold(self):
        original = copy.deepcopy(self.summary)
        for key, value in (("runtime_fingerprints", {}), ("host", {}), ("threshold", 0.7)):
            self.summary = {**copy.deepcopy(original), key: value}
            self.save()
            self.assertFalse(self.result(offline=True)["allowed"])

    def test_stale_evidence_and_fake_model(self):
        self.summary["recorded_at"] = (self.now - dt.timedelta(days=8)).isoformat()
        self.save()
        self.assertFalse(self.result(offline=True)["allowed"])
        self.summary["recorded_at"] = self.now.isoformat()
        self.summary["served_model"] = ["FAKE-scripted-not-a-model"]
        self.save()
        self.assertFalse(self.result(offline=True)["allowed"])

    def test_missing_or_tampered_evidence(self):
        (self.folder / "synthetic.jsonl").write_text("{}\n")
        self.assertFalse(self.result(offline=True)["allowed"])
        self.save()
        self.summary["evidence"]["decisions"]["file"] = "../outside.jsonl"
        self.path.write_text(json.dumps(self.summary))
        self.assertFalse(self.result(offline=True)["allowed"])

    def test_recomputed_cases_and_gates(self):
        self.rows[0]["text"] = "changed"
        self.save()
        self.assertFalse(self.result(offline=True)["allowed"])
        self.rows[0]["text"] = evaluation.load_items(yaml.safe_load((gate.GEN / "decider-eval.yaml").read_text()))[0]["text"]
        self.rows[0]["choice"] = "process"
        self.rows[0]["verdict"] = "CONFIDENT_MISS"
        self.save()
        self.assertFalse(self.result(offline=True)["allowed"])

    def test_incomplete_agent_or_failed_independent_test(self):
        self.runs[0]["independent_privilege_pass"] = False
        self.save()
        self.assertFalse(self.result(offline=True)["allowed"])

    def test_replay_and_launcher_recording_are_bound(self):
        self.replay["threshold"] = 0.7
        self.save()
        self.assertFalse(self.result(offline=True)["allowed"])
        self.replay["threshold"] = 0.6
        self.save()
        other = self.folder / "other.json"
        other.write_text("{}")
        self.assertFalse(self.result(offline=True, recording=other)["allowed"])

    def test_newer_failure_never_selects_an_older_pass(self):
        records = self.folder / "recordings"
        records.mkdir()
        older = records / "decider-eval-old.summary.json"
        newer = records / "decider-eval-new.summary.json"
        older.write_text("{}"); newer.write_text("{}")
        os.utime(older, (1, 1)); os.utime(newer, (2, 2))
        def eligibility(path, **kwargs):
            return {"allowed": path == older, "reason": "newest evaluation failed"}
        with (patch.object(gate, "GEN", self.folder), patch.object(gate, "check", side_effect=eligibility) as checker,
              patch("sys.argv", ["demo_gate.py", "--offline"]), contextlib.redirect_stdout(io.StringIO())):
            self.assertEqual(gate.main(), 1)
            self.assertEqual(checker.call_count, 1)
            self.assertEqual(checker.call_args.args[0], newer)


if __name__ == "__main__":
    unittest.main()
