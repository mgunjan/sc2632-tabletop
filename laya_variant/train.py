#!/usr/bin/env python3
"""
Fine-tune a Laya checkpoint on the constructed dataset.

Objective: maximise laya's own strictly proper scoring rule, `laya.common.proper_reward`
(log score + spherical score, + ranked probability score for `score` questions). With one-hot
targets the log-score term is exactly negative cross-entropy, so this is supervised training on
the same reward RLCD optimises — without RLCD's sampling, which buys nothing for single-step
decisions like these. (Upstream's notebook uses GRPO-style policy gradient; use it if you want
the RL path. This script is the simpler, deterministic-gradient one.)

Two regimes:
  --freeze-encoder   head-only: the ModernBERT encoder is frozen (laya's `detach_encoder`), only
                     the 2-layer decision head + scorer train. Minutes on an Apple-silicon GPU.
  (default)          full fine-tune. Wants a CUDA GPU (Kaggle 2xT4 is enough; see README).

Model selection is on the `cal` split's log-loss, never on a test split. Calibration
(temperature fitting) is a separate step: laya_variant/calibrate.py, on `cal` again.

Usage:
  python3 laya_variant/train.py --base convaiinnovations/laya --subfolder typed-decisions \
      --data laya_variant/data --out runs/v1 --freeze-encoder --epochs 3
"""
import argparse, hashlib, json, math, pathlib, random, shutil, subprocess, sys, time

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import lv  # noqa: E402
from questions import question_set_hash  # noqa: E402


def batches(groups, bs, rng):
    idx = list(range(len(groups))); rng.shuffle(idx)
    for i in range(0, len(idx), bs):
        yield [groups[j] for j in idx[i:i + bs]]


def step_loss(model, b, device, freeze):
    import torch
    from laya.common import proper_reward
    logits, _ = model(b["input_ids"].to(device), b["attention_mask"].to(device), b["marker_pos"].to(device),
                      b["marker_mask"].to(device), b["qtype"].to(device), detach_encoder=freeze)
    mask = b["marker_mask"].to(device).float()
    q = torch.softmax(logits, -1)
    r = proper_reward(q, b["target"].to(device), b["qtype"].to(device), mask)
    acc = (logits.argmax(-1).cpu() == b["label"]).float().mean().item()
    return -r.mean(), acc


def evaluate_loss(agent, groups, freeze, bs=16):
    import torch
    from laya.common import collate_items
    agent.model.eval(); tot = n = 0; accs = []
    with torch.no_grad():
        for i in range(0, len(groups), bs):
            b = collate_items(groups[i:i + bs], agent.tok.pad_token_id)
            l, a = step_loss(agent.model, b, agent.device, freeze)
            k = b["input_ids"].shape[0]; tot += l.item() * k; n += k; accs.append((a, k))
    return tot / max(n, 1), sum(a * k for a, k in accs) / max(n, 1)


def git_sha():
    try:
        return subprocess.check_output(["git", "-C", str(HERE.parent), "rev-parse", "--short", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"


def save(agent, base_dir, out, meta):
    from safetensors.torch import save_file
    out = pathlib.Path(out); out.mkdir(parents=True, exist_ok=True)
    for sub in ("tokenizer", "encoder"):
        if (base_dir / sub).exists():
            shutil.copytree(base_dir / sub, out / sub, dirs_exist_ok=True)
    cfg = dict(agent.cfg)
    if (out / "encoder").exists():
        cfg["encoder"] = str((out / "encoder").resolve())
    # Inherited temperatures belong to the BASE model's logits; after training they are wrong.
    # Reset to neutral and drop per-bucket values (upstream README: stale buckets silently win).
    cfg["temperature"] = [1.0, 1.0, 1.0]
    cfg.pop("temperature_by_options", None)
    cfg["trustfall_variant"] = meta
    (out / "rl_agent_config.json").write_text(json.dumps(cfg, indent=2))
    sd = {k: v.detach().cpu().contiguous() for k, v in agent.model.state_dict().items()}
    save_file(sd, str(out / "model.safetensors"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True, help="hub id or local checkpoint dir")
    ap.add_argument("--subfolder")
    ap.add_argument("--data", default=str(HERE / "data"))
    ap.add_argument("--out", required=True)
    ap.add_argument("--mode", default="labels_ab", choices=["noul", "labels_ab", "choice_ab"])
    ap.add_argument("--tasks", default="intent,exception,input")
    ap.add_argument("--freeze-encoder", action="store_true")
    ap.add_argument("--epochs", type=int, default=3)
    ap.add_argument("--lr", type=float)
    ap.add_argument("--batch-states", type=int, default=4, help="states per step; each state carries all its questions")
    ap.add_argument("--max-steps", type=int, help="stop early (tests)")
    ap.add_argument("--limit", type=int, help="use only the first N train rows (tests)")
    ap.add_argument("--device")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument('--questions', type=pathlib.Path, help='Explicit task/question definitions for a new use case')
    ap.add_argument('--selection-split', default='cal', help='Use dev for checkpoint selection, leaving cal untouched')
    ap.add_argument('--max-seconds', type=float, help='Stop training steps at a wall-clock budget; evaluation still completes')
    a = ap.parse_args()
    if pathlib.Path(a.out).exists() and any(pathlib.Path(a.out).iterdir()):
        sys.exit('Training output already exists; preserve the checkpoint and use a new directory')
    if a.epochs < 1 or a.batch_states < 1 or (a.max_steps is not None and a.max_steps < 1):
        sys.exit('Epochs, batch size and step limit must be positive')
    if a.max_seconds is not None and (not math.isfinite(a.max_seconds) or a.max_seconds <= 0):
        sys.exit('Training time budget must be positive and finite')
    if a.lr is not None and (not math.isfinite(a.lr) or a.lr <= 0):
        sys.exit('Learning rate must be positive and finite')
    if a.selection_split not in ('cal', 'dev'):
        sys.exit('Checkpoint selection must use dev or cal, never a test split')
    question_sets = json.loads(a.questions.read_text()) if a.questions else None

    import torch
    from laya.common import collate_items
    torch.manual_seed(a.seed); rng = random.Random(a.seed)
    tasks = a.tasks.split(",")
    agent = lv.load_agent(a.base, a.subfolder, a.device)
    base_dir = lv.checkpoint_dir(a.base, a.subfolder)
    train_rows = lv.load_rows(pathlib.Path(a.data) / "train.jsonl", tasks)[: a.limit]
    cal_rows = lv.load_rows(pathlib.Path(a.data) / f'{a.selection_split}.jsonl', tasks)[: (a.limit and max(8, a.limit // 4))]
    if not train_rows or not cal_rows: sys.exit('Training and selection splits must be nonempty')
    tr, cal = lv.encode_rows(agent, train_rows, a.mode, question_sets=question_sets), lv.encode_rows(agent, cal_rows, a.mode, question_sets=question_sets)
    print(f"train states {len(tr)} ({sum(map(len, tr))} question rows), cal states {len(cal)}", flush=True)

    model = agent.model
    params = [p for n, p in model.named_parameters() if not (a.freeze_encoder and n.startswith("encoder."))]
    if a.freeze_encoder:
        for n, p in model.named_parameters():
            if n.startswith("encoder."): p.requires_grad_(False)
    lr = a.lr or (1e-4 if a.freeze_encoder else 2e-5)
    opt = torch.optim.AdamW(params, lr=lr, weight_decay=0.01)
    total = a.max_steps or a.epochs * math.ceil(len(tr) / a.batch_states)
    sched = torch.optim.lr_scheduler.LambdaLR(opt, lambda s: min(1.0, (s + 1) / max(1, total // 10)) * max(0.0, 1 - s / max(1, total)))

    l0, acc0 = evaluate_loss(agent, cal, a.freeze_encoder)
    print(f"before: cal loss {l0:.4f} acc {acc0:.3f}", flush=True)
    best, step, hist = (l0, None), 0, [{"step": 0, "cal_loss": l0, "cal_acc": acc0}]
    data_manifest = (pathlib.Path(a.data) / "MANIFEST.json")
    meta = {"base": a.base, "subfolder": a.subfolder, "mode": a.mode, "tasks": tasks, "freeze_encoder": a.freeze_encoder,
            "lr": lr, "epochs": a.epochs, "seed": a.seed, "repo_sha": git_sha(),
            "question_set": hashlib.sha256(json.dumps(question_sets, sort_keys=True).encode()).hexdigest()[:16] if question_sets else question_set_hash(),
            "data_manifest_sha": hashlib.sha256(data_manifest.read_bytes()).hexdigest()[:16] if data_manifest.exists() else None,
            "calibrated": False, 'selection_split': a.selection_split,
            'question_definitions_sha256': hashlib.sha256(a.questions.read_bytes()).hexdigest() if a.questions else None,
            'data_sha256': {s: hashlib.sha256((pathlib.Path(a.data)/f'{s}.jsonl').read_bytes()).hexdigest() for s in ['train', a.selection_split]},
            'training_source_sha256': hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest()}
    t0 = time.time()
    for ep in range(a.epochs):
        model.train()
        if a.freeze_encoder: model.encoder.eval()
        for grp in batches(tr, a.batch_states, rng):
            b = collate_items(grp, agent.tok.pad_token_id)
            loss, acc = step_loss(model, b, agent.device, a.freeze_encoder)
            opt.zero_grad(); loss.backward(); torch.nn.utils.clip_grad_norm_(params, 1.0); opt.step(); sched.step(); step += 1
            if step % 50 == 0:
                print(f"  step {step}/{total} loss {loss.item():.4f} acc {acc:.3f} {time.time() - t0:.0f}s", flush=True)
            if a.max_steps and step >= a.max_steps: break
            if a.max_seconds and time.time() - t0 >= a.max_seconds: break
        lc, ac = evaluate_loss(agent, cal, a.freeze_encoder)
        hist.append({"step": step, "epoch": ep + 1, "cal_loss": lc, "cal_acc": ac})
        print(f"epoch {ep + 1}: cal loss {lc:.4f} acc {ac:.3f}", flush=True)
        if lc < best[0]:
            best = (lc, ep + 1); save(agent, base_dir, a.out, {**meta, "selected_epoch": ep + 1, "history": hist,
                'completed_steps': step, 'training_loop_seconds': round(time.time()-t0, 3)})
        if a.max_steps and step >= a.max_steps: break
        if a.max_seconds and time.time() - t0 >= a.max_seconds: break
    if best[1] is None:
        print("no epoch beat the base model on cal log-loss; nothing saved as a variant", flush=True)
        (pathlib.Path(a.out)).mkdir(parents=True, exist_ok=True)
        (pathlib.Path(a.out) / "NOT_SAVED.json").write_text(json.dumps({**meta, "history": hist}, indent=2))
        return 1
    print(f"saved epoch {best[1]} ({a.selection_split} loss {best[0]:.4f}) -> {a.out}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
