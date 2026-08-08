# SESSION 03 — DURABLE ORCHESTRATOR, SCHEDULER AND FAILURE RECOVERY

Execute under the Master Control Prompt and recovery protocol.

## Objective

Build the control plane that replaces manual handoffs: durable jobs, dependencies, event-driven successors, timers, leases, retries, idempotency and restart recovery.

## Actions

### 1. Implement job lifecycle

Support:

```text
PENDING
BLOCKED
READY
LEASED
RUNNING
SUCCEEDED
FAILED_RETRYABLE
FAILED_TERMINAL
BLOCKED_EXTERNAL
UNCERTAIN_EXTERNAL_EFFECT
CANCELLED
```

Implement transactional state transitions and reject invalid changes.

### 2. Implement dependency resolution

A job becomes `READY` only when:

- every required dependency has succeeded;
- `scheduled_at <= now`;
- the workflow is active;
- the object is in the expected lifecycle state;
- no dedupe/idempotency collision exists.

Dependency failure must propagate according to the workflow contract rather than silently leaving dead jobs.

### 3. Implement leasing and workers

Use PostgreSQL row locking and leases:

- `FOR UPDATE SKIP LOCKED`;
- worker ID;
- lease start and expiry;
- heartbeat;
- graceful completion;
- lease reaper;
- crash recovery;
- bounded concurrency;
- no double execution.

### 4. Implement retries

Classify failures:

```text
RETRYABLE_TRANSIENT
AUTH_REQUIRED
REPAIR_REQUIRED
NON_RETRYABLE
UNCERTAIN_EXTERNAL_EFFECT
```

Requirements:

- exponential or configured backoff;
- max attempts;
- no blind retry of uncertain external effects;
- exact error and provider correlation stored;
- final failure emits a workflow event.

### 5. Implement idempotency

Support:

- stable job idempotency keys;
- external-operation keys;
- duplicate event suppression;
- successor-job uniqueness;
- reconciliation before retry after timeouts.

### 6. Implement scheduler

The scheduler must:

- promote due jobs;
- create weekly-loop jobs;
- create monthly deep-pass jobs;
- create thirty-day maturity jobs from listing publication time;
- enforce publication ramp;
- detect stalled jobs;
- emit `JOB_STALLED`;
- recover expired leases.

No schedule may rely on process memory.

### 7. Implement workflow templates

Create executable workflow definitions for:

```text
product_experiment
competitor_teardown
publish_listing
weekly_review
monthly_deep_pass
incident_repair
```

The product experiment template must create successor jobs for every normal path.

### 8. Implement event dispatcher and successor factory

Successor creation must occur transactionally with the completed job result.

Examples:

```text
RESEARCH_COMPLETED → ANALYZE_RESEARCH
PRODUCT_QUALIFIED → RUN_TEARDOWN or CREATE_PRODUCT_SPEC
PRODUCT_SPEC_CREATED → CHECK_DEDUPE
DEDUPE_PASSED → BUILD_NOTION_TEMPLATE
BUILD_COMPLETED → RUN_PRODUCT_QA
PRODUCT_QA_PASSED → CREATE_VARIANTS
VARIANTS_COMPLETED → GENERATE_LISTING_PACKAGE
ASSETS_COMPLETED → CREATE_ETSY_DRAFT
DRAFT_CREATED → RUN_PREFLIGHT
PREFLIGHT_PASSED → PUBLISH_ETSY_LISTING
LISTING_PUBLISHED → POST_PUBLISH_VERIFY + SCHEDULE_WEEKLY_METRICS + SCHEDULE_MATURITY
LISTING_MATURED → EVALUATE_LISTING
WINNER_DETECTED → CREATE_SUCCESSOR_SPEC
LISTING_CULLED → DEACTIVATE_LISTING
BROKEN_LINK_DETECTED → OPEN_INCIDENT + REPAIR_BROKEN_LINK
```

### 9. Provide operator commands

CLI/API support:

- start workflow;
- inspect workflow graph;
- inspect job;
- retry an eligible job;
- cancel reversible work;
- reconcile uncertain external effect;
- run scheduler once;
- run worker once;
- list stalled work.

### 10. Tests

Use deterministic fake handlers to prove:

- complete happy-path job chaining;
- dependency blocking/release;
- duplicate successor suppression;
- job lease exclusivity;
- worker crash and lease recovery;
- retry backoff;
- terminal failure;
- uncertain-effect pause and reconciliation;
- weekly schedule;
- monthly schedule;
- publication ramp;
- 30-day timer;
- workflow cancellation;
- restart from persisted state.

### 11. Review and checkpoint

Use orchestration and concurrency reviewers. Fix race conditions and state holes.

Commit:

```text
feat(orchestration): add durable linked workflow engine
```

## Exit criteria

- Job linkage is functional without agents.
- Worker and scheduler survive restart.
- Successor creation is transactional and idempotent.
- Timers are durable.
- Failure paths are explicit.
- Tests cover concurrency and recovery.
- Control files and commit are current.

## Required exit code

```text
SESSION_03_DURABLE_ORCHESTRATOR_COMPLETE
```

Next prompt:

```text
07_SESSION_04_AGENT_RUNTIME_AND_ROSTER.md
```
