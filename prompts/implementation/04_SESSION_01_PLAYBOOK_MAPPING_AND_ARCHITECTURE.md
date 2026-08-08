# SESSION 01 — PLAYBOOK MAPPING, ARCHITECTURE AND EXECUTABLE CONTRACTS

Execute under the Master Control Prompt and recovery protocol.

## Objective

Convert the playbook-derived process into the canonical technical design that all implementation sessions will follow. Produce precise contracts and architectural decisions, then encode the first executable domain schemas and state definitions.

This session is not a prolonged planning exercise. Omar has approved the target architecture in the Master Control Prompt. Complete the design, review it and prepare the code contracts that Session 02 will implement.

## Actions

### 1. Restore exact state

Read the control files, source register, all `docs/playbook/*`, git state and current tests.

Confirm Session 00 is complete. Correct any bootstrap defect before continuing.

### 2. Complete the chapter-to-software map

For every playbook step in chapters 12–16 and prompts 1–13, record:

- source chapter/step;
- business input;
- business output;
- owning agent;
- job type;
- persisted entity;
- emitted event;
- downstream job;
- external side effect;
- retry class;
- automation mode;
- success evidence.

No playbook job may be left ownerless.

### 3. Finalise the architecture documents

Create or complete:

```text
docs/architecture/SYSTEM_OVERVIEW.md
docs/architecture/STATE_MACHINE.md
docs/architecture/DATA_MODEL.md
docs/architecture/AGENT_ROSTER.md
docs/architecture/JOB_AND_EVENT_CONTRACTS.md
docs/architecture/ARTIFACT_LINEAGE.md
docs/architecture/INTEGRATION_MATRIX.md
docs/architecture/PLATFORM_COMPATIBILITY.md
docs/architecture/AUTONOMY_MODEL.md
docs/architecture/OBSERVABILITY.md
docs/architecture/DEPLOYMENT.md
```

Use Mermaid diagrams for:

- service architecture;
- product lifecycle;
- job dependency flow;
- cull/multiply closed loop;
- broken-link incident repair;
- deployment topology.

### 4. Write the ADRs

Complete the seven ADRs defined in the repository structure:

1. modular monolith;
2. PostgreSQL durable jobs;
3. typed agent contracts;
4. provider adapters with API/Composio/browser/fixture implementations;
5. artifact lineage;
6. standing-authority autonomy configuration;
7. deterministic asset rendering.

Each ADR must state:

- decision;
- rationale;
- consequences;
- rejected alternatives;
- when the decision should be revisited.

Do not add architecture beyond the Master Control Prompt.

### 5. Define exact state and job enums

Implement initial executable code for:

- product lifecycle states;
- job states;
- agent run states;
- side-effect classes;
- retry classifications;
- decision types;
- incident types;
- event names;
- autonomy modes.

Add transition tables and tests that validate:

- all documented transitions are represented;
- impossible transitions fail;
- every terminal branch has a defined result;
- `MULTIPLY` reaches a successor workflow;
- `CULL` reaches deactivation.

### 6. Define typed contracts

Create Pydantic contracts for:

- `JobEnvelope`;
- `AgentResult`;
- `ArtifactReference`;
- `EvidenceReference`;
- `ProductSpec`;
- `ResearchReport`;
- `TeardownReport`;
- `DedupeResult`;
- `BuildResult`;
- `ProductQAResult`;
- `ListingPackage`;
- `PreflightResult`;
- `MetricsSnapshot`;
- `PortfolioDecision`;
- `IncidentResult`.

The contracts may evolve, but they must be precise enough for Session 02 schema design.

### 7. Define configuration contracts

Complete:

```text
config/product_rules.yaml
config/publishing_ramp.yaml
config/autonomy.example.yaml
config/agents.yaml
config/workflows.yaml
```

Encode the playbook defaults, including:

- 25–40 research rows target;
- five shortlisted candidates;
- 30/40 build threshold;
- one primary and one backup;
- six to eight hubs;
- three or four colour variants;
- thirteen tags;
- ten images and one video;
- two or three launch listings per week;
- fifteen-per-week cap;
- thirty-day maturity;
- bottom-80-percent cull setting;
- monthly deep pass;
- one new-front experiment per batch.

Use configuration, not undocumented magic numbers.

### 8. Integration capability assessment

Inspect currently available:

- Etsy API/client access;
- Notion API;
- Composio actions;
- connected browser profiles;
- PostHog access;
- storage options;
- LLM provider access.

For each required operation, select:

```text
DIRECT_API
COMPOSIO
BROWSER
INTERNAL_RENDERER
MANUAL_EXTERNAL_BLOCKER
```

This is an implementation capability assessment, not a business critique.

### 9. Adversarial design review

Use specialist subagents to review:

- workflow completeness;
- database normalisation and lineage;
- orchestration/restart design;
- provider adapter boundaries;
- agent contract clarity;
- operator simplicity.

Resolve every critical and high-severity finding in the documents and contract code.

### 10. Verify and checkpoint

Run:

- format;
- Ruff;
- Pyright;
- contract tests;
- transition tests;
- existing bootstrap tests.

Commit:

```text
docs(architecture): define playbook automation contracts
```

## Exit criteria

- Every playbook step maps to an agent, job, state and successor.
- Architecture and ADRs are complete and consistent.
- State, event and job enums exist in code.
- Typed contracts exist and pass validation tests.
- Configuration contains the playbook defaults.
- Integration strategy is explicit for every provider operation.
- Reviews are resolved.
- Control files and git checkpoint are current.

## Required exit code

```text
SESSION_01_ARCHITECTURE_AND_CONTRACTS_COMPLETE
```

Next prompt:

```text
05_SESSION_02_ENGINEERING_FOUNDATION_AND_DATABASE.md
```
