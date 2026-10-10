# Decisions

## D-0001 — Canonical naming authority

**Status:** accepted for Session 00 bootstrap.

The embedded workbook prompt names `D:\hands-off-money-machine`, `/mnt/d/hands-off-money-machine`, a private remote `hands-off-money-machine`, and commit `chore(bootstrap): create hands-off money machine monorepo`. The later, current PRD/test specification intentionally supersedes those engineering names with:

- canonical roots `D:\Money Machine` and `/mnt/d/Money Machine`;
- remote name exactly `money-machine`;
- bootstrap commit exactly `chore(bootstrap): initialise money machine autonomous monorepo`;
- a distinct evidence-closure commit that contains the still-incomplete pre-transition state;
- a later state-pointer commit that contains the completed state but does not attempt to record its
  own object ID inside that state file.

The PDF remains authoritative for business rules. The current PRD/spec is authoritative for repository/path/remote/commit engineering contracts. The contradiction is recorded rather than silently normalized. No remote currently exists, so no public or incorrectly named remote was created.

## D-0002 — Source preservation and redistribution

Both original root sources remain byte-identical and in place. The PDF is strict-deny Git content. Committed derived maps use short paraphrases and page references rather than reproducing source text. The implementation prompt files are byte-extracted only from explicit workbook COPY markers; embedded plugin labels are inert text.

## D-0003 — Session state is fail-closed

Session 00 remains `incomplete` until every required evidence flag is true, both distinct commit SHAs are recorded, the implementation and adversarial reviews pass, `completed_sessions` includes 0, and `next_session` becomes 1. A focused green slice cannot perform that transition.

`evidence_closure_commit_sha` and `head_sha` identify the real commit at repository `HEAD` immediately
before the atomic completion transition. The bootstrap SHA must resolve to the exact bootstrap
commit and be its ancestor. Once the tool writes the completed state, a separate state-pointer
commit checkpoints that write; the state file never claims that later commit's SHA.

## D-0004 — Source identity versus runtime receipts

The committed source record is the path-relative `docs/source/CANONICAL_SOURCE_REGISTER.json` plus its copyright-safe Markdown summary and coverage map. Detailed rename/preservation receipts contain machine-local observations and remain ignored runtime evidence under `.omx/`. Canonical verification reads the private PDF when present; clean clones may omit only that ignored file and must explicitly select the missing-private-source verification mode.

## D-0005 — Runtime directory markers are not runtime evidence

The canonical scaffold requires the `runtime/` directory tree to exist, but runtime data must never be committed. The repository therefore tracks only scoped, empty `.gitkeep` markers under `runtime/artifacts`, `runtime/browser-profiles`, `runtime/receipts`, `runtime/screenshots`, and `runtime/temp`; all other content below those directories remains denied. These inert markers preserve the single canonical scaffold without weakening the strict-deny rule for generated evidence, browser state, receipts, or payloads.

## D-0006 — Completion candidates cannot manufacture closure evidence

The evidence-closure commit must contain the exact live incomplete state that existed before the completion command. Every non-Git evidence fact and all continuity fields are locked before that commit; the completion candidate may only perform the declared Session 00 transition, record the distinct closure SHA, flip the closure-recorded flag, remove exactly the Session 00 outer-gates blocker, advance the timestamp/revision/session pointer, and preserve unrelated blockers such as the push-only remote blocker. This prevents reviews, tests, service results, or other completion facts from being fabricated after closure.

## D-0007 — Local session completion is distinct from remote publication

The current PRD/test specification permits Session 00 to complete locally when its repository, runtime, review, and Git-evidence gates pass. A missing remote blocks only authenticated private push; it does not invalidate the real local bootstrap, evidence-closure, or state-pointer commits. Accordingly, Session 00 advances to Session 01 while retaining `REMOTE_NOT_CONFIGURED` with scope exactly `push only`. No remote is guessed or created, and no publication authority is inferred.

## D-0008 — Explicit operator authorization for a public remote

After Session 00 closed, the operator explicitly instructed that the GitHub repository be created and kept public. That instruction supersedes D-0001/D-0007's earlier private-remote assumption for `OmarA1-Bakri/money-machine` only. The repository therefore uses public visibility and default branch `build/full-automation`; this does not authorize publishing products, customer/provider data, credentials, runtime evidence, the source PDF, or any live commercial effect. Strict-deny tracking rules remain unchanged.

## D-0009 — Repository identity preserves canonical spelling but verifies filesystem identity

**Status:** accepted for Session 01.

`/mnt/d/Money Machine` remains the persisted display name. On the current Windows-backed filesystem, `/mnt/d/Money Machine` and `/mnt/d/money machine` identify the same directory even though `Path.resolve()` preserves the caller's spelling. Control validation therefore derives the operational root from the canonical state-file location, proves that it is the Git worktree root, and uses filesystem identity to compare the recorded root. It does not lowercase stored paths, admit a second tree, or accept a state file outside `docs/control/IMPLEMENTATION_STATE.json`.

## D-0010 — Session continuity uses explicit activation and completion transitions

**Status:** accepted for Session 01; control implementation required before Session 01 closure.

`current_session` identifies the active or most recently completed session. Starting the recorded `next_session` is an atomic activation transition: preserve `completed_sessions`, set `current_session` to `next_session`, set `session_status` to `incomplete`, and retain the same next-session pointer until completion. Completion is a second atomic transition that appends the active session exactly once, records independently verified closure evidence, marks it complete, and advances `next_session` and `next_prompt`. `head_sha` records the pre-transition evidence-closure commit, not the later state-pointer commit, so no state document claims its own object ID. Each session defines its own evidence keys; Session 00's hard-coded evidence contract must not be reused as a universal schema.

## D-0011 — Required Session 01 contracts are the canonical top-level result vocabulary

**Status:** accepted for Session 01.

The prompt-required names are canonical API contracts. Source-map names remain traceability labels or nested records:

- `DedupeVerdict` is represented by `DedupeResult`;
- `ProductArtifact` and its checkpoints are represented by `BuildResult` plus artifact references;
- `QAReport` is represented by `ProductQAResult`;
- `PreflightReport` is represented by `PreflightResult`;
- `WeeklyMetricSnapshot` is represented by `MetricsSnapshot`;
- `ReviewVerdict`, `BuildSlotDecision`, and `ScaleDecision` are represented by `PortfolioDecision` with a typed decision and evidence;
- listing copy, drafts, delivery files, and media are inputs or members of `ListingPackage`, not competing package types.

`CandidateShortlist`, `QualificationScore`, `NicheDecision`, `PriceDecision`, and `BuyerChainReceipt` remain distinct supporting domain records. Aliases must not become parallel models with drifting fields.

## D-0012 — Workflow states, outcomes, events, and telemetry are separate taxonomies

**Status:** accepted for Session 01.

Product lifecycle state, durable job state, agent-run status, branch outcome, portfolio decision, side-effect class, retry class, incident type, capability channel, and autonomy mode are separate enums. `PASS`, `FAIL`, and `TOO_CLOSE` are results that select transitions; they are not lifecycle states. Uppercase durable domain events drive transactional workflow. Lowercase PostHog events observe execution and may map to domain events, but telemetry is never workflow authority or commerce evidence.

## D-0013 — Dedupe combines exact concept identity with configured title similarity

**Status:** accepted for Session 01.

A matching normalized identity and base category always fails. Otherwise titles are Unicode-normalized, case-folded, stripped of punctuation, whitespace-collapsed, tokenized, and compared with a configured Jaccard threshold of `0.70`. A materially matching concept fingerprint also fails even when title wording changes. Differentiation evidence must identify a real change in identity, category, buyer problem, structure, or feature set; wording alone is not differentiation. Every failure emits cited evidence and creates `ReconceptProductJob`. The metric and threshold are revisited only with recorded collision evidence, never weakened ad hoc to pass a product.

## D-0014 — Maturity and bottom-80-percent culling are evidence-gated

**Status:** accepted for Session 01.

Maturity requires at least thirty accumulated live 24-hour periods from the verified UTC publication time; paused or deactivated time does not count. Defects bypass maturity and create repair work immediately. The bottom-80-percent setting defines an eligibility pool within a configured shop/cohort and evaluation window; it does not command automatic deletion of 80 percent of listings. Cohorts smaller than five do not produce percentile cull eligibility, and ties at the cutoff remain out of the cull pool. A durable `CULL` decision still requires its metrics evidence and creates a separately authorized, reconcilable deactivation job.

## D-0015 — Playbook ranges remain ranges and batches are durable work groups

**Status:** accepted for Session 01.

The `25–40`, `6–8`, `3–4`, and `2–3` source values are stored as minimum/maximum contracts rather than collapsed into hidden constants. Insufficient research evidence blocks the affected decision instead of fabricating rows. The initial publication target is two listings per week and may grow within configuration to the hard cap of fifteen. A batch is a durable build-slot group with a stable batch ID. Each non-empty batch schedules one genuinely new-front experiment when an eligible experiment exists; a blocked experiment remains queued for the next batch rather than being silently counted as delivered. Exact source values such as five candidates, `30/40`, thirteen tags, ten images, and one video remain exact.

## D-0016 — Capability channel, availability, and operating authority are independent

**Status:** accepted for Session 01.

`DIRECT_API`, `COMPOSIO`, `BROWSER`, `INTERNAL_RENDERER`, and `MANUAL_EXTERNAL_BLOCKER` describe the selected capability channel for an operation. They do not encode adapter implementation, fixture use, `simulation`/`draft`/`live` autonomy, current credential availability, or standing authority. The capability assessment may record configured/not configured, safely probed/not safely probed, available/blocked/unknown, reconciliation need, and exact operator action. It must not inspect or commit credentials, tokens, cookies, browser contents, private-source text, customer/provider payloads, or foreign-agent configuration. Current safe configuration establishes only simulation/disabled availability; unknown live capabilities fail closed.

## D-0017 — `MULTIPLY` creates a new dedupe-gated lineage

**Status:** accepted for Session 01.

`MULTIPLY` creates a new workflow ID and ProductSpec identity/version with explicit parent product, parent decision, and source-evidence lineage. The successor begins at the dedupe gate before build. It never rewrites the mature winner's workflow, ProductSpec, product, or listing lineage.

## D-0018 — Pydantic contracts are strict, immutable, versioned, and UTC-aware

**Status:** accepted for Session 01.

Session 01 contracts use Pydantic v2 with `extra="forbid"`, strict scalar validation, frozen models, `schema_version: Literal[1]`, UUID identifiers, and timezone-aware datetimes normalized to UTC. Agent errors are structured records, not replacement prose. Common envelopes use JSON-compatible payload values; workflow-specific result models carry concrete typed fields. Additive compatible evolution increments model fields without silently accepting unknown input; incompatible changes require a new schema version and explicit adapter.

## D-0019 — YAML is an application contract with an owned parser

**Status:** accepted for Session 01.

The five Session 01 YAML files are application authority, not comments. Python validation uses a directly declared YAML parser and Pydantic-backed configuration models; it must not rely on a transitive lockfile dependency. Unknown keys, invalid enum values, contradictory ranges, and live effects in test configuration fail closed. Tests and development remain simulation-only regardless of machine credentials.

## D-0020 — Standing authority carries explicit enablement switches beyond the workbook's eleven keys

**Status:** accepted for Session 01 (records the deviation found by the 2026-09-07 adversarial review).

Workbook section 13 lists eleven autonomy keys. `config/autonomy.example.yaml` and `AutonomyConfig` add `version`, `currency`, `external_mutations_enabled`, `external_spend_enabled`, `external_message_enabled`, `message_monthly_cap`, `authorized_recipient_scopes`, and `recipient_consent_evidence_required`. Consequence: live publication requires `mode: live`, `external_mutations_enabled: true`, `auto_publish: true`, and `publishing_ramp.publishing_enabled: true`. This is deliberate and still "configured once": `mode` selects channel semantics, `external_mutations_enabled` and `external_spend_enabled` are operator kill switches that halt all provider writes or spend without editing per-operation flags, and `publishing_enabled` gates the ramp independently of the standing authority file. Messaging is separated because the workbook's section 13 has no message cap while section 7 requires customer response, so message authority needs its own cap and consented recipient scopes. None of these switches is a per-listing approval, and none may be added as a routine approval gate. The operator file is `config/autonomy.yaml` (git-ignored); the tracked example is a template and production refuses to load it. The human-intervention boundary lists six stop reasons where the workbook lists five: "missing recipient consent/authority" is added because message authority is gated on consented recipient scopes; it is a fail-closed stop, not an approval gate.

## D-0021 — Recorded deviations from workbook section 10 in the executable state machine

**Status:** accepted for Session 01.

The executable table adds one state and four edges that section 10 does not draw: `QUALIFYING -> REJECTED` (a terminal result for a candidate below the 30/40 threshold, otherwise a rejected candidate has no lifecycle end); `VARIANT_QA -> VARIANT_BUILD` and `ASSET_QA -> ASSET_BUILD` (repair loops symmetrical with `BUILD_QA -> BUILD_REPAIR` and `PREFLIGHT -> LISTING_REPAIR`); and `SUCCESSOR_SPEC -> OBSERVING` (the mature winner keeps selling after a `MULTIPLY` decision). The workbook edge `SUCCESSOR_SPEC -> DEDUPE_CHECK -> new product workflow` is a workflow boundary, not a same-workflow transition: `require_successor_spawn` authorizes a successor with a distinct `workflow_id` to enter at `DEDUPE_CHECK`, and the same-workflow edge is rejected so a live winner can never be pulled back into build (D-0017). Defects during `OBSERVING` are incident and job level and do not add lifecycle edges; the maturity clock is evidence-gated per D-0014.

## D-0022 — Playbook shape rules are bound into contracts, not only into configuration

**Status:** accepted for Session 01.

`ListingPackage` requires a `ListingRules` value and `ProductSpec` requires a `ProductShapeRules` value; both are produced from `config/product_rules.yaml` through `ProductRulesConfig.listing_rules()` and `product_shape_rules()`. A package with other than the configured thirteen tags, ten images, one video, eight description sections, quantity 999, or an anchor below the price cannot be constructed; a spec outside six to eight unique hubs or three to four unique colour variants cannot be constructed. The rule version travels with the artifact for lineage. Numbers stay in configuration; the binding is what makes them invariants. The hard weekly cap of fifteen is the one typed constant, because the playbook treats it as the machine limit rather than a tunable.

## D-0023 — Workflow graphs are validated for reachability and effect-mode consistency

**Status:** accepted for Session 01.

Every job in a workflow must be reachable from an entry job, and jobs with `EXTERNAL_SPEND` or `EXTERNAL_MESSAGE` effects may not admit `draft` mode. `CullDecisionJob` was removed as a duplicate of `PortfolioDecisionJob`'s `CULL` branch. `ScaleEvaluationJob` hangs from `MonthlyDeepPassJob`, which the `ScheduleConfigurationJob` entry now schedules alongside `WeeklyReviewJob`. `LinkVerificationJob` (A09, read-only) and `NotionRepairJob` (A07) complete the broken-link repair loop drawn in `STATE_MACHINE.md`. Provisioning writes admit `simulation` so the lifecycle is exercisable end to end without live authority. `config/telemetry.yaml` is typed by `TelemetryConfig` against the `TelemetryEventName` taxonomy and loaded in the bundle; it remains disabled. Commissioning evidence must be a URI or repository-relative `docs/`, `tests/`, or `scripts/` path. A `DedupeResult` records its rule version and the compared catalogue; `TOO_CLOSE` cannot claim differentiation and a `PASS` against a non-empty catalogue must cite it.

## D-0024 — Repair jobs emit `REPAIR_APPLIED`; only the verifier emits `REPAIR_COMPLETED`

**Status:** accepted for Session 01.

`BuildRepairJob`, `ListingRepairJob`, and `NotionRepairJob` persist an effect receipt and emit `REPAIR_APPLIED`. The verifying successor (`ProductQAJob`, `PreflightJob`, or `LinkVerificationJob`) emits `REPAIR_COMPLETED` only after a fresh verification passes, and that event closes the incident. A repair is therefore never recorded complete on the repairing agent's own word. The canonical `scripts/test.sh` and `scripts/test.ps1` gates run Ruff against explicit `src`, `tests`, `scripts`, and `apps` paths rather than the repository root after an observed, unreproduced Ruff 0.16.2 panic during a root-scope format walk (receipt: `.omx/evidence/session-01/ruff-format-panic-2026-09-07.log`, ignored runtime evidence); the root cause is UNVERIFIED and the change removes the non-deterministic directory walk from the gate.

## D-0025 — Agent results carry the lineage chain and reconcilable effect references

**Status:** accepted for Session 01.

`AgentResult` carries `agent_run_id`, `agent_id`, `agent_definition_version`, `prompt_reference`, and `prompt_sha256`, so the workbook lineage chain (product, spec version, producing job, agent run, prompt version, source inputs, artifact hash, QA result, listing version) has a typed carrier at every link before Session 02 designs the schema. Every artifact a result returns must cite that run and job. `EffectReference` records one attempted external effect by idempotency key with `effect_state` of `CONFIRMED`, `ABSENT`, or `UNKNOWN`; a result with status `UNCERTAIN_EXTERNAL_EFFECT` must cite the unresolved effect, and `JOB_AND_EVENT_CONTRACTS.md` defines reconciliation as an adapter read that never repeats the mutation, with per-job idempotency key templates. `ProductQAResult` names the artifact IDs it checked and `PreflightResult` pins the listing package hash, so a QA verdict cannot silently cover a later artifact version.

`NOTION_LINK_PUBLISH` and `NOTION_WORKSPACE_PROVISION` were corrected to `BROWSER` and `MANUAL_EXTERNAL_BLOCKER`: publishing a page to the web with secret-link collection is an interface operation, and workspace creation is holder-only. `INTEGRATION_MATRIX.md` now names the `capability_operation` code on every row and a test asserts the codes and channels match the configuration, which is what makes the Session 01 exit criterion on integration strategy checkable rather than prose.

## D-0026 — Every session prompt is adversarially reviewed and corrected before it is executed

**Status:** accepted; effective from Session 02 onward.

A session prompt states what to build. It is not evidence that its own instructions are correct, current, safe, or achievable here. The Session 02 prompt was verified byte-identical to the workbook and was still defective: executed literally it would have removed the fail-closed worker and scheduler boundary before the durable orchestrator existed, dropped every Session 01 lineage field at the schema boundary with no table for a QA, preflight, or dedupe result, seeded a second source of truth for standing authority, seeded a commissioning state that does not exist in the code, and left an integration-status surface that invites credential reads and live provider calls. Its exit criteria were satisfiable by stubs, and one was arguably already true with no work.

Every session therefore runs the prompt-integrity review and corrective exercise in `docs/PROMPT_INTEGRITY_REVIEW.md` before its own first action, and records the result under `docs/control/reviews/`. The corrective addendum governs execution; the prompt remains the unamended source of record.

The instruction lives in a governance document rather than inside the prompts because `prompts/implementation/*` are deterministically extracted from the workbook between copy markers and each file's SHA-256 is asserted against the workbook appendix, while the workbook and the playbook PDF are immutable root sources preserved byte-for-byte. Editing a prompt to carry its own review instruction would break extraction, fail the prompt-pack verification, and corrupt the source register. `AGENTS.md`, `CLAUDE.md`, and `docs/DEVELOPMENT-GOVERNANCE.md` section 0 carry the standing rule, and `tests/bootstrap/test_prompt_integrity.py` enforces that the record exists for the active session and every session completed under this rule. Amendments may only make a prompt more exact, safer, or more verifiable; reducing scope or relaxing a business rule or safety boundary remains the operator's decision.

## D-0027 — Structural integrity is enforced by the database, not by application convention

**Status:** accepted for Session 02, after two independent closure reviews returned NOT CLEAR.

The reviews demonstrated, with probes, that several documented guarantees were unenforced. Each is now a database rule:

- **Evidence has a home.** Thirteen Session 01 contracts require at least one evidence citation and nothing persisted them. `evidence_references` stores a citation with a constrained polymorphic owner, so a result row's evidence survives.
- **Optimistic locking is real.** `update_versioned` compared an in-memory value and issued an unqualified UPDATE, so a lost update was reproducible. The versioned mapper now sets `version_id_col`, the emitted UPDATE carries the version predicate, and a losing writer raises.
- **Lineage is foreign-keyed.** `product_specs`, `products` and `listing_versions` name their producing job and agent run; specifications name their research run and teardown report; listing versions name their QA verdict; `listing_version_artifacts` relates media and delivery artifacts.
- **A verdict cannot cite what does not exist.** The JSON identifier lists on QA and dedupe results became `qa_result_artifacts` and `dedupe_comparisons` relations with foreign keys.
- **A lineage record cannot lie.** Composite foreign keys bind `agent_runs` to its agent definition version and to its prompt version, reference and hash, and bind `preflight_results` to the exact listing-package hash it pinned.
- **Three-valued logic cannot bypass a rule.** The decision successor checks wrap their predicate in `coalesce`, so a NULL decision no longer satisfies them.
- **Append-only means append-only.** `events` and `receipts` carry a `BEFORE UPDATE OR DELETE` trigger that raises. Alembic does not autogenerate triggers, so the revision installs them explicitly and a test asserts they exist in the migrated database.
- **Taxonomies agree with the contracts.** Incident, dedupe and QA vocabularies were reconciled with `IncidentResult`, `DedupeResult` and `ProductQAResult`, and a test asserts every contract value is admitted by its table.
- Also: a `RECONCEPT` specification must cite its parent, a listing version's specification must belong to its product, structured errors must carry a code and message, artifact sizes use a 64-bit integer, currency codes are checked against ISO 4217, and `alembic check` now surfaces a table that is no longer declared rather than ignoring it.

The seed became convergent as well as idempotent: a row that has drifted from the YAML authority is restored, a renamed prompt file has its reference repaired, and concurrent seeding succeeds on every process because inserts use `ON CONFLICT DO NOTHING`.

On the operations side: the container health probe uses liveness, because a readiness probe would keep a fresh unmigrated stack permanently unhealthy while readiness remains the operator signal; credential-bearing URL query parameters are stripped into the secret rather than surviving into logs and responses; continuous integration runs on this branch, checks migration reversibility, and asserts the second seed run changes nothing; a build-ignore file keeps the private source, environment files and operator authority out of the build context; and production builds from the maintained image definitions.

## D-0028 — Exit 78 lift with commissioning evidence gates (Wave 9)

**Status:** accepted for Session 04 Wave 9 (SERIAL), 2026-09-20.

### Context

Exit 78 (`EXIT_UNAVAILABLE = 78`) is the fail-closed boundary that prevents worker and scheduler processes from claiming and executing production jobs. Session 02 implemented the database foundation, Session 03 delivered orchestration library functions (leases, dependency resolution, event dispatch, successor creation), and Session 04 delivered the agent runtime (provider abstraction, prompt store, agent registry, runner, tool permissions, observability). Lane C (completed at `744cc36b`) proved the library integration path: lease → execute → persist → event → successor with deterministic fake providers and TESTED agent state only.

Worker and scheduler entrypoints have remained fail-closed since Session 02:
- `worker.main()` → `uncommissioned_process("worker")` → `EXIT_UNAVAILABLE`
- `scheduler.main()` → `uncommissioned_process("scheduler")` → `EXIT_UNAVAILABLE`

Both processes prove database connectivity and log the result, then exit 78 without claiming any job. This was the contract from Session 02's corrective addendum point 1 and Session 03's addendum point 4.

Wave 9 lifts Exit 78 conditionally: worker and scheduler will claim and execute jobs ONLY when commissioning evidence gates pass for the target agent. Uncommissioned agents (state = `DESIGNED`) remain fail-closed and refuse execution.

### Commissioning evidence requirements

An agent may be claimed and executed on the production worker path if and only if:

1. **Agent definition loaded:** Agent row exists in the `agents` table with `commissioning_state` set to `TESTED` or `COMMISSIONED`.
2. **Contract tests pass:** All eight contract tests for that agent pass (prompt exists, schema imports, config validates, tools resolve, side-effect class declared, fake provider produces valid result, malformed output fails closed, uncommissioned agent refuses production).
3. **Runtime integration tests pass:** The lease → execute → persist → event → successor flow completes successfully for that agent with deterministic fake provider, real lease acquisition (`FOR UPDATE SKIP LOCKED`), real database transactions, and real event emission.
4. **Prompt integrity proven:** Agent's prompt file exists at the declared `prompt_path`, SHA-256 matches the stored hash in `prompt_versions` table, required sections are present, and no runtime secrets are embedded.
5. **Tool permissions enforced:** `AgentRunner` enforces the agent's `allowed_tools` allowlist at runtime; disallowed tool calls raise `ToolPermissionError` and fail the job.

Session 04 Wave 8 delivered contract tests for all sixteen agents (A01–A16) proving items 2–5 above for the implemented agents (A01, A02) and item 2 partial evidence for the remaining DESIGNED agents. Lane C delivered runtime integration tests proving item 3 for the library path.

Wave 9 connects the production claim path: worker process claims READY jobs, invokes `AgentRunner.execute()`, persists `AgentResult`, emits events, and spawns successor jobs. The worker checks agent commissioning state before execution; if `commissioning_state = DESIGNED`, the worker refuses execution and fails the job with `AgentNotCommissionedError`.

### Exit 78 lift conditions

Worker and scheduler entrypoints lift Exit 78 when ALL of:

- Session 04 contract tests pass (all 135+ tests including A01–A16 roster contracts)
- Lane C runtime integration tests pass (lease → execute → persist → event → successor)
- Wave 9 runtime integration tests pass (concurrent claim, idempotency, commissioning gates)
- At least one agent (A01 or A02) is in state `TESTED` with all five commissioning evidence items satisfied

If any of these conditions fail, worker and scheduler continue to exit 78.

### Controlled rollout path

1. **Wave 9 initial:** Lift Exit 78 conditionally. Worker claims jobs ONLY for agents in state `TESTED` or `COMMISSIONED`. A01 Shop Orchestrator and A02 Account & Integration diagnostics are the only agents eligible. All other agents (A03–A16) remain at `DESIGNED` and refuse execution.
2. **Post-Wave 9:** Operator reviews A01/A02 execution logs, observability data, and runtime metrics. Decision record in `docs/control/DECISIONS.md` records approval or identifies blockers.
3. **Future waves (S05–S11):** Domain-specific agents (research, concept, Notion build, variant, QA, merchandising, assets, draft, publisher, analytics, support) are implemented with prompts, integration tests, and commissioning evidence, then promoted to `TESTED` individually.
4. **Commissioning to `COMMISSIONED`:** Requires operator-approved decision record citing: passing integration tests, prompt hash verification, tool permission enforcement, structured output validation, cost/usage metrics within budget, and at least one successful end-to-end workflow execution (research → … → publish → analytics) in simulation mode.

### Concurrent claim safety

Wave 9 proves concurrent claim safety with tests:

- **Idempotent re-claim:** If a lease expires and another worker re-claims the same job, idempotency keys prevent duplicate effects. Test: two workers claim the same idempotency-keyed job concurrently; exactly one succeeds with `READY → RUNNING → SUCCESS`; the second gets a lease collision and finds the job already complete.
- **Double-execution prevention:** `FOR UPDATE SKIP LOCKED` lease acquisition ensures only one worker can claim a READY job. Test: two workers claim concurrently; exactly one acquires the lease, the other skips and finds no READY job.
- **Reconciliation:** If a worker crashes after executing but before emitting events, lease expiry allows retry. Idempotency keys prevent duplicate external effects. Test: claim → execute → kill before event → lease expires → re-claim → event + successor created exactly once.

### Fail-closed enforcement

Uncommissioned agents remain fail-closed:

- `AgentRunner.execute()` checks `agent_definition.commissioning_state` before invoking the agent.
- If state = `DESIGNED`, raise `AgentNotCommissionedError` and fail the job with event `AGENT_NOT_COMMISSIONED`.
- Contract tests prove this for all sixteen agents.

### Rollback procedure

If Exit 78 lift causes production issues:

1. Revert the commit that lifted Exit 78 (worker/scheduler return to `uncommissioned_process()` path).
2. Redeploy worker and scheduler containers; they exit 78 immediately.
3. Investigate logs, agent runs, events, and cost metrics to identify root cause.
4. File incident in `docs/control/DECISIONS.md` with reproduction, root cause, and remediation plan.
5. Exit 78 remains until remediation is complete and verified.

### Evidence location

- Contract tests: `tests/unit/test_roster_contracts.py` (135 tests parametrized A01–A16)
- Runtime integration tests (library): `tests/integration/test_runtime_integration.py` (Lane C)
- Runtime integration tests (production claim path): `tests/integration/test_runtime_integration.py` (Wave 9 additions)
- Concurrent claim + idempotency tests: `tests/integration/test_concurrent_claims.py` (Wave 9 new file)
- Commissioning state enforcement: `tests/unit/test_agent_runner.py` (existing + Wave 9 additions)
- Worker/scheduler claim path: `src/money_machine/orchestration/worker.py`, `src/money_machine/orchestration/scheduler.py` (Wave 9 edits)

### Session 04 closure relationship

Exit 78 lift is Wave 9 scope within Session 04, but Session 04 closure does not require Exit 78 to be lifted. The eight Session 04 evidence keys are:
1. `provider_abstraction_implemented` (W2) ✓
2. `prompt_registry_and_hashes_implemented` (W3) ✓
3. `agent_runner_integrated_with_jobs` (Lane A orchestrator wire) — OPEN
4. `sixteen_agents_registered` (W5) ✓
5. `uncommissioned_agents_documented` (W8) ✓
6. `contract_and_runtime_tests_pass` (W8 + Lane C) ✓
7. `control_files_and_checkpoint_current` (tip-sync) ✓
8. `evidence_closure_commit_recorded` — OPEN

Wave 9 is a bounded slice within Session 04 that conditionally lifts Exit 78 with commissioning gates. Session 04 may close with Exit 78 either lifted (Wave 9 complete) or held (Wave 9 incomplete), as long as all eight evidence keys are true. The decision to lift Exit 78 is captured here; the Session 04 closure decision is separate.

### Related decisions

- D-0003 (Session state is fail-closed) — Exit 78 is a production-blocking fail-closed boundary until commissioning evidence passes
- D-0026 (Prompt integrity as standing gate) — Agent prompts must pass hash verification before execution
- Session 02 addendum point 1 — "Job claiming is commissioned in Session 03" (later superseded by Session 03 addendum)
- Session 03 addendum point 4 — "commissioning evidence, agent promotion to COMMISSIONED, and removal of exit 78 are Session 04's scope"
- Session 04 addendum point 1 — "Exit 78 stays until decision record + commissioning evidence gate"

## D-0029 — Session 07 section 10 names are labels on the workflow graph

**Status:** accepted for Session 07 Wave 10, 2026-10-07.

### Context

Prompt section 10 names the chain DEDUPE_PASSED, BUILD_NOTION_TEMPLATE, RUN_PRODUCT_QA, REPAIR, CREATE_VARIANTS, RUN_VARIANT_QA, and GENERATE_LISTING_PACKAGE. Those names are not the job types in `config/workflows.yaml`. The Session 03 prompt-integrity review, finding M11, already voided the prompt's example job names as a parallel authority and bound implementation to `config/workflows.yaml`.

### Decision

The workflow link records the existing graph. It does not edit `config/workflows.yaml` and it does not create jobs.

- BUILD_NOTION_TEMPLATE is ProductBuildJob. DEDUPE_PASSED maps to that job alone.
- RUN_PRODUCT_QA is ProductQAJob.
- REPAIR is BuildRepairJob. The edge is recorded. This wave does not execute it.
- CREATE_VARIANTS is VariantBuildJob.
- RUN_VARIANT_QA is VariantPublishJob, because VARIANT_LINKS_VERIFIED maps to ScreenshotJob on `event_successor_map`.
- GENERATE_LISTING_PACKAGE ready is ListingCopyJob, whose output contract includes ListingPackage. The path reaches it through ScreenshotJob. SCREENSHOTS_CAPTURED maps to ListingCopyJob, AssetFactoryJob, and DeliveryBuildJob. There is no direct VariantPublishJob to ListingCopyJob edge.

Each of the ten edges is checked three ways. The predecessor must admit the event. The predecessor must name the successor. `event_successor_map` must list that event's successors in canonical order. The eight persisted step labels stay the section-10 names. An extra successor refuses. The real three-job SCREENSHOTS_CAPTURED list still passes.

Caller `buyer_problem`, `flagship_feature`, `hubs`, `identity`, and `tier` are not a second fact source. The expected hubs are the caller's hubs when that caller is the hub set QA judged: the same hub names, in order, and `spec.identity` equal to the notification row Name. That ordered name tuple is the stored spec. A mismatched caller is refused when the live section prose is not that caller's prose. Identity `Not The Row`, or hubs named `Other ` plus the judged name, after a post-QA hub, buyer, or practice edit, raises `fact ledger caller does not match` and writes nothing. A stored BLOCKED ledger is not overwritten to PASS when that caller resumes. A live purpose, buyer, or practice edit on a matching caller is BLOCKED, with ready empty and `qa_verdict` false. A missing block id is still a refusal. Tier follows the stored database kinds. The ledger counts known ids only. The proof copy is not a known id, and `page_count` stays 15. No ListingCopyJob reads the ledger in this wave.

A mismatched caller whose descriptions still equal the live section text is not that edit. `_require_hub_name` accepts a 64-character hub name and refuses 65, on the named path and on the unnamed path. The unnamed detail check repeats that name rule. A 65-character name is refused by `_require_hub_name` and does not reach the detail check. `test_legal_bounds_pass_and_one_past_refuses` kills `_require_hub_name`. `test_unnamed_sixty_four_character_hub_name_passes` is the 64-character PASS. A buyer problem of 501 to 1000 characters passes on both paths. The on-disk progress record stores `next_phase`, and a named BLOCKED ledger's in-memory `next_phase` is that same value (`test_matrix`).

Amended 2026-10-08 after the verifier FAIL on tip `9eff481e`: reading buyer, flagship, and hub prose back off the live pages had turned a live edit into a ledger PASS. Amended again after reviewer review 5454105031 on tip `5dc55814`: the unmatched-caller branch was still reading that prose off the live pages. Amended again after verifier comment 6056684351 on the same tip: the refusal is the post-QA edit, and a 64-character name on the unmatched path stays legal. Amended again after verifier comment 6060511391 and CodeRabbit review 5455831580 on tip `45818d9e`: the checkpoint stores a digest of the QA-approved descriptions, buyer, and flagship. Amended again after reviewer review 5457879480 on the same tip: each variant name is checked on its own, a QA formula expression must be an exact `str`, and a provider `ProductBuildError` does not leave with its message or its cause chain. Amended again after verifier comment 6066644759 on tip `0b2007a7`: the read failure is raised after its handler has returned, so no provider or code error is reachable on `__cause__` or `__context__`, and an own-prefix message counts as an own refusal only when package code raised it and its cause is not a `ProviderFailure`. Amended again after reviewer review 5464808945 and verifier comment 6072697310 on tip `1e614857`: a fact that is a str subclass is refused, a variant name with a comma is refused, a QA provider response is neither stored nor raised, and a cancellation or other `BaseException` leaves the ledger read as a fresh error of the same kind with no text or chain. Amended again after reviewer review 5466065420 on tip `08484bf0`: any `Exception` from a QA provider call is recorded and raised under the fixed provider text, a custom `BaseException` keeps its kind only when building it runs no caller code (otherwise its nearest built-in base), and a `BaseExceptionGroup` keeps its kind with cleaned members.

Caller-trust limit. The QA record stores `prose_digest`, the sha256 of the hub descriptions in order, then `buyer_problem`, then `flagship_feature`. Hub names and the row identity are not in that digest. `_plan` compares the stored digest with the caller's prose before `live_qa_passed` and before any write. A mismatch raises `fact ledger caller does not match` and writes nothing. Amended 2026-10-10 by D-0031: `_saved_holds` returns false, and QA runs again, only when that caller is the judged hub names and the notification-row identity. Any other caller raises `qa caller does not match` and writes nothing. The digest is length-prefixed with a 4-byte big-endian utf-8 length. It is not a newline join. A caller who keeps the judged hub names and the row identity, and who changes a description, the buyer, or the flagship after QA, does not get a ledger PASS until that re-run. A mismatched caller who rewrites descriptions to edited pages is the same refusal when that prose is not the stored digest. The 64-character unnamed path still PASSes when the descriptions, buyer, and flagship are the ones QA judged. Forged prose that QA has not re-judged is not a ledger PASS. The ledger call itself does not re-run QA.

Supported devices are recorded as `unverified`. The free-update policy is recorded as `not_configured`. Nothing persisted verifies either one. Those tokens are not a device claim and not a free-update claim.

### Consequences

A missing admitted event, a missing successor type, a missing edge, an extra successor, or a missing ListingPackage output raises `workflow link does not match` before any write. Merchandising may claim only the facts in the ledger. Section 11 and commissioning stay out of this wave.

## D-0030 — Section 11 fixture defects are not repaired in place

**Status:** accepted for Session 07 Wave 12, 2026-10-10.

### Context

Prompt section 11 says to prove broken-formula repair, wrong-linked-view repair, and missing-sub-page repair. Wave 9 already recorded that the fixture has no in-place update, and that a new id would not match the stored checkpoint. Those defects are refused or recorded `BLOCKED` with zero adapter writes. Wave 12 is the fixture test matrix. It does not add update methods.

### Decision

The matrix proves the fixture contract. It does not repair the three defects.

- A wrong formula expression, or a linked view pointed at another known database, records `BLOCKED` with zero adapter writes. The expression and the view target stay as they were.
- A missing hub section makes the ledger read raise `fact ledger section is missing`. The matrix writes nothing and does not recreate the block. Hub sections in this fixture are text blocks, not child pages.
- ListingCopyJob stays a recorded ready name (D-0029). The matrix does not create the job.
- The live sandbox stays unauthorized. Narrative `next_phase` after a recorded matrix is `sandbox_build`, and that phase is not run.

### Consequences

A matrix `PASS` means the live fixture still matches the passing ledger. It is not a repair. Commissioning and the twelve evidence keys stay false. In-place repair waits for a later wave that adds fixture update methods without breaking stored ids. The 2026-10-10 Eng Ops run recorded in the session-close note is title-only, QA NOT_RUN, in sandbox MM S06 Sandbox. It is not this matrix phase. It does not authorize `sandbox_build` and it does not flip an evidence key.

## D-0031 — QA prose is length-prefixed, and only the judged caller can refresh it

**Status:** accepted for Session 07 Wave 13, 2026-10-10.

### Context

D-0029 stores a sha256 of the hub descriptions, the buyer problem, and the flagship feature. The first encoding joined those fields with a newline. A newline inside one field could hash as the next field. The same decision re-ran QA on every digest mismatch. A caller who was not the judged hub set could refresh the digest and then pass the ledger. Secret-link facts kept the query and the fragment, and a userinfo password survived the page-id strip.

### Decision

- `prose_digest` hashes each field with a 4-byte length prefix. Hub names and the row identity stay out of the digest.
- A stored digest that differs from the caller is a new judgement only when the hub names match, in order, and `spec.identity` is the notification row Name. That caller may re-run QA.
- Any other caller raises `qa caller does not match`. The checkpoint bytes stay as they were. No adapter write runs.
- A secret-link fact is `scheme://host`, or the word `missing`. The page id, userinfo, port, path, query, and fragment are not stored.

### Consequences

The ledger still refuses a mismatched caller whose live prose is not the caller's prose (D-0029). A judged caller can still be judged again after a prose edit. W13 did not start the live sandbox. The close records that title-only Eng Ops run. It records the `:145` operand check as equivalent at the public entry. It records `:156` as a survivor when a proof page already exists. In-place repair, commissioning, and the twelve evidence keys stay out.

## D-0032 — Session 07 close is Omar's merge, and the evidence keys stay false

**Status:** accepted 2026-10-10.

### Context

The Session 06 close (`ac6afcfb`, #50) set `session_status` to complete, kept `current_session` on the closed session, appended that session to `completed_sessions`, and advanced `next_session` and `next_prompt`. It also set every Session 06 evidence key true. Session 07's twelve evidence keys are still false. Exit 78 was not lifted. Omar merged #64 himself.

### Decision

Record Session 07 with the Session 06 pointer convention, and do not flip the twelve evidence keys.

- `session_status` is complete. `current_session` stays 7. `completed_sessions` is `[0, 1, 2, 3, 4, 5, 6, 7]`. `next_session` is 8. `next_prompt` is `11_SESSION_08_MERCHANDISING_AND_ASSET_FACTORY.md`. `completion_requires_next_session` is 8.
- `head_sha` tip-syncs to `b782751fdb1b255c436ff7f6fa655e6d783b1e8c`. It is not the commit that contains the state file. `evidence_closure_commit_sha` stays the Session 06 tip `0f94d585f23d79e5ac18479f01e14f67cbaad332`. `last_verified_commit` stays bootstrap.
- The twelve evidence keys stay false. `commissioned_agents` stays empty. Exit 78 stays HELD.
- The close gate is that merge, at 2026-10-10 12:36:46 +0700. Omar's words, relayed by Grok Bot from its chat at 2026-10-10 12:39 ICT: "Yes, my merge is the Session 07 close gate. Fix the Verifier items in a follow-up PR."
- #64 merged while Verifier round 2 was FAIL (comment 6094256754). Those items are what this pull request fixes.
- No Lead Reviewer pass is on record.
- `validate_completion_transition` from the `b782751` state to this record fails first with `unsupported completion: notes cannot change`. With `notes` copied unchanged, it then fails with `pre-transition evidence must be complete except for the evidence-closure commit`, because the twelve evidence keys are false. This checked-in record is the operator gate. It is not that CLI transition. State revision 63 to 64. `updated_at` is `2026-10-10T05:36:46Z`, the merge commit time.

### Consequences

Session 08 is named as the next prompt and is not activated. `current_session` stays 7. A later activation would install Session 08's evidence keys and is a separate change. The twelve Session 07 keys stay false, so they are not evidence that the product build or QA is complete.
