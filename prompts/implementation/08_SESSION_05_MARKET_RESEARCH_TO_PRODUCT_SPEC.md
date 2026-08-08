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
