# SESSION 13 — COMPLETE E2E, FAILURE INJECTION AND HARDENING

Execute under the Master Control Prompt and recovery protocol.

## Objective

Challenge the full implementation as a single system. Remove remaining stubs, prove every main and failure path, verify restart behaviour and ensure the repository is genuinely ready for deployment.

## Actions

### 1. Inventory completeness

Generate an implementation matrix for:

- every playbook step;
- every job type;
- every event;
- every lifecycle transition;
- every agent;
- every provider action;
- every console view;
- every runbook.

Classify:

```text
IMPLEMENTED_AND_TESTED
IMPLEMENTED_NOT_LIVE_TESTED
BLOCKED_BY_EXTERNAL_CREDENTIAL
MISSING
```

Implement every `MISSING` item in the active path. Do not hide gaps in documentation.

### 2. Remove false implementations

Search for:

- TODO;
- FIXME;
- `pass`;
- `NotImplementedError`;
- dummy production adapters;
- fake success returns;
- hardcoded provider IDs;
- skipped tests without reason;
- dead branches;
- duplicate orchestration logic;
- prompts with no contract tests.

Resolve all active-path findings.

### 3. Full synthetic E2E

Run the complete fixture-backed workflow:

```text
research
→ shortlist
→ score
→ teardown
→ ProductSpec
→ dedupe
→ Notion build
→ QA
→ variants
→ listing copy
→ assets
→ PDFs
→ Etsy draft
→ preflight
→ publish simulation
→ post-publish verification
→ weekly metrics
→ thirty-day maturity
→ winner
→ successor ProductSpec
→ successor build job
```

Persist and inspect all artifacts and receipts.

### 4. Alternate E2E paths

Run:

#### Cull

```text
mature loser
→ cull decision
→ deactivation
→ lesson
```

#### Repair

```text
mature conversion problem
→ listing repair
→ updated version
→ observation
```

#### Broken link

```text
buyer issue
→ incident
→ reproduce
→ source repair
→ listing file replacement
→ verify
→ response
```

#### Dedupe

```text
too-close ProductSpec
→ reconcept
→ pass
→ build
```

### 5. Failure injection

Inject:

- worker crash;
- scheduler restart;
- database reconnect;
- expired lease;
- duplicate event;
- duplicate publish request;
- provider timeout before response;
- provider timeout after success;
- expired Etsy token;
- expired Notion session;
- malformed LLM output;
- unavailable LLM provider;
- asset-render failure;
- wrong PDF link;
- stale ProductFacts;
- browser selector change;
- ramp full;
- spend cap reached.

Verify recovery or exact blocking state.

### 6. Concurrency and performance

Prove:

- two workers do not run the same job;
- multiple product workflows can progress;
- publication cap remains global to the shop;
- database indexes support ready-job polling;
- artifact generation does not exhaust memory;
- browser contexts are bounded and cleaned;
- no unbounded retry loop.

### 7. Security and secret review

Check:

- `.env` excluded;
- browser profiles excluded;
- source PDF excluded;
- logs redact secrets;
- PostHog excludes sensitive data;
- API mutation endpoints are protected appropriately for deployment;
- no credentials in git history;
- downloaded competitor files remain private;
- runtime paths have sensible permissions.

Keep this focused on real implementation risks.

### 8. Backup and restore proof

Create a workflow with artifacts, back up:

- PostgreSQL;
- configuration;
- artifact storage metadata.

Restore into a clean environment and prove:

- workflow state;
- jobs;
- products;
- listings;
- schedules;
- agent definitions;
- artifacts;
- incidents.

### 9. Broad verification

Run:

- Python formatting;
- Ruff;
- Pyright;
- all Python tests;
- frontend lint/type/tests;
- browser E2E;
- migrations from empty;
- migrations from current;
- Docker production build;
- vulnerability checks available locally without adding paid services.

### 10. Independent final review

Use independent reviewers for:

- architecture;
- orchestration;
- integrations;
- data integrity;
- agent contracts;
- product outputs;
- frontend;
- DevOps.

Fix all critical/high defects and all medium defects that threaten autonomous operation.

### 11. Checkpoint

Commit:

```text
test(system): complete E2E and failure hardening
```

## Exit criteria

- No active-path stub remains.
- Complete happy/cull/multiply/repair paths pass.
- Restart and duplicate-effect tests pass.
- Backup/restore passes.
- Full quality suite passes.
- External credential-only gaps are explicit.
- Control files and commit are current.

## Required exit code

```text
SESSION_13_E2E_AND_HARDENING_COMPLETE
```

Next prompt:

```text
17_SESSION_14_DEPLOYMENT.md
```
