#!/usr/bin/env python3
"""Run local comparisons sequentially with source snapshots and complete process receipts."""
import argparse
import json
from pathlib import Path
import platform
import subprocess
import sys
import time

HERE=Path(__file__).resolve().parent


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--data',type=Path,required=True);ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--model',action='append',default=[],help='label=local checkpoint')
    ap.add_argument('--ollama-model');ap.add_argument('--device',default='cpu')
    a=ap.parse_args();a.out.mkdir(parents=True,exist_ok=False)
    start=time.perf_counter();records=[]
    jobs=[(c,['--candidate',c]) for c in ('majority','rules','logistic','candidate-lr','retrieval','context-retrieval')]
    for model in a.model:
        label,path=model.split('=',1)
        if not label or '/' in label or label in ('.','..') or label in [j[0] for j in jobs]:raise ValueError('Invalid or duplicate model label')
        jobs.append((label,['--candidate','laya','--model',path,'--device',a.device]))
    if a.ollama_model:jobs.append(('ollama',['--candidate','ollama','--model',a.ollama_model]))
    def status(state,current=None):
        (a.out/'RUN-STATUS.json').write_text(json.dumps({'state':state,'current':current,'runs':records,
            'elapsed_seconds':time.perf_counter()-start,'python':sys.version,'platform':platform.platform(),
            'qualification':'Independent review, source-grounded expansion and hosted baseline remain separate requirements'},indent=2)+'\n')
    (a.out/'RUNNER.py.txt').write_bytes(Path(__file__).read_bytes())
    for name,args in jobs:
        argv=[sys.executable,str(HERE/'benchmark.py'),'--data',str(a.data),'--out',str(a.out/name),*args]
        status('RUNNING',name);print(json.dumps({'starting':name}),flush=True)
        t=time.perf_counter()
        with (a.out/(name+'.log')).open('w') as log:
            process=subprocess.Popen(argv,stdout=log,stderr=subprocess.STDOUT)
            code=process.wait()
        records.append({'name':name,'argv':argv,'returncode':code,'elapsed_seconds':time.perf_counter()-t})
        print(json.dumps(records[-1]),flush=True)
        if code:
            status('FAILED',name);return 1
    status('RUNS_FINISHED')
    from report import render
    print(json.dumps(render(a.out)),flush=True)
    return 0


if __name__=='__main__':sys.exit(main())
