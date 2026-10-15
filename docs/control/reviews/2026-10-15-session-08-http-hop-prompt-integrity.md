# Session 08 Prompt Integrity Review — same-host http hop

**Date:** 2026-10-15
**Prompt:** `prompts/implementation/11_SESSION_08_MERCHANDISING_AND_ASSET_FACTORY.md`
**Verified SHA-256:** `a7a406cecd9c93efdec1045f394b911e614cd79366840e33d5c53d9968f7cd33`
**Workbook authority:** appendix row for this prompt (5,092 bytes, 236 lines)
**Scope:** The parked same-host `http` redirect. Do not activate Session 08. Do not commission A10 or A11.

The prompt file is not amended. This record is the corrective addendum.

## 1. Prompt authenticity

**Status:** VERIFIED

The extracted file's SHA-256 equals `a7a406cecd9c93efdec1045f394b911e614cd79366840e33d5c53d9968f7cd33`. The prompt stays the unamended source of record.

## 2. Three-dimensional review

Action 6 says every embedded link is opened and the variant, public access, and duplicate button are recorded. A failed link creates a repair. The current redirect check treats any later hop on the same host as success. An `https` listing link that lands on `http` on that host is recorded as resolved.

Open pulls #63, #68, #77, and #78 own their files. This wave does not edit them. Action 8 storage and action 9 `CREATE_ETSY_DRAFT` stay on those pulls.

### Fidelity

**Verdict:** CONDITIONAL APPROVE.

**F-01 [HIGH] — "Open each variant link" does not name the scheme of a later hop**

- **Prompt lines:** 128–138.
- **Authority:** Delivery links are `https` on the Notion secret hosts. A same-host `https` path hop is already allowed.
- **Consequence of literal execution:** A checker that returns `http://` on the same host passes validation and no repair is recorded.
- **Amendment:** A hop whose scheme is not `https` raises `redirect_host`. An `https` hop on the same host stays allowed.

### Safety and executability

**Verdict:** CONDITIONAL APPROVE.

**S-01 [HIGH] — Opening the hop would be a live fetch**

- **Prompt lines:** 131–134.
- **Authority:** No live HTTP. The default checker already raises `live_link_check`.
- **Amendment:** The test injects the chain. This wave does not call a socket and does not read provider credentials.

### Gameability

**Verdict:** CONDITIONAL APPROVE.

**G-01 [HIGH] — The host compare hides a scheme downgrade**

- **Cheap fake:** Delete the scheme check. The other-host test still fails, and the same-host `https` hop still passes.
- **Amendment:** The `http` same-host chain fails only `test_a_same_host_http_hop_is_refused`.

## 3. Corrective addendum

1. Prove the prompt hash, then refuse a redirect hop whose scheme is not `https`.
2. The refusal code stays `redirect_host`. The repair names the opened URI.
3. An `https` hop on the same host remains a passing record.
4. Do not edit `IMPLEMENTATION_STATE.json`, `.github/workflows/ci.yml`, or the files of open pulls #63, #68, #77, and #78. Exit 78 stays HELD. Session 08 stays inactive. Do not print the session exit code.

## 4. Deferrals

| Finding | Owner | Reason |
|---|---|---|
| Punycode and uppercase on-host URIs | Later | Separate host-identity check |
| `file:` allow, sendBeacon, spelled-out emails, raster text, `_prepare` non-ASCII | Later | Still parked; other files |
| Live S3 and `CREATE_ETSY_DRAFT` | #78 and #77 | Those pulls own the slices |
| Commission A10 and A11 | Action 11 | Operator hold |
| Session exit code and Exit 78 | Session exit | Operator hold |

## 5. Final verdict

**CONDITIONAL APPROVE.** Critical and high findings are resolved by the numbered addendum above. The scheme check may start. The prompt file stays unamended.
