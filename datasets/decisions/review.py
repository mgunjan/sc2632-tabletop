#!/usr/bin/env python3
"""Export blind case forms and validate two independent label submissions."""
import argparse
import json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path.insert(0,str(HERE))
from build import DISPOSITIONS,digest,write_jsonl


def export(data,out):
    data=Path(data);out=Path(out);out.mkdir(parents=True,exist_ok=False)
    rows=[json.loads(l) for l in (data/'blind-review.jsonl').read_text().splitlines()]
    catalog=json.loads((ROOT/'controls/catalog.json').read_text())
    (out/'catalog.json').write_text(json.dumps(catalog,indent=2)+'\n')
    write_jsonl(out/'reviewer-a.jsonl',rows);write_jsonl(out/'reviewer-b.jsonl',rows)
    text=['# Blind security decision review','',
          'Two reviewers should work separately, without consulting proposed labels, model outputs or each other.',
          'Use the accompanying catalog.json and the four dispositions below. Reviewers who authored these cases or their generator cannot count as independent.',
          '', '`recommend`: include a matching rendered control in a proposal, retaining its limits.',
          '`review`: a potentially relevant rendered control needs clarification or prerequisite evidence.',
          '`handoff`: a matching non-rendered identity, governance or unsupported requirement needs its owner.',
          '`exclude`: this candidate is not requested or does not implement the requested capability.',
          '', 'No disposition grants permission, deploys a change, approves an exception or proves containment.',
          '', 'Fill your reviewer ID, authored_any_case_or_generator=false, a rationale and all ten catalog keys in decisions for every case in your own JSONL file. Record disagreement or ambiguous wording in the rationale. Do not edit the case input. Leave the other reviewer file to the other person.', '']
    for r in rows:
        text += [f"## {r['case_id']}",'',f"**Intent:** {r['intent']}",'',f"**Available evidence:** {r['evidence']}",'',
                 f"**Constraints:** {r['constraints']}",'','Disposition for each catalog control:','']
        text += [f'- {key}: ______' for key in catalog['controls']]
        text += ['','Rationale / acceptable alternatives / ambiguous facts: ______','']
    (out/'BLIND-REVIEW.md').write_text('\n'.join(text).rstrip()+'\n')
    m={'source_data_manifest_sha256':digest(data/'MANIFEST.json'),'cases':len(rows),
       'catalog_sha256':digest(out/'catalog.json'),'files':{p.name:digest(p) for p in out.iterdir() if p.is_file()},
       'independent_review_completed':False}
    (out/'MANIFEST.json').write_text(json.dumps(m,indent=2)+'\n')
    return m


def validate_submission(path,original):
    rows=[json.loads(l) for l in Path(path).read_text().splitlines()]
    originals={r['case_id']:r for r in original};seen=set();reviewers=set()
    controls=set(json.loads((ROOT/'controls/catalog.json').read_text())['controls'])
    for r in rows:
        cid=r['case_id']
        if cid in seen or cid not in originals:raise ValueError('Duplicate or unknown reviewed case')
        seen.add(cid);o=originals[cid]
        if any(r[k]!=o[k] for k in ('intent','evidence','constraints','catalog_sha256')):
            raise ValueError('Reviewed inputs differ from frozen case')
        if r.get('authored_any_case_or_generator') is not False:
            raise ValueError('Independent non-authorship declaration is required')
        if not r.get('reviewer_id','').strip() or not r.get('rationale','').strip():
            raise ValueError('Reviewer identity and rationale are required')
        reviewers.add(r['reviewer_id'])
        if set(r.get('decisions',{}))!=controls:raise ValueError('Every control needs an explicit disposition')
        if any(d not in DISPOSITIONS for d in r['decisions'].values()):raise ValueError('Invalid reviewed disposition')
    if seen!=set(originals) or len(reviewers)!=1:raise ValueError('One identified reviewer must label every case')
    return rows,next(iter(reviewers))


def compare(data,reviewer_a,reviewer_b,out):
    data=Path(data);out=Path(out)
    original=[json.loads(l) for l in (data/'blind-review.jsonl').read_text().splitlines()]
    a,aid=validate_submission(reviewer_a,original);b,bid=validate_submission(reviewer_b,original)
    if aid==bid:raise ValueError('Two distinct independent reviewers are required')
    b={r['case_id']:r for r in b};agreements=[];disagreements=[]
    for r in a:
        other=b[r['case_id']]
        for key,label in r['decisions'].items():
            target={'case_id':r['case_id'],'control':key,'reviewer_a':label,'reviewer_b':other['decisions'][key]}
            (agreements if label==other['decisions'][key] else disagreements).append(target)
    out.mkdir(parents=True,exist_ok=False)
    write_jsonl(out/'agreements.jsonl',agreements);write_jsonl(out/'disagreements.jsonl',disagreements)
    m={'reviewers':[aid,bid],'review_submission_sha256':[digest(reviewer_a),digest(reviewer_b)],
       'data_manifest_sha256':digest(data/'MANIFEST.json'),'cases':len(a),'agreed_decisions':len(agreements),
       'disagreed_decisions':len(disagreements),'decision_agreement':len(agreements)/(len(agreements)+len(disagreements)),
       'status':'AGREED_REVIEW_LABELS_AVAILABLE' if not disagreements else 'HUMAN_ADJUDICATION_REQUIRED',
       'reviewer_identity_basis':'Reviewer self-declaration retained; professional credentials are not independently verified by this tool'}
    (out/'SUMMARY.json').write_text(json.dumps(m,indent=2)+'\n');return m


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);sub=ap.add_subparsers(dest='command',required=True)
    ex=sub.add_parser('export');ex.add_argument('--data',type=Path,required=True);ex.add_argument('--out',type=Path,required=True)
    co=sub.add_parser('compare');co.add_argument('--data',type=Path,required=True);co.add_argument('--reviewer-a',type=Path,required=True)
    co.add_argument('--reviewer-b',type=Path,required=True);co.add_argument('--out',type=Path,required=True)
    a=ap.parse_args()
    print(json.dumps(export(a.data,a.out) if a.command=='export' else compare(a.data,a.reviewer_a,a.reviewer_b,a.out),indent=2))
