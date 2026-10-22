#!/usr/bin/env python3
"""Selection, paired comparison and training-accounting failure checks."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import report_retrain as r


class RetrainReport(unittest.TestCase):
    def test_selection_uses_selected_development_epoch(self):
        self.assertEqual(r.selected_loss({'selected_epoch':1,'history':[{'step':0,'cal_loss':.1},
            {'epoch':1,'cal_loss':.7},{'epoch':2,'cal_loss':.8}]}),.7)
        with self.assertRaises(ValueError):r.selected_loss({'selected_epoch':None})

    def test_paired_improvement_and_identity_check(self):
        before=[{'case_id':f'c{i}','family_id':f'f{i}','prediction':'exclude','expected':'recommend'} for i in range(5)]
        after=[{**x,'prediction':'recommend'} for x in before]
        result=r.paired_interval(before,after)
        self.assertEqual(result['delta_exact_plan_rate'],1)
        self.assertEqual(result['family_bootstrap_95_low'],1)
        self.assertEqual(result['family_bootstrap_95_high'],1)
        with self.assertRaises(ValueError):r.paired_interval(before,after[:-1])

    def test_draw_replay_rejects_fabricated_accounting(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)
            rows=[{'id':str(i),'state':'fixture-state-'+str(i),'labels':{'q':label}} for i,label in enumerate(r.DISPOSITIONS)]
            (p/'train.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in rows))
            (p/'MANIFEST.json').write_text('{}')
            receipt={'total_completed_steps':270,'label_draw_counts':{str(i):270 for i in range(4)},
                     'unique_training_assessments_seen':4}
            result=r.draws(p,receipt,90)
            self.assertEqual(result['unique_training_assessments_full_run'],4)
            self.assertFalse(result['source_record_ids_full_run'])
            with self.assertRaises(ValueError):r.draws(p,{**receipt,'unique_training_assessments_seen':5},90)


if __name__=='__main__':unittest.main()
