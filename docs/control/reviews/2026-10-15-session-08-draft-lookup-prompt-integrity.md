# Session 08 Prompt Integrity Review — draft lookup

**Date:** 2026-10-15
**Prompt:** `prompts/implementation/11_SESSION_08_MERCHANDISING_AND_ASSET_FACTORY.md`
**Verified SHA-256:** `a7a406cecd9c93efdec1045f394b911e614cd79366840e33d5c53d9968f7cd33`
**Workbook authority:** appendix row for this prompt (5,092 bytes, 236 lines)
**Scope:** Three fixture holes in the merged Etsy draft client. Do not activate Session 08. Do not commission A10 or A11.

The prompt file is not amended. This record is the corrective addendum.

## 1. Prompt authenticity

**Status:** VERIFIED

The extracted file's SHA-256 equals `a7a406cecd9c93efdec1045f394b911e614cd79366840e33d5c53d9968f7cd33`. The prompt stays the unamended source of record.

## 2. Three-dimensional review

Action 9 stops at `CREATE_ETSY_DRAFT` ready. The fixture client is on `build/full-automation` at `b3425319`. `getListingsByShop` defaults `state` to `active`. A GET that omits `state` still reaches the fixture transport. `record()` creates `name.next` with `O_EXCL`, so a leftover from a crash blocks the next record. The page walk compares `count` only with pages it has already read.

Open pulls #63, #68, #78, #79, #80, #81, and #82 stay untouched. This slice edits `draft_client.py` and its unit test.

### Fidelity

**Verdict:** CONDITIONAL APPROVE.

**F-01 [HIGH] — A draft lookup must not inherit the active default**

- **Prompt lines:** 167–181. The chain ends at a ready draft, not an active listing.
- **Authority:** The measured `getListingsByShop` default is `state=active`.
- **Consequence of literal execution:** A GET without `state` is treated as a successful lookup.
- **Amendment:** A GET whose `state` is missing or is not `draft` raises `lookup_state` before the transport.

### Safety and executability

**Verdict:** CONDITIONAL APPROVE.

**S-01 [HIGH] — A leftover `.next` file makes the ledger unwritable**

- **Prompt lines:** 167–181.
- **Consequence of literal execution:** `O_EXCL` on the existing temp name raises, and the fixture retry never records.
- **Amendment:** Unlink that temp name without following a symlink, then create it again with `O_CREAT|O_EXCL|O_NOFOLLOW`.

### Gameability

**Verdict:** CONDITIONAL APPROVE.

**G-01 [HIGH] — A stable count across the walk hides a later insert**

- **Prompt lines:** 184–199. Successor draft creation has to be the same fixture, not a second listing.
- **Cheap fake:** Keep the per-page compare and skip a second read of offset 0. The existing change-between-pages row stays red, and a shop that grows after the short page still posts.
- **Amendment:** After a short page whose `count` matches, read offset 0 again. A different `count` raises `count` and does not post. Deleting that compare fails only the new race row.

## 3. Corrective addendum

1. Prove the prompt hash, then refuse a GET that does not carry `state=draft`.
2. Clear a stale `.next` name with `unlink` before the exclusive create. Do not follow a symlink.
3. Re-read offset 0 after a consistent short page. A changed `count` raises `count` and does not post.
4. Do not edit `IMPLEMENTATION_STATE.json`, `.github/workflows/ci.yml`, or the files of open pulls #63, #68, #78, #79, #80, #81, and #82. Exit 78 stays HELD. Session 08 stays inactive. Do not print the session exit code. No live Etsy call.

## 4. Deferrals

| Finding | Owner | Reason |
|---|---|---|
| `file:` allow, sendBeacon, raster text | Operator park | W6 integrity already parked them |
| Uppercase hosts, spelled-email gaps, further host defangs | Open pulls #79, #81, #82 | Those files are owned |
| Live S3, `updateListing`, publish | Operator hold | Live provider transport |
| Commission A10 and A11 | Action 11 | Operator hold |
| Session exit code and Exit 78 | Session exit | Operator hold |

## 5. Final verdict

**CONDITIONAL APPROVE.** Critical and high findings are resolved by the numbered addendum above. The three fixture fixes may start. The prompt file stays unamended.
