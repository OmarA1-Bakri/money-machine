# Money Machine

Money Machine is a staged modular-monolith implementation of the workflow described by the registered internal business playbook. The intended runtime comprises a FastAPI API, durable worker, scheduler, compact operator console, and PostgreSQL canonical state.

## Current state

Session 00 repository bootstrap is **incomplete** until every runtime, review, Git, and evidence gate in `docs/control/IMPLEMENTATION_STATE.json` is satisfied. Documentation and prompt extraction are not completion evidence.

## Sources

- The original PDF remains an immutable, ignored root source and is not redistributed by Git.
- The implementation workbook supplies engineering/session contracts and the canonical 21-file prompt pack.
- Registration and copyright-safe derived maps live under `docs/source/` and `docs/playbook/`.

## Bootstrap

From a fresh clone, in order:

1. Copy `.env.example` to `.env` and set local values. Bootstrap never creates or edits
   `.env` for you, and no credential belongs in the example file. Nothing loads `.env`
   automatically: Compose reads it for interpolation, and a host-native command needs the
   variables exported, for example `set -a; . ./.env; set +a`. A host-native
   `MONEY_MACHINE_DATABASE_URL` must use `127.0.0.1`, not the Compose hostname `postgres`.
2. Run `bash scripts/bootstrap.sh`, or `scripts/bootstrap.ps1` on Windows. It installs
   Python and Node dependencies from the frozen lockfiles and validates the Compose files.
   It requires `uv`, `pnpm` and Docker on the path.
3. Start PostgreSQL with `bash scripts/verify_postgres.sh`, which waits for health and
   proves an authenticated TCP query.
4. Apply the schema with `uv run money-machine db upgrade`, then seed canonical
   configuration with `uv run money-machine db seed`. Use these rather than `alembic`
   directly: they report a typed result and a plain error instead of a driver traceback.
   Seeding is idempotent and convergent: an unchanged second run reports nothing created
   and nothing corrected, and a row that has drifted from the YAML authority is restored.
5. Check the result with `uv run money-machine status`, which exits non-zero when the
   database is unreachable, and `uv run money-machine integrations status`, which reports
   provider configuration presence without reading any credential.
6. Run the gates with `bash scripts/test.sh`. Database-backed tests create and drop their
   own throwaway databases; they skip with an explicit reason when PostgreSQL is absent.

Live provider effects are disabled by default and tests use simulation only. Going live is
a separate, deliberate step documented in `docs/architecture/DEPLOYMENT.md`.

### Services

`docker compose up -d postgres api web` starts the operator surfaces. The API exposes
`/health` for liveness and `/readiness`, which fails with 503 when the database is
unreachable or unmigrated. The worker and scheduler are registered but **not
commissioned**: each performs a read-only database connectivity check, logs the result,
and exits 78 without claiming any job. That exit is the intended contract until the
durable orchestrator is commissioned, which is why both set `restart: "no"` and carry no
health check.

### PostgreSQL contract

`POSTGRES_USER`, `POSTGRES_PASSWORD`, and `POSTGRES_DB` define one Compose database contract.
Unless `DATABASE_URL` is explicitly supplied, Compose builds it from those values and shares
the same four variables with `postgres`, `api`, `worker`, and `scheduler`. The URL uses the
Compose service hostname `postgres`; a host-native process must explicitly use `localhost`
instead. Keep custom credentials URL-safe, or provide a correctly percent-encoded
`DATABASE_URL` that matches them.

Start PostgreSQL and prove a real password-authenticated TCP connection with:

```bash
scripts/verify_postgres.sh
```

```powershell
scripts/verify_postgres.ps1
```

The verifier starts only the `postgres` service, waits for its health check, and then runs
`psql` from the existing PostgreSQL image against `127.0.0.1` with `PGPASSWORD`. It exits
nonzero unless `SELECT 1` succeeds, so a readiness-only result is not accepted as database
connectivity evidence. It leaves PostgreSQL running for local development; stop it with
`docker compose down` when finished.

## Continuity

Read `AGENTS.md`, `docs/control/IMPLEMENTATION_STATE.json`, `docs/control/NEXT_SESSION.md`, and the current prompt in `prompts/implementation/` before resuming. Contradictions and blockers are recorded rather than silently resolved.

Completion state is written only through the fail-closed transition command. Prepare a proposed
state in a separate file, then run:

```bash
money-machine-control apply-completion --candidate /path/to/proposed-state.json
```

The command validates Session 00 evidence against real Git commit objects before atomically
replacing `docs/control/IMPLEMENTATION_STATE.json`; a rejected transition leaves the current file
unchanged. `bootstrap_commit_sha` must be an ancestor of the evidence-closure commit, and repository
`HEAD` plus candidate `head_sha` must both identify that pre-transition closure commit. After the
write, create a separate state-pointer commit containing the completed control state. Its object ID
is intentionally not written into the file it contains, which avoids a self-referential commit hash.
