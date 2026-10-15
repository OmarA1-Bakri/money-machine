# Session 08 Prompt Integrity Review — spaced-dot set (#80)

**Date:** 2026-10-15
**Prompt:** `prompts/implementation/11_SESSION_08_MERCHANDISING_AND_ASSET_FACTORY.md`
**Verified SHA-256:** `a7a406cecd9c93efdec1045f394b911e614cd79366840e33d5c53d9968f7cd33`
**Scope:** The spaced ` . ` accept set on the shared normalizer. Do not activate Session 08. This branch only. #81 and #82 are not pushed.

The prompt file is not amended. This record supersedes the r4 lowercase rule for the spaced form. Bare `dot`, bare `at`, and bracket forms stay on the curated list.

## 1. Prompt authenticity

**Status:** VERIFIED

The extracted file's SHA-256 equals `a7a406cecd9c93efdec1045f394b911e614cd79366840e33d5c53d9968f7cd33`. The prompt stays the unamended source of record.

## 2. Three-dimensional review

Reviewer 5537793108 on `2dc56676` fails because a spaced `.` undoes any curated TLD when no word follows. `Rest . Co`, `Plan . Io`, `Rest . Co.`, `Plan . Io!`, and end-of-text `Pick one . Shop` return `paid_checkout`. On base `8d40dd57` the first two return None. r4 required `token.islower()`, which lets `X . COM` through. That refuse row stays.

Open pulls #63 and #68 stay untouched. `IMPLEMENTATION_STATE.json` stays untouched. No live HTTP.

### Fidelity

**Verdict:** CONDITIONAL APPROVE.

**F-01 [HIGH] — The spaced form is a smaller set than a bare `dot`**

- **Prompt lines:** The gift host gate. r3 used `CURATED_TLDS` for a spaced `.`. r4 added an `islower` gate.
- **Authority:** Owner ruling after Reviewer 5537793108. The spaced form accepts only `{com, c0m, net, org}` plus lookalikes.
- **Consequence of r4:** `X . COM` casefolds to `com` and is no longer refused.
- **Amendment:** Casefold the token. Accept it when the fold is in that set. ``c0m`` is the zero spelling of ``com``. A zero inside ``org`` also counts. Letter lookalikes are already folded to ASCII before this check.

### Safety and executability

**Verdict:** CONDITIONAL APPROVE.

**S-01 [HIGH] — End-of-text prose must stay, and so must a following word of prose**

- **Prompt lines:** Gift checkout refusal. The word-boundary skip at the spaced-dot undo does not run at the end of the text.
- **Authority:** Base allows `Rest . Co`. `Pick one . Shop local` and `Tea . Co op` already pass.
- **Consequence:** A capitalised `co`, `io`, or `shop` at the end of a gift field becomes `paid_checkout` when the spaced form uses the full curated list.
- **Amendment:** Those tokens are not in the spaced set, so they stay prose at the end of the text and when another word follows. A following word still skips the undo, so `Plan 2 . Net profit` stays prose. `com`, `c0m`, `net`, and `org` at the end of the text still refuse, in any case.

### Gameability

**Verdict:** CONDITIONAL APPROVE.

**G-01 [HIGH] — Case and the wide curated list hide the set**

- **Prompt lines:** The spaced-dot accept function.
- **Authority:** Existing refuse rows stay green. Each new guard needs a row the others do not save.
- **Consequence:** An `islower` gate keeps `Rest . Co` green while `X . COM` stops refusing. Using `CURATED_TLDS` keeps `acme . net` green while `Pick one . Shop` starts refusing.
- **Amendment:** `X . COM` is the case row. End-of-text `x . shop`, `acme . io`, and `acme . co` are the set rows. `c0m` stays a named member. `x . 0rg` is the zero-lookalike row. A Cyrillic `o` in `com` is the letter-lookalike row.

## 3. Addendum

1. Keep one normalizer. Fold, then candidates, then undo inside those spans.
2. A spaced `.` is undone only when the token casefolds into `{com, c0m, net, org}`. `c0m` is the zero spelling of `com`. A zero inside `org` (`0rg`) also counts. Mapping that zero onto `com` does not replace the `c0m` member.
3. That decision does not depend on letter case. It applies wherever the token sits, including at the end of the text.
4. A following word still skips the spaced undo. Bare `dot`, bare `at`, and bracket forms keep the curated list and the IANA snapshot.
5. Must-pass, each `None` from `refuse_paid_checkout`: `Rest . Co`, `Plan . Io`, `Rest . Co.`, `Plan . Io!`, `Pick one . Shop`, `Pick one . Shop local`, `Tea . Co op`.
6. Existing refuse rows stay refusals, including `X . COM`, `x . com`, `acme . c0m`, `acme . net`, and `acme . org`.
7. Session 08 stays inactive. `current_session` stays 7. `state_revision` stays 64. Exit 78 stays HELD. Push this branch only.

## 4. What already holds

The fold-then-candidates-then-undo order, the Notion `xn--` and non-ASCII host refusal, and the bracket IANA path stay as r3 measured them. r4's prose rows for `co`, `io`, and `shop` stay. r4's lowercase gate does not.
