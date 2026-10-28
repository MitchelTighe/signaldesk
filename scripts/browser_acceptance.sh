#!/bin/sh
# Run only after building Containerfile.browser on an authorized rootless host.
set -eu
cd "$(dirname "$0")/.."
out=${1:-browser-output}
if [ "$#" -gt 0 ]; then shift; fi
mkdir "$out"
out=$(CDPATH= cd -- "$out" && pwd)
entry=$(pwd)
image=${SIGNALDESK_BROWSER_IMAGE:-}
if [ -z "$image" ]; then
  image=$(podman image inspect localhost/signaldesk-browser:1.55.0-p4 --format '{{.Id}}')
fi
# SYS_CHROOT is needed by Chromium's enabled sandbox inside this rootless namespace.
# No host IPC, SYS_ADMIN, unconfined seccomp or --no-sandbox flags.
exec podman run --rm --pull=never --network=none --read-only --userns=keep-id \
  --cap-drop=all --cap-add=SYS_CHROOT --security-opt=no-new-privileges \
  --pids-limit=256 --memory=1g --cpus=1 --env PYTHONDONTWRITEBYTECODE=1 \
  --mount "type=bind,src=$entry,dst=/app,ro,relabel=private" \
  --mount "type=bind,src=$out,dst=/out,relabel=private" --workdir /app \
  "$image" python tests/replay_browser.py --output /out "$@"
