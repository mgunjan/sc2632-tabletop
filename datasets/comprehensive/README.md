# Kubernetes security dataset

This is the broadest local collection in this project: **19 immutable upstream sources, 37,166 typed records and 25,486 distinct record payloads**. It spans admission, runtime detection and enforcement, identity, network controls, posture checks, attack procedures, recorded logs, and response references. Counts include fixtures and version variants; they are not counts of independent incidents or enterprise-qualified controls.

The full normalized data is local at `.session-build/comprehensive-data-20261017/corpus-published/`. The public repository carries the reproducible tools, source and runtime locks, retained license notices, [coverage manifest](MANIFEST.json), and [execution audit](EXECUTION-AUDIT.json). Raw imported content retains its source terms and is not distributed under a blanket project license.

## Contents

| Collection | Records | Meaning |
|---|---:|---|
| Admission policy definitions | 1,596 | 844 reference implementations plus 752 fixture definitions; modern and legacy Kyverno, Gatekeeper and selected KubeArmor admission examples |
| Explicit behavior cases | 12,429 | Original resources and separately stored upstream expectations; includes 4,685 generated Pod Security Admission fixtures across Kubernetes versions |
| Runtime policies | 577 | KubeArmor and Tetragon definitions, including eight fixture policies |
| Network policies | 128 | Kubernetes/Cilium and related implementation examples, including fixtures |
| Detection rules | 752 | Falco core/plugin and selected Linux/container/cloud Sigma definitions; dependency entities are retained separately |
| Posture content | 594 | 290 Kubescape controls and 304 rule metadata records, with their available Rego source implementations |
| Attack procedures and references | 580 | 452 selected Atomic Red Team procedures, 102 Stratus techniques and 26 KubeHound attack references |
| Runtime generators | 116 | Source definitions and authored tests; collected as data, not executed by the builder |
| ATT&CK/defense reference graph | 2,695 | Techniques, defensive references and explicit upstream relationships for Containers/Linux/IaaS and linked objects |
| Recorded log entries | 50 | Parsed from 14 hash-verified upstream Kubernetes/container log files, with 14 separate dataset-context records |
| Natural-language statements | 147 | PolicyBench source text; includes 79 Kubernetes-admission statements; its private evaluator fixtures are unavailable |
| Description-to-control pairs | 2,092 | A separate file aligning source descriptions with their own implementation IDs; weak supervision for retrieval |
| Response examples | 18 | Seven Falco Talon action definitions and 11 example event-to-action mappings |

The corpus also retains 16,046 raw resource fixtures, 741 Chainsaw workflow definitions, 670 detection dependencies and 13 Falco test source definitions. These record types remain separate. Many are supporting material rather than individually labelled decision examples.

There are 4,304 exact duplicate groups. `duplicates.jsonl` records every source identity instead of inflating novelty by counting copies and repeated versions as new evidence. Source families and duplicates must stay together in future splits. Near-duplicate and cross-engine equivalence review remains outstanding; **no training/test split is silently assigned**.

## Sources and scope

[`sources.lock.json`](sources.lock.json) pins:

- Kyverno current policies and the `release-1.16` legacy policy snapshot.
- OPA Gatekeeper library; Kubernetes Pod Security Admission fixtures; Kubescape Regolibrary.
- Falco rules, plugins, testing and event-generator sources; Falco Talon response examples.
- KubeArmor policy templates and selected Tetragon examples/test data.
- Sigma's selected Linux, Kubernetes, container and cloud rules. Windows-only content is outside this collection's scope.
- Atomic Red Team's Linux/container/IaaS procedures; Stratus Red Team and KubeHound references.
- MITRE ATT&CK Containers/Linux/IaaS techniques and linked defense objects; the current enterprise bundle is used, rather than treating every historical release as a new case.
- PolicyBench's natural-language corpus and the selected Splunk Attack Data Kubernetes/container logs.

Each record has a source path, immutable revision, file hash, applicable source license ID, record type, family ID and review requirement. The file inventory records 20,515 source files read and zero parse errors for the selected material. This is a declared selection from these repositories, not a claim that every file or all public datasets have been ingested.

## Executed evidence

The original [core collection](../guardrails/README.md) retains its 142 modern Kyverno suite runs and 87 Falco capture replays. The expanded local run adds:

- **469 legacy Kyverno suites:** 467 exited successfully. `allowed-label-changes` and `prepend-image-registry` failed comparisons under CLI 1.19.1; their raw failures are retained. Legacy policy deprecation warnings are also retained.
- **49 Gatekeeper suites, 270 case passes per configuration:** tested with native validation disabled and enabled. Enabling native validation does not prove every template selected CEL or provide 540 independent cases.

The audit links case-level observations conservatively. A passing process does not verify missing or ambiguous rows. Legacy declarations include disabled suite files and expectations that do not appear in the CLI output. Duplicate Gatekeeper case names can also prevent a unique mapping even when every printed case passed. See [EXECUTION-AUDIT.json](EXECUTION-AUDIT.json) for current counts rather than treating every imported expectation as a verified label.

All new engine executions used a pinned Linux/arm64 image on Docker Desktop, no network, read-only inputs/filesystem, dropped capabilities, an unprivileged user, one CPU and a 1 GiB memory limit per container, with at most three jobs concurrent. The legacy batch took 121.96 seconds; the two Gatekeeper configurations together took 2.76 seconds. These are offline batch timings, not model latency or production throughput. No attack procedures, Talon responses or cluster changes were executed by this expansion. No hosted model API was called; local compute/storage cost is unpriced.

## Local reproduction

Use Python 3.11+, Git, PyYAML and Docker. The runtime lock is Linux/arm64; another architecture needs its own immutable runtime and recorded evaluation.

```sh
python datasets/comprehensive/collect.py \
  --cache .session-build/comprehensive-data-20261017 \
  --legacy-cache .session-build/upstream-data-20261016

python datasets/comprehensive/fetch_runtime.py \
  --cache .session-build/comprehensive-data-20261017 \
  --legacy-cache .session-build/upstream-data-20261016

python datasets/comprehensive/build.py \
  --cache .session-build/comprehensive-data-20261017 \
  --legacy-cache .session-build/upstream-data-20261016 \
  --out output/my-comprehensive-corpus

docker pull busybox@sha256:73aaf090f3d85aa34ee199857f03fa3a95c8ede2ffd4cc2cdb5b94e566b11662

python datasets/comprehensive/run_offline.py \
  --cache .session-build/comprehensive-data-20261017 \
  --legacy-cache .session-build/upstream-data-20261016 \
  --out .session-build/comprehensive-data-20261017/runs/gatekeeper \
  --image sha256:73aaf090f3d85aa34ee199857f03fa3a95c8ede2ffd4cc2cdb5b94e566b11662 \
  --kind gatekeeper
```

Repeat the last command with a fresh output directory and `--kind kyverno-legacy`. Output directories must be fresh; the recorded paths above already exist on the author's machine. Collection and normalization can run without executing any engine or contacting a cluster.

`audit.py` checks the corpus and local execution receipts. To audit the recorded expansion, it also requires the earlier core corpus under `datasets/guardrails/corpus/` and each run's `SOURCES.lock.json` snapshot. The runner preserves that snapshot automatically. The recorded expansion added the independent log source after the engine runs; the audit keeps executed source identities and final collection identities separate.

```sh
python datasets/comprehensive/audit.py \
  --corpus .session-build/comprehensive-data-20261017/corpus-published \
  --cache .session-build/comprehensive-data-20261017 \
  --out output/my-execution-audit
python datasets/comprehensive/test_comprehensive.py
```

## Training use and remaining coverage

The immediate task is intent-to-control retrieval/selection. `intent-pairs.jsonl` offers 2,092 source-description alignments, and original implementations provide candidate context. Source wording is not independent expert intent annotation: upstream descriptions can be incomplete or inconsistent with a control. Review them, deduplicate families and freeze the task before comparing trained models.

Use actual policy engines as behavioral oracles. Expected outcomes, fixture names, rule names, later observations and provenance paths can leak answers. Keep targets/provenance separate and remove test-only cues before model inputs. Name-dependent policy semantics require special handling rather than blindly renaming resources. Repeated Kubernetes versions, captures and replay configurations belong in one split group.

Recorded logs can mix routine activity and attack activity. Their dataset-level description does not establish a per-event maliciousness label. A rule firing does not establish containment success. Talon and ATT&CK mappings supply response candidates and general guidance; they do not supply independently reviewed incident decisions or measured rollback/availability/evidence outcomes.

Still missing: independently labelled enterprise incidents; authorized benign/maintenance counterexamples; adjudicated acceptable response alternatives under availability/evidence constraints; measured exception expiry and recovery outcomes across platforms; and a frozen external evaluation set. The collected platform fixtures are not all executed here. These gaps are visible requirements for model qualification, and they do not prevent exploratory local training.

The existing ten-control compiler, model pilot evaluations and workshop reference/replay default are unchanged. Importing an implementation does not automatically make it a supported or enterprise-qualified compiler action.
