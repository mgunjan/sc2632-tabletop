# SC2632 co-presenter cards

Milind Gunjan and Vivek Mayuranathan share the briefing, demo and debrief. These cards follow the 60-minute deck; they add no activity. Keep the Participant Decision Record open and lock each table's answer before revealing new facts.

## Room contract

The audience is a mixed cloud-security room. No Kubernetes vocabulary, laptop or YAML is required. Translate terms when first used and ask what a control actually covers. Score evidence, justified restraint, clear authority and a testable recovery condition. Do not score speed or maximum lockdown. Hear at most two 20-second table reports per round.

The case setting is a fictional shared Kubernetes platform. A payment API is used to make availability measurable: three copies, at least two Ready. The cases demonstrate generic Kubernetes controls; they are not payment-compliance guidance. No incident is assigned until slide 13. Support, operations and monitoring agents are workloads with identities. The policy copilot is a separate system. Human reviewers retain approval and deployment authority.

## Opening handoffs (slides 1–14, minute 0–12)

| Time | Slides / lead | Room outcome |
|---|---|---|
| 00:00–03:30 | 1–3, 5–6, Milind | State the conflict; why this fictional setting; fixed facts and unknowns; 60-minute agenda and participant output; plain-language cluster map; Falco / audit, Kyverno, NetworkPolicy / RBAC and human-approval boundaries. Slide 4 is a hidden reference backup. |
| 03:30–05:30 | 7, Vivek (8 hidden backup) | Explain Python-controlled workflow, typed model output, what the model sees and trust boundaries. No model has deployment authority. |
| 05:30–07:15 | 9–10, Milind | Trace one supplied requirement to one policy and its fixture tests. Show the rest of the intent ledger is unresolved. |
| 07:15–08:15 | 11, Vivek | Explain Quarantine Q0–Q3; each mode is an operator action with a distinct scope and verification. |
| 08:15–09:00 | 12, Vivek | Hold up the participant pack: cases 2–5, shared record 6–7, later evidence 8–9. Name the four table roles. |
| 09:00–10:15 | 13, both | Assign the table's default case or allow a 30-second choice. Read only the selected case. Keep 8–9 sealed. |
| 10:15–12:00 | 14, both | Choose one operating constraint and write case, roles and minimum service floor on page 6. |

**Falco statement:** system-call rules passed static validation; Kubernetes audit rules passed synthetic tests. The workshop does not run live Falco capture, prove API-server delivery, route alerts to the policy agent or automatically trigger quarantine. These alerts are supplied exercise facts.

## Participant decisions and evidence (minute 12–60)

| Time | Slides | Lead | Cue and evidence to elicit |
|---|---:|---|---|
| 12–16 | 15 | Milind | Write the behavior, identity, dependency to preserve and measurable floor. |
| 16–20 | 16 | Vivek | Lock approve / modify / reject / escalate. Name one change and one acceptance test. |
| 20–23 | 17 | Milind | Verify approver and permission; define exception scope, owner, expiry and revocation test. A ticket or TTL label alone proves neither. |
| 23–27 | 18 | Vivek | Set Audit / Warn / Deny per control; state promotion and rollback criteria. Do not treat modes as universal stages. |
| 27–28 | — | Both | Unseal page 8 at minute 27. Allow the transition; begin the decision round at minute 28. |
| 28–35 | 19 | Both | Use page 8. Order evidence capture, identity/action, containment scope, service floor and verification. |
| 35–39 | 20 | Milind | Open page 9. Revise or defend; cite the new fact and preserve the original decision. |
| 39–40 | 21 | Milind asks; Vivek tallies | Keep slide 21 projected. Read all four concise setups and collect one hands-up vote for each; record, do not discuss. This is a fast prediction check, not four table reports. |
| 40–41:15 | 22 | Milind / Vivek | Reveal the DNS result: NetworkPolicy allows are additive. Ask which allow must change and which UDP/TCP tests would verify it. |
| 41:15–42:30 | 23 | Vivek / Milind | Explain that PDB limits voluntary eviction by readiness count, not trust. One eviction is allowed at 3 Ready; Q3 blocks replacement; a second is denied at minAvailable 2. Direct deletion bypasses the PDB. |
| 42:30–43:30 | 24 | Vivek | Reveal the debug subresource boundary. Ask who owns a test and what forensic image should be approved. |
| 43:30–45 | 25 | Milind / Vivek | Reveal the policy-engine failure and native Q1 guard. Keep scope explicit: protects matched writes; it is not a universal defense against administrator actions. These are recorded lab observations. |
| 45–46 | 26; backup 35 | Vivek | Case D only: compare a prediction locked earlier with the separate synthetic credential observation. Do not generalize one observed 41.2-second interval as a guarantee. |
| 46–49 | 27 | Both | Give CONTROL-REVIEW page 1; keep page 2 sealed. Ask what authority the evidence supports and what remains unimplemented. |
| 49–51 | 28 (29 hidden backup) | Milind | Reveal. Six tests covered one privilege rule; three intent clauses remain unresolved. Screening scores and workflow cost are distinct measurements. |
| 51–55 | 30 | Both | Record evidence that permits recovery, who can lift controls and what triggers rollback. |
| 55–58 | 31 | Both | Compare the illustrative paper record; tables score with REVIEW-SCORECARD; ask each person for one work action, an owner and a verification step. |
| 58–60 | 32 | Both | Resources and repository; Q&A. |

## Four case probes

| Case | Ask | Look for |
|---|---|---|
| A: library update and egress | What happens to an already-running compromised workload? | Admission versus live traffic; identity and exact egress paths; evidence before replacement. |
| B: support assistant and tools | Does removing token automount remove every credential or tool authority? | Projected credentials, workload identity and application-tool access examined separately. |
| C: unapproved replica changes | Does a ticket annotation prove an authorized approval? | Approval provenance and effective requester permissions. |
| D: cross-namespace Secret reads | Which control can stop a Secret read? | RBAC and credential response with an explicit GET/LIST test; no admission-policy claim. |

Accept different answers when the scope, evidence, owner and service constraint are explicit. Ask what would falsify the decision. A pause can be correct when the required check is absent.

## Demo boundaries and fallback

The local reference command compiles supplied source and runs offline fixture tests. It does not invoke a hosted model, open a pull request or apply to a cluster. Run it only after `demo.py --check` returns `ready: true` with Kyverno CLI 1.19.1. If preflight fails, stop troubleshooting and show hidden slides 33–34 as dated fixture results. Do not describe recorded observations as fresh execution. Never expose environment files or API credentials.

## Five-minute catch-up plan

Use only if the minute-39 finding section starts at actual minute 44. Compress commentary, not the decision tasks: four prediction/reveal pairs at 45 seconds each (3:00), Case D comparison at 0:30, independent proposal review at 3:00, incomplete-coverage reveal at 0:30, recovery writing at 4:00, personal action and reports at 3:30, questions at 1:30 (16:00 in total, ending at minute 60; slide 29 stays hidden). Keep the independent review and recovery intact; move methodology questions to backup slides. This is a planned fallback, not a rehearsed result.
