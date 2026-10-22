#!/usr/bin/env python3
"""Rescore frozen predictions against agreed independent labels; never change predictions."""
import argparse
import json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE))
from benchmark import load,quantify,bootstrap
from build import digest


def score(data,review,run,out):
    data=Path(data);review=Path(review);run=Path(run);out=Path(out)
    agreement=json.loads((review/'SUMMARY.json').read_text())
    frozen=json.loads((run/'summary.json').read_text())
    data_sha=digest(data/'MANIFEST.json')
    if agreement['status']!='AGREED_REVIEW_LABELS_AVAILABLE':raise ValueError('Resolve independent reviewer disagreement first')
    if agreement['data_manifest_sha256']!=data_sha or frozen['data_manifest_sha256']!=data_sha:
        raise ValueError('Review and prediction data identities differ')
    if len(set(agreement['reviewers']))!=2:raise ValueError('Two independent reviewers are required')
    test=load(data,'test_authored');original={r['id']:r for r in test}
    labels={}
    for line in (review/'agreements.jsonl').read_text().splitlines():
        r=json.loads(line);rid=r['case_id']+':'+r['control']
        if rid in labels or r['reviewer_a']!=r['reviewer_b']:raise ValueError('Invalid agreement record')
        labels[rid]=r['reviewer_a']
    if set(labels)!=set(original):raise ValueError('Independent labels do not cover the exact frozen test')
    responses=[json.loads(l) for l in (run/'test-responses.jsonl').read_text().splitlines()]
    if len(responses)!=len(original) or {r['id'] for r in responses}!=set(original):raise ValueError('Incomplete or duplicated predictions')
    import hashlib
    scored=[]
    for r in responses:
        expected_hash=hashlib.sha256(original[r['id']]['state'].encode()).hexdigest()
        if r['state_sha256']!=expected_hash:raise ValueError('Prediction input differs from reviewed input')
        scored.append({**r,'expected':labels[r['id']]})
    threshold=frozen['metrics']['routing']['threshold']
    result={'candidate':frozen['candidate'],'data_manifest_sha256':data_sha,
            'prediction_file_sha256':digest(run/'test-responses.jsonl'),
            'review_summary_sha256':digest(review/'SUMMARY.json'),
            'review_agreements_sha256':digest(review/'agreements.jsonl'),
            'reviewers':agreement['reviewers'],'metrics':quantify(scored,threshold),'family_bootstrap_95':bootstrap(scored),
            'threshold_source':'Previously frozen calibration selection; not refitted to independent test labels',
            'status':'INDEPENDENT_REVIEW_LABELS_SCORED',
            'limitations':['Reviewed assistant-authored inputs; independent input authorship is not established',
                           'No automatic production or industry-leadership qualification']}
    out.parent.mkdir(parents=True,exist_ok=True)
    if out.exists():raise ValueError('Preserve the prior reviewed score')
    out.write_text(json.dumps(result,indent=2)+'\n');return result


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    for name in ('data','review','run','out'):ap.add_argument('--'+name,type=Path,required=True)
    a=ap.parse_args();print(json.dumps(score(a.data,a.review,a.run,a.out),indent=2))
