#!/usr/bin/env python3
"""Reject mismatched approval scope, altered states and fabricated cost summaries."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import build
import compare_hosted as c
import hosted


class HostedAudit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.tmp.name)
        build.build(cls.root / 'data')
        cls.preview = cls.root / 'preview'
        cls.manifest = hosted.export_preview(cls.root / 'data', cls.preview)
        # Simulated authorization is confined to this temporary unit-test fixture.
        cls.approval = {'status': 'APPROVED', 'model': 'claude-opus-5-5',
                        'api_usage_budget_usd': 8, 'preview_sha256': cls.manifest['preview_sha256']}
        entries = [json.loads(l) for l in (cls.preview / 'OUTBOUND-PREVIEW.jsonl').read_text().splitlines()]
        cls.records = []
        for e in entries:
            if e['phase'] == 'warmup':
                continue
            state = json.loads(e['outbound_body']['messages'][0]['content'])['state']
            cls.records.append({'id': e['assessment_id_for_preview_only'],
                                'state_sha256': hashlib.sha256(state.encode()).hexdigest()})

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_exact_scope_passes_without_any_network(self):
        result = c.verify_preview(self.preview, self.approval, self.records, 'claude-opus-5-5')
        self.assertEqual(result['requests'], 301)

    def test_pending_approval_or_different_model_is_rejected(self):
        for change in ({'status': 'PENDING'}, {'model': 'claude-sonnet-5-5'}, {'api_usage_budget_usd': 9}, {'preview_sha256': 'wrong'}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                c.verify_preview(self.preview, {**self.approval, **change}, self.records, 'claude-opus-5-5')

    def test_missing_or_changed_assessment_is_rejected(self):
        changed = copy.deepcopy(self.records)
        changed[0]['state_sha256'] = 'altered-evidence'
        for records in (changed, self.records[:-1]):
            with self.assertRaises(ValueError):
                c.verify_preview(self.preview, self.approval, records, 'claude-opus-5-5')

    def test_false_cost_and_tampered_metrics_are_rejected(self):
        for value in (None, float('nan'), 1.2, True):
            with self.subTest(value=value), self.assertRaises(ValueError):
                c.require_close(value, .12, 'test')
        root = self.root / 'tampered'
        root.mkdir(exist_ok=True)
        source = b'fixture-only'
        (root / 'BENCHMARK.py.txt').write_bytes(source)
        (root / 'summary.json').write_text(json.dumps({'benchmark_sha256': hashlib.sha256(source).hexdigest(),
                                                      'metrics': {'routing': {'threshold': None}}}))
        row = {'id': 'cal', 'case_id': 'case', 'family_id': 'family', 'expected': 'exclude',
               'prediction': 'exclude', 'probabilities': None, 'confidence': None}
        (root / 'cal-raw.jsonl').write_text(json.dumps(row) + '\n')
        (root / 'test-responses.jsonl').write_text(json.dumps({**row, 'id': 'test'}) + '\n')
        with self.assertRaisesRegex(ValueError, 'metrics differ'):
            c.load_run(root)


if __name__ == '__main__':
    unittest.main()
