# Case D: executed read authorization and credential response

One real run on the marked presenting-Mac k3d lab, October 13, 2026. The fictional monitoring incident is separate from these synthetic fixtures. This is human-reviewed RBAC, not model-generated enforcement or generator scenario `d`.

| State | Actual copied-credential requests | Positive controls |
|---|---|---|
| Broad Secret-read binding | GET and LIST synthetic Secrets in two other namespaces return 200; access review allows cluster-wide LIST | Required named Secret and ConfigMap GET return 200; collector and unaffected control reach API TCP |
| Suspect Pod quarantined | The same out-of-Pod credential still GETs/LISTs those Secrets with 200 | Suspect's new API TCP connection fails; unaffected control still connects; stand-in HTTP health succeeds |
| Binding narrowed | Outside-namespace GET/LIST return 403; cluster-wide and in-namespace LIST are denied | Same credential retains GET of exactly the required named Secret and ConfigMap; stand-in remains available |
| Clean replacement and old bound Pod deleted | Old credential fails authentication with 401, observed 41.2 seconds after deletion | New credential has required GET access, denied outside reads, restored API connectivity and stand-in health |

[result.json](result.json) contains 58 passing observations, including repeated health samples while revocation propagates. There are 45 distinct check descriptions; this is not 58 independent incident scenarios. The full [status-only transcript](run.txt) and exact [before](before-rbac.json)/[after](after-rbac.json) RBAC manifests are retained. [cleanup-verified.json](cleanup-verified.json) confirms all five created namespace/cluster-RBAC resources were absent after cleanup.

The current verifier source hash matches the result. Tokens stay in process memory and never enter files, logs or command arguments. The actual transport disables proxies and redirects and validates the loopback API server's TLS CA. Synthetic Secret values are explicitly non-credentials. Requests never target real Secret objects in the lab's existing namespaces.

The old token still had more than three minutes of natural lifetime before bound-Pod deletion. Its 401 therefore measures observed invalidation of this Pod-bound Kubernetes credential, not ordinary expiry. Kubernetes [verifies the bound object's identity and deletion state](https://kubernetes.io/docs/reference/access-authn-authz/service-accounts-admin/#bound-service-account-tokens); this one observed delay is not a worst-case guarantee.

These checks prove synthetic authorization, new TCP connection behavior, a stand-in HTTP endpoint and Kubernetes bound-token invalidation. They do not prove production metrics delivery, complete audit evidence, compromise eradication or rotation of application keys already read from Secrets. RBAC controls add across bindings; the production identity needs a full effective-permission review.

Use the [reference human PR](../../../../scenarios/d-secret-enumeration/review/PR.md) during preparation. Before the reveal, teams predict which layer stops the copied credential and which exact dependency must remain. Afterward, require an exit test for any exposed application credential and name its owner. The lab result cannot substitute for that remaining incident work.
