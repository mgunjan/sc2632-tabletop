# Current SC2632 session package

Co-presenters: **Milind Gunjan and Vivek Mayuranathan**. October 26, 2026, 4:30–5:30 PM Mountain Time. Four selectable incident cases, timed decisions, sealed evidence and a written containment review.

The opening begins with an incident and the decision participants own: a concrete Case A illustration, uncertain exposure, operating services and the evidence needed before tightening controls. Environment definitions follow that situation. Slide 5 states what co-presenters provide and what tables do. The supplied-spec demo is explicit; the policy agent is distinguished from the case agents. Four case choices, 29 main slides, six backups and the six-minute setup remain.

The lab discussions now supply technical facts before asking for a response and confirming test. The temporary-access round asks for a defended choice before its conditions are discussed. Slide 28 traces an [illustrative Case A decision record](../../tabletop/congress-2026/WORKED-DECISION.md) from initial intent through later evidence and recovery. This is a paper plan, not executed containment or the only acceptable answer. Model measurements remain historical candidate screening; production selection still needs error-cost and reviewer-effort evidence.

The session also supports attendees new to Kubernetes. The opening explains the shared application platform and familiar functions before naming Pods, replicas, namespaces and workload identities. Scenario choices, availability and the recorded-removal question use plain-language equivalents. Participants can state observable security behavior and acceptance evidence without naming products or writing code. Scoring assesses the decision, not platform vocabulary.

Slide 4 introduces the control roles upfront: Falco and audit logs supply detection evidence, Kyverno checks proposed changes, separate traffic/API/tool controls constrain access, and people authorize containment and recovery. Its visible disclosure distinguishes validated Falco rules from unverified live detection. The exercise supplies incident alerts; the common demo compiles proposals and runs policy tests. The participant primer and co-presenter wording match this boundary.

| Material | Use |
|---|---|
| [SC2632-session-four-cases.pptx](SC2632-session-four-cases.pptx) | Current editable deck: 29 main slides and six hidden backups |
| [SC2632-session-four-cases.pdf](SC2632-session-four-cases.pdf) | All 35 slide visuals, including backups |
| [CONTROL-REVIEW.pdf](CONTROL-REVIEW.pdf) | Two-page trained-model proposal exercise; keep page 2 sealed until decisions are recorded |
| [Participant pack](PARTICIPANT-PACK.pdf) | Four selectable cases, worksheets and two sealed injects; eight pages |
| [Review scorecard](REVIEW-SCORECARD.pdf) | Twelve core review criteria plus three evidence criteria for the proposal review |
| [Session runbook](../2026-10-12/SESSION-RUNBOOK.md) | Hour, print order, handoffs, demonstration and fallback |
| [Co-presenter cards](../../tabletop/congress-2026/CO-PRESENTER-CARDS.md) | Prompts, evidence requirements and time-pressure cuts |
| [Rehearsal record](../../tabletop/congress-2026/REHEARSAL.md) | Executed checks and pending venue/human release work |
| [REVIEW.md](REVIEW.md) | Real local training, classical baselines, recording-integrity corrections and control-library scope |
| [TRAINING-PROTOCOL.md](TRAINING-PROTOCOL.md) | Frozen local training procedure and split boundaries |
| [Control library](../../controls/README.md) | Ten stable IDs, implementation bindings, coverage limits, owners, tests and rollback |
| [Enterprise qualification](../../controls/ENTERPRISE-QUALIFICATION.md) | Independent labels, platform evidence and release requirements |

The current review replaces the old three-question model-choice bonus during minutes 45–49. It uses the actual trained-model proposal, six passing privilege tests and the independent ledger's incomplete coverage. Teams justify a bounded approval, revision, escalation or rejection and name the missing evidence. The original model-choice handout remains optional backup material.

The model pilot supports a bounded discussion, not a model-family winner. The trained Laya candidate is not a stage default. Historical Jev/Claude/zero-shot results retain their original inputs; OpenAI has no authenticated result. Use reference compilation or authentic replay for the dependable proposal demonstration, and use only the separately rehearsed disposable lab for actual enforcement.

The local [live-rehearsal evidence](live-rehearsal/README.md) records actual enforcement separately from model and fixture evidence. Case D now has an [executed synthetic RBAC/network/credential record](live-rehearsal/case-d/README.md): Pod quarantine leaves the copied credential usable, narrowing RBAC denies outside reads while retaining named dependencies, and deleting the old bound Pod invalidates its credential after a clean replacement is ready. Native PowerPoint/projector inspection and a full human co-presenter rehearsal remain required. The separate public source release is authorized and verified. The repository's visibility is unchanged. Earlier source packages and submitted copies remain preserved under October 12.

The curated local `ATTENDEE-SOURCE-KIT.zip` has a [start-here guide](../../tabletop/congress-2026/ATTENDEE-START-HERE.md), current materials and reproducible source without repository history or credentials. All three reference proposals and the authentic Jev replay ran successfully from an extracted source copy; each retains human review. The authorized curated source is now public at [mgunjan/sc2632-tabletop](https://github.com/mgunjan/sc2632-tabletop). Start with its README for the no-key reference demo. The full presenter source export remains `../2026-10-12/SESSION-KIT.zip`.

The delivery revision clarifies scoring of written plans, justified refusals and held authority. Co-presenters have [case-specific scoring anchors](../../tabletop/congress-2026/SCORING-ANCHORS.md) and a [blank human rehearsal record](../../tabletop/congress-2026/REHEARSAL-RECORD.md). These are preparation materials; scoring calibration and the full human hour remain unperformed.

The [October 14 demo audit](../2026-10-14/README.md) records a fresh prepared Jev fixture run, an explicit CLI-path option and a requirement-visibility repair. It does not qualify arbitrary audience intent or replace the human rehearsal.
