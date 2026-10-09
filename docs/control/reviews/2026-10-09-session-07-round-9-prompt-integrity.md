# Session 07 Prompt Integrity Review — Sandbox run, round 9 remediating turn

**Date:** 2026-10-09
**Prompt:** `prompts/implementation/10_SESSION_07_PRODUCT_BUILD_VARIANTS_AND_QA.md`
**Verified SHA-256:** `d52011a6f0b725b16427629dc664cfc9f3432c4b5f71d26ce032d4b6c8ecb39d`
**Workbook authority:** `hands-off-money-machine-full-implementation-workbook.md` appendix row for this prompt
**Scope:** Round-9 code fix on PR #60 tip `fc9c01c3a3e86f3c4e09101c0dc8c64ff6559d34`. The prompt file is not amended. This is a remediating turn of the existing Session 07 sandbox-run slice, not a new session.

## 1. Prompt authenticity

**Status:** VERIFIED against the 2026-10-07 record. The extracted file SHA-256 still equals the workbook appendix value.

## 2. Three-dimensional review

The 2026-10-07 addendum remains in force. This turn adds no new session-prompt findings. Reviewer FAIL 5468348253 is a review of the work, not of the prompt.

**Fidelity:** CONDITIONAL APPROVE. Same F-01 as 2026-10-07: do not run a live sandbox build.

**Safety:** CONDITIONAL APPROVE. Same S-01/S-02: fixtures only, sockets blocked, no live Notion, no Etsy, no `--execute` against a live host, no token, Exit 78 stays HELD, STATE `head_sha` / `state_revision` unchanged. Procfs detection is fail-closed when libc/statfs or mountinfo is unavailable. Tests monkeypatch fstype/mountinfo; do not require a real user namespace.

**Gameability:** CONDITIONAL APPROVE. Same G-01 plus sweep-honesty: publish only measured mutation numbers with the pinned command and basetemp outside the repo. Label any incomplete sweep PARTIAL. **Claim no equivalents.** Kill each touched row with a test, or list it as a SURVIVOR with a one-line reason. Withdraw the `_is_proc`→False, walk-limit, and ns:456 EQ claims and the `11/3 EQ` label.

## 3. Corrective addendum (this remediating turn)

1. Keep the 2026-10-07 addendum. Do not mark Session 07 complete. Do not change `state_revision` or `head_sha`. Do not lift Exit 78. Do not open a new PR. Do not merge. Do not run `--execute` against live Notion.
2. Fail closed: if libc or statfs is unavailable, or mountinfo is empty or unreadable, refuse with 64 before any POST. Load libc with `ctypes.CDLL(None)` and cache it. Do not call `find_library` per path. `_fd_on_procfs` uses `fstatfs` on the fd only; never `/proc/self/fd/N`.
3. Decode mountinfo octal escapes (`\040`, `\011`, `\012`, `\134`) before comparing. Test a mount point that contains a space. Keep longest-match so a later short `proc` line does not win.
4. Refuse the literal `/proc` path even when `f_type` is not procfs (tmpfs over `/proc`). Test via monkeypatch.
5. Count unique walk nodes, not pushes, so a relative symlink chain with K≥16 is accepted and a true cycle is refused. Test both.
6. Add a helper-level test for ns:456, or list it as a SURVIVOR.
7. Claim no equivalents. Withdraw the three EQ claims and the `11/3 EQ` label in the PR body, mapping, and control docs.
8. Tests remain fake-client only. Block sockets. Do not call the live Notion host.

## 4. Deferrals

Same as 2026-10-07: live execution, W9, W10, W11, Exit 78. A full mutation table is not claimed unless this turn actually runs it. A real user-namespace bind-mount or a musl image is not required in CI; fstype and libc availability are injected.
