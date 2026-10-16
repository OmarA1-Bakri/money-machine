# Session 08 Prompt Integrity Review — foreign duplicate markers

**Date:** 2026-10-16
**Prompt:** `prompts/implementation/11_SESSION_08_MERCHANDISING_AND_ASSET_FACTORY.md`
**Verified SHA-256:** `a7a406cecd9c93efdec1045f394b911e614cd79366840e33d5c53d9968f7cd33`
**Scope:** Fixture-only. A foreign shop or description row with two `mm-draft` lines must not halt draft creation. A row that carries our marker twice still refuses. The dead `token.casefold()` in `_outside_curated` is removed. Do not activate Session 08. Do not commission A10, A11, or A13. Do not lift Exit 78.

The prompt file is not amended. This record is the corrective addendum.

## 1. Prompt authenticity

**Status:** VERIFIED.

The extracted file's SHA-256 equals `a7a406cecd9c93efdec1045f394b911e614cd79366840e33d5c53d9968f7cd33`. The prompt stays the unamended source of record.

## 2. Three-dimensional review

### Fidelity

**Verdict:** CONDITIONAL APPROVE.

**F-01 [HIGH] — Two marker lines refuse a foreign row**

- **Prompt lines:** Action 9, draft lookup. The description carries one exact `mm-draft` line. A retry adopts that line.
- **Authority:** #99 raises `duplicate_marker` from `_line_marker` whenever a description has two `mm-draft:` lines. The raise runs before the line is compared with our marker. A listing hashed for another shop, or another description, is not our draft.
- **Consequence:** One foreign row with two marker lines refuses `create_draft` and posts nothing, including when our own single-marker row is on a later page row.
- **Amendment:** A row whose `mm-draft:` lines do not include our marker is not adopted. The walk continues. Our single exact line is still adopted. A row that includes our marker and a second `mm-draft:` line still raises `duplicate_marker` and posts nothing.

**F-02 [HIGH] — `token.casefold()` in `_outside_curated` is unused**

- **Prompt lines:** Action 5 and Action 6, the spaced-host rules.
- **Authority:** `_outside_curated` returns only when `token.islower()` is true. The candidate regex is ASCII. For those tokens `casefold()` equals the token. `x . CO today` stays prose because it is not lowercase. Using the fold by dropping `islower` would undo that form.
- **Amendment:** Compare `token` itself. Do not change the one-letter com rule's breadth or case handling. Screenshot text still allows `x dot com`. The bare end-of-text host stays as it is.

### Safety and executability

**Verdict:** CONDITIONAL APPROVE.

**S-01 [HIGH] — This slice stays off the held pulls and the state file**

- **Authority:** #63 and #68 are operator holds. Session 08 is not activated. Exit 78 stays HELD. `current_session` stays 7.
- **Amendment:** Edit the draft client, the defang normalizer, the draft-client tests, this addendum, and the implementation log. Do not edit `IMPLEMENTATION_STATE.json`. Do not push `build/full-automation`. Do not force-push, rebase, or merge. If that base moves, merge it with a normal merge commit. Do not touch pulls #63 or #68.

**S-02 [HIGH] — No live provider call**

- **Authority:** Fixture transport only.
- **Amendment:** Tests construct fixture rows. No HTTP, no production Notion, no production Etsy.

### Gameability

**Verdict:** CONDITIONAL APPROVE.

**G-01 [HIGH] — A refusal on our own row hides the foreign halt**

- **Prompt lines:** Action 9.
- **Authority:** `test_one_row_with_two_marker_lines_is_not_adopted` only builds rows that contain our marker. Deleting the foreign skip still passes that test.
- **Consequence:** A green duplicate-marker test does not show that a foreign shop row or a foreign description row still posts.
- **Amendment:** One test posts a new draft for a foreign shop hash and a foreign description hash, each with two marker lines. One test adopts our single marker when a foreign two-marker row is listed first. The existing test still refuses our marker plus a second `mm-draft:` line. Measure each mutant on the draft-client file and restore the source.

## 3. Addendum

1. Prove the prompt hash. It stays `a7a406cecd9c93efdec1045f394b911e614cd79366840e33d5c53d9968f7cd33`.
2. Confirm with a failing test that a foreign shop row and a foreign description row, each with two `mm-draft:` lines, raise `duplicate_marker` and post nothing.
3. Skip those rows. Post our draft. Adopt our single exact marker when a foreign two-marker row is listed first.
4. Keep refusing a row that contains our marker and another `mm-draft:` line.
5. Delete `token.casefold()` in `_outside_curated`. Compare `token`. Do not change the one-letter com rule, screenshot `x dot com`, or the bare end-of-text host.
6. Do not activate Session 08. Do not commission A10, A11, or A13. Do not lift Exit 78. Do not edit `IMPLEMENTATION_STATE.json`.
