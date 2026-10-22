#!/usr/bin/env python3
"""Record selected-checkpoint train/dev fit and direct/runtime probability parity."""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys
import time

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parents[1]/'laya_variant'))
import lv
from build import DISPOSITIONS, QUESTION, digest, write_jsonl
from benchmark import load
from train import plan_selection


def diagnose(data, weights, out):
    import torch
    from laya.common import collate_items
    t=time.perf_counter();a=lv.load_agent(str(weights),device='mps');a.model.eval()
    result={'checkpoint_sha256':digest(weights/'model.safetensors'),'actual_device':str(a.device),
            'precision':'float32 direct forward; runtime comparison includes API probability rounding',
            'data_manifest_sha256':digest(data/'MANIFEST.json'),'splits':{},'runtime_parity':[]}
    qs=json.loads((data/'questions.json').read_text())
    for split in ('train','dev'):
        rows=load(data,split);groups=lv.encode_rows(a,rows,'labels_ab',question_sets=qs)
        records=[];losses=[];confusion=Counter();maxlen=0
        with torch.no_grad():
            for i in range(0,len(groups),16):
                sub=groups[i:i+16];batch=collate_items(sub,a.tok.pad_token_id)
                maxlen=max(maxlen,max(len(it['ids']) for grp in sub for it in grp))
                logits,_=a.model(batch['input_ids'].to(a.device),batch['attention_mask'].to(a.device),
                    batch['marker_pos'].to(a.device),batch['marker_mask'].to(a.device),batch['qtype'].to(a.device))
                logp=torch.log_softmax(logits.float(),-1).cpu();p=logp.exp().tolist()
                for j,(r,probs) in enumerate(zip(rows[i:i+16],p)):
                    y=r['labels']['q'];pred=DISPOSITIONS[max(range(4),key=lambda k:probs[k])]
                    loss=-float(logp[j,DISPOSITIONS.index(y)]);losses.append(loss);confusion[y+'->'+pred]+=1
                    records.append({'id':r['id'],'case_id':r['case_id'],'family_id':r['family_id'],
                        'state_sha256':digest_state(r['state']),'expected':y,'prediction':pred,
                        'probabilities':dict(zip(DISPOSITIONS,probs)),'cross_entropy':loss})
        predictions=[DISPOSITIONS.index(r['prediction']) for r in records]
        _,plan=plan_selection(rows,predictions,sum(losses)/len(losses))
        write_jsonl(out/(split+'-fit.jsonl'),records)
        recalls={y:sum(r['prediction']==y for r in records if r['expected']==y)/sum(r['expected']==y for r in records) for y in DISPOSITIONS}
        result['splits'][split]={'rows':len(rows),'accuracy':sum(r['expected']==r['prediction'] for r in records)/len(rows),
            'cross_entropy':sum(losses)/len(losses),'recall_by_disposition':recalls,'confusion':dict(confusion),
            'max_encoded_length':maxlen,**plan}
        if split=='dev':
            for y in DISPOSITIONS:
                idx=next(i for i,r in enumerate(records) if r['expected']==y)
                api=a.predict(rows[idx]['state'],QUESTION)['answers']['q']
                delta=max(abs(records[idx]['probabilities'][k]-api['probabilities'][k]) for k in DISPOSITIONS)
                if api['choice']!=records[idx]['prediction'] or delta>.001:
                    raise ValueError('Training/inference parity failed')
                result['runtime_parity'].append({'id':rows[idx]['id'],'expected':y,'choice':api['choice'],'max_probability_difference':delta})
    result['elapsed_seconds']=time.perf_counter()-t
    (out/'SELECTED-FIT.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


def digest_state(s):
    import hashlib
    return hashlib.sha256(s.encode()).hexdigest()


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    for k in ('data','weights','out'):ap.add_argument('--'+k,type=Path,required=True)
    a=ap.parse_args();print(json.dumps(diagnose(a.data,a.weights,a.out),indent=2))
