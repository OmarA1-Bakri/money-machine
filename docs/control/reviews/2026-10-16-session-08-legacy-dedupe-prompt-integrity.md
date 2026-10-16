# Session 08 Prompt Integrity Review — legacy product dedupe key

**Date:** 2026-10-16
**Prompt:** `prompts/implementation/11_SESSION_08_MERCHANDISING_AND_ASSET_FACTORY.md`
**Verified SHA-256:** `a7a406cecd9c93efdec1045f394b911e614cd79366840e33d5c53d9968f7cd33`
**Scope:** Fixture-only lookup for the product `ASSETS_COMPLETED` key written by `create_ready_draft_listing_job` in #101–#104. The base is `edc0632fb43777d834053d5dbfe42f31f3478ab7` (#105). No live HTTP, Notion, Etsy, or S3. Do not activate Session 08.

The prompt file is not amended. This record is the corrective addendum for this slice. The file is 5092 bytes and its SHA-256 equals the workbook appendix entry for `11_SESSION_08_MERCHANDISING_AND_ASSET_FACTORY.md`.

## 1. Prompt authenticity

**Status:** VERIFIED

The extracted file's SHA-256 equals `a7a406cecd9c93efdec1045f394b911e614cd79366840e33d5c53d9968f7cd33`. The prompt stays the unamended source of record.

## 2. Three-dimensional review

Sections 9 and 10 name the ready draft step. D-0034 already removed the copy and pricing edges. This slice does not reopen that graph. Open pulls #63 and #68 stay untouched. `IMPLEMENTATION_STATE.json` stays untouched. Defang rules stay untouched.

### Fidelity

**Verdict:** CONDITIONAL APPROVE.

**F-01 [HIGH] — The product key does not see the #101–#104 key**

- **Prompt lines:** Sections 9 and 10.
- **Authority:** CodeRabbit on #105 at `event_dispatcher.py` line 62. #105 stores a product `ASSETS_COMPLETED` as `ASSETS_COMPLETED:{product}:product`. `create_ready_draft_listing_job` in #101–#104 stored `ASSETS_COMPLETED:{product}:{workflow}:null` (`job_id` was null). A seeded legacy row beside a `PENDING` job is not that key, so dispatch appends a second event.
- **Consequence:** One product holds two `ASSETS_COMPLETED` rows.
- **Amendment:** Write the failing test first. Dedupe also matches the legacy key. Do not migrate the row. D-0035 records why a lookup was chosen over a rewrite. Do not change `_dedupe_key` for every event.

**F-02 [MEDIUM] — The worker key's `aggregate_id` repeats `job_id`**

- **Prompt lines:** Sections 9 and 10.
- **Authority:** `worker.py` passes `job.id` for both ids. Replacing `aggregate_id` with `job_id` in the worker key still yields two events in `test_two_job_ids_on_one_worker_aggregate_record_two_events`.
- **Consequence:** That substitution has no red test.
- **Amendment:** Document the survivor. Do not invent a dispatch the worker never makes. The production caller keeps both ids equal to `job.id`.

### Safety and executability

**Verdict:** CONDITIONAL APPROVE.

**S-01 [HIGH] — This slice stays off the held pulls and the state file**

- **Authority:** #63 and #68 are operator holds. Session 08 is not activated. Exit 78 stays HELD.
- **Amendment:** Edit the dispatcher product branch, the shared-session test, this addendum, `DECISIONS.md`, and the implementation log. Do not edit `IMPLEMENTATION_STATE.json`, `src/money_machine/control/`, `tests/bootstrap/`, or the defang rules. Do not change the D-0034 graph. Do not push `build/full-automation`. Do not force-push, rebase, or merge. One branch: `cursor/s08-legacy-dedupe-key`. If the base moves, merge it normally.

**S-02 [HIGH] — No live provider call**

- **Authority:** Fixture transport only.
- **Amendment:** Tests construct fixture rows. No HTTP, no production Notion, no production Etsy, no S3.

**S-03 [HIGH] — The event log stays append-only**

- **Authority:** `EventRepository` appends and does not update a row. A migration that rewrites `dedupe_key` would mutate history.
- **Amendment:** Look the legacy key up. Leave the stored key in place. New writes still use the product key. No migration file.

### Gameability

**Verdict:** CONDITIONAL APPROVE.

**G-01 [HIGH] — The legacy row is the only kill for skipping the lookup**

- **Authority:** A count of names can be satisfied by rewriting the row onto the new key.
- **Amendment:** The new test seeds `ASSETS_COMPLETED:{product}:{workflow}:null` beside a `PENDING` job. After the call there is one `ASSETS_COMPLETED`, that legacy key is still present, the product key is absent, and the job is `READY`. Skipping the lookup is that test's unique kill.

**G-02 [MEDIUM] — The body must name the existing `RUNNING` → `READY` kill**

- **Authority:** #105 verifier SF2. Allowing `READY` from `RUNNING` in `JOB_TRANSITIONS` is killed by `test_a_later_running_job_keeps_the_callers_session`.
- **Amendment:** Name that test in the pull request body. Do not edit the transition table.

**G-03 [MEDIUM] — PostgreSQL remains untested**

- **Authority:** #105 Limits. The fixture models the savepoint.
- **Amendment:** Keep the PostgreSQL limits note. Do not add a PostgreSQL test.

## 3. Corrective addendum

1. Prove the prompt hash. It stays `a7a406cecd9c93efdec1045f394b911e614cd79366840e33d5c53d9968f7cd33`.
2. Write the legacy-key test first. One event remains, the legacy key stays, the product key is not written, and the pending job becomes `READY`.
3. Look up `ASSETS_COMPLETED:{product}:{workflow}:null` before appending a product event. Do not migrate.
4. Record the lookup-over-migration choice in D-0035.
5. Document the `aggregate_id` survivor. The worker sets it equal to `job.id`.
6. Name `test_a_later_running_job_keeps_the_callers_session` as the kill for `RUNNING` → `READY` in the body.
7. Keep the PostgreSQL limits note. Fixture-only.
8. Session 08 stays inactive. `current_session` stays 7. `state_revision` stays 64. Exit 78 stays HELD. Do not start the close gate or A10/A11 commissioning.

## 4. Deferrals

**D-01 — D-0034 ordering.** Copy and pricing still do not gate the draft. The operator has not ruled. This slice does not open that question.

**D-02 — PostgreSQL savepoint, cancellation, and concurrency.** Still untested. The limits note stays. No PostgreSQL session is opened.

**D-03 — The `aggregate_id` substitution.** Documented, not pinned. Every production worker call sets `aggregate_id` and `job_id` to `job.id`.

## 5. What already holds

One product already has one `DraftListingJob`. A second workflow already skips a new event when the product key matches. A refused asset chain already writes nothing. A worker event for one job id is already one row across two workflows. `RUNNING` and `SUCCEEDED` already have separate tests. D-0034 stays the graph. Defang rules stay as they are.
