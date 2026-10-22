#!/usr/bin/env python3
"""Run the separate three-full-pass convergence extension, then frozen scoring."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    for key in ('data','base','weights','out','protocol'):ap.add_argument('--'+key,type=Path,required=True)
    a=ap.parse_args();a.out.mkdir(parents=True,exist_ok=False)
    if a.weights.exists():raise SystemExit('Preserve prior weights')
    (a.out/'RUNNER.py.txt').write_bytes(Path(__file__).read_bytes())
    (a.out/'TRAINER.py.txt').write_bytes((ROOT/'laya_variant/train.py').read_bytes())
    (a.out/'PROTOCOL.md').write_bytes(a.protocol.read_bytes())
    records=[];start=time.perf_counter()
    def status(state):
        (a.out/'RUN-STATUS.json').write_text(json.dumps({'state':state,'runs':records,'elapsed_seconds':time.perf_counter()-start,
            'data':str(a.data),'weights':str(a.weights),'qualification':'Supplemental convergence run; authored regression, not a fresh blind test'},indent=2)+'\n')
    argv=[sys.executable,str(ROOT/'laya_variant/train.py'),'--base',str(a.base),'--data',str(a.data),
        '--questions',str(a.data/'questions.json'),'--tasks','guardrail_candidate','--out',str(a.weights),
        '--epochs','3','--batch-states','4','--lr','0.0001','--encoder-lr','0.00002','--encoder-last-layers','2',
        '--seed','19','--selection-split','dev','--selection-metric','macro-loss','--objective','cross-entropy',
        '--balanced-labels','--steps-per-epoch','256','--max-steps','768','--max-seconds','1800','--device','mps']
    status('TRAINING');t=time.perf_counter()
    with (a.out/'training.log').open('w') as log:code=subprocess.run(argv,stdout=log,stderr=subprocess.STDOUT).returncode
    records.append({'phase':'train','argv':argv,'returncode':code,'elapsed_seconds':time.perf_counter()-t})
    if code:status('FAILED_TRAINING');raise SystemExit(code)
    argv=[sys.executable,str(HERE/'benchmark.py'),'--data',str(a.data),'--out',str(a.out/'evaluation'),
          '--candidate','laya','--model',str(a.weights),'--device','mps']
    status('EVALUATING');t=time.perf_counter()
    with (a.out/'evaluation.log').open('w') as log:code=subprocess.run(argv,stdout=log,stderr=subprocess.STDOUT).returncode
    records.append({'phase':'evaluate','argv':argv,'returncode':code,'elapsed_seconds':time.perf_counter()-t})
    status('RUNS_FINISHED' if not code else 'FAILED_EVALUATION');raise SystemExit(code)
