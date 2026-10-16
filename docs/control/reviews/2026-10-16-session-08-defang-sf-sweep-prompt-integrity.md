# Session 08 Prompt Integrity Review — defang should-fix sweep

**Date:** 2026-10-16
**Prompt:** `prompts/implementation/11_SESSION_08_MERCHANDISING_AND_ASSET_FACTORY.md`
**Verified SHA-256:** `a7a406cecd9c93efdec1045f394b911e614cd79366840e33d5c53d9968f7cd33`
**Scope:** Fixture-only sweep of the parked defang should-fixes on the normalizer and the screenshot and gift paths. No live HTTP. No production Notion or Etsy. Do not activate Session 08.

The prompt file is not amended. This record is the corrective addendum for this slice. The base is `e6516655`.

## 1. Prompt authenticity

**Status:** VERIFIED

The extracted file's SHA-256 equals `a7a406cecd9c93efdec1045f394b911e614cd79366840e33d5c53d9968f7cd33`. The prompt stays the unamended source of record.

## 2. Three-dimensional review

Action 5 refuses sample data in screenshot text. Action 6 refuses a paid checkout host. Open pulls #63 and #68 stay untouched. `IMPLEMENTATION_STATE.json` stays untouched. No live HTTP.

### Fidelity

**Verdict:** CONDITIONAL APPROVE.

**F-01 [HIGH] — The spaced zero branch is covered by the digit map**

- **Prompt lines:** Action 6, gift host gate.
- **Authority:** `_spaced_dot_tld` maps `0` to `o` twice. `_ZERO_TO_O` accepts `0rg` because the result is `org`. `_CURATED_DIGITS` does the same map and `org` is already in the spaced set.
- **Consequence:** Deleting `_ZERO_TO_O` still refuses `x . 0rg`. Keeping the branch does not kill a mutant the digit map misses.
- **Amendment:** Delete `_ZERO_TO_O` and `_SPACED_ZERO_TARGETS`. `x . 0rg` still refuses through the digit map.

**F-02 [HIGH] — Spaced `1` to `i` never lands in the spaced set**

- **Prompt lines:** Action 6.
- **Authority:** The spaced digit map sends `3` to `e`, so `n3t` is `net`. The same table sends `1` to `i`, and none of `com`, `c0m`, `net`, or `org` contains `i`. `x . 1o` stays prose. The earlier spaced-n3t addendum parked that form.
- **Consequence:** A spaced translate that drops `1` to `i` still passes every row. `x dot 1o` only kills the bare path.
- **Amendment:** A spaced token whose digit map is `io` refuses. `x . 1o` and `acme . 1o` are `paid_checkout` and `sensitive_data`. Literal `acme . io` stays prose. Dropping `io` from the spaced digit targets fails only that row.

**F-03 [HIGH] — A lone CR is the safe direction, and stripping every CR is unpinned**

- **Prompt lines:** Action 9, draft lookup.
- **Authority:** `_row_text` folds `\r\n` to `\n` and leaves a lone `\r`. The #92 row posts when the two walks differ only by CRLF versus LF. Stripping every `\r` still posts that row.
- **Consequence:** `description.replace("\r", "")` ships. A lone CR compared with the same text without that CR would post.
- **Amendment:** `alpha\rbeta` against `alphabeta` refuses with `count` and zero posts. The CRLF pair still posts. The fold stays `\r\n` to `\n`.

**F-04 [HIGH] — Lowercase words are not hosts**

- **Prompt lines:** Action 5 and Action 6.
- **Authority:** A one-character label plus `co`, `io`, or `shop` and a following word is a defanged host (`x . shop now`). A longer label is prose. A digit label plus a digit-mapped `1o` is a step number. `x dot 1o` and `x . shop now` stay refusals.
- **Consequence:** `read . io docs`, `go . shop now`, `tea . co op`, and `step 3 dot 1o` publish as hosts.
- **Amendment:** Those four stay prose on both paths. `x . shop now` and `x dot 1o` still refuse.

**F-05 [HIGH] — Two spaced-letter hosts disagree across the paths**

- **Prompt lines:** Action 5 and Action 6.
- **Authority:** Gift checkout uses `host_matches`. Screenshot text does not, except through the narrower helpers. `x dot c o m` is `x.com` on the gift path and is allowed on the screenshot path. `x . c o today` is allowed on both. `x dot com` on the screenshot path is a separate ruling.
- **Consequence:** Spaced letters that restore `com` publish in a screenshot. Letter-spaced `co` before a word publishes on a one-character label.
- **Amendment:** `x . c o today` and `x dot c o m` refuse on both paths. Screenshot text still allows `x dot com`.

**F-06 [HIGH] — The screenshot co/io/shop helper is the spaced-dot helper**

- **Prompt lines:** Action 5.
- **Authority:** `trailing_outside_host_matches` requires a spaced dot and then calls `host_matches`. `tight_spaced_host_matches` requires a spaced dot and then calls `host_matches`.
- **Consequence:** The co/io/shop screenshot term can be deleted and every row still passes.
- **Amendment:** Remove `trailing_outside_host_matches` and its pattern. `x . shop now` still refuses through the spaced-dot helper.

### Safety and executability

**Verdict:** CONDITIONAL APPROVE.

**S-01 [HIGH] — This slice stays off the held pulls and the state file**

- **Authority:** #63 and #68 are operator holds. Session 08 is not activated. Exit 78 stays HELD.
- **Amendment:** Edit the defang normalizer, screenshot text, the draft-client test, this addendum, and the implementation log. Do not edit `IMPLEMENTATION_STATE.json`. Do not push `build/full-automation`. Do not force-push, rebase, or merge. Do not touch pulls #63 or #68.

**S-02 [HIGH] — No live provider call**

- **Authority:** Fixture transport only.
- **Amendment:** Tests construct fixture rows. No HTTP, no production Notion, no production Etsy.

### Gameability

**Verdict:** CONDITIONAL APPROVE.

**G-01 [HIGH] — One row must not save the next guard**

- **Authority:** A survivor that another row already kills is not a pin.
- **Amendment:** Each mutant below fails its own row and leaves the sibling rows green. `x dot com` on the screenshot path is not changed and is not claimed as a pin.

## 3. Addendum

1. Prove the prompt hash. It stays `a7a406cecd9c93efdec1045f394b911e614cd79366840e33d5c53d9968f7cd33`.
2. Delete the dead `_ZERO_TO_O` branch. `x . 0rg` still refuses.
3. Accept a spaced digit map that lands on `io`. `x . 1o` and `acme . 1o` refuse on both paths. Literal `acme . io` stays prose.
4. A lone `\r` is not folded. `alpha\rbeta` against `alphabeta` refuses with `count` and zero posts. The CRLF pair still posts.
5. Reuse `_TwoWalks` for the CRLF post when the posted body can be passed in.
6. A `co`, `io`, or `shop` after a spaced dot, including letter-spaced `c o`, undoes only when the label is one character and a word follows. A digit label does not take the digit map. The four prose rows stay prose. `x . shop now` and `x dot 1o` still refuse.
7. `x . c o today` and `x dot c o m` refuse on both paths. Screenshot text still allows `x dot com`.
8. Remove the unreachable screenshot co/io/shop helper.
9. Session 08 stays inactive. `current_session` stays 7. `state_revision` stays 64. Exit 78 stays HELD. Do not claim SESSION complete.

## 4. What already holds

Lowercase and all-caps `com`, `c0m`, `net`, and `org` already refuse. Title case stays prose. `x . n3t` already refuses on both paths and `x . N3t` stays prose. `x dot com` already refuses on the gift path and stays allowed on the screenshot path. CRLF and LF of the same description already post. `x . shop now` already refuses.
