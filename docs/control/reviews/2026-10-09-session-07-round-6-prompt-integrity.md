# Session 07 Prompt Integrity Review — Sandbox run, round 6 remediating turn

**Date:** 2026-10-09
**Prompt:** `prompts/implementation/10_SESSION_07_PRODUCT_BUILD_VARIANTS_AND_QA.md`
**Verified SHA-256:** `d52011a6f0b725b16427629dc664cfc9f3432c4b5f71d26ce032d4b6c8ecb39d`
**Workbook authority:** `hands-off-money-machine-full-implementation-workbook.md` appendix row for this prompt
**Scope:** Round-6 code fix on PR #60 tip `bcf9a36ce9b32f2862171667457a0a1a68595a2a`. The prompt file is not amended. This is a remediating turn of the existing Session 07 sandbox-run slice, not a new session.

## 1. Prompt authenticity

**Status:** VERIFIED against the 2026-10-07 record. The extracted file SHA-256 still equals the workbook appendix value.

## 2. Three-dimensional review

The 2026-10-07 addendum remains in force. This turn adds no new session-prompt findings. The Reviewer FAIL (5465433904) and Verifier FAIL (6073572255) are reviews of the work, not of the prompt.

**Fidelity:** CONDITIONAL APPROVE. Same F-01 as 2026-10-07: do not run a live sandbox build.

**Safety:** CONDITIONAL APPROVE. Same S-01/S-02: fixtures only, sockets blocked, no live Notion, no production workspace, Exit 78 stays HELD, STATE `head_sha` / `state_revision` unchanged.

**Gameability:** CONDITIONAL APPROVE. Same G-01 plus the Reviewer/Verifier sweep-honesty requirement: publish only serially reproduced mutation counts.

## 3. Corrective addendum (this remediating turn)

1. Keep the 2026-10-07 addendum. Do not mark Session 07 complete. Do not change `state_revision` or `head_sha`. Do not lift Exit 78. Do not open a new PR. Do not merge. Do not run `--execute` against live Notion.
2. Fix `under_proc` so leading `//proc/...` and a symlink-to-`/proc` refuse with exit 64 and 0 network.
3. Kill each named behaviour-changing survivor at the public entry (or helper for `:137`) with a durable test that fails on the mutant and passes on stock.
4. Close the gap-0 SIGINT burst that maps EEXIST after an interrupted first write to exit 64 with no file and no ids.
5. Re-run the mutation table honestly after the fixes and publish only reproduced numbers.
6. Tests remain fake-client only. Block sockets. Do not call the live Notion host.

## 4. Deferrals

Same as 2026-10-07: live execution, W9, W10, W11, Exit 78. Round-4 Verifier V-B1–B5 hold on `bcf9a36c` except the new `//proc`/symlink bypass of V-B4 and the `:137` survivor from V-B5, which this turn folds in.
