# Docker image-import repair verified — 24 October 2026

The earlier automatic-approval usage-limit block cleared on retry. Docker access and the repaired image-import path have now been exercised on the marked disposable Mac lab, with a separate fresh-cluster Linux CI run. The [machine-readable summary](IMPORT-REPAIR.json) preserves source hashes, phase timings, the retained failure and the successful reruns. This adds evidence to the [October 22 local record](../2026-10-22/LOCAL-LAB-VERIFICATION.md); it does not rewrite that historical run.

## What changed

Two retained CI logs showed direct image import reporting `Failed to copy read stream` and failing to finish. [The importer](../../lab/images/build.sh) now uses k3d 5.9.0's actual `tools-node` mode, with a default 180-second deadline. A timeout exits 124 and leaves setup incomplete. A successful import command is followed by native image-content checks on every node; command success alone does not satisfy setup. Seven [import regression tests](../../generator/test_image_import.py) cover transport selection, all-node verification, refusal and failure paths, and deadline/temporary-archive cleanup.

The extended Mac run found a separate Case D verification weakness: the script waited for Pod TCP readiness but did not establish the initial Service-name HTTP path before starting containment measurements. Its first baseline HTTP check failed, so that sequence remains failed. The original probe did not capture sufficient diagnostics to identify its DNS, Service or HTTP subcause. [The verifier](../../lab/verify-case-d.py) now waits at most 30 seconds for that initial positive control and records sanitized probe outcomes. Health checks after intervention still fail directly. Eight [Case D guard tests](../../generator/test_case_d_guards.py) include delayed startup, permanent failure, timeout and unexpected-response coverage.

## Executed evidence

| Check | Result | Duration / scope |
| --- | --- | --- |
| Mac native fixture import | PASS | 5.22 s; all three ARM64 nodes checked |
| New-tag transport proof | PASS | 3.56 s including archive/import/verification/cleanup; the tag was absent on all three nodes before import and complete on all three afterward |
| Setup and local API/CNI e2e | PASS | Setup 30.54 s; e2e 191.97 s, 63 assertions and three documented gaps |
| Initial Case D sequence | **FAIL, retained** | 14 of 15 checks passed; baseline HTTP failed; all five owned-resource cleanup operations succeeded |
| Case D after startup repair, run 1 | PASS | 56/56 checks, 38.10 s |
| Case D after startup repair, run 2 | PASS | 58/58 checks, 48.32 s |
| Case D after startup repair, run 3 | PASS | 58/58 checks, 48.20 s |
| Prepared slide-22 Q3 path | PASS, labelled LIVE | 12.86 s; scoped DNS/dependency checks and clean controls |
| Restore starting posture | PASS | Re-staged in 42.64 s; final preflight 8/8 in 0.67 s; three replicas Ready, two suspects and one clean |
| Local regression checks | PASS | Full suite at the import fix; all 15 combined import/Case D tests after the startup repair |
| Final Linux CI | PASS | All four jobs: full suite, Falco static/synthetic checks, Laya plumbing/baselines and fresh-cluster lab |

Case D check counts vary because credential-invalidation polling records each observation; all checks passed in each successful run. All three startup probes succeeded on their first attempt. Repetition improves confidence but does not establish an environmental failure rate. Temporary unique image tags and Case D resources were removed successfully. The default kubeconfig hash remained unchanged during both local sequences.

The final runtime revision is `a9a42acec2d092286c3b6d9d0066c8de3dc40d70`; the import change is `902ff97d5c5f2160edd53fe7250a237698144a83`. [Final CI run 40105771093](https://github.com/mgunjan/agentic-k8s-guardrails/actions/runs/40105771093) checks the former revision, including the full suite and a fresh Linux cluster. The private maintainer CI link may require access; the local summary above is included in the participant package. An earlier import-only CI run, 40105066532, also passed all four jobs.

## Limits

The e2e suite still reports unavailable memory checkpointing, the system-namespace RBAC bypass and the unguarded controller-disable path as three documented gaps. Their observation is not a repair of those gaps. Case D exercises synthetic resources, real bearer-token API reads, CNI/RBAC changes and copied Pod-bound credentials; stand-in HTTP health does not qualify a real monitoring pipeline or external application-key rotation. The October 22 exception-expiry lifecycle was not rerun in this sequence.

No live Falco kernel capture or audit delivery was tested. This retest does not establish production containment, native PowerPoint/venue rendering, or the two-presenter 60-minute rehearsal. Raw forensic logs, kubeconfig contents and bearer tokens stay outside the public package. The existing v21 deck, rendered PDFs and print materials are unchanged; this release updates lab source and verification evidence.
