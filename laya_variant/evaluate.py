#!/usr/bin/env python3
"""
Evaluate one or more Laya checkpoints — and two non-model baselines — on every split, through
laya's public inference API (`Agent.predict_batch`), exactly as classify.py will call it.

Per question:  accuracy, positive-class F1 (yes/no), Brier, ECE on `answer_confidence`
               (the calibrated max-p quantity; NOT laya's `confidence`, which for choice/score is
               normalised entropy and is not what temperature scaling fits), and the coverage
               you keep if you only accept answers above the confidence that gives >= --target
               accuracy on the `cal` split (selective prediction; everything else goes to a human).
Per task:      macro accuracy, and for exceptions the end-to-end triage verdict agreement.
Baselines:     "majority" (per-question most frequent train label), "keywords" (a few lines of
               regex a reviewer could write in ten minutes), and two learned ones from baselines.py:
               tf-idf + logistic regression and tf-idf cosine kNN. Optionally the local model you
               already run, zero-shot through Ollama (--ollama-model qwen3-coder:30b).
Gate:          pooled accuracy on the keyword-weak yes/no questions of --gate-split (default gold).
               The bar is the BEST baseline, not keywords. A model passes only if it beats the bar
               with McNemar p < 0.05 and ECE <= 0.10 there. Predictors run in parallel.

Usage:
  python3 laya_variant/evaluate.py --data laya_variant/data \
      --model base=convaiinnovations/laya --model td=convaiinnovations/laya:typed-decisions \
      --model v1=runs/v1 --splits test_iid,test_ood,gold,scenario --out runs/report
  # add the local LLM as a baseline (runs on your Mac, where Ollama is):
  OLLAMA_NUM_PARALLEL=4 ollama serve &   # then:
  python3 laya_variant/evaluate.py --splits gold,scenario --ollama-model qwen3-coder:30b --out runs/qwen
"""
import argparse, collections, concurrent.futures as cf, hashlib, json, math, pathlib, random, re, sys, time

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent / "generator"))
import lv  # noqa: E402
from questions import QUESTION_SETS, render, strip_private, label_keys  # noqa: E402

YESNO = lambda q: q["type"] == "noul"


# ------------------------------------------------------------------ predictors

def model_predictor(spec, mode, device):
    name, _, ref = spec.partition("=")
    model, _, sub = ref.partition(":")
    agent = lv.load_agent(model, sub or None, device)
    trained_mode = agent.cfg.get("trustfall_variant", {}).get("mode")
    m = trained_mode or mode

    def predict(task, states):
        qs = render(QUESTION_SETS[task], m)
        res = agent.predict_batch(states, strip_private(qs), batch_size=16)
        out = []
        for r in res:
            row = {}
            for qid, ans in r["answers"].items():
                keys = label_keys(qs[qid])
                if ans["type"] == "noul":
                    p = [1 - ans["noul"], ans["noul"]]
                else:
                    p = [ans["probabilities"][k] for k in keys]
                row[qid] = {"p": p, "keys": keys, "was_noul": qs[qid].get("_was_noul", False) or ans["type"] == "noul",
                            "conf": ans["answer_confidence"]}
            out.append(row)
        return out
    meta = {"name": name, "model": model, "subfolder": sub or None, "mode": m,
            "calibrated": agent.cfg.get("trustfall_variant", {}).get("calibrated", False),
            "variant": {k: v for k, v in agent.cfg.get("trustfall_variant", {}).items() if k not in ("history", "calibration")}}
    return name, predict, meta


def majority_predictor(train_rows):
    counts = collections.defaultdict(collections.Counter)
    for r in train_rows:
        for q, v in r["labels"].items(): counts[q][json.dumps(v)] += 1
    top = {q: json.loads(c.most_common(1)[0][0]) for q, c in counts.items()}

    def predict(task, states):
        return [{q: _hard(QUESTION_SETS[task][q], top[q]) for q in QUESTION_SETS[task] if q in top} for _ in states]
    return "majority", predict, {"name": "majority"}


KW = {
    "asks_network": r"egress|east-west|traffic|connect|talk to|reach|internet|cut .* off",
    "asks_identity": r"service account|token|identity|secrets|kubernetes api|credential",
    "asks_workload_security": r"privilege|privileged|root|capabilit|hostpath|host network|read-only root",
    "asks_supply_chain": r"image|registry|signed|digest|docker\.io",
    "asks_agent_behaviour": r"\bagent\b|assistant|bot|copilot|tool",
    "asks_evidence": r"evidence|forensic|preserve|capture the memory|audit trail|context log",
    "asks_runtime_detection": r"alert|page |tell us when|detect",
    "concrete_need": r"\bneeds?\b|\bfails?\b|until|window|rollout|finishes|runs",
    "owner_accountable": r"@|\(|[A-Z]\. [A-Z]",
    "touches_suspect": None,
    "authority_unverified": r"approved|ok'd|said it's fine|pre-approved|system note|note to",
    "echoes_agent_input": r"no ticket|skip|bypass|api credentials|authori[sz]ed",
    "prompt_injection": r"system note|ignore (your|all|previous)|assistant|you are now|debugbot|note to any",
    "jailbreak": r"ignore (your|all|previous)|no rules|maintenance mode",
    "requests_sensitive_data": r"credential|card|token|export|environment variables|api key|cardholder|ssn",
    "requests_privilege_change": r"clusterrolebinding|skip approval|access|on-call group|no need for a ticket|widen",
    "requests_prod_change": r"scale|restart|roll back|deploy|patch|delete|bump",
}

def keyword_predictor():
    def text_of(task, s):
        if task == "intent": return s["intent"]
        if task == "input": return s["text"]
        ex = s["exception"]
        return {"owner": ex["owner"], "reason": ex["reason"], "all": json.dumps(s)}

    def predict(task, states):
        out = []
        for s in states:
            row, t = {}, text_of(task, s)
            for q, qd in QUESTION_SETS[task].items():
                if not YESNO(qd):
                    continue
                if task == "exception":
                    if q == "touches_suspect":
                        v = s["exception"]["workload"] in s["incident"] or s["exception"]["workload"] == "*"
                    else:
                        v = bool(re.search(KW[q], t["owner"] if q == "owner_accountable" else t["reason"], re.I))
                else:
                    v = bool(re.search(KW[q], t, re.I))
                row[q] = _hard(qd, v)
            out.append(row)
        return out
    return "keywords", predict, {"name": "keywords"}


def _hard(qd, v):
    keys = label_keys(qd)
    key = ("true" if v else "false") if isinstance(v, bool) else v
    return {"p": [1.0 if k == key else 0.0 for k in keys], "keys": keys, "was_noul": isinstance(v, bool), "conf": 1.0}


# ------------------------------------------------------------------ metrics

def gold_key(qd_keys, v, was_noul):
    if isinstance(v, bool):
        if "true" in qd_keys: return "true" if v else "false"
        return "A" if v else "B"
    return v


def metrics(pairs):
    """pairs: list of (pred dict, gold value)."""
    import numpy as np
    try:
        from laya.common import ece_score
    except ImportError:   # baselines-only runs (e.g. the Ollama column on a laptop) don't need laya installed
        ece_score = lambda conf, correct: _ece(list(conf), list(correct))
    if not pairs: return {}
    correct, conf, brier, tp = [], [], [], {"tp": 0, "fp": 0, "fn": 0}
    for pr, g in pairs:
        gk = gold_key(pr["keys"], g, pr["was_noul"])
        valid = pr.get('valid', True)
        pk = pr.get('decision', pr['keys'][max(range(len(pr['p'])), key=lambda i: pr['p'][i])]) if valid else None
        correct.append(valid and pk == gk); conf.append(pr['conf'] if valid else 0)
        if valid and pr.get('distribution_valid', True):
            brier.append(sum((pr["p"][i] - (1.0 if pr["keys"][i] == gk else 0.0)) ** 2 for i in range(len(pr["keys"]))))
        if isinstance(g, bool):
            pos = "true" if "true" in pr["keys"] else "A"
            tp["tp"] += (pk == pos and gk == pos); tp["fp"] += (pk == pos and gk != pos); tp["fn"] += (pk != pos and gk == pos)
    answered = [i for i, (pr, _) in enumerate(pairs) if pr.get('valid', True)]
    m = {"n": len(pairs), "accuracy": round(float(np.mean(correct)), 4),
         'answered': len(answered), 'unreadable': len(pairs) - len(answered),
         'answer_coverage': round(len(answered) / len(pairs), 4),
         "brier": round(float(np.mean(brier)), 4) if brier else None,
         'brier_items': len(brier),
         "ece": round(ece_score(np.array([conf[i] for i in answered]), np.array([correct[i] for i in answered], dtype=float)), 4) if answered else None}
    if isinstance(pairs[0][1], bool):
        p = tp["tp"] / max(1, tp["tp"] + tp["fp"]); r = tp["tp"] / max(1, tp["tp"] + tp["fn"])
        m["f1_pos"] = round(2 * p * r / max(1e-9, p + r), 4)
    return m, list(zip(conf, correct))


def selective(cal_cc, test_cc, target):
    """Lowest threshold whose cal accuracy (on answers at or above it) >= target; coverage/accuracy on test."""
    if not cal_cc: return None
    ths = sorted({c for c, _ in cal_cc})
    thr = None
    for t in ths:
        kept = [ok for c, ok in cal_cc if c >= t]
        if kept and sum(kept) / len(kept) >= target:
            thr = t; break
    if thr is None: return {"threshold": None, "coverage": 0.0}
    kept = [ok for c, ok in test_cc if c >= thr]
    return {"threshold": round(thr, 4), "coverage": round(len(kept) / max(1, len(test_cc)), 4),
            "accuracy_kept": round(sum(kept) / len(kept), 4) if kept else None}


def _scaled(pr, T):
    """Temperature-scale one prediction's probability vector: p_i ∝ p_i^(1/T). Accuracy is unchanged; confidence moves."""
    if T == 1.0 or not pr.get('valid', True): return pr
    w = [max(x, 1e-9) ** (1.0 / T) for x in pr["p"]]; z = sum(w); p = [x / z for x in w]
    decision = pr.get('decision')
    return {**pr, "p": p, "conf": p[pr['keys'].index(decision)] if decision in pr['keys'] else max(p)}


def fit_temperature(pairs):
    """One temperature per question, by negative log-likelihood on the cal split (Guo et al. 2017). T=1 if too few rows."""
    pairs = [(pr, g) for pr, g in pairs if pr.get('valid', True) and pr.get('distribution_valid', True)]
    if len(pairs) < 20: return 1.0
    best, bestT = None, 1.0
    for i in range(61):
        T = math.exp(math.log(0.25) + i * (math.log(8) - math.log(0.25)) / 60)
        nll = 0.0
        for pr, g in pairs:
            gk = gold_key(pr["keys"], g, pr["was_noul"]); sp = _scaled(pr, T)
            nll -= math.log(max(sp["p"][pr["keys"].index(gk)], 1e-9)) if gk in pr["keys"] else 0.0
        if best is None or nll < best: best, bestT = nll, T
    return round(bestT, 3)


def run(predictors, data, splits, target, temp_scale=False):
    import classify  # triage rule lives with the inference code, one definition
    import baselines
    rows_by = {s: lv.load_rows(pathlib.Path(data) / f"{s}.jsonl") for s in set(splits) | {"cal"}}
    def one(pred):
        name, predict, meta = pred
        rep = {"meta": meta, "splits": {}}
        cc_cal = collections.defaultdict(list); temps = {}
        need_cal = temp_scale or not meta.get("skip_cal")
        order = (["cal"] if need_cal else []) + [s for s in splits if s != "cal"]
        for split in order:
            rows = rows_by[split]
            per_q = collections.defaultdict(list); ids = collections.defaultdict(list); groups = collections.defaultdict(list)
            triage = []; t0 = time.time()
            for task in ("intent", "exception", "input"):
                tr = [r for r in rows if r["task"] == task]
                if not tr: continue
                preds = predict(task, [r["state"] for r in tr])
                if len(preds) > len(tr): raise ValueError('Predictor returned extra rows')
                preds = list(preds) + [{} for _ in range(len(tr) - len(preds))]
                for r, pr in zip(tr, preds):
                    if not isinstance(pr, dict): pr = {}
                    for q, g in r["labels"].items():
                        if q not in pr:
                            # Keyword rules deliberately support predicates only.
                            if name == 'keywords' and QUESTION_SETS[task][q]['type'] != 'noul': continue
                            pr[q] = baselines.failed_answer(QUESTION_SETS[task][q], 'missing')
                        try:
                            _validate_prediction(pr[q])
                        except (KeyError, TypeError, ValueError):
                            pr[q] = baselines.failed_answer(QUESTION_SETS[task][q], 'malformed')
                        per_q[q].append((pr[q], g))
                        group = f"{task}:{r['id']}"
                        ids[q].append(f'{group}:{q}'); groups[q].append(group)
                    if task == "exception" and all(q in pr and pr[q].get('valid', True) for q in QUESTION_SETS["exception"]):
                        triage.append((classify.triage(_as_answers(pr))[0], classify.triage(_gold_answers(r["labels"]))[0]))
            out = {}
            for q, pairs in per_q.items():
                if temp_scale:
                    if split == "cal": temps[q] = fit_temperature(pairs)
                    pairs = [(_scaled(pr, temps.get(q, 1.0)), g) for pr, g in pairs]
                m, cc = metrics(pairs)
                if temp_scale: m["temperature"] = temps.get(q, 1.0)
                if split == "cal": cc_cal[q] = cc
                else:
                    sel = selective(cc_cal.get(q), cc, target)
                    if sel: m["selective"] = sel
                    m["correct"] = [int(ok) for _, ok in cc]   # per item, row order: paired tests across predictors
                    m["conf"] = [round(float(c), 4) for c, _ in cc]
                    m['valid'] = [bool(pr.get('valid', True)) for pr, _ in pairs]
                    m['ids'] = ids[q]; m['groups'] = groups[q]
                out[q] = m
            s = {"questions": out, "seconds": round(time.time() - t0, 1)}
            if triage:
                s['triage_answered_rows'] = len(triage)
                s["triage_agreement"] = round(sum(a == b for a, b in triage) / len(triage), 4)
                s["triage_confusion"] = dict(collections.Counter(f"{b}->{a}" for a, b in triage))
            if split != "cal": rep["splits"][split] = s
        if temp_scale: rep["meta"] = {**meta, "temperature_scaled_on": "cal"}
        return name + ("+T" if temp_scale else ""), rep

    with cf.ThreadPoolExecutor(max_workers=max(1, len(predictors))) as ex:
        return dict(ex.map(one, predictors))


BASELINE_NAMES = ("majority", "keywords", "tfidf-lr", "tfidf-lr-full-state", "tfidf-knn15")


def _validate_prediction(pr):
    if not pr.get('valid', True): return
    p, keys = pr['p'], pr['keys']
    if not p or len(p) != len(keys) or len(set(keys)) != len(keys): raise ValueError('Invalid distribution shape')
    if any(isinstance(x, bool) or not math.isfinite(x) or not 0 <= x <= 1 for x in p): raise ValueError('Invalid probabilities')
    tol = len(p)*.00005 + 1e-9 if all(round(x, 4) == x for x in p) else 1e-5
    if not math.isclose(sum(p), 1, abs_tol=tol): raise ValueError('Distribution does not sum to one')
    pr['p'] = [x/sum(p) for x in p]
    c = pr['conf']
    if isinstance(c, bool) or not math.isfinite(c) or not 0 <= c <= 1: raise ValueError('Invalid confidence')
    if 'decision' in pr and pr['decision'] not in keys: raise ValueError('Invalid decision')


# Pre-registered (build log, Sep 24, before any model was scored): the yes/no questions keyword rules
# handle worst on test_ood. Fixed here so the gate never picks its questions on the split it scores.
GATE_QUESTIONS = ("authority_unverified", "concrete_need", "echoes_agent_input", "prompt_injection", "requests_privilege_change")


def keyword_weak(report, split):
    return list(GATE_QUESTIONS)


def _boot_delta(a, b, n_boot=4000):
    """95% paired bootstrap interval for mean(a) - mean(b). Deterministic (fixed LCG), no numpy needed."""
    if len(a) != len(b) or not a: raise ValueError('Paired predictions must have equal nonzero length')
    n = len(a); x = 12345; ds = []
    for _ in range(n_boot):
        s = 0
        for _ in range(n):
            x = (1103515245 * x + 12345) % 2 ** 31; i = x % n; s += a[i] - b[i]
        ds.append(s / n)
    ds.sort()
    return round(ds[int(0.025 * n_boot)], 4), round(ds[int(0.975 * n_boot) - 1], 4)


def _mcnemar(a, b):
    """Exact two-sided McNemar on paired 0/1 lists: a right & b wrong vs the reverse."""
    if len(a) != len(b): raise ValueError('Paired predictions must have equal length')
    n10 = sum(1 for x, y in zip(a, b) if x and not y); n01 = sum(1 for x, y in zip(a, b) if y and not x)
    n = n10 + n01
    if n == 0: return 1.0, n10, n01
    k = min(n10, n01)
    p = sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n
    return min(1.0, 2 * p), n10, n01


def _ece(conf, correct, bins=10):
    e, n = 0.0, len(conf)
    for i in range(bins):
        lo, hi = i / bins, (i + 1) / bins
        idx = [j for j, c in enumerate(conf) if (lo < c <= hi) or (i == 0 and c == 0)]
        if idx:
            e += len(idx) / n * abs(sum(correct[j] for j in idx) / len(idx) - sum(conf[j] for j in idx) / len(idx))
    return e


def _cluster_boot_delta(a, b, groups, n_boot=4000):
    """Resample whole states, preserving dependence between questions on a state."""
    if not a or len(a) != len(b) or len(a) != len(groups): raise ValueError('Unpaired state groups')
    by = collections.defaultdict(list)
    for x, y, group in zip(a, b, groups): by[group].append(x - y)
    clusters = list(by.values()); rng = random.Random(12345); ds = []
    for _ in range(n_boot):
        sample = [clusters[rng.randrange(len(clusters))] for _ in clusters]
        ds.append(sum(sum(c) for c in sample) / sum(len(c) for c in sample))
    ds.sort()
    return [round(ds[int(.025*n_boot)], 4), round(ds[int(.975*n_boot)-1], 4)]


def gate(report, split):
    weak = keyword_weak(report, split)
    pooled = {}
    for n, rep in report.items():
        qs = rep["splits"].get(split, {}).get("questions", {})
        if not weak or not all(q in qs and "correct" in qs[q] for q in weak): continue
        corr = [x for q in weak for x in qs[q]["correct"]]; conf = [x for q in weak for x in qs[q]["conf"]]
        valid = [x for q in weak for x in qs[q].get('valid', [True] * len(qs[q]['correct']))]
        ids = [x for q in weak for x in qs[q].get('ids', [])]
        groups = [x for q in weak for x in qs[q].get('groups', [])]
        if not corr: continue
        answered = [i for i, v in enumerate(valid) if v]
        pooled[n] = {"n": len(corr), "accuracy": round(sum(corr) / len(corr), 4),
                     'answered': len(answered), 'unreadable': len(corr) - len(answered),
                     'states': len(set(groups)) if groups else None,
                     "ece": round(_ece([conf[i] for i in answered], [corr[i] for i in answered]), 4) if answered else None,
                     "_c": corr, '_ids': ids, '_groups': groups}
    base = {n: v for n, v in pooled.items() if n.split("+")[0] in BASELINE_NAMES}
    if not base: return {"split": split, "questions": weak, "note": "no baselines"}
    bar_name = max(base, key=lambda n: base[n]["accuracy"]); bar = base[bar_name]
    acc = bar["accuracy"]
    public = lambda v: {k: x for k, x in v.items() if not k.startswith('_')}
    out = {"split": split, "questions": weak, "bar": {"name": bar_name, **public(bar)},
           'protocol_revision': '2026-10-13: explicit failed answers, identity pairing, state bootstrap',
           'statistical_limitations': 'Author-labelled states; best baseline selected on scored split; pooled McNemar is exploratory because questions on a state are correlated. No production eligibility.',
           "candidates": {}}
    for nme, v in pooled.items():
        if nme.split("+")[0] in BASELINE_NAMES: continue
        if v['unreadable'] or bar['unreadable']:
            out['candidates'][nme] = {**public(v), 'verdict': 'INCOMPLETE',
                'reason': 'Missing or invalid answers; diagnostic accuracy counts them wrong. No complete paired model comparison.'}
            continue
        if not v['_ids'] or v['_ids'] != bar['_ids'] or v['_groups'] != bar['_groups']:
            out['candidates'][nme] = {**public(v), 'verdict': 'UNPAIRED', 'reason': 'Item identities do not match'}
            continue
        p, n10, n01 = _mcnemar(v["_c"], bar["_c"])
        lo, hi = _cluster_boot_delta(v['_c'], bar['_c'], v['_groups'])
        verdict = ("PASS" if v["accuracy"] > acc and p < 0.05 and lo > 0 and v["ece"] <= 0.10 else
                   "NOT PROVEN" if v["accuracy"] > acc else "FAIL")
        out["candidates"][nme] = {"accuracy": v["accuracy"], "ece": v["ece"], "delta_vs_bar": round(v["accuracy"] - acc, 4),
                                  "mcnemar_p": round(p, 4), "delta_95ci": [lo, hi], "only_candidate_right": n10, "only_bar_right": n01, "verdict": verdict}
    out["all"] = {k: public(v) for k, v in pooled.items()}
    return out


def _as_answers(pr):
    """Predictor output -> the answer shape classify.triage() reads."""
    out = {}
    for q, v in pr.items():
        if v["was_noul"]:
            pt = v["p"][1] if "true" in v["keys"] else v["p"][0]
            out[q] = {"type": "noul", "noul": pt}
        else:
            out[q] = {"type": "choice", "choice": v.get('decision', v["keys"][max(range(len(v["p"])), key=lambda i: v["p"][i])])}
    return out


def _gold_answers(labels):
    return {q: ({"type": "noul", "noul": 1.0 if v else 0.0} if isinstance(v, bool) else {"type": "choice", "choice": v}) for q, v in labels.items()}


def markdown(report, splits, gate_result=None):
    L = ["# Laya variant evaluation", "",
         "Generated by `laya_variant/evaluate.py`. Constructed splits are labelled by construction; `scenario` rows are the",
         "session's real inputs (author-labelled, never trained on). Results on these inputs do not establish production performance.",
         'Missing or invalid answers count wrong and reduce answer coverage. ECE uses answered items only. Brier uses actual distributions only; generated self-ratings are not posterior distributions.', '']
    names = list(report)
    for split in splits:
        L += [f"## {split}", "", "| question | " + " | ".join(names) + " |", "|---|" + "---|" * len(names)]
        qs = sorted({q for n in names for q in report[n]["splits"].get(split, {}).get("questions", {})})
        for q in qs:
            cells = []
            for n in names:
                m = report[n]["splits"].get(split, {}).get("questions", {}).get(q)
                if not m: cells.append("—"); continue
                c = f"{m['accuracy']:.2f}"
                if m.get('ece') is not None and n not in ("majority", "keywords"): c += f" · ece {m['ece']:.2f}"
                if m.get('unreadable'): c += f" · {m['unreadable']} unreadable"
                if m.get("selective") and m["selective"].get("threshold") is not None and n not in ("majority", "keywords"):
                    c += f" · cov {m['selective']['coverage']:.2f}"
                cells.append(c)
            L.append(f"| {q} | " + " | ".join(cells) + " |")
        tri = [report[n]["splits"].get(split, {}).get("triage_agreement") for n in names]
        if any(t is not None for t in tri):
            L.append("| **exception triage verdict** | " + " | ".join("—" if t is None else f"**{t:.2f}**" for t in tri) + " |")
        L.append("")
    L += ["Cells: accuracy · ECE on answer_confidence · coverage kept at the cal-set threshold for the target accuracy.", ""]
    if gate_result and gate_result.get("bar"):
        g = gate_result
        L += [f"## Gate ({g['split']}, pre-registered keyword-weak yes/no questions, pooled)", "",
              "Questions (pre-registered Sep 24, fixed in evaluate.GATE_QUESTIONS): " + ", ".join(f"`{q}`" for q in g["questions"]) + ".", "",
              "| predictor | items | answered | states | diagnostic accuracy | ECE (answered) |", "|---|---|---|---|---|---|"]
        for n, v in g["all"].items():
            ece = f"{v['ece']:.3f}" if v['ece'] is not None else '—'
            L.append(f"| {n}{' (bar)' if n == g['bar']['name'] else ''} | {v['n']} | {v['answered']} | {v['states']} | {v['accuracy']:.3f} | {ece} |")
        L += ["", f"Bar: **{g['bar']['name']} {g['bar']['accuracy']:.3f}**. The {g['bar']['n']} question decisions come from {g['bar']['states']} states.", g['statistical_limitations'], '']
        for n, c in g["candidates"].items():
            if 'reason' in c:
                L.append(f"- **{n}: {c['verdict']}** · {c['reason']}")
                continue
            L.append(f"- **{n}: {c['verdict']}** · {c['accuracy']:.3f} ({c['delta_vs_bar']:+.3f} vs bar) · ECE {c['ece']:.3f} · "
                     f"state-bootstrap 95% CI of the gap [{c['delta_95ci'][0]:+.3f}, {c['delta_95ci'][1]:+.3f}] · exploratory McNemar p {c['mcnemar_p']:.3f} (only it right {c['only_candidate_right']}, only the bar right {c['only_bar_right']})")
        L += ["", "PASS needs: a complete identity-paired comparison, above the bar, exploratory McNemar p < 0.05, the state-bootstrap gap's 95% CI above zero, ECE <= 0.10. The gold labels are Claude-authored: "
              "a PASS on them is provisional until two independent labellers agree.", ""]
    for n in names:
        L.append(f"- **{n}**: `{json.dumps(report[n]['meta'])}`")
    return "\n".join(L) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=str(HERE / "data"))
    ap.add_argument("--model", action="append", default=[], help="name=hub_id[:subfolder] or name=local_dir")
    ap.add_argument("--mode", default="labels_ab", help="rendering for checkpoints not trained here")
    ap.add_argument("--splits", default="test_iid,test_ood,scenario")
    ap.add_argument("--target", type=float, default=0.95, help="accuracy target for selective prediction")
    ap.add_argument("--no-baselines", action="store_true")
    ap.add_argument("--no-learned-baselines", action="store_true", help="skip tf-idf LR / kNN")
    ap.add_argument("--ollama-model", action="append", default=[], help="local LLM baseline via Ollama, e.g. qwen3-coder:30b")
    ap.add_argument("--ollama-url", default="http://localhost:11434")
    ap.add_argument("--ollama-recording", action="append", default=[], help="score a recorded real Ollama run (recordings/*.jsonl)")
    ap.add_argument("--decider-url", action="append", default=[], help="a running `strands-decider serve` (e.g. http://localhost:8000)")
    ap.add_argument("--decider-recording", action="append", default=[], help="score a recorded real Decider run")
    ap.add_argument('--openai-decisions-model', action='append', default=[], help='Paid Decisions API candidate, currently gpt-6-luna')
    ap.add_argument('--openai-decisions-recording', action='append', default=[], help='Replay exact states and questions, no API calls')
    ap.add_argument('--openai-env-file', help='Private dotenv or bare OPENAI_API_KEY file; never stored in reports')
    ap.add_argument('--openai-workers', type=int, default=1, help='Concurrent Decisions requests, 1..8; default serial')
    ap.add_argument("--workers", type=int, default=4, help="concurrent Ollama requests")
    ap.add_argument("--gate-split", default="gold")
    ap.add_argument("--temperature-scale", action="store_true", help="fit one temperature per question on the cal split, apply it to every other split")
    ap.add_argument("--device")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    out = pathlib.Path(a.out)
    if out.exists() and any(out.iterdir()):
        sys.exit('Output directory is not empty; preserve earlier evidence and use a new directory')
    if a.openai_decisions_model:
        import openai_decisions
        if a.openai_env_file: openai_decisions.load_credentials(a.openai_env_file, 'openai')
        openai_decisions.require_key('OPENAI_API_KEY')
    splits = a.splits.split(",")
    preds = []
    if not a.no_baselines:
        train = lv.load_rows(pathlib.Path(a.data) / "train.jsonl")
        preds += [majority_predictor(train), keyword_predictor()]
        if not a.no_learned_baselines:
            import baselines
            preds += [baselines.tfidf_lr_predictor(train), baselines.tfidf_knn_predictor(train)]
            preds.append(baselines.tfidf_lr_predictor(train, full_state=True))
    for m in a.ollama_model:
        import baselines
        preds.append(baselines.ollama_predictor(m, a.ollama_url, a.workers))
    for u in a.decider_url:
        import baselines
        preds.append(baselines.decider_predictor(u, a.workers))
    for r in a.decider_recording:
        import baselines
        preds.append(baselines.recorded_decider_predictor(r))
    for r in a.ollama_recording:
        import baselines
        preds.append(baselines.recorded_ollama_predictor(r))
    for m in a.openai_decisions_model:
        import openai_decisions
        preds.append(openai_decisions.predictor(m, a.openai_workers))
    for r in a.openai_decisions_recording:
        import openai_decisions
        preds.append(openai_decisions.recorded_predictor(r))
    for m in a.model:
        try:
            preds.append(model_predictor(m, a.mode, a.device))
        except Exception as e:
            print(f"could not load {m}: {type(e).__name__}: {str(e).splitlines()[0][:200]}", file=sys.stderr)
    if a.gate_split not in splits: splits.append(a.gate_split)
    if a.temperature_scale:   # +T reuses the same answers: cache them so the model is asked once
        def memo(pred):
            name, fn, meta = pred; cache = {}
            def f(task, states):
                k = (task, json.dumps(states, sort_keys=True))
                if k not in cache: cache[k] = fn(task, states)
                return cache[k]
            return name, f, meta
        preds = [memo(p) for p in preds]
    rep = run(preds, a.data, splits, a.target)
    if a.temperature_scale:   # the same predictors again, recalibrated: raw and +T side by side
        rep.update(run([p for p in preds if p[0] not in ("majority", "keywords")], a.data, splits, a.target, temp_scale=True))
    g = gate(rep, a.gate_split)
    out.mkdir(parents=True, exist_ok=True)
    for name, pr in rep.items():   # raw model responses, for re-scoring and provenance
        raw = pr["meta"].pop("_raw", None)
        if raw:
            (out / f"{name.replace(':', '-')}-recording.jsonl").write_text("".join(json.dumps(r) + "\n" for r in raw))
    manifest = {s: hashlib.sha256((pathlib.Path(a.data) / f'{s}.jsonl').read_bytes()).hexdigest()
                for s in set(splits) | {'train', 'cal'} if (pathlib.Path(a.data) / f'{s}.jsonl').is_file()}
    provenance = {'data_sha256': manifest,
                  'source_sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in [HERE / 'evaluate.py', HERE / 'baselines.py', HERE / 'questions.py']},
                  'recording_sha256': {str(p): hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
                                       for p in a.ollama_recording + a.decider_recording + a.openai_decisions_recording}}
    (out / "report.json").write_text(json.dumps({"predictors": rep, "gate": g, 'provenance': provenance}, indent=1) + "\n")
    (out / "REPORT.md").write_text(markdown(rep, splits, g))
    print((out / "REPORT.md").read_text())

if __name__ == "__main__":
    main()
