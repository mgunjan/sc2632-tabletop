import json
from pathlib import Path
import sys
import tempfile
import unittest
from collections import Counter, defaultdict

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1]/'laya_variant'))
import build
import repair_curriculum
import train
import hierarchical


class RepairTests(unittest.TestCase):
    def test_hierarchy_relevance_cannot_be_changed_by_evidence_or_catalog_prose(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);build.build(root/'data')
            rows=[json.loads(l) for l in (root/'data/train.jsonl').read_text().splitlines()]
            predict,_=hierarchical.fit(rows)
            s=json.loads(rows[0]['state']);_,p=predict(json.dumps(s))
            s['available_evidence']='Different evidence with registry, privilege and token words.'
            s['candidate']['objective']='Irrelevant catalog prose should not request a control.'
            _,changed=predict(json.dumps(s))
            self.assertEqual(p['exclude'],changed['exclude'])
            s['candidate']['implementation']=None
            _,hand=predict(json.dumps(s))
            self.assertEqual(hand['recommend'],0.)
            self.assertEqual(hand['review'],0.)
            self.assertAlmostEqual(sum(hand.values()),1.)
            s['candidate']['key']='unknown-control'
            with self.assertRaises(ValueError):predict(json.dumps(s))

    def test_complete_candidates_preserved_originals_and_frozen_evaluation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            build.build(root/'frozen')
            manifest=repair_curriculum.build(root/'frozen', root/'repaired')
            self.assertEqual(manifest['cases'],sum(s['cases'] for s in manifest['splits'].values()))
            self.assertEqual(manifest['candidate_decisions'],sum(s['decisions'] for s in manifest['splits'].values()))
            old = [json.loads(l) for l in (root/'frozen/train.jsonl').read_text().splitlines()]
            rows = [json.loads(l) for l in (root/'repaired/train.jsonl').read_text().splitlines()]
            by_id = {r['id']:r for r in rows}
            for row in old:
                self.assertEqual(by_id[row['id']], row)
            for name in ('dev.jsonl','cal.jsonl','test_authored.jsonl','questions.json'):
                self.assertEqual((root/'frozen'/name).read_bytes(), (root/'repaired'/name).read_bytes())
            cases = defaultdict(list)
            for r in rows:
                cases[r['case_id']].append(r)
                self.assertNotIn('Static reference context', r['state'])
            self.assertTrue(all(len(rs)==10 for rs in cases.values()))
            for rs in cases.values():
                if rs[0]['case_id'].endswith(':negated'):
                    self.assertEqual({r['labels']['q'] for r in rs}, {'exclude'})
            counts = Counter(r['labels']['q'] for r in rows)
            self.assertGreater(counts['exclude']/len(rows), .8)
            self.assertEqual(len({r['state'] for r in rows}), len(rows))

    def test_selection_uses_complete_plans_and_counts_dangerous_errors(self):
        rows = [{'task':'guardrail_candidate','case_id':str(i//10),'labels':{'q': 'recommend' if i%10==0 else 'exclude'}} for i in range(20)]
        exact = [0 if i%10==0 else 3 for i in range(20)]
        key, stats = train.plan_selection(rows,exact,1.)
        self.assertEqual(stats['exact_plans'],2)
        bad = list(exact); bad[1]=0; bad[10]=3
        key_bad, stats_bad = train.plan_selection(rows,bad,.1)
        self.assertLess(key,key_bad)
        self.assertEqual(stats_bad['wrong_recommendations'],1)
        self.assertEqual(stats_bad['missed_required'],1)
        with self.assertRaises(ValueError):train.plan_selection(rows[:-1],bad[:-1],.1)


if __name__ == '__main__':unittest.main()
