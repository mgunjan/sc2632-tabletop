# Supplemental convergence check after the matched-budget trial

The six-condition pilot and its negative regression results remain frozen in
`runs-v1` and `comparison-v1`. A post-run training diagnostic measured 29.2% accuracy
and 1.352 cross-entropy on the supplied balanced set, versus uniform baselines of
25% and 1.386. The selected model saw only 733 distinct rows during the fixed
270-step budget. This justifies checking optimization and training exposure before
attributing the failure to source-data quality alone.

This is a separate, development-driven extension. It is not part of the original
matched-budget causal comparison. The existing authored regression has been seen;
any subsequent regression score is exploratory and cannot be a fresh blind result.
No source profile, label, held-out file, Claude response or scoring rule changes.

1. Run a small head-only overfit sanity check using four training examples, one per
   label. The same four serve as the diagnostic development set intentionally.
   This is a plumbing/optimization check, not independent validation. Use seed 19,
   balanced draws, batch four, cross-entropy, head LR 1e-4, four epochs of 32 steps
   (128 steps). Never score this diagnostic checkpoint as a final candidate.
2. Run the source-adapted condition for three full passes: 256 steps per epoch,
   768 total steps, batch four. Within each class, each of the 256 examples is drawn
   once before cycling. Use the same base, seed 19, head LR 1e-4, encoder LR 2e-5,
   final-two-block adaptation and macro-cross-entropy selection on original dev.
   A 1,800-second training-loop guard bounds local resources. Keep every epoch and
   report actual steps, selection and full-run accounting.
3. Only after training/selection, score with the unchanged benchmark and original
   cal/test files. Reuse Claude recordings; no new hosted calls. Compare with the
   old model and the negative pilot. A gain here cannot distinguish extra compute
   from a data effect. The pilot's source/no-reference controls remain the equal-step
   comparison, not this longer run.

Do not extend or tune this run in response to its regression score. If training
still fails to fit, record that outcome and investigate the learning setup before
making model-quality or dataset-size claims.
