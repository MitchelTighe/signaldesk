# Current screenshot gallery — recorded run and local validator

These images come from the October 22 sandboxed Chromium verification of the current static
page. They show the genuine recorded Nebius replay and the local readings tool, not a mock
vendor run. The page HTML hash matches the accepted implementation; exact capture hashes and
limits are in [CAPTURES.json](screenshots/current/CAPTURES.json). This archive cleanup reuses
those exact captures and makes no new inference request.

| Image | Caption and intended use |
|---|---|
| [Desktop: supported incident](screenshots/current/replay-1280-supported.png) | H05: recorded tape readings support the cleaning runbook; model attribution, exact steps and evidence. |
| [Desktop: handoff](screenshots/current/replay-1280-abstention.png) | H35: conflicting drive/library readings produce a human handoff. |
| [Desktop: quiet window](screenshots/current/replay-1280-quiet.png) | X01: no incident in the supplied recorded window. |
| [Phone: supported incident](screenshots/current/replay-390-supported.png) | The same recorded desk at a 390-pixel CSS viewport. |
| [Phone: handoff](screenshots/current/replay-390-abstention.png) | A phone-width handoff with no unsupported steps. |
| [Editable readings, desktop/light](screenshots/current/panel-1280-light.png) | A judge-entered reading and exact authored-step match; validator only, no model call or action approval. |
| [Editable readings, phone/dark](screenshots/current/panel-390-dark.png) | The local-only form, explicit limits, reset and proposed wording on a narrow viewport. |

Review legibility at the actual form's image size before choosing a gallery. Image count, aspect
ratio and upload limits still require the logged-in form; no uploads were made here. These are
browser viewport captures, not physical-device or operator-study evidence.

Current verification: [replay results](screenshots/current/replay-results.json),
[readings-validator results](screenshots/current/readings-results.json), and
[validation summary](FINAL-VALIDATION.md).
