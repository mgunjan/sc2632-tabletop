# Local Falco and Kyverno dataset

This directory contains a real upstream collection, local execution pipeline and normalized corpus. A workshop rehearsal is not a prerequisite for collecting data or running exploratory local training. Incident-response qualification remains a separate task.

Four upstream repositories are pinned in [sources.lock.json](sources.lock.json). Their source checkouts, CLI binary, 29 syscall captures and raw execution logs are cached under `.session-build/upstream-data-20261016/`. No hosted model or API key is needed.

The subsequent [comprehensive collection](../comprehensive/README.md) expands to 19 pinned sources and 37,166 typed records, including legacy Kyverno, Gatekeeper, official Kubernetes fixtures, runtime enforcement, recorded logs, attack and response references. This directory preserves the original core collection and its executed evidence.

## Collected and executed

| Material | Recorded result |
|---|---|
| Kyverno policy documents | 184 reference documents and 182 test-fixture documents, kept distinct |
| Kyverno tests | All 142 suites returned successful contract comparisons; 1,466 declared resource expectations |
| Kyverno row audit | 1,434 expectations have a unique matching `Ok/Pass` observation; 32 remain missing, ambiguous or unmatched |
| Falco definitions | 96 rules across stable, incubating and sandbox; complete macro/list definitions retained in the entity index |
| Falco execution | 29 distinct captures replayed against each of three rulesets: all 87 executions completed |
| Observed Falco coverage | 19 distinct rule names matched; this capture collection does not exercise every collected rule |

The first exploratory Kyverno sweep took 37.58 seconds; the provenance-bound sweep took 44.27 seconds with three workers. Falco stable/incubating/sandbox sweeps took 17.77/16.06/14.46 seconds with two workers each. They ran on Docker Desktop's Linux/arm64 VM, with one CPU and 768 MiB maximum per container, no network, dropped capabilities and read-only inputs. Incubating and sandbox sweeps overlapped. These are dataset-processing times, not model inference latency or production throughput. Model API calls: zero; local compute and storage are unpriced.

The normalized files in [corpus/](corpus/) contain:

- `catalog.jsonl`: policy/rule definitions, purpose text, types, exact source links and hashes. Test fixtures are excluded from the search baseline.
- `falco-entities.jsonl`: rules, macros and lists, scoped to their ruleset.
- `kyverno-cases.jsonl`: original resource/context where uniquely identified, policy IDs, upstream expectations and separate CLI observations.
- `falco-replays.jsonl`: capture hashes, ruleset, completion, observed rule counts and raw local-run references.
- `MANIFEST.json`: counts, file hashes, coverage and explicit gaps.

[`evidence/`](evidence/) retains the execution summaries, the exact runner source snapshots and raw Kyverno CLI output. Falco event logs and large capture files stay in the local cache. The public records preserve their hashes and per-ruleset counts for reproduction from upstream inputs.

## Why the row audit matters

The CLI emitted 1,506 harness rows, including 35 `Excluded` rows. A harness `Pass` means its comparison succeeded; it does not mean admission was allowed. The normalizer requires one matching `Ok/Pass` row and preserves the expected policy outcome separately. It does not infer a direct policy result from harness status.

The 32 unverified mappings include legacy rule fields without a returned rule ID, duplicated mutation expectations, generated-resource identifiers, and declared resources with no matching observed row. They remain visible; they are not converted into verified labels merely because the suite exited zero. One suite declares `myfailedpod` and `withoutinitcontainer`, while the emitted comparison contains only `mypod`. This is a coverage question requiring inspection, not evidence that the absent resources passed.

Falco matches are engine observations, not labels that an incident was malicious or contained. A historical archive's positive/negative directory name is not adopted as current detection ground truth. Repeated rulesets do not turn 29 captures into 87 independent incidents. The event-generator source is available for future isolated case generation; the recorded executions use capture replay.

## Reproduce locally

Use Python 3.11+, Git, Docker and `pip install -r requirements.txt`. The recorded lock's executable and images are Linux/arm64. Another architecture needs matching immutable image and CLI identities and its own execution record.

```sh
python datasets/guardrails/fetch_upstream.py --base .session-build/upstream-data-20261016

# Obtain the exact recorded images if they are not already local.
docker pull busybox@sha256:73aaf090f3d85aa34ee199857f03fa3a95c8ede2ffd4cc2cdb5b94e566b11662
docker pull falcosecurity/falco@sha256:788f1129c542171813083d4afc61b16730a47dde8c23d9c39370acef996349b6

python datasets/guardrails/run_upstream.py --base .session-build/upstream-data-20261016 \
  --out .session-build/upstream-data-20261016/runs/kyverno-verified --kind kyverno --workers 3 \
  --image sha256:73aaf090f3d85aa34ee199857f03fa3a95c8ede2ffd4cc2cdb5b94e566b11662

python datasets/guardrails/run_upstream.py --base .session-build/upstream-data-20261016 \
  --out .session-build/upstream-data-20261016/runs/falco-verified --kind falco --workers 2 --timeout 180 \
  --image sha256:788f1129c542171813083d4afc61b16730a47dde8c23d9c39370acef996349b6
```

Repeat the Falco command with `--ruleset falco-incubating_rules.yaml --out .../runs/falco-incubating`, then `--ruleset falco-sandbox_rules.yaml --out .../runs/falco-sandbox`. Replace `...` with the cache path above. Every run output directory must be fresh; use another cache for a complete repeat. The runner preserves failures/timeouts and removes its own containers.

```sh
python datasets/guardrails/build_corpus.py --base .session-build/upstream-data-20261016 \
  --out output/my-upstream-corpus
python datasets/guardrails/test_dataset_tools.py
python datasets/guardrails/search_controls.py --query 'Prevent privileged containers' --engine kyverno
```

Search is a local BM25 retrieval baseline returning review candidates. Its score is not a probability or deployment approval. It does not extend the compiler's existing ten-control vocabulary automatically.

## Use for a custom System-1 model

An additional [natural-language source record](natural-language-source.json) pins the locally downloaded
[PolicyBench corpus](https://github.com/jbeaven/policybench): 147 statements, including 79 Kubernetes-admission
statements. It retains upstream source categories and is separate from the executed corpus above. Its public
v1.0 evaluator omits private fixtures, so no published PolicyBench score is reproduced here. Public descriptions
may overlap with our policy sources; deduplicate and group their source families before a training/evaluation
split. The original corpus text remains in the ignored PolicyBench checkout with its provenance and terms.

Use reference control purposes/descriptions to develop intent-to-control retrieval/selection examples. Use executed behavior to verify coverage and mine counterexamples. The upstream expectation labels also support exploratory behavior-supervision tasks. A model replacing deterministic policy evaluation would need to justify why the actual engine should not be used directly.

Fixture names such as `badpod` can disclose the expected answer. Keep provenance, filenames, expected results and later observations outside candidate inputs. Normalize fixture cues, preserve legitimate name-dependent semantics, rerun changed cases, and group policy families/capture hashes before splitting. All descendants and repeated replays stay together. Public fixtures are not an independently collected enterprise incident test.

This collection does not invent incident-response labels, approvals or quarantine decisions. A local fine-tune can proceed as a declared research experiment using task-appropriate labels; production claims require evaluation of that actual task. The existing Laya pilot, frozen workshop comparisons and reference/replay default remain unchanged.

See [the broader dataset design](../../controls/DATASET-DESIGN.md), [control qualification](../../controls/ENTERPRISE-QUALIFICATION.md) and [upstream attribution](NOTICE.md).
