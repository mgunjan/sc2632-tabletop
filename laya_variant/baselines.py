"""
Stronger baselines for the Laya gate, in the same predictor interface as evaluate.py
(name, predict(task, states) -> [ {qid: {"p", "keys", "was_noul", "conf"}} ], meta).

  tfidf-lr    word 1-2 grams + character 3-5 grams, logistic regression (class-balanced). The
              "few hundred labels and a linear model" baseline.
  tfidf-knn   the same features, cosine similarity, 15 nearest training rows vote (distance-weighted).
  ollama:<m>  the local model you already run (e.g. qwen3-coder:30b), zero-shot, one call per row with
              every question of the task and a JSON schema for the answer. Its confidence is the
              model's own stated number: we MEASURE how calibrated that is, we don't assume it.

No learned baseline receives labels or template IDs as input. The legacy baselines
use selected text fields; tfidf-lr-full-state receives all state fields, as the LLM does.
Question wording comes from questions.py, the single definition Laya is also asked with.
"""
import concurrent.futures as cf, json, math, sys, time, urllib.request

from questions import QUESTION_SETS, label_keys


def row_text(task, s, full_state=False):
    if full_state:
        return json.dumps(s, sort_keys=True)
    if task == "intent":
        return s["intent"]
    if task == "input":
        return s["text"]
    ex = s["exception"]
    parts = [f"reason: {ex.get('reason', '')}", f"owner: {ex.get('owner', '')}",
             f"approvals: {json.dumps(ex.get('approvals', []))}",
             f"agent_inputs: {json.dumps(s.get('agent_inputs', []))}"]
    return " || ".join(parts)


def _p_row(qd, probs_by_key, conf=None):
    keys = label_keys(qd)
    p = [float(probs_by_key.get(k, 0.0)) for k in keys]
    if any(not math.isfinite(x) or x < 0 for x in p) or sum(p) <= 0:
        raise ValueError('Invalid probability weights')
    z = sum(p)
    p = [x / z for x in p]
    c = max(p) if conf is None else _probability(conf)
    return {"p": p, "keys": keys, "was_noul": qd["type"] == "noul", "conf": c,
            "valid": True, "decision": keys[max(range(len(p)), key=p.__getitem__)]}


def _probability(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 1:
        raise ValueError('Expected a finite probability in [0,1]')
    return float(value)


def failed_answer(qd, reason='unreadable'):
    # Uniform weights are only a shape placeholder, never an inferred negative answer.
    return {**_p_row(qd, {k: 1 for k in label_keys(qd)}, conf=0),
            'valid': False, 'decision': None, 'failure': reason, 'distribution_valid': False}


def _recording_index(recs):
    by = {}
    for r in recs:
        key = (r['task'], r['state_sha256'])
        if key in by:
            raise ValueError('Duplicate task/state in recording')
        by[key] = r
    if len({r['model'] for r in recs}) > 1:
        raise ValueError('Mixed models in recording')
    return by


def _key(qd, v):
    if isinstance(v, bool):
        return "true" if v else "false"
    return v


def _features():
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.pipeline import make_union
    return make_union(TfidfVectorizer(ngram_range=(1, 2), min_df=2, sublinear_tf=True),
                      TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=2, sublinear_tf=True))


def _fit_per_question(train_rows, make_model, full_state=False):
    models = {}
    for task, qs in QUESTION_SETS.items():
        rows = [r for r in train_rows if r["task"] == task]
        if not rows:
            continue
        for q, qd in qs.items():
            lab = [(row_text(task, r["state"], full_state), _key(qd, r["labels"][q])) for r in rows if q in r["labels"]]
            if len({y for _, y in lab}) < 2:
                continue
            models[(task, q)] = make_model([x for x, _ in lab], [y for _, y in lab])
    return models


def tfidf_lr_predictor(train_rows, full_state=False):
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline

    def make(X, y):
        return make_pipeline(_features(), LogisticRegression(max_iter=2000, C=4, class_weight="balanced")).fit(X, y)
    start = time.perf_counter()
    models = _fit_per_question(train_rows, make, full_state)
    fit_seconds = time.perf_counter() - start

    def predict(task, states):
        X = [row_text(task, s, full_state) for s in states]
        out = [dict() for _ in states]
        for q, qd in QUESTION_SETS[task].items():
            m = models.get((task, q))
            if not m:
                continue
            P = m.predict_proba(X)
            for i, row in enumerate(P):
                out[i][q] = _p_row(qd, dict(zip(m.classes_, row)))
        return out
    name = 'tfidf-lr-full-state' if full_state else 'tfidf-lr'
    return name, predict, {"name": name, "features": "word 1-2 + char_wb 3-5 tf-idf", "C": 4,
                           'training_states': len(train_rows), 'fit_seconds': round(fit_seconds, 3),
                           'input_fields': 'all state fields' if full_state else 'legacy selected text fields; excludes workload/TTL/incident for exceptions'}


def tfidf_knn_predictor(train_rows, k=15):
    import numpy as np

    class KNN:
        def __init__(self, X, y):
            self.f = _features().fit(X)
            self.M = self.f.transform(X)
            self.y = np.array(y)
            self.classes_ = sorted(set(y))

        def predict_proba(self, X):
            S = (self.f.transform(X) @ self.M.T).toarray()   # rows are L2-normalised per vectoriser: cosine-like
            out = []
            for s in S:
                idx = np.argsort(-s)[:k]
                w = {c: 0.0 for c in self.classes_}
                for j in idx:
                    w[self.y[j]] += max(s[j], 1e-6)
                z = sum(w.values())
                out.append([(w[c] + 0.5) / (z + 0.5 * len(w)) for c in self.classes_])   # light smoothing
            return out
    models = _fit_per_question(train_rows, KNN)

    def predict(task, states):
        X = [row_text(task, s) for s in states]
        out = [dict() for _ in states]
        for q, qd in QUESTION_SETS[task].items():
            m = models.get((task, q))
            if not m:
                continue
            for i, row in enumerate(m.predict_proba(X)):
                out[i][q] = _p_row(qd, dict(zip(m.classes_, row)))
        return out
    return f"tfidf-knn{k}", predict, {"name": f"tfidf-knn{k}", "k": k}


# ------------------------------------------------------------------ the local model you already run

def _schema(task):
    props = {}
    for q, qd in QUESTION_SETS[task].items():
        ans = {"type": "boolean"} if qd["type"] == "noul" else {"type": "string", "enum": label_keys(qd)}
        props[q] = {"type": "object", "properties": {"answer": ans, "confidence": {"type": "number"}},
                    "required": ["answer", "confidence"]}
    return {"type": "object", "properties": props, "required": list(props)}


def _prompt(task, state):
    lines = [f"You are reviewing one `{ {'intent': 'intent', 'exception': 'exception', 'input': 'input'}[task] }` "
             "record for a Kubernetes security team. Answer every question about the record below.",
             "For each question give `answer` and `confidence`: your probability, from 0 to 1, that your answer is correct.",
             "", "RECORD:", json.dumps(state, indent=1), "", "QUESTIONS:"]
    for q, qd in QUESTION_SETS[task].items():
        if qd["type"] == "noul":
            lines.append(f"- {q} (true/false): {qd['instructions']}")
        else:
            opts = "; ".join(f"{k} = {v}" for k, v in qd["criteria"].items())
            lines.append(f"- {q} (one of {', '.join(qd['criteria'])}): {qd['instructions']} Options: {opts}")
    return "\n".join(lines)


def ollama_predictor(model, url="http://localhost:11434", workers=4, timeout=300):
    """Zero-shot, temperature 0. Rows run `workers` at a time (set OLLAMA_NUM_PARALLEL >= workers on the server)."""
    def call(task, state):
        body = {"model": model, "stream": False, "format": _schema(task), "options": {"temperature": 0, "num_ctx": 8192},
                "messages": [{"role": "user", "content": _prompt(task, state)}]}
        req = urllib.request.Request(f"{url}/api/chat", data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
        for attempt in range(3):
            try:
                with urllib.request.urlopen(req, timeout=timeout) as r:
                    return json.loads(json.loads(r.read())["message"]["content"])
            except Exception as e:  # noqa: BLE001 — a failed row is counted, not hidden
                err = e
        print(f"ollama: row failed after 3 attempts: {type(err).__name__}: {err}", file=sys.stderr)
        return {}

    stats = {"failed_rows": 0, "rows": 0}

    def predict(task, states):
        with cf.ThreadPoolExecutor(max_workers=workers) as ex:
            answers = list(ex.map(lambda s: call(task, s), states))
        return _rows(task, answers, stats)
    return f"ollama:{model}", predict, {"name": f"ollama:{model}", "url": url, "zero_shot": True,
                                        "confidence": "self-reported", "skip_cal": True, "stats": stats}


def recorded_ollama_predictor(path):
    """Score answers a real Ollama run already produced (recordings/<model>-<date>.jsonl, one line per row:
    {"state_sha256", "task", "model", "content", ...}). Used when the model runs on another machine: the
    recording is the raw model output, matched to rows by a hash of the exact prompt state, never by position."""
    import hashlib
    recs = [json.loads(l) for l in open(path)]
    by = _recording_index(recs)
    model = recs[0]["model"] if recs else "?"
    stats = {"failed_rows": 0, "rows": 0, "missing": 0}

    def predict(task, states):
        answers = []
        for s in states:
            r = by.get((task, hashlib.sha256(json.dumps(s, sort_keys=True).encode()).hexdigest()))
            if r is None:
                stats["missing"] += 1; answers.append({}); continue
            try:
                answers.append(json.loads(r["content"]) if r.get("content") else {})
            except json.JSONDecodeError:
                answers.append({})
        return _rows(task, answers, stats)
    return f"ollama:{model}", predict, {"name": f"ollama:{model}", "recording": str(path), "zero_shot": True,
                                        "confidence": "self-reported", "skip_cal": True, "stats": stats}


def _rows(task, answers, stats):
    out = []
    for a in answers:
        stats['rows'] += 1
        row = {}
        for q, qd in QUESTION_SETS[task].items():
            v = a.get(q) if isinstance(a, dict) else None
            try:
                if not isinstance(v, dict):
                    raise ValueError('Missing answer')
                c = _probability(v.get('confidence'))
                value = v.get('answer')
                if qd['type'] == 'noul' and not isinstance(value, bool):
                    raise ValueError('Expected boolean answer')
                pick = _key(qd, value)
                keys = label_keys(qd)
                if pick not in keys:
                    raise ValueError('Unknown answer')
                top = max(c, 1 / len(keys) + 1e-6)
                rest = (1 - top) / max(1, len(keys) - 1)
                row[q] = {**_p_row(qd, {k: top if k == pick else rest for k in keys}, conf=c),
                          'decision': pick, 'distribution_valid': False}
            except (TypeError, ValueError):
                row[q] = failed_answer(qd)
        bad = sum(not v['valid'] for v in row.values())
        stats['failed_rows'] += bad == len(row)
        stats['unreadable_answers'] = stats.get('unreadable_answers', 0) + bad
        out.append(row)
    return out


# ------------------------------------------------------------------ Strands Decider (a Jev-style decision model)
# `strands-decider serve <model> --port 8000` exposes POST /v1/systemone {"state": ..., "questions": {...}}: the same
# typed-question format as questions.py (noul / choice, instructions, criteria), so the questions go over unchanged.
# The response shape is parsed defensively and the first real response is kept verbatim in the recording, so a
# parser mistake shows up as a failed row, never as a silently wrong answer.

def _decider_questions(task):
    from questions import strip_private
    return strip_private(QUESTION_SETS[task])


def _decider_answer_checked(qd, a):
    """One answer object from the server -> our row format, or None if it can't be read."""
    if not isinstance(a, dict):
        return None
    keys = label_keys(qd)
    conf = a.get("answer_confidence", a.get("confidence"))
    if qd["type"] == "noul":
        pt = a.get("noul", a.get("p_true", a.get("probability")))
        if pt is None and isinstance(a.get("probabilities"), dict):
            pr = a["probabilities"]; pt = pr.get("true", pr.get("yes", pr.get("A")))
        if pt is None and isinstance(a.get("answer"), bool):
            pt = 1.0 if a["answer"] else 0.0
        if pt is None:
            return None
        pt = _probability(pt)
        return _p_row(qd, {"true": pt, "false": 1 - pt}, conf=_probability(conf) if conf is not None else max(pt, 1 - pt))
    pr = a.get("probabilities")
    if pr is not None and (not isinstance(pr, dict) or set(pr) != set(keys)):
        return None
    if isinstance(pr, dict) and set(pr) == set(keys):
        pr = {k: _probability(pr[k]) for k in keys}
        # Laya 0.3.12 serializes each probability to four decimals. Its sum can
        # differ by at most half a rounding unit per option; normalize only that drift.
        tol = len(keys)*.00005 + 1e-9 if all(round(v, 4) == v for v in pr.values()) else 1e-5
        if not math.isclose(sum(pr.values()), 1, abs_tol=tol):
            return None
        got = _p_row(qd, pr, conf=_probability(conf) if conf is not None else None)
        if 'choice' in a:
            if a['choice'] not in keys: return None
            got['decision'] = a['choice']
        return got
    pick = a.get("choice", a.get("answer"))
    if pick in keys:
        c = _probability(conf) if conf is not None else 1.0
        top = max(c, 1 / len(keys) + 1e-6); rest = (1 - top) / max(1, len(keys) - 1)
        return {**_p_row(qd, {k: (top if k == pick else rest) for k in keys}, conf=c), 'decision': pick, 'distribution_valid': False}
    return None


def _decider_answer(qd, a):
    try:
        return _decider_answer_checked(qd, a)
    except (TypeError, ValueError):
        return None


def _decider_rows(task, responses, stats):
    out = []
    for r in responses:
        stats["rows"] += 1
        answers = r.get('answers', r) if isinstance(r, dict) else {}
        if not isinstance(answers, dict): answers = {}
        row, bad = {}, 0
        for q, qd in QUESTION_SETS[task].items():
            got = _decider_answer(qd, answers.get(q))
            if got is None:
                bad += 1; got = failed_answer(qd)
            row[q] = got
        stats["failed_rows"] += bad == len(QUESTION_SETS[task])
        stats["unreadable_answers"] = stats.get("unreadable_answers", 0) + bad
        out.append(row)
    return out


def decider_predictor(url="http://localhost:8000", workers=4, timeout=120, model="strands-decider-2B-hobson-v19"):
    def call(task, state):
        body = {"state": json.dumps(state, indent=1), "questions": _decider_questions(task)}
        req = urllib.request.Request(f"{url}/v1/systemone", data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
        for _ in range(3):
            try:
                with urllib.request.urlopen(req, timeout=timeout) as r:
                    return json.loads(r.read())
            except Exception as e:  # noqa: BLE001
                err = e
        print(f"decider: row failed after 3 attempts: {type(err).__name__}: {err}", file=sys.stderr)
        return {}
    stats = {"failed_rows": 0, "rows": 0}
    raw = []   # every response verbatim, keyed by the exact state, so the run can be re-scored anywhere

    def predict(task, states):
        import hashlib
        with cf.ThreadPoolExecutor(max_workers=workers) as ex:
            responses = list(ex.map(lambda s: call(task, s), states))
        for s, r in zip(states, responses):
            raw.append({"task": task, "model": model, "state_sha256": hashlib.sha256(json.dumps(s, sort_keys=True).encode()).hexdigest(), "response": r})
        return _decider_rows(task, responses, stats)
    return f"decider:{model}", predict, {"name": f"decider:{model}", "url": url, "zero_shot": True,
                                         "confidence": "model reliability score", "skip_cal": True, "stats": stats, "_raw": raw}


def recorded_decider_predictor(path):
    """Score a recorded real Decider run (one JSON line per row: {"state_sha256", "model", "response"})."""
    import hashlib
    recs = [json.loads(l) for l in open(path)]
    by = _recording_index(recs)
    model = recs[0]["model"] if recs else "?"
    stats = {"failed_rows": 0, "rows": 0, "missing": 0}

    def predict(task, states):
        resp = []
        for s in states:
            r = by.get((task, hashlib.sha256(json.dumps(s, sort_keys=True).encode()).hexdigest()))
            if r is None:
                stats["missing"] += 1
            resp.append((r or {}).get("response", {}))
        return _decider_rows(task, resp, stats)
    return f"decider:{model}", predict, {"name": f"decider:{model}", "recording": str(path), "zero_shot": True,
                                         "confidence": "model reliability score", "skip_cal": True, "stats": stats}
