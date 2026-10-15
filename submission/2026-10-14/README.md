# October 14 demo and abstract audit

This follow-up checks whether the prepared proposal path still works and whether a newly written requirement remains visible to its human reviewer. It does not replace the frozen model comparison, establish production suitability or complete the human workshop rehearsal. Slides and printable materials remain under `submission/2026-10-13/`.

## Observed behavior

One fresh prepared Scenario A run called the real Jev API eight times and returned `jev-1.13.0` for every decision, without provider errors. The complete fixture proposal took **2.973 seconds**, rounded to 2.97 on the presenter display. Six independent privilege CREATE tests passed. Three decisions escalated, and the proposal stayed `REVIEW_REQUIRED` with automatic promotion disabled. This is one smoke observation, not a latency distribution, a cost benchmark or arbitrary-intent qualification. No cluster changed. The API cost was not re-priced or reconciled with billing.

The presenting shell initially could not find Kyverno. With the verified local executable, preflight found version 1.19.1 and the reference run completed. The presenter command now accepts `--kyverno` with an explicit executable path, reports that path and checks the exact version. Its compiler and test children use the same executable. Attendees may continue installing the CLI on their own PATH.

## Requirement visibility regression

The registered perturbation appends “Preserve required monitoring access.” to the prepared four-clause intent. Before the fix, the independent check correctly blocked the changed input but printed only the four prepared requirement rows. The fifth requirement was absent from the ledger.

The revised ledger lists all five actual clauses as unreviewed and keeps the proposal `INCOMPLETE_PROPOSAL`. It does not inherit prepared enforcement meanings for changed text. Proposal clauses that do not match the actual input appear separately. An empty intent also remains incomplete. This repair improves what the reviewer sees; the earlier path already withheld promotion.

The actual Jev answers were then replayed through the revised compiler and independent checks. That fresh replay took 0.659 seconds and retained privilege PASS plus human review. Replay time is not inference latency. The A/B/C contracts remain prepared-intent review aids; a new audience statement needs its own independently reviewed contract.

## Evidence

- [Registered plan](demo-audit/PLAN.json), written before the runs.
- [Summary](demo-audit/SUMMARY.json) and [source fingerprints](demo-audit/SOURCE-FINGERPRINTS.json), separating the pre-fix live run from the revised-code replay.
- [Authentic Jev responses](demo-audit/LIVE-JEV-agent-run.json), [spec](demo-audit/LIVE-JEV-spec.json), [provenance](demo-audit/LIVE-JEV-provenance.json), [run timing](demo-audit/LIVE-JEV-demo-run.json) and [privilege test log](demo-audit/LIVE-JEV-privilege-tests.txt).
- [Before ledger](demo-audit/UNBOUND-before-readiness.json), [after ledger](demo-audit/UNBOUND-after-readiness.json), [actual changed intent](demo-audit/UNBOUND-intent.txt), [supplied spec](demo-audit/UNBOUND-spec.json), and [rendered review text](demo-audit/UNBOUND-after-review.md). The original evaluator is retained as a non-executable text snapshot for the comparison.
- [Current-code replay](demo-audit/REPLAY-agent-run.json), [independent review](demo-audit/REPLAY-readiness.json) and [test log](demo-audit/REPLAY-privilege-tests.txt).
- [Generator test log](demo-audit/GENERATOR-TESTS.txt): 46 unittest cases passed, alongside the existing script-style checks executed during imports. The first sandbox attempt denied two mock servers permission to bind loopback sockets; the permitted rerun completed. No hosted calls occur in those tests.

The [abstract-alignment audit](ABSTRACT-ALIGNMENT.md) maps each accepted promise to artifacts and the delivery evidence still missing.

The [extracted-source checks](demo-audit/EXTRACTED-SOURCE-CHECKS.json) ran A/B/C reference proposals and the fresh Jev recording from a source ZIP with provider credentials removed. All four retained human review. A and replay passed the privilege checks; B/C correctly reported that fixed privilege contract as not covered. This verifies reproducible fixture proposals, not Kubernetes enforcement.

All four [CI jobs](demo-audit/CI-RESULT.json) passed for runtime commit `ed2ec0cf22fdd8bc9d3b5a25545a24fb03d37c88`: core tests, Laya plumbing, Falco validation and the real Kubernetes lab including Case D. This is automated code/lab evidence, separate from the presenting Mac and human delivery.

## Presenter use

Keep the supplied-spec reference path as the default. Optional live inference needs its own presenter rehearsal and does not inherit the local Strands demo gate. The frozen Strands result still fails that gate; no threshold or label changed.

For a no-key replay of the fresh Jev recording, use a fresh output directory:

```bash
.venv-session/bin/python tabletop/congress-2026/demo.py --mode replay --scenario a --recording submission/2026-10-14/demo-audit/LIVE-JEV-agent-run.json --out output/oct14-replay
```

If the CLI is outside PATH, add `--kyverno` followed by its actual executable path. The command compiles and tests now, creates a local review proposal and grants no deployment authority.

The full co-presenter hour, independent scoring calibration, participant comprehension and target PowerPoint/projector inspection remain pending. Machine execution does not establish those outcomes.
