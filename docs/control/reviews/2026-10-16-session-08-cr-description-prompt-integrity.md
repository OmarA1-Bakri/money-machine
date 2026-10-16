# Session 08 Prompt Integrity Review — bare CR draft description

**Date:** 2026-10-16
**Prompt:** `prompts/implementation/11_SESSION_08_MERCHANDISING_AND_ASSET_FACTORY.md`
**Verified SHA-256:** `a7a406cecd9c93efdec1045f394b911e614cd79366840e33d5c53d9968f7cd33`
**Scope:** One draft-lookup pin. The two-walk description compare folds CRLF to LF and leaves a bare CR in place, so the same decoy text refuses with `count`. Do not activate Session 08. Do not commission A10, A11, or A13. Do not lift Exit 78.

The prompt file is not amended. This record is the corrective addendum.

## 1. Prompt authenticity

**Status:** VERIFIED on the prior Session 08 records. The prompt file is unchanged.

## 2. Three-dimensional review

### Fidelity

**Verdict:** CONDITIONAL APPROVE.

**F-01 [HIGH] — A bare CR and a LF are different descriptions on the walk**

- **Prompt lines:** Action 9, the draft lookup before create.
- **Authority:** `_row_text` folds `\r\n` and returns the rest unchanged. The two walks must agree on that string.
- **Consequence:** A decoy `alpha\rbeta` on the first walk and `alpha\nbeta` on the second raises `count` and does not post.
- **Amendment:** Those two walks still post. Deleting the leftover `\r` fold fails only that row. The CRLF row still posts. An empty description and a missing one still post. A changed description still refuses.

### Safety and executability

**Verdict:** CONDITIONAL APPROVE.

**S-01 [HIGH] — This stays on the fixture client**

- **Prompt lines:** Action 9.
- **Authority:** No live Etsy write. Session 08 is not activated.
- **Amendment:** Edit the fixture draft client, its test, this addendum, and the implementation log. Do not edit `IMPLEMENTATION_STATE.json` or `defang_normalizer.py`.

### Gameability

**Verdict:** CONDITIONAL APPROVE.

**G-01 [HIGH] — The CRLF row must not save the bare-CR fold**

- **Authority:** `test_a_crlf_description_and_an_lf_one_still_post` is already covered by the `\r\n` fold.
- **Amendment:** `test_a_cr_description_and_an_lf_one_still_post` is the row that dies when the leftover `\r` fold is removed.

**Deferred:** A bare CR inside a marker line stays one line. `_description_lines` already folds `\r\n` and is not this hole. Owning session: Session 08, a later marker pin.

## 3. Addendum

1. Prove the prompt hash. It stays `a7a406cecd9c93efdec1045f394b911e614cd79366840e33d5c53d9968f7cd33`.
2. `_row_text` folds `\r\n` to `\n`, then folds a leftover `\r` to `\n`, before the two walks compare descriptions.
3. `alpha\rbeta` and `alpha\nbeta` still post. `alpha\r\nbeta` and `alpha\nbeta` still post. The empty and missing rows still post. A changed description still refuses.
4. Do not activate Session 08. Do not commission A10, A11, or A13. Do not lift Exit 78. Do not edit `IMPLEMENTATION_STATE.json`.
