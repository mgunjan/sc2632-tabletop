#!/usr/bin/env python3
"""Rescore the first control recording after a parser fix, without any inference."""
import argparse
import hashlib
import json
from pathlib import Path
import statistics

import baselines
import evaluate


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--recording', type=Path, required=True)
    ap.add_argument('--data', type=Path, required=True); ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    if a.out.exists() and any(a.out.iterdir()): raise ValueError('Preserve previous scores')
    original = json.loads((a.recording.parent/'summary.json').read_text())
    for name, digest in original['data_sha256'].items():
        if hashlib.sha256((a.data/name).read_bytes()).hexdigest() != digest: raise ValueError('Data differs from recorded evaluation')
    qd = json.loads((a.data/'questions.json').read_text())['policy_control']['q']
    test = [json.loads(l) for l in (a.data/'test_ood.jsonl').read_text().splitlines()]
    pilot = json.loads((Path(__file__).resolve().parents[1]/'submission/2026-10-12/benchmark/cases.json').read_text())
    expected = {'synthetic_test_ood': {r['id']: (r['state'], [r['labels']['q']]) for r in test},
                'frozen_control_pilot': {r['id']: (r['state'], r['expected']) for r in pilot if r['expected'] is not None and r['question'] == qd}}
    rows = [json.loads(l) for l in a.recording.read_text().splitlines()]
    results = {}; seen = set()
    for r in rows:
        key = (r['candidate'], r['split'], r['id'])
        if key in seen: raise ValueError('Duplicate recorded decision')
        seen.add(key)
        state, labels = expected[r['split']][r['id']]
        if hashlib.sha256(state.encode()).hexdigest() != r['state_sha256'] or r['expected'] != labels:
            raise ValueError('State or labels differ from the first evaluation')
    for candidate, source in original['candidates'].items():
        split_results = {}
        for split, cases in expected.items():
            rr = [r for r in rows if r['candidate'] == candidate and r['split'] == split]
            if {r['id'] for r in rr} != set(cases): raise ValueError('Incomplete recording')
            pairs = []; selected = []; correct = []
            for r in rr:
                pr = r['response'].get('prediction') if candidate == 'tfidf-lr' else baselines._decider_answer(qd, r['response'].get('answers', {}).get('q'))
                pr = pr or baselines.failed_answer(qd)
                pk = pr.get('decision'); ok = pr.get('valid', True) and pk in r['expected']
                gold = pk if ok else r['expected'][0]
                if len(r['expected']) > 1: pr = {**pr, 'distribution_valid': False}
                pairs.append((pr, gold)); correct.append(int(ok))
                if pr.get('valid', True) and pr['conf'] >= .6: selected.append(int(ok))
            m, _ = evaluate.metrics(pairs)
            m.update(correct=sum(correct), of=len(rr), median_ms=round(statistics.median(r['ms'] for r in rr),3),
                routing_at_0_6={'selected':len(selected),'correct':sum(selected),'wrong':len(selected)-sum(selected)})
            split_results[split] = m
        results[candidate] = {**source, 'splits': split_results}
    report = {**original, 'candidates': results, 'rescored_without_inference': True,
              'reason': 'Laya serializes probabilities to four decimals; validate the maximum rounding drift instead of rejecting legitimate distributions.',
              'recording_sha256': hashlib.sha256(a.recording.read_bytes()).hexdigest(),
              'scoring_source_sha256': {n: hashlib.sha256(Path(__file__).with_name(n).read_bytes()).hexdigest() for n in ['baselines.py','evaluate.py','rescore_control.py']}}
    a.out.mkdir(parents=True, exist_ok=True); (a.out/'summary.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__ == '__main__': main()
