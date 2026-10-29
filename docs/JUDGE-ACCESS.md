# Judge access — recorded Nemotron runs and a local validator

The primary judge surface is [site/index.html](../site/index.html). It replays the genuine
October 21 Nebius Token Factory recording: 108 model/case rows, two requested Nemotron models
and 54 incidents. Original reports, failures, routing reconstruction and same-author/tuning
limits are in [RUNTIME-EVIDENCE.md](RUNTIME-EVIDENCE.md). This checked-in build does not perform
fresh inference. The [hosted variant](https://mitcheltighe.github.io/signaldesk/) is configured
for explicit live submissions through the bounded Worker in [DEPLOY.md](../DEPLOY.md).
Both live models use reasoning off; the recorded accuracy figures do not measure that variant.

## What a judge can do without a key

- Explore the recorded incidents, switch between the route and either model, inspect a validator
  veto, open the readings and cited runbook, and export an incident note.
- Expand **Try your own readings**, enter drive/library values and check a proposed runbook step.
  This is local deterministic validation, not a new Nemotron answer. Blank fields stay missing;
  a matching reading and exact step text do not interpret ticket context or apply stop caveats.
- Open the static page directly from a checkout, with no account, API key, quota or payment.
  The page executes no library commands. Editable inputs do not alter the recorded evidence.

All replay data and app code are bundled locally. The checked-in page has no enabled model-call
broker or browser credential; its Content-Security-Policy includes `connect-src 'none'`. The separate
[QA showcase](../site/showcase/index.html) is labelled local mock transport testing. It is not
the judge entry point or qualifying vendor-runtime evidence.

For a new vendor evaluation, a judge can supply their own local environment credential and use
the bounded command in the [README integration guide](../README.md#how-we-used-nemotron-on-token-factory).
Those separate terminal calls may incur charges. The browser replay and readings tool make none.

## Hosting and publication

**GitHub Pages is primary; Cloudflare Pages is the fallback.** The manual
[Pages workflow](../.github/workflows/pages.yml) publishes `site/` when an authorized maintainer
starts it, after testing the offline build and enabling the live endpoint for publication.
[HOSTING.md](../HOSTING.md) is the deployment and rollback handoff. Neither a workflow
file nor a planned URL proves that deployment or anonymous judge access works.

The maintainer controls publication and verifies anonymous access and current live availability.
Local tests do not establish endpoint health or remaining quota. Keep the final judge URL free
and unrestricted through the documented judging end, and recheck any organizer requirements or extension before
claiming access readiness. No organizer acceptance of this replay access plan is claimed.

## Reproduce the static judge bundle offline

From the repository root, revalidate the two recorded reports into a new directory:

```sh
python3 -m signaldesk.replay --report docs/runtime/live-evaluation-20261021-routed-heldout.json --report docs/runtime/live-evaluation-20261021-routed-hard.json --output replay-check --require-live
python3 -m signaldesk.demo
python3 -m unittest discover -s tests -v
python3 scripts/artifact_check.py
```

The builder checks fixture/label integrity, independently revalidates drafts and vetoes, and
recomputes metrics. `--require-live` rejects mock provenance. `manifest.json` contains local file
checksums; neither it nor a saved report cryptographically attests provider execution.

Before publication, review the allowlisted export, run the pinned secret scan, and verify the
actual hosted URL anonymously on desktop and phone. Check the walkthrough, exact release manifest,
relative links, download, local readings panel and browser requests. Public hosting, physical-device
use, screen-reader review, independent operator benefit and uptime remain separate acceptance steps.
