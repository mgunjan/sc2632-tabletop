# Case D reference review: narrow the monitoring identity's read authority

**Manually authored exercise proposal. No GitHub PR, model-generated RBAC or production deployment is claimed.** The fictional identity is `system:serviceaccount:payments:monitoring-agent`. A separate lab verifier uses fresh namespaces, a collector identity and synthetic Secrets to test the control boundary.

The old dashboard integration left a cluster-wide Secret GET/LIST binding. Stop outside-namespace reads, preserve the specifically required monitoring access, retain evidence and replace the potentially exposed Kubernetes credential. Changing admission rules or quarantining the Pod alone cannot remove a copied credential's API authority.

## Proposed changes for human review

1. Inventory every RoleBinding and ClusterRoleBinding affecting this identity. Confirm the actual required resources with the monitoring owner. Additional bindings can preserve excess rights even when this binding is removed.
2. Add a namespaced Role and RoleBinding allowing GET of exactly the approved monitoring Secret and target ConfigMap. Verify required access before cutting over. Do not retain namespace-wide Secret LIST as a convenience.
3. Remove the identity's excess cluster-wide binding. Review every subject on the binding first; do not rewrite a shared ClusterRole and inadvertently change other identities.
4. Bring up a reviewed replacement collector and verify its credential, required API connectivity and monitoring delivery. Preserve the original workload's evidence before replacement.
5. Retire the old bound workload/credential and verify the old credential fails authentication. Inventory application credentials that the old identity could read and coordinate their rotation with their respective service owners.

Illustrative scoped rule for the fictional monitoring identity:

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: monitoring-required-reads
  namespace: payments
rules:
  - apiGroups: [""]
    resources: ["secrets"]
    resourceNames: ["monitoring-client-key"]
    verbs: ["get"]
  - apiGroups: [""]
    resources: ["configmaps"]
    resourceNames: ["metrics-targets"]
    verbs: ["get"]
```

The matching RoleBinding must name the independently verified ServiceAccount. These are proposed names and requirements, not an authorized production allowlist.

## Acceptance evidence

Require actual GET/LIST requests with the intended credential, not only a manifest inspection or `can-i` result. Outside-namespace synthetic Secret reads must fail authorization; the named in-namespace Secret and ConfigMap GET must succeed; broad in-namespace Secret LIST must fail. Confirm a reachable positive control so an unavailable API is not mistaken for containment.

Test network containment separately: the suspect's new API connection is blocked, an unaffected positive control still connects, and the copied credential's out-of-Pod request is tested independently. Confirm clean replacement connectivity before revoking the old credential. Authentication failure of a Pod-bound Kubernetes token does not revoke application keys already read from Secrets.

The [executed lab record](../../../submission/2026-10-13/live-rehearsal/case-d/README.md) supplies synthetic evidence for these boundaries. Its stand-in HTTP health check is not production metrics delivery, and it collects no server audit export. Production audit evidence, real dependencies, approval identity and external-key rotation remain required.

## Exceptions, rollout and rollback

No admission PolicyException can grant or revoke Secret-read authorization. A temporary RBAC grant needs its own verified approver, exact resource scope, owner, expiration and independently tested revocation mechanism. A TTL annotation on a Role is not an implementation of that mechanism.

Stage the scoped grant, verify positive access, remove the broad binding, verify denied access and then perform credential/workload replacement. Rollback can restore only the reviewed minimum required resource access; restoring the compromised broad binding is a new security decision. Name the monitoring, identity, incident and application-credential owners before approving the change.
