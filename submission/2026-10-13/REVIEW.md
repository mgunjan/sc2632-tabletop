# October 13 verification and training results

We can train a local model for control selection and build a versioned control library. This pilot does not qualify the trained model or the library for production. It adds measured evidence and makes the remaining enforcement work visible.

## Real local Laya training

We trained the decision head of the cached Laya typed-decisions checkpoint on 480 author-labelled synthetic control-selection states. The encoder was frozen; 120 steps took 57 seconds in the corrected run, excluding initial development evaluation and model loading. Development proper-scoring loss improved from 1.3400 to 0.7065; development accuracy stayed at 66.7%. A separate 60-state calibration split fitted temperature 0.8381 for ten-option choices. Neither split contains real enterprise labels.

The benchmark below uses the actual policy-agent option order, identical states/questions/labels for both candidates, and the existing 0.6 cutoff. Four hostile cases remain report-only and are excluded from the 33 scored decisions.

| Candidate | Correct / 33 | Accepted at 0.6 | Wrong among accepted | Median local decision time |
|---|---:|---:|---:|---:|
| Base Laya | 16 | 2 | 0 | 87 ms |
| Trained Laya | 16 | 21 | 6 | 87 ms |

Training increased accepted coverage without improving accuracy. The calibrated temperature was fitted on synthetic data; it did not establish reliable confidence for the regression cases. Do not promote this candidate or claim that fine-tuning has solved the task.

Three complete fixture-based Scenario A runs took a median **0.975 seconds**, with four local decisions each. They generated the privilege policy but omitted the network control and left API access unresolved. The independent requirement ledger marked the proposal **INCOMPLETE_PROPOSAL**. These runs include compilation, Kyverno simulation and proposal files; they exclude human review, deployment and real containment. No API charge was incurred; compute, energy, hardware and operating costs are unpriced.

Raw results: [base runtime order](laya-training/base-runtime-order/summary.json), [trained runtime order](laya-training/trained-runtime-order/summary.json), [complete-run measurements](laya-training/workflow-cost/summary.json). The local checkpoint stays in ignored `.session-build/laya-control-training/checkpoint-v2/`; weights are not pushed to GitHub. Training source, pinned dependencies, curriculum, protocol and measured results are in the repository.

## Classical control selection

The same 480-state curriculum trained a TF-IDF word/character feature model with logistic regression. It trained in 0.101 seconds on CPU, with no GPU or model download.

| Candidate | Untouched synthetic test / 60 | Control-only pilot / 27 | Control-pilot median time |
|---|---:|---:|---:|
| TF-IDF + logistic regression | 54 | 20 | 0.52 ms |
| Base Laya | 36 | 12 | 89.6 ms |
| Trained Laya | 37 | 12 | 89.0 ms |

The 27-state comparison covers control selection only, using the runtime option order. It excludes the six dependency/blocked-workload questions in the full workflow benchmark. These are small author-labelled samples; no universal model-family ranking is established. The classifier's control-pilot ECE is 0.247, so its probability calibration is also insufficient for automatic approval.

[Final scores](laya-training/control-holdout-rescored/summary.json) were recomputed from the immutable [original responses](laya-training/control-holdout/responses.jsonl), without rerunning inference. Laya serializes probabilities to four decimals; the first scoring pass incorrectly rejected legitimate rounding drift. A regression test now accepts only the bounded rounding error while rejecting malformed distributions. The first report remains diagnostic evidence.

## Original triage comparison

The legacy selected-text classifier reproduces **0.803 accuracy** on the 66 pooled triage question decisions. The new full-state classifier scores **0.818**. These 66 decisions come from only 27 states; they are not 66 independent incident examples.

Giving the classifier full exception fields raises scope accuracy from **2/12 to 12/12** on the authored gold set. The old scope comparison withheld workload/TTL/incident fields from the classifier while supplying them to Qwen. It does not prove that only a language model can answer new sentences or reason about scope.

The September Qwen recording matches only 45/51 current states, including 39/42 gold states. The same mismatch exists when rebuilding the original recording commit. Its original unmatched prompt states were not preserved. The evaluator now counts absent answers wrong and marks the complete comparison **INCOMPLETE**; it never pairs by position or invents replacement answers. The quoted 0.788/ECE 0.195 result is not reproducible as a complete current comparison. Do not put it on a slide as freshly verified.

[Current triage report](classical-verification-final/REPORT.md) and [recording audit](classical-verification/recording-audit.json). The earlier pre-fix reports are retained as diagnostics.

## Control library

The [reference catalog](../../controls/README.md) has ten stable control IDs, including seven existing admission implementations and explicit handoffs for RBAC, rollout governance and unsupported requirements. Each entry records its owner/approver role, applicability, actual coverage, gaps, tests, platform evidence, proposed exception limit and rollback. Compiler and policy-agent proposals now include a catalog/spec/policy-bound review artifact.

Use the maintained [Kyverno policy library](https://github.com/kyverno/policies) to extend implementations and the [Pod Security Standards](https://kubernetes.io/docs/concepts/security/pod-security-standards/) to define workload requirements. Our catalog is a project-authored reference release, not a full PSS or compliance implementation. Enterprise qualification still needs target-platform evidence for CNI behavior, effective RBAC, controller failure handling, expiry enforcement, approval provenance and rollback.

For example, the privilege template does not implement runAsNonRoot or full Restricted PSS; a registry prefix check does not verify signatures; an egress label is not network containment. Training the selector cannot fill these implementation gaps.

## OpenAI candidate

The existing Responses structured-output client remains available. A separate adapter now implements the [Decisions API](https://developers.openai.com/api/docs/guides/decisions) with `gpt-6-luna`, predicate/choice results, raw probabilities, refusals, usage and input-cost estimates. Offline contract tests passed. No authenticated OpenAI run has occurred because an OpenAI credential is not configured; Jev and Claude keys do not authenticate to OpenAI. No OpenAI charges were incurred.

## Reproducibility findings

- V1 training alphabetized options in JSON. V2 preserves inference order and repeats the same data, base, seed, optimizer and budget. V1 remains diagnostic evidence.
- The original frozen pilot also alphabetizes options, while the policy agent preserves declaration order. The original benchmark and labels are unchanged; separate `--question-order runtime` results measure production parity. Legacy results must retain their input-order configuration.
- Trained-pilot responses produced before the adapter metadata fix say local calibration was not fitted. The checkpoint actually contains the separate calibration result. Numeric answers are preserved; the adapter now reports the checkpoint flag without treating fitted temperature as verified deployment calibration.
- The independent requirement ledger, not model confidence or passing tests of selected policies alone, identifies omitted requirements.

The enterprise training set should include independently reviewed compound intents, negation, ambiguous scope, malicious input, dependency tradeoffs and real exception requests. Select the checkpoint on development data, fit confidence on calibration data, and reserve new organizations/incidents for evaluation. Changing control definitions, option order or enforcement implementations requires a new bound evaluation.
