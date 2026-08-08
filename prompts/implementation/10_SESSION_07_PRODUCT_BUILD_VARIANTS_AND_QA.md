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
