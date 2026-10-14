# Session 08 Prompt Integrity Review — W2 design tokens and listing images

**Date:** 2026-10-10
**Prompt:** `prompts/implementation/11_SESSION_08_MERCHANDISING_AND_ASSET_FACTORY.md`
**Verified SHA-256:** `a7a406cecd9c93efdec1045f394b911e614cd79366840e33d5c53d9968f7cd33`
**Workbook authority:** `hands-off-money-machine-full-implementation-workbook.md` appendix row for this prompt (5,092 bytes, 236 lines)
**Scope:** Wave 2 only. Action 3, and the ten listing images in action 4. Fixture screenshots and fixture A10 output. No other action.

The prompt file is not amended. This record is the corrective addendum. It does not overwrite the Wave 0 record `2026-10-10-session-08-prompt-integrity.md` or the Wave 1 record `2026-10-10-session-08-w1-prompt-integrity.md`.

## 1. Prompt authenticity

**Status:** VERIFIED

- The extracted file's SHA-256 equals the workbook appendix value `a7a406cecd9c93efdec1045f394b911e614cd79366840e33d5c53d9968f7cd33`.
- The workbook copy between `COPY START` and `COPY END` contains that same extract.
- The prompt stays the unamended source of record.

## 2. Three-dimensional review

The operator instruction for this wave is the design-token system and the ten listing-image templates. Video, delivery PDFs, live screenshot acquisition, link injection, storage, workflow linkage, and commissioning are not this wave.

### Fidelity

**Verdict:** CONDITIONAL APPROVE. Three high findings, resolved by the addendum.

**F-01 [HIGH] — The prompt's full session is not this wave**

- **Prompt lines:** 1–236, especially actions 4 (video and PDFs), 5–12, and the required exit code at line 229.
- **Authority:** The operator slice is action 3 and the ten listing images in action 4. D-0032 keeps Session 08 inactive. `current_session` stays 7. A10 and A11 stay `DESIGNED`.
- **Consequence of literal execution:** Rendering video and PDFs, capturing live Notion screenshots, validating links, writing S3, linking the workflow, commissioning A11, and printing `SESSION_08_MERCHANDISING_AND_ASSETS_COMPLETE` would claim the session is finished.
- **Amendment:** Implement tokens and the ten fixture listing images only. Do not print the session exit code. Do not activate Session 08. Do not edit `IMPLEMENTATION_STATE.json`.

**F-02 [HIGH] — Listing images can be drawn from copy that claim validation would reject**

- **Prompt lines:** 78–89 and 147–156. Action 2 already requires every claim to reference a ProductFact. Action 4 says to use actual screenshots and the actual page count, and does not say to re-check the pixels' text.
- **Authority:** `src/money_machine/domain/services/claim_validation.py` is the claim gate. Its rules are not changed in this wave. Wave 1's addendum: buyer-facing text is the fixed template of the claims it cites.
- **Consequence:** A template can paint "Bestseller" or "500 sold" beside a valid image line, and a green render test would still pass.
- **Amendment:** Every visible string in a listing image is passed through `validate_claims`. A copy that fails, or a string that is not the validated image-strip line for that frame, refuses the render before a PNG is returned. Page count and hub lines come from the A10 image strip, which is already bound to the built page count and the built hubs.

**F-03 [HIGH] — Artifact lineage in the prompt includes storage URIs and invalidation of every later asset**

- **Prompt lines:** 140–155. Storage URI and S3 are action 8. Full invalidation of video and PDFs is not this wave.
- **Authority:** Operator slice. The image record still has to carry product id, spec version, build version, source screenshot hashes, merchandising version, template version, output hash, dimensions, and QA status.
- **Consequence:** Inventing a storage URI would pretend action 8 is done. Omitting spec version would let a product-version change keep the same lineage.
- **Amendment:** Each listing image returns that lineage record. QA status on a returned image is `passed`. No storage URI. A changed spec version changes the lineage and the output hash. Video, PDFs, and storage stay deferred.

**What the prompt already gets right**

- The ten frames and their order match the image strip Wave 1 already emits: hero, overview, five hubs, colour options, devices, how it works (lines 80–87 and the `IMAGE_ROLES` contract).
- Tokens are a reusable system, not a one-off canvas (lines 55–70).
- Claims stay fact-bound (lines 38–52). This wave does not relax that.
- A11 is ordered after A10. This wave consumes A10 output. It does not reimplement copy generation.

### Safety and executability

**Verdict:** CONDITIONAL APPROVE. Three high findings, resolved by the addendum.

**S-01 [HIGH] — Playwright can reach the network, and screenshot acquisition is a live Notion path**

- **Prompt lines:** 76 and 116–125.
- **Authority:** Fixture-only. No live HTTP, no Notion, no Etsy, no Canva. Exit 78 stays HELD.
- **Consequence:** A renderer that loads a remote font, or a screenshot step that opens a Notion page, leaves the fixture boundary.
- **Amendment:** Fonts are a vendored file. The browser context aborts `http` and `https`. Screenshots are fixture files the caller names. A missing file is refused. A file whose bytes are not in the caller's allow-list is refused. No Notion client is constructed.

**S-02 [HIGH] — Open pull requests #63 and #68 own the control and CI files**

- **Authority:** Do not edit `.github/workflows/ci.yml`, `AGENTS.md`, `CLAUDE.md`, `src/money_machine/control/**`, `src/money_machine/cli/s07_navigation_guard.py`, `docs/architecture/S07_EVIDENCE_RECORD.md`, `docs/control/IMPLEMENTATION_STATE.json`, `tests/bootstrap/**`, `tests/fixtures/control/**`, or `tests/unit/agents/test_notion_product_builder_*.py`.
- **Consequence:** Editing any of those collides with the open pulls.
- **Amendment:** This wave does not edit them. If a token or image change cannot land without one of them, stop. Do not commission A10 or A11. Do not register an implementation for either agent.

**S-03 [HIGH] — An unpinned browser render is not a deterministic hash**

- **Prompt lines:** 197–198, applied to images.
- **Consequence:** A timestamp, a network font, or a device scale that follows the host display makes two renders of the same inputs differ. A test can then pin nothing.
- **Amendment:** Fixed viewport, device scale factor 1, vendored font, no visible timestamp, and a lineage chunk that is a pure function of the inputs. The same inputs produce the same PNG hash in one runtime.

**Executability**

- A10 already returns a `ListingCopy` whose image strip is the ten frames. This wave reads that copy. It does not construct `ListingPackage`.
- There is no domain `ProductFact` write. Facts stay the in-memory rows from Wave 1.
- Playwright is a dev dependency. The render aborts remote URLs. CI does not gain a workflow edit; the test run installs the pinned Chromium only when it is absent.
- `assets/*.py` scaffolds for video, PDF, screenshots, links, and the generic renderer stay scaffolds.

### Gameability

**Verdict:** CONDITIONAL APPROVE. The acceptance criteria in the pull request are the ungameable form of this wave.

**G-01 [HIGH] — Ten tiny files with the same bytes satisfy "all ten render"**

- **Cheap fake:** Write one PNG ten times and skip the templates.
- **Amendment:** The ten roles render through the token CSS and the A10 line for that role. Their output hashes differ. A second render of the same inputs matches the first byte for byte.

**G-02 [HIGH] — A refusal that is only asserted by reading the source is not a kill**

- **Cheap fake:** A test searches the file for `raise` and never feeds a bad screenshot or a bad claim.
- **Amendment:** Each refusal is its own call. The real function rejects the bad input. A copy of the module with that call deleted accepts the same input and is failed by a behavioural test.

## 3. Corrective addendum

This addendum governs Wave 2. The prompt remains the unamended source of record.

1. Prove the prompt hash, then implement only action 3 and the ten listing images in action 4.
2. Design tokens are typed data for palette, typography, spacing, cards, device frames, icons, hero layout, hub slide, colour options, how it works, device compatibility, and PDF pages. A CSS emitter turns a validated token set into one stylesheet. Validation refuses a missing required section and a text pair below contrast 4.5.
3. The ten images follow the prompt order, which is `IMAGE_ROLES`. Each frame is HTML/CSS/SVG rendered by headless Playwright at a fixed viewport and device scale factor 1. Visible text is the A10 image-strip line for that role, plus the fixture screenshot for that role. The page count and the five hubs are the ones A10 already bound to the built facts.
4. Before any PNG is returned, `validate_claims` runs on the copy. Every visible string is placed on that frame and run through `validate_claims` again. Either failure refuses the render. Claim-validation rules are not edited.
5. A screenshot path that is not a file is `missing_screenshot`. A file whose SHA-256 is outside the caller-supplied allow-list is `unknown_screenshot`. Both refuse the render.
6. The same inputs produce the same PNG hash. The font file is vendored. Remote URLs are aborted. No timestamp is drawn.
7. Each image's lineage records product id, spec version, build version, source screenshot hashes, merchandising version, template version, output hash, width, height, and QA status `passed`. A higher spec version, with the same copy and the same screenshots, changes the lineage and the output hash.
8. Do not render video or PDFs. Do not acquire live screenshots. Do not inject or validate links. Do not write S3 or a storage URI. Do not link the workflow. Do not register or commission A10 or A11. Do not edit A07, A08, or A09. Leave the video, PDF, screenshot, link, and generic renderer scaffolds untouched.
9. Do not edit the files owned by open pulls #63 and #68, and do not edit `IMPLEMENTATION_STATE.json`. Exit 78 stays HELD. Session 08 stays inactive. Do not print the session exit code.
10. Killing tests: deleting the missing-key check, the contrast check, the missing-screenshot check, the unknown-screenshot check, the unvalidated-copy check, or the unclaimed-text check accepts the input that the real function refuses.

## 4. Deferrals

| Finding | Owner | Reason |
|---|---|---|
| Short video, README/access PDF, free-gift PDF | Later Session 08 wave | Operator slice is listing images |
| Live screenshot acquisition | Later Session 08 wave | S-01; this wave uses fixture files |
| Link injection and validation | Later Session 08 wave | Operator slice |
| Storage URI and S3 | Later Session 08 wave | F-03 |
| Workflow linkage and successor draft job | Later Session 08 wave | Operator slice |
| Action 11 commissioning | Operator decision after implementation | A10 and A11 stay DESIGNED |
| Action 12 session exit code and the five control-file close | Session 08 close | This wave is not the close |
| Product-design visual sign-off of rendered marketing art | Session 08 close | Tokens and templates are testable here; the close inspects final art |
| Exit 78 | Unchanged | Operator instruction |
| Parked claim-validation publishers and over-refusals from #69 | Unchanged | This wave does not edit `claim_validation.py` |
