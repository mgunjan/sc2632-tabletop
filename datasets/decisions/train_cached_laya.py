#!/usr/bin/env python3
"""Fit the unchanged native Laya head with cached frozen-encoder features.

Training/dev only. No architecture, task, labels, probability masks or test access
changes. A checkpoint must fit ALL four training classes before dev selection.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import random
import shutil
import sys
import time

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parents[1]/'laya_variant'))
import lv
from build import DISPOSITIONS,digest,write_jsonl
from diagnose_optimization import head_forward
from train import plan_selection


def cache_split(agent,rows,questions,folder,batch_size=1):
    import numpy as np
    import torch
    from laya.common import collate_items
    groups=lv.encode_rows(agent,rows,'labels_ab',question_sets=questions)
    lengths=[len(g[0]['ids']) for g in groups];width=agent.model.encoder.config.hidden_size
    folder.mkdir(parents=True,exist_ok=False)
    bank=np.lib.format.open_memmap(folder/'hidden.npy',mode='w+',dtype='float32',shape=(len(rows),max(lengths),width))
    agent.model.eval();start=time.perf_counter()
    with torch.no_grad():
        for start_row in range(0,len(groups),batch_size):
            batch=collate_items(groups[start_row:start_row+batch_size],agent.tok.pad_token_id)
            h=agent.model.encoder(input_ids=batch['input_ids'].to(agent.device),attention_mask=batch['attention_mask'].to(agent.device)).last_hidden_state.cpu().numpy()
            for j in range(h.shape[0]):bank[start_row+j,:lengths[start_row+j]]=h[j,:lengths[start_row+j]]
            if start_row%160==0:print('cached',folder.name,start_row,'/',len(rows),flush=True)
    bank.flush()
    metadata={'lengths':lengths,'markers':[g[0]['markers'] for g in groups],'qtypes':[g[0]['qtype'] for g in groups],
        'labels':[g[0]['label'] for g in groups],'ids':[r['id'] for r in rows],
        'state_sha256':[hashlib.sha256(r['state'].encode()).hexdigest() for r in rows],
        'elapsed_seconds':time.perf_counter()-start,'encoder_batch_size':batch_size}
    (folder/'INDEX.json').write_text(json.dumps(metadata,indent=2)+'\n')
    return bank,metadata,groups


def cached_batch(bank,meta,indices,device):
    import numpy as np
    import torch
    length=max(meta['lengths'][i] for i in indices)
    h=torch.from_numpy(np.array(bank[indices,:length],copy=True)).to(device)
    attention=torch.arange(length,device=device)[None,:]<torch.tensor([meta['lengths'][i] for i in indices],device=device)[:,None]
    markers=torch.tensor([meta['markers'][i] for i in indices],device=device)
    qtype=torch.tensor([meta['qtypes'][i] for i in indices],device=device)
    labels=torch.tensor([meta['labels'][i] for i in indices],device=device)
    return h,attention,markers,torch.ones_like(markers,dtype=torch.bool),qtype,labels


def evaluate(model,bank,meta,rows,device,bs=8):
    if bs < 1: raise ValueError('Evaluation batch size must be positive')
    import torch
    choices=[];losses=[];records=[];model.eval()
    with torch.no_grad():
        for i in range(0,len(rows),bs):
            indices=list(range(i,min(i+bs,len(rows))))
            h,attention,markers,mask,qtype,labels=cached_batch(bank,meta,indices,device)
            logits=head_forward(model,h,attention,markers,mask,qtype)
            p=torch.softmax(logits,-1).cpu().tolist();ls=torch.nn.functional.cross_entropy(logits,labels,reduction='none').cpu().tolist()
            for j,idx in enumerate(indices):
                pred=max(range(4),key=lambda k:p[j][k]);choices.append(pred);losses.append(ls[j])
                records.append({'id':rows[idx]['id'],'case_id':rows[idx]['case_id'],'family_id':rows[idx]['family_id'],
                    'expected':rows[idx]['labels']['q'],'prediction':DISPOSITIONS[pred],
                    'probabilities':dict(zip(DISPOSITIONS,p[j])),'cross_entropy':ls[j],
                    'state_sha256':meta['state_sha256'][idx]})
    loss=sum(losses)/len(losses);_,plans=plan_selection(rows,choices,loss)
    recalls={k:sum(r['prediction']==k for r in records if r['expected']==k)/sum(r['expected']==k for r in records) for k in DISPOSITIONS}
    metrics={'loss':loss,'accuracy':sum(r['prediction']==r['expected'] for r in records)/len(records),'recall_by_disposition':recalls,**plans}
    return metrics,records


def fit_gate(metrics):
    return metrics['accuracy']>=.995 and min(metrics['recall_by_disposition'].values())>=.98


def materialize(base,head,out,meta):
    from safetensors.torch import load_file,save_file
    out.mkdir(parents=True,exist_ok=False)
    sd=load_file(str(base/'model.safetensors'),device='cpu');updated=load_file(str(head),device='cpu')
    if set(updated)-set(sd):raise ValueError('Unknown native-head parameter')
    sd.update(updated);save_file(sd,str(out/'model.safetensors'))
    for sub in ('encoder','tokenizer'):shutil.copytree(base/sub,out/sub)
    cfg=json.loads((base/'rl_agent_config.json').read_text());cfg['encoder']=str((out/'encoder').resolve())
    cfg['temperature']=[1.,1.,1.];cfg.pop('temperature_by_options',None);cfg['trustfall_variant']=meta
    (out/'rl_agent_config.json').write_text(json.dumps(cfg,indent=2)+'\n')


def main(a):
    import numpy as np
    import torch
    from laya.common import collate_items
    from safetensors.torch import save_file
    a.out.mkdir(parents=True,exist_ok=False);a.cache.mkdir(parents=True,exist_ok=False)
    if a.weights.exists():raise ValueError('Preserve earlier checkpoints')
    source=Path(__file__).read_bytes();(a.out/'TRAINER.py.txt').write_bytes(source)
    (a.out/'HEAD-FORWARD.py.txt').write_bytes((HERE/'diagnose_optimization.py').read_bytes())
    start=time.perf_counter();torch.manual_seed(19);rng=random.Random(19)
    manifest=json.loads((a.data/'MANIFEST.json').read_text())
    for name in ('train.jsonl','dev.jsonl','questions.json'):
        if digest(a.data/name)!=manifest['files'][name]['sha256']:raise ValueError('Changed frozen input: '+name)
    agent=lv.load_agent(str(a.base),device='mps');model=agent.model
    questions=json.loads((a.data/'questions.json').read_text())
    if tuple(questions['guardrail_candidate']['q']['criteria'])!=DISPOSITIONS:raise ValueError('Changed label order')
    rows={s:lv.load_rows(a.data/(s+'.jsonl'),['guardrail_candidate']) for s in ('train','dev')}
    banks={};indices={}
    for split in ('train','dev'):
        banks[split],indices[split],groups=cache_split(agent,rows[split],questions,a.cache/split,a.encoder_batch_size)
        if split=='train':
            # Compare the cache against the full unmodified native forward.
            batch=collate_items(groups[:8],agent.tok.pad_token_id)
            with torch.no_grad():
                full,_=model(batch['input_ids'].to(agent.device),batch['attention_mask'].to(agent.device),batch['marker_pos'].to(agent.device),batch['marker_mask'].to(agent.device),batch['qtype'].to(agent.device))
                b=cached_batch(banks[split],indices[split],list(range(8)),agent.device)
                cached=head_forward(model,*b[:5]);difference=float((full-cached).abs().max().cpu())
            if difference>1e-4:raise ValueError('Cache/native mismatch')
    # Release the 395M frozen encoder; its original bytes are retained on disk.
    model.encoder=None
    torch.mps.empty_cache()
    for p in model.parameters():p.requires_grad_(True)
    parameters=[p for name,p in model.named_parameters() if not name.startswith('act_head.')]
    opt=torch.optim.AdamW(parameters,lr=1e-4,weight_decay=.01)
    pools={label:[i for i,y in enumerate(indices['train']['labels']) if y==label] for label in range(4)}
    remaining={k:[] for k in pools};history=[];best=None;seen=Counter();draws=Counter();trained=0
    def choose():
        selected=[]
        # Every microbatch carries each disposition; shuffle label order, recycle
        # each class without replacement. Larger effective batch stabilizes updates.
        for label in range(4):
            if not remaining[label]:remaining[label]=rng.sample(pools[label],len(pools[label]))
            i=remaining[label].pop();selected.append(i);seen[i]+=1;draws[str(label)]+=1
        rng.shuffle(selected);return selected
    for update in range(a.updates+1):
        if update%a.evaluate_every==0 or update==a.updates:
            train_metrics,train_records=evaluate(model,banks['train'],indices['train'],rows['train'],agent.device)
            dev_metrics,dev_records=evaluate(model,banks['dev'],indices['dev'],rows['dev'],agent.device)
            passed=fit_gate(train_metrics)
            item={'update':update,'train':train_metrics,'dev':dev_metrics,'fit_gate':passed,'elapsed_seconds':time.perf_counter()-start}
            history.append(item);print(json.dumps(item),flush=True)
            a.out.joinpath('HISTORY.json').write_text(json.dumps(history,indent=2)+'\n')
            head=a.cache/f'head-{update}.safetensors'
            save_file({k:v.detach().cpu().contiguous() for k,v in model.state_dict().items() if not k.startswith('act_head.')},str(head))
            key=(-dev_metrics['exact_plans'],dev_metrics['development_error_cost'],dev_metrics['loss'])
            if passed and (best is None or key<best[0]):
                best=(key,update,head,train_metrics,dev_metrics)
                write_jsonl(a.out/'selected-train.jsonl',train_records);write_jsonl(a.out/'selected-dev.jsonl',dev_records)
        if update==a.updates:break
        model.eval() # Deliberately disable dropout; autograd stays enabled.
        opt.zero_grad(set_to_none=True)
        for _ in range(a.accumulate):
            selected=choose();b=cached_batch(banks['train'],indices['train'],selected,agent.device)
            logits=head_forward(model,*b[:5]);loss=torch.nn.functional.cross_entropy(logits,b[5])/a.accumulate
            loss.backward()
        torch.nn.utils.clip_grad_norm_(parameters,1.);opt.step();trained=update+1
        if trained%25==0:print('update',trained,'elapsed',round(time.perf_counter()-start,1),flush=True)
    receipt={'state':'FIT_GATE_PASSED' if best else 'FIT_GATE_FAILED','native_architecture_unchanged':True,'actual_device':str(agent.device),
        'source_checkpoint_sha256':digest(a.base/'model.safetensors'),'data_manifest_sha256':digest(a.data/'MANIFEST.json'),
        'question_sha256':digest(a.data/'questions.json'),'trainer_sha256':hashlib.sha256(source).hexdigest(),
        'cache_native_max_logit_difference':difference,'optimizer_updates':trained,'effective_batch_size':4*a.accumulate,
        'label_draw_counts':dict(draws),'unique_rows_seen':len(seen),'exposure_per_row':dict(Counter(seen.values())),
        'dropout':'disabled','optimizer':'AdamW','lr':1e-4,'weight_decay':.01,'lr_schedule':'constant until fitting gate; no early decay',
        'sampling':'Exactly one per class per microbatch, without replacement within class; original training rows/labels unchanged',
        'fit_gate':{'accuracy':.995,'minimum_per_class_recall':.98},'selected_update':best[1] if best else None,
        'elapsed_seconds':time.perf_counter()-start,'new_hosted_calls':0,'api_usd':0,
        'selection':'Among fit-gated checkpoints only: dev exact plans, dev error cost, dev cross-entropy; no cal/test access'}
    (a.out/'TRAINING-RUN.json').write_text(json.dumps(receipt,indent=2)+'\n')
    if best:
        meta={**receipt,'freeze_encoder':True,'base':str(a.base),'tasks':['guardrail_candidate'],'mode':'labels_ab',
              'selected_train_metrics':best[3],'selected_dev_metrics':best[4]}
        materialize(a.base,best[2],a.weights,meta)
        (a.out/'CHECKPOINT-CONFIG.json').write_bytes((a.weights/'rl_agent_config.json').read_bytes())
    else:raise SystemExit('No fitted checkpoint; do not open calibration/test or claim a repaired model')


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    for k in ('base','data','cache','weights','out'):ap.add_argument('--'+k,type=Path,required=True)
    ap.add_argument('--updates',type=int,default=750);ap.add_argument('--accumulate',type=int,default=4)
    ap.add_argument('--evaluate-every',type=int,default=100)
    ap.add_argument('--encoder-batch-size',type=int,default=1)
    main(ap.parse_args())
