# Presenting-Mac rehearsal evidence

This is a disposable local lab, not an enterprise or venue qualification. All cluster commands use the separate rehearsal kubeconfig and context `k3d-sc2632-rehearsal-20261013`. The original Kubernetes configuration and default context were hash-checked unchanged; no EKS commands were run.

The lab uses k3d 5.9.0, K3s 1.33.4, official Kyverno 1.19.1/chart 3.9.1 and three linux/arm64 node containers. [Native image evidence](native-image-import.txt) confirms all 12 stand-in tags plus real BusyBox and the approved debug image are fully loaded/unpacked on every node. Docker's native platform archive avoids the earlier missing foreign-platform content. BusyBox's short and fully qualified names are excluded from stand-in tagging.

## Live enforcement

The [final release rehearsal](e2e-final.txt) completed with 61 passes, zero failures and three documented gaps. It ran after the native image and expiry-permission repairs. The [earlier successful run](e2e-before-final-image-fix.txt) is preserved separately. The reviewed baseline policy posture was restored afterward; this does not claim that every incident workload was returned to its pre-exercise state. It verifies positive connectivity, admission refusals, Q1/Q2/Q3 behavior, forensic debug restrictions, Service rotation, capacity/recovery conflict, controller disablement and independent guardrail protection. The initial [dependency failure](e2e-dependency-failure.txt) is retained: missing PyYAML produced misleading fixture failures; preflight now refuses before any live writes.

Three explicit gaps remain: memory checkpointing is unavailable; an overbroad agent role can change system-namespace resources outside Kyverno's evaluated scope; and disabling an unprotected policy engine removes its admission controls. The last two are deliberately exercised as failures of the unguarded setup and compared with the independent protection. A passing overall rehearsal does not remove these boundaries.

## Actual exception expiry

[Before the RBAC repair](expiry-before-rbac-fix/result.json), the same exact new Pod request was denied without an exception and admitted with it. Scheduled deletion failed and the probe timed out. The [controller log](expiry-missing-permission-controller.txt) identifies the missing `delete` permission for `policyexceptions.policies.kyverno.io`. The failed source and original policy are preserved with that result.

The [scoped Role/RoleBinding](../../../exceptions/cleanup-policy-exceptions-rbac.yaml) grants only PolicyException deletion in payments. The cleanup selector is restricted to that namespace. The [repaired verification](expiry-after-rbac-fix/result.json) confirms deletion authority in payments, denial of that authority in inventory, initial admission denial, admission with the active exception, actual scheduled resource deletion, then renewed denial for the same Pod request. The final cleanup removes only the specifically named probe exception.

The declared expiry was `2026-10-13T22:31:44.219680Z`; deletion was observed at `22:35:01.119615Z`, **196.9 seconds later**. This is an observation with 15-second polling on one five-minute scheduled-cleanup run, not a worst-case guarantee. It verifies new Pod admission after deletion. It does not test termination of existing Pods, established sessions, network connections or exposed credentials. A requirement for an immediate admission cutoff needs a separate expiry check in the authorization/admission path; scheduled cleanup alone cannot establish that guarantee.

Run the prepared verifier only on a marked disposable lab after applying the scoped cleanup RBAC:

```bash
.venv-session/bin/python lab/verify-exception-expiry.py \
  --kubeconfig .session-build/live-rehearsal/kubeconfig-20261013 \
  --context k3d-sc2632-rehearsal-20261013 \
  --out output/expiry-rehearsal-new
```

## Case D: copied credential response

The [executed synthetic case](case-d/README.md) has 58 passing observations (45 distinct descriptions), including positive connectivity, required named Secret/ConfigMap reads, denied outside GET/LIST after RBAC narrowing, and the old bound credential returning 401 after deletion. Stand-in HTTP health remains available. The observed invalidation delay was 41.2 seconds, not a worst-case guarantee. Application keys previously read from Secrets still need their own rotation and exit evidence.

## Proposal evidence and release boundaries

The [fresh reference proposal](reference-proposal/demo-run.json) completed in 1.304 seconds, with no possible hosted API call and no deployment. Its [requirement ledger](reference-proposal/proposal/readiness.json) remains REVIEW_REQUIRED despite passing six privilege tests. It retains the RBAC and operations handoffs. This is a compiler/review check, separate from live containment.

The current slide/PDF/handout checks are in [ARTIFACT-VALIDATION.json](../ARTIFACT-VALIDATION.json). Native PowerPoint/projector inspection, full human co-presenter rehearsal and authorized attendee distribution remain pending. The [Case D record](case-d/README.md) now verifies read authorization and Pod-bound credential response separately. None of this evidence promotes catalog 0.1.0 as enterprise qualified.

Text exports remove terminal color escapes and trailing whitespace. The original local outputs are retained in ignored build storage; policy, verifier and bound proposal source files remain unchanged.
