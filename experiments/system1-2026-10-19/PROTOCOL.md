# Balanced source-context retraining: protocol frozen before model runs

Date: October 19, 2026. The user requested balanced training using the collected
data and a before/after comparison with the saved Claude results. This run makes
no hosted requests and does not extend the earlier API spending approval.

## Data and attribution

The source recipe considers the 2,092 collected description/implementation alignments.
It excludes metadata-only posture controls, duplicate descriptions and sources
outside this recipe's Apache-2.0/MIT scope. Topic selection chooses reference
contexts, not incident-response labels. Every selected row retains the source
record, source file/revision/content hashes, original terms and generation profile.

The new set has 1,024 candidate assessments, exactly 256 for each of `recommend`,
`review`, `handoff`, `exclude`. It retains original training examples and adds
bounded-request/evidence counterfactuals around the actual reference catalog.
The source excerpts are explicitly static context, never invented live telemetry
or deployment authorization. Labels are programmatic and pending expert review.
Forty request wordings and their evidence variants are reused across source
contexts; 1,024 rows do not mean 1,024 independent incidents or expert decisions.

The original development, calibration, authored test and question files are copied
byte-for-byte. No labels are revised to accommodate a model answer. The old test
has already been examined: it is a frozen regression comparison, not a newly blind
test or evidence of enterprise generalization. Independent labels and new incident
families remain necessary.

## Six runs with matched optimizer budgets

| Condition | Training inputs | Purpose |
|---|---|---|
| balanced | Original 360 assessments, equal per-label sampling | Isolate balancing and the revised training recipe from source expansion. |
| no-reference | New balanced rows with static excerpts removed; same IDs and labels | Measure the curated decision/evidence templates without source text. Duplicate template aliases remain explicit. |
| source | New balanced rows including source reference excerpts | Measure the additional effect of collected source text. |

Run each condition with (a) encoder frozen and (b) final two encoder blocks plus
final normalization adapted. All start from the same already head-tuned October 13
checkpoint. All use seed 19, batch size four, three epochs, 90 steps per epoch:
**270 optimizer steps and 1,080 assessment draws per run**, 270 draws per disposition.
Sampling without replacement within each class cycles only when a class is exhausted;
repeated draws never count as new examples. The head learning rate is 1e-4 for all
runs. Adapted encoder parameters use 2e-5. The original October 18 recipes remain
historical baselines and differed in learning rate and selection recipe.

Use stable log-softmax cross-entropy for this supervised four-choice task. This
avoids the default proper-reward implementation's log floor flattening the log-score
gradient for an extremely underweighted target class. The original training
objective remains available and unchanged by default; all six new conditions use
the same revised objective, so the balanced control also controls for this recipe change.
Select each checkpoint on original `dev` macro-averaged cross-entropy,
so the dominant exclusion class does not overwhelm selection. Use the same dev
set for all conditions; do not select by calibration/test performance. Record
initial/epoch dev losses, actual draws/unique inputs, source snapshots, parameter
fingerprints, selected checkpoint, GPU placement, full elapsed time and memory.
A 900-second training-loop limit per run is a resource guard; report any incomplete
step budget or failure rather than claiming a matched completed run.

## Frozen evaluation

Finish all six training runs before running the evaluation batch. Reuse the
unchanged October 18 benchmark code, fit each candidate's temperature and routing
threshold on original `cal`, then score original `test_authored`. Compare exact
paired states, case/family IDs and labels against saved starting/head/adapted,
rules/retrieval and Claude predictions. Different training manifests are expected;
the held-out bytes, typed question and scoring source must match exactly.

Primary results: complete plans, omitted required controls, unsupported
recommendations, correct reviews/handoffs, and accepted-plan coverage/error.
Report latency, memory scope and API cost separately. Local API charge is zero;
hardware, energy and human review remain unpriced. Claude's saved cost/timing and
calibration are unchanged; no new Claude calls occur.

Do not tune on the resulting regression scores. A change shared by source and
no-reference conditions is not evidence that source excerpts caused improvement.
Any win on this small authored test remains exploratory. Preserve every run,
including failed or worse candidates, and report the actual outcome.
