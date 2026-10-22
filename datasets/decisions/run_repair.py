#!/usr/bin/env python3
"""Train one prespecified repair, then run the unchanged authored regression."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    for key in ('data','base','weights','out'):ap.add_argument('--'+key,type=Path,required=True)
    a=ap.parse_args()
    if a.weights.exists():raise SystemExit('Preserve prior weights')
    a.out.mkdir(parents=True,exist_ok=True)
    if (a.out/'RUN-STATUS.json').exists():raise SystemExit('Preserve prior run')
    for source,name in [(ROOT/'laya_variant/train.py','TRAINER.py.txt'),(Path(__file__),'RUNNER.py.txt'),(HERE/'repair_curriculum.py','DATA-BUILDER.py.txt')]:
        (a.out/name).write_bytes(source.read_bytes())
    records=[];start=time.perf_counter()
    def status(state):
        (a.out/'RUN-STATUS.json').write_text(json.dumps({'state':state,'runs':records,'elapsed_seconds':time.perf_counter()-start},indent=2)+'\n')
    phases=[('training',[sys.executable,str(ROOT/'laya_variant/train.py'),'--base',str(a.base),'--data',str(a.data),
        '--questions',str(a.data/'questions.json'),'--tasks','guardrail_candidate','--out',str(a.weights),
        '--epochs','4','--batch-states','4','--lr','0.0001','--encoder-lr','0.00002','--encoder-last-layers','2',
        '--seed','19','--selection-split','dev','--selection-metric','plan','--objective','cross-entropy',
        '--save-epoch-deltas','--evaluate-train','--max-seconds','2400','--device','mps']),
        ('evaluation',[sys.executable,str(HERE/'benchmark.py'),'--data',str(a.data),'--out',str(a.out/'evaluation'),
                       '--candidate','laya','--model',str(a.weights),'--device','mps'])]
    for phase,argv in phases:
        status(phase.upper());t=time.perf_counter()
        with (a.out/(phase+'.log')).open('w') as log:code=subprocess.run(argv,stdout=log,stderr=subprocess.STDOUT).returncode
        records.append({'phase':phase,'argv':argv,'returncode':code,'elapsed_seconds':time.perf_counter()-t})
        if code:status('FAILED_'+phase.upper());raise SystemExit(code)
    status('COMPLETED')
