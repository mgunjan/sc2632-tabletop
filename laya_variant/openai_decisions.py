"""Decisions API triage candidate with exact-state and exact-question replay.

One HTTP request per state containing all task questions. Labels never enter the
request. Raw probability signals, usage and client latency remain in the recording.
No retries: failed requests stay visible and cannot qualify as a complete run.
"""
import concurrent.futures as cf
import hashlib
import json
import pathlib
import sys
import time

import baselines
from questions import QUESTION_SETS, strip_private

BENCH = pathlib.Path(__file__).resolve().parents[1] / 'submission/2026-10-12/benchmark'
sys.path.insert(0, str(BENCH))
from provider_clients import OpenAIDecisionsProvider, load_credentials, require_key  # noqa: E402


def questions_hash(task):
    # Option order changes model input; never alphabetize the criteria for this binding.
    return hashlib.sha256(json.dumps(strip_private(QUESTION_SETS[task])).encode()).hexdigest()


def predictor(model='gpt-6-luna', workers=1, provider=None):
    provider = provider or OpenAIDecisionsProvider(model)
    if not 1 <= workers <= 8: raise ValueError('workers must be within 1..8')
    stats = {'rows': 0, 'failed_rows': 0}
    raw = []

    def call(task, state):
        start = time.perf_counter(); response = {}; error = None
        try:
            response = provider.decide(state, strip_private(QUESTION_SETS[task]))
        except Exception as exc:
            # Error classes only: no remote error bodies or credentials in evidence.
            error = type(exc).__name__
        return {'task': task, 'model': model,
                'state_sha256': hashlib.sha256(json.dumps(state, sort_keys=True).encode()).hexdigest(),
                'questions_sha256': questions_hash(task), 'state': state,
                'ms': round((time.perf_counter() - start) * 1000, 3), 'error': error, 'response': response}

    def predict(task, states):
        with cf.ThreadPoolExecutor(max_workers=workers) as pool:
            records = list(pool.map(lambda state: call(task, state), states))
        raw.extend(records)
        return baselines._decider_rows(task, [r['response'] for r in records], stats)

    name = f'openai-decisions:{model}'
    return name, predict, {'name': name, 'model': model, 'endpoint': '/v1/decisions', 'api_status': 'public beta',
                           'zero_shot': True, 'workers': workers, 'skip_cal': True, 'stats': stats, '_raw': raw,
                           'confidence': 'API choice confidence or max predicate probability; local calibration not fitted',
                           'latency_basis': 'one request per state, excludes setup; concurrent requests include contention'}


def recorded_predictor(path):
    records = [json.loads(line) for line in pathlib.Path(path).read_text().splitlines() if line.strip()]
    by = baselines._recording_index(records)
    model = records[0]['model'] if records else '?'
    stats = {'rows': 0, 'failed_rows': 0, 'missing': 0, 'question_mismatch': 0, 'model_mismatch': 0}

    def predict(task, states):
        responses = []
        for state in states:
            key = (task, hashlib.sha256(json.dumps(state, sort_keys=True).encode()).hexdigest())
            r = by.get(key)
            if r is None:
                stats['missing'] += 1
                responses.append({})
            elif r.get('questions_sha256') != questions_hash(task):
                stats['question_mismatch'] += 1
                responses.append({})
            elif r.get('response', {}).get('model') != model:
                stats['model_mismatch'] += 1
                responses.append({})
            else:
                responses.append(r.get('response', {}))
        return baselines._decider_rows(task, responses, stats)

    name = f'openai-decisions:{model}'
    return name, predict, {'name': name, 'recording': str(path), 'skip_cal': True, 'stats': stats,
                           'confidence': 'API choice confidence or max predicate probability; local calibration not fitted'}
