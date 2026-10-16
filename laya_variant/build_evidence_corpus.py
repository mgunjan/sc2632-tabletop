#!/usr/bin/env python3
"""Normalize examined Falco/Kyverno evidence; never creates training labels."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
BASE = Path('submission/2026-10-16')
WITNESS = 'sc2632-test-witness'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def read(root, path):
    path = Path(path)
    if path.is_absolute() or '..' in path.parts or not (root/path).resolve().is_relative_to(root.resolve()):
        raise ValueError('Evidence must be inside the source checkout')
    return (root/path).read_bytes()


def reference(root, path):
    return {'path': str(path), 'sha256': digest(read(root, path))}


def load(root, path):
    return json.loads(read(root, path))


def keyed(rows, key):
    result = {key(row): row for row in rows}
    if len(result) != len(rows):
        raise ValueError('Duplicate case or observation identity')
    return result


def record(case_id, task, family, inputs, target, refs, observations, controls=None):
    return {'schema_version': '0.1.0', 'id': case_id, 'task': task, 'family_id': family,
            'split': 'regression_only', 'training_eligible': False,
            'inputs': inputs, 'target': target, 'observations': observations,
            'control_ids': controls or [], 'decision_label': None,
            'provenance': {'label_origin': 'presenter-authored behavioral contract',
                           'independent_response_review': False, 'sources': refs}}


def falco_rows(root):
    folder = BASE/'falco-audit'
    contract_path = folder/'repaired/contract.json'
    contract = load(root, contract_path)
    cases = keyed(contract['cases'], lambda c: c['id'])
    receipts = Counter((event['auditID'], event['stage'])
                       for case in cases.values() for event in case['events'])
    observations = {case_id: [] for case_id in cases}
    for name in ('baseline', 'repaired', 'ci-amd64'):
        run = folder/name
        result = load(root, run/'result.json')
        if (result['contract_sha256'] != digest(read(root, contract_path))
                or read(root, run/'contract.json') != read(root, contract_path)
                or result['rules_sha256'] != digest(read(root, run/'rules.yaml'))
                or result['harness_sha256'] != digest(read(root, folder/'verify-falco-audit.py.txt'))):
            raise ValueError('Falco contract, rules or harness provenance mismatch')
        parsed = [json.loads(line) for line in read(root, run/'falco.stdout.jsonl').decode().splitlines()
                  if line.lstrip().startswith('{')]
        received = Counter((r['output_fields']['ka.auditid'], r['output_fields']['ka.stage'])
                           for r in parsed if WITNESS in r.get('tags', []))
        if received != receipts or result['events_received'] != sum(receipts.values()) or result['webhook_http_status'] != 200:
            raise ValueError('Missing or duplicate Falco receipt; absence is not negative evidence')
        checks = keyed(result['checks'], lambda c: c['id'])
        if set(checks) != set(cases) or result['case_count'] != len(cases):
            raise ValueError('Incomplete Falco result identities')
        artifacts = [reference(root, run/path) for path in ('result.json', 'rules.yaml', 'contract.json',
                     'falco.stdout.jsonl', 'falco.stderr.txt', 'falco.yaml', 'witness.yaml')]
        for case_id, case in cases.items():
            matched = [a for a in parsed if a['output_fields'].get('ka.target.name') == case['target_name']
                       and WITNESS not in a.get('tags', [])]
            actual = {'alert_tags': sorted(t for a in matched for t in a.get('tags', [])
                                          if t in ('quarantine-q1', 'quarantine-q2')),
                      'evidence_gap_tags': sorted(t for a in matched for t in a.get('tags', [])
                                                 if t == 'audit-visibility-gap')}
            expected = {'alert_tags': case['expected_alert_tags'],
                        'evidence_gap_tags': case['expected_evidence_gap_tags']}
            check = checks[case_id]
            if (actual['alert_tags'] != check['observed_alerts']
                    or actual['evidence_gap_tags'] != check['observed_evidence_gaps']
                    or expected['alert_tags'] != check['expected_alerts']
                    or expected['evidence_gap_tags'] != check['expected_evidence_gaps']
                    or check['passed'] != (actual == expected)):
                raise ValueError('Falco raw output, target and result disagree')
            observations[case_id].append({'run_id': name, 'engine_identity': result['image_identity'],
                'plugin_sha256': result['plugin_sha256'], 'observed': actual,
                'meets_contract': actual == expected, 'artifacts': artifacts,
                'scope': result['scope']})
        passed = sum(c['passed'] for c in checks.values())
        if result['passed_cases'] != passed or result['status'] != ('PASS' if passed == len(cases) else 'FAIL'):
            raise ValueError('Falco summary does not match observations')
    return [record('falco-audit:'+case_id, 'falco_rule_behavior', 'authored-audit-contract-v1',
                   {'event_source': 'k8s_audit', 'events': case['events']},
                   {'alert_tags': case['expected_alert_tags'], 'evidence_gap_tags': case['expected_evidence_gap_tags']},
                   [reference(root, contract_path)], observations[case_id])
            for case_id, case in cases.items()]


def kyverno_rows(root):
    folder = BASE/'dataset/kyverno'
    suite = yaml.safe_load(read(root, folder/'kyverno-test.yaml'))
    resources = keyed(list(yaml.safe_load_all(read(root, folder/'resources.yaml'))),
                      lambda r: r['metadata']['namespace']+'/'+r['metadata']['name'])
    expected = {}
    for item in suite['results']:
        for name in item['resources']:
            if name in expected:
                raise ValueError('Duplicate Kyverno expectation')
            expected[name] = item['result']
    report = load(root, folder/'apply.json')
    if json.loads(read(root, folder/'apply.stdout.txt')) != report:
        raise ValueError('Parsed Kyverno report differs from raw stdout')
    observed = keyed(report['results'], lambda r: r['resources'][0]['namespace']+'/'+r['resources'][0]['name'])
    execution = load(root, folder/'execution.json')
    for ref in execution['input_sources'] + execution['input_artifacts']:
        if reference(root, ref['path']) != ref:
            raise ValueError('Original Kyverno expectation/resource provenance changed')
    original = yaml.safe_load(read(root, 'generator/contracts/privilege-test.yaml'))
    if (original['results'] != suite['results']
            or read(root, 'generator/contracts/privilege-resources.yaml') != read(root, folder/'resources.yaml')):
        raise ValueError('Copied Kyverno contract does not match recorded source')
    if (set(resources) != set(expected) or set(expected) != set(observed)
            or any(len(r['resources']) != 1 for r in report['results'])
            or any(r['policy'] != 'deny-privilege-escalation' for r in report['results'])
            or execution['runs']['test']['returncode'] != 0
            or '6 tests passed and 0 tests failed' not in read(root, folder/'test.stdout.txt').decode()
            or execution['runs']['apply']['returncode'] != 1):
        raise ValueError('Incomplete or inconsistent Kyverno observations')
    counts = Counter(r['result'] for r in observed.values())
    if any(report['summary'].get(k) != counts[k] for k in ('pass', 'fail', 'skip', 'warn', 'error')):
        raise ValueError('Kyverno summary does not match policy results')
    artifacts = [reference(root, folder/path) for path in ('policy.yaml', 'resources.yaml', 'kyverno-test.yaml',
        'apply.json', 'apply.stdout.txt', 'apply.stderr.txt', 'test.stdout.txt', 'test.stderr.txt', 'execution.json')]
    return [record('kyverno-privilege:'+name, 'kyverno_policy_behavior', 'authored-pod-privilege-v1',
                   {'resource': resource, 'policy_yaml': read(root, folder/'policy.yaml').decode(),
                    'evaluation_context': 'offline CLI; no API-server admission'},
                   {'policy_result': expected[name]}, artifacts,
                   [{'run_id': 'offline-cli-2026-10-16', 'engine_identity': execution['engine_version_output'],
                     'observed': {'policy_result': observed[name]['result']},
                     'meets_contract': observed[name]['result'] == expected[name],
                     'artifacts': artifacts, 'scope': execution['scope']}], ['ACG-POD-001'])
            for name, resource in resources.items()]


def build(root=ROOT):
    rows = sorted(falco_rows(root)+kyverno_rows(root), key=lambda r: r['id'])
    keyed(rows, lambda r: r['id'])
    refs = {ref['path']: ref for row in rows for ref in row['provenance']['sources']}
    for row in rows:
        for observation in row['observations']:
            refs.update({ref['path']: ref for ref in observation['artifacts']})
    for path in (BASE/'falco-audit/verify-falco-audit.py.txt', Path('laya_variant/build_evidence_corpus.py'),
                 Path('generator/contracts/privilege-test.yaml'), Path('generator/contracts/privilege-resources.yaml')):
        refs[str(path)] = reference(root, path)
    manifest = {'schema_version': '0.1.0', 'scope': 'Examined behavioral regression seed; not independent model evaluation',
                'logical_cases': len(rows), 'case_groups': dict(Counter(r['task'] for r in rows)),
                'observations': sum(len(r['observations']) for r in rows),
                'training_eligible_rows': 0, 'independent_response_labels': 0,
                'family_groups': sorted({r['family_id'] for r in rows}),
                'model_ready_inputs': False, 'upstream_collections_imported': False,
                'source_artifacts': sorted(refs.values(), key=lambda ref: ref['path'])}
    return rows, manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    rows, manifest = build()
    data = ''.join(json.dumps(row, sort_keys=True)+'\n' for row in rows).encode()
    manifest['records_sha256'] = digest(data)
    args.out.mkdir(parents=True, exist_ok=False)
    (args.out/'records.jsonl').write_bytes(data)
    (args.out/'MANIFEST.json').write_text(json.dumps(manifest, indent=2)+'\n')
    print(json.dumps({key: manifest[key] for key in ('logical_cases', 'observations', 'training_eligible_rows')}))


if __name__ == '__main__':
    main()
