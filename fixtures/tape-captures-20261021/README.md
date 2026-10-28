# mhVTL captures for the three hero cases (2026-10-21)

These are the raw outputs behind held-out cases **H05**, **H35** and **H36**. They come from
an **emulated** tape library: mhVTL 1.8 (open source, https://github.com/markh794/mhvtl),
configured as an STK L700 changer with IBM ULT3580-TD8 (LTO-8) drive emulation, on a lab
machine the authors control. No real site, real drive, employer system or person is involved.

- `capture.sh` reproduces every file. Faults are **injected** with mhVTL's own `vtlcmd`
  (TapeAlert flags, load delay, a drive-side unload). Every reading is the unmodified output
  of `sg_logs`, `sg_turs`, `mtx`, `mt`, `lsscsi`, LTFS 2.4 and `journalctl`.
- `sanitize.sh` replaced the host name and device serials with generic values
  (`tapehost01`, `LIBSN0001`, `DRVSN0001`–`DRVSN0004`). Nothing else was edited.
- Command captures normally record timestamp, command, output and exit code. The device map and later journal re-pulls use different headers; they are not all uniform command receipts.
- [CAPTURE-MANIFEST.json](CAPTURE-MANIFEST.json) hashes all 75 retained raw text files. The October 22 [provenance audit](../../docs/CAPTURE-PROVENANCE.md) checks existing evidence; it is not a new capture.

| Case | Folder | What the files show |
|---|---|---|
| H05 supported | `raw/a-cleaning-tapealert/` | After injection, page 0x2e reports "Cleaning required: 1" and "Cleaning requested: 1" (flags 20 and 21); read/write error counters are 0. A cleaning cartridge load follows. |
| H35 handoff | `raw/b-mount-timeout-view-mismatch/` | `mtx status` reports drive 1 Full with A00005L8 while `sg_turs` returns 02/3A/00 medium not present; LTFS fails with LTFS17168E; the kernel contains two reset-related messages for the same target; the number of distinct reset events is unknown. |
| H36 handoff | `raw/c-missing-log-page/` | The changer rejects pages 0x02/0x03 with 05/24/00 and `sg_logs` cannot decode its page 0x2e. |

Two things did not go as scripted, and the cases use what actually happened:
the 150 s load delay did not hold (the drive answered "becoming ready" at +8 s and was ready by +21 s),
so H35 is a mount **failure** rather than a timeout; and the cleaning-cartridge load returned a
Hardware Error (04/03) to `mtx` even though the drive logged "Cleaning media loaded".
The TapeAlert flags were cleared with `vtlcmd`, not by the emulated cleaning cycle.
- The LTFS mount point was rewritten from a lab path to `/media/ltfs-b` (also in `sanitize.sh`).
