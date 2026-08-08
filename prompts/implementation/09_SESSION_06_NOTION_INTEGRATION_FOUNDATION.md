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
