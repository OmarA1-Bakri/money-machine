# Session 08 Prompt Integrity Review — W3 delivery PDFs

**Date:** 2026-10-14
**Prompt:** `prompts/implementation/11_SESSION_08_MERCHANDISING_AND_ASSET_FACTORY.md`
**Verified SHA-256:** `a7a406cecd9c93efdec1045f394b911e614cd79366840e33d5c53d9968f7cd33`
**Workbook authority:** `hands-off-money-machine-full-implementation-workbook.md` appendix row for this prompt (5,092 bytes, 236 lines)
**Scope:** Wave 3 only. The README/access PDF and the optional free-gift PDF in action 4. Fixture copy, fixture facts, and the merged design-token and listing-image modules. No other action.

The prompt file is not amended. This record is the corrective addendum. It does not overwrite the Wave 0, Wave 1, or Wave 2 records.

## 1. Prompt authenticity

**Status:** VERIFIED

- The extracted file's SHA-256 equals the workbook appendix value `a7a406cecd9c93efdec1045f394b911e614cd79366840e33d5c53d9968f7cd33`.
- The workbook copy between `COPY START` and `COPY END` contains that same extract.
- The prompt stays the unamended source of record.

## 2. Three-dimensional review

The operator instruction for this wave is the two-page README/access PDF and the one-page free-gift PDF. Ten listing images, video, live screenshot acquisition, link opening, storage, workflow linkage, and commissioning are not this wave. Carried parks from #70 that are named in the operator instruction are in scope as tests or small fixes.

### Fidelity

**Verdict:** CONDITIONAL APPROVE. Three high findings, resolved by the addendum.

**F-01 [HIGH] — The prompt's full session is not this wave**

- **Prompt lines:** 1–236, especially actions 1–3, 4 (images and video), 5–12, and the required exit code at line 229.
- **Authority:** The operator slice is the README/access PDF and the optional free-gift PDF. D-0032 keeps Session 08 inactive. `current_session` stays 7. A10 and A11 stay `DESIGNED`. `IMPLEMENTATION_STATE.json` stays at revision 64.
- **Consequence of literal execution:** Rendering the ten images again, capturing live Notion screenshots, opening variant links, writing S3, linking the workflow, commissioning A11, and printing `SESSION_08_MERCHANDISING_AND_ASSETS_COMPLETE` would claim the session is finished.
- **Amendment:** Implement the two delivery PDFs only, plus the named #70 parks. Do not print the session exit code. Do not activate Session 08. Do not edit `IMPLEMENTATION_STATE.json`.

**F-02 [HIGH] — PDF sentences can be drawn from copy that claim validation would reject**

- **Prompt lines:** 102–113. Action 2 already requires every claim to reference a ProductFact. The PDF lines name setup, widgets, access links, a duplication reminder, support, a review request, the free gift, and the free community, and do not say to re-check those sentences.
- **Authority:** `validate_claims` is the claim gate. Chapter 15.2 admits only free links. The gift contract already rejects a paid or checkout URL on the gift configuration.
- **Consequence:** A template can paint "Bestseller 500 sold" or a checkout URL beside a valid gift name, and a green page-count test would still pass.
- **Amendment:** Every visible PDF sentence is a fixed template of cited claims and is passed through `validate_claims` before a PDF is returned. A listing copy that fails, or a sentence that is not that template, refuses the render. The gift PDF refuses a paid or checkout URL even when the sentence is otherwise a matching template.

**F-03 [HIGH] — Artifact lineage in the prompt includes storage URIs and screenshot parents these PDFs do not have**

- **Prompt lines:** 140–155. Storage URI and S3 are action 8. These PDFs are not screenshots.
- **Authority:** Operator slice. The delivery record still has to carry product id, spec version, build version, merchandising version, template version, output hash, page count, and QA status.
- **Consequence:** Inventing a storage URI would pretend action 8 is done. Omitting spec version would let a product-version change keep the same bytes.
- **Amendment:** Each PDF returns that lineage record, and the same lineage text is appended to the PDF bytes so a spec-version change changes the hash. QA status on a returned PDF is `passed`. No storage URI. No source-screenshot hash.

**What the prompt already gets right**

- The README is two pages and the gift PDF is one page (lines 104–113).
- The gift PDF is optional and has no paid checkout link (lines 110–113).
- Claims stay fact-bound (lines 38–52). This wave does not relax the rejection classes.
- Tokens and listing images already exist. This wave reuses them.

### Safety and executability

**Verdict:** CONDITIONAL APPROVE. Three high findings, resolved by the addendum.

**S-01 [HIGH] — Playwright can reach the network, and link validation is a live open**

- **Prompt lines:** 76 and 128–138.
- **Authority:** Fixture-only. No live HTTP, no Notion, no Etsy, no Canva. Exit 78 stays HELD.
- **Consequence:** A renderer that loads a remote font, or a link step that opens a variant page, leaves the fixture boundary.
- **Amendment:** Fonts are the vendored file already used by the listing images. The browser context aborts `http` and `https`. Variant links are the admitted `secret_links` fact rendered into the PDF. They are not opened. No Notion client is constructed.

**S-02 [HIGH] — Open pull requests #63 and #68 own the control and CI files**

- **Authority:** Do not edit `.github/workflows/ci.yml`, `AGENTS.md`, `CLAUDE.md`, `src/money_machine/control/**`, `src/money_machine/cli/s07_navigation_guard.py`, `docs/architecture/S07_EVIDENCE_RECORD.md`, `docs/control/IMPLEMENTATION_STATE.json`, `tests/bootstrap/**`, `tests/fixtures/control/**`, or `tests/unit/agents/test_notion_product_builder_*.py`.
- **Consequence:** Editing any of those collides with the open pulls.
- **Amendment:** This wave does not edit them. Do not commission A10 or A11. Do not register an implementation for either agent.

**S-03 [HIGH] — An unpinned PDF is not a deterministic hash**

- **Prompt lines:** 197–198, applied to delivery PDFs.
- **Consequence:** Chromium writes the creation date, the modification date, and a document id into the PDF. Two renders of the same inputs differ. A test can then pin nothing.
- **Amendment:** Same-length replacement pins the creation date, the modification date, and the document id. Producer text is left unchanged when it is already stable. Lineage is appended after `%%EOF` so the xref offsets stay valid. The same inputs produce the same PDF bytes.

**Executability**

- A10 already returns a `ListingCopy`. This wave reads that copy and the built variants. It does not construct `ListingPackage`.
- `validate_claims` only walks listing surfaces. PDF sentences are attached as `pdf_blocks` on a probed draft so the same function accepts or rejects them. A10 does not emit those blocks. Empty blocks leave the listing hash inputs extended by one empty field, recomputed in the listing tests.
- The #70 parks that this wave takes on are the sRGB divisor, direct token validation, `TokenValidationError` for invalid token shapes, swatch colours from `request.variants`, and the hub screenshot that lineage records.
- `playwright` stays a dev dependency.

### Gameability

**Verdict:** CONDITIONAL APPROVE. The acceptance criteria in the pull request are the ungameable form of this wave.

**G-01 [HIGH] — A two-byte file named `.pdf` satisfies "exactly 2 pages"**

- **Cheap fake:** Return a stub and assert `len(pages) == 2` on a hand-built list.
- **Amendment:** Page count is parsed from the PDF bytes (`/Type /Page`). The readme render refuses a count other than 2. The gift render refuses a count other than 1. Deleting that check returns the PDF whose parsed count is wrong.

**G-02 [HIGH] — A refusal that is only asserted by reading the source is not a kill**

- **Cheap fake:** A test searches the file for `raise` and never feeds a bad sentence or a checkout URL.
- **Amendment:** Each refusal is its own call. The real function rejects the bad input. A copy of the module with that call deleted accepts the same input and is failed by a behavioural test. The constant mutants for contrast are run with the AST meta-tests deselected.

## 3. Corrective addendum

This addendum governs Wave 3. The prompt remains the unamended source of record.

1. Prove the prompt hash, then implement only the README/access PDF and the optional free-gift PDF, plus the named #70 parks.
2. The README PDF is exactly two pages. Page 1 is three setup sentences plus the configured widgets and resources. Page 2 is one access line per built variant, the duplication reminder, the support channel, and a review request. Every sentence is a `render` template of cited claims.
3. The gift PDF is exactly one page when a free gift is configured. It states the gift name and, when the fact has a community, the free community. It is refused when no gift is configured. A paid or checkout URL in the rendered gift text is refused.
4. Before any PDF is returned, `validate_claims` runs on the listing copy and again on the copy with the PDF sentences attached. Visible text that is not those sentences refuses the render. Claim-rejection classes are not edited.
5. The same inputs produce the same PDF bytes. Creation date, modification date, and document id are pinned. Lineage records product id, spec version, build version, merchandising version, template version, output hash, page count, and QA status `passed`. A higher spec version changes the lineage and the bytes.
6. Fonts stay vendored. Remote URLs are aborted. No Notion, Etsy, or other network client is constructed. Variant links are not opened.
7. Carry these #70 parks: pin contrast for a channel on the linear side of 0.04045 and for channel `0x0B`; `emit_css` and `compose_listing_documents` validate tokens when called directly; invalid token shapes raise `TokenValidationError`; swatch count and colours come from `request.variants`; hub frames embed the hub screenshot whose hash lineage records.
8. Do not render video. Do not acquire live screenshots. Do not open or repair links. Do not write S3 or a storage URI. Do not link the workflow. Do not register or commission A10 or A11. Do not edit A07, A08, or A09.
9. Do not edit the files owned by open pulls #63 and #68, and do not edit `IMPLEMENTATION_STATE.json`. Exit 78 stays HELD. Session 08 stays inactive. Do not print the session exit code.
10. Killing tests: deleting the unvalidated-copy check, the unclaimed-text check, the paid-checkout check, or the page-count check accepts the input that the real function refuses.

## 4. Deferrals

| Finding | Owner | Reason |
|---|---|---|
| Ten listing images, already merged in #70 | Closed by #70 | This wave reuses them and does not re-render the package |
| Short video | Later Session 08 wave | Operator slice is the two PDFs |
| Live screenshot acquisition | Later Session 08 wave | S-01 |
| Opening variant links and link repair | Later Session 08 wave | Fixture-only; links are rendered, not fetched |
| Storage URI and S3 | Later Session 08 wave | F-03 |
| Workflow linkage and successor draft job | Later Session 08 wave | Operator slice |
| Action 11 commissioning | Operator decision after implementation | A10 and A11 stay DESIGNED |
| Action 12 session exit code and the five-file close | Session 08 close | This wave is not the close |
| Product-design visual sign-off | Session 08 close | Page count and claim text are testable here |
| Exit 78 | Unchanged | Operator instruction |
| Parked claim-validation publishers and over-refusals from #69 | Unchanged | This wave does not edit those rules |
| W2 mutants that #70 parked and this operator did not name | Later Session 08 wave | Quote-strip, route abort, role-order, escape, device-scale factor, dev-only Playwright import |
| Moving the sRGB cutoff inside `(10/255, 11/255)` | Equivalent for every 8-bit channel | No integer channel lies between 0.03928 and 0.04045 |
