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
