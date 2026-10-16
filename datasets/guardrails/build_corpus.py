#!/usr/bin/env python3
"""Build a source-linked catalog and preserve upstream expectations separately from observations."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import subprocess

import yaml
from run_upstream import json_results

HERE = Path(__file__).resolve().parent


def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1048576), b''):
            value.update(chunk)
    return value.hexdigest()


def source_ref(source, path):
    relative = str(path)
    return {'repository': source['url'].removesuffix('.git'), 'revision': source['revision'],
            'path': relative, 'url': source['url'].removesuffix('.git')+'/blob/'+source['revision']+'/'+relative,
            'license': source['license']}


def verify_expectation(expected, resource, rows):
    wanted = resource.split('/')
    candidates = []
    for row in rows:
        parts = row.get('RESOURCE', '').split('/')
        if (row.get('POLICY') == expected['policy'] and len(parts) >= 3
                and parts[-3] == expected['kind'] and parts[-1] == wanted[-1]
                and (len(wanted) == 1 or parts[-2] == wanted[-2])
                and (not expected.get('rule') or row.get('RULE') == expected['rule'])):
            candidates.append(row)
    usable = [row for row in candidates if row.get('REASON') == 'Ok']
    verified = len(usable) == 1 and usable[0].get('RESULT') == 'Pass'
    return {'verified_expectation': verified, 'test_rows': candidates,
            'basis': 'unique Ok/Pass contract comparison' if verified else 'missing, ambiguous or unmatched comparison',
            'direct_policy_result': None}


def write_rows(path, rows):
    path.write_text(''.join(json.dumps(row, sort_keys=True)+'\n' for row in rows))
    return {'path': path.name, 'rows': len(rows), 'sha256': digest(path), 'bytes': path.stat().st_size}


def verify_run(base, folder, summary, run):
    artifact = base/'runs'/folder/run['folder']
    if digest(base/'runs'/folder/'RUNNER.py.txt') != summary['runner_sha256']:
        raise ValueError('Runner snapshot differs from execution record')
    if digest(base/run['source']) != run['source_sha256']:
        raise ValueError('Executed input changed')
    for ref in run['input_artifacts']:
        if digest(base/ref['path']) != ref['sha256']:
            raise ValueError('Executed configuration or engine input changed')
    if digest(artifact/'stdout.txt') != run['stdout_sha256'] or digest(artifact/'stderr.txt') != run['stderr_sha256']:
        raise ValueError('Run output changed')
    return artifact


def suite_inputs(path, suite, catalog, root):
    resources = []
    for name in suite['resources']:
        for doc in yaml.safe_load_all((path.parent/name).read_text()):
            if isinstance(doc, dict):
                resources.extend(doc.get('items', []) if doc.get('kind') == 'List' else [doc])
    context = {key: yaml.safe_load((path.parent/suite[key]).read_text())
               for key in ('variables', 'context', 'userinfo') if key in suite}
    paths = {str((path.parent/name).resolve().relative_to(root)) for name in suite['policies']}
    policy_ids = [row['id'] for row in catalog if row['engine'] == 'kyverno' and row['source']['path'] in paths]
    return resources, context, policy_ids


def build(base, out):
    lock = json.loads((HERE/'sources.lock.json').read_text())
    sources = {s['name']: s for s in lock['sources']}
    for name, source in sources.items():
        revision = subprocess.check_output(['git', '-C', str(base/name), 'rev-parse', 'HEAD'], text=True).strip()
        dirty = subprocess.check_output(['git', '-C', str(base/name), 'status', '--porcelain'], text=True)
        if revision != source['revision'] or dirty or digest(base/name/'LICENSE') != source['license_sha256']:
            raise ValueError('Source differs from locked revision')
    catalog = []
    source = sources['kyverno-policies']
    root = base/source['name']
    for path in sorted(root.rglob('*.yaml')):
        if '.git' in path.parts:
            continue
        for index, doc in enumerate(yaml.safe_load_all(path.read_text())):
            if not isinstance(doc, dict) or not doc.get('apiVersion', '').startswith('policies.kyverno.io/') or not doc.get('kind', '').endswith('Policy'):
                continue
            annotations = doc.get('metadata', {}).get('annotations', {})
            relative = path.relative_to(root)
            catalog.append({'id': 'kyverno:'+str(relative)+':'+str(index), 'engine': 'kyverno',
                            'name': doc.get('metadata', {}).get('name'), 'kind': doc['kind'],
                            'role': 'fixture' if any(part.startswith('.') for part in relative.parts) else 'reference',
                            'title': annotations.get('policies.kyverno.io/title', ''),
                            'description': annotations.get('policies.kyverno.io/description', ''),
                            'category': annotations.get('policies.kyverno.io/category', ''),
                            'document': doc, 'source': source_ref(source, relative), 'file_sha256': digest(path)})
    source = sources['falco-rules']
    entities = []
    for name in ('falco_rules.yaml', 'falco-incubating_rules.yaml', 'falco-sandbox_rules.yaml'):
        path = base/'falco-rules/rules'/name
        for index, doc in enumerate(yaml.safe_load(path.read_text())):
            kind = next((key for key in ('rule', 'macro', 'list') if key in doc), None)
            if not kind:
                continue
            row = {'id': 'falco:'+name+':'+str(index), 'engine': 'falco', 'kind': kind, 'name': doc[kind],
                   'ruleset': name, 'document': doc, 'source': source_ref(source, Path('rules')/name),
                   'file_sha256': digest(path)}
            entities.append(row)
            if kind == 'rule':
                catalog.append(row)
    kyverno_run = json.loads((base/'runs/kyverno-verified/SUMMARY.json').read_text())
    for name, revision in kyverno_run['upstream_revisions'].items():
        if revision != sources[name]['revision']:
            raise ValueError('Executed source identity differs')
    cases = []
    for run in kyverno_run['results']:
        suite_path = base/run['source']
        artifact = verify_run(base, 'kyverno-verified', kyverno_run, run)
        if json_results((artifact/'stdout.txt').read_text()) != run['test_rows']:
            raise ValueError('Parsed contract results differ from raw output')
        suite = yaml.safe_load(suite_path.read_text())
        resource_docs, context, policy_ids = suite_inputs(suite_path, suite, catalog, root)
        source = sources['kyverno-policies']
        for index, expected in enumerate(suite['results']):
            for resource in expected['resources']:
                observed = verify_expectation(expected, resource, run['test_rows'])
                names = resource.split('/')
                matched = [doc for doc in resource_docs if doc.get('kind') == expected['kind']
                           and doc.get('metadata', {}).get('name') == names[-1]
                           and (len(names) == 1 or doc.get('metadata', {}).get('namespace', 'default') == names[-2])]
                cases.append({'id': 'kyverno:'+str(suite_path.relative_to(root))+':'+str(index)+':'+resource,
                              'task': 'upstream_policy_expectation', 'family_id': expected['policy'],
                              'inputs': {'policy_ids': policy_ids, 'resource': matched[0] if len(matched) == 1 else None,
                                         'context': context},
                              'expected': expected, 'resource': resource, 'observation': observed,
                              'supervision_origin': 'upstream-authored test, compared by actual CLI',
                              'incident_response_label': None, 'model_input_normalization_required': True,
                              'source': source_ref(source, suite_path.relative_to(root)),
                              'raw_run_folder': str(artifact.relative_to(base)),
                              'scope': 'offline CLI contract; does not establish API-server admission'})
    replays = []
    for folder in ('falco-verified', 'falco-incubating', 'falco-sandbox'):
        summary = json.loads((base/'runs'/folder/'SUMMARY.json').read_text())
        if summary['upstream_revisions']['falco-rules'] != sources['falco-rules']['revision']:
            raise ValueError('Replayed rules revision differs')
        for run in summary['results']:
            artifact = verify_run(base, folder, summary, run)
            alerts = [json.loads(line) for line in (artifact/'stdout.txt').read_text().splitlines()
                      if line.startswith('{') and '"rule"' in line]
            if dict(Counter(row['rule'] for row in alerts)) != run['rule_counts'] or len(alerts) != run['alerts']:
                raise ValueError('Alert counts differ from raw replay output')
            replays.append({'capture': run['source'], 'capture_sha256': run['source_sha256'],
                            'family_id': 'capture:'+run['source_sha256'],
                            'ruleset': summary.get('ruleset') or 'falco_rules.yaml',
                            'completed': run['completed'], 'alerts': run['alerts'], 'rule_counts': run['rule_counts'],
                            'elapsed_seconds': run['elapsed_seconds'], 'image': run['image'],
                            'raw_run_folder': str(artifact.relative_to(base)),
                            'incident_response_label': None,
                            'scope': 'recorded syscall replay; rule matches are not maliciousness labels'})
    out.mkdir(parents=True, exist_ok=False)
    files = [write_rows(out/'catalog.jsonl', catalog), write_rows(out/'falco-entities.jsonl', entities),
             write_rows(out/'kyverno-cases.jsonl', cases), write_rows(out/'falco-replays.jsonl', replays)]
    manifest = {'schema_version': '0.1.0', 'sources_lock_sha256': digest(HERE/'sources.lock.json'),
                'files': files, 'catalog_entries': len(catalog),
                'kyverno_policy_documents_by_role': dict(Counter(r['role'] for r in catalog if r['engine'] == 'kyverno')),
                'falco_rule_definitions': sum(r['engine'] == 'falco' for r in catalog),
                'kyverno_suites_executed': kyverno_run['sources'], 'kyverno_suites_completed': kyverno_run['completed'],
                'kyverno_declared_resource_expectations': len(cases),
                'kyverno_unique_verified_expectations': sum(r['observation']['verified_expectation'] for r in cases),
                'kyverno_cases_with_unique_input_resource': sum(r['inputs']['resource'] is not None for r in cases),
                'kyverno_harness_rows': sum(len(r['test_rows']) for r in kyverno_run['results']),
                'kyverno_excluded_harness_rows': sum(r['reason_counts'].get('Excluded', 0) for r in kyverno_run['results']),
                'falco_distinct_captures': len({r['capture_sha256'] for r in replays}),
                'falco_replay_observations': len(replays), 'falco_replays_completed': sum(r['completed'] for r in replays),
                'falco_rule_names_observed': sorted({name for r in replays for name in r['rule_counts']}),
                'independent_incident_decision_labels': 0, 'production_model_qualified': False,
                'fixture_cues_require_review_before_model_input': True,
                'split_requirement': 'Group policy families and capture hashes; never split repeated replays across folds'}
    (out/'MANIFEST.json').write_text(json.dumps(manifest, indent=2)+'\n')
    print(json.dumps({k: v for k, v in manifest.items() if k not in ('files', 'falco_rule_names_observed')}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    build(args.base.resolve(), args.out.resolve())
