#!/bin/sh
# Runs only inside the pinned read-only scanner container.
set -eu
if [ ! -r /src ] || [ ! -x /src ]; then
  printf 'Scan refused: source directory is unreadable\n' >&2
  exit 2
fi
# Gitleaks may return zero when an unreadable path contains no scanned files.
# Require traversal/read access first; never count skipped content as clean.
find /src -type d -exec /bin/sh -c '
  for path in "$@"; do
    if [ ! -r "$path" ] || [ ! -x "$path" ]; then
      printf "Scan refused: source directory is unreadable\n" >&2
      exit 2
    fi
  done
' sh {} +
if find /src -type l -print | grep -q .; then
  printf 'Scan refused: source contains a symlink\n' >&2
  exit 2
fi
find /src -type f -exec /bin/sh -c '
  for path in "$@"; do
    if [ ! -r "$path" ]; then
      printf "Scan refused: source file is unreadable\n" >&2
      exit 2
    fi
  done
' sh {} +
exec gitleaks dir /src --redact=100 --no-banner --log-level=error
