# Submission preparation — SignalDesk

**Track:** Best Apps and Agents. **Entrant:** Mitchel Tighe. The entrant has registered on Devpost and has Token Factory access. Deadline: October 30, 2026, 13:00 EDT / 17:00 UTC.

**Hosted demo:** https://mitcheltighe.github.io/signaldesk/ — recorded Nebius cases replay
instantly. The hosted variant is configured so **Run live on Nebius** explicitly sends
synthetic ticket text and readings to
https://signaldesk-live.goblinworkbench.workers.dev/api/live. The Cloudflare Worker calls
Nemotron 3.5 Lightning on Nebius Token Factory, validates the draft, and routes to Nemotron
3 Super after a veto, abstention or physical proposal. Live results are separate from replay;
quotas or failures leave the recording available. Both live models run with reasoning off,
so the recorded accuracy figures below do not measure the live variant. No actions execute.

**Offline judge build:** open `site/index.html`; replay and editable readings validation
need no network or key. `python3 scripts/configure_live.py` reproduces this default artifact.
`--live` builds the hosted variant; the Pages workflow tests offline mode first, then enables
the documented Worker endpoint for publishing. See [deployment and tests](DEPLOY.md).

**Source:** https://github.com/MitchelTighe/signaldesk (MIT). Setup and test instructions are in the [README](README.md).

**Video:** VIDEO_URL_PENDING_OWNER — the owner will upload the public video and supply its YouTube URL.

SignalDesk proposes tape-library runbook steps, checks them against telemetry, and hands unsupported or uncertain cases to a person. The recorded route scored 53 correct of 54 same-author incidents, with zero unsafe actions; the separate second-author check scored 4/10 versus 8/10 for rules. The route is reconstructed from recorded calls, and the emulated-library captures are not real hardware or a real site. See [runtime evidence](docs/RUNTIME-EVIDENCE.md) and [final validation](docs/FINAL-VALIDATION.md).

[Technology feedback on Nebius Token Factory and NVIDIA Nemotron](FEEDBACK.md) describes the recorded experience and requests. AI tools assisted with code, documentation and synthetic fixture authoring. No production reliability, real-hardware validation, externally validated accuracy, model superiority or measured operator time saving is claimed.

The entrant must complete the organizer's identity, eligibility and terms directly, confirm the Devpost teammate list and submit. Organizer acceptance of replay access has not been confirmed. Nothing has been submitted on the entrant's behalf.
