# Agent Roster

**Contract status:** A01–A16 are designed but not commissioned. Registration, prompts, provider tools, implementation, and contract tests are required before any status becomes `COMMISSIONED`.

| ID | Agent | Primary jobs | Input/output contract boundary | Side-effect class | Commissioning state |
|---|---|---|---|---|---|
| A01 | Shop Orchestrator | bootstrap records, schedules, build slots, routing, successor creation | `JobEnvelope` → `AgentResult` with workflow/job references | `NONE` | `DESIGNED` |
| A02 | Account & Integration | provisioning checks, environment audit, connection diagnostics | readiness input → `IncidentResult`/readiness output | `EXTERNAL_READ` or holder-gated `EXTERNAL_WRITE` | `DESIGNED` |
| A03 | Market Research | research collection and shortlist | source policy → `ResearchReport` | `EXTERNAL_READ` | `DESIGNED` |
| A04 | Competitor Teardown | capped purchase and structure-only teardown | purchase/provenance → `TeardownReport` | `EXTERNAL_SPEND` for purchase; otherwise `NONE` | `DESIGNED` |
| A05 | Product Strategy | qualification, niche selection, ProductSpec | research/teardown → `ProductSpec` and decisions | `NONE` | `DESIGNED` |
| A06 | Catalogue Dedupe | concept/title collision and reconcept evidence | ProductSpec/catalogue → `DedupeResult` | `NONE` | `DESIGNED` |
| A07 | Notion Product Builder | databases, dashboards, formulas, first build, repair | ProductSpec → `BuildResult` | `EXTERNAL_WRITE` | `DESIGNED` |
| A08 | Variant Builder | colour/identity variants and link publishing | QA-passed build → `BuildResult` variants | `EXTERNAL_WRITE` | `DESIGNED` |
| A09 | Product QA | formulas, duplication, page counts, isolation, access | build/artifacts → `ProductQAResult` | `EXTERNAL_READ` | `DESIGNED` |
| A10 | Merchandising | title, description, tags, price presentation | verified facts → `ListingPackage` copy/pricing | `NONE` | `DESIGNED` |
| A11 | Creative Asset | screenshots, images, video, delivery PDFs | facts/build/links → `BuildResult`/artifact references | `EXTERNAL_READ` and `NONE` renderer | `DESIGNED` |
| A12 | Preflight | exact launch checklist and readiness | immutable listing package/draft → `PreflightResult` | `EXTERNAL_READ` | `DESIGNED` |
| A13 | Etsy Publishing | draft, files/media, price, sale, publish, update, deactivate | `ListingPackage`/authority → provider result | `EXTERNAL_WRITE` or `EXTERNAL_SPEND` | `DESIGNED` |
| A14 | Analytics | weekly metrics, live age, maturity, deep pass | provider snapshots → `MetricsSnapshot` | `EXTERNAL_READ` | `DESIGNED` |
| A15 | Cull & Multiply | HOLD/REPAIR/CULL/MULTIPLY, successor spec, scale | metrics/cohort → `PortfolioDecision` | `NONE`; successor effects are separate jobs | `DESIGNED` |
| A16 | Customer Support & Repair | customer issue intake, diagnosis, internal artifact repair, scoped provider-repair requests | issue/incident → `IncidentResult` and typed A07/A08/A13 repair job | `NONE`, `EXTERNAL_READ`, or separately authorized `EXTERNAL_MESSAGE` | `DESIGNED` |

## Required definition fields

Every registered agent definition contains:

- stable ID and human-readable name;
- implementation and schema version;
- versioned system-prompt reference;
- Pydantic input and output contract references;
- allowed tools and provider operations;
- default side-effect class;
- timeout and retry class;
- model/provider policy;
- commissioning state and evidence references.

## Commissioning states

| State | Meaning |
|---|---|
| `DESIGNED` | Contract exists in architecture only |
| `IMPLEMENTED` | Real code exists but commissioning gates are incomplete |
| `TESTED` | Focused contract and simulation tests pass |
| `COMMISSIONED` | Implementation, contract tests, provider-mode safety, affected regression, and required review pass |
| `SUSPENDED` | Previously commissioned but disabled by capability, credential, safety, or compatibility failure |

Fixtures and mocks can prove contract behaviour but cannot by themselves establish live provider commissioning. A suspended agent's jobs remain blocked or route to admitted alternatives; no different agent silently inherits its authority.

## Routing rules

- Each job has exactly one `owner_agent_id`.
- A01 performs deterministic routing but does not synthesize another agent's business result.
- A13 owns Etsy mutations; other agents produce typed inputs rather than calling Etsy directly.
- A07/A08 own Notion mutations; A09/A12 verify through read-only adapter operations.
- A15 decides cull/multiply; A13 executes deactivation and A01 creates the successor workflow.
- A16 diagnoses incidents and may create replacement internal artifacts, but never calls Etsy or Notion mutation operations directly. It creates a typed, incident-scoped A07/A08 Notion repair job or A13 listing repair job; that effect owner creates a new affected version and triggers fresh verification.
- Agent free text may explain a result but never replaces structured output, evidence, or events.