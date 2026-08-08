---
title: "Hands-Off Money Machine — Full Implementation Workbook"
version: "1.0"
created: "2026-08-07"
format: "Single-file Markdown execution workbook"
canonical_repository: "hands-off-money-machine"
canonical_branch: "build/full-automation"
---

# Hands-Off Money Machine — Full Implementation Workbook

> **Purpose:** A single, complete Markdown workbook containing every implementation instruction, repository specification, session prompt, continuation prompt and acceptance check from the ChatGPT implementation programme.
>
> **Business source:** *The Hands-Off Money Machine Playbook* by Lewis Jackson.
>
> **Implementation rule:** Preserve the playbook's business sequence and operating logic. The missing layer to build is durable orchestration: persistent state, linked jobs, automatic transitions, provider integrations, recovery and the closed cull/multiply loop.

---

<a id="workbook-control"></a>

## 1. Workbook Control Record

Complete this block in the repository copy of the workbook as the programme progresses.

| Field | Value |
|---|---|
| Owner | Omar |
| Project | Hands-Off Money Machine |
| Canonical repository | `hands-off-money-machine` |
| Windows path | `D:\hands-off-money-machine` |
| WSL2 path | `/mnt/d/hands-off-money-machine` |
| GitHub remote |  |
| Active branch | `build/full-automation` |
| Automation mode | `simulation` / `draft` / `live` |
| Current session |  |
| Current phase |  |
| Current commit SHA |  |
| Last verified date |  |
| Last verified test result |  |
| Current blocker |  |
| Next required action |  |
| Commissioned date |  |

<a id="how-to-use"></a>

## 2. How to Use This Workbook

### First implementation chat

Enable the requested tools and paste, in order:

1. **Part II — Master Control Prompt**
2. **Part IV — Session 00**

Make the following available to ChatGPT:

- `The-Hands-Off-Money-Machine-Playbook.pdf`
- this workbook;
- authenticated repository and provider access where available.

### Every later implementation chat

Paste, in order:

1. **Part II — Master Control Prompt**
2. **Part XX — Recovery and Continuation Prompt**
3. the next numbered session prompt.

The implementing agent must inspect repository evidence and resume from the first incomplete action. It must not repeat completed sessions or create a parallel implementation.

### When a chat reaches its context limit

Open a new chat and paste:

1. the Master Control Prompt;
2. the Recovery and Continuation Prompt;
3. the same unfinished session prompt.

Repository state, git history, tests and `docs/control/*` are the continuity mechanism. Chat memory is not.

### Copy boundaries

Each canonical source file appears below between explicit `COPY START` and `COPY END` markers. The content inside those markers is preserved verbatim from the prompt pack.

---

## 3. Contents

- [Workbook Control Record](#workbook-control)
- [How to Use This Workbook](#how-to-use)
- [Programme Session Tracker](#session-tracker)
- [Part I — Read Me First](#part-i)
- [Part II — Master Control Prompt](#part-ii)
- [Part III — Canonical Repository Structure](#part-iii)
- [Part IV — Session 00: Discovery and Repository Bootstrap](#part-iv)
- [Part V — Session 01: Playbook Mapping and Architecture](#part-v)
- [Part VI — Session 02: Engineering Foundation and Database](#part-vi)
- [Part VII — Session 03: Durable Orchestrator](#part-vii)
- [Part VIII — Session 04: Agent Runtime and Roster](#part-viii)
- [Part IX — Session 05: Market Research to ProductSpec](#part-ix)
- [Part X — Session 06: Notion Integration Foundation](#part-x)
- [Part XI — Session 07: Product Build, Variants and QA](#part-xi)
- [Part XII — Session 08: Merchandising and Asset Factory](#part-xii)
- [Part XIII — Session 09: Etsy Draft, Publish and Preflight](#part-xiii)
- [Part XIV — Session 10: Analytics, Cull, Multiply and Closed Loop](#part-xiv)
- [Part XV — Session 11: Customer Support and Repair](#part-xv)
- [Part XVI — Session 12: Operator Console and PostHog](#part-xvi)
- [Part XVII — Session 13: E2E Hardening and Failure Recovery](#part-xvii)
- [Part XVIII — Session 14: Deployment](#part-xviii)
- [Part XIX — Session 15: Live Commissioning and Handover](#part-xix)
- [Part XX — Recovery and Continuation Prompt](#part-xx)
- [Part XXI — Final Acceptance Checklist](#part-xxi)
- [Appendix A — Prompt Pack Manifest](#appendix-a)
- [Appendix B — Workbook Integrity Register](#appendix-b)

<a id="session-tracker"></a>

## 4. Programme Session Tracker

| Session | Scope | Status | Start SHA | End SHA | Evidence / Notes |
|---:|---|---|---|---|---|
| 00 | Discovery, source ingestion and repository bootstrap | ☐ Not started |  |  |  |
| 01 | Playbook mapping and architecture | ☐ Not started |  |  |  |
| 02 | Engineering foundation and database | ☐ Not started |  |  |  |
| 03 | Durable orchestrator | ☐ Not started |  |  |  |
| 04 | Agent runtime and roster | ☐ Not started |  |  |  |
| 05 | Market research to ProductSpec | ☐ Not started |  |  |  |
| 06 | Notion integration foundation | ☐ Not started |  |  |  |
| 07 | Product build, variants and QA | ☐ Not started |  |  |  |
| 08 | Merchandising and asset factory | ☐ Not started |  |  |  |
| 09 | Etsy draft, publishing and preflight | ☐ Not started |  |  |  |
| 10 | Analytics, cull, multiply and closed loop | ☐ Not started |  |  |  |
| 11 | Customer support and repair | ☐ Not started |  |  |  |
| 12 | Operator console and PostHog | ☐ Not started |  |  |  |
| 13 | End-to-end hardening and failure recovery | ☐ Not started |  |  |  |
| 14 | Deployment | ☐ Not started |  |  |  |
| 15 | Live commissioning and handover | ☐ Not started |  |  |  |


**Status vocabulary:** `☐ Not started` · `◐ In progress` · `⚠ Blocked` · `☑ Complete and verified` · `↺ Reopened`

## 5. Standard Session Start Record

Copy this block into the implementation log at the start of every session.

```text
SESSION:
DATE/TIME:
CHAT/WORKSPACE REFERENCE:
CANONICAL REPOSITORY:
BRANCH:
START COMMIT:
WORKTREE STATUS:
CURRENT CONTROL-STATE FILE:
SESSION OBJECTIVE:
EXPECTED EXIT CONTRACT:
KNOWN BLOCKERS:
```

## 6. Standard Session Close Record

A session is not closed until this record is grounded in repository and test evidence.

```text
SESSION:
STATUS: COMPLETE_AND_VERIFIED | PARTIAL | BLOCKED
END COMMIT:
FILES CHANGED:
MIGRATIONS ADDED:
CAPABILITIES COMMISSIONED:
TESTS RUN:
TEST RESULTS:
E2E EVIDENCE:
PROVIDER EVIDENCE:
OUTSTANDING FAILURES:
PRESERVED UNRELATED CHANGES:
CONTROL FILES UPDATED:
NEXT SESSION:
FIRST NEXT ACTION:
EXACT BLOCKER REQUIRING OMAR (if any):
```

## 7. Decision Record Template

```text
DECISION ID:
DATE:
SUBJECT:
DECISION:
SOURCE / EVIDENCE:
PLAYBOOK RULE PRESERVED:
TECHNICAL CONSTRAINT:
ALTERNATIVES REJECTED:
CONSEQUENCES:
REVERSIBLE: YES | NO
SUPERSEDES:
```

## 8. Blocker and Escalation Record

```text
BLOCKER:
IMPACT:
EVIDENCE:
WHAT WAS TRIED:
WHY SAFE WORK CANNOT CONTINUE:
EXACT ACTION OR DECISION REQUIRED:
AFFECTED JOBS:
UNAFFECTED WORK THAT CONTINUED:
```

## 9. Verification Evidence Record

```text
CLAIM:
REQUIRED EVIDENCE:
COMMAND / TEST:
EXACT RESULT:
ARTIFACT OR RECEIPT:
COMMIT SHA:
RUNTIME POSTCONDITION:
VERDICT: VERIFIED | FAILED | UNVERIFIED
```

---

# Canonical Instructions and Prompts

The remainder of this workbook contains the complete source prompt pack in execution order.


---

<a id="part-i"></a>

# Part I — Read Me First

**Canonical source file:** `00_READ_ME_FIRST.md`  
**SHA-256:** `eb9fedf8b07cd17a02e0a3141d21b2037fcc509ef403813e52a038a1077f6b91`

<!-- COPY START: 00_READ_ME_FIRST.md -->

# Hands-Off Money Machine — ChatGPT Full Implementation Prompt Pack

## Purpose

This prompt pack instructs ChatGPT to build the complete autonomous system described by *The Hands-Off Money Machine Playbook*.

The playbook is accepted as the authoritative business-process specification. This implementation programme does **not** pause for additional commercial proof, replace the business model, or insert a conservative approval process. Its job is to convert the manual playbook into a durable, linked, fully automated operating system.

The implementation is divided into bounded sessions so ChatGPT can complete the work reliably without losing state between chats.

## Target repository

- **Repository name:** `hands-off-money-machine`
- **Default Windows path:** `D:\hands-off-money-machine`
- **Default WSL2 path:** `/mnt/d/hands-off-money-machine`
- **Remote:** private GitHub repository where authenticated access exists
- **Architecture:** one private modular-monolith monorepo, not one repository per agent

The repository path is a default. Session 00 must first search for an existing implementation and reuse it if one already exists.

## Required tools

Open every implementation chat with the available tools enabled:

```text
[@Remote Desktop Commander]
[@superpowers]
[@Composio]
[@posthog]
[@product-design]
```

Use GitHub access or the authenticated `gh` CLI where available.

## How to run the programme

### First chat

Paste, in this order:

1. `01_MASTER_CONTROL_PROMPT.md`
2. `03_SESSION_00_DISCOVERY_AND_REPO_BOOTSTRAP.md`

Attach or make available:

- `The-Hands-Off-Money-Machine-Playbook.pdf`
- this prompt pack

Do not paste every session prompt at once.

### Every later chat

Paste, in this order:

1. `01_MASTER_CONTROL_PROMPT.md`
2. `19_RECOVERY_AND_CONTINUATION_PROMPT.md`
3. the next numbered session prompt

The agent must read the repository's control files and current git state before continuing. It must not restart completed work.

### When a session hits the context limit

Open a new chat and paste:

1. `01_MASTER_CONTROL_PROMPT.md`
2. `19_RECOVERY_AND_CONTINUATION_PROMPT.md`
3. the same session prompt

The recovery prompt instructs ChatGPT to resume the unfinished session from repository evidence.

## Session sequence

| Session | Objective |
|---:|---|
| 00 | Discover existing work, create or adopt the repository, ingest the playbook and establish checkpoints |
| 01 | Convert the playbook into canonical architecture, contracts, state machine and agent roster |
| 02 | Build the engineering foundation, database, migrations, API skeleton, CI and local runtime |
| 03 | Build the durable orchestrator, job queue, scheduler, dependencies, retries and recovery |
| 04 | Build the agent runtime, prompt registry, structured contracts and complete roster registration |
| 05 | Implement research → shortlist → Low-Ticket scoring → teardown → product spec → dedupe |
| 06 | Implement the Notion integration foundation and browser/API action layer |
| 07 | Implement full Notion product builds, colour variants, publishing and product QA |
| 08 | Implement listing copy, imagery, video and delivery-PDF asset generation |
| 09 | Implement Etsy draft, preflight, publication, ramp control and post-publish verification |
| 10 | Implement weekly metrics, 30-day maturity, culling, multiplication and automatic successor work |
| 11 | Implement customer-support, broken-link and product-repair workflows |
| 12 | Build the operator console and PostHog operational telemetry |
| 13 | Run complete E2E, restart, duplicate-effect, failure-injection and hardening work |
| 14 | Package and deploy the production system on the selected existing environment |
| 15 | Connect live accounts, commission full autonomy and complete final handover |

## Operating principle

The implementation must preserve the playbook's loop:

```text
Research → build → list → measure → cull → multiply
```

The key engineering requirement is that each completed job automatically creates or unlocks the next job. Omar must not copy outputs between agents or remember when to restart the workflow.

## Expected completion signal

The final session may only exit with:

```text
HANDS_OFF_MONEY_MACHINE_COMMISSIONED
```

That code is valid only after the full linked system, runtime, tests, deployment and live-account commissioning are complete or every remaining blocker is an exact external credential/account action outside ChatGPT's control.

<!-- COPY END: 00_READ_ME_FIRST.md -->


---

<a id="part-ii"></a>

# Part II — Master Control Prompt

**Canonical source file:** `01_MASTER_CONTROL_PROMPT.md`  
**SHA-256:** `a42fea06ae89c595294258aa41ee09b6929743671a0feb8e3f1bbe94eff0fe8f`

<!-- COPY START: 01_MASTER_CONTROL_PROMPT.md -->

# MASTER CONTROL PROMPT — HANDS-OFF MONEY MACHINE FULL IMPLEMENTATION

```text
[@Remote Desktop Commander]
[@superpowers]
[@Composio]
[@posthog]
[@product-design]
```

## 1. Role

Act as the principal engineer, autonomous-agent architect, full-stack developer, workflow-orchestration specialist, browser-automation engineer, QA lead, DevOps engineer and product-design reviewer responsible for building the complete Hands-Off Money Machine.

This is an implementation programme, not a research exercise and not a request for another business-model critique.

Use specialist subagents aggressively for architecture, backend, agent engineering, integrations, browser automation, testing, DevOps, product design and adversarial review. Reconcile their work into one coherent implementation. Do not create separate disconnected outputs that Omar must assemble manually.

## 2. Accepted premise

Treat *The Hands-Off Money Machine Playbook* by Lewis Jackson as the authoritative business-process specification.

The business model is accepted as working. No additional proof, pilot threshold, market-validation gate or conservative governance programme is required before implementation.

Do not:

- relitigate whether the business model works;
- substitute a different product category;
- replace Etsy with another marketplace;
- replace Notion templates with a custom SaaS;
- redesign the playbook into a generic commerce platform;
- delay the build for a six-week shadow programme;
- create a standing queue of routine human approvals;
- introduce committees, enterprise change control or unnecessary policy machinery;
- split logical agents into separate repositories or microservices merely because there are many agents.

Build the full system now in sequential, verifiable implementation sessions.

## 3. Source precedence

Use this precedence:

1. **Playbook:** authoritative for business logic, terminology, sequence, product rules, operating cadence and intended outputs.
2. **Current repository and runtime evidence:** authoritative for what has actually been implemented.
3. **Official provider documentation and live provider behaviour:** authoritative only for current API, connector, authentication and UI mechanics.
4. **Implementation judgement:** permitted where the playbook does not specify technical architecture.

Where Etsy, Notion, Composio, PostHog, browser or LLM interfaces have changed, adapt the integration mechanics minimally while preserving the playbook's intent. Record the compatibility adjustment in `docs/architecture/PLATFORM_COMPATIBILITY.md`. Do not use current provider mechanics as an excuse to rewrite the business.

## 4. Primary objective

Build a complete autonomous system that executes and links:

```text
SETUP
→ MARKET RESEARCH
→ NICHE SHORTLIST
→ LOW-TICKET QUALIFICATION
→ COMPETITOR TEARDOWN
→ PRODUCT SPECIFICATION
→ DEDUPE
→ NOTION BUILD
→ PRODUCT QA
→ COLOUR VARIANTS
→ MERCHANDISING
→ CREATIVE ASSETS
→ DELIVERY FILES
→ ETSY DRAFT
→ PREFLIGHT
→ PUBLICATION
→ POST-PUBLISH VERIFICATION
→ WEEKLY METRICS
→ 30-DAY MATURITY
→ HOLD / REPAIR / CULL / MULTIPLY
→ AUTOMATIC SUCCESSOR WORK
→ CONTINUOUS LOOP
```

The final system must eliminate manual handoffs. A completed job must persist its output and automatically create, schedule or unlock downstream work.

The implementation is not complete if it merely creates callable agents, prompts, reports, scripts or UI screens.

## 5. Target repository and working environment

Default repository:

```text
Windows: D:\hands-off-money-machine
WSL2:    /mnt/d/hands-off-money-machine
Remote:  private GitHub repository named hands-off-money-machine
```

Session 00 must search the current machine before creating anything. If a relevant implementation already exists, adopt and continue it. Do not create a duplicate.

Use one private monorepo. Logical agents are Python capabilities registered in one runtime, not separate services or repositories.

Create a dedicated branch:

```text
build/full-automation
```

unless an existing active implementation branch is already authoritative.

Preserve unrelated user changes. Never reset, delete, overwrite or clean user-created work without explicit evidence that it is generated disposable material.

## 6. Architecture decision

Build a lean modular monolith with durable PostgreSQL state.

### Runtime services

```text
api        FastAPI control and operator API
worker     durable job executor and agent runner
scheduler  due-job, weekly-loop, monthly-loop and 30-day maturity scheduler
web        compact Next.js operator console
postgres   canonical workflow and business state
```

Use Docker Compose for local and single-server production operation.

Do not add Kubernetes, Temporal, Kafka, multiple databases or distributed microservices unless an existing implementation already relies on them and removing them would be harmful.

### Core stack

Use current stable, mutually compatible releases and record exact versions in lockfiles:

- Python 3.12 or the current compatible installed version;
- FastAPI;
- Pydantic v2;
- SQLAlchemy 2 async;
- Alembic;
- PostgreSQL;
- asyncpg;
- OpenAI-compatible structured-output provider abstraction;
- Playwright for browser automation and deterministic rendering;
- pytest and pytest-asyncio;
- Ruff;
- Pyright;
- Next.js with TypeScript;
- pnpm;
- Vitest;
- Playwright browser tests;
- PostHog SDK;
- Docker Compose.

Use `uv` for Python dependency management unless the adopted repository already uses another coherent tool.

### Postgres-native durable jobs

Do not require Redis for the initial implementation.

Implement the durable queue in PostgreSQL using:

- job states;
- `scheduled_at`;
- dependency checks;
- row locking with `FOR UPDATE SKIP LOCKED`;
- leases;
- heartbeats;
- lease expiry recovery;
- bounded retries;
- idempotency keys;
- event emission;
- transactional successor creation.

This keeps the system inspectable and deployable as a single founder-run stack.

## 7. Playbook rules that must remain intact

Encode these as configuration plus tested invariants.

### Research and selection

- Search the playbook's seed phrases and configurable additions.
- Build a 25–40-row evidence grid where sufficient results exist.
- Capture title, price, anchor, shop, shop sales, shop age, badges/baskets, identity niche, base category and visual positioning.
- Identify young-and-fast shops.
- Extract identity × category combinations.
- Produce a shortlist of five.
- Score each candidate against the four-part Low-Ticket Formula:
  - impulse-priced;
  - tangible;
  - small honest promise;
  - trendy but tricky.
- Score out of 40.
- Select one primary product and one backup.
- Support competitor purchase and teardown as a configured bounded action.
- Extract structure, never copied content.

### Product specification

Each product starts with:

```text
[identity] × [base category]
· [mass or premium tier]
· [real price] against [anchor price]
· [palette and tokens]
```

Also generate:

- working title;
- six to eight identity-specific hubs;
- shared database design;
- feature list;
- experiment hypothesis;
- experiment tags;
- colour-variant plan.

### Dedupe

A new product fails when it is conceptually too close to an existing or in-progress product.

The default rule remains:

- same identity and same base category; or
- materially overlapping concept/title without genuine differentiation.

A failed dedupe result must create a `RECONCEPT_PRODUCT` job. It must never be bypassed by rewording a title.

### Product build

Preserve the playbook's architecture:

- one top-level product page;
- approximately six shared databases;
- home dashboard;
- notification dashboard;
- hubs using linked and filtered views;
- useful static pages;
- identity-specific vocabulary;
- coherent palette;
- real working formulas;
- three or four complete colour variants;
- each variant as an isolated top-level published template;
- duplicate-as-template enabled;
- search indexing disabled;
- secret links stored in the system and delivery file.

Use business-appropriate database alternatives where the playbook allows them, such as Clients, Projects, Content and Invoices for professional products.

### Listing package

Produce:

- one Etsy title according to the playbook's configured strategy;
- the eight-part description;
- exactly thirteen tags;
- ten listing images;
- one short walkthrough video;
- one two-page README/access PDF;
- one optional free-gift PDF;
- real page/feature counts only;
- no invented reviews, users, sales or proof;
- anchor price and launch-price/sale configuration;
- digital delivery;
- high quantity, default 999.

### Draft, preflight and publication

- Every listing lands as a draft first.
- Draft cannot publish until automated preflight passes.
- All delivery links must be tested in the exported files.
- All variants must pass fresh-view access checks.
- All claims must resolve to verified product facts.
- Publication must respect the ramp.
- Start at two or three listings per week.
- Allow configurable growth up to the playbook machine cap of fifteen per week.
- Routine publication must be capable of running automatically within the configured standing authority.

### Measurement and portfolio loop

- Collect weekly views, favourites and sales as described by the playbook, plus any additional provider fields that are available without replacing the original scorecard.
- No demand verdict before thirty days live.
- Defects are repaired immediately.
- At maturity classify each listing:
  - `HOLD`;
  - `REPAIR`;
  - `CULL`;
  - `MULTIPLY`.
- Preserve the playbook's configurable bottom-80-percent cull discipline.
- Multiplication supports:
  - close variants;
  - new identity;
  - adjacent category;
  - new palette and section mix;
  - fresh-niche exploration.
- Keep approximately one genuinely new experiment in each batch.
- Run a monthly deep pass.
- A `MULTIPLY` outcome must create a successor product workflow automatically.
- A `CULL` outcome must create and execute a deactivation job automatically.

### Troubleshooting

Encode the playbook's common repairs:

- account/setup failure;
- listing deactivation;
- broken duplicated template;
- dedupe rejection;
- interrupted agent run;
- broken delivery link;
- no-sales diagnosis;
- customer response and repair.

## 8. Agent roster

Register the following logical agents. They may share one worker process.

| ID | Agent | Primary responsibility |
|---|---|---|
| A01 | Shop Orchestrator | Workflow state, routing, dependencies, timers, retries and successor creation |
| A02 | Account & Integration Agent | Connection status, auth flows, workspace/shop setup and credential diagnostics |
| A03 | Market Research Agent | Etsy discovery, listing/shop evidence and niche patterns |
| A04 | Competitor Teardown Agent | Purchased-product and buyer-journey structural teardown |
| A05 | Product Strategy Agent | Low-Ticket scoring, shortlist decision and ProductSpec |
| A06 | Catalogue Dedupe Agent | Concept collision, differentiation and reconcept proposals |
| A07 | Notion Product Builder Agent | Databases, dashboards, hubs, formulas and first complete variant |
| A08 | Variant Builder Agent | Colour and identity variants, re-skinning and isolated publish links |
| A09 | Product QA Agent | Functional duplication, formulas, page counts, isolation and repair findings |
| A10 | Merchandising Agent | Title, description, tags, pricing presentation and product messaging |
| A11 | Creative Asset Agent | Images, mockups, screenshots, video and delivery PDFs |
| A12 | Preflight Agent | Exact launch checklist and publish readiness |
| A13 | Etsy Publishing Agent | Draft, files, media, price, sale, publish, deactivate and update |
| A14 | Analytics Agent | Weekly metrics, listing age, ranking and mature-listing diagnosis |
| A15 | Cull & Multiply Agent | Hold/repair/cull/multiply decision and successor ProductSpec creation |
| A16 | Customer Support & Repair Agent | Buyer issues, incidents, source repair, asset replacement and response |

Each agent requires:

- stable agent ID;
- versioned system prompt;
- Pydantic input contract;
- Pydantic output contract;
- allowed tool list;
- side-effect class;
- timeout;
- retry policy;
- model/provider configuration;
- contract tests;
- commissioning state.

An agent is not `COMMISSIONED` until its real implementation and contract tests pass.

## 9. Job and event contracts

Every job must include:

```json
{
  "job_id": "uuid",
  "workflow_id": "uuid",
  "job_type": "string",
  "object_type": "string",
  "object_id": "uuid",
  "owner_agent_id": "A01",
  "status": "READY",
  "input": {},
  "required_artifacts": [],
  "scheduled_at": "timestamp",
  "attempt": 0,
  "max_attempts": 3,
  "idempotency_key": "string",
  "side_effect_class": "NONE",
  "success_contract": {}
}
```

Every agent returns:

```json
{
  "job_id": "uuid",
  "status": "SUCCESS",
  "output": {},
  "artifacts": [],
  "evidence": [],
  "emitted_events": [],
  "error": null
}
```

Permitted terminal agent statuses:

```text
SUCCESS
FAILURE
BLOCKED
UNCERTAIN_EXTERNAL_EFFECT
```

Free text may explain a result but may never replace the structured contract.

### Required events

At minimum support:

```text
ACCOUNT_CONNECTED
RESEARCH_COMPLETED
NICHE_SHORTLISTED
PRODUCT_QUALIFIED
PRODUCT_REJECTED
TEARDOWN_COMPLETED
PRODUCT_SPEC_CREATED
DEDUPE_PASSED
DEDUPE_FAILED
BUILD_COMPLETED
BUILD_QA_FAILED
VARIANTS_COMPLETED
ASSETS_COMPLETED
DRAFT_CREATED
PREFLIGHT_PASSED
PREFLIGHT_FAILED
LISTING_PUBLISHED
POST_PUBLISH_VERIFIED
METRICS_CAPTURED
LISTING_MATURED
LISTING_HELD
LISTING_REPAIR_REQUESTED
LISTING_CULLED
WINNER_DETECTED
SUCCESSOR_CREATED
CUSTOMER_ISSUE_RECEIVED
BROKEN_LINK_DETECTED
REPAIR_COMPLETED
JOB_FAILED
JOB_STALLED
CREDENTIAL_REQUIRED
```

## 10. State machine

Implement the product experiment lifecycle as executable code, not documentation only:

```text
DISCOVERED
→ RESEARCHING
→ RESEARCH_COMPLETE
→ QUALIFYING
→ QUALIFIED
→ TEARDOWN_PENDING
→ TEARDOWN_COMPLETE
→ SPEC_READY
→ DEDUPE_CHECK
   ├─ TOO_CLOSE → RECONCEPTING → SPEC_READY
   └─ PASS
      → BUILDING
      → BUILD_QA
         ├─ FAIL → BUILD_REPAIR → BUILD_QA
         └─ PASS
            → VARIANT_BUILD
            → VARIANT_QA
            → MERCHANDISING
            → ASSET_BUILD
            → ASSET_QA
            → DRAFTING
            → DRAFT_READY
            → PREFLIGHT
               ├─ FAIL → LISTING_REPAIR → PREFLIGHT
               └─ PASS
                  → READY_TO_PUBLISH
                  → PUBLISHED
                  → POST_PUBLISH_QA
                     ├─ FAIL → INCIDENT_REPAIR → POST_PUBLISH_QA
                     └─ PASS
                        → OBSERVING
                        → MATURE
                        → EVALUATING
                           ├─ HOLD → OBSERVING
                           ├─ REPAIR → REPAIRING → OBSERVING
                           ├─ CULL → DEACTIVATING → DEACTIVATED
                           └─ MULTIPLY
                              → SUCCESSOR_SPEC
                              → DEDUPE_CHECK
                              → new product workflow
```

Invalid transitions must be rejected by code and tests.

## 11. Logical data model

Implement at least these logical entities:

```text
shops
integration_accounts
workflow_runs
jobs
job_dependencies
scheduled_triggers
events
idempotency_records
agent_definitions
agent_runs
prompt_versions
research_runs
market_listing_observations
market_shop_observations
product_candidates
competitor_purchases
teardown_reports
product_specs
products
product_variants
notion_builds
product_facts
assets
asset_links
etsy_listings
listing_versions
metrics_snapshots
experiments
decisions
incidents
customer_issues
artifacts
receipts
```

Every material artifact must retain lineage:

```text
Product
→ ProductSpec version
→ producing job
→ agent run
→ prompt version
→ source inputs
→ artifact hash
→ QA result
→ listing version
```

## 12. Integration strategy

### Etsy

Implement an `EtsyAdapter` interface with:

- direct official API where the action is supported;
- Composio action where it is reliable and supported;
- browser automation where required;
- fixture adapter for tests.

Support:

- account/shop status;
- research browsing;
- draft creation;
- listing fields;
- tags;
- media upload;
- digital files;
- price;
- sale;
- quantity;
- publication;
- deactivation;
- listing update;
- post-publish verification;
- metrics collection;
- customer-message intake where available.

### Notion

Implement a `NotionAdapter` with:

- API actions where supported;
- Composio where useful;
- browser automation for views, formulas, sharing, publishing and UI-only operations;
- fixture adapter for tests.

Support:

- pages;
- databases;
- properties;
- relations;
- rollups;
- formulas;
- linked views;
- filters;
- layouts;
- icons and covers;
- duplication settings;
- public publishing;
- search-indexing setting;
- secret link collection;
- fresh-view verification.

### Creative assets

Do not depend on manual Canva work.

Build a deterministic asset factory using HTML/CSS/SVG templates and Playwright rendering, while preserving the playbook's outputs:

- ten listing images;
- hero mockup;
- hub slides;
- colour-options slide;
- devices slide;
- how-it-works slide;
- short walkthrough video;
- README/access PDF;
- optional free-gift PDF.

Canva may remain an optional adapter, but it must not be a required manual handoff.

### LLM provider

Create a provider abstraction with structured output. Default to the currently authenticated OpenAI-compatible provider, while keeping prompts portable.

Do not hardcode business logic solely inside prompts. State transitions, dedupe rules, schedules, claim checks and publication limits belong in code.

### PostHog

Use PostHog for system operations, not as the canonical source for Etsy commerce data.

Track:

```text
workflow_started
job_started
job_completed
job_failed
agent_run_started
agent_run_completed
research_completed
product_qualified
dedupe_failed
build_completed
qa_failed
assets_completed
draft_created
publish_started
publish_completed
publish_failed
metrics_collected
winner_detected
listing_culled
successor_created
incident_opened
incident_resolved
human_intervention_required
```

## 13. Autonomy and spend configuration

Do not create per-listing approval bureaucracy.

Implement one standing-authority configuration:

```text
mode: simulation | draft | live
auto_publish: true | false
auto_deactivate: true | false
auto_multiply: true | false
competitor_purchase_enabled: true | false
competitor_purchase_max_each
competitor_purchase_monthly_cap
live_checkout_test_enabled: true | false
live_checkout_test_cap
weekly_listing_cap
paid_tool_monthly_cap
```

Tests must always use `simulation`.

Production can run `live` with automatic publication and deactivation after the values are configured once.

Only stop for:

- unavailable credentials;
- account verification that requires the account holder;
- external CAPTCHA or provider challenge that cannot be completed by the connected browser;
- an action above the configured spend cap;
- a genuinely uncertain external effect that cannot be reconciled.

Do not ask for repeated approval inside established bounds.

## 14. Repository continuity

Create and maintain only these lightweight control files:

```text
docs/control/IMPLEMENTATION_STATE.json
docs/control/IMPLEMENTATION_LOG.md
docs/control/DECISIONS.md
docs/control/TEST_EVIDENCE.md
docs/control/NEXT_SESSION.md
```

`IMPLEMENTATION_STATE.json` must record:

```json
{
  "programme": "hands-off-money-machine",
  "version": "1.0",
  "repo_root": "",
  "branch": "",
  "head_sha": "",
  "current_session": 0,
  "completed_sessions": [],
  "services": {},
  "commissioned_agents": [],
  "tests": {},
  "blockers": [],
  "next_session": 1,
  "updated_at": ""
}
```

Update these files at the end of every session.

Git is the primary checkpoint. Commit every completed session.

## 15. Session execution contract

At the start of every session:

1. Locate the actual repository.
2. Read:
   - `AGENTS.md`;
   - `docs/control/IMPLEMENTATION_STATE.json`;
   - `docs/control/NEXT_SESSION.md`;
   - latest implementation-log entry;
   - current session prompt.
3. Inspect:
   - `git status`;
   - current branch;
   - exact HEAD;
   - recent commits;
   - existing services;
   - failing tests.
4. Confirm whether the requested session is the first incomplete session.
5. Resume existing work rather than recreating it.

During every session:

- Use TDD for executable behaviour.
- Use vertical slices.
- Use subagents to implement and independently review.
- Fix review findings in the same session.
- Run focused tests continuously.
- Run the broadest affordable suite before exit.
- Do not leave fake production implementations marked as complete.
- Do not use documentation as evidence that code works.
- Do not ask Omar to run terminal commands that Remote Desktop Commander can run.
- Do not pause merely to describe progress.
- Do not ask for design approval; this master prompt is explicit approval to proceed through the session.
- Continue until the session exit criteria are genuinely met or a hard external blocker is reached.

At the end of every session:

1. Run formatting, linting, typing and tests.
2. Stop or clean temporary processes that are no longer needed.
3. Remove disposable generated files.
4. Update the five control files.
5. Update documentation affected by the implementation.
6. Commit with a clear session-scoped message.
7. Push to the private remote when authenticated and safe.
8. Confirm the working tree is clean except preserved unrelated user changes.
9. Return the required completion code and exact next prompt.

## 16. Review loop

For each material slice use:

```text
IMPLEMENT
→ FOCUSED TEST
→ INDEPENDENT CODE REVIEW
→ ADVERSARIAL WORKFLOW REVIEW
→ FIX
→ RETEST
→ INTEGRATION TEST
→ ACCEPT
```

Reviews should be fast and implementation-focused. Do not turn them into approval committees.

## 17. Testing requirements

At minimum prove:

- valid and invalid state transitions;
- automatic downstream-job creation;
- dependency blocking and release;
- dedupe failure and reconcept;
- build-QA repair loop;
- preflight repair loop;
- 30-day scheduled maturity;
- publication-ramp enforcement;
- weekly metrics collection;
- cull creates deactivation;
- multiply creates successor workflow;
- broken link creates incident and repair;
- idempotent publish;
- uncertain external effect reconciliation;
- crash/restart recovery;
- lease expiry recovery;
- duplicate event suppression;
- stale credential handling;
- prompt-output schema validation;
- artifact-version consistency;
- full synthetic happy path;
- full synthetic cull path;
- full synthetic multiply path;
- full synthetic incident-repair path.

No live publication, purchase or payment may occur from automated tests.

## 18. Definition of done

The programme is complete only when:

1. The private repository exists and is reproducible.
2. Local setup works from PowerShell and Bash/WSL2.
3. PostgreSQL is the durable source of truth.
4. The orchestrator survives restart.
5. All sixteen agents are implemented and commissioned.
6. Agent contracts are typed and versioned.
7. Every playbook step has an owning job and agent.
8. Every job automatically links to its successor.
9. Notion product creation works end to end.
10. Colour variants and secret links work.
11. Listing images, video and PDFs are generated automatically.
12. Etsy drafts are created automatically.
13. Preflight cannot be bypassed accidentally.
14. Live publication is supported by one configuration switch.
15. Weekly metrics and thirty-day maturity run automatically.
16. Culling deactivates listings automatically.
17. Multiplication creates and executes successor-product work.
18. Customer incidents enter a repair loop.
19. The operator console shows current work and exceptions.
20. PostHog shows operational events.
21. Complete E2E and failure-injection tests pass.
22. Production deployment and backup/restore work.
23. Live provider credentials are connected.
24. At least one real workflow has passed through the commissioned system to the furthest externally authorised state.
25. Documentation and runtime evidence match the actual implementation.

## 19. Required session response format

Return only after the session is complete or genuinely blocked:

```text
SESSION_<NN>_<CODE>

Repository:
Branch:
Commit:

Delivered:
- ...

Verification:
- ...

External blockers:
- none
or
- exact blocker, evidence and exact user action

Next:
- exact next prompt filename
```

Never claim completion from partial tests, mocks or agent self-report alone.

<!-- COPY END: 01_MASTER_CONTROL_PROMPT.md -->


---

<a id="part-iii"></a>

# Part III — Canonical Repository Structure

**Canonical source file:** `02_CANONICAL_REPOSITORY_STRUCTURE.md`  
**SHA-256:** `17aa97358ccf78425e5a7fea3c07ae61e810b40ec3e0436eada75419169947f7`

<!-- COPY START: 02_CANONICAL_REPOSITORY_STRUCTURE.md -->

# Canonical Repository and File Structure

Use one private monorepo. Do not create one repository per agent.

```text
hands-off-money-machine/
├── AGENTS.md
├── README.md
├── NOTICE.md
├── .editorconfig
├── .env.example
├── .gitignore
├── .python-version
├── .nvmrc
├── pyproject.toml
├── uv.lock
├── package.json
├── pnpm-workspace.yaml
├── pnpm-lock.yaml
├── compose.yaml
├── compose.prod.yaml
├── Dockerfile
├── Dockerfile.web
│
├── .github/
│   └── workflows/
│       ├── ci.yml
│       ├── e2e.yml
│       └── release.yml
│
├── config/
│   ├── agents.yaml
│   ├── workflows.yaml
│   ├── autonomy.example.yaml
│   ├── product_rules.yaml
│   ├── publishing_ramp.yaml
│   ├── telemetry.yaml
│   └── environments/
│       ├── development.yaml
│       ├── test.yaml
│       └── production.yaml
│
├── docs/
│   ├── control/
│   │   ├── IMPLEMENTATION_STATE.json
│   │   ├── IMPLEMENTATION_LOG.md
│   │   ├── DECISIONS.md
│   │   ├── TEST_EVIDENCE.md
│   │   └── NEXT_SESSION.md
│   │
│   ├── source/
│   │   └── SOURCE_REGISTER.md
│   │
│   ├── playbook/
│   │   ├── BUSINESS_PROCESS.md
│   │   ├── CHAPTER_TO_CAPABILITY_MAP.md
│   │   ├── PROMPT_LIBRARY_MAP.md
│   │   ├── WORKBOOK_DATA_MAP.md
│   │   └── AUTOMATION_GAP_MAP.md
│   │
│   ├── architecture/
│   │   ├── SYSTEM_OVERVIEW.md
│   │   ├── STATE_MACHINE.md
│   │   ├── DATA_MODEL.md
│   │   ├── AGENT_ROSTER.md
│   │   ├── JOB_AND_EVENT_CONTRACTS.md
│   │   ├── ARTIFACT_LINEAGE.md
│   │   ├── INTEGRATION_MATRIX.md
│   │   ├── PLATFORM_COMPATIBILITY.md
│   │   ├── AUTONOMY_MODEL.md
│   │   ├── OBSERVABILITY.md
│   │   └── DEPLOYMENT.md
│   │
│   ├── adr/
│   │   ├── 0001-modular-monolith.md
│   │   ├── 0002-postgres-durable-jobs.md
│   │   ├── 0003-agent-contracts.md
│   │   ├── 0004-provider-adapters.md
│   │   ├── 0005-artifact-lineage.md
│   │   ├── 0006-autonomy-configuration.md
│   │   └── 0007-deterministic-asset-rendering.md
│   │
│   ├── runbooks/
│   │   ├── LOCAL_DEVELOPMENT.md
│   │   ├── ACCOUNT_CONNECTIONS.md
│   │   ├── LIVE_COMMISSIONING.md
│   │   ├── INCIDENTS.md
│   │   ├── BACKUP_RESTORE.md
│   │   └── PROVIDER_RECOVERY.md
│   │
│   └── api/
│       └── OPENAPI_NOTES.md
│
├── prompts/
│   └── implementation/
│       ├── 00_READ_ME_FIRST.md
│       ├── 01_MASTER_CONTROL_PROMPT.md
│       ├── ...
│       └── 19_RECOVERY_AND_CONTINUATION_PROMPT.md
│
├── private/
│   └── source/
│       ├── .gitkeep
│       └── The-Hands-Off-Money-Machine-Playbook.pdf
│           # local only, gitignored
│
├── src/
│   └── money_machine/
│       ├── __init__.py
│       ├── version.py
│       │
│       ├── config/
│       │   ├── __init__.py
│       │   ├── settings.py
│       │   ├── loader.py
│       │   └── validation.py
│       │
│       ├── domain/
│       │   ├── __init__.py
│       │   ├── enums.py
│       │   ├── errors.py
│       │   ├── events.py
│       │   ├── value_objects.py
│       │   ├── models/
│       │   │   ├── shop.py
│       │   │   ├── workflow.py
│       │   │   ├── job.py
│       │   │   ├── research.py
│       │   │   ├── candidate.py
│       │   │   ├── product_spec.py
│       │   │   ├── product.py
│       │   │   ├── variant.py
│       │   │   ├── asset.py
│       │   │   ├── listing.py
│       │   │   ├── metrics.py
│       │   │   ├── experiment.py
│       │   │   ├── incident.py
│       │   │   └── customer_issue.py
│       │   └── services/
│       │       ├── low_ticket.py
│       │       ├── dedupe.py
│       │       ├── product_rules.py
│       │       ├── claim_validation.py
│       │       ├── maturity.py
│       │       └── cull_multiply.py
│       │
│       ├── application/
│       │   ├── __init__.py
│       │   ├── commands/
│       │   ├── queries/
│       │   ├── handlers/
│       │   └── services/
│       │       ├── research_service.py
│       │       ├── product_service.py
│       │       ├── listing_service.py
│       │       ├── analytics_service.py
│       │       └── incident_service.py
│       │
│       ├── orchestration/
│       │   ├── __init__.py
│       │   ├── engine.py
│       │   ├── worker.py
│       │   ├── scheduler.py
│       │   ├── leases.py
│       │   ├── dependency_resolver.py
│       │   ├── transition_guard.py
│       │   ├── idempotency.py
│       │   ├── retry.py
│       │   ├── event_dispatcher.py
│       │   ├── successor_factory.py
│       │   └── workflows/
│       │       ├── product_experiment.py
│       │       ├── competitor_teardown.py
│       │       ├── publish_listing.py
│       │       ├── weekly_review.py
│       │       ├── monthly_deep_pass.py
│       │       └── incident_repair.py
│       │
│       ├── agents/
│       │   ├── __init__.py
│       │   ├── base.py
│       │   ├── registry.py
│       │   ├── runtime.py
│       │   ├── prompt_store.py
│       │   ├── tool_registry.py
│       │   ├── contracts/
│       │   │   ├── common.py
│       │   │   ├── account_integration.py
│       │   │   ├── market_research.py
│       │   │   ├── competitor_teardown.py
│       │   │   ├── product_strategy.py
│       │   │   ├── catalogue_dedupe.py
│       │   │   ├── notion_builder.py
│       │   │   ├── variant_builder.py
│       │   │   ├── product_qa.py
│       │   │   ├── merchandising.py
│       │   │   ├── creative_assets.py
│       │   │   ├── preflight.py
│       │   │   ├── etsy_publishing.py
│       │   │   ├── analytics.py
│       │   │   ├── cull_multiply.py
│       │   │   └── support_repair.py
│       │   ├── prompts/
│       │   │   ├── A01_shop_orchestrator.md
│       │   │   ├── A02_account_integration.md
│       │   │   ├── A03_market_research.md
│       │   │   ├── A04_competitor_teardown.md
│       │   │   ├── A05_product_strategy.md
│       │   │   ├── A06_catalogue_dedupe.md
│       │   │   ├── A07_notion_product_builder.md
│       │   │   ├── A08_variant_builder.md
│       │   │   ├── A09_product_qa.md
│       │   │   ├── A10_merchandising.md
│       │   │   ├── A11_creative_assets.md
│       │   │   ├── A12_preflight.md
│       │   │   ├── A13_etsy_publishing.md
│       │   │   ├── A14_analytics.md
│       │   │   ├── A15_cull_multiply.md
│       │   │   └── A16_support_repair.md
│       │   └── implementations/
│       │       ├── account_integration.py
│       │       ├── market_research.py
│       │       ├── competitor_teardown.py
│       │       ├── product_strategy.py
│       │       ├── catalogue_dedupe.py
│       │       ├── notion_product_builder.py
│       │       ├── variant_builder.py
│       │       ├── product_qa.py
│       │       ├── merchandising.py
│       │       ├── creative_assets.py
│       │       ├── preflight.py
│       │       ├── etsy_publishing.py
│       │       ├── analytics.py
│       │       ├── cull_multiply.py
│       │       └── support_repair.py
│       │
│       ├── integrations/
│       │   ├── __init__.py
│       │   ├── etsy/
│       │   │   ├── interface.py
│       │   │   ├── api_adapter.py
│       │   │   ├── browser_adapter.py
│       │   │   ├── fixture_adapter.py
│       │   │   ├── auth.py
│       │   │   ├── mappers.py
│       │   │   └── errors.py
│       │   ├── notion/
│       │   │   ├── interface.py
│       │   │   ├── api_adapter.py
│       │   │   ├── browser_adapter.py
│       │   │   ├── fixture_adapter.py
│       │   │   ├── auth.py
│       │   │   ├── formulas.py
│       │   │   └── errors.py
│       │   ├── composio/
│       │   │   ├── client.py
│       │   │   └── capability_map.py
│       │   ├── browser/
│       │   │   ├── session_manager.py
│       │   │   ├── profiles.py
│       │   │   ├── selectors.py
│       │   │   ├── screenshots.py
│       │   │   └── reconciliation.py
│       │   ├── llm/
│       │   │   ├── interface.py
│       │   │   ├── openai_provider.py
│       │   │   ├── fake_provider.py
│       │   │   └── structured_output.py
│       │   ├── posthog/
│       │   │   ├── client.py
│       │   │   └── events.py
│       │   ├── storage/
│       │   │   ├── interface.py
│       │   │   ├── local.py
│       │   │   └── s3.py
│       │   └── messaging/
│       │       ├── interface.py
│       │       └── etsy_messages.py
│       │
│       ├── assets/
│       │   ├── renderer.py
│       │   ├── screenshots.py
│       │   ├── video.py
│       │   ├── pdf.py
│       │   ├── link_validator.py
│       │   ├── design_tokens.py
│       │   └── templates/
│       │       ├── listing/
│       │       ├── pdf/
│       │       └── video/
│       │
│       ├── persistence/
│       │   ├── __init__.py
│       │   ├── database.py
│       │   ├── tables.py
│       │   ├── unit_of_work.py
│       │   └── repositories/
│       │       ├── jobs.py
│       │       ├── workflows.py
│       │       ├── events.py
│       │       ├── agents.py
│       │       ├── research.py
│       │       ├── products.py
│       │       ├── listings.py
│       │       ├── metrics.py
│       │       ├── artifacts.py
│       │       └── incidents.py
│       │
│       ├── api/
│       │   ├── __init__.py
│       │   ├── main.py
│       │   ├── dependencies.py
│       │   ├── schemas.py
│       │   └── routers/
│       │       ├── health.py
│       │       ├── workflows.py
│       │       ├── jobs.py
│       │       ├── products.py
│       │       ├── listings.py
│       │       ├── metrics.py
│       │       ├── incidents.py
│       │       ├── integrations.py
│       │       └── settings.py
│       │
│       ├── observability/
│       │   ├── logging.py
│       │   ├── telemetry.py
│       │   ├── receipts.py
│       │   └── correlation.py
│       │
│       └── cli/
│           ├── main.py
│           └── commands/
│               ├── database.py
│               ├── workflow.py
│               ├── worker.py
│               ├── scheduler.py
│               ├── integrations.py
│               └── commission.py
│
├── apps/
│   └── web/
│       ├── app/
│       │   ├── layout.tsx
│       │   ├── page.tsx
│       │   ├── pipeline/page.tsx
│       │   ├── shop/page.tsx
│       │   ├── blocked/page.tsx
│       │   ├── decisions/page.tsx
│       │   ├── incidents/page.tsx
│       │   └── settings/page.tsx
│       ├── components/
│       ├── lib/
│       ├── public/
│       ├── tests/
│       ├── package.json
│       ├── tsconfig.json
│       └── next.config.ts
│
├── migrations/
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│
├── tests/
│   ├── unit/
│   │   ├── domain/
│   │   ├── orchestration/
│   │   ├── agents/
│   │   └── assets/
│   ├── contract/
│   │   ├── agents/
│   │   └── integrations/
│   ├── integration/
│   │   ├── database/
│   │   ├── orchestration/
│   │   ├── etsy/
│   │   ├── notion/
│   │   └── posthog/
│   ├── e2e/
│   │   ├── test_happy_path.py
│   │   ├── test_cull_path.py
│   │   ├── test_multiply_path.py
│   │   ├── test_broken_link_repair.py
│   │   └── test_restart_recovery.py
│   ├── failure_injection/
│   │   ├── test_duplicate_publish.py
│   │   ├── test_expired_lease.py
│   │   ├── test_uncertain_external_effect.py
│   │   └── test_expired_credentials.py
│   └── fixtures/
│       ├── etsy/
│       ├── notion/
│       ├── research/
│       └── llm/
│
├── scripts/
│   ├── bootstrap.ps1
│   ├── bootstrap.sh
│   ├── dev.ps1
│   ├── dev.sh
│   ├── test.ps1
│   ├── test.sh
│   ├── e2e.ps1
│   ├── e2e.sh
│   ├── backup.ps1
│   ├── backup.sh
│   ├── restore.ps1
│   ├── restore.sh
│   ├── commission.ps1
│   └── commission.sh
│
├── infra/
│   ├── docker/
│   ├── caddy/
│   │   └── Caddyfile
│   └── deploy/
│       ├── install-service.sh
│       └── update.sh
│
└── runtime/
    ├── artifacts/
    ├── screenshots/
    ├── receipts/
    ├── browser-profiles/
    └── temp/
        # entire runtime directory is gitignored except optional .gitkeep files
```

## Structural rules

1. Business rules live in `domain`, not only in prompts.
2. External mutations live behind integration adapters.
3. Agent prompts are versioned source files.
4. Agent schemas are Python contracts and tests.
5. Runtime artifacts, screenshots, browser profiles and secrets never enter git.
6. The source PDF remains local and gitignored unless Omar explicitly directs otherwise.
7. The operator web app is a client of the API; it must not implement business state transitions.
8. The worker and scheduler use the same Python package as the API.
9. No agent creates its own database or private untracked state.
10. No session creates a second orchestration engine.

<!-- COPY END: 02_CANONICAL_REPOSITORY_STRUCTURE.md -->


---

<a id="part-iv"></a>

# Part IV — Session 00: Discovery and Repository Bootstrap

**Canonical source file:** `03_SESSION_00_DISCOVERY_AND_REPO_BOOTSTRAP.md`  
**SHA-256:** `207a79ffdaa903da128c678628eb4736f9977fe5c0a8d434d2b3bc4410e944ba`


### Workbook Run Record

| Field | Entry |
|---|---|
| Status | ☐ Not started |
| Date started |  |
| Date completed |  |
| Start commit |  |
| End commit |  |
| Tests / evidence |  |
| Blocker |  |
| Next action |  |

<!-- COPY START: 03_SESSION_00_DISCOVERY_AND_REPO_BOOTSTRAP.md -->

# SESSION 00 — DISCOVERY, SOURCE INGESTION AND REPOSITORY BOOTSTRAP

```text
[@Remote Desktop Commander]
[@superpowers]
[@Composio]
[@posthog]
[@product-design]
```

Execute this session under `01_MASTER_CONTROL_PROMPT.md`.

## Objective

Locate any existing implementation, adopt it if present, or create the canonical private monorepo. Ingest the playbook as the business source, establish the full repository structure and create durable cross-session checkpoints.

This session must leave a reproducible repository that Session 01 can continue immediately.

## Actions

### 1. Inspect before creating

Search the Windows and WSL2 filesystems for likely repositories or folders containing:

```text
hands-off-money-machine
money-machine
agents-to-income
etsy automation
notion template automation
Lewis Jackson
```

Inspect candidate repositories using:

- path;
- git remote;
- branch;
- recent commits;
- README;
- agent files;
- workflow/state code;
- provider integrations;
- tests.

If a credible existing implementation exists, adopt it. Do not create a duplicate. Record why it is authoritative.

### 2. Establish the canonical root

If no implementation exists, create:

```text
D:\hands-off-money-machine
```

with WSL2 access at:

```text
/mnt/d/hands-off-money-machine
```

Initialise git and create:

```text
build/full-automation
```

Create a private GitHub remote named `hands-off-money-machine` through authenticated GitHub access or `gh` when available. Never create a public repository.

If remote creation is not possible, complete the local repo and record the exact authentication blocker without stopping other work.

### 3. Inspect the environment

Record exact working versions of:

- Windows;
- WSL2 distribution;
- Git;
- GitHub CLI;
- Docker and Docker Compose;
- Python;
- `uv`;
- Node;
- `pnpm`;
- Playwright/browser availability.

Install project-local dependencies where required. Avoid unnecessary machine-wide installations.

### 4. Ingest the playbook

Make the attached playbook available locally at:

```text
private/source/The-Hands-Off-Money-Machine-Playbook.pdf
```

Keep `private/source/*.pdf` gitignored.

Calculate and record:

- filename;
- local path;
- SHA-256;
- page count;
- ingestion date.

Create `docs/source/SOURCE_REGISTER.md`.

Create source-derived documents:

```text
docs/playbook/BUSINESS_PROCESS.md
docs/playbook/CHAPTER_TO_CAPABILITY_MAP.md
docs/playbook/PROMPT_LIBRARY_MAP.md
docs/playbook/WORKBOOK_DATA_MAP.md
docs/playbook/AUTOMATION_GAP_MAP.md
```

Requirements:

- Preserve the playbook's terminology and sequence.
- Map every chapter 12–16 step and every prompt 1–13.
- Map the six workbook pages into future structured records.
- Identify manual handoffs that the software must replace.
- Do not rewrite or criticise the business model.
- Do not copy the entire copyrighted book into committed files.
- Store concise implementation-relevant derived material with chapter/page references.

### 5. Copy this prompt pack into the repository

Create:

```text
prompts/implementation/
```

Copy all prompt-pack Markdown files into it so every later session can recover from the repository.

### 6. Create the canonical scaffold

Create the full folder and file skeleton defined in `02_CANONICAL_REPOSITORY_STRUCTURE.md`.

At minimum populate now:

- `AGENTS.md`;
- `README.md`;
- `NOTICE.md`;
- `.gitignore`;
- `.editorconfig`;
- `.env.example`;
- `pyproject.toml`;
- root `package.json`;
- `pnpm-workspace.yaml`;
- `compose.yaml`;
- placeholder but valid Dockerfiles;
- `config/*.yaml` with documented example values;
- PowerShell and Bash bootstrap/dev/test scripts;
- the five control files;
- minimal Python package;
- minimal FastAPI health endpoint;
- minimal test proving import and health behaviour.

`NOTICE.md` must state that the source playbook is third-party material used as an internal business specification and is not redistributed by the repository.

### 7. Establish repository rules

`AGENTS.md` must include:

- the playbook is authoritative for business logic;
- no commercial revalidation gate;
- no duplicate repositories or orchestration engines;
- no business rules hidden only in prompts;
- no external mutation outside adapters;
- no secrets, browser profiles or source PDF in git;
- no false completion;
- preserve user changes;
- every completed session updates control files and commits;
- tests must not publish, buy or spend.

### 8. Establish initial runtime

Bring up PostgreSQL through Docker Compose.

Prove:

- the database container starts;
- the API service starts;
- `/health` returns success;
- the minimal test suite passes;
- PowerShell and Bash entry scripts are syntactically valid.

Do not build the complete schema yet; Session 02 owns that work.

### 9. Initialise control files

Set:

```text
current_session = 0
completed_sessions = [0]
next_session = 1
```

Record:

- canonical path;
- branch;
- HEAD;
- remote status;
- environment versions;
- tests;
- genuine blockers.

### 10. Review and checkpoint

Use one implementation reviewer to inspect repository coherence and one adversarial reviewer to identify:

- duplicate structure;
- missing source mappings;
- broken bootstrap commands;
- committed private files;
- path problems between Windows and WSL2.

Fix findings now.

Commit:

```text
chore(bootstrap): create hands-off money machine monorepo
```

Push when authenticated.

## Exit criteria

- Existing work was either adopted or ruled out with evidence.
- The canonical repository exists.
- The playbook is registered and locally available.
- Derived playbook documents exist.
- The complete folder scaffold exists.
- PostgreSQL and the health endpoint run.
- Minimal tests pass.
- Control files are current.
- Git commit exists.
- Working tree is clean except explicitly preserved unrelated work.

## Required exit code

```text
SESSION_00_REPOSITORY_BOOTSTRAP_COMPLETE
```

Next prompt:

```text
04_SESSION_01_PLAYBOOK_MAPPING_AND_ARCHITECTURE.md
```

<!-- COPY END: 03_SESSION_00_DISCOVERY_AND_REPO_BOOTSTRAP.md -->


---

<a id="part-v"></a>

# Part V — Session 01: Playbook Mapping and Architecture

**Canonical source file:** `04_SESSION_01_PLAYBOOK_MAPPING_AND_ARCHITECTURE.md`  
**SHA-256:** `104b890e45f84d96be48a77f6247bfb616a807ac775771f6ac6dcf1299db5ada`


### Workbook Run Record

| Field | Entry |
|---|---|
| Status | ☐ Not started |
| Date started |  |
| Date completed |  |
| Start commit |  |
| End commit |  |
| Tests / evidence |  |
| Blocker |  |
| Next action |  |

<!-- COPY START: 04_SESSION_01_PLAYBOOK_MAPPING_AND_ARCHITECTURE.md -->

# SESSION 01 — PLAYBOOK MAPPING, ARCHITECTURE AND EXECUTABLE CONTRACTS

Execute under the Master Control Prompt and recovery protocol.

## Objective

Convert the playbook-derived process into the canonical technical design that all implementation sessions will follow. Produce precise contracts and architectural decisions, then encode the first executable domain schemas and state definitions.

This session is not a prolonged planning exercise. Omar has approved the target architecture in the Master Control Prompt. Complete the design, review it and prepare the code contracts that Session 02 will implement.

## Actions

### 1. Restore exact state

Read the control files, source register, all `docs/playbook/*`, git state and current tests.

Confirm Session 00 is complete. Correct any bootstrap defect before continuing.

### 2. Complete the chapter-to-software map

For every playbook step in chapters 12–16 and prompts 1–13, record:

- source chapter/step;
- business input;
- business output;
- owning agent;
- job type;
- persisted entity;
- emitted event;
- downstream job;
- external side effect;
- retry class;
- automation mode;
- success evidence.

No playbook job may be left ownerless.

### 3. Finalise the architecture documents

Create or complete:

```text
docs/architecture/SYSTEM_OVERVIEW.md
docs/architecture/STATE_MACHINE.md
docs/architecture/DATA_MODEL.md
docs/architecture/AGENT_ROSTER.md
docs/architecture/JOB_AND_EVENT_CONTRACTS.md
docs/architecture/ARTIFACT_LINEAGE.md
docs/architecture/INTEGRATION_MATRIX.md
docs/architecture/PLATFORM_COMPATIBILITY.md
docs/architecture/AUTONOMY_MODEL.md
docs/architecture/OBSERVABILITY.md
docs/architecture/DEPLOYMENT.md
```

Use Mermaid diagrams for:

- service architecture;
- product lifecycle;
- job dependency flow;
- cull/multiply closed loop;
- broken-link incident repair;
- deployment topology.

### 4. Write the ADRs

Complete the seven ADRs defined in the repository structure:

1. modular monolith;
2. PostgreSQL durable jobs;
3. typed agent contracts;
4. provider adapters with API/Composio/browser/fixture implementations;
5. artifact lineage;
6. standing-authority autonomy configuration;
7. deterministic asset rendering.

Each ADR must state:

- decision;
- rationale;
- consequences;
- rejected alternatives;
- when the decision should be revisited.

Do not add architecture beyond the Master Control Prompt.

### 5. Define exact state and job enums

Implement initial executable code for:

- product lifecycle states;
- job states;
- agent run states;
- side-effect classes;
- retry classifications;
- decision types;
- incident types;
- event names;
- autonomy modes.

Add transition tables and tests that validate:

- all documented transitions are represented;
- impossible transitions fail;
- every terminal branch has a defined result;
- `MULTIPLY` reaches a successor workflow;
- `CULL` reaches deactivation.

### 6. Define typed contracts

Create Pydantic contracts for:

- `JobEnvelope`;
- `AgentResult`;
- `ArtifactReference`;
- `EvidenceReference`;
- `ProductSpec`;
- `ResearchReport`;
- `TeardownReport`;
- `DedupeResult`;
- `BuildResult`;
- `ProductQAResult`;
- `ListingPackage`;
- `PreflightResult`;
- `MetricsSnapshot`;
- `PortfolioDecision`;
- `IncidentResult`.

The contracts may evolve, but they must be precise enough for Session 02 schema design.

### 7. Define configuration contracts

Complete:

```text
config/product_rules.yaml
config/publishing_ramp.yaml
config/autonomy.example.yaml
config/agents.yaml
config/workflows.yaml
```

Encode the playbook defaults, including:

- 25–40 research rows target;
- five shortlisted candidates;
- 30/40 build threshold;
- one primary and one backup;
- six to eight hubs;
- three or four colour variants;
- thirteen tags;
- ten images and one video;
- two or three launch listings per week;
- fifteen-per-week cap;
- thirty-day maturity;
- bottom-80-percent cull setting;
- monthly deep pass;
- one new-front experiment per batch.

Use configuration, not undocumented magic numbers.

### 8. Integration capability assessment

Inspect currently available:

- Etsy API/client access;
- Notion API;
- Composio actions;
- connected browser profiles;
- PostHog access;
- storage options;
- LLM provider access.

For each required operation, select:

```text
DIRECT_API
COMPOSIO
BROWSER
INTERNAL_RENDERER
MANUAL_EXTERNAL_BLOCKER
```

This is an implementation capability assessment, not a business critique.

### 9. Adversarial design review

Use specialist subagents to review:

- workflow completeness;
- database normalisation and lineage;
- orchestration/restart design;
- provider adapter boundaries;
- agent contract clarity;
- operator simplicity.

Resolve every critical and high-severity finding in the documents and contract code.

### 10. Verify and checkpoint

Run:

- format;
- Ruff;
- Pyright;
- contract tests;
- transition tests;
- existing bootstrap tests.

Commit:

```text
docs(architecture): define playbook automation contracts
```

## Exit criteria

- Every playbook step maps to an agent, job, state and successor.
- Architecture and ADRs are complete and consistent.
- State, event and job enums exist in code.
- Typed contracts exist and pass validation tests.
- Configuration contains the playbook defaults.
- Integration strategy is explicit for every provider operation.
- Reviews are resolved.
- Control files and git checkpoint are current.

## Required exit code

```text
SESSION_01_ARCHITECTURE_AND_CONTRACTS_COMPLETE
```

Next prompt:

```text
05_SESSION_02_ENGINEERING_FOUNDATION_AND_DATABASE.md
```

<!-- COPY END: 04_SESSION_01_PLAYBOOK_MAPPING_AND_ARCHITECTURE.md -->


---

<a id="part-vi"></a>

# Part VI — Session 02: Engineering Foundation and Database

**Canonical source file:** `05_SESSION_02_ENGINEERING_FOUNDATION_AND_DATABASE.md`  
**SHA-256:** `dd64137dfa21792e7956d3fe4a24b449aa59625872af05c567e294eee2aad0ab`


### Workbook Run Record

| Field | Entry |
|---|---|
| Status | ☐ Not started |
| Date started |  |
| Date completed |  |
| Start commit |  |
| End commit |  |
| Tests / evidence |  |
| Blocker |  |
| Next action |  |

<!-- COPY START: 05_SESSION_02_ENGINEERING_FOUNDATION_AND_DATABASE.md -->

# SESSION 02 — ENGINEERING FOUNDATION, DATABASE AND LOCAL RUNTIME

Execute under the Master Control Prompt and recovery protocol.

## Objective

Build the production-quality engineering foundation: locked dependencies, settings, PostgreSQL schema, migrations, repositories, API/CLI skeletons, local runtime, CI and test harness.

## Actions

### 1. Restore and verify

Read control files, architecture, contracts and ADRs. Run existing tests before changing code.

### 2. Finalise project tooling

Configure:

- `uv` and locked Python dependencies;
- Ruff;
- Pyright;
- pytest;
- coverage;
- pre-commit hooks if they add no manual friction;
- pnpm workspace;
- TypeScript;
- Vitest;
- Playwright;
- GitHub Actions.

Provide equivalent PowerShell and Bash scripts for setup, development and tests.

### 3. Implement settings and environment validation

Create typed settings for:

- database;
- API;
- worker;
- scheduler;
- LLM;
- Etsy;
- Notion;
- Composio;
- PostHog;
- storage;
- browser profiles;
- autonomy;
- publication ramp;
- artifact paths.

Requirements:

- `.env.example` contains names and explanations, never credentials;
- missing required production settings fail clearly;
- test settings use fixtures and simulation;
- secret values are never logged.

### 4. Implement the PostgreSQL schema

Create SQLAlchemy tables and Alembic migrations for the logical model in the Master Control Prompt.

At minimum implement now:

```text
shops
integration_accounts
workflow_runs
jobs
job_dependencies
scheduled_triggers
events
idempotency_records
agent_definitions
agent_runs
prompt_versions
research_runs
market_listing_observations
market_shop_observations
product_candidates
competitor_purchases
teardown_reports
product_specs
products
product_variants
notion_builds
product_facts
assets
asset_links
etsy_listings
listing_versions
metrics_snapshots
experiments
decisions
incidents
customer_issues
artifacts
receipts
```

Use:

- UUID primary keys;
- UTC timestamps;
- explicit state enums or validated strings;
- uniqueness constraints for idempotency;
- indexes for ready/due jobs;
- foreign keys for lineage;
- immutable event and receipt records where appropriate;
- soft deactivation rather than destructive deletion for business records.

### 5. Implement persistence services

Build:

- async database session management;
- unit of work;
- repositories;
- transaction helpers;
- pagination;
- optimistic versioning where concurrent edits matter;
- artifact hash storage;
- event append/read;
- idempotency lookup/write.

### 6. Seed canonical configuration

Create a seed command that inserts:

- one default shop record in unconnected state;
- all sixteen agent definitions as `UNCOMMISSIONED`;
- prompt-version placeholders tied to actual prompt files;
- workflow templates;
- playbook product rules;
- autonomy configuration in simulation mode.

Do not mark unimplemented agents commissioned.

### 7. Build API and CLI skeletons

API:

- health;
- readiness;
- version;
- database status;
- workflow list/detail;
- job list/detail;
- integration status.

CLI:

```text
money-machine db upgrade
money-machine db seed
money-machine status
money-machine workflow list
money-machine job list
money-machine integrations status
```

### 8. Build Docker Compose runtime

Services:

```text
postgres
api
worker
scheduler
web
```

Worker and scheduler may initially run skeletal loops but must connect to the database and expose liveness.

Add named volumes and health checks.

### 9. CI

GitHub Actions must run:

- Python formatting check;
- Ruff;
- Pyright;
- unit tests;
- migration upgrade on a fresh PostgreSQL service;
- frontend lint/type/test;
- build checks.

### 10. Tests

At minimum prove:

- migrations upgrade from empty database;
- seed is idempotent;
- settings reject invalid modes;
- secrets are redacted;
- repository CRUD and constraints;
- event append immutability;
- idempotency uniqueness;
- API health/readiness;
- CLI status;
- Docker service health.

### 11. Review, cleanup and checkpoint

Use database and DevOps reviewers. Fix critical/high findings.

Commit:

```text
feat(foundation): add database runtime and project tooling
```

## Exit criteria

- Fresh clone/bootstrap path is documented.
- Database schema and migrations work.
- Seeds are idempotent.
- API, worker, scheduler and web containers start.
- CI configuration is complete.
- Foundation tests pass.
- Control files and commit are current.

## Required exit code

```text
SESSION_02_ENGINEERING_FOUNDATION_COMPLETE
```

Next prompt:

```text
06_SESSION_03_DURABLE_ORCHESTRATOR.md
```

<!-- COPY END: 05_SESSION_02_ENGINEERING_FOUNDATION_AND_DATABASE.md -->


---

<a id="part-vii"></a>

# Part VII — Session 03: Durable Orchestrator

**Canonical source file:** `06_SESSION_03_DURABLE_ORCHESTRATOR.md`  
**SHA-256:** `3adc85b2d98f9dca22062bd13391d55633862110d3ed1fe2afa56882f1d3f232`


### Workbook Run Record

| Field | Entry |
|---|---|
| Status | ☐ Not started |
| Date started |  |
| Date completed |  |
| Start commit |  |
| End commit |  |
| Tests / evidence |  |
| Blocker |  |
| Next action |  |

<!-- COPY START: 06_SESSION_03_DURABLE_ORCHESTRATOR.md -->

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

<!-- COPY END: 06_SESSION_03_DURABLE_ORCHESTRATOR.md -->


---

<a id="part-viii"></a>

# Part VIII — Session 04: Agent Runtime and Roster

**Canonical source file:** `07_SESSION_04_AGENT_RUNTIME_AND_ROSTER.md`  
**SHA-256:** `beb748811662b90c06098e51ab14a691f634f56900daf05c57e0fbdec0f826a3`


### Workbook Run Record

| Field | Entry |
|---|---|
| Status | ☐ Not started |
| Date started |  |
| Date completed |  |
| Start commit |  |
| End commit |  |
| Tests / evidence |  |
| Blocker |  |
| Next action |  |

<!-- COPY START: 07_SESSION_04_AGENT_RUNTIME_AND_ROSTER.md -->

# SESSION 04 — AGENT RUNTIME, PROMPT REGISTRY AND COMPLETE ROSTER

Execute under the Master Control Prompt and recovery protocol.

## Objective

Build the shared runtime that executes all logical agents through typed contracts, versioned prompts and explicit tool permissions. Register the complete roster and commission only the runtime capabilities genuinely implemented in this session.

## Actions

### 1. Implement provider abstraction

Create:

- `LLMProvider` interface;
- current OpenAI-compatible provider;
- deterministic fake provider;
- structured-output validator;
- timeout handling;
- retry for transport/schema errors;
- token/cost metadata where available;
- prompt/model version recording.

Inspect current official provider documentation before writing version-specific calls.

### 2. Implement prompt store

Every agent prompt must be:

- stored in `src/money_machine/agents/prompts`;
- versioned;
- hashable;
- referenced by `prompt_versions`;
- loadable by ID;
- testable for required sections;
- free of runtime secrets.

Adapt the playbook's prompts into agent system prompts while preserving their business logic.

### 3. Implement agent base and registry

Create:

- `AgentDefinition`;
- `AgentContext`;
- `BaseAgent`;
- `AgentRegistry`;
- `ToolRegistry`;
- `AgentRunner`;
- structured result validation;
- run receipts;
- error capture;
- commissioning state.

### 4. Implement tool permissions

Each agent receives only relevant tools.

Examples:

- Research: Etsy read/browser, web capture, storage.
- Builder: Notion and asset tools.
- Publisher: Etsy mutation tools.
- Analytics: Etsy stats read.
- Support: Etsy messages, Notion repair and listing update.
- Orchestrator: no direct provider mutations; it creates jobs.

Do not let agents call one another directly. They return results to the orchestrator.

### 5. Register all sixteen agents

Populate `config/agents.yaml` and the database with:

- ID;
- name;
- purpose;
- input contract;
- output contract;
- prompt path/version;
- allowed tools;
- side-effect class;
- timeout;
- max attempts;
- commissioning state.

Implement real working versions now for:

- A01 Shop Orchestrator;
- A02 Account & Integration diagnostics;
- shared deterministic rule agents that do not require external providers.

Register later-domain agents as `UNCOMMISSIONED`, not fake-complete.

### 6. Implement subagent review support

Allow an agent implementation to request bounded internal specialist reviews through the LLM provider, but ensure:

- the owning job remains singular;
- reviews are attached as artifacts;
- reviews do not mutate provider state;
- final structured output comes from the owning agent;
- cost and run count are recorded.

### 7. Implement agent-run observability

Store:

- job;
- agent;
- input hash;
- prompt version;
- model;
- start/end;
- status;
- structured output;
- validation errors;
- tool calls;
- artifacts;
- cost/usage where available.

Emit local structured logs and PostHog-compatible events, even before live PostHog connection.

### 8. Contract tests

For every roster entry prove:

- prompt exists;
- schema imports;
- config validates;
- allowed tools resolve;
- side-effect class is declared;
- fake provider can produce a valid result;
- malformed output fails closed;
- uncommissioned agent cannot execute a production job.

### 9. Runtime integration tests

Prove:

- orchestrator leases an agent job;
- agent runner executes;
- result persists;
- event emits;
- successor creates;
- failed schema output retries appropriately;
- final invalid result fails the job;
- restart retains the run history.

### 10. Review and checkpoint

Use an agent-systems reviewer and prompt-contract reviewer. Fix critical/high findings.

Commit:

```text
feat(agents): add typed runtime and full agent registry
```

## Exit criteria

- Provider abstraction works.
- Prompt registry and hashes work.
- Agent runner integrates with durable jobs.
- All sixteen agents are registered.
- Unimplemented agents are honestly uncommissioned.
- Contract and runtime tests pass.
- Control files and commit are current.

## Required exit code

```text
SESSION_04_AGENT_RUNTIME_COMPLETE
```

Next prompt:

```text
08_SESSION_05_MARKET_RESEARCH_TO_PRODUCT_SPEC.md
```

<!-- COPY END: 07_SESSION_04_AGENT_RUNTIME_AND_ROSTER.md -->


---

<a id="part-ix"></a>

# Part IX — Session 05: Market Research to ProductSpec

**Canonical source file:** `08_SESSION_05_MARKET_RESEARCH_TO_PRODUCT_SPEC.md`  
**SHA-256:** `e7df623562b0cc4a79e1440c19a11258115c05fcfccea10d9e8b5f348e723db5`


### Workbook Run Record

| Field | Entry |
|---|---|
| Status | ☐ Not started |
| Date started |  |
| Date completed |  |
| Start commit |  |
| End commit |  |
| Tests / evidence |  |
| Blocker |  |
| Next action |  |

<!-- COPY START: 08_SESSION_05_MARKET_RESEARCH_TO_PRODUCT_SPEC.md -->

# SESSION 05 — MARKET RESEARCH TO PRODUCT SPECIFICATION VERTICAL SLICE

Execute under the Master Control Prompt and recovery protocol.

## Objective

Implement and commission the complete front half of the playbook:

```text
market research
→ evidence grid
→ niche shortlist
→ Low-Ticket score
→ primary and backup
→ competitor teardown
→ ProductSpec
→ dedupe or reconcept
```

This session must end with a fully linked vertical slice that can produce a dedupe-passed ProductSpec without manual copy/paste.

## Actions

### 1. Implement Etsy research adapters

Complete the Etsy read/research interface with:

- fixture adapter;
- browser adapter;
- direct API or Composio read actions where they genuinely support the requirement.

Capture:

- search phrase;
- rank/page;
- title;
- current price;
- anchor/crossed-out price;
- shop;
- shop sales;
- approximate shop age;
- badges;
- basket/urgency signals where visible;
- review signals;
- identity niche;
- base category;
- visual positioning;
- source URL;
- screenshot/evidence timestamp.

Use the ten seed phrases from the playbook as default configuration.

### 2. Implement A03 Market Research Agent

The agent must:

- execute configured searches;
- target 25–40 useful rows;
- identify young-and-fast shops;
- persist raw observations;
- create a `ResearchReport`;
- expose thin evidence instead of inventing values;
- emit `RESEARCH_COMPLETED`.

### 3. Implement shortlist analysis

Extract:

- every visible identity × category combination;
- evidence for each;
- price bands;
- young-fast patterns;
- five strongest candidates;
- one risk per candidate.

Persist candidates.

### 4. Implement Low-Ticket scoring

A05 Product Strategy Agent must score each candidate out of 40 using the playbook's four checks.

Rules:

- under 30 fails;
- rank the candidates;
- select primary and backup;
- keep reasoning concise and source-linked;
- emit `PRODUCT_QUALIFIED` or `PRODUCT_REJECTED`.

### 5. Implement competitor purchase and teardown workflow

Support:

- configured bounded purchase job;
- manual external completion when authentication/payment challenge requires Omar;
- receipt/reference capture;
- uploaded or downloaded competitor files;
- structural teardown;
- delivery anatomy;
- buyer journey;
- product architecture;
- variant delivery;
- backend bridge;
- professional standard;
- gaps.

Do not copy competitor text, designs or files into generated products.

Where the purchase is disabled, fixture teardown must keep test workflows runnable. Production workflow remains blocked only at the actual paid action.

### 6. Implement ProductSpec generation

Generate and persist:

- identity niche;
- base category;
- mass/premium tier;
- real price;
- anchor;
- palette name and tokens;
- working title;
- six to eight hubs;
- shared databases;
- flagship feature;
- page/feature targets;
- variants;
- experiment hypothesis;
- experiment tags;
- source research and teardown references;
- version.

### 7. Implement A06 Catalogue Dedupe Agent

Use deterministic rules plus semantic comparison.

Return:

```text
PASS
TOO_CLOSE
```

If too close:

- identify the conflict;
- create three genuine reconcept options;
- create `RECONCEPT_PRODUCT`;
- generate a revised ProductSpec;
- rerun dedupe automatically.

Do not allow title-only evasion.

### 8. Link the workflow

Prove automatic chaining:

```text
RUN_MARKET_RESEARCH
→ ANALYZE_RESEARCH
→ SCORE_CANDIDATES
→ RUN_TEARDOWN
→ CREATE_PRODUCT_SPEC
→ CHECK_DEDUPE
→ BUILD_NOTION_TEMPLATE ready
```

No manual content transfer.

### 9. Tests

Use fixtures to prove:

- 25–40-row grid construction;
- thin evidence handling;
- five-candidate shortlist;
- candidate under 30 rejected;
- primary and backup selected;
- teardown output;
- ProductSpec validation;
- duplicate concept rejected;
- reconcept loop;
- successor build job creation;
- restart recovery mid-research.

Run an optional live read-only smoke against Etsy if browser access is available, without publication or purchase.

### 10. Commission agents

Mark A03, A04, A05 and A06 `COMMISSIONED` only after real implementations and tests pass. A04 may be commissioned with purchase awaiting configured credentials if its full fixture and ingestion paths work and the exact live blocker is recorded.

### 11. Review and checkpoint

Use a product-strategy reviewer and data-evidence reviewer. Fix findings.

Commit:

```text
feat(research): automate niche research through dedupe
```

## Exit criteria

- Research through dedupe works as one linked workflow.
- All outputs are persisted.
- ProductSpec is versioned and evidence-linked.
- Dedupe automatically reconcepts.
- Build job is created after pass.
- Relevant agents are commissioned.
- Tests and control files are current.

## Required exit code

```text
SESSION_05_RESEARCH_TO_SPEC_COMPLETE
```

Next prompt:

```text
09_SESSION_06_NOTION_INTEGRATION_FOUNDATION.md
```

<!-- COPY END: 08_SESSION_05_MARKET_RESEARCH_TO_PRODUCT_SPEC.md -->


---

<a id="part-x"></a>

# Part X — Session 06: Notion Integration Foundation

**Canonical source file:** `09_SESSION_06_NOTION_INTEGRATION_FOUNDATION.md`  
**SHA-256:** `7ef25c4fb6bd00bcd85a1996e4b8ce5de4442b369cca4066dca3dbb38b1c3df9`


### Workbook Run Record

| Field | Entry |
|---|---|
| Status | ☐ Not started |
| Date started |  |
| Date completed |  |
| Start commit |  |
| End commit |  |
| Tests / evidence |  |
| Blocker |  |
| Next action |  |

<!-- COPY START: 09_SESSION_06_NOTION_INTEGRATION_FOUNDATION.md -->

# SESSION 06 — NOTION INTEGRATION FOUNDATION

Execute under the Master Control Prompt and recovery protocol.

## Objective

Build the reliable Notion action layer required to construct complete templates automatically. This session owns authentication, API/browser capability selection, reusable operations, reconciliation and fixture parity. Session 07 will use it to build the actual products.

## Actions

### 1. Inspect current Notion capabilities

Inspect:

- current official Notion API;
- connected Composio Notion actions;
- existing authenticated browser profiles;
- any current Notion MCP or integration;
- limitations around views, formulas, relations, rollups, sharing, publishing and duplicate-as-template.

Update `docs/architecture/PLATFORM_COMPATIBILITY.md`.

For every required operation choose one implementation:

```text
DIRECT_API
COMPOSIO
BROWSER
COMBINED
```

Do not redesign the product because an API lacks a UI feature. Use the browser adapter for the missing operation.

### 2. Implement adapter interfaces

Implement `NotionAdapter` operations for:

- connection status;
- workspace discovery;
- top-level page creation;
- page duplication;
- page rename;
- page move to top level;
- icons;
- covers;
- text and callout blocks;
- database creation;
- properties;
- relations;
- rollups;
- formulas;
- linked database views;
- filters;
- sorts;
- calendar/table/board views;
- view-title visibility;
- child pages;
- public publishing;
- duplicate-as-template setting;
- search-indexing setting;
- public URL retrieval;
- unpublish;
- page/database inspection;
- stranger/private-view verification.

Implement:

- direct API adapter;
- browser adapter;
- fixture adapter;
- adapter router that selects the correct method per operation.

### 3. Implement browser session management

Support:

- persistent browser profiles outside git;
- authenticated profile status;
- controlled reuse;
- screenshot capture on error;
- selector abstraction;
- timeout and retry;
- reconciliation after uncertain clicks;
- CAPTCHA/verification detection;
- safe restart;
- one operation receipt per mutation.

Never store browser cookies or profiles in git.

### 4. Implement Notion operation receipts

Every mutation records:

- job ID;
- operation;
- workspace;
- page/database target;
- pre-state when available;
- post-state;
- provider response;
- screenshot or response evidence;
- timestamp;
- idempotency key;
- status.

### 5. Implement formula and schema builders

Create reusable builders for:

- Tasks;
- Events;
- Habits;
- Finance;
- Meals;
- Notes;
- business alternatives:
  - Clients;
  - Projects;
  - Content;
  - Invoices.

Implement the notification-dashboard formula-generation service using verified property names.

Do not bury database definitions in one agent prompt.

### 6. Implement relation and linked-view helpers

Support:

- one canonical database per data type;
- hub views linked to canonical databases;
- filters by date/category/status;
- dashboard today view;
- monthly calendar;
- quick notes;
- relation/rollup setup for the one-row notification dashboard.

### 7. Implement publishing and isolation helpers

Support:

- ensure page is top level;
- publish to web;
- duplicate as template on;
- search indexing off;
- capture secret link;
- verify public access;
- verify no unintended navigation to other catalogue pages.

### 8. Fixture parity

The fixture adapter must model:

- pages;
- databases;
- properties;
- views;
- filters;
- relations;
- public links;
- duplication behaviour;
- broken/no-access states.

Tests for Session 07 must run entirely against fixtures.

### 9. Live connection path

Implement `money-machine integrations notion connect/status/test`.

When a live account is available, run only safe sandbox operations:

- create a temporary test page;
- create a small database;
- publish/unpublish;
- delete or archive the temporary page after evidence is captured.

Do not create a production product in this session.

### 10. Tests

Prove:

- adapter routing;
- API and browser contract parity;
- browser profile recovery;
- idempotent create;
- uncertain click reconciliation;
- relation/rollup creation;
- linked-view creation;
- publish settings;
- isolation verification;
- fixture duplication;
- safe temporary cleanup.

### 11. Review and checkpoint

Use a Notion-integration reviewer and browser-automation reviewer. Fix brittle selectors and missing reconciliation.

Commit:

```text
feat(notion): add complete product-building action layer
```

## Exit criteria

- Every Notion operation required by the playbook has an adapter path.
- Fixture adapter is complete enough for full product E2E.
- Browser sessions and receipts work.
- Live sandbox smoke runs where credentials are available.
- Session 07 can build through a stable interface.
- Control files and commit are current.

## Required exit code

```text
SESSION_06_NOTION_INTEGRATION_COMPLETE
```

Next prompt:

```text
10_SESSION_07_PRODUCT_BUILD_VARIANTS_AND_QA.md
```

<!-- COPY END: 09_SESSION_06_NOTION_INTEGRATION_FOUNDATION.md -->


---

<a id="part-xi"></a>

# Part XI — Session 07: Product Build, Variants and QA

**Canonical source file:** `10_SESSION_07_PRODUCT_BUILD_VARIANTS_AND_QA.md`  
**SHA-256:** `d52011a6f0b725b16427629dc664cfc9f3432c4b5f71d26ce032d4b6c8ecb39d`


### Workbook Run Record

| Field | Entry |
|---|---|
| Status | ☐ Not started |
| Date started |  |
| Date completed |  |
| Start commit |  |
| End commit |  |
| Tests / evidence |  |
| Blocker |  |
| Next action |  |

<!-- COPY START: 10_SESSION_07_PRODUCT_BUILD_VARIANTS_AND_QA.md -->

# SESSION 07 — NOTION PRODUCT BUILD, COLOUR VARIANTS AND PRODUCT QA

Execute under the Master Control Prompt and recovery protocol.

## Objective

Implement and commission the agents that turn a dedupe-passed ProductSpec into a complete, tested, published-to-web Notion product with three or four isolated variants and verified secret links.

## Actions

### 1. Implement A07 Notion Product Builder Agent

Consume only a validated ProductSpec.

Build in phases:

```text
1. top-level page and design shell
2. shared databases
3. dashboard and navigation
4. identity-specific hubs
5. notification dashboard
6. aesthetics and content completion
```

Persist phase progress so a crash resumes from the next incomplete operation.

### 2. Build shared databases

For mass-market planner products, implement the playbook defaults:

- Tasks;
- Events;
- Habits;
- Finance;
- Meals;
- Notes.

For business products, adapt using ProductSpec:

- Clients;
- Projects;
- Content;
- Invoices;
- Tasks;
- Notes.

Every hub uses linked views of canonical databases. Never create accidental duplicate data stores.

### 3. Build the home dashboard

Include:

- palette cover/header;
- greeting;
- notification dashboard;
- hub navigation;
- today's priorities;
- monthly event calendar;
- quick notes;
- identity-appropriate callouts.

### 4. Build the notification dashboard

Create the one-row database and verified relations/rollups/formula needed to display:

- configured buyer name;
- current date;
- open tasks due today;
- birthday status;
- money spent today;
- water glasses remaining where relevant.

Only include ProductSpec-supported claims.

Seed enough sample data to make screenshots understandable, while clearly distinguishing sample/demo content from buyer data.

### 5. Build six to eight hubs

Each hub must include:

- two to five linked/filtered views;
- two to four useful static pages or sections;
- identity-specific vocabulary;
- no generic filler copied across every product;
- coherent navigation back to the dashboard.

### 6. Implement progress and repair

Persist:

- completed operations;
- deferred operations;
- created Notion IDs;
- property mappings;
- page counts;
- formula state.

When an operation fails:

- capture screenshot/provider response;
- create a repair job;
- resume after repair;
- do not rebuild the whole product unless required.

### 7. Implement A08 Variant Builder Agent

Create three or four total variants.

For each:

- duplicate the complete top-level product;
- rename;
- apply palette tokens;
- change covers, accents, callouts and icons;
- preserve structure;
- apply genuine section/vocabulary differences for identity variants;
- publish as a separate top-level page;
- enable duplicate-as-template;
- disable search indexing;
- record secret link.

### 8. Implement A09 Product QA Agent

QA must verify:

- ProductSpec coverage;
- expected shared databases;
- no unintended duplicate databases;
- all hubs present;
- linked views point to the correct canonical databases;
- formulas compile;
- notification dashboard values update;
- page/subpage count;
- variant count;
- public links load;
- duplicate button appears;
- fresh duplicate works;
- no `No access` blocks;
- no cross-catalogue access;
- palette consistency;
- teardown quality bar;
- product facts are extracted and persisted.

Return:

```text
PASS
FAIL_REPAIRABLE
BLOCKED
```

`FAIL_REPAIRABLE` creates targeted repair jobs and reruns QA automatically.

### 9. Product fact ledger

Persist verified facts used downstream:

- actual page count;
- actual hubs;
- actual databases;
- actual variants;
- actual colour names;
- actual dashboard outputs;
- actual supported devices if verified;
- secret links;
- free-update policy if configured;
- build version.

Merchandising may only claim facts from this ledger.

### 10. Link the workflow

Prove:

```text
DEDUPE_PASSED
→ BUILD_NOTION_TEMPLATE
→ RUN_PRODUCT_QA
→ REPAIR as required
→ CREATE_VARIANTS
→ RUN_VARIANT_QA
→ GENERATE_LISTING_PACKAGE ready
```

### 11. Tests

Use fixture Notion to prove:

- complete mass-market build;
- complete business build;
- crash and resume at every phase;
- broken formula repair;
- wrong linked-view repair;
- missing sub-page repair;
- four variants;
- public link and isolation;
- fresh duplicate;
- product fact extraction;
- automatic successor creation.

Run one live sandbox build where credentials permit. Clean up temporary test products after capturing evidence. Do not publish an Etsy listing.

### 12. Commission agents

Mark A07, A08 and A09 commissioned only after full implementation and tests.

### 13. Review and checkpoint

Use product-architecture, Notion and QA reviewers. Fix all critical/high findings.

Commit:

```text
feat(products): automate Notion builds variants and QA
```

## Exit criteria

- A valid ProductSpec becomes a working multi-variant Notion product.
- QA repair loops are automatic.
- Secret links and product facts persist.
- Downstream merchandising job is created.
- Agents are commissioned.
- Tests, evidence and control files are current.

## Required exit code

```text
SESSION_07_PRODUCT_BUILD_AND_QA_COMPLETE
```

Next prompt:

```text
11_SESSION_08_MERCHANDISING_AND_ASSET_FACTORY.md
```

<!-- COPY END: 10_SESSION_07_PRODUCT_BUILD_VARIANTS_AND_QA.md -->


---

<a id="part-xii"></a>

# Part XII — Session 08: Merchandising and Asset Factory

**Canonical source file:** `11_SESSION_08_MERCHANDISING_AND_ASSET_FACTORY.md`  
**SHA-256:** `a7a406cecd9c93efdec1045f394b911e614cd79366840e33d5c53d9968f7cd33`


### Workbook Run Record

| Field | Entry |
|---|---|
| Status | ☐ Not started |
| Date started |  |
| Date completed |  |
| Start commit |  |
| End commit |  |
| Tests / evidence |  |
| Blocker |  |
| Next action |  |

<!-- COPY START: 11_SESSION_08_MERCHANDISING_AND_ASSET_FACTORY.md -->

# SESSION 08 — MERCHANDISING, LISTING COPY AND AUTOMATED ASSET FACTORY

Execute under the Master Control Prompt and recovery protocol.

## Objective

Implement and commission the agents that turn verified product facts into the complete Etsy listing package: title, description, thirteen tags, ten images, short video and delivery PDFs. Eliminate manual Canva and copy/paste work while preserving the playbook's intended outputs.

## Actions

### 1. Implement A10 Merchandising Agent

Inputs:

- ProductSpec;
- ProductFacts;
- hub list;
- page count;
- actual variants;
- actual notification-dashboard behaviour;
- shop name;
- price/anchor;
- support and free-gift configuration.

Outputs:

- title;
- eight-part description;
- exactly thirteen tags;
- hero copy;
- image-strip copy;
- video sequence;
- price/sale data;
- claim list with fact references.

Preserve the playbook's listing structure.

### 2. Implement claim validation

Every generated claim must reference a ProductFact.

Reject:

- invented page counts;
- nonexistent features;
- variant names not built;
- unsupported automation claims;
- invented reviews;
- invented sales;
- invented trust bars;
- unsupported social proof.

A claim-validation failure returns the copy to the merchandising agent with exact corrections.

### 3. Build the design-token system

Create reusable visual tokens for:

- palette;
- typography;
- spacing;
- cards;
- device frames;
- icons;
- hero layout;
- hub slide;
- colour options;
- how-it-works;
- device compatibility;
- PDF pages.

Product Design should review the system for coherence and usability, not redesign the business.

### 4. Implement A11 Creative Asset Agent

Build deterministic HTML/CSS/SVG templates rendered with Playwright.

Generate:

#### Ten listing images

1. Hero.
2. Product walkthrough/overview still.
3–7. Strongest hubs/sections.
8. Colour options.
9. Devices.
10. How it works.

Use actual product screenshots and actual page count.

#### Short video

Create a roughly thirty-second walkthrough from product screenshots or automated screen capture:

- dashboard;
- notification panel;
- strongest hubs;
- colour options;
- duplication/access.

No voiceover required.

#### README/access PDF

Two pages:

- page one: setup in three steps plus configured widgets/resources;
- page two: colour/variant access links, duplication reminder, support and review request.

#### Optional free-gift PDF

One page with configured free email-list gift and optional free community.

No paid checkout links.

### 5. Implement screenshot acquisition

Automate screenshots from each Notion variant:

- consistent viewport;
- no browser chrome;
- wait for loaded content;
- stable crop;
- sensitive/sample data rules;
- screenshot hash and source build version.

### 6. Implement link injection and validation

After PDF export:

- inspect every embedded link;
- open each variant link;
- verify correct variant;
- verify public access;
- verify duplicate button;
- record result.

A failed link creates a targeted asset-repair job.

### 7. Artifact lineage

Each asset stores:

- product ID;
- ProductSpec version;
- build version;
- source screenshots;
- merchandising version;
- renderer template version;
- hash;
- dimensions/page count;
- QA status;
- storage URI.

A later product change must invalidate stale dependent assets.

### 8. Asset storage

Implement:

- local runtime storage for development;
- S3-compatible adapter for production;
- immutable versioned paths;
- signed/internal retrieval where required;
- cleanup of superseded temporary renders without deleting published evidence.

### 9. Workflow linkage

Prove:

```text
PRODUCT_QA_PASSED
→ GENERATE_LISTING_COPY
→ VALIDATE_CLAIMS
→ CAPTURE_SCREENSHOTS
→ RENDER_LISTING_IMAGES
→ RENDER_VIDEO
→ RENDER_DELIVERY_PDFS
→ VALIDATE_LINKS
→ ASSET_QA_PASSED
→ CREATE_ETSY_DRAFT ready
```

### 10. Tests

Prove:

- exactly thirteen tags;
- description has eight sections;
- unsupported claim rejection;
- all ten images render;
- PDF page counts;
- embedded link extraction;
- wrong-link repair;
- video render;
- asset invalidation after product version change;
- deterministic render hashes for same inputs;
- fixture and real screenshot paths;
- successor draft job creation.

### 11. Commission agents

Mark A10 and A11 commissioned after tests and real output inspection.

### 12. Review and checkpoint

Use product-design, copy-quality and asset-engineering reviewers. Inspect rendered files visually and fix issues.

Commit:

```text
feat(assets): generate complete Etsy merchandising package
```

## Exit criteria

- A verified product automatically produces the complete listing package.
- No manual Canva assembly is required.
- Claims are fact-bound.
- All links are tested.
- Assets are versioned and inspectable.
- Etsy draft job is automatically ready.
- Agents are commissioned.
- Tests and control files are current.

## Required exit code

```text
SESSION_08_MERCHANDISING_AND_ASSETS_COMPLETE
```

Next prompt:

```text
12_SESSION_09_ETSY_DRAFT_PUBLISH_AND_PREFLIGHT.md
```

<!-- COPY END: 11_SESSION_08_MERCHANDISING_AND_ASSET_FACTORY.md -->


---

<a id="part-xiii"></a>

# Part XIII — Session 09: Etsy Draft, Publish and Preflight

**Canonical source file:** `12_SESSION_09_ETSY_DRAFT_PUBLISH_AND_PREFLIGHT.md`  
**SHA-256:** `eab1e4a5ae05008e06607526a1bf45b0fb35850a5bbf82e4002bd94954f58936`


### Workbook Run Record

| Field | Entry |
|---|---|
| Status | ☐ Not started |
| Date started |  |
| Date completed |  |
| Start commit |  |
| End commit |  |
| Tests / evidence |  |
| Blocker |  |
| Next action |  |

<!-- COPY START: 12_SESSION_09_ETSY_DRAFT_PUBLISH_AND_PREFLIGHT.md -->

# SESSION 09 — ETSY DRAFT, PREFLIGHT, PUBLICATION AND POST-PUBLISH QA

Execute under the Master Control Prompt and recovery protocol.

## Objective

Implement and commission the complete Etsy commerce path: authenticated adapter, draft assembly, exact preflight, publication-ramp enforcement, live publication capability, post-publish verification, updates and deactivation.

## Actions

### 1. Inspect current Etsy capabilities

Inspect:

- official Etsy API;
- connected Composio actions;
- authenticated browser availability;
- current listing form;
- current media/file limits;
- stats and message access;
- OAuth/token requirements.

Update the integration matrix and platform-compatibility document.

Use direct API where complete, browser automation where necessary and fixtures for tests.

### 2. Implement Etsy adapter

Support:

- shop/account status;
- category and attribute discovery;
- draft create;
- digital-product setting;
- title;
- description;
- thirteen tags;
- price;
- quantity 999;
- images;
- video;
- delivery PDFs;
- sale/discount configuration;
- save as draft;
- inspect draft;
- publish;
- inspect active listing;
- update listing;
- replace files;
- deactivate;
- retrieve metrics;
- retrieve messages where available.

### 3. Implement mutation receipts and reconciliation

Every external mutation records:

- operation;
- listing target;
- pre-state;
- expected post-state;
- provider ID;
- response;
- screenshot/API evidence;
- idempotency key;
- final status.

On timeout:

- inspect Etsy before retry;
- reconcile draft/listing state;
- never create duplicate listings blindly.

### 4. Implement A13 Etsy Publishing Agent

The agent consumes a complete, QA-passed ListingPackage.

It must:

- create or reuse the idempotent draft;
- upload every asset;
- set all fields;
- verify quantity and price;
- apply sale configuration;
- save as draft;
- emit `DRAFT_CREATED`.

No publication before A12 preflight passes.

### 5. Implement A12 Preflight Agent

Automate the playbook checklist:

- final PDFs attached;
- every exported PDF link passed today;
- each colour link reaches correct variant;
- free-gift links are configured correctly;
- each variant is top-level and isolated;
- duplicate-as-template on;
- indexing off;
- listing is digital;
- quantity high;
- ten photos present and hero first;
- video present;
- title, description and thirteen tags complete;
- every claim is fact-backed;
- price and sale yield intended buyer price;
- draft is internally consistent.

Return:

```text
PASS
REPAIR_REQUIRED
BLOCKED
```

Repair findings create precise downstream jobs and return automatically to preflight.

### 6. Implement publication ramp

Use `publishing_ramp.yaml`.

Support:

- shop age;
- listings published this week;
- configured weekly cap;
- starting cap of two or three;
- gradual increases;
- absolute cap of fifteen;
- next permissible publication time.

A preflight-passed listing waits as `READY_TO_PUBLISH` if the ramp is full.

### 7. Implement live publication

Production modes:

```text
simulation  no provider mutation
draft       create and verify drafts only
live        publish automatically after pass and ramp
```

In live mode with `auto_publish: true`, no per-listing approval is required.

### 8. Implement post-publish verification

After publish:

- confirm Active;
- verify public URL;
- verify price/sale display;
- verify media;
- download/open delivery files where possible;
- verify links;
- capture publication timestamp;
- calculate `maturity_at = published_at + 30 days`;
- create weekly metrics schedule;
- create maturity trigger;
- emit `POST_PUBLISH_VERIFIED`.

Support the playbook's live checkout test behind:

```text
live_checkout_test_enabled
live_checkout_test_cap
```

Implement the capability without performing a live payment in tests.

### 9. Implement update and deactivation

Support:

- replace broken delivery PDF;
- update copy/assets;
- repair price;
- deactivate listing;
- preserve listing-version history;
- verify resulting provider state.

### 10. Workflow linkage

Prove:

```text
ASSET_QA_PASSED
→ CREATE_ETSY_DRAFT
→ RUN_PREFLIGHT
→ REPAIR as required
→ WAIT_FOR_RAMP if required
→ PUBLISH_ETSY_LISTING
→ POST_PUBLISH_VERIFY
→ SCHEDULE_WEEKLY_METRICS
→ SCHEDULE_30_DAY_MATURITY
```

### 11. Tests

Prove:

- complete fixture draft;
- missing asset preflight failure;
- wrong link repair;
- unsupported claim failure;
- ramp wait and release;
- idempotent draft;
- duplicate publish suppression;
- timeout reconciliation;
- post-publish schedules;
- update file;
- deactivate;
- simulation, draft and live-mode behaviour without real side effects.

Run a live draft smoke when credentials are available. Do not publish live unless the configured production authority already explicitly allows it.

### 12. Commission agents

Mark A12 and A13 commissioned after implementation and tests.

### 13. Review and checkpoint

Use Etsy-integration, external-side-effect and preflight reviewers. Fix findings.

Commit:

```text
feat(etsy): automate drafts preflight and publication
```

## Exit criteria

- Full Etsy draft package is created automatically.
- Preflight is executable and repairs loop back.
- Publication ramp works.
- Live auto-publication capability exists.
- Post-publish schedules are automatic.
- Duplicate external effects are prevented.
- Agents are commissioned.
- Tests and control files are current.

## Required exit code

```text
SESSION_09_ETSY_PUBLISHING_COMPLETE
```

Next prompt:

```text
13_SESSION_10_ANALYTICS_CULL_MULTIPLY_CLOSED_LOOP.md
```

<!-- COPY END: 12_SESSION_09_ETSY_DRAFT_PUBLISH_AND_PREFLIGHT.md -->


---

<a id="part-xiv"></a>

# Part XIV — Session 10: Analytics, Cull, Multiply and Closed Loop

**Canonical source file:** `13_SESSION_10_ANALYTICS_CULL_MULTIPLY_CLOSED_LOOP.md`  
**SHA-256:** `250a666a2e0e81790066b96caaf0f017fde59027cc2921b1417ea71c99677e7a`


### Workbook Run Record

| Field | Entry |
|---|---|
| Status | ☐ Not started |
| Date started |  |
| Date completed |  |
| Start commit |  |
| End commit |  |
| Tests / evidence |  |
| Blocker |  |
| Next action |  |

<!-- COPY START: 13_SESSION_10_ANALYTICS_CULL_MULTIPLY_CLOSED_LOOP.md -->

# SESSION 10 — ANALYTICS, THIRTY-DAY MATURITY, CULL AND MULTIPLY CLOSED LOOP

Execute under the Master Control Prompt and recovery protocol.

## Objective

Complete the business loop. Implement weekly metrics, thirty-day maturity, mature-listing diagnosis, culling, winner multiplication, monthly deep pass and automatic successor-product execution.

This session is the central proof that the system is autonomous rather than a listing generator.

## Actions

### 1. Implement metrics collection

Collect and persist, per listing:

- publish date;
- days live;
- weekly views;
- weekly favourites;
- weekly sales/orders;
- cumulative views;
- cumulative favourites;
- cumulative sales/orders;
- any additional Etsy stats available;
- collection timestamp;
- provider evidence.

Do not replace the playbook's scorecard; extend it only where useful.

### 2. Implement weekly scheduler

On the configured loop day:

- create one collection job per active listing;
- create one shop review job after all collection jobs complete;
- suppress duplicate weekly runs;
- preserve historical snapshots;
- emit `METRICS_CAPTURED`.

### 3. Implement A14 Analytics Agent

Rules:

- under thirty days: `TOO_YOUNG`, no demand verdict;
- defects may be flagged immediately;
- mature listings are ranked;
- low visibility diagnosis targets title/tags/niche;
- views without sales diagnosis targets price/hero/description;
- evidence must reference actual metrics.

Return:

```text
TOO_YOUNG
HOLD
REPAIR
CULL_CANDIDATE
MULTIPLY_CANDIDATE
```

### 4. Implement maturity scheduling

Publication creates one durable trigger at:

```text
published_at + 30 days
```

On maturity:

- mark listing mature;
- collect fresh metrics;
- create evaluation job;
- never depend on an in-memory delay.

### 5. Implement A15 Cull & Multiply Agent

Apply the playbook's configured portfolio rules.

#### Cull

- rank mature listings;
- identify bottom performers;
- support default bottom-80-percent discipline;
- create deactivation jobs;
- log the experiment lesson;
- retain data and artifacts;
- emit `LISTING_CULLED`.

#### Multiply

Generate one or more specific successor proposals:

- close identity variant;
- new palette;
- adjacent category;
- genuinely different section mix;
- fresh-niche experiment.

Each proposal must become a versioned ProductSpec candidate and pass dedupe.

A `MULTIPLY` decision must automatically create:

```text
CREATE_SUCCESSOR_SPEC
→ CHECK_DEDUPE
→ BUILD_NOTION_TEMPLATE
```

Do not stop at a recommendation report.

### 6. Maintain exploration

For each production batch:

- prioritise variants of proven winners;
- reserve approximately one slot for a new-front experiment from fresh research;
- keep publication inside the ramp.

### 7. Implement monthly deep pass

Every fourth weekly loop:

- full mature-listing cull review;
- fresh mini-research;
- seasonal look-ahead;
- discount/price review;
- milestone update;
- new-front candidate creation.

This must create jobs automatically.

### 8. Implement milestone tracking

Persist:

- accounts connected;
- first niche selected;
- teardown complete;
- first template complete;
- first listing live;
- checkout test complete if enabled;
- first favourite;
- first sale;
- first review;
- first cull;
- first multiplied winner;
- first £100 total;
- first month under one hour of operator intervention where measurable.

### 9. Closed-loop E2E tests

Simulate:

#### Winner path

```text
published
→ weekly metrics
→ 30 days
→ winner detected
→ successor ProductSpec
→ dedupe pass
→ new build job
```

#### Loser path

```text
published
→ 30 days
→ cull
→ deactivation job
→ deactivated
→ lesson persisted
```

#### Hold path

```text
mature
→ hold
→ future weekly collection remains scheduled
```

#### Repair path

```text
mature
→ conversion issue
→ listing repair
→ re-observe
```

Prove no manual intervention is required.

### 10. Commission agents

Mark A14 and A15 commissioned after complete tests.

### 11. Review and checkpoint

Use analytics, workflow and commercial-logic reviewers. Their job is to verify faithful playbook implementation and automatic successor work, not to replace the rules with a new methodology.

Commit:

```text
feat(loop): automate metrics culling and winner multiplication
```

## Exit criteria

- Weekly and monthly loops run from durable schedules.
- Thirty-day maturity is automatic.
- Mature listings reach an executable decision.
- Cull deactivates.
- Multiply launches a successor workflow.
- Exploration is retained.
- Agents are commissioned.
- Closed-loop E2E tests pass.
- Control files and commit are current.

## Required exit code

```text
SESSION_10_CLOSED_LOOP_AUTOMATION_COMPLETE
```

Next prompt:

```text
14_SESSION_11_CUSTOMER_SUPPORT_AND_REPAIR.md
```

<!-- COPY END: 13_SESSION_10_ANALYTICS_CULL_MULTIPLY_CLOSED_LOOP.md -->


---

<a id="part-xv"></a>

# Part XV — Session 11: Customer Support and Repair

**Canonical source file:** `14_SESSION_11_CUSTOMER_SUPPORT_AND_REPAIR.md`  
**SHA-256:** `f5e5c5a000285286bbc3389ae4dd564b3accd9cc820f01b506b8b1cb536a1428`


### Workbook Run Record

| Field | Entry |
|---|---|
| Status | ☐ Not started |
| Date started |  |
| Date completed |  |
| Start commit |  |
| End commit |  |
| Tests / evidence |  |
| Blocker |  |
| Next action |  |

<!-- COPY START: 14_SESSION_11_CUSTOMER_SUPPORT_AND_REPAIR.md -->

# SESSION 11 — CUSTOMER SUPPORT, INCIDENTS AND AUTOMATED REPAIR

Execute under the Master Control Prompt and recovery protocol.

## Objective

Implement the troubleshooting and customer-support side of the playbook as linked incident workflows. Buyer issues must create reproducible repairs, update the original product/listing and close with verified resolution.

## Actions

### 1. Implement customer issue intake

Support intake through:

- Etsy messages where accessible;
- manual/API issue creation;
- operator console;
- webhook or polling where available.

Persist:

- buyer/message reference;
- listing;
- product;
- variant;
- issue text;
- attachments;
- received time;
- urgency;
- current status.

Never expose credentials or unrelated buyer data in logs.

### 2. Implement incident classification

Classify:

```text
BROKEN_DELIVERY_LINK
NOTION_PAGE_UNPUBLISHED
WRONG_VARIANT_LINK
NO_ACCESS_BLOCK
LINKED_VIEW_BROKEN
FORMULA_ERROR
DOWNLOAD_FILE_MISSING
LISTING_DEACTIVATED
ACCOUNT_VERIFICATION
DEDUPE_REJECTION
AGENT_RUN_INTERRUPTED
NO_SALES_DIAGNOSIS
OTHER_PRODUCT_DEFECT
```

Create the appropriate repair workflow automatically.

### 3. Implement A16 Customer Support & Repair Agent

The agent must:

- reproduce the reported problem;
- inspect the original product/listing;
- form one hypothesis at a time;
- execute or route the source repair;
- update the original published artifact;
- verify with a fresh view/duplicate;
- update the Etsy listing where required;
- draft or send the buyer response according to autonomy settings;
- close only after verified resolution.

### 4. Broken-link workflow

Implement:

```text
CUSTOMER_ISSUE_RECEIVED
→ REPRODUCE_LINK
→ LOCATE_FAILURE
→ REPAIR_NOTION_OR_PDF
→ REPLACE_ETSY_FILE
→ VERIFY_BUYER_PATH
→ RESPOND
→ CLOSE_INCIDENT
```

Prioritise this workflow above routine research/build jobs.

### 5. Broken duplicated-template workflow

Check:

- all subpages published;
- linked views point to the duplicate's intended data source;
- relations and formulas reference current properties;
- no accidental references to inaccessible originals;
- public settings;
- duplicate-as-template.

Repair the original published variant so future buyers receive the corrected version.

### 6. Listing-deactivation workflow

Support:

- ingest provider notice;
- inspect listing version;
- identify likely trigger from actual fields/assets;
- create repair changes;
- update or request reactivation/relist according to available provider path;
- preserve original evidence.

Do not build a large compliance bureaucracy. Handle the concrete provider issue.

### 7. Interrupted-agent recovery

When an agent run is interrupted:

- recover from job, artifacts and phase state;
- re-lease if safe;
- resume from incomplete operation;
- do not restart the entire product unnecessarily.

### 8. No-sales troubleshooting

After the playbook's maturity rule:

- inspect the full listing log;
- distinguish search, conversion and demand patterns using configured playbook logic;
- create a concrete two-week repair/research plan as executable jobs;
- do not merely return advice.

### 9. Customer response control

Support:

```text
support_mode: draft | auto
```

In auto mode, send bounded factual support responses after repair verification.

Responses must:

- acknowledge once;
- state the fix;
- include the working access path where appropriate;
- avoid invented claims;
- invite the buyer to reply if the issue remains.

### 10. Tests

Prove:

- broken PDF link;
- unpublished Notion variant;
- wrong colour link;
- no-access block;
- formula error;
- listing file replacement;
- interrupted run recovery;
- repair verification failure;
- customer response draft;
- auto-response after verified repair;
- incident priority over routine work;
- no duplicate repair side effects.

### 11. Commission agent

Mark A16 commissioned after full workflow and tests.

### 12. Review and checkpoint

Use incident-response and customer-experience reviewers. Fix findings.

Commit:

```text
feat(support): automate buyer incidents and source repairs
```

## Exit criteria

- Customer issues create linked incidents.
- Common playbook troubleshooting paths are executable.
- Repairs update the source product/listing.
- Resolution is verified.
- Support response can draft or send automatically.
- A16 is commissioned.
- Tests and control files are current.

## Required exit code

```text
SESSION_11_SUPPORT_AND_REPAIR_COMPLETE
```

Next prompt:

```text
15_SESSION_12_OPERATOR_CONSOLE_AND_POSTHOG.md
```

<!-- COPY END: 14_SESSION_11_CUSTOMER_SUPPORT_AND_REPAIR.md -->


---

<a id="part-xvi"></a>

# Part XVI — Session 12: Operator Console and PostHog

**Canonical source file:** `15_SESSION_12_OPERATOR_CONSOLE_AND_POSTHOG.md`  
**SHA-256:** `c84a6c59948264f654efc1c11448e3a01bbc0c0f07960b1792d7681e96e48677`


### Workbook Run Record

| Field | Entry |
|---|---|
| Status | ☐ Not started |
| Date started |  |
| Date completed |  |
| Start commit |  |
| End commit |  |
| Tests / evidence |  |
| Blocker |  |
| Next action |  |

<!-- COPY START: 15_SESSION_12_OPERATOR_CONSOLE_AND_POSTHOG.md -->

# SESSION 12 — OPERATOR CONSOLE AND POSTHOG TELEMETRY

Execute under the Master Control Prompt and recovery protocol.

## Objective

Build a compact exception-led operator console and connect PostHog operational telemetry. The interface must make the machine understandable without turning Omar into its dispatcher.

## Actions

### 1. API completion

Expose typed endpoints for:

- current shop;
- workflows;
- pipeline stages;
- ready/running/blocked jobs;
- products and variants;
- listing state;
- weekly metrics;
- decisions;
- incidents;
- integration status;
- autonomy settings;
- milestone progress;
- system health.

Use pagination and stable schemas.

### 2. Operator console structure

Build the Next.js console with these views.

#### NOW

- what is running;
- recent completions;
- next scheduled work;
- whether action is required.

#### PIPELINE

- product experiments by stage;
- blocked dependency;
- current owning agent;
- elapsed time;
- next transition.

#### SHOP

- active/draft/deactivated listings;
- age;
- views;
- favourites;
- sales;
- current decision;
- next review time.

#### BLOCKED

Only real blockers:

- credentials;
- account verification;
- CAPTCHA/provider challenge;
- configured spend limit;
- uncertain external effect.

#### DECISIONS

Show:

- hold;
- repair;
- cull;
- multiply;
- successor created;
- evidence and status.

Do not turn routine automated decisions into approval requests.

#### INCIDENTS

- buyer issue;
- severity;
- current repair step;
- response status;
- resolution evidence.

#### SETTINGS

- autonomy mode;
- publication cap;
- purchase caps;
- loop day;
- PostHog connection;
- provider status.

### 3. Design requirements

Use Product Design to create a clear, dense, professional interface.

Requirements:

- desktop-first but responsive;
- no decorative dashboard clutter;
- no vanity charts;
- status and exceptions visible immediately;
- one-screen summary;
- accessible labels and keyboard behaviour;
- deterministic empty/loading/error states.

### 4. Live updates

Use simple polling or server-sent events. Do not add a separate real-time platform unless already present.

### 5. PostHog integration

Implement server and web telemetry for the event taxonomy in the Master Control Prompt.

Include properties:

- workflow ID;
- job type;
- agent ID;
- product/listing ID where appropriate;
- duration;
- attempt;
- status;
- environment;
- autonomy mode;
- error classification.

Do not send:

- secrets;
- browser cookies;
- private competitor files;
- raw buyer messages;
- sensitive personal data.

### 6. Operational metrics

Create PostHog insights or documented queries for:

- workflow completion rate;
- job failure rate;
- agent failure rate;
- human intervention count;
- mean research-to-draft time;
- draft-to-publish time;
- QA rejection rate;
- retry count;
- stalled workflows;
- winner detection;
- culls;
- automatic successor creation;
- incident resolution time;
- automation percentage.

Etsy remains the canonical source for shop commerce data.

### 7. Operator actions

Allow only practical actions:

- inspect;
- retry eligible failed job;
- reconcile uncertain effect;
- supply credential status;
- pause/resume workflow;
- change standing-authority settings;
- manually create customer issue;
- trigger safe schedule run.

Do not expose arbitrary database editing.

### 8. Tests

Prove:

- API schema;
- auth boundary if configured;
- each page renders;
- empty/error states;
- workflow detail;
- blocked item;
- incident flow;
- settings validation;
- telemetry event shape;
- secrets excluded;
- browser E2E navigation;
- accessibility smoke;
- no routine approval queue.

### 9. Review and checkpoint

Use product-design, frontend and observability reviewers. Fix findings.

Commit:

```text
feat(console): add operator UI and PostHog telemetry
```

## Exit criteria

- Operator can understand current system state quickly.
- Console does not require manual orchestration.
- PostHog receives useful operational events.
- Sensitive data is excluded.
- UI and browser tests pass.
- Control files and commit are current.

## Required exit code

```text
SESSION_12_OPERATOR_CONSOLE_COMPLETE
```

Next prompt:

```text
16_SESSION_13_E2E_HARDENING_AND_FAILURE_RECOVERY.md
```

<!-- COPY END: 15_SESSION_12_OPERATOR_CONSOLE_AND_POSTHOG.md -->


---

<a id="part-xvii"></a>

# Part XVII — Session 13: E2E Hardening and Failure Recovery

**Canonical source file:** `16_SESSION_13_E2E_HARDENING_AND_FAILURE_RECOVERY.md`  
**SHA-256:** `d277afd72c2c90c29e0a8d2e4b607bb342b32d84fd485151de7ad6a1b32e21f2`


### Workbook Run Record

| Field | Entry |
|---|---|
| Status | ☐ Not started |
| Date started |  |
| Date completed |  |
| Start commit |  |
| End commit |  |
| Tests / evidence |  |
| Blocker |  |
| Next action |  |

<!-- COPY START: 16_SESSION_13_E2E_HARDENING_AND_FAILURE_RECOVERY.md -->

# SESSION 13 — COMPLETE E2E, FAILURE INJECTION AND HARDENING

Execute under the Master Control Prompt and recovery protocol.

## Objective

Challenge the full implementation as a single system. Remove remaining stubs, prove every main and failure path, verify restart behaviour and ensure the repository is genuinely ready for deployment.

## Actions

### 1. Inventory completeness

Generate an implementation matrix for:

- every playbook step;
- every job type;
- every event;
- every lifecycle transition;
- every agent;
- every provider action;
- every console view;
- every runbook.

Classify:

```text
IMPLEMENTED_AND_TESTED
IMPLEMENTED_NOT_LIVE_TESTED
BLOCKED_BY_EXTERNAL_CREDENTIAL
MISSING
```

Implement every `MISSING` item in the active path. Do not hide gaps in documentation.

### 2. Remove false implementations

Search for:

- TODO;
- FIXME;
- `pass`;
- `NotImplementedError`;
- dummy production adapters;
- fake success returns;
- hardcoded provider IDs;
- skipped tests without reason;
- dead branches;
- duplicate orchestration logic;
- prompts with no contract tests.

Resolve all active-path findings.

### 3. Full synthetic E2E

Run the complete fixture-backed workflow:

```text
research
→ shortlist
→ score
→ teardown
→ ProductSpec
→ dedupe
→ Notion build
→ QA
→ variants
→ listing copy
→ assets
→ PDFs
→ Etsy draft
→ preflight
→ publish simulation
→ post-publish verification
→ weekly metrics
→ thirty-day maturity
→ winner
→ successor ProductSpec
→ successor build job
```

Persist and inspect all artifacts and receipts.

### 4. Alternate E2E paths

Run:

#### Cull

```text
mature loser
→ cull decision
→ deactivation
→ lesson
```

#### Repair

```text
mature conversion problem
→ listing repair
→ updated version
→ observation
```

#### Broken link

```text
buyer issue
→ incident
→ reproduce
→ source repair
→ listing file replacement
→ verify
→ response
```

#### Dedupe

```text
too-close ProductSpec
→ reconcept
→ pass
→ build
```

### 5. Failure injection

Inject:

- worker crash;
- scheduler restart;
- database reconnect;
- expired lease;
- duplicate event;
- duplicate publish request;
- provider timeout before response;
- provider timeout after success;
- expired Etsy token;
- expired Notion session;
- malformed LLM output;
- unavailable LLM provider;
- asset-render failure;
- wrong PDF link;
- stale ProductFacts;
- browser selector change;
- ramp full;
- spend cap reached.

Verify recovery or exact blocking state.

### 6. Concurrency and performance

Prove:

- two workers do not run the same job;
- multiple product workflows can progress;
- publication cap remains global to the shop;
- database indexes support ready-job polling;
- artifact generation does not exhaust memory;
- browser contexts are bounded and cleaned;
- no unbounded retry loop.

### 7. Security and secret review

Check:

- `.env` excluded;
- browser profiles excluded;
- source PDF excluded;
- logs redact secrets;
- PostHog excludes sensitive data;
- API mutation endpoints are protected appropriately for deployment;
- no credentials in git history;
- downloaded competitor files remain private;
- runtime paths have sensible permissions.

Keep this focused on real implementation risks.

### 8. Backup and restore proof

Create a workflow with artifacts, back up:

- PostgreSQL;
- configuration;
- artifact storage metadata.

Restore into a clean environment and prove:

- workflow state;
- jobs;
- products;
- listings;
- schedules;
- agent definitions;
- artifacts;
- incidents.

### 9. Broad verification

Run:

- Python formatting;
- Ruff;
- Pyright;
- all Python tests;
- frontend lint/type/tests;
- browser E2E;
- migrations from empty;
- migrations from current;
- Docker production build;
- vulnerability checks available locally without adding paid services.

### 10. Independent final review

Use independent reviewers for:

- architecture;
- orchestration;
- integrations;
- data integrity;
- agent contracts;
- product outputs;
- frontend;
- DevOps.

Fix all critical/high defects and all medium defects that threaten autonomous operation.

### 11. Checkpoint

Commit:

```text
test(system): complete E2E and failure hardening
```

## Exit criteria

- No active-path stub remains.
- Complete happy/cull/multiply/repair paths pass.
- Restart and duplicate-effect tests pass.
- Backup/restore passes.
- Full quality suite passes.
- External credential-only gaps are explicit.
- Control files and commit are current.

## Required exit code

```text
SESSION_13_E2E_AND_HARDENING_COMPLETE
```

Next prompt:

```text
17_SESSION_14_DEPLOYMENT.md
```

<!-- COPY END: 16_SESSION_13_E2E_HARDENING_AND_FAILURE_RECOVERY.md -->


---

<a id="part-xviii"></a>

# Part XVIII — Session 14: Deployment

**Canonical source file:** `17_SESSION_14_DEPLOYMENT.md`  
**SHA-256:** `92d8c9a1b99e523ea227b2a4dc339fd0e32c6d007a9d05a4735b7a163cf7b624`


### Workbook Run Record

| Field | Entry |
|---|---|
| Status | ☐ Not started |
| Date started |  |
| Date completed |  |
| Start commit |  |
| End commit |  |
| Tests / evidence |  |
| Blocker |  |
| Next action |  |

<!-- COPY START: 17_SESSION_14_DEPLOYMENT.md -->

# SESSION 14 — PRODUCTION PACKAGING AND DEPLOYMENT

Execute under the Master Control Prompt and recovery protocol.

## Objective

Package and deploy the complete system to the selected existing environment without introducing unnecessary cloud infrastructure or recurring spend.

## Actions

### 1. Select the deployment target from evidence

Inspect available machines and existing infrastructure.

Prefer:

1. an existing suitable VPS or always-on machine already owned by Omar;
2. the current Windows/WSL2 machine for local commissioning;
3. a new paid environment only if Omar has explicitly approved it.

Do not create unapproved spend.

Record the selected target and rationale in `docs/architecture/DEPLOYMENT.md`.

### 2. Finalise production containers

Build production images for:

- API;
- worker;
- scheduler;
- web.

Use one Python image where sensible.

Configure:

- non-root runtime where practical;
- health checks;
- restart policy;
- persistent PostgreSQL volume;
- artifact storage;
- runtime browser profiles;
- environment/secrets;
- log rotation;
- browser dependencies;
- resource limits appropriate to the host.

### 3. Reverse proxy and access

Use Caddy or the existing reverse proxy.

Support:

- HTTPS where a domain is available;
- local/private access where no domain is configured;
- operator-console authentication;
- API protection;
- health endpoints.

Do not delay local commissioning for a public domain.

### 4. Database and release process

Implement:

- migration on deployment;
- seed/upgrade idempotency;
- release version;
- rollback to prior container image;
- database backup before migration;
- compatibility checks.

### 5. Backup and restore automation

Provide PowerShell and Bash commands for:

- database backup;
- artifact backup;
- restore;
- verification;
- retention cleanup.

Schedule backups in production.

### 6. Runtime service management

Support:

- start;
- stop;
- restart;
- status;
- logs;
- worker scale within host limits;
- scheduler singleton;
- migration;
- safe update.

### 7. Deploy

Deploy the latest exact commit.

Prove:

- all services healthy;
- database migrated;
- seed present;
- operator console accessible;
- worker leasing;
- scheduler tick;
- fixture/simulation workflow;
- PostHog event path where configured;
- restart after host/service reboot.

### 8. CI release path

Complete a private-repo release workflow that:

- runs tests;
- builds images;
- records commit/image tags;
- deploys through the selected mechanism or produces an exact deploy command;
- never exposes secrets.

### 9. Runbooks

Complete:

```text
LOCAL_DEVELOPMENT.md
ACCOUNT_CONNECTIONS.md
LIVE_COMMISSIONING.md
INCIDENTS.md
BACKUP_RESTORE.md
PROVIDER_RECOVERY.md
```

Keep them operational and concise.

### 10. Review and checkpoint

Use DevOps and operational-recovery reviewers. Fix defects.

Commit:

```text
feat(deploy): package and deploy production runtime
```

Tag a pre-commissioning release:

```text
v0.1.0-rc1
```

## Exit criteria

- Production stack is deployed on the selected environment.
- Services survive restart.
- Backups run and restore has evidence.
- Operator console is accessible.
- Simulation workflow passes in the deployed runtime.
- Release and rollback paths exist.
- Control files and commit are current.

## Required exit code

```text
SESSION_14_PRODUCTION_DEPLOYMENT_COMPLETE
```

Next prompt:

```text
18_SESSION_15_LIVE_COMMISSIONING_AND_HANDOVER.md
```

<!-- COPY END: 17_SESSION_14_DEPLOYMENT.md -->


---

<a id="part-xix"></a>

# Part XIX — Session 15: Live Commissioning and Handover

**Canonical source file:** `18_SESSION_15_LIVE_COMMISSIONING_AND_HANDOVER.md`  
**SHA-256:** `b09859086ad510862f493227c1da075cc0a29d76ebd07ca4cd6f80710c8ce712`


### Workbook Run Record

| Field | Entry |
|---|---|
| Status | ☐ Not started |
| Date started |  |
| Date completed |  |
| Start commit |  |
| End commit |  |
| Tests / evidence |  |
| Blocker |  |
| Next action |  |

<!-- COPY START: 18_SESSION_15_LIVE_COMMISSIONING_AND_HANDOVER.md -->

# SESSION 15 — LIVE ACCOUNT COMMISSIONING, FULL ACCEPTANCE AND HANDOVER

Execute under the Master Control Prompt and recovery protocol.

## Objective

Connect the real provider accounts, commission live autonomy, run the first real linked workflow to the furthest authorised external state and complete operational handover.

No new architecture is allowed in this session unless a verified defect requires it.

## Actions

### 1. Confirm deployed exact state

Read control files and verify:

- deployed commit;
- service versions;
- database migration;
- all agent commissioning states;
- full test results;
- open credential blockers;
- configured autonomy mode.

Run production smoke tests.

### 2. Connect LLM provider

Configure and verify:

- provider credentials;
- structured-output call;
- model selection;
- prompt-version logging;
- usage/cost capture;
- redaction.

Run one harmless agent contract smoke.

### 3. Connect Notion

Through the Account & Integration Agent and browser/API adapters:

- authenticate;
- identify the correct workspace;
- verify create/read/update/publish;
- verify persistent browser profile;
- clean temporary test page.

### 4. Connect Etsy

- authenticate OAuth/browser;
- identify shop;
- verify shop status;
- verify draft/read capability;
- verify media/file capability;
- verify stats read;
- verify message path where available;
- clean test draft if one is created.

Do not publish a meaningless test listing.

### 5. Connect Composio and PostHog

- record available actions;
- connect only useful integrations;
- verify PostHog server and web events;
- confirm sensitive fields are absent.

### 6. Configure standing authority once

Set the production values with Omar only where values are genuinely absent:

```text
mode
auto_publish
auto_deactivate
auto_multiply
weekly_listing_cap
competitor_purchase_enabled
competitor_purchase_max_each
competitor_purchase_monthly_cap
live_checkout_test_enabled
live_checkout_test_cap
paid_tool_monthly_cap
weekly_loop_day
```

Ask for all missing values in one compact request, not repeated approvals.

After configuration, routine work inside bounds proceeds automatically.

### 7. Run the first real workflow

Execute:

```text
live Etsy research
→ shortlist
→ Low-Ticket score
→ primary and backup
→ competitor teardown path
→ ProductSpec
→ dedupe
→ live Notion build
→ QA
→ variants
→ listing copy
→ assets
→ PDFs
→ Etsy draft
→ preflight
```

If production authority has `auto_publish: true` and the ramp permits it:

```text
→ publish
→ post-publish verify
→ weekly schedule
→ thirty-day maturity schedule
```

If a real paid competitor purchase or checkout test is enabled within cap, execute it. If not enabled, the workflow must use the configured non-purchase path or stop only that exact job while continuing everything else.

### 8. Verify operational autonomy

Prove from runtime state:

- no manual copy/paste occurred;
- every successor job was created automatically;
- artifacts are versioned;
- provider receipts exist;
- current workflow can resume after restart;
- weekly metrics job is scheduled;
- maturity trigger exists;
- incident path is ready;
- console reflects reality;
- PostHog records the run.

### 9. Final acceptance matrix

Mark every definition-of-done item from the Master Control Prompt:

```text
PASS
FAIL
BLOCKED_EXTERNAL
```

No item may be silently omitted.

Resolve every `FAIL`.

A `BLOCKED_EXTERNAL` item is allowed only for an exact account-holder or provider action that ChatGPT cannot perform and that does not invalidate the implemented system.

### 10. Final documentation and handover

Update:

- README;
- architecture;
- runbooks;
- integration status;
- agent roster;
- test evidence;
- control state.

Create:

```text
docs/FINAL_HANDOVER.md
docs/FINAL_ACCEPTANCE.md
```

Include:

- system purpose;
- exact deployed location;
- service commands;
- console URL;
- current autonomy settings;
- connected accounts;
- first workflow result;
- scheduled jobs;
- backup status;
- remaining external blockers;
- how to pause/resume;
- how to inspect a failure;
- how to update.

### 11. Final review and release

Run the complete quality suite again.

Use an independent final reviewer to compare:

- playbook;
- architecture;
- implementation;
- runtime;
- first real workflow;
- definition of done.

Fix every material mismatch.

Commit:

```text
chore(release): commission hands-off money machine
```

Tag:

```text
v1.0.0
```

Push private remote.

Update `IMPLEMENTATION_STATE.json`:

```text
current_session = 15
completed_sessions = [0..15]
next_session = null
status = COMMISSIONED
```

## Required final exit code

Use only when the implementation and commissioned runtime support the complete linked workflow:

```text
HANDS_OFF_MONEY_MACHINE_COMMISSIONED
```

The final response must include:

```text
HANDS_OFF_MONEY_MACHINE_COMMISSIONED

Repository:
Branch:
Commit:
Release:
Deployment:
Console:

Live workflow:
- current stage
- product/listing identifiers
- schedules created

Verification:
- complete test summary
- provider connection summary
- backup/restore status

External blockers:
- none
or exact non-implementation account/provider actions
```

<!-- COPY END: 18_SESSION_15_LIVE_COMMISSIONING_AND_HANDOVER.md -->


---

<a id="part-xx"></a>

# Part XX — Recovery and Continuation Prompt

**Canonical source file:** `19_RECOVERY_AND_CONTINUATION_PROMPT.md`  
**SHA-256:** `75677038b5bd148e1efab565f1e3ccf27d45657b4530eb0078477ba426c3e8de`

<!-- COPY START: 19_RECOVERY_AND_CONTINUATION_PROMPT.md -->

# RECOVERY AND CONTINUATION PROMPT

```text
[@Remote Desktop Commander]
[@superpowers]
[@Composio]
[@posthog]
[@product-design]
```

Recover and continue the existing Hands-Off Money Machine implementation.

Do not restart the programme.

## Recovery procedure

1. Search for the canonical repository, preferring:
   - `D:\hands-off-money-machine`;
   - `/mnt/d/hands-off-money-machine`;
   - any path recorded in `IMPLEMENTATION_STATE.json`.
2. Read:
   - `AGENTS.md`;
   - `docs/control/IMPLEMENTATION_STATE.json`;
   - `docs/control/NEXT_SESSION.md`;
   - the latest entries in `IMPLEMENTATION_LOG.md`;
   - `DECISIONS.md`;
   - `TEST_EVIDENCE.md`.
3. Inspect:
   - git remote;
   - current branch;
   - exact HEAD;
   - git status;
   - recent commits;
   - running containers/services;
   - failing tests;
   - incomplete migrations;
   - leased/running/stalled jobs.
4. Compare the requested session prompt with `current_session`, `completed_sessions` and repository evidence.
5. Resume the first incomplete action in the requested session.
6. Preserve all completed work, decisions, fixtures, receipts, failures and user changes.
7. Do not ask Omar to repeat context already in the repository.
8. Do not create a second repo, second workflow engine or new architecture.
9. Run a focused verification of prior-session foundations before modifying them.
10. Continue until the requested session's exit criteria are met.

## State conflict handling

If control files disagree with code or git:

- current code, migrations, tests, git history and runtime evidence take precedence;
- repair the control files;
- record the contradiction;
- continue from the real state.

If a previous assistant claimed completion without evidence:

- mark the session incomplete;
- complete it now;
- do not restart earlier completed work.

## Response

Return only the requested session's completion format and next prompt after updating control files and committing.

<!-- COPY END: 19_RECOVERY_AND_CONTINUATION_PROMPT.md -->


---

<a id="part-xxi"></a>

# Part XXI — Final Acceptance Checklist

**Canonical source file:** `20_FINAL_ACCEPTANCE_CHECKLIST.md`  
**SHA-256:** `b0f1a3b7c8ca6a9bebda664cca1253e018d95697cce7ad2bb76024a4e8c22797`

<!-- COPY START: 20_FINAL_ACCEPTANCE_CHECKLIST.md -->

# Final Acceptance Checklist

This checklist is used in Session 15. Every line requires evidence.

## Repository and runtime

- [ ] Canonical private repository exists.
- [ ] Windows and WSL2 paths are documented.
- [ ] Private source PDF is excluded from git.
- [ ] Prompt pack is stored in the repo.
- [ ] Fresh bootstrap succeeds.
- [ ] Production compose succeeds.
- [ ] Database migrations succeed.
- [ ] Backup and restore succeed.
- [ ] API, worker, scheduler, web and PostgreSQL are healthy.
- [ ] Restart recovery succeeds.

## Orchestration

- [ ] PostgreSQL durable jobs are active.
- [ ] Dependencies block and release correctly.
- [ ] Leases prevent double execution.
- [ ] Expired leases recover.
- [ ] Idempotency suppresses duplicates.
- [ ] Timers survive restart.
- [ ] Thirty-day maturity is durable.
- [ ] Weekly and monthly schedules are durable.
- [ ] Successors are created transactionally.
- [ ] Uncertain external effects reconcile before retry.

## Agents

- [ ] A01 Shop Orchestrator commissioned.
- [ ] A02 Account & Integration commissioned.
- [ ] A03 Market Research commissioned.
- [ ] A04 Competitor Teardown commissioned.
- [ ] A05 Product Strategy commissioned.
- [ ] A06 Catalogue Dedupe commissioned.
- [ ] A07 Notion Product Builder commissioned.
- [ ] A08 Variant Builder commissioned.
- [ ] A09 Product QA commissioned.
- [ ] A10 Merchandising commissioned.
- [ ] A11 Creative Asset commissioned.
- [ ] A12 Preflight commissioned.
- [ ] A13 Etsy Publishing commissioned.
- [ ] A14 Analytics commissioned.
- [ ] A15 Cull & Multiply commissioned.
- [ ] A16 Customer Support & Repair commissioned.

## Playbook workflow

- [ ] Research evidence grid is generated.
- [ ] Shortlist of five is generated.
- [ ] Low-Ticket score out of forty is generated.
- [ ] Primary and backup are selected.
- [ ] Competitor teardown workflow exists.
- [ ] ProductSpec is versioned.
- [ ] Dedupe fails and reconcepts automatically.
- [ ] Notion product builds automatically.
- [ ] Shared databases and linked views work.
- [ ] Notification dashboard works.
- [ ] Six to eight hubs exist.
- [ ] Three or four variants exist.
- [ ] Public links are isolated.
- [ ] Product facts are extracted.
- [ ] Listing title is generated.
- [ ] Eight-part description is generated.
- [ ] Exactly thirteen tags are generated.
- [ ] Ten images are generated.
- [ ] Video is generated.
- [ ] README/access PDF is generated.
- [ ] Optional free-gift PDF path exists.
- [ ] Every link is tested.
- [ ] Etsy draft is created.
- [ ] Preflight blocks defects.
- [ ] Publication ramp works.
- [ ] Live auto-publication can be enabled without code change.
- [ ] Post-publish verification works.
- [ ] Weekly metrics are collected.
- [ ] No demand verdict occurs before thirty days.
- [ ] Mature loser is culled and deactivated.
- [ ] Winner creates successor ProductSpec and build job.
- [ ] Monthly deep pass creates work.
- [ ] Customer issue creates repair workflow.

## Product integrity

- [ ] Claims reference verified ProductFacts.
- [ ] No invented reviews or trust counts.
- [ ] Asset lineage is complete.
- [ ] Stale assets invalidate after product change.
- [ ] Fresh duplicate test passes.
- [ ] Wrong link repair passes.
- [ ] Cross-catalogue access test passes.
- [ ] Listing versions are retained.
- [ ] Deactivated products retain evidence.

## Integrations

- [ ] LLM provider connected.
- [ ] Notion connected.
- [ ] Etsy connected.
- [ ] Composio capability map recorded.
- [ ] PostHog connected.
- [ ] Browser profiles persist outside git.
- [ ] Provider receipts exist.
- [ ] Credential expiry produces exact blocker.
- [ ] Fixture adapters cover all external providers.

## Operator experience

- [ ] NOW page reflects current work.
- [ ] PIPELINE page reflects workflow stages.
- [ ] SHOP page reflects listings and metrics.
- [ ] BLOCKED contains only genuine blockers.
- [ ] DECISIONS shows cull/multiply outcomes.
- [ ] INCIDENTS shows repairs.
- [ ] SETTINGS changes standing authority.
- [ ] No routine approval queue exists.
- [ ] PostHog operational events are visible.

## Test paths

- [ ] Full happy path passes.
- [ ] Full cull path passes.
- [ ] Full multiply path passes.
- [ ] Full repair path passes.
- [ ] Dedupe/reconcept path passes.
- [ ] Worker crash recovery passes.
- [ ] Scheduler restart passes.
- [ ] Duplicate publish suppression passes.
- [ ] Uncertain external effect passes.
- [ ] Expired credentials path passes.
- [ ] Backup/restore path passes.
- [ ] Full lint/type/unit/integration/E2E suite passes.

## Live commissioning

- [ ] Standing authority configured once.
- [ ] First real research run completed.
- [ ] First real ProductSpec completed.
- [ ] First real Notion product completed.
- [ ] First real listing package completed.
- [ ] First real Etsy draft completed.
- [ ] Live publication completed where authorised.
- [ ] Weekly metrics schedule exists.
- [ ] Thirty-day maturity schedule exists.
- [ ] Runtime can continue without manual handoff.
- [ ] Final handover and acceptance documents exist.
- [ ] Release `v1.0.0` exists.

<!-- COPY END: 20_FINAL_ACCEPTANCE_CHECKLIST.md -->


---

<a id="appendix-a"></a>

# Appendix A — Prompt Pack Manifest

**Canonical source file:** `MANIFEST.json`  
**SHA-256:** `0a559cdda4d1cdb837883b02c8e2c8d7c7495176093245198b66fa1f91c0a475`

<!-- COPY START: MANIFEST.json -->

{
  "name": "Hands-Off Money Machine ChatGPT Full Implementation Prompt Pack",
  "version": "1.0",
  "files": [
    {
      "name": "00_READ_ME_FIRST.md",
      "bytes": 4491,
      "sha256": "eb9fedf8b07cd17a02e0a3141d21b2037fcc509ef403813e52a038a1077f6b91"
    },
    {
      "name": "01_MASTER_CONTROL_PROMPT.md",
      "bytes": 24993,
      "sha256": "a42fea06ae89c595294258aa41ee09b6929743671a0feb8e3f1bbe94eff0fe8f"
    },
    {
      "name": "02_CANONICAL_REPOSITORY_STRUCTURE.md",
      "bytes": 16177,
      "sha256": "17aa97358ccf78425e5a7fea3c07ae61e810b40ec3e0436eada75419169947f7"
    },
    {
      "name": "03_SESSION_00_DISCOVERY_AND_REPO_BOOTSTRAP.md",
      "bytes": 5989,
      "sha256": "207a79ffdaa903da128c678628eb4736f9977fe5c0a8d434d2b3bc4410e944ba"
    },
    {
      "name": "04_SESSION_01_PLAYBOOK_MAPPING_AND_ARCHITECTURE.md",
      "bytes": 5581,
      "sha256": "104b890e45f84d96be48a77f6247bfb616a807ac775771f6ac6dcf1299db5ada"
    },
    {
      "name": "05_SESSION_02_ENGINEERING_FOUNDATION_AND_DATABASE.md",
      "bytes": 4593,
      "sha256": "dd64137dfa21792e7956d3fe4a24b449aa59625872af05c567e294eee2aad0ab"
    },
    {
      "name": "06_SESSION_03_DURABLE_ORCHESTRATOR.md",
      "bytes": 4552,
      "sha256": "3adc85b2d98f9dca22062bd13391d55633862110d3ed1fe2afa56882f1d3f232"
    },
    {
      "name": "07_SESSION_04_AGENT_RUNTIME_AND_ROSTER.md",
      "bytes": 4261,
      "sha256": "beb748811662b90c06098e51ab14a691f634f56900daf05c57e0fbdec0f826a3"
    },
    {
      "name": "08_SESSION_05_MARKET_RESEARCH_TO_PRODUCT_SPEC.md",
      "bytes": 4943,
      "sha256": "e7df623562b0cc4a79e1440c19a11258115c05fcfccea10d9e8b5f348e723db5"
    },
    {
      "name": "09_SESSION_06_NOTION_INTEGRATION_FOUNDATION.md",
      "bytes": 5016,
      "sha256": "7ef25c4fb6bd00bcd85a1996e4b8ce5de4442b369cca4066dca3dbb38b1c3df9"
    },
    {
      "name": "10_SESSION_07_PRODUCT_BUILD_VARIANTS_AND_QA.md",
      "bytes": 5255,
      "sha256": "d52011a6f0b725b16427629dc664cfc9f3432c4b5f71d26ce032d4b6c8ecb39d"
    },
    {
      "name": "11_SESSION_08_MERCHANDISING_AND_ASSET_FACTORY.md",
      "bytes": 5092,
      "sha256": "a7a406cecd9c93efdec1045f394b911e614cd79366840e33d5c53d9968f7cd33"
    },
    {
      "name": "12_SESSION_09_ETSY_DRAFT_PUBLISH_AND_PREFLIGHT.md",
      "bytes": 5597,
      "sha256": "eab1e4a5ae05008e06607526a1bf45b0fb35850a5bbf82e4002bd94954f58936"
    },
    {
      "name": "13_SESSION_10_ANALYTICS_CULL_MULTIPLY_CLOSED_LOOP.md",
      "bytes": 4813,
      "sha256": "250a666a2e0e81790066b96caaf0f017fde59027cc2921b1417ea71c99677e7a"
    },
    {
      "name": "14_SESSION_11_CUSTOMER_SUPPORT_AND_REPAIR.md",
      "bytes": 4556,
      "sha256": "f5e5c5a000285286bbc3389ae4dd564b3accd9cc820f01b506b8b1cb536a1428"
    },
    {
      "name": "15_SESSION_12_OPERATOR_CONSOLE_AND_POSTHOG.md",
      "bytes": 4280,
      "sha256": "c84a6c59948264f654efc1c11448e3a01bbc0c0f07960b1792d7681e96e48677"
    },
    {
      "name": "16_SESSION_13_E2E_HARDENING_AND_FAILURE_RECOVERY.md",
      "bytes": 4650,
      "sha256": "d277afd72c2c90c29e0a8d2e4b607bb342b32d84fd485151de7ad6a1b32e21f2"
    },
    {
      "name": "17_SESSION_14_DEPLOYMENT.md",
      "bytes": 3456,
      "sha256": "92d8c9a1b99e523ea227b2a4dc339fd0e32c6d007a9d05a4735b7a163cf7b624"
    },
    {
      "name": "18_SESSION_15_LIVE_COMMISSIONING_AND_HANDOVER.md",
      "bytes": 5243,
      "sha256": "b09859086ad510862f493227c1da075cc0a29d76ebd07ca4cd6f80710c8ce712"
    },
    {
      "name": "19_RECOVERY_AND_CONTINUATION_PROMPT.md",
      "bytes": 1955,
      "sha256": "75677038b5bd148e1efab565f1e3ccf27d45657b4530eb0078477ba426c3e8de"
    },
    {
      "name": "20_FINAL_ACCEPTANCE_CHECKLIST.md",
      "bytes": 5092,
      "sha256": "b0f1a3b7c8ca6a9bebda664cca1253e018d95697cce7ad2bb76024a4e8c22797"
    }
  ]
}

<!-- COPY END: MANIFEST.json -->


---

<a id="appendix-b"></a>

# Appendix B — Workbook Integrity Register

This table proves which canonical files were embedded in the workbook. Hashes cover the normalised UTF-8 source content between the copy markers.

| Source file | SHA-256 | Bytes | Lines |
|---|---|---:|---:|
| `00_READ_ME_FIRST.md` | `eb9fedf8b07cd17a02e0a3141d21b2037fcc509ef403813e52a038a1077f6b91` | 4,491 | 110 |
| `01_MASTER_CONTROL_PROMPT.md` | `a42fea06ae89c595294258aa41ee09b6929743671a0feb8e3f1bbe94eff0fe8f` | 24,993 | 873 |
| `02_CANONICAL_REPOSITORY_STRUCTURE.md` | `17aa97358ccf78425e5a7fea3c07ae61e810b40ec3e0436eada75419169947f7` | 16,177 | 441 |
| `03_SESSION_00_DISCOVERY_AND_REPO_BOOTSTRAP.md` | `207a79ffdaa903da128c678628eb4736f9977fe5c0a8d434d2b3bc4410e944ba` | 5,989 | 257 |
| `04_SESSION_01_PLAYBOOK_MAPPING_AND_ARCHITECTURE.md` | `104b890e45f84d96be48a77f6247bfb616a807ac775771f6ac6dcf1299db5ada` | 5,581 | 237 |
| `05_SESSION_02_ENGINEERING_FOUNDATION_AND_DATABASE.md` | `dd64137dfa21792e7956d3fe4a24b449aa59625872af05c567e294eee2aad0ab` | 4,593 | 235 |
| `06_SESSION_03_DURABLE_ORCHESTRATOR.md` | `3adc85b2d98f9dca22062bd13391d55633862110d3ed1fe2afa56882f1d3f232` | 4,552 | 204 |
| `07_SESSION_04_AGENT_RUNTIME_AND_ROSTER.md` | `beb748811662b90c06098e51ab14a691f634f56900daf05c57e0fbdec0f826a3` | 4,261 | 179 |
| `08_SESSION_05_MARKET_RESEARCH_TO_PRODUCT_SPEC.md` | `e7df623562b0cc4a79e1440c19a11258115c05fcfccea10d9e8b5f348e723db5` | 4,943 | 221 |
| `09_SESSION_06_NOTION_INTEGRATION_FOUNDATION.md` | `7ef25c4fb6bd00bcd85a1996e4b8ce5de4442b369cca4066dca3dbb38b1c3df9` | 5,016 | 224 |
| `10_SESSION_07_PRODUCT_BUILD_VARIANTS_AND_QA.md` | `d52011a6f0b725b16427629dc664cfc9f3432c4b5f71d26ce032d4b6c8ecb39d` | 5,255 | 237 |
| `11_SESSION_08_MERCHANDISING_AND_ASSET_FACTORY.md` | `a7a406cecd9c93efdec1045f394b911e614cd79366840e33d5c53d9968f7cd33` | 5,092 | 236 |
| `12_SESSION_09_ETSY_DRAFT_PUBLISH_AND_PREFLIGHT.md` | `eab1e4a5ae05008e06607526a1bf45b0fb35850a5bbf82e4002bd94954f58936` | 5,597 | 254 |
| `13_SESSION_10_ANALYTICS_CULL_MULTIPLY_CLOSED_LOOP.md` | `250a666a2e0e81790066b96caaf0f017fde59027cc2921b1417ea71c99677e7a` | 4,813 | 234 |
| `14_SESSION_11_CUSTOMER_SUPPORT_AND_REPAIR.md` | `f5e5c5a000285286bbc3389ae4dd564b3accd9cc820f01b506b8b1cb536a1428` | 4,556 | 200 |
| `15_SESSION_12_OPERATOR_CONSOLE_AND_POSTHOG.md` | `c84a6c59948264f654efc1c11448e3a01bbc0c0f07960b1792d7681e96e48677` | 4,280 | 226 |
| `16_SESSION_13_E2E_HARDENING_AND_FAILURE_RECOVERY.md` | `d277afd72c2c90c29e0a8d2e4b607bb342b32d84fd485151de7ad6a1b32e21f2` | 4,650 | 256 |
| `17_SESSION_14_DEPLOYMENT.md` | `92d8c9a1b99e523ea227b2a4dc339fd0e32c6d007a9d05a4735b7a163cf7b624` | 3,456 | 177 |
| `18_SESSION_15_LIVE_COMMISSIONING_AND_HANDOVER.md` | `b09859086ad510862f493227c1da075cc0a29d76ebd07ca4cd6f80710c8ce712` | 5,243 | 263 |
| `19_RECOVERY_AND_CONTINUATION_PROMPT.md` | `75677038b5bd148e1efab565f1e3ccf27d45657b4530eb0078477ba426c3e8de` | 1,955 | 63 |
| `20_FINAL_ACCEPTANCE_CHECKLIST.md` | `b0f1a3b7c8ca6a9bebda664cca1253e018d95697cce7ad2bb76024a4e8c22797` | 5,092 | 150 |
| `MANIFEST.json` | `0a559cdda4d1cdb837883b02c8e2c8d7c7495176093245198b66fa1f91c0a475` | 3,835 | 111 |


## Integrity Validation Rules

- Every file listed above must appear exactly once between matching `COPY START` and `COPY END` markers.
- Session completion must be supported by repository commits, test results and runtime evidence.
- The playbook remains the business-process source; this workbook is the implementation control surface.
- A later canonical revision must increment the workbook version and preserve a clear supersession record.

## Final Commissioning Code

The programme may emit the following only after every mandatory acceptance item is evidenced:

```text
HANDS_OFF_MONEY_MACHINE_COMMISSIONED
```
