# Rejected-draft diagnostics

The live provider records a fixed rejection_code when a completed response cannot become a
validated brief. It retains the existing handoff, error metric and zero-action behavior. It does
not save raw model text, exception messages, arbitrary fields or unvalidated prose.

| Code | Meaning |
|---|---|
| response-envelope | Required completion/message/content fields could not be read. |
| unfinished-response | The completion did not end with finish_reason=stop. |
| invalid-json | Content failed bounded JSON parsing, including duplicate keys or nonfinite numbers. |
| draft-schema | Top-level draft object or exact field set is wrong. |
| draft-lists | Step/web-citation lists are malformed or exceed limits. |
| selection-invalid | A runbook/evidence reference failed the existing selection validator. |
| abstention-shape | A null runbook tried to carry a hypothesis, citations or steps. |
| web-citation | A public document was not retrieved. |
| web-family | A retrieved citation belongs to a different runbook family. |
| runbook-content | The hypothesis title or step count does not match the authored runbook. |
| step-citation | Step source, index or exact text failed validation. |
| evidence-support | Cited readings differ from the supporting readings. |
| draft-validation | A structural validation failure has no more specific fixed code. |
| unknown-legacy | A rejected cached result predates diagnostics; its precise cause is unavailable. |

Only these code strings may survive cache replay. A recomputed cache checksum cannot make
arbitrary diagnostic prose acceptable. Codes themselves are local records, not cryptographic
vendor attestations; without the discarded raw draft, a cached category cannot be independently
re-derived. Existing request payloads and cache keys stay unchanged so old recordings still replay.
A telemetry veto is distinct from a malformed draft and receives no rejection code.

The October 22 second-author batch predates this change. Its nine rejected drafts all finished
with stop, but their precise validation causes remain **unknown**. Existing results are not
backfilled with guesses. [Original result and scoring correction](RUNTIME-EVIDENCE.md#second-author-check-ten-new-incidents-october-22).
No fresh vendor call, prompt change, threshold change or case tuning establishes this feature.
Tests exercise the actual provider, evaluator and cache with explicit mock transports; an offline
replay of the real old cache verifies compatibility without credentials or network access.
