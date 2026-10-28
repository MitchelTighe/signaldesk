#!/bin/sh
# Pinned Gitleaks 8.30.1. Filesystem scan only, no git history or external verification.
set -eu
cd "$(dirname "$0")/.."
image=docker.io/zricethezav/gitleaks@sha256:b109bc5f8f76a38196a3e413704fc5b9e3c32360bce4e4b603bd6f45b3721dbb
[ "$(podman info --format '{{.Host.Security.Rootless}}')" = true ]
podman image exists "$image" || podman pull "$image"
# Findings are fully redacted. No raw secret or finding report is written.
podman run --rm --pull=never --network=none --read-only --userns=keep-id --user "$(id -u):$(id -g)" \
  --cap-drop=all --security-opt=no-new-privileges --pids-limit=64 --memory=256m --cpus=1 \
  --mount "type=bind,src=$(pwd),dst=/src,ro,relabel=private" \
  --entrypoint=/bin/sh "$image" /src/scripts/scan_inside.sh
printf 'PASS: pinned Gitleaks 8.30.1 filesystem scan; application network=none; fully redacted findings\n'
