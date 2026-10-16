# Co-presenter decision prompts

Milind Gunjan and Vivek Mayuranathan share presentation, demonstration and debrief responsibilities. These cards supplement the timed runbook; they do not add rounds or extend the hour.

## Delivery pattern

Open a round with one question. Give participants quiet time to record a decision before asking for volunteers. Hear two different decisions, then ask for the evidence that separates them. Reveal the new evidence only after decisions are recorded. Ask teams to retain their first decision beside the revision.

Alternate the speaking lead by round. During team work, each co-presenter visits different tables and brings back one defended tradeoff. Invite the independent reviewer to speak before the table lead finalizes the decision. Avoid letting the most Kubernetes-fluent person supply every answer.

At most two table reports per round, 20 seconds each. A report has a decision, a boundary and the evidence needed to proceed. Park implementation questions that cannot change the current decision. The score rewards documented reasoning under the chosen constraint, never speed or the most restrictive quarantine level. Use SCORING-ANCHORS.md to calibrate a refusal and a bounded approval before the hour. Credit stated verification requirements; a paper plan cannot establish that a live test passed.

## 00–07:15: Technical briefing before scenarios

Give security professionals the implementation before they assess a case. Use [TECHNICAL-BRIEF.md](TECHNICAL-BRIEF.md) for code locations, task payloads, defaults and authority boundaries. Introduce the purpose without starting a case narrative. Explain familiar platform functions alongside their technical names.

| Minutes | Lead and slide | What the room learns |
|---|---|---|
| 00–00:20 | Milind, 1 | Session purpose and co-presenters |
| 00:20–01:00 | Milind, 2 | Security-change problem and intended artifact |
| 01:00–01:40 | Milind, 3 | Shared platform, workload copies, groups and identities |
| 01:40–02:30 | Vivek, 4 | Falco/audit detection, admission and separate containment controls |
| 02:30–03:30 | Milind, 5 | Fixed Python loop, typed model choices, tools and three-round bound |
| 03:30–04:30 | Vivek, 6 | Provider-visible task data, uncertainty defaults and deployment boundary |
| 04:30–05:15 | Milind, 7 | Supplied-spec compiler walkthrough and exact Pod CREATE scope |
| 05:15–06:15 | Milind, 8 | Bound requirement contract, fixed tests and unresolved enforcement |
| 06:15–07:15 | Vivek, 9 | Quarantine manifests, operator actions and per-layer checks |

**Purpose:** “Services and agents share infrastructure and credentials. A security change must restrict harmful access while essential services continue. We will build a reviewed change set and a scoped containment and recovery plan. First we will show the implementation and authority boundaries, then your table will assess a case.”

**Detection boundary:** Falco rules passed validation; live detection remains unverified. The alerts are supplied fictional exercise facts. No Falco-to-agent or automatic Falco-to-Quarantine integration is implemented.

**Model boundary:** Python fixes the sequence. The optional provider receives task strings and returns a listed choice plus score. Explain the exact input fields on slide 6. Invalid or below-0.6 decisions escalate; an uncertain dependency retains its proposed allowance and flags review. The score is not a calibrated probability of safe deployment. Code not issuing a deployment does not enforce credential isolation. Separate observation and deployment permissions require operator controls.

**Compiler walkthrough:** The supplied spec bypasses the model. Run the bounded reference command; use its pre-opened artifact immediately if unavailable or over deadline. Show the catalog key, ValidatingPolicy, namespace, CREATE coverage, regular/init containers and required fields. The output is local PR.md, stage files, tests, readiness and provenance. No GitHub PR opens and no cluster change occurs. The next slide expands from one privilege requirement to the four-clause reference contract. Do not describe audience prose as executed input. Keep provider comparison for minute 49.

**Quarantine boundary:** A human applies the reviewed objects and performs evidence/identity steps separately. Q1 is a native API-server write freeze for covered identities. Q2 combines traffic rules and labels with manual authorization work. Q3 adds suspect isolation and a Pod CREATE gate. Each needs a positive/negative check and explicit recovery authority. Preserve the later lab observations for their reveal.

## 07:15–11: Assignment, case choice and setup

| Minutes | Lead and slide | What attendees do |
|---|---|---|
| 07:15–08:00 | Vivek, 10 | Locate page 6 and understand the record and table roles |
| 08:00–09:15 | Vivek, 11 | Choose one of four cases and read its opening alert |
| 09:15–10:00 | Milind, 12 | Select the operating constraint and measurable service floor |
| 10:00–11:00 | Both, 12 remains visible | Record case, constraint, roles and service floor on page 6 |

**Assignment:** “We supply case facts, prepared proposals and enforcement evidence. Your table writes, reviews and revises decisions on page 6. Your intent stays on that record; the common demo used a supplied reference spec. Decide what may proceed, what you hold and the evidence required. Work in plain language. No laptop or YAML is required.”

Hold up the pack and name its pages: four cases on 2–5, shared record on 6, sealed updates on 7/8. Keep the independent review findings sealed too. Lead states the decision; recorder writes; analyst checks evidence; independent reviewer raises a concern first. Combine roles for a small table. Both co-presenters support different tables.

Before Round 1 a ready table can identify its case and roles, explain what data the model sees, name who deploys, distinguish request prevention from runtime response, and state its minimum service. Accept behavioral security requirements without product vocabulary.

## 11–15: Intent

**Opening prompt:** “Which behavior must stop, which identity is responsible, and which dependency must keep working?”

Milind opens; Vivek collects two intent statements. The recorder writes one statement and a measurable availability floor. The independent reviewer marks the part admission cannot enforce.

If a team writes “secure the cluster,” ask it to name an observable forbidden action. Let participants use platform-neutral language; YAML syntax is not part of the score.

**Evidence of learning:** A scoped intent, an essential dependency and an enforcement-layer handover.

## 15–19: Proposal review

Vivek opens; Milind samples table reasoning. Ask teams to record APPROVE, MODIFY, REJECT or ESCALATE and one acceptance test before hearing another table's answer. A draft can proceed for review while enforcement remains withheld; participants should specify the authority they are granting.

Choose the probe for the table's case:

| Case | Probe | Evidence that earns credit |
|---|---|---|
| A | “What happens to an already running compromised Pod?” | Admission versus runtime distinction; workload/image scope; a test of actual allowed paths. |
| B | “Does removing token automount remove every credential available to the assistant?” | Shared identity, explicit projected credentials and application tool authority reviewed separately. |
| C | “Does a ticket annotation establish that an authorized person approved the change?” | Verified approval provenance and effective requester permissions. |
| D | “Which part of your proposal can stop a Secret read?” | RBAC/credential response and an executed GET/LIST test plan; no admission claim. |

Do not require identical control choices. Ask each table what would falsify its decision.

## 19–26: Exceptions and rollout

Milind opens the case-specific operational request; Vivek leads the rollout comparison. Ask teams to commit before naming a preferred disposition: “Which legitimate operation must continue, what authority would you grant while approval is checked, and what evidence would change your answer?” Then probe independently verified approval and the exact permission that expires. A named owner, a ticket or a TTL label alone does not prove approval or revocation.

Ask teams to choose modes per control. A confirmed exposure can justify immediate enforcement for one control while another remains at Warn because the compatibility evidence is incomplete. Require an availability check and a promotion/rollback trigger rather than accepting “audit first” as a universal answer.

**Evidence of learning:** Precise scope, verified approver, owner/expiry, a revocation check and a control-specific promotion decision.

## 26–38: Containment and later evidence

Vivek revisits the implementation taught before case selection and asks teams to name authority and scope during minute 26–27. Open page 7 at minute 27; each named control still requires application and verification. Vivek introduces page 7; Milind introduces page 8. Before either reveal, the recorder retains the original plan. Ask: “Which action must happen first to preserve evidence and serving capacity?”

After page 8 ask: “Which assumption changed, and what action changes with it?” Holding a decision can be reasonable if its original scope already covered the new finding; require an explanation. A changed answer earns no automatic bonus.

For D, distinguish observing a Secret LIST from proving external credential use. Identify audit policy level and response evidence before asserting which values were exposed. Plan precautionary rotation according to exposure and operational dependencies; the alert alone does not establish exfiltration.

Before minute 34, D tables lock a copied-credential prediction: can it still read Secrets after only the suspect Pod is quarantined? Name the exact required in-namespace Secret GET and the test proving that authorization. Keep the original prediction visible for the later comparison.

**Evidence of learning:** An ordered response and an explicit link between additional evidence and a revised or defended decision.

## 38–44: Recorded lab consequences

Milind presents networking and eviction; Vivek presents the debug and guardrail-identity findings. Supply the visible technical facts before asking for a decision and confirming test. Avoid testing recall of Kubernetes semantics. DNS has an existing allowance; removal needs clean capacity and evidence; debug uses another API path; the agent can modify the Deployment running the policy engine. Ask which part of the table’s response changes, then reveal the recorded observation. Keep each discussion/reveal under 90 seconds. These four discussions are ungraded.

Use “recorded k3s observation” when identifying the source. The fictional incident and recorded lab are different evidence. Bring each finding back to a participant decision: additive network allows, clean replacement capacity, API subresources and identities with authority over the policy engine.

**Evidence of learning:** One test a table would add to its own environment, with an owner.

If no table chose D, collect a short ungraded prediction before displaying slide 24; name the copied token and the Pod-only network control. Do not imply it was recorded earlier. Otherwise, at 44–45 read one D table's locked prediction and compare it with the separate October 13 synthetic lab record, using backup 33 or the status-only transcript within the existing case-comparison minute. Narrowing RBAC preserves a required named Secret GET; copied-token revocation and clean replacement are verified separately. Do not add a fifth live demo. Stand-in health is not real metrics delivery; external application-key rotation remains outstanding.

## 45–50: Independent proposal review

Vivek distributes CONTROL-REVIEW.pdf page 1 and opens the question. Milind shows slide 25 with the actual recorded trained-Laya choices. Tables have three minutes to record the scope and authority they would grant, an outstanding requirement/owner and an acceptance test. Keep page 2 sealed.

Ask: “Which requirement has actually been tested, and which action remains unimplemented?” Six privilege CREATE checks pass. The network and rollout/expiry requirements map to a privilege control with high scores; API access escalates. Scores from synthetic calibration are not validated deployment probabilities.

At 48 minutes Milind reveals INCOMPLETE_PROPOSAL on slide 26. Vivek hears one defended disposition and asks for the enforcement owner. A table can justify a bounded privilege control while documenting and escalating the remaining exposure. It must not declare the incident contained. Award up to three points for the limited test scope, actual owner/evidence and justified authority boundary.

At 49 minutes connect slide 27 to the authority just withheld: low API cost or short runtime does not resolve a missing requirement. Show the historical candidate-screening metrics for one minute. Production selection also needs representative error costs, reviewer effort and setup/operations measurements. This uses frozen option order and the zero-shot Laya configuration; the trained runtime-order comparison is separate. Jev/Claude's small author-labelled accuracy gap is inconclusive. No authenticated OpenAI result exists. The trained candidate's faster proposal remains incomplete and accepts additional wrong choices.

The old three-case Jev/Claude challenge is an optional Q&A or rehearsal activity, with its original labels and caveats retained. Do not add it to this hour.

**Evidence of learning:** A review disposition that states exactly what it authorizes, what it leaves exposed, and the test/owner needed to proceed.

## 50–60: Recovery and transfer

Milind opens recovery; Vivek asks for the personal action. Have neighboring tables review one exit test and ask whether it establishes safe service, restored controls and authorized rollback. A quiet alert stream alone does not establish recovery.

At 54–55, show the illustrative Case A decision record on slide 29 and trace initial intent, held authority, new evidence, changed action order and recovery checks. It is a paper example, not executed containment or the only acceptable answer. Use WORKED-DECISION.md for the full record and compare an actual table revision. At 55–57, tally scores and transfer the review to one requirement in each attendee’s environment.

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
