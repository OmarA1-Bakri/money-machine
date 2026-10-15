# Session 08 Prompt Integrity Review — W6 link injection and validation

**Date:** 2026-10-15
**Prompt:** `prompts/implementation/11_SESSION_08_MERCHANDISING_AND_ASSET_FACTORY.md`
**Verified SHA-256:** `a7a406cecd9c93efdec1045f394b911e614cd79366840e33d5c53d9968f7cd33`
**Workbook authority:** `hands-off-money-machine-full-implementation-workbook.md` appendix row for this prompt (5,092 bytes, 236 lines)
**Scope:** Wave 6 only. Action 6, fixture-backed checks of the README/access and free-gift PDFs from W3. Live opens stay behind an injected checker that defaults to refusal. Cheap carried fixes from #73 are in scope. No other action.

The prompt file is not amended. This record is the corrective addendum. It does not overwrite the Wave 0 through Wave 5 records.

## 1. Prompt authenticity

**Status:** VERIFIED

- The extracted file's SHA-256 equals the workbook appendix value `a7a406cecd9c93efdec1045f394b911e614cd79366840e33d5c53d9968f7cd33`.
- The workbook copy between `COPY START` and `COPY END` contains that same extract (5,092 bytes, 236 lines).
- The prompt stays the unamended source of record.

## 2. Three-dimensional review

The operator instruction for this wave is to extract every embedded link from the A11 PDFs after export, open each variant link through an injected fixture checker, and record the result. A failed link creates one targeted repair. Guards already settled on #71 are reused. A per-link round-trip must fail when any one injected URI differs from the exact string that passed validation.

### Fidelity

**Verdict:** CONDITIONAL APPROVE. Three high findings, resolved by the addendum.

**F-01 [HIGH] — The prompt's full session is not this wave**

- **Prompt lines:** 1–236, especially actions 1–5, 7–12, and the required exit code at line 229.
- **Authority:** The operator slice is action 6 plus the named #73 carries. D-0032 keeps Session 08 inactive. `current_session` stays 7. A10 and A11 stay `DESIGNED`. `IMPLEMENTATION_STATE.json` stays at revision 64. Exit 78 stays HELD.
- **Consequence of literal execution:** Writing S3, linking the workflow, commissioning A11, and printing `SESSION_08_MERCHANDISING_AND_ASSETS_COMPLETE` would claim the session is finished.
- **Amendment:** Implement fixture link validation and the named #73 carries only. Do not print the session exit code. Do not activate Session 08. Do not edit `IMPLEMENTATION_STATE.json`.

**F-02 [HIGH] — "Open each variant link" is not a licence to call Notion or the network**

- **Prompt lines:** 127–138.
- **Authority:** Fixture-only. No production Notion or Etsy, and no live HTTP. Any live check goes through an injectable checker that refuses by default.
- **Consequence:** A literal `page.goto` or `urlopen` of a variant URL would perform the live read this wave is not allowed to perform.
- **Amendment:** The default checker raises `live_link_check` before any open. Tests inject a fixture checker. The default clock raises `live_clock`. Timestamps come from the injected clock.

**F-03 [HIGH] — New URL, percent, and PDF parsers would fork the #71 guards**

- **Prompt lines:** 131 and 193. Action 10 names embedded link extraction. #71 already settled the walk, the raw allowlist, and the percent guard.
- **Authority:** The operator said to reuse those guards and not write new ones.
- **Consequence:** A second walker or a second `%xx` regex can drift from the gift checks and still look green.
- **Amendment:** Extraction is `link_annotations`. Info and XMP are `refuse_gift_document_info`. The raw allowlist is `refuse_raw_charset`, and it runs before any fold. Percent is `refuse_paid_checkout`. On a full URI that function returns at `://` before `%xx`, so the URI percent check is the same function on the path, query, and fragment. Host admission is `_allowed_secret_host`.

**What the prompt already gets right**

- Failed links create a targeted asset-repair job (line 138).
- The README and the free-gift PDF are the A11 documents this check reads (lines 103–113).
- Claims stay fact-bound. This wave does not relax the rejection classes.

### Safety and executability

**Verdict:** CONDITIONAL APPROVE. Two high findings, resolved by the addendum.

**S-01 [HIGH] — Open pull requests #63 and #68 own the control and CI files**

- **Authority:** Do not edit `.github/workflows/ci.yml`, `AGENTS.md`, `CLAUDE.md`, `src/money_machine/control/**`, `src/money_machine/cli/s07_navigation_guard.py`, `docs/architecture/S07_EVIDENCE_RECORD.md`, `docs/control/IMPLEMENTATION_STATE.json`, `tests/bootstrap/**`, `tests/fixtures/control/**`, or `tests/unit/agents/test_notion_product_builder_*.py`.
- **Consequence:** Editing any of those collides with the open pulls.
- **Amendment:** This wave does not edit them. Do not commission A10 or A11.

**S-02 [HIGH] — A shared secret link is not three different URLs**

- **Prompt lines:** 166 and 131–136. W3 paints one admitted `secret_links` fact on every access anchor.
- **Authority:** Existing goldens stay. This wave does not rewrite the PDF sentences.
- **Consequence:** Treating one URL as three variant identities without passing the expected variant into the checker makes two of the three README rows fail, or a normalised URL hides a swapped string.
- **Amendment:** The checker receives the URI and the expected variant. The record stores the extracted URI. It must equal the accepted string exactly, including case. A same-host hop is allowed. A hop whose host differs is `redirect_host`.

**Executability**

- `link_annotations`, `document_strings`, `refuse_raw_charset`, `refuse_paid_checkout`, and `refuse_gift_document_info` already exist.
- The rendered README is opened only inside the existing Playwright PDF render. Validation itself does not launch a browser and does not open the URI.
- The #73 carries stay inside `screenshot_text.py` (the Latin-1 row is a test), `screenshots.py`, and the screenshot tests.

### Gameability

**Verdict:** CONDITIONAL APPROVE. The acceptance criteria in the pull request are the ungameable form of this wave.

**G-01 [HIGH] — Comparing link counts, or only the first URI, survives a one-link swap**

- **Cheap fake:** Assert `len(uris) == len(accepted)`, or compare `uris[0]` only. Swapping the second URI stays green.
- **Amendment:** Each index is compared with `!=` on the exact string. The test swaps index 0, 1, and 2, one at a time. The repair names that URI and no other. A case-only swap of one URI is the same refusal.

**G-02 [HIGH] — A repair that lists every link hides which one failed**

- **Cheap fake:** On any failure, emit a repair for every embedded URI.
- **Amendment:** A PDF with three links and one auth wall produces one repair. The other two records stay public. Zero links produce one repair with an empty link, not a repair of unrelated assets.

**G-03 [HIGH] — `> 255` accepts Latin-1 Zoë, and `O_NOFOLLOW` is redundant beside `O_EXCL`**

- **Cheap fake:** The existing charset rows all sit above 255, so `ord > 255` stays green. Dropping `O_EXCL` or `O_NOFOLLOW` stays green because the staging directory is new and empty.
- **Amendment:** `Zoë` (U+00EB) expects `fixture_charset`. `O_EXCL` refuses an existing file and an existing symlink, and the symlink target is not written. `O_NOFOLLOW` is removed: on Linux, `O_EXCL` already returns `EEXIST` for a symlink and does not follow it. The `/sw.js` continuation is deleted. Production capture passes an empty allow-list, and the loop never changed the network test.

## 3. Corrective addendum

This addendum governs Wave 6. The prompt remains the unamended source of record.

1. Prove the prompt hash, then implement fixture link validation, plus the carried #73 fixes named by the operator.
2. After export, read links with `link_annotations` and Info/XMP with `refuse_gift_document_info`. Do not add a second walker, allowlist, or percent expression.
3. A PDF with zero link annotations is `missing_links`. A link annotation without a URI is `malformed`. `http` is `not_https`. A host outside `_allowed_secret_host` is `host`. Userinfo, whitespace, and `mailto` are `malformed`.
4. `refuse_raw_charset` runs on the raw variant and on the raw URI probe before any fold. `Zoë` in either place is `paid_checkout`. `%xx` is `refuse_paid_checkout` on the path, query, and fragment, and on Info and XMP. A bare `%` stays on the allowlist.
5. Each extracted URI must equal the accepted string at that index. The checker then reports the variant, public access, and the duplicate button. The record stores the link, the variant, those three results, the injected timestamp, the PDF sha256, and the link sha256.
6. A failed link raises. The repair names that asset and that link. Other links in the same PDF are not repaired. The default checker raises `live_link_check`. The default clock raises `live_clock`.
7. Unknown variants are refused before the checker is called. A redirect chain whose host differs is `redirect_host`. A same-host hop is allowed.
8. The rendered README paints `SECRET_LINK` once per variant plus the duplication line. Chromium m153 stores each annotation as that string plus `/`. Validation against the painted string is `link_mismatch`. Validation against the annotation string passes, and replacing one annotation fails. The rendered gift PDF has zero links and is `missing_links`.
9. Add the Latin-1 `Zoë` screenshot row. Delete the `/sw.js` loop. Keep `O_EXCL` and drop `O_NOFOLLOW`, with tests for an existing file and a symlink.
10. Do not edit the files owned by open pulls #63 and #68, and do not edit `IMPLEMENTATION_STATE.json`. Exit 78 stays HELD. Session 08 stays inactive. Do not print the session exit code. Do not change the committed screenshot or video goldens.

## 4. Deferrals

| Finding | Owner | Reason |
|---|---|---|
| `file:` allow | Later wave | Operator park. The route still allows only the pinned template |
| `sendBeacon` via `set_content` with JavaScript on | Later wave | Operator park. Production capture leaves JavaScript off |
| Spelled-out `at ... dot com` emails | Later wave | Operator park |
| Non-ASCII refusal inside `_prepare` | Later wave | Operator park. The raw allowlist on `refuse_fixture_value` stays the fixture gate |
| `-flags +bitexact` on its own | Later wave | Operator park |
| Cross-platform video hash | Later wave | Operator park |
| Trailer tampering after the Matroska bytes | Later wave | Operator park |
| Text inside raster images | Later wave | Operator park |
| Storage URI and S3 | Later Session 08 wave | Action 8 |
| Workflow linkage and commissioning | Later Session 08 wave | F-01 |
| Session exit code | Later, at a real session exit | F-01 |
| Exit 78 | Held | Operator instruction |
| Whole-document `/OpenAction`, `/AA`, and outlines | Later wave | W3 park |
| Non-Link URI annotations | Later wave | W3 park |
| Defanged hosts | Later wave | W3 park |
| José and Zoë in the gift name or community | Later wave | The Latin-1 row is the screenshot gate, not the gift field |
| Bare `127.1`, `0x7f000001`, and `2130706433` | Later wave | W3 park |
| Deleting the URI loop while `if count:` stays | Later wave | W3 park |
| Newest xref only, with no `/Prev` | Later wave | W3 park |
| #69 publishers and over-refusals | Later wave | Not this slice |
| W2 survivors other than the font edge space | Later wave | Not this slice |
| Chromium m153 writes no XMP and no `/ID` | Later wave | PDF bytes already pinned by the renderer |

## 5. Final verdict

**CONDITIONAL APPROVE.** Critical and high findings are resolved by the numbered addendum above. Implementation of Wave 6 may start. The prompt file stays unamended.
