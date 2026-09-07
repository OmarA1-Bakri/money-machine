# Prompt Integrity Review

**Status:** mandatory standing instruction, executed at the start of every session prompt.
**Effective:** 7 September 2026, from Session 02 onward.
**Scope:** every `prompts/implementation/NN_SESSION_*.md` prompt, before any implementation work in that session.

## Why this lives here and not in the prompt

The session prompts are deterministically extracted from the implementation workbook between `COPY START` and `COPY END` markers, and each file's SHA-256 is asserted against the workbook's own appendix. The workbook and the playbook PDF are immutable root sources that must be preserved byte-for-byte. A standing instruction therefore cannot be typed into the prompt files: doing so would break extraction, fail the prompt-pack test, and corrupt the source register. This document is that instruction, and it binds every prompt as if it were printed at the top of each one.

A session prompt is authority for **what to build**. It is not evidence that its own instructions are correct, current, safe, or achievable in this repository. Session 01 shipped a prompt whose literal execution would have dropped the entire artifact-lineage design and removed a fail-closed boundary. The prompt was faithfully extracted and still wrong. Treat every prompt as a hypothesis about the work, and test it before executing it.

## The standing instruction

> **Before executing any action in a session prompt, run an adversarial review of the prompt itself and complete the corrective exercise. Record the result. Do not begin implementation until the corrective addendum exists and every critical and high finding is resolved or explicitly deferred with a reason.**

This runs after restoring control state and before the prompt's own first action.

## Procedure

### 1. Prove the prompt is authentic

Confirm the extracted file's SHA-256 equals the value the workbook declares for it, and that the content matches the workbook's embedded copy. A mismatch is a stop: the prompt pack has drifted and must be re-extracted before anything else.

### 2. Review the prompt across three dimensions

Use independent reviewers, one per dimension. They review the **prompt**, not the codebase.

- **Fidelity.** Does the prompt agree with the workbook sections it implements, the Master Control Prompt, the canonical repository structure, and every accepted decision in `docs/control/DECISIONS.md`? Does it require the outputs of earlier sessions to be carried forward, or does it silently drop them? Name every contract, field, table, or invariant an earlier session produced that this prompt never mentions.
- **Safety and executability.** What breaks if a competent agent executes each instruction literally against this repository as it stands today? Check fail-closed boundaries, credential and provider exposure, sources of truth, ordering traps, and every named tool or dependency as supported, absent, or unknown. Check that the work decomposes into bounded slices rather than one mega-task.
- **Gameability.** For each exit criterion and required test, write the cheapest change that satisfies the wording without the system working, then write the wording that makes that fake impossible. Identify which completion-evidence keys are self-reported rather than machine-earned.

### 3. Complete the corrective exercise

Produce a **corrective addendum** for the session: the amended instruction set the session will actually execute. For each finding, either a concrete amendment or an explicit deferral with a reason. The addendum is what governs execution; the prompt remains the unamended source of record. Where an amendment contradicts the workbook rather than merely sharpening it, record a decision in `docs/control/DECISIONS.md`, because the workbook is the engineering authority and a contradiction must be visible rather than absorbed.

Amendments may only make a prompt more exact, more safe, or more verifiable. They may not reduce scope, weaken the playbook's business rules, or relax a safety boundary. Cutting scope is the operator's call, not the executor's.

### 4. Record it

Write `docs/control/reviews/<YYYY-MM-DD>-session-<NN>-prompt-integrity.md` containing:

- the prompt path and its verified SHA-256;
- the three review verdicts;
- every finding with severity, the prompt line at fault, the authority it contradicts or omits, and the consequence of literal execution;
- the corrective addendum, as the numbered instruction set the session will execute;
- deferrals with reasons and their owning session;
- what the prompt already gets right, so later sessions do not re-litigate it.

Reference the record in `docs/control/IMPLEMENTATION_LOG.md` for that session. `tests/bootstrap/test_prompt_integrity.py` asserts the record exists for the active session and for every session completed under this rule.

## Failure modes this prevents

An instruction that no longer matches the code it was written against. A stale enum, path, or tool name that silently fails validation. A boundary the prompt permits removing because it predates the boundary. Two sources of truth created by a seeding instruction. An exit criterion satisfied by a stub. Work that cannot be executed within the governance cadence. Earlier sessions' designs quietly dropped at a boundary the prompt never mentions.

## What this instruction is not

It is not licence to rewrite the programme. It is not a planning phase: it is bounded by the three dimensions above and ends with an executable addendum. It does not replace the session's own required reviews at its exit, which review the work rather than the instructions.
