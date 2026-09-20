# Session 05 Lane 1 — Etsy Research Adapters — Prompt Integrity Review

**Date:** 2026-09-20  
**Scope:** Bounded L1 implementation of Etsy research adapters only (not full Session 05)  
**Prompt:** `08_SESSION_05_MARKET_RESEARCH_TO_PRODUCT_SPEC.md` (Section 1 only)  
**SHA-256:** `e7df623562b0cc4a79e1440c19a11258115c05fcfccea10d9e8b5f348e723db5`  
**Verified:** Prompt file hash matches

## Review Scope

This review covers **only Section 1** of Session 05 (Etsy research adapters), implementing as a bounded SERIAL-first merge lane. The full Session 05 activation and remaining sections (A03-A06 agents, workflow linking, commissioning) are OUT OF SCOPE for this lane.

## Lane-Specific Instruction Set (User Override)

The operator provided a focused lane instruction that constrains Session 05 Section 1:

**IN SCOPE:**
1. Fixture adapter first (+ browser/API stubs only where safe / no paid calls)
2. Capture workbook fields: search phrase, rank, title, prices, shop signals, niche, URL, evidence timestamp
3. Ten seed phrases as config (not hardcoded magic in business logic)
4. Tests proving fixture path returns structured rows; fail-closed if required fields missing

**OUT OF SCOPE:**
- Paid Etsy purchase / live paid teardown
- A03/A05/A06 agent logic (deferred to L2–L4)
- Scheduler Exit 78 lift
- Session 06 work

**HARD RULES:**
- Simulation/fixtures for anything that would cost money
- Thin evidence; no invented metrics
- Minimal diffs; library-quality
- Worker Exit 78 already gated on tip — do not regress

## Fidelity Review

**Verdict:** COMPLIANT with lane constraints

**Findings:**
- ✅ Section 1 of Session 05 prompt specifies fixture adapter as primary implementation
- ✅ Workbook field capture list matches playbook Chapter 12-13 research patterns
- ✅ Ten seed phrases from playbook are explicitly required as configuration
- ✅ Prompt specifies "fixture teardown must keep test workflows runnable" when purchase disabled
- ✅ Lane scope explicitly excludes agent logic (A03-A06), which are Session 05 sections 2-7

**Contracts carried forward from Session 04:**
- Worker Exit 78 conditionally lifted behind D-0028 commissioning gates (must not regress)
- Fail-closed simulation/draft/live mode boundaries (must preserve)
- Control state management (may need minimal S05 activation if not already present)

**Amendments:** None required; lane scope already tighter than prompt Section 1.

## Safety and Executability Review

**Verdict:** SAFE with bounded scope

**Findings:**

✅ **No external mutations:** Fixture adapter has zero Etsy API cost or risk.

✅ **Fail-closed boundaries preserved:** Browser/API stubs documented as safe-only (no paid calls).

✅ **Ordering:** Session 04 complete at tip `79d48ad`; dependencies (database schema, migrations) already present.

✅ **Decomposition:** Single bounded slice (fixture adapter + config + tests) is executable within governance.

⚠️ **S05 activation:** Current state shows `current_session: 4`, `session_status: complete`, no S05 evidence keys. Minimal activation may be required per operator instruction.

**Safety rules to preserve:**
- Never commit secrets, `.env`, tokens, cookies, browser profiles, customer/provider payloads
- Never publish, purchase, spend, or message customers from tests
- Preserve immutable root source files byte-for-byte
- Worker Exit 78 conditional lift must not regress

**Amendments:**
1. If S05 not activated: include minimal `money-machine-control activate` call in this PR (current_session=5, session_status=incomplete, S05 evidence keys all-false, prompt-integrity record).
2. Fixture data must be synthetic/anonymized; never real Etsy shop data.
3. Browser/API adapter stubs must be explicitly marked UNIMPLEMENTED with safe defaults.

## Gameability Review

**Verdict:** Tests are verifiable

**Exit criteria for this lane:**
- PR open, CI green, undrafted
- Fixture adapter returns structured rows with all required fields
- Tests prove fixture path works; fail-closed if required fields missing
- Ten seed phrases loaded from config (not hardcoded)
- Browser/API stubs present but safe (no paid calls)

**Anti-gaming measures:**
1. **"Fixture adapter returns structured rows"** — Test must assert presence of ALL required fields per workbook (search phrase, rank, title, prices, shop signals, niche, URL, timestamp). Empty or stub fields for non-fixture paths is OK; fixture path must be complete.

2. **"Tests prove fixture path works"** — Must execute against fixture data (not live Etsy) and assert structured output. Test name must be explicit (e.g., `test_etsy_fixture_adapter_returns_required_fields`).

3. **"Ten seed phrases as config"** — Must be loaded from `config/*.yaml` or environment, NOT string literals in business logic. Test must prove config loading works.

4. **"Browser/API stubs safe"** — Stubs must raise `NotImplementedError` or return empty/None. No actual HTTP calls, no browser launch. Test must prove they don't mutate external state.

**Gameability-resistant wording:**
- "Fixture adapter must parse synthetic Etsy search result data and return a list of research observations, each containing every field specified in Session 05 Section 1, with no missing keys or None values for the fixture code path."
- "Ten seed search phrases must be defined in a configuration file under `config/`, loaded via a configuration module, and never appear as string literals in `money_machine/domain/` or `money_machine/agents/`."
- "Browser and API adapter stubs must be present as separate modules with type signatures matching the fixture adapter, but must not make network requests or launch browsers; tests must prove these stubs raise NotImplementedError or return empty collections."

## Corrective Addendum — Executable Instruction Set

This lane will execute the following bounded implementation:

### 1. S05 Activation (if required)

**Check:** Read `IMPLEMENTATION_STATE.json`. If `current_session` is 4 and no S05 evidence keys exist:

```bash
money-machine-control activate --session 5
```

Record minimal activation commit. Install evidence keys:
- `etsy_adapters_implemented: false`
- `research_agent_implemented: false`
- `shortlist_analysis_implemented: false`
- `scoring_agent_implemented: false`
- `teardown_workflow_implemented: false`
- `product_spec_generation_implemented: false`
- `dedupe_agent_implemented: false`
- `workflow_linking_complete: false`

This lane will flip ONLY `etsy_adapters_implemented: true`.

### 2. Configuration

Create `config/research.yaml` containing the ten seed search phrases from the playbook (Chapter 12):
- digital planner
- printable wall art
- custom pet portrait
- wedding invitation template
- vintage logo design
- social media templates
- budget spreadsheet
- meal planner printable
- business card template
- resume template

### 3. Fixture Adapter Implementation

**Module:** `money_machine/integrations/etsy/research_adapter.py`

**Interface:**
```python
class EtsyResearchObservation(BaseModel):
    search_phrase: str
    rank: int
    title: str
    current_price_cents: int
    anchor_price_cents: int | None
    shop_name: str
    shop_sales_count: int | None
    shop_age_years: int | None
    badges: list[str]
    urgency_signals: list[str]
    review_count: int | None
    identity_niche: str
    base_category: str
    listing_url: str
    evidence_timestamp: datetime

class EtsyResearchAdapter(Protocol):
    def search(self, phrase: str, target_count: int) -> list[EtsyResearchObservation]: ...
```

**Fixture implementation:**
- Load synthetic search result data from `tests/fixtures/etsy_search_results.json`
- Parse into `EtsyResearchObservation` instances
- Return 25-40 rows per configured seed phrase
- All required fields present and typed

**Browser stub:**
```python
class EtsyBrowserAdapter:
    def search(self, phrase: str, target_count: int) -> list[EtsyResearchObservation]:
        raise NotImplementedError("Browser adapter not yet implemented")
```

**API stub:**
```python
class EtsyAPIAdapter:
    def search(self, phrase: str, target_count: int) -> list[EtsyResearchObservation]:
        raise NotImplementedError("Etsy API adapter not yet implemented")
```

### 4. Tests

**Test suite:** `tests/integrations/etsy/test_research_adapter.py`

Required tests:
1. `test_fixture_adapter_returns_all_required_fields` — Assert every field present, correctly typed, no None for required fields
2. `test_fixture_adapter_returns_25_to_40_rows` — Assert row count in range
3. `test_config_loads_ten_seed_phrases` — Assert seed phrases loaded from config, not hardcoded
4. `test_browser_stub_raises_not_implemented` — Assert stub doesn't make real calls
5. `test_api_stub_raises_not_implemented` — Assert stub doesn't make real calls
6. `test_fixture_adapter_captures_thin_evidence` — Assert no invented metrics (e.g., review_count can be None if not in fixture)

### 5. Fixture Data

**File:** `tests/fixtures/etsy_search_results.json`

Structure:
```json
{
  "digital planner": [
    {
      "rank": 1,
      "title": "2026 Digital Planner Pro",
      "current_price_cents": 1299,
      "anchor_price_cents": 1999,
      "shop_name": "PlannerStudio",
      "shop_sales_count": 15234,
      "shop_age_years": 2,
      "badges": ["Star Seller", "Fast Shipping"],
      "urgency_signals": ["Only 3 left", "12 people have this in their cart"],
      "review_count": 4523,
      "identity_niche": "productivity digital downloads",
      "base_category": "Office & School Supplies",
      "listing_url": "https://www.etsy.com/listing/fake-12345",
      "search_timestamp": "2026-09-20T20:00:00Z"
    }
    // ... 25-40 synthetic rows per seed phrase
  ]
}
```

**Requirements:**
- Synthetic data only (no real Etsy shop names/URLs)
- Covers all required fields
- Demonstrates thin evidence (some optional fields None where appropriate)
- 25-40 rows per seed phrase

### 6. Integration

Wire adapter selection in `money_machine/integrations/etsy/__init__.py`:
```python
def get_research_adapter(mode: str = "fixture") -> EtsyResearchAdapter:
    if mode == "fixture":
        return EtsyFixtureAdapter()
    elif mode == "browser":
        return EtsyBrowserAdapter()
    elif mode == "api":
        return EtsyAPIAdapter()
    else:
        raise ValueError(f"Unknown adapter mode: {mode}")
```

Default to `mode="fixture"` in tests. Production mode selection deferred to agent implementation (L2).

### 7. Documentation

Add docstrings:
- Module purpose: "Etsy research adapters for market research observations"
- Fixture adapter: "Loads synthetic search results from test fixtures. Safe for CI; no external calls."
- Browser stub: "Playwright-based Etsy search scraper. NOT IMPLEMENTED; raises NotImplementedError."
- API stub: "Etsy API client. NOT IMPLEMENTED; raises NotImplementedError."

### 8. Control Updates

If S05 activated in step 1:
- Update `IMPLEMENTATION_STATE.json`: `etsy_adapters_implemented: true`
- Add entry to `IMPLEMENTATION_LOG.md`: "S05 L1: Etsy fixture adapter + config + tests"
- Update `TEST_EVIDENCE.md`: Add fixture adapter test results

If S05 not activated (existing activation sufficient):
- Skip state flip; just implement + test

### 9. PR Requirements

- Branch name: `cursor/s05-l1-etsy-adapters-<suffix>-185d` (where suffix is descriptive)
- PR title: "feat(research): S05 L1 — Etsy fixture adapter + config"
- PR body: Describe fixture adapter, config loading, test coverage, stub safety
- Undrafted after CI green

### 10. Out of Scope (Explicit)

- A03 Market Research Agent implementation
- A04/A05/A06 agent logic
- Live Etsy browser automation
- Paid Etsy API calls
- Teardown workflow (Session 05 Section 5)
- ProductSpec generation (Session 05 Section 6)
- Workflow linking (Session 05 Section 8)
- Scheduler Exit 78 lift
- Session 06 work

## Deferrals

None. This lane is executable as scoped.

## What the Lane Already Gets Right

- Fixture-first approach matches governance (safe, fast, testable)
- Config-driven seed phrases avoid magic strings
- Thin evidence principle (no invented metrics)
- Explicit stubs prevent accidental external calls
- Bounded scope fits Level 1 governance cadence

## Approval

**Fidelity:** COMPLIANT  
**Safety:** SAFE  
**Gameability:** VERIFIABLE  

**Proceed with implementation per corrective addendum.**
