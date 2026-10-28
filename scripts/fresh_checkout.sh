#!/bin/sh
# Test the public package from a NEW directory, with no parent repo or git metadata.
set -eu
cd "$(dirname "$0")/.."
umask 022
entry=$(pwd)
out=${1:?Usage: sh scripts/fresh_checkout.sh NEW_OUTPUT_DIRECTORY}
mkdir "$out"
out=$(CDPATH= cd -- "$out" && pwd)
image=$(cat runtime-image.txt)
[ "$(podman info --format '{{.Host.Security.Rootless}}')" = true ]
podman image exists "$image" || podman pull "$image"
podman run --rm --pull=never --network=none --read-only --userns=keep-id \
  --cap-drop=all --security-opt=no-new-privileges --pids-limit=128 --memory=256m --cpus=1 \
  --env PYTHONDONTWRITEBYTECODE=1 \
  --mount "type=bind,src=$entry,dst=/app,ro,relabel=private" \
  --mount "type=bind,src=$out,dst=/out,relabel=private" --workdir /app "$image" \
  python scripts/package_public.py --output /out/export > "$out/package.txt"
podman run --rm --pull=never --network=none --read-only --userns=keep-id \
  --cap-drop=all --security-opt=no-new-privileges --pids-limit=64 --memory=256m --cpus=1 \
  --mount "type=bind,src=$out,dst=/out,relabel=private" "$image" \
  python -c 'import tarfile; tarfile.open("/out/export/signaldesk.tar.gz").extractall("/out/source", filter="data")'
cd "$out/source/signaldesk"
# This launcher is the single command documented for a fresh standalone checkout.
sh demo.sh --json > "$out/demo.json"
sh run.sh test > "$out/tests.txt" 2>&1
sh run.sh evaluate > "$out/evaluation.json"
sh run.sh evaluate --split challenge > "$out/challenge-evaluation.json"
podman run --rm --pull=never --network=none --read-only --user 65534:65534 \
  --cap-drop=all --security-opt=no-new-privileges --pids-limit=64 --memory=256m --cpus=1 \
  --env PYTHONDONTWRITEBYTECODE=1 \
  --mount "type=bind,src=$(pwd),dst=/app,ro,relabel=private" --workdir /app "$image" \
  python -m signaldesk.finish_eval > "$out/finish-evaluation.json"
printf 'PASS: fresh public-archive extraction; one-command recorded demo; tests; heldout/challenge/finish evals; no parent repo; application network=none\n' > "$out/result.txt"
cat "$out/result.txt"
