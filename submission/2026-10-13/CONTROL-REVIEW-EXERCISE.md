# Four-minute control review

This is the main proposal-review round at minutes 45–49; it replaces the earlier three-question model-choice bonus. Milind and Vivek are co-presenters. The artifacts below come from the actual local trained-Laya Scenario A run; this is recorded evidence, not live containment.

Vivek displays the operator's intent and proposed change. Each table records one disposition: authorize a bounded subset, request revision, require more evidence, or reject. It must identify the unresolved requirement and the evidence needed to resolve it.

## Participant card

**Intent:** Deny new east-west communication from the payments namespace while preserving known dependencies. Prevent privilege escalation. Restrict the compromised workload's Kubernetes API access. Preserve availability, stage the rollout and time-box exceptions.

**Proposal:** One generated privilege policy, with Audit/Warn/Deny manifests. Six fixed positive/negative Pod CREATE privilege tests pass. No network control or RBAC change is included.

| Requirement | Model choice | Reported answer confidence | Routing |
|---|---|---:|---|
| East-west restriction | Privilege control | 0.8986 | Accepted |
| Privilege escalation | Privilege control | 0.8574 | Accepted |
| Kubernetes API access | Privilege control | 0.5895 | Human review |
| Availability/staging/expiry | Privilege control | 0.9107 | Accepted |

The temperature was fitted on a separate synthetic calibration set. It has not been validated for this incident distribution.

1. Which intent requirement has actually been tested?
2. What must be added or proved before the containment change can proceed?
3. Who owns each missing control, and what availability, evidence and rollback criteria constrain approval?

## Co-presenter reveal

Milind shows `readiness.json`: **INCOMPLETE_PROPOSAL**, with unexpected mappings for network and process requirements, and unresolved API access. The privilege policy's six tests pass; they establish six privilege behaviors only.

Vivek asks a table to defend its disposition using the control library:

- `ACG-NET-001`: dependency-aware NetworkPolicies and target-CNI connectivity evidence.
- `ACG-IAM-001`: effective RBAC, credential response and actual-principal authorization tests.
- `ACG-GOV-001`: approved rollout conditions, owned exceptions, verified expiry and rollback.

The review is complete only when the team distinguishes proposed coverage, tested behavior and still-required evidence. Model confidence cannot substitute for any of them.

Source: [recorded run](laya-training/workflow-cost/run-1/agent-run.json), [fixed test output](laya-training/workflow-cost/run-1/tests/result.txt), [independent ledger](laya-training/workflow-cost/run-1/readiness.json), [control catalog](../../controls/catalog.json).
