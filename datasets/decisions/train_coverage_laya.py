#!/usr/bin/env python3
"""Train Laya's unchanged native head with full row coverage each epoch.

The earlier class-cycling sampler oversampled minority rows tens of times while
each exclusion was presented only once or twice. This trainer shuffles all rows
into ordinary batches each epoch and uses inverse-frequency class weighting, so
every row is covered and each disposition has equal total loss contribution.

Only train/dev inputs are read. Frozen encoder features are cached float32 values;
the resulting checkpoint is materialized in the ordinary Laya format.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import random
import sys
import time

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / 'laya_variant'))
import lv
from build import DISPOSITIONS, digest
from diagnose_optimization import head_forward
from train_cached_laya import cached_batch, evaluate, fit_gate, materialize


def coverage_batches(n_rows, batch_size, rng):
    """Yield a shuffled partition: every row exactly once, including the tail."""
    if n_rows < 1 or batch_size < 1:
        raise ValueError('Rows and batch size must be positive')
    order = list(range(n_rows))
    rng.shuffle(order)
    return [order[i:i + batch_size] for i in range(0, n_rows, batch_size)]


def frequency_class_weights(labels, power=1.0, n_classes=4):
    """Inverse-frequency weights (power=1), normalized to unit mean over train rows."""
    import torch
    if not 0.0 < power <= 1.0:
        raise ValueError('Class weight power must be in (0, 1]')
    counts = torch.bincount(labels, minlength=n_classes).float()
    if torch.any(counts == 0):
        raise ValueError('Every disposition must occur in training data')
    weights = (len(labels) / (n_classes * counts)).pow(power)
    weights /= (weights[labels].mean())
    return weights


def validate_cache(data, rows, index, base, agent):
    import numpy as np
    import torch
    from laya.common import collate_items
    manifest = json.loads((data / 'MANIFEST.json').read_text())
    for name in ('train.jsonl', 'dev.jsonl', 'questions.json'):
        if digest(data / name) != manifest['files'][name]['sha256']:
            raise ValueError('Frozen input hash mismatch: ' + name)
    if index['ids'] != [r['id'] for r in rows]:
        raise ValueError('Feature cache row order does not match frozen data')
    state_hashes = [hashlib.sha256(r['state'].encode()).hexdigest() for r in rows]
    labels = [DISPOSITIONS.index(r['labels']['q']) for r in rows]
    if index['state_sha256'] != state_hashes or index['labels'] != labels:
        raise ValueError('Feature cache states or labels do not match frozen data')
    # Recompute one cached row through the unmodified full Laya forward. This
    # binds feature cache/source checkpoint identity and exercises train/runtime parity.
    groups = lv.encode_rows(agent, rows[:1], 'labels_ab',
                            question_sets=json.loads((data / 'questions.json').read_text()))
    batch = collate_items(groups, agent.tok.pad_token_id)
    bank = np.load(base / 'train' / 'hidden.npy', mmap_mode='r')
    with torch.no_grad():
        full, _ = agent.model(
            batch['input_ids'].to(agent.device), batch['attention_mask'].to(agent.device),
            batch['marker_pos'].to(agent.device), batch['marker_mask'].to(agent.device),
            batch['qtype'].to(agent.device))
        hidden, attention, markers, mask, qtype, _ = cached_batch(
            bank, index, [0], agent.device)
        cached = head_forward(agent.model, hidden, attention, markers, mask, qtype)
    difference = float((full - cached).abs().max().cpu())
    if difference > 1e-4:
        raise ValueError(f'Frozen feature cache does not reproduce Laya logits: {difference}')
    return difference


def main(a):
    import numpy as np
    import torch
    from safetensors.torch import save_file

    a.out.mkdir(parents=True, exist_ok=False)
    if a.weights.exists():
        raise ValueError('Preserve earlier checkpoints; choose a fresh weights path')
    trainer_source = Path(__file__).read_bytes()
    forward_source = (HERE / 'diagnose_optimization.py').read_bytes()
    helper_source = (HERE / 'train_cached_laya.py').read_bytes()
    (a.out / 'TRAINER.py.txt').write_bytes(trainer_source)
    (a.out / 'HEAD-FORWARD.py.txt').write_bytes(forward_source)
    (a.out / 'CACHE-HELPERS.py.txt').write_bytes(helper_source)

    torch.manual_seed(a.seed)
    rng = random.Random(a.seed)
    start = time.perf_counter()
    print(f'loading source Laya checkpoint on {a.device}', flush=True)
    agent = lv.load_agent(str(a.base), device=a.device)
    model = agent.model
    print(f'loaded source Laya checkpoint on {agent.device}', flush=True)
    data_manifest = json.loads((a.data / 'MANIFEST.json').read_text())
    questions = json.loads((a.data / 'questions.json').read_text())
    if tuple(questions['guardrail_candidate']['q']['criteria']) != DISPOSITIONS:
        raise ValueError('Frozen disposition order changed')
    rows = {split: lv.load_rows(a.data / f'{split}.jsonl', ['guardrail_candidate'])
            for split in ('train', 'dev')}
    cache = {}
    for split in ('train', 'dev'):
        cache[split] = json.loads((a.cache / split / 'INDEX.json').read_text())
        if len(cache[split]['ids']) != len(rows[split]):
            raise ValueError('Cache row count mismatch for ' + split)
        if cache[split]['ids'] != [r['id'] for r in rows[split]]:
            raise ValueError('Cache identities mismatch for ' + split)
        if cache[split]['labels'] != [DISPOSITIONS.index(r['labels']['q']) for r in rows[split]]:
            raise ValueError('Cache labels mismatch for ' + split)
    cache_parity = validate_cache(a.data, rows['train'], cache['train'], a.cache, agent)

    banks = {split: np.load(a.cache / split / 'hidden.npy', mmap_mode='r')
             for split in ('train', 'dev')}
    train_labels = torch.tensor(cache['train']['labels'], dtype=torch.long)
    weights_cpu = frequency_class_weights(train_labels, power=a.class_weight_power)
    class_weights = weights_cpu.to(agent.device)

    # The encoder stays frozen. Optimizing its native head over cached native features
    # avoids repeatedly running the 400M-parameter encoder and preserves exact logits.
    model.encoder = None
    if torch.backends.mps.is_available():
        torch.mps.empty_cache()
    for parameter in model.parameters():
        parameter.requires_grad_(True)
    params = [p for name, p in model.named_parameters() if not name.startswith('act_head.')]
    optimizer = torch.optim.AdamW(params, lr=a.lr, weight_decay=0.01)
    total_rows = len(rows['train'])
    batches_per_epoch = (total_rows + a.batch_size - 1) // a.batch_size
    history, seen, class_seen, best = [], Counter(), Counter(), None

    def evaluate_split(split):
        return evaluate(model, banks[split], cache[split], rows[split], agent.device, bs=a.eval_batch_size)

    def record(epoch, update):
        nonlocal best
        train_metrics, train_records = evaluate_split('train')
        dev_metrics, dev_records = evaluate_split('dev')
        passed = fit_gate(train_metrics)
        entry = {'epoch': epoch, 'update': update, 'train': train_metrics,
                 'dev': dev_metrics, 'fit_gate': passed,
                 'elapsed_seconds': time.perf_counter() - start}
        history.append(entry)
        (a.out / 'HISTORY.json').write_text(json.dumps(history, indent=2) + '\n')
        print(json.dumps(entry), flush=True)
        if passed:
            # Retain only checkpoints that prove near-perfect train fit. Dev is used
            # solely to select among checkpoints that have already passed this gate.
            checkpoint = a.weights.parent / (a.weights.name + f'-epoch-{epoch:02d}.safetensors')
            save_file({k: v.detach().cpu().contiguous() for k, v in model.state_dict().items()
                       if not k.startswith('act_head.')}, str(checkpoint))
            key = (-dev_metrics['exact_plans'], dev_metrics['development_error_cost'], dev_metrics['loss'])
            if best is None or key < best[0]:
                best = (key, epoch, update, checkpoint, train_metrics, dev_metrics)
                from build import write_jsonl
                write_jsonl(a.out / 'selected-train.jsonl', train_records)
                write_jsonl(a.out / 'selected-dev.jsonl', dev_records)
        return entry

    # Capture the untouched source checkpoint baseline before the first update.
    record(0, 0)
    update = 0
    for epoch in range(1, a.epochs + 1):
        model.eval()  # Keep dropout off while retaining gradients for optimization.
        order = coverage_batches(total_rows, a.batch_size, rng)
        epoch_ids = []
        for batch_ids in order:
            h, attention, markers, mask, qtype, labels = cached_batch(
                banks['train'], cache['train'], batch_ids, agent.device)
            logits = head_forward(model, h, attention, markers, mask, qtype)
            row_weights = class_weights[labels]
            per_row = torch.nn.functional.cross_entropy(logits, labels, reduction='none')
            loss = (per_row * row_weights).mean()
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(params, 1.0)
            optimizer.step()
            update += 1
            epoch_ids.extend(batch_ids)
            for idx in batch_ids:
                seen[idx] += 1
                class_seen[str(cache['train']['labels'][idx])] += 1
        if len(epoch_ids) != total_rows or len(set(epoch_ids)) != total_rows:
            raise ValueError('Coverage sampler did not visit each row exactly once')
        record(epoch, update)
        print(f'coverage epoch {epoch}/{a.epochs} updates {update} elapsed '
              f'{time.perf_counter()-start:.1f}s', flush=True)

    source_hash = digest(a.base / 'model.safetensors')
    receipt = {
        'state': 'FIT_GATE_PASSED' if best else 'FIT_GATE_FAILED',
        'native_architecture_unchanged': True,
        'actual_device': str(agent.device),
        'source_checkpoint_sha256': source_hash,
        'data_manifest_sha256': digest(a.data / 'MANIFEST.json'),
        'question_sha256': digest(a.data / 'questions.json'),
        'trainer_sha256': hashlib.sha256(trainer_source).hexdigest(),
        'head_forward_sha256': hashlib.sha256(forward_source).hexdigest(),
        'cache_helpers_sha256': hashlib.sha256(helper_source).hexdigest(),
        'cache_native_max_logit_difference': cache_parity,
        'optimizer': 'AdamW', 'lr': a.lr, 'weight_decay': 0.01,
        'loss': f"per-row cross entropy weighted by inverse class frequency to power {a.class_weight_power}; weights normalized to unit train mean",
        'class_counts': dict(Counter(str(x) for x in cache['train']['labels'])),
        'class_weights': {DISPOSITIONS[i]: float(weights_cpu[i]) for i in range(4)},
        'batch_size': a.batch_size, 'epochs': a.epochs,
        'optimizer_updates': update, 'total_row_presentations': sum(seen.values()),
        'unique_training_rows_seen': len(seen),
        'presentations_per_row': dict(Counter(seen.values())),
        'presentations_by_disposition': {DISPOSITIONS[int(k)]: v for k, v in class_seen.items()},
        'sampling': 'Each shuffled epoch is an exact partition of all frozen training rows; final partial batch retained',
        'dropout': 'disabled with model.eval(); gradients enabled',
        'fit_gate': {'accuracy': 0.995, 'minimum_per_class_recall': 0.98},
        'selected_epoch': best[1] if best else None,
        'selected_update': best[2] if best else None,
        'history': history,
        'elapsed_seconds': time.perf_counter() - start,
        'new_hosted_calls': 0, 'api_usd': 0,
        'selection': 'Among train-fit-gated checkpoints only: dev exact plans, dev error cost, then unweighted dev cross entropy; no cal/test access'
    }
    (a.out / 'TRAINING-RUN.json').write_text(json.dumps(receipt, indent=2) + '\n')
    if best:
        _, epoch, selected_update, checkpoint, train_metrics, dev_metrics = best
        meta = {**receipt, 'freeze_encoder': True, 'base': str(a.base),
                'tasks': ['guardrail_candidate'], 'mode': 'labels_ab',
                'selected_epoch': epoch, 'selected_update': selected_update,
                'selected_train_metrics': train_metrics, 'selected_dev_metrics': dev_metrics}
        materialize(a.base, checkpoint, a.weights, meta)
        (a.out / 'CHECKPOINT-CONFIG.json').write_bytes((a.weights / 'rl_agent_config.json').read_bytes())
        print(json.dumps({'selected_epoch': epoch, 'selected_update': selected_update,
                          'train': train_metrics, 'dev': dev_metrics}), flush=True)
    else:
        print('No checkpoint met the training-fit gate; calibration/test remain unopened.', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('base', 'data', 'cache', 'weights', 'out'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--epochs', type=int, default=20)
    parser.add_argument('--batch-size', type=int, default=16)
    parser.add_argument('--lr', type=float, default=1e-4)
    parser.add_argument('--class-weight-power', type=float, default=1.0,
                        help='1 gives equal total class weight; .5 is inverse-square-root weighting')
    parser.add_argument('--seed', type=int, default=19)
    parser.add_argument('--device', choices=('cpu', 'mps'), default='cpu')
    parser.add_argument('--eval-batch-size', type=int, default=16)
    args = parser.parse_args()
    if args.epochs < 1 or args.batch_size < 1 or args.eval_batch_size < 1 or args.lr <= 0 or not 0 < args.class_weight_power <= 1:
        parser.error('epochs, batch sizes and learning rate must be positive; class weight power must be in (0, 1]')
    main(args)
