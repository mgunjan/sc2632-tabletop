# Quarantine Mode — a leveled, reversible containment posture for Kubernetes

Quarantine Mode is a **named posture with levels**, not a button. Each level has an entry
trigger, a control delta, a declaring authority, a lifting authority, exit criteria, and
an availability floor. Descent is staged. Evidence is captured before any control touches
the suspect.

The individual moves are old. NetworkPolicy isolation, cordon/drain, RBAC removal, and
"label the Pod you are quarantining" are all in vendor docs (Google's GKE security
mitigations doc uses that exact phrase) and in tools like Falco Talon. What this document
adds is the part those sources leave out: **levels, authority, and exit criteria.**

## Four rules

1. **Evidence before containment, at every level.** Run `capture-evidence.sh` before
   applying Q2 or Q3. Containment that destroys evidence is a second incident, and — as
   Scenarios A and B show — the evidence is often what tells you which containment is right.
2. **A level without exit criteria is not a level; it's a panic button.**
3. **Descent is staged.** Q3 → Q2 → Q1 → Q0, each step declared by the authority that
   raised it, each with its own check. There is no single "all clear."
4. **The availability floor is stated per level.** If a level cannot honor it, that is an
   incident-commander decision made in advance, not a surprise during payroll.

## The levels

| | **Q0 Normal** | **Q1 Freeze** | **Q2 Constrain** | **Q3 Isolate** |
|---|---|---|---|---|
| **Entry trigger** (any one) | — | One high-confidence runtime alert; OR first anomalous cross-namespace connection | Confirmed lateral-movement attempt; OR credential misuse (SA token used from a workload); OR Q1 signal repeats | Active exfiltration; OR privilege escalation succeeded; OR Q2 controls bypassed |
| **Control delta** (cumulative) | Baseline guardrails, Deny | New PolicyExceptions refused without owner + TTL + IC override (annotation set by an incident commander) · **agents frozen: every write by an identity in the `agents` namespace refused, by a native policy** (`q1/freeze-agent-changes.yaml`) · rollout promotions paused · audit logging raised · affected-scope policies moved to Deny | **Evidence capture first.** Then: ingress default-deny with named allows · suspect Pod → DNS-only (UDP and TCP port 53) · incident team inventories effective RBAC and narrows both RoleBindings and ClusterRoleBindings, then verifies allowed and denied requests; this is not automated · suspect labels protected: only an incident commander can loosen them (`q2/protect-quarantine-labels.yaml`, native) · Audit-only controls → Deny | Suspect Pods deny-all · no new Pods without IC override (annotation + incident-commander identity) · repeat effective-RBAC review across RoleBindings and ClusterRoleBindings · node cordon (**after PDB check**) · signed-image-only (**not built**: a policy decision, no artifact in this repo) |
| **Apply** | `network/payments-baseline-networkpolicies.yaml` | `kubectl apply -f quarantine/q1/` | `capture-evidence.sh`, then `kubectl apply -f quarantine/q2/` | `kubectl apply -f quarantine/q3/` |
| **Declares** | — | On-call platform engineer, self-declare | Incident commander | Incident commander + security lead |
| **Lifts** | — | Same | **Two-person** | IC + security lead, with evidence confirmed |
| **Exit criteria** | — | Alert triaged benign; OR 4h with no further signal | Root cause identified; IOCs cleared from scope; evidence secured off-cluster with hashes | Explicit rollback criteria met (see scenario); then staged descent |
| **Availability floor** | 100% | 100% — nothing running is touched | Approved flows continue; if the allow-list is right, users see nothing | **Degraded.** Continuity from clean replicas on another node pool / namespace. The posture card says what's acceptable |
| **Automate?** | — | Defensible (touches nothing running) | No | No |

## What each level does NOT do

- **Q1** does not stop an attacker who is already inside. It stops the *organization*
  from making things worse in the first 20 minutes: no quick-fix exceptions, no
  promotions, no "just this once", and no agent changes. The agent freeze is enforced
  by the platform, not asked of the agent: in the Replit / SaaStr incident (July 2025)
  an agent ran destructive commands during a declared code freeze. Scope: changes that
  go through the Kubernetes API, and identities in the `agents` namespace. The freeze is a
  native ValidatingAdmissionPolicy, not a Kyverno policy, so it holds even if the agent
  tries to switch Kyverno off (Finding 4).
- **Q2** does not kill anything. The suspect keeps running, DNS-only, observable. That is
  deliberate: a running suspect is evidence; a killed one is a story.
- **Q3** does not restore service. It stops the bleeding. Restoration is a separate,
  explicit decision (usually: clean image + signed-image-only, which this repo does not build, + staged descent).

## The PDB capacity stall when Q3 blocks replacement

Shown live on k3s by `scripts/lab-e2e.sh`. `payments-api` runs three replicas with a
PodDisruptionBudget of `minAvailable: 2`, and two replicas are flagged suspect.

1. Evict suspect 1. **Allowed** (3 → 2). Eviction deletes the Pod, and with it anything you
   had not already captured.
2. The ReplicaSet tries to replace it. **Q3's "no new Pods without IC override" refuses the
   replacement**. The events say `FailedCreate … Quarantine Q3 is active`. Capacity stays at 2.
3. Evict suspect 2. **Refused by the PDB** (`TooManyRequests: Cannot evict pod as it would
   violate the pod's disruption budget`). Q3 prevents the replacement, so the second voluntary
   eviction remains blocked until an operator restores healthy capacity, authorizes a reviewed
   clean replacement, grants a scoped exception, or steps down from Q3. This is a capacity stall,
   not a Kubernetes deadlock or a permanent condition.

The operator must resolve the interaction deliberately. Options, in order:

1. **Don't evict to contain. Isolate in place.** Q3's network step (below) cuts a suspect off
   completely without deleting it. Cordon the node so nothing new lands there. The suspect stays
   as evidence and keeps its place in the PDB count, so no eviction is attempted.
2. If a suspect must go, **restore capacity first**, then evict. Annotating the Deployment's
   template does *not* help: Q3's override is checked against who makes the request, and the
   ReplicaSet controller is not an incident commander (it would also roll every replica, in
   Scenario A onto the same compromised image). Either the IC creates the clean replacement Pods
   directly (`scenarios/a-compromised-library/fixtures/q3-override.yaml` is one), or the IC grants a
   scoped, expiring PolicyException to `q3-no-new-pods-in-payments`, or you step back down to Q2.
3. Delete the suspect directly (`kubectl delete pod` is not an eviction and ignores the PDB).
   The replacement is still refused under Q3, so direct deletion can lose evidence and reduce capacity.
4. Edit the PDB. Last resort; log it as an incident action.

None of the containment playbooks we reviewed mention the PDB interaction, and we have not
seen this interaction covered by the offline policy tests; the sequence is demonstrated by the recorded live lab.

## Found on a live cluster (and not by any offline test)

Each of these passed every offline suite and failed the first time it met a real API server,
CNI or kubelet. Each now has a live assertion in `scripts/lab-e2e.sh`:

| What | Why offline tests missed it | Fix |
|---|---|---|
| **Q3 "deny-all" left the suspect DNS.** NetworkPolicies only add allows, so a deny-all cannot cancel Q2's DNS allow. The suspect kept a DNS channel out | Offline tests check each policy on its own, never the union | Q2's DNS allow skips Pods labelled `trustfall.example/isolated=true`; Q3 applies that label as its second step |
| **Suspects still received gateway traffic at Q2.** They were DNS-only, so those customer requests failed | Same: no test of how the policies combine | Q2's gateway allow skips `trustfall.example/suspect` Pods. It was also **still a Service endpoint**. Now the Service selects `trustfall.example/in-rotation=true` and evidence capture sets it `false`: out of rotation, still owned by its ReplicaSet, still running |
| **`capture-evidence.sh` captured no process list.** `kubectl debug` without `--attach` returns when the container is *created*; its output lives only in that container's log | The fake kubectl returned output where the real one returns none | Create, wait, then `kubectl logs -c <debug>` |
| **It hashed error messages and called them evidence.** Run against a terminating Pod, or with the kubelet unreachable, it sealed a manifest of `Error from server` lines and exited 0 | Nothing simulated a Pod that was already going away | Preflight refuses a terminating Pod (exit 3); a missing piece makes the capture `INCOMPLETE` (exit 4) |
| **The debug container is a write.** It is recorded permanently in `spec.ephemeralContainers` | "Exactly one mutating call" counted only `label` | Counted and documented as the evidence footprint; `pod.yaml` is captured after it |
| **Admission policies miss `kubectl debug`.** A docker.io image entered a running payments Pod under Q2's registry Deny, via `pods/ephemeralcontainers` | Policies match `pods`; nothing exercised the subresource | **Fixed:** `quarantine/q2/ephemeral-containers.yaml` covers the subresource, for the containers a request *adds*. The first version checked all of them and made any Pod that had ever been debugged undebuggable, including by incident response. Evidence capture now needs the approved debug image (`DEBUG_IMAGE=`) |
| **`kubectl scale` slipped past the agent guardrail.** Scenario C's policy matched `deployments`; `kubectl scale` writes the `deployments/scale` subresource, which that rule never sees, so the agent's 3→12 scale-up was admitted | The offline `kyverno test` fixtures patched `deployments`, never the subresource | Policy and generator now also match `deployments/scale` and `statefulsets/scale` |
| **The agent scaled the policy engine to zero.** A ServiceAccount with the common "patch/scale Deployments cluster-wide" right scaled `kyverno-admission-controller` to 0; Kyverno then deleted its own webhooks (by design, to avoid fail-closed outages) and every Kyverno admission rule, the quarantine levels' included, stopped applying with no error (NetworkPolicies kept holding) | Kyverno excludes its own namespace from its webhooks, so no Kyverno policy can cover this; nothing offline models the engine's own availability | **`guard/protect-the-guardrail.yaml`**: a native ValidatingAdmissionPolicy (evaluated in the API server, so it survives Kyverno being down) that lets only Kyverno itself and platform admins change or remove Kyverno's Deployments and webhook configurations. It does not cover Kyverno's ConfigMap, policy or PolicyException deletes, or the quarantine's own native policies: those are RBAC's job today (post-conference work). Self-contained — no paramRef, which would be its own fail-closed dependency |
| **The old e2e hid its own NetworkPolicy test.** Its probe used docker.io's busybox, Q2 refused it, and the test "skipped" | It never ran on a cluster | Probes use the approved-registry stand-in; skips are failures |

## The guardrail that blocked its own containment

This one happened to us while testing, which is why it is here.

`capture-evidence.sh` marks the suspect by relabelling it `trustfall.example/egress-profile=quarantined`
so the Q2/Q3 NetworkPolicies select it. A label change is an **UPDATE** admission request. Our
first version of the guardrails refused it, twice over:

1. `restrict-egress-profile` only admitted `db`, `monitoring`, `none` — so it refused the move
   to `quarantined`.
2. `deny-sa-token-for-agent-sidecars` (Scenario B) evaluated on UPDATE too — and the suspect
   Pod predated the policy, so it didn't comply, so *any* change to it was refused.

The guardrail you deployed for the incident would have stopped you containing the incident.
The fix, now in every policy and in the generator's templates:

- `quarantined` is always an admissible profile. It is strictly more restrictive than any
  approved one (no egress at Q0, DNS only at Q2).
- Checks on **immutable Pod-spec fields** (privilege escalation, SA-token mount) evaluate on
  **CREATE only**.
- **Image** checks evaluate on CREATE, and on UPDATE **only if an image changed**
  (`oldObject` comparison) — so `kubectl set image` on a running Pod is still caught.

Regression tests: `scenarios/{a,b}/tests/kyverno-test-quarantine-relabel.yaml` simulate the
relabel as an UPDATE — including a Pod with a non-compliant image under Q2's Deny.

The general rule: **every guardrail you ship must be tested against the containment actions
you will take under it.**

## Evidence capture — what `capture-evidence.sh` does and doesn't do

Does: checkpoint via the kubelet Checkpoint API where the CRI supports it (KEP-2008). On k3s
v1.33 / containerd 2.0 the API is on by default and fails only for want of CRIU on the node:
`CRIU binary not found or too old`. Install CRIU on the node (and have a kernel built with
CHECKPOINT_RESTORE) if you want memory. Then: a live process/socket/env
snapshot via an ephemeral debug container; logs, spec, events, node; SHA-256 manifest;
then — and only then — labels the Pod as suspect.

Doesn't: memory dump (needs node access), disk image (needs node access), network capture.
If you need those, that's a Q3 decision and a node-level runbook.

## Relative vs absolute expiry

Two mechanisms ship for time-boxed exceptions:

- `cleanup.kyverno.io/ttl: 24h` label — Kyverno's cleanup controller deletes the
  resource 24h after **creation**. Native; what `kyverno apply --generate-exceptions`
  emits. Relative.
- `trustfall.example/expires-at: "2026-10-27T23:00:00Z"` annotation + a `DeletingPolicy` —
  deletes at a **wall-clock time**. Regulated postures usually want this: "expires when
  someone is on shift", not "24 hours from whenever it was applied at 3 a.m."

Kyverno's `PolicyException` has no expiry field of its own. Say so.
