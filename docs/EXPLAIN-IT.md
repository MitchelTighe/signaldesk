# SignalDesk in one page

**One sentence:** when a tape drive or library misbehaves, SignalDesk tells the on-call person what
to do now, or to stop and hand it off, and a plain Python validator can veto the AI before a
cartridge ever moves.

## What a user sees

1. **What to do now** at the top: "Do this" with up to three exact runbook steps, "Hand off to a
   person", or "No incident". It names which model answered, how long it took and what it cost.
2. **Validator veto**, when there is one: "Lightning proposed *Drive requests cleaning*. Vetoed:
   the readings do not back it."
3. **Why**, one click down: every reading, its gate, abnormal or normal, and the checks the
   validator ran.
4. **Model trace**: Lightning and Super side by side on this incident, with latency, tokens and cost.
5. **Export incident note**: a Markdown note to paste into a ticket. Every page shows **0 actions executed**.

## The four judging criteria, and our honest answer

| Criterion | What we built | What we do not claim |
|---|---|---|
| **Technological implementation** | NVIDIA Nemotron on Nebius Token Factory with a reason for each model: Lightning (reasoning off) drafts most incidents cheaply; Super (reasoning on) is the second reader before any physical action and after any veto. A deterministic pre-triage skips the model when no model could change the answer. On 54 recorded incidents the route made 53 correct decisions and 0 unsafe ones for USD 0.040, against USD 0.091 for Super alone. The validator vetoed 12 of 84 proposed runbooks. Budget guard, offline replay, automated Python tests. | Latency was noisy during the recorded run, so no speed claim. The route is computed from recorded calls of both models, not a separate cascade run. |
| **Design** | Action first, evidence one click down, a distinct "No incident" state for a quiet library, a visible veto, an exportable note, a 30-second walkthrough, light and dark, phone width, zero axe violations in automated checks. | No study with real operators. |
| **Potential impact** | For small archive, HPC, research and media teams that run LTO libraries without a vendor engineer on site. LTO shipped a record 176.5 EB of (compressed) tape capacity in 2024, up 15.4% ([LTO Program figures as reported by Blocks and Files](https://www.blocksandfiles.com/ai-ml/2025/07/23/lto-tape-market-rebounds-in-2024-with-1765-eb-shipped/1601737)). A wrong action costs real money: IBM says to clean a drive only when it asks, never on a schedule, and a cleaning cartridge is rated for 50 cleanings ([IBM docs](https://www.ibm.com/docs/POWER7/p7hdt/fcEU11cleaningdrive.htm)); a repeated failed robot move or a forced unload can strand or damage a cartridge. | No measured time saving and no production use. |
| **Quality of the idea** | **Evidence-gated AI for physical infrastructure.** The model proposes; the telemetry decides; a person acts. Two keys: the validator can stop any claim the readings do not back, and a stronger model can stop an action the readings back but the context forbids. Neither can start an action alone. | Same-author test incidents; the hard set shaped the routing policy (see below). |

## New evidence that limits the headline

On October 22, ten frozen incidents from a second AI author scored **4/10 for the route versus
8/10 for rules alone**, with nine rejected model drafts. The author saw public manuals and eight
titles, not our runbooks. This is still synthetic evidence with reviewer normalization, not an
operator study. A scoring bug was fixed offline without new calls or changed routing decisions.
[Full negative result, original report and erratum](RUNTIME-EVIDENCE.md#second-author-check-ten-new-incidents-october-22).
The earlier 53/54 result describes the recorded same-author page only.
The hosted live variant disables reasoning for both models; those recorded accuracy figures
do not measure it. The checked-in build stays offline. See [DEPLOY.md](../DEPLOY.md).

## Why it is not "just another evidence viewer"

1. **Physical infrastructure.** A wrong answer wastes a cleaning cartridge, wears drive heads or
   repeats a failed robot move. That is why the default is to stop.
2. **The validator vetoes; it does not just display.** Plain Python, outside the model: the reading
   must belong to the incident, meet the runbook gate, and only one failure family may be abnormal.
   Every step must match the authored runbook word for word.
3. **Real telemetry from a real (virtual) tape library.** Hero readings are `sg_logs`, `mtx`,
   `sg_turs`, `mt` and LTFS output from mhVTL, an open-source virtual tape library, with faults
   injected on purpose. Raw files and the capture script ship in `fixtures/tape-captures-20261021/`.
4. **Cost-aware routing between two Nemotron models,** with a recorded receipt.

## What we learned that an outsider would not know

- **Rules alone ace the easy test.** A baseline that reads only the numbers scored 40/40 on our
  first test set, the same as both models. So we wrote 14 harder incidents from the mhVTL captures.
- **Neither rules nor a fast model reads context.** On "the cleaning flag came back after two
  cleanings today" and "the cleaning cartridge load just failed with a Hardware Error", rules,
  Lightning and Super with reasoning off all said "clean it". Only Super with reasoning on applied
  the runbook caveat and stopped. That is what the second reader is for.
- **Fast models get talked into things.** When the operator insisted the heads were dirty,
  Lightning followed the ticket text; the readings said media, and the validator vetoed it.
- **A quiet window must say "no incident".** Lightning proposed a runbook on five all-normal
  windows; every one was vetoed.

## The five walkthrough scenes

| Case | What happens | Source |
|---|---|---|
| **H05** do this | TapeAlert flags 20/21 set. Lightning drafts "Drive requests cleaning"; because cleaning moves a cartridge, Super reads it again; the validator backs it. | mhVTL capture |
| **X06** veto | Operator says clean it; telemetry shows the media flag. Lightning proposes cleaning and is vetoed; Super's "Suspect cartridge" is backed. | Hand-written |
| **X02** stop | Flags 20/21 set again after two cleanings today. Super applies the caveat: hand off. | mhVTL capture + authored context |
| **H35** conflict | Library says loaded, drive says no medium, LTFS cannot mount. Two families abnormal: hand off without asking a model. | mhVTL capture |
| **X01** quiet | All TapeAlert flags 0, inventory matches. No incident. | mhVTL capture |

## Real versus synthetic

| Item | Status |
|---|---|
| Hero readings | Captured from mhVTL 1.8 (STK L700 + IBM LTO-8 emulation) and sanitized. Real tool output; injected faults; not real hardware or a real site. |
| Recorded-page incidents | 40 held-out + 14 hard, written by the same author as the runbooks. The hard set shaped the prompt and the routing policy; the held-out set did not. |
| Runbooks | Eight, authored for this project; each step cites public sg3_utils, mtx, mt, lsscsi, T10 or LTFS docs. |
| Nemotron results | Genuine Nebius Token Factory calls; day total about USD 0.20. |

## Likely judge questions

1. **What does the model add over rules?** Rules cannot read the ticket. On the two incidents where
   the context says stop, rules (and fast models) say act. The route's second reader caught both.
2. **Why two models?** Lightning is about eight times cheaper per incident; Super with reasoning is
   the one that applied caveats. The route spends Super only where an action is physical or something
   looked wrong: 17 of 54 incidents.
3. **Why not let it act?** Nothing in SignalDesk can send a command to a library. A person acts.
4. **What if the evidence is thin?** No hypothesis: "Hand off" for missing or conflicting
   readings, "No incident" for an all-normal window.
5. **How would it plug into a real library?** A read-only collector turns `sg_logs`, `sg_turs` and
   `mtx status` output into readings. Not built yet; next step, with scenarios written by real tape operators.
