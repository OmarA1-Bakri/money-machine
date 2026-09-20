# Session 05 Lane 4 Scope Review

**Date:** 2026-09-20  
**Session:** 05  
**Lane:** L4 (parallel bounded slice)  
**Reviewer:** Cloud Agent (this run)  
**Status:** Lightweight scope verification (not full prompt integrity review)

## Context

User requested specific Lane 4 work within Session 05:
- A06 Catalogue Dedupe implementation (PASS/TOO_CLOSE + reconcept loop)
- Fixture competitor teardown workflow (simulation only, no IP copying)
- Workflow link proving: RUN_MARKET_RESEARCH → ... → CHECK_DEDUPE → BUILD_NOTION_TEMPLATE ready
- Fixture tests from workbook §9

This is a **bounded Level 1/2 slice** within Session 05, not execution of the full session prompt. Session 05 prompt (`08_SESSION_05_MARKET_RESEARCH_TO_PRODUCT_SPEC.md`) remains the authority for the complete session, but L4 implements a specific vertical: dedupe and teardown fixture support.

## Scope Verification

### In Scope (Lane 4)
1. **A06 Catalogue Dedupe Agent**
   - Implement `dedupe.py` service with deterministic rules per D-0013
   - Identity + category exact match → EXACT_IDENTITY_CATEGORY collision
   - Title similarity using Jaccard threshold 0.70 → TITLE_SIMILARITY collision
   - Concept fingerprint match → CONCEPT_FINGERPRINT collision
   - Return PASS (with differentiation evidence) or TOO_CLOSE (with collisions)
   - Emit DEDUPE_PASSED or DEDUPE_FAILED events
   - Create ReconceptProductJob on TOO_CLOSE

2. **Fixture Competitor Teardown**
   - Implement fixture TeardownReport generation
   - NO actual competitor IP copying (simulation only)
   - Structure-only teardown as per TeardownReport contract
   - Support CompetitorPurchaseJob and TeardownJob in fixture mode

3. **Workflow Link Proving**
   - Integration test showing: ProductSpecJob → DedupeJob → ProductBuildJob (on PASS)
   - Integration test showing: ProductSpecJob → DedupeJob → ReconceptProductJob → DedupeJob (on TOO_CLOSE loop)
   - Use fixtures for dependencies (ResearchReport, TeardownReport, ProductSpec)

4. **Tests**
   - Dedupe PASS with empty catalogue
   - Dedupe PASS with non-conflicting catalogue (requires differentiation evidence)
   - Dedupe TOO_CLOSE on identity+category collision
   - Dedupe TOO_CLOSE on title similarity collision
   - Dedupe TOO_CLOSE on concept fingerprint collision
   - Reconcept loop (TOO_CLOSE → ReconceptProductJob → new spec → DedupeJob → PASS)

### Out of Scope (Other Lanes or Later Sessions)
- A03 Market Research Agent implementation (L1)
- A04 Competitor Teardown Agent implementation (L3)
- A05 Product Strategy Agent implementation (L2)
- Live Etsy read/research adapters (Session 05 scope but not L4)
- Actual competitor purchase (requires credentials, live mode)
- Notion integration (Session 06)
- Agent commissioning state transitions (done after all lanes merge)

## Safety Checks

✅ **No competitor IP copying** - Fixture only, structure-based TeardownReport  
✅ **No live external effects** - Dedupe is NONE side effect class  
✅ **No credential requirements** - All fixture-based  
✅ **Fail-closed boundaries preserved** - Agent remains DESIGNED until commissioning  
✅ **No source file mutations** - Playbook PDF and workbook untouched  
✅ **No secret commits** - No `.env`, tokens, credentials  
✅ **D-0013 contract binding** - Jaccard 0.70, identity+category, concept fingerprint rules  

## Fidelity to Workbook

- D-0013: Dedupe rules (identity+category, Jaccard 0.70, concept fingerprint, differentiation required for PASS against non-empty catalogue)
- D-0017: MULTIPLY creates new dedupe-gated lineage (RECONCEPT is similar pattern)
- D-0018: Pydantic strict validation, frozen models, UTC timestamps
- D-0023: Workflow validation (DedupeJob → ProductBuildJob or ReconceptProductJob successors)
- Session 05 prompt action #7: "Implement A06 Catalogue Dedupe Agent" with deterministic rules + semantic comparison, PASS/TOO_CLOSE outcomes, reconcept loop

## Dependencies

Lane 4 can proceed independently by using fixture:
- **ProductSpec** - Already defined in domain models
- **DedupeResult** - Already defined with validation rules
- **TeardownReport** - Already defined
- **Workflow configuration** - Already in config/workflows.yaml
- **Event/job definitions** - Already in domain enums and workflows

If L1/L2/L3 are not merged yet, L4 tests use fixture ProductSpec, TeardownReport, ResearchReport instances.

## Execution Plan

1. Implement `dedupe.py` service (title normalization, Jaccard, collision detection)
2. Implement `catalogue_dedupe.py` agent (orchestrate dedupe service, persist result, emit events)
3. Implement fixture `TeardownReport` generator for tests
4. Write unit tests for dedupe service
5. Write integration tests for dedupe agent + workflow link
6. Run affected tests (Level 1 verification)
7. Integrate and run broader regression (Level 2 if this becomes integration boundary)
8. Update control files if this is final L4 checkpoint

## Verdict

**PROCEED** - Lane 4 scope is well-defined, safe, independent, and aligned with Session 05 requirements and existing architecture. No critical findings. Fixture-based approach removes live-effect risk. Dedupe logic is fully specified in D-0013.

## Amendments

None required - user instruction is clear and bounded.

## Deferred to Later

- Full Session 05 prompt integrity review (when executing full session or merging all lanes)
- Agent commissioning to TESTED/COMMISSIONED state (Session 05 exit requirement)
- Live Etsy adapter implementation (other lanes)
- End-to-end smoke test with real browser (Session 05 exit, optional)
