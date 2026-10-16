"""Evidence cannot acquire a stronger label through normalization."""
import copy
import json
from pathlib import Path
import shutil
import tempfile
import unittest

import build_evidence_corpus as corpus


class EvidenceCorpus(unittest.TestCase):
    def snapshot(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        _, manifest = corpus.build()
        sources = {ref['path'] for ref in manifest['source_artifacts']}
        for name in sources:
            target = root/name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(corpus.ROOT/name, target)
        return root

    def test_failed_observations_and_scope_survive(self):
        rows, manifest = corpus.build()
        self.assertEqual(manifest['logical_cases'], 20)
        self.assertEqual(manifest['observations'], 48)
        self.assertEqual(manifest['training_eligible_rows'], 0)
        self.assertEqual(manifest['independent_response_labels'], 0)
        self.assertTrue(all(r['split'] == 'regression_only' and r['training_eligible'] is False
                            and r['decision_label'] is None for r in rows))
        falco = [r for r in rows if r['task'] == 'falco_rule_behavior']
        failed = {name: sum(not o['meets_contract'] for r in falco for o in r['observations']
                           if o['run_id'] == name) for name in ('baseline', 'repaired', 'ci-amd64')}
        self.assertEqual(failed, {'baseline': 4, 'repaired': 0, 'ci-amd64': 0})
        kyverno = [r for r in rows if r['task'] == 'kyverno_policy_behavior']
        self.assertEqual(sorted(r['observations'][0]['observed']['policy_result'] for r in kyverno),
                         ['fail', 'fail', 'fail', 'fail', 'pass', 'skip'])
        self.assertTrue(all(r['observations'][0]['meets_contract'] for r in kyverno))

    def test_missing_receipt_cannot_become_a_negative(self):
        root = self.snapshot()
        path = root/corpus.BASE/'falco-audit/repaired/falco.stdout.jsonl'
        lines = path.read_text().splitlines()
        index = next(i for i, line in enumerate(lines) if corpus.WITNESS in line)
        path.write_text('\n'.join(lines[:index]+lines[index+1:])+'\n')
        with self.assertRaisesRegex(ValueError, 'receipt'):
            corpus.build(root)

    def test_incomplete_case_results_are_rejected(self):
        root = self.snapshot()
        path = root/corpus.BASE/'falco-audit/baseline/result.json'
        result = json.loads(path.read_text())
        result['checks'].pop()
        path.write_text(json.dumps(result))
        with self.assertRaisesRegex(ValueError, 'identities'):
            corpus.build(root)

    def test_rule_hash_mismatch_is_rejected(self):
        root = self.snapshot()
        path = root/corpus.BASE/'falco-audit/repaired/rules.yaml'
        path.write_text(path.read_text()+'\n# unrecorded change\n')
        with self.assertRaisesRegex(ValueError, 'provenance'):
            corpus.build(root)

    def test_policy_harness_success_cannot_replace_policy_result(self):
        root = self.snapshot()
        folder = root/corpus.BASE/'dataset/kyverno'
        report = json.loads((folder/'apply.json').read_text())
        bad = copy.deepcopy(report)
        for row in bad['results']:
            row['result'] = 'pass'
        (folder/'apply.json').write_text(json.dumps(bad))
        with self.assertRaisesRegex(ValueError, 'raw stdout'):
            corpus.build(root)

    def test_policy_change_requires_new_execution_evidence(self):
        root = self.snapshot()
        path = root/corpus.BASE/'dataset/kyverno/policy.yaml'
        path.write_text(path.read_text()+'\n# changed after execution\n')
        with self.assertRaisesRegex(ValueError, 'provenance'):
            corpus.build(root)

    def test_removed_resource_is_not_ignored(self):
        root = self.snapshot()
        folder = root/corpus.BASE/'dataset/kyverno'
        report = json.loads((folder/'apply.json').read_text())
        report['results'].pop()
        for path in ('apply.json', 'apply.stdout.txt'):
            (folder/path).write_text(json.dumps(report))
        with self.assertRaisesRegex(ValueError, 'Kyverno observations'):
            corpus.build(root)

    def test_targets_are_outside_candidate_inputs(self):
        rows, _ = corpus.build()
        for row in rows:
            self.assertFalse({'expected', 'target', 'observed', 'classification'} & row['inputs'].keys())
        gap = next(r for r in rows if r['id'] == 'falco-audit:metadata-only')
        self.assertEqual(gap['target']['alert_tags'], [])
        self.assertEqual(gap['target']['evidence_gap_tags'], ['audit-visibility-gap'])
        self.assertIn('events', gap['inputs'])


if __name__ == '__main__':
    unittest.main()
