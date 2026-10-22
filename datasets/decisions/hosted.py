#!/usr/bin/env python3
"""Claude probability-estimate baseline on the unchanged local assessment harness."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import time
import urllib.error
import urllib.request

HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE))
import benchmark as bench
from build import DISPOSITIONS,digest

SOURCE=Path(__file__).read_bytes()
PRICES={'claude-opus-5-5':(4.,20.),'claude-sonnet-5-5':(2.,10.),'claude-fable-5-1':(10.,50.)}
PRICE_SOURCE='https://platform.claude.com/docs/en/models/overview'


def credentials(path,workspace_file=None):
    text=Path(path).read_text().strip();values={}
    if text and '\n' not in text and '=' not in text:values['ANTHROPIC_API_KEY']=text
    else:
        for line in text.splitlines():
            line=line.strip().removeprefix('export ')
            if not line or line.startswith('#') or '=' not in line:continue
            k,v=line.split('=',1)
            if k.strip() in ('ANTHROPIC_API_KEY','CLAUDE_API_KEY','ANTHROPIC_WORKSPACE_ID'):
                values[k.strip()]=v.strip().strip('"').strip("'")
    key=values.get('ANTHROPIC_API_KEY') or values.get('CLAUDE_API_KEY')
    workspace=Path(workspace_file).read_text().strip() if workspace_file else values.get('ANTHROPIC_WORKSPACE_ID') or os.environ.get('ANTHROPIC_WORKSPACE_ID')
    if not key:raise ValueError('Missing Claude API credential')
    return key,workspace


def usage_cost(usage,model):
    rates=PRICES[model]
    fields=('input_tokens','output_tokens','cache_creation_input_tokens','cache_read_input_tokens')
    values={k:usage.get(k,0) for k in fields}
    if any(not isinstance(v,int) or isinstance(v,bool) or v<0 for v in values.values()):
        raise ValueError('Invalid provider usage accounting')
    if 'input_tokens' not in usage or 'output_tokens' not in usage:raise ValueError('Missing provider usage accounting')
    plain=(values['input_tokens']*rates[0]+values['output_tokens']*rates[1])/1e6
    # No cache is requested. If a service applies caching, retain usage and give a
    # conservative spending bound instead of inventing a billed cache price.
    has_cache=bool(values['cache_creation_input_tokens'] or values['cache_read_input_tokens'])
    upper=plain+(2*values['cache_creation_input_tokens']+values['cache_read_input_tokens'])*rates[0]/1e6
    return {'tokens':values,'estimated_usd':None if has_cache else plain,'conservative_upper_usd':upper,
            'price_as_of':'2026-10-18','input_usd_per_million':rates[0],'output_usd_per_million':rates[1],
            'price_source':PRICE_SOURCE,'basis':'Published list-price estimate; not an invoice'}


class Claude:
    def __init__(self,key,workspace,model,max_usd=8.,transport=None):
        self.key=key;self.workspace=workspace;self.model=model;self.max_usd=max_usd
        self.transport=transport or self.post
        self.meta={'candidate':'claude','model':model,'device':'Hosted service; server hardware unmeasured',
                   'provider':'anthropic','confidence_kind':'generated probability estimates, not token probabilities',
                   'adapter_sha256':hashlib.sha256(SOURCE).hexdigest(),'workspace_configured':bool(workspace),
                   'thinking':'adaptive','effort':'medium','max_output_tokens':1024,
                   'spending_limit_usd':max_usd,'usage':{'calls':0,'known_estimated_api_usd':0.,
                      'conservative_upper_api_usd':0.,'input_tokens':0,'output_tokens':0,'unknown_cost_attempts':0,'budget_exhausted':False}}

    def post(self,payload):
        headers={'Content-Type':'application/json','x-api-key':self.key,'anthropic-version':'2023-06-01'}
        if self.workspace:headers['anthropic-workspace-id']=self.workspace
        req=urllib.request.Request('https://api.anthropic.com/v1/messages',data=json.dumps(payload).encode(),headers=headers)
        try:
            with urllib.request.urlopen(req,timeout=120) as response:return json.load(response)
        except urllib.error.HTTPError as e:
            # Keep a useful API diagnostic while explicitly removing any credential
            # a service might unexpectedly repeat. Never retain request headers.
            try:message=json.loads(e.read()).get('error',{}).get('message','')
            except Exception:message=''
            self.meta['_last_provider_response']={'http_status':e.code,'message':message.replace(self.key,'[REDACTED]')[:400]}
            raise RuntimeError('Claude HTTP '+str(e.code)) from None

    def payload(self,state):
        schema={'type':'object','properties':{'probabilities':{'type':'object',
                 'properties':{d:{'type':'number'} for d in DISPOSITIONS},
                 'required':list(DISPOSITIONS),'additionalProperties':False}},
                'required':['probabilities'],'additionalProperties':False}
        return {'model':self.model,'max_tokens':1024,'thinking':{'type':'adaptive'},
                 'system':'Assess the supplied typed question using only its criteria and evidence. Return a probability for each listed disposition, summing to one. These are estimates to be evaluated, not authority to act.',
                 'messages':[{'role':'user','content':json.dumps({'state':state,'question':bench.QUESTION['q']})}],
                 'output_config':{'effort':'medium','format':{'type':'json_schema','schema':schema}}}
    def predict(self,state):
        payload=self.payload(state)
        upper_reserve=(2*(len(json.dumps(payload).encode())+1000)*PRICES[self.model][0]+1024*PRICES[self.model][1])/1e6
        if self.meta['usage']['conservative_upper_api_usd']+upper_reserve>self.max_usd:
            self.meta['usage']['budget_exhausted']=True
            raise RuntimeError('Declared API spending limit reached')
        self.meta['usage']['calls']+=1
        try:raw=self.transport(payload)
        except Exception:
            self.meta['usage']['unknown_cost_attempts']+=1
            self.meta['usage']['conservative_upper_api_usd']+=upper_reserve
            raise
        retained={k:raw.get(k) for k in ('id','model','stop_reason','usage')}
        retained['content']=[p for p in raw.get('content',[]) if p.get('type')=='text']
        retained['thinking_blocks_retained']=False
        self.meta['_last_provider_response']=retained
        try:cost=usage_cost(raw.get('usage',{}),self.model)
        except ValueError:
            self.meta['usage']['unknown_cost_attempts']+=1
            self.meta['usage']['conservative_upper_api_usd']+=upper_reserve
            raise
        retained['cost']=cost
        stats=self.meta['usage'];stats['input_tokens']+=cost['tokens']['input_tokens'];stats['output_tokens']+=cost['tokens']['output_tokens']
        stats['conservative_upper_api_usd']+=cost['conservative_upper_usd']
        if cost['estimated_usd'] is not None:stats['known_estimated_api_usd']+=cost['estimated_usd']
        else:stats['unknown_cost_attempts']+=1
        if raw.get('model')!=self.model:raise ValueError('Provider returned an unexpected model identity')
        if raw.get('stop_reason')!='end_turn':raise ValueError('Provider response was truncated or incomplete')
        answer=json.loads(''.join(p['text'] for p in retained['content']))
        p=answer['probabilities']
        if set(p)!=set(DISPOSITIONS) or any(not isinstance(v,(float,int)) or isinstance(v,bool) or not math.isfinite(v) or not 0<=v<=1 for v in p.values()) or abs(sum(p.values())-1)>.03:
            raise ValueError('Invalid generated probability estimates')
        p=bench.normalized(p);return max(p,key=p.get),p


def export_preview(data,out,model='claude-opus-5-5'):
    data=Path(data);out=Path(out);out.mkdir(parents=True,exist_ok=False)
    provider=Claude('',None,model)
    train=bench.load(data,'train');cal=bench.load(data,'cal');test=bench.load(data,'test_authored')
    rows=[('warmup',train[0])]+[('calibration',r) for r in cal]+[('authored_test',r) for r in test]
    destination='https://api.anthropic.com/v1/messages'
    with (out/'OUTBOUND-PREVIEW.jsonl').open('w') as stream:
        for phase,r in rows:
            visible=json.loads(r['state'])
            if set(visible)!={'operator_intent','available_evidence','operational_constraints','candidate'}:
                raise ValueError('Unexpected model-visible field')
            body=provider.payload(r['state'])
            stream.write(json.dumps({'phase':phase,'assessment_id_for_preview_only':r['id'],
                                     'destination':destination,'outbound_body':body})+'\n')
    report={'destination':destination,'model':model,'requests':len(rows),'calibration_assessments':len(cal),
            'test_assessments':len(test),'warmup_assessments':1,'data_manifest_sha256':digest(data/'MANIFEST.json'),
            'preview_sha256':digest(out/'OUTBOUND-PREVIEW.jsonl'),
            'adapter_sha256':hashlib.sha256(SOURCE).hexdigest(),
            'contents':'Assistant-authored fictional scenario prose, versioned control-catalog coverage and typed task instructions',
            'excluded':'Proposed labels, rationale, reviewer identities, imported source alignments, telemetry files, API credentials and request headers',
            'api_usage_budget_usd':8,'price_source':PRICE_SOURCE,'price_as_of':'2026-10-18',
            'approval_status':'PENDING_EXPLICIT_EXPORT_AND_PAID_USAGE_AUTHORIZATION'}
    (out/'MANIFEST.json').write_text(json.dumps(report,indent=2)+'\n')
    (out/'EXPORT-REVIEW.md').write_text('\n'.join([
        '# Hosted comparison export review','',
        '**Destination:** Anthropic Messages API, `https://api.anthropic.com/v1/messages`.',
        '**Model/configuration:** Claude Opus 5.5, adaptive thinking at medium effort, maximum 1,024 output tokens per request.',
        '**Budget:** $8 at the recorded list prices; actual usage and price estimates are retained. This is not an invoice.',
        '', '**Exact scope:** one warmup plus 150 calibration and 150 authored-test assessments. The same case evidence and candidate-control coverage used by local models are sent.',
        '', 'The scenarios were authored in this experiment and describe fictional workloads and operational situations. The candidate text comes from the project reference catalog. No imported logs, real incident records, private answer labels, reviewer names or API keys are in the prompt bodies.',
        '', 'The API credential is used only as an authentication header and stays in the ignored local file. The provider receives the prompt bodies and can process them according to the account agreement.',
        '', 'All request bodies are available in [OUTBOUND-PREVIEW.jsonl](OUTBOUND-PREVIEW.jsonl). Preview assessment IDs and phase names are local audit metadata and are not sent as part of the body.',
        '', 'Automatic approval review rejected the first attempt because broad model-comparison authorization did not specifically authorize exporting local assessment data and paid usage. No benchmark prompt was sent in that rejected attempt.'
    ])+'\n')
    return report


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--data',type=Path,required=True);ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--key-file',type=Path,required=True);ap.add_argument('--workspace-file',type=Path)
    ap.add_argument('--model',choices=tuple(PRICES),default='claude-opus-5-5')
    ap.add_argument('--max-api-usd',type=float,default=8.)
    a=ap.parse_args()
    if not math.isfinite(a.max_api_usd) or a.max_api_usd<=0:ap.error('Spending limit must be positive and finite')
    key,workspace=credentials(a.key_file,a.workspace_file);provider=Claude(key,workspace,a.model,a.max_api_usd)
    original=bench.predictor;start=time.perf_counter()
    # Isolated process-scoped dependency injection. The scoring/calibration harness,
    # state identities, question and action options are exactly the local version.
    def factory(*args,**kwargs):return provider.predict,provider.meta
    bench.predictor=factory
    try:
        result=bench.run(a.data,a.out,'claude')
        def phase_cost(filename):
            rows=[json.loads(l) for l in (a.out/filename).read_text().splitlines()]
            values=[r.get('provider_response',{}).get('cost',{}).get('estimated_usd') if r.get('provider_response') else None for r in rows]
            return sum(values) if all(v is not None for v in values) else None
        cal_cost=phase_cost('cal-raw.jsonl');test_cost=phase_cost('test-responses.jsonl')
        correct=result['metrics']['routing']['correctly_accepted_cases'];cases=result['metrics']['cases']
        total=provider.meta['usage']['known_estimated_api_usd'] if not provider.meta['usage']['unknown_cost_attempts'] else None
        result['cost']={'api_usd':None,'estimated_api_usd_all_calls':total,
                        'estimated_calibration_api_usd':cal_cost,'estimated_test_api_usd':test_cost,
                        'estimated_api_usd_per_attempted_test_case':test_cost/cases if test_cost is not None else None,
                        'estimated_api_usd_per_correctly_accepted_test_case':test_cost/correct if test_cost is not None and correct else None,
                        'spending_limit_usd':a.max_api_usd,'price_as_of':'2026-10-18','price_source':PRICE_SOURCE,
                        'basis':'Published list-price estimate from provider usage; billed cost and human review remain unpriced',
                        'total_operating_usd':None}
        result['memory_scope']='Benchmark client only; hosted service hardware/memory is not measured'
        result['qualification']='INCOMPLETE_API_BUDGET' if provider.meta['usage']['budget_exhausted'] else 'INCOMPLETE_INDEPENDENT_REVIEW_AND_SOURCE_GROUNDED_DATA_EXPANSION'
        temp=a.out/'summary-final.tmp';temp.write_text(json.dumps(result,indent=2)+'\n');temp.replace(a.out/'summary.json')
        (a.out/'HOSTED.py.txt').write_bytes(SOURCE)
        (a.out/'HOSTED-RUN.json').write_text(json.dumps({'state':'BUDGET_EXHAUSTED' if provider.meta['usage']['budget_exhausted'] else 'RUNS_FINISHED','model':a.model,
            'elapsed_seconds':time.perf_counter()-start,'usage':provider.meta['usage'],'cost':result['cost'],
            'adapter_sha256':hashlib.sha256(SOURCE).hexdigest()},indent=2)+'\n')
        print(json.dumps({'model':a.model,'cost':result['cost'],'metrics':result['metrics']},indent=2))
    except Exception as e:
        if a.out.exists():
            (a.out/'HOSTED-RUN.json').write_text(json.dumps({'state':'FAILED','error_type':type(e).__name__,
                'elapsed_seconds':time.perf_counter()-start,'usage':provider.meta['usage'],
                'adapter_sha256':hashlib.sha256(SOURCE).hexdigest()},indent=2)+'\n')
        raise
    finally:bench.predictor=original


if __name__=='__main__':main()
