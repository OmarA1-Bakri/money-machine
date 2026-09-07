# State Machine

**Contract status:** Session 01 executable design. `ProductLifecycleState`, branch-result enums, and transition tables must match this document exactly.

## Product lifecycle

```mermaid
stateDiagram-v2
    [*] --> DISCOVERED
    DISCOVERED --> RESEARCHING
    RESEARCHING --> RESEARCH_COMPLETE
    RESEARCH_COMPLETE --> QUALIFYING
    QUALIFYING --> QUALIFIED: qualified
    QUALIFYING --> REJECTED: below threshold
    QUALIFIED --> TEARDOWN_PENDING
    TEARDOWN_PENDING --> TEARDOWN_COMPLETE
    TEARDOWN_COMPLETE --> SPEC_READY
    SPEC_READY --> DEDUPE_CHECK
    DEDUPE_CHECK --> RECONCEPTING: TOO_CLOSE
    RECONCEPTING --> SPEC_READY
    DEDUPE_CHECK --> BUILDING: PASS
    BUILDING --> BUILD_QA
    BUILD_QA --> BUILD_REPAIR: FAIL
    BUILD_REPAIR --> BUILD_QA
    BUILD_QA --> VARIANT_BUILD: PASS
    VARIANT_BUILD --> VARIANT_QA
    VARIANT_QA --> VARIANT_BUILD: FAIL
    VARIANT_QA --> MERCHANDISING: PASS
    MERCHANDISING --> ASSET_BUILD
    ASSET_BUILD --> ASSET_QA
    ASSET_QA --> ASSET_BUILD: FAIL
    ASSET_QA --> DRAFTING: PASS
    DRAFTING --> DRAFT_READY
    DRAFT_READY --> PREFLIGHT
    PREFLIGHT --> LISTING_REPAIR: FAIL
    LISTING_REPAIR --> PREFLIGHT
    PREFLIGHT --> READY_TO_PUBLISH: PASS
    READY_TO_PUBLISH --> PUBLISHED
    PUBLISHED --> POST_PUBLISH_QA
    POST_PUBLISH_QA --> INCIDENT_REPAIR: FAIL
    INCIDENT_REPAIR --> POST_PUBLISH_QA
    POST_PUBLISH_QA --> OBSERVING: PASS
    OBSERVING --> MATURE: 30 accumulated live days
    MATURE --> EVALUATING
    EVALUATING --> OBSERVING: HOLD
    EVALUATING --> REPAIRING: REPAIR
    REPAIRING --> OBSERVING
    EVALUATING --> DEACTIVATING: CULL
    DEACTIVATING --> DEACTIVATED
    EVALUATING --> SUCCESSOR_SPEC: MULTIPLY
    SUCCESSOR_SPEC --> OBSERVING: winner keeps selling
    state "new workflow" as NewWorkflow {
        [*] --> DEDUPE_CHECK
    }
    SUCCESSOR_SPEC --> NewWorkflow: spawn successor (distinct workflow_id)
    REJECTED --> [*]
    DEACTIVATED --> [*]
```

`REJECTED` is the terminal result for an unqualified candidate. `DEACTIVATED` is terminal for that listing version, not deletion of product lineage. Provider ambiguity is represented in job/agent-run status; it never invents a product lifecycle transition.

## Transition contract

- Only edges in the immutable transition table are valid.
- Branch results (`PASS`, `FAIL`, `TOO_CLOSE`) and portfolio decisions (`HOLD`, `REPAIR`, `CULL`, `MULTIPLY`) select edges; they are not product states.
- A transition records source state, target state, causing job, event, evidence references, and UTC time.
- No transition occurs until the causing job and its declared success contract commit.
- Failed or blocked agent runs leave product state unchanged unless an explicit failure edge exists.
- `RECONCEPTING` creates a new ProductSpec version in the same pre-build workflow.
- `SUCCESSOR_SPEC` creates a new ProductSpec and workflow identity with parent lineage; the winner returns to `OBSERVING`. The only same-workflow edge out of `SUCCESSOR_SPEC` is to `OBSERVING`; `require_successor_spawn` authorizes the cross-workflow entry of the successor at `DEDUPE_CHECK` and rejects a successor whose `workflow_id` equals the parent's.

## Core job dependency flow

```mermaid
flowchart TD
    Research[ResearchCollectionJob] --> Shortlist[ShortlistJob]
    Shortlist --> Qualify[QualificationJob]
    Qualify -->|qualified| Select[NicheSelectionJob]
    Qualify -->|rejected| Stop[Terminal rejection]
    Select --> Purchase[CompetitorPurchaseJob]
    Purchase --> Teardown[TeardownJob]
    Teardown --> Spec[ProductSpecJob]
    Spec --> Dedupe[DedupeJob]
    Dedupe -->|failed| Reconcept[ReconceptProductJob]
    Reconcept --> Spec
    Dedupe -->|passed| Build[ProductBuildJob]
    Build --> ProductQA[ProductQAJob]
    ProductQA -->|failed| BuildRepair[BuildRepairJob]
    BuildRepair --> ProductQA
    ProductQA -->|passed| Variant[VariantBuildJob]
    Variant --> VariantPublish[VariantPublishJob]
    VariantPublish --> Screenshot[ScreenshotJob]
    Screenshot --> Copy[ListingCopyJob]
    Screenshot --> Media[AssetFactoryJob]
    VariantPublish --> Delivery[DeliveryBuildJob]
    Copy --> Draft[DraftListingJob]
    Delivery --> Draft
    Media --> Draft
    Draft --> Preflight[PreflightJob]
    Preflight -->|failed| ListingRepair[ListingRepairJob]
    ListingRepair --> Preflight
    Preflight -->|passed| Publish[PublishListingJob]
    Publish --> Verify[PostPublishVerificationJob]
    Verify -->|failed| Incident[IncidentRepairJob]
    Incident --> Verify
    Verify --> Weekly[WeeklyReviewJob]
    Weekly --> Decision[PortfolioDecisionJob]
```

## Cull and multiply closed loop

```mermaid
flowchart TD
    Metrics[MetricsSnapshot + live duration] --> Defect{Defect?}
    Defect -->|yes| Repair[IncidentRepairJob]
    Repair --> Observe[OBSERVING]
    Defect -->|no| Mature{30 live days?}
    Mature -->|no| Observe
    Mature -->|yes| Decide[PortfolioDecisionJob]
    Decide -->|HOLD| Observe
    Decide -->|REPAIR| Repair
    Decide -->|CULL| Deactivate[DeactivateListingJob]
    Deactivate --> Reconcile{Provider reconciled?}
    Reconcile -->|yes| Deactivated[DEACTIVATED]
    Reconcile -->|unknown| Uncertain[UNCERTAIN_EXTERNAL_EFFECT]
    Decide -->|MULTIPLY| Successor[SuccessorProductJob]
    Successor --> NewWorkflow[New workflow + ProductSpec + parent lineage]
    NewWorkflow --> Dedupe[DedupeJob]
    Dedupe -->|failed| Reconcept[ReconceptProductJob]
    Reconcept --> RevisedSpec[ProductSpecJob creates revised spec]
    RevisedSpec --> Dedupe
    Dedupe -->|passed| Build[ProductBuildJob]
```

## Broken-link incident repair

```mermaid
sequenceDiagram
    participant Check as LinkVerificationJob
    participant DB as PostgreSQL
    participant Repair as A16 Repair Agent
    participant Owner as A07/A08/A13 effect owner
    participant Provider as Provider adapter
    participant QA as LinkVerificationJob / PreflightJob

    Check->>DB: persist BROKEN_LINK_DETECTED and incident
    DB->>Repair: unlock IncidentRepairJob
    Repair->>Provider: read/reconcile current link state
    Repair->>DB: persist diagnosis and replacement artifact if required
    Repair->>DB: create incident-scoped NotionRepairJob or ListingRepairJob
    DB->>Owner: unlock job for the exclusive mutation owner
    alt effect is safe and authorized
        Owner->>Provider: replace source link/file using idempotency key
        Owner->>DB: persist new artifact/listing version and effect receipt; emit REPAIR_APPLIED
        DB->>QA: create verification successor
        QA->>Provider: fresh-view and click verification
        QA->>DB: emit REPAIR_COMPLETED; close incident
    else credentials/challenge/uncertain effect
        Owner->>DB: BLOCKED or UNCERTAIN_EXTERNAL_EFFECT
        DB-->>Owner: resume only after holder action or reconciliation
    end
```

## Terminal guarantees

| Branch | Required durable result | Successor |
|---|---|---|
| Qualification rejection | Score and cited rejection | none for candidate |
| Dedupe failure | `DedupeResult` with collisions | `ReconceptProductJob` |
| QA/preflight failure | Structured defects | matching repair job |
| `HOLD` | `PortfolioDecision` | next scheduled review |
| `REPAIR` | `PortfolioDecision` and incident/defects | repair then observation |
| `CULL` | `PortfolioDecision` and reconciliation evidence | deactivation |
| `MULTIPLY` | `PortfolioDecision`, parent lineage, successor spec | new workflow at dedupe |
| Uncertain external effect | effect reference and reconciliation requirement | no ordinary retry |