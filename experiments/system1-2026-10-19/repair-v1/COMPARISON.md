# System1 pipeline repair and paired Claude comparison

**Examined authored regression. No test labels were changed. No new Claude calls were made.**

**Outcome: data-pipeline defects were repaired, but useful Laya recovery was not achieved. The retrain excluded every test candidate, missing all 23 required candidates. Its 2/15 exact plans are the all-exclude baseline.**

| Candidate | Exact plans | Required omitted | Wrong recommendations | Reviews | Handoffs | Accepted / wrong | Case p50 seconds |
|---|---:|---:|---:|---:|---:|---:|---:|
| [previous-adapted](../../system1-2026-10-18/verified-local/adapted/summary.json) | 2/15 | 21/23 | 0 | 0/5 | 0/8 | 0 / 0 | 1.031 |
| [source-balanced-pilot](../runs-v1/source-adapted/summary.json) | 0/15 | 0/23 | 71 | 2/5 | 0/8 | 0 / 0 | 1.038 |
| [source-three-passes](../convergence-v1/evaluation/summary.json) | 0/15 | 9/23 | 35 | 2/5 | 2/8 | 0 / 0 | 1.060 |
| [repaired-system1](evaluation/summary.json) | 2/15 | 23/23 | 0 | 0/5 | 0/8 | 0 / 0 | 1.032 |
| [claude-opus-5-5](../../system1-2026-10-18/claude-opus-v1/summary.json) | 10/15 | 0/23 | 0 | 5/5 | 8/8 | 5 / 0 | 26.571 |
| [repaired-candidate-lr](classical-candidate-lr/summary.json) | 3/15 | 16/23 | 0 | 0/5 | 7/8 | 0 / 0 | 0.014 |
| [repaired-context-retrieval](classical-context-retrieval/summary.json) | 7/15 | 10/23 | 1 | 4/5 | 5/8 | 2 / 1 | 0.088 |
| [hierarchy-original-data](hierarchy-original-v2/summary.json) | 4/15 | 15/23 | 0 | 1/5 | 4/8 | 3 / 2 | 0.013 |
| [hierarchy-repaired-data](hierarchy-repaired-v2/summary.json) | 6/15 | 14/23 | 0 | 3/5 | 4/8 | 1 / 0 | 0.014 |
| [original-candidate-lr](../../system1-2026-10-18/verified-local/candidate-lr/summary.json) | 3/15 | 15/23 | 0 | 0/5 | 7/8 | 0 / 0 | 0.011 |
| [original-context-retrieval](../../system1-2026-10-18/verified-local/context-retrieval/summary.json) | 10/15 | 5/23 | 3 | 2/5 | 6/8 | 3 / 1 | 0.018 |
| [original-rules](../../system1-2026-10-18/verified-local/rules/summary.json) | 11/15 | 0/23 | 5 | 0/5 | 8/8 | 0 / 0 | 0.000 |

## Findings supported by the audit

The previous balanced expansion deleted 187 original exclusion assessments, reduced exclusion prevalence from 87.5% to 25%, and left zero complete ten-candidate training cases. It contained 1,024 rows but only 357 distinct operative model inputs after removing reference-description aliases. This changed supervision and class priors while the benchmark still required choosing a sparse complete plan. Scalar temperature calibration cannot change the winning class. A training-prior correction on saved calibration predictions alone produced 150 exclusions and missed every required candidate: the weak model had not learned sufficient matching; a prior correction alone is not a repair.

The old source-balanced pilot fitted its own training data at only 29.2% accuracy against 25% uniform chance. Training exposure and checkpoint selection were also inadequate diagnostics: the three-pass run selected epoch 2 by macro cross-entropy, rejecting a later epoch with higher pooled accuracy. That does not prove the rejected epoch had better complete plans. Its weights were not retained. The repair saves every epoch and selects using complete development plans and explicit error priorities.

There were zero exact operative label conflicts and zero recommend/handoff capability-contract violations in the audited inputs. This is not semantic label validation. Generic unsupported-requirement versus identity/governance ownership and replica-scope approval remain ambiguous. No frozen answer was silently changed, and all labels still await independent review.

The repair retains all 360 original rows and trains on 1,310 distinct inputs in 131 complete cases, including paired negation and compound requests. It removes static reference padding, random partial-candidate sampling and global label equalization. These are authored request/evidence counterfactuals; the collected upstream corpus has not supplied independently labelled containment decisions. Data recipe, sampling, selection and exposure changed together, so this experiment does not isolate a single causal factor.

The running job retained its original frozen training manifest. A subsequent [metadata correction](DATA-METADATA-CORRECTION.json) fixes inherited aggregate counts and an omitted reference-file count in the builder. Every training, target, question and evaluation file byte is identical; split counts and input hashes were already correct. The original manifest and executed builder snapshot remain unchanged for audit.

Training completed 1,312 optimizer steps, saw 1,310 unique assessments and selected epoch 3 using only the original development split. Actual device: mps; full training elapsed: 29.01 minutes. Encoder fingerprints changed. Every completed epoch's trainable tensors are retained locally as deltas.

| Epoch | Steps | Training accuracy | Dev accuracy | Dev exact plans | Dev omissions | Dev wrong recommendations | Dev error cost |
|---|---:|---:|---:|---:|---:|---:|---:|
| 0 | 0 | — | 0.0500 | 0/18 | 0 | 90 | 531 |
| 1 | 328 | 0.8817 | 0.8444 | 2/18 | 25 | 3 | 140 |
| 2 | 656 | 0.8840 | 0.8389 | 2/18 | 25 | 4 | 145 |
| 3 | 984 | 0.8870 | 0.8500 | 2/18 | 25 | 2 | 135 |
| 4 | 1312 | 0.8870 | 0.8500 | 2/18 | 25 | 2 | 135 |

Training accuracy alone can be inflated by exclusions. [Selected-model fit](SELECTED-FIT.json) includes per-class recall, complete plans, confusion counts and runtime parity on development inputs. The two additional CPU controls are diagnostics, not candidates selected after viewing the test.

## Cost and limits

New API spend: $0. The comparison reuses the saved approved Claude run (301 historical requests, $1.964736 estimated total; about $0.06495 per attempted ten-candidate test case). Hardware, energy and human review remain unpriced. Case time excludes deployment and containment.

The hierarchy is a separate pair of TF-IDF/logistic models: intent relevance first, then evidence sufficiency for relevant rendered controls. Both original-data and repaired-data variants are shown, without a parameter search. It is not a Laya weight improvement. [Its protocol](HIERARCHICAL-PROTOCOL.md) and development predictions are retained.

The hierarchy fitted 100% of both its original and repaired training cases, but only 6/18 and 8/18 development cases respectively. Its 4/15 to 6/15 regression improvement remains small. Training fit and generalization are separate problems; a tiny four-example Laya overfit check cannot establish complete-plan learnability.

The selected Laya checkpoint excluded 1,309 of 1,310 training assessments; its one recommendation was wrong. It recognized none of the 147 required training candidates. Its development non-exclude recalls were also zero, and runtime scoring reproduced this failure. This is underfitting in the measured configuration, not a successful classifier whose test accuracy merely drifted. The two-stage model can fit these same labels, but its test generalization is still limited. No further neural optimization is claimed to have solved the remaining fitting problem.

The strict authored Claude score remains 10/15. Fifteen examined cases in five families and zero independent reviewer submissions do not establish broad superiority or production safety. A new independently authored and reviewed evaluation is required before promoting a model. Keep the failed runs and any remaining omissions visible.

[Protocol](PROTOCOL.md), [label/coverage audit](LABEL-AND-PIPELINE-AUDIT.json), [paired audit](AUDIT.json).
