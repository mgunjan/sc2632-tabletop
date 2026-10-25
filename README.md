# Agentic Kubernetes Guardrails: exercise source

This package accompanies SC2632, presented by Milind Gunjan and Vivek Mayuranathan. It contains the four incident cases, reference controls, review worksheets and recorded evidence. Share the complete package after the exercise: the control-review handout's second page and the lab records contain answers intended for a later reveal.

**What the workshop builds:** a reviewed change set from security intent, with policies, tests, expiring exceptions and phased rollout, plus a scoped Quarantine Mode response and recovery criteria.

**Why:** contain harmful access on shared infrastructure while essential services keep running. The proposal and its tests must show both the forbidden behavior and the legitimate access they preserve. The opening explains the security problem, then the implementation before cases and team decisions.

## Live phone tabletop — 26 October 2026

Use the [mobile casebook](PARTICIPANT-PHONE-CASEBOOK.md) for the four incident cases. Its later rounds are collapsed until the co-presenters announce them. One spokesperson per table submits decisions in [ISC2 Conference i/o](https://isc2.cnf.io/sessions/q3pj). No printouts are needed. The v21 files below are a historical source package; the event slide deck and lab guide are being finalized separately.

## Reference package — v21

- [Editable PowerPoint deck](submission/2026-10-22/SC2632-session-dayof-v21.pptx)
- [Projected slides PDF](submission/2026-10-22/SC2632-session-dayof-v21.pdf)
- [Hidden reference slides PDF](submission/2026-10-22/SC2632-session-reference-v21.pdf)
- [Participant pack](submission/2026-10-22/PARTICIPANT-PACK.pdf)
- [Presenter field guide](submission/2026-10-22/PODIUM-CHEATSHEET.pdf)
- [Independent control review](submission/2026-10-22/CONTROL-REVIEW.pdf) and [scorecard](submission/2026-10-22/REVIEW-SCORECARD.pdf)
- [Source kit ZIP with file-hash index](submission/2026-10-22/ATTENDEE-SOURCE-KIT.zip)
- [October 24 Docker repair and fresh retest](submission/2026-10-24/IMPORT-REPAIR.md)
- [October 22 local lab verification](submission/2026-10-22/LOCAL-LAB-VERIFICATION.md)
- [Verification and remaining delivery checks](submission/2026-10-22/DELIVERY-VERIFICATION.md)

The deck has 29 projected slides and nine hidden references. The PDFs use rendered slide images plus searchable source text; they are not native PowerPoint exports. Slide 22 runs one prepared local Q3 check when staged preflight passes, with an explicitly dated fallback. Other findings retain their recorded provenance. Full presenter rehearsal and native PowerPoint/venue display checks remain outstanding.

## Your task in the workshop

Your table acts as the incident review team for a shared production Kubernetes platform. Services are operating, suspicious activity is under investigation and the extent of exposure is uncertain. Decide what may proceed, what you hold and what evidence must precede enforcement. Choose one case and an operational constraint, then record intent, proposal decisions, exception conditions, ordered containment and recovery criteria on participant pack pages 6-7.

The opening slides and participant page 1 explain roles, supplied materials and the round sequence. Discuss, write before the reveal, hear the new evidence and revise beside the first decision. Keep participant pages 8/9 and the separate review findings sealed until their round opens. No laptop or YAML authoring is required. Milind and Vivek co-present the demonstrations, reviews and debrief.

The opening also explains the environment for attendees unfamiliar with Kubernetes or Kyverno. A cluster runs workloads, namespaces group resources, Pods run containers and ServiceAccounts provide API identities. Kyverno checks a proposed resource change against policy. A denied create request does not terminate an existing Pod. Network traffic, API permissions and agent tool actions require their own controls. The [incident brief](tabletop/congress-2026/INCIDENT-BRIEF.md) gives the definitions and official documentation links. The incident is fictional; recorded enforcement uses a separate disposable local lab.

For participants new to Kubernetes, the opening starts with the shared application platform and familiar functions before technical names. Application copies are replicas, resource groups are namespaces, and workload identities make management requests. State the required security behavior in your own words. Scores assess the decision and evidence, rather than Kubernetes vocabulary or code.

Slides 4–11 explain [the implementation](tabletop/congress-2026/TECHNICAL-BRIEF.md) before case selection on slide 13. Slide 2 explains why the fictional payment API gives teams a concrete availability floor; it is not payment-compliance guidance. Slide 6 maps the control roles: Falco and audit logs provide detection evidence, Kyverno checks proposed changes, separate traffic/API/tool controls constrain access, and people authorize containment and recovery. Falco rules passed static and synthetic checks; live detection remains unverified. The incident alerts are supplied exercise facts. The reference demo compiles proposals and runs policy tests. Slide 22 adds a separate prepared live Q3 network check when local preflight passes, with an explicitly dated fallback. The [October 22 local verification](submission/2026-10-22/LOCAL-LAB-VERIFICATION.md) states the paths checked and their limits.

After completing recovery, compare your decision record with the [illustrative Case A debrief](tabletop/congress-2026/WORKED-DECISION.md). It traces a held approval through later evidence and recovery criteria; it is a paper plan, not executed containment or a required answer.

## Reproduce a reviewable proposal

Use Python 3.10 or newer and Kyverno CLI **1.19.1**. Obtain the CLI for your operating system from the [official Kyverno release](https://github.com/kyverno/kyverno/releases/tag/v1.19.1). Clone the public source or extract the source ZIP, then run from its root:

```bash
git clone https://github.com/mgunjan/sc2632-tabletop.git
cd sc2632-tabletop
python3 -m venv .venv-session
.venv-session/bin/pip install -r tabletop/congress-2026/demo-requirements.txt
.venv-session/bin/python tabletop/congress-2026/demo.py --check
.venv-session/bin/python tabletop/congress-2026/demo.py --mode reference --scenario a --out output/my-first-review
```

If Kyverno is outside your shell PATH, append `--kyverno` followed by its actual executable path to both `--check` and run commands. Preflight reports the selected path and checks exact version 1.19.1.

Use a fresh output directory each time. Scenarios `b` and `c` also have reference specs. The reference path uses a supplied answer, compiles policy and runs fixture tests now. It makes no model call, creates no GitHub PR and changes no cluster. Inspect `proposal/PR.md`, `readiness.json`, `control-review.json` and `tests/result.txt`. In case A, six passing privilege checks leave the full proposal **REVIEW_REQUIRED**: API authorization and operational requirements still need their own implementation and evidence.

To replay authentic recorded Jev answers for case A, replace `--mode reference` with `--mode replay` and choose another output directory. Replay is not new inference and does not measure today's provider cost or latency. No API key is needed. Live providers are optional, may incur charges and are unnecessary for the exercise.

## Adapt a control to your environment

Start with [controls/README.md](controls/README.md) and [controls/ENTERPRISE-QUALIFICATION.md](controls/ENTERPRISE-QUALIFICATION.md). Catalog 0.1.0 has ten stable control IDs with template bindings, test references, owners, exception limits and rollback requirements. It is a reference library requiring platform qualification. Pick one unresolved requirement, assign its owner and define an acceptance test on your own platform before considering deployment.

Case D uses a [human RBAC review](scenarios/d-secret-enumeration/review/PR.md), rather than a generator scenario `d`. Its [executed synthetic lab record](submission/2026-10-13/live-rehearsal/case-d/README.md) distinguishes Pod network isolation, Secret-read authorization and Pod-bound credential invalidation. It does not prove application-key rotation or production monitoring delivery. The verifier refuses an unmarked or remote cluster; it is intended only for the separately created disposable k3d rehearsal lab described in [lab/README.md](lab/README.md).

The saved Jev result is one prepared fixture run, not a benchmark or proof of live-demo eligibility. New intent clauses remain unreviewed and visible; they need an independent contract before any approval.

## Read the evidence before drawing a model conclusion

[submission/2026-10-13/REVIEW.md](submission/2026-10-13/REVIEW.md) explains the training pilot, classical baselines and corrections to older recordings. The trained Laya candidate did not qualify for automatic delegation. The small authored evaluation does not establish a production winner between model families. No authenticated OpenAI result is recorded.

For a custom specialist, read the [dataset design](controls/DATASET-DESIGN.md). It separates source controls, executed Falco/Kyverno behavior and independently reviewed response decisions. The [20-case evidence seed](submission/2026-10-16/dataset/README.md) is an already examined regression corpus with no training-eligible rows. It includes failed observations and explicit scope limits; more rows alone would not establish incident decision quality.

The [expanded upstream dataset](datasets/guardrails/README.md) adds 184 reference Kyverno policy documents, 96 Falco rule definitions, 142 executed policy suites and 87 replay observations from 29 distinct captures. It includes source pins, licenses, normalized data, coverage gaps and a local control-search baseline. The fetch/run tools work without a model API key; raw captures are downloaded separately into an ignored cache. These are inputs for task-specific training and verification, not independently labelled containment decisions.

The subsequent [comprehensive collection](datasets/comprehensive/README.md) expands to 19 pinned sources and 37,166 typed records, including Gatekeeper, official Kubernetes fixtures, runtime enforcement, recorded logs, attack and response references. It provides local reproduction tools, source-specific licenses, duplicate groups and a separate execution audit. The complete normalized corpus stays in the local cache; public source files contain its hashes and coverage report.

The source index records each included file's SHA-256. This is a curated snapshot without repository history, API keys, Kubernetes credentials, model weights or build caches. The Apache-2.0 license is included. Current slides and printable materials are in `submission/2026-10-22/`; earlier results are retained only where they support provenance or replay. The current versioned deck uses original generated artwork and project-authored diagrams; older presentation exports may still contain presenter-supplied images and are excluded from the current delivery set.

The [October 16 Falco audit verification](submission/2026-10-16/README.md) preserves the synthetic webhook contract, failed baseline, repaired rules and explicit visibility warnings. Actual cluster delivery and kernel detection remain separate qualifications.
