# Session 08 Prompt Integrity Review — shared defang normalizer (#81)

**Date:** 2026-10-15
**Prompt:** `prompts/implementation/11_SESSION_08_MERCHANDISING_AND_ASSET_FACTORY.md`
**Verified SHA-256:** `a7a406cecd9c93efdec1045f394b911e614cd79366840e33d5c53d9968f7cd33`
**Workbook authority:** appendix row for this prompt (5,092 bytes, 236 lines)
**Scope:** One normalizer for the Notion host, spelled email, and gift host detectors. Do not activate Session 08.

The prompt file is not amended. This record is the corrective addendum for the r3 ruling. It supersedes the separate matcher lists on #80, #81, and #82.

## 1. Prompt authenticity

**Status:** VERIFIED

The extracted file's SHA-256 equals `a7a406cecd9c93efdec1045f394b911e614cd79366840e33d5c53d9968f7cd33`. The prompt stays the unamended source of record.

## 2. Three-dimensional review

Action 5 allows only plain Notion hosts. r1 refuses `xn--`. `urlparse` does not IDNA-encode, so a Unicode label never contains `xn--`. The r2 lists on #81 and #82 are separate matchers. The r3 ruling replaces them with one pipeline.

Open pulls #63 and #68 stay untouched. `IMPLEMENTATION_STATE.json` stays untouched.

### Fidelity

**Verdict:** CONDITIONAL APPROVE.

**F-01 [HIGH] — Three detectors do not share a normalizer**

- **Prompt lines:** 125–132 for the secret host. The email and gift rows are the owner gates on #81 and #82.
- **Authority:** Owner r3 ruling. One normalizer, fixed order, then an exact match.
- **Consequence of keeping the r2 matchers:** A fold, a candidate scan, or an undo can drift apart, and a detector can skip the fold.
- **Amendment:** `normalize_defanged` folds, finds candidates, then undoes defanging only inside those spans. `host_matches`, `email_matches`, and `url_matches` call it and then match an exact host, email, or `http` URL.

### Safety and executability

**Verdict:** CONDITIONAL APPROVE.

**S-01 [HIGH] — A Unicode secret host is not `xn--`**

- **Prompt lines:** 125–132.
- **Authority:** Owner gate for #80. `urlparse` leaves the label intact.
- **Consequence:** `fíxture.notion.site` and a fullwidth label are allowed if the only check is `xn--`.
- **Amendment:** `_capture_secret_link` and `_allowed_secret_host` both refuse a host that is not ASCII. The PDF path returns `host` for that case before the raw allowlist labels it `paid_checkout`. The docstring does not say parsing produces `xn--`.

**S-02 [HIGH] — Bare `dot` and a spaced `.` swallow prose**

- **Authority:** Owner rows `Day 1 . Habits`, `Notes . md`, and `dot matrix`.
- **Amendment:** Those separators undo only when the next token, spaces removed, is on `{com, c0m, net, io, shop, org, co}` plus a zero lookalike. A spaced single-word TLD followed by another word stays prose. Bracket, parenthesis, and brace forms also accept the IANA snapshot, so `evil[.]md` and `x[.]c0m` both undo.

### Gameability

**Verdict:** CONDITIONAL APPROVE.

**G-01 [HIGH] — A detector can skip the normalizer and still match a plain string**

- **Amendment:** The corpus includes a fullwidth bracket host, a Cyrillic TLD, and `hxxp://evil[.]com`. Each detector calls `normalize_defanged`. One test raises if that call is removed. Another fails if fold, candidate detection, and undo run in a different order.

## 3. Corrective addendum

1. Do not activate Session 08. Do not edit `IMPLEMENTATION_STATE.json`, #63, or #68.
2. Put the normalizer in `defang_normalizer.py`. Order is NFKC and lookalike fold, then candidate spans, then undo only inside those spans.
3. Bare `dot`, bare `at`, and a spaced `.` undo only for the curated TLD list. Bracket forms undo for IANA or that list.
4. Gift checkout calls `host_matches` and `url_matches`. Screenshot text calls `email_matches`, `url_matches`, and the bracket and lookalike host checks. Secret-link capture and the host allowlist call `normalize_defanged` and refuse a non-ASCII host.
5. Tests cover the shared corpus, prose that must stay, `ceo at acme dot io`, `dot matrix`, and both secret-host call sites.

## 4. What already holds

`xn--` is still refused. Plain `fixture.notion.site` stays allowed. No live HTTP. The prompt file is unchanged.
