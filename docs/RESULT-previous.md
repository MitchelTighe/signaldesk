RESULT: DONE

Pass 2 completed on `live-demo`, based on pass 1 commit `53760be`.
Local commit only; no push, deployment, real provider call, key access or new dependencies.

Implemented:
- `web/replay-template.html`: ordered ticket → Lightning draft → deterministic validator
  → Super when required → final incident note playback. X06 opens first with a red veto,
  the actual failed numeric gate and Super's supported media proposal. Each model stage
  shows its observed milliseconds and input/output tokens. Missing measurements stay
  unavailable. Pre-triage, single-model comparisons, abstentions and rejected drafts
  retain their actual paths. Reduced motion renders immediately; replacement cancels
  earlier animation timers.
- Live tickets use the same visual language, with waiting and response-playback states,
  a sourced final note and Markdown export. Export preserves the submitted ticket and
  readings even if edited while the request runs. Provider failures retain a partial
  trace when present and explicitly say the custom ticket has no live answer.
- Evidence-derived scoreboard: 0 unsafe actions executed; 12 of 84 model proposals
  vetoed; estimated route cost $0.040 vs $0.091 Super-only (56% less); 53/54 correct
  routed decisions vs Lightning's 50/54. Each card's tooltip cites `site/replay.json`
  and its contributing fields. Unsafe recommendations (2 to 0) remain distinct from
  equipment actions (none).
- Three editable messy handovers, including X06-style misleading cleaning advice and
  X02-style repeated cleaning. Each example fills matching numeric readings.
- Large text, high contrast, a short explanatory strip and responsive desktop/mobile
  layouts. Honest evidence and live-configuration limits are in “What's next”.
- Rebuilt `site/index.html`, `site/showcase/index.html` and their manifests; updated
  `README.md`; added `worker/pass2.browser.test.mjs` to the browser test script.

Verified commands and observed results:
- `python3 -m unittest discover -s tests`: 183 tests in 28.368s, OK.
- `node --test worker/worker.test.mjs`: 21 passed, 0 failed.
- `node --test worker/runtime.test.mjs` in a network-isolated container: 2 passed,
  including real workerd/SQLite quota races and a mocked Lightning-veto/Super cascade.
- `node --test worker/browser.test.mjs worker/pass2.browser.test.mjs` in a
  network-isolated container: 4 passed, 0 failed, 21.173s. Checked recorded route and
  model-only paths, evidence/metrics, examples, animation order and cancellation,
  reduced motion, export snapshots, invalid source text, missing usage, partial upstream
  failure, pre-triage, quota fallback and zero live requests from the disabled page.
  Both color themes have no horizontal overflow at 1280px and 390px.
- `python3 scripts/live_assets.py --check`: prompt and eight runbooks match.
- `python3 scripts/generate_demo.py --check`: all six generated files match.
- `python3 scripts/artifact_check.py`: 225 public files checked; manifest and static
  bundle budgets passed. Separate PNG CRC/dimension checks passed for all 8 new captures.
- `python3 scripts/check_contrast.py`: minimum checked palette ratio 6.3107:1.
- `git diff --check`: passed.
- Recorded `site/replay.json` is byte-identical to pass 1; SHA-256:
  `8a7f8957b1cd2a87e22ad187d6b375f12a10daa786c7d7839cfebfd4c8c04f50`.

Screenshots (headless Chromium 138.0.2 / Playwright 1.55.0 in a bounded container):

| View | 1280px | 390px |
|---|---|---|
| Intro and scoreboard | [Desktop](../artifacts/2026-10-28/pass2/intro-1280.png) | [Mobile](../artifacts/2026-10-28/pass2/intro-390.png) |
| X06 cascade | [Desktop](../artifacts/2026-10-28/pass2/cascade-1280.png) | [Mobile](../artifacts/2026-10-28/pass2/cascade-390.png) |
| Custom ticket examples | [Desktop](../artifacts/2026-10-28/pass2/ticket-1280.png) | [Mobile](../artifacts/2026-10-28/pass2/ticket-390.png) |
| Complete recorded page | [Desktop](../artifacts/2026-10-28/pass2/replay-1280.png) | [Mobile](../artifacts/2026-10-28/pass2/replay-390.png) |

Capture dimensions and hashes: [screenshots.json](../artifacts/2026-10-28/pass2/screenshots.json).
The capture container was read-only with a writable output mount and temporary filesystem,
network disabled, non-root user, 2 CPU / 1 GiB / 256 PID bounds. It used the existing pinned
Python image and Node binary, with pass 1's installed pinned browser tooling. No installs.
Screenshots were visually inspected, including the mobile ticket and desktop/mobile cascade.

Limits:
- Live remains disabled pending the deployment steps in `DEPLOY.md`. Live UI checks used
  intercepted synthetic responses; provider availability and real live quality are unverified.
- The recorded route is computed from separately saved calls. Playback speed is illustrative;
  recorded model timing is observed. Separate validator timing was not recorded. Live trace
  call timing includes validation; it does not provide a separate validator measurement.
- The 54-case benchmark is same-author synthetic evidence with mhVTL captures, not production
  accuracy or a user study. The bounded live proxy disables hidden thinking for both models;
  recorded Super reasoning-on accuracy does not transfer. Cost is a token estimate using
  recorded rates, not a new billing observation. Operator review is required.
- Pass 1's uncompleted Gitleaks image pull remains unverified; the repo's existing public
  source/credential-shape checks passed. No claim of exhaustive secret scanning is made.
