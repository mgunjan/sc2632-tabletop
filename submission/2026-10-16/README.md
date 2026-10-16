# Falco audit behavior and current delivery review

The actual Falco audit plugin received 15 synthetic webhook events covering 14 authored cases. Before repair, four cases failed the expected behavior. After repair, all 14 cases met the same contract, including two explicit visibility warnings. The contract and verifier hashes match across the before/after runs. This is an authored regression suite, not a field detection benchmark.

## What compilation missed

| Case | Before | After |
|---|---|---|
| Unrelated subject with an agent-like binding name | Q2 candidate | No agent association from the name |
| Metadata-only audit event | Q2 candidate from the name | Separate evidence-gap warning |
| JSON Patch without subjects | Q2 candidate from the name | Separate evidence-gap warning |
| RequestReceived and ResponseComplete for one action | Two Q1 candidates | One completed-event candidate |

Completed denied requests remain visible as attempts. Alerts now include the response code and audit ID and describe a requested/attempted change. The subject-based rule requires the actual `agents:ops-agent` ServiceAccount. The visibility rule asks a human to resolve the effective binding and audit-policy coverage. It does not infer association, escalation or success from missing data.

Stage filtering does not deduplicate repeated delivery of a completed event. Subject-free JSON Patch needs authoritative before/after binding resolution. A generic evidence-gap warning can be noisy under a Metadata-only audit policy; audit-policy design and a triage owner remain necessary. No Q1/Q2 temporal correlation or automatic response controller is implemented.

## Reproduce and inspect

Use Docker, Python 3 and the real plugin binaries for the container architecture. CI installs signature-verified, pinned `k8saudit:0.18.0` and `json:0.7.4` with Falcoctl 0.14.2. Then run from the repository root:

```bash
mkdir -p .session-build/falco-audit-plugins
docker run --rm --user 0:0 \
  -v "$PWD/.session-build/falco-audit-plugins:/plugins" \
  falcosecurity/falcoctl:0.14.2 --config /tmp/falcoctl/config.yaml artifact install \
  ghcr.io/falcosecurity/plugins/plugin/k8saudit:0.18.0 \
  ghcr.io/falcosecurity/plugins/plugin/json:0.7.4 \
  --plugins-dir=/plugins --state-dir=/tmp/falcoctl/state
python3 scripts/verify-falco-audit.py \
  --plugins .session-build/falco-audit-plugins --out output/falco-audit-new
```

The output path must be fresh. Falco 0.45.0 runs in a disposable container with all capabilities dropped, a read-only filesystem and only an ephemeral loopback HTTP port. Kernel capture is disabled; no Kubernetes context or credential is mounted. Each run records engine/plugin identities, source hashes, raw output, case results and cleanup. Failures return a nonzero exit status.

The test-only witness rule proves that every injected event reached the plugin. `rule_matching: all` allows the witness and a project rule to match the same input. That instrumentation is separate from production detection rules. The suite covers five positive cases, seven negative controls and two visibility gaps, not independent incidents or calibrated precision/recall.

Read [the summary](falco-audit/SUMMARY.json), [baseline](falco-audit/baseline/result.json) and [repaired result](falco-audit/repaired/result.json), including their raw logs and copied rules. The source verifier is also preserved as a non-executable snapshot. The first execution was on Docker Desktop's Linux/arm64 VM. The required CI audit job also passed on Linux/amd64 with identical rules, contract and verifier hashes. Its [raw evidence](falco-audit/ci-amd64/result.json) is retained separately. This is one cross-architecture reproduction of the same authored suite.

## Use in the session

Keep the existing workshop timing and sealed findings. As an optional technical Q&A example, explain that our valid rules still confused binding names with subjects and counted two audit stages. The behavioral contract exposed those errors. The repair preserves uncertainty as an explicit investigation request instead of converting it into a stronger incident claim.

The main deck remains 36 slides, with the implementation before case selection. The visible slides, PDF and handouts are unchanged by this detector repair. Speaker-note citations now point to the public source. All 26 cited source paths are included, with the historical October 10 cloud record explicitly labelled as such. The actual API-server-to-Falco delivery path, kernel event detection, production audit delivery/loss and automatic containment remain unverified. The full human rehearsal is still unperformed, confirmed by Milind on October 16. Native PowerPoint inspection remains deferred at his request.

Primary documentation: [Falco audit events](https://falco.org/docs/concepts/event-sources/plugins/kubernetes-audit/) and the [audit plugin's event-source and field definitions](https://github.com/falcosecurity/plugins/tree/master/plugins/k8saudit). The pinned versions and the observed local execution, rather than the moving documentation branch, bind the recorded result.

The complete workflow for runtime commit `908398b9c85fcb1577cde49aa6f483a57272482e` passed all four jobs: Falco, policy/test, Laya plumbing/baselines and the live isolated Kubernetes lab including Case D. See [CI-RESULT.json](CI-RESULT.json). Laya plumbing does not qualify a model, and the synthetic Falco check does not qualify an operational sensor pipeline.
