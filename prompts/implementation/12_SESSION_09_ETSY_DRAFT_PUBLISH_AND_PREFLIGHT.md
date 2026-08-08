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
