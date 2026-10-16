# Kubernetes control library

The model proposes a control ID. This versioned library describes the implementation, the coverage it can actually provide, and the evidence a reviewer still needs. It is a reference foundation for enterprise policy, not a qualified production release.

`catalog.json` contains ten stable IDs: seven existing admission templates, an RBAC requirement, rollout governance, and unsupported requirements. `schema.json` checks its structure. `generator/control_library.py` checks the catalog against the model's decision vocabulary and the compiler functions, and rejects unknown controls, duplicate IDs and invalid test paths.

Every new compiler or policy-agent proposal includes `control-review.json` and a PR section with:

- Control and catalog version, exact parameters and rendered policy hash.
- Enforcement layer, covered operations and explicit coverage gaps.
- Required positive/negative test references and platform evidence.
- Owning role, approving role, proposed exception time limit and rollback guidance.

The catalog never grants exceptions, marks unexecuted tests passed, or authorizes deployment. The TTL ceilings are proposed reference limits for enterprise owners to ratify. They are flagged in review metadata; this is not a live exception admission controller.

```sh
python generator/control_library.py
python generator/control_library.py --spec generator/spec-a.json --out /tmp/control-a-review
python generator/test_control_library.py
```

For example, `ACG-POD-001` prevents privileged containers and requires `allowPrivilegeEscalation=false` in regular and init containers on Pod CREATE. It does not claim the full Restricted Pod Security Standard: non-root identity, capabilities, seccomp, existing Pods and debug subresources need other controls. `ACG-NET-001` validates an egress-profile label; CNI connectivity evidence is required to establish containment.

Use the maintained [Kyverno policy library](https://github.com/kyverno/policies) as a source for additional implementations and the [Kubernetes Pod Security Standards](https://kubernetes.io/docs/concepts/security/pod-security-standards/) for workload security requirements. Our current policies were authored in this project; none is represented as a vendored upstream policy. Import future policies at an immutable revision with license attribution and tests. Framework crosswalks must map exact behavior; a control name is not a compliance certification.

Before promoting a catalog release for an enterprise, collect target-platform evidence for API/CNI behavior, effective RBAC, admission-controller availability, load and failure handling, exception expiry, approval provenance and rollback. Protect policy and exception writers from the agent. Existing prefix-based exception matches require a scope review because they can also match similarly named workloads. Bind approval to catalog, compiler, spec and rendered artifact hashes.

[ENTERPRISE-QUALIFICATION.md](ENTERPRISE-QUALIFICATION.md) defines the training-label contract, per-layer qualification work and release gates. The local Laya training run is measured; its candidate is rejected for delegation because confidence increased without better regression accuracy. Training and qualifying enforcement are separate work.

[DATASET-DESIGN.md](DATASET-DESIGN.md) specifies how selected Falco/Kyverno sources, executed behavior and independent response labels form separate linked collections. The initial 20-case evidence seed is regression-only; it is not a training corpus or a new independent model test.

The [expanded upstream dataset](../datasets/guardrails/README.md) adds pinned policy/rule catalogs, executed test/replay observations and a local lexical retrieval baseline. Its 184 reference Kyverno documents and 96 Falco rules are candidate implementations; they do not automatically become new compiled controls or qualified incident responses.

This makes an effective tabletop challenge: ask each team which enforcement layer has actually been proved, which exception it would authorize, and which missing evidence prevents promotion. Changing the model cannot resolve a missing enforcement component.
