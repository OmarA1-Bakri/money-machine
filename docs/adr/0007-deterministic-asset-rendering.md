# 0007 Deterministic Asset Rendering

**Status:** Accepted

## Context

The playbook requires ten listing images, one walkthrough video, a two-page README/access PDF, and an optional free-gift PDF. Manual Canva assembly would leave a recurring handoff and make output difficult to reproduce or verify.

## Decision

Build an internal deterministic asset factory using versioned HTML/CSS/SVG templates, explicit fonts/assets, and pinned Playwright browser rendering. Structured render manifests reference verified product facts, screenshots, palette tokens, copy, dimensions, template version, and source hashes.

The factory produces:

- ten listing images including hero, hub, colour, device, and how-it-works views;
- one short walkthrough video from deterministic frames and timing;
- one two-page README/access PDF;
- an optional free-gift PDF containing only admitted free links.

Every output is byte-hashed and registered in artifact lineage. Renders use fixed viewport, locale, timezone, animation state, network policy, and font readiness. Truth checks ensure displayed counts, features, links, and claims resolve to verified product facts. URL policy and click tests run on delivery files. Canva may exist as an optional adapter but is not required for the production path.

## Rationale

Template-driven rendering eliminates a routine manual dependency, supports repeatable repair, and ties every visible claim to durable inputs.

## Consequences

- Browser, font, and codec versions must be pinned and recorded.
- Exact bytes can change after an intentional renderer upgrade; version and migration receipts distinguish them.
- Visual QA remains required in addition to deterministic generation.
- Remote assets and uncontrolled network requests are prohibited during rendering.
- Product-specific creativity is expressed through structured templates and tokens, not untracked editor state.

## Rejected alternatives

- **Required manual Canva workflow:** cannot support autonomous repeatable operation.
- **LLM-generated raster assets without manifests:** weak provenance and unstable output.
- **Screenshots alone:** cannot produce the complete listing and delivery package.
- **Provider-hosted mutable source files:** undermine reproducibility.
- **Claim review by prompt only:** cannot enforce truth deterministically.

## Revisit when

Revisit the renderer when provider media specifications, accessibility requirements, or supported asset classes change. Preserve deterministic manifests, pinned execution, truth checks, hashes, and lineage.