# Session 08 Prompt Integrity Review — draft job should-fix sweep

**Date:** 2026-10-16
**Prompt:** `prompts/implementation/11_SESSION_08_MERCHANDISING_AND_ASSET_FACTORY.md`
**Verified SHA-256:** `a7a406cecd9c93efdec1045f394b911e614cd79366840e33d5c53d9968f7cd33`
**Scope:** Fixture-only sweep of the parked #102 should-fixes around `create_ready_draft_listing_job`. The base is `35aefac0`. No live HTTP, Notion, Etsy, or S3. Do not activate Session 08.

The prompt file is not amended. This record is the corrective addendum for this slice.

## 1. Prompt authenticity

**Status:** VERIFIED

The extracted file's SHA-256 equals `a7a406cecd9c93efdec1045f394b911e614cd79366840e33d5c53d9968f7cd33`. The prompt stays the unamended source of record.

## 2. Three-dimensional review

Sections 9 and 10 name the ready draft step. D-0034 already removed the copy and pricing edges. This slice does not reopen that graph. Open pulls #63 and #68 stay untouched. `IMPLEMENTATION_STATE.json` stays untouched.

### Fidelity

**Verdict:** CONDITIONAL APPROVE.

**F-01 [HIGH] — A full rollback discards the caller's session**

- **Prompt lines:** Sections 9 and 10, the ready draft step.
- **Authority:** `create_ready_draft_listing_job` calls `uow.rollback()` on any exception after dispatch. The unit of work rolls back the whole transaction. A later workflow that finds the product job `RUNNING` or `SUCCEEDED` raises `InvalidTransitionError` and erases the first job and the first event.
- **Consequence:** A shared session loses work that this call did not own.
- **Amendment:** Roll back only this call's writes, with a savepoint or nested transaction. Write the failing test first. After the exception, the first job, the first `ASSETS_COMPLETED` event, and any other row the caller had already placed in the session are still there. Cover both `RUNNING` and `SUCCEEDED`.

**F-02 [HIGH] — A second workflow records a second event**

- **Prompt lines:** Sections 9 and 10.
- **Authority:** The dispatcher dedupe key includes `workflow_id`. D-0034 keys the job on the product and does not ask for a second `ASSETS_COMPLETED` row. The parked note left the second event unconfirmed.
- **Consequence:** Two successful workflows for one product leave two events and one job. A test that only counts jobs stays green.
- **Amendment:** A second workflow for the same product does not leave a second `ASSETS_COMPLETED` event. When the product job is already `READY`, do not append one. Do not change the global dedupe key.

**F-03 [HIGH] — A worker-shaped assets event inserts a pending draft**

- **Prompt lines:** Sections 9 and 10.
- **Authority:** The worker dispatches completion with `aggregate_type="Job"` and `aggregate_id` equal to the job id. D-0034 keys `DraftListingJob` on the product aggregate. That job id is a different aggregate, so the factory inserts another `DraftListingJob` and leaves it `PENDING`.
- **Consequence:** One product can hold two draft jobs. The YAML map still has to name `DraftListingJob` for `ASSETS_COMPLETED`.
- **Amendment:** An `ASSETS_COMPLETED` event whose aggregate type is `Job` does not insert a draft job. The product path still does. Do not edit `config/workflows.yaml`.

**F-04 [HIGH] — Three mutants still pass**

- **Prompt lines:** Sections 9 and 10.
- **Authority:** The product-id guard, the key `DraftListingJob:{aggregate_id}` from D-0034, and `except Exception` are unpinned. `InvalidTransitionError` is a `ValueError`, so `except RuntimeError` skips the rollback.
- **Consequence:** Deleting the guard, restoring a per-workflow idempotency key, or narrowing the handler leaves the suite green.
- **Amendment:** A missing product id raises `ValueError` and inserts nothing. The created job's `idempotency_key` is `DraftListingJob:{product_id}`. An `InvalidTransitionError` after the inner write still undoes that write.

### Safety and executability

**Verdict:** CONDITIONAL APPROVE.

**S-01 [HIGH] — This slice stays off the held pulls and the state file**

- **Authority:** #63 and #68 are operator holds. Session 08 is not activated. Exit 78 stays HELD.
- **Amendment:** Edit the draft successor, the factory pass-through, the successor tests, this addendum, the job/event contract lines named below, and the implementation log. Do not edit `IMPLEMENTATION_STATE.json`, `src/money_machine/control/`, or `tests/bootstrap/`. Do not push `build/full-automation`. Do not force-push, rebase, or merge. One branch: `cursor/s08-draft-job-sf-sweep`.

**S-02 [HIGH] — No live provider call**

- **Authority:** Fixture transport only.
- **Amendment:** Tests construct fixture rows. No HTTP, no production Notion, no production Etsy, no S3.

**S-03 [HIGH] — Pricing and copy stay out of the draft job**

- **Authority:** The operator has not ruled on a pricing or copy gate. D-0034 is the graph.
- **Amendment:** Do not add a pricing or copy gate or dependency. Do not change the D-0034 edges in `config/workflows.yaml`.

### Gameability

**Verdict:** CONDITIONAL APPROVE.

**G-01 [HIGH] — A pin has to fail when that one behavior is removed**

- **Authority:** A survivor that another row already kills is not a pin.
- **Amendment:** Each mutant below fails its own row. The shared-session row is the only kill for a whole-session rollback and for `except RuntimeError`. The second-event row is the only kill for appending on an already-`READY` job. The worker row is the only kill for inserting a draft from a `Job` aggregate. The product-id row is the only kill for deleting the guard. The key row is the only kill for a per-workflow idempotency key.

## 3. Corrective addendum

1. Prove the prompt hash. It stays `a7a406cecd9c93efdec1045f394b911e614cd79366840e33d5c53d9968f7cd33`.
2. Write the shared-session test first. A later workflow that finds `RUNNING` or `SUCCEEDED` raises `InvalidTransitionError` and leaves the first job, the first event, and the caller's other row in place.
3. Use a nested transaction for that rollback. Do not call `UnitOfWork.rollback` from this function.
4. A second workflow does not leave a second `ASSETS_COMPLETED` event when the job is already `READY`.
5. A worker-shaped `ASSETS_COMPLETED` event does not add a `PENDING` draft job.
6. Pin the missing-product `ValueError`, the idempotency key `DraftListingJob:{product_id}`, and the `except Exception` boundary.
7. Change `docs/architecture/JOB_AND_EVENT_CONTRACTS.md` line 163 from `pricing/draft assembly` to `pricing`, and line 165 from `draft assembly` to `no successor`.
8. Session 08 stays inactive. `current_session` stays 7. `state_revision` stays 64. Exit 78 stays HELD. Do not start the close gate or A10/A11 commissioning.

## 4. What already holds

One product already has one `DraftListingJob`. Copy and pricing already do not spawn another. A repeated call on the same workflow already reuses the event. A refused asset chain already writes nothing. The job is already `READY` and is not claimed. D-0034 stays the graph.
