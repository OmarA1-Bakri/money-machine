# Session 08 Prompt Integrity Review — asset storage r3

**Date:** 2026-10-15
**Prompt:** `prompts/implementation/11_SESSION_08_MERCHANDISING_AND_ASSET_FACTORY.md`
**Verified SHA-256:** `a7a406cecd9c93efdec1045f394b911e614cd79366840e33d5c53d9968f7cd33`
**Scope:** Remediate reviewer r2 on the fixture store. Do not activate Session 08.

The prompt file is not amended. This record is the corrective addendum for the r3 slice.

## Review

**Fidelity:** CONDITIONAL APPROVE. Action 8 still requires versioned paths and cleanup that keeps the current temporary render. r2 left the path grammar and the link-race collision unpinned.

**Safety:** HIGH findings below are amended here. No live transport, no credentials, no `IMPLEMENTATION_STATE.json` edit.

**Gameability:** A key check that another check also raises `storage path` for stays green when deleted. Each shape below has its own error text so deleting that line fails its row and no other row.

## Findings

**R3-01 [HIGH] — Key grammar is fail-open when the UUID, spec, or digest line is deleted.** `temp://not-a-uuid/1/<hex>` and `temp://<pid>/0/<hex>` walk. A full-width spec digit passes `isdigit`.

**R3-02 [HIGH] — `os.link` raising `FileExistsError` after another writer plants different bytes returns success if `refuse_collision` is replaced with a stored return.**

**R3-03 [MEDIUM] — A failed write leaves `.<hex>` in the published directory. Cleanup with a bad keep hash deletes every temporary object. An orphan `.<name>` is skipped, but deleting that filter survives the suite.**

## Addendum

1. Refuse a leading slash, a backslash, a part count other than three, and a dot segment on their own lines, with their own error text.
2. Refuse a product that is not a lowercase UUID, a spec that is not `[1-9][0-9]*`, and a digest that is not 64 lowercase hex, each on its own line.
3. The directory walk still refuses `.` and `..` when `_key` is bypassed.
4. A link that loses the race to different bytes raises `storage collision` and leaves those bytes in place.
5. A failed write removes the temp name. Cleanup refuses a keep hash that is not 64 lowercase hex before it deletes anything, and it skips a non-hex orphan.
6. Session 08 stays inactive. `current_session` stays 7. `state_revision` stays 64. Exit 78 stays HELD.
