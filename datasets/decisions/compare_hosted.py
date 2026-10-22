#!/usr/bin/env python3
"""Audit the approved hosted run and compare it with frozen local predictions, offline."""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import benchmark as bench
from build import digest
import hosted


def read_rows(path):
    rows = [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]
    if len({r['id'] for r in rows}) != len(rows):
        raise ValueError('Duplicate assessment IDs')
    return rows


def identities(rows):
    return {r['id']: (r['state_sha256'], r['expected'], r['case_id'], r['family_id']) for r in rows}


def require_close(actual, expected, field):
    if not isinstance(actual, (float, int)) or isinstance(actual, bool) or not math.isclose(actual, expected, rel_tol=1e-10, abs_tol=1e-10):
        raise ValueError('Usage or cost mismatch: ' + field)


def verify_preview(preview, approval, records, model):
    """Bind the human approval to the exact outbound bodies and evaluated states."""
    manifest = json.loads((preview / 'MANIFEST.json').read_text())
    preview_hash = digest(preview / 'OUTBOUND-PREVIEW.jsonl')
    if preview_hash != manifest['preview_sha256'] or preview_hash != approval['preview_sha256']:
        raise ValueError('The export preview differs from the approved payload')
    if approval['status'] != 'APPROVED' or approval['model'] != model or approval['api_usage_budget_usd'] != 8:
        raise ValueError('Missing approval for this model and budget')
    entries = [json.loads(line) for line in (preview / 'OUTBOUND-PREVIEW.jsonl').read_text().splitlines()]
    phases = Counter(e['phase'] for e in entries)
    if phases != {'warmup': 1, 'calibration': 150, 'authored_test': 150} or manifest['requests'] != 301:
        raise ValueError('Unexpected approved assessment scope')
    provider = hosted.Claude('', None, model)
    expected = {}
    for e in entries:
        body = e['outbound_body']
        state = json.loads(body['messages'][0]['content'])['state']
        if e['destination'] != manifest['destination'] or body != provider.payload(state):
            raise ValueError('Outbound body differs from the approved adapter configuration')
        visible = json.loads(state)
        if set(visible) != {'operator_intent', 'available_evidence', 'operational_constraints', 'candidate'}:
            raise ValueError('Unexpected exported state field')
        if e['phase'] != 'warmup':
            key = e['assessment_id_for_preview_only']
            if key in expected:
                raise ValueError('Repeated preview assessment')
            expected[key] = hashlib.sha256(state.encode()).hexdigest()
    if {r['id']: r['state_sha256'] for r in records} != expected:
        raise ValueError('Hosted responses do not match the complete approved assessment scope')
    return manifest


def load_run(root):
    summary = json.loads((root / 'summary.json').read_text())
    if digest(root / 'BENCHMARK.py.txt') != summary['benchmark_sha256']:
        raise ValueError('Executed benchmark source snapshot is missing or changed')
    cal, test = read_rows(root / 'cal-raw.jsonl'), read_rows(root / 'test-responses.jsonl')
    if not cal or not test or set(r['id'] for r in cal) & set(r['id'] for r in test):
        raise ValueError('Missing or overlapping evaluation phases')
    computed = bench.quantify(test, summary['metrics']['routing']['threshold'])
    if computed != summary['metrics']:
        raise ValueError('Reported metrics differ from retained predictions')
    pairs = [(r['probabilities'], r['expected']) for r in cal if r['probabilities'] is not None]
    temperature, calibration = bench.fit_temperature(pairs) if len(pairs) == len(cal) else (1, {'status': 'UNAVAILABLE', 'reason': 'Missing probability distributions'})
    calibrated = []
    for r in cal:
        p = bench.tempered(r['probabilities'], temperature) if r['probabilities'] else None
        calibrated.append({**r, 'probabilities': p, 'prediction': max(p, key=p.get) if p else r['prediction'],
                           'confidence': max(p.values()) if p else None})
    threshold, curve = bench.route_threshold(calibrated)
    if calibration != summary['calibration'] or threshold != summary['metrics']['routing']['threshold'] or curve != summary['routing_selection']['curve']:
        raise ValueError('Calibration or routing differs from retained calibration responses')
    return summary, cal, test


def render(local, hosted_root, preview, approval_path, out):
    local, hosted_root, preview, out = map(Path, (local, hosted_root, preview, out))
    status = json.loads((local / 'RUN-STATUS.json').read_text())
    run = json.loads((hosted_root / 'HOSTED-RUN.json').read_text())
    approval = json.loads(Path(approval_path).read_text())
    if status['state'] != 'RUNS_FINISHED' or run['state'] != 'RUNS_FINISHED':
        raise ValueError('Both comparisons must finish before publication')
    model = run['model']
    hs, hc, ht = load_run(hosted_root)
    if hs['benchmark_sha256'] != hashlib.sha256(bench.BENCHMARK_SOURCE).hexdigest():
        raise ValueError('The offline scoring code differs from the executed benchmark')
    if digest(hosted_root / 'HOSTED.py.txt') != run['adapter_sha256'] or run['adapter_sha256'] != hashlib.sha256(hosted.SOURCE).hexdigest():
        raise ValueError('The hosted adapter differs from its executed snapshot')
    manifest = verify_preview(preview, approval, hc + ht, model)
    if hs['data_manifest_sha256'] != manifest['data_manifest_sha256']:
        raise ValueError('The dataset manifest differs from the approved freeze')
    if hs['candidate']['model'] != model or hs['candidate']['adapter_sha256'] != run['adapter_sha256']:
        raise ValueError('The summary identifies a different hosted model or adapter')
    if run['cost'] != hs['cost'] or run['usage'] != hs['candidate']['usage']:
        raise ValueError('The final summary and hosted receipt disagree')
    usage = run['usage']
    if usage['calls'] != 301 or usage['unknown_cost_attempts'] or usage['budget_exhausted']:
        raise ValueError('This report requires all approved requests and complete usage accounting')
    if run['cost']['spending_limit_usd'] != approval['api_usage_budget_usd'] or usage['conservative_upper_api_usd'] > approval['api_usage_budget_usd']:
        raise ValueError('The run did not retain the approved spending limit')
    phase_costs, phase_tokens = [], []
    for rows, temperature in ((hc, 1), (ht, hs['calibration']['temperature'])):
        cost, tokens = 0., Counter()
        for r in rows:
            raw = r['provider_response']
            if raw['model'] != model or raw['stop_reason'] != 'end_turn':
                raise ValueError('Unexpected model identity or incomplete response')
            recalculated = hosted.usage_cost(raw['usage'], model)
            if recalculated != raw['cost'] or recalculated['estimated_usd'] is None:
                raise ValueError('Missing or inconsistent per-request usage receipt')
            answer = json.loads(''.join(p['text'] for p in raw['content']))
            probabilities = bench.tempered(bench.normalized(answer['probabilities']), temperature)
            if r['probabilities'] != probabilities or r['prediction'] != max(probabilities, key=probabilities.get):
                raise ValueError('Stored prediction differs from the retained provider response')
            cost += recalculated['estimated_usd']
            tokens.update(recalculated['tokens'])
        phase_costs.append(cost)
        phase_tokens.append(tokens)
    for phase, cost in zip(('calibration', 'test'), phase_costs):
        require_close(hs['cost']['estimated_' + phase + '_api_usd'], cost, phase)
    warmup_tokens = {k: usage[k] - sum(t[k] for t in phase_tokens) for k in ('input_tokens', 'output_tokens')}
    if any(v < 0 for v in warmup_tokens.values()):
        raise ValueError('Aggregate usage is smaller than retained assessment usage')
    warmup_estimate = hosted.usage_cost(warmup_tokens, model)['estimated_usd']
    require_close(usage['known_estimated_api_usd'], sum(phase_costs) + warmup_estimate, 'all requests')
    require_close(hs['cost']['estimated_api_usd_all_calls'], usage['known_estimated_api_usd'], 'summary total')
    require_close(hs['cost']['estimated_api_usd_per_attempted_test_case'], phase_costs[1] / hs['metrics']['cases'], 'per case')
    correct_accepted = hs['metrics']['routing']['correctly_accepted_cases']
    correct_cost = hs['cost']['estimated_api_usd_per_correctly_accepted_test_case']
    if correct_accepted:
        require_close(correct_cost, phase_costs[1] / correct_accepted, 'per correct accepted plan')
    elif correct_cost is not None:
        raise ValueError('Cost per correct accepted plan must be undefined when none qualify')
    results = []
    for item in status['runs']:
        if item['returncode'] != 0:
            raise ValueError('A local candidate failed')
        root = local / item['name']
        s, cal, test = load_run(root)
        if (s['data_manifest_sha256'], s['benchmark_sha256']) != (hs['data_manifest_sha256'], hs['benchmark_sha256']):
            raise ValueError('Local and hosted runs use different frozen data or scoring code')
        if identities(cal) != identities(hc) or identities(test) != identities(ht):
            raise ValueError('Local and hosted runs are not exactly paired')
        results.append((item['name'], s, root))
    results.append((model, hs, hosted_root))
    out.mkdir(parents=True, exist_ok=False)
    def link(path):
        import os
        return Path(os.path.relpath(path.resolve(), out.resolve())).as_posix()
    m = hs['metrics']
    text = ['# Hosted and local guardrail decision comparison', '',
            '**Preliminary authored study. Independent review and enterprise qualification remain incomplete.**', '',
            f"All {len(results)} candidates use the same {m['decisions']} test assessments from {m['cases']} cases in {m['scenario_families']} authored families. Each case has ten dependent candidate-control decisions. Calibration uses a separate 150 assessments; test labels do not select routing thresholds.", '',
            '| Candidate | Exact plans | Missed requirements | Wrong recommendations | Reviews correct | Handoffs correct | Case p50 / p95, seconds | Test API estimate per case |',
            '|---|---:|---:|---:|---:|---:|---:|---:|']
    for name, s, root in results:
        x, t = s['metrics'], s['timing']
        cost = s['cost'].get('estimated_api_usd_per_attempted_test_case')
        price = f'${cost:.4f}' if cost is not None else '$0 API'
        text.append(f"| [{name}]({link(root / 'summary.json')}) | {x['exact_plan_cases']}/{x['cases']} | {x['missed_required_controls']}/{x['required_controls']} | {x['wrong_recommendations']} | {x['correct_reviews']}/{x['expected_reviews']} | {x['correct_handoffs']}/{x['expected_handoffs']} | {t['full_case_p50_ms']/1000:.4f} / {t['full_case_p95_ms']/1000:.4f} | {price} |")
    text += ['', '## Cost and execution scope', '',
             f"The approved Claude run made {usage['calls']} API calls: one warmup, 150 calibration assessments and 150 test assessments. Provider-reported usage totals {usage['input_tokens']:,} input and {usage['output_tokens']:,} output tokens. The list-price estimate is **${hs['cost']['estimated_api_usd_all_calls']:.4f}**, within the **$8** cap. Full hosted-run wall time was **{run['elapsed_seconds']/60:.2f} minutes**.", '',
             f"Calibration cost estimate: ${phase_costs[0]:.4f}. Test cost estimate: ${phase_costs[1]:.4f}. Warmup estimate: ${warmup_estimate:.4f}, reconciled from aggregate usage minus the 300 retained assessment receipts. The original harness did not retain the individual warmup response; its response ID and content cannot be audited separately.", '',
             f"Prices use the recorded [Anthropic model documentation]({hosted.PRICE_SOURCE}) snapshot of October 18, 2026. These are published list-price estimates from usage receipts, not invoices. Hardware, energy, setup, maintenance and human review remain unpriced for every candidate. Local API cost of zero is not zero total operating cost.", '',
             'Case timings sum ten sequential requests, including client inference/API round trips and response validation. They exclude human review, deployment and actual containment. Batching or generating all ten decisions in one call has not been benchmarked. Hosted server memory is unmeasured; local process RSS and Ollama client RSS have different scopes. This compares measured configurations, not equal compute budgets.', '',
             '## Confidence routing', '',
             '| Candidate | Accepted test plans | Correct accepted | Wrong accepted | Observed risk | Test API estimate per correct accepted plan |',
             '|---|---:|---:|---:|---:|---:|']
    for name, s, _ in results:
        r = s['metrics']['routing']
        risk = 'Undefined: none accepted' if r['observed_risk'] is None else f"{100*r['observed_risk']:.1f}%"
        correct_cost = s['cost'].get('estimated_api_usd_per_correctly_accepted_test_case') if name == model else s['cost'].get('api_usd_per_correctly_accepted_case')
        cost_text = 'Undefined' if correct_cost is None else f'${correct_cost:.4f}'
        text.append(f"| {name} | {r['accepted_cases']} | {r['correctly_accepted_cases']} | {r['wrong_accepted_cases']} | {risk} | {cost_text} |")
    text += ['', 'Cost per correct accepted plan divides the complete test-phase API estimate by the number of correct accepted test plans, including API spend on deferred or incorrect plans. It is undefined when none qualify. Calibration, training and human review are accounted for separately or remain unpriced.', '',
             'The threshold maximizes observed coverage subject to at most 5% whole-plan error on the small calibration set. It is an exploratory rule, not a production guarantee. If nothing qualifies, all plans defer. Generated-model probabilities are self-estimates, not token probabilities. A zero wrong-recommendation count can mean no controls were recommended.', '',
             '## Limits and reproducibility', '',
             'All cases and proposed labels were authored for this experiment. The two independent reviewer submissions are still required; these results must not be presented as independently established ground truth. The local specialist has only 36 training cases; the larger reference corpus and source alignments did not train these candidates. This run establishes neither industry leadership nor a production containment capability.', '',
             'The rules baseline was written with knowledge of this task. Local and hosted models differ in size, prompting, adaptation and reasoning budget. This is one run per configuration; repeated-run variability and inference optimizations have not been studied. Results apply to the frozen four-disposition task and configurations. The first two local training recipes also differ in learning rate, so their difference does not isolate encoder adaptation.', '',
             f"Offline audit: [AUDIT.json](AUDIT.json). Approved payload hash: `{manifest['preview_sha256']}`. Dataset manifest: `{hs['data_manifest_sha256']}`. Executed benchmark: `{hs['benchmark_sha256']}`.", '',
             'The offline audit checks exact paired calibration/test states and labels, exported-body scope, source snapshots, complete request accounting, per-request token costs and reported metrics. It makes no new model or network calls.']
    (out / 'COMPARISON.md').write_text('\n'.join(text) + '\n')
    audit = {'status': 'PASSED_OFFLINE_PAIRED_RUN_AUDIT', 'candidates': len(results),
             'data_manifest_sha256': hs['data_manifest_sha256'], 'benchmark_sha256': hs['benchmark_sha256'],
             'approved_preview_sha256': manifest['preview_sha256'], 'hosted_adapter_sha256': run['adapter_sha256'],
             'approved_calls': 301, 'observed_calls': usage['calls'], 'usage_tokens': {k: usage[k] for k in warmup_tokens},
             'estimated_api_usd': hs['cost']['estimated_api_usd_all_calls'], 'approved_budget_usd': 8,
             'calibration_assessments': len(hc), 'test_assessments': len(ht),
             'warmup_receipt_limit': 'Only aggregate-difference token accounting; individual response not retained',
             'reporter_sha256': digest(Path(__file__)), 'qualification': 'AUTHORED_STUDY_PENDING_INDEPENDENT_REVIEW'}
    (out / 'AUDIT.json').write_text(json.dumps(audit, indent=2) + '\n')
    return audit


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    for flag in ('local', 'hosted', 'preview', 'approval', 'out'):
        ap.add_argument('--' + flag, type=Path, required=True)
    a = ap.parse_args()
    print(json.dumps(render(a.local, a.hosted, a.preview, a.approval, a.out), indent=2))
