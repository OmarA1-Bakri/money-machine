# Implementation Log

## 2026-09-11 — Recovery review and ordered delivery plan

- Recovered canonical `build/full-automation` at `3720653`, Session02 complete, next Session03; preserved untracked `CLAUDE.md`. Wrote metadata-only recovery checkpoint `.omx/state/review-resume-20260911.json`.
- Reconciled the older integration branch as reference material: 49 unique commits versus 10 canonical commits, historical Session07 closure, and protected uncommitted Session08 work. No history, source, database or old worktree was replaced.
- Two independent read-only reviews identified current startup defects and a session-scoped reuse strategy. The durable review and plan are `docs/control/reviews/2026-09-11-recovery-review-and-finish-plan.md`; it records findings, sources, milestone acceptance and the next repair/Session03 wave.
- Live Docker inventory showed only the project's PostgreSQL container running. Worker/scheduler remain intentionally unimplemented beyond the Session02 exit-78 boundary. No provider action, commissioning or session transition was performed.

## 2026-08-08T13:43:51Z — Session 00 source/control lane

- Adopted the sole canonical root at `/mnt/d/Money Machine`; the old lowercase root is absent and `wslpath` maps the root to `D:\Money Machine`.
- Rehashed both immutable sources and recorded post-rename byte-identity evidence.
- Deterministically extracted the 21-file canonical prompt pack from COPY markers and verified Appendix hashes/bytes plus calculated source lines and output line counts.
- Added copyright-safe continuous PDF page coverage and exhaustive Chapter 12-16 step, Prompt 1-13, and Workbook Page 1-6 mappings.
- Initialized fail-closed control state as `incomplete`. Runtime, review, Git, and outer verification gates remain pending and must not be inferred from this documentation slice.

## 2026-08-08T14:47:04Z — Session 00 integrated local verification

- Reconfirmed the canonical WSL/Windows root and immutable source hashes; the 21-file prompt pack remains verified.
- Passed the full Python gates: Ruff, strict Pyright, and all 17 Pytest tests.
- Received HTTP 200 from the live API `/health` endpoint and passed Bash and PowerShell parser checks.
- Passed isolated frozen `uv` and `pnpm` installs plus the clean bootstrap and complete web lint, typecheck, test, and build sequence.
- Confirmed Compose resolves `postgres`, `api`, `scheduler`, `web`, and `worker`.
- `timeout 15 docker info` exited 124. Docker-backed PostgreSQL health/runtime is therefore unverified.
- No Git remote exists. Independent reviews, the bootstrap commit, and the distinct evidence-closure commit remain pending; Session 00 stays fail-closed and `next_session` remains `0`.

## 2026-08-08T15:53:49Z — Session 00 review remediation

- Reconciled Compose to one interpolated database credential contract and added authenticated TCP PostgreSQL smoke scripts for Bash and PowerShell.
- Moved completion-transition validation into the shipped `money-machine-control` entry point with atomic persistence and rejection tests against the real CLI.
- Replaced the committed detailed rename receipt with a safe source identity register; detailed receipts remain ignored runtime evidence.
- Added Appendix B line-count validation and a copyright-safe deterministic PDF page-tree/content-stream verifier.
- Reran the full canonical Python gates and a source-only clean bootstrap: Ruff, strict Pyright, 23 Pytest tests, prompt/source verification, frozen installs, web lint/typecheck/2 tests/build, Compose interpolation, and Bash/PowerShell parsing passed.
- Docker daemon responsiveness and authenticated PostgreSQL runtime remain unproven. Fresh post-remediation reviews and Git checkpoints remain pending, so Session 00 remains `incomplete`.
- The latest bounded `docker info` attempt returned exit 1 with `Cannot connect to the Docker daemon at unix:///var/run/docker.sock`; this supersedes the earlier timeout as the current blocker evidence.

## 2026-08-08T17:26:54Z — Session 00 full-scaffold and second-review repair

- Added every file and directory declared by the canonical repository structure: the deterministic verifier reports 293 files and 96 directories, with inert Python placeholders and fail-closed uncommissioned operational surfaces.
- Repaired completion semantics to require real Git commit objects, exact bootstrap subject, ancestry, branch/HEAD agreement, clean tracked state, and a non-self-referential closure followed by a separate state-pointer commit.
- Isolated Compose contract tests from developer `.env` files and stale ambient `DATABASE_URL` values; static contract checks remain runnable when Docker Desktop is unavailable, while the real CLI check skips with an explicit infrastructure reason.
- Recorded exact Windows, WSL, PowerShell, Git/GitHub CLI, Docker/Compose, Python/uv, Node/pnpm, Chromium, and Playwright availability evidence.
- Integrated canonical gates passed: Ruff across 271 files, strict Pyright with zero findings, 27 Pytest tests with one Docker-CLI skip, scaffold/prompt/PDF verifiers, Bash syntax and fail-closed exits, and PowerShell AST parsing/fail-closed exits.
- A fresh source-only clean copy excluded both private PDF locations and `.omx`; frozen Python/Node installs, the same Python gates, 27 tests with one Docker-CLI skip, clean-clone source verification, web lint/typecheck/2 tests, and a nine-route production build passed.
- Docker Desktop's WSL CLI mount now returns `Input/output error`; Compose CLI, PostgreSQL runtime, and health remain externally blocked. Post-repair review and Git checkpoints remain pending, so Session 00 remains `incomplete`.

## 2026-08-08T17:54:20Z — Session 00 Docker runtime restored

- Docker server `29.4.2` became available. A WSL-only credential-helper PATH mismatch was handled process-locally and then repaired in `scripts/verify_postgres.sh` without changing global Docker configuration.
- Pulled PostgreSQL 16 Alpine, created the Compose network and data volume, reached container `healthy`, and passed an authenticated TCP `psql` query returning exactly `1`.
- Built the API, web, worker, and scheduler images from the repository Dockerfiles. PostgreSQL, API, and web all reached Compose health.
- Container API `/health` returned HTTP 200 with the typed `api` payload; container web `/api/health` returned `dependencies: unverified` and `externalActions: false`.
- Worker and scheduler containers both exited exactly 78 with restart disabled, proving the intended fail-closed uncommissioned boundary.
- Reran the full Python suite with the real Compose CLI: **28 passed** with no skips. A fresh source-only bootstrap also passed its Docker Compose configuration step.
- Runtime gates are now closed. Fresh implementation/adversarial review and the Git checkpoint sequence remain; Session 00 stays `incomplete` until those receipts exist.

## 2026-08-08T20:33:22Z — Session 00 final remediation and implementation approval

- Repaired the bootstrap scripts so both Python and web dependencies are installed from frozen lockfiles; added strict-deny root rules and adversarial ignore probes for tokens, cookies, browser profiles, screenshots, receipts, customer data, and provider payloads.
- Prevented production restart loops by explicitly setting worker and scheduler restart policies to `no`; fresh containers exited intentionally with code 78 and zero restarts.
- Hardened the completion transition so the committed pre-transition state must already contain every non-Git evidence fact, continuity fields cannot be rewritten by the candidate, exactly one outer-gates blocker may be removed, and the closure commit's state must exactly equal the live pre-transition state.
- Fresh canonical and source-only runs passed Ruff across 271 files, strict Pyright with zero findings, **53 Pytest tests**, web lint/typecheck/**2 tests**/nine-route build, Bash and PowerShell parsing/fail-closed checks, development and production Compose resolution, authenticated PostgreSQL, API/web health, and worker/scheduler fail-closed runtime.
- Independent focused re-review changed the implementation verdict from REJECT to **APPROVE** after both HIGH findings were repaired. Adversarial clearance and the three-commit local closure sequence remain pending; the remote blocker remains push-only.
- Independent adversarial re-audit then issued **CLEAR** for the leader-owned local closure sequence after 35 fresh focused tests and a 375-path staging projection with no forbidden paths. This clearance is not itself a completion or push claim; the three required local commits and atomic transition remain.
- Created the exact 375-path bootstrap commit `1abf0d7cca3a6b8cd7efcd0a45523538fd5bfd9d` with subject `chore(bootstrap): initialise money machine autonomous monorepo`. The staged-path manifest matched the adversarial projection, contained no forbidden path or symlink, and immutable source hashes were unchanged immediately before commit.

## 2026-08-08T20:57:00Z — Session 00 atomic completion

- Created evidence-closure commit `50350b9937ad97dabf4be3762a00638d62aaa5b9`, a direct descendant of bootstrap `1abf0d7cca3a6b8cd7efcd0a45523538fd5bfd9d`, containing the exact still-incomplete pre-transition state.
- Ran the shipped `money_machine.control apply-completion` entry point while branch `build/full-automation` was clean and attached at that closure commit. The validator resolved both commit objects, checked the exact bootstrap subject and ancestry, compared the closure document with the live state, and atomically advanced state revision 9 to 10.
- Session 00 is now locally complete: `completed_sessions` is `[0]`, `next_session` is `1`, the canonical Session 01 prompt is selected, all completion evidence is true, and only the precise push-only `REMOTE_NOT_CONFIGURED` blocker remains.
- This completed state and the four companion control documents are checkpointed by the later state-pointer commit containing this entry; the state intentionally does not claim that commit's own object ID.

## 2026-08-08T23:36:23Z — Public GitHub publication and CodeRabbit review

- Acting on explicit operator authorization, created public repository `OmarA1-Bakri/money-machine`, configured `origin`, and pushed `build/full-automation`. Remote HEAD for that branch exactly matched local `ef4a2039d976285d295e429cebbfdd9951bd7bf4`; GitHub reported visibility `PUBLIC` and selected the pushed branch as default.
- The public-visibility instruction supersedes the earlier private-remote assumption for this repository only. The immutable PDF, `.omx`, runtime evidence, secrets, browser state, customer/provider payloads, dependency caches, and local knowledge graph were not tracked or pushed.
- CodeRabbit's all-file CLI attempt was rejected by the 150-file limit, so the review was split into bounded scopes using an isolated empty Git metadata baseline without changing the canonical worktree/index/history.
- CodeRabbit completed agents, domain, integrations, control, and orchestration reviews. It raised four issues: one critical and one major in `control/state.py`, plus trivial locking and logging findings. Persistence, API, tests, apps, and scripts retries were blocked by a 51-52 minute account rate limit because the selected organization lacks an assigned seat/API key.
- No CodeRabbit-suggested change was applied automatically. The issues and incomplete scopes are carried into Session 01 for validation and an authorized fix/re-review cycle.

## 2026-09-06T18:30:01Z — Session 01 activation and adversarial-review remediation (in progress)

- Session 01 work had accumulated in the worktree since 2026-08-09 without a ledger entry; this entry records it. A three-lane adversarial review on 2026-09-07 returned NOT CLEAR (one critical, seven high); the record is `docs/control/reviews/2026-09-07-session-01-adversarial-review.md`.
- Implemented the D-0010 activation transition (`money-machine-control activate`) with fail-closed tests for wrong-session, double, evidence-claiming, and pointer-rewriting activations, and generalised completion beyond Session 00 with a Session 01 closure test. Applied the activation to the live state through the shipped CLI: revision 11 → 12, `current_session` 1, `session_status` incomplete, Session 01 evidence keys installed as false.
- Implemented D-0009 filesystem identity (`same_file` on the canonical directory entry) so the lowercase WSL spelling of the root is accepted and hard-linked aliases are rejected.
- Made `MULTIPLY` a workflow boundary: the winner returns to `OBSERVING`, `require_successor_spawn` admits a distinct-workflow successor at `DEDUPE_CHECK`, and the same-workflow edge is rejected. Transition tests are now exhaustive over every state pair.
- Bound playbook shape rules into `ListingPackage` and `ProductSpec` (D-0022), typed the fifteen-per-week machine cap as an invariant, added `config/autonomy.yaml` (git-ignored) as the only production authority with `APP_ENV` environment resolution (D-0020), and recorded state-machine deviations (D-0021).
- Governance scripts `scripts/write_resume_checkpoint.py` and `scripts/omx_task_metrics.py` are now on this branch (copied byte-for-byte from `integration/first-product-vertical-slice`); `scripts/run_affected_tests.sh` remains conditional in governance because its database helpers are not on this branch.
- Worktree register (status relative to `build/full-automation` HEAD `0827baa`, all under ignored `.omx/`, none deleted): `integration/first-product-vertical-slice` unmerged, 49 commits ahead, last 2026-08-28, active reference source; `wave1/orchestration-task-4` (5 ahead), `wave1/research-task-5` (4), `wave1/build-task-6` (4), `wave1/build-task-6-clean` (4), `wave1/build-task-6-clean-r5` (4), `wave1/build-task-6-r7` (5), `wave1/listing-task-7` (13), all last touched 2026-08-09/10, inactive; two detached `worker-*` trees (1 ahead each, 2026-08-09), inactive. Their unmerged content has not been reconciled into this branch and is not claimed as Session 01 evidence.
- CodeRabbit's four Session 00 issues are fixed in `control/state.py` and tested; the `CODERABBIT_REVIEW_OPEN` blocker and the OPEN rows in `TEST_EVIDENCE.md` stay until the remaining scopes are re-reviewed. Session 01 remains `incomplete`.

## 2026-09-06T20:52:51Z — Session 01 review findings 9 to 13 remediated

- Canonical `bash scripts/test.sh` now exits 0 on this tree: frozen sync, Ruff format and lint across the repository scope, strict Pyright with zero findings, **149 Pytest tests passed** with one filesystem-dependent skip, and Compose configuration. Tool directories and Markdown are excluded from Ruff; tool directories and the operator autonomy file are git-ignored.
- Workflow graph validated for reachability and effect-mode consistency (D-0023); `CullDecisionJob` removed, `LinkVerificationJob` and `NotionRepairJob` added, `ScaleEvaluationJob` wired through the monthly deep pass, provisioning writes admit simulation.
- Telemetry typed and loaded (`TelemetryEventName`, `TelemetryConfig`); commissioning evidence typed as locatable references; `DedupeResult` records rule version and compared catalogue; real subprocess tests prove fail-closed exit 78.
- CodeRabbit disposition recorded in `TEST_EVIDENCE.md`; the blocker remains until the vendor re-review completes. Web gates remain environment-blocked (`pnpm` EACCES on `/mnt/d`). Session 01 remains `incomplete`; remaining closure work is the Session 01 exit criteria evidence, the independent final reviews, and the closure commit sequence.
- Independent re-review of this wave found an unreproduced Ruff panic in the root-scope format walk plus doc/config drift and an event-ordering defect; remediated per D-0024 (explicit-path gate, `REPAIR_APPLIED` before `REPAIR_COMPLETED`, doc-versus-config drift test, traversal guard). Final canonical gate result is recorded in `TEST_EVIDENCE.md`.

## 2026-09-07T00:54:17Z — Session 01 closure wave

- Ran the two closure reviews the Session 01 prompt requires. They raised three HIGH findings, all remediated: `AgentResult` now carries `agent_run_id`, `agent_id`, `agent_definition_version`, `prompt_reference`, and `prompt_sha256` with artifact-to-run binding; `NOTION_LINK_PUBLISH` moved to `BROWSER` and `NOTION_WORKSPACE_PROVISION` to `MANUAL_EXTERNAL_BLOCKER`; reconciliation of uncertain external effects is designed with a typed `EffectReference` and per-job idempotency-key templates (D-0025).
- Also closed the accompanying mediums: the integration matrix names the `capability_operation` code on every row and a test asserts codes and channels match configuration; the entity diagram corrects product-to-spec and listing-to-metrics cardinality and adds the idempotency, receipt, research, asset and incident edges; `ProductQAResult` names the artifacts it checked and `PreflightResult` pins the package hash; `DEPLOYMENT.md` states the five-step go-live procedure and `AUTONOMY_MODEL.md` names the second publication switch.
- Web gates passed after the install failure was diagnosed: the pnpm hardlink rename fails on the 9p `/mnt/d` mount, so the install used `--package-import-method copy`. Lint, typecheck, two tests and a nine-route production build all exited 0. The first build attempt failed with a Turbopack out-of-memory error and passed on one rerun; both are recorded in `TEST_EVIDENCE.md`.
- **Integrator error recorded:** `git checkout -- docs/architecture/INTEGRATION_MATRIX.md` discarded that file's uncommitted Session 01 content and restored the committed placeholder. The file was reconstructed in full from content read earlier in the session, improved with operation codes, and is now covered by a test. No other file and no committed history was affected. The lost bytes were never committed and are unrecoverable; the reconstruction is content-equivalent by review, not byte-identical.
- Final full gate on the frozen bytes: `bash scripts/test.sh` exit 0 with Ruff format and lint clean, strict Pyright zero findings, **152 Pytest tests passed** with one filesystem-dependent skip, and Docker Compose configuration valid; canonical scaffold verification passed; web lint, typecheck, tests and nine-route build all green.

## 2026-09-07T00:56:53Z — Session 01 atomic completion

- Implementation commit `156e279` carries the canonical subject `docs(architecture): define playbook automation contracts` and 75 paths with no secret, private source, runtime evidence, provider payload, symlink, or tool-directory content.
- Evidence-closure commit `15b5df45c3a535548fe24698a590fc16c5757829` contains the exact still-incomplete pre-transition state at revision 14.
- The shipped `money-machine-control apply-completion` entry point validated both commit objects, ancestry from the prior closure, branch and HEAD agreement, a clean tracked tree, and the closure document's byte equality with the live state, then advanced revision 14 to 15 atomically.
- Session 01 is locally complete: `completed_sessions` is `[0, 1]`, `next_session` is 2, the canonical Session 02 prompt is selected, and all nine Session 01 evidence keys are true. The `CODERABBIT_REVIEW_OPEN` blocker is retained because the vendor re-review is still rate-limited.
- This completed state and its four companion control documents are checkpointed by the later state-pointer commit that contains this entry; the state does not claim that commit's own object ID.

## 2026-09-07T01:01:06Z — Post-transition regression repair

- The post-transition full gate failed: 45 control-state tests broke because their Session 00 fixtures deep-copy the live state, which now carries `transition_contract.completion_requires_next_session: 2`. The fixtures, not the transition, were wrong; the applied Session 01 completion is unaffected and was not rewritten.
- Fixed by pinning the Session 00 fixture and its candidate to their own transition contract, so programme advance can no longer break session-scoped fixtures. Re-ran the canonical gate: `bash scripts/test.sh` exit 0 with Ruff clean, strict Pyright zero findings, **152 Pytest tests passed** with one filesystem-dependent skip, and Compose configuration valid.
- Recorded rather than hidden: the earlier 152-test green predates the control-file update, so it did not bind these bytes. The lesson is that the final gate must run after the control files are written, not before.

## 2026-09-07T04:36:32Z — Session 02 activation

- Added Session 02's completion-evidence contract to `SESSION_EVIDENCE_KEYS` from the prompt's own exit criteria: fresh bootstrap path documented, schema and migrations work, seeds idempotent, runtime containers start, CI configuration complete, foundation tests pass, control files current, plus the evidence-closure key. A test now asserts every session's contract is contiguous and carries the closure key, so a future session cannot be activated without one.
- Ran `money-machine-control activate`: revision 15 to 16, `current_session` 2, `session_status` incomplete, `completed_sessions` `[0, 1]` and the next-session pointer unchanged, all eight Session 02 evidence keys installed as false. `head_sha` still records the Session 01 evidence-closure commit, as the contract requires.
- No Session 02 implementation work has started. Provider effects remain in simulation; nothing is commissioned.

## 2026-09-07T04:51:00Z — Prompt-integrity review becomes a standing gate

- Every session now proves its own prompt before obeying it. `docs/PROMPT_INTEGRITY_REVIEW.md` defines the adversarial review across fidelity, safety and executability, and gameability, followed by a corrective exercise that produces the addendum the session actually executes. `AGENTS.md`, `CLAUDE.md`, and governance section 0 carry the standing rule; D-0026 records why it cannot live inside the prompt files, which are hash-verified extracts of an immutable source.
- `tests/bootstrap/test_prompt_integrity.py` enforces it: the procedure must be published and referenced from all three rule documents, every session from 02 onward must have a record, each record must carry its prompt's verified hash and a corrective addendum, and every extracted prompt must still match the workbook appendix so amendments can never be made in place. The gate was observed failing closed for Session 02 before its record existed.
- Ran the review for Session 02 and recorded it at `docs/control/reviews/2026-09-07-session-02-prompt-integrity.md`. The prompt is byte-faithful and still defective: one critical finding that would remove the fail-closed worker and scheduler boundary before the durable orchestrator exists, five high findings including the loss of every Session 01 lineage field at the schema boundary and the absence of any QA, preflight, or dedupe result table, and exit criteria that are satisfiable by stubs. The ten-point corrective addendum now governs Session 02 execution, with three deferrals recorded against named owners.
- No Session 02 implementation work has started.

## 2026-09-07T07:41:19Z — Session 02 engineering foundation implemented

- Executed the ten-point corrective addendum from the Session 02 prompt-integrity review in four bounded slices: tooling and settings; schema, migrations and persistence; seed, command line and interface; containers, continuous integration and documentation.
- Added the database dependencies and a `money-machine` console script distinct from the fail-closed `money-machine-control`. Runtime settings cover database, interface, worker, scheduler, storage and five providers, with a `Secret` type that redacts in every representation and a URL that never holds a credential.
- Implemented 45 tables: the workbook's 33 logical entities plus twelve the addendum and its reviews required so Session 01's contracts persist, one reviewed Alembic revision, an async session and unit of work, and typed repositories with bounded pages and real optimistic locking.
- Seeding is idempotent, convergent and concurrency-safe. Interfaces expose liveness, a readiness check that actually fails, version, database status, workflow and job pages, and an integration status that reports presence only.
- Worker and scheduler keep their fail-closed contract: a read-only connectivity check, then exit 78, with no claim path anywhere in the source. Verified in containers.
- Two independent closure reviews both returned NOT CLEAR with two critical and ten high findings between them. All were remediated and pinned by tests: evidence has a table, optimistic locking is enforced by the mapper, lineage is foreign-keyed, verdicts cannot cite what does not exist, composite keys stop a lineage record lying, append-only tables carry refusal triggers, and taxonomies agree with the contracts. Recorded as D-0027.
- Final gates: `bash scripts/test.sh` exit 0 with **370 Pytest tests passed** and one filesystem-dependent skip; web lint, typecheck, two tests and a nine-route build all 0; canonical scaffold verification passed.
- Recorded rather than acted on: the shared development database and roughly four hundred leftover test databases belong to other branches and were left untouched. One verification command of mine briefly pointed the stack at that shared database; the migration aborted before any statement and the database was confirmed unchanged.

## 2026-09-07T07:43:45Z — Session 02 atomic completion

- Implementation commit `05695fa` carries the canonical subject `feat(foundation): add database runtime and project tooling` across 74 paths with no secret, private source, runtime evidence, operator authority, tool directory or symlink.
- Evidence-closure commit `e75b31745beef8d0368e9a21c437176edafb46a2` contains the exact still-incomplete pre-transition state at revision 18.
- The shipped `money-machine-control apply-completion` entry point validated both commit objects, ancestry from the Session 01 closure, branch and HEAD agreement, a clean tracked tree, and the closure document's byte equality with the live state, then advanced revision 18 to 19 atomically.
- Session 02 is locally complete: `completed_sessions` is `[0, 1, 2]`, `next_session` is 3, the canonical Session 03 prompt is selected, and all eight Session 02 evidence keys are true. The `CODERABBIT_REVIEW_OPEN` blocker is retained because the vendor re-review is still rate-limited.
- This completed state and its four companion control documents are checkpointed by the later state-pointer commit containing this entry.
