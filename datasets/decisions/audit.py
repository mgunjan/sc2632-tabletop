#!/usr/bin/env python3
"""Audit counts, file identity and cross-split text similarity without changing labels."""
import argparse
from collections import Counter,defaultdict
import json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE))
from build import SPLITS,digest


def audit(data,out):
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    data=Path(data);out=Path(out);manifest=json.loads((data/'MANIFEST.json').read_text())
    for name,meta in manifest['files'].items():
        if digest(data/name)!=meta['sha256']:raise ValueError('Frozen file mismatch: '+name)
    cases={};groups=defaultdict(set);labels={};tag_counts={}
    for split in SPLITS:
        rows=[json.loads(l) for l in (data/f'{split}.jsonl').read_text().splitlines()]
        labels[split]=dict(Counter(r['labels']['q'] for r in rows));tags=Counter()
        for r in rows:
            groups[split].add(r['family_id'])
            if r['case_id'] not in cases:
                visible=json.loads(r['state'])
                case={k:visible[k] for k in ('operator_intent','available_evidence','operational_constraints')}
                cases[r['case_id']]={'case_id':r['case_id'],'family_id':r['family_id'],'split':split,
                                     'text':json.dumps(case,sort_keys=True),'tags':r['tags']}
                tags.update(r['tags'])
        tag_counts[split]=dict(tags)
    for s in SPLITS:
        for t in SPLITS:
            if s!=t and groups[s]&groups[t]:raise ValueError('Family leakage')
    ids=sorted(cases);texts=[cases[i]['text'] for i in ids]
    X=TfidfVectorizer(analyzer='char_wb',ngram_range=(3,5)).fit_transform(texts)
    sim=cosine_similarity(X);pairs=[]
    for i,a in enumerate(ids):
        for j in range(i+1,len(ids)):
            b=ids[j]
            if cases[a]['split']!=cases[b]['split']:
                pairs.append({'a':a,'b':b,'a_split':cases[a]['split'],'b_split':cases[b]['split'],
                              'character_tfidf_cosine':float(sim[i,j])})
    pairs.sort(key=lambda r:r['character_tfidf_cosine'],reverse=True)
    report={'data_manifest_sha256':digest(data/'MANIFEST.json'),'auditor_sha256':digest(__file__),
            'cases':len(cases),'families':len({r['family_id'] for r in cases.values()}),
            'candidate_decisions':sum(sum(c.values()) for c in labels.values()),
            'labels_by_split':labels,'case_tags_by_split':tag_counts,'cross_split_family_overlap':0,
            'cross_split_top_similarity_pairs':pairs[:25],
            'cross_split_pairs_at_or_above_0_8':sum(p['character_tfidf_cosine']>=.8 for p in pairs),
            'independently_reviewed_cases':0,
            'current_training_uses_upstream_alignments':False,
            'quality_findings':['All decision labels are assistant-authored and provisional',
                                'Candidate rows from the same case are dependent',
                                'Exclude dominates; pooled accuracy can hide complete failure to find controls',
                                'Text similarity is a screening signal, not proof of semantic independence',
                                'The upstream alignments are retained references, not newly labelled incident decisions'],
            'publication_qualification':'INCOMPLETE'}
    out.parent.mkdir(parents=True,exist_ok=True)
    if out.exists():raise ValueError('Preserve the previous audit')
    out.write_text(json.dumps(report,indent=2)+'\n');return report


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--data',type=Path,required=True);ap.add_argument('--out',type=Path,required=True)
    a=ap.parse_args();r=audit(a.data,a.out);print(json.dumps({k:v for k,v in r.items() if k!='cross_split_top_similarity_pairs'},indent=2))
