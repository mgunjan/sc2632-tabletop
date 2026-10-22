# Local guardrail decision experiment v1

Status: protocol and authored development corpus, October 18, 2026. This is a new
experiment. The October 13 pilot remains an examined regression set. No result
from this experiment establishes industry leadership or production qualification.

## Task and authority

Given an operator's intent, evidence available at decision time, operational
constraints and one entry in the versioned control catalog, return one disposition:

- `recommend`: include the requested control in a reviewable proposal, subject to
  its documented limits. This never authorizes deployment or establishes containment.
- `review`: the control may be relevant, but missing evidence, conflicting
  requirements or unresolved operational dependencies prevent a definite proposal.
- `handoff`: the requested requirement belongs to the catalog's identity,
  governance or unsupported-requirement owner rather than a rendered admission policy.
- `exclude`: the candidate is not requested, is explicitly out of scope, or does
  not address the requirement. A benign event alone does not request new controls.

Score every catalog entry for the same case. Aggregate the ten dispositions into
a plan, preserving all requested controls and required handoffs. Selecting one
correct control does not compensate for omitting another. This experiment does
not replace the existing compiler, authorize exceptions, or deploy a policy.

The model reads prose and a capability specification. Authentication, approval
validity, numeric expiry enforcement and actual policy execution remain deterministic
checks. Cases about those facts test recognition of the required review/handoff,
not delegated authority to approve an exception.

## Data and label provenance

`scenarios.json` contains individually authored scenario families with meaningful
counterfactuals, including compound requests, negation, authorized activity,
ambiguous evidence, exception requests and recovery. No namespace/name substitutions
are counted as new cases. They are assistant-authored hypotheses, not independently
reviewed enterprise decisions. The targets remain physically separate from inputs.

The comprehensive upstream corpus is a linked reference source, not automatically
relabelled training data. `source-alignments.jsonl` preserves original description
alignments for a separate retrieval task, with source family, license and immutable
revision. No source description is silently converted into a containment label.

All siblings and counterfactual descendants stay in one split. Exact duplicate
inputs are rejected. Normalized text overlap and source family overlap are audited.
Shared control capabilities and task instructions intentionally appear in every split.
Semantic near-duplicate and label reviews remain explicit human review items.

Training uses `train`; checkpoint selection uses `dev`; temperature fitting and
routing-threshold selection use `cal`. `test_authored` is an authored stress test,
not independent evaluation. A separate blinded review export contains no proposed
answers. Independent reviewers must identify themselves, disclose authorship,
record labels separately, and resolve disagreements before a versioned independent
test can be scored. An absent review produces an INCOMPLETE qualification result.

## Frozen comparison

Compare majority, transparent keyword rules, TF-IDF nearest-neighbour retrieval,
TF-IDF logistic regression, the existing local Laya checkpoint, a head-only
candidate, a candidate adapting the final encoder blocks, and strong language-model
baselines. Every candidate receives exactly the same case evidence and catalog
coverage. Hosted failures and invalid answers count as failures, not negative labels.
Record model identity, prompt/input hashes and actual usage. Replayed responses must
match exact input identities. No test-set search for a winning model or threshold.

Use the same starting weights for head-only and adapted candidates. Record the
starting checkpoint's prior training history and full weight/config hashes. The
available October 13 checkpoint has already received head-only synthetic training;
do not describe it as an untouched pretrained base. Adaptation must prove that
encoder tensors changed; a command-line flag is not sufficient evidence.

Select checkpoints on development proper-scoring loss, report development accuracy,
and retain failures. Use a separate calibration fit for each candidate. Choose any
confidence routing rule on calibration cases only and retain full coverage/risk
curves. Thresholds are exploratory until incident/control owners ratify risk limits.

Initial run configuration, fixed before scoring the authored test: seed 18, three
epochs, four candidate states per optimizer step, head-only learning rate 0.0001,
final-two-encoder-block adaptation learning rate 0.00002, AdamW weight decay 0.01.
Use the full training split with no test-selected subset. A 900-second training-loop
budget per candidate may stop the run; record actual completed steps and keep
selection/calibration timings separate. This bounded first comparison is a pipeline
and feasibility study, not a comprehensive hyperparameter search.

## Measurements and completion

Report candidate-level and whole-case results: required-control recall, exact plan
match, missed controls, extra recommendations, wrong recommendations retained by
confidence routing, correct review/handoff decisions, calibration and invalid/missing
responses. Bootstrap by scenario family, not candidate rows. Show uncertainty and
per-category results; do not pool dependent decisions as independent incidents.

Record setup/load, training, calibration, warm p50/p95 decision time, full ten-control
case time, process peak RSS, accelerator allocation where measurable, model size,
hardware/software identities and actual API usage. Report price per attempted case
and correctly accepted case. API charge can be zero while local hardware, energy,
operator time and review are unpriced. Missing costs are null, never zero.

Completion requires executable policy receipts tied to the candidate control
implementations, both trained candidates, calibrated comparisons, independent
scenario review, strong-model baselines and an audited operational report. Authored
test results alone leave the original goal incomplete.
