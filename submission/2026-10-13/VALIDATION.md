# Current evidence and historical validation records

As of October 16, the current deck is 36 slides: 30 main, six hidden backups and 14 editable tables. ARTIFACT-VALIDATION.json binds its exact hashes and rendered checks. The technical briefing precedes case selection; the revised timing remains unverified by a human rehearsal. Milind confirmed the full rehearsal is still unperformed on October 16. Native PowerPoint inspection is deferred at his request.

The [synthetic Falco audit record](../2026-10-16/README.md) adds real plugin ingestion and matching: 15 synthetic HTTP events across 14 authored cases. The same contract exposed four baseline failures and passes after repair. It does not prove real API-server delivery, kernel capture or production detection quality. The updated workflow makes this behavioral check mandatory. All four jobs passed for runtime commit 908398b, including the real isolated cluster lab and Case D; the complete result is in ../2026-10-16/CI-RESULT.json.

The sections below preserve historical validations, counts, slide positions and limitations for their respective revisions. Use the current artifact and package verification JSON for present bindings.

# Verification record

All listed checks passed on this checkout. Mock tests use no paid inference. Model measurements are documented separately in REVIEW.md.

| Check | Passed | What it verifies |
|---|---:|---|
| benchmark/test_provider_clients.py and test_runtime_questions.py | 14 | Responses/Decisions contracts, finite scores, refusals, cost accounting, calibrated-flag reporting and runtime question parity |
| benchmark/test_workflow_cost.py | 1 | Failed API calls remain counted with unknown cost and an incomplete proposal |
| laya_variant/test_evaluation_integrity.py | 10 | Missing answers stay wrong, zero/invalid confidence, bounded rounding, identity pairing, state bootstrap and bound Decisions replay |
| laya_variant/test_baselines.py | 5 | Real local mock HTTP flow, learned probabilities, parsing, scaling and paired arithmetic |
| laya_variant/test_control_training.py | 2 | Disjoint templates/states, vocabulary order and refusal to select on test data |
| laya_variant/test_pipeline.py | 7 | Tiny random checkpoint: train/encode/calibrate/evaluate/classify plumbing; no model-quality claim |
| generator/test_control_library.py | 5 | Vocabulary/template binding, evidence requirements, hashes, exception limits and shared artifact writer |
| generator/test_generate.py | 5 | Mock compiler flow, schema/CEL injection rejection and policy rendering |
| generator/test_policy_agent.py | 12 | Fixture proposal/replay, abstention, omission detection, model identity and local review artifacts |
| generator/test_policy_contracts.py | 4 | Fixed positive/negative privilege checks and independent requirement ledger |
| generator/test_demo_gate.py | 9 | Current code/config/input/host/recording gate bindings |
| generator/test_presenter_demo.py | 4 | Evidence preservation, bounded execution and child termination |
| generator/test_lab_guards.py | 5 | Rejection of unmarked existing clusters, unsupported runtimes, unevaluated live-model claims and live writes without PyYAML |
| generator/test_image_import.py | 4 | Native archive import, content verification on every node, preservation of BusyBox aliases, offline cached base and wrong-context refusal |

Also passed: catalog lint, Python syntax checks, shell syntax for the touched lab/preflight scripts, and git diff whitespace checks.

The real local model runs use cached pretrained weights on MPS, with the protocol/data/checkpoint configuration retained. The complete proposal measurements use fixtures and Kyverno CLI; no live cluster changes were performed in this training task.

OpenAI Decisions inference remains untested because no credential is configured. Offline adapter tests cannot establish live endpoint access.

The later session revision repaired native Docker image export/import and verified content on all three nodes of the separate presenting-Mac rehearsal cluster. The actual e2e run records 61 passes, zero failures and three documented gaps. The first real expiry run failed because the cleanup controller lacked PolicyException deletion permission; preserve it alongside the repaired verification. See [live-rehearsal evidence](live-rehearsal/README.md) for the final scope and results.

The current deck and handouts are now reauthored with the recorded trained-proposal exercise. Package, geometry, font-policy and first-party import checks passed; changed rendered slides and handouts were visually inspected. This is separate from native PowerPoint/projector verification and the full human rehearsal, which remain pending.

## Four-case revision and CI reproduction

The current deck is `SC2632-session-four-cases.pptx`: 35 slides, 29 main and six hidden backups, with 11 editable native tables. The revised case summary and actual Case D evidence table were visually inspected at full size and the whole deck was scanned. All 35 PDF embedded images match the current rendered slides exactly. The eight-page participant pack's changed pages 1, 5 and 8 were inspected. Speaker notes require Case D predictions before the reveal. Native PowerPoint/projector execution remains unverified because macOS computer-use permissions are pending.

The complete local `scripts/test-all.sh` run passed all installed policy, Python, evidence-capture, expiry and static Falco checks. Kubeconform, shellcheck and the legacy packet browser-render check were skipped locally because those dependencies were unavailable; the CI workflow installs the first two. Case D's five offline guard tests passed. Its real 58-observation run and separate resource-absence verification are retained in `live-rehearsal/case-d/`.

The prior GitHub run for commit `16778d9` failed: the baseline test relied on ignored generated training data, and the separate Laya job lacked scikit-learn. The corrected baseline test builds its training split in memory; all five checks passed in a source copy with no generated data directory. A shared CPU requirements file now supplies pinned numpy/scikit-learn to both CI jobs. The local tiny-checkpoint pipeline passed seven checks; this verifies plumbing, not model quality. A new CI run must verify the changed workflow after push. The live CI lab uses a separate kubeconfig and also runs Case D after the existing e2e exercise.

The corrected workflow for `b623bde` completed successfully in [GitHub run 38517726149](https://github.com/mgunjan/agentic-k8s-guardrails/actions/runs/38517726149): policy/test, Laya plumbing/baselines and the real Linux lab including Case D all passed. The three known e2e gaps remain visible. Falco's audit step was still ignored: the image lacked `falcoctl`, and loading the real plugins then uncovered an invalid string `contains` operation on a list field. The repair uses the typed namespaced ServiceAccount list with `intersects`, pins Falco 0.45.0/Falcoctl 0.14.2/k8saudit 0.18.0/json 0.7.4 and removes `continue-on-error`. Actual local plugin-loaded validation passed; a subsequent CI run must verify the mandatory repair. This establishes compilation, not runtime audit ingestion or production detection coverage.

The public repository was separately authorized and verified. Only slide 29 changed visually when its real address was added; the other 34 rendered slides match the prior revision. The PDF matches all 35 current slide renders, and all eight participant footers were inspected with the published address.

The final mandatory workflow passed for code commit `fcd951d7f1b6983cdd89ce61dd6fd39ee223f25a`, [run 38519483635](https://github.com/mgunjan/agentic-k8s-guardrails/actions/runs/38519483635), completed October 14 UTC. All four jobs passed: policy/test, tiny-checkpoint Laya and baselines, both real Falco rule validations, and the isolated Linux lab including Case D. No failed validation was ignored. The earlier signed-plugin cache-permission failure and narrow static-lint allowlist were repaired; signature verification stays enabled and the live lab waits for mandatory audit validation. This is separate from production audit ingestion and from the pending human/presentation checks.

An anonymous public checkout matched the source index and reproduced A/B/C reference compilation plus authentic Jev replay. All proposals retained human review; the fixed privilege suite applies to A and remains NOT_COVERED for B/C. Published scripts preserve executable permissions and the snapshot includes the frozen examples cited by the handouts. See ATTENDEE-PACKAGE-VERIFICATION.json for exact archive and public commit bindings.

The delivery review corrected the stale Case D speaker note and the paper-exercise rubric. Only slide 7 changed visually; the other 34 rendered slides match the prior release, and the new PDF matches all 35 renders. The revised one-page scorecard was visually inspected. Added scoring anchors, a blank human rehearsal record, a no-D-table fallback and a mathematically timed five-minute catch-up plan. These plans do not establish human rehearsal or scoring calibration. No runtime policy, model evaluation, frozen label or enforcement code changed.

## Participant orientation revision

The revised opening visibly establishes incident context, participant assignment, supplied materials and the discuss/record/reveal/revise sequence. It identifies the shared worksheet, case selection, roles, operating constraint and both co-presenters' responsibilities. Detailed scoring moved off the setup slide into the existing handout so the final setup minute is participant work. Round 1, containment and recovery prompts now state the page and written task.

Slides 2–8, 16 and 27 changed visually and were inspected individually at full size. The other 26 slide visuals match the previous release exactly. Package, geometry, font-policy and first-party import checks passed, with 35 total slides, 29 main slides, six hidden backups and 11 native editable tables. The new PDF's 35 embedded slide images match the rendered deck exactly. The participant pack remains eight pages; its revised orientation and worksheet pages (1 and 6) were visually inspected, and the other six pages retain identical extracted content. The runbook, co-presenter opening script and take-home guide now use the same assignment and six-minute setup timing.

This is a content/layout revision. Runtime code, model inputs/labels and enforcement evidence remain unchanged. Participant comprehension, the full 60-minute human rehearsal and native PowerPoint/projector inspection remain unverified.

## Environment and Kyverno primer

The environment briefing now names the shared workloads and explains cluster, namespace, Pod, replicas and ServiceAccount in plain language. The next visible slide explains Kyverno's demonstrated admission-validation role with a request/rule/denial example, followed by the boundary between new changes and already running workloads. The assignment and round sequence share slide 4. The first three minutes now allocate twenty seconds to the cover, fifty each to environment and Kyverno, and one minute to the assignment. Case selection and participant writing time remain unchanged.

Slides 2–4 changed and were inspected individually at full size. The other 32 slide visuals match the preceding revision. The deck remains 35 slides with 11 editable tables and six hidden backups. Structural/layout/font/import checks passed, and all 35 PDF embedded images match the deck renders. The participant pack remains eight pages; only page 1 changes, and its rendered primer was inspected. Definitions cite official Kubernetes and Kyverno documentation in the speaker notes and incident brief. The co-presenter cards include the plain-language explanation and a comprehension prompt for someone unfamiliar with Kyverno. This is prepared content, not evidence that an audience comprehension test has been performed.

## Accessibility for participants new to Kubernetes

The opening now begins with Kubernetes' role in the shared application platform and explains familiar functions before product terms. Application copies, resource groups and workload identities precede replicas, namespaces and ServiceAccounts. The request-check example, case choices, availability constraint, rollout language and recorded removal question use equivalent plain-language descriptions. Co-presenter prompts and scoring anchors accept behavioral security requirements without vocabulary or code requirements.

Slides 2–6, 14 and 20 changed visually and were individually inspected. The remaining 28 visuals match the prior deck. Structural/layout/font/import checks passed; 35 slides, six hidden backups and 11 editable tables remain. The PDF matches all 35 rendered slide images. The participant pack remains eight pages, with only page 1 changed and visually inspected; the other seven pages have identical extracted content. The six-minute setup is unchanged. The first handout draft overflowed onto a ninth page; shortening its co-presenter footer restored the original eight-page order before delivery. Runtime code, frozen labels and enforcement evidence are unchanged. A human comprehension check with someone new to Kubernetes remains pending.

## Purpose before the technology primer

A dedicated slide 2 now states what the workshop builds and why it matters. The environment and Kyverno move to slides 3–4, participant task and table roles share slide 5, case choice moves to slide 6, and constraint/setup share slide 7. This preserves 35 total slides and all exercise/evidence slide numbers from 8 onward. The runbook and co-presenter opening timing match the new order: purpose precedes terminology, case choice retains seventy-five seconds and final setup retains a full minute.

Slides 2–7 and the participant pack's first page were inspected at full size. The other 29 slide visuals match the prior revision. Structural/layout/font/import checks passed, with 11 native tables and six hidden backups. The new PDF's 35 embedded slide images match all deck renders. The participant pack remains eight pages; pages 2–8 have unchanged extracted content. Purpose and assignment checks are prepared in the human rehearsal record; they have not yet been performed with participants. Model evidence and runtime enforcement code are unchanged.

## Audience-review revision, October 14

Thirteen main-slide visuals changed: 2, 5, 8, 9, 10, 13, 15, 19–22, 26 and 28. The other 22 visuals are pixel-identical to the preceding revision. All changed slides and participant page 1 received full-size visual inspection; the whole deck received a montage review. The exact final PPTX passed package, geometry, font-policy and first-party import checks, with 35 slides and 12 editable tables. All 35 PDF page images match the source renders exactly. The participant pack remains eight pages; pages 2–8 retain identical extracted content.

The opening uses a concrete incident illustration, the prepared input contract is explicit, and lab response questions provide technical facts. The closing record is an illustrative paper plan, not an executed response. This revision changes presentation and preparation material, not inference or enforcement code. Human comprehension, the 60-minute rehearsal, scoring calibration and target-display behavior remain unverified.
