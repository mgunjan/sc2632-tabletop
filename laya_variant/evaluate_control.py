#!/usr/bin/env python3
"""One-time held-out control-selection evaluation; never tunes on these labels."""
import argparse
import hashlib
import json
from pathlib import Path
import statistics
import sys
import time

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent/'generator'))
import evaluate
import baselines


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', type=Path, required=True)
    ap.add_argument('--model', action='append', required=True, help='name=local checkpoint')
    ap.add_argument('--device', default='mps')
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    if a.out.exists() and any(a.out.iterdir()): sys.exit('Output exists; preserve the first evaluation')
    a.out.mkdir(parents=True, exist_ok=True)
    qs = json.loads((a.data/'questions.json').read_text())['policy_control']
    train = [json.loads(l) for l in (a.data/'train.jsonl').read_text().splitlines()]
    test = [json.loads(l) for l in (a.data/'test_ood.jsonl').read_text().splitlines()]
    pilot = json.loads((HERE.parent/'submission/2026-10-12/benchmark/cases.json').read_text())
    scored = [r for r in pilot if r['expected'] is not None and r['question'] == qs['q']]
    # Training is multiclass for one frozen question; other workflow questions are not silently pooled.
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    t0 = time.perf_counter()
    clf = make_pipeline(baselines._features(), LogisticRegression(max_iter=2000, C=4, class_weight='balanced'))
    clf.fit([r['state'] for r in train], [r['labels']['q'] for r in train])
    fit_seconds = time.perf_counter()-t0
    results = {}; recording = []
    sources = {'synthetic_test_ood': test, 'frozen_control_pilot': scored}
    for label, model in [('tfidf-lr', None)] + [s.split('=', 1) for s in a.model]:
        setup = time.perf_counter()
        if model:
            import laya
            agent = laya.load(model, device=a.device)
            agent.predict('clause: Require an approved registry.\nintent: Require an approved registry.', qs)
        setup_seconds = time.perf_counter()-setup
        split_results = {}
        for split, rows in sources.items():
            pairs = []; latencies = []; selected = []; choices = []
            for row in rows:
                start = time.perf_counter()
                if model:
                    response = agent.predict(row['state'], qs)
                    pr = baselines._decider_answer(qs['q'], response['answers'].get('q'))
                else:
                    p = clf.predict_proba([row['state']])[0]
                    pr = baselines._p_row(qs['q'], dict(zip(clf.classes_, p))); response = {'prediction': pr}
                ms = (time.perf_counter()-start)*1000
                pr = pr or baselines.failed_answer(qs['q'])
                expected = row.get('expected', [row.get('labels', {}).get('q')])
                choice = pr.get('decision'); correct = pr.get('valid', True) and choice in expected
                gold = choice if correct else expected[0]
                if len(expected) > 1: pr = {**pr, 'distribution_valid': False}
                pairs.append((pr, gold)); latencies.append(ms); choices.append(int(correct))
                if pr.get('valid', True) and pr['conf'] >= .6: selected.append(int(correct))
                recording.append({'candidate': label, 'split': split, 'id': row['id'],
                    'state_sha256': hashlib.sha256(row['state'].encode()).hexdigest(),
                    'choice': choice, 'expected': expected, 'correct': correct, 'ms': round(ms,3), 'response': response})
            m, _ = evaluate.metrics(pairs)
            m.update(correct=sum(choices), of=len(rows), median_ms=round(statistics.median(latencies),3),
                     routing_at_0_6={'selected': len(selected), 'correct': sum(selected), 'wrong': len(selected)-sum(selected)})
            split_results[split] = m
        results[label] = {'model': model, 'device': a.device if model else 'CPU',
                          'setup_and_warmup_seconds': round(setup_seconds,3),
                          'fit_seconds': round(fit_seconds,3) if not model else None, 'splits': split_results}
        if model: del agent
    (a.out/'responses.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in recording))
    report = {'candidates': results, 'limitations': 'Synthetic templates and author-labelled pilot; no independent enterprise labels. Control pilot is a subset of the 33-decision workflow benchmark. No production qualification.',
              'data_sha256': {n: hashlib.sha256((a.data/n).read_bytes()).hexdigest() for n in ['train.jsonl','test_ood.jsonl','questions.json','MANIFEST.json']}}
    (a.out/'summary.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__': main()
