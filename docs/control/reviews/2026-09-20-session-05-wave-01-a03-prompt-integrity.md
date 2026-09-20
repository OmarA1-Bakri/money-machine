# Session 05 Wave 01 — A03 Market Research Agent Prompt Integrity Review

**Date:** 2026-09-20  
**Wave:** S05-L2-A03  
**Scope:** A03 Market Research Agent implementation only (scoped subset of full Session 05)  
**Reviewer:** Cloud Agent (cursor/s05-l2-a03-research-market-agent-1776)

## Scoped Prompt Summary

**IN SCOPE:**
1. A03 Market Research Agent: execute searches via fixture adapter
2. Produce 25–40 observation rows; young-and-fast filter  
3. Persist observations + ResearchReport; thin evidence only
4. Emit RESEARCH_COMPLETED event
5. Shortlist analysis: identity×category, price bands, 5 candidates + risk notes
6. Fail-closed if uncommissioned / missing evidence

**OUT OF SCOPE:**
- Paid live Etsy (fixtures only)
- A05 scoring / ProductSpec (L3)
- A06 dedupe / full workflow wire (L4)
- Scheduler Exit 78 lift; S06

**HARD RULES:**
- Fixtures only for paid paths
- No invented metrics; thin evidence
- No manual copy/paste between steps — agent emits artifacts

## Fidelity Review

### Alignment with Parent Session 05 Prompt

**Session 05 Prompt Location:** `prompts/implementation/08_SESSION_05_MARKET_RESEARCH_TO_PRODUCT_SPEC.md`

**Verification:**
- ✅ A03 agent is Action #2 in Session 05 prompt (lines 54-62)
- ✅ Shortlist analysis is Action #3 (lines 64-76)
- ✅ ResearchRun, MarketListingObservation, MarketShopObservation tables exist in schema (tables.py:766-814)
- ✅ ProductCandidate table exists (tables.py:816-842)
- ✅ Agent registry includes A03 in DESIGNED state
- ✅ Fail-closed commissioning boundary exists via D-0028

**Scoped Subset Justification:**
This wave implements only A03 agent and its immediate outputs (research observations, shortlist). It explicitly defers:
- A05 Product Strategy (Low-Ticket scoring) to L3
- A06 Catalogue Dedupe to L4
- A04 Competitor Teardown (depends on purchase workflow)
- Workflow chaining (requires orchestrator work)

**Contracts Preserved from Session 01:**
- ✅ Agent lineage fields (agent_run_id, agent_id, agent_definition_version, prompt_reference, prompt_sha256) exist
- ✅ Commissioning states (DESIGNED → TESTED → COMMISSIONED) enforced
- ✅ External effect modes (SIMULATION/DRAFT/LIVE) enforced

### Alignment with Session 04 Foundation

**Dependencies from Session 04:**
- ✅ AgentRunner integration complete (W9 @ 14da7fe)
- ✅ PromptStore and hashes implemented (W3 @ 726437d)
- ✅ Sixteen-agent roster registered (W5 @ 827272b)
- ✅ Tool registry available
- ✅ Worker claim path functional (D-0028 commissioning gates)

**Required Inputs:**
- ✅ `MarketResearchJob` exists (job type RUN_MARKET_RESEARCH)
- ✅ Workflow context available via workflow_id foreign key
- ✅ Source policy version tracking (ResearchRun.source_policy_version)

## Safety and Executability Review

### External Effect Boundaries

**Finding SF-01: Etsy API/Browser adapter usage mode**
- **Severity:** HIGH
- **Line:** Scoped prompt "execute searches via fixture adapter"
- **Authority:** D-0028 commissioning gates, AUTONOMY_MODEL.md
- **Consequence:** If browser/API adapter is used before commissioning, live Etsy mutations possible
- **Remediation:** Fixture adapter ONLY for this wave. Browser/API adapters remain uncommissioned scaffolds. Add explicit adapter-selection check in A03 implementation that refuses non-fixture modes when uncommissioned.

**Finding SF-02: No external provider spend**
- **Severity:** CRITICAL  
- **Line:** "Fixtures only for paid paths"
- **Authority:** AGENTS.md "Never publish, purchase, spend"
- **Consequence:** If purchase workflow is invoked, real Etsy spend could occur
- **Remediation:** A04 competitor purchase is OUT OF SCOPE. MarketResearchJob must not trigger CompetitorPurchase. Add test asserting no purchase job is spawned from RUN_MARKET_RESEARCH.

**Finding SF-03: RESEARCH_COMPLETED event creation**
- **Severity:** MEDIUM
- **Line:** "Emit RESEARCH_COMPLETED"
- **Authority:** Event persistence contract from Session 02
- **Consequence:** If event schema incomplete or successor rules wrong, workflow breaks
- **Remediation:** Verify WorkflowEvent.event_type accepts "RESEARCH_COMPLETED". Add test for event emission with correct workflow_id, job_id. Check successor creation rules don't auto-spawn A05 (out of scope).

### Data Integrity

**Finding SF-04: Observation uniqueness**
- **Severity:** HIGH
- **Line:** "Produce 25–40 observation rows"
- **Authority:** Schema constraint UniqueConstraint("research_run_id", "source_reference") on MarketListingObservation and MarketShopObservation
- **Consequence:** Duplicate source_reference within one ResearchRun will fail database insert
- **Remediation:** Agent must dedupe by source_reference before persistence. Add test for duplicate handling (should skip or merge, not crash).

**Finding SF-05: Thin evidence requirement**
- **Severity:** MEDIUM
- **Line:** "thin evidence only" and "expose thin evidence instead of inventing values"
- **Authority:** Session 05 prompt line 62 "expose thin evidence instead of inventing values"
- **Consequence:** If agent invents shop_sales, shop_opened_on, or price data, research is corrupted
- **Remediation:** Use nullable fields correctly. If fixture doesn't provide a value, store NULL not a fabricated number. Add test asserting NULL fields when fixture data is absent.

### Commissioning and Fail-Closed

**Finding SF-06: Uncommissioned execution refusal**
- **Severity:** CRITICAL
- **Line:** "Fail-closed if uncommissioned / missing evidence"
- **Authority:** D-0028 commissioning gates, Session 04 W9 uncommissioned-agent refusal
- **Consequence:** If A03 is DESIGNED and worker invokes it, undefined behavior
- **Remediation:** Worker already checks commissioning_state (Session 04 W9). A03 state must remain DESIGNED until tests pass. Add test that DESIGNED agent raises AgentNotCommissionedError.

**Finding SF-07: Missing evidence handling**
- **Severity:** HIGH
- **Line:** "Fail-closed if ... missing evidence"
- **Authority:** Playbook requirement for research before product spec
- **Consequence:** If A03 runs without seed phrases or fixture data, empty ResearchRun persists
- **Remediation:** Agent must validate seed phrases configured before execution. If fixture returns zero results, log warning but don't fail (real Etsy might have zero results). Add test for empty-result handling.

## Gameability Review

### Exit Criteria Gameability

**Finding GF-01: "25–40 observation rows" can be satisfied by stubs**
- **Severity:** HIGH
- **Line:** Scoped prompt "Produce 25–40 observation rows"
- **Authority:** Session 05 prompt line 58 "target 25–40 useful rows"
- **Consequence:** Agent could generate exactly 25 empty MarketListingObservation rows and pass
- **Hardening:** Test must assert:
  - At least 25 MarketListingObservation rows created
  - Each row has non-null title, source_reference
  - At least 5 distinct identity_niche values (proves diversity)
  - At least 10 rows have price > 0 (proves real data, not stubs)
  - At least 5 MarketShopObservation rows (proves shop data collected)

**Finding GF-02: "shortlist analysis" can return five empty candidates**
- **Severity:** HIGH
- **Line:** "5 candidates + risk notes"
- **Authority:** Session 05 prompt line 75 "five strongest candidates"
- **Consequence:** Agent could create 5 ProductCandidate rows with empty identity/category
- **Hardening:** Test must assert:
  - Exactly 5 ProductCandidate rows created
  - Each has non-empty identity, base_category
  - Each has at least one evidence reference (facts column or observation link)
  - Each has a distinct identity×category combination (proves no duplicates)
  - Risk notes present (can be in facts column as {risk: "..."})

**Finding GF-03: "thin evidence" is not machine-verifiable**
- **Severity:** MEDIUM
- **Line:** "thin evidence only"
- **Authority:** Session 05 "expose thin evidence instead of inventing values"
- **Consequence:** No automated test can prove values are real vs fabricated
- **Hardening:** Reviewer must manually inspect fixture data vs persisted observations. Test can only assert nullable fields are used correctly and that fixture adapter is used (not browser/API which could be mocked).

**Finding GF-04: RESEARCH_COMPLETED event can be emitted without real work**
- **Severity:** HIGH
- **Line:** "Emit RESEARCH_COMPLETED"
- **Authority:** Workflow event contract
- **Consequence:** Agent could emit event immediately without running searches
- **Hardening:** Test must assert:
  - RESEARCH_COMPLETED event emitted only after ResearchRun persisted
  - ResearchRun.completed_at is not null when event emitted
  - ResearchRun.observation_count >= 25

### Completion Evidence

**Finding GF-05: No explicit test list provided**
- **Severity:** MEDIUM
- **Line:** "DONE WHEN: PR open, CI green, undrafted"
- **Authority:** Session 05 prompt lines 171-182 (test requirements)
- **Consequence:** CI could pass with incomplete coverage
- **Hardening:** This wave must include:
  - Test for 25–40 observation generation via fixture
  - Test for thin evidence handling (NULL fields when absent)
  - Test for five-candidate shortlist
  - Test for uncommissioned refusal
  - Test for RESEARCH_COMPLETED event emission
  - Test for duplicate source_reference handling

## Corrective Addendum

The scoped S05-L2-A03 prompt is **CONDITIONALLY EXECUTABLE** after the following amendments:

### 1. Fixture Adapter Only (SF-01, SF-02)
**Amend:** Agent implementation must use ONLY FixtureEtsyAdapter. Add explicit check: if adapter is not FixtureEtsyAdapter, raise NotImplementedError("Only fixture adapter supported in wave 01").

**Test:** Assert A03 agent raises NotImplementedError if invoked with browser or API adapter settings.

### 2. No Purchase Job Spawn (SF-02)
**Amend:** RUN_MARKET_RESEARCH job handler must NOT create CompetitorPurchaseJob. Successor creation is out of scope for this wave.

**Test:** Assert no CompetitorPurchase or related purchase job rows created after A03 execution.

### 3. Event Schema and Emission (SF-03)
**Amend:** Verify "RESEARCH_COMPLETED" is a valid WorkflowEventType. If not, add it. Event must include workflow_id, job_id, research_run_id in payload.

**Test:** Assert RESEARCH_COMPLETED event created with correct foreign keys.

### 4. Observation Deduplication (SF-04)
**Amend:** Agent must dedupe observations by source_reference before bulk insert. If duplicate detected within same fixture response, keep first occurrence.

**Test:** Fixture returns same listing twice; assert only one MarketListingObservation persisted.

### 5. Nullable Field Discipline (SF-05)
**Amend:** If fixture data is missing price, shop_sales, shop_opened_on, identity_niche, base_category, store NULL not zero/empty string/"unknown".

**Test:** Fixture with partial data; assert NULL in database for missing fields, not fabricated values.

### 6. Commissioning State Check (SF-06)
**Amend:** Worker already handles this (Session 04 W9). Verify A03 is registered in DESIGNED state and remains there until tests pass.

**Test:** (Already exists in Session 04) Invoke A03 while DESIGNED; assert AgentNotCommissionedError raised.

### 7. Seed Phrase Validation (SF-07)
**Amend:** Agent must load seed phrases from configuration before execution. If configuration is empty, fail fast with clear error.

**Test:** Invoke A03 with empty seed phrase config; assert ValueError("No seed phrases configured").

### 8. Anti-Stub Test Coverage (GF-01, GF-02, GF-04)
**Amend:** Tests must assert:
- At least 25 MarketListingObservation rows with non-null title, source_reference
- At least 5 distinct identity_niche values
- At least 10 rows with price > 0
- At least 5 MarketShopObservation rows
- Exactly 5 ProductCandidate rows with non-empty identity, base_category
- RESEARCH_COMPLETED event emitted only after ResearchRun.completed_at set

**Test:** One comprehensive integration test covering all assertions.

### 9. Manual Evidence Review (GF-03)
**Defer to:** Final wave review before Session 05 closure.

**Reason:** Thin evidence verification requires human judgment. Fixture data will be reviewed manually to ensure it represents plausible Etsy listings, not obvious fabrications. This is a Level 3 (session exit) gate, not a Level 1 (wave) gate.

### 10. Shortlist Analysis Concreteness (GF-02)
**Amend:** Shortlist generation must extract identity_niche and base_category from MarketListingObservation rows, not generate them independently. Use GROUP BY to find most frequent combinations, then select top 5 by observation count or price-band diversity.

**Test:** Assert each ProductCandidate.identity + base_category combination appears in at least one MarketListingObservation row.

## Execution Order

1. Implement FixtureEtsyAdapter with 40+ plausible Etsy listing fixtures (identity, category, price, shop data)
2. Implement A03 agent to call fixture adapter, persist observations, generate shortlist
3. Add seed phrase configuration (default 10 phrases from playbook)
4. Write integration test covering amendments 1-8, 10
5. Run test; iterate until green
6. Manual fixture data review (amendment 9 deferred to session closure)
7. Create PR, verify CI green, undraft

## Findings Summary

| ID | Severity | Category | Status |
|----|----------|----------|--------|
| SF-01 | HIGH | External effects | REMEDIATED (fixture-only check) |
| SF-02 | CRITICAL | Spend boundary | REMEDIATED (no purchase spawn) |
| SF-03 | MEDIUM | Event schema | REMEDIATED (event verification) |
| SF-04 | HIGH | Data integrity | REMEDIATED (dedupe logic) |
| SF-05 | MEDIUM | Evidence quality | REMEDIATED (nullable discipline) |
| SF-06 | CRITICAL | Commissioning | ALREADY HANDLED (Session 04 W9) |
| SF-07 | HIGH | Configuration | REMEDIATED (seed validation) |
| GF-01 | HIGH | Test gameability | HARDENED (anti-stub assertions) |
| GF-02 | HIGH | Shortlist stubs | HARDENED (evidence linkage) |
| GF-03 | MEDIUM | Evidence quality | DEFERRED (manual review at L3) |
| GF-04 | HIGH | Event gaming | HARDENED (pre-conditions) |
| GF-05 | MEDIUM | Coverage gaps | REMEDIATED (test list) |

## Verdict

**CLEAR TO EXECUTE** after applying the 10-point corrective addendum.

## What This Wave Gets Right

- Scope is appropriately bounded (A03 only, no L3/L4 dependencies)
- Schema tables already exist and are correct
- Fixture-only mandate prevents live Etsy exposure
- Fail-closed commissioning is preserved
- No workflow chaining complexity in wave 01

## References

- Session 05 Prompt: `prompts/implementation/08_SESSION_05_MARKET_RESEARCH_TO_PRODUCT_SPEC.md`
- Schema: `src/money_machine/persistence/tables.py` lines 766-842
- Session 04 W9 commissioning: D-0028 in DECISIONS.md
- Governance: `docs/DEVELOPMENT-GOVERNANCE.md` Level 1/2/3 cadence
