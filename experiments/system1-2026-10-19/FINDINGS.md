# System1 diagnosis: data-pipeline defects, repaired training fit, and generalization limits

In the final [native optimization repair](optimization-v1/native-training-v5/COMPARISON.md),
freezing the encoder, caching full float32 token sequences, presenting all 1,310
repaired rows once per epoch (batch size 16, dropout disabled) and applying
normalized inverse-frequency class weights repaired training underfit: **99.69%
training accuracy** and **>=99.66% recall on every disposition**, verified through
Laya's native prediction API. Despite near-perfect training fit, out-of-sample test
performance stayed at **2/15 exact plans** (omitting **17/23** required controls and
making **2** wrong recommendations).

Earlier, the [complete-case repair](repair-v1/COMPARISON.md) retained all 360 original rows,
replaced partial candidate sampling with 131 complete cases / 1,310 assessments,
removed reference aliases, restored natural candidate frequency and selected on
development complete plans. Under natural batching, that four-epoch neural rerun
matched **2/15** test plans, omitting **23/23** required candidates (the all-exclude baseline).

The separate two-stage classifier fitted 100% of its training cases and improved
from **4/15 to 6/15** on the same examined test when given the repaired data. It still
omitted 14 required candidates. Saved Claude remains **10/15**, with no omissions
or wrong recommendations by the frozen authored labels. The original retrieval
model remains 10/15; expanding its data reduced that result to 7/15. Together, these
runs establish that the bottleneck is cross-feature generalization in a small
frozen-encoder classifier head rather than training optimization—and that deterministic
catalog gates plus simulation remain essential.

The audits found no exact operative label conflicts or capability-label violations.
Semantic ambiguity remains around generic unsupported ownership and replica scope
approval. Both independent reviewer forms remain blank. Test answers were not changed,
and the Claude usage/export audit was rerun offline with zero new API calls.

## Historical matched-budget pilot and convergence extension

The matched-budget pilot is complete. The dataset was rebuilt with equal labels,
the collected source text entered real local GPU training, and the resulting
checkpoints were scored against the same saved Claude comparison. **The current
recipe did not produce a useful improvement.** The separate [full-pass convergence
extension](CONVERGENCE-PROTOCOL.md) investigates the weak training fit before
attributing this failure to source-data quality alone.

**Final extension result:** the three-full-pass run also matched **0/15 complete
plans**. It omitted **9/23** required candidates and made **35** wrong recommendations.
This improves some decisions relative to the pilot, but the previous adapted
model still matched 2/15 complete plans and saved Claude matched 10/15. See the
[full-pass report](convergence-v1/COMPARISON.md) for the selected epoch and learning
curve. This extra-compute run does not isolate the contribution of source text.

| Candidate | Exact complete plans | Required candidates omitted | Wrong recommendations |
|---|---:|---:|---:|
| Previous adapted Laya | 2/15 | 21/23 | 0 |
| New source-adapted Laya, selected by dev loss | 0/15 | 0/23 | 71 |
| Saved Claude Opus 5.5 | 10/15 | 0/23 | 0 |

All six newly trained Laya variants matched zero complete plans. Both expanded
candidate-conditioned logistic-regression controls matched 2/15, versus 3/15
using the original training set. None of the new candidates accepted a test plan
under the frozen calibrated routing rule. These are small authored-label results;
independent review is still pending.

## What changed and what was actually used

The new set contains 1,024 assessments, 256 per disposition. It includes 851 rows
with reference excerpts linked to 202 upstream records from eight publishers.
The source-trained selected checkpoints actually drew 733 distinct assessment IDs
and encountered excerpts from 197 of those records, verified by seeded sampler
replay against the actual draw accounting. This is actual training exposure,
rather than copying unused source files into a directory.

The additional labels are programmatic request/evidence counterfactuals around
the existing reference catalog. Forty request wordings and evidence variants are
reused across sources. These are not 1,024 independent incidents or expert labels.
The source descriptions provide static context, not validated containment decisions.

All six runs used the same base, seed, optimizer-step budget and head rate. Three
conditions separate the revised balanced recipe, expanded decision examples with
reference text removed, and those examples with reference text present. Each has
a head-only and final-two-block adaptation run. The matched source/no-reference
conditions expose the same assessment IDs; only the excerpts differ.

## Interpretation

Balancing changed the failure mode. The previous model omitted required controls;
the new source-adapted model broadly recommended or reviewed candidates, producing
81 recommendations and 69 reviews, with no exclusions or handoffs. Counting zero
omitted candidates therefore does not mean the plan improved. It made 71 wrong
recommendations by the existing authored labels.

Adding the source excerpts yielded no complete-plan improvement over the matched
no-reference condition. Each source-trained neural variant made seven more wrong
recommendations than its no-reference counterpart. The classical source-text
control also showed no complete-plan gain. These are observations from one seed
and a small examined regression set, not proof that domain data cannot help.

The before/after result bundles sampling, objective, selection and learning-rate
changes; the new within-experiment controls are what test the additional data.
Equal optimizer steps do not mean equal input tokens or compute time. The exact
task, calibration/test bytes, labels and scoring source remained unchanged.

## Checks and remaining work

The curation audit reproduced the set exactly and verified upstream corpus hashes.
All 1,024 encoded training states and all four options fit without truncation.
A sampled development check found agreement between direct model scoring and the
runtime API; batching changed probabilities by less than two parts in ten million
on that check. These checks do not certify every aspect of model training.

The four-example sanity check reached 100%; the pilot's full supplied training-set
accuracy was 29.2%, and the longer run's dev pooled accuracy reached 67.2% at its
last epoch. Macro-cross-entropy selected the earlier epoch 2, whose dev pooled
accuracy was 36.7%. All epochs and the predeclared selection rule are retained;
the final-epoch accuracy was not substituted for the selected checkpoint's result.

The next useful work is to investigate the remaining decision-quality gap, obtain
independent labels for contrasting supported/unsupported and sufficient/insufficient
evidence cases, and evaluate new independently authored families. Simply attaching
more policy descriptions is not a demonstrated solution to this decision task.
Preserve these negative results; do not relabel the test or tune to its answers.

The six pilot training receipts total about 28.4 minutes on MPS, followed by separate
evaluation. The full-pass extension adds about 14.3 minutes of training; the tiny
overfit and read-only diagnostics are separate. There were no new hosted calls. Hardware, energy and human review are
unpriced. New checkpoints remain research candidates and have not been promoted
into the presenter workflow.

[Complete paired report](comparison-v1/COMPARISON.md),
[data card](DATA-CARD.md), [data audit](DATA-AUDIT.json),
[inference parity check](INFERENCE-PARITY.json).
