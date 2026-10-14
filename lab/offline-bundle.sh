#!/usr/bin/env bash
# Run ONCE while you have network (hotel, home). Saves everything the lab needs so that on the
# day, `KYVERNO_MANIFEST=lab/.bundle/kyverno-install.yaml ./lab/setup.sh` needs no network at all.
#   - Kyverno's release manifest and its five images
#   - busybox (base for the stand-in images and the evidence debug container)
#   - the k3s node image setup.sh pins (it stays in Docker's local cache; this just makes sure)
#   - k3d's helper images: k3d-proxy (the cluster's load balancer, needed by `k3d cluster create`)
#     and k3d-tools (needed by `k3d image import`). Without them a k3d cluster cannot be created
#     or loaded offline.
# Bash 3.2 / BSD userland safe (stock macOS).
set -euo pipefail
cd "$(dirname "$0")"
V="${KYVERNO_VERSION:-v1.19.1}"
# Same default as lab/setup.sh; keep the two in step.
K3S_IMAGE="${K3S_IMAGE:-rancher/k3s:v1.33.4-k3s1}"
# k3d tags its helper images with its own version, without the leading "v" (k3d vX.Y.Z uses
# ghcr.io/k3d-io/k3d-proxy:X.Y.Z). Detected from the installed k3d; set K3D_HELPER_TAG to override
# (k3d itself honours K3D_HELPER_IMAGE_TAG, so match that if you set it).
K3D_HELPER_TAG="${K3D_HELPER_TAG:-${K3D_HELPER_IMAGE_TAG:-}}"
if [ -z "$K3D_HELPER_TAG" ] && command -v k3d >/dev/null 2>&1; then
  K3D_HELPER_TAG=$(k3d version 2>/dev/null | awk '/^k3d version/{print $3; exit}' | sed 's/^v//')
fi
mkdir -p .bundle
curl -fsSL -o .bundle/kyverno-install.yaml "https://github.com/kyverno/kyverno/releases/download/${V}/install.yaml"
IMAGES=$(grep -o 'image: "[^"]*"' .bundle/kyverno-install.yaml | cut -d'"' -f2 | sort -u)
for i in $IMAGES busybox:1.36; do docker pull -q "$i"; done
docker pull -q "$K3S_IMAGE"
if [ -n "$K3D_HELPER_TAG" ]; then
  for i in "ghcr.io/k3d-io/k3d-proxy:$K3D_HELPER_TAG" "ghcr.io/k3d-io/k3d-tools:$K3D_HELPER_TAG"; do docker pull -q "$i"; done
else
  echo "WARNING: could not detect the k3d version: k3d-proxy and k3d-tools NOT cached." >&2
  echo "         Install k3d, or set K3D_HELPER_TAG=<k3d version without the v>, and re-run." >&2
fi
printf '%s\n' $IMAGES > .bundle/kyverno-images.txt
echo "bundle ready: lab/.bundle/ (manifest + $(wc -l < .bundle/kyverno-images.txt | tr -d ' ') Kyverno images, $K3S_IMAGE, k3d helpers ${K3D_HELPER_TAG:-MISSING} in Docker's cache)"
echo "on the day: KYVERNO_MANIFEST=lab/.bundle/kyverno-install.yaml ./lab/setup.sh"
