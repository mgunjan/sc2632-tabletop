#!/usr/bin/env python3
"""
Run the pre-registered evaluation (generator/decider-eval.yaml) against a live Strands Decider server and record
every answer. Real runs only: nothing here is simulated, and the recording says which model served it.

  python3 generator/decider_eval.py                      # server at http://127.0.0.1:8000
  python3 generator/decider_eval.py --decider URL --label mac-m-series

Writes generator/recordings/decider-eval-<served model>-<date>[-label].jsonl (one line per call) and a .summary.json,
prints a summary, and exits 0 only if gates G1 and G2 pass (G3 is reported). The demo only runs the model live when
this exits 0 on the presenting laptop.
"""
import argparse, collections, datetime, hashlib, json, pathlib, platform, statistics, sys

GEN = pathlib.Path(__file__).resolve().parent
ROOT = GEN.parent
sys.path.insert(0, str(GEN))
import decider_agent as da  # noqa: E402


def load_items(cfg):
    items = []
    d = cfg["demo"]
    intent = (ROOT / d["intent_file"]).read_text()
    for i, (c, lab) in enumerate(zip(da.split_clauses(intent), d["labels"]), 1):
        for r in range(cfg["repeats"]):
            items.append({"set": "demo", "id": f"demo-{i}", "repeat": r, "text": c, "intent": intent, **lab})
    assert len(da.split_clauses(intent)) == len(d["labels"]), "demo labels must cover every sentence"
    for s, labs in cfg["core"].items():
        intent = (GEN / f"intent-{s}.txt").read_text()
        cl = da.split_clauses(intent)
        assert len(cl) == len(labs), f"core {s}: {len(cl)} sentences, {len(labs)} labels"
        items += [{"set": "core", "id": f"{s}-{i}", "text": c, "intent": intent, **lab} for i, (c, lab) in enumerate(zip(cl, labs), 1)]
    items += [{"set": "paraphrase", "id": f"p-{i}", "intent": p["text"], **p} for i, p in enumerate(cfg["paraphrase"], 1)]
    items += [{"set": "hostile", "id": f"h-{i}", "text": t, "intent": t, "control": None} for i, t in enumerate(cfg["hostile"], 1)]
    return items


def judge(item, choice, conf, threshold):
    if item["control"] is None:
        return "reported"
    good = {item["control"], *item.get("ok", [])}
    if choice is None:
        return "unreadable"
    if conf < threshold:
        return "escalated"
    return "correct" if choice in good else "CONFIDENT_MISS"


def gates(rows, threshold):
    by = collections.defaultdict(list)
    for r in rows:
        by[r["set"]].append(r)
    g = {}
    demo = collections.defaultdict(list)
    for r in by["demo"]:
        demo[r["id"]].append(r)
    g1_fail = []
    for i, rs in demo.items():
        if len({r["choice"] for r in rs}) != 1:
            g1_fail.append(f"{i}: repeats disagree {sorted({str(r['choice']) for r in rs})}")
        if any(r["verdict"] == "CONFIDENT_MISS" or r["verdict"] == "unreadable" for r in rs):
            g1_fail.append(f"{i}: {rs[0]['choice']} ({rs[0]['confidence']:.2f})")
        if rs[0].get("must_be_confident") and any(r["verdict"] != "correct" for r in rs):
            g1_fail.append(f"{i}: must be confident and correct, got {rs[0]['choice']} ({rs[0]['confidence']:.2f})")
    g["G1_demo"] = {"pass": not g1_fail and bool(demo), "problems": g1_fail}
    core = by["core"]
    miss = sum(r["verdict"] == "CONFIDENT_MISS" for r in core)
    good = sum(r["verdict"] == "correct" for r in core)
    g["G2_core"] = {"pass": len(core) == 11 and miss <= 1 and good >= 7, "confident_correct": good, "confident_miss": miss,
                    "escalated": sum(r["verdict"] == "escalated" for r in core), "of": len(core)}
    allr = core + by["paraphrase"]
    m = sum(r["verdict"] == "CONFIDENT_MISS" for r in allr)
    g["G3_all"] = {"pass": bool(allr) and m <= 0.10 * len(allr), "confident_miss": m, "of": len(allr),
                   "confident_correct": sum(r["verdict"] == "correct" for r in allr),
                   "escalated": sum(r["verdict"] == "escalated" for r in allr)}
    return g


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--decider", default="http://127.0.0.1:8000")
    ap.add_argument("--config", default=str(GEN / "decider-eval.yaml"))
    ap.add_argument("--label", default="", help="appended to the recording name, e.g. the laptop")
    ap.add_argument("--outdir", default=str(GEN / "recordings"))
    a = ap.parse_args()
    import yaml
    import demo_gate
    raw_cfg = pathlib.Path(a.config).read_bytes()
    cfg = yaml.safe_load(raw_cfg)
    th = float(cfg["threshold"])
    if not da.healthy(a.decider, timeout=5):
        sys.exit(f"no Decider server answering at {a.decider}/health: start it with scripts/decider-up.sh")
    items = load_items(cfg)
    rows = []
    for n, it in enumerate(items, 1):
        try:
            resp = da.ask(a.decider, it["text"], it["intent"], timeout=120)
        except Exception as e:  # noqa: BLE001 — recorded as unreadable, never retried into a better answer
            resp = {"error": f"{type(e).__name__}: {e}"}
        choice, conf, pr = da.parse_choice(resp)
        v = judge(it, choice, conf, th)
        rows.append({**{k: it[k] for k in ("set", "id", "text", "control") if k in it}, "repeat": it.get("repeat"),
                     "ok": it.get("ok", []), "must_be_confident": it.get("must_be_confident", False),
                     "choice": choice, "confidence": round(conf, 4), "verdict": v,
                     "probabilities": {k: round(p, 4) for k, p in sorted(pr.items(), key=lambda kv: -kv[1])[:3]},
                     "served_model": resp.get("model"), "client_ms": resp.get("client_ms"), "raw_error": resp.get("error")})
        print(f"[{n:>3}/{len(items)}] {v:<14} {conf:.2f} {str(choice):<38} {it['text'][:60]}", flush=True)
    served = sorted({r["served_model"] for r in rows if r["served_model"]}) or ["unknown"]
    lat = [r["client_ms"] for r in rows if r["client_ms"]]
    g = gates(rows, th)
    summary = {"served_model": served, "decider_url": a.decider, "threshold": th,
               "config_sha256": hashlib.sha256(raw_cfg).hexdigest(),
               "agent_question_sha256": hashlib.sha256(json.dumps(da.QUESTION, sort_keys=True).encode()).hexdigest(),
               "host": demo_gate.host(), "runtime_fingerprints": demo_gate.fingerprints(),
               "recorded_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
               "latency_ms": {"median": round(statistics.median(lat), 1) if lat else None,
                              "p95": round(sorted(lat)[int(0.95 * (len(lat) - 1))], 1) if lat else None, "n": len(lat)},
               "gates": g, "demo_live_allowed": g["G1_demo"]["pass"] and g["G2_core"]["pass"],
               "hostile": [{"text": r["text"], "choice": r["choice"], "confidence": r["confidence"],
                            "escalated": r["confidence"] < th} for r in rows if r["set"] == "hostile"]}
    # the whole agent, 5 times on Scenario A against the fixtures: it must finish, write the privilege policy, and agree
    import tempfile
    import policy_agent as pa
    runs = []; first_recording = None
    for r in range(cfg["repeats"]):
        d = pathlib.Path(tempfile.mkdtemp()) / "pr"
        try:
            rec = pa.Agent("a", (ROOT / cfg["demo"]["intent_file"]).read_text(), a.decider, th, False, d, echo=lambda *_: None).run()
            if first_recording is None:
                first_recording = rec
            runs.append({"repeat": r, "finished": (d / "PR.md").exists(),
                         "privilege_policy": (d / "policies" / "deny-privilege-escalation.yaml").exists(),
                         "served_model": rec["model"],
                         "independent_privilege_pass": rec["readiness"]["independent_behavior"]["passed"],
                         "trace": [t["what"] + ": " + t["detail"] for t in rec["trace"]],
                         "decisions": [(c["about"], c.get("choice"), c.get("confidence")) for c in rec["calls"]],
                         "requests": rec["requests"], "escalations": rec["escalations"]})
        except Exception as e:  # noqa: BLE001
            runs.append({"repeat": r, "finished": False, "error": f"{type(e).__name__}: {e}"})
        print(f"[agent {r + 1}/{cfg['repeats']}] finished={runs[-1]['finished']} privilege_policy={runs[-1].get('privilege_policy')}", flush=True)
    same = len({json.dumps([x[:2] for x in rr.get("decisions", [])]) for rr in runs}) == 1
    agent_ok = all(rr["finished"] and rr.get("privilege_policy") for rr in runs) and same
    g["G1_demo"]["agent_runs"] = {"pass": agent_ok, "identical_decisions": same, "trace_of_first": runs[0].get("trace")}
    if not agent_ok:
        g["G1_demo"]["pass"] = False
        g["G1_demo"]["problems"].append("agent run: " + ("decisions differ between repeats" if not same else "did not finish with the privilege policy"))
    summary["gates"] = g; summary["demo_live_allowed"] = g["G1_demo"]["pass"] and g["G2_core"]["pass"]
    out = pathlib.Path(a.outdir); out.mkdir(parents=True, exist_ok=True)

    stem = f"decider-eval-{served[0].split('/')[-1]}-{datetime.date.today().isoformat()}" + (f"-{a.label}" if a.label else "")
    (out / f"{stem}.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    (out / f"{stem}.agent-runs.json").write_text(json.dumps(runs, indent=2) + "\n")
    (out / f"{stem}.demo-replay.json").write_text(json.dumps(first_recording, indent=2) + "\n")
    summary["evidence"] = {kind: {"file": f"{stem}.{suffix}", "sha256": demo_gate.sha(out / f"{stem}.{suffix}")}
                           for kind, suffix in (("decisions", "jsonl"), ("agent_runs", "agent-runs.json"), ("demo_replay", "demo-replay.json"))}
    (out / f"{stem}.summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print("\n" + json.dumps({k: summary[k] for k in ("served_model", "latency_ms", "gates", "demo_live_allowed")}, indent=2))
    print(f"\nrecorded: {out / stem}.jsonl and .summary.json")
    sys.exit(0 if summary["demo_live_allowed"] else 1)


if __name__ == "__main__":
    main()
