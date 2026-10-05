# Session 07 Prompt Integrity Review

**Date:** 2026-10-03
**Prompt:** `prompts/implementation/10_SESSION_07_PRODUCT_BUILD_VARIANTS_AND_QA.md`
**Verified SHA-256:** `d52011a6f0b725b16427629dc664cfc9f3432c4b5f71d26ce032d4b6c8ecb39d`
**Workbook authority:** `hands-off-money-machine-full-implementation-workbook.md` appendix row for this prompt (5,255 bytes, 237 lines)
**Scope:** Wave 1 only. Activate session 7 incomplete. Phase 1 of A07 only: top-level page and design shell from a validated ProductSpec, against the fixture Notion probe, with the phase persisted so a later wave can resume.

The prompt file is not amended. This record is the corrective addendum.

## 1. Prompt authenticity

**Status:** VERIFIED

- The extracted file's SHA-256 equals the workbook appendix value.
- The workbook copy between `COPY START` and `COPY END` is the same extract the appendix hashes.
- The prompt stays the unamended source of record.

## 2. Three-dimensional review

### Fidelity

**Verdict:** CONDITIONAL APPROVE. One high finding, resolved by the addendum.

**F-01 [HIGH] — The prompt's full session is not this wave**

- **Prompt lines:** 1–237, especially actions 2–13 and the required exit code at line 230.
- **Authority:** The operator slice is action 1, phase 1 only, plus session activation with evidence keys false. Session 06 is already complete at `ac6afcfb97c8b59fd0215083e89a1b37d292282b`. D-0010 activation preserves `completed_sessions`, sets `current_session` to `next_session`, and installs the new session's evidence keys all false.
- **Consequence of literal execution:** Building shared databases, the home dashboard, the notification dashboard, hubs, variants, QA, the fact ledger, and the workflow link, then printing `SESSION_07_PRODUCT_BUILD_AND_QA_COMPLETE`, would claim the session is finished.
- **Amendment:** Execute phase 1 only. Leave every session 7 evidence key false. Do not set the exit code. Do not commission A07, A08, or A09.

**What the prompt already gets right**

- Phase 1 is named and ordered ahead of databases, dashboards, hubs, and aesthetics (lines 17–24).
- The builder consumes a validated ProductSpec (line 13).
- Phase progress is persisted so a later run resumes at the next incomplete phase (line 26).
- Fixture Notion is the test double (line 188). The live sandbox sentence is a separate sentence (line 202) and is not this wave.
- The next prompt after a real session close is `11_SESSION_08_MERCHANDISING_AND_ASSET_FACTORY.md`. This wave does not advance `next_session` or `next_prompt`.

### Safety and executability

**Verdict:** CONDITIONAL APPROVE. One critical finding and two high findings, resolved by the addendum.

**S-01 [CRITICAL] — Action 11's live sandbox build mutates a real Notion workspace**

- **Prompt line:** 202.
- **Authority:** Standing rule against live provider mutation from tests. Session 06's fixture probe (`FixtureNotionAdapter`) and `FakeNotionProbe` are the in-process boundaries. Exit 78 for the scheduler stays held.
- **Consequence:** A literal run that finds credentials would create and delete Notion pages and databases, and could publish a page.
- **Amendment:** This wave performs no live HTTP, opens no real Notion workspace, creates no Etsy listing, and does not lift Exit 78. The probe argument must be the fixture adapter itself.

**S-02 [HIGH] — Action 12 commissions agents**

- **Prompt line:** 204–206.
- **Authority:** `commissioned_agents` is empty. A07, A08, and A09 are `DESIGNED` in `config/agents.yaml`. Commissioning is an operator decision. Activation cannot change `commissioned_agents`.
- **Consequence:** Marking those agents commissioned would unlock external writes the implementation does not have.
- **Amendment:** Do not commission A07, A08, or A09. Do not register an A07 implementation on the agent registry. `commissioned_agents` stays empty.

**S-03 [HIGH] — Two ProductSpec types already exist**

- **Prompt line:** 13 ("Consume only a validated ProductSpec").
- **Authority:** `money_machine.domain.models.product_spec.ProductSpec` is the A05 spec and carries `palette_name` and `palette_tokens`. `money_machine.domain.models.products.ProductSpec` is the catalogue and dedupe spec and has no palette. Workflow linking, which would choose a single handoff, is action 10 and is out of this wave.
- **Consequence:** Accepting either model, or a dict that happens to parse, builds a shell from the wrong contract or from unvalidated input.
- **Amendment:** Phase 1 accepts only the exact A05 type, which is already validated by its model. The catalogue spec is rejected. No workflow event is emitted. This sharpens the prompt; it does not contradict the workbook, so no decision record is added.

**Executability**

- The fixture adapter already creates a top-level page (`parent_type="workspace"`) and a callout block. Phase 1 uses those two operations and no others.
- `notion_builds.checkpoint_names` and `provider_object_references` already name a resumable checkpoint. This wave persists that shape to an injected file, not to Postgres and not to a live workspace.
- Parked Session 06 nits (int-subclass SystemExit, the False-row mutant, backtick `__context__` in the #49 body, CodeRabbit tip lag, `connected: true` in fake mode, argparse extra-arg token echo) do not block phase 1. They stay parked.

### Gameability

**Verdict:** CONDITIONAL APPROVE. One critical finding, resolved by the addendum.

**G-01 [CRITICAL] — The exit code and a stub page both satisfy a careless reading**

- **Prompt lines:** 218–230.
- **Cheap fake:** Write `SESSION_07_PRODUCT_BUILD_AND_QA_COMPLETE` into the control files, or return a checkpoint without calling the fixture.
- **Ungameable for this wave:** Session status stays `incomplete`. Every session 7 evidence key is false. `next_session` stays 7 and `next_prompt` stays this prompt. Tests show the fixture holds one unpublished workspace-parent page, a palette callout, no database, no hub page, and no second page on replay. A checkpoint whose page is missing does not create a replacement. Phase 2 is not run.

## 3. Corrective addendum

This addendum governs Wave 1. The prompt remains the unamended source of record.

1. Prove the prompt hash, then implement only the slice below.
2. Activate session 7 with D-0010: `current_session` 7, `session_status` `incomplete`, `completed_sessions` `[0, 1, 2, 3, 4, 5, 6]`, `next_session` 7, `next_prompt` `10_SESSION_07_PRODUCT_BUILD_VARIANTS_AND_QA.md`. Install the session 7 evidence keys and leave each one false. Do not set `SESSION_07_PRODUCT_BUILD_AND_QA_COMPLETE`. Do not claim SESSION_07 COMPLETE.
3. Keep `head_sha` and `evidence_closure_commit_sha` at the Session 06 closure tip `0f94d585f23d79e5ac18479f01e14f67cbaad332`. Keep `last_verified_commit` at the bootstrap SHA. Advance `state_revision` by one. Change `updated_at`. Leave `commissioned_agents`, blockers, and the transition contract's other flags unchanged. `completion_requires_next_session` stays 7 because `next_session` stays 7.
4. Evidence keys, all false:
   - `notion_product_builder_implemented`
   - `shared_databases_built`
   - `home_dashboard_built`
   - `notification_dashboard_built`
   - `identity_hubs_built`
   - `variant_builder_implemented`
   - `product_qa_implemented`
   - `product_fact_ledger_persisted`
   - `build_workflow_linked`
   - `product_build_tests_pass`
   - `control_files_and_checkpoint_current`
   - `evidence_closure_commit_recorded`
5. Phase 1 only, from prompt lines 17–18. Input is an exact `product_spec.ProductSpec`. Probe is an exact `FixtureNotionAdapter`. Create one top-level page (`parent_type` `workspace`, title from the spec, unpublished). Record the design shell as one callout of the palette name and palette tokens. Do not create shared databases, dashboards, hubs, notification dashboards, variants, QA results, fact-ledger rows, or workflow successors.
6. Persist `checkpoint_names` `["top_level_page_and_design_shell"]` and the provider ids to an injected path. A later call with that checkpoint does not create another page. The next phase name is `shared_databases` and this wave does not run it. A missing page behind a saved checkpoint is an error, not a rebuild.
7. Tests use the fixture only. No live HTTP, no real Notion workspace, no Etsy listing, no Exit 78 lift, no action 11 sandbox.
8. Session 06 parked nits stay parked.

## 4. Deferrals

| Finding | Owner | Reason |
|---|---|---|
| Actions 2–10 (databases, dashboards, hubs, repair, variants, QA, fact ledger, workflow) | Later Session 07 waves | Operator slice stops at phase 1 |
| Action 11 live sandbox | Later wave with explicit authorization | S-01 |
| Action 12 commissioning | Operator decision after full implementation | S-02 |
| Action 13 session exit code and reviewers | Session 07 close | This wave is not the close |
| Parked S06 nits | Unowned until one blocks a slice | Operator instruction |
| Single ProductSpec handoff from dedupe | Workflow-link wave | S-03; catalogue spec is rejected here, not converted |
