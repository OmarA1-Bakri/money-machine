# Session 08 Prompt Integrity Review — spaced-dot case (#80)

**Date:** 2026-10-15
**Prompt:** `prompts/implementation/11_SESSION_08_MERCHANDISING_AND_ASSET_FACTORY.md`
**Verified SHA-256:** `a7a406cecd9c93efdec1045f394b911e614cd79366840e33d5c53d9968f7cd33`
**Scope:** Reviewer 5539163598 on `b5db3518`. Spaced ` . ` refuses only an all-lowercase TLD in `{com, c0m, net, org}`. This branch only. Do not activate Session 08.

The prompt file is not amended. This record restores the lowercase gate that r5 removed. Uppercase `acme . NET` stays parked.

## 1. Prompt authenticity

**Status:** VERIFIED

The extracted file's SHA-256 equals `a7a406cecd9c93efdec1045f394b911e614cd79366840e33d5c53d9968f7cd33`. The prompt stays the unamended source of record.

## 2. Three-dimensional review

`_spaced_dot_tld` casefolds before the set check, so `Done . Net` returns `paid_checkout`. Base allows it. r5 made the spaced form case-insensitive so `X . COM` would refuse. That uppercase refusal drops again.

Open pulls #63 and #68 stay untouched. `IMPLEMENTATION_STATE.json` stays untouched. No live HTTP.

### Fidelity

**Verdict:** CONDITIONAL APPROVE.

**F-01 [HIGH] — Title case after a spaced dot is prose**

- **Prompt lines:** The gift host gate.
- **Authority:** Reviewer 5539163598. Case is read after NFKC and before any lowercasing. The lookalike fold keeps case.
- **Consequence:** Casefolding the token, or folding an uppercase lookalike to a lowercase letter, refuses `Done . Net` and `Done . Ｎｅｔ`.
- **Amendment:** The token must be all lowercase and then be `com`, `c0m`, `net`, or `org`. A lowercase zero inside `org` still counts. `c0m` stays its own member.

### Safety and executability

**Verdict:** CONDITIONAL APPROVE.

**S-01 [HIGH] — Lowercase hosts at the end of the text still refuse**

- **Prompt lines:** The gift host gate.
- **Authority:** The lowercase set is unchanged.
- **Consequence:** An `islower` gate that also drops `com` or `c0m` looks green on the prose rows.
- **Amendment:** `acme . com`, `acme . c0m`, `acme . net`, and `mail me at acme . com` return `paid_checkout`.

### Gameability

**Verdict:** CONDITIONAL APPROVE.

**G-01 [HIGH] — Each case branch needs its own row**

- **Prompt lines:** The spaced-dot accept function and the lookalike fold.
- **Authority:** A following word, an `isupper` skip, and a case-destroying fold must not save one another.
- **Consequence:** `Done . Net` stays green if the only new row is fullwidth, or if uppercase lookalikes are still folded to lowercase.
- **Amendment:** `Done . Net` kills a missing `islower` check. `Go . Com` kills an `isupper`-only skip. `Done . Ｎｅｔ` kills a casefold after NFKC. `acme . cОm` (Cyrillic capital O) stays, and the lowercase Cyrillic `o` still refuses. Fullwidth lowercase `ｎｅｔ` refuses, which a skipped NFKC does not.

## 3. Addendum

1. Keep the r5 set `{com, c0m, net, org}` and the zero lookalike of `org`.
2. Refuse a spaced `.` only when the token is all lowercase. Read that case after NFKC and the lookalike fold, before any lowercasing. Uppercase lookalikes fold to uppercase ASCII.
3. Must-pass, each `None`: `Done . Net`, `Done . Net.`, `Done . Ｎｅｔ`, `Rest . Co`, `Plan . Io`, `Go . Co`, `Go . Com`, `See . Org`, `Rest . Co.`, `Plan . Io!`, `Pick one . Shop`, `Pick one . Shop local`, `Tea . Co op`.
4. Must-refuse: `acme . com`, `acme . c0m`, `acme . net`, `mail me at acme . com`.
5. `acme . NET` is parked. Do not add a row for it.
6. Session 08 stays inactive. `current_session` stays 7. `state_revision` stays 64. Exit 78 stays HELD. Push this branch only.

## 4. What already holds

Bare `dot`, bare `at`, and bracket forms stay on the curated list and the IANA snapshot. A following word still skips the spaced undo. `Plan 2 . Net profit` stays prose.
