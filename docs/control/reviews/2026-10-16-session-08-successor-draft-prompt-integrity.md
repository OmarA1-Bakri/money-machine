# Session 08 Prompt Integrity Review — successor draft job

**Date:** 2026-10-16
**Prompt:** `prompts/implementation/11_SESSION_08_MERCHANDISING_AND_ASSET_FACTORY.md`
**Verified SHA-256:** `a7a406cecd9c93efdec1045f394b911e614cd79366840e33d5c53d9968f7cd33`
**Workbook authority:** appendix row for this prompt (5,092 bytes, 236 lines)
**Scope:** Sections 9 and 10, successor draft job creation only. Do not activate Session 08. Do not commission A10, A11, or A13. Do not run the draft job.

The prompt file is not amended. This record is the corrective addendum. It does not overwrite earlier Session 08 reviews.

## 1. Prompt authenticity

**Status:** VERIFIED

The extracted file's SHA-256 equals `a7a406cecd9c93efdec1045f394b911e614cd79366840e33d5c53d9968f7cd33`. The prompt stays the unamended source of record.

## 2. Three-dimensional review

The operator instruction is fixture-only successor creation after `prepare_etsy_draft` passes. No live HTTP, Notion, Etsy, or S3. No worker or scheduler change. Open pulls #63 and #68 stay untouched. `IMPLEMENTATION_STATE.json`, `src/money_machine/control/`, and `tests/bootstrap/` stay untouched.

### Fidelity

**Verdict:** CONDITIONAL APPROVE.

**F-01 [HIGH] — Sections 9 and 10 are not a licence to finish the session**

- **Prompt lines:** 167–181, 199, and 215–229.
- **Authority:** D-0032 keeps Session 08 inactive. Exit 78 stays HELD. A10, A11, and A13 stay `DESIGNED`.
- **Consequence of literal execution:** Commissioning the agents and printing `SESSION_08_MERCHANDISING_AND_ASSETS_COMPLETE` would claim the session is finished.
- **Amendment:** Create the ready successor job and stop. Do not edit `IMPLEMENTATION_STATE.json`. Do not print the session exit code. Do not commission an agent.

**F-02 [HIGH] — `ASSET_QA_PASSED` and `CREATE_ETSY_DRAFT` are prompt labels**

- **Prompt lines:** 180–181 and 199.
- **Authority:** `config/workflows.yaml` maps `ASSETS_COMPLETED` to `[DraftListingJob]`. `EventName` has `ASSETS_COMPLETED` and has no `ASSET_QA_PASSED`. Session 03 finding M11 and D-0029 already voided the prompt's example job names as a second vocabulary. D-0029 recorded the graph and did not create the job. This slice creates the job.
- **Consequence:** Adding the prompt names to the enum or the YAML map would fork the orchestrator and break the event catalogue and roster-adjacent workflow contracts.
- **Amendment:** Reuse `ASSETS_COMPLETED` and `DraftListingJob`. Do not edit `config/workflows.yaml`. Record the naming choice in D-0033.

### Safety and executability

**Verdict:** CONDITIONAL APPROVE.

**S-01 [HIGH] — Creating the job must not run an external write**

- **Prompt lines:** 181 and 222. `DraftListingJob` is `EXTERNAL_WRITE` owned by A13.
- **Authority:** A13 stays `DESIGNED`, the same hold D-0029 used when it refused to run a recorded successor. The operator forbids worker and scheduler edits and forbids live Etsy.
- **Consequence:** Claiming the new job would call the Etsy draft writer.
- **Amendment:** `EventDispatcher.dispatch` and `SuccessorFactory.create_successors` insert the job. The new row moves `PENDING` to `READY` and stops. `claim_ready_job` and the worker are not called.

**S-02 [HIGH] — A refused chain must not leave a successor**

- **Prompt lines:** 169–181. The chain is one sequence. A failed gate is not `CREATE_ETSY_DRAFT ready`.
- **Authority:** `prepare_etsy_draft` already raises `DraftGateError` before the fixture client. The successor has to sit after that return.
- **Amendment:** Dispatch only after `prepare_etsy_draft` returns a receipt. A gate error propagates and writes no event and no job.

### Gameability

**Verdict:** CONDITIONAL APPROVE.

**G-01 [HIGH] — A boolean flag can pretend the job exists**

- **Cheap fake:** Return the draft receipt and set `created = True` without inserting a `DraftListingJob`.
- **Amendment:** The pass test counts factory inserts. There is one job, its type is `DraftListingJob`, and the recorded event is `ASSETS_COMPLETED`.

**G-02 [HIGH] — A second call can hide behind the first return value**

- **Cheap fake:** Return the first job id on the second call while inserting another row.
- **Amendment:** The re-dispatch test counts `Job` inserts. The second call adds none. The fixture client does not post again.

**G-03 [HIGH] — `READY` can be swapped for a run**

- **Cheap fake:** Set the job to `RUNNING` or `SUCCEEDED`, or call `claim_ready_job`.
- **Amendment:** The not-executed test requires status `READY`, attempt 0, an empty lease, and zero calls to `claim_ready_job` and `_execute_job_with_runner`.

**What the prompt already gets right**

- The chain stops when the draft job is ready. It does not publish (line 181).
- Asset QA stays in front of that job (line 180).
- Section 10 names successor draft job creation as its own proof (line 199).

## 3. Corrective addendum

This addendum governs this slice. The prompt remains the unamended source of record.

1. Prove the prompt hash, then create the successor only after `prepare_etsy_draft` returns.
2. The event is `ASSETS_COMPLETED`. The job type is `DraftListingJob`. Do not add `ASSET_QA_PASSED` or `CREATE_ETSY_DRAFT` to code or to `config/workflows.yaml`. D-0033 records that choice.
3. Call the existing `EventDispatcher` and `SuccessorFactory`. Do not add a second successor map. Do not edit the worker or the scheduler.
4. Transition the new job from `PENDING` to `READY`. Do not claim it and do not run it.
5. A `DraftGateError` creates no event and no job. Each existing gate has that proof.
6. A second dispatch with the same product and workflow inserts no second job.
7. Do not edit open pulls #63 and #68, `IMPLEMENTATION_STATE.json`, `src/money_machine/control/`, or `tests/bootstrap/`. Exit 78 stays HELD. Session 08 stays inactive. A10, A11, and A13 stay `DESIGNED`.

## 4. Deferrals

| Finding | Owner | Reason |
|---|---|---|
| Running `DraftListingJob` | A13 commissioning, Session 09 | A13 is `DESIGNED`. The job stops at `READY` |
| `ASSET_QA_PASSED` as a new event name | Not this slice | The durable name is already `ASSETS_COMPLETED` |
| Session exit code and Exit 78 | Session exit | Operator hold |
| Live Etsy, Notion, and S3 | Later waves | Operator park |

## 5. Final verdict

**CONDITIONAL APPROVE.** Critical and high findings are resolved by the numbered addendum above. Implementation of successor draft job creation may start. The prompt file stays unamended.
