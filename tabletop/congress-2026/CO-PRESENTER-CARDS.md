# Co-presenter decision prompts

Milind Gunjan and Vivek Mayuranathan share presentation, demonstration and debrief responsibilities. These cards supplement the timed runbook; they do not add rounds or extend the hour.

## Delivery pattern

Open a round with one question. Give participants quiet time to record a decision before asking for volunteers. Hear two different decisions, then ask for the evidence that separates them. Reveal the new evidence only after decisions are recorded. Ask teams to retain their first decision beside the revision.

Alternate the speaking lead by round. During team work, each co-presenter visits different tables and brings back one defended tradeoff. Invite the independent reviewer to speak before the table lead finalizes the decision. Avoid letting the most Kubernetes-fluent person supply every answer.

At most two table reports per round, 20 seconds each. A report has a decision, a boundary and the evidence needed to proceed. Park implementation questions that cannot change the current decision. The score rewards documented reasoning under the chosen constraint, never speed or the most restrictive quarantine level.

## 06–10: Intent

**Opening prompt:** “Which behavior must stop, which identity is responsible, and which dependency must keep working?”

Milind opens; Vivek collects two intent statements. The recorder writes one statement and a measurable availability floor. The independent reviewer marks the part admission cannot enforce.

If a team writes “secure the cluster,” ask it to name an observable forbidden action. If a team names a product, ask what behavior that product must prevent. Let participants use platform-neutral language; YAML syntax is not part of the score.

**Evidence of learning:** A scoped intent, an essential dependency and an enforcement-layer handover.

## 10–13:30: Compiler and proposal demo

Vivek presents the review question; Milind operates the prepared compiler. Show the intent and ask: “Would a clean admission report be enough to approve this change?” Give tables 20 seconds to record yes/no and a reason.

Run the bounded reference command. Show `readiness.json`, clause 3's RBAC handover, and the fixed privilege tests. A passing privilege suite covers six Pod CREATE behaviors; it does not resolve network connectivity, existing workloads, debug access or credentials.

If the reference output is unavailable, use slides 9–11 and the pre-opened reference proposal. Say that the artifact is prepared. If using the optional model replay, state that recorded model answers are being reused while compilation and tests run now. Do not describe replay time as new inference latency.

**Discussion prompt:** “Who owns the unresolved clause, and what independent test would close it?”

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

Milind opens the authority question; Vivek leads the rollout comparison. Ask: “Who independently verified this approval, and what exact permission expires?” A named owner, a ticket or a TTL label alone does not prove approval or revocation.

Ask teams to choose modes per control. A confirmed exposure can justify immediate enforcement for one control while another remains at Warn because the compatibility evidence is incomplete. Require an availability check and a promotion/rollback trigger rather than accepting “audit first” as a universal answer.

**Evidence of learning:** Precise scope, verified approver, owner/expiry, a revocation check and a control-specific promotion decision.

## 26–38: Containment and later evidence

Vivek introduces page 7; Milind introduces page 8. Before either reveal, the recorder retains the original plan. Ask: “Which action must happen first to preserve evidence and serving capacity?”

After page 8 ask: “Which assumption changed, and what action changes with it?” Holding a decision can be reasonable if its original scope already covered the new finding; require an explanation. A changed answer earns no automatic bonus.

For D, distinguish observing a Secret LIST from proving external credential use. Identify audit policy level and response evidence before asserting which values were exposed. Plan precautionary rotation according to exposure and operational dependencies; the alert alone does not establish exfiltration.

Before minute 34, D tables lock a copied-credential prediction: can it still read Secrets after only the suspect Pod is quarantined? Name the exact required in-namespace Secret GET and the test proving that authorization. Keep the original prediction visible for the later comparison.

**Evidence of learning:** An ordered response and an explicit link between additional evidence and a revised or defended decision.

## 38–44: Recorded lab consequences

Milind presents networking and eviction; Vivek presents the debug and guardrail-identity findings. Before each reveal ask for a prediction and one assumption. Keep each pair of prediction/reveal under 90 seconds.

Use “recorded k3s observation” when identifying the source. The fictional incident and recorded lab are different evidence. Bring each finding back to a participant decision: additive network allows, clean replacement capacity, API subresources and identities with authority over the policy engine.

**Evidence of learning:** One test a table would add to its own environment, with an owner.

At 44–45 read one D table's locked prediction and compare it with the separate October 13 synthetic lab record, using backup 32 or the status-only transcript within the existing case-comparison minute. Narrowing RBAC preserves a required named Secret GET; copied-token revocation and clean replacement are verified separately. Do not add a fifth live demo. Stand-in health is not real metrics delivery; external application-key rotation remains outstanding.

## 45–50: Independent proposal review

Vivek distributes CONTROL-REVIEW.pdf page 1 and opens the question. Milind shows slide 24 with the actual recorded trained-Laya choices. Tables have three minutes to record the scope and authority they would grant, an outstanding requirement/owner and an acceptance test. Keep page 2 sealed.

Ask: “Which requirement has actually been tested, and which action remains unimplemented?” Six privilege CREATE checks pass. The network and rollout/expiry requirements map to a privilege control with high scores; API access escalates. Scores from synthetic calibration are not validated deployment probabilities.

At 48 minutes Milind reveals INCOMPLETE_PROPOSAL on slide 25. Vivek hears one defended disposition and asks for the enforcement owner. A table can justify a bounded privilege control while documenting and escalating the remaining exposure. It must not declare the incident contained. Award up to three points for the limited test scope, actual owner/evidence and justified authority boundary.

At 49 minutes show slide 26's historical provider metrics for one minute. This uses frozen option order and the zero-shot Laya configuration; the trained runtime-order comparison is separate. Jev/Claude's small author-labelled accuracy gap is inconclusive. No authenticated OpenAI result exists. The trained candidate's faster proposal remains incomplete and accepts additional wrong choices.

The old three-case Jev/Claude challenge is an optional Q&A or rehearsal activity, with its original labels and caveats retained. Do not add it to this hour.

**Evidence of learning:** A review disposition that states exactly what it authorizes, what it leaves exposed, and the test/owner needed to proceed.

## 50–60: Recovery and transfer

Milind opens recovery; Vivek asks for the personal action. Have neighboring tables review one exit test and ask whether it establishes safe service, restored controls and authorized rollback. A quiet alert stream alone does not establish recovery.

Close with two 20-second reports: a decision whose justification changed and a test the participant will introduce at work. Record an owner, a change and a verification step. Leave the remaining time for questions.

## Time-pressure cuts

Protect participant writing and the final recovery decision. If the demo is over its allotted time, stop it and use the prepared artifact. If five minutes behind, take one table report per remaining round and reveal the four lab findings with brief predictions; retain all four because each tests a different boundary. Show the full model comparison for one minute and move its detailed methodology to the backup slides. Do not spend exercise time troubleshooting installations or provider credentials.
