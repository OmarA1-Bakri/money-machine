# Session 13 Prompt Integrity Review

**Date:** 2026-10-17
**Prompt:** `prompts/implementation/16_SESSION_13_E2E_HARDENING_AND_FAILURE_RECOVERY.md`
**Verified SHA-256:** `d277afd72c2c90c29e0a8d2e4b607bb342b32d84fd485151de7ad6a1b32e21f2`
**Base:** Session 12 is complete at revision 97. `next_session` is 13. Session 13 is not activated. Exit 78 stays HELD.

The prompt file is not amended. This record is the corrective addendum. The review reads the prompt against D-0010, D-0020, D-0026, and D-0028. The prompt is 4,650 bytes and 256 lines.

## 1. Prompt authenticity

**Status:** VERIFIED

The extracted file's SHA-256 equals the workbook appendix entry for `16_SESSION_13_E2E_HARDENING_AND_FAILURE_RECOVERY.md`. The required exit string in the file is `SESSION_13_E2E_AND_HARDENING_COMPLETE`.

## 2. Three-dimensional review

### Fidelity

**Verdict:** CONDITIONAL APPROVE.

**F-01 [CRITICAL] — "Implement every MISSING item" would open live paths.** The inventory names playbook steps, job types, events, lifecycle transitions, agents, provider actions, console views, and runbooks. Literal execution treats every fail-closed `NotImplementedError` as a stub to replace. **Amendment:** The matrix records one of the four classifications for each required row. A live credential gap stays `BLOCKED_BY_EXTERNAL_CREDENTIAL` or `MISSING`. A fail-closed raise stays. **Deferral:** implementing a live provider path. Owner: an operator authority record.

**F-02 [HIGH] — Failure injection would crash a live worker and expire live tokens.** Worker crash, scheduler restart, database reconnect, and expired Etsy or Notion credentials are named. **Amendment:** Each injection is a fixture. It ends in recovery or an exact blocked state. **Deferral:** a live process crash or a live credential. Owner: the operator under D-0028.

**F-03 [HIGH] — Backup and restore would copy a live database.** **Amendment:** The backup key is an in-memory snapshot of a workflow, a job, a product, a listing, and an incident. A second restore does not duplicate them. **Deferral:** a live PostgreSQL backup. Owner: an operator authority record.

**F-04 [HIGH] — The exit string is not a D-0010 completion.** **Amendment:** Do not write `SESSION_13_E2E_AND_HARDENING_COMPLETE`. Do not edit `IMPLEMENTATION_STATE.json` in the contract commit. **Deferral:** activation. Owner: the next transition after this contract.

**F-05 [HIGH] — Broad verification demands a production Docker build and browser E2E.** **Amendment:** This wave is the contract test, `ruff check`, and `pyright` on the touched control modules. **Deferral:** the full suite, the frontend gates, and browser E2E. Owner: the session exit after the keys are earned.

### Safety

**Verdict:** CONDITIONAL APPROVE.

**S-01 [CRITICAL] — Literal execution removes fail-closed raises and starts the worker.** **Amendment:** Do not edit `worker.py` or `scheduler.py`. Do not replace a fail-closed `NotImplementedError` with success. Exit 78 stays HELD. Tests open no socket and read no provider credential.

**S-02 [HIGH] — A secret review can read and print credentials.** **Amendment:** Do not read `.env`, a browser profile, or a provider payload. Do not commit a secret. The matrix does not quote a credential.

**S-03 [HIGH] — A duplicate publish request can publish twice on a live shop.** **Amendment:** The duplicate effect is a fixture. It does not call Etsy, Notion, or PostHog.

### Gameability

**Verdict:** CONDITIONAL APPROVE.

**G-01 [CRITICAL] — The exit string, or the commit subject `test(system): complete E2E and failure hardening`, as completion.** **Amendment:** Neither string is an evidence key. Completion is the six-key contract.

**G-02 [HIGH] — A matrix that marks every row `IMPLEMENTED_AND_TESTED`.** **Amendment:** `implementation_matrix_recorded` is earned only when each required row has one of the four classifications and a live gap is not relabeled as implemented.

**G-03 [HIGH] — One function that returns success for every injected failure.** **Amendment:** `failure_injection_implemented` is earned only when each named injection, including a restart and a duplicate effect, ends in recovery or an exact blocked state.

**G-04 [HIGH] — A backup that copies nothing and reports restored.** **Amendment:** `backup_restore_fixture_implemented` is earned only when the restored fixture contains the workflow, job, product, listing, and incident from the snapshot, and a second restore does not duplicate them.

## 3. Corrective addendum

1. The prompt hash stays `d277afd72c2c90c29e0a8d2e4b607bb342b32d84fd485151de7ad6a1b32e21f2`. The prompt file stays byte-identical.
2. This wave installs the Session 13 contract and does not activate the session. Do not edit `IMPLEMENTATION_STATE.json`. Do not write the exit string or the commit subject `test(system): complete E2E and failure hardening`.
3. The contract keys are `implementation_matrix_recorded`, `synthetic_paths_implemented`, `failure_injection_implemented`, `backup_restore_fixture_implemented`, `control_files_and_checkpoint_current`, and `evidence_closure_commit_recorded`. A later activation installs every key false.
4. Live failure injection, a live PostgreSQL backup, a production Docker build, browser E2E, Exit 78, and `SESSION_13_E2E_AND_HARDENING_COMPLETE` are not keys.
5. Do not edit `worker.py` or `scheduler.py`. Do not replace a fail-closed raise with success. Exit 78 stays HELD.
6. Do not publish, spend, message a buyer, or call live Etsy, Notion, or PostHog. Tests open no socket and read no provider credential.
7. Level 1 for this wave is the contract test, then `ruff check` and `pyright` on the touched control modules.

## 4. Deferrals

**D-01 — Session 13 activation.** Owner: the next transition. The contract is installed. The session stays inactive.

**D-02 — Live failure injection and live credentials.** Owner: the operator under D-0028. A fixture injection is not a live crash and not a live token.

**D-03 — Live PostgreSQL backup and restore.** Owner: an operator authority record. The fixture snapshot is the evidence key.

**D-04 — The full quality suite, the production Docker build, and browser E2E.** Owner: the session exit after the keys are earned.

## 5. What already holds

The fixture-backed workflow chain is the right shape for the synthetic paths. External credential gaps must stay explicit. Control files remain a real exit criterion. Exit 78 stays HELD. Etsy remains the commerce source.
