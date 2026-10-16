# Session 08 Prompt Integrity Review — draft job should-fix sweep 2

**Date:** 2026-10-16
**Prompt:** `prompts/implementation/11_SESSION_08_MERCHANDISING_AND_ASSET_FACTORY.md`
**Verified SHA-256:** `a7a406cecd9c93efdec1045f394b911e614cd79366840e33d5c53d9968f7cd33`
**Scope:** Fixture-only sweep of the parked #103 should-fixes around `create_ready_draft_listing_job`. The base is `cd300e7e`. No live HTTP, Notion, Etsy, or S3. Do not activate Session 08.

The prompt file is not amended. This record is the corrective addendum for this slice. The file is 5092 bytes and its SHA-256 equals the workbook appendix entry for `11_SESSION_08_MERCHANDISING_AND_ASSET_FACTORY.md`.

## 1. Prompt authenticity

**Status:** VERIFIED

The extracted file's SHA-256 equals `a7a406cecd9c93efdec1045f394b911e614cd79366840e33d5c53d9968f7cd33`. The prompt stays the unamended source of record.

## 2. Three-dimensional review

Sections 9 and 10 name the ready draft step. D-0034 already removed the copy and pricing edges. This slice does not reopen that graph. Open pulls #63 and #68 stay untouched. `IMPLEMENTATION_STATE.json` stays untouched.

### Fidelity

**Verdict:** CONDITIONAL APPROVE.

**F-01 [HIGH] — An existing PENDING job stays PENDING while the receipt says ready**

- **Prompt lines:** Sections 9 and 10, "Etsy draft job is automatically ready."
- **Authority:** CodeRabbit comment 4292269893. `EventDispatcher.dispatch` returns no ids when `ASSETS_COMPLETED` is already stored. The transition loop does not run. `prepare_etsy_draft` has already returned `ready=True`.
- **Consequence:** The product job remains `PENDING`. The worker claims `READY` jobs, so the listing sits with no claimable job.
- **Amendment:** Move that existing job to `READY` through `require_job_transition`. Do not return `ready=False`. `receipt.ready` is the draft `prepare_etsy_draft` already accepted, and the shop post already happened. Reporting it as not ready leaves the same stuck `PENDING` job. `RUNNING`, `SUCCEEDED`, and `CANCELLED` still raise and roll back. An existing event with no job still does not flush.

**F-02 [HIGH] — Cancellation skips the savepoint**

- **Prompt lines:** Sections 9 and 10.
- **Authority:** `except Exception` does not catch `BaseException`. `asyncio.CancelledError` is a `BaseException`. SQLAlchemy's `async with session.begin_nested()` commits when the block finishes and rolls back on any other exit, including cancellation (`TransactionalContext.__exit__`).
- **Consequence:** A cancelled call leaves its new event in the caller's session.
- **Amendment:** Use `async with uow.session.begin_nested()`. A `CancelledError` after dispatch rolls back to that savepoint and leaves the caller's earlier job, event, and sentinel row in place.

**F-03 [HIGH] — The savepoint commit does not commit**

- **Prompt lines:** Sections 9 and 10.
- **Authority:** The fixture boundary's `commit` returns without releasing the savepoint. Deleting `await boundary.commit()` still passes.
- **Consequence:** The success path is unpinned.
- **Amendment:** `commit` releases the savepoint. A later `rollback` on that boundary is a no-op and the ready job and event remain. Skipping the commit leaves the savepoint open, and that rollback removes them.

**F-04 [HIGH] — The READY continue is unreachable**

- **Prompt lines:** Sections 9 and 10.
- **Authority:** The function returns before dispatch when the product job is already `READY`. A new `DraftListingJob` is inserted as `PENDING`. The loop never observes `READY`.
- **Consequence:** Restoring `if status is JobStatus.READY: continue` changes nothing.
- **Amendment:** Remove the continue. Do not add a test that claims to kill it.

**F-05 [HIGH] — A worker event is stored once per workflow**

- **Prompt lines:** Sections 9 and 10.
- **Authority:** The worker dispatches `ASSETS_COMPLETED` with `aggregate_type="Job"`. #103 skips the draft job and still appends. The dedupe key includes `workflow_id`, so a second workflow appends a second event and still inserts no job.
- **Consequence:** One job completion leaves one event per workflow.
- **Amendment:** For that worker shape only, the dedupe key ignores `workflow_id` and keeps the job id. Two workflows and one job id leave one `ASSETS_COMPLETED`. A different job id still records its own event. Do not change `_dedupe_key` for every event. Do not edit `config/workflows.yaml`.

### Safety and executability

**Verdict:** CONDITIONAL APPROVE.

**S-01 [HIGH] — This slice stays off the held pulls and the state file**

- **Authority:** #63 and #68 are operator holds. Session 08 is not activated. Exit 78 stays HELD.
- **Amendment:** Edit the draft successor, the dispatcher dedupe for this one event shape, the successor test double, the shared-session tests, this addendum, and the implementation log. Do not edit `IMPLEMENTATION_STATE.json`, `src/money_machine/control/`, or `tests/bootstrap/`. Do not push `build/full-automation`. Do not force-push, rebase, or merge. One branch: `cursor/s08-draft-job-sf-sweep2`. If the base moves, merge it normally.

**S-02 [HIGH] — No live provider call**

- **Authority:** Fixture transport only.
- **Amendment:** Tests construct fixture rows. No HTTP, no production Notion, no production Etsy, no S3.

**S-03 [HIGH] — Pricing and copy stay out of the draft job**

- **Authority:** The operator has not ruled on a pricing or copy gate. D-0034 is the graph.
- **Amendment:** Do not add a pricing or copy gate or dependency. Do not change the D-0034 edges.

### Gameability

**Verdict:** CONDITIONAL APPROVE.

**G-01 [HIGH] — Each new pin fails on its own mutant**

- **Authority:** A survivor that another row already kills is not a pin.
- **Amendment:** The pending-job row is the only kill for skipping the existing-job transition. The cancellation row is the only kill for `except Exception`. The savepoint-commit row is the only kill for leaving the savepoint open. The second-workflow row is the only kill for keeping `workflow_id` in that dedupe key. The other-job row is the only kill for one key shared by every worker job. Restoring the dead continue fails nothing.

## 3. Corrective addendum

1. Prove the prompt hash. It stays `a7a406cecd9c93efdec1045f394b911e614cd79366840e33d5c53d9968f7cd33`.
2. Write the pending-job test first. An existing `PENDING` `DraftListingJob` plus an existing product `ASSETS_COMPLETED` ends `READY`, with `receipt.ready is True`, one event, and one job.
3. Hold the draft writes in `async with uow.session.begin_nested()`. Cancellation rolls back to that savepoint.
4. Releasing the savepoint is observable: rolling it back after success keeps the job and the event.
5. Remove the unreachable `READY` continue.
6. A worker-path `ASSETS_COMPLETED` for one job id records one event across two workflows. A different job id records its own event.
7. Session 08 stays inactive. `current_session` stays 7. `state_revision` stays 64. Exit 78 stays HELD. Do not start the close gate or A10/A11 commissioning.

## 4. Deferrals

**D-01 — #96 rulings and the `I . com` ruling.** The #103 verifier left them parked. This operator scope is the draft-job should-fixes. They stay parked. No owning session is opened here.

## 5. What already holds

One product already has one `DraftListingJob`. A second workflow already skips a new event when that job is `READY`. A refused asset chain already writes nothing. A later `RUNNING` or `SUCCEEDED` job already keeps the caller's session. A worker-shaped event already inserts no draft job. The idempotency key is already `DraftListingJob:{product_id}`. D-0034 stays the graph.
