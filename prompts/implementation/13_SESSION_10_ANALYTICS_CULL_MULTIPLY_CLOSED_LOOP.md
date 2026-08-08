# SESSION 10 — ANALYTICS, THIRTY-DAY MATURITY, CULL AND MULTIPLY CLOSED LOOP

Execute under the Master Control Prompt and recovery protocol.

## Objective

Complete the business loop. Implement weekly metrics, thirty-day maturity, mature-listing diagnosis, culling, winner multiplication, monthly deep pass and automatic successor-product execution.

This session is the central proof that the system is autonomous rather than a listing generator.

## Actions

### 1. Implement metrics collection

Collect and persist, per listing:

- publish date;
- days live;
- weekly views;
- weekly favourites;
- weekly sales/orders;
- cumulative views;
- cumulative favourites;
- cumulative sales/orders;
- any additional Etsy stats available;
- collection timestamp;
- provider evidence.

Do not replace the playbook's scorecard; extend it only where useful.

### 2. Implement weekly scheduler

On the configured loop day:

- create one collection job per active listing;
- create one shop review job after all collection jobs complete;
- suppress duplicate weekly runs;
- preserve historical snapshots;
- emit `METRICS_CAPTURED`.

### 3. Implement A14 Analytics Agent

Rules:

- under thirty days: `TOO_YOUNG`, no demand verdict;
- defects may be flagged immediately;
- mature listings are ranked;
- low visibility diagnosis targets title/tags/niche;
- views without sales diagnosis targets price/hero/description;
- evidence must reference actual metrics.

Return:

```text
TOO_YOUNG
HOLD
REPAIR
CULL_CANDIDATE
MULTIPLY_CANDIDATE
```

### 4. Implement maturity scheduling

Publication creates one durable trigger at:

```text
published_at + 30 days
```

On maturity:

- mark listing mature;
- collect fresh metrics;
- create evaluation job;
- never depend on an in-memory delay.

### 5. Implement A15 Cull & Multiply Agent

Apply the playbook's configured portfolio rules.

#### Cull

- rank mature listings;
- identify bottom performers;
- support default bottom-80-percent discipline;
- create deactivation jobs;
- log the experiment lesson;
- retain data and artifacts;
- emit `LISTING_CULLED`.

#### Multiply

Generate one or more specific successor proposals:

- close identity variant;
- new palette;
- adjacent category;
- genuinely different section mix;
- fresh-niche experiment.

Each proposal must become a versioned ProductSpec candidate and pass dedupe.

A `MULTIPLY` decision must automatically create:

```text
CREATE_SUCCESSOR_SPEC
→ CHECK_DEDUPE
→ BUILD_NOTION_TEMPLATE
```

Do not stop at a recommendation report.

### 6. Maintain exploration

For each production batch:

- prioritise variants of proven winners;
- reserve approximately one slot for a new-front experiment from fresh research;
- keep publication inside the ramp.

### 7. Implement monthly deep pass

Every fourth weekly loop:

- full mature-listing cull review;
- fresh mini-research;
- seasonal look-ahead;
- discount/price review;
- milestone update;
- new-front candidate creation.

This must create jobs automatically.

### 8. Implement milestone tracking

Persist:

- accounts connected;
- first niche selected;
- teardown complete;
- first template complete;
- first listing live;
- checkout test complete if enabled;
- first favourite;
- first sale;
- first review;
- first cull;
- first multiplied winner;
- first £100 total;
- first month under one hour of operator intervention where measurable.

### 9. Closed-loop E2E tests

Simulate:

#### Winner path

```text
published
→ weekly metrics
→ 30 days
→ winner detected
→ successor ProductSpec
→ dedupe pass
→ new build job
```

#### Loser path

```text
published
→ 30 days
→ cull
→ deactivation job
→ deactivated
→ lesson persisted
```

#### Hold path

```text
mature
→ hold
→ future weekly collection remains scheduled
```

#### Repair path

```text
mature
→ conversion issue
→ listing repair
→ re-observe
```

Prove no manual intervention is required.

### 10. Commission agents

Mark A14 and A15 commissioned after complete tests.

### 11. Review and checkpoint

Use analytics, workflow and commercial-logic reviewers. Their job is to verify faithful playbook implementation and automatic successor work, not to replace the rules with a new methodology.

Commit:

```text
feat(loop): automate metrics culling and winner multiplication
```

## Exit criteria

- Weekly and monthly loops run from durable schedules.
- Thirty-day maturity is automatic.
- Mature listings reach an executable decision.
- Cull deactivates.
- Multiply launches a successor workflow.
- Exploration is retained.
- Agents are commissioned.
- Closed-loop E2E tests pass.
- Control files and commit are current.

## Required exit code

```text
SESSION_10_CLOSED_LOOP_AUTOMATION_COMPLETE
```

Next prompt:

```text
14_SESSION_11_CUSTOMER_SUPPORT_AND_REPAIR.md
```
