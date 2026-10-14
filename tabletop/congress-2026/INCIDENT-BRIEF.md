# Incident containment on a shared Kubernetes platform

Co-presenters: Milind Gunjan and Vivek Mayuranathan.

## What the workshop produces and why

**What:** a change set prepared from security intent for human review, containing policies, behavior tests, expiring exceptions and a phased rollout. Each table records its approval conditions and a scoped Quarantine Mode response with recovery tests.

**Why:** harmful access can extend beyond the intended workload or identity on shared infrastructure. The response must constrain that access while preserving essential services. A proposed policy or a narrow passing test does not establish that all the required control boundaries are covered. Human reviewers need evidence of the prohibited behavior and the legitimate behavior the change must preserve.

Quarantine Mode is the prebuilt incident posture that tightens selected controls. Teams justify its level, scope, declaring authority, exceptions and exit criteria. The demonstration uses a supplied reference specification and prepared evidence. The audience's newly written intent is a review artifact, not a promise of automatic model translation or deployment.

Your team operates a Kubernetes platform supporting several production services. Unexpected workload activity has been detected. Depending on the selected case, the evidence concerns network connections, assistant tool activity, workload mutation or cross-namespace Secret enumeration. The affected service remains operational, and the extent of compromise is uncertain.

Customer services and automated agents depend on the same platform. Broad isolation may interrupt legitimate dependencies, while delay may expose other workloads. Each table reviews one selected case. The opening alerts are alternatives, not four simultaneous confirmed incidents.

Propose a containment change that restricts the affected identities and workloads, preserves evidence and maintains essential service dependencies. Record every unresolved security requirement and every exception's scope, owner, approver and expiry. Define the evidence needed to promote enforcement and to authorize recovery.

The platform and incident context are fictional. Workload and namespace names such as `payments-api`, `payments`, `hr-sync` and `ops-agent` are retained from the repository fixtures and recordings for traceability. They do not imply a payroll deadline or a particular industry. Initial observations do not establish root cause.

## Participant assignment and materials

### Environment and policy vocabulary

Kubernetes is the platform managing application packages, called containers, across machines. The applications and automated agents in this exercise share that platform. Explain what each component does before naming its Kubernetes type. Participants can state the prohibited behavior, legitimate access, evidence and minimum service in plain language; prior Kubernetes or Kyverno knowledge is unnecessary for the written decisions.

| Term | Meaning in this exercise |
|---|---|
| Cluster | The shared Kubernetes platform running the applications and agents. |
| Namespace | A named resource group such as `payments` or `agents`. It does not create network isolation automatically. |
| Pod | A running unit containing one or more containers. Replicas are copies of a workload. |
| ServiceAccount | A workload's identity for Kubernetes API requests. |
| Admission | A checkpoint before a covered resource-change request takes effect. |
| Kyverno | The policy engine that validates those proposed changes in the demonstrated workflow. In Deny mode, it refuses a covered policy violation. |
| NetworkPolicy | A network traffic rule, enforced by a supporting network implementation. |
| RBAC | API permissions assigned to an identity, including permission to read a Kubernetes Secret. |
| Sidecar | An additional container in the same Pod, sharing its network and potentially its credentials. |
| Secret | A platform record that can hold credentials. An observed listing does not by itself establish application-key use. |
| Eviction | A voluntary request to remove a running application copy. |
| PodDisruptionBudget | An availability rule limiting voluntary removals. It does not prevent every cause of service failure. |

Use “application copies” before replicas, “resource groups” before namespaces and “API permissions” before RBAC. Score the stated behavior and acceptance evidence, not recall of these names. The Kubernetes [overview](https://kubernetes.io/docs/concepts/overview/) and [container documentation](https://kubernetes.io/docs/concepts/containers/) provide the platform/package definitions.

For example, a reviewed rule requires new `payments` Pods to disallow privilege escalation. Kyverno can refuse a covered create request that violates that rule. The admission check does not stop an already running Pod or revoke a credential copied elsewhere. Existing-workload response, network restrictions, API permissions and application tool controls need their own owners and evidence.

The production incident is fictional. Recorded enforcement comes from a separate disposable local k3s/Kyverno lab with synthetic stand-in applications. The reference compiler demonstrates policy generation and fixture admission simulation; it does not automatically deploy attendees' prose.

Definitions follow the [Kubernetes Pod documentation](https://kubernetes.io/docs/concepts/workloads/pods/), [namespaces](https://kubernetes.io/docs/concepts/overview/working-with-objects/namespaces/), [ServiceAccounts](https://kubernetes.io/docs/concepts/security/service-accounts/), [RBAC](https://kubernetes.io/docs/reference/access-authn-authz/rbac/) and [Kyverno ValidatingPolicy](https://kyverno.io/docs/policy-types/validating-policy/) documentation. The concrete enforcement boundaries and local lab are recorded in `lab/README.md` and `submission/2026-10-13/live-rehearsal/`.

Your table is the incident review team. Decide what may proceed, what you hold and what evidence must come before enforcement. Use one shared decision record on participant pack page 6. It captures your intent, proposal disposition, exception/rollout conditions, containment order and recovery criteria. No laptops or YAML authoring are required.

Before Round 1, choose a case on pages 2–5, choose a primary operational constraint, assign an incident lead, recorder, analyst and independent reviewer, and write a measurable minimum service. The lead states the decision, the recorder documents it, the analyst checks claims against the evidence, and the reviewer raises a concern before the decision. Combine roles if the table has fewer than four people.

The table receives case cards and proposal excerpts, a worksheet, sealed incident updates and an independent-review handout/scorecard. Discuss the evidence and record a decision before each reveal. After the new evidence, revise beside the original answer. Keep pages 7/8 and the separate review findings closed until their round opens.

Milind demonstrates the compiler and policy consequences. Vivek leads proposal reviews and evidence reveals. Both share round discussion and debrief. The model proposes bounded choices; participants retain review authority. The common compiler demonstration uses a supplied reference spec. The audience's newly written intent is a review artifact, not an automatically deployed change.

## Four selectable cases

| Case | Initial observations | Main review boundary |
|---|---|---|
| A: library update | A recently updated workload connects to unexpected services; several replicas share the image | Admission coverage, network allowances, affected workload scope and replacement capacity |
| B: support assistant | A ticket-reading assistant invokes unexpected tools while its Pod shares identity and networking with an application | Application tool authority, Pod identity, untrusted input and debug subresources |
| C: operations agent | An agent changes workloads outside its namespace without the expected ticket reference | Request identity, standing RBAC, approval authority and protection of the policy engine |
| D: Secret enumeration | A monitoring identity lists Secrets across namespaces while metrics continue | Read authorization, audit evidence, credential exposure and coordinated rotation |

A/B/C use repository reference proposals and fixture tests. D has a manually reviewed RBAC proposal and a separately executed synthetic CNI/read-authorization/credential lab. Its generator scenario `d` is not implemented; the common compiler demonstration makes that enforcement-layer handoff visible.

## Operational constraints

Each table chooses availability, evidence preservation, delivery continuity or containment as its primary constraint. The table must document a measurable availability floor, required dependencies and the evidence that would change its decision. The constraint changes the tradeoff; it does not remove the security requirement.

## Observable session outputs

1. A natural-language intent and requirement-to-control map, including unsupported enforcement layers.
2. A documented approval decision, independent test requirements and scoped exception/rollout criteria.
3. An ordered Quarantine Mode plan with triggers, scope, evidence handling, preserved dependencies and recovery authority.
4. An independent review of an actual trained-model proposal, stating the tested scope, missing owner/evidence and exact authority granted or withheld.

Timed rounds, additional evidence, peer comparison and a transparent 12+3-point rubric provide the interactive structure. Scores assess documented reasoning and evidence; they do not certify security or establish human/model superiority.

## Evidence boundaries

Keep fictional alerts, recorded k3s observations, live fixture simulation and model screening results visibly distinct. The recorded lab demonstrates additive network allowances, admission/replacement interactions, the debug-subresource gap and policy-engine authority. It is not a newly validated venue cluster.

The frozen model pilot retains its original cases, wording, labels and hashes. Reframing the workshop does not rerun or relabel that experiment. Three complete Scenario A runs per hosted provider and local Laya timings are recorded separately. Price estimates exclude human review, deployment and unmeasured operational cost.
