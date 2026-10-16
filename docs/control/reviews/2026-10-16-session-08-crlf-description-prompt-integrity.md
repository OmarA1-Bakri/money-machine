# Session 08 Prompt Integrity Review — CRLF draft description

**Date:** 2026-10-16
**Prompt:** `prompts/implementation/11_SESSION_08_MERCHANDISING_AND_ASSET_FACTORY.md`
**Verified SHA-256:** `a7a406cecd9c93efdec1045f394b911e614cd79366840e33d5c53d9968f7cd33`
**Scope:** One draft-lookup pin. The marker reader already folds CRLF to LF. The two-walk description compare does not, so the same decoy text refuses with `count`. Do not activate Session 08. Do not commission A10, A11, or A13. Do not lift Exit 78.

The prompt file is not amended. This record is the corrective addendum.

## 1. Prompt authenticity

**Status:** VERIFIED on the prior Session 08 records. The prompt file is unchanged.

## 2. Three-dimensional review

### Fidelity

**Verdict:** CONDITIONAL APPROVE.

**F-01 [HIGH] — CRLF and LF are different descriptions on the walk**

- **Prompt lines:** Action 9, the draft lookup before create.
- **Authority:** `_description_lines` replaces `\r\n` before it splits lines. `_row_text` returns the raw string, and the two walks must agree on that string.
- **Consequence:** A decoy `alpha\r\nbeta` on the first walk and `alpha\nbeta` on the second raises `count` and does not post.
- **Amendment:** Those two walks still post. Deleting the `\r\n` fold fails only that row. An empty description and a missing one still post. A changed description still refuses.

### Safety and executability

**Verdict:** CONDITIONAL APPROVE.

**S-01 [HIGH] — This stays on the fixture client**

- **Prompt lines:** Action 9.
- **Authority:** No live Etsy write. Session 08 is not activated.
- **Amendment:** Edit the fixture draft client, its test, this addendum, and the implementation log. Do not edit `IMPLEMENTATION_STATE.json`.

### Gameability

**Verdict:** CONDITIONAL APPROVE.

**G-01 [HIGH] — The empty-description row must not save the newline fold**

- **Authority:** `test_an_empty_description_and_a_missing_one_still_post` has no carriage return.
- **Amendment:** `test_a_crlf_description_and_an_lf_one_still_post` is the row that dies when the fold is removed.

## 3. Addendum

1. Prove the prompt hash. It stays `a7a406cecd9c93efdec1045f394b911e614cd79366840e33d5c53d9968f7cd33`.
2. `_row_text` folds `\r\n` to `\n` before the two walks compare descriptions.
3. `alpha\r\nbeta` and `alpha\nbeta` still post. The empty and missing rows still post. A changed description still refuses.
4. Do not activate Session 08. Do not commission A10, A11, or A13. Do not lift Exit 78. Do not edit `IMPLEMENTATION_STATE.json`.
