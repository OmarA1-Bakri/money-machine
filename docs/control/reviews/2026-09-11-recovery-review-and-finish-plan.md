# Money Machine recovery review and finish plan

Date: 2026-09-11. Status: review and execution plan; not a session closure or commissioning claim.

## Decision and outcome

Operator clarification, 2026-09-11: faithfully implementing `hands-off-money-machine-full-implementation-workbook.md` is the governing requirement. This plan sequences delivery; it does not replace or reduce that workbook. Preserve its business sequence, thresholds, outputs, automatic handoffs and cull/multiply loop. No commercial revalidation or substitute business model. Apply the workbook's own source precedence and its narrowly permitted provider-mechanics adaptations.

Before porting business behavior, reconcile existing decisions against the workbook and its playbook authority. An entry labelled accepted is not, by itself, proof that an added business restriction was authorized. In particular, D-0014 adds cohort-size/tie handling while the workbook specifies the bottom-80-percent discipline and a publication-based maturity timer; establish source support or resolve the discrepancy explicitly before carrying those interpretations forward. This is a source-fidelity check, not a new commercial gate. Do not certify literal conformance until requirements are traced to implementation and tests/runtime evidence. Material business deviations require the operator's explicit instruction, rather than unilateral implementation judgement.

Continue in `D:\Money Machine`, branch `build/full-automation`, from reviewed HEAD `37206532766d3ba0539902ba8cd434fb67c3d36a`. Preserve the September foundation and recover useful earlier implementation in bounded, session-scoped ports. Do not merge the older integration branch wholesale, restart the programme, or create another orchestration harness.

The delivery target remains the complete playbook workflow and Session 15 acceptance. The first operational milestone is a durable simulation workflow running through API, worker and scheduler and recovering after process restart. That milestone is useful progress, but is not a live business system.

## Recovered state and evidence limits

| Area | Observed state | Meaning |
|---|---|---|
| Canonical control state | Revision 19, Sessions 00–02 complete, next Session 03, no commissioned agents | September work is the current foundation |
| Canonical working tree on entry | Only untracked `CLAUDE.md` | Preserve this user file; no production changes to inherit |
| Previous checkpoint | Session02 implementation checkpoint at `9502b44`, before closure | Stale, superseded by the new metadata checkpoint |
| Recovery checkpoint | `.omx/state/review-resume-20260911.json`, canonical HEAD, one dirty path | Current recovery identity recorded before deeper review |
| Older integration | `integration/first-product-vertical-slice`, HEAD `b60a58c`, 49 commits unique versus 10 canonical commits | Valuable divergent implementation, not canonical state |
| Older dirty work | 44 modified tracked paths and 10 untracked paths, including Session08 service, storage, migration and tests | Protected incomplete work; no cleanup or reset |
| Runtime inventory | Docker server 29.7.2; only `money-machine-postgres-1` running for this project, healthy | No currently running Money Machine API, web, worker or scheduler was observed |
| Worker/scheduler source | Read-only database check followed by exit 78; no claiming implementation | Intentional Session02 boundary, not a switch that can safely be enabled |
| Canonical historical verification | September7 record: 370 Python tests passed, one filesystem-dependent skip; web lint/typecheck/two tests/build; disposable runtime checks | Historical evidence, not a fresh full gate or running service proof |
| Older historical verification | Session07 record: 1,271 tests; live Notion smoke explicitly not run | Reuse candidate evidence only; cannot transfer completion or commissioning |
| CodeRabbit | Four old issues recorded fixed; vendor re-review remains open | Current rate-limit/seat status was not queried; do not repeat the old limit as a fresh observation |

The old integration Git pointer works with WSL-native Git; Windows Git labels WSL worktrees prunable. That is not permission to prune or delete them. September's implementation log already classifies the integration tree as a reference source and other historical worktrees as inactive.

## Review scope

The integrator restored control/governance state, checked Git and Docker state, read the next-session and terminal contracts, and ran targeted verification. Two independent read-only lanes reviewed (1) recent foundation/control/runtime changes and (2) old implementation reuse and contract conflicts. Findings below cite repository version 0.1.0 at the reviewed HEAD. This is a programme-wide readiness review with targeted code inspection, not a claim that every historical line, provider account, production deployment or final acceptance path was re-tested.

### Findings to repair first

1. **P1: readiness accepts an unrelated database revision.** `src/money_machine/api/routers/health.py:52` treats any non-null migration revision as ready; `src/money_machine/persistence/database.py:67` returns the first revision. The existing next-session record explicitly warns that the shared database belongs to another branch. Compare applied migration heads against this checkout's expected heads and reject incompatible or incomplete schema. Test missing, wrong and matching revisions on isolated databases. Do not migrate the shared database as a shortcut.
2. **P1: database URL round trips corrupt valid credentials and IPv6.** `src/money_machine/config/runtime.py:204` retains encoded userinfo and `:157` encodes it again. Independent synthetic probes using Python 3.12.3 and installed Pydantic 2.13.4 converted password `p%40ss` to `p%2540ss`; reconstructing `[::1]` removed brackets and raised a port-parsing `ValueError`. Correct parsing/reassembly and test usernames, passwords, reserved characters, IPv6 and secret redaction. Probe inputs were synthetic, not credentials.
3. **P2: production Compose does not select production configuration.** `compose.prod.yaml:13` provides database environment but no `APP_ENV`; `src/money_machine/config/loader.py:48` defaults to development. Explicitly select production and test the resolved services, including the expected refusal when production authority is absent. This currently fails closed rather than enabling live actions.
4. **Before network exposure: enforce API authentication and bind development access appropriately.** The reviewed API stores an auth-token setting without request enforcement, and development Compose exposes the API without a loopback bind. The reviewed API is read-only. Complete the protection before adding operator mutations or exposing real operational data; final production authentication remains part of deployment acceptance.
5. **During Session03 port: bound event/effect reads.** `EventRepository.for_aggregate()` and `EffectAttemptRepository.unresolved()` are unbounded despite the base repository's pagination contract. Add pagination/batches when the durable runtime consumes these paths.

The review did not modify production code. Findings 1–3 are the first repair wave, not silently accepted residual defects.

Continuation: findings 1–3 were subsequently implemented in the startup repair wave. See [the repair record](2026-09-11-startup-repair.md) for corrected Compose carriers, the independent review findings and final verification. Findings 4–5 remain scoped to the next runtime/API work. The numbered findings above preserve the original review state.

### Why a whole-branch merge is the wrong recovery operation

The two committed trees differ across 464 files (about 102,669 additions and 16,779 deletions). The canonical schema is ORM-mapped with migration root `9f46f3152a68`; the old tree uses Core tables and a `0001`–`0011` migration chain. Its 1,391-line unit of work already couples later research/product services; the canonical unit of work is 81 lines. Old `JobState` and experiment taxonomies differ from canonical `JobStatus` and `ProductLifecycleState`.

The Session03 prompt also names lifecycle states that do not exactly match current enums. The mandatory prompt-integrity addendum must resolve this explicitly with a decision and any required migration. Do not silently rename stored states or copy the old enum over the new schema.

## Reuse inventory

| Session | Recovery source | Port, adapt and prove |
|---|---|---|
| 03 | `7895f76`, then relevant later fixes | Leasing, dependencies, retries, reconciliation, durable scheduling, successors, API/CLI; adapt old concurrency/reaper/retry/scheduler tests to canonical persistence |
| 04 | `6ce46b5` | Agent runtime, registry, prompt store, provider calls and scoped tools; preserve current job/run/prompt lineage and authority |
| 05 | `a01c9e7` | Evidence-bound research, qualification, teardown, spec, dedupe/reconcept and restart behavior; map to canonical entities |
| 06 | `efa442c` | Notion API/browser/fixture routing, connector, receipt/reconciliation and schema-building logic; verify current provider versions and capabilities before live use |
| 07 | `e3ad1ed`, closure `b60a58c` | Six build phases, isolated variants, QA/repair and verified ProductFacts; port phase-restart and product-flow tests |
| 08 | Protected uncommitted integration tree | `session08_asset_service.py`, storage, seven Session08 test modules and associated assets; inspect actual dirty bytes, adapt schema changes and verify before acceptance |

Use each session-era commit before importing later fixes to avoid dragging unimplemented sessions into the current slice. Transfer behavior and adversarial tests, not old controls, commissioning flags, migrations or completion receipts. Sessions09–15 are unclosed work; scaffold presence is not implementation evidence.

## Ordered delivery plan

One integrator owns the canonical checkout, integration and evidence. Each row has a demonstrable output. Session transitions and their exact commits remain sequential even when independent internal slices overlap.

| Order | Scope | Acceptance before advancing |
|---|---|---|
| 0 | Repair the three startup findings above | Focused RED/GREEN tests, affected configuration/API/DB checks, one independent changed-scope review, checkpoint |
| 1 | Session03: durable orchestrator | Start and inspect a persisted fake-handler workflow; dependencies and transactional successors work; concurrent workers cannot claim twice; kill/restart and expired leases recover; uncertain effects reconcile without reissuing; weekly/monthly/maturity timers survive restart; all required Session03 gates and closure |
| 2 | Session04–05: agents and research-to-spec | Scoped typed agent execution with prompt/cost/run evidence; fixture research → shortlist/score → teardown path → spec → dedupe or reconcept automatically; persistence/restart evidence; required session closures |
| 3 | Session06–07: Notion products | Fixture product build through all six phases, QA, three/four isolated variants, fresh-duplicate checks and bounded repairs; verified fact ledger; exact live-capability gaps listed; session closures |
| 4 | Session08: complete listing package | Fact-backed title/eight-part description/13 tags; 10 images, video and delivery PDFs; all links verified, lineage intact and stale assets invalidated; visually inspect exported assets; session closure |
| 5 | Session09: commerce | Adapter creates complete simulated draft; preflight blocks defects; publication caps and idempotency enforced; timeout reconciles before retry; post-publish verification and deactivation work; session closure |
| 6 | Session10–11: business loop and repairs | Weekly metrics persist; no premature demand verdict; mature cull and winner successor paths execute; monthly work scheduled; support issue produces a verified repair; session closures |
| 7 | Session12: operator visibility | NOW/PIPELINE/SHOP/BLOCKED/DECISIONS/INCIDENTS/SETTINGS reflect real persisted state; useful telemetry with sensitive data excluded; no routine handoff queue; session closure |
| 8 | Session13–14: hardening and deployment | Complete happy/cull/multiply/repair/reconcept failure matrix; no active stubs; exact deployment on selected existing host; protected API/console; backup and successful restore; restart and rollback proof; session closures |
| 9 | Session15: real commissioning | Correct accounts, bounded standing authority, first real research → spec → Notion product → assets → Etsy draft/preflight, authorized publication, schedules and restart; required passing evidence before commissioning/release closure; otherwise record the exact external blocker and leave commissioning incomplete |

Run a read-only provider-readiness inventory while recovering Sessions04–07, so missing account identity, credentials or capabilities are discovered before the final stage. Record provider/API version, account/workspace/shop identity, supported operation, permission and last successful check; never expose secret values. Do not infer runtime provider readiness from a desktop connector being installed. Real writes, publication, purchases and messages require the configured authority; gather genuinely missing standing-authority values once when a concrete commissioning run is ready.

Choose deployment from available existing infrastructure in Session14. Local/private commissioning must not wait for a public domain. No new paid environment is presumed.

## Execution discipline that shortens delivery

- Resume from the checkpoint and this plan; do not rediscover the entire repository on every continuation.
- Before executing each immutable session prompt, verify its hash, complete the required three-dimension review and write its corrective addendum. Reuse its routing receipt for that phase. This recovery review does not substitute for the Session03 prompt review.
- Default to one executor. Add at most three independent lanes only when ownership is disjoint. No nested workers, duplicate trees, parallel state machines or replacement harness.
- Keep Level1 slices small: one behavior and its failure case. Integrate once per Level2 wave and review affected boundaries. Freeze after required session reviewers and repairs, then run one final Level3 gate.
- Reuse valid evidence for unchanged bytes. Do not run duplicate full suites; serialize shared database/frontend/runtime work. Fix a concrete cause before retrying; escalate a repeated unchanged failure as a specific blocker.
- Keep old worktrees intact. Use unique disposable databases, never the existing cross-branch application database. Remove only temporary resources created by the current verification.
- At each session exit update the five control files and create the exact required commits. Keep a current metadata checkpoint between exits. Ordinary checkpoints are continuation points, not requests for Omar to type “continue”.
- Report the operating milestone reached, the next critical-path item and exact blocker. Do not use percentages or pass counts as a substitute for demonstrated workflow behavior.

## Next executable wave

1. Reconcile HEAD/dirty set with `.omx/state/review-resume-20260911.json` and the review commit. Keep untracked `CLAUDE.md` untouched.
2. Repair findings 1–3 against the current canonical foundation with failing tests first; run relevant unit/API/isolated-DB regression and review the changed scope.
3. Run Session03 prompt integrity on `prompts/implementation/06_SESSION_03_DURABLE_ORCHESTRATOR.md`; resolve state-taxonomy, current lineage, winner/successor boundary, receipt reconciliation and commissioning differences in its addendum.
4. Add the Session03 control evidence contract and activate through the existing CLI. Port the smallest claim/lease/heartbeat/recovery slice from Session03-era code, then successors and scheduling; do not replace the canonical unit of work or schema wholesale.
5. Keep executing the ordered plan through valid closures. Stop only for a concrete external authority/account dependency or an unresolved failure requiring operator action.

## Terminal truth

Use `prompts/implementation/20_FINAL_ACCEPTANCE_CHECKLIST.md` and the Session15 contract; do not invent another definition of done. The older checklist's private-repository language must be reconciled with the already recorded explicit public-repository authorization rather than changing visibility without authority. No `HANDS_OFF_MONEY_MACHINE_COMMISSIONED` claim until the actual deployed linked workflow supports it.

## Fresh verification and review receipts

- Immutable PDF and workbook: both SHA-256 values match `docs/source/CANONICAL_SOURCE_REGISTER.json` on September11.
- `uv run --frozen ruff check src tests scripts apps`: passed, Ruff 0.16.2.
- `uv run --frozen pyright`: passed, zero errors/warnings/information, Pyright 1.1.411. Its newer-version notice is not a test failure or a reason to change dependencies during recovery.
- Independent foundation review: five findings recorded above; synthetic URL probes reproduced finding2. No production fixes claimed.
- Independent reuse review: session-scoped recovery approved; whole-tree replacement rejected because of demonstrated contract/schema conflicts.
- Independent plan review: one material wording correction applied so an external blocker cannot be used to claim completed commissioning. Reuse, preservation and execution order approved.
- `uv run --frozen pytest tests/bootstrap tests/unit/test_foundation_processes.py tests/unit/test_operations_contract.py -q`: 109 passed, one skipped, 434.58 seconds. The skip is not passing evidence.
- `uv run --frozen pytest tests/integration/test_migrations.py tests/integration/test_concurrency.py tests/integration/test_review_remediation.py -q -rs`: 30 passed, no skips, 346.67 seconds; database-backed checks used the existing disposable-database fixtures.
- No full regression, fresh web build, live provider run or deployment acceptance claimed. Production code remained unchanged during this review.
