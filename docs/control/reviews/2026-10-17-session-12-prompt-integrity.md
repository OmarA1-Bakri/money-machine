# Session 12 Prompt Integrity Review

**Date:** 2026-10-17
**Prompt:** `prompts/implementation/15_SESSION_12_OPERATOR_CONSOLE_AND_POSTHOG.md`
**Verified SHA-256:** `c84a6c59948264f654efc1c11448e3a01bbc0c0f07960b1792d7681e96e48677`
**Base:** Session 11 is complete at revision 90. `next_session` is 12. Session 12 is not activated. Exit 78 stays HELD.

The prompt file is not amended. This record is the corrective addendum. The review reads the prompt against D-0010, D-0020, D-0026, D-0028, and the offline `PostHogClient`.

## 1. Prompt authenticity

**Status:** VERIFIED

The extracted file's SHA-256 equals the workbook appendix entry for `15_SESSION_12_OPERATOR_CONSOLE_AND_POSTHOG.md` (4,280 bytes, 226 lines). The required exit string in the file is `SESSION_12_OPERATOR_CONSOLE_COMPLETE`.

## 2. Three-dimensional review

### Fidelity

**Verdict:** CONDITIONAL APPROVE.

**F-01 [CRITICAL] — "PostHog receives useful operational events" is a live capture.** `PostHogClient.capture` queues in memory and raises when telemetry is disabled. It does not open a socket. **Amendment:** This wave does not capture to a live project. **Deferral:** live dispatch. Owner: an operator authority record.

**F-02 [HIGH] — Operator actions would write standing authority and run the scheduler.** Pause, resume, cap changes, credential status, and "trigger safe schedule run" sit on D-0020 and D-0028. **Amendment:** Name the actions and fail them closed. Do not edit autonomy files, `worker.py`, or `scheduler.py`. **Deferral:** a live operator mutation. Owner: the operator under D-0028.

**F-03 [HIGH] — "API completion" would expose live shop, job, and listing rows.** **Amendment:** The read model is typed and in memory. **Deferral:** a deployed API. Owner: the operator console session after activation.

**F-04 [HIGH] — The exit string is not a D-0010 completion.** **Amendment:** Do not write `SESSION_12_OPERATOR_CONSOLE_COMPLETE`. Do not edit `IMPLEMENTATION_STATE.json` in the contract commit. **Deferral:** activation. Owner: the next transition after this contract.

**F-05 [HIGH] — A Next.js console and browser E2E are not on the trunk.** **Amendment:** The contract names the read model, the exception views, redaction, and fail-closed actions. It does not claim a deployed UI. **Deferral:** the Next.js app and browser E2E. Owner: the evidence keys after activation.

### Safety

**Verdict:** CONDITIONAL APPROVE.

**S-01 [CRITICAL] — Event properties are an open dict.** `build_posthog_event` accepts any properties. Literal execution can place a secret, a cookie, or a raw buyer message in the queue. **Amendment:** The telemetry key, when earned, refuses those property names and does not send. **Deferral:** a live capture. Owner: an operator authority record.

**S-02 [HIGH] — Literal execution starts the worker or the scheduler.** **Amendment:** Do not edit `worker.py` or `scheduler.py`. Exit 78 stays HELD. Tests open no socket and read no provider credential.

**S-03 [HIGH] — Settings would change publication and purchase caps.** **Amendment:** The settings view reads. It does not write caps.

### Gameability

**Verdict:** CONDITIONAL APPROVE.

**G-01 [CRITICAL] — The exit string, or the commit subject `feat(console): add operator UI and PostHog telemetry`, as completion.** **Amendment:** Neither string is an evidence key. Completion is the six-key contract.

**G-02 [HIGH] — A function that returns the word "connected".** **Amendment:** `telemetry_redaction_implemented` is earned only when a secret, a cookie, or a raw buyer message is refused. A status word is not the proof.

**G-03 [HIGH] — An empty page component.** **Amendment:** `exception_views_implemented` is earned only when each named view is derived from the read model, including an empty state and an error state. A blank component fails.

**G-04 [HIGH] — Routine decisions become an approval queue.** **Amendment:** A routine automated decision is not an approval request. The decisions view shows hold, repair, cull, multiply, and successor created.

## 3. Corrective addendum

1. The prompt hash stays `c84a6c59948264f654efc1c11448e3a01bbc0c0f07960b1792d7681e96e48677`. The prompt file stays byte-identical.
2. This wave installs the Session 12 contract and does not activate the session. Do not edit `IMPLEMENTATION_STATE.json`. Do not write the exit string or the commit subject `feat(console): add operator UI and PostHog telemetry`.
3. The contract keys are `console_read_model_implemented`, `exception_views_implemented`, `telemetry_redaction_implemented`, `operator_actions_fail_closed`, `control_files_and_checkpoint_current`, and `evidence_closure_commit_recorded`. A later activation installs every key false.
4. Live PostHog capture, a deployed API, a Next.js app, browser E2E, live operator mutations, Exit 78, and `SESSION_12_OPERATOR_CONSOLE_COMPLETE` are not keys.
5. Do not edit `config/agents.yaml`, autonomy files, `worker.py`, or `scheduler.py`. Exit 78 stays HELD.
6. Do not publish, spend, message a buyer, or call live Etsy, Notion, or PostHog. Tests open no socket and read no provider credential.
7. Level 1 for this wave is the contract test, then `ruff check` and `pyright` on the touched control modules.

## 4. Deferrals

**D-01 — Session 12 activation.** Owner: the next transition. The contract is installed. The session stays inactive.

**D-02 — Live PostHog dispatch.** Owner: an operator authority record. A present key is not authority. The offline client queues and does not send.

**D-03 — Live operator mutations, cap writes, and lifting Exit 78.** Owner: the operator under D-0028.

**D-04 — The Next.js console, the deployed API, polling or server-sent events, and browser E2E.** Owner: the evidence keys after activation.

## 5. What already holds

`PostHogClient` already queues in memory and raises when telemetry is disabled. `build_posthog_event` already builds a capture payload without a network call. Etsy remains the commerce source. Exit 78 stays HELD.
