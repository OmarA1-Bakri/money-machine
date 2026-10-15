# Session 08 Prompt Integrity Review — parked should-fixes

**Date:** 2026-10-15
**Prompt:** `prompts/implementation/11_SESSION_08_MERCHANDISING_AND_ASSET_FACTORY.md`
**Verified SHA-256:** `a7a406cecd9c93efdec1045f394b911e614cd79366840e33d5c53d9968f7cd33`
**Scope:** Carry three parked should-fixes. Do not activate Session 08.

The prompt file is not amended. This record is the corrective addendum for this slice.

## 1. Prompt authenticity

**Status:** VERIFIED

The extracted file's SHA-256 equals `a7a406cecd9c93efdec1045f394b911e614cd79366840e33d5c53d9968f7cd33`. The prompt stays the unamended source of record.

## 2. Three-dimensional review

Action 2 rejects an unsupported claim. Action 8 stores bytes only through the fixture store. The draft lookup walks the fixture transport twice before a post. Open pulls #63, #68, #80, #81, and #82 stay untouched. `defang_normalizer.py` stays untouched. `IMPLEMENTATION_STATE.json` stays untouched. No live HTTP.

### Fidelity

**Verdict:** CONDITIONAL APPROVE.

**F-01 [HIGH] — A closing parenthesis still publishes a count**

- **Prompt lines:** Claim validation, unsupported claim rejection.
- **Authority:** The count-punctuation slice added `(`. `)` was left parked.
- **Consequence:** `(500) reviews` and `(reviews) 500` still merchandise.
- **Amendment:** Both are class claims. Dropping `)` publishes them and leaves `500 (reviews)` refused.

**F-02 [HIGH] — A word-first thousands group is not one count**

- **Prompt lines:** Claim validation.
- **Authority:** `1,000` stays one number. `Reviews: 1,000` was matching only the leading digit, so a fact of `Reviews: 1` covered it.
- **Consequence:** A one-review fact authorizes a one-thousand-review sentence.
- **Amendment:** The word-first review match consumes the thousands commas. `Reviews: 1` does not cover `Reviews: 1,000`. `Reviews: 1,000` covers itself. `1,000` with no count word stays allowed.

**F-03 [HIGH] — The found compare and a description change are unpinned**

- **Prompt lines:** Draft lookup before create.
- **Authority:** Gate #83 r2 parked `found != confirm_found`. A marker can move onto an existing id while the id list stays equal. A description can change while the found id stays equal.
- **Consequence:** Deleting the found compare adopts or posts. A same-id description edit is adopted.
- **Amendment:** Swapping the marker between two existing ids refuses with `count` and does not post. Editing one existing description, marker still on that id, refuses with `count` and does not post. Each compare has its own row.

**F-04 [HIGH] — Two shape anchors and a vanished link still fail open**

- **Prompt lines:** Asset storage, fixture bytes only.
- **Authority:** Gate #78 r3 parked `fullmatch` to `search` on the product id and the digest, and the post-link `EEXIST` read that substitutes empty bytes.
- **Consequence:** `<uuid>x` and a 65-hex digest pass the shape check. An `EEXIST` whose name is then gone returns stored when the payload is empty.
- **Amendment:** `<uuid>x` and 65 hex each raise `storage path`. A vanished link target raises `storage missing` and does not return stored.

### Safety and executability

**Verdict:** CONDITIONAL APPROVE.

**S-01 [HIGH] — These slices share no files with the open host pulls**

- **Prompt lines:** The session touches merchandising, drafts, and storage.
- **Authority:** #80, #81, and #82 own the defang files. #63 and #68 stay operator holds.
- **Consequence:** Editing those files mixes unrelated branches.
- **Amendment:** Edit only claim validation, the draft client, the local store, their tests, this addendum, and the implementation log.

### Gameability

**Verdict:** CONDITIONAL APPROVE.

**G-01 [HIGH] — One row must not save the next guard**

- **Prompt lines:** Each refusal.
- **Authority:** A survivor that another row already kills is not a pin.
- **Consequence:** `Reviews: 1,000` still refuses when the match is one digit. A marker swap still refuses when descriptions are compared as a multiset. A digest of other bytes does not catch a vanished name.
- **Amendment:** Narrowing the word-first digit run fails only the cover row. Deleting the found compare fails only the swap. Deleting the description compare fails only the edit. `search` on the product id fails only `<uuid>x`. `search` on the digest fails only 65 hex. Returning stored after a vanished link fails only the empty vanish row.

## 3. Addendum

1. Prove the prompt hash, then add `)` to the count-separator set. `(500) reviews` and `(reviews) 500` are class claims. `500 (reviews)` stays a class claim when `)` is removed.
2. `Reviews: 1,000` is one count. A fact `Reviews: 1` does not cover that prose. A fact `Reviews: 1,000` does. `1,000` alone stays allowed.
3. Compare `found` and the sorted description texts across the two draft walks. A marker swap between existing ids, and a description edit that keeps the same found id, each raise `count` and do not post.
4. A product segment `<uuid>x` and a 65-hex digest raise `storage path`. After `link` raises `EEXIST`, a missing name raises `storage missing` and does not return a stored object.
5. Session 08 stays inactive. `current_session` stays 7. `state_revision` stays 64. Exit 78 stays HELD. Do not edit `IMPLEMENTATION_STATE.json`, `defang_normalizer.py`, or files owned by #63, #68, #80, #81, or #82.

## 4. What already holds

`.`, `_`, `/`, `-`, `+`, `;`, `,`, `:`, `=`, and `(` already collapse. The sorted id lists are already compared. `fullmatch` is already what the shape checks call. A raced link that leaves different bytes already collides and keeps those bytes.
