# Source notes — second blind synthetic author

Read date: 2026-10-22. The browsing tool supplied public page extracts; these were not exhaustive full-document reviews. No product source, product runbook, prior case, test, result, handoff, or repository state was opened for this task. Local access was confined to checking the three exact output names and creating these three files in the assigned output directory.

Primary technical pages actually read:

- https://www.t10.org/lists/asc-num.htm — numeric assignments and relevant excerpts for cleaning, read errors, readiness transitions, hardware fault, resets, and protection. These describe codes, not universal operational thresholds.
- https://raw.githubusercontent.com/doug-gilbert/sg3_utils/master/doc/sg_logs.8 — upstream author manual: LOG SENSE decoding, supported-page behavior, TapeAlert brief output, and cumulative-value selection.
- https://raw.githubusercontent.com/doug-gilbert/sg3_utils/master/doc/sg_turs.8 — upstream author manual: readiness command behavior, repeated checks, absent optional progress, and return-status semantics.
- https://sourceforge.net/p/mtx/code/HEAD/tree/trunk/mtx/mtx.1 — official project manual: changer status, numbering, cartridge identity/location, inventory, and movement semantics.
- https://github.com/LinearTapeFileSystem/ltfs/wiki/ltfs — official project command reference: LTFS mounts, index behavior, and special recovery-related mount options.
- https://github.com/LinearTapeFileSystem/ltfs/wiki/ltfsck — official project command reference: verification, rollback, recovery, and the possible block erasure associated with deep recovery.

Primary navigation or overview pages also read while locating the manuals:

- https://sourceforge.net/p/mtx/code/HEAD/tree/
- https://sourceforge.net/p/mtx/code/HEAD/tree/trunk/
- https://sourceforge.net/p/mtx/code/HEAD/tree/trunk/mtx/
- https://github.com/LinearTapeFileSystem/ltfs
- https://github.com/LinearTapeFileSystem/ltfs/wiki

Unsuccessful retrievals, not used as sources: https://sg.danny.cz/sg/sg_logs.html ; https://sg.danny.cz/sg/sg_turs.html ; corresponding sg_logs.8.html and sg_turs.8.html paths on that host; https://sourceforge.net/p/mtx/code/HEAD/tree/trunk/mtx.1 ; https://raw.githubusercontent.com/LinearTapeFileSystem/ltfs/main/man/ltfs.8 . A web search for working sg manuals returned mixed snippets; secondary search results were not opened or used as technical authority. The upstream author's raw manuals above were the working fallback.

Method and limits:

A fresh second AI author independently invented all ten scenarios, observations, quantities, time windows, and labels. The only product-specific knowledge supplied was the eight permitted problem titles. Manuals informed public command and sense-code semantics; the scenarios are not quotations or reconstructions of published incidents. No claim is made that any chosen timing, count, volume, or action is a hidden product threshold, a manufacturer limit, or a measured field distribution. Missing values are explicit nulls, not assumed zeroes.

The label word runbook means the named problem is sufficiently supported for its ordinary documented workflow. Handoff means the specific facts require a service, recovery, ownership, or evidence decision beyond an ordinary retry, even when a problem title can be identified. Quiet means the observation describes a resolved expected transition without a current actionable incident. Unsafe to repeat refers to repeating the failed or proposed operational attempt under the described conditions, not to repeating a read-only diagnostic query. These judgments are this author's independent choices, not learned product policy.

This is blind AI-authored synthetic material, not independent human review, field validation, equipment certification, or empirical performance evidence. The author did not see model outputs or tune cases to an evaluation score. All ten cases are retained. CASES.json, LABELS.json, and this note are frozen together at initial creation, with no revisions after freeze. Labels remain outside the case input file.
