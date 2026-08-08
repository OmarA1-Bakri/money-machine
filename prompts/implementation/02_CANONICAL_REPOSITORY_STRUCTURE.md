# Canonical Repository and File Structure

Use one private monorepo. Do not create one repository per agent.

```text
hands-off-money-machine/
├── AGENTS.md
├── README.md
├── NOTICE.md
├── .editorconfig
├── .env.example
├── .gitignore
├── .python-version
├── .nvmrc
├── pyproject.toml
├── uv.lock
├── package.json
├── pnpm-workspace.yaml
├── pnpm-lock.yaml
├── compose.yaml
├── compose.prod.yaml
├── Dockerfile
├── Dockerfile.web
│
├── .github/
│   └── workflows/
│       ├── ci.yml
│       ├── e2e.yml
│       └── release.yml
│
├── config/
│   ├── agents.yaml
│   ├── workflows.yaml
│   ├── autonomy.example.yaml
│   ├── product_rules.yaml
│   ├── publishing_ramp.yaml
│   ├── telemetry.yaml
│   └── environments/
│       ├── development.yaml
│       ├── test.yaml
│       └── production.yaml
│
├── docs/
│   ├── control/
│   │   ├── IMPLEMENTATION_STATE.json
│   │   ├── IMPLEMENTATION_LOG.md
│   │   ├── DECISIONS.md
│   │   ├── TEST_EVIDENCE.md
│   │   └── NEXT_SESSION.md
│   │
│   ├── source/
│   │   └── SOURCE_REGISTER.md
│   │
│   ├── playbook/
│   │   ├── BUSINESS_PROCESS.md
│   │   ├── CHAPTER_TO_CAPABILITY_MAP.md
│   │   ├── PROMPT_LIBRARY_MAP.md
│   │   ├── WORKBOOK_DATA_MAP.md
│   │   └── AUTOMATION_GAP_MAP.md
│   │
│   ├── architecture/
│   │   ├── SYSTEM_OVERVIEW.md
│   │   ├── STATE_MACHINE.md
│   │   ├── DATA_MODEL.md
│   │   ├── AGENT_ROSTER.md
│   │   ├── JOB_AND_EVENT_CONTRACTS.md
│   │   ├── ARTIFACT_LINEAGE.md
│   │   ├── INTEGRATION_MATRIX.md
│   │   ├── PLATFORM_COMPATIBILITY.md
│   │   ├── AUTONOMY_MODEL.md
│   │   ├── OBSERVABILITY.md
│   │   └── DEPLOYMENT.md
│   │
│   ├── adr/
│   │   ├── 0001-modular-monolith.md
│   │   ├── 0002-postgres-durable-jobs.md
│   │   ├── 0003-agent-contracts.md
│   │   ├── 0004-provider-adapters.md
│   │   ├── 0005-artifact-lineage.md
│   │   ├── 0006-autonomy-configuration.md
│   │   └── 0007-deterministic-asset-rendering.md
│   │
│   ├── runbooks/
│   │   ├── LOCAL_DEVELOPMENT.md
│   │   ├── ACCOUNT_CONNECTIONS.md
│   │   ├── LIVE_COMMISSIONING.md
│   │   ├── INCIDENTS.md
│   │   ├── BACKUP_RESTORE.md
│   │   └── PROVIDER_RECOVERY.md
│   │
│   └── api/
│       └── OPENAPI_NOTES.md
│
├── prompts/
│   └── implementation/
│       ├── 00_READ_ME_FIRST.md
│       ├── 01_MASTER_CONTROL_PROMPT.md
│       ├── ...
│       └── 19_RECOVERY_AND_CONTINUATION_PROMPT.md
│
├── private/
│   └── source/
│       ├── .gitkeep
│       └── The-Hands-Off-Money-Machine-Playbook.pdf
│           # local only, gitignored
│
├── src/
│   └── money_machine/
│       ├── __init__.py
│       ├── version.py
│       │
│       ├── config/
│       │   ├── __init__.py
│       │   ├── settings.py
│       │   ├── loader.py
│       │   └── validation.py
│       │
│       ├── domain/
│       │   ├── __init__.py
│       │   ├── enums.py
│       │   ├── errors.py
│       │   ├── events.py
│       │   ├── value_objects.py
│       │   ├── models/
│       │   │   ├── shop.py
│       │   │   ├── workflow.py
│       │   │   ├── job.py
│       │   │   ├── research.py
│       │   │   ├── candidate.py
│       │   │   ├── product_spec.py
│       │   │   ├── product.py
│       │   │   ├── variant.py
│       │   │   ├── asset.py
│       │   │   ├── listing.py
│       │   │   ├── metrics.py
│       │   │   ├── experiment.py
│       │   │   ├── incident.py
│       │   │   └── customer_issue.py
│       │   └── services/
│       │       ├── low_ticket.py
│       │       ├── dedupe.py
│       │       ├── product_rules.py
│       │       ├── claim_validation.py
│       │       ├── maturity.py
│       │       └── cull_multiply.py
│       │
│       ├── application/
│       │   ├── __init__.py
│       │   ├── commands/
│       │   ├── queries/
│       │   ├── handlers/
│       │   └── services/
│       │       ├── research_service.py
│       │       ├── product_service.py
│       │       ├── listing_service.py
│       │       ├── analytics_service.py
│       │       └── incident_service.py
│       │
│       ├── orchestration/
│       │   ├── __init__.py
│       │   ├── engine.py
│       │   ├── worker.py
│       │   ├── scheduler.py
│       │   ├── leases.py
│       │   ├── dependency_resolver.py
│       │   ├── transition_guard.py
│       │   ├── idempotency.py
│       │   ├── retry.py
│       │   ├── event_dispatcher.py
│       │   ├── successor_factory.py
│       │   └── workflows/
│       │       ├── product_experiment.py
│       │       ├── competitor_teardown.py
│       │       ├── publish_listing.py
│       │       ├── weekly_review.py
│       │       ├── monthly_deep_pass.py
│       │       └── incident_repair.py
│       │
│       ├── agents/
│       │   ├── __init__.py
│       │   ├── base.py
│       │   ├── registry.py
│       │   ├── runtime.py
│       │   ├── prompt_store.py
│       │   ├── tool_registry.py
│       │   ├── contracts/
│       │   │   ├── common.py
│       │   │   ├── account_integration.py
│       │   │   ├── market_research.py
│       │   │   ├── competitor_teardown.py
│       │   │   ├── product_strategy.py
│       │   │   ├── catalogue_dedupe.py
│       │   │   ├── notion_builder.py
│       │   │   ├── variant_builder.py
│       │   │   ├── product_qa.py
│       │   │   ├── merchandising.py
│       │   │   ├── creative_assets.py
│       │   │   ├── preflight.py
│       │   │   ├── etsy_publishing.py
│       │   │   ├── analytics.py
│       │   │   ├── cull_multiply.py
│       │   │   └── support_repair.py
│       │   ├── prompts/
│       │   │   ├── A01_shop_orchestrator.md
│       │   │   ├── A02_account_integration.md
│       │   │   ├── A03_market_research.md
│       │   │   ├── A04_competitor_teardown.md
│       │   │   ├── A05_product_strategy.md
│       │   │   ├── A06_catalogue_dedupe.md
│       │   │   ├── A07_notion_product_builder.md
│       │   │   ├── A08_variant_builder.md
│       │   │   ├── A09_product_qa.md
│       │   │   ├── A10_merchandising.md
│       │   │   ├── A11_creative_assets.md
│       │   │   ├── A12_preflight.md
│       │   │   ├── A13_etsy_publishing.md
│       │   │   ├── A14_analytics.md
│       │   │   ├── A15_cull_multiply.md
│       │   │   └── A16_support_repair.md
│       │   └── implementations/
│       │       ├── account_integration.py
│       │       ├── market_research.py
│       │       ├── competitor_teardown.py
│       │       ├── product_strategy.py
│       │       ├── catalogue_dedupe.py
│       │       ├── notion_product_builder.py
│       │       ├── variant_builder.py
│       │       ├── product_qa.py
│       │       ├── merchandising.py
│       │       ├── creative_assets.py
│       │       ├── preflight.py
│       │       ├── etsy_publishing.py
│       │       ├── analytics.py
│       │       ├── cull_multiply.py
│       │       └── support_repair.py
│       │
│       ├── integrations/
│       │   ├── __init__.py
│       │   ├── etsy/
│       │   │   ├── interface.py
│       │   │   ├── api_adapter.py
│       │   │   ├── browser_adapter.py
│       │   │   ├── fixture_adapter.py
│       │   │   ├── auth.py
│       │   │   ├── mappers.py
│       │   │   └── errors.py
│       │   ├── notion/
│       │   │   ├── interface.py
│       │   │   ├── api_adapter.py
│       │   │   ├── browser_adapter.py
│       │   │   ├── fixture_adapter.py
│       │   │   ├── auth.py
│       │   │   ├── formulas.py
│       │   │   └── errors.py
│       │   ├── composio/
│       │   │   ├── client.py
│       │   │   └── capability_map.py
│       │   ├── browser/
│       │   │   ├── session_manager.py
│       │   │   ├── profiles.py
│       │   │   ├── selectors.py
│       │   │   ├── screenshots.py
│       │   │   └── reconciliation.py
│       │   ├── llm/
│       │   │   ├── interface.py
│       │   │   ├── openai_provider.py
│       │   │   ├── fake_provider.py
│       │   │   └── structured_output.py
│       │   ├── posthog/
│       │   │   ├── client.py
│       │   │   └── events.py
│       │   ├── storage/
│       │   │   ├── interface.py
│       │   │   ├── local.py
│       │   │   └── s3.py
│       │   └── messaging/
│       │       ├── interface.py
│       │       └── etsy_messages.py
│       │
│       ├── assets/
│       │   ├── renderer.py
│       │   ├── screenshots.py
│       │   ├── video.py
│       │   ├── pdf.py
│       │   ├── link_validator.py
│       │   ├── design_tokens.py
│       │   └── templates/
│       │       ├── listing/
│       │       ├── pdf/
│       │       └── video/
│       │
│       ├── persistence/
│       │   ├── __init__.py
│       │   ├── database.py
│       │   ├── tables.py
│       │   ├── unit_of_work.py
│       │   └── repositories/
│       │       ├── jobs.py
│       │       ├── workflows.py
│       │       ├── events.py
│       │       ├── agents.py
│       │       ├── research.py
│       │       ├── products.py
│       │       ├── listings.py
│       │       ├── metrics.py
│       │       ├── artifacts.py
│       │       └── incidents.py
│       │
│       ├── api/
│       │   ├── __init__.py
│       │   ├── main.py
│       │   ├── dependencies.py
│       │   ├── schemas.py
│       │   └── routers/
│       │       ├── health.py
│       │       ├── workflows.py
│       │       ├── jobs.py
│       │       ├── products.py
│       │       ├── listings.py
│       │       ├── metrics.py
│       │       ├── incidents.py
│       │       ├── integrations.py
│       │       └── settings.py
│       │
│       ├── observability/
│       │   ├── logging.py
│       │   ├── telemetry.py
│       │   ├── receipts.py
│       │   └── correlation.py
│       │
│       └── cli/
│           ├── main.py
│           └── commands/
│               ├── database.py
│               ├── workflow.py
│               ├── worker.py
│               ├── scheduler.py
│               ├── integrations.py
│               └── commission.py
│
├── apps/
│   └── web/
│       ├── app/
│       │   ├── layout.tsx
│       │   ├── page.tsx
│       │   ├── pipeline/page.tsx
│       │   ├── shop/page.tsx
│       │   ├── blocked/page.tsx
│       │   ├── decisions/page.tsx
│       │   ├── incidents/page.tsx
│       │   └── settings/page.tsx
│       ├── components/
│       ├── lib/
│       ├── public/
│       ├── tests/
│       ├── package.json
│       ├── tsconfig.json
│       └── next.config.ts
│
├── migrations/
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│
├── tests/
│   ├── unit/
│   │   ├── domain/
│   │   ├── orchestration/
│   │   ├── agents/
│   │   └── assets/
│   ├── contract/
│   │   ├── agents/
│   │   └── integrations/
│   ├── integration/
│   │   ├── database/
│   │   ├── orchestration/
│   │   ├── etsy/
│   │   ├── notion/
│   │   └── posthog/
│   ├── e2e/
│   │   ├── test_happy_path.py
│   │   ├── test_cull_path.py
│   │   ├── test_multiply_path.py
│   │   ├── test_broken_link_repair.py
│   │   └── test_restart_recovery.py
│   ├── failure_injection/
│   │   ├── test_duplicate_publish.py
│   │   ├── test_expired_lease.py
│   │   ├── test_uncertain_external_effect.py
│   │   └── test_expired_credentials.py
│   └── fixtures/
│       ├── etsy/
│       ├── notion/
│       ├── research/
│       └── llm/
│
├── scripts/
│   ├── bootstrap.ps1
│   ├── bootstrap.sh
│   ├── dev.ps1
│   ├── dev.sh
│   ├── test.ps1
│   ├── test.sh
│   ├── e2e.ps1
│   ├── e2e.sh
│   ├── backup.ps1
│   ├── backup.sh
│   ├── restore.ps1
│   ├── restore.sh
│   ├── commission.ps1
│   └── commission.sh
│
├── infra/
│   ├── docker/
│   ├── caddy/
│   │   └── Caddyfile
│   └── deploy/
│       ├── install-service.sh
│       └── update.sh
│
└── runtime/
    ├── artifacts/
    ├── screenshots/
    ├── receipts/
    ├── browser-profiles/
    └── temp/
        # entire runtime directory is gitignored except optional .gitkeep files
```

## Structural rules

1. Business rules live in `domain`, not only in prompts.
2. External mutations live behind integration adapters.
3. Agent prompts are versioned source files.
4. Agent schemas are Python contracts and tests.
5. Runtime artifacts, screenshots, browser profiles and secrets never enter git.
6. The source PDF remains local and gitignored unless Omar explicitly directs otherwise.
7. The operator web app is a client of the API; it must not implement business state transitions.
8. The worker and scheduler use the same Python package as the API.
9. No agent creates its own database or private untracked state.
10. No session creates a second orchestration engine.
