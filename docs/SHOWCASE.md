# Synthetic judge showcase

The default page contains **58 tape-library incidents × two mock model slots = 116
records**. The forty held-out inputs are reused unchanged;
eighteen additional synthetic library A scenarios are presentation-only. No model
generated these responses. The timestamp is a fixed synthetic clock; latency
and token counts are zero. This expanded set is **not an evaluation benchmark**.
The genuine evaluator still uses its original forty frozen inputs.

From the standalone entry:

```sh
python3 scripts/generate_demo.py
python3 scripts/generate_demo.py --check
python3 -m signaldesk.demo
```

The generator has no random seed, clock dependency, network or credential access.
It writes `fixtures/showcase.json`, `fixtures/walkthrough.json` and the four
`site/` files. It exercises the real deterministic validator, including rejection
of an invented source. Every response has zero executed actions. Error and
not-run records remain outside successful abstention counts.

| Select / action | What to inspect |
|---|---|
| Start 28-second walkthrough | H05 support → H35 conflict → H36 missing data → second requested model |
| H05, Inspect source, numbered source link | TapeAlert cleaning flag, exact threshold, cited public steps and caveat |
| D01–D08 | Eight tape families; library A tickets with an sg_logs/mtx snapshot and an irrelevant mount count |
| D09 → D10 | Exactly one cleaning flag supports RB-CLEAN; zero flags do not |
| D11 → D12 | A negative flag count is invalid; string `"1"` is not numeric evidence |
| D13 → D14 | Empty TapeAlert attachment; cleaning and hardware flags together |
| D15 | Unicode title and long wrapping text; inspect at 320px and 200% zoom |
| D16 | Simulated transport error; no completed response or fabricated usage |
| D17 | Invented-source rejection; human handoff and zero steps |
| D18 | Simulated budget stop; not requested, not a successful abstention |
| Errors / Not run filter | Distinct degraded states and honest denominators |
| Search `D15`, then `no-such-ticket` | Matching incident and announced empty result; clear to recover |
| Previous / Next; model switch | Native controls preserve selected incident where possible |
| Download replay evidence | Actual JSON download; 116 records with synthetic/mock disclosures |
| Light theme / Dark theme | Both color schemes; theme starts from browser preference |
| Tab, Enter, `/`, skip link | Keyboard access, search shortcut, pause/resume and focus return |

`fixtures/walkthrough.json` is the machine-readable contract for tests and capture.
The checked-in fixture file is compared to generator output. Tests resolve every
listed scenario for both models and confirm all eight source families. Browser
tests exercise the actual controls and source anchors.

The live provider rejects every added D-series input. The replay builder rejects
`--require-live` on this showcase and refuses live provenance in its rows. After
genuine evaluation, build `site/` from the real held-out report as documented in
[NVIDIA-PATH.md](NVIDIA-PATH.md); do not relabel this generated dataset. Preserve
the showcase in a separate review copy if it is needed for future rehearsals.
