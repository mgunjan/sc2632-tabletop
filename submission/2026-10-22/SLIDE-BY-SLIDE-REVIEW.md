# SC2632 room-read review

Reviewed against `SC2632-session-dayof-review-v11.pptx`, all 38 rendered slides, and the embedded notes on October 22. The first 32 slides are the timed session; 33–38 are hidden backups. The deck tells participants what environment they face, what they must decide, what the controls can and cannot prove, and how to leave with an actionable playbook. Slides 4 and 28 use original generated illustrations; slide 5 uses a neutral, source-authored platform diagram. No supplied meme photo is included.

| Slide | What the room sees / does | Review and claim boundary |
|---:|---|---|
| 1 | Session title and purpose | Strong visual opening; no technical outcome is promised before the exercise. |
| 2 | Case-agnostic incident premise | Establishes the common fictional platform, three-copy/two-healthy service floor and why the fictional payment setting makes that tradeoff concrete, what is known, and what remains unknown until teams select a case. No suspect is identified early. |
| 3 | 60-minute agenda and participant output | Shows the briefing, decision rounds, evidence reveal, model challenge, recovery and take-home action. States what the shared Decision Record must contain and that no laptop or Kubernetes experience is required. |
| 4 | Two AI shifts; generated workload/copilot illustration | Distinguishes AI agents operating as workloads from a separate policy-writing copilot. The generated image is conceptual, not evidence. |
| 5 | Shared platform and neutral cluster map | Defines Pod, namespace and workload identity, shows three payment Pods and the separate API, RBAC, Kyverno and DNS boundaries. The map no longer names a suspect before case choice. |
| 6 | Detect, admit, contain, authorize | Defines Falco runtime rules and API audit logs. Visible boundary states that live capture, API-server delivery and alert-to-response were not exercised. |
| 7 | Four-zone policy-agent architecture | Separates model selection from Python-controlled YAML, tests and review bundle. |
| 8 | Data, trust boundaries and uncertainty | Explains model inputs and fail-open/fail-closed behavior; no raw Falco log ingestion is implied. |
| 9 | One intent clause compiled to a control | Shows a concrete policy and admission fixtures; makes clear this is one clause, not complete incident containment. |
| 10 | Whole-intent clause ledger | Exposes unmet network, RBAC and exception/rollout needs. Green checks do not close omitted requirements. |
| 11 | Quarantine Mode Q0–Q3 | Defines the graduated posture and operator authority; identity/RBAC steps are manual and cover both binding types. |
| 12 | How the workshop runs | Names the three-step workflow, four table roles, no-participant-setup requirement and sealed pages. The demo box fits; it distinguishes local fixture checks from a live cluster and gives the recorded fallback. |
| 13 | Four prepared cases | Tables select a scenario and work from the participant pack; distinct incident narratives do not imply all are live-cluster incidents. |
| 14 | Availability, evidence, velocity, containment | Requires an explicit service floor so teams can defend tradeoffs instead of choosing controls in a vacuum. |
| 15 | Round 1: write intent | Participants draft prohibited behavior, identity, preserved dependency and release allowance before seeing model output. |
| 16 | Review the containment proposal | Teams classify approve, modify, reject or escalate; the checks and omissions are visible before locking the decision. |
| 17 | Urgent exception inject | Makes owner, scope, expiry and validation explicit under time pressure. |
| 18 | Audit, warn, deny | Participants must assign promotion modes and observable exit criteria; no automatic promotion is claimed. |
| 19 | Ordered containment | Requires evidence first, scope, service floor and declaring authority in the action order. |
| 20 | Mid-containment evidence change | Teams revise or defend their plan and preserve the prior decision for comparison. |
| 21 | Predict four operational traps | The room predicts before seeing recorded lab results; this is a knowledge check, not proof all cases were freshly run today. |
| 22 | Additive NetworkPolicy allows | Demonstrates why an added default-deny does not override another policy's allow. The DNS detail is consistent with UDP and TCP allowances in Q2. |
| 23 | PDB blocks a second eviction | Correctly describes a voluntary-disruption/capacity stall while Q3 blocks replacement, not a deadlock or permanent condition. |
| 24 | Debugging through a subresource | Clarifies the authorized debug-subresource path and its evidence footprint; avoid generalizing one lab configuration to every cluster. |
| 25 | Guarding the policy engine | Shows the native API-server guard surviving Kyverno scale-down; notes preserve documented gaps in what it protects. |
| 26 | Later findings and unresolved requirements | Distinguishes fictional case facts from recorded Case D evidence and later observations from established root causes. |
| 27 | Trained proposal / expert review | Audience is asked to review the proposal and identify unsupported clauses. Scores are routing signals, not safe-deployment probabilities. |
| 28 | Green tests versus missing coverage; generated “self-awarded pass” illustration | Reveals `INCOMPLETE_PROPOSAL`; exact scope is six tests on one rule with three intent clauses unresolved. The generated image is an analogy, not an actual model trace or test result. |
| 29 | Quality, time and cost comparison | Same-slide caveat keeps the 33-item screening pilot distinct from three-run workflow measurements and flags incomparable score signals. |
| 30 | Recovery exit criteria | Participants define proof, authority and rollback condition before closing quarantine. |
| 31 | Worked decision record and scorecard | Example is explicitly illustrative; attendees compare against their own revisions and choose a Monday action. |
| 32 | Open-source resource and transfer | Asks each participant to adapt a guardrail, dependency and verification test; managed-platform support is not claimed. |
| 33 | Hidden fallback policy excerpt | Use only if the fresh local reference is unavailable; clearly labeled supplied spec, not a live run. |
| 34 | Hidden offline fixture outcomes | Correctly labels these as fixture simulations, not runtime traffic, credential or API containment. |
| 35 | Hidden Case D copied-credential response | Synthetic October 13 record; 401 timing is the observed 41.2 seconds, not a bound or SLA. |
| 36 | Hidden training-fit versus task performance | Keeps the 99.69% synthetic fit gate separate from authored held-out exact-plan results and Claude's saved run. |
| 37 | Hidden operating cost model | Setup and reviewer time are unmeasured; the one-minute/$120 sensitivity is labeled illustrative. |
| 38 | Hidden complete pilot and workflow economics | Separates screening labels, workflow runs, local latency and estimated usage cost; warns against comparing unlike scopes. |

## Audience comprehension pass

| Persona | What they need to understand | Result after the v11 edits |
|---|---|---|
| Security leader new to Kubernetes | What is shared, what can keep running, and what decision belongs to the table | Slides 2–5 set the fictional platform, separate fixed facts from unknowns, show the agenda, define basic objects and service floor, and defer case choice to slide 13. No YAML or attendee setup is required. |
| Cloud security engineer | Which control blocks new requests, which stops live traffic, and which governs API access | Slides 6–11 separate detection, admission, network, identity and human approval, then show how the proposal is tested and where it remains incomplete. |
| Kubernetes platform engineer | Whether the operational sequence is technically bounded | The deck distinguishes admission from existing workloads, PDB voluntary eviction from direct deletion, and Q3 replacement stalls from deadlock. DNS, RBAC and system-namespace gaps remain explicit. |
| Principal security architect | Whether claims match evidence and authority | Live Falco integration is not claimed; fixture runs are separated from cluster enforcement; Case D stays a dated synthetic observation; scores are not deployment probabilities; reviewers retain authorization and recovery authority. |
| First-time tabletop participant | What to read, decide, write, and keep sealed | Slide 12 gives the paper workflow and sealed-page rules; slide 13 assigns one of four cases; slides 15–20 direct the shared record and preserve decisions before reveals. |

The opening works for mixed experience when Milind translates the platform terms on slide 5 aloud and Vivek pauses on the authority and trust boundary in slides 7–8. If presenters skip those notes, the later controls and test names become jargon-heavy for a first-time Kubernetes participant.

## Room-level delivery call

The opening now establishes shared facts, unknowns, the route through the hour and the expected written output before the technical map and control boundaries. The deck then moves from mechanisms to participant choices, evidence reveal, expert review and recovery. The biggest remaining experiential risk is not missing explanation in the slides; it is the uncompleted co-presenter rehearsal. Before presenting, rehearse the live local preflight, fallback transition, sealed-page timing and actual room display. Do not describe offline reference runs as fresh cluster enforcement or recorded results as fresh runs.
