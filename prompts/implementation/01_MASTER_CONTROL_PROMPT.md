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
