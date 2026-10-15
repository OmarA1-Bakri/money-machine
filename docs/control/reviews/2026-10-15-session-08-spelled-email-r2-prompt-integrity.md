# Session 08 Prompt Integrity Review — spelled email r2

**Date:** 2026-10-15
**Prompt:** `prompts/implementation/11_SESSION_08_MERCHANDISING_AND_ASSET_FACTORY.md`
**Verified SHA-256:** `a7a406cecd9c93efdec1045f394b911e614cd79366840e33d5c53d9968f7cd33`
**Workbook authority:** appendix row for this prompt (5,092 bytes, 236 lines)
**Scope:** TLD split for spelled emails and bracketed hosts in screenshot text. Do not activate Session 08. Do not commission A10 or A11.

The prompt file is not amended. This record is the corrective addendum for the r2 ruling.

## 1. Prompt authenticity

**Status:** VERIFIED

The extracted file's SHA-256 equals `a7a406cecd9c93efdec1045f394b911e614cd79366840e33d5c53d9968f7cd33`. The prompt stays the unamended source of record.

## 2. Three-dimensional review

Action 6 refuses sensitive text in fixture screenshots. r1 refuses `ceo at acme-corp dot com` with a `{2,}` TLD. That quantifier refuses `ceo at acme dot md` and misses bracketed `at` / `dot` forms.

Open pulls #63, #68, #78, #80, #82, #83, and #84 stay untouched. `gift_links.py` stays on #82. `publishing.py` stays on #80. The TLD module is the same file #82 adds.

### Fidelity

**Verdict:** CONDITIONAL APPROVE.

**F-01 [HIGH] — A spelled email and a bracketed host do not share one TLD list**

- **Prompt lines:** 140–148. Fixture text must not carry a real address.
- **Authority:** Owner ruling for #81 r2. The curated list `{com, c0m, net, io, shop, org, co}` plus lookalikes applies only to a bare `dot` and a spaced `.`. Bracketed and parenthesized defangs check the IANA list.
- **Consequence of leaving `{2,}`:** `ceo at acme dot io` can be dropped by a `{3,}` mutant, and `ceo at acme dot md` is refused. `ceo [at] acme [dot] com` and `ceo at acme . com` are painted.
- **Amendment:** Bare `dot` and spaced `.` inside an email use the curated list. Bracket pairs use IANA. `x dot com` stays allowed because it has no local part and no `at`. `evil[.]md` is refused by `refuse_sensitive_text`, `refuse_rendered_text`, and `refuse_fixture_value`. `Notes . md` stays allowed. `email_rule_matches("evil[.]md")` stays false.

### Safety and executability

**Verdict:** CONDITIONAL APPROVE.

**S-01 [HIGH] — A newline must not join an address**

- **Prompt lines:** 140–148.
- **Amendment:** Email separators are `[ \t]`, not `\s`. Tests call the text helpers only. No browser, no network, no credentials. The IANA snapshot is the embedded copy, not a fetch.

### Gameability

**Verdict:** CONDITIONAL APPROVE.

**G-01 [HIGH] — One pattern lets the other shapes survive**

- **Cheap fake:** Keep `{2,}` and add only `dot com`.
- **Amendment:** Deleting the bare-`dot` email check fails only the spelled `com` row. Deleting the spaced-email check fails only `ceo at acme . com`. Deleting each bracket email check fails only that pair. `ceo at acme dot md` fails a mutant that uses IANA or `{2,}` for a bare `dot`. `ceo [at] acme [dot] md` fails a mutant that uses the curated list for brackets. `evil[.]md` fails a mutant that drops the square host check, and the parenthesis and brace host checks have their own rows.

## 3. Corrective addendum

1. Prove the prompt hash, then split the email TLD lists in `screenshot_text.py`.
2. Use the shared curated list and IANA snapshot. Do not fetch the list.
3. `ceo at acme dot io` is an email. `ceo at acme dot md` is not. `x dot com` is not.
4. `evil[.]md` is caught by all three refuse entry points. `Notes . md` is not. The email rule does not match `evil[.]md`.
5. Do not edit `IMPLEMENTATION_STATE.json` or the files of open pulls #63, #68, #78, #80, #82, #83, and #84. Exit 78 stays HELD. Session 08 stays inactive. Do not print the session exit code.

## 4. Deferrals

| Finding | Owner | Reason |
|---|---|---|
| Gift-text defangs | #82 | That pull owns `gift_links.py` |
| Unicode hosts before the `xn--` guard | #80 | That pull owns `publishing.py` |
| Raster text and `_prepare` non-ASCII | Later | Still parked |
| Live S3 and `CREATE_ETSY_DRAFT` | #78 and #77 | Those pulls own the slices |
| Commission A10 and A11 | Action 11 | Operator hold |
| Session exit code and Exit 78 | Session exit | Operator hold |

## 5. Final verdict

**CONDITIONAL APPROVE.** Critical and high findings are resolved by the numbered addendum above. The r2 spelled-email checks may start. The prompt file stays unamended.
