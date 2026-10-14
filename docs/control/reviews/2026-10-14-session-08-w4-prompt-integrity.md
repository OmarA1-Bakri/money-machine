# Session 08 Prompt Integrity Review — W4 short video

**Date:** 2026-10-14
**Prompt:** `prompts/implementation/11_SESSION_08_MERCHANDISING_AND_ASSET_FACTORY.md`
**Verified SHA-256:** `a7a406cecd9c93efdec1045f394b911e614cd79366840e33d5c53d9968f7cd33`
**Workbook authority:** `hands-off-money-machine-full-implementation-workbook.md` appendix row for this prompt (5,092 bytes, 236 lines)
**Scope:** Wave 4 only. The fixture short walkthrough in action 4. Design tokens, listing images, and delivery PDFs already merged. No other action.

The prompt file is not amended. This record is the corrective addendum. It does not overwrite the Wave 0, Wave 1, Wave 2, or Wave 3 records.

## 1. Prompt authenticity

**Status:** VERIFIED

- The extracted file's SHA-256 equals the workbook appendix value `a7a406cecd9c93efdec1045f394b911e614cd79366840e33d5c53d9968f7cd33`.
- The workbook copy between `COPY START` and `COPY END` contains that same extract.
- The prompt stays the unamended source of record.

## 2. Three-dimensional review

The operator instruction for this wave is one silent fixture walkthrough of about 30 seconds, plus the cheap carried fixes from #70 and #71. Live screenshot acquisition, link opening, storage, workflow linkage, and commissioning are not this wave.

### Fidelity

**Verdict:** CONDITIONAL APPROVE. Three high findings, resolved by the addendum.

**F-01 [HIGH] — The prompt's full session is not this wave**

- **Prompt lines:** 1–236, especially actions 1–3, 4 (images and the two PDFs), 5–12, and the required exit code at line 229.
- **Authority:** The operator slice is the short video. D-0032 keeps Session 08 inactive. `current_session` stays 7. A10 and A11 stay `DESIGNED`. `IMPLEMENTATION_STATE.json` stays at revision 64.
- **Consequence of literal execution:** Re-rendering the ten images and both PDFs, capturing live Notion screenshots, opening variant links, writing S3, linking the workflow, commissioning A11, and printing `SESSION_08_MERCHANDISING_AND_ASSETS_COMPLETE` would claim the session is finished.
- **Amendment:** Implement the silent walkthrough only, plus the carried fixes that are cheap. Do not print the session exit code. Do not activate Session 08. Do not edit `IMPLEMENTATION_STATE.json`.

**F-02 [HIGH] — Beat sentences are not paint-safe, and the prompt does not re-check them**

- **Prompt lines:** 91–100. The existing beats are `Dashboard output: {encoded}.`, `Notification panel: {encoded}.`, `Hubs: {names}.`, `Variants: {names}.`, and `Duplicate the template. Access link: {url}.`
- **Authority:** Chapter 15.2 admits only free links. The gift PDF already refuses a paid or checkout URL and characters outside the gift allowlist. Action 2 already requires every claim to reference a ProductFact.
- **Consequence:** Painting the stock beat text would put a colon, a pipe, or `https://fixture.notion.site` on screen. A green duration test would still pass.
- **Amendment:** On-screen captions are separate templates of the same claims. They cite the dashboard, the hubs, the variants, and the access fact, and they do not paint the access URL. `validate_claims` runs on the listing copy and again with those captions attached as `pdf_blocks`. Every painted string, including an injected caption, also goes through `refuse_gift_charset` and `refuse_paid_checkout` and fails closed.

**F-03 [HIGH] — Artifact lineage in the prompt includes a storage URI this video does not have**

- **Prompt lines:** 140–155. Storage URI and S3 are action 8.
- **Authority:** Operator slice. The record still has to carry product id, spec version, build version, source screenshot hashes, merchandising version, template version, output hash, and QA status.
- **Consequence:** Inventing a storage URI would pretend action 8 is done. Omitting the screenshot hashes would let a fixture swap keep the same recorded inputs.
- **Amendment:** Lineage records those fields plus the pinned width, height, fps, scene order, and per-scene frame counts. The same text is appended after the container. QA status on a returned video is `passed`. No storage URI. The output hash is of the returned bytes and is not written inside them.

**What the prompt already gets right**

- The walkthrough is about 30 seconds, has no voiceover, and uses the playbook beats in order (lines 91–100).
- Claims stay fact-bound (lines 38–52). This wave does not relax the rejection classes.
- Tokens, listing images, and delivery PDFs already exist. This wave reuses them.

### Safety and executability

**Verdict:** CONDITIONAL APPROVE. Three high findings, resolved by the addendum.

**S-01 [HIGH] — A browser capture or a system ffmpeg is not a fixture render**

- **Prompt lines:** 76 and 91–100.
- **Authority:** Fixture-only. No live HTTP, no Notion, no Etsy. CI installs no system ffmpeg. Open pull #68 owns `.github/workflows/ci.yml`, so this wave cannot add a package there.
- **Consequence:** Playwright video, or `/usr/bin/ffmpeg`, either leaves the fixture boundary or fails closed on CI for the wrong reason.
- **Amendment:** Frames are drawn in process from the committed listing-screenshot PNGs and the W2 token colours. The encoder is the `imageio-ffmpeg==0.6.0` wheel already locked for dev. No browser is launched for the video. No remote URL is fetched.

**S-02 [HIGH] — Open pull requests #63 and #68 own the control and CI files**

- **Authority:** Do not edit `.github/workflows/ci.yml`, `AGENTS.md`, `CLAUDE.md`, `src/money_machine/control/**`, `src/money_machine/cli/s07_navigation_guard.py`, `docs/architecture/S07_EVIDENCE_RECORD.md`, `docs/control/IMPLEMENTATION_STATE.json`, `tests/bootstrap/**`, `tests/fixtures/control/**`, or `tests/unit/agents/test_notion_product_builder_*.py`.
- **Consequence:** Editing any of those collides with the open pulls.
- **Amendment:** This wave does not edit them. Do not commission A10 or A11. Do not register an implementation for either agent.

**S-03 [HIGH] — An unpinned encoder is not a deterministic hash**

- **Prompt lines:** 197–198, applied to the video render.
- **Consequence:** A default x264 or a system ffmpeg build writes a different file on the next machine. A test can then pin nothing, or pin a hash the code itself just computed.
- **Amendment:** Duration, resolution, fps, scene order, and per-scene frame counts are constants. The encoder is FFV1 in Matroska with bitexact flags, one thread, and a pinned epoch. The same inputs in this process produce the same bytes for this wheel. Tests recompute screenshot and output hashes with `hashlib` on the fixture files and the returned bytes. If that encoder cannot be made deterministic, the wave says so and does not report a green hash.

**Executability**

- A10 already returns a `ListingCopy` whose `video_sequence` is `VIDEO_BEATS`. This wave reads that copy. It does not construct `ListingPackage`.
- `validate_claims` only accepts the stock beat templates on `video_sequence`. Caption templates are attached as `pdf_blocks`, where the template id is the required template. A10 does not emit those blocks.
- The carried fixes are the font-family edge spaces, the letter-prefixed dotted address, the marked-last IPv4 alternative, a `/Kids` link that is actually found, and a deep `/Info` chain that raises `DeliveryPdfRefusal`.
- `imageio-ffmpeg==0.6.0` is a dev dependency. `playwright` stays a dev dependency and is not used by the video path.

### Gameability

**Verdict:** CONDITIONAL APPROVE. The acceptance criteria in the pull request are the ungameable form of this wave.

**G-01 [HIGH] — A 30-byte buffer named `.mkv` satisfies "about 30 seconds"**

- **Cheap fake:** Return a stub and assert a plan field equals 30.
- **Amendment:** Duration, width, height, and fps are parsed from the container with the bundled ffmpeg. The render refuses a duration outside 28–32 seconds and a frame that is not 160×90 at 10 fps. Scene pixels are read back from the decoded frames. Deleting either container check returns the file whose probe is wrong.

**G-02 [HIGH] — A refusal that is only asserted by reading the source is not a kill**

- **Cheap fake:** A test searches the file for `raise` and never feeds a missing screenshot, a bad caption, or a reordered scene.
- **Amendment:** Each refusal is its own call. The real function rejects the bad input. A copy of the module with that call deleted accepts the same input. The kill count below is the deselected suite, so the meta-tests that only exec a mutant are not the evidence.

## 3. Corrective addendum

This addendum governs Wave 4. The prompt remains the unamended source of record.

1. Prove the prompt hash, then implement only the silent walkthrough, plus the carried #70 and #71 fixes that are cheap.
2. Scenes, in order, are dashboard, notification panel, strongest hubs, colour options, and duplication/access. There is no audio stream.
3. Resolution is 160×90. Frame rate is 10. Per-scene frame counts are 60, 60, 80, 50, and 50. The container is 30.0 seconds, inside 28–32.
4. Screenshots are the committed fixture PNGs: hero, overview, hub 1–5, colour options, and how it works. Remote URLs are not fetched.
5. On-screen captions are `video_dashboard_caption`, `video_notification_caption`, `video_hubs_caption`, `video_variants_caption`, and `video_duplication_caption`. The duplication caption cites access and does not paint the URL. `validate_claims` runs before a video is returned. Every painted string also passes the gift charset and the gift URL refusal.
6. The same inputs produce the same bytes on `imageio-ffmpeg==0.6.0`. Lineage records product id, spec version, build version, the nine screenshot hashes, merchandising version, template version, output hash, width, height, fps, scene order, scene frames, and QA status `passed`. A higher spec version changes the bytes. No storage URI.
7. Carry these fixes: leading or trailing space in `font_family` is refused and an internal space still loads; `v1.2.3.4` still renders; `1.2.0x7f` is refused; a `/Link` behind indirect `/Kids` is found; a deep `/Info` chain returns `paid_checkout` and the gift render raises `DeliveryPdfRefusal`.
8. Do not acquire live screenshots. Do not open or repair links. Do not write S3 or a storage URI. Do not link the workflow. Do not register or commission A10 or A11. Do not edit A07, A08, or A09.
9. Do not edit the files owned by open pulls #63 and #68, and do not edit `IMPLEMENTATION_STATE.json`. Exit 78 stays HELD. Session 08 stays inactive. Do not print the session exit code.
10. Killing tests: deleting the missing-screenshot check, the unknown-screenshot check, the charset check, the URL check, the unvalidated-copy check, the scene-order check, the scene-marker check, the frame-size check, or the duration check accepts the input that the real function refuses.

## 4. Deferrals

| Finding | Owner | Reason |
|---|---|---|
| Live screenshot acquisition | Later Session 08 wave | S-01 |
| Opening or repairing variant links | Later Session 08 wave | Operator slice is the silent video |
| Storage URI and S3 | Later Session 08 wave | F-03; action 8 |
| Workflow linkage and commissioning | Later Session 08 wave | F-01; D-0032 |
| Session exit code | Later, at a real session exit | F-01 |
| Exit 78 | Held | Operator instruction |
| Whole-document `/OpenAction`, `/AA`, and outline scanning | Later wave | W3 park, not this slice |
| Non-Link URI annotations | Later wave | W3 park |
| Defanged hosts `x . com`, `x[.]com`, `x dot com`, `x.c0m` | Later wave | They render; W3 park |
| José and Zoë in the gift name or community | Later wave | W3 park |
| Bare `127.1`, `0x7f000001`, and `2130706433` | Later wave | They render; W3 park |
| Deleting the URI loop while `if count:` stays | Later wave | W3 park |
| Scan reading only the newest xref, with no `/Prev` | Later wave | W3 park |
| #69 publishers and over-refusals | Later wave | Not named in this operator slice |
| W2 survivors other than the font edge space | Later wave | Only the named #70 font item is carried |
| Contrast nearest-pair wording in the W2 log | Closed as historical | The log is not rewritten |
| Chromium m153 writes no XMP and no `/ID` | Later wave | PDF pinning already landed; not this encoder |
| Hash stability across ffmpeg builds other than this wheel | This wave, documented | S-03; the pin is the locked wheel, not every binary |

## 5. Final verdict

**CONDITIONAL APPROVE.** Critical and high findings are resolved by the numbered addendum above. Implementation of Wave 4 may start. The prompt file stays unamended.
