#!/usr/bin/env python3
"""Training-only gradient audit and controlled same-control fitting diagnostics."""
import argparse
from collections import Counter
import json
from pathlib import Path
import random
import sys
import time

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parents[1]/'laya_variant'))
import lv
import train
from build import digest


def head_forward(model,h,attention,markers,marker_mask,qtype):
    import torch
    h=h+model.type_emb(qtype)[:,None,:]
    if model.head is not None:
        for layer in model.head.layers:h=layer(h,src_key_padding_mask=~attention.bool())
    m=torch.gather(h,1,markers[:,:,None].expand(-1,-1,h.shape[-1]))
    return model.scorer(m).squeeze(-1).float().masked_fill(~marker_mask,-1e4)


def main(a):
    import torch
    from laya.common import collate_items
    torch.manual_seed(19)
    a.out.mkdir(parents=True,exist_ok=False)
    (a.out/'EXECUTED.py.txt').write_bytes(Path(__file__).read_bytes())
    agent=lv.load_agent(str(a.model),device='mps');model=agent.model
    rows=lv.load_rows(a.data/'train.jsonl',['guardrail_candidate'])
    # Select contrasting labels for the SAME candidate, from training only.
    cases=[('egress_profile',lab) for lab in ('recommend','review','exclude')]
    cases += [('restrict_registry',lab) for lab in ('recommend','review','exclude')]
    cases += [('restrict_api_access',lab) for lab in ('handoff','exclude')]
    chosen=[next(r for r in rows if json.loads(r['state'])['candidate']['key']==key and r['labels']['q']==lab) for key,lab in cases]
    qs=json.loads((a.data/'questions.json').read_text())
    groups=lv.encode_rows(agent,chosen,'labels_ab',question_sets=qs)
    batch=collate_items(groups,agent.tok.pad_token_id)
    dev=agent.device
    b={k:v.to(dev) if hasattr(v,'to') else v for k,v in batch.items()}
    params=train.configure_trainable(model,encoder_last_layers=2)
    model.train();loss,_=train.step_loss(model,batch,dev,False,objective='cross-entropy')
    loss.backward()
    gradients={}
    for name,p in model.named_parameters():
        if p.requires_grad:
            prefix='.'.join(name.split('.')[:3]) if name.startswith('encoder.layers') else name.split('.')[0]
            d=gradients.setdefault(prefix,{'parameters':0,'parameters_with_gradient':0,'gradient_squared_norm':0.,'parameter_squared_norm':0.})
            d['parameters']+=p.numel();d['parameter_squared_norm']+=float(p.detach().float().square().sum().cpu())
            if p.grad is not None:
                d['parameters_with_gradient']+=p.numel();d['gradient_squared_norm']+=float(p.grad.detach().float().square().sum().cpu())
    model.zero_grad(set_to_none=True);model.eval()
    with torch.no_grad():
        h=model.encoder(input_ids=b['input_ids'],attention_mask=b['attention_mask']).last_hidden_state.detach()
        direct,_=model(b['input_ids'],b['attention_mask'],b['marker_pos'],b['marker_mask'],b['qtype'])
        cached=head_forward(model,h,b['attention_mask'],b['marker_pos'],b['marker_mask'],b['qtype'])
    parity=float((direct-cached).abs().max().cpu())
    if parity>1e-5:raise ValueError('Frozen encoder cache did not reproduce native logits')
    base={k:p.detach().clone() for k,p in model.named_parameters() if not k.startswith('encoder.')}
    for p in model.encoder.parameters():p.requires_grad_(False)
    head_params=[p for k,p in model.named_parameters() if not k.startswith('encoder.') and p.requires_grad]
    report={'model_sha256':digest(a.model/'model.safetensors'),'dataset_manifest_sha256':digest(a.data/'MANIFEST.json'),
        'ids':[r['id'] for r in chosen],'labels':[r['labels']['q'] for r in chosen],
        'gradient_audit':gradients,'encoder_gradient_checkpointing':model.encoder.is_gradient_checkpointing,
        'cache_max_logit_difference':parity,'experiments':[],
        'qualification':'Eight TRAINING inputs, including same-candidate counterfactuals; deliberate overfit diagnostic, never a test result'}
    (a.out/'DIAGNOSTIC.json').write_text(json.dumps(report,indent=2)+'\n')
    for lr in (1e-4,1e-3):
        with torch.no_grad():
            for k,p in model.named_parameters():
                if k in base:p.copy_(base[k])
        # Fixed eval mode removes dropout for an optimization-only capacity check.
        model.eval();opt=torch.optim.AdamW(head_params,lr=lr,weight_decay=.01)
        history=[];start=time.perf_counter()
        for step in range(a.steps+1):
            logits=head_forward(model,h,b['attention_mask'],b['marker_pos'],b['marker_mask'],b['qtype'])
            loss=torch.nn.functional.cross_entropy(logits,b['label'])
            if step%25==0 or step==a.steps:
                acc=float((logits.argmax(-1)==b['label']).float().mean().cpu())
                history.append({'step':step,'loss':float(loss.detach().cpu()),'accuracy':acc})
                print(json.dumps({'lr':lr,**history[-1]}),flush=True)
            if step==a.steps:break
            opt.zero_grad(set_to_none=True);loss.backward();torch.nn.utils.clip_grad_norm_(head_params,1.);opt.step()
        report['experiments'].append({'head_lr':lr,'mode':'eval, gradients enabled; dropout disabled','history':history,'elapsed_seconds':time.perf_counter()-start})
        (a.out/'DIAGNOSTIC.json').write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    for k in ('model','data','out'):ap.add_argument('--'+k,type=Path,required=True)
    ap.add_argument('--steps',type=int,default=200)
    main(ap.parse_args())
