# Session 07 Prompt Integrity Review — Sandbox run, round 8 remediating turn

**Date:** 2026-10-09
**Prompt:** `prompts/implementation/10_SESSION_07_PRODUCT_BUILD_VARIANTS_AND_QA.md`
**Verified SHA-256:** `d52011a6f0b725b16427629dc664cfc9f3432c4b5f71d26ce032d4b6c8ecb39d`
**Workbook authority:** `hands-off-money-machine-full-implementation-workbook.md` appendix row for this prompt
**Scope:** Round-8 code fix on PR #60 tip `e571b8e7b92fcef09f7a76a7a0a98dd26a73b6db`. The prompt file is not amended. This is a remediating turn of the existing Session 07 sandbox-run slice, not a new session.

## 1. Prompt authenticity

**Status:** VERIFIED against the 2026-10-07 record. The extracted file SHA-256 still equals the workbook appendix value.

## 2. Three-dimensional review

The 2026-10-07 addendum remains in force. This turn adds no new session-prompt findings. Reviewer FAIL 5467032904 is a review of the work, not of the prompt.

**Fidelity:** CONDITIONAL APPROVE. Same F-01 as 2026-10-07: do not run a live sandbox build.

**Safety:** CONDITIONAL APPROVE. Same S-01/S-02: fixtures only, sockets blocked, no live Notion, no Etsy, no `--execute` against a live host, no token, Exit 78 stays HELD, STATE `head_sha` / `state_revision` unchanged. Procfs detection must use filesystem type, not `st_dev` vs `/proc`. Tests must monkeypatch `statfs` / mountinfo; do not require a real user namespace.

**Gameability:** CONDITIONAL APPROVE. Same G-01 plus sweep-honesty: publish only measured mutation numbers with the pinned command and basetemp outside the repo. Label any incomplete sweep PARTIAL. Do not claim a full-table sweep that was not run. Do not claim an EQ without a probe. Withdraw the false `_on_procfs`→False and `_tmp_kind` S_ISLNK→False EQ claims.

## 3. Corrective addendum (this remediating turn)

1. Keep the 2026-10-07 addendum. Do not mark Session 07 complete. Do not change `state_revision` or `head_sha`. Do not lift Exit 78. Do not open a new PR. Do not merge. Do not run `--execute` against live Notion.
2. Detect procfs by filesystem type (`statfs` `f_type == PROC_SUPER_MAGIC` `0x9fa0`, or mountinfo fstype `proc`) for every existing ancestor, lexical and resolved, and at each re-check. Do not compare `st_dev` with `/proc`.
3. Add a helper test that `_tmp_kind` returns `"symlink"` for a leftover symlink. Withdraw that EQ claim. Withdraw or kill the `_on_procfs`→False EQ with a bind-mount / second-procfs style test that monkeypatches fstype.
4. Kill the named public survivors with tests that fail on the mutant: relative symlink to `/proc/self/root`, bounded walk on a symlink cycle, ordinary-dir ancestor symlink accepted, dry-run SIGINT after link exits 69, `workspace_id: null`. Cover namespace-dependent survivors via monkeypatched fstype where possible.
5. Set `SIG_IGN` inside `_raise_interrupt` before anything else. Deterministic hook test plus a looped real-signal test.
6. Do as many listed should-fixes and nits as are safe: 69 after creates including LINK ENOENT, dirfd `openat`/`linkat`, dry-run WRITE:1 gap-0, run-plan `|| exit 1`, helper-only survivors documented or tested, FSYNC traceback, leftover-tmp log, pipeline:206 bound, correct probe counts.
7. Tests remain fake-client only. Block sockets. Do not call the live Notion host.

## 4. Deferrals

Same as 2026-10-07: live execution, W9, W10, W11, Exit 78. A full mutation table is not claimed unless this turn actually runs it. A real user-namespace bind-mount is not required in CI; fstype is injected.
