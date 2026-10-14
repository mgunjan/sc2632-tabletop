"""Measure complete fixture-based Scenario A proposal runs, without deployment."""
import argparse
import json
import os
from pathlib import Path
import statistics
import time
import comparison as pilot
from provider_clients import ClaudeProvider, JevProvider, LayaProvider, OpenAIDecisionsProvider, load_credentials, require_key


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--provider', choices=['claude', 'jev', 'laya', 'openai-decisions'], required=True)
    ap.add_argument('--env-file')
    ap.add_argument('--workspace-file')
    ap.add_argument('--run-tag')
    ap.add_argument('--repeats', type=int, default=3)
    ap.add_argument('--model')
    ap.add_argument('--device', default='mps')
    ap.add_argument('--out', type=Path)
    a = ap.parse_args()
    if not 1 <= a.repeats <= 5:
        ap.error('repeats must be 1..5')
    if a.env_file:
        load_credentials(a.env_file, 'openai' if a.provider == 'openai-decisions' else a.provider)
    if a.workspace_file:
        os.environ['ANTHROPIC_WORKSPACE_ID'] = Path(a.workspace_file).read_text().strip()
    out = a.out or pilot.OUT / 'workflow-cost' / (a.run_tag or a.provider)
    if out.exists():
        ap.error('Preserve existing run; output already exists')
    if a.provider == 'openai-decisions': require_key('OPENAI_API_KEY')
    load_start = time.perf_counter()
    if a.provider == 'laya': provider = LayaProvider(a.model or 'convaiinnovations/laya-typed-decisions', a.device)
    elif a.provider == 'claude': provider = ClaudeProvider(a.model or 'claude-opus-5-5')
    elif a.provider == 'openai-decisions': provider = OpenAIDecisionsProvider(a.model or 'gpt-6-luna')
    else: provider = JevProvider(a.model or 'jev-1.13.0')
    model_load_seconds = time.perf_counter()-load_start
    out.mkdir(parents=True)
    runs = []
    for i in range(a.repeats):
        calls = []
        def ask(url, state, question):
            start = time.perf_counter()
            try:
                raw = provider(url, state, question)
            except Exception as exc:
                calls.append({'ms': (time.perf_counter()-start)*1000, 'question': question, 'state': state,
                              'response': {}, 'error': type(exc).__name__})
                raise
            calls.append({'ms': (time.perf_counter()-start)*1000, 'question': question,
                          'state': state, 'response': raw})
            return raw
        target = out / f'run-{i+1}'
        start = time.perf_counter()
        rec = pilot.pa.Agent('a', (pilot.ROOT/'generator/intent-a.txt').read_text(), '', .6,
                             False, target, asker=ask, echo=lambda *args: None).run()
        elapsed = time.perf_counter()-start
        def valid_tokens(c, key):
            value = c['response'].get('usage', {}).get(key)
            return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None
        input_counts = [valid_tokens(c, 'input_tokens') for c in calls]
        output_counts = [valid_tokens(c, 'output_tokens') for c in calls]
        inp = sum(v for v in input_counts if v is not None)
        tokens_out = sum(v for v in output_counts if v is not None)
        cost = (inp*4+tokens_out*20)/1e6 if a.provider=='claude' else inp*.042/1e6 if a.provider=='jev' else None
        if a.provider in ['claude', 'jev'] and (any(v is None for v in input_counts) or
            (a.provider == 'claude' and any(v is None for v in output_counts))): cost = None
        if a.provider == 'openai-decisions':
            estimates = [c['response'].get('cost_estimate', {}).get('estimated_usd') for c in calls]
            cost = sum(estimates) if all(v is not None for v in estimates) else None
        row = {'run':i+1,'elapsed_seconds':elapsed,'api_seconds':sum(c['ms'] for c in calls)/1000,
               'api_calls':len(calls) if a.provider!='laya' else 0,
               'decision_calls':len(calls),'input_tokens':inp if a.provider!='laya' and all(v is not None for v in input_counts) else None,
               'output_tokens':tokens_out if a.provider!='laya' and all(v is not None for v in output_counts) else None,
               'estimated_usd':cost,'escalations':len(rec['escalations']),
               'exception_requests':len(rec['requests']),
               'privilege_policy_present':(target/'policies/deny-privilege-escalation.yaml').exists()}
        (target/'api-calls.json').write_text(json.dumps(calls,indent=2)+'\n')
        (target/'measurement.json').write_text(json.dumps(row,indent=2)+'\n')
        runs.append(row)
        print(a.provider, json.dumps(row), flush=True)
    summary = {'provider':a.provider,'model':provider.model,'runs':runs,
               'median_elapsed_seconds':statistics.median(r['elapsed_seconds'] for r in runs),
               'median_estimated_usd':statistics.median(r['estimated_usd'] for r in runs) if all(r['estimated_usd'] is not None for r in runs) else None,
               'local_api_charge_usd':0 if a.provider=='laya' else None,
               'model_load_seconds':model_load_seconds,
               'device':str(provider.agent.device) if a.provider=='laya' else 'hosted',
               'scope':'Scenario A fixtures: API decisions, compilation, Kyverno simulation and local proposal files; no human review, deployment or cluster observation',
               'cost_basis': 'Input-only Decisions list price as of 2026-10-13; not invoice' if a.provider=='openai-decisions' else 'No API charge; compute/power/hardware unpriced' if a.provider=='laya' else 'List-price estimate on 2026-10-12, not invoice; no human or operations cost',
               'reasoning_effort':'medium' if a.provider=='claude' else None}
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')


if __name__=='__main__':
    main()
