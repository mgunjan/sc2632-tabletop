# Evidence-linked local decision experiments

This experiment evaluates complete Kubernetes guardrail proposals, missing evidence
and owner handoffs. It is research tooling, not a deployment authorization system.
See [the frozen initial protocol](PROTOCOL.md) and `experiments/system1-2026-10-18/PUBLICATION.md`.

The October 19 balanced-source experiment (`experiments/system1-2026-10-19/README.md`)
adds reproducible source-context curation, equal per-label sampling, a matched
reference-removal ablation, six actual GPU retrains and a frozen before/after
comparison with the saved Claude results. It retains the negative matched-budget
pilot, a separate full-pass convergence check, the dataset and diagnostic evidence.
The three-full-pass selected checkpoint also matched 0/15 complete plans; no
useful complete-plan improvement was established by this retraining study.

For the complete-case pipeline and native optimization repairs, see
`experiments/system1-2026-10-19/repair-v1/PROTOCOL.md`
and `experiments/system1-2026-10-19/optimization-v1/native-training-v5/COMPARISON.md`.
The earlier balanced recipe remains available to reproduce its negative result.
`repair_curriculum.py` retains every original training row, assesses all ten
candidates per case, removes reference-description aliases and adds explicit
negation and compound requests. `run_repair.py` uses natural sampling, records
training fit, selects on development complete plans and retains each epoch's
trainable tensors. `train_coverage_laya.py` caches full float32 encoder token
sequences, presents all 1,310 rows once per epoch and applies normalized
inverse-frequency class weights: it repairs training fit to 99.69% accuracy
(>=99.66% per-class recall), while out-of-sample test plans remain 2/15 (17/23
required candidates omitted). The separate `hierarchical.py` baseline learns intent
relevance before evidence sufficiency; it improved from 4/15 to 6/15, while saved
Claude scored 10/15 with zero omissions or wrong recommendations. These are
examined authored regressions, not evidence that any local learner is production qualified.

```sh
python datasets/decisions/repair_curriculum.py \
  --frozen output/decision-data-new --out output/decision-repaired-new
python datasets/decisions/run_repair.py \
  --data output/decision-repaired-new \
  --base .session-build/laya-control-training/checkpoint-v2 \
  --weights output/decision-repaired-weights-new --out output/decision-repaired-run-new
```

These operations train locally and reuse the original calibration/test task. They
do not make new Claude calls. Keep new labels provisional until independent review.

The October 18 authored corpus has **84 logical cases in 28 scenario families**.
Each case produces ten candidate-control assessments: **840 dependent decisions**,
not 840 independent incidents. Only 36 cases / 360 assessments belong to training.
The 2,092 upstream description alignments did not train the October 18 candidates.
The later source-context pilot reused selected descriptions as background; the
complete-case repair removes that background. The larger reference collection remains under
[`../comprehensive/`](../comprehensive/README.md).

Every input contains only operator intent, available evidence, operational
constraints and the candidate's actual catalog coverage. Labels, rationale, source
paths and split identity remain outside model-visible state. `recommend` proposes
a supported control; `review` identifies unresolved context; `handoff` routes a
non-rendered requirement to its owner; `exclude` omits a candidate that does not
address the request. Every whole-case score checks all ten candidates.

## Reproduce a new run

Use an isolated Python 3.12 environment with `laya_variant/requirements-training.txt`,
PyYAML 6.0.3 and jsonschema 4.26.0. The measured environment is recorded alongside
the experiment evidence. On macOS the sandbox may hide Metal and Docker; the
recorded training explicitly verified real `mps` placement outside that sandbox.

```sh
python datasets/decisions/build.py \
  --out output/decision-data-new \
  --corpus .session-build/comprehensive-data-20261017/corpus-published
python datasets/decisions/audit.py \
  --data output/decision-data-new --out output/decision-audit-new.json
python datasets/decisions/test_decisions.py
python datasets/decisions/test_benchmark.py
```

Omit `--corpus` to reproduce the authored task files without imported reference
content. Task-file hashes remain the same; the enclosing manifest differs because
it records whether the separate source-alignment reference file was included.

Run `verify_controls.py --out output/decision-engine-new` with local Docker and the
pinned engine paths in the comprehensive runtime lock. It renders the compiler's
policies and runs existing suites and a privilege boundary contract in read-only,
network-disabled containers. A passing engine comparison does not validate an
incident response label or demonstrate live containment.

The initial paired training starts from the existing October 13 checkpoint. It is
already head-tuned; do not call it an untouched pretrained model. Set `--base` to
that local checkpoint and preserve its identity:

```sh
python laya_variant/train.py \
  --base .session-build/laya-control-training/checkpoint-v2 \
  --data output/decision-data-new \
  --questions output/decision-data-new/questions.json --tasks guardrail_candidate \
  --out output/decision-head-new --freeze-encoder \
  --epochs 3 --batch-states 4 --lr 0.0001 --seed 18 \
  --selection-split dev --max-seconds 900 --device mps

python laya_variant/train.py \
  --base .session-build/laya-control-training/checkpoint-v2 \
  --data output/decision-data-new \
  --questions output/decision-data-new/questions.json --tasks guardrail_candidate \
  --out output/decision-adapted-new --encoder-last-layers 2 \
  --epochs 3 --batch-states 4 --lr 0.00002 --seed 18 \
  --selection-split dev --max-seconds 900 --device mps

python datasets/decisions/benchmark.py \
  --data output/decision-data-new --out output/decision-head-report-new \
  --candidate laya --model output/decision-head-new --device mps
```

The benchmark fits temperatures and selects routing thresholds using `cal` only,
then opens `test_authored`. It measures missed requirements and wrong recommendations
as well as pooled accuracy. Rejecting every candidate can score well on pooled
accuracy because most candidate rows are intentionally irrelevant.

Baseline candidate choices are `majority`, `rules`, `logistic`, `candidate-lr`,
`retrieval` and `context-retrieval`. The latter two conditioned variants address
the relationship between the supplied candidate and intent; plain concatenated
TF-IDF has no explicit candidate/text interactions. These variants were added
during the authored-test feasibility study and are not an untouched independent
comparison. Raw predictions and source hashes preserve each development run.

An installed Ollama model can run with `--candidate ollama --model qwen3:4b-instruct`.
The script does not download models. Its generated probabilities are self-estimates,
not token probabilities. Keep failed and truncated responses. `responses-live.jsonl`
preserves completed requests if the process is interrupted. Check the existing
process handle before resuming; do not restart an apparently slow run blindly.

`run_comparison.py` runs the local candidates sequentially, keeps complete process
times and generates a report only after verifying identical assessment identities,
labels, source snapshots and dataset versions across the completed candidates.

The Claude adapter in `hosted.py` uses the same assessment/calibration harness and
keeps usage-based price estimates separately from an invoice. Its offline tests
are in `test_hosted.py`. The user specifically approved the frozen 301-request
export and an $8 usage cap on October 18; the exact outbound scope and authorization (`experiments/system1-2026-10-18/hosted-export-preview/EXPORT-REVIEW.md`)
are retained. That approval covers this run, not additional exports or paid reruns.
The model's generated probability estimates are not certified or token
probabilities. No credential or workspace identifier is stored in reports.

`compare_hosted.py` audits the completed run offline against the approved export,
usage receipts and exactly paired local calibration/test predictions. It recalculates
metrics, calibration and routing, checks source snapshots, and creates the combined
comparison with cost and latency. It makes no API calls:

```sh
python datasets/decisions/compare_hosted.py \
  --local experiments/system1-2026-10-18/verified-local \
  --hosted experiments/system1-2026-10-18/claude-opus-v1 \
  --preview experiments/system1-2026-10-18/hosted-export-preview \
  --approval experiments/system1-2026-10-18/hosted-export-preview/AUTHORIZATION.json \
  --out output/decision-hosted-comparison-new
python datasets/decisions/test_compare_hosted.py
```

## Independent review

```sh
python datasets/decisions/review.py export \
  --data output/decision-data-new --out output/decision-blind-review-new
python datasets/decisions/review.py compare \
  --data output/decision-data-new \
  --reviewer-a path/to/completed-review-a.jsonl \
  --reviewer-b path/to/completed-review-b.jsonl \
  --out output/decision-review-comparison-new
python datasets/decisions/score_review.py \
  --data output/decision-data-new --review output/decision-review-comparison-new \
  --run output/decision-head-report-new --out output/decision-reviewed-score-new.json
```

Reviewers work separately without proposed answers, declare non-authorship, identify
themselves, label all controls and give rationales. Blank forms, altered case inputs
and repeated reviewer identities are rejected. Disagreements require human
adjudication; this tool does not turn either opinion into consensus automatically.
Reviewed labels rescore the exact frozen predictions with their original routing
threshold. They never rewrite a model response or tune to the new test labels.

The reviewed authored stress test still does not establish generalization to real
enterprise incidents or independently authored inputs. Those remain required for
the publication objective. No industry-leading or production-qualified model is
established by the current experiment.
