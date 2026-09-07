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
