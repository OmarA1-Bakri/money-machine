# Session 08 Prompt Integrity Review — defanged host r2

**Date:** 2026-10-15
**Prompt:** `prompts/implementation/11_SESSION_08_MERCHANDISING_AND_ASSET_FACTORY.md`
**Verified SHA-256:** `a7a406cecd9c93efdec1045f394b911e614cd79366840e33d5c53d9968f7cd33`
**Workbook authority:** appendix row for this prompt (5,092 bytes, 236 lines)
**Scope:** TLD split for defanged gift hosts. Do not activate Session 08. Do not commission A10 or A11.

The prompt file is not amended. This record is the corrective addendum for the r2 ruling. It supersedes the r1 deferral that spelled dots other than `com` stay parked.

## 1. Prompt authenticity

**Status:** VERIFIED

The extracted file's SHA-256 equals `a7a406cecd9c93efdec1045f394b911e614cd79366840e33d5c53d9968f7cd33`. The prompt stays the unamended source of record.

## 2. Three-dimensional review

Action 4 says the free-gift PDF has no paid checkout links. r1 refuses `x . com`, `x[.]com`, `x dot com`, and `x.c0m`. The spaced pattern uses `[A-Za-z]{2,}`, so ordinary copy such as `Notes . md` is refused with those hosts.

Open pulls #63, #68, #78, #80, #81, #83, and #84 stay untouched. `screenshot_text.py` stays on #81. `publishing.py` stays on #80.

### Fidelity

**Verdict:** CONDITIONAL APPROVE.

**F-01 [HIGH] — One TLD list cannot serve both a bare dot and a bracket**

- **Prompt lines:** 110–114. The gift page has no paid checkout links.
- **Authority:** Owner ruling for #82 r2. The curated list is exactly `{com, c0m, net, io, shop, org, co}` plus lookalikes, and it applies only to a bare `dot` and a spaced `.`. Bracketed and parenthesized defangs (`[.]`, `(.)`, `{.}`, `[dot]`, `(dot)`) check the IANA list.
- **Consequence of literal execution of the r1 pattern:** `Notes . md`, `Mr . Jones`, `Day 1 . Habits`, `Page 3 . Notes`, and `Sip tea . Relax` are `paid_checkout`. `x dot shop`, `x dot io`, and `evil(.)md` are painted.
- **Amendment:** Replace the spaced, bracket, and spelled patterns. Keep `_HOST` and the real-dot `c0m` pattern. `evil[.]md`, `evil(.)md`, and `evil{.}md` are `paid_checkout`. `Notes . md` stays allowed.

### Safety and executability

**Verdict:** CONDITIONAL APPROVE.

**S-01 [HIGH] — The IANA list must be a snapshot, not a fetch**

- **Prompt lines:** 110–114.
- **Amendment:** Embed the 2026-10-15 IANA snapshot (`tlds-alpha-by-domain.txt` version `2026101500`, 1,437 labels). Do not fetch it at runtime. No browser, no network, no credentials. Tests call `refuse_paid_checkout` and the three bracket detectors.

### Gameability

**Verdict:** CONDITIONAL APPROVE.

**G-01 [HIGH] — A shared TLD list lets the wrong shape survive**

- **Cheap fake:** Point every defang at `[A-Za-z]{2,}`, or point the brackets at the curated list.
- **Amendment:** Deleting the spaced check fails only the spaced rows. Deleting each bracket detector fails only that pair's `md` row. Deleting the bare-`dot` check fails only the spelled rows. `Notes . md` fails a mutant that uses IANA or `{2,}` for a spaced dot. `evil[.]md` fails a mutant that uses the curated list for brackets. `evil[.]zz` fails a mutant that treats every two-letter token as a TLD. `x dot sh0p` fails a mutant that drops the `0`→`o` fold. `x . c o m` fails a mutant that drops space-joining. `x .\ncom` fails a mutant that uses `\s`.

## 3. Corrective addendum

1. Prove the prompt hash, then split the defang TLD lists in `refuse_paid_checkout`.
2. Curated membership is exactly `{com, c0m, net, io, shop, org, co}`. Lookalikes strip spaces and map `0` to `o`. That list is only for a bare `dot` and a spaced `.` (a space on either side of the dot).
3. Square, parenthesis, and brace defangs, including the word `dot` inside the pair, check the embedded IANA snapshot with no lookalike fold.
4. `evil[.]md` is caught by the square detector, `evil(.)md` by the parenthesis detector, and `evil{.}md` by the brace detector. `Notes . md` does not trigger.
5. Keep `_HOST` and `_LEET_HOST`. Horizontal whitespace is `[ \t]`.
6. Do not edit `IMPLEMENTATION_STATE.json` or the files of open pulls #63, #68, #78, #80, #81, #83, and #84. Exit 78 stays HELD. Session 08 stays inactive. Do not print the session exit code.

## 4. Deferrals

| Finding | Owner | Reason |
|---|---|---|
| Bracket lookalike `x[.]c0m` | Later | `c0m` is not an IANA TLD. This slice does not add an allow test for that hole |
| Spelled emails and screenshot entry points | #81 | That pull owns `screenshot_text.py` |
| Unicode hosts before the `xn--` guard | #80 | That pull owns `publishing.py` |
| Uppercase on-host URIs | Later | The raw netloc fold lives in `link_validation.py` |
| Live S3 and `CREATE_ETSY_DRAFT` | #78 and #77 | Those pulls own the slices |
| Commission A10 and A11 | Action 11 | Operator hold |
| Session exit code and Exit 78 | Session exit | Operator hold |

## 5. Final verdict

**CONDITIONAL APPROVE.** Critical and high findings are resolved by the numbered addendum above. The r2 defanged-host checks may start. The prompt file stays unamended.
