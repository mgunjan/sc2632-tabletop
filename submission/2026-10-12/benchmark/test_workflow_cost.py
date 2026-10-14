"""A failed API workflow must remain unpriced, not appear free."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import run_workflow_cost as cost


class FailedProvider:
    model = 'fake-unavailable-provider'
    def __call__(self, *args): raise RuntimeError('Provider HTTP 503')


class CostFailure(unittest.TestCase):
    def test_failed_requests_remain_counted_and_cost_unknown(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d)/'run'
            with patch.object(cost, 'JevProvider', lambda *args: FailedProvider()), \
                 patch('sys.argv', ['run_workflow_cost.py', '--provider', 'jev', '--out', str(out), '--repeats', '1']), \
                 contextlib.redirect_stdout(io.StringIO()):
                cost.main()
            r = json.loads((out/'summary.json').read_text())
            self.assertEqual(r['runs'][0]['api_calls'], 4)
            self.assertIsNone(r['runs'][0]['input_tokens'])
            self.assertIsNone(r['runs'][0]['estimated_usd'])
            self.assertIsNone(r['median_estimated_usd'])
            self.assertEqual(r['runs'][0]['escalations'], 4)
            self.assertFalse(r['runs'][0]['privilege_policy_present'])


if __name__ == '__main__': unittest.main()
