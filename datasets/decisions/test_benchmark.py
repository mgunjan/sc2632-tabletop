#!/usr/bin/env python3
"""Failure-sensitive metrics and genuine blind-review validation."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE))
import benchmark as b
import build
import review


def row(case,expected,prediction,confidence=.9):
    return {'id':case+':x','case_id':case,'family_id':case.split(':')[0],
            'expected':expected,'prediction':prediction,'confidence':confidence,'probabilities':None}


class Metrics(unittest.TestCase):
    def test_majority_accuracy_does_not_hide_missing_controls(self):
        rows=[row('family:case','exclude','exclude') for _ in range(9)]+[row('family:case','recommend','exclude')]
        m=b.quantify(rows,.8)
        self.assertEqual(m['decision_accuracy'],.9);self.assertEqual(m['required_control_recall'],0)
        self.assertEqual(m['missed_required_controls'],1);self.assertEqual(m['exact_plan_cases'],0)
        self.assertEqual(m['routing']['wrong_accepted_cases'],1)

    def test_invalid_response_is_a_missed_requirement(self):
        m=b.quantify([row('f:c','review','INVALID',None)])
        self.assertEqual(m['invalid_decisions'],1);self.assertEqual(m['missed_required_controls'],1)
        self.assertEqual(m['required_control_recall'],0)

    def test_case_gating_catches_one_confident_wrong_control(self):
        rows=[row('f:c','recommend','recommend'),row('f:c','review','recommend')]
        m=b.quantify(rows,.8)
        self.assertEqual(m['wrong_recommendations'],1)
        self.assertEqual(m['routing']['wrong_accepted_cases'],1)
        t,_=b.route_threshold(rows)
        self.assertGreater(t,1)

    def test_temperature_fit_uses_supplied_calibration_pairs(self):
        p={'recommend':.99,'review':.003,'handoff':.003,'exclude':.004}
        T,m=b.fit_temperature([(p,'review')]*5)
        self.assertGreater(T,1);self.assertLess(m['nll_after'],m['nll_before'])
        with self.assertRaises(ValueError):b.normalized({'recommend':float('nan')})


class Reviews(unittest.TestCase):
    def test_blank_or_author_reviews_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            data=Path(tmp)/'data';build.build(data)
            rows=[json.loads(l) for l in (data/'blind-review.jsonl').read_text().splitlines()]
            p=Path(tmp)/'review.jsonl';build.write_jsonl(p,rows)
            with self.assertRaises(ValueError):review.validate_submission(p,rows)
            filled=copy.deepcopy(rows)
            controls=json.loads((HERE.parents[1]/'controls/catalog.json').read_text())['controls']
            for r in filled:
                r.update(reviewer_id='unit-test-simulated-reviewer',rationale='Test fixture only; never independent evidence',
                         authored_any_case_or_generator=True,decisions={k:'exclude' for k in controls})
            build.write_jsonl(p,filled)
            with self.assertRaises(ValueError):review.validate_submission(p,rows)

    def test_reviewer_cannot_change_case_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            data=Path(tmp)/'data';build.build(data)
            rows=[json.loads(l) for l in (data/'blind-review.jsonl').read_text().splitlines()]
            modified=copy.deepcopy(rows);modified[0]['evidence']='Different evidence'
            p=Path(tmp)/'review.jsonl';build.write_jsonl(p,modified)
            with self.assertRaises(ValueError):review.validate_submission(p,rows)


if __name__=='__main__':unittest.main()
