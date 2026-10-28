# Public requirement recheck · 2026-10-17

**Oct 18 implementation/status update:** the supplied task confirms entrant registration and Token Factory catalog access. Current guarded inference, confirmed case-sensitive model IDs and the static judge plan are in [NVIDIA-PATH.md](NVIDIA-PATH.md) and [JUDGE-ACCESS.md](JUDGE-ACCESS.md). This does not claim a new rules review or a worker live inference call. The findings below remain dated Oct 17.

Compared with the Oct 17 scan summaries in the parent artifact. This is a fresh public-page review, not a byte diff of archived rule versions. **No material change detected in the requirements checked.** The rules page is now directly readable; the FAQ still returns 403 directly and was rechecked through public search indexing. No registration or account access occurred.

| Source | Fresh finding / change from prior record |
|---|---|
| [Official rules](https://nebiusglobalaihackathon.devpost.com/rules), §4 and §6 | Deadline remains **Oct 30, 2026, 10am PDT / 17:00 UTC**. Actual NVIDIA inference through Token Factory, or NVIDIA use on AI Cloud compute, is required. Stage one is viability/stack pass/fail. Stage two has four equally weighted criteria: implementation, design, impact, idea. No exact model ID or API hostname is mandated. |
| [Event / track / deliverables](https://nebiusglobalaihackathon.devpost.com/) | Best Apps and Agents remains the fit; its guidance favors Nemotron. Working demo/test build, public licensed repository with README, description and firsthand technology feedback remain required. Serverless deployment is encouraged, not mandatory. Prior-project updates must be described if applicable. |
| [FAQ](https://nebiusglobalaihackathon.devpost.com/details/faqs) | Indexed text confirms an NVIDIA runtime call through Token Factory suffices; the frontend can run elsewhere. Other inference providers do not satisfy the Nebius requirement. No maximum team size. Direct access remains blocked. |
| [Token Factory quickstart](https://docs.tokenfactory.nebius.com/quickstart) | Global OpenAI-compatible base remains `https://api.tokenfactory.nebius.com/v1/`. Its sample DeepSeek model is not an NVIDIA qualifying choice. |
| [Nebius Nano recipe](https://github.com/nebius/token-factory-cookbook/blob/main/models/nemotron/nemotron3-nano-30b.md), [Super recipe](https://github.com/nebius/token-factory-cookbook/blob/main/models/nemotron/nemotron3-super-120B.md), [Ultra recipe](https://github.com/nebius/token-factory-cookbook/blob/main/models/nemotron/nemotron3-ultra-550b-a55b.md) | Public recipes were checked via their raw GitHub pages. They specify exact case-sensitive IDs and the regional endpoint, documented in [ADAPTER.md](ADAPTER.md). Public documentation does not prove account access or successful inference. |

**Readiness consequence (October 20 update: genuine runtime calls are now recorded in [RUNTIME-EVIDENCE.md](RUNTIME-EVIDENCE.md)):** the local fixture explorer and mocked adapter are prepared for review. Stage-one stack compliance was unproven until the lead made a genuine runtime call and arranges judge access through the judging end. Recheck rules, account model catalog and final submission fields before entering; do not substitute a screenshot of offline output for vendor runtime evidence.

## October 19 finish recheck

The public rules and event requirements were retrieved again. Deadline remains October 30, 13:00 EDT; free judge access runs through December 15. The complete known-field mapping, required formats and explicit execution blockers are in the entrant's private submission packet. The logged-in form was not opened: text limits and additional event questions remain unverified. This is a summary recheck, not an archived-byte comparison.

## October 20 final-polish recheck

Anonymous retrieval of the official rules and event overview succeeded. Checked
requirements remain: October 30 at 10:00 PDT / 13:00 EDT deadline; genuine NVIDIA
runtime via Token Factory or qualifying AI Cloud use; working demo/test-build
access; public licensed source with setup instructions; English description,
track and firsthand technology feedback. Judging ends December 15 at noon PST. The four criteria remain equally
weighted: implementation, design, impact and idea. No logged-in form was opened,
no account action occurred, and replay suitability is not an organizer ruling.
The final mock script targets 165 seconds. Sources: [rules](https://nebiusglobalaihackathon.devpost.com/rules),
[overview](https://nebiusglobalaihackathon.devpost.com/).
