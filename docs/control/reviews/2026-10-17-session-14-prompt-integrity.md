# Session 14 Prompt Integrity Review

**Date:** 2026-10-17
**Prompt:** `prompts/implementation/17_SESSION_14_DEPLOYMENT.md`
**Verified SHA-256:** `92d8c9a1b99e523ea227b2a4dc339fd0e32c6d007a9d05a4735b7a163cf7b624`
**Base:** Session 13 is complete at revision 104. `next_session` is 14. Session 14 is not activated. Exit 78 stays HELD.

The prompt file is not amended. This record is the corrective addendum. The review reads the prompt against D-0010, D-0020, D-0026, and D-0028, and against the existing `docs/architecture/DEPLOYMENT.md` and `compose.prod.yaml`. The prompt is 3,456 bytes and 177 lines.

## 1. Prompt authenticity

**Status:** VERIFIED

The extracted file's SHA-256 equals the workbook appendix entry for `17_SESSION_14_DEPLOYMENT.md`. The required exit string in the file is `SESSION_14_PRODUCTION_DEPLOYMENT_COMPLETE`.

## 2. Three-dimensional review

### Fidelity

**Verdict:** CONDITIONAL APPROVE.

**F-01 [CRITICAL] — "Deploy the latest exact commit" would change a live host.** The exit line requires a production stack on the selected environment. **Amendment:** No live deploy in this session. `deployment_target_recorded` selects `local-wsl` and records the rationale already in `docs/architecture/DEPLOYMENT.md`. **Deferral:** a deploy onto a machine Omar owns. Owner: an operator authority record.

**F-02 [HIGH] — Production images, a reverse proxy, and a public console are named as the deploy.** `compose.prod.yaml` already defines api, worker, scheduler, web, and postgres. Worker and scheduler restart are `no` because Exit 78 is held. **Amendment:** `production_packaging_defined` is earned only when the proof checks those services, the postgres volume, the healthchecks, and the fail-closed restart. A missing public domain does not block. **Deferral:** `docker build` and a public HTTPS certificate. Owner: an operator authority record.

**F-03 [HIGH] — Migration, backup-before-migrate, and scheduled production backups would touch a live database.** Session 13 already has the in-memory backup fixture. **Amendment:** `release_rollback_implemented` plans the backup and refuses live postgres. The bash and PowerShell commands are text. **Deferral:** a scheduled production backup. Owner: an operator authority record.

**F-04 [HIGH] — The exit string, the commit subject, and the tag are not a D-0010 completion.** **Amendment:** Do not write `SESSION_14_PRODUCTION_DEPLOYMENT_COMPLETE`. Do not use `feat(deploy): package and deploy production runtime` as the evidence. Do not treat `v0.1.0-rc1` as a key. Do not edit `IMPLEMENTATION_STATE.json` in the contract commit.

### Safety

**Verdict:** CONDITIONAL APPROVE.

**S-01 [CRITICAL] — A new paid environment is spend.** The prompt allows it only after explicit approval. **Amendment:** `new-paid` raises. This session does not call a cloud API and does not create a host.

**S-02 [CRITICAL] — Starting the worker or scheduler would clear Exit 78.** **Amendment:** Do not edit `worker.py` or `scheduler.py`. `service_controls_fail_closed` refuses start, stop, restart, scale, migrate, and safe update. Exit 78 stays HELD.

**S-03 [HIGH] — Secrets, browser profiles, and provider payloads are named as container configuration.** **Amendment:** Do not read `.env`, a browser profile, or a provider payload. The packaging proof does not print an interpolated secret. `compose.prod.yaml` keeps `POSTGRES_PASSWORD` as a required variable and does not commit a value.

### Gameability

**Verdict:** CONDITIONAL APPROVE.

**G-01 [CRITICAL] — The exit string, the commit subject, or the tag `v0.1.0-rc1` as completion.** **Amendment:** None of those strings is an evidence key. Completion is the six-key contract.

**G-02 [HIGH] — A paragraph that says the stack is deployed.** **Amendment:** `deployment_target_recorded` is earned only when the selector returns `local-wsl` and raises on `new-paid`.

**G-03 [HIGH] — The existing compose file, with no check that worker and scheduler stay fail-closed.** **Amendment:** `production_packaging_defined` is earned only when api, worker, scheduler, web, the postgres volume, and the healthchecks are present, and worker and scheduler restart stay `no`. The six runbooks must name Exit 78 and must not contain a secret.

**G-04 [HIGH] — A release record that tags an image and reports rollback.** **Amendment:** `release_rollback_implemented` binds the image tag to a commit, plans a backup before migration, refuses live postgres, and fails a compatibility check when the schema is incompatible. It does not push an image.

**G-05 [HIGH] — A service control that returns a status word.** **Amendment:** `service_controls_fail_closed` returns a refusal for start, stop, restart, status, logs, scale, the scheduler singleton, migrate, and safe update. A status word is not a running service.

## 3. Corrective addendum

1. The prompt hash stays `92d8c9a1b99e523ea227b2a4dc339fd0e32c6d007a9d05a4735b7a163cf7b624`. The prompt file stays byte-identical.
2. This wave installs the Session 14 contract and does not activate the session. Do not edit `IMPLEMENTATION_STATE.json`. Do not write the exit string, the commit subject `feat(deploy): package and deploy production runtime`, or the tag `v0.1.0-rc1`.
3. The contract keys are `deployment_target_recorded`, `production_packaging_defined`, `release_rollback_implemented`, `service_controls_fail_closed`, `control_files_and_checkpoint_current`, and `evidence_closure_commit_recorded`. A later activation installs every key false.
4. A live deploy, a new paid host, a production image build, public HTTPS, a scheduled production backup, a live PostHog event, Exit 78, and `SESSION_14_PRODUCTION_DEPLOYMENT_COMPLETE` are not keys.
5. Do not edit `worker.py` or `scheduler.py`. Do not replace Exit 78 with a running process. `compose.prod.yaml` keeps worker and scheduler restart at `no`.
6. Do not publish, spend, message a buyer, or call live Etsy, Notion, or PostHog. Tests open no socket and read no provider credential.
7. Carry forward `docs/architecture/DEPLOYMENT.md`, `compose.prod.yaml`, the Session 13 backup fixture, and `commissioned_agents` staying empty.
8. Level 1 for this wave is the contract test, then `ruff check` and `pyright` on the touched control modules.

## 4. Deferrals

**D-01 — Session 14 activation.** Owner: the next transition. The contract is installed. The session stays inactive.

**D-02 — A deploy onto a machine Omar owns.** Owner: an operator authority record. The selector records `local-wsl` and does not open a host.

**D-03 — A production image build, public HTTPS, and a scheduled production backup.** Owner: an operator authority record. The compose spec and the command text are the evidence.

**D-04 — Exit 78 removal.** Owner: Session 15 commissioning, and only after an authority record. This session does not start the worker or the scheduler.

## 5. What already holds

`docs/architecture/DEPLOYMENT.md` already selects a local and single-server topology and says Exit 78 is not deployment success. `compose.prod.yaml` already names the five services, the postgres volume, healthchecks, and fail-closed worker and scheduler restarts. Unapproved spend stays refused. A missing public domain does not delay the local package.
