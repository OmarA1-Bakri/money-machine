# Session 08 Prompt Integrity Review — W7 artifact lineage

**Date:** 2026-10-15
**Prompt:** `prompts/implementation/11_SESSION_08_MERCHANDISING_AND_ASSET_FACTORY.md`
**Verified SHA-256:** `a7a406cecd9c93efdec1045f394b911e614cd79366840e33d5c53d9968f7cd33`
**Workbook authority:** appendix row for this prompt (5,092 bytes, 236 lines)
**Scope:** Action 7 only. Do not activate Session 08. Do not commission A10 or A11.

The prompt file is not amended. This record is the corrective addendum.

## 1. Prompt authenticity

**Status:** VERIFIED

The extracted file's SHA-256 equals `a7a406cecd9c93efdec1045f394b911e614cd79366840e33d5c53d9968f7cd33`. The prompt stays the unamended source of record.

## 2. Three-dimensional review

The operator instruction is to keep building toward a complete app. Action 7 is the next unbuilt slice. Actions 1–6 are already on this branch. Storage, workflow, commissioning, and the session exit stay later.

### Fidelity

**Verdict:** CONDITIONAL APPROVE.

**F-01 [HIGH] — Lineage records exist, but nothing invalidates them**

- **Prompt lines:** 140–155. Each asset stores product id, ProductSpec version, build version, source screenshots, merchandising version, template version, hash, dimensions or page count, QA status, and a storage URI. A later product change invalidates stale dependents.
- **Authority:** Screenshots, listing images, the walkthrough, and delivery PDFs already bind those fields except a storage URI. No function compares a new spec version with those records.
- **Consequence of literal execution:** Adding a comment that lineage is "stored" leaves a spec bump current.
- **Amendment:** Project each existing lineage into one record that includes a fixture storage URI. A spec bump, a different product, a QA status other than `passed`, or a source screenshot that is itself stale, marks that asset stale. The same product and spec stay current.

### Safety and executability

**Verdict:** CONDITIONAL APPROVE.

**S-01 [HIGH] — Action 8 is live object storage, and action 11 commissions agents**

- **Prompt lines:** 157–165 and 201–203.
- **Authority:** No live HTTP, no S3 credentials, Exit 78 HELD, `commissioned_agents` empty. W6 parked storage and commissioning.
- **Amendment:** The storage URI is `fixture://`. Do not call S3, do not write the artifact tables, and do not commission A10 or A11. Do not edit `IMPLEMENTATION_STATE.json`.

### Gameability

**Verdict:** CONDITIONAL APPROVE.

**G-01 [HIGH] — One shared condition can hide which check failed**

- **Cheap fake:** Drop the spec comparison, the product filter, the QA check, or the source walk. A test that only says "something became stale" stays green.
- **Amendment:** Each of those four deletions fails a different test. A matching asset stays current, including when another asset's screenshot is stale. A dependent listed before its source is still stale.

## 3. Corrective addendum

1. Prove the prompt hash, then implement fixture lineage invalidation only.
2. `bind_asset` projects a screenshot, listing image, walkthrough, or delivery PDF. The record carries the action 7 fields. Screenshots have no merchandising version and no source screenshots. Their hash is the screenshot hash. Their dimensions are the crop. PDFs carry page count and no pixel size.
3. The storage URI is `fixture://{product_id}/{spec_version}/{output_sha256}`. It is not an S3 URL.
4. `split_current` keeps assets for other products out of both results. For the named product, a different spec version, a QA status other than `passed`, or a source hash of a stale asset makes that asset stale. The walk repeats so order does not matter. A current asset is returned unchanged.
5. Do not edit the files owned by open pulls #63 and #68, and do not edit `IMPLEMENTATION_STATE.json`. Exit 78 stays HELD. Session 08 stays inactive. Do not print the session exit code.

## 4. Deferrals

| Finding | Owner | Reason |
|---|---|---|
| S3 adapter, immutable paths, signed retrieval, cleanup | Action 8 | Operator park carried from W6. This wave only names a fixture URI |
| Workflow linkage through `CREATE_ETSY_DRAFT` | Action 9 | Later wave |
| Commission A10 and A11 | Action 11 | Operator hold |
| Session exit code and Exit 78 | Session exit | Operator hold |
| Same-host http hop, punycode and uppercase on-host URIs, the URI-stream raise (message pinned to `pdf uri stream`), `file:` allow, sendBeacon, spelled-out emails, `_prepare` non-ASCII, raster text | Later | Still parked. r2 checks resolved roles, measured `/Resources` keys, and the measured `/S` allowlist `{URI}` |

## 5. Final verdict

**CONDITIONAL APPROVE.** Critical and high findings are resolved by the numbered addendum above. Implementation of action 7 may start. The prompt file stays unamended.
