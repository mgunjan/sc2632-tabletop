# A Laya variant for agentic-guardrail decisions

A specialised, calibrated version of Laya that answers three kinds of questions:

- **Intent:** what a security intent asks for.
- **Exceptions:** whether an exception request holds up. These are often written *by an agent*.
- **Inputs:** whether the text an agent read is trying to steer it.

This directory contains dataset, training, calibration and evaluation tooling. A separate control-selection head was trained locally on the real Laya weights on October 13; it did not improve the 33-decision regression accuracy and did not qualify for delegation. That run does not establish a trained, qualified variant for the triage questions below. See [the measured pilot](../submission/2026-10-13/REVIEW.md).

## Why a variant, not the base model

We read the laya 0.3.12 source and README (`pip download laya==0.3.12`). The findings below changed the plan:

1. **The base checkpoints are near chance on typed decisions zero-shot.** Upstream measured this:
   - `laya` scores 0.362 and `laya-multilingual` scores 0.352.
   - Random guessing scores 0.318 and the majority class scores 0.461.
   - The 0.766 headline comes from `laya-typed-decisions`, which was fine-tuned on that benchmark's own training split.
   - Upstream says it plainly: *"Laya is a fast base to specialise, not a zero-shot decision engine."*

   So the uncalibrated "second opinion" in `generator/classify.py` was, until now, likely noise with a confidence number attached.
2. **`noul` can answer from its option labels instead of the text on the English checkpoint** (upstream #156). It returns a confident "no" on clearly positive input. `classify.py` asked every yes/no question as a bare `noul`. It now defaults to the A/B-label override, and `evaluate.py` compares all three renderings (`noul`, `labels_ab`, `choice_ab`) so the choice is measured, not assumed.
3. **`confidence` is not the calibrated number.** For `choice` and `score` questions, laya's `confidence` is normalised entropy. The calibrated quantity is `answer_confidence` (max p). Upstream's own gating example uses the wrong one. We gate and measure calibration error on `answer_confidence` only.
4. **`action.act_probability` carries no signal** (upstream #185, AUROC 0.30). We never read it.
5. **The right base to start from is `convaiinnovations/laya` with `subfolder="typed-decisions"`:**
   - It has 1024-token context. The English checkpoint has 512, and an exception plus its incident plus the agent's inputs does not fit in 512.
   - It is already tuned on "security incidents" and "agent-trace observability" workflows.

## Design rules

- **The model only answers questions that need language understanding.** Anything a field lookup answers is a rule in `classify.py`, not a model question. That includes "is the author verified?", "is there a linked ticket?" and "is an approval recorded?". A model that learns to read a boolean field is a worse rule.
- **The model's answers feed a rule you can read; they never gate anything.** `classify.triage()` turns typed answers into routine / human-review / refuse-under-Q1. Admission never waits on the model.
- **One definition of every question** (`questions.py`). It is used for labels, training, calibration and inference. Its hash is stamped into every trained checkpoint.
- **Training and inference encode identically.** Training rows go through laya's own `Agent._encode_state`. `test_pipeline.py` checks that our probabilities equal `laya.predict()` to 2e-3, in all three renderings.

## The questions

| Set | Question | Why it needs a model |
|---|---|---|
| intent | `asks_network`, `asks_identity`, `asks_workload_security`, `asks_supply_chain`, `asks_agent_behaviour`, `asks_evidence`, `asks_runtime_detection`, `admission_sufficient` | Intents are free text; "put a fence around ledger" asks for network policy without saying so |
| exception | `concrete_need`, `owner_accountable`, `scope`, `ttl_fit`, `touches_suspect` | Whether a reason is a real dependency, and whether a TTL fits it, is judgement over prose |
| exception | **`authority_unverified`**, **`echoes_agent_input`** | The agent's exception reasons. "The IC OK'd this on the bridge" with no recorded approval, or a reason that repeats the injected ticket's wording. This is the case typed classifiers are best at |
| input | `prompt_injection`, `jailbreak`, `requests_sensitive_data`, `requests_privilege_change`, `requests_prod_change` | Instructions aimed at the AI versus a customer's request |

## Data (`build_dataset.py`)

Labels are **by construction**. Every example is assembled from parts whose meaning is known, so the label is a fact about how it was built, not a teacher model's opinion.

| Split | What | Used for |
|---|---|---|
| `train` / `cal` / `test_iid` | Constructed, training templates and entity names | Training; confidence calibration (`cal`); in-distribution check. Use separate development data for model selection in the next study |
| `test_ood` | Constructed from **held-out templates AND held-out entity names** | "Did it learn the task or the strings?" |
| `gold` | Hand-written, realistic phrasing, no template wording | "Is it useful on text that looks like real life?" |
| `scenario` | The session's real tickets, Slack messages, intents and exceptions | The demo. **Never trained on.** A regression test |

**The lesson from the first real run** is in `BASELINES.md`: ten minutes of keyword regexes, no model. On constructed `test_ood` they average **0.91** accuracy, against **0.64** for majority-class. On `gold` they average **0.85**. Constructed data is keyword-separable because templates are.

So beating keywords on constructed splits proves nothing. The questions where keywords *fail* on realistic text are where a model has to earn its place:

- `concrete_need` (0.58)
- `prompt_injection` (0.67)
- `requests_privilege_change` (0.73)
- `authority_unverified` (0.75)
- `echoes_agent_input` (0.75)

**Honesty about `gold`.** The 42 rows shipped here were written by Claude (the AI assistant that built this repo). That is the same author as the templates and the keyword rules, so they are **not an independent test**. They are marked `"source": "claude-authored"`. Before any number goes on a slide:

- have two people who did not write templates label 30+ items per task, without looking at each other's labels;
- put those items in `gold/independent-*.jsonl`;
- report their agreement with each other next to the model's.

## Pipeline

```bash
pip install laya torch transformers              # any machine
python3 laya_variant/build_dataset.py --n 6000 --with-dev   # use a fresh --out to preserve prior evidence

# 0. Baselines and zero-shot bases. Is a variant even needed?
python3 laya_variant/evaluate.py --out runs/zero-shot \
  --model english=convaiinnovations/laya \
  --model typed=convaiinnovations/laya:typed-decisions \
  --model typed-choice=convaiinnovations/laya:typed-decisions --mode choice_ab

# 1. Head-only fine-tune: encoder frozen, decision head trains. Apple-silicon GPU (MPS) is fine.
python3 laya_variant/train.py --base convaiinnovations/laya --subfolder typed-decisions \
  --out runs/v1-head --freeze-encoder --epochs 3

# 2. Calibrate on the cal split (never train/test), in place
python3 laya_variant/calibrate.py --model runs/v1-head

# 3. Evaluate against the baselines and the zero-shot bases
python3 laya_variant/evaluate.py --out runs/v1-report \
  --model typed=convaiinnovations/laya:typed-decisions --model v1=runs/v1-head \
  --splits test_iid,test_ood,gold,scenario

# 4. Use it
python3 generator/classify.py --scenario b --model runs/v1-head
```

New training defaults to checkpoint selection on `dev`, leaving `cal` for
temperature fitting. The legacy builder's `--with-dev` flag reserves development
rows from its former training allocation. Omitting it preserves the historical
split generation for reproduction; it does not produce a separate development
file. Previously recorded datasets and scores have not been rewritten.

**Full fine-tune** (drop `--freeze-encoder`) wants a CUDA GPU. Upstream's reference point: Kaggle's free 2×T4 takes 4–5 h for 4 epochs over ~30k question rows. The default build gives about 4,200 training states and about 28k question rows, so budget a similar evening. `train.py` optimises laya's own `proper_reward`, a strictly proper scoring rule, directly. Upstream's notebook reaches the same reward through GRPO-style policy gradient. Use theirs if you want the RL path. For single-step decisions the deterministic gradient is simpler and should not be worse, but that is untested here.

## The acceptance gate (one gate; before anything reaches the room)

Pre-registered on Sep 24, before any model was scored, and fixed in code (`evaluate.GATE_QUESTIONS`): the five
yes/no questions keyword rules handle worst, `authority_unverified`, `concrete_need`, `echoes_agent_input`,
`prompt_injection`, `requests_privilege_change`, pooled on `gold`. A candidate (a Laya variant, or the local LLM)
goes on a slide only if:

1. it beats the **best baseline**, not just keywords, with complete answer coverage and identical item identities;
2. exploratory exact McNemar p < 0.05 **and** the state-bootstrap 95% interval of the gap is above zero (questions within a state are correlated);
3. calibration error (ECE on its confidence) is <= 0.10;
4. every `scenario` row is right, or the miss is shown on stage.

The 66 question decisions come from only 27 states. There is no universal gap below which a paired result is noise;
the discordant predictions and state dependence matter. The gold set is Claude-authored, and the best baseline is
selected on the scored split. A PASS is provisional until independent labels and a separate validation set exist.
The October 13 protocol revision adds explicit failure scoring, identity pairing and a state bootstrap; it must not
be described as part of the original pre-registration.

Current verification: [October 13 report](../submission/2026-10-13/classical-verification-final/REPORT.md).
The original selected-text LR reproduces 0.803; the new full-state LR scores 0.818. Legacy exception features omit
workload, TTL and incident context, so their poor scope accuracy does not establish that a language model is required.
The September Qwen recording matches 45/51 current states, including 39/42 gold states. Its complete current gate is
**INCOMPLETE**, not evidence that one model family won. Missing responses no longer earn a negative-label match.

## Where things ran

| | Where | Status |
|---|---|---|
| Dataset, baselines, all tests | Cloud workspace (no Hugging Face access) | **Ran.** `test_pipeline.py`: 7/7 on a tiny random checkpoint in laya's format, through laya's real `Agent` |
| Control-selection base, head training, calibration and evaluation on real weights | Local Apple-silicon Mac, cached Laya typed-decisions weights | **Ran October 13.** See the completed control-selection pilot below; this does not verify a trained triage variant |

`make_tiny_checkpoint.py` writes a random 64-dimensional model in laya's on-disk format, so all of this is testable without the weights. Its answers are noise by design. Never quote a number from it.

## Running the gate, with the local LLM as a baseline

`evaluate.py` runs every predictor in parallel on the same rows: majority, keywords, tf-idf + logistic
regression, tf-idf cosine kNN (`baselines.py`), any Laya checkpoint (`--model`), and the local model you run
through Ollama, either directly (`--ollama-model qwen3:4b-instruct`) or from a recording of a real run on another
machine (`--ollama-recording laya_variant/recordings/<file>.jsonl`, matched to rows by a hash of the exact state).
The LLM's confidence is its own stated number: the report measures its calibration rather than trusting it.

## OpenAI structured decisions

The dedicated OpenAI Decisions adapter is separate from the existing OpenAI Responses structured-output client.
Its current beta model is `gpt-6-luna`, through `POST /v1/decisions`. It preserves predicate probabilities, choice
distributions and the separate choice-confidence signal. See the [official guide](https://developers.openai.com/api/docs/guides/decisions).
Offline adapter tests do not establish account access or live model performance.

```sh
# Paid API inference: provide a private key file; labels never enter the request.
python laya_variant/evaluate.py --splits gold,scenario \
  --openai-decisions-model gpt-6-luna --openai-env-file /path/to/private.env \
  --out runs/openai-decisions-first

# Later, score the exact recorded states/questions without another API call.
python laya_variant/evaluate.py --splits gold,scenario \
  --openai-decisions-recording runs/openai-decisions-first/openai-decisions-gpt-6-luna-recording.jsonl \
  --out runs/openai-decisions-replay
```

The frozen policy-agent pilot also supports `run_provider.py --provider openai-decisions`. Token-based cost estimates
use the October 13 input-only list price and mark missing usage unknown. No authenticated OpenAI result is recorded yet.

## Training for control selection

`build_control_dataset.py` prepares a separate curriculum for the actual ten-option policy-agent decision. This is
different from the triage question sets above. It keeps training, development, calibration and synthetic test templates
and entities separate, preserves inference option order, and checks against the unchanged policy benchmark.

```sh
python laya_variant/build_control_dataset.py --out runs/control-data
python laya_variant/train.py --base /path/to/cached/laya-checkpoint --data runs/control-data \
  --questions runs/control-data/questions.json --tasks policy_control --selection-split dev \
  --freeze-encoder --epochs 1 --seed 13 --lr 0.0001 --batch-states 4 \
  --max-steps 120 --max-seconds 600 --device mps --out runs/control-model
python laya_variant/calibrate.py --model runs/control-model --data runs/control-data \
  --questions runs/control-data/questions.json --device mps
```

Follow the [training protocol](../submission/2026-10-13/TRAINING-PROTOCOL.md); independent real-world labels remain
required. Training can improve language decisions; it cannot repair an incomplete enforcement implementation.
The [control library](../controls/README.md) records those implementation boundaries and review obligations.

The [completed local training pilot](../submission/2026-10-13/REVIEW.md) did not improve the 33-case accuracy;
it increased accepted coverage and confident errors. Use it as measured evidence, not a qualified demo backend.
Install `requirements-training.txt` for the recorded Python 3.12 environment.

## Falco, Kyverno and the next dataset

The [comprehensive local corpus](../datasets/comprehensive/README.md) now contains 37,166 typed records from 19 pinned sources and 2,092 source-description alignments for retrieval experiments. Its cases, dependencies, recorded logs and response candidates remain distinct. This expansion does not train or qualify a new Laya checkpoint, and no examined workshop labels were changed.

The [upstream collection](../datasets/guardrails/README.md) is now downloaded and executed locally: 142 Kyverno
suites and 87 Falco capture/ruleset replays. Its catalog, resource/context examples, expectations and observations
are available for task-specific curriculum building. Local collection and exploratory fine-tuning do not require
a workshop rehearsal. Keep behavior-supervision labels distinct from incident-response decisions.

The [dataset design](../controls/DATASET-DESIGN.md) separates a versioned control library, executed behavioral
evidence and independently reviewed incident decisions. Upstream rules and policy tests are useful sources;
their existence does not label the appropriate response to an incident.

`build_evidence_corpus.py` assembles the existing 14 Falco audit cases and six Kyverno privilege resources into
a provenance-linked, regression-only seed. Expected results, actual observations and model-visible inputs
are separate. No row is eligible for training or independent evaluation, and no incident response labels are
invented. The seed retains test-only naming for reproduction and is not a ready-to-train model input format.

```sh
python laya_variant/build_evidence_corpus.py --out output/evidence-corpus
python laya_variant/test_evidence_corpus.py
```
