#!/usr/bin/env python3
"""
Fit temperatures on the `cal` split and write them into a checkpoint's rl_agent_config.json.

laya applies, at inference, `temperature_by_options["<type>:<size>"]` if present, else
`temperature[type]` (buckets: 2, 3-5, 6-10, 11+ options; values clamped to [0.5, 5.0]). We fit
one temperature per bucket that has enough cal rows (>= --min-rows), and one per type as the
fallback, by minimising negative log-likelihood of the true option. Nothing is fitted on train
or test data.

Usage: python3 laya_variant/calibrate.py --model runs/v1 --data laya_variant/data
"""
import argparse, json, math, pathlib, sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import lv  # noqa: E402

TMIN, TMAX = 0.5, 5.0


def collect(agent, groups, bs=16):
    import torch
    from laya.common import collate_items
    agent.model.eval(); out = []
    with torch.no_grad():
        for i in range(0, len(groups), bs):
            b = collate_items(groups[i:i + bs], agent.tok.pad_token_id)
            logits, _ = agent.model(b["input_ids"].to(agent.device), b["attention_mask"].to(agent.device),
                                    b["marker_pos"].to(agent.device), b["marker_mask"].to(agent.device), b["qtype"].to(agent.device))
            k = b["marker_mask"].sum(-1)
            for r in range(logits.shape[0]):
                out.append((int(b["qtype"][r]), int(k[r]), logits[r, : int(k[r])].float().cpu().tolist(), int(b["label"][r])))
    return out


def nll(rows, T):
    s = 0.0
    for _, _, z, y in rows:
        m = max(v / T for v in z); lse = m + math.log(sum(math.exp(v / T - m) for v in z))
        s += lse - z[y] / T
    return s / max(1, len(rows))


def fit(rows):
    """Golden-section search on log T within [TMIN, TMAX]; NLL in T is unimodal for one scalar."""
    lo, hi = math.log(TMIN), math.log(TMAX); g = (math.sqrt(5) - 1) / 2
    a, b = hi - g * (hi - lo), lo + g * (hi - lo)
    for _ in range(60):
        if nll(rows, math.exp(a)) < nll(rows, math.exp(b)): hi = b
        else: lo = a
        a, b = hi - g * (hi - lo), lo + g * (hi - lo)
    return round(math.exp((lo + hi) / 2), 4)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True, help="local checkpoint dir to calibrate IN PLACE")
    ap.add_argument("--data", default=str(HERE / "data"))
    ap.add_argument("--mode", help="question rendering; defaults to the one the checkpoint was trained with")
    ap.add_argument("--min-rows", type=int, default=50)
    ap.add_argument("--device")
    ap.add_argument('--questions', type=pathlib.Path, help='Definitions used for custom-task training')
    a = ap.parse_args()
    from laya.common import QTYPE_NAMES, temp_bucket
    d = pathlib.Path(a.model); cfg = json.loads((d / "rl_agent_config.json").read_text())
    expected = cfg.get('trustfall_variant', {}).get('question_definitions_sha256')
    if expected and (not a.questions or __import__('hashlib').sha256(a.questions.read_bytes()).hexdigest() != expected):
        sys.exit('Calibration question definitions differ from training')
    mode = a.mode or cfg.get("trustfall_variant", {}).get("mode", "labels_ab")
    # Neutral temperatures while collecting: we want the raw logits.
    cfg["temperature"] = [1.0, 1.0, 1.0]; cfg.pop("temperature_by_options", None)
    (d / "rl_agent_config.json").write_text(json.dumps(cfg, indent=2))
    agent = lv.load_agent(str(d), device=a.device)
    question_sets = json.loads(a.questions.read_text()) if a.questions else None
    rows = collect(agent, lv.encode_rows(agent, lv.load_rows(pathlib.Path(a.data) / "cal.jsonl"), mode, question_sets=question_sets))
    report = {"mode": mode, "cal_rows": len(rows), "per_type": {}, "per_bucket": {}}
    temps = [1.0, 1.0, 1.0]
    for qt in range(3):
        rs = [r for r in rows if r[0] == qt]
        if len(rs) >= a.min_rows:
            temps[qt] = fit(rs)
            report["per_type"][QTYPE_NAMES[qt]] = {"n": len(rs), "T": temps[qt], "nll_before": round(nll(rs, 1.0), 4), "nll_after": round(nll(rs, temps[qt]), 4)}
    buckets = {}
    for r in rows:
        buckets.setdefault(temp_bucket(r[0], r[1]), []).append(r)
    tbo = {}
    for bk, rs in sorted(buckets.items()):
        if len(rs) >= a.min_rows:
            tbo[bk] = fit(rs)
            report["per_bucket"][bk] = {"n": len(rs), "T": tbo[bk], "nll_before": round(nll(rs, 1.0), 4), "nll_after": round(nll(rs, tbo[bk]), 4)}
    cfg["temperature"] = temps
    if tbo: cfg["temperature_by_options"] = tbo
    lvmeta = cfg.setdefault("trustfall_variant", {})
    lvmeta["calibrated"] = True; lvmeta["calibration"] = report
    (d / "rl_agent_config.json").write_text(json.dumps(cfg, indent=2))
    print(json.dumps(report, indent=2))

if __name__ == "__main__":
    main()
