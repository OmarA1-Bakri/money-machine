# Integration Matrix

**Assessment date:** 2026-08-26 (operation codes and channel corrections added 2026-09-07)

**Safety boundary:** This assessment used repository configuration and available tool metadata only. It did not inspect credentials, token values, cookies, connected-browser contents, customer/provider payloads, the private PDF, or foreign-agent configuration. No live provider operation was executed.

## Availability summary

| Capability | Safe current evidence | Availability state |
|---|---|---|
| Etsy API/client | No commissioned adapter or safely probed application credential | `NOT_SAFELY_PROBED` |
| Notion API | No commissioned adapter or safely probed application credential | `NOT_SAFELY_PROBED` |
| Composio actions | No admitted Composio operation surface available to this implementation session | `UNAVAILABLE` |
| Connected browser | Repository browser adapter/profile is uncommissioned; profile contents were not inspected | `NOT_SAFELY_PROBED` |
| PostHog | `config/telemetry.yaml` is disabled and no commissioned client exists | `DISABLED` |
| Artifact storage | Denied local runtime scaffold exists; storage adapter is uncommissioned | `DESIGNED_NOT_COMMISSIONED` |
| LLM provider | No commissioned application provider; the development agent's authentication is not product authority | `NOT_SAFELY_PROBED` |
| Internal renderer | Architecture selected; implementation and browser pinning are absent | `DESIGNED_NOT_COMMISSIONED` |

Unknown external availability fails closed. `MANUAL_EXTERNAL_BLOCKER` means the operation has no safely admitted automated path now; it is not a routine approval queue.

**Vendor capability status: UNVERIFIED.** Each `DIRECT_API` selection below records the intended channel. No Etsy Open API or Notion API primary source has been read against a pinned version for these operations, so whether the vendor supports each operation, its rate limits, and its authorization scopes remain unverified until the owning session reads the current vendor reference and records the citation here.

## Etsy operations

Every row names the `capability_operation` code used in `config/workflows.yaml` and `config/agents.yaml`; a test asserts that the codes and channels agree with the configuration.

| Operation | Operation code | Selected channel | Current state | Authority | Reconcile before retry | Blocker |
|---|---|---|---|---|---|---|
| provider account provisioning | `ACCOUNT_PROVISIONING` | `MANUAL_EXTERNAL_BLOCKER` | holder-only account creation and verification | account holder | no | `PROVIDER_HOLDER_ACTION_REQUIRED` |
| shop/account provisioning | `ETSY_SHOP_PROVISION` | `MANUAL_EXTERNAL_BLOCKER` | holder-only identity, bank and shop setup | account holder | no | `ETSY_HOLDER_ACTION_REQUIRED` |
| research browsing and search evidence | `MARKET_RESEARCH_READ` | `BROWSER` | not safely probed | connected browser; compliant read | no | `ETSY_BROWSER_UNAVAILABLE` |
| listing detail and metrics read | `ETSY_METRICS_READ` | `DIRECT_API` | not safely probed | read credential | no | `ETSY_CREDENTIAL_REQUIRED` |
| draft read for preflight | `ETSY_DRAFT_READ` | `DIRECT_API` | not safely probed | read credential | no | `ETSY_CREDENTIAL_REQUIRED` |
| draft creation, listing fields, tags, media upload, digital files, price, sale and quantity | `ETSY_DRAFT_WRITE` | `DIRECT_API` | not safely probed | draft/live + mutation authority | yes | `ETSY_DRAFT_CAPABILITY_UNVERIFIED` |
| publication | `ETSY_PUBLISH` | `DIRECT_API` | not safely probed | live + `auto_publish` + weekly cap | yes | `ETSY_PUBLISH_NOT_COMMISSIONED` |
| deactivation | `ETSY_DEACTIVATE` | `DIRECT_API` | not safely probed | live + `auto_deactivate` | yes | `ETSY_DEACTIVATE_NOT_COMMISSIONED` |
| listing update and repair | `ETSY_LISTING_REPAIR` | `DIRECT_API` | not safely probed | draft/live + incident scope | yes | `ETSY_UPDATE_NOT_COMMISSIONED` |
| post-publish visibility and checkout/buyer-chain test | `ETSY_POST_PUBLISH_CHECKOUT` | `BROWSER` | not safely probed | live checkout enabled + cap | yes | `ETSY_CHECKOUT_NOT_AUTHORISED` |
| competitor purchase | `COMPETITOR_PURCHASE` | `BROWSER` | not safely probed | live spend + per-item and monthly caps | yes | `PURCHASE_AUTHORITY_REQUIRED` |
| customer-message intake | `CUSTOMER_SUPPORT_READ` | `MANUAL_EXTERNAL_BLOCKER` | unknown provider coverage | holder-authorized access | yes | `ETSY_MESSAGE_CHANNEL_UNKNOWN` |
| proof-recipient messages | `PROOF_DISTRIBUTION` | `MANUAL_EXTERNAL_BLOCKER` | no consent/recipient contract commissioned | explicit recipient authority | yes | `MESSAGE_AUTHORITY_REQUIRED` |

Composio may replace a selected Etsy channel only after an operation-specific safe probe demonstrates compatible fields, idempotency, reconciliation, and reliability. It is not selected speculatively.

## Notion operations

| Operation | Operation code | Selected channel | Current state | Authority | Reconcile before retry | Blocker |
|---|---|---|---|---|---|---|
| workspace provisioning | `NOTION_WORKSPACE_PROVISION` | `MANUAL_EXTERNAL_BLOCKER` | holder-only account creation | account holder | no | `NOTION_HOLDER_ACTION_REQUIRED` |
| shop HQ, catalogue and workbook records | `NOTION_SHOP_HQ_WRITE` | `DIRECT_API` | not safely probed | draft/live workspace write | yes | `NOTION_API_NOT_COMMISSIONED` |
| pages, databases, properties, relations, rollups, formulas, icons and covers | `NOTION_PRODUCT_WRITE` | `DIRECT_API` | not safely probed | draft/live workspace write | yes | `NOTION_API_NOT_COMMISSIONED` |
| colour and identity variant pages | `NOTION_VARIANT_WRITE` | `DIRECT_API` | not safely probed | draft/live workspace write | yes | `NOTION_API_NOT_COMMISSIONED` |
| incident-scoped source repair | `NOTION_PRODUCT_REPAIR` | `DIRECT_API` | not safely probed | draft/live workspace write | yes | `NOTION_API_NOT_COMMISSIONED` |
| build read for QA | `NOTION_BUILD_READ` | `DIRECT_API` | not safely probed | read credential | no | `NOTION_API_NOT_COMMISSIONED` |
| linked views, filters, layouts, duplication-as-template, search indexing, public publishing and secret-link collection | `NOTION_LINK_PUBLISH` | `BROWSER` | not safely probed | connected browser write; publish-link authority | yes | `NOTION_PUBLISH_NOT_COMMISSIONED` |
| fresh-view, duplication and delivery-link verification | `NOTION_LINK_READ` | `BROWSER` | not safely probed | isolated browser read | no | `NOTION_BROWSER_UNAVAILABLE` |
| truthful product screenshots | `NOTION_SCREENSHOT_READ` | `BROWSER` | not safely probed | isolated browser read | no | `NOTION_BROWSER_UNAVAILABLE` |

Views, formulas, sharing, publishing and other interface-only operations stay on `BROWSER` per workbook section 12. The `DIRECT_API` rows above cover structured page and database content only.

## Internal and supporting operations

| Operation | Provider | Selected channel | Current state | Authority/reconciliation | Blocker |
|---|---|---|---|---|---|
| structured model output | configured LLM | `DIRECT_API` | not safely probed | no commercial effect; strict schema required | `LLM_PROVIDER_NOT_COMMISSIONED` |
| operational telemetry | PostHog | `DIRECT_API` | disabled | opt-in config; never workflow authority | `POSTHOG_DISABLED` |
| render images/PDF/video | internal Playwright factory | `INTERNAL_RENDERER` | designed, not commissioned | no network; deterministic manifest | `RENDERER_NOT_COMMISSIONED` |
| artifact bytes | local storage adapter initially | `DIRECT_API` | scaffold only | denied path, hashes, atomic write | `STORAGE_NOT_COMMISSIONED` |
| canonical workflow state | PostgreSQL | `DIRECT_API` | Compose contract exists; runtime not proved here | authenticated DB and migrations | `DATABASE_RUNTIME_UNVERIFIED` |
| test provider behavior | fixtures | `DIRECT_API` | scaffold fixtures only | simulation only; cannot prove live capability | `FIXTURES_NOT_COMMISSIONED` |
