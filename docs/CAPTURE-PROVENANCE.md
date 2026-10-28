# Captured readings and authored incidents

An October 22 audit found three existing hero capture sets from October 21. This audit did not
rerun the lab, inject a fault, call a model or generate three new incidents. The files already
ship with the demo and its “mhVTL captures” filter. They are emulator output with deliberately
injected faults, not observations from physical tape hardware or an employer system.

The [capture manifest](../fixtures/tape-captures-20261021/CAPTURE-MANIFEST.json) records SHA-256
hashes for all 75 retained raw text files and their original source revision. Hashes detect
subsequent changes; they cannot independently authenticate the original execution. Hostnames,
serials and one mount path were sanitized as described in the [capture notes](../fixtures/tape-captures-20261021/README.md).

| Frozen case | What is backed by output | Limit |
|---|---|---|
| H05, cleaning request | [TapeAlert flags](../fixtures/tape-captures-20261021/raw/a-cleaning-tapealert/05-sg_logs-tapealert-after.txt) show cleaning required/requested set; [read counters](../fixtures/tape-captures-20261021/raw/a-cleaning-tapealert/07-sg_logs-read-errors.txt) are zero. | Title, ticket wording and expected runbook are authored. Two set flags are not two independent fault incidents. |
| H35, mount failure and view mismatch | [LTFS output](../fixtures/tape-captures-20261021/raw/b-mount-timeout-view-mismatch/08-ltfs-mount-timeout.txt) records a failed mount; later [library status](../fixtures/tape-captures-20261021/raw/b-mount-timeout-view-mismatch/14-mtx-status-stale-full.txt) and [drive status](../fixtures/tape-captures-20261021/raw/b-mount-timeout-view-mismatch/15-sg_turs-drive-empty.txt) disagree. | These are time-separated snapshots. They do not establish that the later mismatch caused the earlier mount failure. |
| H36, unavailable numeric evidence | The changer rejects [page 0x02](../fixtures/tape-captures-20261021/raw/c-missing-log-page/07-sg_logs-0x02-write-errors-changer.txt) and [page 0x03](../fixtures/tape-captures-20261021/raw/c-missing-log-page/08-sg_logs-0x03-read-errors-changer.txt); [page 0x2e](../fixtures/tape-captures-20261021/raw/c-missing-log-page/09-sg_logs-0x2e-changer.txt) cannot be decoded. | Missing readings do not mean zero errors. |

## H35 reset-count caveat

The [kernel extract](../fixtures/tape-captures-20261021/raw/b-mount-timeout-view-mismatch/20-kernel-b.txt)
contains “Power-on or device reset occurred” at 13:00:52 and “Power on/reset recognized” at
13:01:00 for the same SCSI target. Those may describe the same reset; two distinct events are
**unknown**. The frozen H35 field `scsi_unit_attention_count=2` and ticket's “two events” wording
are the author's interpretation of two messages, not an independently verified event count.
The recorded vendor input remains unchanged so its fingerprints and original result stay
reproducible. Do not present that field as two measured resets or independent reliability evidence.

The 13:01:46 library/drive mismatch follows an explicit `vtlcmd ... unload` injection at
13:01:43. X09's “unloaded on its own” wording describes the fictional ticket context, not a
naturally occurring ejection; the captured reading itself is genuine emulator output.

The hard cases reuse capture readings with authored context, caveats and adversarial text.
They are neither additional captured incidents nor independent-author validation. New fault
families (for example media/hardware alerts or a full library) remain separate work; this audit
claims no such new capture and no operator benefit.
