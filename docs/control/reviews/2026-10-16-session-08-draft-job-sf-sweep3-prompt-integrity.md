# Session 08 Prompt Integrity Review — draft job should-fix sweep 3

**Date:** 2026-10-16
**Prompt:** `prompts/implementation/11_SESSION_08_MERCHANDISING_AND_ASSET_FACTORY.md`
**Verified SHA-256:** `a7a406cecd9c93efdec1045f394b911e614cd79366840e33d5c53d9968f7cd33`
**Scope:** Fixture-only sweep of the should-fixes parked on #104, around `create_ready_draft_listing_job` and the worker `ASSETS_COMPLETED` path. The base is `3385ad299f6b28ebea60fc2025f2bee42a0f5611`. No live HTTP, Notion, Etsy, or S3. Do not activate Session 08.

The prompt file is not amended. This record is the corrective addendum for this slice. The file is 5092 bytes and its SHA-256 equals the workbook appendix entry for `11_SESSION_08_MERCHANDISING_AND_ASSET_FACTORY.md`.

## 1. Prompt authenticity

**Status:** VERIFIED

The extracted file's SHA-256 equals `a7a406cecd9c93efdec1045f394b911e614cd79366840e33d5c53d9968f7cd33`. The prompt stays the unamended source of record.

## 2. Three-dimensional review

Sections 9 and 10 name the ready draft step. D-0034 already removed the copy and pricing edges. This slice does not reopen that graph. Open pulls #63 and #68 stay untouched. `IMPLEMENTATION_STATE.json` stays untouched. Defang rules stay untouched.

### Fidelity

**Verdict:** CONDITIONAL APPROVE.

**F-01 [HIGH] — A pending job beside another workflow's event appends a second product event**

- **Prompt lines:** Sections 9 and 10.
- **Authority:** #104 verifier P1. The product dedupe key still includes `workflow_id`. The early return covers a job that is already `READY`. A `PENDING` `DraftListingJob` beside an `ASSETS_COMPLETED` from another workflow still takes the dispatch path and appends again. The same pair appends on `3385ad29`.
- **Consequence:** One product holds two `ASSETS_COMPLETED` rows.
- **Amendment:** Write the failing test first. A `PENDING` product job and another workflow's product `ASSETS_COMPLETED` end as one event and a `READY` job. The product key for `ASSETS_COMPLETED` omits `workflow_id`. Do not change `_dedupe_key` for every event.

**F-02 [HIGH] — A worker completion with no job is stored**

- **Prompt lines:** Sections 9 and 10.
- **Authority:** #104 verifier P3. `aggregate_type="Job"` still appends when `job_id` is missing and when no `Job` row exists. The null branch of the worker key is untested. The idempotent success path also returns an empty tuple, so a silent skip is indistinguishable from a duplicate.
- **Consequence:** The log says a job completed when no job was named or loaded.
- **Amendment:** Fail closed. Raise `ValueError` and append nothing when `job_id` is missing or the `Job` row is absent. Do not ignore the call. The worker in `worker.py` passes `job.id` for both ids after that row was loaded, so this refusal does not change a real completion.

**F-03 [HIGH] — Two harmless mutants have no test, and one test covers two statuses**

- **Prompt lines:** Sections 9 and 10.
- **Authority:** #104 review nits. `test_a_later_workflow_keeps_the_callers_session` loops `RUNNING` and `SUCCEEDED`, so both kills share one test id. The worker suffix `:job:{job_id}` repeats `aggregate_id` on every caller that sets them equal, so deleting it survives. The `else "null"` branch survives for the same reason.
- **Consequence:** A redundant key fragment and an untested null branch can change without a red test.
- **Amendment:** Split that loop into two tests. Refuse a missing job id before the key is built, which removes the null branch. Drop `:job:{job_id}` only after checking the sole production caller and the dedupe tests: `worker.py` sets `aggregate_id` and `job_id` to `job.id`, and one event per job across workflows must still hold. If a call can store two job ids on one aggregate, keep the suffix.

**F-04 [MEDIUM] — PostgreSQL savepoint behaviour is untested**

- **Prompt lines:** Sections 9 and 10.
- **Authority:** #104 parked should-fix. The fixture models `begin_nested`. Savepoint release, cancellation, and concurrent primary-key or dedupe collisions are not run on PostgreSQL.
- **Consequence:** A green fixture suite can be read as dialect proof.
- **Amendment:** State that limit under Limits in the pull request body. Do not add a PostgreSQL test. Fixture-only.

### Safety and executability

**Verdict:** CONDITIONAL APPROVE.

**S-01 [HIGH] — This slice stays off the held pulls and the state file**

- **Authority:** #63 and #68 are operator holds. Session 08 is not activated. Exit 78 stays HELD.
- **Amendment:** Edit the draft successor, the dispatcher branches for this event, the shared-session tests, the successor test seeds that must match the product key, this addendum, and the implementation log. Do not edit `IMPLEMENTATION_STATE.json`, `src/money_machine/control/`, or `tests/bootstrap/`. Do not push `build/full-automation`. Do not force-push, rebase, or merge. One branch: `cursor/s08-draft-job-sf-sweep3`. If the base moves, merge it normally.

**S-02 [HIGH] — No live provider call**

- **Authority:** Fixture transport only.
- **Amendment:** Tests construct fixture rows. No HTTP, no production Notion, no production Etsy, no S3.

**S-03 [HIGH] — Pricing and copy stay out of the draft job**

- **Authority:** The operator has not ruled on a pricing or copy gate. D-0034 is the graph.
- **Amendment:** Do not add a pricing or copy gate or dependency. Do not change the D-0034 edges. Do not edit defang rules.

### Gameability

**Verdict:** CONDITIONAL APPROVE.

**G-01 [HIGH] — Each new pin fails on its own mutant**

- **Authority:** A survivor that another row already kills is not a pin.
- **Amendment:** The cross-workflow pending row is the only kill for putting `workflow_id` back into the product key. The missing-row row is the only kill for appending a worker event when the `Job` row is absent. The missing-job-id row is the only kill for appending when `job_id` is none. The `SUCCEEDED` row is the only kill for allowing `SUCCEEDED -> READY`. Restoring the deleted `READY` continue still fails nothing, because the loop never sees `READY`; it stays deleted and is not given a fake pin.

## 3. Corrective addendum

1. Prove the prompt hash. It stays `a7a406cecd9c93efdec1045f394b911e614cd79366840e33d5c53d9968f7cd33`.
2. Write the cross-workflow pending test first. One product event remains, and the job becomes `READY`.
3. Write the worker tests first. No job id, and a job id with no row, each raise `ValueError` and leave the log empty.
4. Split the `RUNNING` / `SUCCEEDED` loop into two tests.
5. Keep the worker key's `:job:{job_id}` fragment. Two job ids on one aggregate are two events, so the fragment is not equivalent to `aggregate_id` alone. One job id across two workflows is still one event. The missing-job-id check runs before the key is built, so the `null` branch is gone.
6. Document the untested PostgreSQL savepoint, cancellation, and concurrency behaviour under Limits. Fixture-only.
7. Session 08 stays inactive. `current_session` stays 7. `state_revision` stays 64. Exit 78 stays HELD. Do not start the close gate or A10/A11 commissioning.

## 4. Deferrals

**D-01 — D-0034 ordering.** Copy and pricing still do not gate the draft. The operator has not ruled. This slice does not open that question.

**D-02 — The deleted `READY` continue.** Restoring it remains equivalent. No test can kill it. It stays deleted.

## 5. What already holds

One product already has one `DraftListingJob`. A second workflow already skips a new event when that job is `READY`. A refused asset chain already writes nothing. Cancellation already rolls the savepoint back in the fixture. A worker event for one job id is already one row across two workflows. D-0034 stays the graph. Defang rules stay as they are.
