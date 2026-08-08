# Test Evidence

## 2026-08-08T13:43:51Z — Evidence registered, outer run pending

| Claim | Evidence | Verdict |
|---|---|---|
| Root sources preserved | SHA-256 values in `docs/source/CANONICAL_SOURCE_REGISTER.json` match the canonical files; detailed rename receipts remain ignored runtime evidence | PASS for source lane |
| Prompt pack deterministic | `python3 scripts/extract_prompt_pack.py --check` must report 21 verified files | Pending fresh owned suite below |
| Control transition fail-closed | `tests/bootstrap/test_control_state.py` exercises allowed and unsupported completion | Pending fresh owned suite below |
| Full Session 00 | Runtime, build, ignore audit, reviews, and Git checkpoint evidence | NOT PROVEN |

No runtime or Session 00 completion claim is made by this entry.

## 2026-08-08 — Fresh owned validation

- `uvx --from pytest pytest -q tests/bootstrap/test_prompt_pack.py tests/bootstrap/test_control_state.py` -> **12 passed in 10.86s** after formatting.
- `python3 scripts/extract_prompt_pack.py --check` -> **verified 21 prompt files against Appendix A**.
- `python3 -m py_compile ...` over the extractor and owned tests -> **pass**.
- `python3 -m json.tool` over control state and the safe canonical source register -> **pass**.
- `sha256sum` -> PDF `c9cd…0fad`; workbook `4dbe…7f2b`, exactly matching registration.
- `git check-ignore -v` -> strict-deny rules matched the PDF, `.omx`, `.trigger-tree`, `.codebase-memory`, `.env`, runtime, and secrets probes.

These results close only the source/prompt/control lane. Session 00 outer gates remain unproven.

## 2026-08-08T14:47:04Z — Integrated local gate receipt

| Gate | Fresh machine result | Verdict |
|---|---|---|
| Canonical inputs | WSL/Windows path mapping and both registered source SHA-256 values matched | PASS |
| Prompt pack | Extractor check verified all 21 canonical prompt files | PASS |
| Python | Ruff passed; strict Pyright reported no errors; Pytest reported **17 passed** | PASS |
| Live API | `/health` returned HTTP **200** from a running API process | PASS |
| Script syntax | Bash and PowerShell parser checks completed successfully | PASS |
| Isolated clean bootstrap | Frozen `uv` and `pnpm` installs, bootstrap validation, web lint, typecheck, tests, and production build passed in isolation | PASS |
| Compose definition | `docker compose config --services` listed `postgres`, `worker`, `api`, `scheduler`, and `web` | PASS for configuration only |
| PostgreSQL runtime | `timeout 15 docker info` exited **124** before a daemon response | NOT VERIFIED |
| Remote | `git remote -v` returned no configured remotes | BLOCKED for push only |
| Independent reviews | No implementation approval or adversarial clearance receipt exists | PENDING |
| Git checkpoints | No bootstrap or evidence-closure commit SHA exists | PENDING |

The Docker timeout does not support a PostgreSQL health claim. The passing local gates do not complete Session 00 without PostgreSQL runtime evidence, both reviews, and both distinct commits.

## 2026-08-08T15:53:49Z — Review remediation and clean-copy rerun

| Gate | Fresh machine result | Verdict |
|---|---|---|
| Review finding: database credentials | All four database-consuming services resolve the same interpolated user, password, database, and `postgresql+asyncpg` URL; contract tests include a custom credential set | PASS for configuration |
| Authenticated PostgreSQL smoke | Bash and PowerShell scripts now connect over TCP with `PGPASSWORD`, `--no-password`, `ON_ERROR_STOP`, and `SELECT 1` | IMPLEMENTED; runtime blocked by daemon |
| Review finding: control transition | Shipped `money-machine-control apply-completion` validates and atomically writes the transition; tests invoke the production entry point | PASS |
| Review finding: receipt policy | Detailed receipt removed from source documentation; safe source identity is committed and detailed receipts remain under ignored `.omx/` | PASS |
| Review finding: Appendix B | Extractor validates the independent Appendix B hash, byte, and line-count register for 21 prompts plus `MANIFEST.json` | PASS |
| Review finding: PDF proof | Deterministic standard-library verifier proved 82 ordered, nonempty, text-bearing pages without emitting copyrighted text | PASS on canonical tree |
| Python outer gates | Ruff format/check passed; strict Pyright reported 0 errors; Pytest reported **23 passed** with one third-party deprecation warning | PASS |
| Clean source-only copy | Ignored PDF and `.omx` were absent; frozen installs, Python gates, **23 tests**, web lint/typecheck/**2 tests**/production build, and missing-private-PDF register verification passed | PASS |
| Script syntax | Bash parse and Windows PowerShell AST parse reported 0 errors | PASS |
| Compose definition | Custom credentials resolved identically for `postgres`, `api`, `worker`, and `scheduler`; exact five-service set preserved | PASS for configuration only |
| Docker daemon | Latest bounded `docker info` exited **1** with `Cannot connect to the Docker daemon at unix:///var/run/docker.sock` | UNAVAILABLE |

The first clean-copy run exposed a test that assumed `.git` metadata existed. The test now validates the live Git ignore decision when inside a repository and validates the explicit `.omx/` rule in source-only copies; both canonical and clean-copy runs pass. PostgreSQL runtime, fresh independent review clearance, and Git checkpoint receipts remain open.

## 2026-08-08T16:37:31Z — Environment and Git-evidence contract receipt

- Windows: `Microsoft Windows 10.0.26200.8973`; Windows PowerShell: `5.1.26100.8972`.
- WSL `2.7.11.0`; WSL2 kernel `6.18.33.2-microsoft-standard-WSL2`; WSLg `1.0.73.2`.
- Git `2.43.0`; GitHub CLI `2.92.0`.
- Docker client `29.4.2` build `055a478`; Docker Compose `v5.1.3`; daemon unavailable at `unix:///var/run/docker.sock`.
- Python `3.12.3`; uv `0.11.7`; Node `24.15.0`; pnpm `10.33.2`.
- Chromium `150.0.7871.128` launchers are available at `/snap/bin/chromium` and `/usr/bin/chromium-browser`; Playwright is not installed in the Session 00 project.
- The shipped completion command now requires real Git commit objects, the exact bootstrap subject, bootstrap-to-closure ancestry, current branch/HEAD agreement, a clean tracked pre-transition state, and a non-self-referential closure tree. Focused production-entry-point tests use real temporary Git commits and reported **13 passed** with Ruff and strict Pyright clean.

## 2026-08-08T17:26:54Z — Full canonical scaffold and integrated rerun

| Gate | Fresh machine result | Verdict |
|---|---|---|
| Canonical scaffold | Parser verified **293 declared files** and **96 declared directories**; persisted empty directories use 33 scoped `.gitkeep` markers | PASS |
| Python | Ruff format/check passed across **271 files**; strict Pyright reported 0 errors; Pytest reported **27 passed, 1 skipped** | PASS with explicit Docker-CLI skip |
| Control Git evidence | Real temporary commits prove valid application; nonexistent, non-ancestor, wrong-subject, dirty-state, and unsupported transitions are rejected without writes | PASS |
| Canonical sources | Prompt pack verified 21 files; private PDF verifier proved 82 ordered/nonempty/text-bearing pages | PASS |
| Bash operations | All scripts parsed; `e2e`, `backup`, `restore`, and `commission` returned fail-closed exit **78** | PASS |
| PowerShell operations | Windows AST parser reported 0 errors; the same four operations returned fail-closed exit **78** | PASS |
| Source-only clean copy | Both private PDF locations and `.omx` absent; frozen installs, Python gates, 27 tests plus one Docker skip, scaffold/prompt/source checks, and web lint/typecheck/2 tests/build passed | PASS |
| Web production build | Nine static routes built, including `/api/health`, `/pipeline`, `/shop`, `/blocked`, `/decisions`, `/incidents`, and `/settings` | PASS |
| Docker/Compose CLI | `/usr/bin/docker` and the Compose plugin point into Docker Desktop's WSL mount, which returned `Input/output error` | UNAVAILABLE |
| PostgreSQL authenticated runtime | Cannot run while Docker Desktop's WSL CLI/runtime surface is unavailable | NOT VERIFIED |

The Docker-dependent Compose resolution test is the single explicit skip; static tests still prove the shared anchor, exact nested URL contract, five-service declaration, healthcheck, and fail-closed worker/scheduler settings without substituting for the missing runtime proof.

## 2026-08-08T17:54:20Z — Docker-backed runtime receipt

| Gate | Fresh machine result | Verdict |
|---|---|---|
| Docker server | `docker info --format '{{.ServerVersion}}'` returned `29.4.2` | PASS |
| PostgreSQL | `postgres:16-alpine` reached healthy; authenticated TCP `psql` with `PGPASSWORD`, `--no-password`, and `ON_ERROR_STOP` returned exactly `1` | PASS |
| API container | Image built; container reached healthy; `GET /health` returned HTTP 200 and the typed versioned payload | PASS |
| Web container | Image and nine-route production app built; container reached healthy; `GET /api/health` retained `dependencies: unverified` and `externalActions: false` | PASS |
| Worker and scheduler | Both images built; both containers exited exactly **78** with restart disabled | PASS fail-closed |
| Compose contract tests | Real CLI resolution used isolated environment input; full Pytest result became **28 passed** with no skips | PASS |
| Clean bootstrap | Source-only clean copy completed frozen uv sync and `docker compose config --quiet` | PASS |

The initial public-image pull exposed Docker Desktop's Windows credential helper missing from the WSL PATH. `scripts/verify_postgres.sh` now adds the existing Docker Desktop helper directory only for that process when needed; the same script passed afterward without an inherited helper PATH.

## 2026-08-08T20:33:22Z — Final remediation, clean bootstrap, and implementation re-review

| Gate | Fresh machine result | Verdict |
|---|---|---|
| Canonical sources | Immutable hashes matched; deterministic verifier covered 82 ordered pages; extractor verified 21 prompt files | PASS |
| Python static gates | Ruff format/check passed across 271 files; strict Pyright reported 0 errors, 0 warnings | PASS |
| Transition/scaffold/Compose regressions | **43 passed**; the complete Python suite reported **53 passed** with one third-party Starlette deprecation warning | PASS |
| Script boundaries | Bash and PowerShell parsed; e2e, backup, restore, and commission returned intentional exit 78 in both shells | PASS fail-closed |
| Compose/runtime | Development and production configs resolved; production worker/scheduler resolved restart `no`; PostgreSQL authenticated; API/web healthy; worker/scheduler exited 78 with restart count 0 | PASS |
| Clean source-only bootstrap | Frozen uv and pnpm installs, source/scaffold checks, Ruff, Pyright, 53 Python tests, web lint/typecheck/2 tests/nine-route build | PASS |
| Strict-deny audit | Named token, cookie, browser-profile, screenshot, receipt, customer, provider-payload, PDF, runtime, and OMX probes were ignored; curated documentation/config paths remained visible | PASS |
| Post-rename receipt | Ignored receipt SHA-256 `abb1d417ac0e45dbcbcd9bed8a6d13936906b252176b6fd9948dd1d9edb316e0` records current source/path identity and the pre-rename receipt hash | PASS |
| Independent implementation re-review | `.omx/evidence/session-00/implementation-review.md` SHA-256 `87b84524bee8894f1c63f23a8d730c4d51995199c99089a88294389ac1a3a19c`; explicit post-remediation verdict **APPROVE** | PASS |
| Adversarial review | `.omx/evidence/session-00/acceptance-audit.md` SHA-256 `80d865efcec010cbc2c05c12362ff41f29073bd840b1a7cffcf72e84796fe137`; fresh focused suite **35 passed**; 375-path staging projection had no forbidden paths; explicit verdict **CLEAR** for the local closure sequence | PASS |
| Git checkpoints | Branch remains unborn; bootstrap, evidence-closure, and state-pointer commits are not yet recorded | PENDING |

The full ignored verification summary is `.omx/evidence/session-00/verification.md` (SHA-256 `d98ebb7fdc03c67c82991b3d52eb7aa0a6f30daa429e3d822d474045007a6e7c`). The passing gates and independent reviews establish readiness for the required Git transition; they do not themselves complete Session 00.
