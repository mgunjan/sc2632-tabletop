#!/usr/bin/env python3
"""
Write a TINY, RANDOMLY INITIALISED checkpoint in Laya's on-disk format, so the whole variant
pipeline (encode -> train -> calibrate -> evaluate -> classify.py) can be exercised in CI and in
sandboxes that cannot reach Hugging Face. Its answers are noise. It exists to prove the plumbing,
never to produce a number anyone should quote.

Layout written (same as a real Laya checkpoint):
  rl_agent_config.json   model.safetensors   tokenizer/   encoder/config.json
"""
import argparse, json, pathlib, sys

def build(out, data_glob=None, hidden=64, layers=2):
    import torch
    from safetensors.torch import save_file
    from tokenizers import Tokenizer, models, pre_tokenizers, trainers, processors
    from transformers import PreTrainedTokenizerFast, ModernBertConfig
    from laya.common import build_model

    out = pathlib.Path(out); (out / "tokenizer").mkdir(parents=True, exist_ok=True); (out / "encoder").mkdir(exist_ok=True)
    corpus = []
    here = pathlib.Path(__file__).resolve().parent
    import glob
    for f in (sorted(map(pathlib.Path, glob.glob(data_glob))) if data_glob else []):
        corpus += [l for l in f.read_text().splitlines()][:2000]
    corpus += [open(here / "questions.py").read()]
    specials = ["[PAD]", "[UNK]", "[CLS]", "[SEP]", "[MASK]"]
    tok = Tokenizer(models.WordPiece(unk_token="[UNK]"))
    tok.pre_tokenizer = pre_tokenizers.BertPreTokenizer()
    tok.train_from_iterator(corpus, trainers.WordPieceTrainer(vocab_size=4000, special_tokens=specials))
    tok.post_processor = processors.TemplateProcessing(single="[CLS] $A [SEP]", special_tokens=[("[CLS]", 2), ("[SEP]", 3)])
    fast = PreTrainedTokenizerFast(tokenizer_object=tok, pad_token="[PAD]", unk_token="[UNK]", cls_token="[CLS]",
                                   sep_token="[SEP]", mask_token="[MASK]")
    fast.save_pretrained(out / "tokenizer")

    ecfg = ModernBertConfig(vocab_size=fast.vocab_size, hidden_size=hidden, intermediate_size=hidden * 2,
                            num_hidden_layers=layers, num_attention_heads=2, max_position_embeddings=1024,
                            global_attn_every_n_layers=1, local_attention=128, pad_token_id=0, cls_token_id=2,
                            sep_token_id=3, bos_token_id=2, eos_token_id=3)
    ecfg.save_pretrained(out / "encoder")
    cfg = {"encoder": str(out / "encoder"), "head_layers": 1, "max_len": 1024, "head_max_len": 256,
           "temperature": [1.0, 1.0, 1.0], "act_costs": {"escalate": 1.0},
           "tiny_random_checkpoint": "NOT A MODEL: random weights for pipeline tests only"}
    (out / "rl_agent_config.json").write_text(json.dumps(cfg, indent=2))
    torch.manual_seed(0)
    m = build_model(cfg, encoder_dir=str(out / "encoder"), pretrained=False)
    sd = {k: v.contiguous() for k, v in m.state_dict().items()}
    save_file(sd, str(out / "model.safetensors"))
    return out

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--data-glob", default="laya_variant/data/train.jsonl")
    a = ap.parse_args()
    print(build(a.out, a.data_glob))
