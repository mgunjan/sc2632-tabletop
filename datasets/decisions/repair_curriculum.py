#!/usr/bin/env python3
"""Complete-case counterfactual curriculum; source text is not a decision label."""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import shutil

from build import ROOT, digest, state, write_jsonl

HERE = Path(__file__).resolve().parent


def complete_case(case, cid, family, decisions, catalog):
    if set(decisions) - set(catalog):
        raise ValueError('Unknown control')
    rows = []
    for key, control in catalog.items():
        label = decisions.get(key, 'exclude')
        if (label == 'recommend' and not control['implementation']) or (label == 'handoff' and control['implementation']):
            raise ValueError('Disposition contradicts compiler capability')
        rows.append({'id': cid+':'+key, 'case_id': cid, 'family_id': family,
                     'task': 'guardrail_candidate', 'state': state(case, key, control),
                     'labels': {'q': label}, 'rationale': 'Explicit request/evidence counterfactual; all ten candidates assessed. No upstream incident label is inferred.',
                     'tags': ['complete_case_counterfactual'], 'split': 'train',
                     'label_status': 'programmatic_counterfactual_pending_review',
                     'independent_expert_label': False})
    return rows


def build(frozen, out):
    frozen, out = Path(frozen), Path(out)
    if out.exists():
        raise ValueError('Preserve prior datasets')
    parent = json.loads((frozen/'MANIFEST.json').read_text())
    for name, meta in parent['files'].items():
        if digest(frozen/name) != meta['sha256']:
            raise ValueError('Changed frozen input: '+name)
    catalog = json.loads((ROOT/'controls/catalog.json').read_text())['controls']
    profiles = json.loads((HERE/'source_profiles.json').read_text())
    original = [json.loads(l) for l in (frozen/'train.jsonl').read_text().splitlines()]
    rows = list(original)
    # One copy per operative request/evidence state. Publisher excerpts and aliases
    # supplied no response supervision and must not inflate effective sample size.
    for key, p in profiles.items():
        for i, request in enumerate(p['requests']):
            modes = ('recommend', 'review') if catalog[key]['implementation'] else ('handoff',)
            for label in modes:
                evidence = p['missing' if label == 'review' else 'present']
                case = {'intent': request, 'evidence': evidence[i % len(evidence)],
                        'constraints': p['constraints']+' Assess only the explicitly requested capability; background references are not additional requests.'}
                cid = f'repaired:{key}:{i}:{label}'
                rows += complete_case(case, cid, 'repaired:'+key, {key: label}, catalog)
        # Paired negation: same evidence/candidate vocabulary, no requested change.
        case = {'intent': 'Explain the existing configuration. Do not propose the following change: '+p['requests'][0],
                'evidence': p['present'][0], 'constraints': 'Keep the current settings. The quoted change is explicitly out of scope.'}
        rows += complete_case(case, 'repaired:'+key+':negated', 'repaired:'+key, {}, catalog)
    # Compound cases teach that matching one requirement never activates all controls.
    keys = list(profiles)
    for i, key in enumerate(keys):
        other = keys[(i+3) % len(keys)]
        a, b = profiles[key], profiles[other]
        for conflict in (False, True):
            labels = {}
            for k in (key, other):
                labels[k] = ('review' if conflict and k == key else 'recommend') if catalog[k]['implementation'] else 'handoff'
            ea = a['missing' if labels[key] == 'review' else 'present'][0]
            case = {'intent': a['requests'][1]+' Separately, '+b['requests'][2],
                    'evidence': ea+' '+b['present'][0], 'constraints': a['constraints']+' '+b['constraints']}
            # A non-rendered first candidate cannot acquire a rendered review label;
            # in that case the conflict flag creates no new evidence, so skip alias.
            if conflict and not catalog[key]['implementation']:
                continue
            cid = f'repaired:compound:{key}:{other}:{int(conflict)}'
            rows += complete_case(case, cid, 'repaired:compound:'+key, labels, catalog)
    states = [r['state'] for r in rows]
    if len(states) != len(set(states)):
        raise ValueError('Duplicate operative input')
    for split in ('dev', 'cal', 'test_authored'):
        heldout = {json.loads(l)['state'] for l in (frozen/(split+'.jsonl')).read_text().splitlines()}
        if heldout & set(states):
            raise ValueError('Held-out collision')
    by_case = defaultdict(list)
    for r in rows:
        by_case[r['case_id']].append(r)
    if any(len(rs) != len(catalog) for rs in by_case.values()):
        raise ValueError('Partial candidate set')
    out.mkdir(parents=True)
    for p in frozen.iterdir():
        if p.is_file() and p.name != 'MANIFEST.json' and not p.name.startswith('train.') and p.name != 'source-alignments.jsonl':
            shutil.copyfile(p, out/p.name)
    write_jsonl(out/'train.jsonl', rows)
    write_jsonl(out/'train.inputs.jsonl', [{k:r[k] for k in ('id','case_id','family_id','task','state')} for r in rows])
    write_jsonl(out/'train.targets.jsonl', [{k:v for k,v in r.items() if k not in ('state','case_id','family_id','task')} for r in rows])
    counts = dict(Counter(r['labels']['q'] for r in rows))
    manifest = {**parent, 'version': 'complete-case-repair-v1.1', 'parent_manifest_sha256': digest(frozen/'MANIFEST.json'),
                'builder_sha256': digest(__file__), 'profile_sha256': digest(HERE/'source_profiles.json'),
                'original_training_assessments_retained': len(original), 'training_assessments': len(rows),
                'label_counts': counts, 'reference_excerpts': 0, 'independent_reviewed_cases': 0,
                'upstream_description_alignments': 0,
                'parent_upstream_description_alignments': parent.get('upstream_description_alignments',0),
                'qualification': 'Authored development counterfactuals; no external incident decision labels',
                'splits': {**parent['splits'], 'train': {'decisions': len(rows), 'cases': len(by_case),
                    'families': len({r['family_id'] for r in rows}), 'labels': counts}},
                'files': {p.name: {'sha256': digest(p), 'bytes': p.stat().st_size} for p in sorted(out.iterdir())}}
    manifest.update(cases=sum(s['cases'] for s in manifest['splits'].values()),
                    scenario_families=sum(s['families'] for s in manifest['splits'].values()),
                    candidate_decisions=sum(s['decisions'] for s in manifest['splits'].values()))
    (out/'MANIFEST.json').write_text(json.dumps(manifest, indent=2)+'\n')
    return manifest


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--frozen', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    print(json.dumps(build(a.frozen, a.out)['splits']['train'], indent=2))
