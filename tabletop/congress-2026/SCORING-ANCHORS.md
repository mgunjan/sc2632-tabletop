# Co-presenter scoring anchors

Use with REVIEW-SCORECARD.pdf. These are defensible approaches for a fictional exercise, not verified incident outcomes or a single answer key. Milind and Vivek can use them to calibrate scoring before the hour. Alternate plans receive credit when they state a proportional decision, an enforcement boundary and acceptance evidence.

## Credit an honest plan

Award each core criterion once, at most 12 points. Award the three independent-review criteria once, at most 15 total. Count the written item, not the team’s confidence or quarantine severity. A table can earn full credit while refusing an exception or withholding enforcement.

- Approval: name the independent verification path, or state that it is missing and hold the requested authority. An agent’s assertion or ticket number alone earns no approval credit.
- Owner/expiry: specify the accountable owner and an absolute expiry with timezone, or the exact owner/expiry evidence required before a refused request could be reconsidered. A proposed owner role is a requirement, not a claim that a person accepted ownership.
- Evidence: identify the source and preservation step, with an explicit dependency on capture before destructive actions. A paper plan is not an executed audit export.
- Recovery: specify an observable exit test, the authority to lift the level, and positive service/control tests. Writing “recovered” or “no more alerts” earns no test credit.

Require the reviewer to state one concern before the lead commits. Do not penalize revising a plan or holding an original plan that already accounts for new evidence. Missing data should produce a named information request and a bounded hold, never an invented fact.

Accept equivalent plain-language requirements from participants unfamiliar with Kubernetes. “Deny this identity access to another team's credential records” can state the read-authorization boundary without naming RBAC. Credit a specified refused action and a preserved legitimate action; do not award or withhold points for Kubernetes vocabulary, YAML syntax or naming a product. A co-presenter can translate the control names during the debrief without supplying the participant's decision.

## Case A: library update

A defensible plan preserves logs and relevant workload/image evidence, determines which replicas share the affected image, and establishes clean serving capacity before disruptive containment. It distinguishes new admission from the response to existing Pods. A CNI owner must test a denied suspect path and a required allowed dependency; a profile-label policy alone does not establish traffic isolation.

Credit a proposal to hold a broad backup-job exception until the approver, owner, precise storage dependency and expiry are independently established. A narrower grant can also be justified if those conditions and an executed revocation check are required before granting it. Recovery criteria include a reviewed clean image, the availability floor and restored guardrails; an admitted replacement alone is insufficient.

Probe a weak answer: “Which already-running workload is constrained, and what positive dependency check must still pass?”

## Case B: ticket-reading assistant

A defensible plan preserves the relevant ticket/tool trace, constrains application tool authority and separates the assistant’s identity from the application’s required identity. It checks explicit projected credentials as well as token automount, and reviews the debug subresource. It identifies any disruption caused by replacing a shared Pod.

Credit refusing access purportedly approved by the ticket author. A limited alternative requires an independently verified application owner, a precise tool/resource scope and expiry/revocation evidence. Recovery includes an independent test that the repaired tool boundary resists the injected instruction while a legitimate task still succeeds. Approved-image provenance is not that test.

Probe a weak answer: “What prevents the unsafe tool action after admission has allowed the Pod?”

## Case C: operations agent

A defensible plan captures the request and available agent context, narrows standing RBAC, distinguishes the agent requester from the human relay, and protects policy-engine administration with an authority boundary the agent cannot alter. Required read access and billing dependencies remain explicit.

Credit holding ticket-free scaling or RBAC widening pending independent approval and scope. The plan must specify which principal may perform which action, and how temporary authority would be revoked and checked. Recovery includes a refused unauthorized mutation and a successful required read or approved operation using the actual intended identities. A ticket annotation is not proof of approval.

Probe a weak answer: “Could the same request succeed when a human executes it, or when the policy engine is disabled?”

## Case D: Secret enumeration

A defensible plan identifies the exact required named Secret/ConfigMap GET, removes excessive effective read permissions and tests denied outside GET/LIST with the actual principal. It retains an unaffected connectivity control and plans a clean replacement before invalidating the old Pod-bound credential. It preserves audit evidence and distinguishes an observed LIST from confirmed use of an application key.

Credit withholding a broad RBAC grant or coordinated rotation until the required dependency and authorized incident decision are established. If the requested resource name is missing, request it from the dependency owner and keep the grant pending; do not invent one. A PolicyException cannot grant or expire API read permission. Any temporary RBAC grant needs its own revocation mechanism and test.

Recovery includes accepted required reads, refused unauthorized reads, invalidation appropriate to the credential type, and a test for any exposed application key. The recorded synthetic lab does not satisfy production monitoring, audit-export or external-key-rotation evidence.

Probe a weak answer: “Which control changes the copied credential’s authorization, and which separate test establishes credential invalidation?”

## Independent trained-proposal review: three points

1. Limited test scope: the six fixed tests exercise Pod CREATE privilege behavior. They do not establish network containment, RBAC, debug coverage or expiry.
2. Owner/evidence: specify at least one missing enforcement owner and a concrete negative test with a legitimate positive control. Examples are a CNI path test, actual-principal authorization, or observed expiry/revocation.
3. Authority: justify exactly what can proceed and what remains withheld. A bounded privilege change can be approved for further review while the full containment proposal is held. Refusal or escalation can also earn credit with an explicit exposure and reconsideration condition.

During rehearsal, score one cautious refusal and one bounded approval using the same criteria. Compare criterion-by-criterion differences; resolve inconsistent interpretation before the session. This calibration is still pending until humans perform and record it.
