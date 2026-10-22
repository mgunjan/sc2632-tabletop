#!/usr/bin/env python3
"""Build balanced, provenance-linked counterfactual training; preserve all held-out bytes."""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import random
import re
import shutil
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from build import DISPOSITIONS, ROOT, digest, state, write_jsonl


def stable(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def select_sources(corpus, profiles, cap=24):
    pairs = [json.loads(l) for l in (corpus/'intent-pairs.jsonl').read_text().splitlines()]
    by_id = {}
    wanted = {p['target']['candidate_record_id'] for p in pairs}
    for line in (corpus/'records.jsonl').open():
        r = json.loads(line)
        if r['id'] in wanted:
            by_id[r['id']] = r
    eligible, exclusions = [], Counter()
    seen = set()
    for p in sorted(pairs, key=lambda x: x['id']):
        record = by_id.get(p['target']['candidate_record_id'])
        text = ' '.join(p['inputs']['intent_text'].split())
        if record is None:
            exclusions['missing_target'] += 1; continue
        if p['source']['license'] not in ('Apache-2.0', 'MIT'):
            exclusions['license_not_in_this_recipe'] += 1; continue
        if record['role'] != 'reference':
            exclusions['non_reference_role'] += 1; continue
        # Metadata-only posture summaries cannot supply an implementation-backed context.
        if record['record_type'] == 'posture_control':
            exclusions['metadata_only_posture_control'] += 1; continue
        if len(text) < 30:
            exclusions['short_description'] += 1; continue
        if len(text) > 1400:
            exclusions['description_too_long'] += 1; continue
        normalized = re.sub(r'\W+', ' ', text.lower()).strip()
        if normalized in seen:
            exclusions['duplicate_description'] += 1; continue
        seen.add(normalized)
        eligible.append({'record_id': record['id'], 'source_family': record['family_id'],
                         'description': text, 'record_type': record['record_type'],
                         'source': record['source'], 'content_sha256': record['content_sha256']})
    selected = {}
    for key, profile in profiles.items():
        candidates = [r for r in eligible if re.search(profile['topic'], r['description'], re.I)]
        # Round-robin across publishers, one context per upstream family per topic.
        groups = defaultdict(list)
        for r in sorted(candidates, key=lambda r: stable([key, r['record_id']])):
            groups[r['source']['name']].append(r)
        selected[key] = []; families = set()
        while any(groups.values()) and len(selected[key]) < cap:
            for name in sorted(groups):
                while groups[name]:
                    r = groups[name].pop(0)
                    if r['source_family'] not in families:
                        families.add(r['source_family']); selected[key].append(r); break
                if len(selected[key]) >= cap: break
        if not selected[key]:
            raise ValueError('No implementation-backed source context for '+key)
    return selected, {'input_alignments': len(pairs), 'eligible_unique_descriptions': len(eligible),
                      'excluded': dict(exclusions)}


def source_rows(selected, profiles, catalog):
    rows, provenance, cases = [], [], set()
    for key in sorted(selected):
        profile = profiles[key]
        for ref in selected[key]:
            # This is a static reference excerpt, not invented live telemetry.
            excerpt = ('\nStatic reference context, not runtime evidence or authorization: '
                       +ref['description'])
            for wording, request in enumerate(profile['requests']):
                dispositions = ('recommend', 'review') if catalog[key]['implementation'] else ('handoff',)
                for disposition in dispositions:
                    evidence_key = 'missing' if disposition == 'review' else 'present'
                    evidence = profile[evidence_key][wording % len(profile[evidence_key])]
                    case = {'intent': request, 'evidence': evidence+excerpt, 'constraints': profile['constraints']}
                    cid = 'source:'+stable([key, ref['record_id'], wording, disposition])[:20]
                    cases.add(cid)
                    candidates = [(key, disposition)]
                    # Related coverage and unrelated controls both need explicit exclusion examples.
                    others = sorted(k for k in catalog if k != key)
                    offset = int(stable([ref['record_id'], wording, disposition])[:8], 16) % len(others)
                    candidates += [(others[offset], 'exclude'), (others[(offset+4) % len(others)], 'exclude')]
                    for candidate, label in candidates:
                        rid = cid+':'+candidate
                        row = {'id': rid, 'case_id': cid, 'family_id': 'source:'+ref['source_family'],
                               'task': 'guardrail_candidate', 'state': state(case, candidate, catalog[candidate]),
                               'labels': {'q': label}, 'rationale': 'Programmatic bounded request and evidence counterfactual; upstream reference is context, not an incident-response label.',
                               'tags': ['source_context', 'generated_counterfactual', disposition],
                               'label_status': 'programmatic_counterfactual_pending_review', 'independent_expert_label': False,
                               'split': 'train', 'source_refs': [ref['source']],
                               'source_record_id': ref['record_id'], 'generation_profile': key,
                               'generation_wording': wording, 'source_description_sha256': stable(ref['description'])}
                        rows.append(row)
                        provenance.append({'assessment_id': rid, 'source_record_id': ref['record_id'],
                                           'source_family': ref['source_family'], 'source': ref['source'],
                                           'source_content_sha256': ref['content_sha256'],
                                           'source_description_sha256': stable(ref['description']),
                                           'profile': key, 'wording': wording, 'disposition_counterfactual': disposition})
    return rows, provenance, len(cases)


def balanced_selection(original, generated, per_class, seed):
    rng = random.Random(seed); result = []; counts = Counter()
    # Retain every original positive/review/handoff; cap easy original exclusions.
    old = defaultdict(list); new = defaultdict(list)
    for r in original: old[r['labels']['q']].append(r)
    for r in generated: new[r['labels']['q']].append(r)
    for label in DISPOSITIONS:
        rng.shuffle(old[label]); rng.shuffle(new[label])
        keep_old = old[label][:min(len(old[label]), per_class//2)]
        need = per_class-len(keep_old)
        if len(new[label]) < need:
            raise ValueError(f'Insufficient unique generated {label} rows: {len(new[label])} < {need}')
        result += keep_old+new[label][:need]
        counts[label] = len(keep_old)+need
    rng.shuffle(result)
    if len({r['id'] for r in result}) != len(result) or len({r['state'] for r in result}) != len(result):
        raise ValueError('Duplicate training assessment or model-visible state')
    return result, dict(counts)


def build(corpus, frozen, out, per_class=256, seed=19, cap=24):
    corpus, frozen, out = map(Path, (corpus, frozen, out))
    if out.exists(): raise ValueError('Preserve earlier data; choose a new directory')
    source_manifest = json.loads((frozen/'MANIFEST.json').read_text())
    for name, meta in source_manifest['files'].items():
        if digest(frozen/name) != meta['sha256']: raise ValueError('Changed frozen dataset input: '+name)
    profiles = json.loads((HERE/'source_profiles.json').read_text())
    catalog = json.loads((ROOT/'controls/catalog.json').read_text())['controls']
    selected, selection = select_sources(corpus, profiles, cap)
    generated, provenance, generated_cases = source_rows(selected, profiles, catalog)
    original = [json.loads(l) for l in (frozen/'train.jsonl').read_text().splitlines()]
    rows, counts = balanced_selection(original, generated, per_class, seed)
    heldout_states = set()
    for split in ('dev', 'cal', 'test_authored'):
        heldout_states |= {json.loads(l)['state'] for l in (frozen/(split+'.jsonl')).read_text().splitlines()}
    if heldout_states & {r['state'] for r in rows}: raise ValueError('Exact held-out state leakage')
    out.mkdir(parents=True)
    # Copy all nontraining task files byte-for-byte, including question and blind-review inputs.
    for p in frozen.iterdir():
        if p.is_file() and p.name != 'MANIFEST.json' and not p.name.startswith('train.') and p.name != 'source-alignments.jsonl':
            shutil.copyfile(p, out/p.name)
    write_jsonl(out/'train.jsonl', rows)
    public = [{k:r[k] for k in ('id','case_id','family_id','task','state')} for r in rows]
    private = [{'id':r['id'], **{k:v for k,v in r.items() if k not in public[i]}} for i,r in enumerate(rows)]
    write_jsonl(out/'train.inputs.jsonl', public); write_jsonl(out/'train.targets.jsonl', private)
    used_ids = {r['id'] for r in rows}
    used = [p for p in provenance if p['assessment_id'] in used_ids]
    write_jsonl(out/'SOURCE-USE.jsonl', used)
    manifest = {**source_manifest, 'version':'source-balanced-v1', 'parent_manifest_sha256':digest(frozen/'MANIFEST.json'),
                'builder_sha256':digest(Path(__file__)), 'profile_sha256':digest(HERE/'source_profiles.json'),
                'seed':seed, 'label_counts':counts, 'training_assessments':len(rows),
                'original_training_assessments_retained':sum(r['id'] in {a['id'] for a in original} for r in rows),
                'source_context_assessments':len(used), 'source_records_used':len({p['source_record_id'] for p in used}),
                'source_families_used':len({p['source_family'] for p in used}),
                'source_counts':dict(Counter(p['source']['name'] for p in used)),
                'source_selection':selection, 'generated_pool_assessments':len(generated),
                'generated_pool_cases':generated_cases, 'unique_profile_request_wordings':sum(len(p['requests']) for p in profiles.values()),
                'source_corpus_manifest_sha256':digest(corpus/'MANIFEST.json'),
                'reference_text_present_in_training':True,
                'training_case_coverage':'Selected candidate assessments; only the held-out evaluation requires all ten candidates per case',
                'qualification':'Programmatic source-context counterfactual training; no independently verified response labels',
                'source_execution_status':'Upstream descriptions supply reference context, not engine or live-containment proof',
                'frozen_heldout':{n:digest(frozen/n) for n in ('dev.jsonl','cal.jsonl','test_authored.jsonl','questions.json')},
                'files':{p.name:{'sha256':digest(p),'bytes':p.stat().st_size} for p in sorted(out.iterdir()) if p.is_file()}}
    manifest['cases'] = len({r['case_id'] for r in rows})+sum(source_manifest['splits'][s]['cases'] for s in ('dev','cal','test_authored'))
    manifest['scenario_families'] = len({r['family_id'] for r in rows})+sum(source_manifest['splits'][s]['families'] for s in ('dev','cal','test_authored'))
    manifest['candidate_decisions'] = len(rows)+sum(source_manifest['splits'][s]['decisions'] for s in ('dev','cal','test_authored'))
    manifest['upstream_description_alignments'] = 0
    manifest['upstream_alignments_considered_for_source_selection'] = selection['input_alignments']
    manifest['splits'] = {**source_manifest['splits'], 'train':{'decisions':len(rows),'cases':len({r['case_id'] for r in rows}),
                                                           'families':len({r['family_id'] for r in rows}),'labels':counts}}
    (out/'MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return manifest


def mask_reference(source, out):
    """Matched template-only ablation; aliases remain so draw budgets stay identical."""
    source, out = Path(source), Path(out)
    if out.exists(): raise ValueError('Preserve earlier data')
    manifest = json.loads((source/'MANIFEST.json').read_text())
    out.mkdir(parents=True)
    for p in source.iterdir():
        if p.is_file() and p.name != 'MANIFEST.json': shutil.copyfile(p,out/p.name)
    rows = [json.loads(l) for l in (source/'train.jsonl').read_text().splitlines()]
    states = {}
    for r in rows:
        if r.get('source_record_id'):
            visible = json.loads(r['state'])
            visible['available_evidence'] = visible['available_evidence'].split('\nStatic reference context, not runtime evidence or authorization: ',1)[0]
            r['state'] = json.dumps(visible,ensure_ascii=False,sort_keys=True)
        key = r['state']
        if key in states and states[key] != r['labels']: raise ValueError('Conflicting labels after masking')
        states[key] = r['labels']
    write_jsonl(out/'train.jsonl',rows)
    write_jsonl(out/'train.inputs.jsonl',[{k:r[k] for k in ('id','case_id','family_id','task','state')} for r in rows])
    manifest.update(version='source-masked-ablation-v1', parent_source_manifest_sha256=digest(source/'MANIFEST.json'),
                    reference_text_present_in_training=False, unique_model_visible_training_states=len(states),
                    model_visible_source_records=0,
                    ablation_note='Same rows, labels and draws; static reference excerpts removed. Repeated template aliases do not count as independent examples.')
    manifest['files']={p.name:{'sha256':digest(p),'bytes':p.stat().st_size} for p in sorted(out.iterdir()) if p.is_file()}
    (out/'MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return manifest


if __name__ == '__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    for key in ('corpus','frozen','out'): ap.add_argument('--'+key,type=Path,required=True)
    ap.add_argument('--per-class',type=int,default=256);ap.add_argument('--seed',type=int,default=19)
    a=ap.parse_args()
    result=build(a.corpus,a.frozen,a.out,a.per_class,a.seed)
    print(json.dumps({k:v for k,v in result.items() if k not in ('files','splits')},indent=2))
