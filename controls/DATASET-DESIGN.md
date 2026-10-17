# Dataset for bounded security decisions

Status: collection and evaluation design, updated October 17, 2026. The [comprehensive local collection](../datasets/comprehensive/README.md) now spans 19 pinned sources and 37,166 typed records, with source locks, duplicate groups, original assertions and separate execution receipts. Its 2,092 source-description alignments support exploratory retrieval training. The accompanying original evidence seed remains an already examined regression corpus; it is not independent evaluation.

## What the model should learn

The specialist selects reviewed control IDs for an intent clause and identifies missing evidence or a required handoff. Compound intents need multiple decisions and a separate completeness check. Appropriate response choices depend on incident state, effective authority and legitimate service dependencies. Keep acceptable alternatives and reviewer disagreement; do not force one answer where several plans meet the requirements.

Use the actual engines to evaluate known rules and policies. A model predicting an engine's deterministic result adds little when the engine can run directly. Behavioral examples support tests, retrieval and failure analysis; they do not automatically become labels for incident response. The model cannot grant an exception, authorize deployment, certify containment or write its own qualification evidence.

The existing ten-entry [catalog](catalog.json) is the first scope boundary. Seven entries bind admission templates; the other entries represent RBAC, process and unsupported requirements. Falco detections are a separate vocabulary. Extending detection coverage does not silently extend the compiler's supported actions or its decision options.

## Three linked collections

| Collection | Contents | Label authority |
|---|---|---|
| Control library | Versioned implementation, parameters, enforcement layer, operations, limitations, dependencies, ownership, exception and recovery contract | Reviewed control specification and platform qualification |
| Behavioral corpus | Rule/policy revision plus an event/resource, expected result, observed result, raw evidence and execution identity | Explicit authored expectation and the observed tool result, retained separately |
| Decision corpus | Intent, incident evidence, identity/resource state, service constraints, acceptable control sets, missing requirements and handoffs | Independent security reviewers; engine output alone cannot establish response appropriateness |

Keep the library available through deterministic lookup or retrieval. Training on a copied policy does not make a model's memory an authoritative policy release. Bind every decision evaluation to the catalog and input-schema revisions used in that run.

## Sources to acquire

| Source | Reuse | Required acquisition record |
|---|---|---|
| [Kyverno policies](https://github.com/kyverno/policies) | Selected implementations, positive/negative resources and tests | Immutable commit, exact paths, license/NOTICE, policy API, minimum engine/Kubernetes versions, original and locally observed outcomes |
| [Falco rules](https://github.com/falcosecurity/rules) | Selected rules, macros, lists, maturity tags and dependencies | Immutable commit, license/NOTICE, complete dependency closure, event source, engine/plugin and field compatibility |
| [Falco testing](https://github.com/falcosecurity/testing) | Regression fixtures and replay/test patterns | Immutable commit, license/NOTICE, artifact provenance and compatible engine/plugin identities |
| [Falco event-generator](https://github.com/falcosecurity/event-generator) | Selected behavioral generators and expected detections | Immutable commit, license/NOTICE, action definition, isolated execution environment, actual receipts and outputs |
| Authorized organizational cases | Redacted intents, constraints, legitimate exceptions and incident decisions | Permission, redaction review, source grouping, independent labels and allowed use |

The [local upstream collection](../datasets/guardrails/README.md) now pins and downloads all four repositories, retains their licenses, executes 142 Kyverno suites and replays 29 syscall captures against three Falco rulesets. Its normalized catalog and observations are separate from the original 20-case regression seed. Check the coverage manifest: downloading a rule does not establish a matching event, and a passing suite can leave declared expectations without uniquely mapped observations. Raw captures remain in the ignored local cache and are fetched from the original URLs.

## Record contract

Keep model-visible inputs separate from targets, provenance and post-decision observations. Do not send expected labels, fixture filenames that reveal the answer, test summaries or later incident outcomes to a candidate. Preserve authentic event fields, but remove test-only names/receipt markers from future model inputs and record the transformation. The current seed retains original synthetic fields for exact reproduction and is not model-ready.

Each future decision record needs:

- A stable ID, source organization/incident group, control family, scenario/template ancestry, generation method and license/permission provenance.
- Intent clauses, the evidence available at decision time, timestamps, effective identity and resource state, target platform and catalog revision.
- Required service dependencies, availability floor, evidence-preservation constraints, prohibited actions and unresolved facts.
- Acceptable control combinations, unsupported requirements, required handoffs and an explicit insufficient-evidence/abstention option. Quarantine levels are proposed playbook actions requiring their own authorization.
- Separate reviewers' initial labels, rationale, disagreement and adjudication. Mark machine-proposed or author-constructed labels; they are not independent expert labels.
- References and hashes for policy/rule inputs, execution environment, raw observations, receipt/coverage checks and cleanup. Distinguish expected behavior from observed behavior, including failures.
- Split, allowed uses and label-review status. Workshop decision slips require separate informed permission before training use.

Falco records distinguish denied attempts from successful changes, actual subjects from object names, missing fields from negative evidence, audit stages from repeated delivery, and a detector match from an incident. Kyverno records distinguish policy pass/fail/skip/error from test-harness success, Audit from Deny, CLI evaluation from API-server admission, and new changes from existing workloads.

## Coverage before scale

Expand the current catalog by coverage, rather than a target row count. For each included family collect a legitimate positive path, a forbidden path, a benign lookalike, missing context, an allowed scoped exception, an expired/out-of-scope exception, and relevant boundary cases. Some families need additional tests; a fixed checklist is not proof of completeness.

Priority families include workload privilege, image source/integrity, Pod identity, API reads/writes, agent scope, policy-writer authority, network dependencies, exception lifecycle and recovery. Include regular/init/debug containers, CREATE/UPDATE/subresources, existing Pods, copied credentials, controller failure, audit delivery gaps and incompatible platform behavior where relevant. Report unimplemented coverage explicitly.

Use counterfactual pairs: the same suspicious operation under authorized maintenance versus an unknown actor; the same request with actual subject evidence versus a misleading name; the same policy result under Audit versus Deny. Maintain rare but consequential mistakes instead of optimizing only pooled accuracy.

## Splits and qualification

Group related incidents, source organizations, templates, policy/rule variants and generated descendants before assigning splits. All paraphrases, mutations, replay captures and repeated architecture runs of one case remain in the same group. Check exact and near-duplicate overlap. A random row split can leak the answer even when texts differ.

Use training data for fitting, development for model and prompt choices, a separate calibration set for routing thresholds, and untouched independently labelled incidents for final evaluation. New platforms and rule/API versions provide additional shift tests. Existing session cases, the 33-decision pilot and the published evidence seed are examined regression sets. Do not relabel them as an unseen test or tune a model until it wins them.

A foundation model may propose varied wording and candidate labels. Tools verify engine behavior; independent reviewers verify response labels. Preserve that lineage, including disagreement. Teacher-generated answers are hypotheses, not ground truth.

Compare rules/retrieval, a small classical classifier, base/trained Laya and a structured-output API candidate on identical model-visible states and action options. Hold the compiler, evidence access and action authority constant. Report required-control recall, missed requirements, wrong accepted recommendations, abstention/risk coverage, calibration and high-impact error categories. Use incident-group resampling and paired analysis; report uncertainty and incomplete runs. Choose operational risk limits with control owners before scoring a final candidate.

Measure cold load and warm decision latency, complete-run time including retrieval/tools/retries, p50/p95 under a declared workload, token/API usage, local compute, setup/operations, human review and rework. Report cost per attempted and correctly accepted decision on labelled evaluation data, with the denominator and pricing date. Zero API charge does not mean zero operating cost.

## Initial evidence seed

[`../submission/2026-10-16/dataset/`](../submission/2026-10-16/dataset/) contains 20 logical cases: 14 synthetic Falco audit cases and six offline Kyverno privilege resources. Falco's baseline, repaired arm64 and repaired amd64 runs are observations of the same 14 cases, not 42 independent examples. Kyverno includes actual policy pass/fail/skip outputs as well as the separate six-test contract result.

Every row is `regression_only`, `training_eligible=false`, with no expert response label. The [builder](../laya_variant/build_evidence_corpus.py) checks source hashes and expected-versus-observed identity before writing. It does not invoke a model, contact a cluster, acquire upstream collections or train a checkpoint.

For SC2632, this is an optional source resource after the exercise. Keep the existing timed decisions, sealed findings, trained-candidate disclosure and reference/replay default. The next training run needs newly collected decision examples and a frozen protocol; this corpus alone cannot qualify it.
