# Judge rubric scorecard · October 21, 2026

A skeptical-judge score of SignalDesk against the four official criteria of the Nebius × NVIDIA
Global AI Hackathon, before and after the October 21 evening fixes. Scores are 1–10 and are an
internal editorial estimate, not an organizer score or a prediction.

## Before (commit 07a30ad3, the tape pivot)

| Criterion | Score | Three biggest weaknesses |
|---|---:|---|
| Technological implementation | **5** | 1. A rules-only baseline that reads no text and picks the single abnormal family also scores 40/40 on the held-out set, so Nemotron looks decorative. 2. Two models are called but nothing says why each one is used; latency and cost exist only as run totals. 3. The judge site in `site/` is the **mock** showcase ("LOCAL MOCK PREVIEW"), and the model's vetoed proposal is not stored, so the headline veto on H35 cannot be seen on screen. |
| Design | **5** | 1. Evidence first, action last: the operator has to scroll past the ticket and the readings to learn what to do. 2. No output a tape operator could hand on (no incident note or export). 3. A healthy window and a conflicting one both render as the same amber "Pause"; there is no "no incident" state. |
| Potential impact | **4** | 1. The audience is "small storage teams", with no scale facts or sources. 2. The cost of a wrong action (a needless cleaning, a repeated failed robot move) is never stated. 3. No evidence that anyone but the author has used it. |
| Quality of the idea | **5** | 1. Reads as "another evidence viewer", a common theme among sample projects. 2. The 40/40 result is trivially easy and the entry admits it without a harder test. 3. The non-obvious part (a deterministic validator that can veto the model on physical infrastructure) is buried in a mechanics section. |
| **Total** | **19/40** | |

## What changed

Each fix targets a named weakness above. Numbers are from genuine Nebius Token Factory calls
([runtime evidence](RUNTIME-EVIDENCE.md)).

- **Harder test, honest baseline (T, Q).** 14 adversarial incidents built from the mhVTL captures
  ([hard.json](../signaldesk/hard.json)): quiet windows, runbook caveats, injection both ways,
  operator text that contradicts the telemetry, a just-below-gate reading, conflicts, thin changer
  telemetry. A rules-only baseline is now reported next to the models: 40/40 held-out, 12/14 hard.
- **A reason for each model (T).** Lightning with reasoning off drafts; Super with reasoning on is
  the second reader before any physical action and after any veto or abstention; the validator
  answers conflict, missing and all-normal telemetry with no model call. Measured on the same 108
  recorded drafts: route 53/54 correct, 0 unsafe, USD 0.040; Super only 52/54, USD 0.091; Lightning
  only 50/54 with 2 unsafe; rules only 52/54 with 2 unsafe. Per-incident latency, tokens and cost
  are on the page.
- **The veto as the headline (T, Q).** Vetoed proposals are now stored (IDs and step numbers only)
  and re-derived on replay; a forged veto is refused by the tests. Proposed / backed / vetoed:
  84 / 72 / 12. X06 shows Lightning following an operator's "clean it" while the readings point at
  the cartridge, the veto, and Super's backed answer.
- **A product flow (D).** Action first ("Do this", "Hand off to a person", "No incident"), the
  answering model, latency and cost on the action, the veto box, evidence and checks one click down,
  a model trace, an exportable Markdown incident note, a policy receipt with cost bars, and a
  30-second, five-scene walkthrough. The live recorded run is now the page in `site/` (the mock is in
  `site/showcase/`); phones show the action before the queue. Zero axe violations in 42 automated audits.
- **Audience and stakes (I).** Named: small archive, HPC, research and media teams running LTO
  without a vendor engineer. Sourced: 176.5 EB of LTO capacity shipped in 2024 (+15.4%); IBM's
  "clean only when the drive requests", 50-clean cartridge rating. The cost of a wrong action is in
  the first screen of the README.
- **The idea, framed (Q).** "Evidence-gated AI for physical infrastructure": the model proposes, the
  telemetry decides, a person acts; two keys, neither of which can start an action alone. The
  README opens with how this differs from evidence viewers.
- **Ready to be a live link.** GitHub Pages workflow (pinned SHAs, manual run), subpath rehearsal,
  README demo link, owner flip checklist. A fresh agent with only the export ran a first-run test
  (see below).

## After (this commit)

| Criterion | Before | After | Three biggest remaining weaknesses |
|---|---:|---:|---|
| Technological implementation | 5 | **7** | 1. The prompt revision and routing policy were chosen after seeing the 14-case hard split; only the 40 held-out cases were untouched, and every case is same-author. 2. The models' measured advantage over rules rests on two caveat incidents (X02, X03). 3. Service latency was noisy (Lightning p50 7.1 s tonight vs 1.2 s this afternoon), so the route shows a cost win but no speed win; escalation latency adds. |
| Design | 5 | **7** | 1. It is a replay: a judge cannot type their own readings. 2. Below the action, the page is still long and dense on a phone. 3. No study with a real tape operator. |
| Potential impact | 4 | **6** | 1. There is no read-only collector yet, so it cannot run against a real library today. 2. No operator has used it. 3. The scale fact is market capacity, not the number of small teams who would use it. |
| Quality of the idea | 5 | **7** | 1. "A verifier that checks the model" exists elsewhere; the physical-action second reader is the distinct part and needs more than two cases to prove. 2. Eight authored runbook families bound what it can recommend. 3. mhVTL is an emulator: injected faults, not field failures. |
| **Total** | **19/40** | **27/40** | |

## Stranger first-run test

A fresh agent that had never seen the project got only the extracted public export, read the
README as a busy judge would, ran the three commands (all passed, 171 tests) and drove the page in
Chromium. Findings: what it does was clear in about 10 s and who it is for in about 20 s; the
"not just a viewer" point landed at about 45 s, properly at walkthrough scene 2. **Wow within 30 s:**
the X06 veto box. **Aha within 2 min:** the four-policy receipt. Its blunt objections, and what we
did: "rules-only nearly wins, nothing answers what the model adds" (a one-paragraph answer now sits
in the README results and above the receipt: X02/X03); "the live link is pending" (the README now
leads with `site/index.html`); H35 printed a veto although the route calls no model (now labelled
"recorded for comparison"); the quiet library's trace said "handoff kept" (now "no incident");
the README miscounted the demo output, used "Tonight" and linked internal-sounding docs (fixed); an
unlabelled pixel strip in the hero (removed); "Next scene" stayed visible after the walkthrough
ended (hidden). Not changed: the walkthrough still scrolls the hero away, on purpose, so the
answer card stays on screen. An agent is not a human stranger; a person should repeat this.

## What would move the scores next

1. **Let judges try their own readings (D, T):** a "try the validator" panel that runs the
   deterministic pre-triage and gates in the browser with no model (honestly labelled), so the
   no-incident / conflict / veto behaviour is testable live.
2. **A read-only collector for mhVTL (I, T):** turn raw `sg_logs`/`mtx`/`sg_turs` output into readings
   so the hero cases run end to end from the raw capture files that already ship.
3. **Incidents written by someone else (T, Q):** ten caveat-style incidents from a tape operator who
   has not seen the runbooks, run once, reported as is.
