# Laya — the independent second model

> **Read `laya_variant/README.md` first.** Reading laya 0.3.12's source changed the plan.
> The base checkpoints are near chance on typed decisions zero-shot (upstream's numbers), and
> the English checkpoint's `noul` can answer from its labels instead of the text (#156). So this
> page is how to *run* it. `laya_variant/` is how to make it worth running: a tuned, calibrated
> variant, with an acceptance gate before anything reaches a slide.

`generator/classify.py` runs [Laya](https://huggingface.co/convaiinnovations/laya)
(Apache-2.0; an open reproduction of TypeSafe's Jev approach — a 421M-parameter ModernBERT
encoder that answers typed yes/no and multiple-choice questions about text, with a
probability per answer). The policy generator never sees its output.

| Check | Reads | Asks | Shows up as |
|---|---|---|---|
| **intent** | the human's intent | does it ask for network / identity / workload-security / supply-chain / agent-behaviour controls? | "intent asks for X; nothing generated addresses it" — and the reverse |
| **exception** | each proposed exception + the incident | concrete need? accountable owner? scope? TTL fit? touches the suspect? | triage: `routine` / `human-review` / `refuse-under-Q1` |
| **input** (B, C) | the ticket / Slack message the agent consumed | instructions aimed at the AI? asks for secrets? asks for more access? | per-input flags, benign control alongside |

Nothing it says blocks anything. It's labelled **uncalibrated** everywhere: the model card says
it ships over-confident, and we have no labelled data to calibrate on. If it can't load, the
PR says "Not run" and why — it never guesses.

## Run it on your Mac (native terminal, not the Cowork sandbox)

The first run downloads ~1.7 GB of weights from Hugging Face.

```bash
cd ~/projects/agentic-k8s-guardrails
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt laya
# zero-shot, on the checkpoint already tuned for typed decisions (1024-token context)
python3 generator/classify.py --scenario b --subfolder typed-decisions
python3 generator/classify.py --scenario c --check input --subfolder typed-decisions
# the same with a variant you trained (laya_variant/README.md)
python3 generator/classify.py --scenario b --model runs/v1-head
for s in a b c; do python3 generator/generate.py --scenario $s --from-spec generator/spec-$s.json; done
sed -n '/## Independent check/,/## Rollout/p' output/b-*/PR.md
```

Wiring tests (stub model, no download): `python3 generator/test_classify.py`

## What to look for on the first real run

These are what we *hope* it says. Write down what it actually says — that's the result.

| Scenario | Hoped-for | Would mean |
|---|---|---|
| A intent | identity: asked, not generated | it caught clause 3 (the API-access gap) |
| B intent | agent behaviour: asked, not generated | it caught the tool-allow-list gap |
| B exception | `human-review`, "applies to the suspect workload" | it caught that the exception is for the compromised Pod |
| B input | injected ticket: `prompt_injection`, `requests_sensitive_data`; benign: none | the ticket would have been stopped at ingestion |
| C input | injected Slack: `prompt_injection`, `requests_privilege_change`; benign: none | same, for the ops agent |

If it misses most of these zero-shot, keep it in the repo as "here's how you'd wire a second
model" and drop it from the room. If it hits them, it earns one debrief line: *the
second model flagged it in N ms; how many tables did?*

## Known limits (from laya 0.3.12's README and source)

- Zero-shot on typed decisions is near chance on the base checkpoints: 0.36 against a 0.46
  majority baseline. `typed-decisions` reaches 0.77, but on its own benchmark's workflows.
- `noul` label-following (#156). `classify.py` defaults to the A/B-label override
  (`--mode labels_ab`); `laya_variant/evaluate.py` measures all three renderings.
- `confidence` on choice questions is normalised entropy, not the calibrated number. Use
  `answer_confidence`.
- `action.act_probability` carries no signal (#185). Unused here.
- Context: English checkpoint 512 tokens, `typed-decisions` 1024. An exception with its
  incident and the agent's inputs can exceed 512.
