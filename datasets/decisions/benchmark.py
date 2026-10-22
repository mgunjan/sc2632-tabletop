#!/usr/bin/env python3
"""Compare identical control assessments; authored scores never qualify independent performance."""
import argparse
from collections import Counter,defaultdict
import hashlib
import json
import math
from pathlib import Path
import random
import re
import resource
import statistics
import sys
import time
import urllib.request

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
BENCHMARK_SOURCE=Path(__file__).read_bytes()
sys.path.insert(0,str(HERE));sys.path.insert(0,str(ROOT/'laya_variant'))
from build import DISPOSITIONS,QUESTION,digest,write_jsonl


def load(data,split):
    path=data/f'{split}.jsonl'
    manifest=json.loads((data/'MANIFEST.json').read_text())
    if digest(path)!=manifest['files'][path.name]['sha256']:
        raise ValueError('Input file changed after the dataset freeze')
    return [json.loads(l) for l in path.read_text().splitlines()]


def normalized(p):
    if set(p)!=set(DISPOSITIONS) or any(not math.isfinite(v) or v<0 for v in p.values()) or sum(p.values())<=0:
        raise ValueError('Invalid probability distribution')
    total=sum(p.values());return {k:float(p[k]/total) for k in DISPOSITIONS}


def tempered(p,T):
    z={k:math.log(max(v,1e-12))/T for k,v in p.items()};m=max(z.values())
    return normalized({k:math.exp(v-m) for k,v in z.items()})


def fit_temperature(pairs):
    def nll(T):return -sum(math.log(max(tempered(p,T)[y],1e-12)) for p,y in pairs)/len(pairs)
    # A fixed grid is used only on cal; no evaluation labels enter this choice.
    candidates=[math.exp(math.log(.5)+i*(math.log(5)-math.log(.5))/200) for i in range(201)]
    T=min(candidates,key=nll)
    return T,{'rows':len(pairs),'temperature':T,'nll_before':nll(1),'nll_after':nll(T),'split':'cal'}


def quantify(rows,threshold=None):
    by_case=defaultdict(list);by_family=defaultdict(list)
    for r in rows:by_case[r['case_id']].append(r);by_family[r['family_id']].append(r)
    n=len(rows);correct=sum(r['prediction']==r['expected'] for r in rows)
    required=[r for r in rows if r['expected']!='exclude']
    rec=[r for r in rows if r['prediction']=='recommend']
    gold_rec=[r for r in rows if r['expected']=='recommend']
    reviews=[r for r in rows if r['expected']=='review'];hands=[r for r in rows if r['expected']=='handoff']
    exact=sum(all(r['prediction']==r['expected'] for r in rs) for rs in by_case.values())
    accepted=[rs for rs in by_case.values() if threshold is not None and all(r['confidence'] is not None and r['confidence']>=threshold for r in rs)]
    accepted_correct=sum(all(r['prediction']==r['expected'] for r in rs) for rs in accepted)
    probs=[r for r in rows if r['probabilities'] is not None]
    ece=None
    if len(probs)==len(rows):
        ece=0.
        for i in range(10):
            b=[r for r in rows if min(9,int(r['confidence']*10))==i]
            if b:ece+=len(b)/n*abs(sum(r['prediction']==r['expected'] for r in b)/len(b)-statistics.mean(r['confidence'] for r in b))
    return {'decisions':n,'cases':len(by_case),'scenario_families':len(by_family),
            'decision_accuracy':correct/n if n else None,'exact_plan_cases':exact,
            'exact_plan_rate':exact/len(by_case) if by_case else None,
            'required_controls':len(required),
            'missed_required_controls':sum(r['prediction'] in ('exclude','INVALID') for r in required),
            'required_control_recall':sum(r['prediction'] not in ('exclude','INVALID') for r in required)/len(required) if required else None,
            'recommendations':len(rec),'wrong_recommendations':sum(r['expected']!='recommend' for r in rec),
            'recommendation_precision':sum(r['expected']=='recommend' for r in rec)/len(rec) if rec else None,
            'recommendation_recall':sum(r['prediction']=='recommend' for r in gold_rec)/len(gold_rec) if gold_rec else None,
            'correct_reviews':sum(r['prediction']=='review' for r in reviews),'expected_reviews':len(reviews),
            'correct_handoffs':sum(r['prediction']=='handoff' for r in hands),'expected_handoffs':len(hands),
            'invalid_decisions':sum(r['prediction']=='INVALID' for r in rows),'ece_10bins':ece,
            'recall_by_disposition':{d:sum(r['expected']==d and r['prediction']==d for r in rows)/sum(r['expected']==d for r in rows)
                                     if any(r['expected']==d for r in rows) else None for d in DISPOSITIONS},
            'routing':{'threshold':threshold,'accepted_cases':len(accepted),'correctly_accepted_cases':accepted_correct,
                       'wrong_accepted_cases':len(accepted)-accepted_correct,
                       'coverage':len(accepted)/len(by_case) if by_case else None,
                       'observed_risk':(len(accepted)-accepted_correct)/len(accepted) if accepted else None}}


def route_threshold(cal):
    trials=[]
    for t in [i/100 for i in range(50,100)]:
        r=quantify(cal,t)['routing'];trials.append(r)
    eligible=[r for r in trials if r['accepted_cases'] and r['observed_risk']<=.05]
    # If the small calibration set supports no such routing, accept nothing.
    threshold=min(eligible,key=lambda r:(-r['coverage'],r['threshold']))['threshold'] if eligible else 1.000001
    return threshold,trials


def bootstrap(rows,seed=18,n=1000):
    groups=defaultdict(list)
    for r in rows:groups[r['family_id']].append(r)
    keys=sorted(groups);rng=random.Random(seed);values=[]
    for _ in range(n):
        sampled=[]
        for i,k in enumerate(rng.choices(keys,k=len(keys))):
            sampled.extend({**r,'case_id':str(i)+':'+r['case_id']} for r in groups[k])
        values.append(quantify(sampled)['exact_plan_rate'])
    values.sort();return {'metric':'exact_plan_rate','group':'scenario_family','replicates':n,
                          'low':values[int(.025*n)],'high':values[int(.975*n)],
                          'limitations':'Few authored families; not independent enterprise evidence'}


def rules(state):
    s=json.loads(state);text=s['operator_intent'].lower();evidence=s['available_evidence'].lower();key=s['candidate']['key']
    patterns={
      'egress_profile':r'outbound|network (?:profile|boundary|restriction)|traffic|communication|connections',
      'deny_privilege_escalation':r'privileged|privilege.escalat|additional.*privilege|extra privileges',
      'restrict_registry':r'registry|mirror|image.source|images.*from',
      'restrict_api_access':r'(?:remove|reduce|revoke).*?(?:api|permissions|secret)|(?:api|secret).*(?:permissions|reads)',
      'deny_sa_token_for_agent_sidecars':r'automatic.*(?:token|credential|mount)|token.*(?:mount|inject)|automount',
      'deny_agent_mutation_outside_namespace':r'(?:agent|bot|assistant|maintainer|daemon).*?(?:namespace|write)|namespace.*(?:write|boundary)',
      'require_ticket_on_agent_changes':r'ticket|change reference|change annotation',
      'audit_replica_surge':r'replica.*(?:threshold|budget|ceiling|above|over)|scale.*threshold',
      'process':r'exception|expir|rollout|rollback|recovery|evidence chain|exit criteria|evidence owner|custodian',
      'not_implementable':r'tool|chat|generated text|memory|running process|already.running|signature|provenance|seccomp|capabilities|hostprocess|projected token|ephemeral'
    }
    # Transparent starter rules, fixed before scoring. Hard outputs are not assigned
    # an invented probability or used for confidence routing.
    if re.search(r'explain|summarize|describe|document the scheduled|analyze the quoted',text) and re.search(r'unchanged|without|do not|preserve existing|leave|no.*propos',text):return 'exclude'
    if not re.search(patterns[key],text):return 'exclude'
    if s['candidate']['implementation'] is None:return 'handoff'
    if re.search(r'unknown|unidentified|omitted|not available|not identified|not been|no (?:replacement|capacity|baseline|audit subject)|no alternative|unavailable|not.*(?:established|designed|documented)',evidence):return 'review'
    return 'recommend'


def predictor(kind,train,model=None,device='cpu'):
    metadata={'candidate':kind,'device':'cpu'}
    if kind=='rules':return lambda s:(rules(s),None),metadata
    if kind=='majority':
        counts=Counter(r['labels']['q'] for r in train);p=normalized({k:counts[k] for k in DISPOSITIONS})
        return lambda s:(max(p,key=p.get),p),metadata
    if kind in ('logistic','candidate-lr','retrieval','context-retrieval'):
        import baselines
        from sklearn.linear_model import LogisticRegression
        from sklearn.metrics.pairwise import cosine_similarity
        features=baselines._features()
        def feature_text(s):
            if kind!='context-retrieval':return s
            d=json.loads(s);return json.dumps({k:d[k] for k in ('operator_intent','available_evidence','operational_constraints')},sort_keys=True)
        train_keys=[json.loads(r['state'])['candidate']['key'] for r in train]
        keys=sorted(set(train_keys))
        X=features.fit_transform([feature_text(r['state']) for r in train]);labels=[r['labels']['q'] for r in train]
        def conditioned(matrix,row_keys):
            import numpy as np
            from scipy.sparse import hstack
            if set(row_keys)-set(keys):raise ValueError('Unknown candidate key')
            # A linear model over concatenated sentences cannot express "this intent
            # matches THIS candidate" without interactions. Include shared and
            # candidate-specific features; every feature still comes from state only.
            return hstack([matrix]+[matrix.multiply(np.asarray([k==key for k in row_keys])[:,None]) for key in keys],format='csr')
        if kind in ('logistic','candidate-lr'):
            fit_X=conditioned(X,train_keys) if kind=='candidate-lr' else X
            clf=LogisticRegression(C=4,class_weight='balanced',max_iter=2000).fit(fit_X,labels)
            def predict(s):
                x=features.transform([s])
                if kind=='candidate-lr':x=conditioned(x,[json.loads(s)['candidate']['key']])
                p=normalized({k:float(v) for k,v in zip(clf.classes_,clf.predict_proba(x)[0])})
                return max(p,key=p.get),p
        else:
            def predict(s):
                sim=cosine_similarity(features.transform([feature_text(s)]),X)[0]
                if kind=='context-retrieval':
                    key=json.loads(s)['candidate']['key']
                    for i,k in enumerate(train_keys):
                        if k!=key:sim[i]=-1
                idx=sim.argsort()[-3:]
                weights={k:1e-6 for k in DISPOSITIONS}
                for i in idx:weights[labels[i]]+=max(0,float(sim[i]))
                p=normalized(weights);return max(p,key=p.get),p
        return predict,metadata
    if kind=='laya':
        import laya
        a=laya.load(str(model),device=device)
        metadata.update(model=str(model),device=str(a.device),model_sha256=digest(Path(model)/'model.safetensors'),
                        config_sha256=digest(Path(model)/'rl_agent_config.json'))
        def predict(s):
            response=a.predict(s,QUESTION);answer=response['answers']['q']
            p=normalized(answer['probabilities']);return answer['choice'],p
        return predict,metadata
    if kind=='ollama':
        model=str(model)
        with urllib.request.urlopen('http://localhost:11434/api/tags',timeout=10) as response:inventory=json.load(response)
        identity=next((m for m in inventory['models'] if m['name']==model),None)
        if identity is None:raise ValueError('Requested Ollama model is not installed; no automatic download')
        metadata.update(model=model,model_digest=identity['digest'],model_size_bytes=identity['size'],
                        device='Ollama server; placement unmeasured',confidence_kind='generated probability estimates',
                        usage={'input_tokens':0,'output_tokens':0,'calls':0})
        schema={'type':'object','properties':{'probabilities':{'type':'object',
                    'properties':{d:{'type':'number','minimum':0,'maximum':1} for d in DISPOSITIONS},
                    'required':list(DISPOSITIONS),'additionalProperties':False}},
                'required':['probabilities'],'additionalProperties':False}
        def predict(s):
            payload={'model':model,'stream':False,'think':False,'keep_alive':'5m','format':schema,
                     'options':{'temperature':0,'seed':18,'num_ctx':4096,'num_predict':192},
                     'messages':[{'role':'system','content':'Assess the supplied typed question using only its criteria and evidence. Return a probability for each listed disposition, summing to one. These are estimates to be evaluated, not authority to act.'},
                                 {'role':'user','content':json.dumps({'state':s,'question':QUESTION['q']})}]}
            req=urllib.request.Request('http://localhost:11434/api/chat',data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'})
            with urllib.request.urlopen(req,timeout=120) as response:raw=json.load(response)
            metadata['usage']['calls']+=1;metadata['usage']['input_tokens']+=raw.get('prompt_eval_count',0)
            metadata['usage']['output_tokens']+=raw.get('eval_count',0)
            metadata['_last_provider_response']=raw
            if not raw.get('done') or raw.get('done_reason')=='length':raise ValueError('Incomplete model response')
            p=json.loads(raw['message']['content'])['probabilities']
            if any(not isinstance(v,(int,float)) or isinstance(v,bool) or not 0<=v<=1 for v in p.values()) or abs(sum(p.values())-1)>.03:
                raise ValueError('Generated probability estimates do not form a distribution')
            p=normalized(p);return max(p,key=p.get),p
        return predict,metadata
    raise ValueError('Unsupported candidate')


def run(data,out,candidate,model=None,device='cpu'):
    data=Path(data);out=Path(out);out.mkdir(parents=True,exist_ok=False)
    (out/'BENCHMARK.py.txt').write_bytes(BENCHMARK_SOURCE)
    manifest=json.loads((data/'MANIFEST.json').read_text())
    if digest(data/'questions.json')!=manifest['files']['questions.json']['sha256']:
        raise ValueError('Question file changed after the data freeze')
    if json.dumps(json.loads((data/'questions.json').read_text()))!=json.dumps({'guardrail_candidate':QUESTION}):
        raise ValueError('Question definitions or option order differ from frozen training inputs')
    train=load(data,'train');cal=load(data,'cal')
    start=time.perf_counter();predict,meta=predictor(candidate,train,model,device)
    meta['model_family']='specialized_encoder' if candidate=='laya' else candidate
    setup=time.perf_counter()-start
    warmup_start=time.perf_counter()
    predict(train[0]['state']) # Identical warmup input; excluded from warm timings.
    warmup_seconds=time.perf_counter()-warmup_start
    meta.pop('_last_provider_response',None)
    def score(rows,T=1):
        records=[]
        for r in rows:
            start=time.perf_counter();error=None
            try:
                choice,p=predict(r['state'])
                if p is not None:p=tempered(p,T);choice=max(p,key=p.get)
                if choice not in DISPOSITIONS:raise ValueError('Unknown disposition')
            except Exception as e:
                choice='INVALID';p=None;error=type(e).__name__
            trace=meta.pop('_last_provider_response',None)
            records.append({'id':r['id'],'case_id':r['case_id'],'family_id':r['family_id'],
                            'state_sha256':hashlib.sha256(r['state'].encode()).hexdigest(),
                            'prediction':choice,'probabilities':p,'confidence':max(p.values()) if p else None,
                            'expected':r['labels']['q'],'elapsed_ms':(time.perf_counter()-start)*1000,'error':error,
                            'tags':r['tags'],'provider_response':trace})
            # Keep successful and failed requests if a later process interruption occurs.
            with (out/'responses-live.jsonl').open('a') as stream:
                stream.write(json.dumps({'phase':'cal' if rows is cal else 'test_authored',**records[-1]})+'\n')
        return records
    raw_cal=score(cal);write_jsonl(out/'cal-raw.jsonl',raw_cal)
    pairs=[(r['probabilities'],r['expected']) for r in raw_cal if r['probabilities'] is not None]
    T,calibration=fit_temperature(pairs) if len(pairs)==len(cal) else (1,{'status':'UNAVAILABLE','reason':'Missing probability distributions'})
    calibrated=[]
    for r in raw_cal:
        p=tempered(r['probabilities'],T) if r['probabilities'] else None
        calibrated.append({**r,'probabilities':p,'prediction':max(p,key=p.get) if p else r['prediction'],
                           'confidence':max(p.values()) if p else None})
    threshold,curve=route_threshold(calibrated)
    # The authored test file is opened only after calibration and threshold choice.
    test=load(data,'test_authored');records=score(test,T);write_jsonl(out/'test-responses.jsonl',records)
    ms=sorted(r['elapsed_ms'] for r in records);case_ms=defaultdict(float)
    for r in records:case_ms[r['case_id']]+=r['elapsed_ms']
    m=quantify(records,threshold);correct_accepted=m['routing']['correctly_accepted_cases']
    result={'candidate':meta,'data_manifest_sha256':digest(data/'MANIFEST.json'),
            'benchmark_sha256':hashlib.sha256(BENCHMARK_SOURCE).hexdigest(),'setup_seconds':setup,
            'first_decision_warmup_seconds':warmup_seconds,'calibration':calibration,
            'routing_selection':{'split':'cal','maximum_observed_risk':.05,'curve':curve,
                                 'qualification':'Exploratory; no independent risk guarantee'},
            'metrics':m,'family_bootstrap_95':bootstrap(records),
            'timing':{'warm_decision_p50_ms':statistics.median(ms),'warm_decision_p95_ms':ms[math.ceil(.95*len(ms))-1],
                      'full_case_p50_ms':statistics.median(case_ms.values()),
                      'full_case_p95_ms':sorted(case_ms.values())[math.ceil(.95*len(case_ms))-1],
                      'scope':'Sequential ten-candidate assessment; includes inference and response validation, excludes human review and deployment'},
            'peak_process_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024),
            'memory_scope':'Benchmark client only; Ollama server memory is not measured' if candidate=='ollama' else 'Benchmark process; accelerator allocation is recorded separately in training receipts',
            'cost':{'api_usd':0,'api_usd_per_attempted_case':0,
                    'api_usd_per_correctly_accepted_case':0 if correct_accepted else None,
                    'total_operating_usd':None,'hardware_energy_operator_and_review_costs':'UNPRICED'},
            'qualification':'INCOMPLETE_INDEPENDENT_REVIEW_AND_STRONG_MODEL_COMPARISON',
            'limitations':['Assistant-authored cases and labels','Source-family separation does not prove semantic novelty',
                           'Few case families','No enterprise containment or industry-leadership claim']}
    (out/'summary.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ('candidate','metrics','timing','qualification')},indent=2))
    return result


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--data',type=Path,required=True);ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--candidate',choices=('majority','rules','retrieval','context-retrieval','logistic','candidate-lr','laya','ollama'),required=True)
    ap.add_argument('--model',type=Path);ap.add_argument('--device',default='cpu')
    a=ap.parse_args()
    if a.candidate in ('laya','ollama') and not a.model:ap.error('--model is required for model candidates')
    run(a.data,a.out,a.candidate,a.model,a.device)
