# Platform Compatibility Matrix — Notion Integration

**Status:** Wave 1 capability inspection  
**Session:** 06  
**Last Updated:** 2026-09-24  
**Scope:** Method selection for 25+ Notion operations required by playbook product builds

## Method Taxonomy

| Method | Description |
|--------|-------------|
| `DIRECT_API` | Notion Official API via Python SDK (notion-client) |
| `COMPOSIO` | Composio Notion actions (if present) |
| `BROWSER` | Browser automation (Playwright) for UI-only features |
| `COMBINED` | API + browser for create-verify patterns |
| `NOT_IMPLEMENTED` | Not yet supported in any method |

## Operation Contracts

| Operation | Method | Mutates | Requires Auth | Idempotent | Reconcilable | W1 Status | Notes |
|-----------|--------|---------|---------------|------------|--------------|-----------|-------|
| `connection_status` | DIRECT_API | false | true | true | N/A | stub | Check API token validity via /v1/users/me |
| `workspace_discovery` | DIRECT_API | false | true | true | N/A | stub | List accessible workspaces via /v1/search |
| `create_page` | DIRECT_API | true | true | false | true | stub | POST /v1/pages; idempotency via external_id |
| `duplicate_page` | BROWSER | true | true | false | true | stub | UI-only; no API equivalent |
| `rename_page` | DIRECT_API | true | true | true | true | stub | PATCH /v1/pages/{id} title property |
| `move_page` | DIRECT_API | true | true | true | true | stub | PATCH /v1/pages/{id} parent |
| `set_icon` | DIRECT_API | true | true | true | true | stub | PATCH /v1/pages/{id} icon (emoji or external URL) |
| `set_cover` | DIRECT_API | true | true | true | true | stub | PATCH /v1/pages/{id} cover (external URL) |
| `add_text_block` | DIRECT_API | true | true | false | true | stub | PATCH /v1/blocks/{id}/children append paragraph |
| `add_callout_block` | DIRECT_API | true | true | false | true | stub | PATCH /v1/blocks/{id}/children append callout |
| `create_database` | DIRECT_API | true | true | false | true | stub | POST /v1/databases; idempotency via title + parent check |
| `add_property` | DIRECT_API | true | true | true | true | stub | PATCH /v1/databases/{id} properties |
| `create_relation` | DIRECT_API | true | true | true | true | stub | PATCH /v1/databases/{id} add relation property |
| `create_rollup` | DIRECT_API | true | true | true | true | stub | PATCH /v1/databases/{id} add rollup property |
| `create_formula` | BROWSER | true | true | true | true | stub | Formula editor UI-only; API supports read but not write |
| `create_linked_view` | BROWSER | true | true | false | true | stub | Linked database UI-only; no API equivalent |
| `add_filter` | DIRECT_API | true | true | true | true | stub | Part of database query filter (GET /v1/databases/{id}/query) |
| `add_sort` | DIRECT_API | true | true | true | true | stub | Part of database query sorts (GET /v1/databases/{id}/query) |
| `create_calendar_view` | BROWSER | true | true | false | true | stub | View creation UI-only; API supports querying views |
| `create_table_view` | BROWSER | true | true | false | true | stub | View creation UI-only |
| `create_board_view` | BROWSER | true | true | false | true | stub | View creation UI-only |
| `set_view_title_visibility` | BROWSER | true | true | true | true | stub | View settings UI-only |
| `add_child_page` | DIRECT_API | true | true | false | true | stub | POST /v1/pages with parent page_id |
| `publish_page` | BROWSER | true | true | true | true | stub | Share settings UI ("Share to web"); no API equivalent |
| `set_duplicate_as_template` | BROWSER | true | true | true | true | stub | Page settings UI; no API equivalent |
| `set_search_indexing` | BROWSER | true | true | true | true | stub | Page settings UI ("Allow search engines"); no API |
| `get_public_url` | COMBINED | false | true | true | N/A | stub | API returns page.public_url if published; browser verifies stranger access |
| `unpublish_page` | BROWSER | true | true | true | true | stub | Disable "Share to web" via UI; no API |
| `inspect_page` | DIRECT_API | false | true | true | N/A | stub | GET /v1/pages/{id} + GET /v1/blocks/{id}/children |
| `inspect_database` | DIRECT_API | false | true | true | N/A | stub | GET /v1/databases/{id} returns schema |
| `verify_stranger_access` | BROWSER | false | false | true | N/A | stub | Open public URL in logged-out browser; verify 200 |

## Method Selection Rationale

### DIRECT_API Operations

The Notion Official API (v1) supports:
- **CRUD operations**: Pages, databases, blocks, properties
- **Content manipulation**: Text, callouts, child pages, icons, covers
- **Relation setup**: Relations, rollups (read/write)
- **Inspection**: Read page/database metadata and content

**Limitations**:
- No formula write (formula editor is UI-only; API is read-only)
- No view creation (calendar, table, board views require UI)
- No linked database views (UI-only feature)
- No publishing settings (share-to-web, search indexing, duplicate-as-template)

**SDK**: `notion-client` (Python) — not currently in requirements.txt; W1 adds stub only

### BROWSER Operations

Playwright-based browser automation required for:
- **View management**: Create calendar/table/board views, set view title visibility
- **Formula editing**: Formula editor UI (API supports formula read but not write)
- **Linked databases**: Create linked database view from canonical database
- **Publishing**: Share to web, duplicate as template, search indexing settings
- **Duplication**: Duplicate page (UI-only; no API endpoint)

**Requirements**:
- Authenticated browser profile (stored in `runtime/browser-profiles/`, git-ignored)
- Selector abstraction for UI stability
- Screenshot capture on error
- Reconciliation after uncertain clicks
- Deferred to Wave 2+

### COMBINED Operations

API + browser verification for:
- **Public URL retrieval**: API returns `page.public_url` if published; browser verifies stranger (logged-out) access returns 200
- Future: Create-via-API + verify-via-browser patterns

### COMPOSIO Status

**As of W1**: No Composio integration present in repo. If Composio Notion actions become available:
- Check coverage against this matrix
- Prefer Composio for operations where it provides better reliability/receipts than raw API
- Update method column to `COMPOSIO` for covered operations

**W1 Decision**: Defer Composio research to Wave 2+; proceed with DIRECT_API + BROWSER design

## Idempotency & Reconciliation Notes

### Idempotent Operations

Can be safely retried without duplicate effects:
- `rename_page`, `move_page`, `set_icon`, `set_cover`: PATCH operations with new value
- `add_property`, `create_relation`, `create_rollup`: Adding property with same name is idempotent update
- `create_formula`: Updating formula property is idempotent
- `add_filter`, `add_sort`: Query filters/sorts are request parameters, not persisted state
- `set_view_title_visibility`, `publish_page`, `set_duplicate_as_template`, `set_search_indexing`: Boolean settings are idempotent toggles

### Non-Idempotent Operations

Require external idempotency keys or reconciliation:
- `create_page`: Use external_id or check title + parent before retry
- `duplicate_page`: Always creates new page; requires receipt to detect double-execution
- `add_text_block`, `add_callout_block`: Appending blocks is not idempotent
- `create_database`: Check title + parent before retry
- `add_child_page`: Check existing children before retry
- `create_linked_view`, `create_calendar_view`, `create_table_view`, `create_board_view`: View creation not idempotent

### Reconcilable Operations

After uncertain operation (e.g. browser click with unknown outcome):
1. **Inspect post-state**: Use API inspection to check if effect occurred
2. **Compare pre/post**: If pre-state captured, diff to detect change
3. **Receipt decision**: Success if effect detected, Unknown if unable to verify, Failure if neither

All mutation operations are reconcilable via API inspection, even if created via browser.

## W1 Implementation Status

**All operations**: Stub implementations only

- **NotionAdapter interface**: Async method signatures defined
- **FixtureNotionAdapter**: In-memory stubs return typed domain objects
- **APINotionAdapter**: Raises `NotImplementedError("Real API adapter deferred to Session 06 Wave 2+")`
- **BrowserNotionAdapter**: Raises `NotImplementedError("Real browser adapter deferred to Session 06 Wave 2+")`
- **CombinedNotionAdapter**: Raises `NotImplementedError("Real combined adapter deferred to Session 06 Wave 2+")`

**No live Notion calls in W1**.

## Next Wave Priorities

**Wave 2**: Implement DIRECT_API adapter for core CRUD operations (create_page, create_database, add_property, inspect_page, inspect_database)

**Wave 3**: Implement BROWSER adapter for UI-only features (formulas, views, publishing, linked databases)

**Wave 4**: Implement COMBINED patterns (API create + browser verify)

**Wave 5**: Notion operation receipts table + persistence + idempotency keys

## References

- Notion API Reference: https://developers.notion.com/reference/intro
- Notion API Changelog: https://developers.notion.com/page/changelog
- Notion Python SDK: https://github.com/ramnes/notion-sdk-py
- Session 06 Prompt: `prompts/implementation/09_SESSION_06_NOTION_INTEGRATION_FOUNDATION.md`
- Prompt Integrity Review: `docs/control/reviews/2026-09-24-session-06-prompt-integrity.md`
