# Session 08 Prompt Integrity Review — defang wave 2

**Date:** 2026-10-16
**Prompt:** `prompts/implementation/11_SESSION_08_MERCHANDISING_AND_ASSET_FACTORY.md`
**Verified SHA-256:** `a7a406cecd9c93efdec1045f394b911e614cd79366840e33d5c53d9968f7cd33`
**Scope:** Fixture pins and two small refusals. Do not activate Session 08. Do not commission A10, A11, or A13. Do not lift Exit 78. Do not edit `IMPLEMENTATION_STATE.json`. Do not touch pull requests #63 or #68.

The prompt file is not amended. This record is the corrective addendum.

## 1. Prompt authenticity

**Status:** VERIFIED.

The extracted file's SHA-256 equals `a7a406cecd9c93efdec1045f394b911e614cd79366840e33d5c53d9968f7cd33`. The prompt stays the unamended source of record.

## 2. Three-dimensional review

### Fidelity

**Verdict:** CONDITIONAL APPROVE.

**F-01 [HIGH] — One description row can carry two marker lines**

- **Prompt lines:** Action 11, the draft listing is created once and a retry adopts the same draft.
- **Authority:** The draft client adopts a row when any normalized line equals the marker. Two `mm-draft:` lines in that one row still adopt.
- **Consequence:** A duplicated marker inside one description is treated as the single idempotency line.
- **Amendment:** More than one `mm-draft:` line raises `duplicate_marker` and posts nothing. One exact marker line still adopts. A decoy with one different `mm-draft:` line still posts.

**F-02 [HIGH] — `x . com today` and `x . co today` disagree**

- **Prompt lines:** Action 4, no paid checkout links. Action 5, sensitive data on screenshots.
- **Authority:** A one-letter label before `co` undoes when a word follows. The same label before `com` stays prose.
- **Consequence:** Gift text and screenshot text refuse one shape and allow the other.
- **Amendment:** A one-letter alphabetic label undoes a tight spaced TLD when a word follows, on both paths. A longer label stays prose. A digit label stays prose. `acme . io`, screenshot `x dot com`, and screenshot `x dot NET` stay as they are.

### Safety and executability

**Verdict:** CONDITIONAL APPROVE.

**S-01 [HIGH] — The session prompt commissions and reaches providers**

- **Prompt lines:** Action 5 (screenshot acquisition) and Action 11 (commission A10 and A11).
- **Authority:** D-0028. `COMMISSIONED` needs an operator decision plus a simulation run. A10 and A11 are fixture-only and `DESIGNED`. A13 can publish and spend. Exit 78 stays HELD. `current_session` stays 7.
- **Consequence:** A literal session run could capture live screenshots, mark agents commissioned, or call Notion or Etsy.
- **Amendment:** Fixture tests, this addendum, and the implementation log only. No live HTTP. No production Notion or Etsy. Do not edit `IMPLEMENTATION_STATE.json`. Do not touch pull requests #63 or #68.

### Gameability

**Verdict:** CONDITIONAL APPROVE.

**G-01 [HIGH] — A green suite can hide a deleted check**

- **Prompt lines:** Action 4 and Action 5, and the draft retry rule.
- **Authority:** #97 left the lone-CR injection and a trailing CR on the marker line untested. The weak spaced-letter mutant keeps `host_matches` on the whole text inside the span loop. The outside-TLD `islower` check is dead while set membership is case-sensitive. No screenshot test fails when `"\u041c": "M"` is deleted.
- **Consequence:** Those edits stay green.
- **Amendment:** Each item has a test that fails on its mutant. Gift and screenshot asserts for the one-letter host stay in separate tests. Restore the source after every mutant.

**G-02 [MEDIUM] — Out-of-scope hosts can be "fixed" in the same edit**

- **Prompt lines:** Action 4 and Action 5.
- **Authority:** Omar has not ruled on screenshot `x dot com` / `x dot NET`, or on the bare end-of-text host `acme . io`.
- **Consequence:** A broader undo would refuse shapes this wave must leave alone.
- **Amendment:** Do not change those three. Pin them as still allowed where this wave's tests already touch the same helpers.

## 3. Addendum

1. Prove the prompt hash. It stays `a7a406cecd9c93efdec1045f394b911e614cd79366840e33d5c53d9968f7cd33`.
2. Add a lone-CR `marker_injection` spec test and a trailing-CR marker adoption test. One row with two `mm-draft:` lines raises `duplicate_marker` and posts nothing.
3. Add the row that kills the weak spaced-letter mutant: spaced letters in one clause and `x dot com` in another.
4. Casefold the outside-TLD token before the set check, and pin uppercase `x . CO today` as prose on both paths.
5. Make `x . com today` refuse on both paths, matching `x . co today`. Keep `acme . com today` and `3 . com today` as prose.
6. Add a screenshot-only test on `acme . CO\u041c` that fails when `"\u041c": "M"` is deleted.
7. Do not change screenshot `x dot com`, screenshot `x dot NET`, or `acme . io`.
8. Do not activate Session 08. Do not commission A10, A11, or A13. Do not lift Exit 78. Do not edit `IMPLEMENTATION_STATE.json`.
