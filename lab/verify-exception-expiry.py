#!/usr/bin/env python3
"""Observe actual exception deletion and renewed admission denial on a marked lab.

Uses the existing five-minute DeletingPolicy schedule. The same Pod CREATE request
is denied before the exception, admitted while active, and denied after cleanup.
It does not test termination of existing Pods, sessions or exposed credentials.
"""
import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
import subprocess
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--kubeconfig', type=Path, required=True)
    ap.add_argument('--context', required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--timeout', type=int, default=420)
    a = ap.parse_args()
    if not a.context.startswith('k3d-sc2632-rehearsal-'): ap.error('Use the named disposable rehearsal context')
    if not 300 <= a.timeout <= 600: ap.error('Timeout must be 300..600 seconds for the five-minute schedule')
    if a.out.exists() and any(a.out.iterdir()): ap.error('Preserve previous evidence; use a new directory')
    base = ['kubectl', '--kubeconfig', str(a.kubeconfig.resolve()), '--context', a.context, '--request-timeout=10s']
    def call(args, body=None):
        return subprocess.run(base+args, input=json.dumps(body) if body is not None else None,
                              capture_output=True, text=True, timeout=25, cwd=ROOT)
    marker = call(['-n','kube-public','get','configmap','trustfall-lab','-o','json'])
    if marker.returncode: raise SystemExit('REFUSED: named context has no lab marker')
    marker_data = json.loads(marker.stdout)
    if marker_data.get('data', {}).get('created-by') != 'lab/setup.sh':
        raise SystemExit('REFUSED: marker does not identify the disposable SC2632 bootstrap')
    a.out.mkdir(parents=True, exist_ok=True)
    evidence = {'context': a.context, 'scope': 'PolicyException cleanup and new Pod admission only',
                'source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                'started_at': dt.datetime.now(dt.timezone.utc).isoformat(),
                'status': 'IN_PROGRESS', 'steps': []}
    def save(): (a.out/'result.json').write_text(json.dumps(evidence,indent=2)+'\n')
    def need(result, description):
        evidence['steps'].append({'step':description,'returncode':result.returncode,
                                  'stdout':result.stdout.strip(),'stderr':result.stderr.strip()})
        save()
        if result.returncode: raise RuntimeError(description+' failed')
    # Restore the reviewed Q0 policies on this disposable lab only.
    for level in ['q3','q2','q1']:
        need(call(['delete','-f',str(ROOT/'quarantine'/level),'--ignore-not-found']),f'remove {level}')
    need(call(['apply','-f',str(ROOT/'scenarios/a-compromised-library/policies')]),'restore baseline admission')
    need(call(['apply','-f',str(ROOT/'network/payments-baseline-networkpolicies.yaml')]),'restore baseline network')
    need(call(['apply','-f',str(ROOT/'exceptions/expire-policy-exceptions.yaml')]),'ensure unchanged expiry controller policy')
    policy = call(['get','deletingpolicy.policies.kyverno.io','expire-policy-exceptions','-o','json'])
    need(policy,'read expiry policy'); cfg=json.loads(policy.stdout)
    if cfg['spec']['schedule'] != '*/5 * * * *': raise RuntimeError('Unexpected cleanup schedule')
    evidence['cleanup_schedule']=cfg['spec']['schedule']
    evidence['policy_sha256'] = hashlib.sha256((ROOT/'exceptions/expire-policy-exceptions.yaml').read_bytes()).hexdigest()
    evidence['rbac_sha256'] = hashlib.sha256((ROOT/'exceptions/cleanup-policy-exceptions-rbac.yaml').read_bytes()).hexdigest()
    principal = 'system:serviceaccount:kyverno:kyverno-cleanup-controller'
    for namespace, expected in [('payments', 'yes'), ('inventory', 'no')]:
        r = call(['auth','can-i','delete','policyexceptions.policies.kyverno.io',
                  '-n',namespace,'--as='+principal])
        evidence['steps'].append({'step': 'cleanup delete authority in '+namespace,
                                  'returncode': r.returncode, 'stdout': r.stdout.strip(), 'stderr': r.stderr.strip()})
        save()
        if r.stdout.strip() != expected:
            evidence['status'] = 'FAIL'; evidence['error'] = 'Unexpected cleanup deletion scope in '+namespace; save()
            raise RuntimeError(evidence['error'])
    name='sc2632-expiry-'+uuid.uuid4().hex[:8]
    pod={'apiVersion':'v1','kind':'Pod','metadata':{'name':name,'namespace':'payments',
         'labels':{'trustfall.example/egress-profile':'storage'}},
         'spec':{'containers':[{'name':'app','image':'registry.trustfall.internal/platform/lab-target:1',
                   'securityContext':{'allowPrivilegeEscalation':False,'privileged':False}}]}}
    (a.out/'pod.json').write_text(json.dumps(pod,indent=2)+'\n')
    def admission(expected):
        r=call(['create','--dry-run=server','-f','-','-o','name'],pod)
        evidence['steps'].append({'step':'admission '+expected,'returncode':r.returncode,'stdout':r.stdout.strip(),'stderr':r.stderr.strip()})
        save()
        if expected=='deny':
            if r.returncode==0 or 'must carry label trustfall.example/egress-profile' not in r.stderr:
                raise RuntimeError('Expected the specific egress-profile denial')
        elif r.returncode: raise RuntimeError('Expected admission under the active exception')
        print('PASS admission '+expected,flush=True)
    admission('deny')
    expires=dt.datetime.now(dt.timezone.utc)+dt.timedelta(seconds=45)
    ex={'apiVersion':'policies.kyverno.io/v1','kind':'PolicyException','metadata':{'name':name,'namespace':'payments',
        'labels':{'trustfall.example/expiring':'true'},'annotations':{'trustfall.example/owner':'sc2632-rehearsal',
        'trustfall.example/reason':'Disposable expiry proof for one exact Pod CREATE request',
        'trustfall.example/expires-at':expires.isoformat().replace('+00:00','Z')}},
        'spec':{'policyRefs':[{'name':'restrict-egress-profile','kind':'ValidatingPolicy'}],
          'matchConditions':[{'name':'exact-rehearsal-pod','expression':f"object.metadata.namespace == 'payments' && object.metadata.name == '{name}'"}]}}
    (a.out/'exception.json').write_text(json.dumps(ex,indent=2)+'\n')
    evidence['expires_at']=ex['metadata']['annotations']['trustfall.example/expires-at'];save()
    try:
        need(call(['create','-f','-'],ex),'create exact scoped exception')
        # Observe propagation; an unrelated failure is never treated as successful admission.
        for _ in range(15):
            r=call(['create','--dry-run=server','-f','-','-o','name'],pod)
            if r.returncode==0: break
            if 'must carry label trustfall.example/egress-profile' not in r.stderr: raise RuntimeError('Unexpected admission failure during propagation')
            time.sleep(1)
        admission('admit')
        end=time.monotonic()+a.timeout
        while time.monotonic()<end:
            r=call(['-n','payments','get','policyexception.policies.kyverno.io',name,'--ignore-not-found','-o','name'])
            if r.returncode: raise RuntimeError('Could not observe cleanup')
            if not r.stdout.strip():
                observed=dt.datetime.now(dt.timezone.utc)
                if observed<expires: raise RuntimeError('Exception deleted before its declared expiry')
                evidence['deletion_observed_at']=observed.isoformat()
                evidence['observed_cleanup_lag_seconds']=round((observed-expires).total_seconds(),1)
                print('PASS exception deleted after expiry; lag',evidence['observed_cleanup_lag_seconds'],'seconds',flush=True)
                break
            print('WAIT scheduled cleanup; exception still exists',flush=True)
            time.sleep(15)
        else: raise RuntimeError('Timed out waiting for actual scheduled deletion')
        admission('deny')
        evidence['status']='PASS';save()
    except Exception as exc:
        evidence['status']='FAIL';evidence['error']=str(exc);save();raise
    finally:
        # Only the specifically created exception; never bulk-delete exceptions.
        r = call(['-n','payments','delete','policyexception.policies.kyverno.io',name,'--ignore-not-found'])
        evidence['steps'].append({'step': 'final cleanup', 'returncode': r.returncode,
                                  'stdout': r.stdout.strip(), 'stderr': r.stderr.strip()})
        evidence['finished_at'] = dt.datetime.now(dt.timezone.utc).isoformat()
        if r.returncode:
            evidence['status'] = 'FAIL'
            evidence['cleanup_error'] = 'Could not remove the specifically named probe exception'
        save()
        if r.returncode: raise RuntimeError(evidence['cleanup_error'])


if __name__=='__main__': main()
