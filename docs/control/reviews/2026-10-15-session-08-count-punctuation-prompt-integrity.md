# Session 08 Prompt Integrity Review — count punctuation

**Date:** 2026-10-15
**Prompt:** `prompts/implementation/11_SESSION_08_MERCHANDISING_AND_ASSET_FACTORY.md`
**Verified SHA-256:** `a7a406cecd9c93efdec1045f394b911e614cd79366840e33d5c53d9968f7cd33`
**Scope:** Refuse parked review, rating, sold, and orders counts that use `;`, `,`, `:`, `=`, or `(`. Do not activate Session 08.

The prompt file is not amended. This record is the corrective addendum for this slice.

## 1. Prompt authenticity

**Status:** VERIFIED

The extracted file's SHA-256 equals `a7a406cecd9c93efdec1045f394b911e614cd79366840e33d5c53d9968f7cd33`. The prompt stays the unamended source of record.

## 2. Three-dimensional review

Action 2 rejects an unsupported claim. The parked publishers are counts a buyer would read as reviews or sales. Open pulls #63, #68, #80, #81, #82, #83, and #84 stay untouched. `IMPLEMENTATION_STATE.json` stays untouched. No live HTTP.

### Fidelity

**Verdict:** CONDITIONAL APPROVE.

**F-01 [HIGH] — These counts still publish**

- **Prompt lines:** Claim validation, unsupported claim rejection.
- **Authority:** The W1 follow-up left `;`, a comma between the word and a following number, `:`, `=`, parentheses, `Reviews: +500`, `Sold: 500`, and `Orders: 12` publishing.
- **Consequence:** A listing identity can state a review or sales count and still merchandise.
- **Amendment:** `500; reviews`, `reviews, 500`, `500 : reviews`, `500 = reviews`, `500 (reviews)`, `Reviews: +500`, `Sold: 500`, and `Orders: 12` are class claims.

### Safety and executability

**Verdict:** CONDITIONAL APPROVE.

**S-01 [HIGH] — A thousands comma is not a separator**

- **Prompt lines:** Claim validation.
- **Authority:** `1,000` and `4.9` stay whole. `500, reviews` is already a count through the digit run.
- **Consequence:** Putting `,` in the separator set can split a thousands group or change `4.9`.
- **Amendment:** `1,000` and `4.9` stay allowed. `500, reviews` stays a class claim when the separator comma is removed.

### Gameability

**Verdict:** CONDITIONAL APPROVE.

**G-01 [HIGH] — One shared character class can hide a single mark**

- **Prompt lines:** The count scan.
- **Authority:** Each new mark needs a row the other marks do not save.
- **Consequence:** Dropping only `;` stays green if the test uses a colon.
- **Amendment:** Dropping one mark publishes only that mark's row. A different mark in the same set still refuses.

## 3. Addendum

1. Prove the prompt hash, then extend the count-separator set with `;`, `,`, `:`, `=`, and `(`.
2. The eight strings in F-01 are refused as class claims, in `fact_text_problem` and through `merchandise`.
3. `1,000` and `4.9` stay allowed. `500, reviews` stays refused when `,` is removed from the separator set.
4. Glued forms (`500sold`, `2.5ksold`, `500 reviewsX`), the word `thousand`, and the Five_Star family stay parked.
5. Accepted word-first over-refusals (`Sold 4 Ways`, `Orders 2026 Log`, and the rest of that list) stay refused.
6. Session 08 stays inactive. `current_session` stays 7. `state_revision` stays 64. Exit 78 stays HELD. Do not edit `IMPLEMENTATION_STATE.json` or files owned by the open pulls named above.

## 4. What already holds

`.`, `_`, `/`, `-`, and `+` already collapse on either side of the count word. `Reviews: 500` and `Ratings = 2024` already refuse through the word-first review pattern. A comma inside a digit run already stays in the number.
