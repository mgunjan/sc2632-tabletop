# Delivery verification — 22 October 2026

## Current release

The delivery deck is `SC2632-session-dayof-v21.pptx`. Earlier v11–v20 exports are review history, not current delivery files. The original submitted deck is retained separately. The current deck has 38 numbered slides: 29 visible and nine hidden backups (4, 8, 29, 33–38). Each slide has nonempty speaker notes. The hidden model-comparison slides keep pilot quality and separately measured workflow cost distinct.

The visible PDF contains 29 pages; the reference PDF contains the nine hidden slides. They use exact rendered slide images and searchable source text, with bookmarks carrying the PowerPoint slide numbers. They are not native PowerPoint PDF exports. PowerPoint slide jumps use the 38-slide numbering; PDF page numbers differ.

The nine-page `PARTICIPANT-PACK.pdf`, two-page `PODIUM-CHEATSHEET.pdf`, two-page `CONTROL-REVIEW.pdf` and one-page `REVIEW-SCORECARD.pdf` form the print set. Page 8 is unsealed at minute 27 and the containment round starts at 28. Page 9 stays folded until 35. All four room predictions are collected on slide 21 at minutes 39–40 before answers on slides 22–25. Proposal-review page 2 stays folded until slide 28.

## Verified locally

- Official Kyverno CLI 1.19.1 is installed in ignored local build storage. `demo.py --check` reports `ready: true` for the offline reference path.
- Fresh Scenario A/B/C reference runs each completed in under 1.5 seconds. All report `REVIEW_REQUIRED`, with automatic promotion disabled. They compile current source and execute fixtures; they make no provider call or cluster change.
- A's independent fixed privilege gate passes. That gate does not cover B/C; their authored/generated policy suites pass separately. B's illustrative 24-hour exception exceeds a four-hour catalog maximum and is flagged `EXCEPTION_LIMIT_EXCEEDED` for human disposition.
- A Jev replay completes with the independent privilege gate passing. The authentic Strands replay remains `INCOMPLETE_PROPOSAL` / `REQUIRED_POLICY_MISSING`. A failed recorded proposal is not converted into a successful run.
- `scripts/test-all.sh` exits zero with `ALL PASSED`: 12 authored Kyverno suites, seven generated-policy parity suites, 30 Python test scripts (including 12 lab/refusal/launcher guard tests), the separate seven-test tiny random Laya checkpoint pipeline, fake-kubectl evidence capture, offline exception expiry, Falco static lint and standards checks. The tiny checkpoint test proves plumbing, not model quality.
- Strict kubeconform v0.6.7 checks 49 resources: 47 valid, zero invalid/errors, two explicitly skipped kinds. ShellCheck v0.11.0 passes 22 scripts. The browser packet renderer creates 18 PDFs without card overflow using the installed Chrome executable.
- Evidence capture creates private directories/files, labels raw forensic material as sensitive, and refuses bundle-name reuse. Preflight and direct consequence scripts verify the exact expected disposable context; preflight also checks the pinned Kyverno CLI version before cluster access.

A full final offline rerun after the live-script and launcher changes also returned `ALL PASSED`. Full command and machine-local evidence are retained in ignored `.session-build/dayof-current-review/quality-checks.json`, `test-all-full.log`, `test-all-live-final.log`, and `verification.json`. The raw forensic bundle is excluded from participant exports.

## Presentation checks

The first-party authoring library renders all 38 slides. Package integrity, geometry, required native evidence tables and import validation pass. All 38 slides were inspected in the v18 visual pass; v19 changed slides 2, 20, 26, 32 and 33 and these were re-inspected. v20 changed speaking cues and evidence source anchors. v21 changes only slide 22 visually to label the prepared live Q3 check and dated fallback, and updates its notes and related delivery cues. Its other 37 slide renders match v20 byte for byte. Slide 22 and both rebuilt podium PDF pages were inspected. The deck keeps ten native editable tables; evidence has not been replaced by illustrations. All 38 speaker notes and the hidden-slide set are checked after export.

The opening defines the fictional payment service and availability floor, the workload/policy-author distinction, the agenda, Kubernetes terms and control boundaries before case selection. The table instructions show the actual decision record. The three original illustrations support ownership, exception review and narrow self-validation; the [artwork record](IMAGE-RIGHTS-REVIEW.md) identifies their provenance. Supplied meme photos from earlier review drafts are excluded from the delivery deck and public kit.

## Evidence limits and remaining delivery checks

- Slides 23–26 retain their dated k3s and synthetic Case D records. A separate [fresh October 22 local API/CNI run](LOCAL-LAB-VERIFICATION.md) passed 63 assertions with three documented gaps; the actual expiry lifecycle and 56 synthetic Case D checks also passed. The labelled slide-22 live Q3 reveal passed in 12.85 seconds, with positive clean-path controls, and the lab was re-staged. Each has its own scope; offline fixtures do not establish runtime containment.
- Falco static/synthetic checks do not establish live kernel capture, API-server audit delivery or alert-to-response. Live Falco is not part of the workshop demonstration.
- The current v21 deck has not been visually checked in native PowerPoint or on the venue projector. Image rendering and package validation do not establish native font/layout behavior.
- Milind and Vivek have not completed the full 60-minute rehearsal with timed handoffs and sealed evidence. The rehearsal record remains blank until they do.
- Application-key rotation and production containment effectiveness are not established by the copied Pod-bound token demonstration.

The day-of sequence uses the bounded offline reference/replay workflow and one prepared local Q3 path check on slide 22, subject to staged preflight. The wrapper visibly distinguishes live, dated replay and failed execution; the notes state the tested paths and limits. The public package is an adaptable exercise and source example; it is not a production-readiness certification or a claim that the live environment has been contained.
