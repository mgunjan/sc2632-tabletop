#!/usr/bin/env python3
"""
End-to-end test of the variant pipeline on a TINY RANDOM checkpoint (no Hugging Face needed):
build data -> make checkpoint -> train -> calibrate -> evaluate -> classify.py loads the result.

What it proves: the plumbing works against laya's real Agent code, training and inference encode
identically, calibration writes temperatures laya actually applies, and classify.py reports the
variant as calibrated. What it does NOT prove: that any trained model is accurate. The tiny model
is noise by design.

Run: python3 laya_variant/test_pipeline.py
"""
import json, pathlib, subprocess, sys, tempfile

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(ROOT / "generator"))
PASSED = []

def ok(name): PASSED.append(name); print(f"ok  {name}", flush=True)

def sh(*args):
    r = subprocess.run([sys.executable, *args], cwd=ROOT, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stdout[-2000:], r.stderr[-2000:]); raise SystemExit(f"FAILED: {' '.join(args)}")
    return r.stdout

def main():
    import numpy as np, torch
    import laya, lv
    from laya.common import collate_items
    from questions import render, strip_private, INPUT_Q
    tmp = pathlib.Path(tempfile.mkdtemp())
    data, ckpt, run = tmp / "data", tmp / "tiny", tmp / "run"

    sh("laya_variant/build_dataset.py", "--n", "240", "--seed", "3", "--with-dev", "--out", str(data))
    man = json.loads((data / "MANIFEST.json").read_text())
    assert man["splits"]["scenario"]["rows"] == 9 and man["splits"]["gold"]["rows"] >= 40
    train_t = {json.loads(l)["template"] for l in (data / "train.jsonl").read_text().splitlines()}
    ood_t = {json.loads(l)["template"] for l in (data / "test_ood.jsonl").read_text().splitlines()}
    assert len(train_t & ood_t) <= 0.05 * len(ood_t), "test_ood must use held-out templates"
    ok("dataset builds; scenario + gold rows present; test_ood templates are held out")

    from make_tiny_checkpoint import build
    build(ckpt, str(data / "train.jsonl"))
    agent = laya.load(str(ckpt), device="cpu")
    ok("tiny checkpoint loads through laya.load")

    # Parity: probabilities from our training encoding == laya's own predict().
    rows = [r for r in lv.load_rows(data / "test_iid.jsonl") if r["task"] == "input"][:3]
    for mode in ("noul", "labels_ab", "choice_ab"):
        qs = render(INPUT_Q, mode)
        for r in rows:
            g = lv.encode_rows(agent, [r], mode)
            b = collate_items(g, agent.tok.pad_token_id)
            with torch.no_grad():
                logits, _ = agent.model(b["input_ids"], b["attention_mask"], b["marker_pos"], b["marker_mask"], b["qtype"])
            ours = torch.softmax(logits[:, :2], -1)[:, 1 if mode != "choice_ab" else 0].numpy()
            ans = agent.predict(r["state"], strip_private(qs))["answers"]
            theirs = np.array([ans[q]["noul"] if ans[q]["type"] == "noul" else ans[q]["probabilities"]["A"] for q in qs if q in r["labels"]])
            assert np.allclose(ours, theirs, atol=2e-3), (mode, ours, theirs)
    ok("training encoding matches laya.predict() exactly, in all three noul renderings")

    assert (data/'dev.jsonl').is_file() and (data/'cal.jsonl').is_file()

    out = sh("laya_variant/train.py", "--base", str(ckpt), "--data", str(data), "--out", str(run),
             "--epochs", "1", "--limit", "40", "--device", "cpu", "--lr", "3e-3")
    cfg = json.loads((run / "rl_agent_config.json").read_text())
    assert cfg["trustfall_variant"]["question_set"] and cfg["temperature"] == [1.0, 1.0, 1.0]
    assert "temperature_by_options" not in cfg
    assert cfg['trustfall_variant']['selection_split'] == 'dev'
    receipt=json.loads((run/'TRAINING-RUN.json').read_text())
    assert receipt['selection_split']=='dev' and receipt['total_completed_steps']==10
    assert receipt['full_run_elapsed_seconds']>=receipt['optimizer_compute_seconds']>0
    assert (run/'TRAINER.py.txt').is_file()
    ok("train.py saves a checkpoint with manifest and neutral temperatures")

    sh("laya_variant/calibrate.py", "--model", str(run), "--data", str(data), "--device", "cpu", "--min-rows", "10")
    cfg = json.loads((run / "rl_agent_config.json").read_text())
    assert cfg["trustfall_variant"]["calibrated"] is True and cfg.get("temperature_by_options")
    a2 = laya.load(str(run), device="cpu")
    assert a2.temperature_by_options == {k: min(5.0, max(0.5, v)) for k, v in cfg["temperature_by_options"].items()}
    ok("calibrate.py writes temperatures that laya applies at load")

    sh("laya_variant/evaluate.py", "--data", str(data), "--model", f"v={run}", "--splits", "test_ood,scenario,gold",
       "--device", "cpu", "--out", str(tmp / "rep"))
    full = json.loads((tmp / "rep" / "report.json").read_text()); rep = full["predictors"]
    assert {"majority", "keywords", "tfidf-lr", "tfidf-knn15", "v"} <= set(rep) and "scenario" in rep["v"]["splits"]
    assert rep["v"]["meta"]["calibrated"] is True
    g = full["gate"]
    assert g["bar"]["name"] in ("majority", "keywords", "tfidf-lr", "tfidf-lr-full-state", "tfidf-knn15") and g["candidates"]["v"]["verdict"] in ("PASS", "NOT PROVEN", "FAIL", "INCOMPLETE")
    ok("evaluate.py reports model + four baselines (incl. tf-idf LR and kNN) and a gate against the best baseline")

    import classify
    eng = classify.Engine(str(run), device="cpu")
    assert eng.agent is not None and eng.calibrated and eng.mode == cfg["trustfall_variant"]["mode"]
    res = classify.classify("b", (ROOT / "generator/intent-b.txt").read_text(),
                            json.loads((ROOT / "generator/spec-b.json").read_text()), eng)
    assert res["input"]["status"] == "ok" and len(res["input"]["inputs"]) == 2
    sec = classify.pr_section(res)
    assert "**Calibrated**" in sec and "Uncalibrated" not in sec
    ok("classify.py loads the variant, uses its trained rendering, and says it is calibrated")
    print(f"{len(PASSED)} passed")

if __name__ == "__main__":
    main()
