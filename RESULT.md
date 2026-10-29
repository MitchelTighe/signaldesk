RESULT: DONE

Pre-judging review on 2026-10-29. Its fixes are listed below. The container-only gates it could
not run (Worker runtime and browser suites, Wrangler dry-run, browser, accessibility and
Pages-subpath acceptance, pinned launchers, Gitleaks scan) were then run in rootless Podman and
pass; see Container verification.

Changed paths:

- `scripts/fresh_copy.py`: select the README's offline quickstart section instead of its
  earlier billable evaluation example. Reuse the current Python interpreter, preserve tool
  lookup for Node parity, and keep credentials out of child environments. Use the standard
  tar data filter when supported, with existing regular-file/path checks on older Python.
- `scripts/package_public.py`: include exactly the nine reviewed October 28 pass-2 capture
  paths referenced by `docs/RESULT-previous.md`. Previously the source-tree artifact check
  passed but the exported copy failed on those missing screenshot links.
- `tests/test_judge.py`: extend the archive audit to execute the artifact checker inside
  the extracted archive, so missing exported assets fail the suite.
- `README.md`, `SUBMISSION.md`, `DEPLOY.md`: describe configured live submissions separately
  from the checked-in offline artifact and current endpoint health. Make the staged disabled
  Worker deployment instruction explicit; remove the implication that the Worker runs Python.
- `README.md` also states what Nebius Token Factory contributes (all NVIDIA model inference, for
  the recorded evaluation and the hosted live demo) and that no other Nebius service is used.
- `HOSTING.md`, `docs/JUDGE-ACCESS.md`: reconcile live publishing with the offline source;
  replace the missing `runs/live-evaluation.json` example with both bundled genuine reports.
- `docs/SHOWCASE.md`: identify `site/showcase/` as the mock QA output.
- `docs/GALLERY.md`, `docs/FINAL-VALIDATION.md`, `docs/EXPLAIN-IT.md`: date historical captures
  and acceptance evidence, remove a stale current test count, and distinguish recorded
  reasoning-on Super results from the live reasoning-off variant.
- `RESULT.md`: this review, with the pre-existing report preserved below.

Verification and observed output:

- `python3 -m unittest discover -s tests -v` on this worktree: **184 tests in 25.750s, OK**,
  including Node parity and the extracted-archive regression; no skips. Python 3.12.15,
  Node v24.21.0. Used `PYTHONDONTWRITEBYTECODE=1` and a worktree scratch TMPDIR.
- `node --test worker/worker.test.mjs`: **22 passed, 0 failed, 0 skipped**.
- `python3 scripts/package_public.py --output .scratch/prejudge-20261029/delivery-export`:
  **235 allowlisted files exported**. Exactly nine artifact paths are included; unrelated
  artifacts remain excluded.
- `PYTHONDONTWRITEBYTECODE=1 python3 scripts/fresh_copy.py --archive .scratch/prejudge-20261029/delivery-export/signaldesk.tar.gz --output .scratch/prejudge-20261029/delivery-copy`:
  all three README quickstart commands exit 0; demo prints the recorded briefs;
  **184 tests in 23.002s, OK**; artifact checker passes. No extraction warning remains.
  This is a fresh standalone archive, without git metadata or parent imports, not an
  anonymous public Git clone.
- `python3 scripts/artifact_check.py`: **235 public files, 145 resolved local links,
  47 Python files parsed, 12 shell scripts checked, 16 PNGs checked**, valid site manifest
  and bundle budget. The same checks pass inside the standalone export.
- `python3 scripts/live_assets.py --check`: prompt and eight runbooks match.
  `python3 scripts/generate_demo.py --check`: all six generated files match.
- In the extracted copy, `python3 scripts/configure_live.py --live`, artifact check,
  `python3 scripts/configure_live.py`, artifact check: both modes pass; switching back
  restores all four site files byte for byte. Live HTML is 299,892 bytes; offline is
  299,787 bytes, below the 300,000-byte budget. No provider call was made.
- Synthetic quickstart probes: earlier/later shell examples never execute; only the
  offline-heading commands run; a synthetic parent-only variable is absent in children;
  a missing offline heading refuses before any child command.
- Manual local-document check: 44 file/heading targets resolve in README, SUBMISSION,
  DEPLOY, HOSTING and JUDGE-ACCESS. `git diff --check` passes.
- Protected scoring/routing/replay code, the replay template, and both recorded replay
  JSON files match the starting HEAD bytes. Static site files were not changed.

Remaining findings and limits, in priority order:

1. `SUBMISSION.md` still contains `VIDEO_URL_PENDING_OWNER`. A real public video URL and
   entrant submission are required; neither can be invented or uploaded by this pass.
   `scripts/capture_draft.py` remains a mock rehearsal with obsolete pending-runtime and
   forty-case captions; do not use it unchanged for the final video.
2. Hosted access, checked 2026-10-29 15:07 EDT from an ordinary network: the demo page returns
   HTTP 200; the Worker answers the page origin's CORS preflight with 204; one live POST from
   that origin returned a live answer (Lightning vetoed, Super accepted, zero actions). Requests
   that do not come from the page origin get HTTP 403 by design; judges using the page in a
   browser are not affected. Quota and current prices still depend on the account.
3. Container gates now pass in rootless Podman; see Container verification below.
4. Limited tracked-text scans found no likely credential literal, private network address,
   machine-specific path or private-person disclosure. Broader assignment matches
   were known synthetic test fixtures; email-like matches were public distro build metadata
   or synthetic test URLs. Public entrant attribution remains in SUBMISSION and public URLs
   as intentional submission metadata. All eight newly exported captures were visually
   reviewed and all sixteen packaged PNGs passed metadata/CRC checks. This is not an
   exhaustive secret scan, history review, OCR audit or certification of absence.
5. No production TODO/FIXME/debugger/console-debug leftovers were found. The parity test's
   `console.log` serializes test output. One unused `abstention` import remains in
   `signaldesk/live_eval.py`; that evaluation/scoring path was deliberately left untouched.
   Tested legacy CPU-demo pages under `web/` still contain older pending-runtime wording;
   they are not the primary judge entry and were not removed.
6. Current screenshots/video, real phone/screen-reader checks and live quality remain
   separate acceptance work. Historical screenshots do not match the current HTML hash.
   The live HTML has only 108 bytes of budget headroom. Recorded same-author accuracy,
   the negative second-author result and production limitations remain unchanged.

Evidence is under `.scratch/prejudge-20261029/` (ignored, not committed). TASK.md and
ISSUES.md were pre-existing untracked inputs and are left untouched.

Container verification (2026-10-29, rootless Podman, tests executed with networking disabled):

- Pinned runtime image, `sh run.sh test`: 184 tests OK, 1 skipped (parity needs Node). Python 3.12.12 with Node 22.20.0: 184 tests OK.
- Worker on Node 22.20.0 (Debian): unit 22/22, runtime 2/2, browser 5/5 (run twice);
  `wrangler deploy --dry-run` bundle 25.72 KiB (8.02 KiB gzip).
- Playwright 1.55.0 container: judge tour and axe audits (35 checks, 0 violations), replay 81 checks,
  readings 400 checks, showcase in both themes and the GitHub Pages subpath rehearsal,
  repeated on the `--live` build with zero external requests; offline bytes restore exactly.
- `scripts/container_acceptance.sh`: PASS. `scripts/secret_scan.sh` (pinned Gitleaks, tracked
  files): PASS, no findings.

---

Previous report (before this pass; preserved verbatim):

RESULT: DONE

Recording-flow fixes from visual QA:

- **Clean tour start.** Starting the walkthrough closes the own-ticket and evidence disclosures,
  clears any earlier live result, trace and export, and aborts a pending live request; a late
  response cannot repopulate the cleared page.
- **Scenes hold for narration.** Next switches the tour to manual stepping: each scene, including
  scene 3 (repeated cleaning), stays until the next click. Resume restores timed playback, and a
  fresh walkthrough keeps the automatic 30-second mode.
- **"Why? Evidence and checks"** opens the evidence disclosure before scrolling to it.
- **Phone tables.** Below 700 px the evidence, model-trace and policy tables become labeled cards,
  so model names, runbook IDs and costs are readable without horizontal scrolling.
- **Second-author result on the page.** The limits now state the second-author synthetic check:
  Lightning, Super and the route each scored 4/10, rules alone 8/10, and quality gates failed.

`site/` and `site/showcase/` were rebuilt from the shared template; the checked-in judge artifact
stays offline (empty endpoint, `connect-src 'none'`) and both replay JSON files are unchanged.

Verification on 2026-10-29, rootless Podman, tests executed with networking disabled:

- Python 3.12.12 with Node 22.20.0: `python3 -m unittest discover -s tests -v`, 184 tests OK.
- Pinned runtime image, `sh run.sh test`: 184 tests OK, 1 skipped (parity needs Node).
- Worker on Node 22.20.0 (Debian): unit 22/22, runtime 2/2, browser 5/5 (run twice);
  `wrangler deploy --dry-run` bundle 25.72 KiB (8.02 KiB gzip).
- Browser acceptance in the Playwright 1.55.0 container (Chromium sandbox on): judge tour,
  scene holds, evidence link and axe WCAG 2.1 A/AA audits (35 checks, 0 violations), replay 81 checks,
  editable readings 400 checks, showcase in both themes, GitHub Pages subpath rehearsal.
- Live build (`configure_live.py --live`): judge, readings and Pages-subpath checks pass with
  zero external requests; rebuilding without `--live` restores the offline bytes exactly.
- `scripts/container_acceptance.sh`, `scripts/live_assets.py --check`,
  `scripts/generate_demo.py --check` and `scripts/artifact_check.py`: pass.

Local mock and browser tests establish code behavior, not account permissions, current model
availability or real inference accuracy.
