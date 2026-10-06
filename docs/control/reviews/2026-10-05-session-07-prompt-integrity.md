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
- **Ungameable for this wave:** Each colour becomes one workspace page whose title is the product title, a slash, and the colour. Saved aesthetics and created ids are checked before any adapter write. Release refuses every candidate, then drops a copied `product_spec_id` only for a page whose title is a variant title or `{title} (Copy)` and whose spec id equals the source value. A database or page whose parent is the candidate page or any block in its block tree, or a direct child block other than the matching accent and vocabulary, refuses that candidate with zero writes. ProductSpec uniqueness runs after the drop. An unrelated page with a variant title or a `(Copy)` title is not adopted, not published, and not recorded. Icon, cover, accent callout, and vocabulary text come from that index's palette token. Vocabulary text is the literal identity, colour, token name, and hex, and `client_name` is absent. The original page stays unpublished, with duplicate-as-template off and search indexing on. Replay writes nothing and creates no second page. On a stored checkpoint, an extra workspace-level `/ Blue`, `/ Purple`, or `(Copy)` page passes that replay with zero writes. That limit is parked. The secret link is the value returned by `get_public_url` on the variant page, and replay compares that call. A provider failure during release or after the first variant leaves one `provider_response` job, and only when the aesthetics checkpoint already exists. Resume finishes a provable titled page or a provable `{title} (Copy)` page. It does not duplicate that page again. A missing file or a pre-aesthetics checkpoint raises and writes nothing. Adoption compares the title and the copyable shell fields. An unrelated empty workspace page that carries the source `product_id` and shell block id would be adopted, and `parent_id` compares equal when both are `None`. That limit is parked for the live wave. This wave does not claim a proven lineage. `Etsy` and `ETSY` fail the source ban on the new module.

## 3. Corrective addendum

This addendum governs Wave 8. The prompt remains the unamended source of record.

1. Prove the prompt hash, then implement only the slice below.
2. Tip-sync only: `head_sha` becomes `9bc56b2c839f66fce13bebf55cb30e88474f526e`. `evidence_closure_commit_sha` stays `0f94d585f23d79e5ac18479f01e14f67cbaad332`. `last_verified_commit` stays bootstrap `1abf0d7cca3a6b8cd7efcd0a45523538fd5bfd9d`. Advance `state_revision` from 55 to 56. `session_status` stays `incomplete`. `current_session` stays 7. `completed_sessions` stays `[0, 1, 2, 3, 4, 5, 6]`. `next_session` stays 7. `next_prompt` stays this prompt. Narrative `next_phase` becomes `qa` (A09), not started.
3. Leave all twelve session 7 evidence keys false. Do not set `SESSION_07_PRODUCT_BUILD_AND_QA_COMPLETE`. The log and the pull request say this is not SESSION_07 COMPLETE and Exit 78 stays HELD.
4. Keep A07, A08, and A09 DESIGNED. `commissioned_agents` stays empty. Do not edit `config/agents.yaml`.
5. Variants go through `write_checkpoint`. `write_document` stays the single progress writer. `checkpoint_names` stay the six build phases. `created_notion_ids["variants"]` is `None` until variants exist. The aesthetics parser strips the `variants` reference key so a variants file can be read back. Re-entering aesthetics after variants raises `hub page is unexpected` because that checker still allows one top-level page, and it does not rewrite the file.
6. On a provider failure of `variants.duplicate`, including a `ProviderFailure` from the release `drop_page_property`, store kind `provider_response` only when a prior record exists, and a first failure with no record raises and writes no job and no file (`notion_progress.py:250`). The job phase stays `aesthetics_and_content_completion` because variants are not a seventh checkpoint name. Every `build_variants` branch checks saved aesthetics and created ids before any adapter write (`notion_variants.py:98`). The spec-id release (`:103`) and the ProductSpec uniqueness bind (`:104`) run only after that check, and only the empty-variants path releases. Release refuses every candidate before any drop (`:371-374`). A `(Copy)` page planted before an unrelated spec-id page, a database or page whose parent is the candidate page or any of its blocks, and a drop crash followed by a database under that `(Copy)` each raise with zero adapter writes. A hub child titled `{title} (Copy)` or `/ Blue` raises `hub page is unexpected` on replay. Extra workspace-level `/ Blue`, `/ Purple`, or `(Copy)` pages pass replay with zero writes. That outcome is pinned and parked. A provider failure still records a repair job through `write_checkpoint` when a prior record exists. A valid build writes after that validation. A tampered checkpoint raises before any adapter write. Adoption requires the title and the copyable shell fields (`_require_adoptable` at `:548`, defined at `:506`) before any finish write. Resume adoption stays `_find_titled` (`:277`) and `_find_copy` (`:278-279`). Foreign means no direct child block other than the matching accent and vocabulary, and no database or page whose parent is the page or any block in its block tree. An unrelated empty workspace page with the source `product_id` and shell block id would be adopted, and `parent_id` compares equal when both are `None`. That limit is parked. This wave does not claim a proven lineage. Loaded created ids stay. Resume finishes a provable titled page or a provable `(Copy)` page without a second copy.
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
| W9 must-fix survivors from review 5427897657 | Next Session 07 wave | Named with file:line in `NEXT_SESSION.md`. Not killed this wave |
