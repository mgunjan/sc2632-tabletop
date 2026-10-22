# Source-context training data card

This is a programmatically labelled, source-context training curriculum for the
four-disposition `guardrail_candidate` task. Its intended use is local feasibility
research. It supplies no deployment authorization or independently established
incident-response ground truth.

## Contents

The training snapshot contains 1,024 assessments: 256 each for recommend, review,
handoff and exclude. It retains 173 original training assessments, including all
45 non-exclude examples, and adds 851 assessments associated with 202 source
records/families from eight publishers. Each source-context row has record and
file/revision/content hashes, source terms, generation profile and wording index.

The recipe considered 2,092 existing description/implementation alignments. It
excluded 493 repeated descriptions, 286 metadata-only posture controls and 448
alignments outside the recipe's Apache-2.0/MIT scope. Topic selection draws from
the remaining 865 descriptions; it does not prove that an upstream rule implements
one of this project's rendered controls. Only the current reference catalog's
bounded capabilities determine recommendation eligibility.

Source publishers: Falco plugins, Falco rules, Gatekeeper library, KubeArmor
policies, Kubescape regolibrary, historical/current Kyverno policies and Tetragon.
See each row's source attribution and [upstream notices](../../datasets/comprehensive/NOTICE.md)
and [license copies](../../datasets/comprehensive/licenses/). Original source
excerpts retain their upstream terms; generated metadata does not relicense them.

## How labels are made

Forty request wordings and their evidence variants specify a supported bounded
proposal, unresolved operational dependency, non-rendered owner handoff, or an
irrelevant candidate. The actual candidate coverage/limits are supplied in state.
Static upstream descriptions are attached as reference context, explicitly not
live telemetry or authority. **The request/evidence counterfactual determines the
label; the source excerpt does not independently validate that decision.**

Model-visible fields are only operator intent, available evidence, operational
constraints and candidate. Labels, rationales, source IDs, provenance and split
identity stay outside model-visible state. Related counterfactuals and source
contexts are dependent. Do not count 1,024 rows as 1,024 independent incidents.

The no-reference ablation preserves row IDs/labels and sampling but removes the
static excerpts. It has 357 unique model-visible states; repeated aliases are
intentional for matched sampling and are not additional information. This ablation
is required before attributing a gain to the collected source text.

## Held-out data and limits

The original dev, cal, test and question files remain byte-identical. All source
augmentation is training-only. The old authored test has already been examined;
it is a regression comparison, not a newly blind evaluation. Exact duplicates
across training/held-out states are rejected; this does not prove semantic novelty.

No labels in the new curriculum were independently adjudicated. Some control
boundaries overlap. The dataset has only a small number of request/evidence
templates, and synthetic confirmed/missing dependencies do not prove real service
behavior. Public detection definitions and policy descriptions do not become
containment labels simply by collection. Live engine/CNI/runtime evidence and
independent reviews remain separate requirements.

The audit checks construction, source hashes, deterministic reproduction, label
balance and frozen files. It does not certify response correctness or enterprise
coverage. Raw third-party corpora, credentials and model weights are excluded from
this snapshot. A future public release needs its own model/data review.
