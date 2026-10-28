#!/bin/bash
# capture.sh - reproduce the SignalDesk tape-incident captures on an mhVTL host.
#
# Needs: mhVTL 1.8 (vtllibrary 10 + vtltape 11-14, STK L700 + 4x IBM ULT3580-TD8),
# sg3_utils, mt-st, mtx, LTFS (/usr/local/bin/ltfs, ltfsck). Run as root on the tape host:
#   sudo bash capture.sh [OUTDIR]
# Every command's stdout+stderr+exit code is kept verbatim in OUTDIR/<scenario>/NN-name.txt.
# The script restores state at the end (TapeAlert 0, delays 0, drives unloaded).
# Raw output contains the host name and device serials; run sanitize.sh before sharing.
# Then: TAPE_HOST=$(hostname -s) bash sanitize.sh OUTDIR
set -u
OUT=${1:-/tmp/tape-captures}
mkdir -p "$OUT"
LTFS=/usr/local/bin/ltfs
LTFSCK=/usr/local/bin/ltfsck

# Resolve nodes by serial, never by /dev order (st/sg numbering is not stable).
sg_of() { for s in /dev/sg*; do sg_inq -p 0x80 "$s" 2>/dev/null | grep -q "serial number: $1" && { echo "$s"; return; }; done; }
st_of() { lsscsi -g | awk -v sg="$1" '$NF==sg{print $(NF-1)}'; }
CH=$(sg_of SITEB_LIB0)
D1=$(sg_of SITEB_DRV1); ST1=$(st_of "$D1")   # DTE 0, vtltape 11
D2=$(sg_of SITEB_DRV2); ST2=$(st_of "$D2")   # DTE 1, vtltape 12
D3=$(sg_of SITEB_DRV3); ST3=$(st_of "$D3")   # DTE 2, vtltape 13

run() {  # run <scenario> <name> <cmd...>
  local dir="$OUT/$1" name=$2; shift 2; mkdir -p "$dir"
  local n; n=$(printf '%02d' $(( $(ls "$dir" | wc -l) + 1 )))
  { echo "# ts: $(date -Is)"; echo "# cmd: $*"; echo "# ---"
    timeout "${TMO:-120}" "$@" 2>&1; echo "# --- exit: $?"; } > "$dir/$n-$name.txt"
}
# mhVTL logs under the identifier of its full binary path; kernel st/sg lines come from -k.
jlog() { run "$1" "journal-$2" journalctl -t /usr/bin/vtltape -t /usr/bin/vtllibrary --since "$3" --no-pager -o short-iso
         run "$1" "kernel-$2" journalctl -k --since "$3" --no-pager -o short-iso; }
cart_slot() { mtx -f "$CH" status | awk -v b="$1" -F'[ :=]+' '$0 ~ "VolumeTag="b {for(i=1;i<=NF;i++) if($i=="Element"){print $(i+1); exit}}'; }

echo "map: CH=$CH D1=$D1/$ST1 D2=$D2/$ST2 D3=$D3/$ST3" | tee "$OUT/device-map.txt"
lsscsi -g >> "$OUT/device-map.txt"

########## 0. baseline (healthy) ##########
S=00-baseline; T0=$(date '+%F %T')
run $S lsscsi lsscsi -g
run $S mtx-status mtx -f "$CH" status
for d in "$D1" "$D2" "$D3"; do b=$(basename "$d")
  run $S "sg_turs-$b" sg_turs -v "$d"
  run $S "sg_logs-supported-$b" sg_logs -p 0x00 "$d"
  run $S "sg_logs-tapealert-$b" sg_logs -p 0x2e "$d"
done
run $S sg_logs-supported-changer sg_logs -p 0x00 "$CH"
run $S sg_logs-tapealert-changer sg_logs -p 0x2e "$CH"
run $S mt-status-empty mt -f "$ST1" status
jlog $S baseline "$T0"

########## A. drive needs cleaning (TapeAlert) ##########
S=a-cleaning-tapealert; T0=$(date '+%F %T')
DATA=A00004L8; CLN=CLN001L1
SD=$(cart_slot $DATA); SC=$(cart_slot $CLN)
run $S mtx-load-data mtx -f "$CH" load "$SD" 0
run $S mt-status-loaded mt -f "$ST1" status
run $S sg_logs-tapealert-before sg_logs -p 0x2e "$D1"
# TapeAlert mask bit (n-1) = flag n.  Flag 20 = Clean now, flag 21 = Clean periodic.
run $S vtlcmd-tapealert-clean-now vtlcmd 11 TapeAlert 0000000000180000
run $S sg_logs-tapealert-after sg_logs -p 0x2e "$D1"
run $S sg_logs-write-errors sg_logs -p 0x02 "$D1"
run $S sg_logs-read-errors sg_logs -p 0x03 "$D1"
run $S sg_logs-device-status sg_logs -p 0x11 "$D1"
run $S sg_logs-all sg_logs -a "$D1"
run $S sg_turs-flagged sg_turs -v "$D1"
run $S mt-status-flagged mt -f "$ST1" status
# Operator response: unload data cart, load cleaning cart into the same drive.
run $S mtx-unload-data mtx -f "$CH" unload "$SD" 0
run $S mtx-load-cleaning mtx -f "$CH" load "$SC" 0
run $S mt-status-cleaning mt -f "$ST1" status
run $S sg_turs-cleaning sg_turs -v "$D1"
run $S sg_logs-tapealert-during-clean sg_logs -p 0x2e "$D1"
run $S mtx-status-cleaning mtx -f "$CH" status
run $S mtx-unload-cleaning mtx -f "$CH" unload "$SC" 0
run $S vtlcmd-tapealert-clear vtlcmd 11 TapeAlert 0
run $S sg_logs-tapealert-cleared sg_logs -p 0x2e "$D1"
jlog $S a "$T0"

########## B. mount timeout: library says loaded, drive never ready ##########
S=b-mount-timeout-view-mismatch; T0=$(date '+%F %T')
DATA=A00005L8; SD=$(cart_slot $DATA)
run $S vtlcmd-delay-load vtlcmd 12 delay load 150
# The robot move completes immediately; the drive then "threads" for 150 s.
TMO=200 run $S mtx-load mtx -f "$CH" load "$SD" 1 &
sleep 8
run $S mtx-status-library-view mtx -f "$CH" status
run $S sg_turs-drive-view sg_turs -v "$D2"
run $S mt-status-drive-view mt -f "$ST2" status
run $S sg_logs-tapealert-drive sg_logs -p 0x2e "$D2"
run $S sg_logs-sad-drive sg_logs -p 0x0c "$D2"
mkdir -p /media/ltfs-b
TMO=30 run $S ltfs-mount-timeout "$LTFS" -f -o devname="$D2" -o verbose=3 /media/ltfs-b
umount /media/ltfs-b 2>/dev/null
TMO=60 run $S sg_turs-poll-30s bash -c "for i in 1 2 3 4 5 6; do date +%T; sg_turs -v $D2; sleep 5; done"
wait
run $S mtx-status-after-thread mtx -f "$CH" status
run $S sg_turs-after-thread sg_turs -v "$D2"
run $S mt-status-after-thread mt -f "$ST2" status
# Second mismatch: the drive daemon ejects on its own; the robot still records the drive Full.
run $S vtlcmd-drive-unload vtlcmd 12 unload $DATA
sleep 3
run $S mtx-status-stale-full mtx -f "$CH" status
run $S sg_turs-drive-empty sg_turs -v "$D2"
run $S mt-status-drive-empty mt -f "$ST2" status
run $S vtlcmd-delay-load-reset vtlcmd 12 delay load 0
run $S mtx-unload-cleanup mtx -f "$CH" unload "$SD" 1
run $S mtx-status-final mtx -f "$CH" status
jlog $S b "$T0"

########## C. missing / unsupported log page ##########
S=c-missing-log-page; T0=$(date '+%F %T')
DATA=A00003L8; SD=$(cart_slot $DATA)   # cartridge from the interrupted-write drill
run $S mtx-load mtx -f "$CH" load "$SD" 2
run $S sg_logs-supported-drive sg_logs -p 0x00 "$D3"
run $S sg_logs-supported-changer sg_logs -p 0x00 "$CH"
run $S sg_logs-0x14-device-stats-drive sg_logs -v -p 0x14 "$D3"
run $S sg_logs-0x18-protocol-port-drive sg_logs -v -p 0x18 "$D3"
run $S sg_logs-0x1b-compression-drive sg_logs -v -p 0x1b "$D3"
run $S sg_logs-0x02-write-errors-changer sg_logs -v -p 0x02 "$CH"
run $S sg_logs-0x03-read-errors-changer sg_logs -v -p 0x03 "$CH"
run $S sg_logs-0x2e-changer sg_logs -p 0x2e "$CH"
run $S sg_logs-0x17-volume-stats-drive sg_logs -p 0x17 "$D3"
run $S ltfsck-list-rollback "$LTFSCK" -l "$D3"
run $S mtx-unload mtx -f "$CH" unload "$SD" 2
jlog $S c "$T0"

run 99-final mtx-status mtx -f "$CH" status
echo "done: $OUT"
