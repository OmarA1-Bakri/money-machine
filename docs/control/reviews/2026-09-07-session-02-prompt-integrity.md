# Session 02 prompt-integrity review

**Prompt:** `prompts/implementation/05_SESSION_02_ENGINEERING_FOUNDATION_AND_DATABASE.md`
**Verified SHA-256:** `dd64137dfa21792e7956d3fe4a24b449aa59625872af05c567e294eee2aad0ab`, equal to the workbook's declared value and to the prompt-pack manifest. The extraction is authentic; the defects below are in the instruction set, not the extraction.
**Date:** 2026-09-07. **Procedure:** `docs/PROMPT_INTEGRITY_REVIEW.md` (D-0026).

## Verdicts

| Dimension | Verdict |
|---|---|
| Fidelity to the authorities and to Session 01 | NOT CLEAR — three high findings |
| Safety and executability against this repository | NOT CLEAR — one critical, four high |
| Exit-criteria gameability | NOT CLEAR — every criterion has a cheap fake |

## Findings

**C1 CRITICAL — the prompt authorises removing the fail-closed boundary.** Action 8 requires the worker and scheduler to "connect to the database and expose liveness" and the exit criteria require those containers to "start". Both entry points return `EXIT_UNAVAILABLE = 78` today, Compose sets `restart: "no"` so the exit is terminal, and the control state records that as verified evidence. Literal execution deletes the refusal and polls a jobs table that has no lease, visibility-timeout, retry, or dead-letter semantics, because the durable orchestrator is Session 03. That removes the last mechanical barrier between a job row and agent execution and invalidates recorded evidence.

**H2 HIGH — Session 01's lineage layer is dropped at the schema boundary.** Actions 4 and 5 say only "foreign keys for lineage" and "artifact hash storage". Nothing requires persisting `prompt_reference`, `prompt_sha256`, `agent_definition_version`, `EffectReference.effect_state`, `provider_object_id`, `reconciliation_attempt`, `ProductQAResult.checked_artifact_ids`, `PreflightResult.listing_package_sha256`, `DedupeResult.rule_version`, `compared_spec_ids`, `ArtifactReference.sensitivity`, `retention_class`, `parent_artifact_ids`, `JobEnvelope.retry_class`, or `success_contract`. The 33-table list contains no table for a QA, preflight, or dedupe result at all, so a verdict has nowhere to live and D-0025's reconciliation and stale-QA rules become unimplementable without a schema rewrite.

**H3 HIGH — action 6 creates a second source of truth.** Seeding "playbook product rules" and "autonomy configuration in simulation mode" forks authority away from the YAML files that D-0019 and D-0022 make authoritative, with no precedence rule, and invites an agent to create the git-ignored operator authority file `config/autonomy.yaml` just to have something to seed from.

**H4 HIGH — `UNCOMMISSIONED` is not a value in the code.** `AgentCommissioningState` is `DESIGNED`, `IMPLEMENTED`, `TESTED`, `COMMISSIONED`, `SUSPENDED`, and all sixteen agents are `DESIGNED`. Seeding the literal string either fails validation or invents a sixth state.

**H5 HIGH — the integration-status surface invites credential reads and live provider calls.** Neither the route nor the command is scoped, and action 3 makes provider credentials locally available, so "status" reads naturally as read the token and call the provider. D-0016 forbids exactly that.

**H6 HIGH — the session is not executable as one bounded wave.** Thirty-three tables, migrations, persistence services, a six-command CLI, a seven-route API, five services, CI, and ten test classes in one session contradicts the governance rule against a single dirty mega-task.

**M7 to M11 MEDIUM.** Action 3 recreates settings Session 01 already owns. Action 7's API and CLI lists omit canonical routers and commands that `scripts/verify_scaffold.py` enforces, and neither action 4 nor 5 names the canonical `migrations/` and `persistence/` paths. Action 9 is written as though CI does not exist: three workflows are present, two of them deliberate refusal gates that must not be overwritten. Action 2 demands Playwright, which is not installed and downloads browser binaries. `sqlalchemy`, `alembic`, `asyncpg`, an `alembic.ini`, and a `money-machine` console script are all absent and unnamed.

**Gameability.** "Containers start" is arguably already true, since a container that exits 78 has started. "Migrations work" is satisfied by one migration creating two tables, as nothing binds it to the 33 names. "Seeds are idempotent" is satisfied by a seed that inserts nothing. "Foundation tests pass" is satisfied by stubs. Seven of the eight evidence keys are self-reported; only the evidence-closure commit is machine-earned.

## Corrective addendum

This is the instruction set Session 02 executes. The prompt remains the unamended source of record.

1. **Preserve the fail-closed boundary.** The worker and scheduler keep `EXIT_UNAVAILABLE = 78` and must not claim, lease, or transition any job row. They may add a read-only startup database connectivity check and log its result before exiting 78. Compose keeps `restart: "no"`. "Containers start" means each process starts, performs its check, and exits 78 without restart looping; the API, web, and PostgreSQL services must reach Compose health and stay healthy. Job claiming is commissioned in Session 03.
2. **Persist the Session 01 contracts in full.** The 33-table list is a minimum, not a ceiling. `agent_runs` carries the agent definition version, prompt reference, and prompt hash. Add `effect_attempts` for the idempotency key, provider, operation, effect state, provider object identifier, and reconciliation attempt; `qa_results` for the checked artifact identifiers; `preflight_results` for the listing-package hash; and `dedupe_results` for the rule version and compared specification identifiers. Every field of every Session 01 contract has a column or a documented reason it does not.
3. **One runtime authority.** Do not seed autonomy values and do not create, copy, or commit `config/autonomy.yaml`. YAML remains the runtime authority for product rules, ramp, agents, workflows, and telemetry. If a record of the loaded configuration is useful, store a non-authoritative snapshot with its source path and content hash, marked advisory, never read back as a decision input.
4. **Use the real commissioning ladder.** Seed the sixteen agents at the state recorded in `config/agents.yaml`, currently `DESIGNED`. Commissioned status requires evidence that satisfies the locatable-reference rule in D-0023.
5. **Scope integration status.** It reports configured or not configured from settings presence and the declared effect mode. No secret value is read, logged, or returned; no network call is made; no browser profile is opened. Secret presence is a boolean.
6. **Extend, never recreate or overwrite.** Extend the Session 01 settings and loader modules rather than recreating autonomy, ramp, or product-rule configuration. Extend `.github/workflows/ci.yml` with a PostgreSQL service and the format check; do not modify `e2e.yml` or `release.yml`, which are uncommissioned refusal gates. Implement into the canonical paths and keep every canonical file present. Add a `money-machine` console script without renaming `money-machine-control`, and add the database dependencies and `alembic.ini` explicitly.
7. **Four bounded slices.** Tooling, settings, and environment example; then core workflow and job schema with migrations and repositories; then the remaining domain tables and the seed; then API, CLI, Compose, and CI. Integrate after the second and fourth slices.
8. **Harden the exit criteria.** Migrations upgrade an empty database to exactly the declared table set and survive a downgrade to base and back; the seed inserts the named content and a second and third run change nothing; the required tests name their entities and assert database-level constraint rejection; secret redaction is asserted across representation, logs, and responses; readiness fails when PostgreSQL is stopped; the final gate runs after the control files are written; and each non-Git evidence key names a receipt path and a command exit code in `TEST_EVIDENCE.md`.
9. **Standing safety, restated because the prompt omits it.** Simulation only, including in tests. No publication, purchase, spend, customer message, or provider mutation. External effects only through adapters with explicit modes, idempotency written before any external write, and reconciliation. Never commit secrets, environment files, tokens, cookies, browser profiles, runtime state, generated evidence, or the PDF. Preserve both immutable sources byte-for-byte and preserve user changes. Bootstrap must not create or modify `.env`.
10. **Reviews at exit.** Two independent reviews scoped to schema, constraints, lineage foreign keys, and migration reversibility; and to Compose, CI, and secret handling. Each returns CLEAR or NOT CLEAR with numbered findings recorded under `docs/control/reviews/`, and every critical and high finding is remediated and re-reviewed before the closure commit.

## Deferrals

| Item | Reason | Owner |
|---|---|---|
| Playwright installation and configuration | Browser binaries are a large network-dependent side effect adjacent to the provider boundary, and no browser-channel work exists yet | The first session that needs a browser channel |
| Per-session commit-subject enforcement in the control validator | The closure commit's content is already machine-verified; the subject is a labelling convention | Optional hardening, any session |
| Concurrency proof for idempotency uniqueness | Requires the durable orchestrator's claim path | Session 03 |

## What the prompt gets right

Byte-faithful extraction. The 33-entity list matches the workbook exactly. Sixteen agents match the roster. The five Compose services match the architecture decision with no unapproved infrastructure. Schema conventions of UUID keys, UTC timestamps, idempotency uniqueness, immutable event and receipt records, and soft deactivation are correct and conservative. The environment example must carry names and explanations but never credentials, and secrets must never be logged. Unimplemented agents must not be marked commissioned. The ordering of schema, then persistence, then seed is correct.
