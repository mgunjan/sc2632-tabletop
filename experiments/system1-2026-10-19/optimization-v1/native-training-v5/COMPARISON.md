# Native Laya optimization repair and saved Claude comparison

**The native Laya training-underfit failure is repaired in this measured configuration. Generalization is scored separately below. No labels, architecture, options, test inputs or scoring code were changed. No new hosted calls were made.**

The selected update is 1312 of 1640. The ordinary native prediction API reproduces 99.69% accuracy on all 1,310 training assessments, with minimum class recall 99.66%. It matches the cached-head choices on every training and development input. All original encoder tensors are byte-identical; native head weights changed.

| Candidate | Exact plans | Required omitted | Wrong recommendations | Reviews | Handoffs | Accepted / wrong | Case p50 seconds |
|---|---:|---:|---:|---:|---:|---:|---:|
| [previous-adapted](../../../system1-2026-10-18/verified-local/adapted/summary.json) | 2/15 | 21/23 | 0 | 0/5 | 0/8 | 0 / 0 | 1.031 |
| [prior-data-repair-Laya](../../repair-v1/evaluation/summary.json) | 2/15 | 23/23 | 0 | 0/5 | 0/8 | 0 / 0 | 1.032 |
| [native-optimization-Laya](evaluation/summary.json) | 2/15 | 17/23 | 2 | 1/5 | 1/8 | 0 / 0 | 2.974 |
| [saved-Claude](../../../system1-2026-10-18/claude-opus-v1/summary.json) | 10/15 | 0/23 | 0 | 5/5 | 8/8 | 5 / 0 | 26.571 |

## Model and optimization findings

The previous selected model excluded 1,309 of 1,310 training candidates and recognized none of the 147 required candidates. Layer-level gradient checks found live gradients in both selected encoder blocks and in the native decision head. The unused action-routing head has no gradient under supervised answer loss, as expected. Training/inference attention fast paths agreed within 4.8e-7 with no choice flips on eight diagnostic inputs. These measurements rule out a disconnected head or a fast-path choice mismatch in the tested examples.

Eight deliberately contrasting training inputs, including the same control with different dispositions, reached 100% fit at the original head LR of 1e-4. The head therefore has capacity on that tiny subset. Replaying the old natural sampler showed 819/1,312 updates (62.4%) contained exclusions only. The first balanced retry accumulated four microbatches per update, so at update 500 it had made 2,000 draws per class: all 1,163 exclusions appeared at least once, averaging 1.72 presentations each, while minority examples cycled roughly 33–49 times. The retained checkpoint reached only 91.7% training accuracy. A subsequent full-row-coverage run with inverse-square-root weights still predicted only exclude after two epochs. These runs show that a larger dataset and superficial class balancing were not enough.

The repair freezes the same encoder and caches its full float32 token sequences, with a native-forward parity gate. It optimizes the unchanged native attention head, type embedding and answer scorer. Each shuffled epoch partitions all 1,310 rows into batches of 16 (the final partial batch is retained), so every authored assessment is presented exactly once per epoch. The final run uses inverse-frequency class weights normalized so each disposition contributes equal total training loss; no row is dropped or replaced. Dropout is disabled, AdamW LR stays at 1e-4, and checkpoints must pass a whole-training-set fitting gate before development selection. There is no pooling, alternate classifier, candidate masking or custom prediction adapter.

The measured causes were majority-only updates in the natural batch-four run, strong per-row exposure skew in the balanced retry, and insufficient class weighting in the first full-coverage attempt. The final configuration combines full-row coverage with equal total loss contribution for each disposition. It also freezes the encoder and disables dropout, so the bundle does not isolate one causal hyperparameter. The prior dataset defects and failed experiments remain preserved in the [earlier report](../../repair-v1/COMPARISON.md).

| Epoch / update | Train accuracy | Lowest class recall | Dev exact plans | Dev error cost | Fit gate |
|---:|---:|---:|---:|---:|---|
| 0 / 0 | 0.0496 | 0.0000 | 0/18 | 531 | False |
| 1 / 82 | 0.0496 | 0.0000 | 0/18 | 539 | False |
| 2 / 164 | 0.0947 | 0.0244 | 0/18 | 526 | False |
| 3 / 246 | 0.6771 | 0.3659 | 0/18 | 178 | False |
| 4 / 328 | 0.8046 | 0.4634 | 1/18 | 136 | False |
| 5 / 410 | 0.7076 | 0.6887 | 0/18 | 124 | False |
| 6 / 492 | 0.8794 | 0.8000 | 1/18 | 122 | False |
| 7 / 574 | 0.9397 | 0.7073 | 1/18 | 134 | False |
| 8 / 656 | 0.9313 | 0.9269 | 1/18 | 118 | False |
| 9 / 738 | 0.9748 | 0.8537 | 1/18 | 126 | False |
| 10 / 820 | 0.9718 | 0.8889 | 3/18 | 119 | False |
| 11 / 902 | 0.9908 | 0.9016 | 1/18 | 130 | False |
| 12 / 984 | 0.9947 | 0.9778 | 2/18 | 125 | False |
| 13 / 1066 | 0.9962 | 0.9957 | 1/18 | 143 | True |
| 14 / 1148 | 0.9931 | 0.9512 | 1/18 | 127 | False |
| 15 / 1230 | 0.9969 | 0.9756 | 1/18 | 144 | False |
| 16 / 1312 | 0.9969 | 0.9966 | 1/18 | 126 | True |
| 17 / 1394 | 0.9939 | 0.9556 | 0/18 | 134 | False |
| 18 / 1476 | 0.9962 | 0.9957 | 1/18 | 133 | True |
| 19 / 1558 | 0.9969 | 0.9756 | 0/18 | 130 | False |
| 20 / 1640 | 0.9977 | 0.9974 | 1/18 | 134 | True |

## Cost, timing and interpretation

Actual device: cpu. Frozen-encoder caching plus optimization took 44.61 minutes, excluding final checkpoint materialization and runtime verification. The run presented 26,200 training rows across 1,640 optimizer updates and visited all 1,310 unique rows. The separate frozen-feature cache was built from the original encoder and checked against native logits before optimization.

New API spend is $0. Claude is the saved approved October 18 run: 301 historical requests, $1.964736 estimated total, about $0.06495 per attempted ten-candidate test plan. Local API spend is zero, while hardware, energy, setup and human review are unpriced. Case timing covers ten sequential candidate assessments, not deployment or containment.

Successful training fit demonstrates repaired underfitting, not enterprise generalization. The 15 authored test cases in five families have already been examined. Their unchanged labels still lack independent review. This is a regression comparison, not a fresh blind trial or a production safety guarantee. Do not promote a model solely because its training accuracy is high or its API cost is zero.

[Native runtime verification](runtime-verification/VERIFICATION.json), [paired audit](AUDIT.json), [protocol](PROTOCOL.md).
