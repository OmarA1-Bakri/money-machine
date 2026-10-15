# Session 08 Prompt Integrity Review — PDF Prev r2

**Date:** 2026-10-15
**Prompt:** `prompts/implementation/11_SESSION_08_MERCHANDISING_AND_ASSET_FACTORY.md`
**Verified SHA-256:** `a7a406cecd9c93efdec1045f394b911e614cd79366840e33d5c53d9968f7cd33`
**Scope:** Pin the existing refuse-without-follow rule. Do not activate Session 08.

The prompt file is not amended. This record is the corrective addendum for the r2 slice.

## Review

**Fidelity:** CONDITIONAL APPROVE. The reader already raises `pdf prev` when the decoded trailer key is `Prev`, for a classic trailer and an xref stream. It does not walk the offset.

**Safety:** Following `/Prev` would merge an older revision. This slice does not add that walk. `/XRefStm` stays unread.

**Gameability:** A check only in the classic branch, a check that requires an int, or a search for the raw bytes `/Prev` each stays green on the previous two rows. `/XRefStm` was untested, so a follower would still parse.

## Addendum

1. Keep refusing every decoded `Prev`. Do not follow the offset, cap a chain, or merge revisions.
2. `/Prev` in a classic trailer and in an xref-stream dictionary each raise `pdf prev`.
3. `/Pr#65v` raises on both paths, because the name is decoded before the check.
4. `/Prev null` and `/Prev (x)` raise. The value does not have to be an integer.
5. `/XRefStm` is not opened. When that stream's table redefines `/Pages`, the original pages object is the one read.
6. A single-revision file with no `Prev` parses.
7. Session 08 stays inactive. `current_session` stays 7. `state_revision` stays 64. Exit 78 stays HELD.
