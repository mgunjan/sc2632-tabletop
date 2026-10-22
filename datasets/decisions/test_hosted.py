#!/usr/bin/env python3
"""Offline provider tests; simulated responses never count as model evidence."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE))
import hosted
import build


class HostedContract(unittest.TestCase):
    def response(self,**kwargs):
        raw={'id':'unit-response','model':'claude-opus-5-5','stop_reason':'end_turn',
             'usage':{'input_tokens':100,'output_tokens':50},
             'content':[{'type':'text','text':json.dumps({'probabilities':{'recommend':.1,'review':.7,'handoff':.1,'exclude':.1}})}]}
        raw.update(kwargs);return raw

    def test_real_usage_is_counted_and_credential_is_not_in_payload(self):
        observed=[]
        def fake(body):observed.append(body);return self.response()
        p=hosted.Claude('unit-test-credential-not-real','unit-workspace','claude-opus-5-5',transport=fake)
        choice,_=p.predict('fictional state')
        self.assertEqual(choice,'review');self.assertEqual(p.meta['usage']['calls'],1)
        self.assertAlmostEqual(p.meta['usage']['known_estimated_api_usd'],.0014)
        self.assertNotIn('unit-test-credential-not-real',json.dumps(observed))
        self.assertNotIn('unit-workspace',json.dumps(p.meta))

    def test_budget_stops_before_transport(self):
        calls=[]
        p=hosted.Claude('test','workspace','claude-opus-5-5',max_usd=.000001,transport=lambda body:calls.append(body))
        with self.assertRaises(RuntimeError):p.predict('example')
        self.assertFalse(calls)

    def test_truncation_retains_charged_usage(self):
        p=hosted.Claude('test','workspace','claude-opus-5-5',transport=lambda body:self.response(stop_reason='max_tokens'))
        with self.assertRaises(ValueError):p.predict('example')
        self.assertGreater(p.meta['usage']['known_estimated_api_usd'],0)

    def test_invalid_probabilities_are_rejected(self):
        raw=self.response(content=[{'type':'text','text':json.dumps({'probabilities':{'recommend':2,'review':0,'handoff':0,'exclude':0}})}])
        p=hosted.Claude('test','workspace','claude-opus-5-5',transport=lambda body:raw)
        with self.assertRaises(ValueError):p.predict('example')

    def test_missing_usage_reserves_unknown_cost(self):
        p=hosted.Claude('test','workspace','claude-opus-5-5',transport=lambda body:self.response(usage={}))
        with self.assertRaises(ValueError):p.predict('example')
        self.assertEqual(p.meta['usage']['unknown_cost_attempts'],1)
        self.assertGreater(p.meta['usage']['conservative_upper_api_usd'],0)

    def test_preview_contains_only_model_inputs_and_no_answers(self):
        with tempfile.TemporaryDirectory() as tmp:
            data=Path(tmp)/'data';build.build(data)
            out=Path(tmp)/'preview';m=hosted.export_preview(data,out)
            rows=[json.loads(l) for l in (out/'OUTBOUND-PREVIEW.jsonl').read_text().splitlines()]
            self.assertEqual(len(rows),m['requests'])
            for r in rows:
                body=r['outbound_body'];self.assertNotIn('headers',body)
                user=json.loads(body['messages'][0]['content'])
                self.assertEqual(set(user),{'state','question'})
                self.assertEqual(set(json.loads(user['state'])),{'operator_intent','available_evidence','operational_constraints','candidate'})


if __name__=='__main__':unittest.main()
