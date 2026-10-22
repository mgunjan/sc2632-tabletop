# System1 balanced retraining: before and after

**Completed local experiment on the frozen authored regression set. Independent qualification remains incomplete.**

Development loss selected **source-adapted** as the primary source-trained candidate. It matched **0/15 complete plans**, compared with **2/15** for the previous adapted model and **10/15** for saved Claude Opus 5.5. Required-control omissions were **0/23**, compared with **21/23** previously. These are authored labels, not independently established truth.

| Candidate | Exact plans | Missed required | Wrong recommendations | Reviews correct | Handoffs correct | Accepted / wrong accepted | Case p50 seconds |
|---|---:|---:|---:|---:|---:|---:|---:|
| [starting](../../system1-2026-10-18/verified-local/starting/summary.json) | 0/15 | 0/23 | 81 | 2/5 | 0/8 | 0 / 0 | 1.029 |
| [head](../../system1-2026-10-18/verified-local/head/summary.json) | 2/15 | 23/23 | 0 | 0/5 | 0/8 | 0 / 0 | 1.032 |
| [adapted](../../system1-2026-10-18/verified-local/adapted/summary.json) | 2/15 | 21/23 | 0 | 0/5 | 0/8 | 0 / 0 | 1.031 |
| [rules](../../system1-2026-10-18/verified-local/rules/summary.json) | 11/15 | 0/23 | 5 | 0/5 | 8/8 | 0 / 0 | 0.000 |
| [context-retrieval](../../system1-2026-10-18/verified-local/context-retrieval/summary.json) | 10/15 | 5/23 | 3 | 2/5 | 6/8 | 3 / 1 | 0.018 |
| [candidate-lr](../../system1-2026-10-18/verified-local/candidate-lr/summary.json) | 3/15 | 15/23 | 0 | 0/5 | 7/8 | 0 / 0 | 0.011 |
| [claude-opus-5-5](../../system1-2026-10-18/claude-opus-v1/summary.json) | 10/15 | 0/23 | 0 | 5/5 | 8/8 | 5 / 0 | 26.571 |
| [balanced-head](../runs-v1/balanced-head/summary.json) | 0/15 | 0/23 | 80 | 2/5 | 0/8 | 0 / 0 | 1.035 |
| [balanced-adapted](../runs-v1/balanced-adapted/summary.json) | 0/15 | 0/23 | 75 | 1/5 | 2/8 | 0 / 0 | 1.035 |
| [no-reference-head](../runs-v1/no-reference-head/summary.json) | 0/15 | 1/23 | 71 | 2/5 | 0/8 | 0 / 0 | 1.034 |
| [no-reference-adapted](../runs-v1/no-reference-adapted/summary.json) | 0/15 | 0/23 | 64 | 2/5 | 0/8 | 0 / 0 | 1.035 |
| [source-head](../runs-v1/source-head/summary.json) | 0/15 | 0/23 | 78 | 2/5 | 0/8 | 0 / 0 | 1.038 |
| [source-adapted](../runs-v1/source-adapted/summary.json) | 0/15 | 0/23 | 71 | 2/5 | 0/8 | 0 / 0 | 1.038 |
| [no-reference-candidate-lr](../classical-v1/no-reference-candidate-lr/summary.json) | 2/15 | 16/23 | 0 | 0/5 | 7/8 | 0 / 0 | 0.011 |
| [source-candidate-lr](../classical-v1/source-candidate-lr/summary.json) | 2/15 | 15/23 | 0 | 0/5 | 7/8 | 0 / 0 | 0.011 |

Primary source candidate output counts: `{"recommend": 81, "review": 69}`. An omission means exclude/invalid on a required candidate. Retaining a candidate for review is not the same as recommending it correctly or routing the correct handoff. Reviewing everything is not a correct complete plan.

## What the data actually tests

The source condition contains 1,024 candidate assessments, 256 per label, with 851 source-context rows linked to 202 source records from eight publishers. Original training contributes 173 rows, including every original recommend/review/handoff example. Forty request wordings and their evidence variants are reused across contexts. These rows are dependent programmatic counterfactuals; they are not 1,024 independently labelled incidents. Source excerpts are static context and do not establish an incident-response decision or a live enforcement result.

The no-reference condition has the same row IDs, labels and seeded draws, with only the reference excerpts removed. It has 357 unique model-visible states after masking, so its aliases are not independent examples. Compare source with no-reference to evaluate the additional source-text effect. Compare no-reference with balanced to evaluate the curated decision examples. The balanced condition also controls for the revised cross-entropy, sampling, learning-rate and checkpoint-selection recipe. A gain over the October 18 model alone cannot identify which change caused it.

Secondary candidate-conditioned TF-IDF/logistic-regression controls use the expanded source and no-reference sets with unchanged hyperparameters. They test the data with a different architecture and do not share neural optimizer budgets. Their additional protocol was specified before the new regression evaluation.

| Paired contrast | Exact-plan rate change | Exploratory family-bootstrap 95% range |
|---|---:|---:|
| head_source_vs_no_reference | +0.0 pp | +0.0 to +0.0 pp |
| head_expanded_no_reference_vs_balanced | +0.0 pp | +0.0 to +0.0 pp |
| adapted_source_vs_no_reference | +0.0 pp | +0.0 to +0.0 pp |
| adapted_expanded_no_reference_vs_balanced | +0.0 pp | +0.0 to +0.0 pp |
| primary_source_vs_previous_adapted | -13.3 pp | -26.7 to +0.0 pp |
| primary_source_vs_claude | -66.7 pp | -93.3 to -40.0 pp |
| classical_source_vs_original | -6.7 pp | -26.7 to +13.3 pp |
| classical_source_vs_no_reference | +0.0 pp | +0.0 to +0.0 pp |

The intervals resample only five authored families. They do not establish enterprise generalization, production risk bounds or a universal model-family winner. This test was previously examined; it is a regression comparison. No test score selected a checkpoint or changed the frozen labels.

## Training and operational accounting

| Condition | Selected epoch | Dev macro cross-entropy | Steps completed | Unique IDs / model-visible states drawn | Full training seconds | Encoder changed |
|---|---:|---:|---:|---:|---:|---|
| balanced-head | 3 | 1.3791 | 270 | 245 / 245 | 250.84 | no |
| balanced-adapted | 2 | 1.3844 | 270 | 245 / 245 | 277.96 | yes |
| no-reference-head | 3 | 1.3717 | 270 | 733 / 274 | 243.01 | no |
| no-reference-adapted | 3 | 1.3617 | 270 | 733 / 274 | 278.10 | yes |
| source-head | 3 | 1.3715 | 270 | 733 / 733 | 304.29 | no |
| source-adapted | 3 | 1.3708 | 270 | 733 / 733 | 350.82 | yes |

All six runs used the real MPS device, seed 19, 270 optimizer steps, four assessments per step, and 270 label draws per disposition. Full training wall time summed to 28.42 minutes, excluding separate evaluation. Selected checkpoints can predate the final epoch; full-run draw totals are not the selected checkpoint's exposure. See each TRAINING-DRAWS.json for seeded replay checked against actual accounting.

Local API charge was $0; hardware, electricity, maintenance and human review are unpriced. There were no new hosted calls. Saved Claude usage remains $1.964736 for its entire 301-call study, $0.06495 per ten-control test case and 26.57 seconds median case latency. These are list-price estimates rather than invoices or total operating cost. Sequential case timings exclude human review, deployment and containment; no batching optimization was measured.

## Evidence and remaining limits

The typed question and original development/calibration/test files remain unchanged. All candidates' saved calibration and test state hashes, labels, case/family IDs and benchmark source hashes were checked. Executed benchmark SHA256: `e5518c875708613d71cc31255af8609a030348e6bb8f96c6427992c6b3dd27ad`.

The independent review pack remains pending. Some catalog entries overlap, and canonical exact-match labels may exclude reasonable alternatives. Original labels and responses are preserved. The new training labels also require review. A useful regression gain is not an industry-leading or production-qualified model claim.

[Selection rule and development losses](SELECTION.json), [machine-readable contrasts and audit](AUDIT.json), [frozen experiment protocol](../PROTOCOL.md).
