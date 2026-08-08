# Accelerated First Product Vertical Slice — Design

**Status:** Approved for implementation by Omar on 9 August 2026.

**Repository:** `D:\Money Machine` (`/mnt/d/Money Machine`)

**Baseline branch:** `build/full-automation`

**Baseline commit:** `7e62654b2d6f2d49d1ca02961daa127c27ca57ae`

## 1. Objective

Build the smallest durable Money Machine slice that converts admitted market-research evidence into one locally inspectable, commercially credible product package without any live provider mutation.

The slice must execute this state path:

```text
RESEARCHED
→ QUALIFIED
→ SPECIFIED
→ DEDUPE_PASSED
→ BUILT
→ QA_PASSED
→ MERCHANDISED
→ PREFLIGHT_PASSED
→ DRAFT_READY
```

The deliverable is one complete product bundle, listing package, preflight receipt, and replayable workflow evidence.
## 2. Non-goals

This slice does not:

- publish to Etsy;
- purchase a competitor product;
- spend money;
- write to Notion;
- message customers;
- commission any agent for live effects;
- implement the complete sixteen-agent runtime;
- implement analytics, cull/multiply, support, or the final operator console;
- claim demand validation, sales, profitability, or revenue.

All external-effect adapters remain in `simulation` or `draft` mode.

## 3. Delivery strategy

Use a vertical-slice modular monolith. Logical agent roles remain explicit in contracts and receipts, but the first slice runs as typed durable workflow steps rather than sixteen independently deployed services.

One integration owner controls shared contracts, migrations, orchestration, dependency files, control state, and final merges. Parallel implementation lanes use isolated Git worktrees and non-overlapping owned paths.

Every behavior change follows strict red-green-refactor TDD. Production code is forbidden until the relevant failing test has been observed and recorded.
## 4. Runtime architecture

The first slice uses the existing services:

```text
CLI / API
   |
Workflow application service
   |
PostgreSQL durable job + event + artifact state
   |
Worker executes deterministic steps
   |
Local artifact store and provider-neutral adapters
```

The scheduler is required only to enqueue an explicitly configured research-to-draft workflow. It does not run recurring publication, analytics, or customer workflows in this slice.

The worker must lease one job at a time, persist attempts, emit typed events, retry only classified transient failures, and fail closed on uncertain external effects.

## 5. Canonical data flow

1. Import an admitted `ResearchPacket` containing 25–40 observations with provenance.
2. Score candidate concepts against the four playbook qualification dimensions.
3. Persist the top five candidates and select one candidate scoring at least 30/40.
4. Produce a typed `ProductSpec` and a deterministic dedupe decision.
5. Build a local Notion-compatible product bundle from the approved specification.
6. Run structural, content, link, artifact, and truth-only QA.
7. Generate truthful listing copy and deterministic creative assets.
8. Run fail-closed preflight and emit a draft-ready package.
## 6. Required contracts

The initial contract set is limited to the slice:

- `ResearchObservation`
- `ResearchPacket`
- `QualificationScore`
- `CandidateShortlist`
- `ProductSpec`
- `DedupeResult`
- `BuildResult`
- `ProductQAResult`
- `ListingPackage`
- `PreflightResult`
- `ArtifactReference`
- `EvidenceReference`
- `JobEnvelope`
- `JobAttempt`
- `DomainEvent`
- `WorkflowRun`

Contracts for analytics, mature portfolio decisions, customer incidents, publication reconciliation, and live account integration remain deferred until their workflows are implemented.

Every contract is strict, frozen where practical, schema-versioned, and serializable to canonical JSON. Hashes use deterministic UTF-8 JSON with sorted keys and no non-semantic whitespace.

## 7. Durable state

PostgreSQL stores workflow runs, jobs, dependencies, attempts, events, artifacts, evidence references, research packets, candidates, specifications, dedupe decisions, build results, QA results, listing packages, and preflight results.
The schema must enforce:

- unique workflow and job identities;
- explicit parent/child dependencies;
- append-only attempts and domain events;
- one active lease per job;
- idempotency keys for every step;
- immutable artifact and evidence hashes;
- terminal-state consistency;
- transactional state transition plus successor creation.

No business table may be simulated by an in-memory dictionary in the integrated runtime.

## 8. Workflow behavior

The worker claims only jobs whose dependencies are satisfied. A successful job transaction persists its result, event, state transition, and successor job atomically.

Retry classes are:

```text
NEVER
TRANSIENT_INTERNAL
TRANSIENT_PROVIDER_READ
RECONCILE_EXTERNAL_EFFECT
OPERATOR_REQUIRED
```

The first slice uses only `NEVER`, `TRANSIENT_INTERNAL`, and `TRANSIENT_PROVIDER_READ`. No external mutation is permitted, so `RECONCILE_EXTERNAL_EFFECT` remains contract-only.

Workflow replay must produce the same business identities and artifact hashes without duplicating jobs or artifacts.
## 9. Research admission

The first integrated source is a provider-neutral JSON research packet. It may be populated from a compliant manual export, approved connector, or read-only adapter, but its admission contract is identical.

Each observation contains:

- marketplace and source URL;
- observed timestamp;
- title and category;
- price and currency when available;
- demand proxy fields;
- competition proxy fields;
- listing-quality observations;
- evidence hash;
- source mode and freshness status.

The importer rejects missing provenance, duplicate observation identities, future timestamps, stale evidence outside configured policy, malformed money values, and packets outside the 25–40-row target.

## 10. Qualification and selection

The four playbook dimensions are configuration-backed and scored from 0 to 10. A candidate below 30/40 cannot enter product specification.

The workflow persists exactly five shortlisted candidates when at least five qualifying concepts exist. It selects the highest-scoring candidate deterministically using total score, evidence strength, lower operational complexity, and canonical candidate ID as ordered tie-breakers.

A low-supply packet completes as `INSUFFICIENT_EVIDENCE`; it does not invent filler candidates.
## 11. Product build

The first product is generated locally as a Notion-compatible bundle rather than written to a live Notion workspace.

The bundle contains:

```text
product.json
README.md
home.html
hubs/<slug>.html
assets/
manifest.json
```

It must implement six to eight hubs, three or four colour variants, deterministic navigation, progress indicators, and the product-specific content defined by `ProductSpec`.

The builder is deterministic: identical specification and renderer version produce identical semantic files and manifest hashes.

## 12. Product QA

QA verifies:

- required files and hubs;
- valid navigation and internal links;
- no placeholder text;
- no unsupported claims;
- required content sections;
- accessible headings and link labels;
- variant consistency;
- deterministic manifest identity;
- no external mutation or network write.

A failed QA result blocks merchandising.
## 13. Merchandising and assets

The listing package contains:

- one truthful title;
- a structured description;
- exactly thirteen tags;
- feature and buyer-fit statements bound to product facts;
- ten deterministic listing images;
- one short preview video or an explicit `NOT_GENERATED` receipt if the configured renderer cannot produce it;
- one delivery/readme PDF;
- one package manifest.

The first asset renderer may use HTML/CSS/SVG and deterministic screenshot capture. It must not depend on a live design SaaS.

## 14. Preflight

Preflight rejects the package unless:

- product QA passed;
- every claim maps to a product fact;
- title, description, tags, images, video status, and delivery document are present;
- all hashes reconcile;
- all required links resolve locally or are explicitly permitted external links;
- automation mode is `simulation` or `draft`;
- incremental spend is exactly zero;
- no publication receipt exists.

A passing preflight emits `DRAFT_READY`, never `PUBLISHED`.
## 15. Swarm topology

Use `$task-router` to route each bounded task and `$team` or equivalent isolated worktree execution for parallel waves.

### Wave 0 — independent hardening

- **Lane H:** validate and repair the four open CodeRabbit findings.
- **Lane C:** implement and freeze slice contracts, enums, and configuration.

### Wave 1 — parallel implementation after contract freeze

- **Lane P:** PostgreSQL migrations, repositories, leases, and durable orchestration.
- **Lane R:** research admission, qualification, shortlist, ProductSpec, and dedupe.
- **Lane B:** deterministic local product builder and product QA.
- **Lane M:** merchandising, asset renderer, listing package, and preflight.

### Wave 2 — integration

The integration owner merges reviewed lane commits, implements CLI/API composition, runs the complete workflow, and produces the first product package.

### Wave 3 — adversarial review

Independent reviewers inspect architecture compliance, test quality, provenance, replay, artifact truth, and absence of external effects. Findings are fixed before the slice is declared complete.
## 16. Ownership boundaries

Shared files are integration-owner only:

- `pyproject.toml`
- `uv.lock`
- `compose*.yaml`
- `src/money_machine/domain/enums.py`
- `src/money_machine/domain/events.py`
- migration ordering and Alembic heads;
- `src/money_machine/orchestration/engine.py`
- `src/money_machine/api/main.py`
- `src/money_machine/cli/main.py`
- all files under `docs/control/`.

Each lane receives a path manifest. Workers may not edit another lane's files, merge their own branch, modify control state, or launch external effects.

## 17. Test protocol

For every behavior:

1. write one minimal failing test;
2. run it and record the expected failure;
3. implement the minimum production behavior;
4. rerun the targeted test;
5. run the lane suite;
6. refactor only while green;
7. commit the bounded change;
8. submit it for spec and code-quality review.
Mock-only tests do not establish integration behavior. The final slice requires real PostgreSQL, real filesystem artifacts, and deterministic replay in an isolated runtime.

## 18. Required operator surfaces

Provide bounded commands:

```text
money-machine db migrate
money-machine research import --packet <path>
money-machine workflow start first-product --packet-id <id>
money-machine worker run-once
money-machine workflow status <run-id>
money-machine artifacts inspect <run-id>
```

The API may expose read-only workflow and artifact status. Mutation remains CLI-local during the slice.

## 19. Acceptance criteria

The slice is complete only when:

1. CodeRabbit critical and major findings are closed.
2. PostgreSQL contains real slice tables and migrations.
3. Worker and scheduler no longer exit 78 for the first-product workflow.
4. A 25–40-row admitted packet is persisted.
5. Five candidates are shortlisted where evidence permits.
6. One candidate scores at least 30/40.
7. One ProductSpec and passing dedupe result exist.
8. One deterministic local product bundle exists.
9. Product QA passes.
10. One complete listing package exists.
11. Preflight passes and emits `DRAFT_READY`.
12. Replay creates no duplicate business identities or artifacts.
13. PostgreSQL, worker, API, and filesystem integration tests pass.
14. No Etsy, Notion, messaging, purchase, publication, or spend action occurs.
15. The product bundle is inspectable by Omar from a stable local path.
16. All lane commits receive independent review.
17. The full repository verification gate passes against the exact final commit.
18. Control state records the slice truthfully without marking later sessions complete.

## 20. Progress metrics

Status reports lead with:

```text
Research rows admitted
Candidates shortlisted
Candidates scoring ≥30/40
ProductSpecs produced
Dedupe passes
Products built
Products passing QA
Listing packages complete
Preflight passes
Draft-ready products
Live publications
Sales
Revenue
```

Tests, contracts, files, agents, and receipts are supporting evidence.

## 21. Deferred work

Live Notion writes, Etsy draft creation, Etsy publication, analytics, cull/multiply, support automation, PostHog, S3, and the full operator console remain separate later slices. Each requires its own design, TDD plan, provider evidence, and explicit authority.