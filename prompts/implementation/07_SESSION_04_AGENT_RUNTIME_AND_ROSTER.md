# SESSION 04 — AGENT RUNTIME, PROMPT REGISTRY AND COMPLETE ROSTER

Execute under the Master Control Prompt and recovery protocol.

## Objective

Build the shared runtime that executes all logical agents through typed contracts, versioned prompts and explicit tool permissions. Register the complete roster and commission only the runtime capabilities genuinely implemented in this session.

## Actions

### 1. Implement provider abstraction

Create:

- `LLMProvider` interface;
- current OpenAI-compatible provider;
- deterministic fake provider;
- structured-output validator;
- timeout handling;
- retry for transport/schema errors;
- token/cost metadata where available;
- prompt/model version recording.

Inspect current official provider documentation before writing version-specific calls.

### 2. Implement prompt store

Every agent prompt must be:

- stored in `src/money_machine/agents/prompts`;
- versioned;
- hashable;
- referenced by `prompt_versions`;
- loadable by ID;
- testable for required sections;
- free of runtime secrets.

Adapt the playbook's prompts into agent system prompts while preserving their business logic.

### 3. Implement agent base and registry

Create:

- `AgentDefinition`;
- `AgentContext`;
- `BaseAgent`;
- `AgentRegistry`;
- `ToolRegistry`;
- `AgentRunner`;
- structured result validation;
- run receipts;
- error capture;
- commissioning state.

### 4. Implement tool permissions

Each agent receives only relevant tools.

Examples:

- Research: Etsy read/browser, web capture, storage.
- Builder: Notion and asset tools.
- Publisher: Etsy mutation tools.
- Analytics: Etsy stats read.
- Support: Etsy messages, Notion repair and listing update.
- Orchestrator: no direct provider mutations; it creates jobs.

Do not let agents call one another directly. They return results to the orchestrator.

### 5. Register all sixteen agents

Populate `config/agents.yaml` and the database with:

- ID;
- name;
- purpose;
- input contract;
- output contract;
- prompt path/version;
- allowed tools;
- side-effect class;
- timeout;
- max attempts;
- commissioning state.

Implement real working versions now for:

- A01 Shop Orchestrator;
- A02 Account & Integration diagnostics;
- shared deterministic rule agents that do not require external providers.

Register later-domain agents as `UNCOMMISSIONED`, not fake-complete.

### 6. Implement subagent review support

Allow an agent implementation to request bounded internal specialist reviews through the LLM provider, but ensure:

- the owning job remains singular;
- reviews are attached as artifacts;
- reviews do not mutate provider state;
- final structured output comes from the owning agent;
- cost and run count are recorded.

### 7. Implement agent-run observability

Store:

- job;
- agent;
- input hash;
- prompt version;
- model;
- start/end;
- status;
- structured output;
- validation errors;
- tool calls;
- artifacts;
- cost/usage where available.

Emit local structured logs and PostHog-compatible events, even before live PostHog connection.

### 8. Contract tests

For every roster entry prove:

- prompt exists;
- schema imports;
- config validates;
- allowed tools resolve;
- side-effect class is declared;
- fake provider can produce a valid result;
- malformed output fails closed;
- uncommissioned agent cannot execute a production job.

### 9. Runtime integration tests

Prove:

- orchestrator leases an agent job;
- agent runner executes;
- result persists;
- event emits;
- successor creates;
- failed schema output retries appropriately;
- final invalid result fails the job;
- restart retains the run history.

### 10. Review and checkpoint

Use an agent-systems reviewer and prompt-contract reviewer. Fix critical/high findings.

Commit:

```text
feat(agents): add typed runtime and full agent registry
```

## Exit criteria

- Provider abstraction works.
- Prompt registry and hashes work.
- Agent runner integrates with durable jobs.
- All sixteen agents are registered.
- Unimplemented agents are honestly uncommissioned.
- Contract and runtime tests pass.
- Control files and commit are current.

## Required exit code

```text
SESSION_04_AGENT_RUNTIME_COMPLETE
```

Next prompt:

```text
08_SESSION_05_MARKET_RESEARCH_TO_PRODUCT_SPEC.md
```
