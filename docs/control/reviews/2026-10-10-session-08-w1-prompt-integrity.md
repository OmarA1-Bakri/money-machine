# Session 08 Prompt Integrity Review — W1 merchandising and claims

**Date:** 2026-10-10
**Prompt:** `prompts/implementation/11_SESSION_08_MERCHANDISING_AND_ASSET_FACTORY.md`
**Verified SHA-256:** `a7a406cecd9c93efdec1045f394b911e614cd79366840e33d5c53d9968f7cd33`
**Workbook authority:** `hands-off-money-machine-full-implementation-workbook.md` appendix row for this prompt (5,092 bytes, 236 lines)
**Scope:** Wave 1 only. Actions 1 and 2. Fixture-only A10 copy and claim validation.

The prompt file is not amended. This record is the corrective addendum.

The canonical filename `2026-10-10-session-08-prompt-integrity.md` is the Wave 0 record. Round 2 merged that record from `da671037` and does not overwrite it.

## 1. Prompt authenticity

**Status:** VERIFIED

- The extracted file's SHA-256 equals the workbook appendix value `a7a406cecd9c93efdec1045f394b911e614cd79366840e33d5c53d9968f7cd33`.
- The workbook copy between `COPY START` and `COPY END` contains that same extract.
- The prompt stays the unamended source of record.

## 2. Three-dimensional review

The operator instruction for this wave is actions 1 and 2 only: a fixture-only merchandising agent and a claim validator. The rest of the prompt is not this wave.

### Fidelity

**Verdict:** CONDITIONAL APPROVE. Three high findings, resolved by the addendum.

**F-01 [HIGH] — The prompt's full session is not this wave**

- **Prompt lines:** 1–236, especially actions 3–12 and the required exit code at line 229.
- **Authority:** The operator slice is actions 1 and 2. D-0032 keeps Session 08 inactive. `current_session` stays 7.
- **Consequence of literal execution:** Implementing assets, screenshots, storage, workflow linkage, commissioning, and printing the session exit code would claim the session is finished.
- **Amendment:** Implement actions 1 and 2 only. Do not print the session exit code. Do not activate Session 08. Do not edit `IMPLEMENTATION_STATE.json`.

**F-02 [HIGH] — The eight description parts are not named**

- **Prompt lines:** 27–36. The workbook listing package (section 7) says "the eight-part description" and does not name the parts. `The-Hands-Off-Money-Machine-Playbook.pdf` is not in this tree.
- **Authority:** Workbook listing package; session prompt outputs (hero, image strip, video sequence, price/sale, support and free gift); chapter 15.1 in `docs/playbook/CHAPTER_TO_CAPABILITY_MAP.md`.
- **Consequence of literal execution:** An agent would invent eight headings, or copy playbook prose that is not in the repo.
- **Amendment:** The description is eight ordered roles taken from those repo sources: hook, included, audience, how it works, features, variants, support and free gift, offer. Image-strip frames and video beats follow the session prompt's image and video lists. This names a structure the workbook left unnamed. It does not contradict a named list, so it is not a new decision.

**F-03 [HIGH] — `ListingPackage` cannot be built without media artifacts**

- **Prompt lines:** 26–34 versus action 4 (images, video, PDFs).
- **Authority:** `ListingPackage.validate_playbook_shape` requires the configured ten images and one video. D-0022.
- **Consequence:** Returning a `ListingPackage` from this wave would require placeholder media.
- **Amendment:** A10 returns listing copy: title, eight sections, thirteen tags, hero, image-strip copy, video sequence, price/sale data, and claims. It does not construct `ListingPackage`.

**What the prompt already gets right**

- Claims reference a ProductFact, and the eight rejection classes are named (lines 38–52).
- A failed validation returns the copy to A10 with corrections (line 53).
- A10 is ordered before assets. Tag count and section count are exact (lines 188–189).
- Session 07 section 9 already says merchandising may claim only ledger facts.

### Safety and executability

**Verdict:** CONDITIONAL APPROVE. Four high findings, resolved by the addendum.

**S-01 [HIGH] — The LLM seam can reach the network**

- **Prompt lines:** action 1, which does not name a provider. The repo has `LLMProvider` and `OpenAIProvider`.
- **Authority:** No live HTTP, no Notion, no Etsy, no LLM network calls. Workbook section 12: claim checks belong in code, not only in prompts.
- **Consequence:** A literal "call the model" implementation can send product copy to a provider.
- **Amendment:** Generation is a deterministic function of the supplied facts and the built inputs. Tests may inject a fixture generator. This wave does not call `LLMProvider`.

**S-02 [HIGH] — Open pull requests #63 and #66**

- **Authority:** Do not edit `AGENTS.md`, `CLAUDE.md`, `src/money_machine/control/state.py`, or `tests/bootstrap/test_control_state.py`. Do not push to `build/full-automation`.
- **Consequence:** Those files collide with Omar's open work.
- **Amendment:** Do not edit them. Do not edit `IMPLEMENTATION_STATE.json`. The Wave 0 review path stays untouched.

**S-03 [HIGH] — Commissioning A10 would make a DESIGNED agent executable**

- **Prompt lines:** 201–203.
- **Authority:** `config/agents.yaml` keeps A10 `DESIGNED`. `test_designed_agent_has_no_implementation` requires `get_implementation("A10")` to fail. Exit 78 stays HELD.
- **Consequence:** Registering A10 or flipping commissioning would lift a production gate.
- **Amendment:** Do not register A10. Do not change A07, A08, or A09. Do not commission. The prompt scaffold stays uncommissioned.

**S-04 [HIGH] — An unbounded correction loop does not fail closed**

- **Prompt lines:** 53.
- **Consequence:** A generator that keeps emitting the same bad claim retries forever, or the last bad draft is returned as success.
- **Amendment:** At most three attempts. The draft is returned only when validation passes. Exhausted attempts raise and do not return the bad draft.

**Executability**

- Domain `ProductSpec` in `domain.models.products` is the listing contract. The Session 07 builder uses a different `ProductSpec`. This wave uses the domain contract and does not import the builder.
- There is no domain `ProductFact` type yet. The SQL table exists. This wave uses an in-memory fact with an id. It does not write the table.
- Configured listing rules are 13 tags, 8 description sections, quantity 999. Counts come from `config/product_rules.yaml` (D-0022).

### Gameability

**Verdict:** CONDITIONAL APPROVE. The acceptance criteria below are the ungameable form of the prompt's test lines.

**G-01 [HIGH] — Exact counts can be hardcoded in one fixture**

- **Cheap fake:** A test builds one object with 13 tags and 8 sections and never feeds 12, 14, 7, or 9.
- **Amendment:** 12 and 14 tags are rejected. 7 and 9 sections are rejected. Deleting the tag rule accepts the 12-tag draft. Deleting the section rule accepts the 7-section draft.

**G-02 [HIGH] — One generic "bad claim" test covers none of the classes**

- **Cheap fake:** Reject any claim whose text contains "invalid".
- **Amendment:** Each rejection class has its own failing input. A matching ProductFact for reviews, sales, trust bars, social proof, and automation is accepted. Deleting that class's rule accepts its failing input.

**G-03 [HIGH] — The correction loop can ignore the bad draft**

- **Cheap fake:** Return the happy fixture on the first call and never pass corrections.
- **Amendment:** The first generator result is a bad draft. The second call receives that claim's correction. The regenerated draft passes. A generator that stays bad fails closed after three attempts. Replacing the fail-closed raise with a return yields the bad draft.

**G-04 [HIGH] — A claim can omit or invent a fact id**

- **Cheap fake:** `fact_id` optional, or any UUID accepted.
- **Amendment:** `fact_id` is required. An id that is not in the supplied facts is `unknown_fact`. Deleting that rule accepts the unknown id.

## 3. Corrective addendum

This addendum governs Wave 1. The prompt remains the unamended source of record.

1. Prove the prompt hash, then implement only actions 1 and 2.
2. A10 inputs are the domain `ProductSpec`, in-memory `ProductFact` rows, the built hub list, the built page count, the built variants, notification-dashboard behaviour, shop name, price and anchor, and support and free-gift configuration.
3. A10 outputs are title, the eight ordered description roles, exactly the configured tag count, hero copy, the ten image-strip lines, the five video beats, price/sale data, and a claim list. Every claim has a `ProductFact` id.
4. The validator rejects invented page counts, nonexistent features, variant names that were not built, unsupported automation, invented reviews, invented sales, invented trust bars, and unsupported social proof. It also rejects unknown fact ids, tag counts other than the configured 13, and section sequences other than the eight roles.
5. A failure returns exact per-claim corrections to the generator. The generator rebuilds from facts. At most three attempts. Exhaustion raises and does not return the draft.
6. Generation does not call the LLM, Notion, Etsy, or any network client. The generator is injectable so the correction loop can be proved with a bad first draft.
7. Do not construct `ListingPackage`. Do not add a migration. Do not register or commission A10. Do not edit A07, A08, or A09. Do not edit `IMPLEMENTATION_STATE.json`, `state.py`, `test_control_state.py`, `AGENTS.md`, or `CLAUDE.md`.
8. Exit 78 stays HELD. Session 08 stays inactive. Do not print the session exit code.
9. Killing tests: for each rule above, the real validator rejects the failing input and a mutant with that rule deleted accepts it.

## 4. Deferrals

| Finding | Owner | Reason |
|---|---|---|
| Actions 3–10 (tokens, A11, screenshots, links, lineage, storage, workflow, asset tests) | Later Session 08 waves | Operator slice is actions 1 and 2 |
| Action 11 commissioning | Operator decision after implementation | S-03 |
| Action 12 session exit code | Session 08 close | This wave is not the close |
| Persisting description sections and tags as rows | A later Session 08 wave that writes `listing_versions` | Session 02 deferral; this wave does not migrate |
| Calling `LLMProvider` for prose | Not this wave | S-01; claims are derived from facts in code |
| Activating Session 08 | A later activation | D-0032; fixture copy does not read `current_session` |
| Exit 78 | Unchanged | Operator instruction |

## 5. Round 2 amendment

Review on the first tip showed the deny-list could accept buyer-facing prose that no cited fact states. This amendment is part of the same wave.

1. Every buyer-facing string is one fixed template of the claims that string cites. The generator and the validator call the same `render`. A string that is not that template is `unbound_text`.
2. Comparison folds NFKC, case, whitespace, and Latin lookalikes. A Latin string that also contains a non-Latin letter is rejected before that fold.
3. The deny-list stays a per-surface backstop. A hit is allowed only when that span sits inside a cited fact value on the same surface. One passing claim does not license every other surface.
4. Tags are normalized before the duplicate and length checks. Empty normalized tags are rejected.
5. `#66` merged as `da671037`. This wave merges that commit. It does not edit `state.py`, `test_control_state.py`, or the Wave 0 review file. Session 08 stays inactive.

## 6. Round 3 amendment

Review on tip `209508ea` showed fact values and tag cutting were still open. This amendment is part of the same wave.

1. A features fact must equal `spec.features` item for item. Variant facts must equal the built variant names. Page count must equal the built count. A review, sales, trust, social, automation, or page-count hit is allowed only from that class's own fact kind. Identity and buyer-problem values must pass that deny-list themselves.
2. A tag that does not fit in 20 characters is refused. It is not cut to a prefix. Tags are not built from automation, review, sales, trust, or social claims. Identity and the fixture feature names are longer than 20 characters, so they are skipped. Product type, variants, shop, hubs, and devices fill the playbook count of 13 without dropping a word.
3. Mixed script is checked per token, so a non-Latin shop name can sit beside Latin words. A homoglyph inside one token is still rejected. Each surface renders only its own template id. Secret links must be one `https` URL. Device facts must be a clean list.
4. This round does not edit `state.py`, `test_control_state.py`, the Wave 0 review file, `IMPLEMENTATION_STATE.json`, or `config/agents.yaml`. A10 stays DESIGNED. Session 08 stays inactive.
