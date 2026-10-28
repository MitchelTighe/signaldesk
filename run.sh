#!/bin/sh
set -eu
entry_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
image=${SIGNALDESK_IMAGE:-docker.io/library/python@sha256:2986c55feb36e6cae00fa1fefb454283e4b33f35e75ff8bdd123b134130be301}
mode=${1:-demo}
if [ "$#" -gt 0 ]; then shift; fi
case "$mode" in
  demo|list|case|evaluate|export-web) set -- python -m signaldesk "$mode" "$@" ;;
  test) set -- python -m unittest discover -s tests -v "$@" ;;
  *) echo 'Usage: sh run.sh [demo|list|case ID|evaluate|test|export-web]' >&2; exit 2 ;;
esac
# Pull separately: repeatable offline execution must never auto-download anything.
exec podman run --rm --pull=never --network=none --read-only \
  --user 65534:65534 --cap-drop=all --security-opt=no-new-privileges \
  --pids-limit=64 --memory=256m --cpus=1 \
  --env PYTHONDONTWRITEBYTECODE=1 --env PYTHONUNBUFFERED=1 \
  --mount "type=bind,src=$entry_dir,dst=/app,ro,relabel=private" --workdir /app \
  "$image" "$@"
