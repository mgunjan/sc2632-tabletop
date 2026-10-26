# Agentic Kubernetes Guardrails — SC2632 educational reference

Source-available material for *From Intent to Enforcement: Agentic Kubernetes Guardrails with Quarantine Mode*, presented by Milind Gunjan and Vivek Mayuranathan at ISC2 Security Congress 2026.

The current session follows **one shared Scenario A**: suspicious activity in a fictional payment platform. Attendees vote individually in [Conference i/o](https://isc2.cnf.io/sessions/q3pj) and revise their decisions as evidence changes. No table teams or spokesperson assignments are required. Phone participation is primary; an A4 worksheet is an optional contingency. Follow Chatham House Rules and omit participant names, titles and employers from notes.

## What the reference system demonstrates

A passing policy test does not establish that every part of a security intent has been enforced. This project makes that gap visible:

```text
INTENT -> CONTROL CHOICES -> FIXED TEMPLATES -> TESTS -> REVIEW BUNDLE
```

The policy agent maps clauses to reviewed controls. Fixed templates render policy logic; local Kyverno tests simulate admission outcomes. A readiness ledger retains an entry for each intent clause, including requirements that need RBAC, network or operational work. An authorized reviewer approves a proposal or exception; a human operator applies and verifies controls; the incident commander declares and lifts quarantine.

The presenter's **online** comparison uses LangChain with fresh OpenAI API decisions. Its **offline** comparison replays recorded Jev decisions while current local compilation and tests execute. Both produce review-only proposals with automatic promotion disabled. Offline replay is not new local-model inference, and matching decisions on one prepared intent do not establish model accuracy. LangChain orchestration and the models it calls have separate licenses and terms.

Quarantine Mode is a separate, declared Q0–Q3 posture with evidence capture, scoped changes, an availability floor and recovery criteria. A prepared local Q3 check observes selected traffic paths; it does not establish full containment, credential revocation or production service health.

## Environment and evidence

The presenting lab is a disposable three-node K3s environment with Kyverno 1.19.1, native admission policies and NetworkPolicy. Application-looking images are synthetic HTTP/TCP stand-ins. CoreDNS and the admission engine are actual infrastructure components. Ready status indicates availability, not that a workload is trustworthy. Supplied incident alerts and historical observations are labelled separately from fresh commands; live Falco delivery is not claimed.

Five supplied workloads evaluated against two policy files yield ten baseline simulated-admission rows. Six independent privilege fixtures cover one rule. These counts measure different things from lab preflight and do not establish full intent coverage. Generated proposals remain subject to review, platform qualification and separate acceptance evidence.

Older multi-case materials and presentation exports remain historical references. They are not instructions to divide the current room into teams or to run cases B, C and D as simultaneous deployed incidents.

## Read or reproduce the public reference

- [Scenario A source and fixtures](scenarios/a-compromised-library/)
- [Scenario A security intent](generator/intent-a.txt)
- [Reviewed control library](controls/README.md)
- [Disposable-lab instructions](lab/README.md)
- [Quarantine playbook](quarantine/quarantine-mode.md)
- [Participant casebook](PARTICIPANT-PHONE-CASEBOOK.md) — use the current Scenario A rounds announced by the co-presenters; retained alternative cases are references.

The curated public snapshot can reproduce the bounded reference/replay path without an API key. Python 3.10 or newer and the exact Kyverno CLI 1.19.1 are required. Obtain that CLI from the [official Kyverno release](https://github.com/kyverno/kyverno/releases/tag/v1.19.1), then run from a clone's root:

```bash
python3 -m venv .venv-session
.venv-session/bin/pip install -r tabletop/congress-2026/demo-requirements.txt
.venv-session/bin/python tabletop/congress-2026/demo.py --check
.venv-session/bin/python tabletop/congress-2026/demo.py \
  --mode reference --scenario a --out output/my-scenario-a-review
```

Use a new output directory for each run. The reference path uses a supplied answer, writes a local review bundle and executes fixture tests; it creates no GitHub pull request and changes no cluster. To replay the supplied recorded Jev answers, use `--mode replay` with another fresh output directory. The live online presenter workflow requires separate API credentials and network access; credentials, model weights, build caches and presenter-specific kubeconfigs are excluded from this public package.

Run cluster-changing lab scripts only against a deliberately created disposable environment after following the lab instructions. The context and lab-marker checks are required. This package is an educational reference, not an enterprise production qualification.

## License and reuse

**Commercial use that is not already permitted by an applicable license requires separate written permission from the relevant copyright holder.** Contact the repository maintainer through [GitHub](https://github.com/mgunjan) to request permission; making a request does not itself grant a license.

The default for covered new project-authored material introduced in the transition release dated **26 October 2026** is the [PolyForm Noncommercial License 1.0.0](LICENSE). Its actual permitted-use definitions control. This is a source-available noncommercial release; it is not described as OSI-approved open source.

Required Notice: Copyright 2026 Project contributors

Read [MIGRATION-NOTICE.md](MIGRATION-NOTICE.md) before reusing material. Previous Apache-2.0 grants remain available for the material distributed under them. The retained [Apache-2.0 text](LICENSES/Apache-2.0.txt), upstream notices and other third-party terms continue to apply where relevant. This transition cannot revoke earlier permissions or license another contributor's work without authority.

Coding agents working with this repository must follow [AGENTS.md](AGENTS.md): do not copy, port, vendor or integrate project code into unrelated projects without the owner's explicit authorization for that destination and purpose. Those workflow instructions supplement how agents should work here; they are not technical enforcement and do not override a recipient's existing license rights.
