#!/usr/bin/env python3
"""Integrity checks for leakage, counterfactual grouping and real encoder adaptation."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE));sys.path.insert(0,str(HERE.parents[1]/'laya_variant'))
import build


class DatasetIntegrity(unittest.TestCase):
    def run_build(self, folder):
        return build.build(Path(folder)/'data')

    def test_splits_and_target_separation(self):
        with tempfile.TemporaryDirectory() as tmp:
            m=self.run_build(tmp);out=Path(tmp)/'data';seen=set()
            for split in build.SPLITS:
                rows=[json.loads(l) for l in (out/f'{split}.jsonl').read_text().splitlines()]
                families={r['family_id'] for r in rows}
                self.assertFalse(seen & families);seen|=families
                self.assertEqual(set(r['labels']['q'] for r in rows),set(build.DISPOSITIONS))
                public=[json.loads(l) for l in (out/f'{split}.inputs.jsonl').read_text().splitlines()]
                self.assertEqual([r['id'] for r in public],[r['id'] for r in rows])
                for r in public:
                    self.assertNotIn('labels',r);self.assertNotIn('rationale',r)
                    visible=json.loads(r['state'])
                    self.assertEqual(set(visible),{'operator_intent','available_evidence','operational_constraints','candidate'})
                cases={r['case_id'] for r in rows}
                self.assertEqual(len(rows),10*len(cases))
            self.assertEqual(m['independent_reviewed_cases'],0)
            blind=[json.loads(l) for l in (out/'blind-review.jsonl').read_text().splitlines()]
            self.assertEqual(len(blind),m['splits']['test_authored']['cases'])
            for r in blind:
                self.assertEqual(r['decisions'],{});self.assertEqual(r['rationale'],'')

    def test_target_and_provenance_changes_cannot_alter_model_input(self):
        catalog=json.loads((HERE.parents[1]/'controls/catalog.json').read_text())['controls']
        case=json.loads((HERE/'scenarios.json').read_text())['families'][0]['cases'][0]
        other=copy.deepcopy(case);other.update(decisions={'process':'handoff'},rationale='SECRET LABEL',tags=['private'])
        self.assertEqual(build.state(case,'restrict_registry',catalog['restrict_registry']),
                         build.state(other,'restrict_registry',catalog['restrict_registry']))

    def test_duplicate_and_false_recommendation_rejected(self):
        original=json.loads((HERE/'scenarios.json').read_text())
        for corrupt in ('duplicate','nonrendered'):
            doc=copy.deepcopy(original)
            if corrupt=='duplicate':
                duplicate=copy.deepcopy(doc['families'][0]['cases'][0]);duplicate['id']='copy'
                doc['families'][1]['cases'].append(duplicate)
            else: doc['families'][0]['cases'][0]['decisions']['restrict_api_access']='recommend'
            with tempfile.TemporaryDirectory() as tmp:
                p=Path(tmp)/'bad.json';p.write_text(json.dumps(doc))
                with self.assertRaises(ValueError):build.build(Path(tmp)/'data',scenarios=p)

    def test_rebuild_is_deterministic_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            a=build.build(Path(tmp)/'a');b=build.build(Path(tmp)/'b')
            self.assertEqual(a,b)
            with self.assertRaises(ValueError):build.build(Path(tmp)/'a')


@unittest.skipUnless(importlib.util.find_spec('torch'),'torch unavailable')
class EncoderAdaptation(unittest.TestCase):
    def test_only_selected_encoder_blocks_change(self):
        import torch
        import train
        class Encoder(torch.nn.Module):
            def __init__(self):
                super().__init__();self.layers=torch.nn.ModuleList([torch.nn.Linear(3,3) for _ in range(3)])
                self.final_norm=torch.nn.LayerNorm(3)
            def forward(self,x):
                for layer in self.layers:x=torch.tanh(layer(x))
                return self.final_norm(x)
        class Model(torch.nn.Module):
            def __init__(self):super().__init__();self.encoder=Encoder();self.head=torch.nn.Linear(3,2)
            def forward(self,x):return self.head(self.encoder(x))
        torch.manual_seed(13);model=Model();before={n:p.detach().clone() for n,p in model.named_parameters()}
        params=train.configure_trainable(model,encoder_last_layers=1)
        opt=torch.optim.AdamW(params,lr=.01)
        loss=model(torch.randn(4,3)).square().mean();loss.backward();opt.step()
        for n,p in model.named_parameters():
            changed=not torch.equal(before[n],p)
            if n.startswith(('encoder.layers.0.','encoder.layers.1.')):self.assertFalse(changed,n)
            else:self.assertTrue(changed,n)
        with self.assertRaises(ValueError):train.configure_trainable(model,True,1)
        with self.assertRaises(ValueError):train.configure_trainable(model,encoder_last_layers=99)

    def test_head_only_has_no_trainable_encoder(self):
        import torch
        import train
        model=torch.nn.Module();model.encoder=torch.nn.Linear(3,3);model.head=torch.nn.Linear(3,2)
        train.configure_trainable(model,freeze_encoder=True)
        self.assertTrue(all(not p.requires_grad for p in model.encoder.parameters()))
        self.assertTrue(all(p.requires_grad for p in model.head.parameters()))


if __name__=='__main__':unittest.main()
