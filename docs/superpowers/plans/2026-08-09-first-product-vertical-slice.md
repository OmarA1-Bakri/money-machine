# First Product Vertical Slice Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce one durable, replayable, locally inspectable product bundle and listing package that reaches `DRAFT_READY` from a 25–40-row admitted research packet without any live provider mutation.

**Architecture:** Extend the existing modular monolith with strict Pydantic contracts, a PostgreSQL durable workflow spine, deterministic local product and asset rendering, and provider-neutral simulation/draft adapters. Logical agent roles remain explicit, but the first slice executes as typed workflow steps under one worker and one scheduler.

**Tech Stack:** Python 3.12, Pydantic 2, FastAPI, SQLAlchemy 2 async, Alembic, asyncpg, Typer, PostgreSQL 16, Jinja2, Pillow, WeasyPrint or the repository-approved deterministic PDF backend, pytest, Ruff, strict Pyright, Docker Compose.

## Global Constraints

- Baseline design: `docs/superpowers/specs/2026-08-09-first-product-vertical-slice-design.md`.
- All behavior changes use red-green-refactor TDD; no production code before an observed failing test.
- One integration owner controls dependency files, migrations, shared enums/events, orchestration composition, control state, and merges.
- Parallel workers use isolated Git worktrees and non-overlapping owned paths.
- No Etsy, Notion, messaging, purchase, publication, customer, or provider mutation.
- `EXTERNAL_EFFECT_MODE` remains `simulation` or `draft`; incremental spend remains exactly `0.00`.
- No agent may edit `docs/control/` except the integration owner at final reconciliation.
- Preserve both immutable source files and all Session 00 evidence byte-for-byte.
- Each task ends with targeted tests, a bounded commit, implementer self-review, and independent task review.
- Full repository verification runs once after all integrated tasks are stable.

---
## File and ownership map

| Owner | Paths | Responsibility |
|---|---|---|
| Integration | `pyproject.toml`, `uv.lock`, `compose*.yaml`, `migrations/**`, shared domain enums/events, orchestration composition, CLI/API registration, `docs/control/**` | Freeze shared interfaces, integrate lane commits, run final slice |
| Hardening lane | `src/money_machine/control/**`, `src/money_machine/orchestration/_foundation.py`, worker/scheduler entrypoints, focused bootstrap/unit tests | Close open CodeRabbit findings |
| Contract lane | Slice domain models, value objects, config loader/validation, unit contract tests | Define canonical schemas and transition rules |
| Persistence lane | `src/money_machine/persistence/**`, orchestration leases/retry/dependency primitives, database integration tests | Durable PostgreSQL state and atomic job operations |
| Research lane | Research/qualification/dedupe services and market-research/product-strategy wrappers, focused tests | Research packet to approved ProductSpec |
| Build lane | Notion-compatible local builder, product QA, artifact storage, focused tests | ProductSpec to QA-passed product bundle |
| Merchandising lane | Claim validation, listing copy, deterministic assets, preflight, focused tests | QA-passed bundle to DRAFT_READY listing package |
| Integration/review | CLI/API, full workflow, E2E, runtime packet, reviews and control reconciliation | Execute and prove the complete slice |

The integration owner publishes the contract commit before Wave 1 worktrees begin. Wave 1 workers rebase on that commit and never modify shared contracts.

---

### Task 1: Close Session 00 CodeRabbit findings

**Files:**
- Create: `src/money_machine/control/locking.py`
- Modify: `src/money_machine/control/state.py`
- Modify: `src/money_machine/orchestration/_foundation.py`
- Modify: `src/money_machine/orchestration/worker.py`
- Modify: `src/money_machine/orchestration/scheduler.py`
- Test: `tests/bootstrap/test_control_state.py`
- Test: `tests/unit/test_foundation_processes.py`
**Interfaces:**
- Produces: `exclusive_control_lock(path: Path) -> ContextManager[None]`.
- Preserves: `apply_completion_transition(state_path: Path, candidate_path: Path) -> ControlState` public behavior and `ControlStateError` error type.
- Constraint: lock acquisition, Git verification, validation, and atomic write occur under one exclusive sibling lock.

- [ ] **Step 1: Write failing timeout and UTF-8 tests**

Add tests that monkeypatch the Git subprocess helper to raise `subprocess.TimeoutExpired` and assert `ControlStateError("git command timed out")`; also assert every Git invocation receives the configured timeout, `text=True`, and `encoding="utf-8"`.

- [ ] **Step 2: Run the timeout tests and verify RED**

Run: `uv run pytest -q tests/bootstrap/test_control_state.py -k 'timeout or utf8'`

Expected: FAIL because the current subprocess path has no timeout/encoding contract.

- [ ] **Step 3: Implement bounded Git subprocess execution**

Introduce `_run_git(repo_root: Path, *arguments: str) -> str` in `state.py`. It calls `subprocess.run(("git", *arguments), cwd=repo_root, timeout=CONTROL_GIT_TIMEOUT_SECONDS, text=True, encoding="utf-8", capture_output=True, check=False)`, converts `TimeoutExpired` and `OSError` to `ControlStateError`, and preserves explicit return-code validation.

- [ ] **Step 4: Verify timeout tests GREEN**

Run the command from Step 2 and require all selected tests to pass.

- [ ] **Step 5: Write failing atomic descriptor tests**

Add tests that force `os.fdopen` and the write path to fail, assert the raw descriptor is closed exactly once, assert temporary files are removed, and cover a platform without `os.fchmod`.

- [ ] **Step 6: Run descriptor tests and verify RED**

Run: `uv run pytest -q tests/bootstrap/test_control_state.py -k 'descriptor or fchmod or atomic_write'`
Expected: FAIL on descriptor ownership or unconditional `os.fchmod` behavior.

- [ ] **Step 7: Implement portable atomic ownership**

Transfer the `mkstemp` descriptor immediately into `os.fdopen` inside a guarded context, invoke `os.fchmod` only when available, fsync the file, atomically replace the target, fsync the directory where supported, and remove the temporary path on every failure.

- [ ] **Step 8: Write failing concurrent-transition test**

Start two processes against the same candidate and state path. Assert exactly one transition succeeds, the other fails closed with `ControlStateError`, and the final JSON remains valid with a single state-revision increment.

- [ ] **Step 9: Implement the sibling lock**

Create `<state-file>.lock`. Use `fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)` on POSIX and `msvcrt.locking(lock_file.fileno(), msvcrt.LK_LOCK, 1)` on Windows. Hold the lock across state read, candidate read, Git checks, validation, and atomic write. Fail closed when the lock cannot be acquired.

- [ ] **Step 10: Move logging configuration to entrypoints**

Replace `logging.basicConfig` in `_foundation.py` with `LOGGER = logging.getLogger(__name__)`. Configure logging once in `worker.main()` and `scheduler.main()` before calling `unavailable`.

- [ ] **Step 11: Run focused and static gates**

Run:

```bash
uv run pytest -q tests/bootstrap/test_control_state.py tests/unit/test_foundation_processes.py
uv run ruff check src/money_machine/control src/money_machine/orchestration tests/bootstrap/test_control_state.py tests/unit/test_foundation_processes.py
uv run pyright src/money_machine/control src/money_machine/orchestration tests/bootstrap/test_control_state.py tests/unit/test_foundation_processes.py
```

- [ ] **Step 12: Commit**

```bash
git add src/money_machine/control src/money_machine/orchestration/_foundation.py src/money_machine/orchestration/worker.py src/money_machine/orchestration/scheduler.py tests/bootstrap/test_control_state.py tests/unit/test_foundation_processes.py
git commit -m "fix(control): harden state transition and process logging"
```
---

### Task 2: Freeze first-slice contracts, states, and configuration

**Files:**
- Modify: `src/money_machine/domain/enums.py`
- Modify: `src/money_machine/domain/events.py`
- Modify: `src/money_machine/domain/value_objects.py`
- Modify: `src/money_machine/domain/models/research.py`
- Modify: `src/money_machine/domain/models/candidate.py`
- Modify: `src/money_machine/domain/models/product_spec.py`
- Modify: `src/money_machine/domain/models/product.py`
- Modify: `src/money_machine/domain/models/asset.py`
- Modify: `src/money_machine/domain/models/listing.py`
- Modify: `src/money_machine/domain/models/job.py`
- Modify: `src/money_machine/domain/models/workflow.py`
- Modify: `src/money_machine/config/loader.py`
- Modify: `src/money_machine/config/validation.py`
- Modify: `config/product_rules.yaml`
- Modify: `config/agents.yaml`
- Modify: `config/workflows.yaml`
- Test: `tests/unit/domain/test_first_product_contracts.py`
- Test: `tests/unit/domain/test_first_product_transitions.py`
- Test: `tests/unit/config/test_first_product_config.py`

**Interfaces:**
- Produces the canonical Pydantic models and enums consumed verbatim by every later task.
- Produces `canonical_json(value: BaseModel | Mapping[str, object]) -> bytes` and `canonical_sha256(value: BaseModel | Mapping[str, object]) -> str`.
- Produces `assert_product_transition(current, target) -> None` and `assert_job_transition(current, target) -> None`.
**Required enum values:**

```python
class QualificationDimension(StrEnum):
    DEMAND = "demand"
    DIFFERENTIATION = "differentiation"
    BUILD_FEASIBILITY = "build_feasibility"
    BUYER_VALUE = "buyer_value"

class ProductState(StrEnum):
    RESEARCHED = "RESEARCHED"
    QUALIFIED = "QUALIFIED"
    SPECIFIED = "SPECIFIED"
    DEDUPE_PASSED = "DEDUPE_PASSED"
    BUILT = "BUILT"
    QA_PASSED = "QA_PASSED"
    MERCHANDISED = "MERCHANDISED"
    PREFLIGHT_PASSED = "PREFLIGHT_PASSED"
    DRAFT_READY = "DRAFT_READY"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    REJECTED = "REJECTED"
    FAILED = "FAILED"

class JobState(StrEnum):
    PENDING = "PENDING"
    READY = "READY"
    LEASED = "LEASED"
    RUNNING = "RUNNING"
    RETRY_WAIT = "RETRY_WAIT"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"

class RetryClass(StrEnum):
    NEVER = "NEVER"
    TRANSIENT_INTERNAL = "TRANSIENT_INTERNAL"
    TRANSIENT_PROVIDER_READ = "TRANSIENT_PROVIDER_READ"
    RECONCILE_EXTERNAL_EFFECT = "RECONCILE_EXTERNAL_EFFECT"
    OPERATOR_REQUIRED = "OPERATOR_REQUIRED"
```
**Required model boundaries:**

```python
class EvidenceReference(FrozenModel):
    evidence_id: str
    source_url: AnyHttpUrl
    observed_at: datetime
    source_mode: Literal["manual_export", "connector_read", "fixture"]
    freshness_status: Literal["current", "stale", "unknown"]
    content_sha256: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]

class ResearchObservation(FrozenModel):
    observation_id: str
    evidence: EvidenceReference
    marketplace: str
    title: str
    category: str
    identity_niche: str
    base_category: str
    price: Decimal | None
    currency: str | None
    demand_proxies: dict[str, Decimal]
    competition_proxies: dict[str, Decimal]
    qualification_inputs: dict[QualificationDimension, Decimal]
    listing_quality_notes: tuple[str, ...]

class ResearchPacket(FrozenModel):
    packet_id: str
    imported_at: datetime
    observations: Annotated[tuple[ResearchObservation, ...], Field(min_length=25, max_length=40)]
    packet_sha256: str

class QualificationScore(FrozenModel):
    candidate_id: str
    demand: int = Field(ge=0, le=10)
    differentiation: int = Field(ge=0, le=10)
    build_feasibility: int = Field(ge=0, le=10)
    buyer_value: int = Field(ge=0, le=10)
    evidence_ids: tuple[str, ...]
```
class ProductSpec(FrozenModel):
    product_spec_id: str
    candidate_id: str
    identity_niche: str
    base_category: str
    target_buyer: str
    promised_outcome: str
    hubs: Annotated[tuple[str, ...], Field(min_length=6, max_length=8)]
    colour_variants: Annotated[tuple[str, ...], Field(min_length=3, max_length=4)]
    features: tuple[str, ...]
    product_facts: tuple[str, ...]
    source_evidence_ids: tuple[str, ...]
    spec_sha256: str

class JobEnvelope(FrozenModel):
    job_id: UUID
    workflow_run_id: UUID
    job_type: str
    state: JobState
    idempotency_key: str
    input_sha256: str
    retry_class: RetryClass
    max_attempts: int = Field(ge=1, le=5)
```

- [ ] **Step 1: Write failing contract tests**

Test strict unknown-field rejection, timezone-aware timestamps, 25/40 packet limits, canonical 64-character hashes, score bounds, 30/40 threshold behavior, six-to-eight hubs, three-to-four variants, and exact enum serialization.

- [ ] **Step 2: Verify contract tests RED**

Run: `uv run pytest -q tests/unit/domain/test_first_product_contracts.py`

Expected: import or assertion failures because the current files are one-line scaffolds.
- [ ] **Step 3: Implement strict canonical models**

Use one `FrozenModel` base with `ConfigDict(extra="forbid", frozen=True, strict=True)`. Normalize no user content silently. Add field validators only for semantic constraints that Pydantic types cannot express.

- [ ] **Step 4: Write transition-table tests**

Assert the exact happy path, terminal `INSUFFICIENT_EVIDENCE`, `REJECTED`, and `FAILED` branches; reject backward transitions, skipped stages, and transitions out of terminal states. Cover valid job leasing, retry, success, failure, and cancellation transitions.

- [ ] **Step 5: Verify transition tests RED**

Run: `uv run pytest -q tests/unit/domain/test_first_product_transitions.py`

- [ ] **Step 6: Implement transition tables and event names**

Represent allowed transitions as immutable mappings. Define events including `research_packet_admitted`, `candidate_shortlisted`, `product_spec_created`, `dedupe_passed`, `product_built`, `product_qa_passed`, `listing_package_created`, `preflight_passed`, and `draft_ready`.

- [ ] **Step 7: Write configuration tests**

Assert `config/product_rules.yaml` contains research rows `25..40`, shortlist size `5`, threshold `30`, hubs `6..8`, colour variants `3..4`, tags `13`, images `10`, and video count `1`; assert exactly the first-slice logical roles and workflow steps are registered.

- [ ] **Step 8: Implement typed configuration loading**

Load YAML into strict Pydantic settings. Reject missing, duplicated, conflicting, or out-of-range values. Keep `external_mutations_enabled=false` and `spend_enabled=false`.

- [ ] **Step 9: Run the contract lane gates**

```bash
uv run pytest -q tests/unit/domain tests/unit/config/test_first_product_config.py
uv run ruff check src/money_machine/domain src/money_machine/config tests/unit/domain tests/unit/config
uv run pyright src/money_machine/domain src/money_machine/config tests/unit/domain tests/unit/config
```
- [ ] **Step 10: Commit the contract freeze**

```bash
git add src/money_machine/domain src/money_machine/config config/product_rules.yaml config/agents.yaml config/workflows.yaml tests/unit/domain tests/unit/config
git commit -m "feat(domain): freeze first product slice contracts"
```

Publish this commit SHA to every Wave 1 lane. Later tasks may consume but not edit these contracts without integration-owner approval.

---

### Task 3: Add PostgreSQL schema and durable repositories

**Files:**
- Modify: `pyproject.toml`
- Modify: `uv.lock`
- Modify: `migrations/env.py`
- Create: `migrations/versions/0001_first_product_slice.py`
- Create: `scripts/prepare_test_database.sh`
- Create: `scripts/prepare_test_database.ps1`
- Modify: `src/money_machine/persistence/database.py`
- Modify: `src/money_machine/persistence/tables.py`
- Modify: `src/money_machine/persistence/unit_of_work.py`
- Modify: `src/money_machine/persistence/repositories/jobs.py`
- Modify: `src/money_machine/persistence/repositories/events.py`
- Modify: `src/money_machine/persistence/repositories/artifacts.py`
- Modify: `src/money_machine/persistence/repositories/research.py`
- Modify: `src/money_machine/persistence/repositories/products.py`
- Modify: `src/money_machine/persistence/repositories/listings.py`
- Modify: `src/money_machine/persistence/repositories/workflows.py`
- Test: `tests/integration/database/test_first_product_schema.py`
- Test: `tests/integration/database/test_first_product_repositories.py`
- Test: `tests/integration/database/test_atomic_job_completion.py`
**Interfaces:**
- Add dependencies: `sqlalchemy[asyncio]>=2.0.43,<3`, `asyncpg>=0.30,<1`, `alembic>=1.16,<2`, `typer>=0.16,<1`, `jinja2>=3.1,<4`, `pillow>=11,<12`, and `fpdf2>=2.8,<3`.
- Produce `Database.from_url(url: str) -> Database` with `async_sessionmaker`.
- Produce `UnitOfWork` exposing `jobs`, `events`, `artifacts`, `research`, `products`, `listings`, and `workflows` repositories.
- Produce `scripts/prepare_test_database.sh LANE_ID`, which creates or recreates an isolated `money_machine_test_<safe-lane-id>` database and prints only its async SQLAlchemy URL to stdout.
- Produce the PowerShell equivalent with identical naming and output semantics.
- Produce transactional repository methods used by Task 4.

**Required tables:**

```text
workflow_runs
jobs
job_dependencies
job_attempts
domain_events
artifacts
evidence_references
research_packets
research_observations
candidates
qualification_scores
candidate_shortlists
product_specs
dedupe_results
build_results
product_qa_results
listing_packages
preflight_results
```

- [ ] **Step 1: Add failing migration smoke test**

Against `MONEY_MACHINE_TEST_DATABASE_URL`, upgrade a clean database to head and assert the exact table set, primary keys, foreign keys, unique constraints, check constraints, and indexes.

- [ ] **Step 2: Verify migration test RED**

Run: `MONEY_MACHINE_TEST_DATABASE_URL="$(scripts/prepare_test_database.sh persistence-schema)" uv run pytest -q tests/integration/database/test_first_product_schema.py`

Expected: FAIL because Alembic has no migration version and the database has zero user tables.
- [ ] **Step 3: Implement SQLAlchemy metadata and migration**

Use PostgreSQL UUID, JSONB, TIMESTAMPTZ, NUMERIC, and TEXT types. Add database checks for state enum strings, non-negative attempts, lease expiry, 64-character hashes, and product score ranges. Do not use database-native enum types in migration 0001; use check-constrained text to simplify forward migrations.

- [ ] **Step 4: Add failing repository round-trip tests**

Persist and reload one strict instance of every slice result. Assert canonical payload hashes, ordering, immutable insert behavior, and collision rejection when an identity is reused with different bytes.

- [ ] **Step 5: Implement repository mappings**

Repositories serialize Pydantic models to canonical JSON and reconstruct them with `model_validate`. Use explicit insert/select statements; do not expose generic table mutation to application code.

- [ ] **Step 6: Add failing atomic-completion test**

Create a running job, then force successor insertion to violate a uniqueness constraint. Assert the parent remains `RUNNING`, no completion event exists, no result row exists, and no partial successor exists.

- [ ] **Step 7: Implement unit-of-work transaction semantics**

`UnitOfWork.__aenter__` opens one async session and transaction. `commit_job_success(job_id: UUID, lease_token: str, attempt_number: int, result_type: str, result_payload: FrozenModel, event: DomainEvent, successor: JobEnvelope | None) -> None` persists result, terminal attempt, event, parent state, and successor in the same transaction. Exceptions roll back every write.

- [ ] **Step 8: Add migration replay and downgrade tests**

Upgrade empty → head twice without drift, downgrade head → base, then upgrade again. Assert no application data is used in migration tests and no migration performs provider I/O.

- [ ] **Step 9: Run persistence gates**

```bash
MONEY_MACHINE_TEST_DATABASE_URL="$(scripts/prepare_test_database.sh persistence-suite)" uv run pytest -q tests/integration/database
uv run ruff check src/money_machine/persistence migrations tests/integration/database
uv run pyright src/money_machine/persistence tests/integration/database
uv lock --check
```
- [ ] **Step 10: Commit**

```bash
git add pyproject.toml uv.lock migrations src/money_machine/persistence tests/integration/database
git commit -m "feat(persistence): add durable first product state"
```

---

### Task 4: Implement durable job orchestration

**Files:**
- Modify: `src/money_machine/orchestration/transition_guard.py`
- Modify: `src/money_machine/orchestration/dependency_resolver.py`
- Modify: `src/money_machine/orchestration/leases.py`
- Modify: `src/money_machine/orchestration/retry.py`
- Modify: `src/money_machine/orchestration/idempotency.py`
- Modify: `src/money_machine/orchestration/event_dispatcher.py`
- Modify: `src/money_machine/orchestration/successor_factory.py`
- Modify: `src/money_machine/orchestration/engine.py`
- Modify: `src/money_machine/orchestration/worker.py`
- Modify: `src/money_machine/orchestration/scheduler.py`
- Modify: `src/money_machine/orchestration/workflows/product_experiment.py`
- Test: `tests/integration/orchestration/test_job_lifecycle.py`
- Test: `tests/integration/orchestration/test_leasing_and_recovery.py`
- Test: `tests/integration/orchestration/test_first_product_template.py`
- Test: `tests/failure_injection/test_expired_lease.py`
- Test: `tests/e2e/test_restart_recovery.py`

**Interfaces:**
- Consumes the frozen `JobEnvelope`, state enums, event names, and Task 3 repositories.
- Produces `OrchestrationEngine.start_first_product(packet_id: str) -> UUID`.
- Produces `Worker.run_once() -> WorkerResult` and `Scheduler.enqueue_due(now: datetime) -> int`.
**Canonical job sequence:**

```text
ADMIT_RESEARCH_PACKET
SCORE_AND_SHORTLIST
CREATE_PRODUCT_SPEC
RUN_DEDUPE
BUILD_LOCAL_PRODUCT
RUN_PRODUCT_QA
CREATE_LISTING_PACKAGE
RUN_PREFLIGHT
```

- [ ] **Step 1: Write failing template and dependency tests**

Assert `start_first_product` creates one workflow and only the first job as `READY`; every later job is `PENDING` with exactly one predecessor. Assert stable workflow/job/idempotency identities across identical replays.

- [ ] **Step 2: Verify template tests RED**

Run: `MONEY_MACHINE_TEST_DATABASE_URL="$(scripts/prepare_test_database.sh orchestration-template)" uv run pytest -q tests/integration/orchestration/test_first_product_template.py`

- [ ] **Step 3: Implement workflow template and successor factory**

Define the sequence as immutable typed configuration. `SuccessorFactory` creates only the next declared job and rejects unknown, skipped, duplicated, or backward successors.

- [ ] **Step 4: Write failing concurrent lease tests**

Run two workers concurrently against one ready job. Assert exactly one obtains the lease via `SELECT job_id FROM jobs WHERE state='READY' AND available_at<=:now ORDER BY created_at, job_id FOR UPDATE SKIP LOCKED LIMIT 1`; assert lease owner, token, start time, and expiry are persisted.

- [ ] **Step 5: Implement claiming and transition guards**

Claim in one transaction, use a cryptographically random lease token, require exact worker/token binding for heartbeat and completion, and reject completion after lease expiry.

- [ ] **Step 6: Write retry and recovery tests**

Cover `NEVER`, bounded transient retry, exponential delay capped by configuration, exhausted attempts, process crash after lease, and reclaim after expiry without duplicate result or event rows.
- [ ] **Step 7: Implement retry classification and recovery**

Persist every attempt. A retry schedules `available_at`; it never sleeps inside the transaction. Expired `LEASED` or `RUNNING` jobs return to `READY` only when their retry policy permits it.

- [ ] **Step 8: Write failing worker handler tests**

Use a real repository and a test handler registry. Assert success commits result/event/successor atomically, handler failure follows retry policy, unknown handler fails closed, and a handler cannot emit an undeclared successor.

- [ ] **Step 9: Implement `Worker.run_once`**

`run_once` claims at most one job, invokes the exact registered handler outside the claim transaction, then completes through the unit-of-work with the lease token. It returns structured `processed`, `idle`, or `failed` status.

- [ ] **Step 10: Implement bounded scheduler behavior**

The scheduler enqueues the configured first-product workflow only when an explicit schedule record is due. With no schedule record it reports idle and exits zero; it performs no publication or provider action.

- [ ] **Step 11: Run orchestration and failure gates**

```bash
MONEY_MACHINE_TEST_DATABASE_URL="$(scripts/prepare_test_database.sh orchestration-suite)" uv run pytest -q tests/integration/orchestration tests/failure_injection/test_expired_lease.py tests/e2e/test_restart_recovery.py
uv run ruff check src/money_machine/orchestration tests/integration/orchestration tests/failure_injection/test_expired_lease.py tests/e2e/test_restart_recovery.py
uv run pyright src/money_machine/orchestration tests/integration/orchestration tests/failure_injection/test_expired_lease.py tests/e2e/test_restart_recovery.py
```

- [ ] **Step 12: Commit**

```bash
git add src/money_machine/orchestration tests/integration/orchestration tests/failure_injection/test_expired_lease.py tests/e2e/test_restart_recovery.py
git commit -m "feat(orchestration): run durable first product jobs"
```
---

### Task 5: Implement research admission, qualification, ProductSpec, and dedupe

**Files:**
- Modify: `src/money_machine/application/services/research_service.py`
- Modify: `src/money_machine/domain/services/low_ticket.py`
- Modify: `src/money_machine/domain/services/product_rules.py`
- Modify: `src/money_machine/domain/services/dedupe.py`
- Modify: `src/money_machine/agents/implementations/market_research.py`
- Modify: `src/money_machine/agents/implementations/product_strategy.py`
- Modify: `src/money_machine/agents/implementations/catalogue_dedupe.py`
- Modify: `src/money_machine/agents/contracts/market_research.py`
- Modify: `src/money_machine/agents/contracts/product_strategy.py`
- Modify: `src/money_machine/agents/contracts/catalogue_dedupe.py`
- Create: `tests/fixtures/research/valid_packet_30.json`
- Create: `tests/fixtures/research/invalid_duplicate_packet.json`
- Test: `tests/unit/domain/test_research_admission.py`
- Test: `tests/unit/domain/test_qualification.py`
- Test: `tests/unit/domain/test_product_strategy.py`
- Test: `tests/unit/domain/test_dedupe.py`
- Test: `tests/integration/orchestration/test_research_to_spec_handlers.py`

**Interfaces:**
- `ResearchService.import_packet(path: Path, *, now: datetime) -> ResearchPacket`
- `QualificationService.score(packet: ResearchPacket) -> tuple[QualificationScore, ...]`
- `QualificationService.shortlist(packet: ResearchPacket, scores: Sequence[QualificationScore]) -> CandidateShortlist`
- `ProductStrategyService.create_spec(packet: ResearchPacket, shortlist: CandidateShortlist, selected: QualificationScore, rules: ProductRules) -> ProductSpec`
- `DedupeService.evaluate(spec: ProductSpec, catalogue: Sequence[ProductSpec]) -> DedupeResult`

No method may perform marketplace mutation, purchase, browser login, or spend.
- [ ] **Step 1: Write failing research-admission tests**

Cover valid 25-, 30-, and 40-row packets; reject 24/41 rows, duplicate observation IDs, duplicate evidence hashes with conflicting payloads, stale/unknown/future evidence, malformed currency, qualification inputs outside `0..10`, and a supplied packet hash that differs from canonical recomputation.

- [ ] **Step 2: Verify admission tests RED**

Run: `uv run pytest -q tests/unit/domain/test_research_admission.py`

- [ ] **Step 3: Implement packet import and canonical identity**

Compute `packet_sha256` over the canonical packet body excluding the hash field. Derive `packet_id = "RPK-" + packet_sha256[:24]`. Reject caller identities that do not match recomputation.

- [ ] **Step 4: Write failing qualification tests**

Group observations by normalized `(identity_niche, base_category)`. For each of the four dimensions, assert the score is the `ROUND_HALF_UP` integer median of the admitted `0..10` inputs. Derive `candidate_id` from the normalized pair. Assert deterministic ordering by total descending, evidence count descending, build-feasibility descending, then candidate ID ascending.

- [ ] **Step 5: Implement qualification and shortlist**

Persist all scores. When at least five concepts exist, return exactly the top five. Select the first candidate with total `>=30`; if none qualifies, return the terminal `INSUFFICIENT_EVIDENCE` decision without creating a ProductSpec.

- [ ] **Step 6: Write failing ProductSpec tests**

Assert a qualifying candidate produces one deterministic specification with six-to-eight configured hubs, three-to-four configured colour variants, source evidence IDs, non-empty target buyer/outcome/features/facts, and a recomputable `spec_sha256`. Assert unqualified or non-shortlisted candidates are denied.

- [ ] **Step 7: Implement deterministic ProductStrategy service**

Use the candidate's admitted evidence and configured templates. Do not invent marketplace metrics or product claims. Every product fact must be either a configured structural fact or supported by an evidence ID.
- [ ] **Step 8: Write failing dedupe tests**

Reject an exact normalized identity-niche/base-category match. Reject title-token overlap `>=0.70`, where overlap is `|A ∩ B| / min(|A|, |B|)` after Unicode case-folding, punctuation removal, whitespace normalization, and configured stop-word removal. Accept lower overlap and emit the compared catalogue identities.

- [ ] **Step 9: Implement dedupe and workflow handlers**

Implement `SCORE_AND_SHORTLIST`, `CREATE_PRODUCT_SPEC`, and `RUN_DEDUPE` handlers. Each handler loads its exact predecessor result from PostgreSQL, writes no files, and returns a typed result plus the next declared event.

- [ ] **Step 10: Run research lane gates**

```bash
uv run pytest -q tests/unit/domain/test_research_admission.py tests/unit/domain/test_qualification.py tests/unit/domain/test_product_strategy.py tests/unit/domain/test_dedupe.py
MONEY_MACHINE_TEST_DATABASE_URL="$(scripts/prepare_test_database.sh research-handlers)" uv run pytest -q tests/integration/orchestration/test_research_to_spec_handlers.py
uv run ruff check src/money_machine/application/services/research_service.py src/money_machine/domain/services src/money_machine/agents/implementations src/money_machine/agents/contracts tests/unit/domain tests/integration/orchestration/test_research_to_spec_handlers.py
uv run pyright src/money_machine/application/services/research_service.py src/money_machine/domain/services src/money_machine/agents/implementations src/money_machine/agents/contracts tests/unit/domain tests/integration/orchestration/test_research_to_spec_handlers.py
```

- [ ] **Step 11: Commit**

```bash
git add src/money_machine/application/services/research_service.py src/money_machine/domain/services src/money_machine/agents/implementations/market_research.py src/money_machine/agents/implementations/product_strategy.py src/money_machine/agents/implementations/catalogue_dedupe.py src/money_machine/agents/contracts tests/fixtures/research tests/unit/domain tests/integration/orchestration/test_research_to_spec_handlers.py
git commit -m "feat(research): produce dedupe-approved product specs"
```

---
### Task 6: Build the deterministic local product and product QA

**Files:**
- Modify: `src/money_machine/integrations/storage/interface.py`
- Modify: `src/money_machine/integrations/storage/local.py`
- Modify: `src/money_machine/integrations/notion/interface.py`
- Modify: `src/money_machine/integrations/notion/fixture_adapter.py`
- Modify: `src/money_machine/application/services/product_service.py`
- Modify: `src/money_machine/agents/contracts/notion_builder.py`
- Modify: `src/money_machine/agents/contracts/product_qa.py`
- Modify: `src/money_machine/agents/implementations/notion_product_builder.py`
- Modify: `src/money_machine/agents/implementations/product_qa.py`
- Create: `templates/product/home.html.j2`
- Create: `templates/product/hub.html.j2`
- Create: `templates/product/readme.md.j2`
- Create: `templates/product/theme.css.j2`
- Test: `tests/unit/assets/test_local_artifact_store.py`
- Test: `tests/unit/agents/test_product_builder.py`
- Test: `tests/unit/agents/test_product_qa.py`
- Test: `tests/integration/notion/test_local_product_bundle.py`
- Test: `tests/integration/orchestration/test_build_and_qa_handlers.py`

**Interfaces:**
- `LocalArtifactStore(root: Path).put_bytes(relative_path, data, media_type) -> ArtifactReference`
- `LocalNotionAdapter.build(spec: ProductSpec, destination: Path) -> BuildResult`
- `ProductQAService.evaluate(build: BuildResult) -> ProductQAResult`
- Handler outputs remain exact frozen Task 2 models.

The local adapter is the only integrated product-write adapter. Live Notion adapters continue to deny writes.
- [ ] **Step 1: Write failing artifact-store tests**

Assert canonical POSIX-relative paths, path-traversal and symlink rejection, atomic writes, SHA-256 verification, immutable collision behavior, deterministic artifact IDs, and no files outside the configured root.

- [ ] **Step 2: Verify artifact tests RED**

Run: `uv run pytest -q tests/unit/assets/test_local_artifact_store.py`

- [ ] **Step 3: Implement the local artifact store**

Write to a sibling temporary file, fsync, atomically replace, and return `ArtifactReference`. An existing identical artifact is an idempotent success; the same path with different bytes is a collision error.

- [ ] **Step 4: Write failing builder tests**

Given a ProductSpec, require `product.json`, `README.md`, `home.html`, one HTML file per hub, one theme CSS file per colour variant, and `manifest.json`. Assert six-to-eight hubs, three-to-four variants, stable navigation, progress UI, no placeholder tokens, and byte-identical output on replay.

- [ ] **Step 5: Implement the deterministic builder**

Render Jinja templates with `StrictUndefined`, sorted inputs, UTF-8 newlines, stable slugging, and a fixed renderer version. The manifest lists path, media type, byte count, and SHA-256 for every semantic artifact except itself, then records its own canonical manifest hash in `BuildResult`.

- [ ] **Step 6: Write failing QA tests**

Create corrupt bundles for missing hubs, broken internal links, duplicate slugs, placeholder text, absent facts, variant drift, modified artifacts, absolute filesystem paths, and unexpected network URLs. Assert exact failure codes.

- [ ] **Step 7: Implement product QA**

Use standard-library HTML parsing and manifest rehashing. QA may read only the build root. It returns all findings deterministically and sets `passed=true` only when none are blocking.
- [ ] **Step 8: Implement build and QA job handlers**

`BUILD_LOCAL_PRODUCT` loads the exact dedupe-approved ProductSpec and writes to `runtime/artifacts/<workflow-run-id>/product/`. `RUN_PRODUCT_QA` loads the stored BuildResult and emits no successor unless QA passes.

- [ ] **Step 9: Run build lane gates**

```bash
uv run pytest -q tests/unit/assets/test_local_artifact_store.py tests/unit/agents/test_product_builder.py tests/unit/agents/test_product_qa.py tests/integration/notion/test_local_product_bundle.py
MONEY_MACHINE_TEST_DATABASE_URL="$(scripts/prepare_test_database.sh build-handlers)" uv run pytest -q tests/integration/orchestration/test_build_and_qa_handlers.py
uv run ruff check src/money_machine/integrations/storage src/money_machine/integrations/notion src/money_machine/application/services/product_service.py src/money_machine/agents templates tests/unit/assets tests/unit/agents tests/integration/notion tests/integration/orchestration/test_build_and_qa_handlers.py
uv run pyright src/money_machine/integrations/storage src/money_machine/integrations/notion src/money_machine/application/services/product_service.py src/money_machine/agents tests/unit/assets tests/unit/agents tests/integration/notion tests/integration/orchestration/test_build_and_qa_handlers.py
```

- [ ] **Step 10: Commit**

```bash
git add src/money_machine/integrations/storage src/money_machine/integrations/notion src/money_machine/application/services/product_service.py src/money_machine/agents/contracts/notion_builder.py src/money_machine/agents/contracts/product_qa.py src/money_machine/agents/implementations/notion_product_builder.py src/money_machine/agents/implementations/product_qa.py templates/product tests/unit/assets tests/unit/agents tests/integration/notion tests/integration/orchestration/test_build_and_qa_handlers.py
git commit -m "feat(product): build and verify local product bundles"
```

---

### Task 7: Generate merchandising, deterministic assets, and preflight

**Files:**
- Modify: `src/money_machine/domain/services/claim_validation.py`
- Modify: `src/money_machine/application/services/listing_service.py`
- Modify: `src/money_machine/assets/design_tokens.py`
- Modify: `src/money_machine/assets/renderer.py`
- Modify: `src/money_machine/assets/screenshots.py`
- Modify: `src/money_machine/assets/pdf.py`
- Modify: `src/money_machine/assets/video.py`
- Modify: `src/money_machine/agents/contracts/merchandising.py`
- Modify: `src/money_machine/agents/contracts/creative_assets.py`
- Modify: `src/money_machine/agents/contracts/preflight.py`
- Modify: `src/money_machine/agents/implementations/merchandising.py`
- Modify: `src/money_machine/agents/implementations/creative_assets.py`
- Modify: `src/money_machine/agents/implementations/preflight.py`
- Create: `templates/listing/description.md.j2`
- Create: `templates/assets/listing_image.svg.j2`
- Test: `tests/unit/domain/test_claim_validation.py`
- Test: `tests/unit/agents/test_merchandising.py`
- Test: `tests/unit/assets/test_listing_assets.py`
- Test: `tests/unit/agents/test_preflight.py`
- Test: `tests/integration/orchestration/test_listing_and_preflight_handlers.py`

**Interfaces:**
- `ListingService.create(spec: ProductSpec, build: BuildResult, qa: ProductQAResult) -> ListingPackage`
- `CreativeAssetService.render(package: ListingPackage, destination: Path) -> ListingPackage`
- `PreflightService.evaluate(package: ListingPackage, qa: ProductQAResult) -> PreflightResult`

**Deterministic listing constraints:**

```text
Title: 1–140 characters
Tags: exactly 13 unique normalized tags, each 1–20 characters
Images: exactly 10 PNG files, 2000×2000 pixels
Delivery document: exactly one PDF
Preview video: generated artifact or explicit NOT_GENERATED receipt
Claims: every factual claim bound to ProductSpec.product_facts
External mutations: zero
Spend: 0.00
```

- [ ] **Step 1: Write failing claim-validation tests**

Accept structural wording and exact supported product facts. Reject unbound superlatives, sales/demand claims, quantified outcomes absent from ProductSpec, unsupported compatibility claims, and copied marketplace evidence presented as a product fact.
- [ ] **Step 2: Implement the product-fact claim ledger**

Normalize candidate claims without changing meaning. Each accepted claim records the exact fact index or `STRUCTURAL_COPY`; rejected claims record one stable reason code.

- [ ] **Step 3: Write failing merchandising tests**

Assert deterministic title and description, exactly thirteen valid unique tags, product-specific copy, fact-bound claim records, no placeholder text, no sales claims, and identical canonical hashes on replay.

- [ ] **Step 4: Implement merchandising**

Render the description from strict templates and admitted ProductSpec facts. Tag selection is deterministic from normalized identity niche, category, buyer, outcome, and configured synonyms; fail if thirteen compliant unique tags cannot be produced without filler.

- [ ] **Step 5: Write failing asset tests**

Assert ten 2000×2000 PNGs, stable pixel hashes, accessible text contrast according to configured thresholds, no remote fonts or network fetches, one deterministic PDF, complete lineage, and explicit video status.

- [ ] **Step 6: Implement deterministic assets**

Use Pillow with bundled/default fonts and fixed design tokens. Render ten distinct semantic image roles. Generate the delivery PDF with fpdf2 using product instructions, local file inventory, and support information. Emit `NOT_GENERATED` for video until a deterministic local video renderer is implemented.

- [ ] **Step 7: Write failing preflight tests**

Reject failed QA, wrong tag/image counts, broken hashes, unsupported claims, missing PDF, unknown video status, non-local unapproved links, non-zero or unknown spend, external mutation receipts, and automation modes other than `simulation` or `draft`.

- [ ] **Step 8: Implement preflight and handlers**

`CREATE_LISTING_PACKAGE` persists copy and assets only after QA. `RUN_PREFLIGHT` reopens every artifact, rehashes it, validates lineage and policy, then emits `DRAFT_READY` only on a complete pass.

- [ ] **Step 9: Run merchandising gates**

```bash
uv run pytest -q tests/unit/domain/test_claim_validation.py tests/unit/agents/test_merchandising.py tests/unit/assets/test_listing_assets.py tests/unit/agents/test_preflight.py
MONEY_MACHINE_TEST_DATABASE_URL="$(scripts/prepare_test_database.sh listing-handlers)" uv run pytest -q tests/integration/orchestration/test_listing_and_preflight_handlers.py
uv run ruff check src/money_machine/domain/services/claim_validation.py src/money_machine/application/services/listing_service.py src/money_machine/assets src/money_machine/agents tests/unit/domain/test_claim_validation.py tests/unit/agents tests/unit/assets tests/integration/orchestration/test_listing_and_preflight_handlers.py
uv run pyright src/money_machine/domain/services/claim_validation.py src/money_machine/application/services/listing_service.py src/money_machine/assets src/money_machine/agents tests/unit/domain/test_claim_validation.py tests/unit/agents tests/unit/assets tests/integration/orchestration/test_listing_and_preflight_handlers.py
```
- [ ] **Step 10: Commit**

```bash
git add src/money_machine/domain/services/claim_validation.py src/money_machine/application/services/listing_service.py src/money_machine/assets src/money_machine/agents/contracts/merchandising.py src/money_machine/agents/contracts/creative_assets.py src/money_machine/agents/contracts/preflight.py src/money_machine/agents/implementations/merchandising.py src/money_machine/agents/implementations/creative_assets.py src/money_machine/agents/implementations/preflight.py templates/listing templates/assets tests/unit/domain/test_claim_validation.py tests/unit/agents tests/unit/assets tests/integration/orchestration/test_listing_and_preflight_handlers.py
git commit -m "feat(listing): create preflighted draft packages"
```

---

### Task 8: Integrate CLI, read-only API, worker registry, and complete E2E

**Files:**
- Modify: `src/money_machine/agents/registry.py`
- Modify: `src/money_machine/agents/runtime.py`
- Modify: `src/money_machine/application/services/research_service.py`
- Modify: `src/money_machine/cli/main.py`
- Modify: `src/money_machine/cli/commands/database.py`
- Modify: `src/money_machine/cli/commands/workflow.py`
- Modify: `src/money_machine/cli/commands/worker.py`
- Modify: `src/money_machine/api/main.py`
- Modify: `src/money_machine/api/dependencies.py`
- Modify: `src/money_machine/api/schemas.py`
- Modify: `src/money_machine/api/routers/workflows.py`
- Modify: `src/money_machine/api/routers/products.py`
- Modify: `src/money_machine/api/routers/listings.py`
- Modify: `src/money_machine/api/routers/jobs.py`
- Create: `scripts/run_first_product_slice.sh`
- Create: `scripts/run_first_product_slice.ps1`
- Test: `tests/contract/test_first_product_cli.py`
- Test: `tests/contract/test_first_product_api.py`
- Test: `tests/e2e/test_happy_path.py`
- Test: `tests/e2e/test_restart_recovery.py`
- Test: `tests/e2e/test_cull_path.py` only to assert it remains unavailable in this slice.
**Interfaces:**

```text
money-machine db migrate
money-machine research import --packet PATH
money-machine workflow start first-product --packet-id ID
money-machine worker run-once
money-machine worker drain --max-jobs 20
money-machine workflow status RUN_ID
money-machine artifacts inspect RUN_ID
```

Read-only API routes:

```text
GET /workflows/{run_id}
GET /workflows/{run_id}/jobs
GET /products/{product_spec_id}
GET /listings/{listing_package_id}
```

- [ ] **Step 1: Write failing CLI contract tests**

Assert command names, required arguments, JSON output mode, non-zero exits for invalid packets/IDs, no external-effect flag, and stable machine-readable response schemas.

- [ ] **Step 2: Implement dependency composition and CLI commands**

Build one application container from environment settings. Register only the eight first-slice handlers. CLI mutation commands are local operator commands and write immutable receipts; API routes remain read-only.

- [ ] **Step 3: Write failing API tests**

Assert `/health` remains liveness-only, new routes read persisted state, unknown IDs return 404, no POST/PUT/PATCH/DELETE business route exists, and response schemas redact local absolute paths outside explicit artifact-inspection output.

- [ ] **Step 4: Implement read-only API routers**

Use repository query methods and typed response schemas. Do not expose raw SQL, generic file reads, provider credentials, or mutation controls.
- [ ] **Step 5: Write the full E2E test before integration code**

The test upgrades a dedicated PostgreSQL database, imports `valid_packet_30.json`, starts the workflow, drains the worker, and asserts:

```text
30 observations persisted
5 candidates shortlisted
1 candidate total >= 30
1 ProductSpec
1 dedupe pass
1 BuildResult
1 ProductQAResult passed
1 ListingPackage with 13 tags, 10 images, PDF, and video status
1 PreflightResult passed
workflow state DRAFT_READY
external effects 0
spend 0.00
```

- [ ] **Step 6: Verify full E2E RED**

Run: `MONEY_MACHINE_TEST_DATABASE_URL="$(scripts/prepare_test_database.sh e2e-red)" uv run pytest -q tests/e2e/test_happy_path.py`

Expected: FAIL until all handlers and composition are integrated.

- [ ] **Step 7: Integrate and make E2E GREEN**

Wire the handler registry and repositories without duplicating domain logic in CLI, API, or worker modules. Process jobs until idle. Preserve the exact result and event identity from each lane.

- [ ] **Step 8: Add restart and replay E2E**

Stop after each workflow stage in separate parameterized cases, create a fresh engine/worker instance, resume, and require the same final hashes. Start the same packet twice and assert the second invocation resolves to the existing workflow or an explicit replay receipt without duplicate products or artifacts.

- [ ] **Step 9: Assert deferred paths remain unavailable**

`tests/e2e/test_cull_path.py` must assert the cull/multiply workflow is explicitly `NOT_IMPLEMENTED_FOR_SLICE`, not silently successful. The same applies to publication and customer-support commands.

- [ ] **Step 10: Run integration gates**

```bash
uv run pytest -q tests/contract/test_first_product_cli.py tests/contract/test_first_product_api.py
MONEY_MACHINE_TEST_DATABASE_URL="$(scripts/prepare_test_database.sh e2e-suite)" uv run pytest -q tests/e2e/test_happy_path.py tests/e2e/test_restart_recovery.py tests/e2e/test_cull_path.py
uv run ruff check src/money_machine/agents src/money_machine/cli src/money_machine/api scripts tests/contract tests/e2e
uv run pyright src/money_machine/agents src/money_machine/cli src/money_machine/api tests/contract tests/e2e
```
- [ ] **Step 11: Commit**

```bash
git add src/money_machine/agents/registry.py src/money_machine/agents/runtime.py src/money_machine/cli src/money_machine/api scripts/run_first_product_slice.sh scripts/run_first_product_slice.ps1 tests/contract/test_first_product_cli.py tests/contract/test_first_product_api.py tests/e2e
git commit -m "feat(slice): integrate first product workflow"
```

---

### Task 9: Execute a real admitted packet and inspect the product bundle

**Files:**
- Runtime input: `private/research/first-product-packet.json` — ignored, never committed unless the evidence is explicitly licensed and sanitized.
- Runtime output: `runtime/artifacts/<run-id>/` — ignored.
- Create tracked safe manifest: `docs/evidence/first-product-slice/manifest.json`
- Create tracked report: `docs/evidence/first-product-slice/REPORT.md`
- Test: `tests/e2e/test_runtime_manifest_contract.py`

**Interfaces:**
- The packet must satisfy the same Task 2 contract and Task 5 admission rules.
- The tracked manifest contains no copied listing text, customer data, tokens, or absolute private paths.

- [ ] **Step 1: Create the real read-only research packet**

Collect 25–40 current observations through an approved read-only connector or a compliant manual export. Record URLs, timestamps, raw proxies, normalized qualification inputs, and content hashes. Do not purchase competitor products or bypass marketplace controls.

- [ ] **Step 2: Validate packet admission without starting a workflow**

Run:

```bash
money-machine research import --packet private/research/first-product-packet.json --validate-only --json
```

Require a canonical packet ID and zero rejected observations.

- [ ] **Step 3: Run the first product workflow**

Use the bounded script with a dedicated runtime output root. Drain no more than twenty jobs and assert the worker becomes idle after the eight declared jobs.
- [ ] **Step 4: Inspect the output manually and structurally**

Open `home.html`, every hub, all ten images, the delivery PDF, listing copy, and preflight receipt. Confirm the product is coherent, usable, product-specific, free of placeholders, and not merely a test fixture relabelled as a product.

- [ ] **Step 5: Replay the exact packet**

Run the same command again. Require no duplicate workflow, job, product, listing, or artifact identity and byte-identical semantic artifacts.

- [ ] **Step 6: Write and test the safe evidence manifest**

The tracked manifest records run ID, packet hash, product-spec hash, build hash, QA hash, listing hash, preflight hash, artifact counts, state, spend, external-effect count, source mode, and repository commit. It must contain repository-relative safe paths only.

- [ ] **Step 7: Run the manifest contract test**

Run: `uv run pytest -q tests/e2e/test_runtime_manifest_contract.py`

- [ ] **Step 8: Commit only safe evidence**

```bash
git add docs/evidence/first-product-slice tests/e2e/test_runtime_manifest_contract.py
git commit -m "evidence(slice): record first draft-ready product"
```

Do not commit the private packet, runtime bundle, provider payloads, screenshots containing private data, or local database.

---

### Task 10: Final review, verification, and control reconciliation

**Files:**
- Modify: `docs/control/DECISIONS.md`
- Modify: `docs/control/IMPLEMENTATION_LOG.md`
- Modify: `docs/control/IMPLEMENTATION_STATE.json`
- Modify: `docs/control/NEXT_SESSION.md`
- Modify: `docs/control/TEST_EVIDENCE.md`
- Create: `docs/evidence/first-product-slice/FINAL_REVIEW.md`

**Interfaces:**
- Control state records a completed accelerated vertical slice, not completion of Sessions 01–15.
- All result claims bind exact Git commits and artifact hashes.
- [ ] **Step 1: Dispatch independent reviews**

Run separate architecture/spec, code-quality, security/provenance, and test-quality reviews against the exact integrated candidate. Reviewers receive the design, plan, commit range, test evidence, and safe runtime manifest.

- [ ] **Step 2: Resolve all critical and important findings**

Use bounded TDD fix rounds. Re-review only the changed scope after each fix. Minor findings must be either fixed or explicitly adjudicated in `FINAL_REVIEW.md`.

- [ ] **Step 3: Run one final complete verification gate**

```bash
uv sync --frozen --all-groups
uv run ruff format --check .
uv run ruff check .
uv run pyright
MONEY_MACHINE_TEST_DATABASE_URL="$(scripts/prepare_test_database.sh final-suite)" uv run pytest -q
pnpm install --frozen-lockfile
pnpm lint
pnpm typecheck
pnpm test
pnpm build
docker compose config --quiet
docker compose up -d postgres api web
scripts/verify_postgres.sh
curl --fail http://127.0.0.1:8000/health
git diff --check
```

Then run the first-product script once against a clean dedicated database and require `DRAFT_READY`.

- [ ] **Step 4: Verify safety and repository boundaries**

Confirm immutable source hashes, zero forbidden tracked files, no secrets, no private packet/runtime artifacts, no external effects, zero spend, clean worktree, and local/remote commit equality after push.

- [ ] **Step 5: Reconcile control state truthfully**

Record the accelerated slice as a separately named verified milestone. Keep `commissioned_agents=[]`. Do not mark Session 09 publication, Session 10 analytics, or Session 15 commissioning complete. Set the next action to live Notion/Etsy draft capability design only after Omar inspects the bundle.

- [ ] **Step 6: Commit control and review evidence**

```bash
git add docs/control docs/evidence/first-product-slice/FINAL_REVIEW.md
git commit -m "chore(control): close first product vertical slice"
```
- [ ] **Step 7: Push and clean team worktrees**

Push the reviewed branch, verify remote SHA equality, remove completed linked worktrees, prune worktree metadata, and leave no active team process attached to deleted branches.

---

## Parallel execution DAG

```text
Task 1 hardening ───────────────┐
Task 2 contract freeze ─────────┴─> integration checkpoint
                                      |
                 ┌────────────────────┼────────────────────┐
                 v                    v                    v
        Task 3 persistence   Task 5 research       Task 6 product build
                 |                    |                    |
                 └──────────────┬─────┴──────────────┬─────┘
                                v                    v
                        Task 4 orchestration   Task 7 merchandising
                                └──────────┬─────────┘
                                           v
                                  Task 8 integration
                                           v
                                  Task 9 real execution
                                           v
                                  Task 10 final review
```

Task 4 may develop against Task 3's declared interfaces while Task 3 is in review, but it cannot merge until Task 3 is approved. Task 7 consumes the frozen Task 2 contracts and may develop with a contract-valid BuildResult fixture; it cannot merge until Task 6 is approved.

## Swarm operating rules

- Invoke `$task-router` for every lane and persist its routing receipt.
- Use one worktree and branch per lane.
- Use high-throughput team execution only for non-overlapping owned paths.
- One integration owner alone changes shared dependency, migration-order, orchestration-composition, and control files.
- Every lane returns commit SHA, RED evidence, GREEN evidence, static-gate evidence, changed paths, and concerns.
- Every lane receives independent spec and code-quality review before integration.
- Integration owner cherry-picks reviewed commits in DAG order; workers never merge themselves.
- No lane may substitute mocks for the final PostgreSQL/filesystem integration proof.
- No lane may run provider writes or enable external effects.

## Completion signal

```text
FIRST_PRODUCT_VERTICAL_SLICE_COMPLETE
```

This signal is valid only with a real `DRAFT_READY` runtime manifest, exact artifact hashes, zero external effects, zero spend, final review approval, and a clean pushed commit.