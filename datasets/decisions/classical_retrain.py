#!/usr/bin/env python3
"""Run the two prespecified classical controls after local neural work finishes."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time

HERE=Path(__file__).resolve().parent

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    for key in ('source','masked','neural-runs','out'):ap.add_argument('--'+key,type=Path,required=True)
    a=ap.parse_args()
    if json.loads((a.neural_runs/'RUN-STATUS.json').read_text())['state']!='RUNS_FINISHED':
        raise SystemExit('Finish neural training and evaluation before these timed controls')
    a.out.mkdir(parents=True,exist_ok=False);records=[];start=time.perf_counter()
    (a.out/'RUNNER.py.txt').write_bytes(Path(__file__).read_bytes())
    def status(state):
        (a.out/'RUN-STATUS.json').write_text(json.dumps({'state':state,'runs':records,'elapsed_seconds':time.perf_counter()-start},indent=2)+'\n')
    for name,data in (('no-reference-candidate-lr',a.masked),('source-candidate-lr',a.source)):
        status('RUNNING');t=time.perf_counter()
        argv=[sys.executable,str(HERE/'benchmark.py'),'--data',str(data),'--out',str(a.out/name),'--candidate','candidate-lr']
        with (a.out/(name+'.log')).open('w') as log:code=subprocess.run(argv,stdout=log,stderr=subprocess.STDOUT).returncode
        records.append({'name':name,'argv':argv,'returncode':code,'elapsed_seconds':time.perf_counter()-t})
        if code:status('FAILED');raise SystemExit(code)
    status('RUNS_FINISHED');print(json.dumps(records,indent=2))
