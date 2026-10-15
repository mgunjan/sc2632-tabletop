# Co-presenter decision prompts

Milind Gunjan and Vivek Mayuranathan share presentation, demonstration and debrief responsibilities. These cards supplement the timed runbook; they do not add rounds or extend the hour.

## Delivery pattern

Open a round with one question. Give participants quiet time to record a decision before asking for volunteers. Hear two different decisions, then ask for the evidence that separates them. Reveal the new evidence only after decisions are recorded. Ask teams to retain their first decision beside the revision.

Alternate the speaking lead by round. During team work, each co-presenter visits different tables and brings back one defended tradeoff. Invite the independent reviewer to speak before the table lead finalizes the decision. Avoid letting the most Kubernetes-fluent person supply every answer.

At most two table reports per round, 20 seconds each. A report has a decision, a boundary and the evidence needed to proceed. Park implementation questions that cannot change the current decision. The score rewards documented reasoning under the chosen constraint, never speed or the most restrictive quarantine level. Use SCORING-ANCHORS.md to calibrate a refusal and a bounded approval before the hour. Credit stated verification requirements; a paper plan cannot establish that a live test passed.

## 00–06: Context, participant assignment and setup

Start with the incident and the decision participants own. State the required output and service constraint before terminology. Use slide 2 for the situation, then the environment primer and assignment.

| Minutes | Lead and visible slide | What attendees do |
|---|---|---|
| 00–00:20 | Milind, slide 1: session and co-presenters | Find a table and the participant pack. |
| 00:20–01:10 | Milind, slide 2: incident review | Understand the uncertainty, service constraint, authority decision and required output. |
| 01:10–01:50 | Milind, slide 3: environment | Learn the shared application's running units, resource groups and identities. |
| 01:50–02:30 | Vivek, slide 4: Kyverno and its boundary | Follow a request/rule/denial example and distinguish future admission from existing-workload response. |
| 02:30–03:15 | Vivek, slide 5: task, record and roles | Locate page 6, understand the decisions, materials and round sequence, and choose table roles. |
| 03:15–04:30 | Vivek, slide 6: case selection | Choose one case and read its opening alert. Both co-presenters support different tables. |
| 04:30–05:00 | Milind, slide 7: operating constraint | Understand the four tradeoffs and the required minimum service. |
| 05:00–06:00 | Both, slide 7 remains visible: setup | Record the case, roles, constraint and minimum service on page 6. |

**Milind's opening statement:** “Your organisation runs services and automated agents on a shared platform. Your case reports unexpected activity. Services are still operating, and the extent of exposure is uncertain. You are the security review team: decide what may proceed, what must be held and what evidence would justify tightening controls. We provide case facts, prepared proposals and enforcement evidence. You produce a reviewed change set and a scoped containment and recovery plan.”

Give a ten-second illustration from A: a payments process makes unexpected connections after a library update. This establishes a situation before vocabulary; other tables choose alternative cases, not simultaneous incidents. Do not reveal the later finding.

State the interaction contract while showing slide 5: the table's intent stays on its decision record. The common demo compiles a supplied reference spec; participants compare their requirements with prepared proposals and retain approval authority. A table can justify an approval, hold, revision or refusal. Its written boundary and evidence determine what that decision authorizes. The demonstration does not run a branching incident simulation from the table's prose.

**Milind's environment explanation:** “We have applications and automated agents sharing a platform. Kubernetes manages their application packages, called containers, across machines. In this exercise it tries to keep the required number of application copies running. Those running units are Pods, and their copies are replicas. Namespaces group resources. A ServiceAccount identifies a workload making a management request. The incident is fictional, and recorded enforcement uses a separate disposable local lab.”

Begin with the familiar function, then name its Kubernetes equivalent. Explain the management API as the interface for reading or changing platform resources. Participants do not need prior Kubernetes or Kyverno experience to state the required behavior. Use “application copies” for replicas, “resource groups” for namespaces and “API permissions” for RBAC when explaining the task. Retain the technical name beside its explanation so experienced participants can inspect the actual boundary.

**Vivek's Kyverno explanation:** “Kyverno checks a proposed Kubernetes change against policy before the request takes effect. For example, a new Pod requests privilege escalation, but our rule disallows it. In Deny mode, Kyverno refuses that covered request. An existing Pod keeps running. Network controls, API permissions and application tool controls handle different parts of containment. The model proposes a rule; human review authorizes enforcement.”

Use “admission” only after defining it as that request checkpoint. Ask: “Does denying the new Pod stop the one already running?” Accept “no, it needs a separate response” without YAML or product-specific syntax. Kyverno also has other capabilities; the example describes its validation role in this exercise. An unfamiliar participant can still judge scope, legitimate access, exceptions and recovery evidence.

For a participant new to Kubernetes, the task is to answer: which behavior must stop, which access is legitimate, what evidence could change the decision, and what must remain available? Translate their statement into the control-layer terminology during debrief. For example, “prevent this identity from reading another team's stored credentials” states an API-permission requirement without naming RBAC. Do not require tool vocabulary to earn the review points.

**Vivek's assignment statement:** “Your table is the incident review team. Decide what may proceed, what you hold and what evidence must come before enforcement. Write your security intent, review the proposal and exception conditions, then order containment and define recovery. Use one shared record on page 6. Discuss, write before the reveal, hear the new evidence, and revise beside your first answer.”

Hold up the actual materials while identifying them. Keep pages 7 and 8 covered and the independent review findings sealed. Tell participants that the model proposes controls and the team retains review authority. The compiler demonstration uses a supplied reference specification; audience prose does not automatically deploy. Both co-presenters lead discussion, demonstrate evidence and debrief. These opening leads do not make either co-presenter an assistant.

**Setup check before Round 1:** Each table can identify its case, primary constraint, recorder, decision worksheet and minimum service. An attendee can explain the assignment and why refusing a new request does not terminate an existing workload, without Kubernetes YAML. Keep the score explanation to one sentence and leave detailed scoring on the printed scorecard.

## 06–10: Intent

**Opening prompt:** “Which behavior must stop, which identity is responsible, and which dependency must keep working?”

Milind opens; Vivek collects two intent statements. The recorder writes one statement and a measurable availability floor. The independent reviewer marks the part admission cannot enforce.

If a team writes “secure the cluster,” ask it to name an observable forbidden action. If a team names a product, ask what behavior that product must prevent. Let participants use platform-neutral language; YAML syntax is not part of the score.

**Evidence of learning:** A scoped intent, an essential dependency and an enforcement-layer handover.

## 10–13:30: Compiler and proposal demo

Vivek distinguishes the policy agent selecting catalog controls from the case agents whose access is under review. The model is a candidate for varied-language mapping; fixed inputs may need only rules or a catalog. Milind operates the prepared compiler. Show the intent and ask: “Would a clean admission report be enough to approve this change?” Give tables 20 seconds to record yes/no and a reason.

Say that the first example covers one privilege requirement; the next slide expands to the full four-clause Scenario A reference. Teams B/C/D then turn to their own prepared excerpt. Run the bounded reference command. Show `readiness.json`, clause 3's RBAC handover, and the fixed privilege tests. A passing privilege suite covers six Pod CREATE behaviors; it does not resolve network connectivity, existing workloads, debug access or credentials.

If the reference output is unavailable, use slides 9–11 and the pre-opened reference proposal. Say that the artifact is prepared. If using the optional model replay, state that recorded model answers are being reused while compilation and tests run now. Do not describe replay time as new inference latency.

**Discussion prompt:** “Who owns the unresolved clause, and what independent test would close it?”

If asked whether a newly written intent has the same coverage, explain that the independent contract is bound to the prepared input. The October 14 regression added a monitoring requirement: the repaired ledger shows every actual clause as unreviewed and requires a new contract. Keep this as an answer to the input-boundary question, not an added main-session demo. The audit and fresh Jev recording are in submission/2026-10-14/.

**Evidence of learning:** A concrete condition under which a technically valid policy proposal remains incomplete.

## 13:30–18: Proposal review

Vivek opens; Milind samples table reasoning. Ask teams to record APPROVE, MODIFY, REJECT or ESCALATE and one acceptance test before hearing another table's answer. A draft can proceed for review while enforcement remains withheld; participants should specify the authority they are granting.

Choose the probe for the table's case:

| Case | Probe | Evidence that earns credit |
|---|---|---|
| A | “What happens to an already running compromised Pod?” | Admission versus runtime distinction; workload/image scope; a test of actual allowed paths. |
| B | “Does removing token automount remove every credential available to the assistant?” | Shared identity, explicit projected credentials and application tool authority reviewed separately. |
| C | “Does a ticket annotation establish that an authorized person approved the change?” | Verified approval provenance and effective requester permissions. |
| D | “Which part of your proposal can stop a Secret read?” | RBAC/credential response and an executed GET/LIST test plan; no admission claim. |

Do not require identical control choices. Ask each table what would falsify its decision.

## 18–26: Exceptions and rollout

Milind opens the case-specific operational request; Vivek leads the rollout comparison. Ask teams to commit before naming a preferred disposition: “Which legitimate operation must continue, what authority would you grant while approval is checked, and what evidence would change your answer?” Then probe independently verified approval and the exact permission that expires. A named owner, a ticket or a TTL label alone does not prove approval or revocation.

Ask teams to choose modes per control. A confirmed exposure can justify immediate enforcement for one control while another remains at Warn because the compatibility evidence is incomplete. Require an availability check and a promotion/rollback trigger rather than accepting “audit first” as a universal answer.

**Evidence of learning:** Precise scope, verified approver, owner/expiry, a revocation check and a control-specific promotion decision.

## 26–38: Containment and later evidence

Vivek defines Quarantine Mode as this project’s coordinated incident posture; each named control requires application and verification. Vivek introduces page 7; Milind introduces page 8. Before either reveal, the recorder retains the original plan. Ask: “Which action must happen first to preserve evidence and serving capacity?”

After page 8 ask: “Which assumption changed, and what action changes with it?” Holding a decision can be reasonable if its original scope already covered the new finding; require an explanation. A changed answer earns no automatic bonus.

For D, distinguish observing a Secret LIST from proving external credential use. Identify audit policy level and response evidence before asserting which values were exposed. Plan precautionary rotation according to exposure and operational dependencies; the alert alone does not establish exfiltration.

Before minute 34, D tables lock a copied-credential prediction: can it still read Secrets after only the suspect Pod is quarantined? Name the exact required in-namespace Secret GET and the test proving that authorization. Keep the original prediction visible for the later comparison.

**Evidence of learning:** An ordered response and an explicit link between additional evidence and a revised or defended decision.

## 38–44: Recorded lab consequences

Milind presents networking and eviction; Vivek presents the debug and guardrail-identity findings. Supply the visible technical facts before asking for a decision and confirming test. Avoid testing recall of Kubernetes semantics. DNS has an existing allowance; removal needs clean capacity and evidence; debug uses another API path; the agent can modify the Deployment running the policy engine. Ask which part of the table’s response changes, then reveal the recorded observation. Keep each discussion/reveal under 90 seconds. These four discussions are ungraded.

Use “recorded k3s observation” when identifying the source. The fictional incident and recorded lab are different evidence. Bring each finding back to a participant decision: additive network allows, clean replacement capacity, API subresources and identities with authority over the policy engine.

**Evidence of learning:** One test a table would add to its own environment, with an owner.

If no table chose D, collect a short ungraded prediction before displaying slide 23; name the copied token and the Pod-only network control. Do not imply it was recorded earlier. Otherwise, at 44–45 read one D table's locked prediction and compare it with the separate October 13 synthetic lab record, using backup 32 or the status-only transcript within the existing case-comparison minute. Narrowing RBAC preserves a required named Secret GET; copied-token revocation and clean replacement are verified separately. Do not add a fifth live demo. Stand-in health is not real metrics delivery; external application-key rotation remains outstanding.

## 45–50: Independent proposal review

Vivek distributes CONTROL-REVIEW.pdf page 1 and opens the question. Milind shows slide 24 with the actual recorded trained-Laya choices. Tables have three minutes to record the scope and authority they would grant, an outstanding requirement/owner and an acceptance test. Keep page 2 sealed.

Ask: “Which requirement has actually been tested, and which action remains unimplemented?” Six privilege CREATE checks pass. The network and rollout/expiry requirements map to a privilege control with high scores; API access escalates. Scores from synthetic calibration are not validated deployment probabilities.

At 48 minutes Milind reveals INCOMPLETE_PROPOSAL on slide 25. Vivek hears one defended disposition and asks for the enforcement owner. A table can justify a bounded privilege control while documenting and escalating the remaining exposure. It must not declare the incident contained. Award up to three points for the limited test scope, actual owner/evidence and justified authority boundary.

At 49 minutes connect slide 26 to the authority just withheld: low API cost or short runtime does not resolve a missing requirement. Show the historical candidate-screening metrics for one minute. Production selection also needs representative error costs, reviewer effort and setup/operations measurements. This uses frozen option order and the zero-shot Laya configuration; the trained runtime-order comparison is separate. Jev/Claude's small author-labelled accuracy gap is inconclusive. No authenticated OpenAI result exists. The trained candidate's faster proposal remains incomplete and accepts additional wrong choices.

The old three-case Jev/Claude challenge is an optional Q&A or rehearsal activity, with its original labels and caveats retained. Do not add it to this hour.

**Evidence of learning:** A review disposition that states exactly what it authorizes, what it leaves exposed, and the test/owner needed to proceed.

## 50–60: Recovery and transfer

Milind opens recovery; Vivek asks for the personal action. Have neighboring tables review one exit test and ask whether it establishes safe service, restored controls and authorized rollback. A quiet alert stream alone does not establish recovery.

At 54–55, show the illustrative Case A decision record on slide 28 and trace initial intent, held authority, new evidence, changed action order and recovery checks. It is a paper example, not executed containment or the only acceptable answer. Use WORKED-DECISION.md for the full record and compare an actual table revision. At 55–57, tally scores and transfer the review to one requirement in each attendee’s environment.

Close with two 20-second reports: a decision whose justification changed and a test the participant will introduce at work. Record an owner, a change and a verification step. Leave the remaining time for questions.

## Time-pressure cuts

Protect participant writing and the final recovery decision. If the demo is over its allotted time, stop it and use the prepared artifact. If five minutes behind when starting the scheduled minute-38 section, use the exact recovery schedule below. Keep all four control boundaries, the three-minute independent review and four-minute recovery task. Move extended model methodology to the backup discussion. Do not spend exercise time troubleshooting installations or provider credentials.

## Five-minute recovery schedule

Use this only when the scheduled minute-38 segment begins at actual elapsed minute 43. It recovers five minutes without reducing the independent-review or recovery writing tasks. Suppress extra volunteer reports during the compressed reveals.

| Actual clock | Activity | Bound |
|---|---|---|
| 43:00–46:00 | Four recorded lab prediction/reveal pairs | 45 seconds each: short written prediction, evidence, one consequence |
| 46:00–46:30 | D comparison | Use its earlier prediction, or ask before displaying the answer if nobody chose D |
| 46:30–49:30 | Independent trained-proposal review | Preserve three minutes of team work |
| 49:30–50:00 | Reveal incomplete coverage | State the missing control and ownership boundary |
| 50:00–50:30 | Historical model cost/time comparison | Distinguish latency, API cost and incomplete work |
| 50:30–54:30 | Recovery | Preserve four minutes for exit tests and lift authority |
| 54:30–58:30 | Personal action and two short reports | Preserve action, owner and verification; each report at most 20 seconds |
| 58:30–60:00 | Questions and close | Park unresolved implementation detail in the source package |

Time recovered: three minutes from lab commentary, 30 seconds each from case comparison, findings reveal, model commentary and questions. Practise this as a separate drill; the schedule is planned, not a measured human rehearsal result.
