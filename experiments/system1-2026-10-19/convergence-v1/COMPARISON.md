# Supplemental three-full-pass System1 result

**Development-driven extension after a negative matched-budget pilot. This is an examined authored regression, not an independently blind result.**

| Candidate | Exact plans | Required omitted | Wrong recommendations | Reviews correct | Handoffs correct | Accepted / wrong accepted | Case p50 seconds |
|---|---:|---:|---:|---:|---:|---:|---:|
| [previous-adapted](../../system1-2026-10-18/verified-local/adapted/summary.json) | 2/15 | 21/23 | 0 | 0/5 | 0/8 | 0 / 0 | 1.031 |
| [pilot-source-adapted](../runs-v1/source-adapted/summary.json) | 0/15 | 0/23 | 71 | 2/5 | 0/8 | 0 / 0 | 1.038 |
| [three-full-passes](evaluation/summary.json) | 0/15 | 9/23 | 35 | 2/5 | 2/8 | 0 / 0 | 1.060 |
| [claude-opus-5-5](../../system1-2026-10-18/claude-opus-v1/summary.json) | 10/15 | 0/23 | 0 | 5/5 | 8/8 | 5 / 0 | 26.571 |
| [rules](../../system1-2026-10-18/verified-local/rules/summary.json) | 11/15 | 0/23 | 5 | 0/5 | 8/8 | 0 / 0 | 0.000 |

## Training exposure and interpretation

The extension completed **768 optimizer steps**, **3,072 draws**, **768 per label**. All **1,024 distinct training assessments** were seen. This is three full passes over the balanced source-context set, rather than the pilot's 270-step matched budget. Training ran on real MPS for **14.28 minutes**, selected epoch **2** using the unchanged original dev macro-cross-entropy. No new hosted calls occurred. Hardware/energy/human costs remain unpriced.

| Epoch | Steps | Dev macro cross-entropy | Dev pooled accuracy |
|---|---:|---:|---:|
| 0 | 0 | 2.5376 | 0.0500 |
| 1 | 256 | 1.3850 | 0.0500 |
| 2 | 512 | 1.3053 | 0.3667 |
| 3 | 768 | 1.3506 | 0.6722 |

The extension was justified by weak training-set fit in the pilot and a four-example overfit check reaching 100%. The sanity check deliberately reused its four training examples for selection and is not generalization evidence. It was never scored as a final candidate.

This longer run changes training exposure and optimizer budget; the existing warmup/decay schedule also scales with the total step budget. Any gain relative to the pilot cannot be attributed to source excerpts alone. The pilot source/no-reference conditions remain the equal-step ablation. The source labels remain programmatic counterfactuals with repeated request/evidence templates; they are not independent upstream incident-response labels.

All scored candidates share exact calibration/test states, labels, case/family identities and scoring-source hashes. Original labels and Claude recordings were not changed. Five authored families and 15 examined cases cannot establish industry leadership, production risk or generalization to new enterprise incidents.

[Convergence protocol](PROTOCOL.md), [pilot comparison](../comparison-v1/COMPARISON.md), [audit](AUDIT.json).
