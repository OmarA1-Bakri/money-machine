# Session 07 Prompt Integrity Review — Sandbox run, round 7 remediating turn

**Date:** 2026-10-09
**Prompt:** `prompts/implementation/10_SESSION_07_PRODUCT_BUILD_VARIANTS_AND_QA.md`
**Verified SHA-256:** `d52011a6f0b725b16427629dc664cfc9f3432c4b5f71d26ce032d4b6c8ecb39d`
**Workbook authority:** `hands-off-money-machine-full-implementation-workbook.md` appendix row for this prompt
**Scope:** Round-7 code fix on PR #60 tip `8f77434cb48c4bdfaca12821b335ca2a0224eae6`. The prompt file is not amended. This is a remediating turn of the existing Session 07 sandbox-run slice, not a new session.

## 1. Prompt authenticity

**Status:** VERIFIED against the 2026-10-07 record. The extracted file SHA-256 still equals the workbook appendix value.

## 2. Three-dimensional review

The 2026-10-07 addendum remains in force. This turn adds no new session-prompt findings. Reviewer FAIL 5465945944 is a review of the work, not of the prompt.

**Fidelity:** CONDITIONAL APPROVE. Same F-01 as 2026-10-07: do not run a live sandbox build.

**Safety:** CONDITIONAL APPROVE. Same S-01/S-02: fixtures only, sockets blocked, no live Notion, no Etsy, no `--execute` against a live host, no token, Exit 78 stays HELD, STATE `head_sha` / `state_revision` unchanged.

**Gameability:** CONDITIONAL APPROVE. Same G-01 plus sweep-honesty: publish only measured mutation numbers with the pinned command and basetemp outside the repo. Label any incomplete sweep PARTIAL. Do not claim a full-table sweep that was not run.

## 3. Corrective addendum (this remediating turn)

1. Keep the 2026-10-07 addendum. Do not mark Session 07 complete. Do not change `state_revision` or `head_sha`. Do not lift Exit 78. Do not open a new PR. Do not merge. Do not run `--execute` against live Notion.
2. Detect procfs by device (`st_dev` vs `/proc`, or `statfs` `PROC_SUPER_MAGIC`) for every existing ancestor, lexical and resolved. A symlink to `/proc/self/root` that `realpath`s to `/` must refuse. Re-check immediately before `os.link` and before every write.
3. Kill the four named survivors with durable tests that fail on the mutant and pass on stock: guard:354 LF1 (symlink to `/proc/self` plus `/root/<dir>`), leftover tmp symlink (exit 69, no evidence through it), guard:366 SWAP/LF0 (`under_proc('/proc/1/root/x')` is True and does not raise).
4. Refuse a leftover `.ev.json.tmp` that is a symlink, directory, or FIFO before any POST (0 calls).
5. Mask SIGINT around the held-id print so a gap-0 SIGINT burst at POST:2 still prints the ids to stderr.
6. Do as many listed should-fixes and nits as are safe without changing STATE evidence keys or claiming a full mutation sweep.
7. Tests remain fake-client only. Block sockets. Do not call the live Notion host.

## 4. Deferrals

Same as 2026-10-07: live execution, W9, W10, W11, Exit 78. A full 931-row mutation table is not claimed unless this turn actually runs it.
