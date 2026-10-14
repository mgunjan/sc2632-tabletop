# Training and qualifying the control library

The current catalog is reference release 0.1.0. Qualification applies to a particular control revision, parameters and target platform. This document defines the work required to promote a release; it does not grant promotion.

## Train the bounded selector

Train the model to map each reviewed intent clause and relevant workload state to a catalog control ID, or to abstain. A compound request needs multiple clause decisions and an independent completeness review. The model must not invent policy implementations, grant an exception or decide its own deployment authority.

The local feasibility run is complete: 480 synthetic training states, separate development/calibration/test splits, frozen Laya encoder and a trained decision head. Training took 57 seconds for 120 steps. On the existing 33-decision regression set, both base and trained Laya answered 16 correctly; the trained model accepted six wrong decisions at the existing 0.6 threshold. That candidate is rejected for automatic delegation. The control-only comparison is 20/27 for TF-IDF/logistic regression and 12/27 for each Laya candidate. This is a small authored pilot, not independent enterprise validation. See [the training protocol](../submission/2026-10-13/TRAINING-PROTOCOL.md) and [actual results](../submission/2026-10-13/REVIEW.md).

A classifier can generalize to new wording. Whether it generalizes to this organization's incidents must be measured. Neither its model family nor the presence of a fitted temperature establishes reliable confidence.

The next dataset should have independently reviewed labels, collected with the source organization's permission and redacted before use. Each example needs the original intent, explicit clauses, required control IDs, applicability, target resources, legitimate dependencies, forbidden actions, unresolved requirements, acceptable alternatives and reviewer rationale. Mark disagreement and ambiguity; do not force a single preferred label when several controls are valid.

Include negation, unfamiliar wording, compound requirements, missing scope, incompatible controls, malicious instructions, legitimate forensic requests and requests beyond the library's coverage. Split by incident/source organization and template family before training. Use development data to select the model, a separate calibration split to set routing thresholds, and new incidents for final evaluation. The existing pilot has already been examined and must remain a regression set.

Compare a rules baseline, a small classifier, base Laya, trained Laya and a structured-output API candidate on identical inputs. Record per-control recall, missed requirements, abstention, wrong accepted decisions, latency and complete-run cost. Review high-impact errors separately from pooled accuracy. Bind each evaluation to the catalog, input schema, model, option order, threshold and compiler revisions. A changed catalog or implementation needs renewed evidence.

## Qualify controls by enforcement layer

| Library area | Current implementation | Evidence required before enterprise promotion |
|---|---|---|
| Workload privilege | CREATE validation for regular/init containers | Target API positive/negative tests; disposition of existing Pods, debug subresources, Linux/Windows applicability and the rest of Restricted PSS |
| Image sources | Registry prefix validation | Init/debug coverage, digest and signature/provenance controls, registry outage behavior |
| Network containment | Egress label validation plus separate lab NetworkPolicies | Target CNI connectivity, allowed dependencies, existing connections, service capacity and recovery |
| Kubernetes API access | Human RBAC/credential handoff | Effective authorization for the actual identity, intended positive reads, denied reads/writes and exposed credential response |
| Agent mutations | Selected admission restrictions and API-server guard | Subresource coverage, system namespaces, effective RBAC and independent protection of policy/controller writers |
| Exceptions | Scoped PolicyException plus scheduled cleanup | Authorized owner, exact resource/operation scope, admission constraints on expiry/TTL, deletion lag, renewed denial and audit trail |
| Rollout and recovery | Review metadata and runbook | Ratified availability/evidence criteria, authorized approval, tested promotion and rollback on the target platform |

Reuse maintained implementations from the [Kyverno policy library](https://github.com/kyverno/policies), pinning an immutable revision and retaining license attribution and tests. Map workload requirements to the [Kubernetes Pod Security Standards](https://kubernetes.io/docs/concepts/security/pod-security-standards/). Our current privilege template implements only part of those requirements. NetworkPolicy treatment of existing connections is [implementation defined](https://kubernetes.io/docs/concepts/services-networking/network-policies/#networkpolicy-s-impact-on-existing-connections), so admission simulation cannot qualify that behavior.

## Release and approval contract

For each candidate, retain the catalog/spec/compiler/rendered-policy hashes already written to `control-review.json`. Add a platform identity/version record, executed positive and negative test artifacts, failure-mode checks, exception lifecycle evidence, rollback results and an approval bound to those exact revisions. Capture reviewer identity and authorization through the enterprise's existing protected PR/GitOps workflow; a role name in this catalog is only proposed metadata.

Promotion requires all selected controls' required evidence and a disposition for every intent requirement. A passing test of one rendered control cannot authorize missing RBAC, networking or credential response. The agent must not write approvals, exception grants, policy-engine configuration or the evidence used to qualify itself. Ratify reference exception limits with control owners and enforce them independently; the current catalog flags excessive TTL but is not an exception admission controller.

The [real local expiry proof](../submission/2026-10-13/live-rehearsal/README.md) first failed because controller RBAC prohibited deletion. After a namespace-scoped repair, scheduled deletion and renewed admission denial passed. Deletion was observed 196.9 seconds after the timestamp. A strict request-time expiry guarantee requires an independently enforced and tested cutoff in the authorization/admission path; scheduled resource cleanup alone does not provide it.

Start with a platform-specific audit pilot and review observed violations and operational cost. Promote individual controls through warn and enforce using explicit acceptance and rollback criteria. Monitor coverage changes, exception age, drift and unavailable controllers after release. Requalify affected controls after API/CNI/engine upgrades or changes to their scope.

For the ISC2 session, participants review a real trained-model proposal, its actual selected-control tests and its missing requirements. Their decision records should expose scope, evidence and unresolved ownership. Do not use participant submissions for model training without separately informing them and obtaining the needed permission.
