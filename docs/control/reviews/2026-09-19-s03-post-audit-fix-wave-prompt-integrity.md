# Prompt Integrity Review: S03 Post-Audit Fix Wave

**Date:** 2026-09-19  
**Session:** S03 Post-Audit Fix Wave  
**Prompt Source:** User-provided task specification  
**Reviewer:** Cloud Agent (adversarial review mode)  
**Base Branch:** build/full-automation @ b619b24fd962bc32fbd2e1e22c04128dae51214e

---

## 1. Prompt Authenticity

**Status:** ✅ VERIFIED

This is a tactical fix-wave task, not a numbered session from the implementation workbook. The task specification was provided directly by the user via the cloud agent interface and does not require SHA-256 verification against the workbook. The task explicitly references:
- Base commit: b619b24fd962bc32fbd2e1e22c04128dae51214e
- PR #10 AUDIT.md as the coverage target source
- Exit 78 boundary must remain held
- No S04 scope creep

---

## 2. Three-Dimensional Review

### 2.1 Fidelity Review

**Reviewer:** Fidelity Specialist  
**Verdict:** ✅ ALIGNED with repository contracts and S03 completion state

**Findings:**

**F-1: Task References PR #10 AUDIT.md Correctly**
- **Status:** ✅ CORRECT
- **Evidence:** Task explicitly states "do NOT merge PR #10 as a feature — only READ its AUDIT.md for coverage targets"
- **Authority:** PR #10 exists at https://github.com/OmarA1-Bakri/money-machine/pull/10 with AUDIT.md containing SF-1 through SF-5
- **Alignment:** Task correctly treats AUDIT.md as specification, not code to merge

**F-2: Exit 78 Boundary Preservation**
- **Status:** ✅ CORRECT
- **Evidence:** Task explicitly states "Exit 78 / exit-78 fail-closed STAYS"
- **Authority:** Session 03 implementation log confirms worker/scheduler both exit 78 after DB check
- **Alignment:** No commissioning, no production claiming, matches S03 completion contract

**F-3: Library + Tests Only Constraint**
- **Status:** ✅ CORRECT
- **Evidence:** Task states "Library + tests only; fake handlers only; no live providers"
- **Authority:** S03 scope was orchestration primitives; S04 is commissioning
- **Alignment:** Fixes target library code and test coverage, no production activation

**F-4: Single PR Requirement**
- **Status:** ✅ CORRECT
- **Evidence:** Task states "Prefer ONE PR with all fixes" and "Push to a new branch and open ONE PR"
- **Authority:** Development governance allows integrated waves at Level 2
- **Alignment:** All fixes in one PR against build/full-automation reduces integration overhead

**F-5: Carries Forward S03 Contracts**
- **Status:** ✅ PRESERVED
- **Session 02 three-table contract:** Mentioned implicitly via idempotency fixes
- **JobStatus taxonomy:** Not changed, only tested
- **MULTIPLY boundary:** Not weakened, only proven via tests
- **YAML event→successor map:** Not changed, only covered
- **Assessment:** No S03 deliverables are dropped

### 2.2 Safety and Executability Review

**Reviewer:** Safety Specialist  
**Verdict:** ✅ SAFE with constraints correctly maintained

**Findings:**

**S-1: Fail-Closed Boundary Maintained**
- **Status:** ✅ SAFE
- **Evidence:** Task explicitly forbids removing exit 78
- **Risk:** None - worker/scheduler remain stub-only
- **Mitigation:** Task hardcodes "Exit 78 stays. No merge."

**S-2: No External Provider Calls**
- **Status:** ✅ SAFE
- **Evidence:** Task states "fake handlers only; no live providers"
- **Risk:** None - FakeReconciler remains in use
- **Mitigation:** Task explicitly scopes to library + tests

**S-3: No Production Data Exposure**
- **Status:** ✅ SAFE
- **Evidence:** Tests use deterministic UUIDs and throwaway databases
- **Authority:** AUDIT.md confirms "no uuid4" and "isolated throwaway databases"
- **Mitigation:** No secrets, no customer data, no provider tokens required

**S-4: CI Must Pass Before Merge**
- **Status:** ✅ REQUIRED
- **Evidence:** Task states "CI green (ruff format/check, pyright, pytest)" and "Report back: PR URL + tip SHA + CI green run URL"
- **Mitigation:** Explicit gate prevents broken merge

**S-5: Helper-Bypass Test Overclaim Risk**
- **Status:** ⚠️ IDENTIFIED in task as a should-fix
- **Evidence:** Task B) "Helper-bypass test overclaim: spy-only is insufficient"
- **Risk:** Test may not actually prevent helper bypass if it only spies rather than proving rejection
- **Mitigation:** Task explicitly requires this to be fixed

**S-6: Dual YAML Load Path Risk**
- **Status:** ⚠️ IDENTIFIED in task as a should-fix
- **Evidence:** Task B) "Dual YAML load: cached map vs uncached load_yaml_model per job — unify to one load path"
- **Risk:** Inconsistent YAML interpretation if two load paths diverge
- **Mitigation:** Task explicitly requires unification

**S-7: Idempotency Double-Dispatch Risk**
- **Status:** 🔴 BLOCKER (A-1 in task)
- **Evidence:** Task A-1 "dispatch_decision idempotent: On re-entry / double-dispatch, must NOT re-run create_multiply_successor"
- **Risk:** Same decision re-dispatched could create duplicate successor
- **Mitigation:** Task explicitly requires proving test for idempotency

**S-8: SUCCESSOR_CREATED → DedupeJob Footgun**
- **Status:** 🔴 BLOCKER (A-2 in task)
- **Evidence:** Task A-2 "SUCCESSOR_CREATED → DedupeJob YAML footgun via EventDispatcher.dispatch"
- **Risk:** SUCCESSOR_CREATED event could spawn a second DedupeJob (double-Dedupe)
- **Mitigation:** Task explicitly requires removal or rerouting to prevent this

**S-9: reclaim_expired_leases Retry Class Violation**
- **Status:** 🔴 BLOCKER (A-3 in task)
- **Evidence:** Task A-3 "reclaim_expired_leases respects RetryClass: NEVER and MANUAL_RESUME must NOT flip job back to READY"
- **Risk:** Jobs that should stay FAILED or BLOCKED could incorrectly return to READY
- **Mitigation:** Task explicitly requires proving tests

### 2.3 Gameability Review

**Reviewer:** Adversarial Tester  
**Verdict:** ⚠️ SOME WEAK EXIT CRITERIA require strengthening

**Findings:**

**G-1: "Coverage" Without Adversarial Proof**
- **Risk:** HIGH
- **Issue:** Task requires "SF-1 reclaim_expired_leases coverage" but doesn't specify adversarial test shape
- **Cheap Fake:** Call `reclaim_expired_leases()` with empty database, assert no exception
- **Real Proof:** Worker claims job, lease expires (time advance), second worker calls reclaim, job transitions to READY, first worker cannot heartbeat
- **Recommendation:** AUDIT.md SF-1 already specifies this; corrective addendum will reference it

**G-2: "mark_idempotency_completed Coverage"**
- **Risk:** MEDIUM
- **Issue:** Task requires SF-2 but doesn't specify three-table completion proof
- **Cheap Fake:** Call `mark_idempotency_completed()` with any idempotency_key, no assertion
- **Real Proof:** Reserve key, record CONFIRMED attempt, call mark_idempotency_completed, SELECT idempotency_records WHERE key = X, assert completed_at IS NOT NULL
- **Recommendation:** AUDIT.md SF-2 already specifies this; corrective addendum will reference it

**G-3: "Heartbeat Failure Scenarios"**
- **Risk:** MEDIUM
- **Issue:** Task requires SF-4 but doesn't specify LeaseExpiredError vs LeaseNotHeldError proof
- **Cheap Fake:** Mock heartbeat to raise any exception, catch it
- **Real Proof:** (1) Heartbeat with lease_expires_at < now → raises LeaseExpiredError; (2) Heartbeat with mismatched worker_id → raises LeaseNotHeldError
- **Recommendation:** AUDIT.md SF-4 already specifies this; corrective addendum will reference it

**G-4: "YAML Load Failure"**
- **Risk:** LOW
- **Issue:** Task requires SF-5 but doesn't specify FileNotFoundError vs ValueError proof
- **Cheap Fake:** Try/except any YAML load, pass
- **Real Proof:** (1) Remove workflows.yaml, call load_event_successor_map, assert FileNotFoundError with message; (2) Write invalid YAML, assert ValueError; (3) Second call returns cached dict
- **Recommendation:** AUDIT.md SF-5 already specifies this; corrective addendum will reference it

**G-5: "Dual YAML Load Unification"**
- **Risk:** MEDIUM
- **Issue:** Task B) says "unify to one load path" but doesn't specify correctness proof
- **Cheap Fake:** Delete one load path, all tests still pass (but maybe wrong tests)
- **Real Proof:** After unification, run successor creation tests and YAML config tests; both pass; coverage shows only one load path used
- **Recommendation:** Corrective addendum will require: unify, then assert via coverage that only one load path remains

**G-6: "CI Green Run URL"**
- **Status:** ✅ GOOD
- **Evidence:** Task requires "Report back: PR URL + tip SHA + CI green run URL"
- **Assessment:** Machine-verifiable; cannot fake without actual green CI run

---

## 3. Corrective Addendum

**Status:** This is the executable instruction set for the S03 post-audit fix wave.

### Scope

Fix three reviewer blockers (A-1, A-2, A-3), six should-fixes (B), and five coverage targets (C: SF-1 through SF-5) in ONE PR against build/full-automation @ b619b24fd962bc32fbd2e1e22c04128dae51214e.

### Constraints (Hard)

1. Exit 78 stays: worker.py and scheduler.py remain stubs with exit 78 after DB check
2. Library + tests only: no production agent commissioning, no live provider calls
3. No S04 scope: no worker activation, no scheduler trigger creation
4. Deterministic tests: no uuid4; use fixed UUIDs and timestamps
5. CI scope: ruff format (src tests scripts migrations), ruff check, pyright, pytest with DB
6. ONE PR: all fixes in one branch, one PR, against build/full-automation
7. Do NOT merge PR #10: only READ its AUDIT.md for targets

### Execution Sequence

#### Phase 1: Adversarial Review of Current Code

1. Read and understand current implementations:
   - `src/money_machine/orchestration/successor_factory.py` (dispatch_decision idempotency)
   - `src/money_machine/orchestration/event_dispatcher.py` (SUCCESSOR_CREATED → DedupeJob risk)
   - `src/money_machine/orchestration/leases.py` (reclaim_expired_leases RetryClass handling)
   - `src/money_machine/orchestration/idempotency.py` (mark_idempotency_completed)
   - `src/money_machine/orchestration/reconciliation.py` (budget → BLOCKED)
   - `config/workflows.yaml` (YAML load paths)

2. Read existing tests to understand current coverage:
   - `tests/integration/test_event_driven_successors.py`
   - `tests/integration/test_leases.py`
   - `tests/integration/orchestration/test_idempotency.py`
   - `tests/integration/orchestration/test_reconciliation.py`
   - `tests/unit/test_yaml_successor_map.py`

#### Phase 2: Implement Blocker Fixes (A-1, A-2, A-3)

**A-1: dispatch_decision Idempotent**
- **Requirement:** On re-entry / double-dispatch, must NOT re-run create_multiply_successor
- **Proving Test:** Double-dispatch the same decision, assert successor created once only
- **Implementation:**
  - Review `dispatch_decision` in `successor_factory.py`
  - Add idempotency check: if successor already created for this parent job + event + decision, skip creation
  - Add test: `test_dispatch_decision_idempotent_on_reentry` that dispatches same decision twice, asserts one successor only
  - Use deterministic UUIDs for job_id and decision fields

**A-2: SUCCESSOR_CREATED → DedupeJob YAML Footgun**
- **Requirement:** Remove or reroute so SUCCESSOR_CREATED does not spawn a second DedupeJob
- **Proving Test:** Prove YAML/event path cannot create the footgun
- **Implementation:**
  - Review `event_dispatcher.py` and `workflows.yaml`
  - Identify if SUCCESSOR_CREATED is mapped to any successor creation
  - If yes: remove that mapping or route it to a different handler
  - Add test: `test_successor_created_does_not_spawn_dedupe_job` that emits SUCCESSOR_CREATED, asserts no DedupeJob is created
  - Alternative: add explicit exclusion in event_dispatcher.dispatch to skip SUCCESSOR_CREATED

**A-3: reclaim_expired_leases Respects RetryClass**
- **Requirement:** NEVER and MANUAL_RESUME must NOT flip job back to READY
- **Proving Tests:** One test per RetryClass that should stay FAILED/BLOCKED
- **Implementation:**
  - Review `reclaim_expired_leases` in `leases.py`
  - Add RetryClass check: if RetryClass is NEVER or MANUAL_RESUME, do NOT transition to READY
  - Add test: `test_reclaim_expired_lease_respects_retry_never` - job with RetryClass.NEVER, lease expires, reclaim called, job stays FAILED
  - Add test: `test_reclaim_expired_lease_respects_retry_manual_resume` - job with RetryClass.MANUAL_RESUME, lease expires, reclaim called, job stays BLOCKED

#### Phase 3: Implement Should-Fixes (B)

**B-1: object_id=workflow_id + _infer_object_type Heuristics**
- **Issue:** Placeholder heuristics that lie
- **Fix:** Make real/correct, not placeholder
- **Implementation:**
  - Review `_infer_object_type` function (likely in events or object handling)
  - Replace placeholder logic with correct type inference
  - Ensure object_id correctly maps to workflow_id where appropriate

**B-2: Dual YAML Load Unification**
- **Issue:** Cached map vs uncached load_yaml_model per job
- **Fix:** Unify to one load path
- **Implementation:**
  - Review `load_event_successor_map` in `successor_factory.py` and any `load_yaml_model` usage
  - Consolidate to one path: prefer cached map approach
  - Remove or redirect uncached load path
  - Verify via coverage: only one YAML load function is called

**B-3: WINNER→SUCCESSOR recorded_at Order Assert**
- **Issue:** Event order assertion missing
- **Fix:** Add assertion that WINNER event recorded_at < SUCCESSOR event recorded_at
- **Implementation:**
  - Review event recording in `event_dispatcher.py` or relevant test
  - Add test: create WINNER event, create SUCCESSOR event, SELECT both, assert WINNER.recorded_at < SUCCESSOR.recorded_at

**B-4: Helper-Bypass Test Overclaim**
- **Issue:** Spy-only is insufficient — prove direct-call to guarded helper raises / is rejected
- **Fix:** Strengthen test to actually call helper and assert rejection
- **Implementation:**
  - Identify "helper-bypass" test (likely in test_successor_boundary.py or similar)
  - Change from spy-based assertion to actual call assertion
  - Directly call the guarded helper without proper guard, assert exception or rejection

**B-5: FakeReconciler Out of Library Package**
- **Issue:** FakeReconciler is in production orchestration package
- **Fix:** Move to tests/fakes
- **Implementation:**
  - Move `FakeReconciler` from `src/money_machine/orchestration/reconciliation.py` to `tests/fakes/fake_reconciler.py`
  - Update all test imports to reference `tests.fakes.fake_reconciler`
  - Ensure production code does not import from tests/

**B-6: Worker Doc Drift**
- **Issue:** "commissioned in S03" vs exit 78 reality
- **Fix:** Update docs to match exit-78 reality
- **Implementation:**
  - Grep for "commissioned in S03" in docs, README, worker.py, scheduler.py
  - Replace with correct status: "Exit 78 stub; commissioning deferred to Session 04"
  - Update any architecture diagrams or contract docs

#### Phase 4: Implement Coverage Targets (C: SF-1 through SF-5)

**SF-1: reclaim_expired_leases Coverage**
- **Requirement:** Integration test proving expired lease recovery
- **AUDIT.md Acceptance:** Worker claims job, lease expires (time advance), second worker calls reclaim_expired_leases, job transitions to READY, first worker cannot heartbeat
- **Implementation:**
  - Add test: `test_reclaim_expired_leases_recovers_stalled_job`
  - Worker 1 claims job, lease_expires_at set to NOW + 60s
  - Advance time to NOW + 61s (mock or UPDATE)
  - Worker 2 calls reclaim_expired_leases
  - Assert job status → READY, worker_id → NULL, lease cleared
  - Worker 1 attempts heartbeat, assert LeaseExpiredError or LeaseNotHeldError

**SF-2: mark_idempotency_completed Coverage**
- **Requirement:** Three-table contract completion path
- **AUDIT.md Acceptance:** Reserve key, record CONFIRMED attempt, call mark_idempotency_completed, assert completed_at is set
- **Implementation:**
  - Add test: `test_mark_idempotency_completed_sets_timestamp`
  - reserve_idempotency_key(key="test-key")
  - record_effect_attempt(key, state=EffectState.CONFIRMED)
  - mark_idempotency_completed(key)
  - SELECT * FROM idempotency_records WHERE key = "test-key"
  - assert row.completed_at IS NOT NULL

**SF-3: Reconciliation Budget → BLOCKED Path**
- **Requirement:** Job transitions to BLOCKED with incident after exceeding max_reconciliation_attempts
- **AUDIT.md Acceptance:** Job with reconciliation_attempt=2, max=3, reconciler returns UNKNOWN, assert job → BLOCKED, incident created
- **Implementation:**
  - Add test: `test_reconciliation_budget_exhausted_blocks_job`
  - Create job with reconciliation_attempt = 2, max_reconciliation_attempts = 3
  - Call reconcile_uncertain_effect with FakeReconciler returning UNKNOWN
  - Assert job.status = JobStatus.BLOCKED
  - Assert incident record created with reason "reconciliation budget exhausted"

**SF-4: Heartbeat Failure Scenarios**
- **Requirement:** LeaseExpiredError and LeaseNotHeldError raised correctly
- **AUDIT.md Acceptance:** (1) heartbeat with lease_expires_at < now raises LeaseExpiredError; (2) heartbeat with mismatched worker_id raises LeaseNotHeldError
- **Implementation:**
  - Add test: `test_heartbeat_raises_lease_expired_error`
    - Claim job, set lease_expires_at = NOW - 1s
    - Call heartbeat(job_id, worker_id)
    - Assert raises LeaseExpiredError
  - Add test: `test_heartbeat_raises_lease_not_held_error`
    - Claim job with worker_1
    - Call heartbeat(job_id, worker_2)
    - Assert raises LeaseNotHeldError

**SF-5: YAML Load Failure**
- **Requirement:** Missing/malformed YAML raises with helpful message
- **AUDIT.md Acceptance:** (1) missing workflows.yaml raises FileNotFoundError with message; (2) invalid YAML raises ValueError; (3) cache works (second call returns same dict)
- **Implementation:**
  - Add test: `test_yaml_load_missing_file`
    - Rename or delete workflows.yaml temporarily
    - Call load_event_successor_map()
    - Assert raises FileNotFoundError with message containing "workflows.yaml"
  - Add test: `test_yaml_load_invalid_syntax`
    - Write malformed YAML to workflows.yaml
    - Call load_event_successor_map()
    - Assert raises ValueError or yaml.YAMLError
  - Add test: `test_yaml_load_cached`
    - Call load_event_successor_map() twice
    - Assert second call returns cached dict (same object id or mock call count = 1)

#### Phase 5: CI Validation

1. Run `ruff format` on src tests scripts migrations
2. Run `ruff check`
3. Run `pyright`
4. Run `pytest` with database (all tests must pass)
5. Inspect coverage report for:
   - leases.py: reclaim_expired_leases covered
   - idempotency.py: mark_idempotency_completed covered
   - reconciliation.py: budget exhaustion path covered
   - leases.py: heartbeat error paths covered
   - successor_factory.py: YAML load failure paths covered

#### Phase 6: Closure

1. Create new branch: `cursor/s03-post-audit-fixes-d700`
2. Commit all fixes with descriptive message
3. Push to origin
4. Create PR against build/full-automation
5. Report back:
   - PR URL
   - Tip SHA
   - CI green run URL

### Deferrals

**None.** All blockers, should-fixes, and coverage targets are in scope for this fix wave.

### Amendments from Gameability Review

1. **SF-1 through SF-5:** Reference AUDIT.md detailed acceptance criteria, not just high-level names
2. **A-1 Idempotency Proof:** Must use deterministic UUIDs and actually dispatch twice, not just assert via mock
3. **A-2 YAML Footgun:** Must prove via test that SUCCESSOR_CREATED cannot spawn DedupeJob
4. **A-3 RetryClass Respect:** Must have one test per RetryClass (NEVER, MANUAL_RESUME)
5. **B-2 YAML Unification:** Must verify via coverage that only one load path remains after unification

---

## 4. What the Task Already Gets Right

1. **Exit 78 Boundary Preservation:** Explicitly stated multiple times; no risk of accidental removal
2. **Single PR Strategy:** Reduces integration overhead and review cycles
3. **Deterministic Tests:** Explicitly requires no uuid4; ensures reproducibility
4. **CI Gate:** Requires green CI before reporting completion
5. **AUDIT.md as Specification:** Correctly treats PR #10's AUDIT.md as coverage target source, not code to merge
6. **No S04 Scope Creep:** Explicitly forbids worker commissioning, production activation, or live provider integration

---

## 5. Verification Gates for This Fix Wave

### Level 1 (Per Fix)
- RED: Failing test proves the issue
- GREEN: Fix makes test pass
- Focused regression: Related tests still pass

### Level 2 (Integration)
- All A, B, C fixes integrated
- Full orchestration test suite passes
- ruff format, ruff check, pyright pass
- Coverage inspection confirms SF-1 through SF-5 paths covered

### Level 3 (Session Exit - Not Required for Fix Wave)
- Not applicable: this is a tactical fix wave, not a numbered session
- However, per development governance, this wave should:
  - Update IMPLEMENTATION_LOG.md with fix wave record
  - Update TEST_EVIDENCE.md with new coverage data
  - No IMPLEMENTATION_STATE.json change (no session number)

---

## 6. Risk Assessment

### High Risk (Mitigated)

**R-1: Idempotency Violation in dispatch_decision**
- **Risk:** Double-dispatch creates duplicate successors
- **Mitigation:** A-1 requires proving test before implementation

**R-2: SUCCESSOR_CREATED Footgun**
- **Risk:** Event loop creates second DedupeJob
- **Mitigation:** A-2 requires removal or explicit routing + proving test

**R-3: RetryClass Violation in reclaim_expired_leases**
- **Risk:** NEVER/MANUAL_RESUME jobs incorrectly retried
- **Mitigation:** A-3 requires tests for each RetryClass

### Medium Risk (Managed)

**R-4: YAML Load Path Divergence**
- **Risk:** Cached vs uncached load could interpret YAML differently
- **Mitigation:** B-2 requires unification + coverage verification

**R-5: Helper-Bypass Test Weakness**
- **Risk:** Test doesn't actually prove guard works
- **Mitigation:** B-4 requires actual call + rejection assertion

### Low Risk

**R-6: Documentation Drift**
- **Risk:** Docs say "commissioned in S03" when reality is exit 78
- **Mitigation:** B-6 requires doc update; low consequence if missed

---

## 7. Completion Evidence Required

1. **Branch:** cursor/s03-post-audit-fixes-d700
2. **Commits:** All fixes in one or more logical commits
3. **PR:** Created against build/full-automation
4. **CI:** Green run URL provided
5. **Coverage:** Inspection confirms SF-1 through SF-5 paths covered
6. **Tests:** All new tests pass with deterministic UUIDs
7. **Exit 78:** Still held (worker.py, scheduler.py unchanged except docs)

---

## Signature

**Review Completed By:** Cloud Agent (adversarial review mode)  
**Review Date:** 2026-09-19  
**Corrective Addendum Status:** EXECUTABLE  
**Blockers:** None (all identified in task as A-1, A-2, A-3)  
**Deferrals:** None  
**Proceed to Implementation:** ✅ YES
