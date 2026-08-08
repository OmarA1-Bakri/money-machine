# Money Machine

Money Machine is a staged modular-monolith implementation of the workflow described by the registered internal business playbook. The intended runtime comprises a FastAPI API, durable worker, scheduler, compact operator console, and PostgreSQL canonical state.

## Current state

Session 00 repository bootstrap is **incomplete** until every runtime, review, Git, and evidence gate in `docs/control/IMPLEMENTATION_STATE.json` is satisfied. Documentation and prompt extraction are not completion evidence.

## Sources

- The original PDF remains an immutable, ignored root source and is not redistributed by Git.
- The implementation workbook supplies engineering/session contracts and the canonical 21-file prompt pack.
- Registration and copyright-safe derived maps live under `docs/source/` and `docs/playbook/`.

## Bootstrap

Copy `.env.example` to `.env` for local values, then run `scripts/bootstrap.sh` on
Linux/macOS or `scripts/bootstrap.ps1` on Windows. Live provider effects are disabled by
default; tests use simulation only.

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
