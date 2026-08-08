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
