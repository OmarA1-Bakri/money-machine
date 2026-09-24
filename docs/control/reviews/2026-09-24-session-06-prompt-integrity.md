# Session 06 Prompt Integrity Review

**Date:** 2026-09-24  
**Reviewer:** Cloud Agent (autonomous)  
**Prompt:** `prompts/implementation/09_SESSION_06_NOTION_INTEGRATION_FOUNDATION.md`  
**Verified SHA-256:** `7ef25c4fb6bd00bcd85a1996e4b8ce5de4442b369cca4066dca3dbb38b1c3df9`  
**Workbook Authority:** `hands-off-money-machine-full-implementation-workbook.md` line 3234, Appendix confirmed  
**Scope:** Wave 1 ONLY per operator instruction — foundation stubs, no live Notion, no Exit78 lift, no SESSION_06 COMPLETE

## 1. Prompt Authenticity

**Status:** VERIFIED

- Prompt file SHA-256 matches workbook Appendix declaration exactly
- Content between `<!-- COPY START -->` and `<!-- COPY END -->` in workbook matches extracted file
- Prompt is 224 lines, 5,016 bytes per Appendix

## 2. Three-Dimensional Review

### Dimension 1: Fidelity

**Verdict:** CONDITIONAL APPROVE with ONE HIGH finding

#### Findings

**F-01 [HIGH] — Session 06 full scope vs Wave 1 bounded instruction**

- **Prompt line:** Entire prompt scope (lines 1-224)
- **Authority contradicted:** Operator instruction limits Wave 1 to: (1) capability inspect + PLATFORM_COMPATIBILITY.md, (2) NotionAdapter interface + fixture skeleton + router stubs, (3) control activation (programme pattern), (4) unit tests. Explicitly OUT OF SCOPE: live Notion, browser receipts stack, formula builders beyond stubs, Exit78 lift, SESSION_06 COMPLETE.
- **Consequence of literal execution:** Implementing lines 36-207 (sections 3-11) would build full browser session management, formula builders, publishing helpers, relation/linked-view helpers, live connection CLI, and claim SESSION_06 COMPLETE — violating the bounded W1 instruction.
- **Amendment:** Execute ONLY sections 1-2 (lines 10-76) for W1. Defer sections 3-11 to later waves. Control activation follows programme pattern (session 6 active, evidence keys false, S05 still complete). Exit criteria deferred; W1 ends when PLATFORM_COMPATIBILITY.md updated, NotionAdapter + fixture + router stubs exist, control activated, tests green.

**F-02 [MEDIUM] — Fixture adapter completeness ambiguity**

- **Prompt line:** 166 (section 8: "The fixture adapter must model...")
- **Authority:** Prompt states fixture must be "complete enough for full product E2E" (line 207), but W1 instruction states "fixture adapter skeleton (in-memory/stub parity enough for unit tests — not full Session-07 E2E fixture completeness)"
- **Consequence:** Over-building W1 fixture to Session 07 standards wastes W1 scope
- **Amendment:** W1 fixture is skeleton-only: stub CRUD operations that return typed domain objects, enough for NotionAdapter interface tests. Full E2E fixture completeness deferred to later wave before Session 07.

#### What the Prompt Gets Right

- Operation enumeration (lines 36-62) is comprehensive and maps to playbook requirements
- Adapter interface pattern (lines 64-76) correctly abstracts DIRECT_API | COMPOSIO | BROWSER | COMBINED
- Fixture parity principle (section 8) correctly requires testable stubs before live integration
- Control-file update requirement (line 196) preserves programme discipline
- Exit criteria (lines 203-214) are measurable (though deferred for W1)

### Dimension 2: Safety and Executability

**Verdict:** CONDITIONAL APPROVE with TWO CRITICAL, THREE HIGH findings

#### Findings

**S-01 [CRITICAL] — Live Notion mutation risk**

- **Prompt line:** 169-177 (section 9: "Live connection path")
- **Authority violated:** Playbook simulation/draft/live discipline; standing rule "Never... mutate live provider data from tests"
- **Consequence:** Section 9 instructs "create a temporary test page", "create a small database", "publish/unpublish", "delete or archive" — all live Notion writes. If credentials exist, literal execution would mutate live workspace.
- **Amendment:** W1 implements ZERO live Notion calls. Live connection path deferred to later wave with explicit operator authorization, sandbox workspace isolation, and reconciliation receipts. W1 stubs raise NotImplementedError.

**S-02 [CRITICAL] — Browser profile storage in repo risk**

- **Prompt line:** 88 (section 3: "Never store browser cookies or profiles in git")
- **Authority:** Correct prohibition, but no enforcement mechanism specified
- **Consequence:** If browser adapter stubs don't enforce `.gitignore` coverage, authenticated profiles could leak
- **Amendment:** W1 browser adapter stubs must NOT instantiate real browser sessions. No browser launch, no profile creation, no cookies. Full browser implementation deferred. Assert `runtime/browser-profiles/` remains in `.gitignore`.

**S-03 [HIGH] — Missing Notion operation taxonomy**

- **Prompt line:** 36-62 (section 2: operation list)
- **Contract omission:** Prompt lists 25+ operations but doesn't define: (1) which operations are read vs write, (2) which require auth vs public, (3) which are idempotent vs side-effecting, (4) which block vs async
- **Consequence:** Adapter interface without operation contracts leads to unsafe retry, missing idempotency, and unclear reconciliation boundaries
- **Amendment:** PLATFORM_COMPATIBILITY.md must tag each operation with: method (DIRECT_API|COMPOSIO|BROWSER|COMBINED), mutates (bool), requires_auth (bool), idempotent (bool), reconcilable (bool). Defer implementation of non-idempotent ops until reconciliation design exists.

**S-04 [HIGH] — Receipt schema undefined**

- **Prompt line:** 91-108 (section 4: "Implement Notion operation receipts")
- **Missing authority:** Receipt fields listed but no table schema, no persistence, no idempotency-key contract
- **Consequence:** Section 4 cannot be implemented without Session 02-style domain model + migration + repository
- **Amendment:** W1 defers receipts. Later wave defines NotionOperationReceipt table with job_id FK, operation enum, workspace/page/database IDs, pre_state JSONB, post_state JSONB, evidence_url, status, idempotency_key unique constraint, created_at. Receipt stub in W1 returns typed object without persistence.

**S-05 [HIGH] — Formula builders premature**

- **Prompt line:** 110-123 (section 5: formula builders for Tasks/Events/Habits/Finance/etc.)
- **Timing violation:** Formula generation requires: (1) final ProductSpec schema from Session 05, (2) database property name resolution, (3) Notion formula syntax validation. Session 05 just closed; ProductSpec is not yet battle-tested.
- **Consequence:** Building formula logic now hardcodes assumptions that Session 07 product builds will invalidate
- **Amendment:** W1 formula builders are STUBS ONLY: typed interfaces that raise NotImplementedError. Actual formula generation deferred to wave covering Section 5, after Session 07 validates ProductSpec contract.

#### Executability Checks

**Tool availability:**
- Notion API: Python SDK `notion-client` not in requirements.txt — add
- Composio: Not in repo, no integration — research required
- Browser: Playwright present in S00 env check but not in Python deps — add `playwright` to requirements if browser work proceeds

**Dependency order:**
- PLATFORM_COMPATIBILITY.md (section 1) can proceed immediately ✓
- NotionAdapter interface (section 2) depends on operation taxonomy from S-03 amendment ✓
- Fixture adapter (section 2 + 8) requires typed domain objects (page/database/property/view stubs) ✓
- Router (section 2) requires adapter interface + config ✓
- Sections 3-11 deferred to later waves ✓

**Session 05 continuity:**
- Prompt never mentions Session 05 deliverables (Etsy adapters, A03/A05/A06, ProductSpec, dedupe workflow)
- Session 06 does not depend on any Session 05 output — safe to proceed independently
- Control-file preservation (line 199) correctly requires updating five control files without erasing S05 history

### Dimension 3: Gameability

**Verdict:** CONDITIONAL APPROVE with ONE CRITICAL, TWO HIGH findings

#### Findings

**G-01 [CRITICAL] — Exit criteria satisfiable by stubs**

- **Prompt line:** 203-213 (exit criteria)
- **Gameability:** "Every Notion operation required by the playbook has an adapter path" satisfied by 25+ stub methods that raise NotImplementedError. "Fixture adapter is complete enough for full product E2E" satisfied by fixture that returns empty lists. "Browser sessions and receipts work" satisfied by stub that returns success=True without browser.
- **Why it's a fake:** Stubs satisfy wording without Notion integration working
- **Ungameable wording:** Exit criteria must require: (1) At least one operation implemented end-to-end with real API or browser evidence, (2) Fixture adapter validated by Session 07-style test that constructs page + database + relation + view, (3) Browser receipt includes screenshot evidence or explicit defer decision, (4) Live sandbox smoke documented with operator-authorized workspace isolation plan
- **W1 Amendment:** W1 exit criteria are: (1) PLATFORM_COMPATIBILITY.md updated with per-op method tags, (2) NotionAdapter interface defined with 25+ operation signatures, (3) Fixture adapter returns typed stubs for page/database/property/view CRUD, (4) Router selects fixture|API|browser|combined per config, (5) Unit tests prove router selection + fixture returns, (6) Control: session 6 active, S06 evidence keys false, S05 complete in history, (7) CI green (ruff/tests). Defer ungameable full-integration criteria to later wave.

**G-02 [HIGH] — "Live sandbox smoke" self-certified**

- **Prompt line:** 170-176 (section 9: safe sandbox operations)
- **Gameability:** Agent creates temp page, claims "evidence captured", deletes page. No independent verification that page was real, public link worked, or cleanup succeeded.
- **Ungameable wording:** Live smoke must: (1) Record Notion page ID + URL in durable receipt, (2) Screenshot page as stranger (logged out), (3) Independent operator verifies link returns 200, (4) Cleanup reconciliation proves page deleted or archived with before/after workspace page count
- **W1 Amendment:** Live smoke deferred entirely to later wave. W1 has no live Notion calls.

**G-03 [HIGH] — "Fixture duplication" tested with fake**

- **Prompt line:** 188 (tests: "fixture duplication")
- **Gameability:** Test calls `fixture.duplicate_page(page_id)`, fixture returns `DuplicatedPage(id="new-id")`, test passes. Real Notion duplication never proven.
- **Ungameable wording:** Fixture duplication test must prove: (1) Original page has properties + blocks, (2) Duplicate receives distinct ID, (3) Duplicate properties match original, (4) Duplicate blocks match original, (5) Changes to duplicate don't affect original
- **Amendment:** W1 fixture duplication test satisfies ungameable wording using in-memory fixture state. Real Notion duplication tested in later wave after API/browser adapters implemented.

## 3. Corrective addendum — Wave 1 Execution

**Status:** Executable after all CRITICAL and HIGH findings resolved

This addendum governs Wave 1 execution. The prompt remains the unamended source of record.

### Wave 1 Scope (Bounded)

Execute ONLY:

1. **Notion capability inspection** (Prompt Section 1, lines 10-31)
   - Inspect available methods: Notion official API, Composio actions (if present), browser automation patterns, any existing MCP
   - DO NOT call live Notion APIs
   - DO NOT instantiate browser sessions
   - Research documentation and SDK signatures only

2. **PLATFORM_COMPATIBILITY.md** (Prompt Section 1, line 20)
   - Create or update `docs/architecture/PLATFORM_COMPATIBILITY.md`
   - For each of 25+ operations from prompt lines 36-62, record:
     - `operation`: snake_case operation name
     - `method`: DIRECT_API | COMPOSIO | BROWSER | COMBINED | NOT_IMPLEMENTED
     - `mutates`: true | false
     - `requires_auth`: true | false
     - `idempotent`: true | false
     - `reconcilable`: true | false | N/A
     - `w1_status`: stub | deferred
   - Method selection rationale: prefer DIRECT_API where Notion API supports it, BROWSER for UI-only features (views, formulas, publish settings), COMBINED where API + browser verify together
   - Tag all as `w1_status: stub` or `deferred` — no real implementation in W1

3. **NotionAdapter interface** (Prompt Section 2, lines 34-76)
   - Define `NotionAdapter` protocol or ABC in `src/money_machine/integrations/notion/adapter.py`
   - Declare async methods for all 25+ operations (connection_status, workspace_discovery, create_page, duplicate_page, rename_page, move_page, set_icon, set_cover, add_text_block, add_callout_block, create_database, add_property, create_relation, create_rollup, create_formula, create_linked_view, add_filter, add_sort, create_calendar_view, create_table_view, create_board_view, set_view_title_visibility, add_child_page, publish_page, set_duplicate_as_template, set_search_indexing, get_public_url, unpublish_page, inspect_page, inspect_database, verify_stranger_access)
   - Typed arguments and return values (use Pydantic models or dataclasses)
   - Docstrings stating method, mutates, requires_auth, idempotent per PLATFORM_COMPATIBILITY.md

4. **Fixture adapter skeleton** (Prompt Section 2 + 8, lines 64-76, 156-166)
   - Implement `FixtureNotionAdapter` in `src/money_machine/integrations/notion/fixture_adapter.py`
   - In-memory state: dict of pages, databases, properties, views
   - CRUD stubs return typed domain objects: `NotionPage`, `NotionDatabase`, `NotionProperty`, `NotionView`
   - Stub behavior sufficient for unit tests: create → returns object with ID, duplicate → returns copy with new ID, delete → removes from dict
   - NO live Notion calls
   - NO persistence to database (fixture is ephemeral per test)

5. **Adapter router stubs** (Prompt Section 2, lines 71-76)
   - Implement `NotionAdapterRouter` in `src/money_machine/integrations/notion/router.py`
   - Config-driven selection: reads `config/integrations.yaml` (create if needed) with `notion.adapter_mode: fixture | api | browser | combined`
   - Returns appropriate adapter instance: `FixtureNotionAdapter()` | `APINotionAdapter()` | `BrowserNotionAdapter()` | `CombinedNotionAdapter()`
   - API/Browser/Combined adapter stubs in separate files: `api_adapter.py`, `browser_adapter.py`, `combined_adapter.py`
   - Stub implementations raise `NotImplementedError` with message "Real {API|browser|combined} adapter deferred to Session 06 Wave N"
   - NO browser launch, NO API calls, NO live credentials

6. **Control activation (programme pattern)** (Prompt line 199)
   - Update `IMPLEMENTATION_STATE.json`:
     - `current_session`: 5 → 6
     - `session_status`: "complete" → "incomplete"
     - `completed_sessions`: append 5 stays as [0,1,2,3,4,5] — do not remove
     - `next_session`: 6 → 6 (unchanged, points to self while active)
     - `head_sha`: stays at S05 L4 tip `9b791d45f9461030f09eda8a46838afc5447416c`
     - `last_verified_commit`: stays at bootstrap `1abf0d7cca3a6b8cd7efcd0a45523538fd5bfd9d`
     - `state_revision`: 31 → 32
   - Define Session 06 evidence keys in `SESSION_EVIDENCE_KEYS`:
     ```python
     6: {
         "notion_capability_inspected": False,
         "platform_compatibility_documented": False,
         "notion_adapter_interface_defined": False,
         "fixture_adapter_implemented": False,
         "adapter_router_implemented": False,
         "adapter_unit_tests_pass": False,
         "control_files_and_checkpoint_current": False,
         "evidence_closure_commit_recorded": False,
     }
     ```
   - Install all eight keys as false in `required_completion_evidence`
   - Preserve S05 complete history: do NOT mark S06 complete, do NOT flip S06 evidence to true (except control_files after final W1 checkpoint)
   - Keep Exit78 scheduler HELD: do not touch worker/scheduler lift
   - Carry forward S05 nits from state revision 31
   - Align IMPLEMENTATION_LOG.md, TEST_EVIDENCE.md, DECISIONS.md
   - NO JSON drift: state.json `completed_sessions` must match LOG prose

7. **Unit tests** (Prompt line 180-192, subset for W1)
   - `tests/unit/integrations/notion/test_adapter_interface.py`: NotionAdapter protocol/ABC signature validation
   - `tests/unit/integrations/notion/test_router.py`: config-driven adapter selection (fixture mode returns FixtureNotionAdapter, api mode returns APINotionAdapter stub, etc.)
   - `tests/unit/integrations/notion/test_fixture_adapter.py`: CRUD operations return typed objects, duplicate creates new ID, delete removes from state
   - `tests/unit/integrations/notion/test_api_adapter_stub.py`: verify raises NotImplementedError
   - `tests/unit/integrations/notion/test_browser_adapter_stub.py`: verify raises NotImplementedError
   - CI must pass: `bash scripts/test.sh` exits 0 (ruff format, ruff lint, pyright, pytest)

### Wave 1 OUT OF SCOPE (Hard Boundaries)

DO NOT implement in W1:

- **Section 3** (Browser session management) — deferred to Wave 2+
- **Section 4** (Notion operation receipts) — deferred to Wave 2+ (requires receipt table schema + persistence)
- **Section 5** (Formula and schema builders) — deferred to Wave 3+ (requires Session 07 ProductSpec validation)
- **Section 6** (Relation and linked-view helpers) — deferred to Wave 3+
- **Section 7** (Publishing and isolation helpers) — deferred to Wave 4+
- **Section 9** (Live connection path) — deferred to Wave 4+ (requires operator authorization + sandbox workspace)
- **Section 10** (Tests for live integration) — deferred with live connection path
- **Section 11** (Review and checkpoint) — deferred until Session 06 integration waves complete
- Live Notion API calls
- Live browser automation
- Notion credentials or authentication flows
- Browser profile creation or storage
- Formula generation logic
- Notion receipt persistence
- Exit78 scheduler lift
- SESSION_06 COMPLETE marking

### Wave 1 Exit Criteria

W1 ends when:

1. `docs/architecture/PLATFORM_COMPATIBILITY.md` exists with 25+ operations tagged (method, mutates, requires_auth, idempotent, reconcilable, w1_status)
2. `NotionAdapter` interface defined with 25+ async method signatures + docstrings
3. `FixtureNotionAdapter` returns typed stubs for create/duplicate/delete/inspect operations
4. `NotionAdapterRouter` selects fixture | api_stub | browser_stub | combined_stub per config
5. API/Browser/Combined adapter stubs raise `NotImplementedError` with defer message
6. Control files updated: session 6 active, S06 evidence keys false (except control_files after W1), S05 still in completed_sessions, no S06 complete claim
7. Unit tests prove: router selection logic, fixture CRUD operations, stub NotImplementedError behavior
8. CI green: `bash scripts/test.sh` exits 0 (ruff, pyright, pytest)
9. Draft PR created from `5e87f3fa3a2ec39e775c7a5986b1abf10f1e418a` with clear W1 scope in title/description
10. Operator verification: Exit78 unchanged, no live Notion calls made

### Deferrals

- **Browser session management** (Section 3) → Session 06 Wave 2, owner: TBD
- **Notion receipts table + persistence** (Section 4) → Session 06 Wave 2, requires domain model + migration
- **Formula builders** (Section 5) → Session 06 Wave 3, requires Session 07 ProductSpec battle-test
- **Relation/linked-view helpers** (Section 6) → Session 06 Wave 3
- **Publishing helpers** (Section 7) → Session 06 Wave 4
- **Live connection + sandbox smoke** (Section 9) → Session 06 Wave 4, requires operator authorization
- **SESSION_06 COMPLETE** → After all waves integrated, full test suite green, required reviewers pass, control files updated, canonical commit

## 4. What the Prompt Already Gets Right

- **Adapter abstraction** (line 64-76): Separating API/browser/fixture with router is correct pattern
- **Fixture-first development** (line 164-166): Tests against fixtures before live integration is safe discipline
- **Operation enumeration** (line 36-62): Comprehensive coverage of Notion features required by playbook
- **Control file requirement** (line 199): Preserves programme continuity
- **Safe sandbox principle** (line 170): Temp page creation + cleanup is correct (though deferred in W1)
- **Never commit browser state** (line 88): Correct security boundary

## 5. Recorded Decisions

None. All amendments sharpen the prompt without contradicting workbook business rules. W1 scope reduction is operator instruction, not workbook contradiction.

## 6. Review Sign-Off

**Fidelity:** CONDITIONAL APPROVE (1 HIGH finding resolved by W1 scope reduction)  
**Safety & Executability:** CONDITIONAL APPROVE (2 CRITICAL + 3 HIGH findings resolved by deferring live calls, browser, receipts, formulas)  
**Gameability:** CONDITIONAL APPROVE (1 CRITICAL + 2 HIGH findings resolved by bounded W1 exit criteria, deferring ungameable live criteria)

**Overall Verdict:** EXECUTE WAVE 1 ADDENDUM

**Next Review:** After W1 checkpoint, before Wave 2 begins (to review browser session management + receipts design)
