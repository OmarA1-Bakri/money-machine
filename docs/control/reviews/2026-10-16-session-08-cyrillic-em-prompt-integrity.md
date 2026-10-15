# Session 08 Prompt Integrity Review — Cyrillic Em

**Date:** 2026-10-16
**Prompt:** `prompts/implementation/11_SESSION_08_MERCHANDISING_AND_ASSET_FACTORY.md`
**Verified SHA-256:** `a7a406cecd9c93efdec1045f394b911e614cd79366840e33d5c53d9968f7cd33`
**Scope:** One gift-host pin. The lookalike fold already maps Cyrillic Es and O. It does not map Cyrillic Em, so `acme . СОМ` stays prose. Do not activate Session 08. Do not commission A10, A11, or A13. Do not lift Exit 78.

The prompt file is not amended. This record is the corrective addendum.

## 1. Prompt authenticity

**Status:** VERIFIED on the prior Session 08 records. The prompt file is unchanged.

## 2. Three-dimensional review

### Fidelity

**Verdict:** CONDITIONAL APPROVE.

**F-01 [HIGH] — Cyrillic Em is outside the fold**

- **Prompt lines:** Action 6, gift host gate.
- **Authority:** The fold maps U+0421 to Latin `C` and U+041E to Latin `O`. U+041C is the same lookalike class and is already folded to `m` on the listing-text path. The gift-host fold omits it.
- **Consequence:** `acme . СОМ` (U+0421 U+041E U+041C) publishes. Mapping U+041C to lowercase `m` leaves `COm`, which stays prose. Mapping U+043C to uppercase `M` leaves `coM`, which stays prose.
- **Amendment:** `acme . СОМ` refuses. `acme . coм` (U+043C) refuses. Title case stays prose.

### Safety and executability

**Verdict:** CONDITIONAL APPROVE.

**S-01 [HIGH] — Commissioning is not ready**

- **Prompt lines:** Action 11.
- **Authority:** D-0028. `COMMISSIONED` needs an operator decision record plus a simulation run from research through analytics. A10 and A11 are fixture-only and `DESIGNED`. A13 can publish and spend.
- **Consequence:** Marking them commissioned would let a worker treat unfinished fixture code as production.
- **Amendment:** Do not edit `config/agents.yaml` or `IMPLEMENTATION_STATE.json`. Exit 78 stays HELD. Session 08 stays inactive.

### Gameability

**Verdict:** CONDITIONAL APPROVE.

**G-01 [HIGH] — The Es row must not save the Em row**

- **Prompt lines:** Action 6.
- **Authority:** `acme . СOM` already refuses through the Es map alone.
- **Consequence:** A missing Em map still passes that row.
- **Amendment:** The all-caps Em row fails when U+041C is deleted or mapped to `m`. The lowercase row fails when U+043C is deleted or mapped to `M`.

## 3. Addendum

1. Prove the prompt hash. It stays `a7a406cecd9c93efdec1045f394b911e614cd79366840e33d5c53d9968f7cd33`.
2. Map U+043C to `m` and U+041C to `M` in the gift-host fold, preserving case.
3. `acme . СОМ` and `acme . coм` refuse. Existing title-case rows stay prose.
4. Do not activate Session 08. Do not commission A10, A11, or A13. Do not lift Exit 78. Do not edit `IMPLEMENTATION_STATE.json`.
