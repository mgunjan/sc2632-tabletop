"""
Shared plumbing for the Laya variant: load rows, encode them EXACTLY as laya's Agent does at
inference (same tokenizer, same `_encode_state`, same question rendering), attach targets, and
resolve a checkpoint directory. Train/inference skew is the classic way a fine-tune "works" in
the notebook and not in production; routing both through the Agent's own encoder prevents it.
"""
import json, os, pathlib, sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from questions import QUESTION_SETS, render, strip_private, label_keys  # noqa: E402


def load_rows(path, tasks=None):
    rows = [json.loads(l) for l in pathlib.Path(path).read_text().splitlines() if l.strip()]
    return [r for r in rows if tasks is None or r["task"] in tasks]


def load_agent(model, subfolder=None, device=None):
    import laya
    return laya.load(model, device=device, subfolder=subfolder)


def checkpoint_dir(model, subfolder=None):
    """Local directory holding rl_agent_config.json / model.safetensors / tokenizer / encoder."""
    if os.path.isdir(model):
        d = pathlib.Path(model)
    else:
        from huggingface_hub import snapshot_download
        d = pathlib.Path(snapshot_download(model, local_files_only=True))
    return d / subfolder if subfolder else d


def rendered(task, mode, question_sets=None):
    return render((question_sets or QUESTION_SETS)[task], mode)


def target_for(q_rendered, value):
    """One-hot target over the options in the order the model scores them."""
    keys = label_keys(q_rendered)
    if isinstance(value, bool):
        if q_rendered["type"] == "noul":
            key = "true" if value else "false"
        else:  # choice_ab
            key = "A" if value else "B"
    else:
        key = value
    return [1.0 if k == key else 0.0 for k in keys], keys.index(key)


def encode_rows(agent, rows, mode, qids=None, question_sets=None):
    """-> list of per-row item groups, each item carrying ids/markers/qtype/target/label + meta."""
    groups = []
    for r in rows:
        qs = rendered(r["task"], mode, question_sets)
        ids = [q for q in qs if (qids is None or q in qids) and q in r["labels"]]
        internal = {q: agent._to_internal(strip_private({q: qs[q]})[q]) for q in ids}
        items = agent._encode_state(r["state"], ids, internal)
        for q, it in zip(ids, items):
            tgt, lab = target_for(qs[q], r["labels"][q])
            it.update(target=tgt, label=lab, qid=q, row=r["id"], task=r["task"])
        groups.append(items)
    return groups
