# Session 08 Prompt Integrity Review — defanged host

**Date:** 2026-10-15
**Prompt:** `prompts/implementation/11_SESSION_08_MERCHANDISING_AND_ASSET_FACTORY.md`
**Verified SHA-256:** `a7a406cecd9c93efdec1045f394b911e614cd79366840e33d5c53d9968f7cd33`
**Workbook authority:** appendix row for this prompt (5,092 bytes, 236 lines)
**Scope:** Defanged hosts in gift text. Do not activate Session 08. Do not commission A10 or A11.

The prompt file is not amended. This record is the corrective addendum.

## 1. Prompt authenticity

**Status:** VERIFIED

The extracted file's SHA-256 equals `a7a406cecd9c93efdec1045f394b911e614cd79366840e33d5c53d9968f7cd33`. The prompt stays the unamended source of record.

## 2. Three-dimensional review

Action 4 says the free-gift PDF has no paid checkout links. `refuse_paid_checkout` already refuses a dotted host. `x . com`, `x[.]com`, `x dot com`, and `x.c0m` do not match that pattern, and the gift renderer still paints them.

Open pulls #63, #68, #77, #78, #79, #80, and #81 stay untouched. `screenshot_text.py` stays on #81. `link_validation.py` stays on #79. `screenshots.py` stays on #77.

### Fidelity

**Verdict:** CONDITIONAL APPROVE.

**F-01 [HIGH] — A broken-up host is still a checkout address**

- **Prompt lines:** 110–114. The gift page has no paid checkout links.
- **Authority:** `_HOST` refuses `x.com`. The same label with the dot spelled, spaced, bracketed, or written `c0m` is the same host.
- **Consequence of literal execution:** Those four strings are gift names and the PDF paints them.
- **Amendment:** Each of the four shapes returns `paid_checkout`. `4.9`, `e.g.`, `127.1`, `0x7f000001`, `2130706433`, and `v1.2.3.4` stay allowed. A spelled dot is only the word `dot` followed by `com`, so `polka dot journal` stays allowed.

### Safety and executability

**Verdict:** CONDITIONAL APPROVE.

**S-01 [HIGH] — Proving the refusal by rendering would launch Chromium**

- **Prompt lines:** 110–114.
- **Amendment:** The new tests call `refuse_paid_checkout` only. No browser, no network, no credentials. The existing render rows for those four names are removed so they no longer assert that the PDF paints them.

### Gameability

**Verdict:** CONDITIONAL APPROVE.

**G-01 [HIGH] — One shared pattern lets three shapes survive**

- **Cheap fake:** Add a single check for `x dot com`. The other three render rows stay green.
- **Amendment:** Deleting the spaced-dot check fails only `test_a_spaced_dot_host_is_refused`. Deleting the bracket check fails only `test_a_bracket_dot_host_is_refused`. Deleting the spelled-dot check fails only `test_a_spelled_dot_host_is_refused`. Deleting the `c0m` check fails only `test_a_leet_com_host_is_refused`.

## 3. Corrective addendum

1. Prove the prompt hash, then refuse the four defanged hosts in `refuse_paid_checkout`.
2. The refusal code stays `paid_checkout`. Case is ignored on these four patterns only.
3. Keep the decimal, example, short IPv4, hex, integer, and letter-prefixed dotted rows allowed.
4. Do not edit `IMPLEMENTATION_STATE.json`, `.github/workflows/ci.yml`, or the files of open pulls #63, #68, #77, #78, #79, #80, and #81. Exit 78 stays HELD. Session 08 stays inactive. Do not print the session exit code.

## 4. Deferrals

| Finding | Owner | Reason |
|---|---|---|
| Uppercase on-host URIs | After #79 | The raw netloc is folded in `link_validation.py`, which that pull owns |
| `file:` allow and sendBeacon | After #77 | `screenshots.py` is on that pull |
| Spelled-out emails | #81 | That pull owns `screenshot_text.py` |
| Raster text and `_prepare` non-ASCII | Later | Still parked |
| Spelled dots other than `com` | Later | `polka dot journal` stays a product name |
| Leet digits other than `c0m` | Later | This slice is the parked `x.c0m` shape |
| Bare `127.1`, `0x7f000001`, and `2130706433` | Later | They stay allowed |
| Live S3 and `CREATE_ETSY_DRAFT` | #78 and #77 | Those pulls own the slices |
| Commission A10 and A11 | Action 11 | Operator hold |
| Session exit code and Exit 78 | Session exit | Operator hold |

## 5. Final verdict

**CONDITIONAL APPROVE.** Critical and high findings are resolved by the numbered addendum above. The defanged-host checks may start. The prompt file stays unamended.
