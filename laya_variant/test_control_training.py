"""Split isolation and training protocol checks. No pretrained model needed."""
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

import build_control_dataset as b


class Curriculum(unittest.TestCase):
    def test_curriculum_split_isolation_and_question_parity(self):
        with tempfile.TemporaryDirectory() as d:
            p = pathlib.Path(d)/'data'; manifest = b.build(p)
            seen_states, seen_templates = set(), set()
            for split, info in manifest['splits'].items():
                rows = [json.loads(l) for l in (p/f'{split}.jsonl').read_text().splitlines()]
                self.assertEqual(len(rows), 480 if split == 'train' else 60)
                states, templates = {r['state'] for r in rows}, {r['template'] for r in rows}
                self.assertFalse(seen_states & states); self.assertFalse(seen_templates & templates)
                self.assertEqual({r['labels']['q'] for r in rows}, set(b.da.CONTROLS))
                seen_states |= states; seen_templates |= templates
            qs = json.loads((p/'questions.json').read_text())
            self.assertEqual(qs['policy_control']['q'], b.da.QUESTION['control'])
            self.assertEqual(list(qs['policy_control']['q']['criteria']), list(b.da.CONTROLS))
            p2 = pathlib.Path(d)/'repeat'; other = b.build(p2)
            self.assertEqual(manifest, other)
            with self.assertRaises(ValueError): b.build(p)

    def test_training_cannot_select_a_checkpoint_on_test_data(self):
        with tempfile.TemporaryDirectory() as d:
            r = subprocess.run([sys.executable, str(pathlib.Path(__file__).with_name('train.py')),
                '--base', 'does-not-exist', '--out', d, '--selection-split', 'test_ood'], capture_output=True, text=True)
            self.assertNotEqual(r.returncode, 0); self.assertIn('never a test split', r.stderr)
            self.assertFalse(any(pathlib.Path(d).iterdir()))


if __name__ == '__main__': unittest.main()
