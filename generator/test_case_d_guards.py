"""Case D refusal/cleanup/redaction contracts. No Docker, cluster or API calls."""
import base64
import contextlib
import datetime as dt
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('case_d_verifier', ROOT/'lab/verify-case-d.py')
case_d = importlib.util.module_from_spec(spec); spec.loader.exec_module(case_d)


class GuardTests(unittest.TestCase):
    def test_baseline_service_can_settle_before_intervention(self):
        responses = [subprocess.CompletedProcess([], 1, '', 'service not ready'),
                     subprocess.CompletedProcess([], 0, 'trustfall lab stand-in', '')]
        observations = []
        fake = unittest.mock.Mock()
        fake.call.side_effect = responses
        with patch.object(case_d.time, 'sleep'):
            case_d.wait_for_baseline_service(fake, 'synthetic-test', observations.append)
        self.assertEqual([o['healthy'] for o in observations], [False, True])
        self.assertEqual(fake.call.call_count, 2)

    def test_unavailable_baseline_service_fails_at_deadline(self):
        observations = []
        fake = unittest.mock.Mock()
        fake.call.return_value = subprocess.CompletedProcess([], 1, '', 'unavailable')
        with self.assertRaisesRegex(RuntimeError, 'startup deadline'):
            case_d.wait_for_baseline_service(fake, 'synthetic-test', observations.append, seconds=0.01)
        self.assertTrue(observations)
        self.assertFalse(any(o['healthy'] for o in observations))

    def test_health_timeout_and_unexpected_body_never_count_as_success(self):
        fake = unittest.mock.Mock()
        fake.call.side_effect = subprocess.TimeoutExpired('probe', 1)
        self.assertFalse(case_d.probe_standin_health(fake, 'synthetic-test')['healthy'])
        payload = 'must-not-enter-evidence'
        fake.call.side_effect = None
        fake.call.return_value = subprocess.CompletedProcess([], 0, payload, '')
        observation = case_d.probe_standin_health(fake, 'synthetic-test')
        self.assertFalse(observation['healthy'])
        self.assertNotIn(payload, json.dumps(observation))

    def test_non_rehearsal_context_refuses_before_any_command(self):
        with patch.object(case_d.Lab, 'call') as command:
            with self.assertRaisesRegex(ValueError, 'named disposable'):
                case_d.Lab('/tmp/unused-config', 'production-context')
        command.assert_not_called()

    def test_remote_api_server_refuses_before_resource_creation(self):
        responses = [subprocess.CompletedProcess([], 0, json.dumps({'data': {'created-by': 'lab/setup.sh'}}), ''),
                     subprocess.CompletedProcess([], 0, 'https://production.example:6443', ''),
                     subprocess.CompletedProcess([], 0, base64.b64encode(b'public-ca').decode(), '')]
        with patch.object(case_d.Lab, 'call', side_effect=responses) as command:
            with self.assertRaisesRegex(ValueError, 'loopback HTTPS'):
                case_d.Lab('/tmp/unused-config', 'k3d-sc2632-rehearsal-test')
        self.assertEqual(command.call_count, 3)
        self.assertFalse(any('create' in call.args[0] for call in command.call_args_list))

    def test_proxy_and_redirect_are_disabled_for_the_bearer_transport(self):
        responses = [subprocess.CompletedProcess([], 0, json.dumps({'data': {'created-by': 'lab/setup.sh'}}), ''),
                     subprocess.CompletedProcess([], 0, 'https://127.0.0.1:6443', ''),
                     subprocess.CompletedProcess([], 0, base64.b64encode(b'public-ca').decode(), '')]
        with patch.object(case_d.Lab, 'call', side_effect=responses), patch.object(case_d.ssl, 'create_default_context'), \
                patch.object(case_d.urllib.request, 'build_opener') as build:
            case_d.Lab('/tmp/unused-config', 'k3d-sc2632-rehearsal-test')
        self.assertEqual(build.call_args.args[0].proxies, {})
        self.assertIsInstance(build.call_args.args[2], case_d.NoRedirect)
        self.assertIsNone(build.call_args.args[2].redirect_request(None, None, 302, '', {}, 'https://elsewhere.example'))

    def run_main(self, fake):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)/'evidence'
            output = io.StringIO()
            with patch.object(case_d, 'Lab', return_value=fake), \
                    patch.object(sys, 'argv', ['verify-case-d', '--kubeconfig', '/tmp/unused',
                                                '--context', 'k3d-sc2632-rehearsal-test', '--out', str(folder)]), \
                    contextlib.redirect_stdout(output):
                status = case_d.main()
            return status, json.loads((folder/'result.json').read_text()), output.getvalue()

    def test_existing_namespace_is_never_deleted_after_create_refusal(self):
        class Refuse:
            def __init__(self): self.commands = []
            def call(self, arguments, body=None, timeout=25):
                self.commands.append(arguments)
                return subprocess.CompletedProcess([], 1, '', 'already exists')
        fake = Refuse()
        status, result, _ = self.run_main(fake)
        self.assertEqual(status, 1)
        self.assertEqual(result['cleanup'], [])
        self.assertEqual(len(fake.commands), 1)
        self.assertEqual(fake.commands[0], ['create', '-f', '-'])

    def test_auth_failure_never_persists_token_or_response_payload(self):
        credential = 'unit-test-bearer-must-never-be-persisted'
        class Fake:
            def __init__(self): self.commands = []
            def call(self, arguments, body=None, timeout=25):
                self.commands.append(arguments)
                if 'wget' in arguments: stdout = 'trustfall lab stand-in'
                elif '--raw' in arguments:
                    stdout = json.dumps({'status': {'token': credential, 'expirationTimestamp':
                        (dt.datetime.now(dt.timezone.utc)+dt.timedelta(minutes=10)).isoformat()}})
                elif 'jsonpath={.metadata.uid}' in arguments: stdout = 'unit-pod-uid'
                elif 'jsonpath={.spec.clusterIP}' in arguments: stdout = '10.43.0.1'
                else: stdout = 'created'
                return subprocess.CompletedProcess([], 0, stdout, '')
            def api(self, token, path, body=None):
                return 401, {'message': credential, 'data': {'credential': credential}}
        fake = Fake()
        status, result, output = self.run_main(fake)
        self.assertEqual(status, 1)
        self.assertEqual(result['status'], 'FAIL')
        self.assertTrue(result['tokens'])
        self.assertNotIn(credential, json.dumps(result))
        self.assertNotIn(credential, output)
        self.assertNotIn(credential, json.dumps(fake.commands))
        self.assertTrue(result['cleanup'])


if __name__ == '__main__': unittest.main()
