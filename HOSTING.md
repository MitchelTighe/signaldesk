# Hosting handoff — GitHub Pages first, Cloudflare Pages fallback

**Primary: GitHub Pages from the public repository.** [.github/workflows/pages.yml](.github/workflows/pages.yml)
publishes `site/` with the official `actions/upload-pages-artifact` and `actions/deploy-pages`
actions, pinned to commit SHAs, and runs only when started by hand. The page uses relative URLs
only and was rehearsed under the `/signaldesk/` subpath with
[tests/pages_subpath_browser.py](tests/pages_subpath_browser.py). Expected URL after the repository is
public and Pages is set to "GitHub Actions": `https://mitcheltighe.github.io/signaldesk/`.
GitHub Pages ignores `site/_headers`; the same Content-Security-Policy is also in the page's own
meta tag, so the page still cannot make network requests.

## Fallback: Cloudflare Pages, prepare only

The maintainer owns deployment and monitoring. Nothing is deployed. Keep the stable production
URL free, public and unrestricted through **2026-12-15 20:00 UTC**, and longer if
judging extends. Confirm organizer acceptance of recorded test-build access.
`site/` is the complete static bundle: no build command, Functions, API key,
analytics, remote assets, login or fresh inference. `_headers` supplies browser
security policy and revalidation. App resources/data are inline. Navigation and any browser-generated favicon
request go to the same host; the evidence download is a local Blob. Supplemental public-doc
links, if present after genuine grounding, navigate externally only when clicked.

**Maintainer commands, from the reviewed standalone entry** (not executed by
this worker). First obtain the genuine report through the existing broker per
[NVIDIA-PATH.md](docs/NVIDIA-PATH.md), then:

```sh
python3 -m signaldesk.replay --report runs/live-evaluation.json --output site --require-live
python3 scripts/artifact_check.py
sh scripts/secret_scan.sh
python3 scripts/package_public.py --output public-export-final
# On the maintainer's authorized tooling host with Wrangler installed and existing
# brokered Cloudflare credentials; never add credentials to this bundle.
# Once only if the project does not already exist:
wrangler pages project create signaldesk --production-branch main
# Every release, explicitly use the production branch:
wrangler pages deploy site --project-name signaldesk --branch main
```

If the project name is unavailable, choose one once and substitute it in both
commands; record the returned real URL. Account creation/OAuth is an owner step
if existing authorization is absent. Review the standalone archive separately
before public source publication. Direct Upload accepts a directory; keep the
source archive out of the site. Commands follow the [official Direct Upload
guide](https://developers.cloudflare.com/pages/get-started/direct-upload/).
Header syntax follows [Pages headers](https://developers.cloudflare.com/pages/configuration/headers/).

**Acceptance and uptime plan:** after deployment the maintainer opens the production URL in
a private browser on desktop and phone with no login, runs the walkthrough and
download, checks `manifest.json` and MOCK removal against the genuine report,
and verifies headers and no unexpected requests. Save the reviewed bundle,
manifest and deployment ID locally for rollback. Disable optional analytics and
access challenges for this project; do not change unrelated account security.
Arrange an existing free monitor every 15 minutes through December 15: GET the
root and manifest, require HTTP 200, expected title, expected release hash and
`live_recorded: true`; alert the maintainer after two consecutive failures. The maintainer checks daily
and before judging, responds the same day, rolls back to the last genuine build
if broken, and retests anonymously. Static assets need no warm-up process.
This is a plan, not an installed monitor or uptime guarantee. Do not remove the
project, gate access or expire its URL before judging ends.

**Fresh inference option — code ready, deployment pending:** the optional Cloudflare
Worker and explicit live button are implemented. See [DEPLOY.md](DEPLOY.md) for atomic
durable quotas, owner secret injection, exact routes, model/cost bounds and the kill
switch. The checked-in bundle remains offline by default. Enabling live configures
both the HTML meta CSP and `_headers` to allow exactly the reviewed proxy origin;
recorded cases remain the instant default. A replay rebuild resets that opt-in.
