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
