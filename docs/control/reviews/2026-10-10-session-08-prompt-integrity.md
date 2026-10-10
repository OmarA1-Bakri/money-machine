# Session 08 Prompt Integrity Review — W0 activation gate

**Date:** 2026-10-10
**Prompt:** `prompts/implementation/11_SESSION_08_MERCHANDISING_AND_ASSET_FACTORY.md`
**Verified SHA-256:** `a7a406cecd9c93efdec1045f394b911e614cd79366840e33d5c53d9968f7cd33`
**Workbook authority:** `hands-off-money-machine-full-implementation-workbook.md` appendix row for this prompt (5,092 bytes, 236 lines)
**Scope:** Wave 0 only. Governance. Do not activate Session 08. Do not implement A10 or any other product code.

The prompt file is not amended. This record is the corrective addendum.

## 1. Prompt authenticity

**Status:** VERIFIED

- The extracted file's SHA-256 equals the workbook appendix value `a7a406cecd9c93efdec1045f394b911e614cd79366840e33d5c53d9968f7cd33`.
- The workbook copy between `COPY START` and `COPY END` contains that same extract.
- The prompt stays the unamended source of record.

## 2. Three-dimensional review

The operator instruction for this wave is not the session prompt. It is a governance slice. On `00b952a8` the validator never checked prior-session evidence for any session: a 0→1 activation with every key false was accepted. A Session 08 candidate was rejected earlier, with `unsupported activation: no completion evidence contract for session 8`, because `SESSION_EVIDENCE_KEYS` ended at 7. Adding that contract alone would have exposed the hole. This wave adds both the contract and the check.

### Fidelity

**Verdict:** CONDITIONAL APPROVE. Two high findings, resolved by the addendum.

**F-01 [HIGH] — The prompt's full session is not this wave**

- **Prompt lines:** 1–236, especially actions 1–12 and the required exit code at line 229.
- **Authority:** The operator slice is the activation gate only. D-0010 activation is a separate transition from product work. D-0032 records Session 07 complete with the twelve evidence keys false and says Session 08 is not activated.
- **Consequence of literal execution:** Implementing A10 through commissioning and printing `SESSION_08_MERCHANDISING_AND_ASSETS_COMPLETE` would claim the session is finished and would move control state this wave forbids.
- **Amendment:** Do not implement product code. Do not set the exit code. Do not activate Session 08 in `IMPLEMENTATION_STATE.json`.

**F-02 [HIGH] — Activation of Session 08 has no evidence contract, so a prior-evidence check is not the only blocker**

- **Prompt lines:** exit criteria, lines 215–224. They name outcomes. They do not name evidence-key strings.
- **Authority:** D-0010: a session without an entry in `SESSION_EVIDENCE_KEYS` cannot be activated. Session 07's keys were installed in code at the activation wave (`b0536cd`). `validate_activation_transition` rejects `next_session` 8 today with `no completion evidence contract for session 8`, before it looks at Session 07's keys. The checked-in continuity test's `if session == 7` branch (`tests/bootstrap/test_control_state.py`) allows those twelve keys to stay false. The validator has no `session == 7` branch. The hole is that the validator never requires the completed session's keys to be true, for Session 07 or for any earlier session.
- **Consequence:** Adding only a prior-evidence check still rejects a well-formed Session 08 candidate after the twelve keys are true, for a different reason. Deleting the new check would not make that candidate succeed, so the killing test would not kill. Session 06 met the prior-evidence rule because its close set every key true and the continuity test required that for every complete session except the Session 07 special case.
- **Amendment:** Define the Session 08 evidence contract in the validator module so a candidate that installs those keys, all false, is accepted once Session 07's keys are all true. Do not write those keys into `IMPLEMENTATION_STATE.json`. Do not flip any Session 07 key. The continuity pin that the checked-in Session 07 keys are false stays. It records D-0032. It is not an activation exemption.

**What the prompt already gets right**

- A10 is ordered first, then claim validation, then tokens, A11, screenshots, links, lineage, storage, and workflow (lines 11–182).
- Claims must reference a ProductFact and invented counts, features, reviews, sales, and trust bars are rejected (lines 38–52).
- The next prompt after a real session close is `12_SESSION_09_ETSY_DRAFT_PUBLISH_AND_PREFLIGHT.md`. This wave does not advance `next_session` or `next_prompt`.

### Safety and executability

**Verdict:** CONDITIONAL APPROVE. Two high findings, resolved by the addendum.

**S-01 [HIGH] — Actions 5 and 11 reach live providers and commissioning**

- **Prompt lines:** 116–125 (screenshot acquisition) and 201–203 (commission A10 and A11).
- **Authority:** No live HTTP, no Notion, no Etsy. Exit 78 stays HELD. `commissioned_agents` is empty. A10 is `DESIGNED` in `config/agents.yaml`.
- **Consequence:** A literal run that found credentials could capture real screenshots or mark agents commissioned.
- **Amendment:** This wave performs no live HTTP, opens no Notion workspace, creates no Etsy listing, and does not lift Exit 78. Do not commission A10 or A11.

**S-02 [HIGH] — Open pull request #63 and the Session 07 close record**

- **Authority:** Do not push to `build/full-automation`. Do not rebase, force-push, or close a branch or pull request this wave did not create. #63 (`cursor/cloud-agent-environment-1467`) touches only `AGENTS.md` and `CLAUDE.md`.
- **Consequence:** Editing those files, or rewriting the Session 07 state record, collides with Omar's close and with #63.
- **Amendment:** Touch the control-state validator, its tests, this review, and the implementation log. Leave `AGENTS.md`, `CLAUDE.md`, and `IMPLEMENTATION_STATE.json` unchanged.

**Executability**

- The checked-in state is session 7, `complete`, `next_session` 8, twelve evidence keys false, revision 64.
- `validate_activation_transition` is the CLI `activate` gate.
- No product module reads `current_session` as a licence to implement A10. W1 fixture work does not require Session 08 to be activated.

### Gameability

**Verdict:** CONDITIONAL APPROVE. One high finding, resolved by the addendum.

**G-01 [HIGH] — Deleting the new check, or wrapping it, satisfies a careless reading**

- **Cheap fake:** Delete the prior-evidence call, or wrap it in `current_session != 7`. The base validator has no `session == 7` branch. The continuity pin is the only `session == 7` branch, and it is a test. Pointing at the old missing-contract error, or at that pin, does not prove the new check.
- **Ungameable for this wave:** Session 08 activation with the twelve Session 07 keys false is rejected by the CLI and names those keys. The same candidate with those keys true is accepted and installs the Session 08 contract all false. A mutant that deletes the check, and a mutant that wraps it in `current_session != 7`, accept the false-key candidate. The real function rejects it. Direct tests also reject one missing key, one extra key, exactly one false key (and name only that key), and a previous session with no contract (`ControlStateError`, not `KeyError`). A behavioural call, with no source inspection, rejects the session-7 false-key pair, so the wrap fails that test. No Session 07 evidence key is flipped. `current_session` stays 7.

## 3. Corrective addendum

This addendum governs Wave 0. The prompt remains the unamended source of record.

1. Prove the prompt hash, then implement only the slice below.
2. `validate_activation_transition` rejects activation of session N+1 unless session N's evidence keys are exactly its contract and every value is true. No session number is exempt. Session 06 met this rule because every Session 06 key was true.
3. Session 08 evidence contract, installed only by a future activation, all false, not written into `IMPLEMENTATION_STATE.json`:
   - `merchandising_agent_implemented`
   - `claim_validation_implemented`
   - `design_tokens_implemented`
   - `creative_asset_agent_implemented`
   - `screenshot_acquisition_implemented`
   - `link_validation_implemented`
   - `asset_lineage_recorded`
   - `asset_storage_implemented`
   - `merchandising_workflow_linked`
   - `merchandising_asset_tests_pass`
   - `control_files_and_checkpoint_current`
   - `evidence_closure_commit_recorded`
4. Killing tests: (a) Session 08 activation with the twelve Session 07 keys false is rejected; (b) with those keys true it is accepted; (c) deleting the check, or wrapping it in `current_session != 7`, fails a test. Direct tests reject a missing key, an extra key, exactly one false key (naming only that key), and a previous session with no evidence contract (`ControlStateError`, not `KeyError`).
5. Do not flip an evidence key. Do not change `current_session`, `next_session`, `next_prompt`, `session_status`, `completed_sessions`, or `state_revision`. Do not activate Session 08. Exit 78 stays HELD.
6. Do not weaken an existing activation or completion check.
7. No live HTTP, no Notion, no Etsy, no product code under `src/` except the control-state validator module.
8. Leave the checked-in continuity pin (`if session == 7`, keys false, `head_sha` at the #64 tip) in place. That pin describes D-0032. It does not authorise activation.

## 4. Deferrals

| Finding | Owner | Reason |
|---|---|---|
| Actions 1–10 (A10, claims, tokens, A11, screenshots, links, lineage, storage, workflow, tests) | Later Session 08 waves | Operator slice is the activation gate |
| Action 11 commissioning | Operator decision after implementation | S-01 |
| Action 12 session exit code | Session 08 close | This wave is not the close |
| Flipping the twelve Session 07 evidence keys | A later record that actually earns them | D-0032; this wave must not edit that record |
| Exit 78 | Unchanged | Operator instruction |
| Whether W1 must activate Session 08 | No | Fixture A10 and claim validation do not read `current_session` as a gate. A10 stays `DESIGNED`. This wave does not activate Session 08, and W1 does not need that activation to land fixture-only code. |
