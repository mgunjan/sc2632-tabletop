# Fresh local enforcement verification — 22 October 2026

This record describes executed checks on a separate, explicitly selected disposable Apple Silicon lab. It does not establish completion of the two-presenter session rehearsal, venue display verification or production containment. The [machine-readable summary](LOCAL-LAB-RESULT.json) preserves source hashes, phase exit codes, measured durations and limits without publishing raw forensic logs, kubeconfig contents or credentials.

## Environment and executed checks

Docker Engine 29.5.3 ran three native ARM64 k3d 5.9.0 nodes, K3s 1.33.4 and official Kyverno 1.19.1/chart 3.9.1. Commands used an isolated kubeconfig and the exact expected marked rehearsal context. The default kubeconfig file was unchanged during the enforcement run. Existing unrelated lab resources were left in place.

| Check | Result | Measured duration | What it establishes |
| --- | --- | ---: | --- |
| Setup after readiness repair | PASS | 24.45 s | The current lab and policies become ready using the pinned policy API's actual readiness field. |
| Live API/CNI e2e | PASS, 63 passing assertions and 3 documented gaps | 188.71 s | Authored admission, network, evidence, disruption and guardrail checks execute against the local API server. The three expected gaps remain visible. |
| Actual exception lifecycle | PASS | 122.75 s | The same new-Pod request is denied before an exception, admitted while active and denied after scheduled deletion. Cleanup is permitted in payments and refused in inventory. |
| Separate synthetic Case D | PASS, 56/56 checks | 37.07 s | Actual bearer-token API reads, network/RBAC changes, retained named dependencies and Pod-bound credential invalidation in isolated test namespaces. |
| Final staged preflight | PASS, 8/8 applicable checks | 0.60 s | Correct target, lab marker, controller, 3/3 Ready replicas, two suspects plus one clean, Python dependencies and pinned CLI. Model inference is intentionally skipped. |
| Slide 22 labelled live launcher | PASS, LIVE banner and completion | 12.85 s | Q3's added deny-all preserves an existing Q2 DNS allowance; excluding the suspect from that allowance blocks its DNS lookup. Clean DNS/database paths and Ready count remain. |
| Restore starting posture after reveal | PASS | 43.17 s | Q1/Q2 staged again; the final stage-aware preflight passes. Q3 was not left active after this rehearsal check. |

The exception cleanup controller retained its five-minute schedule. Deletion was observed 76.7 seconds after the expiry timestamp in this single run. That is a measured delay, not an SLA or an instantaneous expiry guarantee. Existing workloads and exposed credentials are outside that admission-lifecycle check.

The three documented e2e gaps are unavailable memory checkpointing, a system-namespace RBAC bypass and the loss of Kyverno admission rules when an unguarded overprivileged identity disables its controller. A successful harness result confirms these observed gaps rather than declaring them repaired.

## Slide 22: live observation and exact limits

The launcher first checks the selected lab and staged state. The live script then checks the initial suspect DNS lookup and clean database path, applies Q3 over Q1/Q2, observes that the existing Q2 DNS allowance remains effective, and applies the suspect's isolation label. It checks that suspect DNS lookup fails while the clean replica retains DNS and TCP database connectivity and three replicas remain Ready.

This is one service-name lookup and a clean TCP dependency check. It is not a separate UDP/TCP protocol matrix, a suspect TCP database-denial test or a full application health assessment. The longer e2e suite separately exercises UDP and TCP DNS behavior. None of these observations proves complete containment or a production availability target.

At minute 40, announce the prepared lab scope. Use `play.sh 1-deny-all`; its LIVE/replay/failure banner is the authority for which path ran. A failed preflight plays the explicitly dated October 10 recording. A failed live execution reports failure and does not silently replay; make no success claim and move to dated slide evidence. Slides 23–26 remain recorded observations even when slide 22 succeeds live. The old recording does not establish the newer script's clean dependency checks. Exact operator commands and reset instructions are in [the rehearsal guide](../../tabletop/congress-2026/REHEARSAL.md).

## Repairs and retained failures

The earlier setup waited for a nonexistent generic `Ready` condition and ignored its timeout. Kyverno 1.19.1 exposes readiness at `.status.conditionStatus.ready`. The shared wait now uses that field and fails closed; refusal tests cover both outcomes. The first corrected local setup/e2e/expiry/Case D sequence passed, then the final labelled launcher was run and reset independently.

An initial lab attempt used a name outside the verifier's deliberate rehearsal-name boundary. That newly created attempt was stopped and removed; its failed/superseded log remains private. It is excluded from the passing sequence. An earlier GitHub run also failed before lab creation because a floating k3d installer returned HTTP 404. CI now downloads pinned k3d, kubectl and Helm artifacts and verifies their official release checksums. Remote CI results remain separate from these measured Mac results.

No fresh hosted model call, live Falco kernel capture, API-server audit delivery or automatic alert-to-response path was exercised. Case D uses synthetic resources and stand-in health; it does not prove application-key rotation or production monitoring delivery. Raw local logs are retained privately; only the reviewed summary is included in the attendee package.

## Subsequent October 24 retest

The [import-repair record](../2026-10-24/IMPORT-REPAIR.md) documents a later setup-reliability repair, a real new-tag transfer to all three nodes, fresh local e2e checks, a retained Case D baseline failure and three successful runs after a bounded Service startup wait was added. The prepared live Q3 path and reset/preflight also passed. Keep that later evidence separate from the October 22 phase timings and expiry lifecycle reported here.
