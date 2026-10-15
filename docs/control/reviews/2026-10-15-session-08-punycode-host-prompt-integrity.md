# Session 08 Prompt Integrity Review — punycode host

**Date:** 2026-10-15
**Prompt:** `prompts/implementation/11_SESSION_08_MERCHANDISING_AND_ASSET_FACTORY.md`
**Verified SHA-256:** `a7a406cecd9c93efdec1045f394b911e614cd79366840e33d5c53d9968f7cd33`
**Workbook authority:** appendix row for this prompt (5,092 bytes, 236 lines)
**Scope:** A punycode label on a Notion secret host. Do not activate Session 08. Do not commission A10 or A11.

The prompt file is not amended. This record is the corrective addendum.

## 1. Prompt authenticity

**Status:** VERIFIED

The extracted file's SHA-256 equals `a7a406cecd9c93efdec1045f394b911e614cd79366840e33d5c53d9968f7cd33`. The prompt stays the unamended source of record.

## 2. Three-dimensional review

Action 6 checks every embedded delivery link. Host admission is `_allowed_secret_host`. A label that contains `xn--` and then `.notion.site` is admitted, because the prefix has no dot. `urlparse` keeps that punycode in `hostname`, so the gate can live in the shared helper. The raw uppercase host is folded before that helper runs, and the fold is in `link_validation.py`, which pull #79 owns.

Open pulls #63, #68, #77, #78, and #79 stay untouched.

### Fidelity

**Verdict:** CONDITIONAL APPROVE.

**F-01 [HIGH] — A secret host is a plain Notion label, not an IDNA label**

- **Prompt lines:** 131–134. The link must be the variant's public Notion URL.
- **Authority:** `_EXACT_SECRET_HOSTS` and a single ASCII label plus `.notion.site`.
- **Consequence of literal execution:** `https://xn--fixture.notion.site/Sage-Green` is treated as an allowed host.
- **Amendment:** A hostname containing `xn--` is refused. The delivery-link code stays `host`.

### Safety and executability

**Verdict:** CONDITIONAL APPROVE.

**S-01 [HIGH] — Resolving the host would be a live lookup**

- **Prompt lines:** 131–134.
- **Amendment:** The test builds a PDF and injects no checker call when the host is refused. No socket and no credentials.

### Gameability

**Verdict:** CONDITIONAL APPROVE.

**G-01 [HIGH] — The suffix check hides an IDNA label**

- **Cheap fake:** Delete the `xn--` return. `fixture.notion.site` still passes, and a foreign host still fails the suffix check.
- **Amendment:** Deleting that return fails only `test_a_punycode_notion_host_is_refused`.

## 3. Corrective addendum

1. Prove the prompt hash, then refuse a secret hostname that contains `xn--`.
2. The delivery-link refusal stays `host`. A plain `fixture.notion.site` link still validates.
3. Do not edit `IMPLEMENTATION_STATE.json`, `.github/workflows/ci.yml`, or the files of open pulls #63, #68, #77, #78, and #79. Exit 78 stays HELD. Session 08 stays inactive. Do not print the session exit code.

## 4. Deferrals

| Finding | Owner | Reason |
|---|---|---|
| Uppercase on-host URIs | After #79 | The raw netloc is folded in `link_validation.py`, which that pull owns |
| `file:` allow, sendBeacon, spelled-out emails, raster text, `_prepare` non-ASCII | Later | Still parked; other files |
| Live S3 and `CREATE_ETSY_DRAFT` | #78 and #77 | Those pulls own the slices |
| Commission A10 and A11 | Action 11 | Operator hold |
| Session exit code and Exit 78 | Session exit | Operator hold |

## 5. Final verdict

**CONDITIONAL APPROVE.** Critical and high findings are resolved by the numbered addendum above. The punycode check may start. The prompt file stays unamended.
