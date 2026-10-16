# Session 10 Prompt Integrity Review

**Date:** 2026-10-16
**Prompt:** `prompts/implementation/13_SESSION_10_ANALYTICS_CULL_MULTIPLY_CLOSED_LOOP.md`
**Verified SHA-256:** `250a666a2e0e81790066b96caaf0f017fde59027cc2921b1417ea71c99677e7a`
**Base:** `edc0632fb43777d834053d5dbfe42f31f3478ab7` (`#105` merged). Session 10 is not activated. `current_session` stays 7. `state_revision` stays 64. Exit 78 stays HELD.

The prompt file is not amended. This record is the corrective addendum. Reviews: [S10 fidelity review](https://cursor.com/agents/bc-be37c08d-be9b-5cb0-9b70-d8b17c457204), [S10 safety review](https://cursor.com/agents/bc-9bac1276-8727-5f47-9f9f-eeedddc3b2af), [S10 gameability review](https://cursor.com/agents/bc-024873e3-0625-5dda-b840-446a53a12956). All three returned CONDITIONAL APPROVE.

## 1. Prompt authenticity

**Status:** VERIFIED

The extracted file's SHA-256 equals the workbook appendix entry for `13_SESSION_10_ANALYTICS_CULL_MULTIPLY_CLOSED_LOOP.md` (4,813 bytes, 234 lines). The required exit string in the file is `SESSION_10_CLOSED_LOOP_AUTOMATION_COMPLETE`.

## 2. Three-dimensional review

### Fidelity

**Verdict:** CONDITIONAL APPROVE.

**F-01 [CRITICAL] — Session 10 would close while Sessions 08 and 09 are inactive.** D-0010 separates activation from completion. D-0032 keeps `current_session` at 7. **Amendment:** This wave does not activate Session 10, does not emit the exit string, and does not edit `IMPLEMENTATION_STATE.json`. **Deferral:** activation and the exit string. Owner: the operator, after Sessions 08 and 09 are closed.

**F-02 [CRITICAL] — Commissioning A14 and A15 after tests.** Both stay `DESIGNED` with empty `commissioning_evidence`. D-0028 requires an operator decision and a simulation run through analytics before `COMMISSIONED`. **Amendment:** Do not edit `config/agents.yaml`. Contract tests may use a deterministic fake. **Deferral:** promotion to `TESTED` or `COMMISSIONED`. Owner: the operator under D-0028.

**F-03 [HIGH] — `published_at + 30 days` contradicts D-0014.** Maturity is thirty accumulated live UTC 24-hour periods. Paused or deactivated time does not count. `scheduled_triggers.trigger_kind` admits `WEEKLY_REVIEW`, `MONTHLY_DEEP_PASS`, and `BUILD_SLOT` only. **Amendment:** This wave's clock counts accumulated live periods and excludes paused time. It does not store `published_at + 30 days`, does not call `schedule_maturity_timer`, and does not add a trigger kind or job type. Defects still open repair work immediately. This discharges Session 09 D-05 for the pure clock. It is not deferred again.

**F-04 [HIGH] — Bottom 80 percent is not a deletion quota, and A15 must not emit `LISTING_CULLED`.** D-0014: cohorts smaller than five are not percentile-eligible, ties stay out, and a `CULL` still needs metrics evidence plus a separately authorized deactivation job. The graph emits `LISTING_CULL_REQUESTED` before A13, and only A13 emits `LISTING_CULLED` after a reconciled deactivation. `auto_deactivate` stays false. **Amendment:** The portfolio slice keeps `cull_bottom_percent` `"80"` as a pool. It returns `CULL` with an unexecuted fixture `deactivation_job_id` and does not emit `LISTING_CULLED`. **Deferral:** executing deactivation. Owner: the operator-authorized adapter session named by Session 09 F-10.

**F-05 [HIGH] — A14's five labels are not `DecisionType`.** The enum is `HOLD`, `REPAIR`, `CULL`, `MULTIPLY`. A14 writes `MetricsSnapshot` and emits `METRICS_CAPTURED` or, once mature, `LISTING_MATURED`. A15 writes `PortfolioDecision`. A new collection job type would double-spawn `PortfolioDecisionJob`. A live listing must not enter `ListingRepairJob`. **Amendment:** `TOO_YOUNG` means no decision row. Repair returns `repair_job_id` and does not add a lifecycle edge. Do not edit `event_successor_map` or `config/workflows.yaml`.

**F-06 [HIGH] — The multiply label chain is not the job graph.** D-0017 and D-0021 start a new workflow at `DEDUPE_CHECK` and leave the winner on `OBSERVING`. One decision holds one successor. A fresh-niche spec with no research row is blocked by D-0015. **Amendment:** `MULTIPLY` returns a new workflow id and a `SUCCESSOR` spec with parent lineage, and stops at dedupe. Do not add `CREATE_SUCCESSOR_SPEC`, `CHECK_DEDUPE`, or `BUILD_NOTION_TEMPLATE` as job types. **Deferral:** the Notion build. Owner: the operator-authorized adapter session.

**F-07 [HIGH] — "Approximately one slot" is not D-0015.** Each non-empty batch schedules exactly one eligible new-front experiment. A blocked experiment stays `QUEUED` and is not counted. **Amendment:** The portfolio slice uses that rule. `publishing_enabled` stays false. The initial cap stays 2 and the hard cap stays 15. Only reconciled publications count.

**F-08 [MEDIUM] — An open stats bag is not `MetricsSnapshot`.** **Amendment:** The metrics slice carries listing version, provider, `observed_at`, views, favourites, orders, gross revenue, currency, `reconciled`, and one evidence citation. One row per listing version and window. Cumulative totals are derived. Additional provider stats are refused until a new schema version exists.

**F-09 [MEDIUM] — Every fourth week is not `deep_pass_cadence: monthly`.** **Amendment:** The plan uses `MONTHLY_DEEP_PASS`. Do not add a fourth-run counter. **Deferral:** replacing the configured month with a 28-day counter. Owner: the operator.

**F-10 [HIGH] — The exit lines are satisfiable by flipping operator switches.** D-0020 requires `mode: live`, `external_mutations_enabled`, `auto_publish`, and `publishing_enabled` before a live publish. **Amendment:** Do not edit `config/autonomy.yaml`, `config/autonomy.example.yaml`, or `config/publishing_ramp.yaml`. Those switches stay false. **Deferral:** live enablement. Owner: an operator authority record.

### Safety and executability

**Verdict:** CONDITIONAL APPROVE.

**S-01 [CRITICAL] — Do not close Session 10 on this tree.** Same resolution as F-01. No push to `build/full-automation`. No merge. PRs #63 and #68 stay untouched. #105 is already merged as `edc0632`.

**S-02 [CRITICAL] — Do not commission A14 or A15.** Same resolution as F-02. Exit 78 stays HELD.

**S-03 [CRITICAL] — Actions 2, 4, and 7 must not lift the scheduler.** `scheduler.main` returns `uncommissioned_process("scheduler")` and exits 78. `schedule_maturity_timer` inserts a `PENDING` job when called. **Amendment:** `scheduler.py` stays unchanged. Tests do not call `schedule_maturity_timer` and do not insert `READY` or `PENDING` provider jobs. The job plan is pure data inside the three lanes. **Deferral:** wiring the loops into the process entrypoint. Owner: an operator decision that lifts Exit 78.

**S-04 [CRITICAL] — Cull must not call `etsy.deactivate_listing`.** Same resolution as F-04. A13 stays `DESIGNED`.

**S-05 [HIGH] — No Etsy stats client exists.** The named tools bind to `_simulated_handler`. A literal collector would add an HTTP client and read tokens. **Amendment:** Metrics come from an injected fixture. The new modules do not import `httpx` or `socket`, do not read environment variables or `.env`, and store an evidence citation rather than a raw body. **Deferral:** a live stats transport. Owner: the operator-authorized adapter session after D-0028.

**S-06 [HIGH] — The calendar trigger and the candidate labels.** Same resolution as F-03 and F-05.

**S-07 [HIGH] — `BUILD_NOTION_TEMPLATE` is a live Notion write.** Same resolution as F-06.

**S-08 [HIGH] — Exploration and the monthly price review must not publish or spend.** Same resolution as F-07 and F-10. Do not change price, send a customer message, or run checkout.

**S-09 [HIGH] — Actions 1 through 11 are one mega-task.** **Amendment:** At most three Level 1 fixture lanes. Workers do not edit `docs/control/`, `config/agents.yaml`, `scheduler.py`, `publishing_ramp.yaml`, or `IMPLEMENTATION_STATE.json`. **Deferral:** process E2E, monthly job execution, and the three named session reviewers. Owner: Session 10 Level 3 after operator activation.

**S-10 [MEDIUM] — The four arrow paths are a live round trip on this tree.** **Amendment:** Tests drive the pure functions and assert returned ids and labels. A deactivation id is present and unexecuted. A successor stops at dedupe.

### Gameability

**Verdict:** CONDITIONAL APPROVE.

**G-01 [CRITICAL] — "No manual intervention" is a constant or a seeded milestone.** **Amendment:** Each path test passes listings, intervals, and scripted metrics only. It must not pass the expected `PortfolioDecision` in as an input. Seeding operator-minutes `0` fails. With A14 and A15 left `DESIGNED`, this wave does not claim their jobs.

**G-02 [CRITICAL] — Commissioning by editing YAML after a green test.** **Amendment:** A test reads the committed agents file and asserts A14 and A15 stay `DESIGNED` with empty evidence. **Deferral:** the state change. Owner: the operator under D-0028.

**G-03 [CRITICAL] — `live_days = 30` or `published_at + 30 days` counts paused time.** **Amendment:** The killing fixture is verified UTC `published_at` T, 20 live periods, 10 inactive periods. At T+30 calendar days the listing is not mature and no decision is returned. Maturity is due only when active time reaches `maturity_live_days` 30. A stored `live_days` of 30 does not override the intervals. A defect inside the window returns repair work immediately. Do not defer this clock again.

**G-04 [CRITICAL] — A log line named `LISTING_CULLED` is not a deactivation.** **Amendment:** `CULL` cites a reconciled snapshot and an unexecuted fixture `deactivation_job_id`. The returned events do not include `LISTING_CULLED`. A log line with no job id fails. **Deferral:** inserting `LISTING_CULLED` only after a fixture read returns `CONFIRMED`, and the retained lesson row. Owner: Session 10 wave 2. A live Etsy write stays with the operator adapter session.

**G-05 [CRITICAL] — A label string or the winner's own spec id is not a successor.** **Amendment:** `MULTIPLY` returns a new spec id, `lineage_kind` `SUCCESSOR`, a different workflow id, and the parent spec, product, decision, and workflow ids. The parent identity is unchanged. Dedupe is the next gate. The three prompt labels with no new spec id fail.

**G-06 [CRITICAL] — A test that passes only by setting `publishing_enabled` or `COMMISSIONED`.** **Amendment:** The suite reads the committed ramp and agents files before and after. `publishing_enabled` stays false. `initial_weekly_cap` stays 2. A14 and A15 stay `DESIGNED`.

**G-07 [CRITICAL] — A cohort of one is "the bottom".** **Amendment:** Cohorts of 1, 2, 3, and 4 return zero `CULL` decisions. Another shop, or a listing outside the window, does not enlarge the cohort. A cohort of five with one strictly worst score may mark only that listing. Two listings tied at the cutoff both stay out.

**G-08 [CRITICAL] — Deactivating `int(0.8 * n)` listings.** **Amendment:** Ten mature listings with identical reconciled metrics return zero culls. Ten with distinct scores leave the best two uncullable. Views without sales return `REPAIR` and no deactivation. An immature listing in the bottom ranks is not culled. No delete of listings, versions, snapshots, or artifacts. `cull_bottom_percent` stays `"80"`.

**G-09 [HIGH] — One inserted trigger row is not a durable loop.** **Amendment:** The metrics slice returns one collection record per active listing, then one shop-review record, and a second call in the same window returns no new collection. Prior snapshot inputs are not rewritten. The monthly record follows `deep_pass_cadence: monthly`, not a fourth-week counter. `scheduler.main` still returns 78. **Deferral:** persisting `scheduled_triggers` through the library. Owner: Session 10 wave 2. Lifting exit 78 stays with the operator.

**G-10 [HIGH] — A candidate string is not an executable decision.** **Amendment:** Under 30 live days and no defect, the portfolio function returns no decision. At maturity it returns exactly one of `HOLD`, `REPAIR`, `CULL`, or `MULTIPLY`, and every cited snapshot is reconciled. An unreconciled snapshot returns no decision.

**G-11 [HIGH] — Reading `new_fronts_per_batch: 1` does no work.** **Amendment:** A non-empty batch with one `QUEUED` experiment that is not a variant of that batch's winner schedules exactly one experiment. A blocked experiment stays `QUEUED`. With `publishing_enabled` false, the slot creates no publication.

**G-12 [HIGH] — Four tests that compare themselves to the prompt text.** **Amendment:** The four paths are row assertions on the pure functions, not one name check. A skip is a failure. The arrange step does not contain the decision or the successor spec.

**G-13 [HIGH] — `future_weekly: true` is not a hold.** **Amendment:** `HOLD` returns a next collection time strictly after `decided_at`, no deactivation id, and no successor spec. A second call before that time returns no new decision.

**G-14 [HIGH] — Setting the state back to `OBSERVING` is not repair.** **Amendment:** Views and zero sales return `REPAIR`, a repair job id, and no deactivation. The result does not emit `REPAIR_COMPLETED`. No second decision is returned until a new reconciled snapshot is supplied.

**G-15 [HIGH] — The exit string and the commit subject are self-reported.** **Amendment:** Do not write `SESSION_10_CLOSED_LOOP_AUTOMATION_COMPLETE`. Do not flip completion booleans. The subject `feat(loop): automate metrics culling and winner multiplication` is not this wave's commit. **Deferral:** control-state evidence keys. Owner: Session 10 Level 3, after Sessions 08 and 09 are closed and an operator activates Session 10.

**G-16 [MEDIUM] — Seeded milestone strings.** **Amendment:** `first_cull` is present only when the fixture already contains a confirmed cull effect. `first_multiplied_winner` is present only when a successor spec is present. An operator-minutes total of `0` is rejected when it was not measured.

**G-17 [LOW] — Three markdown headings are not the checkpoint.** **Deferral:** analytics, workflow, and commercial-logic review of the diff. Owner: Session 10 exit.

## 3. Corrective addendum

1. Prove the prompt hash. It stays `250a666a2e0e81790066b96caaf0f017fde59027cc2921b1417ea71c99677e7a`.
2. Session 10 stays inactive. `current_session` stays 7. `state_revision` stays 64. Exit 78 stays HELD. A14 and A15 stay `DESIGNED`.
3. Do not edit `IMPLEMENTATION_STATE.json`, `config/workflows.yaml`, `config/agents.yaml`, `config/publishing_ramp.yaml`, autonomy files, `scheduler.py`, or `event_successor_map`.
4. Do not publish, spend, message customers, change a price, or call live Etsy, Notion, or S3. Tests open no socket and read no provider credential.
5. Open at most three lanes. Workers do not edit `docs/control/`.
6. Lane `cursor/s10-metrics-fixture-7da5` owns only `src/money_machine/assets/metrics_fixture.py` and `tests/unit/assets/test_metrics_fixture.py`. An injected fixture becomes one `MetricsSnapshot`-shaped row per listing version and window. The weekly plan returns one collection per active listing and one shop review after them. A second call in the same window adds nothing. The monthly plan follows `monthly`, not every fourth week. Milestones are derived from source rows. No network import.
7. Lane `cursor/s10-maturity-clock-7da5` owns only `src/money_machine/assets/maturity_clock.py` and `tests/unit/assets/test_maturity_clock.py`. Thirty accumulated live UTC periods. The 20-live-plus-10-inactive fixture at calendar day 30 is not mature. A defect returns repair work before maturity. No call to `schedule_maturity_timer`.
8. Lane `cursor/s10-portfolio-eligibility-7da5` owns only `src/money_machine/assets/portfolio_eligibility.py` and `tests/unit/assets/test_portfolio_eligibility.py`. Decisions are only `HOLD`, `REPAIR`, `CULL`, and `MULTIPLY`. Cohorts under five, cutoff ties, and identical scores are not culled. `CULL` carries an unexecuted deactivation id and does not emit `LISTING_CULLED`. `MULTIPLY` returns a new successor identity and stops at dedupe. `HOLD` names a future collection time. Exactly one eligible new-front experiment is scheduled, and a blocked one stays queued.
9. Each lane is Level 1: failing test first, then the smallest implementation, then the focused file. `ruff format`, `ruff check`, and `pyright` on the touched files. One uniquely killing test per pin in sections 6–8.
10. Session 10 wave 2 owns persisted schedule rows and fixture-confirmed `LISTING_CULLED` without lifting Exit 78 and without a live provider write. Sessions 11–15 do not start until this wave is green and each later session has its own prompt-integrity addendum.

## 4. Deferrals

**D-01 — Session 10 activation, the exit string, and the control-file booleans.** Owner: the operator, after Sessions 08 and 09 are closed.

**D-02 — Commissioning A14 and A15, and lifting Exit 78.** Owner: the operator under D-0028.

**D-03 — Live stats, live deactivation, Notion successor build, price changes, and checkout.** Owner: an operator authority record. A present token is not authority.

**D-04 — Persisted `scheduled_triggers` and a fixture-confirmed `LISTING_CULLED`.** Owner: Session 10 wave 2. That wave still does not edit `scheduler.py` or `workflows.yaml`.

**D-05 — Process E2E and the analytics, workflow, and commercial-logic reviews.** Owner: Session 10 Level 3.

**D-06 — Sessions 11–15.** Owner: each session's own prompt-integrity addendum after this wave.

## 5. What already holds

`DecisionType` is already only `HOLD`, `REPAIR`, `CULL`, and `MULTIPLY`. `MetricsSnapshot` already requires a listing version, provider, observation time, views, favourites, orders, gross revenue, currency, a reconciled flag, and at least one evidence citation. `PortfolioDecision` already requires snapshot ids, and `CULL` already requires `deactivation_job_id` while `MULTIPLY` already requires a distinct successor workflow and spec. `config/product_rules.yaml` already sets `maturity_live_days` 30, `cull_bottom_percent` `"80"`, `deep_pass_cadence` monthly, and `new_fronts_per_batch` 1. The committed ramp stays disabled at initial cap 2 and hard cap 15. A14 and A15 stay `DESIGNED`. `scheduler.main` still exits 78.
