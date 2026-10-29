# Live Nebius demo — build modes and deployment handoff

**Hosted live configuration:** <https://mitcheltighe.github.io/signaldesk/> uses the Cloudflare
Worker at <https://signaldesk-live.goblinworkbench.workers.dev/api/live> for explicit
**Run live on Nebius** submissions. Synthetic ticket text and readings feed Nemotron
3.5 Lightning on Nebius Token Factory; a deterministic validator checks the draft, and
Nemotron 3 Super reads again after a veto, abstention or physical proposal. Recorded
cases remain the instant default, with local readings validation and zero actions executed.
The live variant's reasoning settings differ from the recorded evaluation, as detailed below.

The checked-in `site/` is the reproducible **offline judge artifact**, with networking
disabled. The manual Pages workflow verifies it before switching the publishing artifact
to live mode. This handoff documents future rebuilds, redeployments and rollback; local
tests do not establish current endpoint health or remaining quota.

## Owner decisions before future deployments

Retain the approved Cloudflare account/project, a dedicated Nebius Token Factory key injected
by the owner/broker, and the spend allowance. Default: **100 admitted runs / UTC day,
USD 2 / UTC day in conservative reservations**, and **20 runs per IP in any rolling hour and 40 per UTC day**.
Use a dedicated provider project/key with a provider-side budget where supported;
verify current billing controls in the account. Cloudflare charges are separate.
Do not create an account, authorize OAuth, change plans, inject a key or deploy as
part of this code review. The commands below are for the owner's authorized deployment.

## What is bounded

`POST /api/live` accepts exactly `{ticket, evidence}`. Ticket: at most 2,000 characters;
body: at most 8,192 UTF-8 bytes; at most eight known numeric metrics with distinct IDs
and metrics. Invalid or unknown fields, caller-specified models, prompts, URLs and
output caps are refused. Empty readings are missing, never fabricated zeros.

A single SQLite-backed Durable Object reserves quota atomically **before** inference.
Every edge uses the same object name. Reservations persist across isolates/restarts,
include failed inference runs and never refund; zero-call pre-triage does not reserve quota. The UTC daily counters
reset at midnight; rolling-hour IP windows survive that boundary. Only secret-keyed HMAC IP hashes and
quota counters are retained; tickets, drafts and provider responses are not stored or
logged by this application. Hashes are pseudonymous identifiers, not anonymization.
Expired IP windows are pruned on the next reservation. Cloudflare and Nebius may retain
platform-level request metadata under their own policies.

The only upstream is Nebius `/v1/chat/completions`, without redirects or retries:

- `nvidia/Nemotron-3_5-Lightning`, then, when required,
  `nvidia/nemotron-3-super-120b-a12b`.
- At most **two calls per admitted run**, 500 output tokens each, 24,000 conservative
  input tokens per call (UTF-8 message bytes plus 4,096 framing tokens).
- Each call has a 20-second deadline covering its body, a 64 KiB response cap, and
  required bounded token-usage accounting. Incoming body reading has a 5-second deadline.
- Missing/conflicting/healthy telemetry short-circuits. A veto, abstention or physical
  proposal from Lightning escalates to Super. A Super veto becomes an empty human handoff.
- This bounded live variant explicitly disables hidden thinking for **both** models,
  so reasoning cannot consume the 500-token allowance. The recorded evaluation uses
  Super with reasoning enabled; its accuracy numbers do not apply to this variant.
  Ticket caveats are model-interpreted; exact citations and numeric evidence do not
  prove semantic safety. All output is advice for operator review, with zero actions executed.

No key, disabled switch, invalid config, quota failure, provider failure, missing usage
or timeout produces a live answer. The page explicitly keeps the recorded replay visible
and says custom input has no live answer. It never substitutes a cached answer for the
custom ticket. Trace rows show fixed model IDs, sanitized proposed runbook IDs, validator
verdicts/codes, elapsed milliseconds and observed input/output tokens; unavailable usage
is labeled unavailable. Raw model prose and provider error bodies are never rendered.

## Validate and prepare on an authorized tooling host

Use Node 22+ and Python 3.12+. Install the locked developer tools **inside a container**
or the existing sandbox; never install these packages on a basement host. The lockfile
pins Wrangler 4.45.0, Playwright 1.55.0 and packaged Chromium 138.0.2. The Worker itself
has no runtime npm dependencies. Chromium is a test-only executable, never shipped to Workers.

```sh
npm ci --prefix worker --no-audit --no-fund
python3 scripts/live_assets.py --check
node --test worker/worker.test.mjs
python3 -m unittest discover -s tests
npm --prefix worker run test:runtime
AWS_EXECUTION_ENV=AWS_Lambda_nodejs22.x npm --prefix worker run test:browser
python3 scripts/generate_demo.py --check
worker/node_modules/.bin/wrangler deploy --config worker/wrangler.toml --dry-run --outdir .scratch/worker-bundle
```

The packaged Chromium test in a minimal Debian container uses its bundled Lambda
libraries through `AWS_EXECUTION_ENV=AWS_Lambda_nodejs22.x` for that test process. Run the container as
a non-root user so archive extraction can set ownership. Tests use intercepted requests,
synthetic responses and network isolation. Runtime tests bind port 0 and dispose workerd.

## Future Worker deployments and secret injection

On the owner's authorized tooling host with an existing authenticated Cloudflare account:

1. Review `worker/wrangler.toml` (currently live-enabled). Before the staged deployment below,
   set `LIVE_ENABLED = "false"`. Set `ALLOWED_ORIGIN`
   to the page's **origin only**, e.g. `https://mitcheltighe.github.io` (no path or trailing slash).
   Keep the approved limits. The code refuses caps above 1,000 runs or 200 cents daily.
2. Deploy the disabled Worker and SQLite namespace:

   ```sh
   worker/node_modules/.bin/wrangler deploy --config worker/wrangler.toml
   ```

3. The owner/broker injects the dedicated key through the interactive secret prompt:

   ```sh
   worker/node_modules/.bin/wrangler secret put NEBIUS_API_KEY --config worker/wrangler.toml
   worker/node_modules/.bin/wrangler secret put IP_HASH_SECRET --config worker/wrangler.toml
   ```

   Use an independently generated high-entropy secret for IP_HASH_SECRET. Rotating it resets per-IP accounting until existing windows expire.
   Never put the value on a command line, in shell history, a file, `.env`, `.dev.vars`,
   Wrangler configuration, browser source or a model prompt. Do not enable request-body
   logging or `wrangler tail` while handling a real key or user text.

The default route is `https://signaldesk-live.<account-subdomain>.workers.dev/api/live`;
use the real URL returned by Wrangler. All other paths are refused. CORS accepts just
the configured page origin and POST/OPTIONS. CORS is not authentication: non-browser
clients can forge Origin, so durable global caps are the spending boundary. Cloudflare's
edge supplies `CF-Connecting-IP`; never expose this handler behind a proxy that trusts
caller-supplied IP headers. Preview URLs are disabled to avoid an alternate live surface.

For an **existing proxied DNS hostname** in an existing Cloudflare zone, alternatively
add this top-level configuration before `[vars]` (replace the example with the owned zone):

```toml
workers_dev = false
routes = [{ pattern = "demo.example.org/api/live*", zone_name = "example.org" }]
```

Replace the existing `workers_dev` line rather than duplicating it. The Worker still
accepts only the exact `/api/live` path without query parameters. Do not change DNS or
create routes for unrelated services. See [Cloudflare routing](https://developers.cloudflare.com/workers/configuration/routing/routes/),
[secrets](https://developers.cloudflare.com/workers/configuration/secrets/) and
[SQLite Durable Objects](https://developers.cloudflare.com/durable-objects/api/sqlite-storage-api/).

## Build offline or live mode

Reproduce the default offline artifact from the template and bundled replay:

```sh
python3 scripts/configure_live.py
python3 -m unittest discover -s tests -v
python3 scripts/artifact_check.py
```

Build the live publishing artifact with the deployed Worker URL above:

```sh
python3 scripts/configure_live.py --live
python3 scripts/artifact_check.py
```

This updates the static HTML, its meta CSP, Cloudflare Pages `_headers`, and manifest
hashes. Only that one proxy origin is allowed in `connect-src`; the key never reaches
the browser. `site/replay.json` is unchanged. Publish that reviewed `site/` bundle through
the existing GitHub Pages workflow or Pages process in `HOSTING.md`. The GitHub Pages
meta CSP and Cloudflare Pages header CSP must agree. Rebuilding a replay with the
original builder disables live again; rerun `--live` after any rebuild. Running without
`--live` restores the exact offline artifact. For a different reviewed proxy use
`--endpoint https://signaldesk-live.example.workers.dev/api/live` instead of `--live`.
The mock `site/showcase/` intentionally remains offline.

Set `LIVE_ENABLED = "true"` in the reviewed Wrangler configuration, then redeploy it.
With the owner-approved key and spend cap, open the page in a private browser:

1. Confirm cached cases are instant and make no proxy requests.
2. Click the prominent live button, enter a synthetic ticket and a single abnormal
   reading, then click Run. Inspect Lightning → validator → Super as applicable, token
   counts and latency. Confirm physical proposals get a second reader and no actions run.
3. Try missing and conflicting readings: pre-triage should make no model calls.
4. Temporarily lower `DAILY_RUN_CAP` to the already consumed count (minimum 1), redeploy,
   and confirm replay is clearly labeled when limited. Restore only the approved cap.
5. Record observed usage and costs in the owner's private billing process. If either exact
   model is unavailable or truncates frequently, keep live disabled; do not silently substitute models.

Local mock tests establish code behavior, not account permissions, current model availability,
current rates, public route propagation or real inference accuracy. Those require this owner smoke test.

## Cost per 1,000 judge clicks

Planning rates from the project's `signaldesk/pricing.json`, observed **2026-10-18**:
Lightning USD 0.06 / 0.24 per million input / output tokens; Super USD 0.30 / 0.90.
Recheck the exact model IDs and rates in the [public model catalog](https://tokenfactory.nebius.com/api/public/models_info)
and the owner account before enabling; these are estimates, not current provider quotes.

| 1,000 clicks | Model token estimate |
| --- | ---: |
| Cached cases, disabled/limited service, or pre-triage | USD 0 |
| Lightning only, assuming 3,000 input + 300 output per call | USD 0.252 |
| Every run escalates, same token assumption for each model | USD 1.422 |
| Maximum bounded input and 500 output, both models every run | USD 9.21 |
| Conservative quota reservation, 2x above maximum rounded up | USD 20 reserved |

Each admitted run reserves **2 cents** regardless of path. With defaults, only 100
live attempts are admitted per UTC day, so 1,000 live attempts take at least ten days;
extra clicks fall back to replay. The daily model-token estimate is at most USD 0.921
at the recorded rates, within the USD 2 reservation cap. No input-cache discounts assumed.
A changed provider tariff can invalidate dollar estimates, so the provider-side cap
and owner review remain necessary. The daily cap is not a lifetime project budget.

Cloudflare Workers and SQLite Durable Objects support a Free plan, subject to current
[platform limits and pricing](https://developers.cloudflare.com/durable-objects/platform/pricing/).
An otherwise unused Free account is expected to cover this small test; quotas may instead
stop service. Existing account traffic, paid plans, storage or abuse can change costs.
The Nebius limiter does not cap Cloudflare charges or unrelated uses of the key.

## Kill switch and rollback

Immediate server-side stop: set `LIVE_ENABLED = "false"` in the Cloudflare dashboard
Worker variables and deploy that change, then also set it false in `worker/wrangler.toml`
to keep the next deployment disabled. Alternatively, edit that file first and run:

```sh
worker/node_modules/.bin/wrangler deploy --config worker/wrangler.toml
```

New requests fail closed. Calls already in flight may finish within their deadlines;
reservations remain charged. For a credential emergency, the owner can remove the Worker
secret without displaying its value:

```sh
worker/node_modules/.bin/wrangler secret delete NEBIUS_API_KEY --config worker/wrangler.toml
```

To return the page to fully offline behavior:

```sh
python3 scripts/configure_live.py --site site
```

Republish the resulting static bundle. This clears the endpoint and restores `connect-src 'none'`.
Keep the quota namespace and stable object name when disabling/redeploying: deleting or renaming
them would reset reservations. Static-page rollback alone does not disable a public API.
