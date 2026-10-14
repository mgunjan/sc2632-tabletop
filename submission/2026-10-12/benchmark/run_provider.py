"""Run an authenticated candidate on the unchanged local pilot cases.

Example: python run_provider.py --provider jev --env-file /path/to/private.env
         python run_provider.py --provider openai --model gpt-6-astra --effort medium --env-file /path/to/private.env
This is a screening pilot, not the larger held-out production validation.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time
import comparison as pilot
from provider_clients import ClaudeProvider, JevProvider, LayaProvider, OpenAIProvider, OpenAIDecisionsProvider, require_key, load_credentials


def runtime_questions(items):
    """A separate parity evaluation; preserve legacy cases, states and labels."""
    import copy
    out = copy.deepcopy(items)
    prototypes = [pilot.da.QUESTION['control'], pilot.pa.DEP_Q, pilot.pa.BLOCK_Q]
    for item in out:
        q = item['question']
        matches = [p for p in prototypes if p == q]
        if len(matches) != 1: raise ValueError('Unknown runtime question')
        item['question'] = copy.deepcopy(matches[0])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--provider', required=True, choices=['openai', 'openai-decisions', 'claude', 'jev', 'laya'])
    ap.add_argument('--model')
    ap.add_argument('--effort', default='medium')
    ap.add_argument('--env-file')
    ap.add_argument('--device', default='mps')
    ap.add_argument('--limit', type=int, default=37)
    ap.add_argument('--agent', action='store_true')
    ap.add_argument('--out', type=Path, help='New output directory; preserve earlier runs')
    ap.add_argument('--question-order', choices=['frozen', 'runtime'], default='frozen',
                    help='Keep legacy serialization or separately measure the production option order')
    a = ap.parse_args()
    if not 1 <= a.limit <= 37:
        sys.exit('--limit must be within 1..37 for the frozen pilot')
    if a.env_file:
        if not Path(a.env_file).is_file():
            sys.exit('Environment file not found')
        load_credentials(a.env_file, 'openai' if a.provider == 'openai-decisions' else a.provider)
    if a.provider == 'openai':
        require_key('OPENAI_API_KEY')
        provider = OpenAIProvider(a.model or 'gpt-6-astra', a.effort)
    elif a.provider == 'openai-decisions':
        require_key('OPENAI_API_KEY')
        provider = OpenAIDecisionsProvider(a.model or 'gpt-6-luna')
    elif a.provider == 'claude':
        require_key('ANTHROPIC_API_KEY', 'CLAUDE_API_KEY')
        provider = ClaudeProvider(a.model or 'claude-opus-5-5', a.effort)
    elif a.provider == 'jev':
        require_key('TYPESAFE_API_KEY', 'JEV_API_KEY')
        provider = JevProvider(a.model or 'jev-1.13.0')
    else:
        provider = LayaProvider(a.model or 'convaiinnovations/laya-typed-decisions', a.device)
    cases = pilot.OUT / 'cases.json'
    contract = json.loads((pilot.OUT / 'CONTRACT.json').read_text())
    assert hashlib.sha256(cases.read_bytes()).hexdigest() == contract['cases_sha256']
    items = json.loads(cases.read_text())
    if a.question_order == 'runtime': items = runtime_questions(items)
    tag = a.provider + '-' + (a.model or provider.model).split('/')[-1] + ('-' + a.effort if a.provider in ['openai', 'claude'] else '')
    output = a.out or pilot.OUT / 'expanded' / tag
    if output.exists() and any(output.iterdir()):
        sys.exit('This run already exists; preserve it rather than overwrite')
    output.mkdir(parents=True, exist_ok=True)
    warm = provider('', 'clause: Require an approved registry.\nintent: Require an approved registry.', pilot.da.QUESTION['control'])
    (output / 'warmup.json').write_text(json.dumps(warm, indent=2) + '\n')
    rows = []
    with (output / 'responses.jsonl').open('w') as fp:
        for item in items[:a.limit]:
            start = time.perf_counter()
            raw, choice, confidence, error = {}, None, 0., None
            try:
                raw = provider('', item['state'], item['question'])
                choice, confidence = pilot.validated(raw, item['question']['criteria'])
            except Exception as e:
                error = f'{type(e).__name__}: {e}'
            row = {**item, 'choice': choice, 'confidence': confidence,
                   'correct': choice in item['expected'] if item['expected'] is not None else None,
                   'ms': round((time.perf_counter() - start) * 1000, 2),
                   'model': raw.get('model', 'unknown'), 'error': error, 'raw': raw}
            fp.write(json.dumps(row) + '\n'); fp.flush(); rows.append(row)
            print(item['id'], choice, 'correct=', row['correct'], 'ms=', row['ms'], flush=True)
    summary = pilot.summarize(rows, tag)
    summary['contract'] = contract
    summary['complete_pilot'] = len(rows) == 37
    summary['configuration'] = {'provider': a.provider, 'model': a.model or provider.model, 'effort': a.effort if a.provider in ['openai', 'claude'] else None,
        'question_order': a.question_order, 'requested_cases_sha256': hashlib.sha256(json.dumps(items[:a.limit]).encode()).hexdigest()}
    if a.provider == 'openai-decisions':
        estimates = [r['raw'].get('cost_estimate', {}).get('estimated_usd') for r in rows]
        known = [v for v in estimates if v is not None]
        summary['decision_cost_estimate'] = {'known_rows': len(known), 'unknown_rows': len(rows) - len(known),
            'known_rows_usd': sum(known), 'total_usd': sum(known) if len(known) == len(rows) else None,
            'warmup_usd_excluded': warm.get('cost_estimate', {}).get('estimated_usd'),
            'basis': 'Input-only list price as of 2026-10-13; not an invoice; agent run excluded'}
    if a.agent:
        target = output / 'agent-a'
        rec = pilot.pa.Agent('a', (pilot.ROOT / 'generator/intent-a.txt').read_text(), '', .6, False, target,
                             asker=provider, echo=print).run()
        summary['agent'] = {'privilege_policy_exists': (target / 'policies/deny-privilege-escalation.yaml').exists(),
                            'requests': rec['requests'], 'escalations': rec['escalations'], 'trace': rec['trace']}
    (output / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps({k:v for k,v in summary.items() if k not in ['contract','hostile_report_only','agent']}, indent=2))


if __name__ == '__main__':
    main()
