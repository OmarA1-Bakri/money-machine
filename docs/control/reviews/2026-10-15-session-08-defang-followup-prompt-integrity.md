# Session 08 Prompt Integrity Review — defang follow-up

**Date:** 2026-10-15
**Prompt:** `prompts/implementation/11_SESSION_08_MERCHANDISING_AND_ASSET_FACTORY.md`
**Verified SHA-256:** `a7a406cecd9c93efdec1045f394b911e614cd79366840e33d5c53d9968f7cd33`
**Scope:** Carry the closed spelled-email and defanged-host rows trunk still lacks, then pin the parked spaced-dot and screenshot survivors. Do not activate Session 08.

The prompt file is not amended. This record is the corrective addendum for this slice.

## 1. Prompt authenticity

**Status:** VERIFIED

The extracted file's SHA-256 equals `a7a406cecd9c93efdec1045f394b911e614cd79366840e33d5c53d9968f7cd33`. The prompt stays the unamended source of record.

## 2. Three-dimensional review

Action 5 refuses sample data in screenshot text. Action 6 refuses a paid checkout host. The closed pulls #81 and #82 were superseded by trunk `74ff34d5`. Open pulls #63 and #68 stay untouched. `IMPLEMENTATION_STATE.json` stays untouched. No live HTTP.

### Fidelity

**Verdict:** CONDITIONAL APPROVE.

**F-01 [HIGH] — A spaced at-sign is not an email on the screenshot path**

- **Prompt lines:** Action 5, screenshot text.
- **Authority:** The spelled-email detector. Trunk already has the #81 and #82 test files. `ceo @ acme dot com` is not among them, and `email_rule_matches` misses it.
- **Consequence:** The screenshot gate allows a spaced `@` plus a spelled dot.
- **Amendment:** `ceo @ acme dot com` is `sensitive_data` from the email rule. Dropping the spaces around `@` publishes it. `ceo@acme dot com` and `ceo at acme dot com` stay refused.

**F-02 [HIGH] — All-caps spaced dots stay prose**

- **Prompt lines:** Action 6, gift host gate.
- **Authority:** The lowercase gate parked `acme . NET`. All-caps is the same separator as lowercase. Title case is not.
- **Consequence:** `acme . NET`, `acme . COM`, and `mail me at acme . COM` publish. `Done . Net` and `Go . Com` must stay prose.
- **Amendment:** An all-uppercase token in `{com, c0m, net, org}` refuses. A mixed-case token stays. `X . COM` refuses with the other all-caps rows.

**F-03 [HIGH] — The casefold after `islower` does not change the token**

- **Prompt lines:** Action 6.
- **Authority:** Case is read before any lowercasing. After `islower`, `casefold` is the identity on the token that reached the set.
- **Consequence:** A casefold before the gate refuses title case. The dead call after the gate does not.
- **Amendment:** Delete the casefold on the lowercase path. Casefolding before the `islower` gate still fails `Go . Com`. All-caps rows stay refused.

**F-04 [HIGH] — Capital Cyrillic Es and capital Greek omicron are unpinned**

- **Prompt lines:** Action 6, lookalike fold.
- **Authority:** The fold maps U+0421 to Latin `C` and U+039F to Latin `O`. Neither mapping has its own row.
- **Consequence:** Deleting the Es map publishes `acme . СOM`. Mapping omicron to lowercase `o` refuses `See . Οrg`.
- **Amendment:** `acme . СOM` (U+0421) refuses. `See . Οrg` (U+039F) stays prose. Each mutant fails only its own row.

**F-05 [HIGH] — The spaced-dot word boundary has no lowercase killer**

- **Prompt lines:** Action 6.
- **Authority:** A later word skips the spaced-dot undo. Title-case rows stay even if that skip is deleted.
- **Consequence:** `acme . com today` would publish as `acme.com`.
- **Amendment:** `acme . com today` stays prose and is the only row that dies when the boundary skip is removed. `acme . com` still refuses. Bare `. org` stays as on this base.

**F-06 [HIGH] — `or url_matches` in screenshot text can be deleted**

- **Prompt lines:** Action 5.
- **Authority:** `refuse_sensitive_text` ORs the URL rule with the email, bracket, and lookalike rules. The shared corpus URL is also a bracket host.
- **Consequence:** A plain `hxxp://` URL publishes when the URL term is removed.
- **Amendment:** `hxxp://acme.com/a` is `sensitive_data`. Removing `or url_matches` fails only that row.

**F-07 [HIGH] — Two #86 survivors are still unpinned**

- **Prompt lines:** Action 8 storage, and the draft lookup before create.
- **Authority:** The post-merge review on trunk `74ff34d5`. `_SPEC.fullmatch` changed to `match` accepts `12x`. Removing `texts.sort()` refuses a reorder that is the same multiset.
- **Consequence:** A suffixed spec passes the shape check. A reordered description walk fails closed with no row that requires the sort.
- **Amendment:** `fixture://<uuid>/12x/<64-hex>` raises `storage path`. Two walks that list the same descriptions in opposite order still post. The marker-swap and description-edit rows stay refusals.

### Safety and executability

**Verdict:** CONDITIONAL APPROVE.

**S-01 [HIGH] — These pins stay on one branch**

- **Prompt lines:** Actions 5, 6, and 8.
- **Authority:** #63 and #68 are operator holds. Session 08 is not activated.
- **Consequence:** Editing `IMPLEMENTATION_STATE.json` or those pulls mixes unrelated work.
- **Amendment:** Edit the defang normalizer, its tests, screenshot text tests, the local store test, the draft client test, this addendum, and the implementation log. Do not edit `IMPLEMENTATION_STATE.json`.

### Gameability

**Verdict:** CONDITIONAL APPROVE.

**G-01 [HIGH] — One row must not save the next guard**

- **Prompt lines:** Each refusal.
- **Authority:** A survivor that another row already kills is not a pin.
- **Consequence:** Title case saves an all-caps hole. A bracket URL saves a deleted `url_matches`. A same-order walk saves a deleted sort.
- **Amendment:** Each mutant above fails its own row and leaves the sibling rows green.

## 3. Addendum

1. Prove the prompt hash. The spelled-email and defanged-host files already match trunk. Add the missing screenshot row: `ceo @ acme dot com` is `sensitive_data`.
2. All-caps spaced dots in `{com, c0m, net, org}` refuse, including `acme . NET`, `acme . COM`, `mail me at acme . COM`, and `X . COM`. Title case stays prose.
3. Remove the casefold that runs after the lowercase gate. Do not casefold before that gate.
4. Pin U+0421 so `acme . СOM` refuses, and pin U+039F so `See . Οrg` stays prose.
5. Pin `acme . com today` as the boundary killer. Bare `. org` stays prose.
6. Pin `hxxp://acme.com/a` as the screenshot URL-rule killer.
7. Pin `12x` as the spec-shape killer, and pin a reordered description pair that still posts.
8. Session 08 stays inactive. `current_session` stays 7. `state_revision` stays 64. Exit 78 stays HELD.

## 4. What already holds

NFKC runs before the case check. Lowercase `com`, `c0m`, `net`, and `org` already refuse, including at the end of the text. Title case already stays. The capital Cyrillic `O` fold already stays prose. The bracket URL in the shared corpus already refuses. UUID and digest suffixes already raise `storage path`. A marker swap and a description edit already refuse with `count`.
