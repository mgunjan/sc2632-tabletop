# Behavioral evidence seed 0.1.0

Twenty logical cases, 48 observations, zero training-eligible rows and zero independent incident-response labels. These are examined regression cases. They do not measure a model or qualify a detector pipeline or enterprise control library.

| Cases | Observations | What is established |
|---|---|---|
| 14 synthetic Falco audit cases | Original rules, repaired arm64 and repaired amd64: 42 total | Plugin receipt and exact rule-tag behavior for the authored events. Original 10/14 and repaired 14/14 are retained; architecture repeats are not independent cases |
| Six Kyverno privilege resources | One fresh offline CLI run: six total | One policy pass, four failures and one out-of-scope skip. All six authored expectations match. No API-server admission or cluster contact |

The Kyverno `test` command reports six passing tests because its observations match their declared expectations. That does not mean six admitted workloads. The separate `apply --policy-report` output records actual pass/fail/skip results. Its exit code 1 is expected for the four violating resources. CLI report properties identify offline/background evaluation; do not recast this as six live admission requests.

Falco's rule tags `quarantine-q1` and `quarantine-q2` are detector candidates. They do not authorize a Quarantine level or prove a successful change. An evidence-gap warning is preserved separately. The underlying [before/after record](../falco-audit/SUMMARY.json) describes delivery, stage and subject limitations.

`records.jsonl` separates original events/resources and policy text from expected targets and actual observations. Every record has `split=regression_only`, `training_eligible=false`, `decision_label=null` and artifact hashes. The original synthetic fixture names, audit IDs, URI markers and resource names remain for reproduction. They can reveal a case's construction, so this is not a ready-to-train input format. Future model inputs need a reviewed normalization and lineage record.

`MANIFEST.json` counts logical cases separately from observations and lists the source artifacts. A passing contract is narrow behavioral evidence. Its expectations were authored for this project, not labelled by independent incident reviewers. No new examples, upstream collections or expert judgments have been fabricated.

## Reproduce the normalization

From a source checkout with Python 3.10+ and `pip install -r requirements.txt`:

```sh
python laya_variant/build_evidence_corpus.py --out output/my-evidence-corpus
python laya_variant/test_evidence_corpus.py
```

Choose a fresh output directory. The builder checks raw Falco receipts and alerts against the recorded summaries, expected identities and source hashes. It checks Kyverno raw policy results separately from contract-test success. It does not run a model, cluster or API request. The output records and manifest reproduce byte for byte from this snapshot.

To rerun the six offline Kyverno cases with CLI 1.19.1, use the saved inputs:

```sh
kyverno test submission/2026-10-16/dataset/kyverno --require-tests --remove-color
kyverno apply submission/2026-10-16/dataset/kyverno/policy.yaml \
  --resource submission/2026-10-16/dataset/kyverno/resources.yaml \
  --policy-report --output-format json --remove-color
```

The second command should return 1 with the recorded pass/fail/skip counts; report timestamps will differ. Preserve new outputs in another directory if collecting a new run. [execution.json](kyverno/execution.json) records the original commands, binary hash, version output, durations and source hashes. Falco reproduction is documented [one level above](../README.md).

## Next collection

Follow the [dataset design](../../../controls/DATASET-DESIGN.md). Acquire selected upstream rules/policies at immutable revisions, preserve licenses and tests, and collect newly authored incident decisions with independent reviewers. Keep all descendants of an incident or fixture family together across splits. This published seed remains a regression set and the session demo defaults remain reference/replay.
