#!/usr/bin/env python3
"""Replay the retained four-pass sampler without loading a model or test input."""
import argparse
from collections import Counter
import json
from pathlib import Path
import random
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / 'laya_variant'))
import train
from build import DISPOSITIONS, digest


def replay(data, receipt, out):
    source = json.loads(receipt.read_text())
    if source['balanced_labels'] or source['total_completed_steps'] != 1312:
        raise ValueError('This replay is for the retained four-pass natural sampler')
    if source['training_manifest_sha256'] != digest(data / 'MANIFEST.json'):
        raise ValueError('Frozen training manifest changed')
    rows = [json.loads(l) for l in (data / 'train.jsonl').read_text().splitlines()]
    groups = [[{'label': DISPOSITIONS.index(r['labels']['q'])}] for r in rows]
    rng = random.Random(19); histogram = Counter(); draws = Counter(); updates = Counter()
    for _ in range(4):
        for batch in train.batches(groups, 4, rng, balanced=False):
            labels = [DISPOSITIONS[g[0]['label']] for g in batch]
            histogram[sum(k != 'exclude' for k in labels)] += 1
            draws.update(labels); updates.update(set(labels))
    if {str(DISPOSITIONS.index(k)): v for k, v in draws.items()} != source['label_draw_counts']:
        raise ValueError('The replay does not reproduce actual draw receipts')
    result = {'scope': 'Exact seeded replay of the previous four-epoch sampler, not a new model run',
              'optimizer_updates': sum(histogram.values()),
              'updates_by_required_examples_in_batch': dict(histogram),
              'exclude_only_update_fraction': histogram[0] / sum(histogram.values()),
              'updates_with_each_disposition': dict(updates),
              'training_rows_by_disposition': dict(Counter(r['labels']['q'] for r in rows)),
              'previous_total_draws': dict(draws), 'seed': 19, 'batch_size': 4,
              'executed_sampler_sha256': digest(Path(train.__file__)),
              'replay_script_sha256': digest(__file__), 'prior_receipt_sha256': digest(receipt),
              'qualification': 'Sampler replay and fitting diagnostics motivate a repair bundle; this does not isolate a single causal hyperparameter.'}
    out.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('data', 'receipt', 'out'):
        parser.add_argument('--' + name, type=Path, required=True)
    replay(**vars(parser.parse_args()))
