RESULT: DONE

The checked-in `site/` is the offline judge artifact again (empty endpoint, `connect-src 'none'`).
`python3 scripts/configure_live.py --live` builds the hosted live variant; running it without the
flag restores the offline bytes exactly. The manual Pages workflow tests the offline default before
building and publishing live mode. Recorded replay data is unchanged.

Fixed during verification:

- Light theme: the **Try your own ticket** and **Run live on Nebius** buttons rendered near-white
  text on white (contrast 1.07:1); they now keep their green background.
- `tests/judge_browser.py`: after leaving the tour, Tab reaches the own-ticket panel and then the
  model control (the panel was added after the check was written).
- Worker browser tests run one file at a time: parallel files raced while extracting the packaged
  Chromium (`spawn ETXTBSY`).
- The JavaScript/Python validator parity test is skipped when Node is not installed, as in the
  pinned Python image used by `sh run.sh test`; it runs wherever Node 22+ is present.
- The export-archive test no longer copies ignored `node_modules/` and `.scratch/` into its
  temporary directory (it ran out of space after `npm ci`).

Verification on 2026-10-29, rootless Podman, tests executed with networking disabled:

- Python 3.12.12 with Node 22.20.0: `python3 -m unittest discover -s tests -v`, 184 tests OK.
- Pinned runtime image, `sh run.sh test`: 184 tests OK, 1 skipped (parity needs Node).
- Worker on Node 22.20.0 (Debian): unit 22/22, runtime 2/2, browser 4/4 (run twice);
  `wrangler deploy --dry-run` bundle 25.72 KiB (8.02 KiB gzip).
- Browser acceptance in the Playwright 1.55.0 container (Chromium sandbox on): judge tour and axe
  WCAG 2.1 A/AA audits (30 checks, 0 violations), replay 81 checks, editable readings 400 checks,
  showcase in both themes, GitHub Pages subpath rehearsal.
- Live build: identical to the published page apart from the light-theme fix; judge, readings and
  Pages-subpath checks pass with zero external requests.
- `scripts/container_acceptance.sh`, `scripts/live_assets.py --check`,
  `scripts/generate_demo.py --check` and `scripts/artifact_check.py`: pass.

Local mock and browser tests establish code behavior, not account permissions, current model
availability or real inference accuracy.
