#!/usr/bin/env bash
# Build the stand-in image under every image name the fixtures use, then load it into the
# lab cluster (k3d on a laptop, or a native k3s). No registry involved at any point, which
# also makes the lab work on conference wifi.
#   ./lab/images/build.sh                 # k3d cluster "trustfall" (default)
#   RUNTIME=k3s ./lab/images/build.sh     # native k3s on this host
set -euo pipefail
cd "$(dirname "$0")/../.."
BASE="${BASE:-busybox:1.36}"
RUNTIME="${RUNTIME:-k3d}"
CLUSTER="${CLUSTER:-trustfall}"
case "$RUNTIME" in k3d|k3s) ;; *) echo "RUNTIME must be k3d or k3s" >&2; exit 2 ;; esac
source lab/lib-guard.sh
lab_guard
if [ "$RUNTIME" = k3d ]; then
  [ "$(kubectl config current-context)" = "k3d-$CLUSTER" ] \
    || { echo "REFUSED: current context does not match the target k3d lab" >&2; exit 3; }
  # Select names/roles only; cluster inventories can contain join credentials.
  nodes=$(docker ps -a --filter "label=k3d.cluster=$CLUSTER" --format '{{.Names}} {{.Label "k3d.role"}} {{.State}}' \
    | awk '$2 == "server" || $2 == "agent" {if ($3 != "running") exit 2; print $1}')
  [ -n "$nodes" ] || { echo "No running k3d server/agent nodes found" >&2; exit 3; }
fi
platform="${IMAGE_PLATFORM:-$(docker version --format '{{.Server.Os}}/{{.Server.Arch}}')}"
case "$platform" in linux/amd64|linux/arm64) ;; *) echo "Unsupported IMAGE_PLATFORM: $platform" >&2; exit 2 ;; esac
# Older fixture tagging could replace busybox:1.36 with the stand-in itself.
# Restore the real native base, then keep it out of the stand-in tag loop.
base_info=$(docker image inspect --format '{{.Os}}/{{.Architecture}} {{json .Config.Entrypoint}}' "$BASE" 2>/dev/null || true)
if [[ "$base_info" != "$platform "* ]] || [[ "$base_info" == *'"/entrypoint.sh"'* ]]; then
  docker pull --platform "$platform" "$BASE" >/dev/null
fi
TAGS=$(grep -h 'image:' scenarios/*/fixtures/*.yaml | awk '{print $NF}' | sort -u \
  | awk -v base="$BASE" '$0 != base && $0 != "busybox:1.36" && $0 != "docker.io/library/busybox:1.36" && $0 != "index.docker.io/library/busybox:1.36"')
TAGS="$TAGS registry.trustfall.internal/platform/lab-target:1"
# Approved debug image for evidence capture once Q2 closes the kubectl-debug path.
docker tag "$BASE" registry.trustfall.internal/platform/debug:1
DEBUG_TAG=registry.trustfall.internal/platform/debug:1
docker build -q --platform "$platform" --build-arg BASE="$BASE" -t trustfall/lab-standin:1 lab/images >/dev/null
for t in $TAGS; do docker tag trustfall/lab-standin:1 "$t"; done
# busybox:1.36 itself is used by capture-evidence.sh's debug container and the lab probes.
[ "$BASE" = busybox:1.36 ] || docker tag "$BASE" busybox:1.36
archive=$(mktemp "${TMPDIR:-/tmp}/sc2632-images.XXXXXX")
trap 'rm -f "$archive"' EXIT
save_platform=()
if docker image save --help | grep -q -- --platform; then save_platform=(--platform "$platform"); fi
# Explicit native export avoids missing foreign-platform blobs in Docker's OCI image store.
# shellcheck disable=SC2086
docker image save "${save_platform[@]}" --output "$archive" $TAGS busybox:1.36 "$DEBUG_TAG"
case "$RUNTIME" in
  k3d)
    k3d image import --cluster "$CLUSTER" --mode direct "$archive"
    for node in $nodes; do
      ready=$(docker exec "$node" ctr --address /run/k3s/containerd/containerd.sock --namespace k8s.io images check --quiet)
      for tag in $TAGS busybox:1.36 "$DEBUG_TAG"; do
        ref="$tag"
        first="${tag%%/*}"
        case "$tag" in
          */*) case "$first" in *.*|*:*|localhost) ;; *) ref="docker.io/$tag" ;; esac ;;
          *) ref="docker.io/library/$tag" ;;
        esac
        printf '%s\n' "$ready" | grep -Fxq "$ref" \
          || { echo "IMPORT FAILED: $ref is not fully downloaded and unpacked on $node" >&2; exit 4; }
      done
      echo "verified native image content on $node"
    done
    ;;
  k3s)
    k3s ctr -n k8s.io images import "$archive" >/dev/null
    ready=$(k3s ctr -n k8s.io images check --quiet)
    for tag in $TAGS busybox:1.36 "$DEBUG_TAG"; do
      first="${tag%%/*}"; ref="$tag"
      case "$tag" in */*) case "$first" in *.*|*:*|localhost) ;; *) ref="docker.io/$tag" ;; esac ;; *) ref="docker.io/library/$tag" ;; esac
      printf '%s\n' "$ready" | grep -Fxq "$ref" \
        || { echo "IMPORT FAILED: $ref is not fully downloaded and unpacked" >&2; exit 4; }
    done
    ;;
esac
echo "loaded and verified: $(echo $TAGS | wc -w) stand-in tags + BusyBox and approved debug image ($platform)"
