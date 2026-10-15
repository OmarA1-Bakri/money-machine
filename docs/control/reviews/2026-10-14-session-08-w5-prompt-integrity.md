# Session 08 Prompt Integrity Review — W5 screenshot acquisition

**Date:** 2026-10-14
**Prompt:** `prompts/implementation/11_SESSION_08_MERCHANDISING_AND_ASSET_FACTORY.md`
**Verified SHA-256:** `a7a406cecd9c93efdec1045f394b911e614cd79366840e33d5c53d9968f7cd33`
**Workbook authority:** `hands-off-money-machine-full-implementation-workbook.md` appendix row for this prompt (5,092 bytes, 236 lines)
**Scope:** Wave 5 only. Action 5, fixture pages standing in for Notion variant pages. Live acquisition stays parked. Cheap carried fixes from #72 are in scope. No other action.

The prompt file is not amended. This record is the corrective addendum. It does not overwrite the Wave 0, Wave 1, Wave 2, Wave 3, or Wave 4 records.

## 1. Prompt authenticity

**Status:** VERIFIED

- The extracted file's SHA-256 equals the workbook appendix value `a7a406cecd9c93efdec1045f394b911e614cd79366840e33d5c53d9968f7cd33`.
- The workbook copy between `COPY START` and `COPY END` contains that same extract (5,092 bytes, 236 lines).
- The prompt stays the unamended source of record.

## 2. Three-dimensional review

The operator instruction for this wave is fixture-only screenshots of each Notion variant, on the Chromium path the PDFs already use. Live acquisition stays behind an injectable fetcher that defaults to refusal. The outputs must be usable as the screenshot files W2 and W4 already take, without changing those waves' golden hashes.

### Fidelity

**Verdict:** CONDITIONAL APPROVE. Three high findings, resolved by the addendum.

**F-01 [HIGH] — The prompt's full session is not this wave**

- **Prompt lines:** 1–236, especially actions 1–4, 6–12, and the required exit code at line 229.
- **Authority:** The operator slice is action 5 plus the cheap #72 fixes. D-0032 keeps Session 08 inactive. `current_session` stays 7. A10 and A11 stay `DESIGNED`. `IMPLEMENTATION_STATE.json` stays at revision 64.
- **Consequence of literal execution:** Re-rendering the ten images, the PDFs, and the video, opening variant links, writing S3, linking the workflow, commissioning A11, and printing `SESSION_08_MERCHANDISING_AND_ASSETS_COMPLETE` would claim the session is finished.
- **Amendment:** Implement fixture screenshot acquisition and the cheap carried fixes only. Do not print the session exit code. Do not activate Session 08. Do not edit `IMPLEMENTATION_STATE.json`.

**F-02 [HIGH] — "Each Notion variant" is not a licence to open production Notion**

- **Prompt lines:** 116–125. Action 5 says to automate screenshots from each Notion variant, with a consistent viewport, no browser chrome, a wait for loaded content, a stable crop, sensitive/sample data rules, and a screenshot hash plus source build version.
- **Authority:** The operator slice is local fixture pages and a fetcher that defaults to refusal. No production Notion or Etsy, no network writes, no live Notion calls. W4 parked live acquisition.
- **Consequence:** A literal browser run against `notion.so` would capture customer data and perform a live read this wave is not allowed to perform.
- **Amendment:** One local HTML fixture stands in for each built variant. Chromium screenshots that file. A live URL is passed to the injected fetcher. The default fetcher raises `live_acquisition` before navigation. Sensitive checks read the text the page rendered, after the readiness marker.

**F-03 [HIGH] — Swapping the captured bytes into W2 or W4 would move golden hashes**

- **Prompt lines:** 140–155 and 197–198, applied to screenshots that later waves already hash.
- **Authority:** The operator said the outputs plug into the existing image and video inputs without changing those golden hashes unless a change is honestly required.
- **Consequence:** Replacing the committed listing-screenshot PNGs with a new Chromium capture changes the W2 PNG bytes and the W4 Matroska bytes. A green run would then celebrate a different artifact.
- **Amendment:** Captures are RGB PNGs plus a sha256 allow-list entry, which is the input shape `refuse_unknown_screenshot` already enforces. The committed fixture PNGs stay the golden inputs. This wave does not re-pin `6318854297cd5d316fdf4c579a73f188ec5f1e2089745534aa9d4ca6245fe248`.

**What the prompt already gets right**

- Viewport, chrome, load wait, crop, sensitive-data rules, screenshot hash, and source build version are the action 5 list (lines 120–125).
- Claims stay fact-bound. This wave does not relax the rejection classes.
- Tokens, listing images, delivery PDFs, and the silent video already exist. This wave does not rebuild them.

### Safety and executability

**Verdict:** CONDITIONAL APPROVE. Two high findings, resolved by the addendum.

**S-01 [HIGH] — Open pull requests #63 and #68 own the control and CI files**

- **Authority:** Do not edit `.github/workflows/ci.yml`, `AGENTS.md`, `CLAUDE.md`, `src/money_machine/control/**`, `src/money_machine/cli/s07_navigation_guard.py`, `docs/architecture/S07_EVIDENCE_RECORD.md`, `docs/control/IMPLEMENTATION_STATE.json`, `tests/bootstrap/**`, `tests/fixtures/control/**`, or `tests/unit/agents/test_notion_product_builder_*.py`.
- **Consequence:** Editing any of those collides with the open pulls.
- **Amendment:** This wave does not edit them. Chromium is the Playwright browser the PDF tests already install. Do not commission A10 or A11.

**S-02 [HIGH] — A fixed sleep is not a load wait, and the HTML file is not the rendered text**

- **Prompt lines:** 122–124.
- **Consequence:** `time.sleep` then a screenshot can pass while the page is still empty. Scanning the file accepts a secret the page painted from script, or refuses a secret that exists only in a comment.
- **Amendment:** Wait for `html[data-mm-ready="loaded"]`. Then read `page.inner_text("body")`. Refuse emails, `notion.so` / `notion.site`, token-shaped strings, UUIDs, and 32-hex ids in that rendered text. A missing marker is `not_ready`.

**Executability**

- `playwright` is already a dev dependency. The PDF tests launch Chromium with `--no-sandbox` and the same font-stability flags. This wave reuses that launch, headless, with a pinned viewport and a pinned clip.
- The three fixture variants are Sage Green, Navy Blue, and Rose Gold, matching the merchandising fixture. No Notion client is constructed.
- The cheap #72 fixes stay inside `gift_links.py`, `video.py`, and the walkthrough tests. They do not change the painted golden captions.

### Gameability

**Verdict:** CONDITIONAL APPROVE. The acceptance criteria in the pull request are the ungameable form of this wave.

**G-01 [HIGH] — A fixture-only success does not prove live acquisition is refused**

- **Cheap fake:** Capture three local files and never call the fetcher. Flip the default to a function that returns HTML, or delete the raise, and the fixture tests stay green.
- **Amendment:** The default parameter is `default_live_fetcher`. Calling it raises `live_acquisition`. `capture_variant_screenshots` with a `https://www.notion.so/...` URL and no injected fetcher raises the same code before navigation. An injected fetcher that returns fixture HTML is what the live slot actually calls. Deleting the raise, or pointing the default at another callable, fails those tests.

**G-02 [HIGH] — The PDF prefix strip lets `Free gift: hello` paint a blank colon**

- **Prompt lines:** not in action 5. Carried from #72 SF1 and the verifier gate on this wave.
- **Cheap fake:** `refuse_gift_charset` strips `Free gift: ` before the allowlist, and the glyph loop skips a character that the single-character charset check rejects. The colon is painted as an empty cell.
- **Amendment:** The video charset check runs on the full caption, with no prefix strip and no trailing-period trim. `Free gift: hello` is refused. A copy that calls `refuse_gift_charset` again accepts that string. The painted golden captions do not contain that prefix, so the pinned video hash is unchanged.

**G-03 [HIGH] — A lineage field copied from the same helper is not an independent hash**

- **Cheap fake:** The test asserts `lineage.screenshot_sha256 == lineage.screenshot_sha256`.
- **Amendment:** The test parses the PNG `tEXt` chunk with its own walker, hashes the raw PNG with `hashlib`, and compares that digest and the literal build version `5` to the chunk. The object fields are checked against those same independent values.

## 3. Corrective addendum

This addendum governs Wave 5. The prompt remains the unamended source of record.

1. Prove the prompt hash, then implement only fixture screenshot acquisition, plus the carried #72 fixes that are cheap.
2. One local HTML file per fixture variant: Sage Green, Navy Blue, Rose Gold. Chromium is headless. Viewport is 480×360. Clip is 480×270 at the origin. Device scale is 1. No `page.goto` of a remote URL.
3. Wait for `html[data-mm-ready="loaded"]`. A missing marker raises `not_ready`. Do not sleep.
4. After that wait, refuse the rendered body text when it contains an email, `notion.so`, `notion.site`, a token-shaped string, a UUID, or a 32-hex id. A secret only in a comment or a script that does not paint it is allowed. A secret assembled into the DOM is refused.
5. The returned PNG is canonical 8-bit RGB so the existing PNG decoder can read it. Lineage records product id, spec version, build version, the sha256 of those raw bytes, variant, template version `s08-w5-screenshot-1`, viewport, crop, and QA status `passed`. The same fixture captured twice has the same hash.
6. `default_live_fetcher` is the default argument and it raises `live_acquisition`. A caller may inject a fetcher. This wave does not perform a live HTTP fetch.
7. Captured files satisfy `refuse_unknown_screenshot` on the listing-image path and the video path when their hash is allow-listed. The committed listing-screenshot PNGs are not replaced. The W4 golden hash stays `6318854297cd5d316fdf4c579a73f188ec5f1e2089745534aa9d4ca6245fe248`.
8. Video captions call `refuse_raw_charset` on the full string. `Free gift: hello` is `paid_checkout`. A dashboard output `Today-panel` is `caption_glyph`. A wrapped dashboard line of 26 characters is painted. A wrapped dashboard line of 27 characters is `caption_fit`. `refuse_caption_width` on a one-element 27-character tuple is `caption_fit`. A 150×90 container is `frame_size`.
9. Do not open or repair links. Do not write S3. Do not link the workflow. Do not register or commission A10 or A11.
10. Do not edit the files owned by open pulls #63 and #68, and do not edit `IMPLEMENTATION_STATE.json`. Exit 78 stays HELD. Session 08 stays inactive. Do not print the session exit code.

## 4. Deferrals

| Finding | Owner | Reason |
|---|---|---|
| Live Notion navigation | Later Session 08 wave | F-02; the default fetcher stays a refusal |
| Opening or repairing variant links | Later Session 08 wave | Operator slice is acquisition |
| Storage URI and S3 | Later Session 08 wave | Action 8 |
| Workflow linkage and commissioning | Later Session 08 wave | F-01; D-0032 |
| Session exit code | Later, at a real session exit | F-01 |
| Exit 78 | Held | Operator instruction |
| Replacing the committed listing-screenshot PNGs | Not this wave | F-03; golden hashes stay |
| `-flags +bitexact` removed on its own | Parked | Operator; the pair is not a unique byte change to chase this wave |
| The cross-platform video hash | Later wave | W4 park |
| Trailer tampering after the Matroska bytes | Later wave | W4 park |
| Screenshot bytes read three times | Later wave | W4 park |
| An undecodable PNG pastes a blank frame | Later wave | W4 park |
| Verifier #71 SF1 and SF3 | Later wave | W4 park |
| #70 NIT1 contrast wording | Closed as historical | The log is not rewritten |
| `-map_metadata -1`, the metadata strip, `SOURCE_DATE_EPOCH`, and `-threads 1` | Later wave | No byte change on this wheel |
| Whole-document `/OpenAction`, `/AA`, and outline scanning | Later wave | W3 park |
| Non-Link URI annotations | Later wave | W3 park |
| Defanged hosts | Later wave | W3 park |
| José and Zoë | Later wave | W3 park |
| Bare `127.1`, `0x7f000001`, and `2130706433` | Later wave | W3 park |
| Deleting the URI loop while `if count:` stays | Later wave | W3 park |
| Newest xref only, with no `/Prev` | Later wave | W3 park |
| #69 publishers and over-refusals | Later wave | Not this slice |
| W2 survivors other than the font edge space | Later wave | Not this slice |
| Chromium m153 writes no XMP and no `/ID` | Later wave | PDF bytes already pinned |

## 5. Final verdict

**CONDITIONAL APPROVE.** Critical and high findings are resolved by the numbered addendum above. Implementation of Wave 5 may start. The prompt file stays unamended.
