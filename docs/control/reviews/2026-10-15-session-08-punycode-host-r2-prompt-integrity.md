# Session 08 Prompt Integrity Review — punycode host r2

**Date:** 2026-10-15
**Prompt:** `prompts/implementation/11_SESSION_08_MERCHANDISING_AND_ASSET_FACTORY.md`
**Verified SHA-256:** `a7a406cecd9c93efdec1045f394b911e614cd79366840e33d5c53d9968f7cd33`
**Workbook authority:** appendix row for this prompt (5,092 bytes, 236 lines)
**Scope:** Refuse a raw Unicode secret host before the `xn--` check. Do not activate Session 08. Do not commission A10 or A11.

The prompt file is not amended. This record is the corrective addendum for the r2 ruling. The TLD split for bare `dot` and bracket defangs is owned by #81 and #82. This pull checks Notion hosts, not gift copy.

## 1. Prompt authenticity

**Status:** VERIFIED

The extracted file's SHA-256 equals `a7a406cecd9c93efdec1045f394b911e614cd79366840e33d5c53d9968f7cd33`. The prompt stays the unamended source of record.

## 2. Three-dimensional review

Action 5 allows only plain Notion hosts on a secret link. r1 refuses a hostname that contains `xn--`. `urlparse` does not IDNA-encode, so `fíxture.notion.site` and a fullwidth label contain no `xn--` and the guard returns true.

Open pulls #63, #68, #78, #81, #82, #83, and #84 stay untouched.

### Fidelity

**Verdict:** CONDITIONAL APPROVE.

**F-01 [HIGH] — A Unicode label bypasses `xn--`**

- **Prompt lines:** 125–132. The secret host is a plain Notion host.
- **Authority:** Owner gate for #80. `urlparse` leaves the Unicode label intact.
- **Consequence of literal execution of the r1 guard:** `fíxture.notion.site` and `\uff46ixture.notion.site` are allowed.
- **Amendment:** `if not host.isascii(): return False` runs before the `xn--` check. The docstring no longer says parsing produces `xn--`.

### Safety and executability

**Verdict:** CONDITIONAL APPROVE.

**S-01 [HIGH] — Proving the host by fetching would open a socket**

- **Prompt lines:** 125–132.
- **Amendment:** The PDF row and the publishing row call the injected checker only after the host is allowed. A refused host never calls the checker. No network, no Notion, no browser.

### Gameability

**Verdict:** CONDITIONAL APPROVE.

**G-01 [HIGH] — The punycode row stays green if Unicode is allowed**

- **Cheap fake:** Keep the `xn--` return and skip non-ASCII hosts.
- **Amendment:** Deleting `isascii` fails the Unicode rows and leaves the `xn--` row green. Deleting `xn--` fails the punycode row and leaves the Unicode rows green. The punycode test passes a checker that raises if it is called.

## 3. Corrective addendum

1. Prove the prompt hash, then refuse a non-ASCII host before the `xn--` check.
2. Add a Latin-1 homoglyph PDF row and a fullwidth host row. A plain `fixture.notion.site` host stays allowed.
3. Do not edit `IMPLEMENTATION_STATE.json` or the files of open pulls #63, #68, #78, #81, #82, #83, and #84. Exit 78 stays HELD. Session 08 stays inactive. Do not print the session exit code.

## 4. Deferrals

| Finding | Owner | Reason |
|---|---|---|
| Curated and IANA defang lists | #81 and #82 | Those pulls own screenshot text and gift text |
| Uppercase on-host URIs | Later | The raw netloc is folded in `link_validation.py` |
| Live S3 and `CREATE_ETSY_DRAFT` | #78 and #77 | Those pulls own the slices |
| Commission A10 and A11 | Action 11 | Operator hold |
| Session exit code and Exit 78 | Session exit | Operator hold |

## 5. Final verdict

**CONDITIONAL APPROVE.** Critical and high findings are resolved by the numbered addendum above. The r2 punycode-host check may start. The prompt file stays unamended.
