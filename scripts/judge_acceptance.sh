#!/bin/sh
# Run on the authorized rendering host, from an exported standalone checkout.
set -eu
cd "$(dirname "$0")/.."
[ "$#" -eq 1 ] || { echo 'Usage: judge_acceptance.sh NEW_OUTPUT_DIRECTORY' >&2; exit 2; }
mkdir "$1"
out=$(CDPATH= cd -- "$1" && pwd)
image=$(podman image inspect "${SIGNALDESK_JUDGE_IMAGE:-localhost/signaldesk-judge:wave11}" --format '{{.Id}}')
exec nice -n 10 podman run --rm --pull=never --network=none --read-only --userns=keep-id \
  --cap-drop=all --cap-add=SYS_CHROOT --security-opt=no-new-privileges \
  --pids-limit=256 --memory=2g --cpus=2 --env PYTHONDONTWRITEBYTECODE=1 \
  --mount "type=bind,src=$(pwd),dst=/app,ro,relabel=private" \
  --mount "type=bind,src=$out,dst=/out,relabel=private" --workdir /app "$image" \
  sh -ec 'python -m unittest discover -s tests -v; python tests/replay_browser.py --output /out/browser; python tests/judge_browser.py --output /out/a11y; python scripts/capture_draft.py --output /out/video'
