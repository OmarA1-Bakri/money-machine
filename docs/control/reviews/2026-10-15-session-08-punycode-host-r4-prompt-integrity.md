# Session 08 Prompt Integrity Review — spaced-dot case (#80)

**Date:** 2026-10-15
**Prompt:** `prompts/implementation/11_SESSION_08_MERCHANDISING_AND_ASSET_FACTORY.md`
**Verified SHA-256:** `a7a406cecd9c93efdec1045f394b911e614cd79366840e33d5c53d9968f7cd33`
**Scope:** The spaced ` . ` form on the shared normalizer. Do not activate Session 08. This branch only.

The prompt file is not amended. This record is the corrective addendum for the r4 ruling. It narrows the r3 spaced-dot rule. Bare `dot`, bare `at`, and bracket forms stay on the curated list.

## 1. Prompt authenticity

**Status:** VERIFIED

The extracted file's SHA-256 equals `a7a406cecd9c93efdec1045f394b911e614cd79366840e33d5c53d9968f7cd33`. The prompt stays the unamended source of record.

## 2. Three-dimensional review

Verifier r2 on `2dc56676` is green in CI and still wrong: `refuse_paid_checkout("Rest . Co")` returns `paid_checkout`. The same refusal hits `Done . Net`. The r3 pipeline undoes a spaced dot when the next token casefolds onto `CURATED_TLDS`, and the word-boundary skip does not apply at the end of the text.

Open pulls #63 and #68 stay untouched. `IMPLEMENTATION_STATE.json` stays untouched. No live HTTP.

### Fidelity

**Verdict:** CONDITIONAL APPROVE.

**F-01 [HIGH] — A spaced dot is not a bare `dot`**

- **Prompt lines:** The gift and email gates. The r3 addendum treated a spaced `.` like a bare `dot`.
- **Authority:** Owner correction after Verifier r2. A capitalised word after a spaced dot is prose.
- **Consequence of the r3 wording:** `Done . Net` casefolds to `net` and is refused.
- **Amendment:** Undo a spaced `.` only when the TLD word is all lowercase, or a lowercase lookalike the fold already mapped to ASCII, and the token is in `{com, c0m, net, org}`.

### Safety and executability

**Verdict:** CONDITIONAL APPROVE.

**S-01 [HIGH] — End-of-text prose must stay**

- **Prompt lines:** Gift checkout refusal.
- **Authority:** Base allows `Rest . Co`. The tip refuses it.
- **Consequence:** Ordinary gift sentences at the end of a field become `paid_checkout`.
- **Amendment:** The seven prose rows return `None`. Lowercase `com`, `c0m`, and `net` at the end of the text still refuse.

### Gameability

**Verdict:** CONDITIONAL APPROVE.

**G-01 [HIGH] — The set limit and the case limit hide each other**

- **Prompt lines:** The spaced-dot accept function.
- **Authority:** Each new guard needs a row the other guard does not save.
- **Consequence:** `Done . Net` stays green if the set shrinks and the casefold stays. `x . shop` stays green if the case check stays and the set stays wide.
- **Amendment:** `Done . Net` is the case row. A lowercase `shop`, `io`, or `co` at the end of the text is the set row. `c0m` is the digit row. A lowercase Cyrillic `o` in `com` is the lookalike row.

## 3. Addendum

1. Keep one normalizer. Fold, then candidates, then undo inside those spans.
2. A spaced `.` is undone only when `token.islower()` and `token` is in `{com, c0m, net, org}`.
3. Do not casefold that token before the check. Title case and all caps stay prose.
4. A lowercase lookalike that the fold maps onto one of those four still refuses.
5. Bare `dot`, bare `at`, and bracket forms keep the curated list and the IANA snapshot.
6. Must-pass, each `None` from `refuse_paid_checkout`: `Rest . Co`, `Plan . Io`, `Go . Co`, `Done . Net`, `Rest . Co.`, `Plan . Io!`, `Pick one . Shop`.
7. Must-refuse at the end of the text: `mail me at acme . com`, `mail me at acme . c0m`, `acme . net`.
8. Session 08 stays inactive. `current_session` stays 7. `state_revision` stays 64. Exit 78 stays HELD.

## 4. What already holds

The fold-then-candidates-then-undo order, the Notion `xn--` and non-ASCII host refusal, and the bracket IANA path stay as r3 measured them.
