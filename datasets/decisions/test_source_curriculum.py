#!/usr/bin/env python3
"""Sampling, target separation and byte-identical held-out data checks."""
from collections import Counter
import json
from pathlib import Path
import random
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0,str(HERE));sys.path.insert(0,str(HERE.parents[1]/'laya_variant'))
import build
import source_curriculum as c
import train


class SourceTraining(unittest.TestCase):
    def test_macro_selection_does_not_follow_majority_frequency(self):
        import torch
        from types import SimpleNamespace
        class Fixed(torch.nn.Module):
            def forward(self,input_ids,*args,**kwargs):
                return torch.tensor([[3.,0.,0.,0.]]).repeat(input_ids.shape[0],1),None
        groups=[]
        for label in [0]*9+[1]:
            groups.append([{'ids':[1],'markers':[0,0,0,0],'qtype':0,
                            'target':[float(i==label) for i in range(4)],'label':label}])
        agent=SimpleNamespace(model=Fixed(),device='cpu',tok=SimpleNamespace(pad_token_id=0))
        micro,_=train.evaluate_loss(agent,groups,True,macro=False,objective='cross-entropy')
        macro,_=train.evaluate_loss(agent,groups,True,macro=True,objective='cross-entropy')
        losses=-torch.log_softmax(torch.tensor([3.,0.,0.,0.]),0)
        self.assertAlmostEqual(micro,float(.9*losses[0]+.1*losses[1]),places=6)
        self.assertAlmostEqual(macro,float((losses[0]+losses[1])/2),places=6)
        self.assertGreater(macro,micro)

    def test_cross_entropy_has_gradient_for_extremely_unlikely_target(self):
        import torch
        class Fixed(torch.nn.Module):
            def __init__(self):super().__init__();self.logits=torch.nn.Parameter(torch.tensor([[30.,-30.]]))
            def forward(self,*args,**kwargs):return self.logits,None
        model=Fixed()
        b={'input_ids':torch.ones(1,1,dtype=torch.long),'attention_mask':torch.ones(1,1),
           'marker_pos':torch.tensor([[0,0]]),'marker_mask':torch.ones(1,2),
           'qtype':torch.zeros(1,dtype=torch.long),'target':torch.tensor([[0.,1.]]),'label':torch.tensor([1])}
        loss,_=train.step_loss(model,b,'cpu',True,objective='cross-entropy')
        loss.backward()
        self.assertGreater(loss.item(),50)
        self.assertLess(model.logits.grad[0,1].item(),-.99)

    def test_balanced_draws_and_rare_class_coverage(self):
        groups = [[{'label':k,'row':f'{k}:{i}'}] for k,n in ((0,1),(1,4),(2,7),(3,20)) for i in range(n)]
        indices = train.sample_indices(groups,random.Random(19),True,360)
        self.assertEqual(Counter(groups[i][0]['label'] for i in indices),{0:90,1:90,2:90,3:90})
        self.assertEqual(indices,train.sample_indices(groups,random.Random(19),True,360))
        self.assertEqual(len(set(indices)),len(groups))
        with self.assertRaises(ValueError):train.sample_indices(groups,random.Random(19),True,3)
        with self.assertRaises(ValueError):train.sample_indices([[{'label':0},{'label':1}]],random.Random(19),True,4)

    def test_generated_label_contract_and_state_does_not_read_private_targets(self):
        catalog=json.loads((build.ROOT/'controls/catalog.json').read_text())['controls']
        profiles=json.loads((HERE/'source_profiles.json').read_text())
        ref={'record_id':'fixture:1','source_family':'fixture:family','description':'A source authored static control description.',
             'record_type':'admission_policy','source':{'license':'Apache-2.0','name':'fixture'},'content_sha256':'fixture-only'}
        selected={k:[ref] for k in profiles}
        rows,_,_=c.source_rows(selected,profiles,catalog)
        for r in rows:
            key=json.loads(r['state'])['candidate']['key'];label=r['labels']['q']
            if label in ('recommend','review'):self.assertIsNotNone(catalog[key]['implementation'])
            if label=='handoff':self.assertIsNone(catalog[key]['implementation'])
            self.assertEqual(set(json.loads(r['state'])),{'operator_intent','available_evidence','operational_constraints','candidate'})
            self.assertFalse(r['independent_expert_label'])

    def test_balance_rejects_insufficient_real_rows(self):
        with self.assertRaises(ValueError):c.balanced_selection([],[],256,19)

    def test_reference_masking_keeps_labels_and_evaluation_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);data=root/'data';build.build(data)
            rows=[json.loads(l) for l in (data/'train.jsonl').read_text().splitlines()]
            r=rows[0];r['source_record_id']='fixture'
            visible=json.loads(r['state']);visible['available_evidence']+='\nStatic reference context, not runtime evidence or authorization: Static source words'
            r['state']=json.dumps(visible,ensure_ascii=False,sort_keys=True)
            build.write_jsonl(data/'train.jsonl',rows)
            c.mask_reference(data,root/'masked')
            masked=[json.loads(l) for l in (root/'masked/train.jsonl').read_text().splitlines()]
            self.assertEqual([r['labels'] for r in rows],[r['labels'] for r in masked])
            self.assertNotIn('Static source words',masked[0]['state'])
            for name in ('dev.jsonl','cal.jsonl','test_authored.jsonl','questions.json'):
                self.assertEqual((data/name).read_bytes(),(root/'masked'/name).read_bytes())


if __name__=='__main__':unittest.main()
