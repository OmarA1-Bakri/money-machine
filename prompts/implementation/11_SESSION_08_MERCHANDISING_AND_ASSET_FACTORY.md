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
