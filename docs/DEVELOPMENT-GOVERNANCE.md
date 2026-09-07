# Money Machine — Development Governance

**Status:** mandatory repo-wide engineering cadence standard  
**Effective:** 14 August 2026  
**Scope:** all implementation sessions in this repository.

This document governs engineering cadence, verification sequencing, checkpoint size, and subagent topology. It does **not** weaken the playbook, simulation/draft/live boundaries, idempotency, reconciliation, commissioning, migration integrity, secrets/privacy rules, provider permissions, external-effect controls, or zero-spend defaults.

Where the Master Control Prompt or an older plan requires independent code review plus adversarial workflow review for every material slice, this document supersedes that per-slice cadence. Session-specific final exit criteria remain binding.

## 0. Prompt integrity precedes execution

Every session begins by proving its own prompt before obeying it. Run the adversarial review and corrective exercise defined in `docs/PROMPT_INTEGRITY_REVIEW.md`: verify the prompt's hash against the workbook, review it for fidelity, safety and executability, and gameability, then produce the corrective addendum that the session actually executes. Record it at `docs/control/reviews/<date>-session-<NN>-prompt-integrity.md` and reference it in the implementation log.

This gate is bounded and cheap relative to a session: three focused reviews of one document, then an addendum. It is not a planning phase and does not license scope change. No implementation action of the session may begin until every critical and high finding is resolved or explicitly deferred with a reason and an owning session.

## 1. Three governance levels

### Level 1 — bounded implementation slice

Use for a small, reversible change with clear ownership.

Required flow:

`RED -> smallest implementation -> focused GREEN -> small affected regression -> return to integrator`

Level 1 does **not** require independent review, adversarial review, full repository regression, frontend/Compose gates, five-control-file updates, or session closure evidence.
### Level 2 — integrated wave

Use after one or more Level 1 slices are ready. Default to one executor. Use parallel lanes only
when their files and dependencies are genuinely independent, and never exceed three active lanes.

Required flow:

`integrate -> cross-slice regression -> Ruff/Pyright once -> one relevant independent review -> bounded remediation -> integration checkpoint`

A second specialist review is required at Level 2 only when the wave crosses a distinct high-risk boundary such as migration integrity, external-effect handling, provider authorization, secrets/privacy, irreversible state, or commissioning.

Do not run the full repository suite merely because a Level 2 wave integrated successfully. Run the broad affected suite that actually binds the changed behavior.

### Level 3 — session exit

Reserve heavyweight governance for the real session boundary.

Required sequence:

`integrate all session work -> required session reviewers -> fix findings -> affected regression -> freeze bytes -> ONE final full regression/build/runtime gate -> five control files -> canonical session commit/closure`

The final full regression must come **after** required final review and remediation so reviewer fixes do not invalidate expensive evidence.
## 2. Default topology and routing

Default to one primary executor. Add bounded lanes only when parallel work shortens the critical path
without duplicated context or shared-file edits.

```text
PRIMARY INTEGRATOR
└─ Executor — bounded owned slice

OPTIONAL INDEPENDENT WAVE (maximum three lanes)
├─ Agent A — bounded owned slice
├─ Agent B — bounded owned slice
└─ Agent C — bounded owned slice
```

Rules:

- workers do not spawn workers, teams, or mandatory nested probes;
- assign explicit file/module ownership before edits;
- avoid concurrent edits to the same production file;
- the primary integrator owns shared files, integration, Git/control state, and session transitions;
- workers do not update `docs/control/` unless explicitly assigned a final integration task;
- a stalled worker does not block unrelated lanes; preserve its evidence and reassign only that slice;
- do not activate recursive/persistent orchestration merely because work is multi-step.

Route once per phase or integrated wave. Persist one routing receipt and pass its task-specific
subset to child lanes; do not invoke a router again inside each lane. If team launch fails, fall
back to one executor rather than a high-reasoning swarm.

Use the cheapest runtime-proven model/effort capable of the step: low-cost lookup/status for
targeted discovery, medium effort for bounded implementation, and high effort only for
cross-cutting architecture, security boundaries, or final review. When the runtime cannot prove
per-agent model routing, use the session's supported model at medium effort and reduce agent turns;
never claim an unsupported model selection.
## 3. Verification efficiency

Heavy verification is evidence, not ritual.

- Never run a duplicate full suite while an equivalent one is already running.
- Reuse green evidence while the relevant bytes remain unchanged.
- After a narrow repair, rerun the failing subset first, then the affected regression.
- Rerun the full repository suite only when changed bytes materially invalidate the prior full-suite evidence or at the Level 3 session exit.
- Serialize heavyweight pytest/database/frontend/Compose jobs that contend for the same PostgreSQL instance, browser, or `/mnt/d` I/O.
- Parallelize development and lightweight isolated checks instead of heavy contention.
- Do not launch the final full regression until final session reviewers have returned and critical/high findings are repaired.
- On an implementation branch that provides `scripts/run_affected_tests.sh`, use it with a reviewed newline-delimited test manifest for database-backed affected suites. The runner rejects empty or literal shell entries, creates one unique database, and always attempts cleanup while preserving the test exit status.
- Retry a failed command only after a concrete diagnosis or code/config change. The same command gets one retry; a second unchanged failure is a blocker or requires a different approach.

## 4. Integrator utilization

The primary integrator must not spend long periods repeatedly polling `Waiting for agents`.

While workers are active, the integrator should consume completed results, inspect integration boundaries, prepare cross-slice tests, classify remaining work, prepare closure evidence, or work on a non-conflicting integrator-owned task. Poll workers only at meaningful boundaries.
## 5. Session sizing and checkpoints

A session prompt may define a broad deliverable, but implementation must be decomposed into bounded Level 1 slices and Level 2 integration waves. Do not let one agent own the entire session as a single dirty mega-task.

For large sessions, create recoverable intermediate checkpoints when doing so does not violate the session transition contract. Intermediate commits must not claim session completion and must not replace the exact canonical session implementation subject required at Level 3.

If the controller requires one exact implementation commit for the session, the integrator may keep Level 1/2 checkpoints as local evidence or squash/fold only when the existing transition contract explicitly permits it. Never rewrite already-accepted historical session commits.

Before replanning or rescanning after interruption, run the active implementation branch's
`scripts/write_resume_checkpoint.py` and
reconcile its branch, HEAD, dirty-set hash/count, active gate, candidate hash, and command hashes.
The checkpoint is metadata-only and must remain at or below 8 KiB. Never copy prompts, source,
provider/customer payloads, secrets, or command text into it.

Read targeted graph/search results first. Start with no more than eight relevant files; expand only
when a concrete dependency requires it. Do not reread an unchanged file in the same task.

## 6. Review cadence

- Level 1: tests and integrator self-check are sufficient unless the slice itself crosses a high-risk boundary.
- Level 2: one relevant independent review is the default; add a second only for a genuinely distinct risk domain.
- Level 3: run every reviewer explicitly required by the active session prompt or final programme contract.
- Do not re-review unchanged bytes.
- After review remediation, re-review only the invalidated scope.
- One integration review plus one changed-diff re-review is the normal maximum. A second failed
  re-review stops the loop for integrator diagnosis instead of spawning another reviewer handoff.

The Master Control Prompt's former `INDEPENDENT CODE REVIEW -> ADVERSARIAL WORKFLOW REVIEW` loop for every material slice is replaced by this cadence.
## 7. Session exit controls remain mandatory

At Level 3, preserve the existing Money Machine session contract:

- formatting, linting, typing, required tests, relevant frontend/runtime/Compose gates;
- required session reviewers;
- immutable-source and secret/private-artifact checks;
- truthful commissioning state;
- zero unauthorized external effects and spend;
- updates to the five files in `docs/control/`;
- exact canonical session commit subject and required exit code;
- push only when authenticated, safe, and already authorized by repo policy.

## 8. Safety and product truth are unchanged

This optimization never relaxes simulation/draft/live modes, idempotency, reconciliation-before-retry, provider authorization, secrets/privacy, migration integrity, commissioning, playbook business rules, external-effect controls, or the prohibition on unapproved publication, purchases, messages, live provider mutation, or spend.

## 9. Precedence

For engineering cadence, review frequency, test sequencing, session decomposition, and subagent topology, this file supersedes older Money Machine text that applies full review or heavyweight verification to every material internal slice. Session-specific scope and final exit criteria still govern Level 3.

**Govern risk boundaries heavily; develop ordinary internal slices lightly, in parallel, and with evidence proportional to the change.**

## 10. Reporting, measurement, and stopping

- Report only on state change, blocker, checkpoint, or completion; maximum five bullets.
- Append one metadata-only record with the active implementation branch's
  `scripts/omx_task_metrics.py` at completion or terminal
  blockage. Record token counts only when the host exposes exact values; otherwise store `null`.
- A task stops when requested behavior, focused/affected checks, required static gates, integration
  review, and a recoverable checkpoint are complete. Do not add summaries, reviews, full suites,
  or new agents after that stop condition.
- Mark old worktrees inactive in the task checkpoint/ledger and exclude them from discovery. Never
  delete, clean, or rewrite them merely to reduce context.
