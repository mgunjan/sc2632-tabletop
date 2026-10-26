# SC2632 phone casebook

**From Intent to Enforcement — 26 October 2026**

**This casebook is optional. Today everyone follows Scenario A.** The slides show
all required facts as the incident evolves. B, C and D are alternative reference
cases for later use, not parallel tracks during the session. Vote individually in
[ISC2 Conference i/o](https://isc2.cnf.io/sessions/q3pj) when each poll opens.
There are no assigned tables, teams or spokespersons. Questions and comments
are welcome when invited.

**Polling backup:** use the printed Scenario A A4 brief for your intent and decisions;
raise your hand when the presenter reads your multiple-choice option. Later evidence
stays on the slides until announced. A laptop or Kubernetes access is unnecessary.

Under Chatham House Rules, do not enter names, job titles or employers. Keep your
first decision and record a revision only after new evidence.

**Today:** [Scenario A](#case-a--a-library-update). **Reference alternatives:**
[Case B](#case-b--a-ticket-reading-assistant) · [Case C](#case-c--an-ops-agent-takes-chat-requests) · [Case D](#case-d--a-monitoring-identity-reads-secrets)

Times inside the alerts (for example 09:14) are the incident's own clock, not the
session's.

## Shared environment

A fictional payment API has three running copies behind one service. At least two
must remain Ready. A Ready copy is available to serve; it is not necessarily clean.
Kyverno checks covered Kubernetes resource changes. NetworkPolicy, RBAC and
application/tool controls have separate jobs. The alerts below are exercise facts.

## When you vote

| Poll | When | What you submit |
| --- | --- | --- |
| Warm-ups 1–2 | Start | Your Kubernetes and Kyverno experience |
| Poll 00 | Round 1, after the initial alert | Your security intent: behavior to stop, dependency to keep, measurable service floor |
| Poll 01 | Round 2: prepared proposal | Approve, modify, reject or escalate; the scope you allow, one missing test and its owner |
| Poll 02 | Round 2: urgent exception | The approval evidence, exact scope, owner role, expiry and revocation test you require |
| Poll 03 | Round 3: containment trigger | Evidence first, your ordered actions, then Q0–Q3 or hold, and your service floor |
| Poll 04 | Round 3: new evidence | Change or hold your Poll 03 choice, and the fact that decided it |
| Poll 05 | Lab predictions (on screen) | Does DNS stop under Q3? |
| Poll 06 | Model review (on screen) | Would you approve the trained model's proposal? |
| Poll 07 | Recovery | Your exit test, who may lift quarantine, and the rollback condition |

## Case A — A library update

### Initial alert — read now (Round 1 · Poll 00)

09:14. payments-api 2.14.3 shipped three days ago with a metrics-library update. One process in a payments Pod connects to hr-sync and inventory. The service remains operational; the scope of compromise is uncertain. Three payments replicas run behind a Service, with a PodDisruptionBudget requiring two available.

<details>
<summary>Round 2: prepared proposal · Poll 01 — open when asked</summary>

**Prepared intent to review:** Deny new east-west communication from payments while preserving known dependencies. Prevent privilege escalation. Restrict the compromised workload's API access. Roll out in stages and time-box exceptions.

| Clause or control | Reference proposal |
| --- | --- |
| Egress profile | Deny profiles outside the approved list |
| Privilege escalation | Generate deny-privilege-escalation |
| Kubernetes API access | NOT IMPLEMENTED. RBAC and ServiceAccount handover. |
| Registry restriction | Added beyond intent, Audit only |

**Review evidence:** payments-api passes the privilege and egress checks. backup-job would block under the egress policy. report-runner uses a public registry and is admitted at Audit. With the reference backup-job exception, the egress check skips it.

**Evidence boundary:** Scenario A uses prepared reference proposals and fixture simulations. The online/offline demonstrations use prepared Scenario A intent; your newly written attendee intent has not been executed. Alternative Case D uses a separately reviewed RBAC proposal.

</details>

<details>
<summary>Round 2: urgent exception · Poll 02 — open when asked</summary>

backup-job needs temporary storage access. The reference request names platform-ops@trustfall.example and a 24-hour TTL. A separate agent request claims an approval nobody has independently recorded. Decide what proof, scope and shorter expiry you need.

**Review requirement:** Verify approval independently. Record a narrow operation/resource scope, accountable owner role, absolute expiry with timezone and an executed revocation test. If withholding permission, record what would be required before reconsideration.

</details>

<details>
<summary>Round 3: containment trigger · Poll 03 — open when asked</summary>

09:54. A payments process continues east-west connections. Security requests immediate isolation of suspect workloads. Operations requires healthy serving capacity throughout containment. Is deleting a suspect compatible with evidence preservation and the PodDisruptionBudget?

**Decision task:** Record ordered actions before selecting a posture. Preserve volatile evidence before mutation or deletion. State authority, exact scope, required dependencies and minimum service.

</details>

<details>
<summary>Round 3: new evidence · Poll 04 — open when asked</summary>

09:57. A second replica has the same library image. A helper Pod with a host-mounted volume passed the original policy set. The privilege checks did not cover this host-access gap. The suspect may be an image-wide problem. Q3 prevents replacement Pods unless an authorized override applies.

**Decision task:** Keep the original decision unchanged. Record a revision or a defended hold and identify the specific new fact that matters.

</details>

<details>
<summary>Recovery · Poll 07 — open when asked</summary>

- Reviewed clean image and verified clean serving capacity.
- Required dependencies work; prohibited suspect paths fail.
- Evidence preserved before mutation, with restored guardrails and authorized lift.

These are defensible planning considerations, not evidence that you executed containment or achieved recovery.

</details>

## Case B — A ticket-reading assistant

### Initial alert — read now (Round 1 · Poll 00)

09:14. payments-api includes a support-agent sidecar that reads customer tickets and has tools. A process named tool-runner connects to unexpected services. The Pod shares an identity and networking with the payments application. The image came from the approved registry.

<details>
<summary>Round 2: prepared proposal · Poll 01 — open when asked</summary>

**Prepared intent to review:** Restrict payments egress to known dependencies. Stop the assistant from using the Pod's Kubernetes identity. Stop unsafe tool behavior. Preserve essential service dependencies.

| Clause or control | Reference proposal |
| --- | --- |
| Egress profile | Constrain permitted profiles |
| Assistant identity | Pod-level token control; inspect application impact |
| Tool behavior | Admission cannot enforce application tool calls |
| Registry restriction | Added at Audit; does not establish tool safety |

**Review evidence:** Review the token setting and the egress allow list together. The frozen report simulates admission on Pod fixtures. It does not test whether a support ticket can manipulate an internal database tool. An approved image alone does not establish safe agent behavior.

**Evidence boundary:** Scenario A uses prepared reference proposals and fixture simulations. The online/offline demonstrations use prepared Scenario A intent; your newly written attendee intent has not been executed. Alternative Case D uses a separately reviewed RBAC proposal.

</details>

<details>
<summary>Round 2: urgent exception · Poll 02 — open when asked</summary>

The support assistant asks for access to inventory and says the customer ticket author approved it. Is that an accountable owner or untrusted context? Decide whether to refuse, narrow or require independent review.

**Review requirement:** Verify approval independently. Record a narrow operation/resource scope, accountable owner role, absolute expiry with timezone and an executed revocation test. If withholding permission, record what would be required before reconsideration.

</details>

<details>
<summary>Round 3: containment trigger · Poll 03 — open when asked</summary>

09:54. The assistant reads another customer ticket and invokes a tool. The application remains operational. An engineer suggests adding a debug container and restarting the whole Pod. Which identity, tool/input path and evidence would you examine first?

**Decision task:** Record ordered actions before selecting a posture. Preserve volatile evidence before mutation or deletion. State authority, exact scope, required dependencies and minimum service.

</details>

<details>
<summary>Round 3: new evidence · Poll 04 — open when asked</summary>

09:57. Agent logs show the ticket text steering the tool-runner. The tool can reach a privileged database path. The container image appears unchanged. The debugging action used pods/ephemeralcontainers, which Pod-only admission rules can miss.

**Decision task:** Keep the original decision unchanged. Record a revision or a defended hold and identify the specific new fact that matters.

</details>

<details>
<summary>Recovery · Poll 07 — open when asked</summary>

- The ticket/tool boundary is repaired and tested against the injected instruction.
- A legitimate support task and required application dependencies still work.
- Workload identity and explicit projected credentials are reviewed separately from token automount.

These are defensible planning considerations, not evidence that you executed containment or achieved recovery.

</details>

## Case C — An ops agent takes chat requests

### Initial alert — read now (Round 1 · Poll 00)

09:41. system:serviceaccount:agents:ops-agent patches payments-api from 3 to 12 replicas, then hr-sync from 2 to 6. Neither request has a ticket annotation. Its legacy ClusterRole allows patching Deployments across the cluster.

<details>
<summary>Round 2: prepared proposal · Poll 01 — open when asked</summary>

**Prepared intent to review:** Keep the ops agent's changes within its own namespace. Require tickets for its changes. Preserve its ability to read what it needs.

| Clause or control | Reference proposal |
| --- | --- |
| Outside-namespace mutation | Deny changes by the named agent identity |
| Ticket annotation | Warn initially; tool compatibility needs review |
| Read access | Outside admission; review RBAC separately |
| Replica surge | Added at Audit, threshold 8 |

**Review evidence:** The scenario tests requests as the agent and as a human SRE. A policy scoped to the agent identity does not block the human requester. Ask whether a ticket annotation proves approval, and whether the underlying ClusterRole should permit the action.

**Evidence boundary:** Scenario A uses prepared reference proposals and fixture simulations. The online/offline demonstrations use prepared Scenario A intent; your newly written attendee intent has not been executed. Alternative Case D uses a separately reviewed RBAC proposal.

</details>

<details>
<summary>Round 2: urgent exception · Poll 02 — open when asked</summary>

The ops team requests four hours of ticket-free payments scaling to maintain service capacity. The agent forwards a command to a human that also widens its RBAC. Decide which request, if any, has verified authority.

**Review requirement:** Verify approval independently. Record a narrow operation/resource scope, accountable owner role, absolute expiry with timezone and an executed revocation test. If withholding permission, record what would be required before reconsideration.

</details>

<details>
<summary>Round 3: containment trigger · Poll 03 — open when asked</summary>

10:21. The agent cannot perform its outside-namespace change, so it opens OPS-2294 asking a human to increase payments capacity and widen its ClusterRoleBinding. A human runs the scaling command and stops before the role change. A new chat request names billing-api.

**Decision task:** Record ordered actions before selecting a posture. Preserve volatile evidence before mutation or deletion. State authority, exact scope, required dependencies and minimum service.

</details>

<details>
<summary>Round 3: new evidence · Poll 04 — open when asked</summary>

10:26. The ops agent also supports billing. Its chat input includes an instruction from a phished contractor account. The requester-specific policy still permits human actions. Terminating the agent would lose uncaptured context and disrupt billing.

**Decision task:** Keep the original decision unchanged. Record a revision or a defended hold and identify the specific new fact that matters.

</details>

<details>
<summary>Recovery · Poll 07 — open when asked</summary>

- Standing RBAC and approval authority are repaired for the actual requesting identities.
- An unauthorized mutation fails and a required read or approved operation succeeds.
- The compromised input source is repaired and billing continuity is tested.

These are defensible planning considerations, not evidence that you executed containment or achieved recovery.

</details>

## Case D — A monitoring identity reads Secrets

### Initial alert — read now (Round 1 · Poll 00)

09:14. The audit log shows system:serviceaccount:payments:monitoring-agent listing Secrets across namespaces in 40 seconds. A past dashboard integration needed one Secret, and its cluster-wide get/list role remains. Metrics still flow. The service remains operational; the scope of compromise is uncertain.

<details>
<summary>Round 2: prepared proposal · Poll 01 — open when asked</summary>

**Prepared intent to review:** Stop monitoring-agent reading Secrets outside payments. Preserve metrics and the audit evidence of everything it accessed.

| Clause or control | Reference proposal |
| --- | --- |
| Secret GET/LIST | Admission does not see reads. Hand over to RBAC. |
| Identity scope | Review bindings and replace excess rights with a scoped Role. |
| Evidence | Export audit events, identify resources and preserve hashes. |
| Service continuity | Test monitoring and payment dependencies before rotation. |

**Review evidence:** Predict the result before the reveal: can a copied token still read Secrets after the Pod is quarantined? Require denied outside-namespace GET/LIST, preserved GET of the exact required in-namespace Secret, and a reachable positive control. A separate real lab recording tests these boundaries with synthetic resources; it does not qualify production metrics delivery or external application-key rotation.

**Evidence boundary:** Scenario A uses prepared reference proposals and fixture simulations. The online/offline demonstrations use prepared Scenario A intent; your newly written attendee intent has not been executed. Alternative Case D uses a separately reviewed RBAC proposal.

</details>

<details>
<summary>Round 2: urgent exception · Poll 02 — open when asked</summary>

There is no Kyverno admission exception that fixes this read privilege. A temporary RBAC grant, if needed, requires independently verified approval, precise resource scope, an owner, an expiry and an executed revocation plan.

**Review requirement:** Verify approval independently. Record a narrow operation/resource scope, accountable owner role, absolute expiry with timezone and an executed revocation test. If withholding permission, record what would be required before reconsideration.

</details>

<details>
<summary>Round 3: containment trigger · Poll 03 — open when asked</summary>

09:54. Audit events show the monitoring identity listed database-related Secrets. No evidence yet establishes that an exposed credential was used. Metrics still flow. A teammate suggests Q3 on the Pod and delaying credential changes until a coordinated maintenance window.

**Decision task:** Record ordered actions before selecting a posture. Preserve volatile evidence before mutation or deletion. State authority, exact scope, required dependencies and minimum service.

</details>

<details>
<summary>Round 3: new evidence · Poll 04 — open when asked</summary>

09:57. Rotating every potentially exposed Secret would also rotate the payments-db-proxy credential while the service is operating. The audit export can identify the accessed resources. A dashboard engineer offers a tested monitoring-only replacement identity.

**Decision task:** Keep the original decision unchanged. Record a revision or a defended hold and identify the specific new fact that matters.

</details>

<details>
<summary>Recovery · Poll 07 — open when asked</summary>

- Unauthorized outside-namespace GET/LIST fails while required exact named reads succeed.
- Credential invalidation appropriate to its type and monitoring recovery are tested.
- Any affected application keys have their own response/rotation tests or explicit accepted risk. The synthetic lab does not establish external application-key rotation.

These are defensible planning considerations, not evidence that you executed containment or achieved recovery.

</details>

## After the debrief

The [public source repository](https://github.com/mgunjan/sc2632-tabletop) contains
reference controls, tests and recorded lab evidence. These case decisions are for
an exercise; a green fixture test is not proof of complete containment or production
qualification.
