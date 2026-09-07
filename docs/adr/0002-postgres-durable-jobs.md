# 0002 PostgreSQL Durable Jobs

**Status:** Accepted

## Context

Every completed step must persist output and unlock or create successor work. The system must survive process crashes, avoid duplicate effects, enforce dependencies, recover expired work, and remain understandable without a separate queue product.

## Decision

Use PostgreSQL as the canonical durable queue and event store. A job records its workflow/object identity, owner agent, status, input, required artifacts, schedule, attempts, retry class, idempotency key, side-effect class, success contract, lease owner, lease expiry, and timestamps.

Workers claim eligible `READY` jobs in short transactions using `FOR UPDATE SKIP LOCKED`. A claim moves the job to `RUNNING`, increments its attempt, and assigns a bounded lease. Workers heartbeat leases. Expired leases return only safely retryable work to eligibility; uncertain external effects move to `UNCERTAIN_EXTERNAL_EFFECT` until adapter reconciliation persists a result.

Dependencies are rows, not in-memory promises. A job becomes `READY` only when all required predecessors have terminal success and required artifacts exist. Completing a job atomically persists its result, artifact/evidence links, emitted domain events, dependency releases, and deterministic successor jobs. Unique idempotency keys prevent duplicate jobs and effects.

The scheduler inserts due jobs and triggers with the same transaction and uniqueness rules. Events use an outbox-compatible persisted state so dispatch can resume after restart.

## Rationale

The architecture already requires PostgreSQL. Row locking, constraints, transactions, JSONB, and timestamps provide sufficient initial queue semantics while keeping operational state queryable in one place.

## Consequences

- Queue throughput is bounded by database capacity and claim-query quality.
- Indexes on status, schedule, dependency readiness, and lease expiry are mandatory.
- Long provider work occurs outside database transactions; leases and reconciliation bridge that boundary.
- Event consumers must be idempotent.
- Database backup and restore also protect orchestration state.

## Rejected alternatives

- **In-memory or filesystem queue:** cannot provide restart safety or multi-worker correctness.
- **Redis queue:** adds a second source of truth and cross-store consistency.
- **Kafka:** unnecessary operational complexity for the initial single-stack deployment.
- **Temporal:** useful capabilities, but violates the approved lean architecture and duplicates domain state.
- **Polling without leases:** permits concurrent processing and ambiguous crash recovery.

## Revisit when

Revisit when measured claim contention, event volume, retention, or cross-region requirements exceed PostgreSQL's demonstrated capacity. Any replacement must preserve transactional successor creation, idempotency, lease recovery, and complete lineage.