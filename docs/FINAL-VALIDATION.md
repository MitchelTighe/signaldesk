# Current validation — recorded tape desk and editable readings

The judge page in `site/` replays the genuine October 21 Nebius recording. Its October 22 code
preserves reasoning metadata and adds a local-only readings/proposed-step validator. The
remaining `site/showcase/` page is labelled mock transport QA. Nothing in this note establishes
public deployment or submission readiness.

| Verification | Executed evidence and limits |
|---|---|
| Python suite | 186 tests passing in the offline acceptance container on October 22, including independent replay revalidation, routing, forged veto rejection, budgets, fixture integrity generated submission-packet links, frozen second-author inputs, label-free real CLI requests, rejected-draft scoring, and content-free rejection codes/cache validation. Command: `python3 -m unittest discover -s tests -v`. |
| Recorded vendor run | 108 model/case rows over 54 same-author incidents. Route: 53/54 correct, zero unsafe, estimated USD 0.040. It is reconstructed from both models' recorded calls; the hard set shaped the policy. [Runtime reports and failures](RUNTIME-EVIDENCE.md). |
| Second-author vendor check | Ten cases by a fresh AI author blind to product runbooks; 20 completed calls. Corrected route 4/10 versus rules 8/10; quality gates failed. Nine rejected drafts. Original report preserved; scorer regression fixed and offline replay made zero new calls. [Protocol](SECOND-AUTHOR.md) and [full result](RUNTIME-EVIDENCE.md#second-author-check-ten-new-incidents-october-22). |
| Recorded-page browser checks | 81 checks, sandboxed Chromium 140.0.7339.16 / Playwright 1.55.0: reasoning on/off/unknown labels, routing/vetoes, source navigation, exports, no external requests or console errors. [Exact results](screenshots/current/replay-results.json). |
| Editable readings browser checks | 390 checks across 77 scenarios against the actual Python `telemetry_state` and `validate_selection` oracle: eight-family thresholds, decimals/scientific/malformed values, conflicts, exact versus edited steps, reset, unchanged recorded evidence, no storage writes or external traffic. [Exact results](screenshots/current/readings-results.json). |
| Responsive controls | Browser checks at 1280/768/390/320 pixels; no page/panel overflow, minimum 44-pixel form targets at 390/320. [Current screenshots and hashes](GALLERY.md). |
| Package hygiene | October 22 source and freshly extracted standalone export pass the artifact checker, including local links, Python/shell syntax, PNG integrity and static manifest/bundle budget. Limited source/private-path/credential-shape scans are not a history-wide secret-scan certification. |

These browser results came from the actual October 22 acceptance, not a fresh model evaluation.
[CAPTURES.json](screenshots/current/CAPTURES.json) records the exact HTML and image hashes. The
underlying production Python validator, runbook data, earlier genuine reports and recorded replay JSON
remain unchanged. New second-author results are separate; the comparison scorer changed as disclosed above. Source paths for reproducing the checks are
[replay_browser.py](../tests/replay_browser.py) and [readings_browser.py](../tests/readings_browser.py).

[Rejected-draft diagnostic codes and legacy limits](REJECTION-DIAGNOSTICS.md) are tested offline;
they do not recover the discarded model text from earlier runs.

## Limits that still matter

- The local form checks supplied numbers and exact step wording only. It cannot read ticket
  context or apply caveats and never approves or executes a physical action.
- It preserves the Python contract: negative counts are below gates, and one abnormal family
  takes precedence over another invalid reading. It is not full physical-domain validation.
- Same-author fixtures and tuned hard cases are not independent production validation. mhVTL
  is an emulator with injected faults, not physical drive hardware or a real operational site.
- Older axe/contrast/clean-copy reports are retained as historical evidence; they are not fresh
  accessibility, secret-scan or uptime certification for this revision.
- Public repository/Pages access, actual phone/screen-reader use, operator benefit,
  firsthand feedback and Devpost submission remain separate steps.

## Reproduce offline

From the repository root with Python 3.10 or newer:

```sh
python3 -m signaldesk.demo
python3 -m unittest discover -s tests -v
python3 scripts/artifact_check.py
python3 -m signaldesk.replay --report docs/runtime/live-evaluation-20261021-routed-heldout.json --report docs/runtime/live-evaluation-20261021-routed-hard.json --output site-build --require-live
```

Browser scripts require the documented sandbox-capable browser container. Publication and a
complete history/secret review remain governed by [JUDGE-ACCESS.md](JUDGE-ACCESS.md) and
[HOSTING.md](../HOSTING.md).
