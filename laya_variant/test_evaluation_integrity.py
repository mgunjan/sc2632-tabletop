"""Regression tests for failures that could create a false comparison. Offline."""
import hashlib
import json
import pathlib
import sys
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent / 'generator'))
import baselines
import evaluate
import openai_decisions
from questions import QUESTION_SETS


class Integrity(unittest.TestCase):
    def test_failed_answers_are_wrong_even_when_gold_is_false(self):
        stats = {'rows': 0, 'failed_rows': 0}
        row = baselines._rows('input', [{}], stats)[0]
        metric, _ = evaluate.metrics([(row['prompt_injection'], False)])
        self.assertEqual(metric['accuracy'], 0)
        self.assertEqual(metric['unreadable'], 1)
        self.assertIsNone(metric['ece'])
        self.assertIsNone(metric['brier'])

    def test_zero_confidence_is_retained_and_invalid_values_are_not_clamped(self):
        for value in [0, None, '0.9', True, -.1, 1.1, float('nan'), float('inf')]:
            stats = {'rows': 0, 'failed_rows': 0}
            row = baselines._rows('input', [{'prompt_injection': {'answer': True, 'confidence': value}}], stats)[0]['prompt_injection']
            if value == 0 and not isinstance(value, bool):
                self.assertTrue(row['valid']); self.assertEqual(row['decision'], 'true'); self.assertEqual(row['conf'], 0)
            else:
                self.assertFalse(row['valid'])

    def test_bad_predicate_probabilities_cannot_become_negatives(self):
        qd = QUESTION_SETS['input']['prompt_injection']
        for value in [True, '0.9', -1, 2, float('nan'), float('inf')]:
            self.assertIsNone(baselines._decider_answer(qd, {'noul': value}))

    def test_explicit_choice_and_confidence_are_not_replaced_by_argmax(self):
        qd = QUESTION_SETS['exception']['scope']
        pr = baselines._decider_answer(qd, {'choice': 'pattern', 'probabilities': {'single': .6, 'pattern': .3, 'broad': .1}, 'answer_confidence': .2})
        metric, _ = evaluate.metrics([(pr, 'pattern')])
        self.assertEqual(metric['accuracy'], 1); self.assertEqual(pr['conf'], .2)
        self.assertEqual(evaluate._as_answers({'scope': pr})['scope']['choice'], 'pattern')

    def test_documented_four_decimal_rounding_is_not_a_failed_answer(self):
        qd = QUESTION_SETS['exception']['scope']
        pr = baselines._decider_answer(qd, {'choice': 'single', 'probabilities': {'single': .6, 'pattern': .3333, 'broad': .0666}, 'answer_confidence': .6})
        self.assertIsNotNone(pr); self.assertAlmostEqual(sum(pr['p']), 1)
        self.assertIsNone(baselines._decider_answer(qd, {'choice': 'single', 'probabilities': {'single': .6, 'pattern': .3, 'broad': .06}}))

    def test_no_silent_short_pairing(self):
        for fn in [evaluate._mcnemar, evaluate._boot_delta]:
            with self.assertRaises(ValueError): fn([1, 0], [1])

    def test_incomplete_gate_is_not_a_model_result(self):
        def report(valid=True, shift=False):
            qs = {}
            for q in evaluate.GATE_QUESTIONS:
                qs[q] = {'correct': [1, 0], 'conf': [.8, .2], 'valid': [True, valid],
                         'ids': [f'a:{q}', f'{"c" if shift else "b"}:{q}'], 'groups': ['a', 'c' if shift else 'b']}
            return {'splits': {'gold': {'questions': qs}}}
        g = evaluate.gate({'tfidf-lr': report(), 'candidate': report(False)}, 'gold')
        self.assertEqual(g['candidates']['candidate']['verdict'], 'INCOMPLETE')
        g = evaluate.gate({'tfidf-lr': report(), 'candidate': report(shift=True)}, 'gold')
        self.assertEqual(g['candidates']['candidate']['verdict'], 'UNPAIRED')

    def test_cluster_bootstrap_keeps_questions_on_a_state_together(self):
        lo, hi = evaluate._cluster_boot_delta([1]*5+[0]*5, [0]*10, ['a']*5+['b']*5)
        self.assertEqual((lo, hi), (0, 1))

    def test_full_state_text_keeps_structured_evidence(self):
        state = {'exception': {'reason': 'dependency', 'owner': 'ops', 'workload': 'x-*', 'ttl_hours': 24}, 'incident': 'x-1 suspect'}
        legacy = baselines.row_text('exception', state)
        full = baselines.row_text('exception', state, full_state=True)
        self.assertNotIn('x-*', legacy); self.assertIn('x-*', full); self.assertIn('24', full); self.assertIn('x-1 suspect', full)

    def test_decisions_recording_binds_task_state_and_questions(self):
        state = {'text': 'hello', 'channel': 'email'}
        r = {'task': 'input', 'model': 'gpt-6-luna',
             'state_sha256': hashlib.sha256(json.dumps(state, sort_keys=True).encode()).hexdigest(),
             'questions_sha256': openai_decisions.questions_hash('input'),
             'response': {'model': 'gpt-6-luna', 'answers': {q: {'noul': .1} for q in QUESTION_SETS['input']}}}
        with tempfile.TemporaryDirectory() as d:
            p = pathlib.Path(d) / 'recording.jsonl'; p.write_text(json.dumps(r)+'\n')
            _, predict, meta = openai_decisions.recorded_predictor(p)
            self.assertTrue(all(x['valid'] for x in predict('input', [state])[0].values()))
            altered = {**state, 'text': 'hello!'}
            self.assertFalse(any(x['valid'] for x in predict('input', [altered])[0].values()))
            self.assertEqual(meta['stats']['missing'], 1)
            r['questions_sha256'] = 'different'; p.write_text(json.dumps(r)+'\n')
            _, predict, meta = openai_decisions.recorded_predictor(p)
            self.assertFalse(any(x['valid'] for x in predict('input', [state])[0].values()))
            self.assertEqual(meta['stats']['question_mismatch'], 1)
            r['questions_sha256'] = openai_decisions.questions_hash('input')
            r['response']['model'] = 'different'
            p.write_text(json.dumps(r)+'\n'); _, predict, meta = openai_decisions.recorded_predictor(p)
            self.assertFalse(any(x['valid'] for x in predict('input', [state])[0].values()))
            self.assertEqual(meta['stats']['model_mismatch'], 1)
            p.write_text((json.dumps(r)+'\n')*2)
            with self.assertRaises(ValueError): openai_decisions.recorded_predictor(p)


if __name__ == '__main__': unittest.main()
