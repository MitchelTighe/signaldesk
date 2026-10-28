# Ten incidents from a second AI author

On October 22 a fresh AI instance wrote B01–B10 using only eight problem titles and primary
public tape manuals. She did not see the product runbooks, thresholds, existing incidents or
model results. The [original cases](../fixtures/second-author-20261022/CASES.json),
[separate labels](../fixtures/second-author-20261022/LABELS.json) and
[source notes](../fixtures/second-author-20261022/SOURCE-NOTES.md) were frozen together before
normalization or evaluation. [FREEZE.json](../fixtures/second-author-20261022/FREEZE.json) records
all three hashes. This is second-author synthetic evidence, not independent human/field validation.

## Result

The one live batch completed 20 calls: Lightning 4/10, Super 4/10, routed 4/10 and rules-only
8/10. Nine drafts were rejected. Quality gates failed. Estimated total token cost was
USD 0.02108124. [Full result and scoring correction](RUNTIME-EVIDENCE.md#second-author-check-ten-new-incidents-october-22).
The original report is preserved; the scorer correction and cache-only replay made no new calls
and changed no routing decisions. No post-result case, label, threshold or prompt tuning occurred.

## Input conversion and limits

The reviewer mapped explicit quantities into the existing input schema before opening labels.
[NORMALIZATION.json](../fixtures/second-author-20261022/NORMALIZATION.json) records every mapping.
All ten cases and their exact titles/text remain; original observations remain available.
Unsupported observations are retained with observed_* metric names, rather than converted to
unseen TapeAlert bits or filled with zero. For B05, one barcode has different explicit changer
and application slot locations; its mismatch count is one. Actual elapsed load time, rather than
a configured timeout, supplies the load-wait reading.

Six author labels choose a problem workflow, three ask for a handoff and one describes a quiet
window. For a handoff/quiet disposition the expected runbook decision is null; a diagnosed title
can still exist in a handoff's separate author label. The author's unsafe_to_repeat flag concerns
a particular attempted operation, not every possible diagnostic action or a calibrated safety score.
The case loader sends only id, title, incident text and evidence to the model. Labels, disposition,
kind and interpretation metadata remain out of the API payload. Arbitrarily edited cases remain refused.

These labels are the second author's judgments, not organizer or operator certification. The
reviewer's format conversion means this is author blindness to the product, not a fully blinded
end-to-end study. The product's existing thresholds, runbooks, validator and routing policy stay
fixed; a failure on an unsupported observation is retained as a coverage limit.

## Reproduce through the existing guarded path

```sh
# Offline plumbing only; fake local responses are never vendor-quality evidence.
python3 -m signaldesk.live_eval --split second-author --dry-run --no-thinking --reasoning-for nvidia/nemotron-3-super-120b-a12b --max-calls 20 --max-usd 0.5 --output runs/second-author-report.json --cache runs/second-author-cache

# Maintainer only, with NEBIUS_API_KEY exported in the environment; never put its value in a command.
sh scripts/signaldesk_live_eval.sh --split second-author --no-thinking --reasoning-for nvidia/nemotron-3-super-120b-a12b --max-output-tokens 2048 --max-calls 20 --max-usd 0.5 --output runs/second-author-report.json --cache runs/second-author-cache
```

Keep new outputs/cache paths; no automatic retry or case removal. Every completion,
error, veto and not-run row belongs in the result. The budget is an estimated reservation bound,
not an account balance or invoice. Original held-out/hard datasets and recorded page stay unchanged.
