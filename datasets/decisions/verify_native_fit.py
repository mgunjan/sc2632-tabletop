#!/usr/bin/env python3
"""Require saved cached-head fitting to reproduce through the ordinary Laya API.

Training/development only. Does not open calibration or test inputs.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import time

from build import DISPOSITIONS, QUESTION, digest, write_jsonl
from compare_hosted import read_rows
from train_cached_laya import fit_gate


def weight_identity(base, weights):
    from safetensors import safe_open
    import torch
    before = hashlib.sha256()
    after = hashlib.sha256()
    changed = []
    counts = Counter()
    with safe_open(str(base / 'model.safetensors'), framework='pt', device='cpu') as a, \
         safe_open(str(weights / 'model.safetensors'), framework='pt', device='cpu') as b:
        if set(a.keys()) != set(b.keys()):
            raise ValueError('Native parameter names changed')
        for key in sorted(a.keys()):
            x, y = a.get_tensor(key), b.get_tensor(key)
            if x.shape != y.shape or x.dtype != y.dtype:
                raise ValueError('Native parameter shape/dtype changed: ' + key)
            if key.startswith('encoder.'):
                if not torch.equal(x, y):
                    raise ValueError('Frozen encoder changed: ' + key)
                before.update(key.encode()); before.update(x.numpy().tobytes())
                after.update(key.encode()); after.update(y.numpy().tobytes())
                counts['encoder_parameters'] += x.numel()
            elif not torch.equal(x, y):
                changed.append(key)
                counts['changed_head_parameters'] += x.numel()
    if not changed:
        raise ValueError('Head weights did not change')
    return {'encoder_before_sha256': before.hexdigest(), 'encoder_after_sha256': after.hexdigest(),
            'changed_head_tensors': changed, **counts}


def verify(base, weights, data, training, out):
    import laya
    from train import plan_selection
    receipt = json.loads((training / 'TRAINING-RUN.json').read_text())
    if receipt['state'] != 'FIT_GATE_PASSED' or receipt['data_manifest_sha256'] != digest(data / 'MANIFEST.json'):
        raise ValueError('Training fit gate or frozen-data identity failed')
    if receipt['source_checkpoint_sha256'] != digest(base / 'model.safetensors'):
        raise ValueError('Changed source weights')
    manifest = json.loads((data / 'MANIFEST.json').read_text())
    identity = weight_identity(base, weights)
    agent = laya.load(str(weights), device='mps')
    batch_size = 4
    if agent._amp_enabled_for(batch_size):
        raise ValueError('Native verification requires float32, matching the training cache')
    start = time.perf_counter()
    results = {}
    out.mkdir(parents=True, exist_ok=False)
    (out / 'VERIFIER.py.txt').write_bytes(Path(__file__).read_bytes())
    for split in ('train', 'dev'):
        if digest(data / (split + '.jsonl')) != manifest['files'][split + '.jsonl']['sha256']:
            raise ValueError('Changed frozen ' + split)
        rows = read_rows(data / (split + '.jsonl'))
        expected = read_rows(training / ('selected-' + split + '.jsonl'))
        if [r['id'] for r in rows] != [r['id'] for r in expected]:
            raise ValueError('Cached prediction identities changed')
        records = []
        max_difference = 0.
        single_checks = []
        class_checks = Counter()
        for i in range(0, len(rows), batch_size):
            part = rows[i:i + batch_size]
            answers = agent.predict_batch([r['state'] for r in part], QUESTION, batch_size=batch_size)
            if len(answers) != len(part):
                raise ValueError('Native API returned incomplete batch')
            for row, cached, response in zip(part, expected[i:i + batch_size], answers):
                if cached['state_sha256'] != hashlib.sha256(row['state'].encode()).hexdigest() or cached['expected'] != row['labels']['q']:
                    raise ValueError('Cached row identity/label mismatch')
                answer = response['answers']['q']
                difference = max(abs(answer['probabilities'][k] - cached['probabilities'][k]) for k in DISPOSITIONS)
                max_difference = max(max_difference, difference)
                if answer['choice'] != cached['prediction'] or difference > .0002:
                    raise ValueError('Runtime/cache disagreement: ' + row['id'])
                records.append({**cached, 'prediction': answer['choice'], 'probabilities': answer['probabilities'],
                                'cached_probability_max_difference': difference})
                # Also exercise the exact single-row API used by the benchmark,
                # covering each answer without opening calibration/test inputs.
                label = row['labels']['q']
                if class_checks[label] < 4:
                    single = agent.predict(row['state'], QUESTION)['answers']['q']
                    delta = max(abs(single['probabilities'][k] - cached['probabilities'][k]) for k in DISPOSITIONS)
                    if single['choice'] != cached['prediction'] or delta > .0002:
                        raise ValueError('Single-row runtime/cache disagreement: ' + row['id'])
                    single_checks.append({'id': row['id'], 'expected': label, 'prediction': single['choice'],
                                          'max_probability_difference': delta})
                    class_checks[label] += 1
            if i % 160 == 0:
                print('native runtime verified', split, i, '/', len(rows), flush=True)
        recalls = {k: sum(r['prediction'] == k for r in records if r['expected'] == k) /
                      sum(r['expected'] == k for r in records) for k in DISPOSITIONS}
        accuracy = sum(r['prediction'] == r['expected'] for r in records) / len(records)
        _, plans = plan_selection(rows, [DISPOSITIONS.index(r['prediction']) for r in records], 0.)
        metrics = {'rows': len(rows), 'accuracy': accuracy, 'recall_by_disposition': recalls,
                   'runtime_cache_argmax_disagreements': 0, 'max_probability_difference': max_difference,
                   'single_row_checks': single_checks, **plans}
        if split == 'train' and not fit_gate(metrics):
            raise ValueError('Actual native-runtime training fit failed')
        write_jsonl(out / (split + '-responses.jsonl'), records)
        results[split] = metrics
    report = {'state': 'PASSED_NATIVE_TRAINING_FIT_AND_PARITY', 'device': str(agent.device),
              'checkpoint_sha256': digest(weights / 'model.safetensors'),
              'config_sha256': digest(weights / 'rl_agent_config.json'),
              'data_manifest_sha256': digest(data / 'MANIFEST.json'),
              'full_fit_runtime_api': 'predict_batch', 'runtime_batch_size': batch_size,
              'amp_enabled_for_verification_batch': False,
              'single_row_probe_policy': 'First four inputs per expected disposition in each split; all frozen test rows later use single-row benchmark API',
              'verifier_sha256': digest(__file__), 'weights': identity, 'splits': results,
              'elapsed_runtime_seconds': time.perf_counter() - start,
              'calibration_or_test_opened': False, 'new_hosted_calls': 0}
    (out / 'VERIFICATION.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('base', 'weights', 'data', 'training', 'out'):
        parser.add_argument('--' + name, type=Path, required=True)
    verify(**vars(parser.parse_args()))
