#!/bin/sh
# Lead invokes through her credential broker; this wrapper never reads/prints the key.
set -eu
cd "$(dirname "$0")/.."
export PYTHONDONTWRITEBYTECODE=1
exec python3 -m signaldesk.live_eval "$@"
