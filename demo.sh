#!/bin/sh
# Fresh standalone checkout: one command; default is recorded, no credentials.
set -eu
cd "$(dirname "$0")"
case "${1:-}" in
  --help|-h) printf 'Usage: sh demo.sh [--json]\nPinned rootless Podman; recorded synthetic responses; no API calls.\n'; exit 0 ;;
  ''|--json) ;;
  *) printf 'Usage: sh demo.sh [--json]\n' >&2; exit 2 ;;
esac
[ "$#" -le 1 ] || { printf 'Too many arguments\n' >&2; exit 2; }
image=$(cat runtime-image.txt)
[ "$(podman info --format '{{.Host.Security.Rootless}}')" = true ]
if ! podman image exists "$image"; then
  # Package/image pull only. No model call or third-party application request.
  podman pull "$image"
fi
exec podman run --rm --pull=never --network=none --read-only \
  --user 65534:65534 --cap-drop=all --security-opt=no-new-privileges \
  --pids-limit=64 --memory=256m --cpus=1 \
  --env PYTHONDONTWRITEBYTECODE=1 --env PYTHONUNBUFFERED=1 \
  --mount "type=bind,src=$(pwd),dst=/app,ro,relabel=private" --workdir /app \
  "$image" python -m signaldesk.demo "$@"
