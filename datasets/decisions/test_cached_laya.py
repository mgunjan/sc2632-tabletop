import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from train_cached_laya import cached_batch,fit_gate,materialize
from diagnose_optimization import head_forward


class CachedNativeTests(unittest.TestCase):
    def model(self):
        import torch
        from types import SimpleNamespace
        from laya.common import DecisionModel
        class Encoder(torch.nn.Module):
            def __init__(self):
                super().__init__();self.config=SimpleNamespace(hidden_size=64);self.embedding=torch.nn.Embedding(32,64)
            def forward(self,input_ids,attention_mask):return SimpleNamespace(last_hidden_state=self.embedding(input_ids))
        torch.manual_seed(19);model=DecisionModel(Encoder(),head_layers=2);model.eval();return model

    def test_cached_logits_and_padding_match_native_forward(self):
        import numpy as np
        import torch
        model=self.model();ids=torch.tensor([[1,2,3,4,5,0],[6,7,8,9,10,11]])
        mask=torch.tensor([[1,1,1,1,1,0],[1,1,1,1,1,1]])
        markers=torch.tensor([[0,1,2,3]]*2);valid=torch.ones_like(markers,dtype=torch.bool);qtype=torch.zeros(2,dtype=torch.long)
        with torch.no_grad():
            h=model.encoder(ids,mask).last_hidden_state;native,_=model(ids,mask,markers,valid,qtype)
            bank=h.numpy().copy();bank[0,5]=10000
            meta={'lengths':[5,6],'markers':markers.tolist(),'qtypes':[0,0],'labels':[0,1]}
            b=cached_batch(bank,meta,[0,1],'cpu');cached=head_forward(model,*b[:5])
        self.assertTrue(torch.allclose(native,cached,atol=1e-5))

    def test_accumulated_gradients_equal_effective_batch(self):
        import torch
        a=self.model();b=copy.deepcopy(a)
        h=torch.randn(4,6,64);attention=torch.ones(4,6,dtype=torch.bool)
        markers=torch.tensor([[0,1,2,3]]*4);valid=torch.ones_like(markers,dtype=torch.bool);qtype=torch.zeros(4,dtype=torch.long)
        labels=torch.arange(4)
        torch.nn.functional.cross_entropy(head_forward(a,h,attention,markers,valid,qtype),labels).backward()
        for i in range(4):
            loss=torch.nn.functional.cross_entropy(head_forward(b,h[i:i+1],attention[i:i+1],markers[i:i+1],valid[i:i+1],qtype[i:i+1]),labels[i:i+1])/4
            loss.backward()
        for (name,p),(_,q) in zip(a.named_parameters(),b.named_parameters()):
            if p.grad is not None:self.assertTrue(torch.allclose(p.grad,q.grad,atol=1e-5),name)

    def test_fitting_gate_rejects_majority_only_accuracy(self):
        self.assertFalse(fit_gate({'accuracy':.999,'recall_by_disposition':{'recommend':0,'review':0,'handoff':0,'exclude':1}}))
        self.assertTrue(fit_gate({'accuracy':.999,'recall_by_disposition':{k:.99 for k in ('recommend','review','handoff','exclude')}}))

    def test_materialization_preserves_encoder_and_uses_native_format(self):
        import torch
        from safetensors.torch import load_file,save_file
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);base=root/'base';base.mkdir()
            for sub in ('encoder','tokenizer'):
                (base/sub).mkdir();(base/sub/'config.json').write_text('{}')
            (base/'rl_agent_config.json').write_text(json.dumps({'encoder':'old','temperature_by_options':{'4':9}}))
            save_file({'encoder.w':torch.tensor([1.]),'scorer.w':torch.tensor([2.])},str(base/'model.safetensors'))
            save_file({'scorer.w':torch.tensor([5.])},str(root/'head.safetensors'))
            materialize(base,root/'head.safetensors',root/'out',{'freeze_encoder':True})
            weights=load_file(str(root/'out/model.safetensors'))
            self.assertEqual(weights['encoder.w'].item(),1.)
            self.assertEqual(weights['scorer.w'].item(),5.)
            cfg=json.loads((root/'out/rl_agent_config.json').read_text())
            self.assertNotIn('temperature_by_options',cfg)
            self.assertEqual(cfg['temperature'],[1.,1.,1.])


if __name__=='__main__':unittest.main()
