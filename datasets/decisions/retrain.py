#!/usr/bin/env python3
"""Run the preregistered six local training conditions, then frozen evaluation."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    for key in ('frozen','source','masked','base','weights','out','protocol'):
        ap.add_argument('--'+key,type=Path,required=True)
    ap.add_argument('--device',default='mps')
    a=ap.parse_args()
    a.out.mkdir(parents=True,exist_ok=False);a.weights.mkdir(parents=True,exist_ok=False)
    (a.out/'RUNNER.py.txt').write_bytes(Path(__file__).read_bytes())
    (a.out/'TRAINER.py.txt').write_bytes((ROOT/'laya_variant/train.py').read_bytes())
    (a.out/'PROTOCOL.md').write_bytes(a.protocol.read_bytes())
    start=time.perf_counter();records=[]
    conditions={'balanced':a.frozen,'no-reference':a.masked,'source':a.source}
    jobs=[(condition,regime,data) for condition,data in conditions.items() for regime in ('head','adapted')]
    def status(state,current=None):
        temp=a.out/'RUN-STATUS.tmp'
        temp.write_text(json.dumps({'state':state,'current':current,'runs':records,'elapsed_seconds':time.perf_counter()-start,
            'protocol_sha256':hashlib.sha256(a.protocol.read_bytes()).hexdigest(),
            'qualification':'Frozen authored regression; independent review and new final evaluation remain required'},indent=2)+'\n')
        temp.replace(a.out/'RUN-STATUS.json')
    for condition,regime,data in jobs:
        label=condition+'-'+regime;weights=a.weights/label
        argv=[sys.executable,str(ROOT/'laya_variant/train.py'),'--base',str(a.base),'--data',str(data),
              '--questions',str(data/'questions.json'),'--tasks','guardrail_candidate','--out',str(weights),
              '--epochs','3','--batch-states','4','--lr','0.0001','--seed','19','--selection-split','dev',
              '--selection-metric','macro-loss','--objective','cross-entropy','--balanced-labels','--steps-per-epoch','90',
              '--max-steps','270','--max-seconds','900','--device',a.device]
        argv+=['--freeze-encoder'] if regime=='head' else ['--encoder-last-layers','2','--encoder-lr','0.00002']
        status('TRAINING',label);print('Training '+label,flush=True);t=time.perf_counter()
        with (a.out/(label+'.log')).open('w') as log:
            code=subprocess.run(argv,stdout=log,stderr=subprocess.STDOUT).returncode
        records.append({'phase':'train','name':label,'condition':condition,'regime':regime,'data':str(data),
                        'weights':str(weights),'argv':argv,'returncode':code,'elapsed_seconds':time.perf_counter()-t})
        print(json.dumps(records[-1]),flush=True)
        if code:
            status('FAILED_TRAINING',label);return code
    # Training selection is finished before any new calibration or test evaluation.
    for condition,regime,data in jobs:
        label=condition+'-'+regime;weights=a.weights/label
        argv=[sys.executable,str(HERE/'benchmark.py'),'--data',str(data),'--out',str(a.out/label),
              '--candidate','laya','--model',str(weights),'--device',a.device]
        status('EVALUATING',label);print('Evaluating '+label,flush=True);t=time.perf_counter()
        with (a.out/(label+'-evaluation.log')).open('w') as log:
            code=subprocess.run(argv,stdout=log,stderr=subprocess.STDOUT).returncode
        records.append({'phase':'evaluate','name':label,'data':str(data),'argv':argv,'returncode':code,
                        'elapsed_seconds':time.perf_counter()-t})
        if code:
            status('FAILED_EVALUATION',label);return code
    status('RUNS_FINISHED');print('All six local training and evaluation conditions finished',flush=True)
    return 0


if __name__=='__main__':sys.exit(main())
