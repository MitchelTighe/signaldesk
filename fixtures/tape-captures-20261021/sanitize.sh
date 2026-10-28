#!/bin/bash
# sanitize.sh DIR - rewrite host names and device serials in captured output to generic values (in place).
# Mapping: tape host -> tapehost01; library serial -> LIBSN0001; drive serials -> DRVSN0001..4.
set -eu
DIR=${1:?usage: sanitize.sh DIR}
HOST=${TAPE_HOST:-tapehost01}
find "$DIR" -type f -name '*.txt' -print0 | xargs -0 sed -i -E \
  -e "s/\b${HOST}\b/tapehost01/g" \
  -e 's/SITEB_LIB0/LIBSN0001/g' \
  -e 's/SITEB_DRV([1-4])/DRVSN000\1/g' \
  -e 's/SITEB_/SITE_/g' \
  -e 's#/[m]nt/ltfs-b#/media/ltfs-b#g'
