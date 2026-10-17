#!/usr/bin/env python3
"""Audit normalized data and link actual engine receipts without inferring incident-response labels."""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import re
import sys

from collect import HERE, sha
from build import content_hash
sys.path.insert(0,str(HERE.parent/'guardrails'))
from build_corpus import verify_expectation
from run_upstream import json_results


def gator_cases(text):
    test=None;pending=[];rows=[]
    for line in text.splitlines():
        match=re.match(r'^=== RUN\s+(.+)$',line)
        if match:test=match[1]
        match=re.match(r'^    --- (PASS|FAIL|SKIP): (.+?)\s+\(',line)
        if match:pending.append((test,match[2],match[1]))
        match=re.match(r'^ok\s+/data/gatekeeper-library/(\S+)\s+',line)
        if match:
            rows.extend((match[1],*p) for p in pending);pending=[]
    if pending:raise ValueError('Unattributed Gator output')
    return rows


def checked_run(folder):
    result=json.loads((folder/'SUMMARY.json').read_text())
    if sha(folder/'RUNNER.py.txt')!=result['runner_sha256']:
        raise ValueError('Runner snapshot differs')
    for run in result['results']:
        directory=folder/run['id']
        for name in ('stdout','stderr'):
            if sha(directory/(name+'.txt'))!=run[name+'_sha256']:
                raise ValueError('Execution output differs')
        if run['engine']=='kyverno' and json_results((directory/'stdout.txt').read_text())!=run['test_rows']:
            raise ValueError('Parsed rows differ')
    return result


def audit(corpus,cache,out):
    manifest=json.loads((corpus/'MANIFEST.json').read_text())
    for item in manifest['files']:
        path=corpus/item['path']
        if sha(path)!=item['sha256'] or path.stat().st_size!=item['bytes']:
            raise ValueError('Corpus differs: '+item['path'])
    records=[json.loads(x) for x in (corpus/'records.jsonl').read_text().splitlines()]
    if len({r['id'] for r in records})!=len(records):raise ValueError('Duplicate IDs')
    for row in records:
        if content_hash({k:row[k] for k in ('record_type','inputs','target')})!=row['content_sha256']:
            raise ValueError('Payload differs')
        if row['independent_response_label'] or row['training_split']!='unassigned':
            raise ValueError('Unexpected promoted label or split')
    out.mkdir(parents=True,exist_ok=False)
    observations=[]
    legacy=checked_run(cache/'runs/kyverno-legacy')
    executed_lock=cache/'runs/kyverno-legacy/SOURCES.lock.json'
    current_sources={s['name']:s['revision'] for s in json.loads((HERE/'sources.lock.json').read_text())['sources']}
    for source in json.loads(executed_lock.read_text())['sources']:
        if current_sources[source['name']]!=source['revision']:raise ValueError('Executed source pin differs')
    if sha(executed_lock)!=legacy['sources_lock_sha256']:raise ValueError('Executed lock snapshot differs')
    runtime=json.loads((HERE/'runtime.lock.json').read_text())
    if legacy['image']!=runtime['image']:raise ValueError('Executed image differs')
    if legacy['binary_sha256']!=next(a['binary_sha256'] for a in runtime['artifacts'] if a['executable']=='kyverno'):
        raise ValueError('Executed Kyverno differs')
    runs={r['source']:r for r in legacy['results']}
    for row in records:
        if row['source']['name']=='kyverno-legacy' and row['record_type']=='behavior_case':
            run=runs.get('kyverno-legacy/'+row['source']['path'])
            if run is None:
                observations.append({'record_id':row['id'],'engine':'kyverno',
                                     'observation':{'verified_expectation':False,'basis':'suite not executed by selected filename pattern','test_rows':[],'direct_policy_result':None},
                                     'execution_status':'not_executed','incident_response_label':None})
                continue
            expected=row['target'];resource=expected['resources'][row['upstream_resource_index']]
            observed=verify_expectation(expected,resource,run['test_rows'])
            observations.append({'record_id':row['id'],'engine':'kyverno','observation':observed,
                                 'suite_process_succeeded':run['process_succeeded'],
                                 'source_revision':row['source']['revision'],
                                 'evidence':{'run_id':run['id'],'stdout_sha256':run['stdout_sha256']},
                                 'incident_response_label':None})
    gator=checked_run(cache/'runs/gatekeeper')
    gator_lock=cache/'runs/gatekeeper/SOURCES.lock.json'
    if sha(gator_lock)!=gator['sources_lock_sha256'] or gator['image']!=runtime['image']:
        raise ValueError('Gator execution identity differs')
    for source in json.loads(gator_lock.read_text())['sources']:
        if current_sources[source['name']]!=source['revision']:raise ValueError('Gator source pin differs')
    if gator['binary_sha256']!=next(a['binary_sha256'] for a in runtime['artifacts'] if a['executable']=='gator'):
        raise ValueError('Executed Gator differs')
    gator_counts={}
    for run in gator['results']:
        text=(cache/'runs/gatekeeper'/run['id']/'stdout.txt').read_text()
        parsed=gator_cases(text)
        by_key=defaultdict(list)
        for path,test,case,status in parsed:by_key[(path,test,case)].append(status)
        for row in records:
            if row['source']['name']=='gatekeeper-library' and row['record_type']=='behavior_case':
                statuses=by_key.get((row['source']['path'],row['upstream_test_name'],row['name']),[])
                observations.append({'record_id':row['id'],'engine':run['engine'],
                                     'observation':{'verified_expectation':statuses==['PASS'],'case_statuses':statuses,
                                                    'direct_policy_result':None},
                                     'evidence':{'run_id':run['id'],'stdout_sha256':run['stdout_sha256']},
                                     'incident_response_label':None})
        gator_counts[run['engine']]={'case_passes':sum(r[3]=='PASS' for r in parsed),'case_failures':sum(r[3]=='FAIL' for r in parsed),
                                   'suite_summaries':len(re.findall(r'^ok\s',text,re.M))}
    old=HERE.parent/'guardrails/corpus'
    old_manifest=json.loads((old/'MANIFEST.json').read_text())
    for item in old_manifest['files']:
        if sha(old/item['path'])!=item['sha256']:raise ValueError('Earlier evidence corpus differs')
    for line in (old/'kyverno-cases.jsonl').read_text().splitlines():
        row=json.loads(line)
        observations.append({'previous_corpus_record_id':row['id'],'engine':'kyverno-current',
                             'observation':row['observation'],'source':row['source'],'incident_response_label':None})
    for line in (old/'falco-replays.jsonl').read_text().splitlines():
        row=json.loads(line);observations.append({'engine':'falco-replay','observation':row,'incident_response_label':None})
    path=out/'engine-observations.jsonl'
    path.write_text(''.join(json.dumps(r,sort_keys=True)+'\n' for r in observations))
    by_engine={}
    for engine in sorted({r['engine'] for r in observations}):
        selected=[r for r in observations if r['engine']==engine]
        by_engine[engine]={'observations':len(selected),'verified_contract_expectations':sum(r['observation'].get('verified_expectation',False) for r in selected)}
    report={'records_audited':len(records),'corpus_manifest_sha256':sha(corpus/'MANIFEST.json'),
            'audit_sha256':sha(Path(__file__)),'engine_observations':len(observations),'by_engine':by_engine,
            'gator_configurations':gator_counts,
            'gator_native_enabled_is_not_proof_every_case_used_cel':True,
            'legacy_kyverno':{'suites':legacy['processes'],'exit_zero':legacy['exit_zero'],
                             'failed_suites':[r['source'] for r in legacy['results'] if not r['process_succeeded']],
                             'elapsed_seconds':legacy['elapsed_seconds']},
            'independent_response_labels':0,'new_model_trained':False,'model_api_calls':0,
            'observation_file':{'path':path.name,'rows':len(observations),'bytes':path.stat().st_size,'sha256':sha(path)}}
    (out/'EXECUTION-AUDIT.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--corpus',type=Path,required=True);p.add_argument('--cache',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();audit(a.corpus,a.cache,a.out)
