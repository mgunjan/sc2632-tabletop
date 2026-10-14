"""Versioned control review records. Catalog metadata grants no deployment authority."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / 'controls/catalog.json'


def load(path=CATALOG):
    import jsonschema
    import generate as g
    import decider_agent as da
    catalog = json.loads(Path(path).read_text())
    jsonschema.validate(catalog, json.loads((ROOT / 'controls/schema.json').read_text()))
    controls = catalog['controls']
    if set(controls) != set(da.CONTROLS): raise ValueError('Catalog and decision vocabulary differ')
    ids = [c['id'] for c in controls.values()]
    if len(ids) != len(set(ids)): raise ValueError('Duplicate control ID')
    for key, c in controls.items():
        template = g.TEMPLATES.get(key)
        if c['implementation'] != (template.__name__ if template else None) or c['policy'] != g.POLICY_FILE.get(key):
            raise ValueError('Control implementation differs from compiler')
        if template and not c['tests']: raise ValueError('Rendered control has no test reference')
        if not c['limits'] or not c['platform_evidence']: raise ValueError('Missing control limits or evidence requirements')
        for test in c['tests']:
            p = (ROOT / test).resolve()
            if not p.is_relative_to(ROOT) or not p.is_file(): raise ValueError('Invalid test reference')
    return catalog


def review(spec, out=None):
    import generate as g
    g.validate_spec(spec)
    catalog = load(); records = []
    selected = sorted(set(spec['controls']) | {c['control'] for c in spec['clauses']})
    for key in selected:
        c = catalog['controls'][key]
        parameters = spec['controls'].get(key, {})
        policy = g.render_policies(spec, spec['rollout'][-1]).get((c['policy'] or '')+'.yaml')
        exceptions = [e for e in spec['exceptions'] if e['control'] == key]
        excessive = [e['workload'] for e in exceptions if e['ttl_hours'] > c['exception_max_hours']]
        records.append({**c, 'key': key, 'parameters': parameters,
            'parameter_schema': f'generator/schema.json#/properties/controls/properties/{key}' if key in spec['controls'] else None,
            'rendered_sha256': hashlib.sha256(policy.encode()).hexdigest() if policy else None,
            'status': 'EXCEPTION_LIMIT_EXCEEDED' if excessive else 'PLATFORM_EVIDENCE_REQUIRED' if policy else 'HUMAN_IMPLEMENTATION_REQUIRED',
            'excessive_exception_workloads': excessive, 'evidence_status': 'NOT_EXECUTED_BY_CATALOG_REVIEW'})
    result = {'catalog_version': catalog['version'], 'catalog_status': catalog['status'],
              'catalog_sha256': hashlib.sha256(CATALOG.read_bytes()).hexdigest(),
              'compiler_sha256': hashlib.sha256((ROOT/'generator/generate.py').read_bytes()).hexdigest(),
              'spec_sha256': hashlib.sha256(json.dumps(spec, sort_keys=True).encode()).hexdigest(),
              'promotion_allowed': False, 'controls': records,
              'exception_limits_basis': 'Proposed reference limits; enterprise owners must ratify them. No exception is granted.'}
    if out is not None:
        (Path(out)/'control-review.json').write_text(json.dumps(result, indent=2)+'\n')
    return result


def pr_section(result):
    lines = ['', '## Control library review', '',
             f"Reference catalog {result['catalog_version']} (`{result['catalog_sha256'][:12]}`). Platform evidence remains required.", '',
             '| Control | Layer | Status |', '|---|---|---|']
    lines += [f"| {c['id']} / {c['key']} | {c['layer']} | {c['status']} |" for c in result['controls']]
    lines += ['', 'See control-review.json for exact coverage, gaps, test references, owners, exception limits and rollback. Catalog review does not execute these tests or authorize promotion.', '']
    return '\n'.join(lines)


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('--spec', type=Path); ap.add_argument('--out', type=Path)
    a = ap.parse_args()
    if a.spec:
        if a.out: a.out.mkdir(parents=True, exist_ok=True)
        print(json.dumps(review(json.loads(a.spec.read_text()), a.out), indent=2))
    else:
        catalog = load(); print(f"Valid reference catalog {catalog['version']}: {len(catalog['controls'])} controls")
