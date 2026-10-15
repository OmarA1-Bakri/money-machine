# Session 08 Prompt Integrity Review — asset storage

**Date:** 2026-10-15
**Prompt:** `prompts/implementation/11_SESSION_08_MERCHANDISING_AND_ASSET_FACTORY.md`
**Verified SHA-256:** `a7a406cecd9c93efdec1045f394b911e614cd79366840e33d5c53d9968f7cd33`
**Workbook authority:** appendix row for this prompt (5,092 bytes, 236 lines)
**Scope:** Action 8 only. Do not activate Session 08. Do not commission A10 or A11.

The prompt file is not amended. This record is the corrective addendum.

## 1. Prompt authenticity

**Status:** VERIFIED

The extracted file's SHA-256 equals `a7a406cecd9c93efdec1045f394b911e614cd79366840e33d5c53d9968f7cd33`. The prompt stays the unamended source of record.

## 2. Three-dimensional review

Action 7 is merged. The storage modules are empty scaffolds. Action 9's fixture Etsy draft is an open pull request on another branch. This wave does not edit that branch's files.

### Fidelity

**Verdict:** CONDITIONAL APPROVE.

**F-01 [HIGH] — Action 8 names five storage behaviours and the modules are empty**

- **Prompt lines:** 157–165. Local runtime storage, an S3-compatible production adapter, immutable versioned paths, signed or internal retrieval, and cleanup of superseded temporary renders that keeps published evidence.
- **Authority:** `src/money_machine/integrations/storage/` is three scaffold files. Lineage already names `fixture://{product_id}/{spec_version}/{output_sha256}` and does not write bytes.
- **Consequence of literal execution:** A comment that storage "comes later" leaves a second publish of the same hash able to replace bytes, and a cleanup able to delete a published object.
- **Amendment:** A local store writes under a caller-supplied root. A simulation S3 store keeps the same versioned key in memory. The path is `{product_id}/{spec_version}/{sha256}`. The same bytes at that key are idempotent. Different bytes are a collision. Cleanup deletes only superseded temporary objects.

### Safety and executability

**Verdict:** CONDITIONAL APPROVE.

**S-01 [HIGH] — "S3-compatible adapter for production" can be read as a live network call**

- **Prompt lines:** 159–163.
- **Authority:** No live HTTP, no provider credentials, Exit 78 HELD. Development and test force simulation for every provider.
- **Amendment:** `draft`, `live`, and any other mode raise before a store exists. The simulation store does not import a network client and does not read credentials. Signed retrieval is a local token. Local retrieval is an `internal:` name. Neither is fetched.

**S-02 [HIGH] — Cleanup can be pointed at published evidence**

- **Prompt lines:** 165.
- **Amendment:** `discard` of a published URI raises `storage published` and leaves the bytes. Cleanup walks temporary objects only and skips the keep hash.

### Gameability

**Verdict:** CONDITIONAL APPROVE.

**G-01 [HIGH] — One shared refusal hides which check was deleted**

- **Cheap fake:** Drop the mode check, the hash check, the collision check, or the published-discard check. A test that only says "something was refused" stays green.
- **Amendment:** Each deletion below fails a different test. The messages differ where two checks would otherwise raise the same way.

## 3. Corrective addendum

1. Prove the prompt hash, then implement fixture storage only.
2. `LocalAssetStore` writes temporary and published bytes under an absolute directory that is not a symlink. `SimS3AssetStore` stores the same keys in memory.
3. The published local URI is `fixture://{product_id}/{spec_version}/{sha256}`. The temporary local URI is `temp://` with the same tail. S3 published is `s3://simulation/` and S3 temporary is `s3://temporary/`.
4. A mode other than `simulation` raises. `draft` and `live` raise `storage live`. Any further mode raises `storage mode`.
5. The claimed hash must be 64 lowercase hex characters and must be the SHA-256 of the bytes. A spec version is an int of at least 1, and a bool is refused.
6. Creating a new file uses `O_EXCL`. An existing regular file with the same bytes is success. Different bytes raise `storage collision` and are not written. A symlink file raises `storage symlink`.
7. Cleanup removes temporary objects for that product and spec except the keep hash. Discarding a published URI raises `storage published`.
8. Local `signed_retrieval` raises `storage signed`. S3 `internal_retrieval` raises `storage internal`. An S3 token for one URI does not read another. A missing object has no token.
9. Do not edit `IMPLEMENTATION_STATE.json`, `.github/workflows/ci.yml`, or the files of open pulls #63, #68, and #77. Exit 78 stays HELD. Session 08 stays inactive. Do not print the session exit code. Do not call S3, Etsy, or Notion.

## 4. Deferrals

| Finding | Owner | Reason |
|---|---|---|
| Live S3 transport, credentials, and real signed URLs | Later, after commissioning | This wave refuses every mode except simulation |
| Workflow linkage and `CREATE_ETSY_DRAFT` | Action 9, open pull #77 | Another branch owns that slice |
| Commission A10 and A11 | Action 11 | Operator hold |
| Session exit code and Exit 78 | Session exit | Operator hold |
| Same-host http hop, punycode, `file:` allow, sendBeacon, spelled-out emails, raster text | Later | Still parked from link validation |

## 5. Final verdict

**CONDITIONAL APPROVE.** Critical and high findings are resolved by the numbered addendum above. Implementation of action 8 may start. The prompt file stays unamended.

## 6. Measurement

The spec segment is one path layout. Removing it from `object_uri` fails the spec-bump test and both cleanup tests, because those tests look in the spec directory the URI no longer names. The other measured guards fail one test each. The `storage place` raise after `refuse_collision` survives; the collision helper is the kill. Counts are in `docs/control/IMPLEMENTATION_LOG.md`.
