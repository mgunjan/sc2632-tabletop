# Illustrative Case A decision record

Use during the final debrief, after participants have written their recovery criteria. This is a defensible paper plan built from the supplied Case A facts. It is not a model output, an executed incident response, the only acceptable answer or a claim of verified containment. Do not distribute it as an answer before the decisions are recorded.

## Intent and first disposition

**Intent:** stop suspect payments traffic and prevent new privileged workloads while preserving required dependencies and at least two trusted, healthy service copies.

**Disposition:** hold broad enforcement approval. Review the bounded privilege policy on its own merits. Require the network owner to demonstrate actual traffic restrictions and the identity owner to resolve the API-permission requirement. The fixed privilege CREATE fixtures do not cover those requirements.

**Missing evidence:** denied suspect connections, permitted required connections and effective API permissions for the suspect identity. Name the request source and target for every test. Preserve an unaffected positive control so a general outage is not mistaken for successful containment.

## Temporary access and rollout

The backup job's storage need may be legitimate. Hold its requested bypass until the responsible service owner independently verifies the need, workload/control scope and proposed end time. Record the exception owner and approver as actual named people during a real response; role names in this exercise are proposed responsibilities, not verified approvals.

If the table justifies a narrow grant, require an explicit expiry and an executed revocation check, with a human fallback if cleanup is delayed. A timestamp alone does not revoke an existing session or credential. Refusal is also defensible when the dependency or authority remains unverified.

Choose admission rollout mode per control and compatibility evidence. Immediate denial may be defensible for a confirmed harmful operation; a separate untested control may remain held. Do not infer incident containment from an admitted or denied fixture.

## What the later evidence changes

Another application copy has the same library image. A host-mounted helper passed the original policy set. Q3 prevents replacement copies unless an authorized override applies. Removing one process is therefore an insufficient statement of the response, and a readiness count alone does not establish clean capacity.

**Revised order:** preserve relevant process and audit evidence, identify the affected image/identity scope, and have the service owner verify clean replacement capacity before removing affected copies. Apply and test the authorized network and identity changes. If ongoing harm demands faster restriction, the incident authority must document the service impact and accepted exposure; the exercise does not establish one universal action order.

## Ownership and acceptance evidence

| Requirement | Proposed accountable role | Evidence required before claiming success |
|---|---|---|
| Suspect traffic restriction | Network/platform owner | Suspect paths denied; required dependency paths and an unaffected positive control work |
| Platform API access | Identity/platform owner | Effective permissions reviewed; prohibited operations denied; required named operations preserved |
| Privilege / host access | Policy/platform owner | Reviewed workload and API-path coverage; both allowed and denied requests tested |
| Temporary access | Service owner and independent approver | Exact grant and end time; observed revocation; fallback owner if cleanup fails |
| Clean serving capacity | Service owner | Reviewed replacement image and configuration; at least two trusted, healthy copies and dependency checks |
| Evidence and recovery authority | Incident lead | Preserved evidence record; authorized criteria for lifting restrictions and restoring controls |

## Recovery and transfer

Return toward Q0 only after the authorized incident lead reviews denied suspect paths, working essential dependencies, scoped identity permissions, clean serving capacity and restored guardrails. Record a rollback trigger if a dependency fails or an unsafe path remains. Quiet alerts alone do not establish recovery.

For the attendee's own environment, record one requirement, its actual owner and the acceptance evidence still missing. Ask a neighboring table which fact would reverse that decision.

Sources: Case A and the later finding in [the participant pack](../../submission/2026-10-13/PARTICIPANT-PACK.pdf); [the prepared proposal](../../output/frozen-a/PR.md); [the Quarantine Mode playbook](../../quarantine/quarantine-mode.md); and [the recorded lab evidence](../../submission/2026-10-13/live-rehearsal/README.md). These inputs establish the exercise facts, not that this illustrative plan has executed successfully.
