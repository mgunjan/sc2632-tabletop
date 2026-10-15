# SC2632 co-presenter runbook

## The insight the audience should test

**A model decision, a policy test and an operational outcome are different evidence.** A valid policy can omit the required control. A passing fixture suite can miss an API path. An approved control can break recovery. Each round asks the table to identify which evidence is still missing before granting authority.

This makes the session useful across roles. Platform engineers leave with negative-test ideas and protected policy-engine identities. Incident responders leave with evidence/containment ordering and capacity checks. Governance and leadership participants leave with verified approval, scope, expiry and recovery criteria. Everyone produces an intent-to-control coverage record and a decision they can defend.

The exercise takes place on a shared production Kubernetes platform. The affected service remains operational and the extent of compromise is uncertain. Teams document scoped containment, essential dependencies, evidence and recovery authority. Workload names are retained from the fixtures for traceability. The model comparison supports discussion of delegation and review requirements; it does not establish a preferred model class.

## Materials and room mechanics

- Use ../2026-10-13/SC2632-session-four-cases.pptx and ../2026-10-13/PARTICIPANT-PACK.pdf. The deck has 29 main slides and six hidden backup slides, with timed speaker notes. The original submission copy is retained. Slides 24-25 now use the recorded trained-model proposal review, and the cost backup is hidden. Use tabletop/congress-2026/CO-PRESENTER-CARDS.md for prompts and tabletop/congress-2026/REHEARSAL.md for release checks.
- Print one ../2026-10-13/REVIEW-SCORECARD.pdf per table; use 12 core points plus up to three independent-review points. The rubric rewards defended evidence, not the strictest quarantine level.
- Print two copies of participant pages 1-5 per table and one or two copies of page 6 (worksheet). Print two copies of page 7 behind a sealed "Round 3" cover, and two copies of page 8 behind a sealed "Later finding" cover. All four cases remain available for team choice.
- Use the existing tabletop/print/vote-cards.pdf if wanted, or let a table lead speak its vote. Print two copies of ../2026-10-13/CONTROL-REVIEW.pdf page 1 per table and one copy of page 2 behind a sealed review-findings cover. Keep MODEL-DECISION-REVIEW.pdf as an optional backup exercise. The independent review needs a written disposition and acceptance evidence; no external polling system is necessary.
- The original table-01 through table-12 envelopes and old room clock assume assigned A/B/C cases. Do not combine their assignment instructions with the new four-choice pack. The new kit is a separate coherent session variant.
- Milind Gunjan and Vivek Mayuranathan co-present. Share the briefing, demonstration and debrief; alternate table support during exercises. Allow 45 minutes for setup if the venue permits, as the organizer described. Use a separate countdown timer and the runbook below; the old screen has different segment timing.
- The authorized curated source and downloads are public at https://github.com/mgunjan/sc2632-tabletop. The original project retains its private visibility. Slide 29 and the participant footers display the public address. Use the public README for the no-key take-home demo; preserve sealed-evidence timing in the room.

## The hour

| Minutes | Slides | Activity and observable output |
|---|---|---|
| 00-06 | 1-7 | Incident context, participant assignment, materials and round sequence; choose a case/constraint, assign roles and open page 6 |
| 06-10 | 8 | Team writes intent and a preserved dependency |
| 10-13:30 | 9-11 | Explain typed decisions, demonstrate reference compiler, show missing coverage |
| 13:30-18 | 12 | Team reviews proposal and writes APPROVE/MODIFY/REJECT/ESCALATE with one reason |
| 18-22 | 13 | Team verifies exception authority, scope, owner and expiry |
| 22-26 | 14 | Select rollout mode per control and promotion criteria |
| 26-34 | 15-16 | Explain levels briefly, open page 7 and write ordered containment |
| 34-38 | 17 | Open page 8, keep original decision visible and revise it |
| 38-44 | 18-22 | Use supplied facts to choose a response/test; reveal four recorded consequences |
| 44-45 | 23 (32 optional) | Compare cases, read one locked D prediction and reveal its separate lab evidence |
| 45-48 | 24 | Review the recorded trained-model proposal; lock scope, owners and evidence |
| 48-49 | 25 | Open the sealed findings and defend the authority granted |
| 49-50 | 26 | Compare historical model quality and measured cost/time per run |
| 50-54 | 27 | Write exit criteria and recovery authority |
| 54-60 | 28-29 | Trace an illustrative decision through new evidence; personal action, resources and questions |

## The first six minutes

Slide 2 begins with a concrete Case A illustration: unexpected payments connections after a library update while services remain operational and exposure is uncertain. It gives the participant decision and required output before terminology. Other cases remain alternatives. Slides 3–4 explain the shared environment and Kyverno. Slide 5 states what co-presenters provide, what participants write/review and that the common demo uses a supplied spec. Slide 6 preserves case choice; slide 7 remains visible for the final setup minute. Detailed wording is in CO-PRESENTER-CARDS.md.

Milind leads purpose, environment and operating constraints. Vivek leads Kyverno, the participant assignment and case choice. The cover takes twenty seconds, purpose fifty seconds, environment and Kyverno forty seconds each, and assignment forty-five seconds. Case choice gets seventy-five seconds. Constraint explanation takes thirty seconds followed by a full minute of setup writing, preserving the six-minute opening. Both check table readiness. Keep scoring detail on paper and later evidence sealed. A ready table can explain the intended output and security purpose, then name its case, roles, constraint and minimum service. It can distinguish refusing a new request from responding to an existing workload.

Assume some attendees have no Kubernetes experience. Start with the platform's job and familiar functions, then give the technical term: application copies/replicas, resource groups/namespaces, workload identity/ServiceAccount. Define the management API, admission and voluntary removal before using them in a question. Accept behavioral security requirements without product names. The existing score is for justified decisions and evidence, not syntax or glossary recall.

## The independent proposal review

Use ../2026-10-13/CONTROL-REVIEW.pdf. Vivek opens the task; Milind displays the recorded proposal. Give tables three minutes to record a disposition, outstanding requirement/owner, acceptance evidence and rollback condition. A team may justify a reviewed, bounded subset while escalating the remaining exposure. Keep page 2 sealed until choices are recorded.

At 48 minutes reveal the independent ledger: INCOMPLETE_PROPOSAL. The six fixed privilege CREATE tests pass, but the model chose a privilege control for the network requirement and the rollout/expiry requirement. Kubernetes API access remains unresolved. Ask one table to defend its authority decision and identify the actual CNI, RBAC or operations owner. Award up to three independent-review points for limited test scope, enforcement owner/evidence, and a justified authority boundary. These replace the old model-choice bonus; they do not add points or minutes.

The scores were recorded after a local Laya head fine-tune on 480 synthetic examples. Separate synthetic calibration did not establish reliability for the incident cases. The runtime-order 33-choice regression result stayed 16/33; the cutoff accepted 21 trained answers with six wrong, versus two accepted base answers. The reviewed workflow takes median 0.975 seconds but remains incomplete. No API charge; local compute unpriced. This example was selected after failure for teaching, not a controlled human-versus-model benchmark.

At 49 minutes show the historical Jev/Claude/zero-shot-Laya comparison for one minute. It uses its unchanged frozen inputs and option order. Jev 30/33 versus Claude 32/33 is inconclusive (paired p=0.50). Their three-run proposal medians were 1.82 seconds/$0.000191 and 24.18 seconds/$0.037952. Zero-shot Laya's 0.41-second workflow generated no guardrail. These exclude human review and deployment. Keep historical and trained configurations separate. OpenAI has an offline-tested adapter but no authenticated result.

The optional original three-case expert challenge remains available in MODEL-DECISION-REVIEW.pdf for Q&A or a separate practice run. It does not run in addition to the new review during this hour. Preserve its label disputes and raw-score/delegation distinction.

The [reference control library](../../controls/README.md) supplies stable IDs, coverage limits, test references, owners, proposed exception limits and platform evidence requirements. Model selection, policy behavior and containment coverage require separate evidence.

## Dependable compiler demonstration

Run from the repository root in an environment with PyYAML, jsonschema and Kyverno CLI 1.19.1. Use the durable .venv-session environment and the locally verified Kyverno CLI. Run the commands with that environment on PATH; missing PyYAML now fails preflight before live mutations.

```bash
python3 tabletop/congress-2026/demo.py --check
python3 tabletop/congress-2026/demo.py --mode reference --scenario a --out output/congress-2026/reference-demo-01
```

Open proposal/PR.md, readiness.json and provenance.json under the chosen fresh output directory. Say **"The supplied spec is a reference answer. The compiler and admission simulation run now."** Ask teams to predict whether the proposal is ready before showing the missing RBAC clause, one generated policy, the six independent privilege tests, backup-job's WOULD BLOCK, the owner/24h example exception and the stage directories. The result is a local review proposal, not a GitHub PR opened automatically. REVIEW_REQUIRED explicitly retains human disposition and disables automatic promotion.

For the presenter’s live enforcement segment, rehearse a dedicated lab before the venue. A human applies the reviewed privilege policy and demonstrates server-dry-run rejection of a privileged Pod alongside admission of a compliant Pod. The hardened original launcher now uses generator/demo_gate.py rather than health alone. The frozen Strands model still fails; code remediation has not changed its score or granted live eligibility. For the default demonstration use the bounded reference compiler or authentic replay. The presenting-Mac disposable lab rehearsal is recorded separately in ../2026-10-13/live-rehearsal/. Keep the proposal command distinct from lab enforcement.

The original standalone situation display is tabletop/deck/anim/situation.html. It is a redrawn lab recording, not a new live model or cluster result. The new submission deck uses static lab question images with explanatory notes, so it works without embedded video playback. Supply the visible technical facts before asking for a response and confirming test, then reveal each recorded observation. These discussions are ungraded and do not depend on recall of Kubernetes semantics. Use the animated display only after local browser and projector rehearsal.

## Debrief probes

| Case | Probe | Useful consequence |
|---|---|---|
| A | Did the PR implement the whole intent, and is the compromise limited to one Pod? | Add an explicit coverage gate and validate all affected replicas; preserve evidence before replacement. |
| B | Can admission see the unsafe tool call, and whose identity does the assistant use? | Repair tool/input authority and identity scope; an approved image does not establish safe tool behavior. |
| C | Did the guardrail stop the agent, or merely change who executes its request? | Verify the human approval path and narrow standing RBAC; freeze needs an authority boundary the agent cannot alter. |
| D | Would a network quarantine stop a credential used elsewhere? | Revoke/narrow authorization, identify exposed credentials and coordinate rotation with availability. |

During Round 3, D tables lock a copied-credential prediction before minute 34. At 44–45 read one original prediction and reveal the status-only October 13 lab result (backup 32 or transcript). The old token still reads synthetic Secrets after Pod network quarantine; narrowing its broad binding denies outside reads while preserving one required named Secret GET. Replacement and old bound-token revocation are tested separately. Stand-in health is not production metrics delivery, and external application-key rotation remains required. If no table chose D, collect an ungraded prediction before displaying slide 23, then compare it with the separate lab record. This replaces part of the existing case comparison; it adds no minutes or main slides.

The review examines assumptions about: intent coverage, API subresource, shared identity, human approval, additive network allows or recovery capacity. Ask tables to name the boundary, the evidence that checks it and the owner who can authorize crossing it.

## Before October 26

The gate mismatch and confidence validation are remediated. The agent writes staged manifests, provenance, a prepared-intent requirement ledger and focused independent privilege tests. Every requirement still needs human disposition; no deployment approval is implemented. Keep frozen evaluation labels unchanged and collect independently reviewed, held-out incidents. The presenting-Mac lab now has actual e2e evidence; exception lifecycle evidence is separate. Case D now has a separately executed synthetic RBAC/CNI/credential record. Finish the human hour and native display check; authorized public source distribution is verified. See the October 13 evidence and RUNTIME-REMEDIATION.md for their distinct scopes.

## Review rubric and demonstration choice

Use ../2026-10-13/REVIEW-SCORECARD.pdf: 12 core points plus up to three independent-review points. Require a written reason/evidence for each point; a co-presenter checks a sample using tabletop/congress-2026/SCORING-ANCHORS.md. Score acceptance evidence specified in the paper plan. Holding unverified authority earns credit; do not require or reward invented approvals or executed outcomes. The bonus evaluates test scope, enforcement owner/evidence and justified authority. A defensible bounded approval or escalation can earn points; there is no required vote. For equal scores, compare the evidence each team would require to revise the containment plan. At 54–55 use slide 28 and tabletop/congress-2026/WORKED-DECISION.md to trace an illustrative Case A paper plan through new evidence and recovery tests. At 55–57 tally points, hear two short reports and document a requirement, owner and verification step in each participant’s environment. The example is not executed containment or the required answer.

Best default for this submission: reference-spec compilation and fixture admission, with recorded model runs available for replay. The recorded Jev/Claude outputs and failed local-model outputs are authentic; label them as recordings. The isolated presenting-Mac lab has actual e2e evidence; repeat preflight on the day. A reviewed server dry-run can demonstrate admission with a positive control and rollback plan. Venue networking, projector and human delivery remain separate checks.

Optional live AI segment: use Jev on the prepared Scenario A, show its local proposal and the four dependency escalations, then show the independently tested reference artifact. This is a bounded non-deploying proposal demonstration. Claude can offer a second proposal or interpretation, but is not a calibrated automatic fallback; Laya is a useful fast-but-incomplete comparison, not the default enforcement demo. Avoid arbitrary audience intent driving enforcement and avoid the original health-only Decider live path.

A one-run Jev rehearsal can use a fresh run tag; the script refuses existing output rather than overwriting evidence:

```bash
python3 tabletop/congress-2026/demo.py --mode jev --env-file .env.jev --out output/congress-2026/jev-live-demo-01 --deadline 15
```

The script runs fixture-based proposal generation, not cluster deployment. Open proposal/PR.md and the policy files under the chosen output directory. If the deadline expires, stop and use the pre-opened reference artifact or prepared slides. Use the verified public source and downloads for attendee resources.

## Current professional framing

Use tabletop/congress-2026/INCIDENT-BRIEF.md as the current incident context. The original financial story, assigned three-case envelopes and room clock are legacy materials. Retain all frozen benchmark wording and labels, including the earlier business context, as historical inference evidence. Do not rewrite recorded results to match the workshop narrative. The review rubric evaluates documented reasoning; it does not certify security or reward the most restrictive posture.
