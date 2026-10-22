# October 22 local delivery verification

This record distinguishes current local checks from historical lab results. A local fixture pass does not prove enforcement in a live Kubernetes cluster.

## Current source, local environment and tests

- The official Kyverno CLI 1.19.1 macOS arm64 binary is present in the ignored local `.venv-session/bin/kyverno`; its recorded checksum matched the official release archive. It is excluded from Git and participant packages.
- `PATH="$PWD/.venv-session/bin:$PATH" .venv-session/bin/python tabletop/congress-2026/demo.py --check` returned `ready: true`, found the local CLI and verified exact version 1.19.1. The reference workflow does not require a hosted API or cluster.
- `scripts/test-all.sh` completed with `ALL PASSED`. This includes hand-written and generated Kyverno policies, Python/unit and Laya pipeline tests, evidence capture and redaction, expiry behavior, Falco static lint, and standards crosswalk integrity.
- Optional tools unavailable in this environment were skipped: strict `kubeconform`, `shellcheck`, and the browser-based tabletop packet renderer. The Python tests that bind loopback mocks passed when run with local `127.0.0.1` access.
- The deck is produced from the editable source and neutral SVG map. Its build validates source package integrity, imports the result with the first-party authoring library, and runs presentation layout checks. The v11 PPTX was also opened in Microsoft PowerPoint on Mac.

## October 22 delivery files

- `SC2632-session-dayof-review-v11.pptx`: 38 slides, 32 visible and six hidden backups, with 38 speaker notes. Structural and layout validators returned zero findings and warnings; first-party import passed. All 38 slides have title semantics and all 11 embedded images have descriptive text alternatives. The full 38-slide contact sheet and changed opening pages were visually inspected.
- `SC2632-session-dayof-review-v11.pdf`: 38-page 16:9 PDF rendered from the exact deck slide images. It is a review/delivery rendering, not a native PowerPoint PDF export.
- `PODIUM-CHEATSHEET.pdf`: two-page field guide, aligned to the 60-minute agenda, slide numbers, roles, demo boundary and fallback. Its pages were rendered and visually checked.
- `PARTICIPANT-PACK.pdf`: nine-page participant exercise pack.
- `ATTENDEE-SOURCE-KIT.zip`: curated package with deck, PDF, participant and presenter materials, source assets and a SHA-256 file index. Its link audit checked 116 Markdown targets with zero missing links across 727 source files.
- The full contact sheet and build receipt are retained in ignored `.session-build/congress-2026-context-review-v11/`.

The opening now explains why the fictional payment API is used (a visible availability floor, not payment-compliance instruction), what is fixed and unknown before case choice, the two AI roles, the four control boundaries, the hour's agenda, the participant output and the paper-based/no-Kubernetes-experience requirement. The exercise starts at minute 12; the revised speaker notes shift the original sequence once in `mm:ss` and close at minute 60. The presenter and co-presenter guides use the same timing and slide references.

Artwork rights are recorded in `IMAGE-RIGHTS-REVIEW.md`. The deck uses original generated illustrations and a source-authored platform diagram. Presenter-supplied Spider-Man and medal images with unverified redistribution rights are excluded from the current deck and curated package.

## Technical claim boundaries

- Kyverno checks new resource requests; it does not stop an already-running Pod or a Secret read. NetworkPolicy and RBAC cover different traffic and API-action boundaries.
- Falco rules passed static lint and audit rules passed synthetic tests. Live kernel capture, API-server delivery and alert-to-response are not verified for this session. Falco does not trigger quarantine in the workshop implementation.
- Fresh offline A/B/C policy-reference runs completed in 1.54 s, 1.26 s and 0.59 s. All remain `REVIEW_REQUIRED`; automatic promotion is disabled. They compile current source and evaluate fixtures, not live cluster enforcement.
- The historical October 13 lab and Case D records remain dated observations. They are not fresh October 22 cluster runs. The Case D 41.2-second credential observation is one measured interval, not an SLA or guaranteed bound.
- No live cluster end-to-end run is claimed. The active context was not the disposable target lab. The current local demo compiles supplied source and evaluates offline fixtures; it does not call an AI provider, open a PR or modify a cluster.

## Still outstanding before presenting

- The full 60-minute rehearsal with both presenters and sealed evidence handoffs has not occurred.
- The venue projector, speaker notes and local network have not been checked in the room.
- PowerPoint's Accessibility Assistant reports zero issues for contrast, missing image descriptions, missing table headers, missing/duplicate slide titles and restricted access. It raises a generic “Check reading order” review item on all 38 slides; I inspected the first two opening slides and their sequence was logical, but did not mark all remaining slide-order prompts reviewed.
- Structural package checks, first-party import, native open, full contact-sheet review and PDF visual checks passed. Native visual review on the venue projector remains outstanding.
- Live cluster enforcement and live Falco alert-to-response remain unverified. Do not present recorded observations as fresh execution or offline fixture results as containment proof.

The slides and locally runnable offline demo are prepared for review. Rehearsal and room setup remain delivery gates; this document does not claim those gates have passed.
