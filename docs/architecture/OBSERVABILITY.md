# Observability

**Contract status:** operational observation design. PostgreSQL workflow state and provider reconciliation remain authoritative; telemetry is not completion evidence.

## Signals

| Signal | Purpose | Authority |
|---|---|---|
| Structured logs | Diagnose one process/job/adapter attempt | Informational; never unlocks work |
| PostgreSQL job/event state | Current durable workflow, leases, blockers, successors | Canonical internal authority |
| Provider reconciliation receipts | Confirm external object/effect state | Canonical for that external effect |
| Metrics | Queue age, attempts, lease recovery, adapter latency/error, render duration | Operational trend/alert input |
| Traces | Correlate API command, job, agent run, adapter operation | Diagnostic |
| PostHog events | Founder-facing workflow/product operations | Best-effort observation only |
| Health/readiness | Liveness and verified dependency readiness | Narrow claim defined by each endpoint |

The existing web health route and API liveness route must not be described as proof of worker, scheduler, PostgreSQL, or provider health when they do not verify those dependencies.

## Correlation fields

Every log, metric, trace, and telemetry event includes available safe identifiers: `workflow_id`, `job_id`, `agent_run_id`, `object_type`, `object_id`, `agent_id`, `job_type`, `attempt`, and effect/idempotency reference. Provider IDs appear only when safe; credentials and payloads never appear.

## Domain events versus PostHog

| Durable domain event | PostHog observation |
|---|---|
| workflow creation | `workflow_started` |
| job claim/completion/failure | `job_started`, `job_completed`, `job_failed` |
| agent run start/completion | `agent_run_started`, `agent_run_completed` |
| `RESEARCH_COMPLETED` | `research_completed` |
| `PRODUCT_QUALIFIED` | `product_qualified` |
| `DEDUPE_FAILED` | `dedupe_failed` |
| `BUILD_COMPLETED` | `build_completed` |
| QA failure events | `qa_failed` |
| `ASSETS_COMPLETED` | `assets_completed` |
| `DRAFT_CREATED` | `draft_created` |
| publish attempt/result | `publish_started`, `publish_completed`, `publish_failed` |
| `METRICS_CAPTURED` | `metrics_collected` |
| `WINNER_DETECTED` | `winner_detected` |
| `LISTING_CULLED` | `listing_culled` |
| `SUCCESSOR_CREATED` | `successor_created` |
| incident open/repair | `incident_opened`, `incident_resolved` |
| typed human blocker | `human_intervention_required` |

PostHog dispatch occurs after the durable transaction and is idempotent/best effort. Missing telemetry does not roll back business state; duplicate telemetry does not duplicate jobs.

## Required operational metrics

- jobs by status, type, owner, and age;
- ready-queue latency and oldest ready job;
- running leases, heartbeat age, expiries, and recovery outcomes;
- attempts, terminal failures, blocked jobs, and uncertain effects;
- dependency wait time and successor creation failures;
- agent-run duration, schema failures, model/provider errors, and token/cost fields when safely available;
- adapter latency/error/reconciliation by operation and channel;
- publication/deactivation/spend cap reservations and reconciled totals;
- artifact render duration, hash/QA failures, and storage errors;
- weekly metrics freshness and maturity-decision backlog;
- open incidents, broken links, credential blockers, and repair age.

## Alerts and operator exceptions

Alert only on actionable durable conditions: oldest ready job above threshold, lease recovery loop, terminal job failure, unreconciled effect, stale credentials, cap/config contradiction, failed backup, metrics overdue, broken published link, or incident age. Normal internal retries within budget do not create repeated operator noise.

## Logging and privacy

Logs are structured JSON in production and concise human-readable text in local development. Redaction occurs before serialization. Never log:

- credentials, authorization headers, cookies, browser-profile data, bank/payment identity;
- private PDF content or customer/provider payload bodies;
- full prompts/results when they may contain provider or customer data;
- signed/secret delivery URLs except opaque references;
- raw runtime receipts or screenshots.

Errors expose stable codes and safe detail. Full denied evidence is referenced by opaque ID/digest and retention policy.

## Retention

Workflow/events/lineage follow business retention and backup policy. High-volume logs/traces/telemetry use shorter configurable retention. Deleting operational telemetry never deletes canonical jobs, decisions, artifacts, incidents, or effect receipts.