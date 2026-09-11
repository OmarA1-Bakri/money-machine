# Startup repair wave

Date: 2026-09-11. Base: recovery-plan commit `a32f3f4`, canonical `build/full-automation`.
Scope: the first repair wave in `2026-09-11-recovery-review-and-finish-plan.md`; this is not a Session03 activation or Session02 re-closure.

## Changes

1. Readiness now requires the applied Alembic heads to equal the migration heads shipped with the checkout/image and requires every mapped table/column to exist. A reachable database with another branch's revision, an additional revision, a missing table or a missing column returns 503. An absent version table is handled without creating it. The typed database response adds `schema_current`; liveness remains independent. This is compatibility checking, not a claim to inspect every constraint/type/privilege at each request.
2. Database URLs decode encoded userinfo exactly once and preserve IPv6 brackets. Explicit and fallback database passwords preserve nonblank raw values, including surrounding whitespace. Public settings representations stay redacted.
3. Production Compose explicitly selects `APP_ENV=production` and supplies the password separately from the URL. Development Compose also separates the raw default password, using `DATABASE_PASSWORD_FALLBACK` only when the selected URL and explicit password provide none. Embedded external-URL credentials and explicit-password conflict rejection are preserved. `.env.example` documents the carrier and precedence.

Worker/scheduler still exit 78 and do not claim jobs. No agent commissioning, migration revision, source PDF/workbook, provider authority, live provider data or existing application database was changed. Tests create/drop their own disposable databases. Compose checks render configuration; they do not deploy it.

## Source and version grounding

- Python 3.12.3 installed `urllib.parse` implementation: parsing leaves userinfo percent-encoded; reconstruction now handles that explicitly.
- Alembic 1.19.2 installed `alembic/script/base.py:ScriptDirectory.get_heads` and `alembic/runtime/migration.py:MigrationContext.get_current_heads`: inspected before implementing migration-head checks. SQLAlchemy 2.0.52 is the installed database layer; Pydantic 2.13.4 is the installed configuration validator.
- Repository code is version 0.1.0. Canonical Dockerfiles copy `src`, `migrations` and `alembic.ini` and install the project editable; migration discovery is anchored to the installed source path rather than the shell's working directory. A missing migration directory fails readiness closed.

## Review and corrective loop

- Initial synthetic DSN regressions: five failures before the repair, then 26 runtime tests passed; six existing query/credential tests also passed.
- Initial readiness/production regressions reproduced wrong/extra revisions, missing columns and wrong environment. One test initially named a nonexistent fixture table; corrected it to the canonical `config_references` table and separately reproduced the intended readiness failure. No shared database was involved.
- Initial combined API/runtime/operations check: 55 passed.
- Independent Python review accepted readiness's read-only/fail-closed behavior and found a raw-password Compose mismatch. Rendered Compose tests reproduced both literal-percent and reserved-character failures; the separate carrier fixed them.
- Bounded re-review found surrounding whitespace was still stripped by the environment-secret accessor. The integrator diagnosed this, added four failing explicit/fallback/prefixed-password regressions, and limited whitespace preservation to database-secret reads. No additional reviewer loop was launched, following governance's bounded re-review rule.
- Affected regression exposed two old Compose tests pinning the former embedded-password format, plus a new test mistakenly feeding unresolved Compose interpolation into the runtime loader. Corrected the expectations and tested environment selection independently; actual resolved Compose credential tests cover both Compose files and external overrides.
- Latest focused checks: runtime/operations **61 passed**; Compose contracts **5 passed**.
- Final integrated command: `uv run --frozen pytest tests/unit/test_runtime_settings.py tests/unit/test_operations_contract.py tests/unit/test_configuration.py tests/unit/test_foundation_processes.py tests/contract/test_compose.py tests/integration/test_api.py tests/integration/test_cli.py -q --tb=short -rs`: **125 passed, no skips, 121.37 seconds**.
- Final static checks: 227 files formatted; Ruff lint clean; Pyright zero errors/warnings/information. An initial format check caught one long test assertion, corrected before the final run. No full repository suite or new deployment/commissioning claim.

## Remaining programme work

The first next implementation session remains Session03. Complete its prompt-integrity addendum and activation, then recover the old durable orchestration behavior into this schema. API authentication/exposure and bounded event/effect reads remain explicit findings owned by the relevant Session03/API work before operational mutation/exposure; they were not silently declared repaired here.
