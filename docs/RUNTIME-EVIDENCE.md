# Runtime evidence: NVIDIA Nemotron on Nebius Token Factory · October 21–22, 2026

These are **genuine vendor runs**, not mocks. Every request went to
`https://api.tokenfactory.nebius.com/v1/chat/completions` with the credential injected into the
child process by a broker; it never appeared in a command, log or file. Each saved row keeps the
model ID, UTC time, elapsed milliseconds, token usage, request fingerprint and the validated brief.
No raw model text is stored. When the validator vetoes a proposal, the row keeps only the proposed
runbook ID, cited reading IDs and step numbers, and the replay builder re-derives the veto from the
fixture and the runbooks.

## Second-author check: ten new incidents, October 22

**The routed policy scored 4/10; rules alone scored 8/10.** This negative result is separate
from the 54 same-author incidents on the recorded judge page. A fresh AI author saw only eight
problem titles and public manuals. Original cases and labels were frozen before reviewer
normalization, label inspection and the one live batch. [Protocol, originals and limits](SECOND-AUTHOR.md).
No cases were removed, retried or tuned after evaluation; thresholds, prompts and routing decisions
stayed fixed.

| Policy | Correct / 10 | Accepted despite handoff/quiet label | Selected model calls | Estimated token cost |
|---|---:|---:|---:|---:|
| Rules only | 8 | 1 | 0 | USD 0 |
| Lightning only | 4 | 0 | 10 | USD 0.00209904 |
| Super only | 4 | 1 | 10 | USD 0.01898220 |
| Routed | 4 | 1 | 12 | USD 0.01519968 |

The single live batch completed **20 vendor calls**, 68,076 observed tokens, estimated
**USD 0.02108124**, inside a USD 0.50 reservation ceiling. The evaluation completed but failed its
quality gates. The route is reconstructed from those two-model recordings; its 12 selected calls
are not another live cascade. Four cases use zero-call pre-triage and six escalate to Super.
Lightning explicitly disables thinking; Super uses the existing provider-default reasoning path.
No internal reasoning state was independently observed. Rates were rechecked against public
model metadata on October 22; costs remain estimates, not billed amounts or a balance reading.

Lightning had **five rejected drafts** and Super **four**. All nine completions ended with
finish_reason=stop, rather than a length limit. The exact schema, citation or step failure is
**unknown**: rejected raw model text was not retained. B02 exposes a coverage gap: its medium-error
sense observations are retained, but cannot honestly be converted into unobserved TapeAlert bits.
The author expects a media workflow; the product pre-triages it to handoff. On B06, an interrupted
LTFS write with uncertain copies, the author asks for handoff but Super and the route accept the
LTFS workflow. These are synthetic-label disagreements, not observed physical harm. No actions
were executed. The report's unsafe_accepts field counts acceptance against a null author label;
it is not a calibrated safety measure.

**Scoring correction:** the immutable [original report](runtime/live-evaluation-20261022-second-author.json)
has a routing-summary bug: Lightning's comparison says 5/10 while its canonical metrics correctly
say 4/10. A rejected empty draft was counted as a correct handoff. The
[offline erratum](runtime/second-author-scoring-20261022.json) preserves both comparisons and the
original report hash. The corrected scorer excludes rejected drafts from correct answers, keeps
valid zero-call pre-triage answers, and leaves all routing decisions unchanged. A real cache-only
CLI replay confirmed the correction with 20 cache hits and **zero new API calls**.

This small second-AI-author set is not a human/operator or production validation. Reviewer
normalization is another limitation. It provides evidence against generalizing the earlier
53/54 tuned/same-author result; the two sets are not pooled into a headline score.

## The recorded run behind the judge page

Two commands, one budget each (the guard caps a run at 100 calls), 21:20–21:37 UTC:

```sh
# 14 hard adversarial incidents, then the 40 frozen held-out incidents
sh scripts/signaldesk_live_eval.sh --split hard    --no-thinking --reasoning-for nvidia/nemotron-3-super-120b-a12b --max-output-tokens 2048 --max-calls 28
sh scripts/signaldesk_live_eval.sh --split heldout --no-thinking --reasoning-for nvidia/nemotron-3-super-120b-a12b --max-output-tokens 2048 --max-calls 80
```

Lightning ran with reasoning **off**; Super ran with reasoning **on**. Both models were called on
every incident, so each single model, the route and a rules-only baseline can be compared on the
same rows. Reports: [held-out](runtime/live-evaluation-20261021-routed-heldout.json) ·
[hard](runtime/live-evaluation-20261021-routed-hard.json). Rebuild the judge page offline:

```sh
python3 -m signaldesk.replay --report docs/runtime/live-evaluation-20261021-routed-heldout.json \
  --report docs/runtime/live-evaluation-20261021-routed-hard.json --output site-build --require-live
```

### Four ways of deciding, same 54 incidents

| Policy | Held-out 40 | Hard 14 | Unsafe actions | Model calls | Recorded cost |
|---|---:|---:|---:|---:|---:|
| Rules only (reads the readings, never the text) | 40 | 12 | **2** | 0 | USD 0 |
| Nemotron 3.5 Lightning only (reasoning off) | 39 | 11 | **2** | 54 | USD 0.011 |
| Nemotron 3 Super only (reasoning on) | 38 | 14 | 0 | 54 | USD 0.091 |
| **SignalDesk route** | **39** | **14** | **0** | 56 | **USD 0.040** |

"Unsafe" means the policy told the operator to act where the right answer is to stop: X02 (the
cleaning flag came back after two cleanings today) and X03 (the cleaning cartridge load had just
failed with a changer Hardware Error 04/03). Rules cannot read that context. Lightning, and Super
with reasoning off, proposed cleaning anyway (both exploratory runs below). Only Super with reasoning
on applied the runbook caveat.

**The route** ([routing.py](../signaldesk/routing.py), policy v2): the validator pre-triages
conflicting, missing, invalid and all-normal telemetry with no model call (15 of 54 incidents,
USD 0). Lightning drafts the rest. Super, with reasoning, reads it again when Lightning abstains, is
vetoed, has its draft rejected, or proposes a runbook that physically moves media (cleaning,
inventory rescan, moving a cartridge to a second drive): 17 escalations. Lightning alone answered
22. The route's cost is summed from the recorded calls; it is not a separate cascade run.

**Its one miss** is H08 (a supported cleaning case): it escalated because cleaning is physical,
and Super's draft was rejected by the validator (rejected drafts keep no model text, so the exact
reason is not stored). The result was a
handoff, which is safe but wrong.

### Proposed, backed, vetoed

| Model | Runbooks proposed | Backed by the readings | Vetoed by the validator | Drafts rejected (schema/citation) |
|---|---:|---:|---:|---:|
| Lightning, reasoning off | 48 | 37 | **11** (H34, H35, H37, H39, H40, X04, X06, X07, X08, X10, X11) | 1 |
| Super, reasoning on | 36 | 35 | **1** (H39) | 2 |

The headline veto is **X06**: the operator insists the heads are dirty; the readings show the
cartridge's media flag and no cleaning flag. Lightning followed the ticket text and proposed
cleaning; the validator vetoed it; Super read the telemetry and the validator backed "Suspect
cartridge". On the real **H35** capture (library says loaded, drive says no medium, LTFS cannot
mount) Lightning proposed an inventory fix and was vetoed; the route does not ask a model at all.

### Latency and tokens

| Model | p50 | p95 | Tokens in / out | Cost |
|---|---:|---:|---:|---:|
| Lightning, reasoning off | 7.1 s | 32.5 s | 138,119 / 10,452 | USD 0.011 |
| Super, reasoning on | 8.8 s | 16.9 s | 138,119 / 55,318 | USD 0.091 |

Latency on the service varied a lot this evening: the same Lightning configuration had a p50 of
1.2 s in the 17:06 UTC run and 4.5 s in the 21:20 run. We therefore claim **cost**, not speed, for
the route; the per-incident latency of each call is shown on the judge page. Super's extra output
tokens are its reasoning, which is what it spends to apply a caveat.

## How the route was chosen (and what is tuned)

1. **21:15 UTC, hard split, first prompt, reasoning off for both** ([report](runtime/live-evaluation-20261021-hard-v1prompt.json)):
   Lightning 11/14, Super 12/14. Both proposed cleaning on X02 and X03.
2. **21:17 UTC, revised prompt (explicit decision order), reasoning off** ([report](runtime/live-evaluation-20261021-hard-v2prompt-nothink.json)):
   identical decisions. Prompt wording alone did not fix the caveat cases.
3. **21:18 UTC, Super with reasoning on, hard split only** ([report](runtime/live-evaluation-20261021-hard-super-reasoning-probe.json)):
   14/14, no vetoes needed. This is where the routing policy came from.
4. **21:20–21:37 UTC, the recorded run above.** The 40 held-out cases were the check that the
   revised prompt and Super-with-reasoning did not break the easy set (route 39/40).

So the hard split is no longer a blind test for the route: the prompt revision and the policy
were chosen after seeing it. The held-out 40 were not used for any choice. Both sets are written
by the same author as the runbooks.

## Earlier on October 21 (superseded)

The 17:06 UTC run (first prompt, reasoning off, 80 calls, about USD 0.04) scored Super 40/40 and
Lightning 40/40; it is kept as [live-evaluation-20261021-tape-nothink.json](runtime/live-evaluation-20261021-tape-nothink.json).
It did not store vetoed proposals, so the veto could not be shown on screen. A rules-only
baseline also scores 40/40 on that set, which is why the hard split was written.

The lesson from October 20 still holds: with reasoning on and a 1,600-token cap, Lightning spent
the whole budget on hidden reasoning (`finish_reason=length`, empty content), so Lightning always
runs with `--no-thinking`. Super with reasoning on fit within 2,048 output tokens on all 108 calls.

## Spend

| Run | Calls | Recorded cost |
|---|---:|---:|
| 17:06 held-out (superseded) | 80 | about USD 0.04 |
| 21:15 hard, first prompt | 28 | USD 0.015 |
| 21:17 hard, revised prompt | 28 | USD 0.015 |
| 21:18 hard, Super reasoning probe | 14 | USD 0.022 |
| 21:20 hard, recorded | 28 | USD 0.024 |
| 21:23 held-out, recorded | 80 | USD 0.078 |

Day total about **USD 0.20** against the USD 2 cap, at the public rate snapshot in
[pricing.json](../signaldesk/pricing.json). These are token estimates, not an invoice.
Temperature 0 is not guaranteed repeatable on this service.
