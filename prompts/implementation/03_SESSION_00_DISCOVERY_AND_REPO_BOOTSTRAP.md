# SESSION 00 — DISCOVERY, SOURCE INGESTION AND REPOSITORY BOOTSTRAP

```text
[@Remote Desktop Commander]
[@superpowers]
[@Composio]
[@posthog]
[@product-design]
```

Execute this session under `01_MASTER_CONTROL_PROMPT.md`.

## Objective

Locate any existing implementation, adopt it if present, or create the canonical private monorepo. Ingest the playbook as the business source, establish the full repository structure and create durable cross-session checkpoints.

This session must leave a reproducible repository that Session 01 can continue immediately.

## Actions

### 1. Inspect before creating

Search the Windows and WSL2 filesystems for likely repositories or folders containing:

```text
hands-off-money-machine
money-machine
agents-to-income
etsy automation
notion template automation
Lewis Jackson
```

Inspect candidate repositories using:

- path;
- git remote;
- branch;
- recent commits;
- README;
- agent files;
- workflow/state code;
- provider integrations;
- tests.

If a credible existing implementation exists, adopt it. Do not create a duplicate. Record why it is authoritative.

### 2. Establish the canonical root

If no implementation exists, create:

```text
D:\hands-off-money-machine
```

with WSL2 access at:

```text
/mnt/d/hands-off-money-machine
```

Initialise git and create:

```text
build/full-automation
```

Create a private GitHub remote named `hands-off-money-machine` through authenticated GitHub access or `gh` when available. Never create a public repository.

If remote creation is not possible, complete the local repo and record the exact authentication blocker without stopping other work.

### 3. Inspect the environment

Record exact working versions of:

- Windows;
- WSL2 distribution;
- Git;
- GitHub CLI;
- Docker and Docker Compose;
- Python;
- `uv`;
- Node;
- `pnpm`;
- Playwright/browser availability.

Install project-local dependencies where required. Avoid unnecessary machine-wide installations.

### 4. Ingest the playbook

Make the attached playbook available locally at:

```text
private/source/The-Hands-Off-Money-Machine-Playbook.pdf
```

Keep `private/source/*.pdf` gitignored.

Calculate and record:

- filename;
- local path;
- SHA-256;
- page count;
- ingestion date.

Create `docs/source/SOURCE_REGISTER.md`.

Create source-derived documents:

```text
docs/playbook/BUSINESS_PROCESS.md
docs/playbook/CHAPTER_TO_CAPABILITY_MAP.md
docs/playbook/PROMPT_LIBRARY_MAP.md
docs/playbook/WORKBOOK_DATA_MAP.md
docs/playbook/AUTOMATION_GAP_MAP.md
```

Requirements:

- Preserve the playbook's terminology and sequence.
- Map every chapter 12–16 step and every prompt 1–13.
- Map the six workbook pages into future structured records.
- Identify manual handoffs that the software must replace.
- Do not rewrite or criticise the business model.
- Do not copy the entire copyrighted book into committed files.
- Store concise implementation-relevant derived material with chapter/page references.

### 5. Copy this prompt pack into the repository

Create:

```text
prompts/implementation/
```

Copy all prompt-pack Markdown files into it so every later session can recover from the repository.

### 6. Create the canonical scaffold

Create the full folder and file skeleton defined in `02_CANONICAL_REPOSITORY_STRUCTURE.md`.

At minimum populate now:

- `AGENTS.md`;
- `README.md`;
- `NOTICE.md`;
- `.gitignore`;
- `.editorconfig`;
- `.env.example`;
- `pyproject.toml`;
- root `package.json`;
- `pnpm-workspace.yaml`;
- `compose.yaml`;
- placeholder but valid Dockerfiles;
- `config/*.yaml` with documented example values;
- PowerShell and Bash bootstrap/dev/test scripts;
- the five control files;
- minimal Python package;
- minimal FastAPI health endpoint;
- minimal test proving import and health behaviour.

`NOTICE.md` must state that the source playbook is third-party material used as an internal business specification and is not redistributed by the repository.

### 7. Establish repository rules

`AGENTS.md` must include:

- the playbook is authoritative for business logic;
- no commercial revalidation gate;
- no duplicate repositories or orchestration engines;
- no business rules hidden only in prompts;
- no external mutation outside adapters;
- no secrets, browser profiles or source PDF in git;
- no false completion;
- preserve user changes;
- every completed session updates control files and commits;
- tests must not publish, buy or spend.

### 8. Establish initial runtime

Bring up PostgreSQL through Docker Compose.

Prove:

- the database container starts;
- the API service starts;
- `/health` returns success;
- the minimal test suite passes;
- PowerShell and Bash entry scripts are syntactically valid.

Do not build the complete schema yet; Session 02 owns that work.

### 9. Initialise control files

Set:

```text
current_session = 0
completed_sessions = [0]
next_session = 1
```

Record:

- canonical path;
- branch;
- HEAD;
- remote status;
- environment versions;
- tests;
- genuine blockers.

### 10. Review and checkpoint

Use one implementation reviewer to inspect repository coherence and one adversarial reviewer to identify:

- duplicate structure;
- missing source mappings;
- broken bootstrap commands;
- committed private files;
- path problems between Windows and WSL2.

Fix findings now.

Commit:

```text
chore(bootstrap): create hands-off money machine monorepo
```

Push when authenticated.

## Exit criteria

- Existing work was either adopted or ruled out with evidence.
- The canonical repository exists.
- The playbook is registered and locally available.
- Derived playbook documents exist.
- The complete folder scaffold exists.
- PostgreSQL and the health endpoint run.
- Minimal tests pass.
- Control files are current.
- Git commit exists.
- Working tree is clean except explicitly preserved unrelated work.

## Required exit code

```text
SESSION_00_REPOSITORY_BOOTSTRAP_COMPLETE
```

Next prompt:

```text
04_SESSION_01_PLAYBOOK_MAPPING_AND_ARCHITECTURE.md
```
