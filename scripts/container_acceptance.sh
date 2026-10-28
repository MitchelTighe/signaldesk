#!/bin/sh
# Sequential, rootless, offline acceptance. Only the explicit pinned-image pull uses network.
set -eu
cd "$(dirname "$0")/.."
umask 022
out=${1:-acceptance-output}
mkdir "$out"
out=$(CDPATH= cd -- "$out" && pwd)
entry=$(pwd)
image=$(cat runtime-image.txt)
[ "$(podman info --format '{{.Host.Security.Rootless}}')" = true ]
podman --version > "$out/runtime.txt"
printf 'rootless=true\n' >> "$out/runtime.txt"
date -u '+observed_at=%Y-%m-%dT%H:%M:%SZ' >> "$out/runtime.txt"
podman pull "$image" > "$out/pull.txt" 2>&1
printf '%s\n' "$image" > "$out/pinned-image.txt"
podman image inspect "$image" --format 'ID={{.Id}} OS={{.Os}} Architecture={{.Architecture}} RepoDigests={{json .RepoDigests}}' > "$out/image-metadata.txt"
export SIGNALDESK_IMAGE="$image"
# Never run these mounts concurrently: private SELinux relabels are exclusive.
sh run.sh test > "$out/tests.txt" 2>&1
sh run.sh demo > "$out/demo.txt" 2>&1
sh run.sh evaluate > "$out/evaluation.json"
sh run.sh evaluate --split smoke > "$out/smoke-evaluation.json"
sh run.sh evaluate --split challenge > "$out/challenge-evaluation.json"
sh demo.sh --json > "$out/recorded-demo.json"
sh run.sh export-web > "$out/index.html"
cmp web/index.html "$out/index.html"
with_output() {
  podman run --rm --pull=never --network=none --read-only \
    --userns=keep-id --user "$(id -u):$(id -g)" --cap-drop=all --security-opt=no-new-privileges \
    --pids-limit=128 --memory=256m --cpus=1 --env PYTHONDONTWRITEBYTECODE=1 \
    --mount "type=bind,src=$entry,dst=/app,ro,relabel=private" \
    --mount "type=bind,src=$out,dst=/out,relabel=private" --workdir /app "$image" "$@"
}
with_output sh scripts/signaldesk_live_eval.sh --dry-run --cache /out/cache --output /out/dry-run.json > "$out/dry-run.txt"
with_output sh scripts/signaldesk_live_eval.sh --dry-run --replay --cache /out/cache --output /out/mock-replay.json > "$out/mock-replay.txt"
with_output python -m signaldesk.replay --report /out/dry-run.json --output /out/site > "$out/replay-build.txt"
# Explicit negative check: a mock must never pass the real-run gate.
if with_output python -m signaldesk.replay --report /out/dry-run.json --output /out/refused-site --require-live > "$out/mock-refused.txt" 2>&1; then
  printf 'FAIL: mock origin was accepted as live\n' >&2
  exit 1
fi
with_output python -m signaldesk.vision --dry-run --cache /out/vision-cache --output /out/vision.json > "$out/vision.txt"
with_output python -m signaldesk.finish_eval > "$out/finish-evaluation.json"
with_output python -m signaldesk.demo --live --json > "$out/missing-key-demo.json"
with_output python scripts/artifact_check.py > "$out/artifact-checks.json"
with_output python scripts/package_public.py --output /out/public-export > "$out/package.txt"
sha256sum signaldesk/core.py signaldesk/training.json signaldesk/heldout.json signaldesk/data.json signaldesk/challenge.json signaldesk/vision.py web/index.html site/index.html run.sh > "$out/source-sha256.txt"
podman run --rm --pull=never --network=none --read-only --user 65534:65534 --cap-drop=all --security-opt=no-new-privileges --pids-limit=64 --memory=256m --cpus=1 "$image" python --version >> "$out/runtime.txt"
printf 'PASS: tests/demo/recorded-demo/heldout/smoke/challenge/finish-eval/export/mock-HTTP/cache-replay/static-build/mock-refusal/vision-mock/public-export; execution network=none\n' > "$out/result.txt"
cat "$out/result.txt"
