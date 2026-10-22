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

Model selection defaults to the separate `dev` split, never a test split.
Temperature fitting is a separate step on `cal`; do not reuse selection data.

Usage:
  python3 laya_variant/train.py --base convaiinnovations/laya --subfolder typed-decisions \
      --data laya_variant/data --out runs/v1 --freeze-encoder --epochs 3
"""
import argparse, hashlib, json, math, pathlib, random, resource, shutil, subprocess, sys, time

HERE = pathlib.Path(__file__).resolve().parent
TRAINER_SOURCE = pathlib.Path(__file__).read_bytes()
sys.path.insert(0, str(HERE))
import lv  # noqa: E402
from questions import question_set_hash  # noqa: E402


def sample_indices(groups, rng, balanced=False, count=None):
    if not balanced:
        if count is not None: raise ValueError('A fixed draw count requires balanced sampling')
        idx = list(range(len(groups))); rng.shuffle(idx); return idx
    by_label = {}
    for i, group in enumerate(groups):
        labels = {item['label'] for item in group}
        if len(labels) != 1: raise ValueError('Balanced sampling requires one label per state')
        by_label.setdefault(next(iter(labels)), []).append(i)
    labels = sorted(by_label)
    if len(labels) < 2: raise ValueError('Balanced sampling needs at least two labels')
    count = count or len(groups)
    if count % len(labels): raise ValueError('Balanced draw count must divide equally across labels')
    result = []
    for label in labels:
        pool = []
        for _ in range(count//len(labels)):
            if not pool:
                pool = list(by_label[label]); rng.shuffle(pool)
            result.append(pool.pop())
    rng.shuffle(result)
    return result


def batches(groups, bs, rng, balanced=False, count=None):
    idx = sample_indices(groups, rng, balanced, count)
    for i in range(0, len(idx), bs):
        yield [groups[j] for j in idx[i:i + bs]]


def step_loss(model, b, device, freeze, vector=False, objective='proper', with_predictions=False):
    import torch
    from laya.common import proper_reward
    logits, _ = model(b["input_ids"].to(device), b["attention_mask"].to(device), b["marker_pos"].to(device),
                      b["marker_mask"].to(device), b["qtype"].to(device), detach_encoder=freeze)
    mask = b["marker_mask"].to(device).float()
    if objective == 'cross-entropy':
        log_probs = torch.log_softmax(logits.float().masked_fill(~mask.bool(), -1e9), -1)
        losses = -(b['target'].to(device)*log_probs).sum(-1)
    else:
        q = torch.softmax(logits, -1)
        losses = -proper_reward(q, b["target"].to(device), b["qtype"].to(device), mask)
    acc = (logits.argmax(-1).cpu() == b["label"]).float().mean().item()
    result = ((losses if vector else losses.mean()), acc)
    return (*result, logits.argmax(-1).detach().cpu().reshape(-1).tolist()) if with_predictions else result


def evaluate_loss(agent, groups, freeze, bs=16, macro=False, objective='proper', predictions=None):
    import torch
    from laya.common import collate_items
    agent.model.eval(); tot = n = 0; accs = []; class_totals = {}; class_counts = {}
    with torch.no_grad():
        for i in range(0, len(groups), bs):
            b = collate_items(groups[i:i + bs], agent.tok.pad_token_id)
            losses, a, choices = step_loss(agent.model, b, agent.device, freeze, vector=True, objective=objective, with_predictions=True)
            if predictions is not None: predictions.extend(choices)
            values=losses.detach().cpu().reshape(-1).tolist(); labels=b['label'].reshape(-1).tolist()
            k = len(values); tot += sum(values); n += k; accs.append((a, k))
            for label,value in zip(labels,values):
                class_totals[label]=class_totals.get(label,0.)+value
                class_counts[label]=class_counts.get(label,0)+1
    selection_loss = sum(class_totals[k]/class_counts[k] for k in class_totals)/len(class_totals) if macro else tot/max(n,1)
    return selection_loss, sum(a * k for a, k in accs) / max(n, 1)


def plan_selection(rows, predictions, loss):
    """Dev-only lexicographic selection; no calibration or test labels are read."""
    from collections import defaultdict
    labels = ('recommend', 'review', 'handoff', 'exclude')
    if len(rows) != len(predictions) or any(r['task'] != 'guardrail_candidate' for r in rows):
        raise ValueError('Plan selection requires one guardrail decision per row')
    cases = defaultdict(list); missed = wrong_rec = other = 0
    for row, pred in zip(rows, predictions):
        expected, chosen = row['labels']['q'], labels[pred]
        cases[row['case_id']].append(chosen == expected)
        if chosen == expected: continue
        if chosen == 'exclude': missed += 1
        elif chosen == 'recommend': wrong_rec += 1
        else: other += 1
    if any(len(v) != 10 for v in cases.values()):
        raise ValueError('Plan selection requires all ten candidates per case')
    exact = sum(all(v) for v in cases.values())
    cost = 5*(missed+wrong_rec)+other
    return (-exact, cost, loss), {'exact_plans': exact, 'cases': len(cases),
        'missed_required': missed, 'wrong_recommendations': wrong_rec, 'other_errors': other,
        'development_error_cost': cost}


def git_sha():
    try:
        return subprocess.check_output(["git", "-C", str(HERE.parent), "rev-parse", "--short", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"


def configure_trainable(model, freeze_encoder=False, encoder_last_layers=None):
    """Freeze explicitly; optional final-block adaptation changes real encoder weights."""
    if freeze_encoder and encoder_last_layers is not None:
        raise ValueError('Choose head-only or encoder adaptation, not both')
    if encoder_last_layers is not None:
        layers = getattr(model.encoder, 'layers', None)
        if layers is None or not 1 <= encoder_last_layers <= len(layers):
            raise ValueError('Encoder must expose enough layers for the requested adaptation')
        for p in model.encoder.parameters(): p.requires_grad_(False)
        for layer in layers[-encoder_last_layers:]:
            for p in layer.parameters(): p.requires_grad_(True)
        final_norm = getattr(model.encoder, 'final_norm', None)
        if final_norm is not None:
            for p in final_norm.parameters(): p.requires_grad_(True)
    elif freeze_encoder:
        for p in model.encoder.parameters(): p.requires_grad_(False)
    return [p for p in model.parameters() if p.requires_grad]


def parameter_fingerprint(model, encoder_only=False):
    """Hash encoder tensors, including frozen ones, to establish actual adaptation."""
    h = hashlib.sha256(); n = 0
    for name, p in model.named_parameters():
        if encoder_only and not name.startswith('encoder.'): continue
        h.update(name.encode()); h.update(p.detach().cpu().contiguous().numpy().tobytes()); n += p.numel()
    return {'sha256': h.hexdigest(), 'parameters': n}


def save(agent, base_dir, out, meta):
    from safetensors.torch import save_file
    out = pathlib.Path(out); out.mkdir(parents=True, exist_ok=True)
    (out/'TRAINER.py.txt').write_bytes(TRAINER_SOURCE)
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
    run_start = time.perf_counter()
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True, help="hub id or local checkpoint dir")
    ap.add_argument("--subfolder")
    ap.add_argument("--data", default=str(HERE / "data"))
    ap.add_argument("--out", required=True)
    ap.add_argument("--mode", default="labels_ab", choices=["noul", "labels_ab", "choice_ab"])
    ap.add_argument("--tasks", default="intent,exception,input")
    ap.add_argument("--freeze-encoder", action="store_true")
    ap.add_argument('--encoder-last-layers', type=int, help='Adapt only the final N encoder blocks and final normalization')
    ap.add_argument("--epochs", type=int, default=3)
    ap.add_argument("--lr", type=float)
    ap.add_argument('--encoder-lr', type=float, help='Separate learning rate for adapted encoder parameters; --lr stays the head rate')
    ap.add_argument('--balanced-labels', action='store_true', help='Equal deterministic per-label draws; repeats do not create new examples')
    ap.add_argument('--steps-per-epoch', type=int, help='Fixed optimizer budget per epoch with balanced sampling')
    ap.add_argument('--selection-metric', choices=('loss','macro-loss','plan'), default='loss')
    ap.add_argument('--save-epoch-deltas', action='store_true', help='Retain trainable tensors for every epoch, including rejected checkpoints')
    ap.add_argument('--evaluate-train', action='store_true', help='Record full training-set loss/accuracy after every epoch')
    ap.add_argument('--objective', choices=('proper','cross-entropy'), default='proper', help='Stable uncapped cross-entropy is available for supervised choice tasks')
    ap.add_argument("--batch-states", type=int, default=4, help="states per step; each state carries all its questions")
    ap.add_argument("--max-steps", type=int, help="stop early (tests)")
    ap.add_argument("--limit", type=int, help="use only the first N train rows (tests)")
    ap.add_argument("--device")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument('--questions', type=pathlib.Path, help='Explicit task/question definitions for a new use case')
    ap.add_argument('--selection-split', default='dev', help='Development split for checkpoint selection; calibration stays separate')
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
    if a.encoder_lr is not None and (not math.isfinite(a.encoder_lr) or a.encoder_lr <= 0 or a.freeze_encoder):
        sys.exit('Encoder learning rate requires encoder training and must be positive and finite')
    if a.steps_per_epoch is not None and (a.steps_per_epoch < 1 or not a.balanced_labels):
        sys.exit('Fixed steps per epoch require balanced sampling and a positive step count')
    if a.selection_split not in ('cal', 'dev'):
        sys.exit('Checkpoint selection must use dev or cal, never a test split')
    if a.selection_metric == 'plan' and a.selection_split != 'dev':
        sys.exit('Plan selection must use dev; keep calibration separate')
    if a.freeze_encoder and a.encoder_last_layers is not None:
        sys.exit('Choose head-only or encoder adaptation, not both')
    question_sets = json.loads(a.questions.read_text()) if a.questions else None
    if not (pathlib.Path(a.data)/f'{a.selection_split}.jsonl').is_file():
        sys.exit(f'Missing {a.selection_split}.jsonl. Build separate development data; the legacy triage builder supports --with-dev. Do not silently reuse calibration data for selection.')

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
    params = configure_trainable(model, a.freeze_encoder, a.encoder_last_layers)
    encoder_before = parameter_fingerprint(model, encoder_only=True)
    print(json.dumps({'actual_device':str(agent.device), 'trainable_parameters':sum(p.numel() for p in params),
                      'trainable_encoder_parameters':sum(p.numel() for p in model.encoder.parameters() if p.requires_grad)}),flush=True)
    lr = a.lr or (1e-4 if a.freeze_encoder else 2e-5)
    encoder_lr = a.encoder_lr or lr
    encoder_params = [p for p in model.encoder.parameters() if p.requires_grad]
    encoder_ids = {id(p) for p in encoder_params}
    head_params = [p for p in params if id(p) not in encoder_ids]
    parameter_groups = [{'params':head_params,'lr':lr}]
    if encoder_params: parameter_groups.append({'params':encoder_params,'lr':encoder_lr})
    opt = torch.optim.AdamW(parameter_groups, lr=lr, weight_decay=0.01)
    epoch_draws = a.steps_per_epoch*a.batch_states if a.steps_per_epoch else None
    total = a.max_steps or a.epochs * (a.steps_per_epoch or math.ceil(len(tr) / a.batch_states))
    sched = torch.optim.lr_scheduler.LambdaLR(opt, lambda s: min(1.0, (s + 1) / max(1, total // 10)) * max(0.0, 1 - s / max(1, total)))

    macro = a.selection_metric == 'macro-loss'
    choices=[]
    l0, acc0 = evaluate_loss(agent, cal, a.freeze_encoder, macro=macro, objective=a.objective, predictions=choices)
    select0, plan0 = plan_selection(cal_rows, choices, l0) if a.selection_metric == 'plan' else ((l0,), {})
    print(f"before: cal loss {l0:.4f} acc {acc0:.3f}", flush=True)
    best, step, hist = (select0, None), 0, [{"step": 0, "cal_loss": l0, "cal_acc": acc0, **plan0}]
    data_manifest = (pathlib.Path(a.data) / "MANIFEST.json")
    meta = {"base": a.base, "subfolder": a.subfolder, "mode": a.mode, "tasks": tasks, "freeze_encoder": a.freeze_encoder,
            'encoder_last_layers': a.encoder_last_layers,
            'trainable_parameters': sum(p.numel() for p in params), 'encoder_before': encoder_before,
            'actual_device': str(agent.device),
            "lr": lr, 'encoder_lr':encoder_lr if encoder_params else None,
            'balanced_labels':a.balanced_labels,'steps_per_epoch':a.steps_per_epoch,'selection_metric':a.selection_metric,
            'objective':a.objective,
            "epochs": a.epochs, "seed": a.seed, "repo_sha": git_sha(),
            "question_set": hashlib.sha256(json.dumps(question_sets, sort_keys=True).encode()).hexdigest()[:16] if question_sets else question_set_hash(),
            "data_manifest_sha": hashlib.sha256(data_manifest.read_bytes()).hexdigest()[:16] if data_manifest.exists() else None,
            "calibrated": False, 'selection_split': a.selection_split,
            'question_definitions_sha256': hashlib.sha256(a.questions.read_bytes()).hexdigest() if a.questions else None,
            'data_sha256': {s: hashlib.sha256((pathlib.Path(a.data)/f'{s}.jsonl').read_bytes()).hexdigest() for s in ['train', a.selection_split]},
            'training_source_sha256': hashlib.sha256(TRAINER_SOURCE).hexdigest()}
    peak_mps_allocated = 0
    optimizer_seconds = 0.; evaluation_seconds = 0.; checkpoint_seconds = 0.
    setup_and_initial_selection_seconds = time.perf_counter()-run_start
    from collections import Counter
    draw_counts=Counter(); unique_drawn=set()
    t0 = time.time()
    for ep in range(a.epochs):
        model.train()
        if a.freeze_encoder: model.encoder.eval()
        for grp in batches(tr, a.batch_states, rng, a.balanced_labels, epoch_draws):
            compute_start = time.perf_counter()
            b = collate_items(grp, agent.tok.pad_token_id)
            for group in grp:
                for item in group:
                    draw_counts[str(item['label'])]+=1; unique_drawn.add(item['row'])
            loss, acc = step_loss(model, b, agent.device, a.freeze_encoder, objective=a.objective)
            opt.zero_grad(); loss.backward(); torch.nn.utils.clip_grad_norm_(params, 1.0); opt.step(); sched.step(); step += 1
            if str(agent.device).startswith('mps'):
                torch.mps.synchronize()
                peak_mps_allocated=max(peak_mps_allocated,torch.mps.current_allocated_memory())
            optimizer_seconds += time.perf_counter()-compute_start
            if step % 50 == 0:
                print(f"  step {step}/{total} loss {loss.item():.4f} acc {acc:.3f} {time.time() - t0:.0f}s", flush=True)
            if a.max_steps and step >= a.max_steps: break
            if a.max_seconds and time.time() - t0 >= a.max_seconds: break
        evaluation_start = time.perf_counter()
        choices=[]
        lc, ac = evaluate_loss(agent, cal, a.freeze_encoder, macro=macro, objective=a.objective, predictions=choices)
        selection, plan = plan_selection(cal_rows, choices, lc) if a.selection_metric == 'plan' else ((lc,), {})
        train_stats = {}
        if a.evaluate_train:
            tl, ta = evaluate_loss(agent, tr, a.freeze_encoder, objective=a.objective)
            train_stats = {'train_loss': tl, 'train_accuracy': ta}
        evaluation_seconds += time.perf_counter()-evaluation_start
        hist.append({"step": step, "epoch": ep + 1, "cal_loss": lc, "cal_acc": ac, **plan, **train_stats})
        print(json.dumps(hist[-1]), flush=True)
        if a.save_epoch_deltas:
            from safetensors.torch import save_file
            delta_dir=pathlib.Path(a.out)/'epoch-deltas';delta_dir.mkdir(parents=True,exist_ok=True)
            sd={k:p.detach().cpu().contiguous() for k,p in model.named_parameters() if p.requires_grad}
            save_file(sd,str(delta_dir/f'epoch-{ep+1}.safetensors'))
        if selection < best[0]:
            checkpoint_start = time.perf_counter()
            best = (selection, ep + 1); save(agent, base_dir, a.out, {**meta, "selected_epoch": ep + 1, "history": hist,
                'completed_steps': step, 'training_loop_seconds': round(time.time()-t0, 3),
                'encoder_after': parameter_fingerprint(model, encoder_only=True),
                'peak_process_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024),
                'peak_mps_allocated_bytes_sampled_after_steps':peak_mps_allocated or None})
            checkpoint_seconds += time.perf_counter()-checkpoint_start
        if a.max_steps and step >= a.max_steps: break
        if a.max_seconds and time.time() - t0 >= a.max_seconds: break
    run_out=pathlib.Path(a.out);run_out.mkdir(parents=True,exist_ok=True)
    (run_out/'TRAINER.py.txt').write_bytes(TRAINER_SOURCE)
    (run_out/'TRAINING-RUN.json').write_text(json.dumps({
        'training_source_sha256':hashlib.sha256(TRAINER_SOURCE).hexdigest(),
        'actual_device':str(agent.device),'total_completed_steps':step,'requested_epochs':a.epochs,
        'selected_epoch':best[1], 'selection_split':a.selection_split,
        'selection_metric':a.selection_metric,'balanced_labels':a.balanced_labels,
        'objective':a.objective,
        'head_learning_rate':lr,'encoder_learning_rate':encoder_lr if encoder_params else None,
        'label_draw_counts':dict(draw_counts),'unique_training_assessments_seen':len(unique_drawn),
        'training_manifest_sha256':hashlib.sha256(data_manifest.read_bytes()).hexdigest() if data_manifest.exists() else None,
        'history':hist,
        'setup_and_initial_selection_seconds':setup_and_initial_selection_seconds,
        'optimizer_compute_seconds':optimizer_seconds,'epoch_selection_seconds':evaluation_seconds,
        'checkpoint_fingerprint_and_save_seconds':checkpoint_seconds,
        'full_run_elapsed_seconds':time.perf_counter()-run_start,
        'peak_process_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024),
        'peak_mps_allocated_bytes_sampled_after_steps':peak_mps_allocated or None,
        'cost':{'api_usd':0,'hardware_energy_and_operator_cost_usd':None},
        'budget_scope':'Wall time between training start and step checks includes prior epoch selection and saves'
    },indent=2)+'\n')
    if best[1] is None:
        print("no epoch beat the base model on cal log-loss; nothing saved as a variant", flush=True)
        (pathlib.Path(a.out)).mkdir(parents=True, exist_ok=True)
        (pathlib.Path(a.out) / "NOT_SAVED.json").write_text(json.dumps({**meta, "history": hist}, indent=2))
        return 1
    print(f"saved epoch {best[1]} ({a.selection_split} selection {best[0]}) -> {a.out}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
