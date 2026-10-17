# Session 15 Prompt Integrity Review

**Date:** 2026-10-17
**Prompt:** `prompts/implementation/18_SESSION_15_LIVE_COMMISSIONING_AND_HANDOVER.md`
**Verified SHA-256:** `b09859086ad510862f493227c1da075cc0a29d76ebd07ca4cd6f80710c8ce712`
**Base:** Session 14 is complete at revision 111. `next_session` is 15. Session 15 is not activated. Exit 78 stays HELD.

The prompt file is not amended. This record is the corrective addendum. The review reads the prompt against D-0010, D-0080, and D-0087, and against `AutonomyConfig`, the Etsy and Notion fixture adapters, and the deployment checkpoint. The prompt is 5,243 bytes and 263 lines.

## 1. Prompt authenticity

**Status:** VERIFIED

The extracted file's SHA-256 equals the workbook appendix entry for `18_SESSION_15_LIVE_COMMISSIONING_AND_HANDOVER.md`. The required exit string in the file is `HANDS_OFF_MONEY_MACHINE_COMMISSIONED`.

## 2. Three-dimensional review

### Fidelity

**Verdict:** CONDITIONAL APPROVE.

**F-01 [CRITICAL] — "Connect the real provider accounts" and the first real workflow would leave the fixture boundary.** Sessions 09 through 14 earned keys by calling typed checks. A live Etsy research, Notion build, or Etsy draft is a provider mutation. **Amendment:** `provider_connections_fail_closed` and `linked_workflow_fixture` call the fixture adapters and stop at preflight. **Deferral:** a live account connection. Owner: an operator authority record.

**F-02 [HIGH] — "Confirm deployed exact state" and "Run production smoke tests" would start the held services.** Session 14 recorded `local-wsl` and refused a live deploy. **Amendment:** `deployed_state_checked` reads the checkpoint and refuses a live smoke. Do not edit `worker.py` or `scheduler.py`.

**F-03 [HIGH] — Standing authority asks Omar for production values and then says routine work proceeds automatically.** Inventing `auto_publish`, a purchase cap, or a checkout cap would spend. **Amendment:** `standing_authority_recorded` reads `AutonomyConfig` and keeps publish, deactivate, multiply, purchase, and checkout false. This wave does not invent a missing value.

**F-04 [HIGH] — The prompt sets `status = COMMISSIONED` and `next_session = null`.** D-0010 completion uses `session_status` `complete` and advances `next_session` by one. There is no session 16 prompt, so the generic completion transition cannot close session 15 unchanged. **Amendment:** This wave does not edit `IMPLEMENTATION_STATE.json` and does not write `COMMISSIONED`. **Deferral:** the last-session completion shape. Owner: the Session 15 closure increment.

**F-05 [HIGH] — The exit string, the tag, and the commit subject are not a D-0010 completion.** **Amendment:** Do not write `HANDS_OFF_MONEY_MACHINE_COMMISSIONED`. Do not use `chore(release): commission hands-off money machine` as the evidence. Do not treat `v1.0.0` as a key.

### Safety

**Verdict:** CONDITIONAL APPROVE.

**S-01 [CRITICAL] — Connecting an LLM, Notion, Etsy, Composio, or PostHog reads credentials and can mutate a live account.** **Amendment:** Do not read `.env`, a token, a cookie, or a browser profile. The connection proof refuses a live adapter.

**S-02 [CRITICAL] — "If a real paid competitor purchase or checkout test is enabled, execute it" is spend.** **Amendment:** The fixture workflow refuses purchase and checkout. An enabled flag does not authorize the spend.

**S-03 [HIGH] — "Do not publish a meaningless test listing" still allows a publish.** **Amendment:** No publish. The workflow stops at preflight.

**S-04 [HIGH] — Tag `v1.0.0` and push the private remote.** **Amendment:** This wave does not tag and does not push a release.

### Gameability

**Verdict:** CONDITIONAL APPROVE.

**G-01 [CRITICAL] — The exit string, the commit subject, or the tag `v1.0.0` as completion.** **Amendment:** None of those strings is an evidence key. Completion is the seven-key contract.

**G-02 [HIGH] — A paragraph that says the accounts are connected.** **Amendment:** `provider_connections_fail_closed` is earned only when the Etsy and Notion fixture adapters are selected and a live adapter raises.

**G-03 [HIGH] — A config file with `auto_publish` true.** **Amendment:** `standing_authority_recorded` is earned only when the typed authority keeps publish, purchase, and checkout false.

**G-04 [HIGH] — An acceptance matrix that marks every item PASS.** **Amendment:** `acceptance_matrix_recorded` requires every definition-of-done item to be `PASS`, `FAIL`, or `BLOCKED_EXTERNAL`. A live item with no live call is `BLOCKED_EXTERNAL`. A `FAIL` is not a pass.

**G-05 [HIGH] — A handover page that says the machine is commissioned.** **Amendment:** The handover is cited by the acceptance matrix and must not contain the exit string. A page is not, by itself, a true key.

## 3. Corrective addendum

1. The prompt hash stays `b09859086ad510862f493227c1da075cc0a29d76ebd07ca4cd6f80710c8ce712`. The prompt file stays byte-identical.
2. This wave installs the Session 15 contract and does not activate the session. Do not edit `IMPLEMENTATION_STATE.json`. Do not write the exit string, the commit subject `chore(release): commission hands-off money machine`, or the tag `v1.0.0`.
3. The contract keys are `deployed_state_checked`, `provider_connections_fail_closed`, `standing_authority_recorded`, `linked_workflow_fixture`, `acceptance_matrix_recorded`, `control_files_and_checkpoint_current`, and `evidence_closure_commit_recorded`. A later activation installs every key false.
4. A live account, a live publish, a purchase, a checkout, a live PostHog event, Exit 78, and `HANDS_OFF_MONEY_MACHINE_COMMISSIONED` are not keys.
5. Do not edit `worker.py` or `scheduler.py`. Do not start a service. Exit 78 stays HELD.
6. Do not publish, spend, message a buyer, or call live Etsy, Notion, PostHog, Composio, or an LLM. Tests open no socket and read no provider credential.
7. Carry forward `AutonomyConfig`, the Etsy and Notion fixture adapters, the Session 14 checkpoint, and `commissioned_agents` staying empty.
8. Level 1 for this wave is the contract test, then `ruff check` and `pyright` on the touched control modules.

## 4. Deferrals

**D-01 — Session 15 activation.** Owner: the next transition. The contract is installed. The session stays inactive.

**D-02 — A live provider connection, publish, purchase, or checkout.** Owner: an operator authority record. The fixture adapters and the fail-closed authority are the evidence.

**D-03 — The last-session completion shape.** Owner: the Session 15 closure increment. There is no session 16 prompt, and this wave does not set `next_session` to null.

**D-04 — Exit 78 removal.** Owner: an operator authority record. This session does not start the worker or the scheduler.

## 5. What already holds

`AutonomyConfig` already refuses `auto_publish` unless live external mutations are enabled, and the checked-in defaults keep publish and purchase false. The Etsy and Notion fixture adapters already exist beside the live adapters. The Session 14 checkpoint already refuses a deploy that is not the recorded local target. Unapproved spend stays refused.
