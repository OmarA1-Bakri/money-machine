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

# Session 07 Prompt Integrity Review — Wave 7

**Date:** 2026-10-06
**Prompt:** `prompts/implementation/10_SESSION_07_PRODUCT_BUILD_VARIANTS_AND_QA.md`
**Verified SHA-256:** `d52011a6f0b725b16427629dc664cfc9f3432c4b5f71d26ce032d4b6c8ecb39d`
**Workbook authority:** `hands-off-money-machine-full-implementation-workbook.md` appendix row for this prompt (5,255 bytes, 237 lines)
**Scope:** Wave 7 only. Tip-sync the incomplete session, then fixture-only phase `progress_and_repair` (prompt section 6) plus the should-fix sweep named by the operator. The Wave 1 record at `docs/control/reviews/2026-10-03-session-07-prompt-integrity.md` still governs phase 1. Waves 3–6 above still govern their phases. This record is the corrective addendum for Wave 7.

The prompt file is not amended.

## 1. Prompt authenticity

**Status:** VERIFIED

- The extracted file's SHA-256 equals the workbook appendix value `d52011a6f0b725b16427629dc664cfc9f3432c4b5f71d26ce032d4b6c8ecb39d`.
- The workbook copy between `COPY START` and `COPY END` is the same extract the appendix hashes.
- The prompt stays the unamended source of record.

## 2. Three-dimensional review

### Fidelity

**Verdict:** CONDITIONAL APPROVE. One high finding, resolved by the addendum.

**F-01 [HIGH] — Section 6 says capture a screenshot or provider response and do not rebuild unless required**

- **Prompt lines:** 88–104, against actions 7–13 at lines 106–206 and the six `BUILD_PHASES` names.
- **Authority:** `BUILD_PHASES` has six phases and names no seventh. The fixture adapter has no screenshot capture. `build_phases_complete` is the checkpoint sentinel after phase 6, not a variant phase. The next narrative phase is A08 variants, which this wave must not start.
- **Consequence of literal execution:** A failure could rebuild the whole product, a repair record could claim a screenshot the fixture cannot take, or the wave could start A08, A09, the fact ledger, or the workflow link.
- **Amendment:** Persist one typed progress record across the six phases. On a provider failure, store the response with evidence kind `provider_response` and a repair job, and resume from the failed operation, only when a prior record exists. Never rebuild the whole product unless the progress record is unrecoverable. A missing prior record is an error and writes nothing. A failure leaves a repair job only when a prior record exists. A first phase-1 failure with no record raises and writes no job and no file (notion_progress.py:248), which narrows prompt §6's 'create a repair job'. Checkpoint `next_phase` stays `build_phases_complete`. The narrative next phase is variants (A08), not started.

**What the prompt already gets right**

- Progress is persisted so a later run can resume (line 26 and lines 90–97).
- A failed operation captures provider evidence, creates a repair job, and does not rebuild the whole product unless required (lines 99–104). A failure leaves a repair job only when a prior record exists. A first phase-1 failure with no record raises and writes no job and no file (notion_progress.py:248), which narrows prompt §6's 'create a repair job'.
- Variants, QA, the fact ledger, the workflow link, and commissioning are later actions (lines 106–206).

### Safety and executability

**Verdict:** CONDITIONAL APPROVE. The Wave 1 critical and high findings still apply and stay in force.

**S-01 [CRITICAL] — Action 11 live sandbox.** Still deferred. This wave uses `FixtureNotionAdapter` only. No live HTTP, no real Notion workspace, no Etsy listing, no Exit 78 lift. Do not import `httpx`, `requests`, `notion_client`, or `APINotionAdapter`.

**S-02 [HIGH] — Action 12 commissioning.** A07, A08, and A09 stay DESIGNED. `commissioned_agents` stays empty.

**S-03 [HIGH] — Two ProductSpec types.** This phase accepts only `product_spec.ProductSpec`. The catalogue spec is rejected.

**S-04 [HIGH] — Tip-sync must not look like completion.** `head_sha` moves to the post-merge Wave 6 tip `3f0a30a8e52b183f10799128d4fd7b17c1b74495`. `evidence_closure_commit_sha` stays the Session 06 tip `0f94d585f23d79e5ac18479f01e14f67cbaad332`. `last_verified_commit` stays bootstrap. All twelve session 7 evidence keys stay false. `session_status` stays `incomplete`. This wave does not print `SESSION_07_PRODUCT_BUILD_AND_QA_COMPLETE`.

### Gameability

**Verdict:** CONDITIONAL APPROVE. One high finding, resolved by the addendum.

**G-01 [HIGH] — A repair-job string, a self-compared sample, or a case-sensitive source ban satisfies a careless reading**

- **Prompt lines:** 90–104, read against lines 74–76.
- **Cheap fake:** Append a repair-job label with no provider response, resume by rebuilding completed operations, compare sample text to `sample_content()` so a `client_name` suffix survives, or ban only the lowercase token `etsy`.
- **Ungameable for this wave:** A failure injected at each of the six phases leaves a repair job whose kind is `provider_response` and whose response text is the provider response only when a prior record exists, and a first phase-1 failure with no record raises and writes no job and no file (notion_progress.py:248). Resume keeps completed block and database ids and adds only the failed operation onward. A recomputed digest is accepted. Legacy progress files with no progress fail closed. Sample text is asserted as the literal identity, hub name, and hub description, and `client_name` is absent without calling `sample_content()`. `Etsy` and `ETSY` fail the source ban. A junk notification database and a placeholder Buyer name are rejected before any adapter write.

## 3. Corrective addendum

This addendum governs Wave 7. The prompt remains the unamended source of record.

1. Prove the prompt hash, then implement only the slice below.
2. Tip-sync only: `head_sha` becomes `3f0a30a8e52b183f10799128d4fd7b17c1b74495`. `evidence_closure_commit_sha` stays `0f94d585f23d79e5ac18479f01e14f67cbaad332`. `last_verified_commit` stays bootstrap `1abf0d7cca3a6b8cd7efcd0a45523538fd5bfd9d`. Advance `state_revision` from 54 to 55. `session_status` stays `incomplete`. `current_session` stays 7. `completed_sessions` stays `[0, 1, 2, 3, 4, 5, 6]`. `next_session` stays 7. `next_prompt` stays this prompt.
3. Leave all twelve session 7 evidence keys false. Do not set `SESSION_07_PRODUCT_BUILD_AND_QA_COMPLETE`.
4. Keep A07, A08, and A09 DESIGNED. `commissioned_agents` stays empty. Exit 78 stays HELD.
5. Persist one typed progress record for all six build phases: completed operations, deferred operations, created Notion ids, property mappings, page counts, and formula state. One schema, one reader, and one writer. A missing prior record is an error and writes nothing. A recomputed digest is accepted. Legacy progress files with no progress fail closed.
6. On a provider failure, store the response with kind `provider_response`, create a repair job, and resume from the failed operation only when a prior record exists, and a first phase-1 failure with no record raises and writes no job and no file (notion_progress.py:248). Never rebuild the whole product unless the progress record is unrecoverable. State that rule in code and docs. Test a recoverable resume and an unrecoverable rebuild. The fixture has no screenshots, so the record must not claim one.
7. Close the operator must-fixes and the should-fixes that this fixture can close. Park, with a reason, the ones the fixture cannot close: navigation as a page link, one home page per probe, CodeRabbit docstring coverage, the fixed sample date, and assigning page properties through a separate provider write.
8. Tests use the fixture only. Do not start A08, A09, the fact ledger, the workflow link, or commissioning.

## 4. Deferrals

| Finding | Owner | Reason |
|---|---|---|
| Actions 7–13 | Later Session 07 waves or the session close | Not this slice. Narrative next phase is variants (A08), not started |
| Action 11 live sandbox | Later wave with explicit authorization | S-01 |
| Action 12 commissioning | Operator decision after full implementation | S-02 |
| Navigation as a page-link block | Unowned until the fixture grows a link block | Fixture blocks are paragraph and callout only |
| One home page per probe | Unowned until a second top-level page is in scope | Dashboard and hub builders still require one top-level page |
| CodeRabbit docstring coverage 10.88% (W6, stale; not remeasured) | Unowned | Not re-measured this wave |
| Fixed sample catalogue date | Unowned | Sample rows stay on the deterministic catalogue date; the buyer current-date formula stays `now()` |
| Twelve evidence keys | Session close, after the prompt's own criteria | Fixture phase is not that gate |

# Session 07 Prompt Integrity Review — Wave 8

**Date:** 2026-10-06
**Prompt:** `prompts/implementation/10_SESSION_07_PRODUCT_BUILD_VARIANTS_AND_QA.md`
**Verified SHA-256:** `d52011a6f0b725b16427629dc664cfc9f3432c4b5f71d26ce032d4b6c8ecb39d`
**Workbook authority:** `hands-off-money-machine-full-implementation-workbook.md` appendix row for this prompt (5,255 bytes, 237 lines)
**Scope:** Wave 8 only. Fixture-only product variants (prompt section 7, A08) plus the must-fixes carried from Wave 7. Waves 1–7 above still govern their phases. This record is the corrective addendum for Wave 8.

The prompt file is not amended.

## 1. Prompt authenticity

**Status:** VERIFIED

- The extracted file's SHA-256 equals the workbook appendix value `d52011a6f0b725b16427629dc664cfc9f3432c4b5f71d26ce032d4b6c8ecb39d`.
- The prompt stays the unamended source of record.

## 2. Three-dimensional review

### Fidelity

**Verdict:** CONDITIONAL APPROVE. One high finding, resolved by the addendum.

**F-01 [HIGH] — Section 7 says duplicate the complete top-level product and section 11 says four variants**

- **Prompt lines:** 106–121, against line 11 ("four variants") and the six `BUILD_PHASES` names. Section 2 forbids a second catalogue.
- **Authority:** `duplicate_page` on the fixture copies title, parent, icon, cover, and properties. It does not copy child pages, databases, or blocks. `BUILD_PHASES` has six names. `build_phases_complete` is the sentinel after phase 6. `find_spec_page` raises when more than one page carries `product_spec_id`.
- **Consequence of literal execution:** A deep clone would create a second catalogue, a seventh phase name would fail the progress prefix check, and a duplicate that keeps `product_spec_id` would make later resumes fail closed.
- **Amendment:** One variant per `colour_variants` entry, zipped in index order with `palette_tokens`. The lengths must match and must be 3 or 4. "Total" means variant pages and does not count the original unpublished product. A 4-token spec is the four-variant case. A 3-token spec yields 3. A mismatch or a duplicate colour or token name raises and writes nothing. "Duplicate the complete top-level product" means `duplicate_page` only. Pop `product_spec_id` on the copy immediately. Keep the same workspace parent and the other copied properties. Then set that variant's cover, icon, one accent callout, and one vocabulary block. Do not mutate the original page, hubs, or databases. Publish only the variant pages. Enable duplicate-as-template. Disable search indexing. The secret link is `get_public_url`. Checkpoint names stay the six build phases. The returned checkpoint's `next_phase` is `qa`. `provider_object_references["variants"]` marks variants complete. `created_notion_ids["variants"]` stays `None` until then.

**What the prompt already gets right**

- Variants are a separate action after the six build phases (lines 106–121).
- Each variant is published as its own top-level page, with duplicate-as-template on, search indexing off, and a recorded secret link (lines 118–121).
- Commissioning is section 12 and is not this wave.

### Safety and executability

**Verdict:** CONDITIONAL APPROVE. The Wave 1 critical and high findings still apply and stay in force.

**S-01 [CRITICAL] — Action 11 live sandbox.** Still deferred. This wave uses `FixtureNotionAdapter` only. No live HTTP, no real Notion workspace, no Etsy listing, no Exit 78 lift. Do not import `httpx`, `requests`, `notion_client`, or `APINotionAdapter`. The new module may call `publish_page` because section 7 requires it. It must not contain the `https://` literal; the secret link comes from `get_public_url`.

**S-02 [HIGH] — Action 12 commissioning.** A07, A08, and A09 stay DESIGNED. `commissioned_agents` stays empty. `variant_builder_implemented` stays false.

**S-03 [HIGH] — Two ProductSpec types.** This phase accepts only `product_spec.ProductSpec`. The catalogue spec is rejected.

**S-04 [HIGH] — Tip-sync must not look like completion.** `head_sha` moves to the post-merge Wave 7 tip `9bc56b2c839f66fce13bebf55cb30e88474f526e`. `evidence_closure_commit_sha` stays the Session 06 tip `0f94d585f23d79e5ac18479f01e14f67cbaad332`. `last_verified_commit` stays bootstrap. All twelve session 7 evidence keys stay false. `session_status` stays `incomplete`. This wave does not print `SESSION_07_PRODUCT_BUILD_AND_QA_COMPLETE`. The narrative next phase is `qa` (A09) and is not started.

### Gameability

**Verdict:** CONDITIONAL APPROVE. One high finding, resolved by the addendum.

**G-01 [HIGH] — A renamed copy, a self-compared vocabulary string, or a seventh phase label satisfies a careless reading**

- **Prompt lines:** 106–121, read against the six phase names and section 2.
- **Cheap fake:** Create empty pages, leave `product_spec_id` on the copies, publish the original, or append `variants` to `checkpoint_names`.
- **Ungameable for this wave:** Each colour becomes one workspace page whose title is the product title, a slash, and the colour. Saved aesthetics and created ids are checked before any adapter write. Release refuses every candidate, then drops a copied `product_spec_id` only for a page whose title is a variant title or `{title} (Copy)` and whose spec id equals the source value. A database or page whose parent is the candidate page or any block in its block tree, or a direct child block other than the matching accent and vocabulary, refuses that candidate with zero writes. ProductSpec uniqueness runs after the drop. An unrelated page with a variant title or a `(Copy)` title is not adopted, not published, and not recorded. Icon, cover, accent callout, and vocabulary text come from that index's palette token. Vocabulary text is the literal identity, colour, token name, and hex, and `client_name` is absent. The original page stays unpublished, with duplicate-as-template off and search indexing on. Unpublished, duplicate-as-template, search-indexing, icon, and cover drift on an adopted variant page is repaired by `_finish_variant`, not refused. That repair is intended. The original home page is still refused when it is published, marked as a template, or not indexed. Replay writes nothing and creates no second page. On a stored checkpoint, an extra workspace-level `/ Blue`, `/ Purple`, or `(Copy)` page passes that replay with zero writes. That limit is parked. The secret link is the value returned by `get_public_url` on the variant page, and replay compares that call. A provider failure during release or after the first variant leaves one `provider_response` job, and only when the aesthetics checkpoint already exists. Resume finishes a provable titled page or a provable `{title} (Copy)` page. It does not duplicate that page again. A missing file or a pre-aesthetics checkpoint raises and writes nothing. Adoption compares the title and the copyable shell fields. An unrelated empty workspace page that carries the source `product_id` and shell block id would be adopted, and `parent_id` compares equal when both are `None`. That limit is parked for the live wave. This wave does not claim a proven lineage. `Etsy` and `ETSY` fail the source ban on the new module.

## 3. Corrective addendum

This addendum governs Wave 8. The prompt remains the unamended source of record.

1. Prove the prompt hash, then implement only the slice below.
2. Tip-sync only: `head_sha` becomes `9bc56b2c839f66fce13bebf55cb30e88474f526e`. `evidence_closure_commit_sha` stays `0f94d585f23d79e5ac18479f01e14f67cbaad332`. `last_verified_commit` stays bootstrap `1abf0d7cca3a6b8cd7efcd0a45523538fd5bfd9d`. Advance `state_revision` from 55 to 56. `session_status` stays `incomplete`. `current_session` stays 7. `completed_sessions` stays `[0, 1, 2, 3, 4, 5, 6]`. `next_session` stays 7. `next_prompt` stays this prompt. Narrative `next_phase` becomes `qa` (A09), not started.
3. Leave all twelve session 7 evidence keys false. Do not set `SESSION_07_PRODUCT_BUILD_AND_QA_COMPLETE`. The log and the pull request say this is not SESSION_07 COMPLETE and Exit 78 stays HELD.
4. Keep A07, A08, and A09 DESIGNED. `commissioned_agents` stays empty. Do not edit `config/agents.yaml`.
5. Variants go through `write_checkpoint`. `write_document` stays the single progress writer. `checkpoint_names` stay the six build phases. `created_notion_ids["variants"]` is `None` until variants exist. The aesthetics parser strips the `variants` reference key so a variants file can be read back. Re-entering aesthetics after variants raises `hub page is unexpected` because that checker still allows one top-level page, and it does not rewrite the file.
6. On a provider failure of `variants.duplicate`, including a `ProviderFailure` from the release `drop_page_property`, store kind `provider_response` only when a prior record exists, and a first failure with no record raises and writes no job and no file (`notion_progress.py:250`). The job phase stays `aesthetics_and_content_completion` because variants are not a seventh checkpoint name. Every `build_variants` branch checks saved aesthetics and created ids before any adapter write (`notion_variants.py:98`). On an empty variants list, `await _plan_variants` (`:353`, call at `:103`) runs inside the try (`:102`) and before any adapter call. A `ProviderFailure` from the plan `get_public_url` uses `raise_recorded` (`notion_progress.py:133`). A `ProductBuildError` from the plan is not caught and does not append a repair job. The plan checks every adoption, finished colours included: `_require_original` (`:369`), `_require_adoptable` (`:385`, defined at `:626`), the duplicate-block raises (`:712-713` and `:736-737`), and the published secret link (`_require_published_link` at `:386`, `get_public_url` at `:394`). `get_public_url` is a read. It is not a counted write. An empty finish link raises `ProviderFailure` at `:695-696`. A planned page id that is not in the probe raises `planned variant page is missing` (`:381-383`) before any write. Execution then applies that plan: the spec-id release (`:104`), the ProductSpec uniqueness bind (`:105`), and `_ensure_planned` (`:106`). Only the empty-variants path releases. A `(Copy)` page planted before an unrelated spec-id page, a database or page whose parent is the candidate page or any of its blocks, and a drop crash followed by a database under that `(Copy)` each raise with zero adapter writes. A hub child titled `{title} (Copy)` or `/ Blue` raises `hub page is unexpected` on replay. Extra workspace-level `/ Blue`, `/ Purple`, or `(Copy)` pages pass replay with zero writes. That outcome is pinned and parked. A provider failure still records a repair job through `write_checkpoint` when a prior record exists. A valid build writes after that validation. A tampered checkpoint raises before any adapter write. Adoption requires the shell, the spec value, and no foreign or nested child (`_require_adoptable` at `:385`, defined at `:626`) before any finish write. The finish call is `:668`. The plan skips `page_id == ""` at `:379`. Unpublished, duplicate-as-template, search-indexing, icon, and cover drift on an adopted variant page is repaired by `_finish_variant`, not refused. That repair is intended. Resume adoption stays `_find_titled` (`:345`) and `_find_copy` (`:341`). Foreign means no direct child block other than the matching accent and vocabulary, and no database or page whose parent is the page or any block in its block tree. An unrelated empty workspace page with the source `product_id` and shell block id would be adopted, and `parent_id` compares equal when both are `None`. That limit is parked. This wave does not claim a proven lineage. Loaded created ids stay. Resume finishes a provable titled page or a provable `(Copy)` page without a second copy.
7. Close the carried must-fixes with killing tests: phase-6 replay tamper of created ids (CI-1 the `_require_created_ids` call, CI-2 database pairs, CI-3 hub pairs, CI-4 accent and sample pairs), hub `navigation_block_id` on both sides of the replay comparison, duplicate accent labels, `_ensure_row` `client_name`, and `_adopted_database` title type. Name any survivor with its exact site.
8. Tests use the fixture only. Do not start A09, the fact ledger, the workflow link, or commissioning.

## 4. Deferrals

| Finding | Owner | Reason |
|---|---|---|
| Actions 8–13 | Later Session 07 waves or the session close | Not this slice. Narrative next phase is qa (A09), not started |
| Action 11 live sandbox | Later wave with explicit authorization | S-01 |
| Action 12 commissioning | Operator decision after full implementation | S-02 |
| Deep clone of databases and child pages | Rejected for this fixture | `duplicate_page` is shallow, and a second catalogue contradicts section 2 |
| Navigation as a page-link block | Unowned until the fixture grows a link block | Fixture blocks are paragraph and callout only |
| CodeRabbit docstring coverage 10.88% (W6, stale; not remeasured) | Unowned | Not re-measured this wave |
| Twelve evidence keys | Session close, after the prompt's own criteria | Fixture variants are not that gate |
| Extra workspace-level `/ Blue`, `/ Purple`, or `(Copy)` pages on replay | Later wave | They pass replay with zero writes. Pinned by `test_replay_pins_extra_workspace_variant_titles_as_a_known_limit`. A hub child with those titles is refused. Not a proven lineage |
| W9 must-fix survivors from review 5427897657 | Next Session 07 wave | 13 items and 14 sites remain, named with file:line in `NEXT_SESSION.md`. The title compare and the two duplicate-block raises are closed |

# Session 07 Prompt Integrity Review — Wave 9

**Date:** 2026-10-07
**Prompt:** `prompts/implementation/10_SESSION_07_PRODUCT_BUILD_VARIANTS_AND_QA.md`
**Verified SHA-256:** `d52011a6f0b725b16427629dc664cfc9f3432c4b5f71d26ce032d4b6c8ecb39d`
**Workbook authority:** `hands-off-money-machine-full-implementation-workbook.md` appendix row for this prompt (5,255 bytes, 237 lines)
**Scope:** Wave 9 only. Fixture-only A09 product QA (prompt section 8) over the A08 variants checkpoint, plus the must-fixes carried from Wave 8. Waves 1–8 above still govern their phases. This record is the corrective addendum for Wave 9.

The prompt file is not amended.

## 1. Prompt authenticity

**Status:** VERIFIED

- The extracted file's SHA-256 equals the workbook appendix value `d52011a6f0b725b16427629dc664cfc9f3432c4b5f71d26ce032d4b6c8ecb39d`.
- The prompt stays the unamended source of record.

## 2. Three-dimensional review

### Fidelity

**Verdict:** CONDITIONAL APPROVE. One high finding, resolved by the addendum.

**F-01 [HIGH] — Section 8 lists product-fact persistence and automatic repair beside section 9 and section 11**

- **Prompt lines:** 123–153, against section 9 (lines 155–170) and section 11 (lines 186–202).
- **Authority:** `BUILD_PHASES` has six names. Variants leave `next_phase` as `qa`. `write_checkpoint` is the only progress writer. Repair job kinds are `provider_response` and `rebuild_refused`. The fixture can set publish, duplicate-as-template, and search indexing. It cannot update a formula expression or a linked-view source in place. A new formula or view would mint an id the checkpoint does not hold.
- **Consequence of literal execution:** Building the section 9 ledger, the section 10 workflow link, or a second catalogue from "fresh duplicate" would leave the session looking finished, or a repair would orphan the stored ids.
- **Amendment:** QA reads the variants checkpoint through `FixtureNotionAdapter` only. The verdict is `PASS`, `FAIL_REPAIRABLE`, or `BLOCKED`. It is stored in `provider_object_references["qa"]` by `write_checkpoint`. Checkpoint names stay the six build phases. `next_phase` becomes `fact_ledger` and section 9 is not run. Repairable defects are only an unpublished variant, duplicate-as-template off, or search indexing on. Those repairs use the existing adapter methods, then QA runs again. Any other failed check is `BLOCKED` and makes zero adapter writes. A passing run proves one fresh `duplicate_page` of the first variant and does not duplicate it again on resume. The facts stored on the QA reference are the colours, hubs, databases, variant count, page count, and secret links already on the variants build. They are not the section 9 ledger.

**What the prompt already gets right**

- QA returns `PASS`, `FAIL_REPAIRABLE`, or `BLOCKED` (lines 145–151).
- `FAIL_REPAIRABLE` creates targeted repair jobs and reruns QA (line 153).
- QA is a read of the build, and A09 stays `EXTERNAL_READ` on the roster. The one proof duplicate is the section 8 "fresh duplicate works" check, not a second product.

### Safety and executability

**Verdict:** CONDITIONAL APPROVE. The Wave 1 critical and high findings still apply and stay in force.

**S-01 [CRITICAL] — Action 11 live sandbox.** Still deferred. This wave uses `FixtureNotionAdapter` only. No live HTTP, no real Notion workspace, no Etsy listing, no socket, no Exit 78 lift. Do not import `httpx`, `requests`, `notion_client`, or `APINotionAdapter`. The module must not contain an `https://` literal. Public links come from `get_public_url` and `verify_stranger_access`.

**S-02 [HIGH] — Action 12 commissioning.** A07, A08, and A09 stay DESIGNED. `commissioned_agents` stays empty. `product_qa_implemented` stays false. Do not edit `config/agents.yaml`.

**S-03 [HIGH] — Two ProductSpec types.** This phase accepts only `product_spec.ProductSpec`. The catalogue spec is rejected.

**S-04 [HIGH] — Tip-sync must not look like completion.** `head_sha` becomes the W8 squash `6b087370eaaf1a5e09d9868643cca7b3654ddc4a`, the merged base of this wave. It does not become this wave's own commit. `evidence_closure_commit_sha` stays the Session 06 tip `0f94d585f23d79e5ac18479f01e14f67cbaad332`. `last_verified_commit` stays bootstrap. All twelve session 7 evidence keys stay false. `session_status` stays `incomplete`. This wave does not print `SESSION_07_PRODUCT_BUILD_AND_QA_COMPLETE`. Narrative `next_phase` becomes `fact_ledger` and is not started.

### Gameability

**Verdict:** CONDITIONAL APPROVE. One high finding, resolved by the addendum.

**G-01 [HIGH] — A verdict string with no fixture checks, or a repair that still writes on a refusal, satisfies a careless reading**

- **Prompt lines:** 125–153.
- **Cheap fake:** Write `PASS` into the checkpoint without reading the fixture, treat every defect as repairable and rebuild the product, or call `duplicate_page` again on every resume.
- **Ungameable for this wave:** The plan runs before any adapter write. A missing variants checkpoint, a non-fixture probe, or a catalogue spec raises and leaves the file bytes unchanged, with adapter writes empty. `BLOCKED` records the verdict and makes zero adapter writes. `FAIL_REPAIRABLE` applies only the three flag repairs, reruns the plan, and records `PASS` only when the rerun is clean. A lying repair that does not change the flag records `BLOCKED`. The proof duplicate happens once. Resume of a stored `PASS` makes zero adapter writes. A `ProviderFailure` from the plan read or the proof duplicate uses `raise_recorded`. A `ProductBuildError` from the plan does not append a repair job. Tests make no socket or other network access.

## 3. Corrective addendum

This addendum governs Wave 9. The prompt remains the unamended source of record.

1. Prove the prompt hash, then implement only the slice below.
2. Tip-sync only: `head_sha` becomes `6b087370eaaf1a5e09d9868643cca7b3654ddc4a`. `evidence_closure_commit_sha` stays `0f94d585f23d79e5ac18479f01e14f67cbaad332`. `last_verified_commit` stays bootstrap `1abf0d7cca3a6b8cd7efcd0a45523538fd5bfd9d`. Advance `state_revision` from 56 to 57. `session_status` stays `incomplete`. `current_session` stays 7. `completed_sessions` stays `[0, 1, 2, 3, 4, 5, 6]`. `next_session` stays 7. `next_prompt` stays this prompt. Narrative `next_phase` becomes `fact_ledger` and this wave does not run it.
3. Leave all twelve session 7 evidence keys false, including `product_qa_implemented` and `variant_builder_implemented`. Do not set `SESSION_07_PRODUCT_BUILD_AND_QA_COMPLETE`. The log and the pull request say this is not SESSION_07 COMPLETE and Exit 78 stays HELD.
4. Keep A07, A08, and A09 DESIGNED. `commissioned_agents` stays empty. Do not edit `config/agents.yaml`.
5. QA goes through `write_checkpoint`. `write_document` stays the single progress writer. `checkpoint_names` stay the six build phases. The aesthetics parser also strips the `qa` reference key so a QA file can be read back by the variants loader. Re-entering variants after QA does not rewrite the file.
6. Close the carried must-fixes with killing tests. The 13 items and 14 sites in `NEXT_SESSION.md` are in scope, including the saved-path `_require_original` call. A database whose parent is a hub block or a home block is refused before any adapter write. `type(database) is NotionDatabase` also rejects a subclass, with a test. The crash matrix asserts that a block-step crash leaves every page unpublished. `IMPLEMENTATION_LOG.md` line 124 of the W8 entry is reworded to say there is no current test and that probes differ only in refusal message, never in writes or acceptance. The doubled period after `local-only` is removed. The log notes that tests make no socket or network access.
7. Tests use the fixture only. Do not start the section 9 fact ledger, the workflow link, or commissioning. Do not run the live sandbox.

## 4. Deferrals

| Finding | Owner | Reason |
|---|---|---|
| Section 9 fact ledger | Later Session 07 wave | Narrative next phase is `fact_ledger`, not started. QA persists the facts it checked; it does not open a second ledger |
| Section 10 workflow link | Later Session 07 wave | Not this slice |
| Section 11 live sandbox | Later wave with explicit authorization | S-01 |
| In-place formula or linked-view repair | Later wave if the fixture grows an update method | A new id would not match the stored checkpoint. Those defects are `BLOCKED` with zero adapter writes |
| Action 12 commissioning | Operator decision after full implementation | S-02 |
| Twelve evidence keys | Session close, after the prompt's own criteria | Fixture QA is not that gate |

# Session 07 Prompt Integrity Review — Wave 10

**Date:** 2026-10-07
**Prompt:** `prompts/implementation/10_SESSION_07_PRODUCT_BUILD_VARIANTS_AND_QA.md`
**Verified SHA-256:** `d52011a6f0b725b16427629dc664cfc9f3432c4b5f71d26ce032d4b6c8ecb39d`
**Workbook authority:** `hands-off-money-machine-full-implementation-workbook.md` appendix row for this prompt (5,255 bytes, 237 lines)
**Scope:** Wave 10 only. Fixture-only product fact ledger (prompt section 9) and workflow link (prompt section 10) over the merged W8 variants and W9 QA records, plus the four carried items from the #59 final PASS. Waves 1–9 above still govern their phases. This record is the corrective addendum for Wave 10.

The prompt file is not amended.

## 1. Prompt authenticity

**Status:** VERIFIED

- The extracted file's SHA-256 equals the workbook appendix value `d52011a6f0b725b16427629dc664cfc9f3432c4b5f71d26ce032d4b6c8ecb39d`.
- The prompt stays the unamended source of record.

## 2. Three-dimensional review

### Fidelity

**Verdict:** CONDITIONAL APPROVE. Two high findings, resolved by the addendum and by D-0029.

**F-01 [HIGH] — Section 9 lists a second fact set beside the QA snapshot**

- **Prompt lines:** 155–170, against section 8 facts already stored on the QA reference.
- **Authority:** W9 stores colours, hubs, databases, variant count, page count, and secret links on `provider_object_references["qa"]`. Those are a QA snapshot. They are not the section 9 ledger. `write_checkpoint` is the only progress writer. `BUILD_PHASES` has six names.
- **Consequence of literal execution:** Copying the QA snapshot, or reading `colour_variants`, `hubs`, `title`, or `version` off the caller spec, would let merchandising claim facts the fixture did not prove.
- **Amendment:** The ledger is a later read of the persisted checkpoint and the fixture adapter. Page count is the known ids. Hub and database titles come from the adapter. Variant names and secret links come from the stored records, checked against the adapter. Dashboard outputs are the adapter formula expressions. `supported_devices` is `unverified`. `free_update_policy` is `not_configured`. `build_version` is the checkpoint value. Caller spec fields are ignored. QA facts are compared where they overlap. They are not copied in as the ledger.

**F-02 [HIGH] — Section 10 names are not the workflow job types, and "ready" is not a created job**

- **Prompt lines:** 172–184, and exit criterion line 223 ("Downstream merchandising job is created"), against section 11 line 200 ("automatic successor creation").
- **Authority:** `config/workflows.yaml` is the graph. Session 03 prompt-integrity finding M11 voided the prompt's example job names as a parallel authority. D-0029 records the label map: BUILD_NOTION_TEMPLATE is ProductBuildJob, RUN_PRODUCT_QA is ProductQAJob, REPAIR is BuildRepairJob, CREATE_VARIANTS is VariantBuildJob, RUN_VARIANT_QA is VariantPublishJob, and GENERATE_LISTING_PACKAGE ready is ListingCopyJob through ScreenshotJob.
- **Consequence of literal execution:** Editing `config/workflows.yaml`, inserting a second engine, or creating ListingCopyJob would invent a graph the Session 03 decision already refused.
- **Amendment:** Walk the existing YAML graph through `load_workflows_config`. Store the prompt names only as labels on that path. Record the REPAIR edge. Do not execute it. "Ready" means the last step names ListingCopyJob and its output contracts include ListingPackage. Do not create the job. Do not edit `config/workflows.yaml`.

**What the prompt already gets right**

- Section 9 names the facts merchandising may claim, and it forbids claims from anywhere else (lines 155–170).
- Section 10 names one chain that ends at GENERATE_LISTING_PACKAGE ready (lines 172–184).
- Supported devices and the free-update policy are conditional ("if verified", "if configured"). Neither is verified on this fixture.

### Safety and executability

**Verdict:** CONDITIONAL APPROVE. The Wave 1 critical and high findings still apply and stay in force.

**S-01 [CRITICAL] — Action 11 live sandbox.** Still deferred. This wave uses `FixtureNotionAdapter` only. No live HTTP, no real Notion workspace, no Etsy listing, no socket, no Exit 78 lift. Do not import `httpx`, `requests`, `notion_client`, or `APINotionAdapter`. The ledger module must not contain an `https://` literal.

**S-02 [HIGH] — Action 12 commissioning.** A07, A08, and A09 stay DESIGNED. `commissioned_agents` stays empty. `product_fact_ledger_persisted` and `build_workflow_linked` stay false. Do not edit `config/agents.yaml`.

**S-03 [HIGH] — Two ProductSpec types.** This phase accepts only `product_spec.ProductSpec`. The catalogue spec is rejected. The probe must be `FixtureNotionAdapter`.

**S-04 [HIGH] — Tip-sync must not look like completion.** `head_sha` becomes the W9 squash `a4e9b025021b4effbb2b2879c1db756403cb1676`, the merged base of this wave. It does not become this wave's own commit. `evidence_closure_commit_sha` stays the Session 06 tip `0f94d585f23d79e5ac18479f01e14f67cbaad332`. `last_verified_commit` stays bootstrap. All twelve session 7 evidence keys stay false. `session_status` stays `incomplete`. This wave does not print `SESSION_07_PRODUCT_BUILD_AND_QA_COMPLETE`. Narrative `next_phase` becomes `test_matrix` and is not started. Section 11 is not this wave.

### Gameability

**Verdict:** CONDITIONAL APPROVE. One high finding, resolved by the addendum.

**G-01 [HIGH] — A PASS string, caller-spec facts, a second write, or a ready link on a blocked QA satisfies a careless reading**

- **Prompt lines:** 155–184.
- **Cheap fake:** Write `PASS` and `ListingCopyJob` without reading the fixture, copy colour names from the caller spec, write the checkpoint again on resume, or mark the listing ready while QA is `BLOCKED`.
- **Ungameable for this wave:** The plan runs before any adapter write. Every ledger fact is deterministic and comes from persisted state and adapter facts. A stored record that does not match the live plan raises `fact ledger does not match` or `workflow link does not match`, with 0 adapter writes and unchanged file bytes. Every refusal path makes 0 writes. A `BLOCKED` record is re-planned only when the live plan is no longer blocked. Resume of a matching record does not write. A crash inside `write_checkpoint` leaves no ledger key, and the resume writes once to a single `PASS`. There is one `write_checkpoint`. The YAML walk is read from `load_workflows_config`. A missing edge or a missing ListingPackage output raises before that write. An empty captured URL `""` is skipped, the same as a missing URL, so a real unpublish can still repair. That skip is the documented contract at `notion_qa.py:526`. It is pinned, not turned into a refusal.

## 3. Corrective addendum

This addendum governs Wave 10. The prompt remains the unamended source of record.

1. Prove the prompt hash, then implement only the slice below.
2. Tip-sync only: `head_sha` becomes `a4e9b025021b4effbb2b2879c1db756403cb1676`. `evidence_closure_commit_sha` stays `0f94d585f23d79e5ac18479f01e14f67cbaad332`. `last_verified_commit` stays bootstrap `1abf0d7cca3a6b8cd7efcd0a45523538fd5bfd9d`. Advance `state_revision` from 57 to 58. `session_status` stays `incomplete`. `current_session` stays 7. `completed_sessions` stays `[0, 1, 2, 3, 4, 5, 6]`. `next_session` stays 7. `next_prompt` stays this prompt. Narrative `next_phase` becomes `test_matrix` and this wave does not run it.
3. Leave all twelve session 7 evidence keys false, including `product_fact_ledger_persisted` and `build_workflow_linked`. Do not set `SESSION_07_PRODUCT_BUILD_AND_QA_COMPLETE`. The log and the pull request say this is not SESSION_07 COMPLETE and Exit 78 stays HELD.
4. Keep A07, A08, and A09 DESIGNED. `commissioned_agents` stays empty. Do not edit `config/agents.yaml` or `config/workflows.yaml`.
5. The ledger and the link go through one `write_checkpoint`. `write_document` stays the single progress writer. `checkpoint_names` stay the six build phases. The aesthetics parser also strips `fact_ledger` and `workflow_link`. `_write_qa` keeps both keys when QA rewrites, so a later `BLOCKED` to `PASS` replan can still see them.
6. Facts are the persisted checkpoint and the fixture adapter, never the caller spec. A stored mismatch raises `does not match` with 0 adapter writes. A `BLOCKED` result can be re-planned when the live plan is no longer blocked. Crash-resume reaches a single `PASS`. The workflow link records the YAML path, including ScreenshotJob, and does not create ListingCopyJob. D-0029 is the label map.
7. Close the four carried items from the #59 final PASS. The fresh-duplicate title and spec-id tests keep going after the proof error, so each mutant fails at `assert false_checks == ("fresh_duplicate",)`. The applicable mutants replace the title compare and the spec-id check with `True`. An empty captured URL `""` repairs like a missing URL, and a test pins that skip. Re-measure the 17 variant-file mutation rows. Reword the title row so the mutant is literally applicable. Park the section 8 QA coverage gap, the crash-resume repair drop, and the pull-request `docs/control` list in `NEXT_SESSION.md`, marked scheduled for the W11 test matrix. Do not fix them here.
8. Tests use the fixture only, with sockets blocked. Do not start section 11, the live sandbox, or commissioning.

## 4. Deferrals

| Finding | Owner | Reason |
|---|---|---|
| Section 11 test matrix and live sandbox | W11, and explicit authorization for the sandbox | S-01. Narrative next phase is `test_matrix`, not started |
| Section 8 QA coverage gap | W11 test matrix | QA records PASS when the home nav text, the 3 palette callouts, the identity callout, the 6 hub "returns to Home" texts, or the 3 home linked views are deleted. Uncovered: `_linked_views` `notion_qa.py:366`, `_palette` `:576`, `_teardown` `:607` |
| Crash-resume drops earlier repairs | W11 test matrix | Parked with the coverage gap. Not fixed in W10 |
| Action 12 commissioning | Operator decision after full implementation | S-02 |
| Twelve evidence keys | Session close, after the prompt's own criteria | Fixture ledger and link are not that gate |

## Wave 11 addendum (2026-10-09)

The prompt file is unchanged. SHA-256 `d52011a6f0b725b16427629dc664cfc9f3432c4b5f71d26ce032d4b6c8ecb39d`. This addendum does not cut the prompt. It binds this wave to the frozen carry list.

1. Prove the prompt hash, then implement only the slice below. Do not edit the prompt file.
2. Do not edit `IMPLEMENTATION_STATE.json`. State revision stays 58. Another change takes revision 59. This wave does not take it. `head_sha` stays `a4e9b025021b4effbb2b2879c1db756403cb1676`. `evidence_closure_commit_sha` stays `0f94d585f23d79e5ac18479f01e14f67cbaad332`. `last_verified_commit` stays bootstrap. `session_status` stays `incomplete`. `current_session` stays 7. `next_session` stays 7. `next_prompt` stays this prompt. Narrative `next_phase` stays `test_matrix` and this wave does not start section 11.
3. Leave all twelve session 7 evidence keys false. Do not set `SESSION_07_PRODUCT_BUILD_AND_QA_COMPLETE`. A07, A08, and A09 stay DESIGNED. `commissioned_agents` stays empty. Do not edit `config/agents.yaml` or `config/workflows.yaml`. Exit 78 stays HELD.
4. Close the section 8 QA coverage gap. Deleting the home nav text, any of the 3 palette callouts, the identity callout, any of the 6 hub return texts, or any of the 3 home linked views (Tasks, Events, Notes) must record `BLOCKED` with 0 adapter writes, or refuse with 0 writes, and must not record `PASS`. Cover `_linked_views`, `_palette`, and `_teardown`.
5. A crash after a repair must leave that repair in the stored progress record. The resume must still list it.
6. The #61 parked items are fixed in this wave or listed under "Parked to next wave" with a reason. A new test that already passes on `4b899fcf` is not added.
7. Remove the closed coverage entry from `NEXT_SESSION.md`.
8. Tests use the fixture only, with sockets blocked. No live Notion, no Etsy, no `--execute`.

| Finding | Owner | Reason |
|---|---|---|
| Section 11 test matrix and live sandbox | Later wave, and explicit authorization for the sandbox | S-01. Narrative next phase stays `test_matrix`, not started |
| Action 12 commissioning | Operator decision after full implementation | S-02 |
| Twelve evidence keys and STATE revision 59 | After the other revision-59 change merges | This wave does not edit `IMPLEMENTATION_STATE.json` |
