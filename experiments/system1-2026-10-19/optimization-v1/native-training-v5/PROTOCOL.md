# Laya underfitting investigation and repair protocol

This work targets Laya's native four-disposition decision head. It does not change labels, questions, data, architecture, model inputs, inference adapter, calibration rule or benchmark. The authored regression has already been examined; its frozen results are a paired comparison, not a new blind evaluation. No new Claude API calls will be made.

## What the measurements show

The original repaired-data run used shuffled natural batches of four. An exact seeded replay found that 819 of 1,312 updates (62.4%) contained only exclusions, which let the optimizer minimize loss by predicting `exclude` for nearly every candidate.

The first native-head retry addressed class imbalance by drawing one example from each of four classes in each microbatch and accumulating four microbatches per optimizer update. At update 500 it had made 2,000 draws per class. All 1,163 exclusion rows had appeared at least once, but they averaged only 1.72 presentations while the 41–61 rows in each minority class cycled roughly 33–49 times. The retained update-500 result fit 91.7% of the training rows and had 90.6% exclusion recall. The planned 750 updates would average 2.58 presentations per exclusion. This is severe per-row exposure skew; the earlier claim that most exclusions were unseen was an arithmetic error because it omitted gradient accumulation.

The native head itself receives gradients in its attention layers, type embedding and scorer; the unused action head is not used for supervised answer loss. Fast and ordinary attention paths agree within 4.8e-7. A deliberate same-candidate eight-row training diagnostic reached 100% fit at LR 1e-4. That establishes capacity on a tiny subset only, not broad fit or generalization.

The next attempt froze the encoder and gave every one of 1,310 rows one presentation per epoch, but used inverse-square-root class weights. After two epochs it still predicted `exclude` for every row, so that run was stopped before any calibration/test access. Coverage alone with weak class weighting did not solve the collapse.

## Frozen inputs and model

Use the original October 13 head-tuned Laya checkpoint at `.session-build/laya-control-training/checkpoint-v2`, the 1,310-row repaired training split and 180-row original development split in `.session-build/system1-20261019/repaired-data-v1`. The base is already task-tuned and is not an untouched upstream model. Calibration and the 150-row authored test split remain byte-identical to the prior paired Laya/Claude comparison. All labels remain assistant-authored pending independent expert review.

The encoder is frozen. Full float32 token features are cached without pooling; cache row IDs, state hashes and labels are checked against frozen inputs, and a native full-forward versus cached-head comparison must be within 1e-4 before optimization. The native Laya attention head, type embedding and disposition scorer remain unchanged. A standard Laya checkpoint is materialized and train/development predictions are checked through Laya's public prediction API before calibration or test opens.

## Final optimization attempt

Start from the unchanged base checkpoint. Use AdamW, LR 1e-4, weight decay 0.01, gradient clipping 1, seed 19, batch size 16 and 20 shuffled epochs. Disable dropout. Each epoch partitions all 1,310 rows exactly once and retains the final partial batch, giving every row the same number of presentations.

The earlier inverse-square-root weighting did not counter the exclude collapse. The final run uses inverse-frequency class weights, normalized to unit mean so all four dispositions contribute equally in total to the training loss. It changes the loss balance while preserving every input and label. No synthetic resampling, candidate masking, alternate classifier, test-informed prior or encoder fine-tuning is used.

The whole-training fitting gate is accuracy at least 99.5% and recall at least 98% for every disposition. Only checkpoints passing this gate are eligible. Select among them using development exact ten-control plans, development error cost (5 for a missed required control or wrong recommendation, 1 for another wrong disposition), then unweighted development cross-entropy. Do not open calibration or test if no checkpoint passes.

## Runtime and paired comparison

Verify all training and development predictions through the ordinary Laya API. Require frozen encoder bytes to match the source, runtime/cache probabilities within 2e-4, and zero choice disagreements. Then run the unchanged benchmark on the frozen calibration and authored test rows. Pair every row ID, state hash, expected label and benchmark source with prior Laya runs and saved Claude Opus responses. Reuse saved Claude responses only; new hosted calls and API spend are zero.

Report train fit separately from dev/test results. Include omissions, wrong recommendations, reviews, handoffs, complete plans, timings and costs. Local API cost is zero; hardware, energy, operator time and review cost remain unpriced. The previously examined 15 cases do not support a broad superiority or production-safety claim. Preserve every failed attempt and keep independent label review outstanding.
