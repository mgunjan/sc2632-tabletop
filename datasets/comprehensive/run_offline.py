#!/usr/bin/env python3
"""Execute only offline policy fixtures in bounded, isolated containers; never run attack procedures."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
import uuid

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent/'guardrails'))
from run_upstream import json_results
from collect import sha, verify_source


def run_one(job, cache, legacy, out, image):
    folder = out/job['id']
    folder.mkdir()
    name = 'acg-corpus-'+uuid.uuid4().hex
    cmd = ['docker', 'run', '--rm', '--name', name, '--label', 'acg.dataset=comprehensive-20261017',
           '--network', 'none', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges',
           '--read-only', '--user', '65534:65534', '--cpus', '1', '--memory', '1g',
           '--tmpfs', '/tmp:rw,nosuid,noexec,size=128m', '--env', 'HOME=/tmp',
           '--mount', f'type=bind,src={cache},dst=/data,readonly',
           '--mount', f'type=bind,src={legacy}/bin,dst=/legacy-bin,readonly', image, *job['args']]
    start = time.monotonic()
    timed_out = False
    try:
        with (folder/'stdout.txt').open('w') as stdout, (folder/'stderr.txt').open('w') as stderr:
            process = subprocess.Popen(cmd, stdout=stdout, stderr=stderr)
            try:
                code = process.wait(timeout=180)
            except subprocess.TimeoutExpired:
                timed_out = True
                subprocess.run(['docker','rm','-f',name],capture_output=True,timeout=10)
                process.kill(); process.wait(timeout=10); code = None
    finally:
        subprocess.run(['docker','rm','-f',name],capture_output=True,timeout=15)
    text = (folder/'stdout.txt').read_text(errors='replace')
    rows = json_results(text) if job['engine'] == 'kyverno' else []
    result = {'id':job['id'], 'engine':job['engine'], 'source':job['source'],
              'elapsed_seconds':round(time.monotonic()-start,6), 'returncode':code,
              'timed_out':timed_out, 'process_succeeded':code == 0 and not timed_out,
              'stdout_sha256':sha(folder/'stdout.txt'), 'stderr_sha256':sha(folder/'stderr.txt'),
              'test_rows':rows, 'image':image, 'argv':cmd,
              'scope':'Offline harness comparison; no API server, kernel capture or attack execution'}
    (folder/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cache',type=Path,required=True)
    parser.add_argument('--legacy-cache',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--image',required=True)
    parser.add_argument('--kind',choices=('gatekeeper','kyverno-legacy'),required=True)
    args = parser.parse_args()
    if not (args.image.startswith('sha256:') or '@sha256:' in args.image):
        parser.error('Pin the image digest')
    cache=args.cache.resolve(); legacy=args.legacy_cache.resolve();out=args.out.resolve()
    runtime=json.loads((HERE/'runtime.lock.json').read_text())
    if args.image!=runtime['image']:raise ValueError('Image differs from recorded runtime')
    sources=json.loads((HERE/'sources.lock.json').read_text())['sources']
    wanted='gatekeeper-library' if args.kind=='gatekeeper' else 'kyverno-legacy'
    verify_source(cache/wanted,next(s for s in sources if s['name']==wanted))
    out.mkdir(parents=True,exist_ok=False)
    (out/'SOURCES.lock.json').write_bytes((HERE/'sources.lock.json').read_bytes())
    jobs=[]
    if args.kind=='gatekeeper':
        for engine in ('rego','cel'):
            jobs.append({'id':engine,'engine':'gator-'+engine,'source':'gatekeeper-library/library',
                         'args':['/data/bin/gator','verify','/data/gatekeeper-library/library/...',
                                 '--enable-k8s-native-validation='+str(engine=='cel').lower(),'--verbose']})
        binary=cache/'bin/gator'
    else:
        for path in sorted((cache/'kyverno-legacy').rglob('kyverno-test.yaml')):
            relative=str(path.relative_to(cache));ident=hashlib.sha256(relative.encode()).hexdigest()[:16]
            jobs.append({'id':ident,'engine':'kyverno','source':relative,
                         'args':['/legacy-bin/kyverno','test','/data/'+str(path.parent.relative_to(cache)),
                                 '--require-tests','--output-format','json','--remove-color']})
        binary=legacy/'bin/kyverno'
    artifact=next(a for a in runtime['artifacts'] if a['executable']==('gator' if args.kind=='gatekeeper' else 'kyverno'))
    if sha(binary)!=artifact['binary_sha256']:raise ValueError('Executable differs from runtime lock')
    if not jobs:raise ValueError('No fixtures found')
    runner=Path(__file__).read_bytes();(out/'RUNNER.py.txt').write_bytes(runner)
    start=time.monotonic();results=[]
    with ThreadPoolExecutor(max_workers=3) as pool:
        pending=[pool.submit(run_one,j,cache,legacy,out,args.image) for j in jobs]
        for future in as_completed(pending):
            result=future.result();results.append(result)
            if len(results)%25==0 or len(results)==len(jobs):
                print(json.dumps({'completed_processes':len(results),'total':len(jobs),
                                  'exit_zero':sum(r['process_succeeded'] for r in results)}),flush=True)
    result={'kind':args.kind,'sources_lock_sha256':sha(HERE/'sources.lock.json'),
            'runner_sha256':hashlib.sha256(runner).hexdigest(),'binary_sha256':sha(binary),
            'image':args.image,'processes':len(results),'exit_zero':sum(r['process_succeeded'] for r in results),
            'elapsed_seconds':round(time.monotonic()-start,6),'results':sorted(results,key=lambda r:r['id'])}
    (out/'SUMMARY.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='results'}))


if __name__=='__main__':main()
