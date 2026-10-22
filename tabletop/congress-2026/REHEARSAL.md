# SC2632 rehearsal and demo release record

This is a rehearsal plan, not a claim that the venue setup has passed. The validated v20 deck has 38 numbered slides: 29 visible in the 60-minute run and nine hidden (4, 8, 29, 33–38). Slides 4 and 8 are reference backups, slide 29 is a Q&A backup, and 33–38 are technical/demo backups. v20 keeps v19's visuals and updates presenter notes. Protect the participant decision time in the runbook.

## Prepare a durable environment

Use Python 3.10 or newer in a project environment, and put Kyverno CLI 1.19.1 on PATH. The earlier `/tmp` environment is temporary and must not be your conference dependency.

```bash
python3 -m venv .venv-session
.venv-session/bin/pip install -r tabletop/congress-2026/demo-requirements.txt
.venv-session/bin/python tabletop/congress-2026/demo.py --check
```

The October 22 local preflight passes with the official Kyverno CLI 1.19.1 installed at `.venv-session/bin/kyverno`; its archive checksum was verified against the official release checksum and `kyverno version` reports 1.19.1. A fresh Scenario A reference run also completed locally in 1.30 seconds, with `REVIEW_REQUIRED` and automatic promotion disabled. This ignored local environment is not part of the attendee source kit. On this Apple Silicon Mac, restore it with the repository script below. The script verifies the pinned archive checksum before installation. On other platforms, install the official Kyverno CLI 1.19.1 release and verify that platform's published checksum, then require preflight to return `ready: true` before running the demo.

```bash
scripts/install-kyverno-cli.sh
PATH="$PWD/.venv-session/bin:$PATH" .venv-session/bin/python tabletop/congress-2026/demo.py --check
```

If the verified CLI is installed outside PATH, pass its executable explicitly using `--kyverno` on the reference, replay or optional live command. Preflight requires exactly version 1.19.1. The historical live-lab result remains recorded evidence; a fresh local reference run verifies the current source and fixtures but does not repeat Kubernetes enforcement.

The preflight is read-only and checks the interpreter, compiler dependencies and policy CLI. Reference/replay need no model, account, network or cluster. It does not verify PowerPoint, the projector, a CNI or actual Kubernetes enforcement.

## Run the prepared paths

Each output must be a fresh directory. The presenter command applies a whole-proposal deadline, preserves failed output as partial and never deploys or grants an exception.

```bash
PATH="$PWD/.venv-session/bin:$PATH" .venv-session/bin/python tabletop/congress-2026/demo.py --mode reference --scenario a --out output/congress-2026/reference-rehearsal-01
PATH="$PWD/.venv-session/bin:$PATH" .venv-session/bin/python tabletop/congress-2026/demo.py --mode replay --scenario a --out output/congress-2026/jev-replay-rehearsal-01
```

The reference uses the supplied spec, including its illustrative human-owned exception. The replay uses the recorded Jev answers; compilation, fixture simulation and six independent privilege checks run now. All security requirements still need human disposition. Current replay execution time is not historical model inference latency or a new cost comparison.

Prepare the contrasting recorded failure on a separate run. It is the authentic Strands result, with its missing privilege control made visible by the new ledger:

```bash
PATH="$PWD/.venv-session/bin:$PATH" .venv-session/bin/python tabletop/congress-2026/demo.py --mode replay --recording submission/2026-10-12/benchmark/decider-agent-a/agent-run.json --out output/congress-2026/strands-replay-rehearsal-01
```

Use this contrast in a separate rehearsal or backup discussion, with a prediction before revealing its result. The planned compiler walkthrough is 05:30–07:15 (slides 9–10) and shows one compiled control; keep the second workflow outside that slot. The main trained-proposal review remains at 46–49. Replay is recorded model inference with current compilation/tests; preserve the frozen results.

Optional live Jev proposal for a separate provider rehearsal or backup discussion. The planned opening retains the reference walkthrough:

```bash
PATH="$PWD/.venv-session/bin:$PATH" .venv-session/bin/python tabletop/congress-2026/demo.py --mode jev --env-file .env.jev --out output/congress-2026/jev-live-rehearsal-01 --deadline 15
```

Hosted inference can incur usage charges. Credential values stay off the projector and out of artifacts. No automatic hosted fallback occurs. Claude is available with `--mode claude --env-file .env.claude`; its recorded complete runs took longer, so budget an explicit rehearsal deadline up to 60 seconds. Do not extend the session's main demo to accommodate it.

Open the successful reference PR, `readiness.json` and `tests/result.txt` before presenting. The expected teaching observation is privilege behavior PASS alongside an unresolved RBAC requirement and human review. An incomplete proposal or failed test must stay visibly incomplete.

## Controlled failure drill

Rehearse with venue networking unavailable using reference and replay. Verify the PDF and handouts open locally. Stop the presenter command with Ctrl-C and confirm `demo-run.json` reports INTERRUPTED and no complete proposal is presented. Reusing an output name must refuse overwrite. A deadline expiry must report DEADLINE_EXCEEDED and preserve partial output separately. Move immediately to the pre-opened artifact or slides; do not troubleshoot in the room.

The local Strands launcher's current gate must refuse its frozen failed evaluation. `generator/demo_gate.py` binds current code, schema, prepared inputs, model identity, threshold, evidence hashes, presenting host and a seven-day rehearsal window. Runtime adds a five-second identity probe. A healthy server alone is insufficient. The gate is narrow prepared-demo eligibility and does not authorize enforcement or certify production quality.

## Live enforcement release check

Rehearse only on the disposable marked lab. Verify the actual requester/context, policy controller version and readiness, CNI enforcement, positive connectivity controls, permitted forensic identity and available clean serving capacity. Demonstrate rejection of a privileged Pod and acceptance of a compliant Pod using server dry-run; confirm rejection comes from the intended policy. Capture the command output and restore the reviewed lab posture.

The existing cluster-changing consequence scripts require the lab marker. The presenter proposal command does not use them. The actual exception lifecycle verifier is `lab/verify-exception-expiry.py`: the same exact Pod request is denied before an exception, admitted while active and denied after observed scheduled deletion. It preserves failed evidence and verifies that the cleanup controller's deletion authority is limited to payments. This checks new admission; it does not terminate existing workloads or revoke exposed credentials.

The October 13 presenting-Mac lab uses the separate kubeconfig `.session-build/live-rehearsal/kubeconfig-20261013`, cluster `sc2632-rehearsal-20261013`, k3d 5.9.0, K3s 1.33.4 and official Kyverno 1.19.1/chart 3.9.1. Select its exact context before any cluster-changing tabletop command:

```bash
export KUBECONFIG=.session-build/live-rehearsal/kubeconfig-20261013
export TRUSTFALL_EXPECTED_CONTEXT=k3d-sc2632-rehearsal-20261013
```

Native platform archives and every fixture tag are verified on all three node runtimes. A complete e2e run records 61 passes and three explicit gaps: unavailable memory checkpointing, a system-namespace RBAC bypass and loss of admission rules when the unguarded agent disables Kyverno. Reference/replay remain available without this infrastructure.

The first elapsed-time expiry proof failed: the cleanup controller selected the expired exception but could not delete it. The scoped repair adds only PolicyException deletion in payments and keeps the five-minute cleanup schedule. Read the separate [live-rehearsal record](../../submission/2026-10-13/live-rehearsal/README.md) before describing the final result. Scheduled cleanup can lag the expiry timestamp; it is not an instantaneous cutoff.

Case D is now separately executed on that marked lab. It measures actual out-of-Pod bearer-token reads, the suspect Pod’s new TCP connection, scoped RBAC, retained named dependencies and old Pod-bound credential invalidation while a clean replacement stays available. Use [the recorded evidence](../../submission/2026-10-13/live-rehearsal/case-d/README.md) for the timed reveal. Do not turn this into a fifth live demonstration or claim application-key rotation was tested.

## Full co-presenter rehearsal

| Pass | Required observable evidence | Current status |
|---|---|---|
| Code smoke | Fresh A/B/C reference output; authentic replay; independent negative-test failure; gate refusal | [October 22 local verification](../../submission/2026-10-22/DELIVERY-VERIFICATION.md) |
| Failure handling | Interrupted/deadline run terminates its worker; output-name reuse refuses; offline fallback is immediate | Automated/local checks only; presenter drill pending |
| Full 60 minutes | Both presenters practise handoffs, sealed evidence timing, two table reports and recovery round | Not yet completed, confirmed by Milind on October 16 |
| Target display | PowerPoint notes/hidden slides, PDF, font size, readable terminal on actual screen | File/render checks passed; native PowerPoint/projector pending |
| Target enforcement | Intended denial plus compliant positive control, networking, recovery and restoration on presenting lab | 61-check Mac lab pass; three documented gaps retained; separate expiry and Case D records retained |
| Distribution | Authorized source/package access and working attendee resource | Separate public curated repository authorized and verified; extracted reference/replay checks passed |

During the full rehearsal, one person represents a table with little Kubernetes experience and another challenges every approval. Record where the prompt is ambiguous, where a participant has no decision to make, and where a claimed outcome lacks evidence. Adjust prompts or cut explanation time; do not silently change benchmark labels or convert an untested behavior into a passing result.

Use [REHEARSAL-RECORD.md](REHEARSAL-RECORD.md) to capture actual timestamps, participant decisions, scoring differences and display checks. Use [SCORING-ANCHORS.md](SCORING-ANCHORS.md) to grade a cautious refusal and a bounded approval before delivery. The blank record and scoring examples do not establish human rehearsal completion.

## October 14 abstract and requirement audit

The saved Jev fixture run is one smoke observation, not live-demo eligibility or a new benchmark. Replay on the revised code runs the compiler and independent tests again, using those recorded answers.

The requirement ledger now lists every actual intent clause when the input differs from the prepared contract. It marks them unreviewed and keeps the proposal incomplete. Proposal clauses that do not match the input appear separately. This makes a newly added requirement visible without borrowing an unrelated prepared control mapping. Arbitrary audience prose still needs a newly reviewed independent contract; no promotion or deployment authority is granted.
