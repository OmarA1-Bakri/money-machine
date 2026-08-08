# Final Acceptance Checklist

This checklist is used in Session 15. Every line requires evidence.

## Repository and runtime

- [ ] Canonical private repository exists.
- [ ] Windows and WSL2 paths are documented.
- [ ] Private source PDF is excluded from git.
- [ ] Prompt pack is stored in the repo.
- [ ] Fresh bootstrap succeeds.
- [ ] Production compose succeeds.
- [ ] Database migrations succeed.
- [ ] Backup and restore succeed.
- [ ] API, worker, scheduler, web and PostgreSQL are healthy.
- [ ] Restart recovery succeeds.

## Orchestration

- [ ] PostgreSQL durable jobs are active.
- [ ] Dependencies block and release correctly.
- [ ] Leases prevent double execution.
- [ ] Expired leases recover.
- [ ] Idempotency suppresses duplicates.
- [ ] Timers survive restart.
- [ ] Thirty-day maturity is durable.
- [ ] Weekly and monthly schedules are durable.
- [ ] Successors are created transactionally.
- [ ] Uncertain external effects reconcile before retry.

## Agents

- [ ] A01 Shop Orchestrator commissioned.
- [ ] A02 Account & Integration commissioned.
- [ ] A03 Market Research commissioned.
- [ ] A04 Competitor Teardown commissioned.
- [ ] A05 Product Strategy commissioned.
- [ ] A06 Catalogue Dedupe commissioned.
- [ ] A07 Notion Product Builder commissioned.
- [ ] A08 Variant Builder commissioned.
- [ ] A09 Product QA commissioned.
- [ ] A10 Merchandising commissioned.
- [ ] A11 Creative Asset commissioned.
- [ ] A12 Preflight commissioned.
- [ ] A13 Etsy Publishing commissioned.
- [ ] A14 Analytics commissioned.
- [ ] A15 Cull & Multiply commissioned.
- [ ] A16 Customer Support & Repair commissioned.

## Playbook workflow

- [ ] Research evidence grid is generated.
- [ ] Shortlist of five is generated.
- [ ] Low-Ticket score out of forty is generated.
- [ ] Primary and backup are selected.
- [ ] Competitor teardown workflow exists.
- [ ] ProductSpec is versioned.
- [ ] Dedupe fails and reconcepts automatically.
- [ ] Notion product builds automatically.
- [ ] Shared databases and linked views work.
- [ ] Notification dashboard works.
- [ ] Six to eight hubs exist.
- [ ] Three or four variants exist.
- [ ] Public links are isolated.
- [ ] Product facts are extracted.
- [ ] Listing title is generated.
- [ ] Eight-part description is generated.
- [ ] Exactly thirteen tags are generated.
- [ ] Ten images are generated.
- [ ] Video is generated.
- [ ] README/access PDF is generated.
- [ ] Optional free-gift PDF path exists.
- [ ] Every link is tested.
- [ ] Etsy draft is created.
- [ ] Preflight blocks defects.
- [ ] Publication ramp works.
- [ ] Live auto-publication can be enabled without code change.
- [ ] Post-publish verification works.
- [ ] Weekly metrics are collected.
- [ ] No demand verdict occurs before thirty days.
- [ ] Mature loser is culled and deactivated.
- [ ] Winner creates successor ProductSpec and build job.
- [ ] Monthly deep pass creates work.
- [ ] Customer issue creates repair workflow.

## Product integrity

- [ ] Claims reference verified ProductFacts.
- [ ] No invented reviews or trust counts.
- [ ] Asset lineage is complete.
- [ ] Stale assets invalidate after product change.
- [ ] Fresh duplicate test passes.
- [ ] Wrong link repair passes.
- [ ] Cross-catalogue access test passes.
- [ ] Listing versions are retained.
- [ ] Deactivated products retain evidence.

## Integrations

- [ ] LLM provider connected.
- [ ] Notion connected.
- [ ] Etsy connected.
- [ ] Composio capability map recorded.
- [ ] PostHog connected.
- [ ] Browser profiles persist outside git.
- [ ] Provider receipts exist.
- [ ] Credential expiry produces exact blocker.
- [ ] Fixture adapters cover all external providers.

## Operator experience

- [ ] NOW page reflects current work.
- [ ] PIPELINE page reflects workflow stages.
- [ ] SHOP page reflects listings and metrics.
- [ ] BLOCKED contains only genuine blockers.
- [ ] DECISIONS shows cull/multiply outcomes.
- [ ] INCIDENTS shows repairs.
- [ ] SETTINGS changes standing authority.
- [ ] No routine approval queue exists.
- [ ] PostHog operational events are visible.

## Test paths

- [ ] Full happy path passes.
- [ ] Full cull path passes.
- [ ] Full multiply path passes.
- [ ] Full repair path passes.
- [ ] Dedupe/reconcept path passes.
- [ ] Worker crash recovery passes.
- [ ] Scheduler restart passes.
- [ ] Duplicate publish suppression passes.
- [ ] Uncertain external effect passes.
- [ ] Expired credentials path passes.
- [ ] Backup/restore path passes.
- [ ] Full lint/type/unit/integration/E2E suite passes.

## Live commissioning

- [ ] Standing authority configured once.
- [ ] First real research run completed.
- [ ] First real ProductSpec completed.
- [ ] First real Notion product completed.
- [ ] First real listing package completed.
- [ ] First real Etsy draft completed.
- [ ] Live publication completed where authorised.
- [ ] Weekly metrics schedule exists.
- [ ] Thirty-day maturity schedule exists.
- [ ] Runtime can continue without manual handoff.
- [ ] Final handover and acceptance documents exist.
- [ ] Release `v1.0.0` exists.
