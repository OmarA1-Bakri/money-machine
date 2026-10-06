# Session 07 Prompt Integrity Review — Wave 3

**Date:** 2026-10-05
**Prompt:** `prompts/implementation/10_SESSION_07_PRODUCT_BUILD_VARIANTS_AND_QA.md`
**Verified SHA-256:** `d52011a6f0b725b16427629dc664cfc9f3432c4b5f71d26ce032d4b6c8ecb39d`
**Workbook authority:** `hands-off-money-machine-full-implementation-workbook.md` appendix row for this prompt (5,255 bytes, 237 lines)
**Scope:** Wave 3 only. Tip-sync the incomplete session, then fixture-only phase `dashboard_and_navigation`. The Wave 1 record at `docs/control/reviews/2026-10-03-session-07-prompt-integrity.md` still governs phase 1. This record is the corrective addendum for Wave 3.

The prompt file is not amended.

## 1. Prompt authenticity

**Status:** VERIFIED

- The extracted file's SHA-256 equals the workbook appendix value.
- The workbook copy between `COPY START` and `COPY END` is the same extract the appendix hashes.
- The prompt stays the unamended source of record.

## 2. Three-dimensional review

### Fidelity

**Verdict:** CONDITIONAL APPROVE. One high finding, resolved by the addendum.

**F-01 [HIGH] — Section 3 names the notification dashboard inside the home dashboard**

- **Prompt lines:** 50–61, especially line 56, against the phase list at lines 17–24 and action 4 at lines 63–76.
- **Authority:** `BUILD_PHASES` already separates `dashboard_and_navigation`, `identity_specific_hubs`, and `notification_dashboard`. The operator slice for this wave is the home dashboard pieces that belong to `dashboard_and_navigation`: palette cover/header, greeting, hub navigation, today's priorities, monthly event calendar, quick notes, and identity-appropriate callouts. The one-row notification database is the later phase.
- **Consequence of literal execution:** Building the one-row relations/rollups/formulas now would run action 4 inside this wave and would leave `next_phase` wrong.
- **Amendment:** Build only the named home-dashboard pieces. Do not build the one-row notification dashboard. Do not run `identity_specific_hubs`. The checkpoint records `dashboard_and_navigation` and sets `next_phase` to `identity_specific_hubs`.

**What the prompt already gets right**

- Dashboard and navigation is phase 3, after shared databases and before identity-specific hubs (lines 17–24).
- The builder consumes a validated ProductSpec (line 13).
- Phase progress is persisted so a later run resumes (line 26).
- Hub views link to canonical databases and do not create a second store (lines 48–48).
- Mass and business shared-database sets differ (lines 30–46), so a monthly event calendar cannot invent an Events database for the business tier.

### Safety and executability

**Verdict:** CONDITIONAL APPROVE. The Wave 1 critical and high findings still apply and stay in force.

**S-01 [CRITICAL] — Action 11 live sandbox.** Still deferred. This wave uses `FixtureNotionAdapter` only. No live HTTP, no real Notion workspace, no Etsy listing, no Exit 78 lift.

**S-02 [HIGH] — Action 12 commissioning.** A07, A08, and A09 stay DESIGNED. `commissioned_agents` stays empty.

**S-03 [HIGH] — Two ProductSpec types.** This phase accepts only `product_spec.ProductSpec`. The catalogue spec is rejected.

**S-04 [HIGH] — Tip-sync must not look like completion.** `head_sha` moves to the post-merge Wave 2 tip `676fabef5bd1b36018f1d2d539d282225d860a99`. `evidence_closure_commit_sha` stays the Session 06 tip `0f94d585f23d79e5ac18479f01e14f67cbaad332`. `last_verified_commit` stays bootstrap. All twelve session 7 evidence keys stay false. `session_status` stays `incomplete`. This wave does not print `SESSION_07_PRODUCT_BUILD_AND_QA_COMPLETE`.

### Gameability

**Verdict:** CONDITIONAL APPROVE. One high finding, resolved by the addendum.

**G-01 [HIGH] — A checkpoint name without fixture objects satisfies a careless reading**

- **Prompt line:** 26.
- **Cheap fake:** Append `dashboard_and_navigation` to `checkpoint_names` without creating the cover, greeting, navigation, views, or callouts, or create a second Tasks database for "today's priorities".
- **Ungameable for this wave:** Tests show the fixture holds the palette cover and header, one identity greeting, hub names on the home page and no hub pages, one Today linked view of Tasks with the open/due-today filters, a Month calendar linked to Events for the mass tier only, Quick notes linked to Notes, and two identity callouts. Replay does not add another block or view. A missing page, database, shell, or dashboard object behind the saved checkpoint is an error. The source does not name a live client, `publish_page`, or the notification-dashboard builder.

## 3. Corrective addendum

This addendum governs Wave 3. The prompt remains the unamended source of record.

1. Prove the prompt hash, then implement only the slice below.
2. Tip-sync only: `head_sha` becomes `676fabef5bd1b36018f1d2d539d282225d860a99`. `evidence_closure_commit_sha` stays `0f94d585f23d79e5ac18479f01e14f67cbaad332`. `last_verified_commit` stays bootstrap `1abf0d7cca3a6b8cd7efcd0a45523538fd5bfd9d`. Advance `state_revision` by one. `session_status` stays `incomplete`. `current_session` stays 7. `completed_sessions` stays `[0, 1, 2, 3, 4, 5, 6]`. `next_session` stays 7. `next_prompt` stays this prompt.
3. Leave all twelve session 7 evidence keys false, including `shared_databases_built`, `home_dashboard_built`, `notification_dashboard_built`, `product_build_tests_pass`, `control_files_and_checkpoint_current`, and `evidence_closure_commit_recorded`. Do not set `SESSION_07_PRODUCT_BUILD_AND_QA_COMPLETE`.
4. Keep A07, A08, and A09 DESIGNED. `commissioned_agents` stays empty. Exit 78 stays HELD.
5. Resume a checkpoint whose names are `top_level_page_and_design_shell` and `shared_databases`, on an exact `FixtureNotionAdapter` and an exact `product_spec.ProductSpec`. A missing file, a phase-1-only checkpoint, or a missing page, shell, or database is an error. Do not rebuild those objects.
6. On that home page, store the palette cover and header, one greeting, hub navigation that names the spec hubs and does not create hub pages, today's priorities as one linked Tasks view, quick notes as one linked Notes view, and two identity-appropriate callouts. The mass tier also stores one monthly calendar linked to Events. The business tier has no Events database and no monthly calendar. Do not create a second data store.
7. Do not build the one-row notification dashboard. Do not run identity-specific hubs, aesthetics, variants, QA, the fact ledger, or the workflow link.
8. Persist `dashboard_and_navigation` on the checkpoint. `next_phase` is `identity_specific_hubs` and this wave does not run it. Replay does not create another block or view. A missing dashboard object behind that checkpoint is an error.
9. Tests use the fixture only. Parked S06 nits, the #51 published-page mutant, and the #52 shared-database nits stay parked.

## 4. Deferrals

| Finding | Owner | Reason |
|---|---|---|
| One-row notification dashboard (action 4) | Later Session 07 wave | Separate `BUILD_PHASES` entry; operator slice excludes it |
| Identity-specific hubs | Later Session 07 wave | `next_phase` is recorded and not run |
| Actions 6–13 | Later Session 07 waves or the session close | Not this slice |
| Action 11 live sandbox | Later wave with explicit authorization | S-01 |
| Action 12 commissioning | Operator decision after full implementation | S-02 |
| Parked #52, #51, and S06 nits | Unowned until one blocks a slice | Operator instruction |

# Session 07 Prompt Integrity Review — Wave 4

**Date:** 2026-10-05
**Prompt:** `prompts/implementation/10_SESSION_07_PRODUCT_BUILD_VARIANTS_AND_QA.md`
**Verified SHA-256:** `d52011a6f0b725b16427629dc664cfc9f3432c4b5f71d26ce032d4b6c8ecb39d`
**Workbook authority:** `hands-off-money-machine-full-implementation-workbook.md` appendix row for this prompt (5,255 bytes, 237 lines)
**Scope:** Wave 4 only. Tip-sync the incomplete session, then fixture-only phase `identity_specific_hubs`. The Wave 1 record at `docs/control/reviews/2026-10-03-session-07-prompt-integrity.md` still governs phase 1. The Wave 3 record above still governs `dashboard_and_navigation`. This record is the corrective addendum for Wave 4.

The prompt file is not amended.

## 1. Prompt authenticity

**Status:** VERIFIED

- The extracted file's SHA-256 equals the workbook appendix value `d52011a6f0b725b16427629dc664cfc9f3432c4b5f71d26ce032d4b6c8ecb39d`.
- The workbook copy between `COPY START` and `COPY END` is the same extract the appendix hashes.
- The prompt stays the unamended source of record.

## 2. Three-dimensional review

### Fidelity

**Verdict:** CONDITIONAL APPROVE. One high finding, resolved by the addendum.

**F-01 [HIGH] — Section 3 still names the notification dashboard, and section 5 is a separate phase**

- **Prompt lines:** 50–61 and 63–76, against the phase list at lines 17–24 and section 5 at lines 78–86.
- **Authority:** `BUILD_PHASES` separates `dashboard_and_navigation`, `identity_specific_hubs`, and `notification_dashboard`. The operator slice for this wave is section 5 only.
- **Consequence of literal execution:** Building the one-row notification database, or rebuilding the home dashboard, would run the wrong phase and leave `next_phase` wrong.
- **Amendment:** Build six to eight identity-specific hubs from the saved dashboard checkpoint. Do not build the one-row notification dashboard. The checkpoint records `identity_specific_hubs` and sets `next_phase` to `notification_dashboard`. This wave does not run that phase.

**What the prompt already gets right**

- Identity-specific hubs are phase 4, after the home dashboard and before the notification dashboard (lines 17–24).
- Each hub has two to five linked or filtered views, two to four static pages or sections, identity-specific vocabulary, and navigation back to the dashboard (lines 78–86).
- Hub views link to canonical databases and do not create a second store (lines 48–48).
- Mass and business shared-database sets differ (lines 30–46), so a hub must not invent an Events view for the business tier.

### Safety and executability

**Verdict:** CONDITIONAL APPROVE. The Wave 1 critical and high findings still apply and stay in force.

**S-01 [CRITICAL] — Action 11 live sandbox.** Still deferred. This wave uses `FixtureNotionAdapter` only. No live HTTP, no real Notion workspace, no Etsy listing, no Exit 78 lift.

**S-02 [HIGH] — Action 12 commissioning.** A07, A08, and A09 stay DESIGNED. `commissioned_agents` stays empty.

**S-03 [HIGH] — Two ProductSpec types.** This phase accepts only `product_spec.ProductSpec`. The catalogue spec is rejected.

**S-04 [HIGH] — Tip-sync must not look like completion.** `head_sha` moves to the post-merge Wave 3 tip `0f67dc92d5c4bdc105a3801ed5b5f7b517c66283`. `evidence_closure_commit_sha` stays the Session 06 tip `0f94d585f23d79e5ac18479f01e14f67cbaad332`. `last_verified_commit` stays bootstrap. All twelve session 7 evidence keys stay false. `session_status` stays `incomplete`. This wave does not print `SESSION_07_PRODUCT_BUILD_AND_QA_COMPLETE`.

### Gameability

**Verdict:** CONDITIONAL APPROVE. One high finding, resolved by the addendum.

**G-01 [HIGH] — A checkpoint name without hub objects satisfies a careless reading**

- **Prompt line:** 26, read against section 5.
- **Cheap fake:** Append `identity_specific_hubs` to `checkpoint_names` without creating hub pages, sections, or linked views, or create a second Tasks database per hub, or reuse one generic paragraph on every product.
- **Ungameable for this wave:** Tests show each spec hub is a child of the dashboard, with two to five linked views of canonical databases that exist for that tier, two to four identity-specific sections, and a navigation block back to the dashboard title. Mass and business tiers both run. Business creates no Events view. Replay does not add another hub, view, or page. A missing page, database, shell, dashboard piece, or hub object behind the saved checkpoint is an error. The source does not name a live client, `publish_page`, or the notification-dashboard builder.

## 3. Corrective addendum

This addendum governs Wave 4. The prompt remains the unamended source of record.

1. Prove the prompt hash, then implement only the slice below.
2. Tip-sync only: `head_sha` becomes `0f67dc92d5c4bdc105a3801ed5b5f7b517c66283`. `evidence_closure_commit_sha` stays `0f94d585f23d79e5ac18479f01e14f67cbaad332`. `last_verified_commit` stays bootstrap `1abf0d7cca3a6b8cd7efcd0a45523538fd5bfd9d`. Advance `state_revision` by one. `session_status` stays `incomplete`. `current_session` stays 7. `completed_sessions` stays `[0, 1, 2, 3, 4, 5, 6]`. `next_session` stays 7. `next_prompt` stays this prompt.
3. Leave all twelve session 7 evidence keys false, including `home_dashboard_built`, `notification_dashboard_built`, `identity_hubs_built`, `product_build_tests_pass`, `control_files_and_checkpoint_current`, and `evidence_closure_commit_recorded`. Do not set `SESSION_07_PRODUCT_BUILD_AND_QA_COMPLETE`.
4. Keep A07, A08, and A09 DESIGNED. `commissioned_agents` stays empty. Exit 78 stays HELD.
5. Resume a checkpoint whose names are `top_level_page_and_design_shell`, `shared_databases`, and `dashboard_and_navigation`, on an exact `FixtureNotionAdapter` and an exact `product_spec.ProductSpec`. A missing file, an earlier-only checkpoint, or a missing page, shell, database, or dashboard piece is an error. Do not rebuild those objects.
6. For each ProductSpec hub (six to eight), store one child page of the dashboard. Each hub stores two linked views of canonical databases that exist for the tier, three identity-specific static sections, and one navigation block that names the dashboard title. Views are filtered when the source database has a date or status property. The business tier has no Events database and no Events view. Do not create a second data store.
7. Do not build the one-row notification dashboard. Do not run aesthetics, variants, QA, the fact ledger, or the workflow link. Do not commission A07, A08, or A09.
8. Persist `identity_specific_hubs` on the checkpoint. `next_phase` is `notification_dashboard` and this wave does not run it. Replay does not create another hub, view, or page. A missing hub object behind that checkpoint is an error.
9. Tests use the fixture only. Parked should-fix items from #53, #52, #51, and S04–S06 stay parked unless one blocks this slice.

## 4. Deferrals

| Finding | Owner | Reason |
|---|---|---|
| One-row notification dashboard (action 4) | Later Session 07 wave | Separate `BUILD_PHASES` entry; `next_phase` is recorded and not run |
| Actions 6–13 | Later Session 07 waves or the session close | Not this slice |
| Action 11 live sandbox | Later wave with explicit authorization | S-01 |
| Action 12 commissioning | Operator decision after full implementation | S-02 |
| Parked #53, #52, #51, and S04–S06 nits | Unowned until one blocks a slice | Operator instruction |

# Session 07 Prompt Integrity Review — Wave 5

**Date:** 2026-10-06
**Prompt:** `prompts/implementation/10_SESSION_07_PRODUCT_BUILD_VARIANTS_AND_QA.md`
**Verified SHA-256:** `d52011a6f0b725b16427629dc664cfc9f3432c4b5f71d26ce032d4b6c8ecb39d`
**Workbook authority:** `hands-off-money-machine-full-implementation-workbook.md` appendix row for this prompt (5,255 bytes, 237 lines)
**Scope:** Wave 5 only. Tip-sync the incomplete session, then fixture-only phase `notification_dashboard`. The Wave 1 record at `docs/control/reviews/2026-10-03-session-07-prompt-integrity.md` still governs phase 1. The Wave 3 record above still governs `dashboard_and_navigation`. The Wave 4 record above still governs `identity_specific_hubs`. This record is the corrective addendum for Wave 5.

The prompt file is not amended.

## 1. Prompt authenticity

**Status:** VERIFIED

- The extracted file's SHA-256 equals the workbook appendix value `d52011a6f0b725b16427629dc664cfc9f3432c4b5f71d26ce032d4b6c8ecb39d`.
- The workbook copy between `COPY START` and `COPY END` is the same extract the appendix hashes.
- The prompt stays the unamended source of record.

## 2. Three-dimensional review

### Fidelity

**Verdict:** CONDITIONAL APPROVE. One high finding, resolved by the addendum.

**F-01 [HIGH] — Section 3 still lists the notification dashboard inside the home dashboard, and section 5 is hubs**

- **Prompt lines:** 50–61 and 78–86, against section 4 at lines 63–76 and the phase list at lines 17–24.
- **Authority:** `BUILD_PHASES` separates `dashboard_and_navigation`, `identity_specific_hubs`, and `notification_dashboard`. The operator slice for this wave is section 4 only.
- **Consequence of literal execution:** Rebuilding the home dashboard or the hubs, or running aesthetics, would run the wrong phase and leave `next_phase` wrong.
- **Amendment:** Resume the saved identity-hub checkpoint and build only the one-row notification database. Do not rebuild hubs. Do not run `aesthetics_and_content_completion`. The configured buyer name is `ProductSpec.identity`. Do not emit `client_name`. Birthday status, money spent today, and water glasses remaining appear only when that catalogue database is in the tier.

**What the prompt already gets right**

- The notification dashboard is its own phase, after identity-specific hubs and before aesthetics (lines 17–24).
- It is one row of relations, rollups, and formulas for the buyer name, the current date, open tasks due today, birthday status, money spent today, and water glasses remaining where relevant (lines 63–76).
- Only claims the ProductSpec supports are shown, and sample data is distinguished from buyer data (lines 74–76).
- Phase progress is persisted so a later run resumes (line 26).

### Safety and executability

**Verdict:** CONDITIONAL APPROVE. The Wave 1 critical and high findings still apply and stay in force.

**S-01 [CRITICAL] — Action 11 live sandbox.** Still deferred. This wave uses `FixtureNotionAdapter` only. No live HTTP, no real Notion workspace, no Etsy listing, no Exit 78 lift.

**S-02 [HIGH] — Action 12 commissioning.** A07, A08, and A09 stay DESIGNED. `commissioned_agents` stays empty.

**S-03 [HIGH] — Two ProductSpec types.** This phase accepts only `product_spec.ProductSpec`. The catalogue spec is rejected.

**S-04 [HIGH] — Tip-sync must not look like completion.** `head_sha` moves to the post-merge Wave 4 tip `91a33eba7961ea2819dcc695f73ffe9a45e37b33`. `evidence_closure_commit_sha` stays the Session 06 tip `0f94d585f23d79e5ac18479f01e14f67cbaad332`. `last_verified_commit` stays bootstrap. All twelve session 7 evidence keys stay false, including `notification_dashboard_built`. `session_status` stays `incomplete`. This wave does not print `SESSION_07_PRODUCT_BUILD_AND_QA_COMPLETE`.

### Gameability

**Verdict:** CONDITIONAL APPROVE. One high finding, resolved by the addendum.

**G-01 [HIGH] — A checkpoint name without the one-row database satisfies a careless reading**

- **Prompt line:** 26, read against section 4.
- **Cheap fake:** Append `notification_dashboard` to `checkpoint_names` without the one-row database, its relations, rollups, and formulas, or without distinguishing sample rows from the buyer row. A hub view name that exceeds Notion's 64-character cap, or a resume that ignores a deleted design shell, is the same class of fake.
- **Ungameable for this wave:** Tests show the fixture holds one notification database and exactly one buyer row. Mass tier stores buyer name, current date, open tasks due today, birthday status, money spent today, and water glasses remaining. Business tier omits birthday, money, and water. Sample rows are marked SAMPLE. Replay keeps the same checkpoint bytes and ids. A missing checkpoint, shell, hub, database, formula, or sample is an error and is not rebuilt. A realistic long hub view name is capped to 64 characters and stays unique. The source does not name a live client.

## 3. Corrective addendum

This addendum governs Wave 5. The prompt remains the unamended source of record.

1. Prove the prompt hash, then implement only the slice below.
2. Tip-sync only: `head_sha` becomes `91a33eba7961ea2819dcc695f73ffe9a45e37b33`. `evidence_closure_commit_sha` stays `0f94d585f23d79e5ac18479f01e14f67cbaad332`. `last_verified_commit` stays bootstrap `1abf0d7cca3a6b8cd7efcd0a45523538fd5bfd9d`. Advance `state_revision` from 52 to 53. `session_status` stays `incomplete`. `current_session` stays 7. `completed_sessions` stays `[0, 1, 2, 3, 4, 5, 6]`. `next_session` stays 7. `next_prompt` stays this prompt.
3. Leave all twelve session 7 evidence keys false, including `notification_dashboard_built`, `identity_hubs_built`, `home_dashboard_built`, `product_build_tests_pass`, `control_files_and_checkpoint_current`, and `evidence_closure_commit_recorded`. The fixture phase does not meet the prompt's completion criteria for `notification_dashboard_built`. Do not set `SESSION_07_PRODUCT_BUILD_AND_QA_COMPLETE`.
4. Keep A07, A08, and A09 DESIGNED. `commissioned_agents` stays empty. Exit 78 stays HELD.
5. Resume a checkpoint whose names are `top_level_page_and_design_shell`, `shared_databases`, `dashboard_and_navigation`, and `identity_specific_hubs`, on an exact `FixtureNotionAdapter` and an exact `product_spec.ProductSpec`. A missing file, an earlier-only checkpoint, or a missing page, shell, database, dashboard piece, or hub is an error. Do not rebuild those objects.
6. Store one notification database on the home page and exactly one buyer row. Show the buyer name (`ProductSpec.identity`), the current date, and open tasks due today. Show birthday status only when Events is in the tier, money spent today only when Finance is in the tier, and water glasses remaining only when Habits is in the tier. Do not emit `client_name`. Mark sample rows as sample. Do not create a second store for an existing catalogue database.
7. Cap an identity hub view name that would exceed 64 characters. The shortened name is deterministic and unique. A deleted or tampered design shell on resume is an error and is not rebuilt.
8. Do not run aesthetics, variants, QA, the fact ledger, or the workflow link. Do not commission A07, A08, or A09.
9. Persist `notification_dashboard` on the checkpoint. `next_phase` is `aesthetics_and_content_completion` and this wave does not run it. Replay does not create another row, database, or formula. A missing notification object behind that checkpoint is an error.
10. Tests use the fixture only.

## 4. Deferrals

| Finding | Owner | Reason |
|---|---|---|
| Aesthetics and content completion | Later Session 07 wave | `next_phase` is recorded and not run |
| Actions 6–13 | Later Session 07 waves or the session close | Not this slice |
| Action 11 live sandbox | Later wave with explicit authorization | S-01 |
| Action 12 commissioning | Operator decision after full implementation | S-02 |
| `notification_dashboard_built` | Session close, after the prompt's own criteria | Fixture phase is not that gate |

# Session 07 Prompt Integrity Review — Wave 6

**Date:** 2026-10-06
**Prompt:** `prompts/implementation/10_SESSION_07_PRODUCT_BUILD_VARIANTS_AND_QA.md`
**Verified SHA-256:** `d52011a6f0b725b16427629dc664cfc9f3432c4b5f71d26ce032d4b6c8ecb39d`
**Workbook authority:** `hands-off-money-machine-full-implementation-workbook.md` appendix row for this prompt (5,255 bytes, 237 lines)
**Scope:** Wave 6 only. Tip-sync the incomplete session, then fixture-only phase `aesthetics_and_content_completion`. The Wave 1 record at `docs/control/reviews/2026-10-03-session-07-prompt-integrity.md` still governs phase 1. Waves 3–5 above still govern their phases. This record is the corrective addendum for Wave 6.

The prompt file is not amended.

## 1. Prompt authenticity

**Status:** VERIFIED

- The extracted file's SHA-256 equals the workbook appendix value `d52011a6f0b725b16427629dc664cfc9f3432c4b5f71d26ce032d4b6c8ecb39d`.
- The workbook copy between `COPY START` and `COPY END` is the same extract the appendix hashes.
- The prompt stays the unamended source of record.

## 2. Three-dimensional review

### Fidelity

**Verdict:** CONDITIONAL APPROVE. One high finding, resolved by the addendum.

**F-01 [HIGH] — Phase 6 is named and is the last build phase, but it has no action section**

- **Prompt lines:** 17–24, against actions 6–10 at lines 88–184.
- **Authority:** `BUILD_PHASES` ends at `aesthetics_and_content_completion`. The workbook product-build rules that are still open for this phase are a coherent palette and sample content that stays distinct from buyer data (workbook §7; prompt lines 74–76). Action 6 is progress and repair, not this phase. Actions 7–10 are variants, QA, the fact ledger, and the workflow link.
- **Consequence of literal execution:** Treating action 6 or action 7 as this phase would start repair jobs or A08 variants and would leave `next_phase` pointing at work this wave must not run.
- **Amendment:** Resume the notification checkpoint. Apply one palette accent per ProductSpec token and one SAMPLE block per hub, using only ProductSpec fields. Mark hub pages with that token's icon and cover. `next_phase` is `build_phases_complete` because the prompt names no later build phase. Do not start A08, A09, the fact ledger, or the workflow link.

**What the prompt already gets right**

- Aesthetics and content completion is phase 6, after the notification dashboard (lines 17–24).
- Only ProductSpec-supported claims are shown, and sample content is distinct from buyer data (lines 74–76).
- Phase progress is persisted so a later run resumes (line 26).
- Variants, QA, and commissioning are later actions (lines 106–206).

### Safety and executability

**Verdict:** CONDITIONAL APPROVE. The Wave 1 critical and high findings still apply and stay in force.

**S-01 [CRITICAL] — Action 11 live sandbox.** Still deferred. This wave uses `FixtureNotionAdapter` only. No live HTTP, no real Notion workspace, no Etsy listing, no Exit 78 lift.

**S-02 [HIGH] — Action 12 commissioning.** A07, A08, and A09 stay DESIGNED. `commissioned_agents` stays empty.

**S-03 [HIGH] — Two ProductSpec types.** This phase accepts only `product_spec.ProductSpec`. The catalogue spec is rejected.

**S-04 [HIGH] — Tip-sync must not look like completion.** `head_sha` moves to the post-merge Wave 5 tip `0793e73147c0a3e50b6e27be2c74d3084ab1bfd5`. `evidence_closure_commit_sha` stays the Session 06 tip `0f94d585f23d79e5ac18479f01e14f67cbaad332`. `last_verified_commit` stays bootstrap. All twelve session 7 evidence keys stay false. `session_status` stays `incomplete`. This wave does not print `SESSION_07_PRODUCT_BUILD_AND_QA_COMPLETE`.

### Gameability

**Verdict:** CONDITIONAL APPROVE. One high finding, resolved by the addendum.

**G-01 [HIGH] — A checkpoint name without palette accents or sample content satisfies a careless reading**

- **Prompt line:** 26, read against phase 6 and lines 74–76.
- **Cheap fake:** Append `aesthetics_and_content_completion` without accent callouts or SAMPLE blocks, copy one generic paragraph onto every hub, or invent a device or `client_name` claim. A salted `hash()` or random view-name token, an icon-only design-shell edit, and a `sample_marker` value with no schema column are the same class of fake.
- **Ungameable for this wave:** Tests show one accent callout per palette token, one SAMPLE block per hub whose text is only the identity, hub name, and hub description, and a hub icon and cover taken from that token. Replay keeps the same checkpoint bytes and ids. A missing notification checkpoint is an error and nothing is rebuilt. The long view-name token equals the SHA-256 prefix of the full name. An icon-only shell edit raises `does not match`. Sample rows carry schema values and `sample_marker` is a select column.

## 3. Corrective addendum

This addendum governs Wave 6. The prompt remains the unamended source of record.

1. Prove the prompt hash, then implement only the slice below.
2. Tip-sync only: `head_sha` becomes `0793e73147c0a3e50b6e27be2c74d3084ab1bfd5`. `evidence_closure_commit_sha` stays `0f94d585f23d79e5ac18479f01e14f67cbaad332`. `last_verified_commit` stays bootstrap `1abf0d7cca3a6b8cd7efcd0a45523538fd5bfd9d`. Advance `state_revision` from 53 to 54. `session_status` stays `incomplete`. `current_session` stays 7. `completed_sessions` stays `[0, 1, 2, 3, 4, 5, 6]`. `next_session` stays 7. `next_prompt` stays this prompt.
3. Leave all twelve session 7 evidence keys false. The fixture phase does not meet the prompt's completion criteria for any of them. Do not set `SESSION_07_PRODUCT_BUILD_AND_QA_COMPLETE`.
4. Keep A07, A08, and A09 DESIGNED. `commissioned_agents` stays empty. Exit 78 stays HELD.
5. Resume a checkpoint whose names run through `notification_dashboard`, on an exact `FixtureNotionAdapter` and an exact `product_spec.ProductSpec`. A missing file, an earlier-only checkpoint, or a missing page, shell, database, dashboard piece, hub, or notification object is an error. Do not rebuild those objects.
6. On that product, store one palette accent callout per ProductSpec token and one SAMPLE text block per hub. The sample text uses only the identity, the hub name, and the hub description. Set each hub page icon and cover from a palette token. Do not publish. Do not emit `client_name`, a device claim, or a free-update claim.
7. Persist `aesthetics_and_content_completion` on the checkpoint. `next_phase` is `build_phases_complete`. Replay does not create another block or mark. A missing aesthetic object behind that checkpoint is an error.
8. Close the operator-listed fixture defects that this slice can close: page-scoped database titles, deterministic repair or a clear error for a partial database or formula, `sample_marker` as a select column with sample-row values, the buyer Name value, the dead notification reference check, golden view-name token and long-name replay, icon-only design-shell tamper with pinned messages, parser and resume tamper tests, the hub-name bound, deduped linked-view helpers, and the phase-1 published-page mutant. Park a real page-link navigation block: the fixture has paragraph and callout blocks only.
9. Tests use the fixture only. Do not start A08, A09, the fact ledger, the workflow link, or commissioning.

## 4. Deferrals

| Finding | Owner | Reason |
|---|---|---|
| Actions 7–13 | Later Session 07 waves or the session close | Not this slice |
| Action 11 live sandbox | Later wave with explicit authorization | S-01 |
| Action 12 commissioning | Operator decision after full implementation | S-02 |
| Navigation as a page-link block | Unowned until the fixture grows a link block | Fixture blocks are paragraph and callout only |
| Twelve evidence keys | Session close, after the prompt's own criteria | Fixture phase is not that gate |
