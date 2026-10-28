# NVIDIA adapter handoff

> **October 20, 2026 update:** genuine NVIDIA-on-Nebius runs are now recorded. See [RUNTIME-EVIDENCE.md](RUNTIME-EVIDENCE.md). Statements below that no live call had been made describe the record as of the date this document was written.

The current guarded drafting/evaluation path and one-command lead instructions are in **[NVIDIA-PATH.md](NVIDIA-PATH.md)**. It reads `NEBIUS_API_KEY` only from the broker-populated environment, uses the confirmed Oct 18 IDs, reserves calls/tokens/cost before each request, validates model-drafted hypotheses and exact cited steps outside the model, and caches sanitized results for offline judge replay.

The original `signaldesk.providers.NebiusProvider` remains only for injected historical tests. Its real network path is retired. The old FD-based CLI is now refused **before any descriptor or credential read**; all executable live entry points use the broker-injected environment variable. Use `scripts/signaldesk_live_eval.sh` for formal evaluation, or the explicitly authorized guarded rehearsal described in the README. The formal evaluator never replaces a failed vendor response with a recording.

No live NVIDIA or Tavily API call was made by this worker. Existing baseline metrics and screenshots remain offline results. Mock data is never evidence of competition runtime compliance. Actual brokered inference, firsthand feedback, recording and public delivery remain lead/owner steps.
