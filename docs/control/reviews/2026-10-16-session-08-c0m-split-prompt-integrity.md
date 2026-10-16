# Session 08 Prompt Integrity Review — c0m split

**Date:** 2026-10-16
**Prompt:** `prompts/implementation/11_SESSION_08_MERCHANDISING_AND_ASSET_FACTORY.md`
**Verified SHA-256:** `a7a406cecd9c93efdec1045f394b911e614cd79366840e33d5c53d9968f7cd33`
**Scope:** One fixture split. `test_a_lowercase_cyrillic_em_in_c0m_is_refused` asserts both `refuse_paid_checkout` and `refuse_sensitive_text` on `acme . c0\u043c` (U+043C). The fold `\u043c` to `m` is already on trunk. Do not activate Session 08. Do not commission A10, A11, or A13. Do not lift Exit 78.

The prompt file is not amended. This record is the corrective addendum.

## 1. Prompt authenticity

**Status:** VERIFIED.

The extracted file's SHA-256 equals `a7a406cecd9c93efdec1045f394b911e614cd79366840e33d5c53d9968f7cd33`. The prompt stays the unamended source of record.

## 2. Three-dimensional review

### Fidelity

**Verdict:** CONDITIONAL APPROVE.

**F-01 [HIGH] — One row covers two gates**

- **Prompt lines:** Action 4, "No paid checkout links." Action 5, sensitive and sample data on screenshots.
- **Authority:** Gift text and screenshot text are separate refusals. The parked #94 note says the `acme . c0\u043c` asserts share one test.
- **Consequence:** Deleting either gate fails the same test. Pytest stops on the first assert, so the screenshot assert never runs.
- **Amendment:** Two tests. The gift test calls only `refuse_paid_checkout`. The screenshot test calls only `refuse_sensitive_text`. `x dot co\u043c` stays on `test_screenshot_text_refuses_a_lowercase_cyrillic_em_dot`.

### Safety and executability

**Verdict:** CONDITIONAL APPROVE.

**S-01 [HIGH] — The session prompt commissions and reaches providers**

- **Prompt lines:** Action 5 (screenshot acquisition) and Action 11 (commission A10 and A11).
- **Authority:** D-0028. `COMMISSIONED` needs an operator decision plus a simulation run. A10 and A11 are fixture-only and `DESIGNED`. A13 can publish and spend. Exit 78 stays HELD. `current_session` stays 7.
- **Consequence:** A literal session run could capture live screenshots, mark agents commissioned, or edit the draft client and `listing_text.py`.
- **Amendment:** Fixture tests, this addendum, and the implementation log only. Do not edit `listing_text.py`, the Etsy draft client, or `IMPLEMENTATION_STATE.json`. Do not touch pull requests #63 or #68. No live HTTP.

### Gameability

**Verdict:** CONDITIONAL APPROVE.

**G-01 [HIGH] — Either path can hide behind the other assert**

- **Prompt lines:** Action 4 and Action 5, as pinned by the shared test.
- **Authority:** The fold is shared. Deleting it fails the gift assert, the screenshot `x dot co\u043c` row, and the gift `acme . co\u043c` row together.
- **Consequence:** A green combined test does not show which path still refuses `acme . c0\u043c`.
- **Amendment:** Measure a gift-only mutant and a screenshot-only mutant. Each must fail only its own new test. Restore the source after each. Do not change production behavior. The fold stays.

## 3. Addendum

1. Prove the prompt hash. It stays `a7a406cecd9c93efdec1045f394b911e614cd79366840e33d5c53d9968f7cd33`.
2. Replace `test_a_lowercase_cyrillic_em_in_c0m_is_refused` with two tests on `acme . c0\u043c`. One asserts `refuse_paid_checkout` only. The other asserts `refuse_sensitive_text` only.
3. Leave `x dot co\u043c` on `test_screenshot_text_refuses_a_lowercase_cyrillic_em_dot`. Prose stays prose.
4. Do not edit production unless a focused test shows a path is missing. The fold `\u043c` to `m` is already on trunk.
5. Do not activate Session 08. Do not commission A10, A11, or A13. Do not lift Exit 78. Do not edit `IMPLEMENTATION_STATE.json`.
