# Session 08 Prompt Integrity Review — lone CR marker line

**Date:** 2026-10-16
**Prompt:** `prompts/implementation/11_SESSION_08_MERCHANDISING_AND_ASSET_FACTORY.md`
**Verified SHA-256:** `a7a406cecd9c93efdec1045f394b911e614cd79366840e33d5c53d9968f7cd33`
**Scope:** One draft-marker pin parked as SF1 on the #95 verifier (PASS @ 13bfa0f). `_row_text` already folds a leftover CR. `_description_lines` still folds only CRLF, so a marker after a lone CR is not adopted and fails closed. Do not activate Session 08. Do not commission A10, A11, or A13. Do not lift Exit 78.

The prompt file is not amended. This record is the corrective addendum.

## 1. Prompt authenticity

**Status:** VERIFIED.

The extracted file SHA-256 equals the workbook appendix value `a7a406cecd9c93efdec1045f394b911e614cd79366840e33d5c53d9968f7cd33`. The file bytes equal the workbook copy between the `COPY START` and `COPY END` markers for `11_SESSION_08_MERCHANDISING_AND_ASSET_FACTORY.md`.

## 2. Three-dimensional review

### Fidelity

**Verdict:** CONDITIONAL APPROVE.

**F-01 [HIGH] — A marker after a lone CR is not its own line**

- **Prompt lines:** 181 (`CREATE_ETSY_DRAFT ready`) and 222 (Etsy draft job is automatically ready).
- **Authority:** `_description_lines` replaces `\r\n` and then splits on `\n`. A bare `\r` stays inside the line, so `_line_marker` does not see the marker. `_row_text` already folds that leftover `\r` for the two-walk compare. Open PR #95 owned `_row_text` and has merged; this pin does not edit it.
- **Consequence:** A draft whose description places the marker after a lone CR is not adopted. The lookup fails closed and posts a second draft.
- **Amendment:** Before the marker line compare, a bare CR is the same line break as CRLF and LF. That draft is adopted and no second post is made. A changed description still refuses. A marker that is only part of a longer line is still not adopted.

### Safety and executability

**Verdict:** CONDITIONAL APPROVE.

**S-01 [HIGH] — This stays on the fixture marker reader**

- **Prompt lines:** 181, 203 (commission A10 and A11), and 222.
- **Authority:** No live Etsy, S3, or Notion write. Session 08 is not activated. `current_session` stays 7, `state_revision` stays 64, Exit 78 stays HELD. PR #63 and PR #68 are out of scope.
- **Amendment:** Edit `_description_lines`, one test, this addendum, and the implementation log. Do not edit `_row_text`. Do not edit `IMPLEMENTATION_STATE.json`.

### Gameability

**Verdict:** CONDITIONAL APPROVE.

**G-01 [HIGH] — The CRLF marker row must not save the bare CR fold**

- **Authority:** `test_a_crlf_marker_line_is_adopted` uses `\r\n`, which the current fold already accepts. `test_a_cr_description_and_an_lf_one_still_post` has no marker line.
- **Consequence:** A suite that only keeps those rows stays green when `_description_lines` folds `\r\n` and leaves a bare `\r`.
- **Amendment:** `test_a_lone_cr_marker_line_is_adopted` is the row that dies under that mutant. Its description contains `\r` and does not contain `\r\n`. The existing id is adopted and the post list stays empty.

## 3. Addendum

1. Prove the prompt hash. It stays `a7a406cecd9c93efdec1045f394b911e614cd79366840e33d5c53d9968f7cd33`. The prompt file is not edited.
2. In `_description_lines` only, fold `\r\n` to `\n` and then fold a leftover `\r` to `\n` before the marker line compare. Do not edit `_row_text`.
3. A draft whose description has the marker on a line after a lone CR is adopted. No second post. A changed description still refuses. A marker that is only part of a longer line is still not adopted.
4. The new row is the unique kill of the mutant that folds only `\r\n` and leaves a bare `\r`. Measure that mutant on `tests/unit/integrations/test_etsy_draft_client.py`, restore the source, and record F/P in `docs/control/IMPLEMENTATION_LOG.md`.
5. Level 1 only: focused RED/GREEN on that test file, then `ruff format --check`, `ruff check`, and `pyright` on the files this pin touches.
6. Do not activate Session 08. Do not commission A10, A11, or A13. Do not lift Exit 78. Do not edit `IMPLEMENTATION_STATE.json`. Do not touch PR #63 or #68. No live Etsy, S3, or Notion.

## 4. Deferrals

| Finding | Reason | Owner |
|---|---|---|
| Session 08 activation, agent commissioning, and Exit 78 | The operator pinned this to one fixture row. `current_session` stays 7 and `state_revision` stays 64. | Session 08 exit |
| Full merchandising package, live providers, and the thirteen-tag / ten-image / PDF gates | Those are the session deliverable. This pin does not satisfy them and does not weaken them. | Session 08 exit |

## 5. What the prompt already gets right

The draft job stays fail-closed until a whole normalized line equals the marker. A changed description between the two walks still refuses with `count` and does not post. A marker embedded in a longer line is not an adoption. CRLF is already one break in both the description compare and the marker reader. This pin only adds the bare CR the marker reader still drops.
