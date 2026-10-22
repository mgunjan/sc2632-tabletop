# Technical briefing before case selection

Milind Gunjan and Vivek Mayuranathan explain the implemented paths before attendees choose a scenario. Slides 2–3 establish the premise, why the fictional payment API makes availability concrete, the unknowns, the agenda and participant output. The visible technical briefing then uses slides 5–7 and 9–11 to introduce the shared platform, detection sources, decision loop, model data, compiled request scope, independent review contract and Quarantine Mode mechanisms; slides 4 and 8 are hidden reference backups. Case selection starts at minute 9; intent writing starts at minute 12. These are planned timings; the full human rehearsal remains outstanding.

## Implementation and trust boundaries

| Boundary | Implemented behavior | Source |
|---|---|---|
| Detection | A/B syscall rules pass validation. The C audit plugin also passes 14 authored synthetic webhook cases, with subject-based association and separate evidence-gap warnings. Actual cluster delivery and kernel detection remain unverified. Supplied fictional alerts inform the exercise; the policy-agent harness does not ingest Falco. | `runtime/falco-rules-syscall.yaml`, `runtime/falco-rules-k8saudit.yaml`, `submission/2026-10-16/README.md` |
| Orchestration | Python fixes the sequence: map clauses, observe inventory, judge dependencies, render/test, review blocked workloads, write a proposal. At most three render/test rounds. This is the project's harness, not model-selected arbitrary tool execution. | `generator/policy_agent.py:Agent.run` |
| Model input | Control question: clause and full intent. Dependency question: intent, profile and workload names. Block question: intent, workload, policy and up to 300 characters of the denial reason. Hosted adapters transmit those task strings. The presenter uses synthetic fixtures. | `generator/decider_agent.py:_state`, `generator/policy_agent.py:Agent.run`, `submission/2026-10-12/benchmark/provider_clients.py` |
| Model output | Listed choice and a finite numeric score in [0,1]. Unreadable choices or scores below 0.6 escalate. The cutoff is uncalibrated for production deployment risk. | `generator/decision_contract.py:parse_answer`, `generator/policy_agent.py:Agent.decide` |
| Uncertainty | An escalated control clause enables no control. An uncertain dependency retains its proposed profile allowance and flags human review. Only egress-profile allowances can widen in the proposal loop; other widening becomes a human request. These defaults have different availability and exposure implications. | `generator/decider_agent.py:fill_spec`, `generator/policy_agent.py:Agent.run` |
| Compiler | Code fills and validates the spec, renders fixed templates and writes Audit/Warn/Deny stage artifacts. A model does not supply free-form policy YAML in this path. Catalog 0.1.0 has ten entries and seven admission template bindings, with explicit other-layer/process handoffs. | `generator/generate.py`, `controls/catalog.json` |
| Covered behavior | `ACG-POD-001` produces a Kyverno `ValidatingPolicy` for Pod CREATE in payments, aggregating regular and init containers. It requires `privileged=false` and explicit `allowPrivilegeEscalation=false`. It does not implement every Pod Security restriction or stop existing workloads. | `generator/generate.py:t_privesc`, `output/frozen-a/policies/deny-privilege-escalation.yaml`, `controls/catalog.json` |
| Independent checks | The prepared-intent contract, actual input binding and six fixed privilege CREATE expectations accompany the proposal. New intent requires a new independently reviewed contract. A narrow PASS can leave the overall proposal REVIEW_REQUIRED or INCOMPLETE_PROPOSAL. | `generator/policy_contracts.py`, `generator/contracts/requirements.json`, `generator/contracts/privilege-test.yaml` |
| Deployment | The presenter wrapper uses fixtures, makes no kubectl call and opens no GitHub PR. It writes local PR.md, stage files, tests, readiness, provenance and decisions. It does not deploy or approve exceptions. Human application and IAM isolation are separate controls. | `tabletop/congress-2026/demo.py`, `generator/policy_agent.py:Agent.open_pr` |

The core agent CLI has an optional kubeconfig-backed Pod GET path; that is separate from the bounded presenter wrapper. Omitting deployment actions from code does not create a credential sandbox. Operators must separately enforce read-only observation, protected review artifacts and the deployment principal's authority. Task text, workload names and denial messages can be provider-visible data. A typed response alone does not establish correctness or resistance to hostile context.

## Quarantine implementation

Quarantine Mode is a coordinated project-defined posture, with no automatic Falco-triggered controller. An operator applies reviewed manifests and performs identity/evidence steps separately.

| Level | Concrete mechanism | Authority or scope boundary |
|---|---|---|
| Q0 | Reviewed baseline policies and approved traffic rules | Establish legitimate service paths |
| Q1 | Native API-server `ValidatingAdmissionPolicy` freezes writes by identities in the agents namespace; additional gate on new policy exceptions | Other namespace identities and controller-mediated actions require separate review |
| Q2 | NetworkPolicies, protected labels, evidence capture and manual RBAC narrowing | A network manifest does not perform identity revocation or suspend application tools |
| Q3 | Suspect isolation selection, deny-all traffic rule and payments Pod CREATE gate | Reviewed override requires incident-commander annotation and requester group; preserve evidence and clean serving capacity |

Sources: `quarantine/q1/`, `quarantine/q2/`, `quarantine/q3/`, `quarantine/quarantine-mode.md`. Positive/negative traffic and authorization checks, controller readiness and recovery criteria are control-specific. Rule validation, fixture simulation, actual lab observation and venue rehearsal remain distinct evidence.

## Briefing and exercise timing

| Minutes | Slides | Purpose |
|---|---|---|
| 00–03:30 | 1–3, 5–6 | Conflict, premise, agenda, platform map and control roles (slide 4 hidden backup) |
| 03:30–05:30 | 7 (8 hidden backup) | Decision loop, model data and authority |
| 05:30–07:15 | 9–10 | Concrete compiler walkthrough and whole-intent review contract |
| 07:15–08:15 | 11 | Quarantine implementation |
| 08:15–09:00 | 12 | Paper workflow, table roles and sealed pages |
| 09:00–10:15 | 13 | Choose one prepared incident case |
| 10:15–12:00 | 14 | Select operating constraint and service floor |
| 12–16 | 15 | Write intent and preserved dependency |
| 16–20 | 16 | Review proposal |
| 20–23 | 17 | Decide temporary access |
| 23–27 | 18 | Select rollout and promotion criteria |
| 28–35 | 19 | Open page 8; write ordered containment |
| 35–39 | 20 | Open page 9 and revise or defend the plan |
| 39–40 | 21 | Collect four quick hands-up predictions; do not discuss yet |
| 40–41:15 | 22 | Reveal additive DNS allowances and verification tests |
| 41:15–42:30 | 23 | Reveal voluntary PDB eviction and the replacement stall |
| 42:30–43:30 | 24 | Reveal the ephemeral-container subresource boundary |
| 43:30–45 | 25 | Reveal the policy-engine failure and native guard |
| 45–46 | 26 | Compare Case D prediction with its recorded synthetic observation |
| 46–51 | 27–29 | Independent model-proposal review and measured comparison |
| 51–60 | 30–32 | Recovery, worked debrief, transfer and questions |

The validated v20 deck has 38 numbered slides: 29 visible slides and nine hidden slides (4, 8, 29, 33–38). Slides 4 and 8 are reference backups, slide 29 is the model-cost Q&A backup, and 33–38 are technical/demo backups. Minute 27–28 is a transition buffer: unseal participant page 8 at minute 27, then begin the decision round on slide 19 at minute 28. Slide 21 stays projected from 39:00–40:00 while all four predictions are collected; reveal results on slides 22–25 over 40:00–45:00. Later finding details and the trained-model exercise answers stay sealed until their reveal times. The technical briefing supplies the mechanics needed to assess those findings without exposing their particular outcomes.
