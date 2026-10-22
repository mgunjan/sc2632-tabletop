#!/usr/bin/env python3
"""Reproduce distribution/coverage audit and a calibration-only prior diagnostic."""
import argparse
from collections import Counter, defaultdict
import json
import math
import hashlib
from pathlib import Path

from benchmark import DISPOSITIONS, load, normalized, quantify
from build import digest


def inspect(data):
    rows = load(data, 'train')
    cases=defaultdict(list); operative=defaultdict(set); contracts=[]; by_key=defaultdict(Counter)
    for r in rows:
        s=json.loads(r['state']); label=r['labels']['q']; key=s['candidate']['key']
        cases[r['case_id']].append(r)
        s['available_evidence']=s['available_evidence'].split('\nStatic reference context, not runtime evidence or authorization: ',1)[0]
        operative[json.dumps(s,sort_keys=True)].add(label)
        if (label=='recommend' and not s['candidate']['implementation']) or (label=='handoff' and s['candidate']['implementation']):
            contracts.append(r['id'])
        by_key[key][label]+=1
    counts=Counter(r['labels']['q'] for r in rows)
    return {'manifest_sha256':digest(data/'MANIFEST.json'),'assessments':len(rows),
        'cases':len(cases), 'candidate_rows_per_case':dict(Counter(len(v) for v in cases.values())),
        'complete_ten_candidate_cases':sum(len(v)==10 for v in cases.values()),
        'labels':dict(counts),'exclude_fraction':counts['exclude']/len(rows),
        'majority_training_accuracy':max(counts.values())/len(rows),
        'label_frequency_only_training_cross_entropy':-sum((n/len(rows))*math.log(n/len(rows)) for n in counts.values()),
        'distinct_operative_model_inputs_after_removing_reference':len(operative),
        'exact_operative_label_conflicts':sum(len(v)>1 for v in operative.values()),
        'capability_label_contract_violations':contracts,
        'independently_reviewed_assessments':sum(r.get('independent_expert_label',False) for r in rows),
        'per_candidate_labels':dict(by_key)}


def audit(original, failed, repaired, evaluation):
    original,failed,repaired,evaluation=map(Path,(original,failed,repaired,evaluation))
    rows=load(original,'train'); required={r['id']:r for r in rows}; old={r['id']:r for r in load(failed,'train')}
    fixed={r['id']:r for r in load(repaired,'train')}
    unchanged={n:digest(original/n)==digest(repaired/n) for n in ('dev.jsonl','cal.jsonl','test_authored.jsonl','questions.json')}
    if not all(unchanged.values()) or any(fixed.get(k)!=v for k,v in required.items()):
        raise ValueError('Repair changed original data or held-out inputs')
    # No test data is read for this diagnostic. This is not a proposed calibrated
    # decision model: label-shift assumptions are unverified and a prior cannot
    # replace learned intent/candidate matching.
    priors=Counter(r['labels']['q'] for r in rows)
    raw=[json.loads(l) for l in (evaluation/'cal-raw.jsonl').read_text().splitlines()]
    frozen_cal=load(original,'cal')
    if len(raw) != len(frozen_cal):
        raise ValueError('Incomplete calibration responses')
    for a,b in zip(raw,frozen_cal):
        if a['id']!=b['id'] or a['expected']!=b['labels']['q'] or a['state_sha256']!=hashlib.sha256(b['state'].encode()).hexdigest():
            raise ValueError('Calibration mismatch')
    adjusted=[]
    for r in raw:
        p=normalized({k:r['probabilities'][k]*(priors[k]/len(rows))/.25 for k in DISPOSITIONS})
        adjusted.append({**r,'prediction':max(p,key=p.get),'probabilities':p,'confidence':max(p.values())})
    return {'auditor_sha256':digest(__file__),'original':inspect(original),'failed_balanced':inspect(failed),'repaired':inspect(repaired),
        'original_rows_removed_in_failed_set':dict(Counter(r['labels']['q'] for k,r in required.items() if k not in old)),
        'all_original_rows_preserved_in_repair':True,'heldout_bytes_unchanged':unchanged,
        'prior_only_calibration_diagnostic':{'scope':'Original calibration only; no test tuning; training-frequency correction, not a fitted classifier',
            'before':quantify(raw),'after':quantify(adjusted),
            'prediction_counts_after':dict(Counter(r['prediction'] for r in adjusted))},
        'semantic_label_status':'No exact conflicting operative labels or capability contract violation is not proof of semantic correctness. All response labels await independent review.',
        'known_ontology_ambiguity':'Generic not_implementable overlaps identity/process ownership; replica scope acknowledgement versus completed scope approval is underspecified. Frozen labels are preserved, not silently adjudicated.'}


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    for k in ('original','failed','repaired','evaluation','out'):ap.add_argument('--'+k,type=Path,required=True)
    a=ap.parse_args();result=audit(a.original,a.failed,a.repaired,a.evaluation)
    a.out.write_text(json.dumps(result,indent=2)+'\n')
