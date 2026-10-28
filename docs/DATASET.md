# Corpus and held-out evaluation (tape v3)

SignalDesk is a tape-library incident desk. Its eight runbook families cover LTO drives, medium changers and LTFS volumes. Each runbook step cites public documentation only: sg3_utils, mtx and mt-st man pages, the T10 ASC/ASCQ table, and the open-source LTFS and mhVTL projects (see `sources` in [data.json](../signaldesk/data.json)). No employer material, site configuration, hostname or person appears anywhere. Library names like "library A" and device paths like `/dev/sg5` are placeholders.

| Split | File | Size | Purpose |
|---|---|---:|---|
| Training | [training.json](../signaldesk/training.json) | 64 tickets, 8 per family | Text and expected family train the naive Bayes baseline. Metric evidence is not a classifier feature. |
| Demo / smoke | [data.json](../signaldesk/data.json) | 8 tickets | CLI walkthrough (`load-demo`, `clean-demo`, `ltfs-demo`, …); never counted as held-out performance. Holds the 8 runbooks, their thresholds, steps, step sources and caveats. |
| Held-out | [heldout.json](../signaldesk/heldout.json) | 40 tickets | 32 known cases (4 per family: known, known, paraphrase, distractor) plus 8 intended abstentions. |
| Challenge | [challenge.json](../signaldesk/challenge.json) | 64 tickets | 40 ordinary, 8 insufficient or conflicting, 16 adversarial (prompt injection, fake runbooks, homoglyph metrics, hidden conflicts). |

The families are: drive requests cleaning (`tapealert_cleaning_flags` ≥ 1, TapeAlert flags 20/21), suspect cartridge (`tapealert_media_flags` ≥ 1, flags 4/7), drive hardware fault (`tapealert_hardware_flags` ≥ 1, flags 30/31), cartridge load timed out (`load_wait_seconds` ≥ 120), library inventory disagrees (`inventory_mismatch_count` ≥ 1), LTFS volume will not mount (`ltfs_mount_errors` ≥ 1), SCSI path resets (`scsi_unit_attention_count` ≥ 3) and cartridge write-protected (`write_protect_rejections` ≥ 1). Runbooks name hypotheses, not root causes. Thresholds are authored demonstration policy, not vendor guidance.

## Hero cases from mhVTL

Held-out **H05** (cleaning request, supported), **H35** (library and drive disagree after a slow load, so two families are abnormal and the desk hands off) and **H36** (TapeAlert page unavailable, so there is no telemetry and the desk hands off) are the three demo scenes. They are slots for sanitized captures from an mhVTL emulated library the author controls. While a case carries `"capture": "pending-mhvtl"` its values are authored placeholders. When real captures replace them, the field is set to a value starting with `mhvtl`, the replay lists that case under `captured_cases`, and the frozen held-out hash in the tests must be updated. All other cases are hand-authored synthetic text.

## Independence and leakage limits

Training, held-out, challenge and demo IDs and texts are disjoint, and a test enforces it. Training reads only the training file. Model requests contain neither labels nor training examples. **Same AI author, same task, same taxonomy:** this is independent at the file and fitting level only. It is not externally authored or blinded validation. Shared tape vocabulary favours the baseline; paraphrases, distractors, missing or invalid telemetry, concurrent faults and injections expose weaknesses. No thresholds or texts were changed after scoring.

## Measured baseline (CPU naive Bayes, 2026-10-21)

Run `python3 -m signaldesk evaluate`. Quality gates: accepted precision ≥ 0.80, known-case recall ≥ 0.65, all intended unknowns rejected.

| Metric | Observed |
|---|---:|
| Accepted precision | **29/29 = 100%** |
| Known-case recall | **29/32 = 90.6%** |
| Abstention rate | **11/40 = 27.5%** |
| Unknown rejection | **8/8 = 100%** |
| Overall label agreement | **37/40 = 92.5%** |

| Family | Correct / known |
|---|---:|
| Cleaning request | 3/4 |
| Suspect cartridge | 4/4 |
| Drive hardware fault | 4/4 |
| Load timeout | 4/4 |
| Inventory mismatch | 4/4 |
| LTFS index | 4/4 |
| SCSI path resets | 2/4 |
| Write protect | 4/4 |

Misses: H08 (cleaning ticket with a clear media-flag distractor; failed the confidence gate), H15 (path-reset paraphrase with no tape vocabulary; failed the confidence gate) and H16 (path resets with a clear hardware-flag distractor; the classifier picked a family whose telemetry did not corroborate it, so the validator rejected it). They stay visible in the UI and the evaluation JSON. The frozen challenge set scores 64/64 with full injection confinement ([challenge-evaluation.json](challenge-evaluation.json)); that is a property of same-author text, not a robustness guarantee.

Next experiment: have an outside tape operator write a blinded set with overlapping faults and noisy telemetry, then compare the baseline and the Nemotron selector at identical coverage.


## Hard adversarial split (added October 21, evening)

[signaldesk/hard.json](../signaldesk/hard.json) holds 14 incidents, X01–X14, written after a
rules-only baseline (read the numbers, pick the single abnormal family, never read the text) also
scored 40/40 on the held-out set. Nine of them (X01–X05, X07, X09, X11, X13) copy their readings from
the sanitized mhVTL captures; the operator context around them is authored. Kinds: healthy and
decoy-normal windows that must say "no incident", runbook-caveat cases where the readings back an
action the context forbids (X02 flag returns after two cleanings, X03 cleaning load already failed),
prompt injection in both directions (X05, X12), operator text that contradicts the telemetry (X06),
a just-below-gate load (X08), conflicting families (X10), thin changer telemetry (X13) and a
write-protected vault cartridge (X14). Each case carries a `why` field; `kind`, `why` and `expected`
never reach the model. The rules-only baseline scores 12/14 (it fails X02 and X03 by construction).
The prompt revision and the routing policy were chosen after a first live run on this split, so it
is not a blind test of the route; the held-out 40 were not used for any choice.
