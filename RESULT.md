RESULT: BLOCKED browser/runtime verification unavailable on this node

Recording-flow changes are implemented. The full Python suite and Worker unit suite pass;
the browser and workerd suites still need the integrator's working container route before acceptance.

Changed paths:

- `web/replay-template.html`: tour start closes the custom-ticket and evidence disclosures,
  clears the prior live result/trace/export, stops live playback, and aborts any pending request.
  A late response cannot repopulate the cleared UI. Next switches the tour to paused manual
  stepping; scene 3 stays put until another Next click. Resume explicitly restores timed playback,
  and a new tour retains the existing automatic 30-second mode. The Why link opens the disclosure
  before normal anchor navigation. Below 700 px, evidence, trace and policy tables become labeled
  cards; runbook citations can wrap. The existing limits now include the second-author synthetic
  result: Lightning, Super and routed each 4/10, rules-only 8/10, quality gates failed.
- `site/index.html`, `site/manifest.json`, `site/showcase/index.html`,
  `site/showcase/manifest.json`: rebuilt from the shared template. The default judge artifact has
  an empty live endpoint and `connect-src 'none'`. Both replay JSON payloads are byte-unchanged.
- `tests/judge_browser.py`: narration holds after manual Next, subsequent Next, and evidence-link
  opening/navigation regressions, alongside the existing automatic playback checks.
- `worker/browser.test.mjs`: completed-live-run reset and evidence-link regressions.
- `worker/pass2.browser.test.mjs`: pending-request cancellation/late-response protection,
  manual scene holds, fresh automatic tour, labeled mobile cells without internal clipping,
  full-width model/runbook/cost fields, both themes, and the second-author disclosure.
- `RESULT.md`: this handoff. The supplied `TASK.md` and `ISSUES.md` remain untracked.

Observed verification (2026-10-29):

- `python3 -m unittest discover -s tests -v`: 184 tests, OK, including Node validator parity.
- `node --test worker/worker.test.mjs`: 22 tests, 22 pass, 0 fail.
- `python3 scripts/artifact_check.py`: valid static manifest, 140 resolved local links,
  226 public files, source/shape checks and bundle budget pass.
- `python3 scripts/live_assets.py --check`: Worker prompt and eight runbooks match.
- `python3 scripts/generate_demo.py --check`: all six generated showcase files match.
- `node --check worker/browser.test.mjs`, `node --check worker/pass2.browser.test.mjs`,
  and `node --check` on the generated page script: pass.
- Temporary-copy build with `python3 scripts/configure_live.py --site <temporary-site> --live`,
  followed by the same command without `--live`: exact offline-byte round trip, unchanged replay
  JSON. Offline/live HTML sizes are 299787/299892 bytes, both within the 300000-byte gate.
- `git diff --check`: pass.

Browser checks for the integrator to rerun:

1. In the existing approved test container with locked dependencies, run
   `npm --prefix worker run test:runtime` and
   `AWS_EXECUTION_ENV=AWS_Lambda_nodejs22.x npm --prefix worker run test:browser`.
   The browser command now includes five tests; all live responses are synthetic/intercepted.
2. In the pinned browser/axe container, run `python3 tests/judge_browser.py --output <new-output>`,
   `python3 tests/replay_browser.py --output <new-output>`, the existing readings/showcase checks,
   and the Pages-subpath rehearsal. Repeat against a temporary live-enabled publishing build.
3. Visually at desktop and 390 px, in both themes: run a synthetic live ticket, then start the
   tour. Confirm the expanded panel, old live result, trace and export are cleared. Also start
   the tour while a mocked response is pending and confirm it cannot reopen the live UI.
4. Click Next twice to scene 3 and narrate for over a minute. It must stay on X02; only the next
   Next click moves it to H35. Check Pause/Resume, fresh automatic playback, exit and focus.
5. Close Why, follow the evidence link, and confirm the readings and checks open at `#why`.
   At 390 px inspect model trace, evidence, runbook citations/IDs and policy costs: labels and
   values should be readable without horizontal scrolling or clipped text. Check 320 px too.
6. Confirm the second-author line appears with the other current limits.

Limits: browser tests were extended but not executed here. `worker/node_modules/` and local
Playwright are absent. Podman failed with a read-only `/run/user/1000/libpod` sticky-bit error;
container attempts stopped after the repeated error. No host installs, live inference, deployment
or push occurred. Browser layout, accessibility and workerd runtime acceptance remain unverified.
