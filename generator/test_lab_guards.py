"""Lab setup and stage preflight refusal paths, using command stand-ins only."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent


class LabGuardTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.folder = Path(directory.name)
        self.log = self.folder / "commands.log"
        script = f"#!{sys.executable}\n" + '''import os,sys
from pathlib import Path
name=Path(sys.argv[0]).name
args=sys.argv[1:]
with Path(os.environ['TEST_COMMAND_LOG']).open('a') as stream: stream.write(name+' '+ ' '.join(args)+'\\n')
if name == 'k3d': sys.exit(0)
if name == 'kubectl':
 if any('go-template=' in a for a in args):
  print('suspect-one' if any('suspect=true' in a for a in args) else 'clean-one'); sys.exit(0)
 if 'exec' in args and os.environ.get('TEST_DNS_TRANSPORT_FAIL') == '1': sys.exit(1)
 if args and args[0] == 'wait' and 'validatingpolicies.policies.kyverno.io' in args:
  if '--for=jsonpath={.status.conditionStatus.ready}=true' not in args: sys.exit(97)
  sys.exit(0 if os.environ.get('TEST_POLICY_READY') == '1' else 1)
 if 'current-context' in args: print('unit-test-context'); sys.exit(0)
 if any('configmaps/trustfall-lab' in a for a in args): sys.exit(0 if os.environ.get('TEST_MARKER') == '1' else 1)
 if any('readyReplicas' in a for a in args): print('1' if 'kyverno' in args else '3/3')
 sys.exit(0)
if name == 'curl': print('healthy-but-unevaluated'); sys.exit(0)
if name == 'kyverno': print(os.environ.get('FAKE_KYVERNO_VERSION','Version: 1.19.1')); sys.exit(0)
sys.exit(0)
'''
        for name in ("kubectl", "k3d", "docker", "helm", "curl", "kyverno"):
            path = self.folder / name
            path.write_text(script); path.chmod(0o700)
        self.env = {**os.environ, "PATH": str(self.folder) + os.pathsep + str(Path(sys.executable).parent) + os.pathsep + os.environ.get("PATH", ""),
                    "TEST_COMMAND_LOG": str(self.log), "TRUSTFALL_LAB_OK": "", "STAGED": "", "DEMO_REPLAY": "",
                    "TRUSTFALL_EXPECTED_CONTEXT": "unit-test-context",
                    "DECIDER_EVAL_SUMMARY": str(next((ROOT / "submission/2026-10-12/benchmark/preregistered-decider").glob("*.summary.json")))}

    def run_script(self, script, arguments=(), **env):
        return subprocess.run(["/bin/bash", str(ROOT / script), *arguments], cwd=ROOT, env={**self.env, **env}, capture_output=True, text=True, timeout=10)

    def test_ready_policy_gate_uses_pinned_nested_status(self):
        result = subprocess.run(["/bin/bash", "-c", "source lab/lib-guard.sh; wait_validating_policies"],
                                cwd=ROOT, env={**self.env, "TEST_POLICY_READY": "1"},
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("--for=jsonpath={.status.conditionStatus.ready}=true", self.log.read_text())

    def test_unready_policy_gate_fails_instead_of_silently_continuing(self):
        result = subprocess.run(["/bin/bash", "-c", "source lab/lib-guard.sh; wait_validating_policies"],
                                cwd=ROOT, env={**self.env, "TEST_POLICY_READY": "0"},
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("did not become ready", result.stderr)

    def test_dns_reveal_refuses_transport_failure_before_applying_posture(self):
        result = self.run_script("tabletop/consequences/1-deny-all.sh", TEST_MARKER="1",
                                 TEST_DNS_TRANSPORT_FAIL="1", PACE="0")
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("DNS probe unavailable", result.stderr)
        self.assertNotIn("apply", self.log.read_text())

    def test_launcher_labels_live_failure_without_replaying_after_attempt(self):
        result = self.run_script("tabletop/consequences/play.sh", ("1-deny-all",), TEST_MARKER="1",
                                 TEST_DNS_TRANSPORT_FAIL="1", PACE="0", STAGED="0",
                                 DEMO_REPLAY="1")
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("LIVE — prepared disposable lab", result.stdout)
        self.assertIn("LIVE check FAILED", result.stderr)
        self.assertNotIn("(replay,", result.stdout)
        self.assertNotIn("apply", self.log.read_text())

    def test_native_setup_refuses_unmarked_context_before_writes(self):
        result = self.run_script("lab/setup.sh", RUNTIME="k3s")
        self.assertEqual(result.returncode, 3, result.stdout + result.stderr)
        commands = self.log.read_text()
        self.assertNotIn("apply", commands)
        self.assertNotIn("create namespace", commands)
        self.assertNotIn("docker", commands)

    def test_existing_k3d_refuses_before_context_switch(self):
        result = self.run_script("lab/setup.sh", RUNTIME="k3d", CLUSTER="existing")
        self.assertEqual(result.returncode, 3, result.stdout + result.stderr)
        commands = self.log.read_text()
        self.assertNotIn("use-context", commands)
        self.assertNotIn("apply", commands)

    def test_unknown_runtime_never_mutates_context(self):
        result = self.run_script("lab/setup.sh", RUNTIME="unexpected")
        self.assertEqual(result.returncode, 2)
        self.assertFalse(self.log.exists())

    def test_health_alone_never_reports_live_model(self):
        result = self.run_script("tabletop/consequences/preflight.sh", TEST_MARKER="1")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        line = next(line for line in result.stdout.splitlines() if 'decider' in line)
        self.assertTrue(line.startswith("SKIP"), line)
        self.assertNotIn("step 3 runs live", line)
        self.assertNotIn("curl", self.log.read_text())

    def test_preflight_refuses_wrong_context_before_cluster_api_requests(self):
        result = self.run_script("tabletop/consequences/preflight.sh", TRUSTFALL_EXPECTED_CONTEXT="another-context")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("does not match expected 'another-context'", result.stdout)
        commands = self.log.read_text()
        self.assertNotIn("/api/v1/namespaces/payments", commands)
        self.assertNotIn("configmaps/trustfall-lab", commands)

    def test_wrong_kyverno_version_fails_preflight(self):
        result = self.run_script("tabletop/consequences/preflight.sh", TEST_MARKER="1",
                                 FAKE_KYVERNO_VERSION="Version: 1.20.0")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("want exactly 1.19.1", result.stdout)

    def test_stage_refuses_wrong_context_before_destructive_calls(self):
        result = self.run_script("tabletop/consequences/stage.sh", TEST_MARKER="1",
                                 TRUSTFALL_EXPECTED_CONTEXT="another-context")
        self.assertEqual(result.returncode, 3, result.stdout + result.stderr)
        self.assertIn("does not match expected lab context", result.stderr)
        commands = self.log.read_text()
        self.assertNotIn(" delete ", commands)
        self.assertNotIn("apply", commands)

    def test_missing_yaml_fails_before_live_rehearsal_writes(self):
        python = self.folder/'python3'
        python.write_text('#!/bin/sh\nexit 1\n'); python.chmod(0o700)
        result = self.run_script('scripts/lab-e2e.sh', TEST_MARKER='1')
        self.assertEqual(result.returncode, 2)
        self.assertIn('needs PyYAML', result.stdout)
        self.assertFalse(self.log.exists(), 'No Kubernetes command may run with missing fixture dependencies')


if __name__ == "__main__":
    unittest.main()
