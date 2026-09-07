# Session 01 adversarial review — 2026-09-07

**Verdict: NOT CLEAR.** One critical, seven high findings. Session 01 must not be closed or committed until findings 1–8 are remediated.

Scope: working tree at HEAD `0827baa` on `build/full-automation` (uncommitted Session 01 work: 48 modified, 10 new source/test files). Authority: `hands-off-money-machine-full-implementation-workbook.md` sections 6–19 and Session 01 (lines 2013–2257); `docs/control/DECISIONS.md` D-0009–D-0019. Three read-only specialist lanes (domain/state machine; configuration/autonomy; control/orchestration) plus integrator gates. Every finding below was confirmed by the integrator by execution or direct code read.

## Gate baseline (working tree)

| Gate | Result |
|---|---|
| Ruff lint (`src tests scripts apps`) | FAIL — 1 error, `src/money_machine/config/loader.py:3` I001 |
| Ruff lint (`.`, as `scripts/test.sh` runs it) | FAIL — 172 errors, 171 in untracked `.opencode/` |
| Ruff format (`src tests scripts`) | FAIL — 3 files: `orchestration/transition_guard.py`, `tests/bootstrap/test_control_state.py`, `tests/bootstrap/test_prompt_pack.py` |
| Pyright strict | PASS — 0 errors |
| Pytest | PASS — 104 passed |
| `scripts/verify_scaffold.py` | PASS |
| Worker / scheduler entry points | exit 78, no side effects (verified) |
| Web lint/typecheck/test/build | BLOCKED — `pnpm install --frozen-lockfile` failed with EACCES rename on `/mnt/d`; no `apps/` bytes changed since Session 00 green evidence |

## Findings

### 1. CRITICAL — Session activation transition (D-0010) is not implemented
`src/money_machine/control/state.py:17` `SUPPORTED_COMPLETION_SESSION = 0`; `:193` rejects any session other than 0. No `activate` symbol in `state.py` or `cli.py`. `IMPLEMENTATION_STATE.json` still says `current_session: 0`, `session_status: complete` while Session 01 work is in the tree. `tests/bootstrap/test_control_state.py:219-259` hard-asserts `current_session == 0`. A fresh agent resuming from the ledger would conclude no session is in progress. **Fix:** implement `apply_activation_transition` per D-0010 with RED tests (wrong session, double activation, completion without activation), add `activate` to the CLI, generalise completion beyond session 0, then apply activation to the live state.

### 2. HIGH — D-0009 filesystem-identity comparison is recorded but not implemented
`state.py:344` compares `state_path.resolve() != expected_state_path` as strings. From `/mnt/d/money machine`, `resolve()` preserves the lowercase spelling and the comparison fails, though `os.path.samefile` is true. The shipped CLI therefore cannot apply any transition from this worktree, and DECISIONS.md asserts behaviour the code lacks. **Fix:** compare with `os.path.samefile`; add a case-variant alias test.

### 3. HIGH — MULTIPLY successor is not enforced as a new workflow at the state-machine level
`transition_guard.py:105-107` allows `SUCCESSOR_SPEC -> DEDUPE_CHECK` on the same `ProductLifecycleState` sequence with no workflow boundary; `require_product_transition` takes only source/target. The workflow-ID rule lives only in `ProductSpec`/`PortfolioDecision` validators. A literal orchestrator could pull a live winner back into `DEDUPE_CHECK -> BUILDING`. Workbook lines 863–866, D-0017. **Fix:** make `SUCCESSOR_SPEC` terminal for the parent (with a terminal result) and start the successor workflow at its own initial state; test that same-workflow `SUCCESSOR_SPEC -> DEDUPE_CHECK` is rejected.

### 4. HIGH — Section 7 exact invariants are not bound to the typed contracts
`ListingPackage.tags` is `Field(min_length=1)` (`domain/models/listings.py`): 1 tag and 14 tags accepted; no quantity default 999; no image/video role split; `ProductSpec` accepts 1 hub, 20 hubs, 1 variant, duplicate hubs; description is a bare string. `config/product_rules.yaml` holds 13/10/1/6–8/3–4 and tests assert the YAML, but nothing reads the config into the contracts. Workbook lines 607–618. **Fix:** contract validators parameterised by `ProductRulesConfig` (or `validate_against(rules)`), with rejection tests for 12/14 tags, 9 images, 2 hubs, quantity ≠ 999.

### 5. HIGH — `hard_weekly_cap` has no ceiling
`PublishingRampConfig` accepted `hard_weekly_cap: 100` by execution. The playbook cap of fifteen is a current value, not an invariant (workbook 621–622, D-0015). **Fix:** `Literal[15]` or `Field(le=15)` plus a rejection test for 16.

### 6. HIGH — Loader hard-codes `autonomy.example.yaml` as production authority
`config/loader.py:61` loads the example file for every environment. No `autonomy.yaml`, no override, no gitignore entry. `AUTONOMY_MODEL.md:35` says the example is not production authority. **Fix:** load gitignored `autonomy.yaml`, fail closed if absent in PRODUCTION, keep the example as template; test both paths. Related: nothing outside the config package calls `load_config_bundle` or sets `RuntimeEnvironment`, so `apply_environment_safety` protects an environment no process supplies.

### 7. HIGH — Section 13 autonomy contract deviates without a recorded decision
Workbook lines 1010–1022 list 11 keys; `autonomy.example.yaml` has 19. By execution, `mode: live, auto_publish: true` with the workbook key set is REJECTED; live publication additionally needs `external_mutations_enabled: true` and `publishing_ramp.publishing_enabled: true`. Three switches for one standing authority contradicts "configured once" (1041–1043). Not per-listing bureaucracy, but unrecorded. **Fix:** record a DECISIONS entry or collapse the extra flags into `mode`/`auto_publish`.

### 8. HIGH — Governance references scripts that do not exist; Session 01 has no ledger entry
`docs/DEVELOPMENT-GOVERNANCE.md:89,106,152` require `scripts/run_affected_tests.sh`, `scripts/write_resume_checkpoint.py`, `scripts/omx_task_metrics.py`; none exist on this branch (a copy sits in the ignored `.omx/integration/first-product-vertical-slice` worktree). No `IMPLEMENTATION_LOG.md` or `TEST_EVIDENCE.md` entry records any Session 01 work; last entry is 2026-08-08. Eleven Git worktrees exist under `.omx/` against the "no second repository tree" rule (unmerged content UNVERIFIED). **Fix:** commit the scripts or amend governance to "when present"; add an in-progress Session 01 log entry; record each worktree's status.

### 9. MEDIUM — Canonical gate fails and untracked tool directories are unignored
`scripts/test.sh` runs `ruff check .`; `.opencode/` (59 MB), `.claude/`, `.agents/`, `.token-optimizer/`, `opencode.json`, `skills-lock.json`, `CLAUDE.md` are untracked and not ignored (92 paths would stage under `git add -A`). `.claude/settings.local.json` and `.token-optimizer/wiki/evidence.jsonl` need a content check before any commit (not opened). **Fix:** add `.opencode/`, `.agents/`, `.token-optimizer/`, `.claude/settings.local.json`, `opencode.json`, `skills-lock.json` to `.gitignore`; add `extend-exclude` for those paths under `[tool.ruff]`; decide explicitly whether `CLAUDE.md` is tracked; fix the one I001 and three format failures.

### 10. MEDIUM — Workflow graph has unreachable and mode-inconsistent jobs
`CullDecisionJob` and `ScaleEvaluationJob` are neither entry jobs nor successors. `ProvisioningCheckJob` (entry) is `allowed_modes: [live]` so simulation can only enter the lifecycle via the weekly-review chain. `ProofDistributionJob` (`workflows.yaml:275-277`) allows `EXTERNAL_MESSAGE` in `draft`, contradicting `AUTONOMY_MODEL.md:10`. `LinkVerificationJob` and `NotionRepairJob` are named in `STATE_MACHINE.md`/`AGENT_ROSTER.md` but have no owner in `workflows.yaml`. No validator checks reachability or side-effect/mode consistency. **Fix:** reachability and effect-mode validators; wire or delete the orphans.

### 11. MEDIUM — Undocumented deviations from workbook Section 10
Extra state `REJECTED` and edges `QUALIFYING -> REJECTED`, `VARIANT_QA -> VARIANT_BUILD`, `ASSET_QA -> ASSET_BUILD`, `SUCCESSOR_SPEC -> OBSERVING` are sensible but not in workbook lines 788–829 and not in DECISIONS.md. `OBSERVING -> {MATURE}` only: no lifecycle edge for defects during observation (D-0014 "defects bypass maturity" is job-level only). **Fix:** one DECISIONS entry covering these; test that an open incident blocks `MATURE -> EVALUATING` or add the edge.

### 12. MEDIUM — Test rigour gaps
`test_impossible_product_transitions_fail_closed` samples 4 of 34×33 pairs; terminal-result test is a literal dict comparison, not derived. `test_configuration.py` has no negative cases (negative caps, unknown keys, `auto_publish` in simulation, `COMMISSIONED` without evidence). `test_foundation_processes.py` calls `worker_main()` in-process with a stub; no subprocess proves exit 78. `COMMISSIONED` evidence is an unchecked free string. **Fix:** exhaustive pair iteration; parametrised rejection tests; one subprocess test per entry point.

### 13. LOW
Quantity 999, launch-price/sale, digital delivery absent from config; `telemetry.yaml` untyped and unloaded; `DedupeResult.differentiation_evidence` required even for `TOO_CLOSE`; `title_similarity_threshold` unconstrained in results; `MetricsSnapshot.reconciled=False` accepted by decisions; frozen models unhashable (`input: dict`); AUTONOMY_MODEL.md lists six stop reasons vs the workbook's five; INTEGRATION_MATRIX `DIRECT_API` selections cite no vendor primary source (UNVERIFIED); `TEST_EVIDENCE.md:151-153` still marks CodeRabbit issues OPEN though all four are fixed in code.

## Verified correct
- All 25 Section 10 states and every workbook edge present in `PRODUCT_TRANSITIONS`; `PASS/FAIL/TOO_CLOSE` are outcomes not states; CULL reaches `DEACTIVATING -> DEACTIVATED`; invalid edges raise `InvalidTransitionError`.
- All 31 required events present with exact spelling (plus 16 additive); all 55 uppercase vocabulary terms in the chapter map exist in code enums; all 39 job types exist in `workflows.yaml` with an owning agent (none in Python source; job_type is a string per Section 9).
- `JobEnvelope` has all 15 Section 9 fields; `AgentResult` all 7; terminal agent statuses exactly `SUCCESS/FAILURE/BLOCKED/UNCERTAIN_EXTERNAL_EFFECT`; `owner_agent_id` admits exactly A01–A16.
- All 15 required Pydantic contracts exist and honour D-0018 by execution (extra forbid, strict, frozen, schema_version 1, UUIDs, UTC normalisation).
- 16 agents in `agents.yaml` with stable IDs, none `COMMISSIONED`; A13 side effects `EXTERNAL_WRITE, EXTERNAL_SPEND`.
- Playbook defaults 25–40, 5, 30/40, 1+1, 6–8, 3–4, 13, 10+1, 2–3/week, 15, 30 days, 80%, monthly, 1/batch present in YAML, typed, and tested against the real files.
- `yaml.safe_load` only; PyYAML is a direct dependency (D-0019); unknown keys, invalid enums, min>max rejected; nothing defaults to live or spend > 0; tests never enter draft/live.
- All six required Mermaid diagrams present; all seven ADRs have decision/rationale/consequences/rejected/revisit sections.
- CodeRabbit's four Session 00 issues are fixed in `control/state.py` and tested (re-review by CodeRabbit not obtained).
- Atomic state persistence (mkstemp + fsync + replace + dir fsync) with an exclusive lock around validate and write.

## Remediation status — 2026-09-07 (same day, findings 1 to 8)

| Finding | Status | Evidence |
|---|---|---|
| 1 Activation transition | fixed and applied | `apply_activation_transition`, `money-machine-control activate`; live state revision 12, Session 01 incomplete; `SESSION_EVIDENCE_KEYS` pins each session's evidence contract; activation rejection tests for wrong session, double activation, claimed evidence, wrong key set, pointer rewrites |
| 2 Filesystem identity | fixed | `same_file` on the canonical directory entry; hard-link alias rejected; case-variant test skips on case-sensitive filesystems; the live activation from the lowercase root is the positive proof |
| 3 MULTIPLY boundary | fixed | `SUCCESSOR_SPEC -> {OBSERVING}` only; `require_successor_spawn`; exhaustive pair tests. Follow-up: the Session 03 orchestrator must call `require_successor_spawn` on the spawn path |
| 4 Contract binding | fixed | `ListingRules`/`ProductShapeRules` required by `ListingPackage`/`ProductSpec`, produced by `ProductRulesConfig.listing_rules()` and `product_shape_rules()`; rejection tests for 12/14 tags, 9 images, 0 or 2 videos, 7 sections, quantity 998/1000, anchor below price, 2/9 hubs, 1/5 variants. Follow-up (LOW): `rule_version` is free text; consider a rule hash |
| 5 Hard cap | fixed | `PLAYBOOK_MACHINE_WEEKLY_CAP = 15`; `WeeklyCap` bounds `hard_weekly_cap` and `weekly_listing_cap`; 16 and 100 rejected |
| 6 Autonomy loader | fixed | `config/autonomy.yaml` (git-ignored) required in production; example refused; symlink or same-inode alias refused; `APP_ENV` resolution with development default |
| 7 Autonomy deviation | recorded | D-0020 |
| 8 Governance scripts, ledger, worktrees | fixed | `scripts/write_resume_checkpoint.py` and `scripts/omx_task_metrics.py` on branch; IMPLEMENTATION_LOG Session 01 entry with worktree register; resume checkpoint written |

An independent re-review of the remediation diff raised one HIGH (per-session evidence contract not pinned in code) and five MEDIUM/LOW items (shape-test contradiction, chapter-map row 16.3, loader symlink bypass, stale `completion_requires_next_session`, empty `APP_ENV`). All were remediated in the same pass except two recorded follow-ups: orchestrator wiring of `require_successor_spawn` (Session 03) and a `rule_version` integrity hash. Findings 9 to 13 of the original review remain open.

## Remediation status — findings 9 to 13 (same day)

| Finding | Status | Evidence |
|---|---|---|
| 9 Canonical gate and untracked tool directories | fixed | `.gitignore` ignores `.opencode/`, `.agents/`, `.token-optimizer/`, `.claude/settings.local.json`, `opencode.json`, `skills-lock.json`, `config/autonomy.yaml`; Ruff `extend-exclude` covers the tool directories and Markdown; `bash scripts/test.sh` exits 0 end to end including Compose configuration. `CLAUDE.md` is deliberately left untracked and unignored for the operator to decide |
| 10 Workflow graph | fixed | Reachability validator and draft-forbids-spend/message rule in `settings.py` (D-0023); `CullDecisionJob` removed; `ScaleEvaluationJob` reachable via `MonthlyDeepPassJob` from the schedule entry; `LinkVerificationJob` (A09) and `NotionRepairJob` (A07) close the broken-link loop; provisioning writes admit simulation; `ProofDistributionJob` is simulation/live only; tests reject an orphan job and draft spend |
| 11 Undocumented state-machine deviations | recorded | D-0021 (with D-0014 for incidents being job level) |
| 12 Test rigour | fixed | Exhaustive product and job pair tests (earlier pass); parametrised autonomy rejections; real subprocess tests prove worker and scheduler exit 78 with empty stdout; `COMMISSIONED` evidence must be a URI or `docs/`/`tests/`/`scripts/` path |
| 13 LOW items | fixed or recorded | Quantity 999, digital delivery, anchor price in config and contracts (earlier pass); launch-sale configuration deferred to Session 08 merchandising; `telemetry.yaml` typed by `TelemetryConfig` against the 23-member `TelemetryEventName` taxonomy and loaded in the bundle; `DedupeResult` carries `rule_version` and `compared_spec_ids`, forbids differentiation claims on `TOO_CLOSE`, and requires them on a `PASS` against a non-empty catalogue; six stop reasons recorded in D-0020; `INTEGRATION_MATRIX.md` marks vendor capability UNVERIFIED; `TEST_EVIDENCE.md` records the CodeRabbit disposition and pending vendor re-review. Deferred with reasons: `MetricsSnapshot.reconciled` enforcement belongs to the Session 02 decision layer; frozen-model hashability is not required by any contract |

An independent re-review of the findings 9–13 diff raised one HIGH (an unreproduced Ruff 0.16.2 panic during the root-scope format walk in `scripts/test.sh`) and three MEDIUM items (chapter-map allowed-mode drift, `REPAIR_COMPLETED` emitted by repair jobs before verification, path traversal accepted by the commissioning-evidence pattern) plus LOW items. All were remediated: the gate runs Ruff on explicit paths and the panic is recorded in `TEST_EVIDENCE.md` with its receipt (D-0024); repair jobs now emit `REPAIR_APPLIED` and only verifiers emit `REPAIR_COMPLETED` (D-0024); the chapter map and prompt map rows were corrected and a test now asserts single-job rows agree with `workflows.yaml` on side effect and allowed modes; `..` segments are rejected; `.claude/` is ignored and the `.gitignore` comment states the `CLAUDE.md` position truthfully; `TITLE_SIMILARITY` collisions must meet the configured threshold; `MilestoneProjectionJob` was removed from the workbook data map. Root cause of the Ruff panic remains UNVERIFIED.
