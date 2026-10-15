# Session 08 Prompt Integrity Review — W7 artifact lineage

**Date:** 2026-10-15
**Prompt:** `prompts/implementation/11_SESSION_08_MERCHANDISING_AND_ASSET_FACTORY.md`
**Verified SHA-256:** `a7a406cecd9c93efdec1045f394b911e614cd79366840e33d5c53d9968f7cd33`
**Workbook authority:** `hands-off-money-machine-full-implementation-workbook.md` appendix row for this prompt (5,092 bytes, 236 lines)
**Scope:** Wave 7 only. Action 7, fixture lineage records for assets that already exist. Live storage stays parked. Four carried fixes from #74 are in scope, each in its own commit. No other action.

The prompt file is not amended. This record is the corrective addendum. It does not overwrite the Wave 0 through Wave 6 records.

## 1. Prompt authenticity

**Status:** VERIFIED

- The extracted file's SHA-256 equals the workbook appendix value `a7a406cecd9c93efdec1045f394b911e614cd79366840e33d5c53d9968f7cd33`.
- The workbook copy between `COPY START` and `COPY END` contains that same extract (5,092 bytes, 236 lines).
- The prompt stays the unamended source of record.

## 2. Three-dimensional review

The operator instruction for this wave is action 7. Each asset stores product ID, ProductSpec version, build version, source screenshots, merchandising version, renderer template version, hash, dimensions or page count, QA status, and a storage URI. A later product change invalidates stale dependent assets. The work stays fixture-only. The four #74 carries are the seen-key and second-role kill split, a deep `/Kids` chain returning `malformed`, graph URIs outside a link `/A` tied to the accepted list, and a clearer page `/AA` refusal.

### Fidelity

**Verdict:** CONDITIONAL APPROVE. Three high findings, resolved by the addendum.

**F-01 [HIGH] — The prompt's full session is not this wave**

- **Prompt lines:** 1–236, especially actions 1–6, 8–12, and the required exit code at line 229.
- **Authority:** The operator slice is action 7 plus the four named #74 carries. D-0032 keeps Session 08 inactive. `current_session` stays 7. A10 and A11 stay `DESIGNED`. `IMPLEMENTATION_STATE.json` stays at revision 64. Exit 78 stays HELD.
- **Consequence of literal execution:** Writing S3, linking the workflow, commissioning A11, and printing `SESSION_08_MERCHANDISING_AND_ASSETS_COMPLETE` would claim the session is finished.
- **Amendment:** Implement fixture artifact lineage and the four carries only. Do not print the session exit code. Do not activate Session 08. Do not edit `IMPLEMENTATION_STATE.json`.

**F-02 [HIGH] — "Storage URI" is not a licence to add the S3 adapter**

- **Prompt lines:** 140–165. Action 7 names a storage URI. Action 8 is local storage plus an S3-compatible adapter, immutable paths, signed retrieval, and cleanup.
- **Authority:** The operator slice is action 7. W6 parked storage URI and S3 under action 8. Fixture-only. No production Notion or Etsy.
- **Consequence:** A literal S3 client would be a new provider adapter, a live credential path, and a second storage engine beside the fixture record.
- **Amendment:** The URI is `fixture://` and is checked against the product, spec, build, kind, and hash. `s3://`, `http://`, `https://`, and `file://` are `live_storage`. Action 8 stays parked.

**F-03 [HIGH] — Rewriting the bound PNG, PDF, or video lineage would move the W4 golden**

- **Prompt lines:** 142–154, applied to bytes W2, W3, W4, and W5 already hash.
- **Authority:** W4 pinned `6318854297cd5d316fdf4c579a73f188ec5f1e2089745534aa9d4ca6245fe248`. W5 and W6 left that pin in place.
- **Consequence:** Splicing the new fields into `mm-lineage` changes the Matroska suffix and the listing PNG bytes.
- **Amendment:** The common record is a sidecar. Renderers keep their existing bound text. The record is built from the same fields those lineages already carry, plus the fixture URI.

**What the prompt already gets right**

- The ten stored fields and the invalidation rule are the action 7 list (lines 142–155).
- Claims stay fact-bound. This wave does not relax the rejection classes.
- Tokens, listing images, delivery PDFs, the silent video, screenshots, and link validation already exist. This wave does not rebuild them.

### Safety and executability

**Verdict:** CONDITIONAL APPROVE. Two high findings, resolved by the addendum.

**S-01 [HIGH] — Open pull requests #63 and #68 own the control and CI files**

- **Authority:** Do not edit `.github/workflows/ci.yml`, `AGENTS.md`, `CLAUDE.md`, `src/money_machine/control/**`, `src/money_machine/cli/s07_navigation_guard.py`, `docs/architecture/S07_EVIDENCE_RECORD.md`, `docs/control/IMPLEMENTATION_STATE.json`, `tests/bootstrap/**`, `tests/fixtures/control/**`, or `tests/unit/agents/test_notion_product_builder_*.py`.
- **Consequence:** Editing any of those collides with the open pulls.
- **Amendment:** This wave does not edit them. Do not commission A10 or A11. Do not push `build/full-automation`.

**S-02 [HIGH] — Invalidation must not delete bytes or call a provider**

- **Prompt lines:** 155 and 163. A product change invalidates stale dependents. Action 8 mentions cleanup of temporary renders.
- **Consequence:** Deleting a PNG, or calling Notion or Etsy to retract a listing, is a live mutation this wave is not allowed to perform.
- **Amendment:** Invalidation returns a new record whose QA status is `stale`. It does not delete files, does not open a socket, and does not touch another product.

**Executability**

- Screenshot, listing-image, PDF, and video lineages already store most of the action 7 fields. The gap is one record shape, the fixture URI, and dependency invalidation.
- The #74 carries stay inside `pdf_objects.py`, `link_validation.py`, `gift_links.py`, and the link and gift tests. They do not change the committed screenshot, PDF, or video bytes.

### Gameability

**Verdict:** CONDITIONAL APPROVE. The acceptance criteria in the pull request are the ungameable form of this wave.

**G-01 [HIGH] — A record compared with itself does not store the ten fields**

- **Cheap fake:** `assert record == record`, or copy `template_version` into `merchandising_version`.
- **Amendment:** The test builds the expected product id, spec version, build version, screenshot hashes, merchandising version, template version, hash, dimensions or page count, QA status, and URI from literals. The merchandising version and the template version differ. A PDF stores a page count and no dimensions. A screenshot stores dimensions and no page count.

**G-02 [HIGH] — Staling only the edited row leaves a dependent passed**

- **Cheap fake:** Compare `spec_version` on the asset that changed and return every other row untouched.
- **Amendment:** An older spec of this product is `stale`. The current spec stays `passed`. Another product at an older spec stays `passed`. A current asset that depends on a stale asset, including through one intermediate asset, is `stale`.

**G-03 [HIGH] — A host check is not the accepted link list**

- **Prompt lines:** not in action 7. Carried from #74.
- **Cheap fake:** `refuse_graph_uri` returns none for any on-host URI. An unreferenced `/S /URI` whose host is allowed and whose path is not in the accepted list stays green.
- **Amendment:** After the host check, a graph URI outside a link `/A` must equal an accepted string. The off-host row stays `host`. The on-host row that is not accepted is `link_mismatch`.

## 3. Corrective addendum

This addendum governs Wave 7. The prompt remains the unamended source of record.

1. Prove the prompt hash, then implement fixture artifact lineage, plus the four #74 carries. Each carry is its own commit, and the lineage work is not in those commits.
2. The seen set stays `(object number, role)`. Re-entering an action object (`/S` present, no `/Subtype`) raises `pdf seen key`, which validation maps to `malformed`. That row dies when the seen set is keyed by object number only. It stays green when the second-role check allows Widget.
3. Every `/Annots` array is subtype-checked at the parent, including an array that is not the page's own `/Annots`. A Widget reached again under `/Annots` after `/Outlines` is `malformed`. That row dies when the second-role check allows Widget. It stays green when the seen set is keyed by object number only.
4. A `/Kids` chain deeper than 64 raises `pdf kids depth`. `refuse_gift_link_annotations` returns `malformed` for that message. Other parser errors on that function stay `paid_checkout`. `validate_pdf_links` on the same chain returns `malformed`. A deep `/Info` chain stays `paid_checkout`.
5. `refuse_graph_uri` takes the accepted URI set. A graph URI that is not the link action's own `/A` and that fails the host check stays `host`. One that passes the host check and is not an accepted string is `link_mismatch`.
6. A page whose extra key is `/AA` and whose `/AA` contains a `/URI` raises `pdf page /AA`. Validation maps that message to `page_aa`. A page `/AA` without a URI, and a page missing `/Tabs`, stay `malformed` from `pdf page keys`.
7. `ArtifactLineage` stores product id, spec version, build version, source screenshot hashes, merchandising version, template version, content hash, either dimensions or a page count, QA status, and a `fixture://` storage URI. The URI is the canonical string of those coordinates. A live scheme is `live_storage`. A screenshot's source tuple is its own hash. A listing image or walkthrough with no source screenshot is refused.
8. `invalidate_product_change` marks this product's older spec `stale`, then any asset whose dependency URI is stale, including a transitive dependent. The current spec with no stale dependency stays `passed`. Another product stays `passed`. QA status is the only field that changes. No file is deleted.
9. Do not edit the files owned by open pulls #63 and #68, and do not edit `IMPLEMENTATION_STATE.json`. Exit 78 stays HELD. Session 08 stays inactive. Do not print the session exit code. Do not change the committed screenshot, PDF, or video goldens.

## 4. Deferrals

| Finding | Owner | Reason |
|---|---|---|
| Same-host `http` hop | Parked | Operator. A same-host hop stays allowed |
| Punycode and uppercase on-host URIs | Parked | Operator. Host admission stays the existing secret-host check |
| Deleting the URI-stream `raise` | Parked | Operator. The equivalent survivor still passes |
| `file:` allow | Parked | Operator. The route still allows only the pinned template |
| `sendBeacon` via `set_content` with JavaScript on | Parked | Operator. Production capture leaves JavaScript off |
| Spelled-out `at ... dot com` emails | Parked | Operator |
| Non-ASCII refusal inside `_prepare` | Parked | Operator. The raw allowlist on `refuse_fixture_value` stays the fixture gate |
| Text inside raster images | Parked | Operator |
| S3 adapter, signed retrieval, and cleanup | Later Session 08 wave | Action 8. This wave stores a fixture URI only |
| Workflow linkage and commissioning | Later Session 08 wave | F-01 |
| Session exit code | Later, at a real session exit | F-01 |
| Exit 78 | Held | Operator instruction |
| Cross-platform video hash | Later wave | W4 park |
| Trailer tampering after the Matroska bytes | Later wave | W4 park |
| Defanged hosts | Later wave | W3 park |
| José and Zoë in the gift name or community | Later wave | W3 park |
| Bare `127.1`, `0x7f000001`, and `2130706433` | Later wave | W3 park |
| Deleting the URI loop while `if count:` stays | Later wave | W3 park |
| Newest xref only, with no `/Prev` | Later wave | W3 park |
| #69 publishers and over-refusals | Later wave | Not this slice |
| W2 survivors other than the font edge space | Later wave | Not this slice |
| Chromium m153 writes no XMP and no `/ID` | Later wave | PDF bytes already pinned |

## 5. Final verdict

**CONDITIONAL APPROVE.** Critical and high findings are resolved by the numbered addendum above. Implementation of Wave 7 may start. The prompt file stays unamended.
