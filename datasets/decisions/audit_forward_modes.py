#!/usr/bin/env python3
"""Check native Laya logits across gradient/fast-path modes, using training only."""
import argparse
import json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parents[1]/'laya_variant'))
import lv
from diagnose_optimization import head_forward
from build import digest

if __name__=='__main__':
    import torch
    from laya.common import collate_items
    ap=argparse.ArgumentParser(description=__doc__)
    for k in ('model','data','out'):ap.add_argument('--'+k,type=Path,required=True)
    a=ap.parse_args();agent=lv.load_agent(str(a.model),device='mps');agent.model.eval()
    rows=lv.load_rows(a.data/'train.jsonl',['guardrail_candidate'])[:8]
    qs=json.loads((a.data/'questions.json').read_text())
    groups=lv.encode_rows(agent,rows,'labels_ab',question_sets=qs)
    b={k:v.to(agent.device) if hasattr(v,'to') else v for k,v in collate_items(groups,agent.tok.pad_token_id).items()}
    with torch.no_grad():h=agent.model.encoder(input_ids=b['input_ids'],attention_mask=b['attention_mask']).last_hidden_state
    values={}
    for fast in (True,False):
        torch.backends.mha.set_fastpath_enabled(fast)
        for grad in (True,False):
            with torch.set_grad_enabled(grad):
                logits=head_forward(agent.model,h,b['attention_mask'],b['marker_pos'],b['marker_mask'],b['qtype'])
            values[f'fast={fast},grad={grad}']=logits.detach().cpu()
            del logits
    base=values['fast=False,grad=True']
    comparisons={k:{'max_logit_difference':float((v-base).abs().max()),'argmax_flips':int((v.argmax(-1)!=base.argmax(-1)).sum()),'logits':v.tolist()} for k,v in values.items()}
    report={'checkpoint_sha256':digest(a.model/'model.safetensors'),'scope':'Eight original training rows, no parameter updates; isolate head fast-path behavior on identical frozen encoder features','comparisons':comparisons}
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
