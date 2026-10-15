# Session 08 Prompt Integrity Review — W8 Etsy draft fixture

**Date:** 2026-10-15
**Prompt:** `prompts/implementation/11_SESSION_08_MERCHANDISING_AND_ASSET_FACTORY.md`
**Verified SHA-256:** `a7a406cecd9c93efdec1045f394b911e614cd79366840e33d5c53d9968f7cd33`
**Workbook authority:** appendix row for this prompt (5,092 bytes, 236 lines)
**Scope:** Action 9 only, the fixture path that ends with `CREATE_ETSY_DRAFT` ready. Action 8 stays parked. Do not activate Session 08. Do not commission A10, A11, or A13.

The prompt file is not amended. This record is the corrective addendum. It does not overwrite the Wave 0 through Wave 7 records.

## 1. Prompt authenticity

**Status:** VERIFIED

The extracted file's SHA-256 equals `a7a406cecd9c93efdec1045f394b911e614cd79366840e33d5c53d9968f7cd33`. The prompt stays the unamended source of record.

## 2. Three-dimensional review

The operator instruction is the fixture-only path through `CREATE_ETSY_DRAFT`. The Etsy client is injected and refuses unless a fixture transport is present. No production Etsy, no Notion, and no live HTTP. Open pulls #63 and #68 are the only open pulls. Their files stay untouched.

### Fidelity

**Verdict:** CONDITIONAL APPROVE.

**F-01 [HIGH] — The prompt's chain is not a licence to finish the session**

- **Prompt lines:** 167–181 and 215–229.
- **Authority:** D-0032 keeps Session 08 inactive. `current_session` stays 7. `state_revision` stays 64. Exit 78 stays HELD. A10, A11, and A13 stay `DESIGNED`.
- **Consequence of literal execution:** Commissioning the agents and printing `SESSION_08_MERCHANDISING_AND_ASSETS_COMPLETE` would claim the session is finished.
- **Amendment:** Prove the chain with fixture receipts and stop at a draft that is ready. Do not edit `IMPLEMENTATION_STATE.json`. Do not print the session exit code.

**F-02 [HIGH] — `CREATE_ETSY_DRAFT` names a prompt step, not a second job vocabulary**

- **Prompt lines:** 181. Session 03's addendum already voided the prompt's example job names.
- **Authority:** `config/workflows.yaml` names `DraftListingJob` and `ETSY_DRAFT_WRITE`. This wave does not add a parallel map and does not emit a live `DRAFT_CREATED` event.
- **Consequence:** A second successor table would fork the orchestrator.
- **Amendment:** The fixture result is `ready` with `state=draft`. It is not an orchestrator event and it does not publish.

**F-03 [HIGH] — Action 8 is still live object storage**

- **Prompt lines:** 157–165.
- **Authority:** The operator parked S3. W7's storage URI stays `fixture://`.
- **Amendment:** Do not add an S3 client, a signed URL, or a cleanup of published evidence.

### Safety and executability

**Verdict:** CONDITIONAL APPROVE.

**S-01 [HIGH] — A default Etsy client would open a socket**

- **Prompt lines:** 181 and the Session 09 draft adapter, which this wave does not implement.
- **Authority:** No production Etsy and no live HTTP. The verifier runs with non-loopback sockets blocked and fake `ETSY_*` tokens set.
- **Consequence:** Reading `ETSY_ACCESS_TOKEN` and calling `https://openapi.etsy.com` or `https://api.etsy.com` performs the live write this wave is not allowed to perform.
- **Amendment:** The client has no default transport. A missing transport raises `fixture_transport` before any socket. The client never reads `ETSY_*`. The only I/O is the injected fixture transport. Publish and activate are not methods.

**S-02 [HIGH] — Draft creation measured from the Shop Listing API, not from a guessed URL**

- **Authority:** Etsy Open API v3 Shop Listing document, generated from `https://www.etsy.com/openapi/generated/oas/3.0.0.json`, `x-last-validated` 2026-05-30. `createDraftListing` is `POST /v3/application/shops/{shop_id}/listings`. `getListingsByShop` is `GET` on that same path. Its `state` query defaults to `active`, and the enum includes `draft`. `updateListing` is `PATCH /v3/application/shops/{shop_id}/listings/{listing_id}` and its body `state` is `active` or `inactive`. Setting a draft to `active` publishes the listing.
- **Amendment:** The allowlist is exactly those two method and path pairs. `GET` is sent with `state=draft` only. `PATCH`, including `state=active`, is refused before the transport. The create body has no `state` field. A response whose `state` is not `draft` is refused and is not recorded.

**S-03 [HIGH] — Etsy has no client idempotency key**

- **Authority:** `createDraftListing` does not take an idempotency key. A retry that only compares titles will adopt a decoy.
- **Amendment:** The ledger key is `(spec_version, fixture_hash)`. The client writes `pending` before the transport call. On retry it adopts a shop listing only when a full description line equals `mm-draft:{spec_version}:{fixture_hash}`. Title is not a key. A crash after the transport stores the draft and before `record` leaves `pending`, and the next call adopts that listing.

### Gameability

**Verdict:** CONDITIONAL APPROVE.

**G-01 [HIGH] — One shared condition can hide which gate failed**

- **Cheap fake:** Skip product QA, claims, screenshots, the ten images, the video, the two delivery PDFs, link validation, or asset QA, and still return ready.
- **Amendment:** Each of those checks raises its own gate. Deleting that check fails a different test.

**G-02 [HIGH] — Returning the first title match looks like idempotency**

- **Cheap fake:** On retry, return the shop listing whose title equals the request.
- **Amendment:** A same-title decoy with no marker, and a same-title decoy with a different marker, are not adopted. A line that merely contains the marker is not adopted. A recorded ledger row does not call the transport again.

**What the prompt already gets right**

- The chain ends when the draft is ready, not when it is published (line 181).
- Claims stay fact-bound. This wave does not relax them.
- Asset QA stays in front of the draft. A stale lineage is not a ready draft.

## 3. Corrective addendum

This addendum governs Wave 8. The prompt remains the unamended source of record.

1. Prove the prompt hash, then implement the fixture path through `CREATE_ETSY_DRAFT` and the carried #75 simplifications.
2. `prepare_etsy_draft` refuses, in order, a product QA other than `passed`, failed claims, no screenshot, a listing-image count other than `len(IMAGE_ROLES)`, a walkthrough count other than one, a delivery-PDF role set other than `readme` and `free_gift`, failed links, and any asset `split_current` marks stale. The next call is the draft client.
3. `EtsyDraftClient` takes a fixture transport. `None` raises `fixture_transport` and does not open a socket, whether or not `ETSY_API_KEY`, `ETSY_SHARED_SECRET`, `ETSY_ACCESS_TOKEN`, `ETSY_REFRESH_TOKEN`, or `ETSY_SHOP_ID` is set. The shop id in the path is the argument, not the environment.
4. The measured allowlist is `GET` and `POST` on `/v3/application/shops/{shop_id}/listings`. A path that is not that template raises `off_list` in the path check. A method other than those two, on that template, raises `off_list` in the allowlist check. `PATCH` with `state=active` is that method check. `GET` on `/listings/{listing_id}` is that path check. `updateListing` needs both the extra path segment and `PATCH`, so neither check alone can publish. The class has no `publish` and no `activate`. The create body has no `state` field. `GET` query is exactly `state=draft`. A listing whose `state` is not `draft` is not adopted and is not recorded.
5. The ledger key is spec version plus the fixture hash of the draft fields. `pending` is written before `exchange`. A recorded row returns without a second call. A crash after the transport has stored the draft is adopted by the exact marker line. Title is ignored. A longer line that contains the marker is not a match.
6. `_defer_page_annots` defers only when the object number is in the page-tree set. `_source_blocked` is `resolved.kind != "screenshot"` after the unknown-source return. Re-measure the kill counts those collapses change.
7. Do not edit the files owned by open pulls #63 and #68, and do not edit `IMPLEMENTATION_STATE.json`. Exit 78 stays HELD. Session 08 stays inactive. Do not print the session exit code. Action 8 stays parked.

## 4. Deferrals

| Finding | Owner | Reason |
|---|---|---|
| S3 adapter, immutable paths, signed retrieval, cleanup | Action 8 | Operator park. The storage URI stays `fixture://` |
| Image, file, and video upload operations | Session 09 | Not on the measured create-draft pair. `uploadListingImage` and the file and video posts stay out of this allowlist |
| `updateListing`, publish, and activate | Session 09 | The measured `PATCH` publishes when `state=active`. This client does not have that method |
| Commission A10, A11, and A13 | Action 11 | Operator hold |
| Session exit code and Exit 78 | Session exit | Operator hold |
| Same-host http hop, punycode, `file:` allow, sendBeacon, spelled-out emails, `_prepare` non-ASCII, raster text | Later | Still parked from W7 |

## 5. Final verdict

**CONDITIONAL APPROVE.** Critical and high findings are resolved by the numbered addendum above. Implementation of action 9 may start. The prompt file stays unamended.
