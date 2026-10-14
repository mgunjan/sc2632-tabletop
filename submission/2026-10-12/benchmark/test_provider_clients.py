"""Offline contract tests; no API calls and no real credentials."""
import math
import copy
import types
import os
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch
import provider_clients as p

Q = {'type': 'choice', 'instructions': 'Which control?', 'criteria': {'a': 'A', 'b': 'B'}}


class Contracts(unittest.TestCase):
    def test_laya_reports_fitted_temperature_without_claiming_validation(self):
        agent = types.SimpleNamespace(cfg={'trustfall_variant': {'calibrated': True}},
            predict=lambda *args: {'answers': {'q': {'choice': 'a', 'answer_confidence': .7}}})
        with patch.dict('sys.modules', {'laya': types.SimpleNamespace(load=lambda *args, **kwargs: agent)}):
            result = p.LayaProvider()('', 'state', Q)
        self.assertTrue(result['configuration']['temperature_fitted'])
        self.assertIn('deployment calibration not established', result['configuration']['local_calibration'])
        self.assertEqual(result['answers']['q']['confidence'], .7)

    def decision_response(self):
        return {'model': 'gpt-6-luna', 'answers': [{'type': 'choice', 'name': 'q', 'choice': 'a',
            'probabilities': [{'value': 'a', 'probability': .8}, {'value': 'b', 'probability': .2}],
            'confidence': .6}], 'usage': {'input_tokens': 1000, 'output_tokens': 0}}

    @patch.dict(os.environ, {'OPENAI_API_KEY': 'test-credential'})
    def test_decisions_endpoint_and_probability_signals(self):
        calls = []
        def fake(url, body, key):
            calls.append((url, body)); return self.decision_response()
        r = p.OpenAIDecisionsProvider(transport=fake)('', 'evidence', Q)
        self.assertEqual(calls[0][0], 'https://api.openai.com/v1/decisions')
        self.assertEqual(set(calls[0][1]), {'model', 'input', 'questions'})
        self.assertEqual(calls[0][1]['questions'][0]['choices'], [{'value': 'a', 'description': 'A'}, {'value': 'b', 'description': 'B'}])
        self.assertEqual(r['answers']['q']['confidence'], .6)
        self.assertEqual(r['answers']['q']['selected_probability'], .8)
        self.assertEqual(r['api_response']['answers'][0]['probabilities'][0]['probability'], .8)
        self.assertAlmostEqual(r['cost_estimate']['estimated_usd'], .0001)
        self.assertNotIn('test-credential', str(r))

    @patch.dict(os.environ, {'OPENAI_API_KEY': 'test-credential'})
    def test_decisions_predicate_and_refusal_remain_distinct(self):
        def fake(url, body, key):
            self.assertEqual(body['questions'][0]['type'], 'predicate')
            return {'model': 'gpt-6-luna', 'answers': [{'type': 'predicate', 'name': 'p', 'probability': 0},
                {'type': 'refusal', 'name': 'q'}], 'usage': {}}
        r = p.OpenAIDecisionsProvider(transport=fake).decide({'record': 'evidence'},
            {'p': {'type': 'noul', 'instructions': 'Is it true?'}, 'q': Q})
        self.assertEqual(r['answers']['p']['noul'], 0)
        self.assertEqual(r['answers']['p']['answer_confidence'], 1)
        self.assertTrue(r['answers']['q']['refused'])
        self.assertNotIn('choice', r['answers']['q'])
        self.assertIsNone(r['cost_estimate']['estimated_usd'])

    @patch.dict(os.environ, {'OPENAI_API_KEY': 'test-credential'})
    def test_decisions_rejects_invalid_distribution_identity_and_model(self):
        originals = self.decision_response()
        mutations = [
            lambda r: r.update(model='unexpected'),
            lambda r: r.update(answers=[]),
            lambda r: r['answers'].append(copy.deepcopy(r['answers'][0])),
            lambda r: r['answers'][0].update(name='unknown'),
            lambda r: r['answers'][0].update(type='predicate'),
            lambda r: r['answers'][0].update(choice='unknown'),
            lambda r: r['answers'][0].update(confidence=float('nan')),
            lambda r: r['answers'][0].update(confidence=1.1),
            lambda r: r['answers'][0]['probabilities'].pop(),
            lambda r: r['answers'][0]['probabilities'][0].update(probability=.2),
            lambda r: r['answers'][0]['probabilities'][0].update(probability=float('inf')),
            lambda r: r['answers'][0]['probabilities'][0].update(probability=True),
            lambda r: r['answers'][0]['probabilities'][0].update(value='b'),
        ]
        for mutation in mutations:
            raw = copy.deepcopy(originals); mutation(raw)
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                p.OpenAIDecisionsProvider(transport=lambda *args: raw)('', 'evidence', Q)

    def test_decisions_cost_never_invents_missing_usage(self):
        for value in [None, {}, {'input_tokens': -1}, {'input_tokens': True}, {'input_tokens': '1000'}]:
            self.assertIsNone(p.decisions_cost(value)['estimated_usd'])
        self.assertEqual(p.decisions_cost({'input_tokens': 0})['estimated_usd'], 0)

    def test_bare_credential_loader_never_uses_secret_as_variable_name(self):
        with tempfile.TemporaryDirectory() as d, patch.dict(os.environ, {}, clear=True):
            f = Path(d) / 'private.env'
            f.write_text('fake-private-credential\n')
            p.load_credentials(f, 'claude')
            self.assertEqual(os.environ['ANTHROPIC_API_KEY'], 'fake-private-credential')
            self.assertNotIn('fake-private-credential', os.environ)

    @patch.dict(os.environ, {'ANTHROPIC_API_KEY': 'test-credential'})
    def test_claude_structured_output_and_normal_completion(self):
        calls = []
        def fake(url, body, key):
            calls.append(body)
            return {'stop_reason': 'end_turn', 'model': 'resolved-claude',
                    'content': [{'type': 'text', 'text': '{"choice":"a","confidence":0.8}'}]}
        result = p.ClaudeProvider(transport=fake)('', 'evidence', Q)
        self.assertEqual(calls[0]['output_config']['format']['type'], 'json_schema')
        self.assertNotIn('minimum', calls[0]['output_config']['format']['schema']['properties']['confidence'])
        self.assertNotIn('test-credential', str(result))
        with self.assertRaises(ValueError):
            p.ClaudeProvider(transport=lambda *a: {'stop_reason': 'max_tokens'})('', 'evidence', Q)

    def test_invalid_confidence_cannot_pass(self):
        for value in [float('nan'), float('inf'), -.1, 1.1, True, '0.9', None]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                p.checked_answer({'choice': 'a', 'confidence': value}, Q['criteria'])

    @patch.dict(os.environ, {'OPENAI_API_KEY': 'test-credential'})
    def test_openai_strict_schema_store_and_reasoning(self):
        calls = []
        def fake(url, body, key):
            calls.append((url, body))
            return {'status': 'completed', 'model': 'resolved-openai', 'usage': {'input_tokens': 10},
                    'output': [{'type': 'message', 'content': [{'type': 'output_text', 'text': '{"choice":"a","confidence":0.8}'}]}]}
        result = p.OpenAIProvider(transport=fake)('', 'evidence', Q)
        self.assertFalse(calls[0][1]['store'])
        self.assertTrue(calls[0][1]['text']['format']['strict'])
        self.assertEqual(calls[0][1]['reasoning']['effort'], 'medium')
        self.assertNotIn('test-credential', str(result))

    @patch.dict(os.environ, {'TYPESAFE_API_KEY': 'test-credential'})
    def test_jev_pinned_version_and_raw_distribution(self):
        calls = []
        def fake(url, body, key):
            calls.append(body)
            return {'model': 'jev-1.13.0', 'answers': {'q': {'choice': 'a', 'probabilities': {'a': .8, 'b': .2}, 'confidence': .6}}, 'usage': {'input_tokens': 12}}
        result = p.JevProvider(transport=fake)('', 'evidence', Q)
        self.assertEqual(calls[0]['model'], 'jev-1.13.0')
        self.assertEqual(result['answers']['q']['probabilities']['a'], .8)
        self.assertNotIn('test-credential', str(result))

    def test_failed_or_refused_openai_is_unreadable(self):
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'test'}):
            for status in ['incomplete', 'failed']:
                with self.assertRaises(ValueError):
                    p.OpenAIProvider(transport=lambda *a: {'status': status})('', 'evidence', Q)

    def test_cascade_retains_primary_and_routes_only_below_threshold(self):
        def primary(*a): return {'model': 'primary', 'answers': {'q': {'choice': 'a', 'confidence': .4}}}
        def fallback(*a): return {'model': 'fallback', 'answers': {'q': {'choice': 'b', 'confidence': .8}}}
        r = p.CascadeProvider(primary, fallback, .7)('', 'evidence', Q)
        self.assertEqual(r['model'], 'fallback')
        self.assertEqual(r['routing']['primary_response']['model'], 'primary')
        self.assertTrue(r['routing']['fallback_used'])


if __name__ == '__main__':
    unittest.main()
