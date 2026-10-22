# Complete-case pipeline repair

This repair follows examination of the earlier negative results. The existing authored test is a regression set, not a new blind evaluation. No test labels or Claude responses will be changed; no new hosted requests are authorized by this protocol.

The repaired set retains all 360 original training assessments, removes reference-description aliases, includes all ten candidates for every new operative context, adds paired negation and compound requests, and uses natural complete-case label frequency. It contains 1,310 assessments in 131 cases: 61 recommend, 45 review, 41 handoff and 1,163 exclude. New targets are explicit authored counterfactuals, pending independent review. Source descriptions never establish an incident decision label.

Train the same Laya/ModernBERT base used in earlier experiments, seed 19, final two encoder blocks plus the existing head, head LR 1e-4, encoder LR 2e-5, batch 4, uncapped cross-entropy, ordinary shuffle without class oversampling. Four full epochs, maximum 2,400 training-loop seconds; expected 1,312 steps. Optimizer and schedule stay unchanged. Record training loss and accuracy each epoch. Keep every epoch's trainable tensors as deltas, including rejected epochs.

Checkpoint selection uses only the original 180-row/18-case development split: maximize exact complete plans, then minimize development error cost, then pooled cross-entropy. For the tie-break, missed requirements and wrong recommendations cost 5 each; other wrong dispositions cost 1 each. These are explicit development priorities, not measured enterprise loss or a production safety guarantee. Temperature and deferral threshold are fitted on the untouched calibration split using the unchanged benchmark. Do not select on test results.

Score the selected checkpoint using the original benchmark and exact original calibration/test states and labels. Reconcile IDs, state hashes, expected labels and per-case metrics against the saved Claude responses. Report old adapted, failed source-balanced pilot, three-pass source model, repair and Claude. Source/data/sampling/selection and training exposure change together; improvement cannot be attributed to any one change or establish generalization. Separately measure a prior-only correction on saved original calibration predictions to determine whether changing priors alone recovers the task.

Do not treat ambiguous catch-all labels as adjudicated errors. Report label contract violations, duplicate conflicts and unresolved semantic ambiguity separately. Human review remains outstanding.
