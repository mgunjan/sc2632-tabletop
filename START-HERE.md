# Agentic Kubernetes Guardrails: exercise source

This package accompanies SC2632, presented by Milind Gunjan and Vivek Mayuranathan. It contains the four incident cases, reference controls, review worksheets and recorded evidence. Share the complete package after the exercise: the control-review handout's second page and the lab records contain answers intended for a later reveal.

**What the workshop builds:** a reviewed change set from security intent, with policies, tests, expiring exceptions and phased rollout, plus a scoped Quarantine Mode response and recovery criteria.

**Why:** contain harmful access on shared infrastructure while essential services keep running. The proposal and its tests must show both the forbidden behavior and the legitimate access they preserve. This purpose precedes the Kubernetes/Kyverno primer in the opening deck.

## Your task in the workshop

Your table acts as the incident review team for a shared production Kubernetes platform. Services are operating, suspicious activity is under investigation and the extent of exposure is uncertain. Decide what may proceed, what you hold and what evidence must precede enforcement. Choose one case and an operational constraint, then record intent, proposal decisions, exception conditions, ordered containment and recovery criteria on participant pack page 6.

The opening slides and participant page 1 explain roles, supplied materials and the round sequence. Discuss, write before the reveal, hear the new evidence and revise beside the first decision. Keep participant pages 7/8 and the separate review findings sealed until their round opens. No laptop or YAML authoring is required. Milind and Vivek co-present the demonstrations, reviews and debrief.

The opening also explains the environment for attendees unfamiliar with Kubernetes or Kyverno. A cluster runs workloads, namespaces group resources, Pods run containers and ServiceAccounts provide API identities. Kyverno checks a proposed resource change against policy. A denied create request does not terminate an existing Pod. Network traffic, API permissions and agent tool actions require their own controls. The [incident brief](tabletop/congress-2026/INCIDENT-BRIEF.md) gives the definitions and official documentation links. The incident is fictional; recorded enforcement uses a separate disposable local lab.

For participants new to Kubernetes, the opening starts with the shared application platform and familiar functions before technical names. Application copies are replicas, resource groups are namespaces, and workload identities make management requests. State the required security behavior in your own words. Scores assess the decision and evidence, rather than Kubernetes vocabulary or code.

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

Use a fresh output directory each time. Scenarios `b` and `c` also have reference specs. The reference path uses a supplied answer, compiles policy and runs fixture tests now. It makes no model call, creates no GitHub PR and changes no cluster. Inspect `proposal/PR.md`, `readiness.json`, `control-review.json` and `tests/result.txt`. In case A, six passing privilege checks leave the full proposal **REVIEW_REQUIRED**: API authorization and operational requirements still need their own implementation and evidence.

To replay authentic recorded Jev answers for case A, replace `--mode reference` with `--mode replay` and choose another output directory. Replay is not new inference and does not measure today's provider cost or latency. No API key is needed. Live providers are optional, may incur charges and are unnecessary for the exercise.

## Adapt a control to your environment

Start with [controls/README.md](controls/README.md) and [controls/ENTERPRISE-QUALIFICATION.md](controls/ENTERPRISE-QUALIFICATION.md). Catalog 0.1.0 has ten stable control IDs with template bindings, test references, owners, exception limits and rollback requirements. It is a reference library requiring platform qualification. Pick one unresolved requirement, assign its owner and define an acceptance test on your own platform before considering deployment.

Case D uses a [human RBAC review](scenarios/d-secret-enumeration/review/PR.md), rather than a generator scenario `d`. Its [executed synthetic lab record](submission/2026-10-13/live-rehearsal/case-d/README.md) distinguishes Pod network isolation, Secret-read authorization and Pod-bound credential invalidation. It does not prove application-key rotation or production monitoring delivery. The verifier refuses an unmarked or remote cluster; it is intended only for the separately created disposable k3d rehearsal lab described in [lab/README.md](lab/README.md).

## Read the evidence before drawing a model conclusion

[submission/2026-10-13/REVIEW.md](submission/2026-10-13/REVIEW.md) explains the training pilot, classical baselines and corrections to older recordings. The trained Laya candidate did not qualify for automatic delegation. The small authored evaluation does not establish a production winner between model families. No authenticated OpenAI result is recorded.

The source index records each included file's SHA-256. This is a curated snapshot without repository history, API keys, Kubernetes credentials, model weights or build caches. The Apache-2.0 license is included. Current slides and printable materials are in `submission/2026-10-13/`; earlier results are retained only where they support provenance or replay.
