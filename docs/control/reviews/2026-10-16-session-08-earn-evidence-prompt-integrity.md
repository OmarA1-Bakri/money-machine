# Session 08 Prompt Integrity Review — earn the evidence keys

**Date:** 2026-10-16
**Prompt:** `prompts/implementation/11_SESSION_08_MERCHANDISING_AND_ASSET_FACTORY.md`
**Verified SHA-256:** `a7a406cecd9c93efdec1045f394b911e614cd79366840e33d5c53d9968f7cd33`
**Workbook authority:** appendix row for this prompt (5,092 bytes)
**Scope:** Record the Session 08 evidence keys by running the fixture chain that is already in the tree. Do not commission A10 or A11. Do not complete Session 08. Do not print the exit code.

The prompt file is not amended. This record is the corrective addendum. It does not overwrite the earlier Session 08 records.

## 1. Prompt authenticity

**Status:** VERIFIED

The extracted file's SHA-256 equals `a7a406cecd9c93efdec1045f394b911e614cd79366840e33d5c53d9968f7cd33`. The prompt stays the unamended source of record.

## 2. Three-dimensional review

The operator instruction is to continue after activation. Revision 67 has Session 08 incomplete and every evidence key false. The fixture modules for actions 1 through 9 are already on the branch. D-0037 activated the session. It did not earn a key.

### Fidelity

**Verdict:** CONDITIONAL APPROVE.

**F-01 [HIGH] — The prompt's exit is not this slice**

- **Prompt lines:** 201–229.
- **Authority:** D-0010 completion requires every key except the closure key to be true already, and `head_sha` to equal the prior closure commit. `head_sha` is still `b782751fdb1b255c436ff7f6fa655e6d783b1e8c`. The prior closure is `5a48a4c9c04c74019e382a62b2c3c0abfd5b9cfb`. D-0028 keeps Exit 78 HELD. A10 and A11 stay `DESIGNED`.
- **Consequence:** Printing `SESSION_08_MERCHANDISING_AND_ASSETS_COMPLETE`, commissioning the agents, or running `apply-completion` would claim a close the pointer cannot accept.
- **Amendment:** Earn the ten behavioral keys and `control_files_and_checkpoint_current` together. Leave `evidence_closure_commit_recorded` false. Leave the session incomplete. Do not commission. Do not print the exit code.

**F-02 [HIGH] — A hand edit is not a transition**

- **Prompt lines:** 215–224. The exit criteria name outcomes. They do not name the evidence-key strings.
- **Authority:** D-0036. Session 07 keys flipped only through `record-evidence` after `prove_session_07()`. Activation installed the Session 08 keys all false.
- **Consequence:** Setting the twelve booleans in `IMPLEMENTATION_STATE.json` by hand would skip the fixture chain.
- **Amendment:** `prove_session_08()` runs merchandising, claim validation, design tokens, screenshots, the ten images, the walkthrough, both delivery PDFs, link validation, lineage, local storage, and the ready draft. The ten behavioral keys flip only when that function returns them. The control-file key flips in the same transition when the five control files exist. D-0038 records the rule.

### Safety and executability

**Verdict:** CONDITIONAL APPROVE.

**S-01 [HIGH] — Screenshot, link, and draft steps can open a network**

- **Prompt lines:** 116–138 and 181.
- **Authority:** No live Notion, Etsy, or S3. The screenshot module's default fetcher raises `live_acquisition`. The link checker raises `live_link_check`. The draft client has no default transport.
- **Amendment:** The proof injects no live URL, no live fetcher, and no live checker. The draft transport is an in-memory shop. Storage is `LocalAssetStore` in simulation mode. No socket is opened by this slice.

**S-02 [HIGH] — The recorded root is still the operator machine**

- **Authority:** D-0037. `repo_root` stays `/mnt/d/Money Machine`. The recorded `branch` stays `build/full-automation`.
- **Amendment:** The evidence transition uses the same worktree check as D-0036. The state file must be the canonical path inside the Git toplevel. `head_sha` and `evidence_closure_commit_sha` do not change.

### Gameability

**Verdict:** CONDITIONAL APPROVE.

**G-01 [HIGH] — Returning the key set without the chain satisfies a careless reading**

- **Cheap fake:** `prove_session_08` returns the ten names and never calls `merchandise`, `render_listing_images`, or `prepare_etsy_draft`.
- **Amendment:** Each check raises `Session08ProofError` with its own code when the artifact is missing. The returned set is the ten behavioral keys only after the chain has produced thirteen tags, eight description sections, three variant screenshots, ten images, one video, a two-page README, a one-page gift PDF, a passed link report, bound lineage, a stored object whose bytes round-trip, and a draft whose `state` is `draft` and whose `ready` is true. A second image render must hash the same. The transition re-runs the proof. One key, or the closure key, is refused.

## 3. Corrective addendum

1. Prove the prompt hash. It stays `a7a406cecd9c93efdec1045f394b911e614cd79366840e33d5c53d9968f7cd33`.
2. Add `prove_session_08()`. It runs the existing fixture chain and returns only the ten behavioral keys.
3. Extend `record-evidence` so an incomplete Session 08 records those ten keys and `control_files_and_checkpoint_current` together. The closure key stays false.
4. Keep `current_session` at 8 and `session_status` incomplete. Keep `head_sha` and `evidence_closure_commit_sha`.
5. Do not commission A10 or A11. Do not print `SESSION_08_MERCHANDISING_AND_ASSETS_COMPLETE`. Do not run `apply-completion`.
6. Exit 78 stays HELD. No live HTTP, Notion, Etsy, or S3.
7. Record the rule as D-0038.

## 4. Deferrals

**D-01 — Session 08 completion.** Owned by a later transition. `head_sha` still does not equal the prior closure commit, so `validate_completion_transition` refuses. This slice does not move `head_sha`.

**D-02 — Commissioning A10 and A11.** Owned by the prompt's action 11 after real output inspection. Both stay `DESIGNED`.

**D-03 — Exit 78.** Stays HELD under D-0028.

## 5. What already holds

Actions 1 through 9 already have fixture modules and tests. Activation at revision 67 installed the Session 08 contract with every key false. Session 07's twelve keys stay true on the live pointer and false on the historical close `00b952a83bffcec8d442468223d64dd9b2d3e6df`.
