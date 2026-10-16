# Human delivery rehearsal record

Blank record for Milind and Vivek. This file does not establish a completed rehearsal. Use a real 60-minute run with at least a general security reviewer and a Kubernetes reviewer when available. Capture their written decisions rather than substituting presenter narration for participation.

Date/time: __________  Participants: __________  Display/room: __________

| Artifact or handoff | Target minute | Actual minute | Evidence or adjustment |
|---|---:|---:|---|
| Assignment understood; case, constraint and roles recorded on page 6 | 11 | | |
| Intent and preserved dependency written | 15 | | |
| Proposal disposition and missing test written | 19 | | |
| Exception authority/expiry and rollout criteria written | 26 | | |
| Original containment plan retained | 34 | | |
| Revision or defended hold tied to new evidence | 38 | | |
| Recorded consequences compared with predictions | 45 | | |
| Independent proposal disposition recorded before reveal | 48 | | |
| Recovery criteria and lifting authority written | 54 | | |
| Personal action, owner and verification recorded | 58 | | |
| Questions and closing complete | 60 | | |

## Evidence of participation

After slide 2, ask a reviewer to explain the shared-platform security problem and intended change set. After case selection on slide 11, ask them to explain their case's uncertainty, the service constraint and the decision they own: __________

Before Round 1, ask a general security participant to explain the assignment without presenter help: which case the table chose, which record it must complete, what it decides, and what stays sealed. Their answer and any correction: __________

Ask someone unfamiliar with Kyverno: “If the policy refuses a new Pod, what happens to the already running Pod?” Record their explanation of the environment and the need for a separate response: __________

After slide 4, ask: “Which component detects activity, which checks proposed changes, and who authorizes containment? Are the incident alerts live Falco observations?” Record whether the participant identifies the supplied alerts and the compiler/test demo without treating rule validation as live detection: __________

Ask someone unfamiliar with Kubernetes to explain the platform's job, what an application copy is, and their team's task in ordinary security language. Record one intent and its acceptance evidence without requiring product terminology: __________

Record at least one concern stated by the independent reviewer: __________

Record one differing decision defended by another table: __________

Before case selection, after slide 9, ask what exact text a hosted model sees, what an uncertain dependency does, which actions the harness executes, who deploys, and whether Falco activates Quarantine automatically. After the walkthrough on slide 7, also ask whether audience prose was model input: __________

During slides 20–23, record whether the supplied facts let a general security reviewer propose a response and test without guessing unfamiliar platform semantics: __________

After slide 29, ask a reviewer to trace one requirement through the original decision, new evidence, revision and recovery test: __________

Record a phrase that confused the general security reviewer: __________

Record one assumption challenged by the Kubernetes reviewer: __________

Score a cautious refusal and a bounded approval using SCORING-ANCHORS.md. Differences in criterion interpretation and resolution: __________

Did any team claim that an unexecuted verification had passed? Correction: __________

## Delivery failure drill

Perform these as a separate short drill after the timed hour. Keep the prepared proposal/PDF open. Preserve failed command output; do not promote partial evidence.

| Condition | Required observed response | Result and timestamp |
|---|---|---|
| Compiler/demo unavailable | Move immediately to the prepared artifact and identify it as prepared | |
| No table chooses D | Collect an ungraded prediction before slide 24 is displayed, then use the separate D record | |
| Scheduled minute 38 starts at actual elapsed minute 43 | Execute the five-minute recovery plan in CO-PRESENTER-CARDS.md; preserve writing and recovery tasks | |
| Forceful reviewer disputes a score | Point to the written criterion and acceptance evidence; preserve a justified hold/refusal | |
| Native display | Inspect notes, hidden slides, tables and readable terminal on the target display | |

Decision: ready / revise / repeat. Required fixes and owner: __________

Neither a completed record nor a passing code test alone establishes that the venue display or the participants’ learning outcomes have been verified.
