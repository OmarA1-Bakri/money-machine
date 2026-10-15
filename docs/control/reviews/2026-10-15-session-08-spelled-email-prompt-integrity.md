# Session 08 Prompt Integrity Review — spelled email

**Date:** 2026-10-15
**Prompt:** `prompts/implementation/11_SESSION_08_MERCHANDISING_AND_ASSET_FACTORY.md`
**Verified SHA-256:** `a7a406cecd9c93efdec1045f394b911e614cd79366840e33d5c53d9968f7cd33`
**Workbook authority:** appendix row for this prompt (5,092 bytes, 236 lines)
**Scope:** A spelled-out email in screenshot text. Do not activate Session 08. Do not commission A10 or A11.

The prompt file is not amended. This record is the corrective addendum.

## 1. Prompt authenticity

**Status:** VERIFIED

The extracted file's SHA-256 equals `a7a406cecd9c93efdec1045f394b911e614cd79366840e33d5c53d9968f7cd33`. The prompt stays the unamended source of record.

## 2. Three-dimensional review

Action 5 refuses sensitive and sample data in variant screenshots. The email rule is `_EMAIL`, which requires `@` and a dotted host. `ceo at acme-corp dot com` is ASCII, so the fixture charset gate lets it through, and `_prepare` returns no refusal.

Open pulls #63, #68, #77, #78, #79, and #80 stay untouched. `test_variant_screenshots.py` and `screenshots.py` stay on #77. `link_validation.py` stays on #79. `publishing.py` stays on #80.

### Fidelity

**Verdict:** CONDITIONAL APPROVE.

**F-01 [HIGH] — A spelled address is still sample data**

- **Prompt lines:** 124–125. Sensitive and sample data rules apply to screenshot text.
- **Authority:** The email rule already refuses `ceo@acme-corp.com`.
- **Consequence of literal execution:** `ceo at acme-corp dot com` is painted. `email_rule_matches` is false and both refuse helpers return `None`.
- **Amendment:** Whitespace-separated `local at host dot tld` is the same email rule. The refusal code stays `sensitive_data`.

### Safety and executability

**Verdict:** CONDITIONAL APPROVE.

**S-01 [HIGH] — Proving the refusal with a browser would be live capture**

- **Prompt lines:** 116–125.
- **Amendment:** The tests call `email_rule_matches`, `refuse_rendered_text`, and `refuse_fixture_value`. No Chromium, no network, no credentials.

### Gameability

**Verdict:** CONDITIONAL APPROVE.

**G-01 [HIGH] — The `@` pattern hides the spelled form**

- **Cheap fake:** Leave `_EMAIL` in place. Existing `@` rows stay green, and the spelled address still renders.
- **Amendment:** Deleting the spelled check in `email_rule_matches` fails only `test_a_spelled_email_rule_matches`. Deleting the spelled check in `refuse_sensitive_text` fails only `test_a_spelled_email_is_refused`.

## 3. Corrective addendum

1. Prove the prompt hash, then refuse a spelled-out email in screenshot text.
2. The shape is a local part, the word `at`, a host, the word `dot`, and a top-level label of at least two letters. Case is ignored on that pattern only. The code stays `sensitive_data`.
3. `Meet at the studio`, `Sage Green`, and `x dot com` stay allowed. `x dot com` remains the parked host defang.
4. Do not edit `IMPLEMENTATION_STATE.json`, `.github/workflows/ci.yml`, or the files of open pulls #63, #68, #77, #78, #79, and #80. Exit 78 stays HELD. Session 08 stays inactive. Do not print the session exit code.

## 4. Deferrals

| Finding | Owner | Reason |
|---|---|---|
| Uppercase on-host URIs | After #79 | The raw netloc is folded in `link_validation.py`, which that pull owns |
| `file:` allow and sendBeacon | After #77 | `screenshots.py` is on that pull |
| Raster text and `_prepare` non-ASCII | Later | Still parked |
| Bracketed ` [at] ` / ` [dot] ` forms | Later | This slice is the spaced words only |
| Live S3 and `CREATE_ETSY_DRAFT` | #78 and #77 | Those pulls own the slices |
| Commission A10 and A11 | Action 11 | Operator hold |
| Session exit code and Exit 78 | Session exit | Operator hold |

## 5. Final verdict

**CONDITIONAL APPROVE.** Critical and high findings are resolved by the numbered addendum above. The spelled-email check may start. The prompt file stays unamended.
