#!/usr/bin/env python3
"""Local two-stage baseline: intent relevance, then evidence sufficiency."""
import argparse
import json
from pathlib import Path
import sys
import time

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parents[1]/'laya_variant'))
import baselines
import benchmark as bench
from build import digest, write_jsonl


def fit(train):
    import numpy as np
    from scipy.sparse import hstack
    from sklearn.linear_model import LogisticRegression
    visible=[json.loads(r['state']) for r in train]
    keys=sorted({s['candidate']['key'] for s in visible})
    def conditioned(x, candidates):
        return hstack([x]+[x.multiply(np.asarray([k==key for k in candidates])[:,None]) for key in keys],format='csr')
    intent_features=baselines._features()
    x=intent_features.fit_transform([s['operator_intent'] for s in visible])
    relevance=LogisticRegression(C=4,class_weight='balanced',max_iter=2000).fit(
        conditioned(x,[s['candidate']['key'] for s in visible]),[r['labels']['q']!='exclude' for r in train])
    # Non-rendered requests have a deterministic handoff disposition by task
    # definition. Rendered requests require a learned sufficiency assessment.
    indices=[i for i,r in enumerate(train) if r['labels']['q'] in ('recommend','review')]
    evidence_features=baselines._features()
    def evidence_text(s):
        return json.dumps({k:s[k] for k in ('operator_intent','available_evidence','operational_constraints')},sort_keys=True)
    ex=evidence_features.fit_transform([evidence_text(visible[i]) for i in indices])
    sufficiency=LogisticRegression(C=4,class_weight='balanced',max_iter=2000).fit(
        conditioned(ex,[visible[i]['candidate']['key'] for i in indices]),[train[i]['labels']['q']=='recommend' for i in indices])
    def predict(state):
        s=json.loads(state);key=s['candidate']['key']
        if key not in keys:raise ValueError('Untrained candidate key')
        relevant=float(relevance.predict_proba(conditioned(intent_features.transform([s['operator_intent']]),[key]))[0,list(relevance.classes_).index(True)])
        p={'recommend':0.,'review':0.,'handoff':0.,'exclude':1-relevant}
        if s['candidate']['implementation'] is None:
            p['handoff']=relevant
        else:
            sufficient=float(sufficiency.predict_proba(conditioned(evidence_features.transform([evidence_text(s)]),[key]))[0,list(sufficiency.classes_).index(True)])
            p['recommend']=relevant*sufficient;p['review']=relevant*(1-sufficient)
        return max(p,key=p.get),p
    return predict,{'candidate':'hierarchical-tfidf','device':'cpu','adapter_sha256':digest(__file__),
        'relevance_features':'Operator intent only, shared plus candidate-conditioned TF-IDF',
        'disposition_features':'Relevant rendered training rows: intent/evidence/constraints, no static catalog text',
        'algorithm':'Two logistic regressions, C=4, class_weight=balanced; no parameter search',
        'training_rows':len(train),'relevant_rendered_rows':len(indices)}


def run(data,out,dev_only=False):
    data,out=Path(data),Path(out)
    if dev_only:
        out.mkdir(parents=True,exist_ok=False);t=time.perf_counter()
        predict,meta=fit(bench.load(data,'train'));records=[]
        for r in bench.load(data,'dev'):
            pred,p=predict(r['state']);records.append({'id':r['id'],'case_id':r['case_id'],'family_id':r['family_id'],
                'expected':r['labels']['q'],'prediction':pred,'probabilities':p,'confidence':max(p.values())})
        write_jsonl(out/'dev-predictions.jsonl',records)
        (out/'summary.json').write_text(json.dumps({'candidate':meta,'metrics':bench.quantify(records),
            'elapsed_seconds':time.perf_counter()-t,'scope':'Development only; no calibration/test files read'},indent=2)+'\n')
        print(json.dumps(bench.quantify(records),indent=2))
    else:
        original=bench.predictor
        def factory(kind,train,model=None,device='cpu'):
            return fit(train) if kind=='hierarchical-tfidf' else original(kind,train,model,device)
        bench.predictor=factory
        bench.run(data,out,'hierarchical-tfidf')
    (out/'ADAPTER.py.txt').write_bytes(Path(__file__).read_bytes())


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--data',type=Path,required=True);ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--dev-only',action='store_true')
    a=ap.parse_args();run(a.data,a.out,a.dev_only)
