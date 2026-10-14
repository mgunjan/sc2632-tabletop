"""Presenter failure handling: no hosted calls or cluster access."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
DEMO = ROOT / "tabletop/congress-2026/demo.py"


class PresenterDemoTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.folder = Path(folder.name)

    def call(self, *args, **kwargs):
        return subprocess.run([sys.executable, str(DEMO), *args], capture_output=True, text=True, timeout=10, **kwargs)

    def test_preflight_without_policy_tool_is_not_ready(self):
        result = self.call("--check", env={**os.environ, "PATH": str(self.folder)})
        self.assertEqual(result.returncode, 2)
        self.assertFalse(json.loads(result.stdout)["ready"])
        self.assertFalse(list(self.folder.iterdir()))

    def test_existing_evidence_is_preserved(self):
        out = self.folder / "existing"
        out.mkdir()
        marker = out / "evidence.txt"
        marker.write_text("keep")
        result = self.call("--out", str(out))
        self.assertEqual(result.returncode, 2)
        self.assertEqual(marker.read_text(), "keep")
        self.assertEqual(len(list(out.iterdir())), 1)

    def test_invalid_deadline_and_unbound_replay_refused(self):
        for value in ("nan", "inf", "0", "61"):
            result = self.call("--out", str(self.folder / "new"), "--deadline", value)
            self.assertEqual(result.returncode, 2)
        result = self.call("--mode", "replay", "--scenario", "b", "--out", str(self.folder / "new"))
        self.assertEqual(result.returncode, 2)
        self.assertFalse((self.folder / "new").exists())

    @unittest.skipUnless(os.name == "posix", "process group termination is tested on the presenting Unix environment")
    def test_deadline_terminates_the_policy_tool_child(self):
        # A controllably hung CLI validates whole-run deadline behavior and its child signal.
        binary = self.folder / "kyverno"
        signal_record = self.folder / "terminated"
        binary.write_text(f"#!{sys.executable}\n" +
            "import os,signal,sys,time\nfrom pathlib import Path\n" +
            "if sys.argv[1] == 'version':\n print('Version: 1.19.1'); sys.exit(0)\n" +
            "def stop(*args):\n Path(os.environ['TEST_SIGNAL_RECORD']).write_text('terminated'); sys.exit(0)\n" +
            "signal.signal(signal.SIGTERM, stop)\ntime.sleep(60)\n")
        binary.chmod(0o700)
        out = self.folder / "deadline"
        result = self.call("--out", str(out), "--deadline", "2",
                           env={**os.environ, "PATH": str(self.folder) + os.pathsep + os.environ.get("PATH", ""),
                                "TEST_SIGNAL_RECORD": str(signal_record)})
        self.assertEqual(result.returncode, 124, result.stdout + result.stderr)
        run = json.loads((out / "demo-run.json").read_text())
        self.assertEqual(run["status"], "DEADLINE_EXCEEDED")
        self.assertFalse(run["deployment_performed"])
        self.assertTrue(signal_record.exists(), "policy-tool child did not receive termination")
        self.assertFalse((out / "proposal").exists())


if __name__ == "__main__":
    unittest.main()
