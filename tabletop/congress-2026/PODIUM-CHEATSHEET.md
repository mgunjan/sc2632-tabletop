# SC2632 presenter field guide

**October 26, 2026 | 4:30–5:30 PM | Milind Gunjan and Vivek Mayuranathan**

## Opening: set the room before the exercise

**Milind, visible slides 1–3 and 5–6 (00:00–03:30).** Start with the operational conflict, then orient the room: one fictional shared Kubernetes platform, AI agents as workloads, and a separate copilot proposing controls. The payment API is a teaching scenario because it gives teams a concrete service floor (three copies, at least two Ready); the cases teach generic Kubernetes boundaries, not payment compliance. Nothing is assigned as the incident until teams choose on slide 13. Slide 4 is a hidden reference backup.

> “A green policy PR can still leave live traffic and API permissions exposed. Your table must decide what to stop, what to preserve, and what evidence would justify containment.”

Plain-language translations: a cluster is a shared platform; a namespace is a resource group; a Pod is a running workload; a replica is another copy; a ServiceAccount is a workload's Kubernetes API identity. Falco and API audit are detection sources; Kyverno checks proposed resources before they start; NetworkPolicy controls pod traffic; RBAC controls Kubernetes API actions. Each has a different boundary.

**Vivek, slide 7 (03:30–05:30).** Explain the bounded Python harness and its trust boundary. The model returns a typed choice; it does not deploy. Slide 8 is a hidden reference backup. **Milind, slides 9–10 (05:30–07:15).** Trace one supplied intent clause to a tested control, then point to the uncovered requirements. **Vivek, slide 11 (07:15–08:15).** Introduce Q0–Q3 as a human-declared posture, with verification per layer. **Both, slides 12–14 (08:15–12:00).** Orient the paper record, assign the case and roles, and set the operating constraint.

Falco boundary: rules passed static validation and audit-rule synthetic tests, but live capture, API-server delivery and alert-to-response are not exercised. The workshop does not integrate Falco with the policy copilot or automatically trigger quarantine.

## Minute-by-minute run of show

| Elapsed | Slides | Lead | What the room does |
|---|---:|---|---|
| 00–03:30 | 1–3, 5–6 | Milind | Set the stakes, why this scenario, what is known/unknown, platform map and control boundaries. Slide 4 is hidden. |
| 03:30–05:30 | 7 (8 hidden backup) | Vivek | Separate Python orchestration from model choice; explain inputs and trust boundary. |
| 05:30–07:15 | 9–10 | Milind | Follow one intent clause to a test; identify what it does not cover. |
| 07:15–08:15 | 11 | Vivek | Explain Q0–Q3 and the need for human authority and per-layer checks. |
| 08:15–12:00 | 12–14 | Both | Show pages 6–7, assign one case, name roles, choose a constraint and service floor. |
| 12–16 | 15 | Milind | Draft behavior to stop, identity, dependency to preserve and service floor. |
| 16–20 | 16 | Vivek | Approve / modify / reject / escalate; state one change and one missing test. |
| 20–23 | 17 | Milind | Review the exception: approver, exact scope, owner, expiry and revocation check. |
| 23–27 | 18 | Vivek | Set Audit / Warn / Deny per control and a measurable promotion test. |
| 27–28 | — | Both | Unseal page 8 at minute 27; allow the transition and begin decisions at 28. |
| 28–35 | 19 | Both | Use page 8; order evidence, containment scope, service floor and verification. |
| 35–39 | 20 | Milind | Open sealed page 9; revise or defend the plan and state which fact matters. |
| 39–40 | 21 | Milind asks / Vivek tallies | Keep slide 21 projected. Read all four concise setups and collect one hands-up vote each; tally, do not discuss. |
| 40–41:15 | 22 | Milind frames / Vivek runs | Separate prepared lab, Q1/Q2 staged. Run `./tabletop/consequences/play.sh 1-deny-all`; compare suspect DNS before/after isolation label. Report clean DNS/DB and Ready controls; no full-containment claim. |
| 41:15–42:30 | 23 | Vivek / Milind | Dated Oct 10: PDB counts Ready Pods, not trust. One eviction allowed at 3 Ready; Q3 blocks replacement; second denied at minAvailable 2. Direct deletion bypasses PDB. |
| 42:30–43:30 | 24 | Vivek | Dated Oct 10: reveal debug-subresource gap; ask who owns the missing test and which forensic image is approved. |
| 43:30–45 | 25 | Milind / Vivek | Dated Oct 10: reveal policy-engine failure and native Q1 guard; it protects matched writes, not all administrator actions. |
| 45–46 | 26; backup 35 | Vivek | Separate dated synthetic Case D observation; compare the locked prediction without generalizing the measured interval. |
| 46–49 | 27 | Both | Review CONTROL-REVIEW page 1; keep page 2 sealed. Name test scope, missing evidence and owner. |
| 49–51 | 28 | Milind | Reveal incomplete coverage; one rule passed 6/6 checks, three intent clauses remain unresolved. Slide 29 (model cost) is a hidden Q&A backup. |
| 51–55 | 30 | Both | Define recovery evidence, rollback criteria and who can lift each posture. |
| 55–58 | 31 | Both | Compare the illustrative record; score with REVIEW-SCORECARD; choose a take-home action, owner and verification. |
| 58–60 | 32 | Both | Resources and repository; Q&A. |

Keep decision pages sealed until the matching prompt. Hear no more than two 20-second reports per round. Credit a justified hold when evidence is missing; do not award points for maximum lockdown. The four roles are incident lead, recorder, evidence analyst and independent reviewer; combine roles for small tables. Both presenters circulate and facilitate; there is no separate floor facilitator.

For slide 22, call it live only if the launcher prints `LIVE` and `LIVE check complete`. If preflight fails and the launcher labels a dated replay, name it and continue. If it prints `LIVE check FAILED`, claim no result, do not troubleshoot, and use the dated slide evidence. A successful run leaves Q3 active; the operator re-stages the disposable lab after rehearsal.

## Offline reference demo and recovery

Participants need no laptop, YAML or Kubernetes experience. The offline reference path is separate from slide 22's live Q3 lab check. Run the local reference only when `demo.py --check` reports `ready: true` with Kyverno CLI 1.19.1. It compiles supplied source and runs offline fixtures; it does not call a model, open a PR or change a cluster.

Command, from the repository root, into a fresh directory each time (the session venv holds the Python packages and the verified Kyverno 1.19.1):

```
PATH="$PWD/.venv-session/bin:$PATH" .venv-session/bin/python tabletop/congress-2026/demo.py --mode reference --scenario a --out output/congress-2026/live-HHMM
```

If preflight or the demo fails, stop troubleshooting and use hidden slides 33–34 (in the slide show type `33` then Enter; `11` then Enter to return): “These are recorded fixture results, not a fresh cluster run.” Keep the room moving. Never show API keys or environment files. If five minutes behind at the recorded-finding section, use the compressed schedule in the co-presenter cards; preserve the independent review and recovery writing time.

Before calling room delivery verified, complete the 60-minute rehearsal with both presenters, sealed-page handoffs, fallback transition and venue display check. Those checks remain outstanding.

## Print list (12 tables + 2 spares)

- `submission/2026-10-22/PARTICIPANT-PACK.pdf`, single-sided, pages 8 and 9 folded closed (or in an envelope).
- `submission/2026-10-22/CONTROL-REVIEW.pdf`, page 1 and page 2 as separate sheets; page 2 face down until slide 28.
- `submission/2026-10-22/REVIEW-SCORECARD.pdf`, one per table (slide 31).
- Presenters: this field guide (`PODIUM-CHEATSHEET.pdf`) and the co-presenter cards.
