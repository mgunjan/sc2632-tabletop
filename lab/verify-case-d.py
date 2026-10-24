#!/usr/bin/env python3
"""Case D: real bearer-token reads, network isolation, RBAC narrowing and rotation.

Only a marked, loopback k3d SC2632 lab is accepted. All read targets are synthetic
Secrets in newly created namespaces. Tokens stay in memory and never enter logs,
files, command arguments or the published result. Stand-in HTTP health is not a
claim that a real monitoring pipeline has been qualified.
"""
import argparse
import base64
import datetime as dt
import hashlib
import ipaddress
import json
from pathlib import Path
import ssl
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

ROOT = Path(__file__).resolve().parents[1]
IMAGE = 'registry.trustfall.internal/platform/lab-target:1'


def utc(): return dt.datetime.now(dt.timezone.utc).isoformat()


def probe_standin_health(lab, namespace, timeout=8):
    """A positive Service-path control, without persisting response contents."""
    try:
        response = lab.call(['-n', namespace, 'exec', 'positive-control', '--', 'wget',
                             '-q', '-T', '3', '-O', '-', 'http://collector:8080/'], timeout=timeout)
    except subprocess.TimeoutExpired:
        return {'healthy': False, 'returncode': None, 'expected_body': False, 'error': 'PROBE_TIMEOUT'}
    expected = 'trustfall lab stand-in' in response.stdout
    return {'healthy': response.returncode == 0 and expected,
            'returncode': response.returncode, 'expected_body': expected}


def wait_for_baseline_service(lab, namespace, record, seconds=30):
    """Pod TCP readiness does not establish Service/DNS readiness. Wait only before intervention."""
    deadline = time.monotonic() + seconds
    attempt = 0
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise RuntimeError('Baseline Service path did not become healthy within the startup deadline')
        attempt += 1
        observation = probe_standin_health(lab, namespace, timeout=min(8, remaining))
        record({'description': 'baseline Service startup readiness', 'attempt': attempt, **observation})
        if observation['healthy']:
            return
        time.sleep(min(1, max(0, deadline - time.monotonic())))


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, url):
        return None


class Lab:
    def __init__(self, kubeconfig, context):
        if not context.startswith('k3d-sc2632-rehearsal-'):
            raise ValueError('REFUSED: use the named disposable SC2632 rehearsal context')
        self.command = ['kubectl', '--kubeconfig', str(Path(kubeconfig).resolve()),
                        '--context', context, '--request-timeout=10s']
        marker = self.call(['-n', 'kube-public', 'get', 'configmap', 'trustfall-lab', '-o', 'json'])
        if marker.returncode or json.loads(marker.stdout).get('data', {}).get('created-by') != 'lab/setup.sh':
            raise ValueError('REFUSED: lab ownership marker is absent or unexpected')
        # Read only public TLS data and the endpoint, never admin credentials.
        server = self.call(['config', 'view', '--minify', '-o', 'jsonpath={.clusters[0].cluster.server}'])
        ca = self.call(['config', 'view', '--minify', '--raw', '-o', 'jsonpath={.clusters[0].cluster.certificate-authority-data}'])
        self.server = server.stdout.strip()
        url = urllib.parse.urlparse(self.server)
        if (server.returncode or ca.returncode or url.scheme != 'https' or url.hostname not in ('127.0.0.1', 'localhost')
                or url.username or url.password or url.query or url.fragment or url.path not in ('', '/')):
            raise ValueError('REFUSED: target must be the isolated loopback HTTPS API server')
        if not ca.stdout.strip(): raise ValueError('REFUSED: missing API-server CA')
        self.ssl = ssl.create_default_context(cadata=base64.b64decode(ca.stdout).decode())
        # A desktop proxy or redirect must never receive the rehearsal bearer token.
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}),
                                                  urllib.request.HTTPSHandler(context=self.ssl), NoRedirect())

    def call(self, args, body=None, timeout=25):
        return subprocess.run(self.command + args, input=json.dumps(body) if body is not None else None,
                              text=True, capture_output=True, timeout=timeout, cwd=ROOT)

    def api(self, token, path, body=None):
        request = urllib.request.Request(self.server + path, method='POST' if body is not None else 'GET',
                                        data=json.dumps(body).encode() if body is not None else None,
                                        headers={'Authorization': 'Bearer '+token, 'Content-Type': 'application/json'})
        try:
            with self.opener.open(request, timeout=5) as response:
                status, raw = response.status, response.read()
        except urllib.error.HTTPError as error:
            status, raw = error.code, error.read()
        try: data = json.loads(raw)
        except (UnicodeError, json.JSONDecodeError): raise RuntimeError('Unexpected Kubernetes response shape') from None
        return status, data


def manifests(namespaces, role_name):
    observer, inventory, database = namespaces
    def meta(name, namespace=None):
        return {'name': name, **({'namespace': namespace} if namespace else {}),
                'labels': {'sc2632.example/owner': 'case-d-rehearsal'}}
    workload = lambda name, app: {'apiVersion': 'v1', 'kind': 'Pod', 'metadata': {**meta(name, observer),
        'labels': {'app': app, 'sc2632.example/suspect': 'true' if name == 'collector-old' else 'false'}},
        'spec': {'serviceAccountName': 'collector', 'automountServiceAccountToken': False,
                 'containers': [{'name': 'http', 'image': IMAGE, 'imagePullPolicy': 'IfNotPresent',
                                 'readinessProbe': {'tcpSocket': {'port': 8080}, 'periodSeconds': 1},
                                 'securityContext': {'allowPrivilegeEscalation': False, 'privileged': False,
                                                     'runAsNonRoot': True, 'capabilities': {'drop': ['ALL']},
                                                     'seccompProfile': {'type': 'RuntimeDefault'}}}]}}
    scoped = [{'apiVersion': 'rbac.authorization.k8s.io/v1', 'kind': 'Role', 'metadata': meta('metrics-config-reader', observer),
               'rules': [{'apiGroups': [''], 'resources': ['configmaps'], 'resourceNames': ['metrics-targets'], 'verbs': ['get']},
                         {'apiGroups': [''], 'resources': ['secrets'], 'resourceNames': ['monitoring-client-key'], 'verbs': ['get']}]},
              {'apiVersion': 'rbac.authorization.k8s.io/v1', 'kind': 'RoleBinding', 'metadata': meta('metrics-config-reader', observer),
               'roleRef': {'apiGroup': 'rbac.authorization.k8s.io', 'kind': 'Role', 'name': 'metrics-config-reader'},
               'subjects': [{'kind': 'ServiceAccount', 'name': 'collector', 'namespace': observer}]}]
    broad = [{'apiVersion': 'rbac.authorization.k8s.io/v1', 'kind': 'ClusterRole', 'metadata': meta(role_name),
              'rules': [{'apiGroups': [''], 'resources': ['secrets'], 'verbs': ['get', 'list']}]},
             {'apiVersion': 'rbac.authorization.k8s.io/v1', 'kind': 'ClusterRoleBinding', 'metadata': meta(role_name),
              'roleRef': {'apiGroup': 'rbac.authorization.k8s.io', 'kind': 'ClusterRole', 'name': role_name},
              'subjects': [{'kind': 'ServiceAccount', 'name': 'collector', 'namespace': observer}]}]
    objects = [{'apiVersion': 'v1', 'kind': 'Namespace', 'metadata': meta(n)} for n in namespaces]
    objects += [{'apiVersion': 'v1', 'kind': 'ServiceAccount', 'metadata': meta('collector', observer), 'automountServiceAccountToken': False},
                {'apiVersion': 'v1', 'kind': 'ConfigMap', 'metadata': meta('metrics-targets', observer), 'data': {'targets': 'stand-in-only'}}]
    objects += [{'apiVersion': 'v1', 'kind': 'Secret', 'metadata': meta('monitoring-client-key', observer),
                 'type': 'Opaque', 'stringData': {'api-key': 'SC2632-DUMMY-NOT-A-REAL-CREDENTIAL'}}]
    objects += [{'apiVersion': 'v1', 'kind': 'Secret', 'metadata': meta('synthetic-application-key', n), 'type': 'Opaque',
                 'stringData': {'api-key': 'SC2632-DUMMY-NOT-A-REAL-CREDENTIAL'}} for n in [inventory, database]]
    objects += [workload('collector-old', 'case-d-collector'), workload('positive-control', 'case-d-control'),
                {'apiVersion': 'v1', 'kind': 'Service', 'metadata': meta('collector', observer),
                 'spec': {'selector': {'app': 'case-d-collector'}, 'ports': [{'port': 8080, 'targetPort': 8080}]}}] + scoped + broad
    quarantine = {'apiVersion': 'networking.k8s.io/v1', 'kind': 'NetworkPolicy', 'metadata': meta('collector-no-egress', observer),
                  'spec': {'podSelector': {'matchLabels': {'app': 'case-d-collector', 'sc2632.example/suspect': 'true'}},
                           'policyTypes': ['Egress'], 'egress': []}}
    return objects, scoped, broad, quarantine, workload('collector-new', 'case-d-collector')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--kubeconfig', type=Path, required=True)
    parser.add_argument('--context', required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists() and any(args.out.iterdir()): parser.error('Preserve prior evidence; use a fresh output directory')
    lab = Lab(args.kubeconfig, args.context)
    args.out.mkdir(parents=True, exist_ok=True)
    suffix = uuid.uuid4().hex[:8]
    namespaces = [f'sc2632-d-{n}-{suffix}' for n in ['observe', 'inventory', 'database']]
    observer = namespaces[0]; role_name = 'sc2632-d-secret-reader-'+suffix
    objects, scoped, broad, quarantine, replacement = manifests(namespaces, role_name)
    result = {'status': 'IN_PROGRESS', 'started_at': utc(), 'context': args.context, 'namespaces': namespaces,
              'source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'scope': 'Synthetic Secret reads in two fresh namespaces; real bearer-token authentication and CNI/RBAC changes',
              'limits': ['Stand-in HTTP health is not real monitoring delivery.', 'No external application credential is revoked.',
                         'No audit-server export is collected.', 'No generator scenario d or model-generated RBAC is claimed.'],
              'checks': [], 'operations': [], 'tokens': [], 'cleanup': []}
    def save(): (args.out/'result.json').write_text(json.dumps(result, indent=2)+'\n')
    def command(description, argv, body=None, timeout=25, secret_response=False):
        response = lab.call(argv, body, timeout)
        # TokenRequest output is intentionally excluded even on failure.
        result['operations'].append({'description': description, 'returncode': response.returncode,
                                     **({} if secret_response else {'stdout': response.stdout.strip(), 'stderr': response.stderr.strip()})})
        save()
        if response.returncode: raise RuntimeError(description+' failed')
        return response.stdout
    def check(description, good, **metadata):
        result['checks'].append({'description': description, 'passed': bool(good), **metadata}); save()
        if not good: raise RuntimeError(description+' failed')
        print('PASS '+description, flush=True)
    def api_check(description, token, path, expected, body=None):
        code, payload = lab.api(token, path, body)
        check(description, code == expected, http_status=code, expected=expected, path=path)
        return payload
    def tcp(pod):
        return lab.call(['-n', observer, 'exec', pod, '--', 'sh', '-c', 'nc -w 2 '+api_ip+' 443 </dev/null >/dev/null 2>&1']).returncode == 0
    def health(description):
        observation = probe_standin_health(lab, observer)
        check(description, observation['healthy'], **observation)
    def issue_token(pod):
        uid = command('read bound Pod UID', ['-n', observer, 'get', 'pod', pod, '-o', 'jsonpath={.metadata.uid}'])
        payload = {'apiVersion': 'authentication.k8s.io/v1', 'kind': 'TokenRequest',
                   'spec': {'expirationSeconds': 600, 'boundObjectRef': {'kind': 'Pod', 'apiVersion': 'v1', 'name': pod, 'uid': uid}}}
        raw = command('issue memory-only Pod-bound token', ['create', '--raw', '/api/v1/namespaces/'+observer+'/serviceaccounts/collector/token', '-f', '-'], payload, secret_response=True)
        data = json.loads(raw)['status']
        result['tokens'].append({'pod': pod, 'pod_uid': uid, 'expires_at': data['expirationTimestamp'], 'stored': False}); save()
        return data['token'], data['expirationTimestamp']
    def secrets(phase, token, expected):
        for namespace in namespaces[1:]:
            base = '/api/v1/namespaces/'+namespace+'/secrets'
            for method, path in [('LIST', base), ('GET', base+'/synthetic-application-key')]:
                payload = api_check(phase+' copied token '+method+' in '+namespace, token, path, expected)
                if expected == 200:
                    names = [x['metadata']['name'] for x in payload['items']] if method == 'LIST' else [payload['metadata']['name']]
                    check(phase+' reads only this run\'s synthetic target', names == ['synthetic-application-key'])
    def cluster_list_permission(phase, token, allowed):
        payload = api_check(phase+' access review is authenticated', token, '/apis/authorization.k8s.io/v1/selfsubjectaccessreviews', 201,
                            {'apiVersion': 'authorization.k8s.io/v1', 'kind': 'SelfSubjectAccessReview',
                             'spec': {'resourceAttributes': {'verb': 'list', 'group': '', 'resource': 'secrets'}}})
        check(phase+' cluster-wide Secret LIST authorization', payload['status']['allowed'] is allowed, allowed=payload['status']['allowed'])
    created_namespaces = []; created_cluster_objects = []
    try:
        for obj in objects:
            # CREATE refuses collision; cleanup only tracks resources we created successfully.
            command('create '+obj['kind']+'/'+obj['metadata']['name'], ['create', '-f', '-'], obj)
            if obj['kind'] == 'Namespace': created_namespaces.append(obj['metadata']['name'])
            if obj['kind'] in ('ClusterRole', 'ClusterRoleBinding'): created_cluster_objects.append((obj['kind'].lower(), obj['metadata']['name']))
        for name, value in [('before-rbac.json', broad+scoped), ('after-rbac.json', scoped), ('network-quarantine.json', [quarantine]), ('replacement-pod.json', [replacement])]:
            (args.out/name).write_text(json.dumps({'apiVersion': 'v1', 'kind': 'List', 'items': value}, indent=2)+'\n')
        command('wait for stand-in and positive control', ['-n', observer, 'wait', '--for=condition=Ready', 'pod/collector-old', 'pod/positive-control', '--timeout=60s'], timeout=75)
        def startup_observation(observation):
            result['operations'].append(observation)
            save()
        wait_for_baseline_service(lab, observer, startup_observation)
        api_ip = command('read API Service IP for DNS-independent probes', ['-n', 'default', 'get', 'service', 'kubernetes', '-o', 'jsonpath={.spec.clusterIP}'])
        ipaddress.ip_address(api_ip)
        token, expiry = issue_token('collector-old')
        config_path = '/api/v1/namespaces/'+observer+'/configmaps/metrics-targets'
        required_secret = '/api/v1/namespaces/'+observer+'/secrets/monitoring-client-key'
        secrets('baseline', token, 200); cluster_list_permission('baseline', token, True)
        api_check('baseline required ConfigMap GET', token, config_path, 200)
        api_check('baseline required named in-namespace Secret GET', token, required_secret, 200)
        check('baseline collector reaches API TCP endpoint', tcp('collector-old'))
        check('baseline positive control reaches API TCP endpoint', tcp('positive-control'))
        health('baseline stand-in health remains available')

        command('apply collector egress quarantine', ['create', '-f', '-'], quarantine)
        for _ in range(15):
            if not tcp('collector-old'): break
            time.sleep(1)
        check('quarantined collector cannot open new API TCP connection', not tcp('collector-old'))
        check('unquarantined positive control still reaches API TCP endpoint', tcp('positive-control'))
        health('stand-in health remains available under quarantine')
        secrets('after network quarantine', token, 200)
        api_check('after quarantine required named in-namespace Secret GET', token, required_secret, 200)

        command('remove the excess cluster-wide binding', ['delete', 'clusterrolebinding', role_name])
        # Observe authorization propagation on a synthetic GET, retaining only status codes.
        deadline = time.monotonic()+30
        while time.monotonic() < deadline:
            code, _ = lab.api(token, '/api/v1/namespaces/'+namespaces[1]+'/secrets/synthetic-application-key')
            if code == 403: break
            if code != 200: raise RuntimeError('Unexpected response while observing RBAC propagation')
            time.sleep(1)
        secrets('after RBAC narrowing', token, 403); cluster_list_permission('after RBAC narrowing', token, False)
        api_check('same old token retains required ConfigMap GET', token, config_path, 200)
        api_check('same old token retains only required named in-namespace Secret GET', token, required_secret, 200)
        api_check('same old token cannot LIST in-namespace Secrets', token, '/api/v1/namespaces/'+observer+'/secrets', 403)
        health('stand-in health remains available after RBAC narrowing')

        command('create replacement collector before revocation', ['create', '-f', '-'], replacement)
        command('wait for replacement health', ['-n', observer, 'wait', '--for=condition=Ready', 'pod/collector-new', '--timeout=60s'], timeout=75)
        new_token, _ = issue_token('collector-new')
        api_check('replacement credential retains required ConfigMap GET', new_token, config_path, 200)
        api_check('replacement credential retains required named Secret GET', new_token, required_secret, 200)
        check('clean replacement opens its required API TCP connection', tcp('collector-new'))
        remaining = (dt.datetime.fromisoformat(expiry.replace('Z', '+00:00'))-dt.datetime.now(dt.timezone.utc)).total_seconds()
        check('old credential remains far from natural expiry', remaining > 180, remaining_seconds=round(remaining, 1))
        deleted_at = time.monotonic()
        command('delete only the old bound Pod', ['-n', observer, 'delete', 'pod', 'collector-old', '--wait=false'])
        deadline = time.monotonic()+120
        observed = False
        while time.monotonic() < deadline:
            code, _ = lab.api(token, config_path)
            result['operations'].append({'description': 'observe old credential after bound-Pod deletion', 'http_status': code}); save()
            if code == 401:
                observed = True; break
            if code != 200: raise RuntimeError('Unexpected old-credential status during revocation')
            health('replacement stand-in remains available while revocation propagates')
            print('WAIT bound-token invalidation', flush=True)
            time.sleep(5)
        check('old bound credential is rejected by authentication', observed, http_status=401 if observed else code,
              observed_seconds_after_delete=round(time.monotonic()-deleted_at, 1))
        api_check('replacement credential remains authenticated after old-token revocation', new_token, config_path, 200)
        api_check('replacement named Secret access remains available', new_token, required_secret, 200)
        api_check('replacement credential cannot LIST in-namespace Secrets', new_token, '/api/v1/namespaces/'+observer+'/secrets', 403)
        secrets('replacement credential', new_token, 403)
        health('replacement stand-in health remains available')
        result['status'] = 'PASS'
    except Exception as error:
        result['status'] = 'FAIL'; result['error'] = str(error)
        print('FAIL '+str(error), flush=True)
    finally:
        for kind, name in reversed(created_cluster_objects):
            response = lab.call(['delete', kind, name, '--ignore-not-found', '--wait=false'])
            result['cleanup'].append({'kind': kind, 'name': name, 'returncode': response.returncode})
        for namespace in created_namespaces:
            response = lab.call(['delete', 'namespace', namespace, '--ignore-not-found', '--wait=false'])
            result['cleanup'].append({'kind': 'namespace', 'name': namespace, 'returncode': response.returncode})
        if any(x['returncode'] for x in result['cleanup']):
            result['status'] = 'FAIL'; result['cleanup_error'] = 'A specifically created lab resource could not be removed'
        result['finished_at'] = utc(); result['passed_checks'] = sum(x['passed'] for x in result['checks']); save()
    print('CASE D '+result['status']+'; '+str(result['passed_checks'])+' checks', flush=True)
    return 0 if result['status'] == 'PASS' else 1


if __name__ == '__main__': raise SystemExit(main())
