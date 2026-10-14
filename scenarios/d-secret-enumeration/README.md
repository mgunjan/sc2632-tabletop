# Case D: Secret enumeration and copied credentials

This is the fourth prepared SC2632 case. It has a [human RBAC review proposal](review/PR.md) and an executed, disposable [CNI/RBAC/credential lab](../../submission/2026-10-13/live-rehearsal/case-d/README.md). It does not add a generator scenario `d` or claim that admission controls observe GET/LIST.

Before the reveal, ask teams to identify which part of their plan stops a credential used outside the quarantined Pod. Ask what exact access must survive, what evidence proves it and which exposed application keys may remain usable after Kubernetes-token revocation.

The verifier uses actual bearer-token requests. It creates a temporary ServiceAccount with a broad Secret-read binding, synthetic Secrets in two fresh target namespaces, one legitimate named in-namespace Secret and a target ConfigMap. A suspect Pod and an unaffected positive control establish CNI reachability. Tokens stay in memory, proxies and redirects are disabled, and only owned resources are cleaned up.

Run only on the named marked rehearsal lab:

```bash
.venv-session/bin/python lab/verify-case-d.py \
  --kubeconfig .session-build/live-rehearsal/kubeconfig-20261013 \
  --context k3d-sc2632-rehearsal-20261013 \
  --out output/case-d-fresh
```

The measured result is a single lab run. It verifies synthetic read authorization, new connection behavior, stand-in HTTP health and Pod-bound token invalidation. It does not establish real monitoring delivery, server audit evidence, external application-key rotation or complete enterprise qualification.
