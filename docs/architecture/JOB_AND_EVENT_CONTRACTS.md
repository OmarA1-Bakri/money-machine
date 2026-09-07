# Job and Event Contracts

**Contract status:** Session 01 canonical contract vocabulary. Pydantic code and transition tests must match this document.

## Job envelope

Every job carries:

| Field | Contract |
|---|---|
| `schema_version` | literal `1` |
| `job_id`, `workflow_id`, `object_id` | UUID |
| `job_type`, `object_type` | non-empty canonical names |
| `owner_agent_id` | `A01`–`A16` |
| `status` | durable `JobStatus` |
| `input` | JSON-compatible payload validated again by the owner contract |
| `required_artifacts` | immutable `ArtifactReference[]` |
| `scheduled_at` | timezone-aware UTC datetime |
| `attempt`, `max_attempts` | non-negative / positive with `attempt <= max_attempts` |
| `idempotency_key` | non-empty stable semantic key |
| `side_effect_class` | `SideEffectClass` |
| `retry_class` | `RetryClass` |
| `success_contract` | typed required output/artifact/event declaration |

## Durable job states

```text
PENDING → BLOCKED | READY | CANCELLED
BLOCKED → READY | CANCELLED
READY → RUNNING | CANCELLED
RUNNING → SUCCEEDED | FAILED | BLOCKED | UNCERTAIN_EXTERNAL_EFFECT
FAILED → READY | TERMINAL_FAILURE
UNCERTAIN_EXTERNAL_EFFECT → SUCCEEDED | FAILED | BLOCKED
```

- `PENDING`: created but schedule/dependency evaluation is incomplete.
- `BLOCKED`: waiting on dependency, credential, holder challenge, or declared external blocker.
- `READY`: due and all dependencies/success inputs are present.
- `RUNNING`: owned by one live lease.
- `SUCCEEDED`: success contract, outputs, and events committed.
- `FAILED`: attempt failed and retry policy is being evaluated.
- `TERMINAL_FAILURE`: retry budget or non-retryable contract exhausted.
- `CANCELLED`: explicitly abandoned before effect execution.
- `UNCERTAIN_EXTERNAL_EFFECT`: provider outcome is ambiguous and ordinary retry is prohibited.

## Agent result

An agent returns:

- `schema_version`, `job_id`, and `agent_run_id`;
- the acting `agent_id`, its `agent_definition_version`, and the `prompt_reference` with its `prompt_sha256`;
- terminal `AgentRunStatus`: `SUCCESS`, `FAILURE`, `BLOCKED`, or `UNCERTAIN_EXTERNAL_EFFECT`;
- JSON-compatible output;
- artifact and evidence references;
- emitted domain events;
- effect references for any attempted external effect;
- optional structured error.

`SUCCESS` forbids an error and must satisfy the job success contract. Every other status requires a structured error/blocker. An event is not accepted until result validation and persistence succeed.

## Side effects and retries

| Effect class | Meaning | Default retry requirement |
|---|---|---|
| `NONE` | Pure/internal durable computation | `SAFE` |
| `EXTERNAL_READ` | Provider observation without mutation | `SAFE` with bounded backoff |
| `EXTERNAL_WRITE` | Draft, publish, update, deactivate, Notion mutation | `IDEMPOTENT` or `RECONCILE_FIRST` |
| `EXTERNAL_SPEND` | Purchase or checkout | `RECONCILE_FIRST`; cap reservation required |
| `EXTERNAL_MESSAGE` | Customer/proof-recipient communication | `RECONCILE_FIRST`; recipient authority required |

| Retry class | Contract |
|---|---|
| `SAFE` | Re-execution cannot create an additional external effect |
| `IDEMPOTENT` | Stable key and provider/internal idempotency record prevent duplicate effect |
| `RECONCILE_FIRST` | Query persisted/provider state before deciding success or retry |
| `MANUAL_RESUME` | Resume only after account-holder challenge/action is recorded |
| `NEVER` | Terminal failure; create repair/reconcept/incident work instead |

## Reconciliation of uncertain external effects

`UNCERTAIN_EXTERNAL_EFFECT` means the provider outcome is unknown, so ordinary retry is prohibited until the effect is resolved. Resolution is a read, never a repeat of the mutation.

1. The owning agent's adapter performs `reconcile(idempotency_key, effect_reference)` as an `EXTERNAL_READ`.
2. The adapter returns an `EffectReference` whose `effect_state` is `CONFIRMED`, `ABSENT`, or `UNKNOWN`, and the worker persists it against the job's idempotency record inside the completion transaction.
3. `CONFIRMED` moves the job to `SUCCEEDED` using the recorded provider object; the mutation is never repeated.
4. `ABSENT` moves the job to `FAILED`, which is retry eligible under its retry class.
5. `UNKNOWN` increments `reconciliation_attempt`. Once the configured attempt budget is exhausted the job moves to `BLOCKED` and opens an incident of type `UNCERTAIN_EXTERNAL_EFFECT` naming the operation and the exact operator action.

An `AgentResult` with status `UNCERTAIN_EXTERNAL_EFFECT` must carry the unresolved `EffectReference`; the contract rejects a result that claims uncertainty without citing the effect.

## Idempotency keys

Keys are derived, never random, so a replay after a crash reproduces the same key.

| Job | Key template |
|---|---|
| `BootstrapRecordsJob` | `NOTION_SHOP_HQ_WRITE:{shop_id}` |
| `CompetitorPurchaseJob` | `COMPETITOR_PURCHASE:{candidate_id}` |
| `ProductBuildJob`, `BuildRepairJob` | `NOTION_PRODUCT_WRITE:{spec_id}:{build_version}` |
| `VariantBuildJob` | `NOTION_VARIANT_WRITE:{product_id}:{variant_name}:{build_version}` |
| `VariantPublishJob` | `NOTION_LINK_PUBLISH:{variant_id}:{build_version}` |
| `DraftListingJob` | `ETSY_DRAFT_WRITE:{listing_package_id}` |
| `ListingRepairJob`, `NotionRepairJob` | `{operation}:{incident_id}:{attempt_of_record}` |
| `PublishListingJob` | `ETSY_PUBLISH:{listing_version_id}` |
| `PostPublishVerificationJob` | `ETSY_POST_PUBLISH_CHECKOUT:{listing_version_id}` |
| `DeactivateListingJob` | `ETSY_DEACTIVATE:{etsy_listing_id}:{decision_id}` |
| `ProofDistributionJob` | `PROOF_DISTRIBUTION:{listing_version_id}:{recipient_scope_id}` |
| provisioning jobs | `{operation}:{shop_id}` |

The key's scope is the tuple that makes the effect unique, so a legitimate second effect (a new listing version, a new build version, a new decision) produces a new key while a retry of the same intent does not.

## Branch, decision, and incident taxonomies

- `BranchOutcome` contains `PASS`, `FAIL`, and `TOO_CLOSE`; it selects an edge and is never persisted as lifecycle state.
- `DecisionType` contains `HOLD`, `REPAIR`, `CULL`, and `MULTIPLY`.
- `IncidentType` contains `BROKEN_LINK`, `CUSTOMER_ISSUE`, `BUILD_DEFECT`, `LISTING_DEFECT`, `CREDENTIAL_FAILURE`, `PROVIDER_MISMATCH`, `TERMINAL_JOB_FAILURE`, and `UNCERTAIN_EXTERNAL_EFFECT`.

An incident records its type, affected object/version, opening event/job, safe detail, evidence references, status, resolution job/result, and UTC timestamps. A credential or provider incident never stores a secret or private payload.

## Required domain events

| Event | Producing result | Typical successor |
|---|---|---|
| `ACCOUNT_CONNECTED` | integration readiness | bootstrap/research work |
| `RESEARCH_COMPLETED` | `ResearchReport` | shortlist |
| `NICHE_SHORTLISTED` | candidate shortlist | qualification |
| `PRODUCT_QUALIFIED` | score at or above threshold | niche selection |
| `PRODUCT_REJECTED` | score below threshold | terminal candidate result |
| `TEARDOWN_COMPLETED` | `TeardownReport` | ProductSpec |
| `PRODUCT_SPEC_CREATED` | `ProductSpec` | dedupe |
| `DEDUPE_PASSED` | passing `DedupeResult` | build |
| `DEDUPE_FAILED` | failing `DedupeResult` | reconcept |
| `BUILD_COMPLETED` | `BuildResult` | product QA |
| `BUILD_QA_PASSED` | passing `ProductQAResult` | variant build |
| `BUILD_QA_FAILED` | failed `ProductQAResult` | build repair |
| `VARIANTS_COMPLETED` | variant `BuildResult` | link verification/assets |
| `ASSETS_COMPLETED` | media/delivery build | draft/preflight |
| `DRAFT_CREATED` | draft listing package | preflight |
| `PREFLIGHT_PASSED` | passing `PreflightResult` | publish |
| `PREFLIGHT_FAILED` | failed `PreflightResult` | listing repair |
| `LISTING_PUBLISHED` | reconciled publication | post-publish verification |
| `POST_PUBLISH_VERIFIED` | buyer/fresh-view verification | observation/weekly review |
| `METRICS_CAPTURED` | `MetricsSnapshot` | maturity/portfolio decision |
| `LISTING_MATURED` | 30 accumulated live days | portfolio decision |
| `LISTING_HELD` | `PortfolioDecision(HOLD)` | next review |
| `LISTING_REPAIR_REQUESTED` | `PortfolioDecision(REPAIR)` or defect | repair incident |
| `LISTING_CULLED` | reconciled deactivation | build-slot evaluation |
| `WINNER_DETECTED` | `PortfolioDecision(MULTIPLY)` | successor creation |
| `SUCCESSOR_CREATED` | new workflow/spec lineage | dedupe |
| `CUSTOMER_ISSUE_RECEIVED` | issue intake | incident triage |
| `BROKEN_LINK_DETECTED` | failed link check | incident repair |
| `REPAIR_APPLIED` | repair job's persisted effect receipt (unverified) | verifying QA/preflight/link check |
| `REPAIR_COMPLETED` | verified repair result emitted by the verifier | incident closure; resume lifecycle |
| `JOB_FAILED` | terminal job failure | incident/operator exception |
| `JOB_STALLED` | lease/recovery signal | safe retry or reconciliation |
| `CREDENTIAL_REQUIRED` | missing/expired access | holder action blocker |
| `ENVIRONMENT_AUDITED` | safe runtime/capability inventory | next provisioning check |
| `SHOP_BOOTSTRAPPED` | canonical shop records and schedule | research collection |
| `NICHE_SELECTED` | primary/backup niche decision | competitor acquisition/teardown |
| `COMPETITOR_PURCHASED` | capped, reconciled purchase receipt | teardown |
| `VARIANT_LINKS_VERIFIED` | isolated duplicable link receipts | screenshot capture |
| `SCREENSHOTS_CAPTURED` | truthful screenshot artifact set | copy and asset factory |
| `LISTING_COPY_COMPLETED` | validated copy fields and claim evidence | pricing/draft assembly |
| `DELIVERY_FILES_COMPLETED` | link-tested delivery artifacts | package/preflight |
| `PRICING_COMPLETED` | bounded price decision | draft assembly |
| `PROOF_FEEDBACK_CAPTURED` | consented proof-recipient feedback | repair or weekly review |
| `SCHEDULE_CONFIGURED` | idempotent recurring trigger | scheduled review |
| `BUILD_SLOT_DEFERRED` | no eligible/cap-admitted work now | deterministic reevaluation |
| `MONTHLY_REVIEW_COMPLETED` | fresh monthly evidence and catalogue review | research/build-slot work |
| `SCALE_DECIDED` | evidence-backed capacity decision | build slot or next review |
| `LISTING_CULL_REQUESTED` | `PortfolioDecision(CULL)` | separately authorized deactivation |

This table is the canonical initial `EventName` vocabulary. Adding an event requires updating the enum, producing-result contract, successor mapping, and affected tests together.

## Atomic completion

A successful job transaction:

1. verifies current lease and expected job version;
2. validates `AgentResult` and the success contract;
3. persists the agent run (with its definition version and prompt version), output, artifacts, evidence links, and effect references;
4. moves the job to `SUCCEEDED`;
5. appends deduplicated domain events;
6. releases dependencies and creates deterministic successors;
7. commits once.

If any step fails, none of them commit. Provider effects already attempted remain represented by the idempotency/effect record and may require reconciliation.

## Event envelope

Each event includes UUID, canonical event name, aggregate type/ID, workflow/job/agent-run IDs, UTC occurrence time, schema version, JSON-compatible payload, evidence/artifact references, and a semantic dedupe key. Telemetry events are emitted after durable commit and cannot create successors.