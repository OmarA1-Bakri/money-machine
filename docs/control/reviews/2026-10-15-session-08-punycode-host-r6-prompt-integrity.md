# Session 08 Prompt Integrity Review — end-of-text spaced refuse (#80)

**Date:** 2026-10-15
**Prompt:** `prompts/implementation/11_SESSION_08_MERCHANDISING_AND_ASSET_FACTORY.md`
**Verified SHA-256:** `a7a406cecd9c93efdec1045f394b911e614cd79366840e33d5c53d9968f7cd33`
**Scope:** Two kill rows on the spaced-dot set. This branch only. Do not activate Session 08.

The prompt file is not amended. This record adds the end-of-text refuse rows to the r5 set rule.

## 1. Prompt authenticity

**Status:** VERIFIED

The extracted file's SHA-256 equals `a7a406cecd9c93efdec1045f394b911e614cd79366840e33d5c53d9968f7cd33`. The prompt stays the unamended source of record.

## 2. Three-dimensional review

The r5 set lets `Rest . Co` and `Pick one . Shop` stay prose at the end of the text. A guard that skips the undo whenever the token ends the text would keep those rows green and also let `com` and `c0m` through.

Open pulls #63 and #68 stay untouched. `IMPLEMENTATION_STATE.json` stays untouched. No live HTTP.

### Fidelity

**Verdict:** CONDITIONAL APPROVE.

**F-01 [HIGH] — End-of-text `com` and `c0m` are still hosts**

- **Prompt lines:** The gift host gate.
- **Authority:** Owner addendum after the spaced-dot set. The TLD word is the last token of the text.
- **Consequence:** Shrinking the set, or skipping an undo at the end of the text, looks green if only prose rows are pinned.
- **Amendment:** `mail me at acme . com` and `mail me at acme . c0m` are the whole text. Each returns `paid_checkout`.

### Safety and executability

**Verdict:** CONDITIONAL APPROVE.

**S-01 [HIGH] — The two rows must not save each other**

- **Prompt lines:** The spaced-dot accept set.
- **Authority:** Each new guard needs a row the other guard does not save.
- **Consequence:** `c0m` stays green when `com` is removed, because the zero spelling is its own member. `com` stays green when `c0m` is removed.
- **Amendment:** Dropping `com` fails the `com` row. Dropping `c0m` fails only the `c0m` row.

### Gameability

**Verdict:** CONDITIONAL APPROVE.

**G-01 [HIGH] — A following word is a different guard**

- **Prompt lines:** The word-boundary skip.
- **Authority:** These rows end on the TLD. No word follows.
- **Consequence:** `Plan 2 . Net profit` stays green if the undo is skipped only at the end of the text.
- **Amendment:** Skipping the undo when the token ends the text fails these two rows. The following-word prose rows stay green.

## 3. Addendum

1. Keep the r5 spaced-dot rule. Casefold into `{com, c0m, net, org}`. `c0m` is the zero spelling of `com`. A zero inside `org` counts. A later word still skips the undo.
2. Add kill rows. The text is exactly `mail me at acme . com` and exactly `mail me at acme . c0m`. Nothing follows the TLD. Each `refuse_paid_checkout` returns `paid_checkout`.
3. Dropping `com` fails the first row and leaves the `c0m` row green. Dropping `c0m` fails only the second row.
4. Session 08 stays inactive. `current_session` stays 7. `state_revision` stays 64. Exit 78 stays HELD. Push this branch only.

## 4. What already holds

Prose at the end of the text (`Rest . Co`, `Plan . Io`, `Pick one . Shop`) and prose with a following word (`Pick one . Shop local`, `Tea . Co op`) stay `None`. Bare `dot`, bare `at`, and bracket forms stay on the curated list.
