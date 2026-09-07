# 0003 Typed Agent Contracts

**Status:** Accepted

## Context

Agents may use different prompts and providers, but their outputs decide durable workflow transitions. Free text cannot safely unlock downstream jobs or prove that an operation completed.

## Decision

Every agent invocation uses versioned Pydantic v2 contracts. Common boundaries are `JobEnvelope`, `AgentResult`, `ArtifactReference`, and `EvidenceReference`; workflow-specific contracts include the Session 01 result models. Models are frozen, strict, reject unknown fields, carry `schema_version: Literal[1]`, use UUID identifiers, and require timezone-aware UTC datetimes.

`JobEnvelope` contains identity, owner, status, JSON-compatible input, required artifact references, schedule, attempt bounds, idempotency key, side-effect class, retry class, and a structured success contract. `AgentResult` contains one permitted terminal status (`SUCCESS`, `FAILURE`, `BLOCKED`, or `UNCERTAIN_EXTERNAL_EFFECT`), structured output, artifacts, evidence, events, and an optional structured error. Status/error consistency is validated.

Prompt text is versioned input to an agent run. It never defines durable states, retry policy, authority, or business thresholds. Model output is parsed into the declared contract before persistence or event emission. A schema failure is an agent-run failure and unlocks no successor.

Schema evolution is explicit. Compatible additions require defaults and preserved semantics; incompatible changes use a new schema version and adapter. Agent definitions record prompt version, model/provider policy, allowed tools, timeout, retry policy, side-effect class, and commissioning state.

## Rationale

Strict contracts create deterministic boundaries around probabilistic model execution, support replay and tests, and prevent plausible prose from being mistaken for evidence.

## Consequences

- Contract changes require tests and migration consideration.
- Strict coercion rejects convenient but ambiguous values.
- JSON-compatible common payloads permit generic orchestration, while concrete result contracts retain business precision.
- Prompts can evolve independently when their contract remains compatible.
- An agent is not `COMMISSIONED` until its implementation and contract tests pass.

## Rejected alternatives

- **Free-text result parsing:** ambiguous, fragile, and unsafe for transitions.
- **Untyped dictionaries:** accept misspelled fields and invalid values silently.
- **One universal result schema only:** loses domain invariants.
- **Provider-native schemas as authority:** couples durable contracts to one model vendor.
- **Permissive coercion and ignored extra fields:** conceal integration drift.

## Revisit when

Revisit when a concrete compatibility requirement cannot be represented through explicit versioning, or when another serialization protocol is required across a proven process boundary. Strict validation and structured terminal results remain non-negotiable.