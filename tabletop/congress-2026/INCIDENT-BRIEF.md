# Incident containment on a shared Kubernetes platform

Co-presenters: Milind Gunjan and Vivek Mayuranathan.

Your team operates a Kubernetes platform supporting several production services. Unexpected workload activity has been detected. Depending on the selected case, the evidence concerns network connections, assistant tool activity, workload mutation or cross-namespace Secret enumeration. The affected service remains operational, and the extent of compromise is uncertain.

Propose a containment change that restricts the affected identities and workloads, preserves evidence and maintains essential service dependencies. Record every unresolved security requirement and every exception's scope, owner, approver and expiry. Define the evidence needed to promote enforcement and to authorize recovery.

The platform and incident context are fictional. Workload and namespace names such as `payments-api`, `payments`, `hr-sync` and `ops-agent` are retained from the repository fixtures and recordings for traceability. They do not imply a payroll deadline or a particular industry. Initial observations do not establish root cause.

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
