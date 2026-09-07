# 0001 Modular Monolith

**Status:** Accepted

## Context

The product has sixteen logical agents and several provider boundaries, but it is operated as a single founder-run system. Independent deployment, data ownership, and scaling needs have not been demonstrated. Splitting agents into services would add network failure modes and distributed transactions before the durable workflow exists.

## Decision

Build one Python modular monolith under `src/money_machine/`, one Next.js operator application, and one PostgreSQL database. Run five Compose services:

- `api`: FastAPI control and operator API;
- `worker`: durable job claimer and agent runner;
- `scheduler`: due-job, weekly, monthly, and maturity scheduling;
- `web`: operator console;
- `postgres`: canonical workflow and business state.

Agents are versioned capabilities registered in the worker, not processes, repositories, or independently deployed services. Python package boundaries separate `domain`, `agents`, `orchestration`, `persistence`, `integrations`, `assets`, `config`, and `api`. Dependencies point inward: domain contracts do not import provider adapters or persistence implementations. External systems are reached only through integration interfaces.

The `money-machine-control` utility remains a separate repository-continuity tool. Its implementation-state machine is not product orchestration.

## Rationale

A modular monolith keeps state transitions, successor creation, event emission, and artifact lineage transactional and inspectable. One deployable stack matches local WSL2 and single-server production operation. Logical boundaries preserve a later extraction path without paying the operational cost now.

## Consequences

- PostgreSQL transactions can atomically complete jobs, emit events, and create successors.
- Worker capacity scales by adding identical worker processes against the same queue.
- Module APIs and ownership must be enforced in code review because process boundaries do not enforce them.
- A defect can affect the shared worker process; leases and restart recovery remain mandatory.
- The web application never becomes workflow authority.

## Rejected alternatives

- **One service or repository per agent:** excessive deployment and coordination overhead with no independent scaling need.
- **Kubernetes:** unnecessary for a five-service founder-run stack.
- **Temporal, Kafka, or Redis queue:** duplicates the required PostgreSQL durability and complicates recovery.
- **Custom SaaS replacing Notion or another marketplace replacing Etsy:** contradicts the accepted business process.

## Revisit when

Revisit only when measured load, security isolation, release independence, or provider-rate constraints require a module to scale or deploy separately. Extraction requires a documented ownership boundary, an idempotent protocol, and evidence that PostgreSQL transactions can be replaced safely.