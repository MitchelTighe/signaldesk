RESULT: BLOCKED full browser/runtime validation needs an approved dependency sandbox

Fixed the three reported Python test failures. The default checked-in site is again
the offline judge artifact. Added an explicit --live build flag using the deployed
Worker endpoint; the manual Pages workflow tests offline mode before building the
live publishing artifact. README.md, SUBMISSION.md and DEPLOY.md now describe the
live demo, its Nebius/Nemotron feed, offline reproduction and failure fallback.

Changed paths: .github/workflows/pages.yml, scripts/configure_live.py,
tests/test_live_worker.py, site/index.html, site/_headers, site/manifest.json,
README.md, SUBMISSION.md, DEPLOY.md, RESULT.md. Recorded replay data is unchanged.
TASK.md and ISSUES.md were supplied untracked inputs and are excluded from the commit.

Checks run here:

- python3 -m unittest discover -s tests -v
  Output tail: Ran 184 tests in 23.570s; OK. No tests skipped.
  The baseline before the fix ran 183 tests with exactly three failures.
- node --test worker/worker.test.mjs
  Output tail: tests 22; pass 22; fail 0; cancelled 0; skipped 0; todo 0.
- python3 scripts/artifact_check.py
  Passed for both offline and --live artifacts: static_manifest_valid true,
  bundle_budget.passed true, source hygiene and local links passed.
- python3 scripts/live_assets.py --check
  Worker prompt and eight runbooks match canonical Python sources.
- python3 scripts/generate_demo.py --check
  Deterministic showcase: all six generated files match.
- python3 -m signaldesk.demo
  Printed the recorded hero briefs and walkthrough, ending with:
  Open site/index.html for the interactive recorded demo.
- git diff --check: passed.

The remaining suites were attempted, not skipped or weakened:

    node --test worker/runtime.test.mjs worker/browser.test.mjs worker/pass2.browser.test.mjs
    tests 3; pass 0; fail 3; skipped 0
    ERR_MODULE_NOT_FOUND: playwright (browser suites), miniflare (runtime suite)

    python3 tests/replay_browser.py --output .scratch/a6/replay-browser
    ModuleNotFoundError: No module named 'playwright'

worker/node_modules is absent. Podman failed to obtain configuration because its
runtime directory is read-only, including when task-local storage/runroot arguments
were supplied. Stopped after the second occurrence. No host installs, service
changes, remote calls, pushes or credential reads were performed. An approved
dependency sandbox is needed to run the remaining browser/runtime checks, including
judge_browser.py and the other browser acceptance scripts. Existing checked-in
screenshots do not establish acceptance of this change. Full-suite success is not claimed.

Decisions: use a build flag rather than duplicate the static bundle. The CLI regression
checks both modes, replay preservation, manifest hashes and exact offline restoration.
The publishing workflow remains manual. The final working-tree site is offline.
Deployment status comes from the task and checked-in configuration; no live endpoint
health, remaining quota or new inference accuracy was measured.

Integrator: provide the locked tools in an approved container/sandbox, then run the
runtime/browser commands in DEPLOY.md and browser acceptance in the pinned judge
container. No test was disabled. Local execution transcripts are in .scratch/a6/
(ignored and excluded from the public package). This report records the verification
blocker; the build/docs fix is ready for integration review.
