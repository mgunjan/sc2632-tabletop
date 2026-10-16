# Lab

```bash
./lab/setup.sh && ./scripts/lab-e2e.sh            # laptop: k3d (Docker Desktop)
RUNTIME=k3s ./lab/setup.sh && ./scripts/lab-e2e.sh  # Linux host / NUC with k3s installed
```

`setup.sh` builds the stand-in images and loads them into the cluster. It then installs Kyverno, the
targets, the baseline NetworkPolicies and the scenario's policies. `lab-e2e.sh` resets to Q0 and
walks the whole ladder and confirms that three documented gaps still exist.

`setup.sh` ends by marking the cluster as a disposable lab: ConfigMap `kube-public/trustfall-lab`.
The tabletop consequence scripts (`tabletop/consequences/*.sh`, via `lab/lib-guard.sh`) refuse to
run, exit 3, against any cluster without that marker, because they scale the policy engine to zero
and delete Pods. For a lab you built by hand:
`kubectl -n kube-public create configmap trustfall-lab --from-literal=created-by=manual`
(or `TRUSTFALL_LAB_OK=1` for one run).

## macOS (the presenter's laptop)

The lab and the tabletop scripts are written for stock macOS: bash 3.2, BSD userland, no GNU
`timeout`, `sha256sum` or GNU `sed`. You need Docker Desktop (or another Docker engine) and:

```bash
brew install k3d helm kubectl
# kyverno CLI pinned to 1.19.1: brew only if `brew info kyverno` shows 1.19.1; otherwise the
# release binary for darwin (arm64 or x86_64) from https://github.com/kyverno/kyverno/releases/tag/v1.19.1
brew install --cask font-ibm-plex-sans font-ibm-plex-mono    # deck and packet fonts
python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt   # jsonschema, pyyaml
```

- `setup.sh` pins the node image (`K3S_IMAGE`, default `rancher/k3s:v1.33.4-k3s1`, the version the
  Linux results were recorded on), switches kubectl to `k3d-trustfall`, and stops if
  `k3d cluster create` fails.
- `setup.sh` pins `KYVERNO_CHART=3.9.1` and checks that its app version is 1.19.1 before installation.
- **One-time Mac run, then commit the result** (this is what removes "k3d on macOS" from the
  not-yet-run list below):

  ```bash
  ./lab/setup.sh && ./scripts/lab-e2e.sh 2>&1 | tee lab/RESULTS-live-$(date +%F)-mac-k3d.txt
  git add lab/RESULTS-live-*-mac-k3d.txt && git commit -m "lab: first live run on macOS k3d"
  ```

  The script now uses bash-3.2-compatible reads and a `shasum` fallback. Activate the Python
  environment first: a missing PyYAML dependency refuses before live writes.
- **On the day:** `caffeinate -d &` for the whole session (a sleeping Mac pauses Docker and the
  cluster), `./tabletop/consequences/stage.sh`, then `STAGED=1 ./tabletop/consequences/preflight.sh`
  before you go on stage. Resolve failed enforcement checks; a model SKIP means use the declared
  reference/replay path. `play.sh` re-runs the preflight quietly before each
  live consequence and replays, with the reason on screen, if anything fails.

## Status: it has run

**Presenting Mac, October 13:** the isolated three-node k3d/K3s rehearsal passed 61 live checks
with the same three explicit gaps. Native image archives and every fixture tag were verified on
all nodes. Actual exception deletion and renewed admission denial passed after repairing the
cleanup controller's missing namespace-scoped deletion permission. Deletion was observed 196.9
seconds after expiry on the unchanged five-minute schedule. See the [separate local evidence](../submission/2026-10-13/live-rehearsal/README.md).
These are local lab results; venue display and human rehearsal remain separate requirements.

The suite first passed on a live cluster on 2026-09-24 (`lab/RESULTS-live-2026-09-24.txt`). The latest run,
on 2026-09-25, after closing the Service-endpoint gap and adding the identity check to the IC override:
49 checks passed, `LAB E2E: ALL PASSED (2 documented gaps confirmed)` (`lab/RESULTS-live-2026-09-25.txt`; re-run 2026-09-26 with standards-tagged headings and the Trustfall Financial names, same result: `lab/RESULTS-live-2026-09-26.txt`). Latest, 2026-09-28, with the Q1 agent freeze as a native ValidatingAdmissionPolicy (enforced by the API server, not asked of the agent, and still in force with Kyverno scaled to zero): 52 checks, same two gaps (`lab/RESULTS-live-2026-09-28.txt`). The run now stops at a preflight if Kyverno's admission controller isn't Ready, instead of reporting a dozen misleading FAILs.

**Earlier Linux run, 2026-10-10:** 61 checks, 3 documented gaps (`lab/RESULTS-live-2026-10-10.txt`). New since the Sep 28 review: positive network controls (an unrestricted Pod reaches every target, so each "cannot reach" is the policy); init containers and native sidecars refused at Q2; privileged debug containers refused; the suspect's containment labels protected by a native policy (only an incident commander can loosen them); exceptions honoured only from `payments`; refusals checked for the control that refused them; the commit recorded in the run header. The third gap, asserted so it stays true: Kyverno never sees `kube-system`, so Scenario C's rule cannot stop the agent changing it; RBAC is the control there.

- **Cluster:** k3s v1.33.4 on one node, running natively in a Linux VM.
- **Kyverno:** v1.19.1, built from source at the release tag.
- **Network:** the built-in NetworkPolicy controller.

That VM can reach no container registry, so the Kyverno build needed two workarounds. Both are recorded here so nobody has to trust the result blind:

- `buf.build/gen/go/bufbuild/protovalidate/...` is served only by buf.build. It was regenerated
  with `protoc-gen-go` v1.36.11 from `bufbuild/protovalidate` at its last commit before the
  pinned module date, and wired in with a `replace` directive.
- `gitlab.com/gitlab-org/api/client-go` was replaced by a compile-only stub. Kyverno reaches it
  only through cosign's "store keys in GitLab CI variables" helper, which admission never calls.

On your laptop, `setup.sh` pulls the official images and none of this applies.

**Not yet run live:**

- Scenario B on a cluster (`SCENARIO=b`; its admission behaviour is covered offline).
- Falco and a strict request-time expiry cutoff. Scheduled exception deletion is now tested separately.
- A memory checkpoint (see below).

## What the e2e found that offline tests could not

See `quarantine/quarantine-mode.md`, "Found on a live cluster". In short:

- Q3's deny-all left the suspect a DNS channel.
- DNS-only suspects still received gateway traffic.
- Evidence capture recorded no process list.
- Evidence capture sealed error messages as evidence.
- The old e2e test skipped its own NetworkPolicy check.

Also found on the first live install, and now handled in `setup.sh`:

- **PolicyExceptions are OFF by default** in both the Helm chart and the release manifest
  (`--enablePolicyException=false`). The flag gates the CEL `policies.kyverno.io` exceptions too.
  Without `features.policyExceptions.enabled=true` and `namespace=*`, every exception in this repo
  is silently ignored.
- **`kubectl get policyexception` returns the wrong resource.** With Kyverno's legacy CRD also
  installed, it looks in the deprecated `kyverno.io/v2` group. Use
  `policyexceptions.policies.kyverno.io` in runbooks.

## The gaps (asserted to still exist, on purpose)

1. **No memory checkpoint.** On k3s v1.33 / containerd 2.0 the kubelet Checkpoint API is on by
   default. It fails only because CRIU is not on the node:
   `CRIU binary not found or too old`. CRIU also needs a kernel built with `CHECKPOINT_RESTORE`.
2. **Nothing stops an identity with the common "scale any Deployment" right from scaling Kyverno to
   zero,** unless `guard/protect-the-guardrail.yaml` is applied. The e2e removes the guard, shows the
   agent doing it (Kyverno deletes its own webhooks, 7 → 2, and a docker.io Pod is admitted), then
   re-applies the guard and asserts the same move is refused. Kyverno's admission rules stop applying;
   NetworkPolicies keep holding.

Closed since the first run:

- **A DNS-only suspect was still a Service endpoint.** `Service/payments-api` now selects
  `trustfall.example/in-rotation=true`, and `capture-evidence.sh` sets it to `false` in the same single label
  write that marks the suspect. The Pod leaves the endpoints, stays owned by its ReplicaSet (no
  replacement), and keeps running as evidence. Asserted live.
- **The IC override was only an annotation.** Anyone who could create Pods in payments could set it.
  Q1 and Q3 now also require the requester to be in `trustfall:incident-commanders`
  (`lab/rbac-humans.yaml`; the lab impersonates both groups). Asserted live and offline.
The third gap found live, `kubectl debug` getting past the admission policies, is now closed by
`quarantine/q2/ephemeral-containers.yaml`. The e2e asserts both that it is refused and that the
approved debug image still works.

## Why k3d / k3s and not kind

k3s ships a NetworkPolicy controller. **kind's default CNI (kindnet) does not enforce
NetworkPolicy**: policies apply cleanly and block nothing. If you must use kind, install
Calico or Cilium first.

## No network at the venue

Conference wifi is not a dependency you want on stage. While you still have network:

```bash
./lab/offline-bundle.sh      # Kyverno manifest + images, busybox, the pinned k3s image and k3d's
                             # helper images (k3d-proxy, k3d-tools) into Docker's local cache
```

On the day:

```bash
KYVERNO_MANIFEST=lab/.bundle/kyverno-install.yaml ./lab/setup.sh
```

The stand-in workload images are always built locally (`lab/images/`), so nothing is pulled at
run time.

## Linux host notes (NUC, or any small VM)

- If the disk is small relative to the filesystem size, kubelet's default
  `nodefs.available<10%` eviction threshold taints the node `disk-pressure` permanently. Image
  garbage collection then deletes your locally loaded images. Set
  `kubelet-arg: ["eviction-hard=nodefs.available<1Gi,imagefs.available<1Gi"]` in
  `/etc/rancher/k3s/config.yaml`.
- If the host has an HTTP proxy in its environment, give k3s a `NO_PROXY` that covers the node
  IP and the Pod/Service CIDRs. Otherwise the API server sends kubelet calls (logs, exec, checkpoint) through the proxy and they
  fail with `EOF`.

## Offline

You don't need a cluster for the admission results. `kyverno test` runs the same policies
against the same fixtures with the CLI alone (`./scripts/test-all.sh`).

## Falco

Falco needs a Linux kernel with BTF for the modern eBPF probe. On macOS Docker Desktop it
is unreliable; run the Falco part on a Linux host (the NUC). For the syscall rules (scenarios A, B), fill in the CIDR lists at the top with
your cluster's Service and Pod ranges first:

```bash
helm repo add falcosecurity https://falcosecurity.github.io/charts
helm install falco falcosecurity/falco -n falco --create-namespace \
  --set driver.kind=modern_ebpf \
  --set-file 'customRules.trustfall\.yaml=runtime/falco-rules-syscall.yaml'
kubectl -n falco logs -l app.kubernetes.io/name=falco -f | grep TRIGGER
```

The k8s_audit rules (scenario C) need the API server's audit webhook pointed at Falco's k8saudit
plugin. **Not run in the lab yet.** CI runs `falco --validate` on the rules.

The separate synthetic webhook check now runs the real audit plugin in a capability-free
container, sends 15 authored events and verifies detection, negative controls and explicit
visibility warnings. Use `scripts/verify-falco-audit.py --plugins /path/to/plugins --out output/falco-audit-new`.
See `submission/2026-10-16/README.md` for baseline failures, repairs and the exact scope.
This does not establish API-server delivery or syscall capture from this cluster.

## Local model

```bash
ollama pull qwen3-coder:30b
python3 generator/generate.py --scenario b
```

Temperature 0 and a fixed seed by default. Provenance lands in `output/<run>/provenance.json`.
