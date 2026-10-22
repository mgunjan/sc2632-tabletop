#!/usr/bin/env python3
"""Test actual compiler policies offline; behavioral receipts are not response labels."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time
import uuid

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'generator'))
sys.path.insert(0,str(ROOT/'datasets/guardrails'))
import generate as g
from run_upstream import json_results,sha
import yaml


def run(out):
    out=Path(out).resolve();out.mkdir(parents=True,exist_ok=False)
    lock=json.loads((ROOT/'datasets/comprehensive/runtime.lock.json').read_text())
    artifact=next(a for a in lock['artifacts'] if a['executable']=='kyverno')
    binary=ROOT/'.session-build/upstream-data-20261016/bin/kyverno'
    if sha(binary)!=artifact['binary_sha256']:raise ValueError('Policy engine hash mismatch')
    mirror=out/'materialized';mirror.mkdir()
    shutil.copytree(ROOT/'quarantine',mirror/'quarantine')
    policies=[];jobs=[]
    for scenario in 'abc':
        spec=json.loads((ROOT/f'generator/spec-{scenario}.json').read_text());g.validate_spec(spec)
        src=g.SCENARIOS[scenario]['dir'];dest=mirror/'scenarios'/src.name
        shutil.copytree(src,dest)
        for p in (dest/'policies').glob('*.yaml'):p.unlink()
        rendered=g.render_policies(spec,'Deny')
        for name,text in rendered.items():
            p=dest/'policies'/name;p.write_text(text)
            key=next(k for k,v in g.POLICY_FILE.items() if v+'.yaml'==name)
            policies.append({'control':key,'scenario':scenario,'path':str(p.relative_to(out)),'sha256':sha(p)})
        for p in sorted((dest/'tests').glob('kyverno-test*.yaml')):
            suite=yaml.safe_load(p.read_text())
            if any('../policies/' in s for s in suite.get('policies',[])):jobs.append(p)
    # Separate regular/init/namespace boundary contract against the generated rule.
    contract=mirror/'contracts';(contract/'tests').mkdir(parents=True);(contract/'policies').mkdir()
    shutil.copyfile(ROOT/'generator/contracts/privilege-test.yaml',contract/'tests/kyverno-test.yaml')
    shutil.copyfile(ROOT/'generator/contracts/privilege-resources.yaml',contract/'tests/resources.yaml')
    spec=json.loads((ROOT/'generator/spec-a.json').read_text())
    (contract/'policies/deny-privilege-escalation.yaml').write_text(g.render_policies(spec,'Deny')['deny-privilege-escalation.yaml'])
    jobs.append(contract/'tests/kyverno-test.yaml')
    receipts=[]
    for index,p in enumerate(jobs):
        name='acg-decision-'+uuid.uuid4().hex
        argv=['docker','run','--rm','--name',name,'--network','none','--read-only',
              '--cap-drop','ALL','--security-opt','no-new-privileges','--user','65534:65534',
              '--cpus','1','--memory','1g','--tmpfs','/tmp:rw,noexec,nosuid,size=64m',
              '--env','HOME=/tmp','--label','acg.dataset=decisions-20261018',
              '--mount',f'type=bind,src={mirror},dst=/fixtures,readonly',
              '--mount',f'type=bind,src={binary.parent},dst=/engine,readonly',lock['image'],
              '/engine/kyverno','test','/fixtures/'+str(p.parent.relative_to(mirror)),
              '--file-name',p.name,'--require-tests','--output-format','json','--remove-color']
        start=time.perf_counter();timed_out=False
        try:
            proc=subprocess.run(argv,capture_output=True,text=True,timeout=120)
            code=proc.returncode;stdout=proc.stdout;stderr=proc.stderr
        except subprocess.TimeoutExpired as e:
            subprocess.run(['docker','rm','-f',name],capture_output=True,timeout=15)
            code=None;timed_out=True;stdout=str(e.stdout or '');stderr=str(e.stderr or '')
        folder=out/f'receipt-{index:02d}';folder.mkdir()
        (folder/'stdout.txt').write_text(stdout);(folder/'stderr.txt').write_text(stderr)
        rows=json_results(stdout)
        suite=yaml.safe_load(p.read_text())
        declared=sum(len(r.get('resources',[])) for r in suite.get('results',[]))
        receipt={'test':str(p.relative_to(out)),'test_sha256':sha(p),'argv':argv,
                 'returncode':code,'timed_out':timed_out,'elapsed_seconds':time.perf_counter()-start,
                 'rows':rows,'declared_expectations':declared,
                 'complete':code==0 and bool(rows) and len(rows)==declared and all(r['RESULT']=='Pass' for r in rows),
                 'stdout_sha256':sha(folder/'stdout.txt'),'stderr_sha256':sha(folder/'stderr.txt')}
        (folder/'result.json').write_text(json.dumps(receipt,indent=2)+'\n');receipts.append(receipt)
        print(json.dumps({'suite':receipt['test'],'complete':receipt['complete'],'rows':len(rows),'declared':declared}),flush=True)
    result={'engine':'kyverno','version':artifact['version'],'binary_sha256':sha(binary),'image':lock['image'],
            'compiler_sha256':sha(ROOT/'generator/generate.py'),'catalog_sha256':sha(ROOT/'controls/catalog.json'),
            'runner_sha256':sha(Path(__file__)),'policies':policies,'receipts':receipts,
            'complete':all(r['complete'] for r in receipts),
            'scope':'Offline fixture behavior only; no cluster, runtime containment or independent response labels',
            'independent_response_labels':0}
    (out/'SUMMARY.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',type=Path,required=True)
    a=ap.parse_args();result=run(a.out);print(json.dumps({k:v for k,v in result.items() if k not in ('policies','receipts')},indent=2))
    sys.exit(0 if result['complete'] else 1)
