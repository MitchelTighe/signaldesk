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
