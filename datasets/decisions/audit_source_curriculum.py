#!/usr/bin/env python3
"""Check exact curation reproducibility, upstream bytes and unchanged held-out data."""
import argparse
from collections import Counter,defaultdict
import json
from pathlib import Path
import sys
import tempfile

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from build import DISPOSITIONS,digest
import source_curriculum as c


def audit(data,masked,corpus,frozen,out):
    data,masked,corpus,frozen,out=map(Path,(data,masked,corpus,frozen,out))
    if out.exists():raise ValueError('Preserve the earlier audit')
    manifest=json.loads((data/'MANIFEST.json').read_text())
    cm=json.loads((corpus/'MANIFEST.json').read_text())
    for meta in cm['files']:
        if digest(corpus/meta['path'])!=meta['sha256']:raise ValueError('Upstream normalized corpus bytes changed')
    for folder in (data,masked):
        m=json.loads((folder/'MANIFEST.json').read_text())
        for name,meta in m['files'].items():
            if digest(folder/name)!=meta['sha256']:raise ValueError('Curated data bytes changed: '+name)
        for name in ('dev.jsonl','cal.jsonl','test_authored.jsonl','questions.json'):
            if (folder/name).read_bytes()!=(frozen/name).read_bytes():raise ValueError('Held-out data or question changed')
    with tempfile.TemporaryDirectory() as tmp:
        rebuilt=Path(tmp)/'source';again=Path(tmp)/'masked'
        c.build(corpus,frozen,rebuilt,per_class=manifest['label_counts']['recommend'],seed=manifest['seed'])
        c.mask_reference(rebuilt,again)
        if (rebuilt/'MANIFEST.json').read_bytes()!=(data/'MANIFEST.json').read_bytes():raise ValueError('Source recipe does not reproduce the frozen manifest')
        if (again/'MANIFEST.json').read_bytes()!=(masked/'MANIFEST.json').read_bytes():raise ValueError('Reference ablation is not reproducible')
    rows=[json.loads(l) for l in (data/'train.jsonl').read_text().splitlines()]
    by_control=defaultdict(Counter)
    for r in rows:
        by_control[json.loads(r['state'])['candidate']['key']][r['labels']['q']]+=1
    old=[json.loads(l) for l in (frozen/'train.jsonl').read_text().splitlines()]
    old_required={r['id'] for r in old if r['labels']['q']!='exclude'}
    if not old_required<={r['id'] for r in rows}:raise ValueError('Original required-control examples were lost')
    actual=Counter(r['labels']['q'] for r in rows)
    if set(actual)!=set(DISPOSITIONS) or len(set(actual.values()))!=1:raise ValueError('Training labels are not balanced')
    used=[json.loads(l) for l in (data/'SOURCE-USE.jsonl').read_text().splitlines()]
    result={'status':'PASSED_SOURCE_CURRICULUM_AUDIT','source_data_manifest_sha256':digest(data/'MANIFEST.json'),
            'masked_data_manifest_sha256':digest(masked/'MANIFEST.json'),'corpus_manifest_sha256':digest(corpus/'MANIFEST.json'),
            'original_data_manifest_sha256':digest(frozen/'MANIFEST.json'),
            'label_counts':dict(actual),'source_context_rows':len(used),'source_records':len({r['source_record_id'] for r in used}),
            'source_families':len({r['source_family'] for r in used}),
            'source_publishers':sorted({r['source']['name'] for r in used}),
            'original_nonexclude_assessments_preserved':len(old_required),
            'per_control_labels':{k:dict(v) for k,v in by_control.items()},
            'heldout_hashes':{n:digest(data/n) for n in ('dev.jsonl','cal.jsonl','test_authored.jsonl','questions.json')},
            'reference_text_role':'Static domain context; the counterfactual request and evidence determine the generated label',
            'independent_response_labels':0,'counterfactual_request_wordings':manifest['unique_profile_request_wordings'],
            'qualification':'Programmatic training labels pending review; this audit proves construction/provenance, not incident-response truth',
            'auditor_sha256':digest(Path(__file__))}
    out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(result,indent=2)+'\n')
    return result


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    for key in ('data','masked','corpus','frozen','out'):ap.add_argument('--'+key,type=Path,required=True)
    a=ap.parse_args();print(json.dumps(audit(a.data,a.masked,a.corpus,a.frozen,a.out),indent=2))
