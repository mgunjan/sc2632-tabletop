#!/usr/bin/env python3
"""Audit native optimization and compare frozen predictions with saved Claude.

Offline only. Report values come from retained observations, including failures.
"""
import argparse
import json
import os
from pathlib import Path

import benchmark
from build import DISPOSITIONS, digest
from compare_hosted import identities, load_run, read_rows
from train_cached_laya import fit_gate


def render(run, training, weights, data, old, repair, claude):
    receipt = json.loads((training / 'TRAINING-RUN.json').read_text())
    history = json.loads((training / 'HISTORY.json').read_text())
    verification = json.loads((run / 'runtime-verification/VERIFICATION.json').read_text())
    if receipt['state'] != 'FIT_GATE_PASSED' or verification['state'] != 'PASSED_NATIVE_TRAINING_FIT_AND_PARITY':
        raise ValueError('Actual native model has not demonstrated training fit')
    if receipt['trainer_sha256'] != digest(training / 'TRAINER.py.txt'):
        raise ValueError('Executed trainer identity changed')
    if verification['verifier_sha256'] != digest(run / 'runtime-verification/VERIFIER.py.txt'):
        raise ValueError('Executed runtime verifier identity changed')
    if receipt['data_manifest_sha256'] != digest(data / 'MANIFEST.json'):
        raise ValueError('Changed training freeze')
    if receipt.get('sampling', '').startswith('Each shuffled epoch'):
        if receipt.get('unique_training_rows_seen') != 1310:
            raise ValueError('Not every original training row was retained and visited')
        if receipt.get('presentations_per_row') != {str(receipt['epochs']): 1310}:
            raise ValueError('Coverage sampler did not present every row once per epoch')
        if receipt.get('total_row_presentations') != 1310 * receipt['epochs']:
            raise ValueError('Coverage sampler presentation accounting failed')
    else:
        if receipt['label_draw_counts'] != {str(k): receipt['optimizer_updates'] * receipt['effective_batch_size'] // 4 for k in range(4)}:
            raise ValueError('Class-balanced draw accounting failed')
        if receipt['unique_rows_seen'] != 1310:
            raise ValueError('Not every original training row was retained and visited')
    eligible = [h for h in history if fit_gate(h['train'])]
    chosen = min(eligible, key=lambda h: (-h['dev']['exact_plans'], h['dev']['development_error_cost'], h['dev']['loss']))
    if chosen['update'] != receipt['selected_update']:
        raise ValueError('Development-only selection mismatch')
    for split in ('train', 'dev'):
        runtime = verification['splits'][split]
        if runtime['accuracy'] != chosen[split]['accuracy'] or runtime['recall_by_disposition'] != chosen[split]['recall_by_disposition']:
            raise ValueError('Native runtime does not reproduce selected ' + split + ' fit')
        cached = read_rows(training / ('selected-' + split + '.jsonl'))
        actual = read_rows(run / 'runtime-verification' / (split + '-responses.jsonl'))
        if identities(cached) != identities(actual) or any(a['prediction'] != b['prediction'] for a, b in zip(cached, actual)):
            raise ValueError('Runtime fitting predictions changed')
    results = []
    cal_id = test_id = source = None
    folders = [('previous-adapted', old / 'adapted'), ('prior-data-repair-Laya', repair / 'evaluation'),
               ('native-optimization-Laya', run / 'evaluation'), ('saved-Claude', claude)]
    for name, folder in folders:
        summary, cal, test = load_run(folder)
        if source is None:
            cal_id, test_id, source = identities(cal), identities(test), summary['benchmark_sha256']
        if (identities(cal), identities(test), summary['benchmark_sha256']) != (cal_id, test_id, source):
            raise ValueError('The comparison is not exactly paired: ' + name)
        results.append((name, summary, folder))
    if source != digest(Path(benchmark.__file__)):
        raise ValueError('Benchmark source changed')
    current = next(s for n, s, _ in results if n == 'native-optimization-Laya')
    model_hash = digest(weights / 'model.safetensors')
    if current['candidate']['model_sha256'] != model_hash or verification['checkpoint_sha256'] != model_hash:
        raise ValueError('Evaluated weights changed')
    if current['candidate']['config_sha256'] != verification['config_sha256'] or verification['config_sha256'] != digest(weights / 'rl_agent_config.json'):
        raise ValueError('Native configuration changed')
    if current['data_manifest_sha256'] != receipt['data_manifest_sha256']:
        raise ValueError('Benchmark training manifest differs')
    if verification['weights']['encoder_before_sha256'] != verification['weights']['encoder_after_sha256']:
        raise ValueError('Frozen encoder changed')
    audit = {'state': 'PASSED_NATIVE_OPTIMIZATION_AND_PAIRED_COMPARISON', 'checkpoint_sha256': model_hash,
             'trainer_sha256': receipt['trainer_sha256'], 'reporter_sha256': digest(__file__),
             'head_forward_source_sha256': digest(training / 'HEAD-FORWARD.py.txt'),
             'protocol_sha256': digest(run / 'PROTOCOL.md'), 'benchmark_sha256': source,
             'data_manifest_sha256': receipt['data_manifest_sha256'],
             'selected_update': receipt['selected_update'], 'training_fit': verification['splits']['train'],
             'calibration_rows_paired': len(cal_id), 'test_rows_paired': len(test_id),
             'new_hosted_calls': 0, 'new_api_usd': 0,
             'qualification': 'EXAMINED_AUTHORED_REGRESSION_PENDING_INDEPENDENT_REVIEW'}
    (run / 'AUDIT.json').write_text(json.dumps(audit, indent=2) + '\n')
    (run / 'REPORTER.py.txt').write_bytes(Path(__file__).read_bytes())
    def link(path):
        return Path(os.path.relpath(path.resolve(), run.resolve())).as_posix()
    fitted = verification['splits']['train']
    text = ['# Native Laya optimization repair and saved Claude comparison', '',
            '**The native Laya training-underfit failure is repaired in this measured configuration. '
            'Generalization is scored separately below. No labels, architecture, options, test inputs or scoring code were changed. No new hosted calls were made.**', '',
            f"The selected update is {receipt['selected_update']} of {receipt['optimizer_updates']}. "
            f"The ordinary native prediction API reproduces {fitted['accuracy']:.2%} accuracy on all {fitted['rows']:,} training assessments, "
            f"with minimum class recall {min(fitted['recall_by_disposition'].values()):.2%}. "
            f"It matches the cached-head choices on every training and development input. "
            'All original encoder tensors are byte-identical; native head weights changed.', '',
            '| Candidate | Exact plans | Required omitted | Wrong recommendations | Reviews | Handoffs | Accepted / wrong | Case p50 seconds |',
            '|---|---:|---:|---:|---:|---:|---:|---:|']
    for name, s, folder in results:
        m = s['metrics']; r = m['routing']
        text.append(f"| [{name}]({link(folder / 'summary.json')}) | {m['exact_plan_cases']}/{m['cases']} | {m['missed_required_controls']}/{m['required_controls']} | {m['wrong_recommendations']} | {m['correct_reviews']}/{m['expected_reviews']} | {m['correct_handoffs']}/{m['expected_handoffs']} | {r['accepted_cases']} / {r['wrong_accepted_cases']} | {s['timing']['full_case_p50_ms']/1000:.3f} |")
    text += ['', '## Model and optimization findings', '',
             'The previous selected model excluded 1,309 of 1,310 training candidates and recognized none of the 147 required candidates. '
             'Layer-level gradient checks found live gradients in both selected encoder blocks and in the native decision head. '
             'The unused action-routing head has no gradient under supervised answer loss, as expected. '
             'Training/inference attention fast paths agreed within 4.8e-7 with no choice flips on eight diagnostic inputs. '
             'These measurements rule out a disconnected head or a fast-path choice mismatch in the tested examples.', '',
            'Eight deliberately contrasting training inputs, including the same control with different dispositions, reached 100% fit at the original head LR of 1e-4. '
            'The head therefore has capacity on that tiny subset. Replaying the old natural sampler showed 819/1,312 updates (62.4%) contained exclusions only. '
            'The first balanced retry accumulated four microbatches per update, so at update 500 it had made 2,000 draws per class: all 1,163 exclusions appeared at least once, averaging 1.72 presentations each, while minority examples cycled roughly 33–49 times. '
            'The retained checkpoint reached only 91.7% training accuracy. A subsequent full-row-coverage run with inverse-square-root weights still predicted only exclude after two epochs. These runs show that a larger dataset and superficial class balancing were not enough.', '',
            'The repair freezes the same encoder and caches its full float32 token sequences, with a native-forward parity gate. '
            'It optimizes the unchanged native attention head, type embedding and answer scorer. '
            'Each shuffled epoch partitions all 1,310 rows into batches of 16 (the final partial batch is retained), so every authored assessment is presented exactly once per epoch. '
            'The final run uses inverse-frequency class weights normalized so each disposition contributes equal total training loss; no row is dropped or replaced. '
            'Dropout is disabled, AdamW LR stays at 1e-4, and checkpoints must pass a whole-training-set fitting gate before development selection. '
            'There is no pooling, alternate classifier, candidate masking or custom prediction adapter.', '',
            'The measured causes were majority-only updates in the natural batch-four run, strong per-row exposure skew in the balanced retry, and insufficient class weighting in the first full-coverage attempt. '
            'The final configuration combines full-row coverage with equal total loss contribution for each disposition. It also freezes the encoder and disables dropout, so the bundle does not isolate one causal hyperparameter. '
             'The prior dataset defects and failed experiments remain preserved in the [earlier report](../repair-v1/COMPARISON.md).', '',
            '| Epoch / update | Train accuracy | Lowest class recall | Dev exact plans | Dev error cost | Fit gate |',
            '|---:|---:|---:|---:|---:|---|']
    for h in history:
        text.append(f"| {h.get('epoch', 0)} / {h['update']} | {h['train']['accuracy']:.4f} | {min(h['train']['recall_by_disposition'].values()):.4f} | {h['dev']['exact_plans']}/18 | {h['dev']['development_error_cost']} | {h['fit_gate']} |")
    text += ['', '## Cost, timing and interpretation', '',
             f"Actual device: {receipt['actual_device']}. Frozen-encoder caching plus optimization took {receipt['elapsed_seconds']/60:.2f} minutes, excluding final checkpoint materialization and runtime verification. "
             f"The run presented {receipt.get('total_row_presentations', sum(receipt.get('label_draw_counts', {}).values())):,} training rows across {receipt['optimizer_updates']:,} optimizer updates and visited all {receipt.get('unique_training_rows_seen', receipt.get('unique_rows_seen')):,} unique rows. "
             'The separate frozen-feature cache was built from the original encoder and checked against native logits before optimization.', '',
             'New API spend is $0. Claude is the saved approved October 18 run: 301 historical requests, $1.964736 estimated total, about $0.06495 per attempted ten-candidate test plan. '
             'Local API spend is zero, while hardware, energy, setup and human review are unpriced. Case timing covers ten sequential candidate assessments, not deployment or containment.', '',
             'Successful training fit demonstrates repaired underfitting, not enterprise generalization. '
             'The 15 authored test cases in five families have already been examined. Their unchanged labels still lack independent review. '
             'This is a regression comparison, not a fresh blind trial or a production safety guarantee. '
             'Do not promote a model solely because its training accuracy is high or its API cost is zero.', '',
             '[Native runtime verification](runtime-verification/VERIFICATION.json), [paired audit](AUDIT.json), [protocol](PROTOCOL.md).']
    (run / 'COMPARISON.md').write_text('\n'.join(text) + '\n')
    return audit


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('run', 'training', 'weights', 'data', 'old', 'repair', 'claude'):
        parser.add_argument('--' + name, type=Path, required=True)
    print(json.dumps(render(**vars(parser.parse_args())), indent=2))
