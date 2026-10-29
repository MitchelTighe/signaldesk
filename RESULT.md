RESULT: DONE

Prepared the optional live Nebius path in the fresh public clone, on local branch
`live-demo`. No push, deployment, account creation, real inference or key access/injection.

Ready:
- `worker/index.mjs`: one public POST endpoint with exact-origin CORS, a disabled-by-default
  kill switch, strict request schema/size limits, and a shared SQLite Durable Object enforcing
  20/IP/rolling hour, 100 runs/UTC day and USD 2/day conservative reservations by default.
- `worker/cascade.mjs`, generated `worker/resources.mjs`: the exact existing Lightning/Super
  IDs, deterministic authored-step/evidence validator, physical-action second reading,
  500 output tokens/call, two calls/run, bounded input/response/time, no retries or redirects,
  sanitized cascade trace with latency and observed token counts, and explicit replay fallback.
- `web/replay-template.html`, `site/`: prominent opt-in button, editable synthetic ticket and
  readings, separate live result/trace, cached cases still default. Checked-in networking disabled.
- `scripts/configure_live.py`: enables one reviewed proxy origin in both CSP surfaces and
  updates manifest hashes; no change to recorded evidence. Empty endpoint restores offline mode.
- `DEPLOY.md`: owner steps for account, secret injection, workers.dev/custom routes, page
  configuration, conservative per-1,000-click estimates, live smoke test and kill switch.
- Locked test tooling and public export support; third-party installs stayed in a container.

Checked commands and observed results:
- `node --test worker/worker.test.mjs`: 21 tests passed, 0 failed. Includes quota boundaries,
  concurrent reservations, UTC rollover, validator vetoes, physical escalation, upstream
  redirects/failures, unavailable usage, request/response size bounds and stream cancellation.
- `python3 -m unittest discover -s tests`: 183 tests passed in 27.421 seconds, OK.
  Includes Python/JavaScript validator agreement across all bundled case/runbook proposals,
  static opt-in policy and recorded-evidence preservation.
- `node --test worker/runtime.test.mjs`, in a bounded network-isolated container: 2 passed.
  Real workerd + SQLite admitted exactly 3 of 12 concurrent requests and rejected 9; the
  mocked Nebius cascade returned Lightning veto -> Super accept. Runtime verification caught
  and fixed unsupported redirect handling before any real upstream request.
- `node --test worker/browser.test.mjs`, in a bounded network-isolated container: 1 passed.
  Chromium verified explicit input submission, trace/latency/tokens, unchanged cached evidence,
  mobile width, rate-limit fallback, and zero live requests from the disabled page.
- `wrangler deploy --config worker/wrangler.toml --dry-run`: succeeded, 25.27 KiB upload /
  7.89 KiB gzip, correct Durable Object binding, LIVE_ENABLED=false; dry-run exited without deployment.
- `python3 scripts/live_assets.py --check`: prompt and eight runbooks match Python sources.
- `python3 scripts/generate_demo.py --check`: all six generated showcase files match.
- `python3 scripts/artifact_check.py`: 224 public files checked, links/syntax/PNG/source hygiene
  and static manifest passed; static bundle remains within its size budgets.
- `git diff --check`: passed.

Limits and owner actions:
- Owner must approve the Cloudflare account/deployment, brokered Nebius secret injection and
  spend allowance before enabling/publishing live. No approval is requested by this worker.
- Actual provider availability, current prices, billing controls, public routes and real-model
  quality remain unverified. The bounded live variant disables hidden thinking for both models;
  recorded Super reasoning-on accuracy does not transfer. Operator review remains required.
- Pinned Gitleaks scan attempted on the allowlisted export, but its image pull failed with
  registry connection EOF through the prescribed proxy. No retry or alternative network route.
  Existing public path/credential-shape checks passed; rerun Gitleaks before owner publication.
- Cost estimates use the project's 2026-10-18 rates. Typical 1,000 all-escalated runs at
  3,000 input/300 output per call: USD 1.422; hard model-token bound: USD 9.21 at those rates;
  conservative reservation USD 20 across at least ten days under the default daily caps.
