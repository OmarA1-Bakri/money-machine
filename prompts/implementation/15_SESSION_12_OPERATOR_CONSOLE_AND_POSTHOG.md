# SESSION 12 — OPERATOR CONSOLE AND POSTHOG TELEMETRY

Execute under the Master Control Prompt and recovery protocol.

## Objective

Build a compact exception-led operator console and connect PostHog operational telemetry. The interface must make the machine understandable without turning Omar into its dispatcher.

## Actions

### 1. API completion

Expose typed endpoints for:

- current shop;
- workflows;
- pipeline stages;
- ready/running/blocked jobs;
- products and variants;
- listing state;
- weekly metrics;
- decisions;
- incidents;
- integration status;
- autonomy settings;
- milestone progress;
- system health.

Use pagination and stable schemas.

### 2. Operator console structure

Build the Next.js console with these views.

#### NOW

- what is running;
- recent completions;
- next scheduled work;
- whether action is required.

#### PIPELINE

- product experiments by stage;
- blocked dependency;
- current owning agent;
- elapsed time;
- next transition.

#### SHOP

- active/draft/deactivated listings;
- age;
- views;
- favourites;
- sales;
- current decision;
- next review time.

#### BLOCKED

Only real blockers:

- credentials;
- account verification;
- CAPTCHA/provider challenge;
- configured spend limit;
- uncertain external effect.

#### DECISIONS

Show:

- hold;
- repair;
- cull;
- multiply;
- successor created;
- evidence and status.

Do not turn routine automated decisions into approval requests.

#### INCIDENTS

- buyer issue;
- severity;
- current repair step;
- response status;
- resolution evidence.

#### SETTINGS

- autonomy mode;
- publication cap;
- purchase caps;
- loop day;
- PostHog connection;
- provider status.

### 3. Design requirements

Use Product Design to create a clear, dense, professional interface.

Requirements:

- desktop-first but responsive;
- no decorative dashboard clutter;
- no vanity charts;
- status and exceptions visible immediately;
- one-screen summary;
- accessible labels and keyboard behaviour;
- deterministic empty/loading/error states.

### 4. Live updates

Use simple polling or server-sent events. Do not add a separate real-time platform unless already present.

### 5. PostHog integration

Implement server and web telemetry for the event taxonomy in the Master Control Prompt.

Include properties:

- workflow ID;
- job type;
- agent ID;
- product/listing ID where appropriate;
- duration;
- attempt;
- status;
- environment;
- autonomy mode;
- error classification.

Do not send:

- secrets;
- browser cookies;
- private competitor files;
- raw buyer messages;
- sensitive personal data.

### 6. Operational metrics

Create PostHog insights or documented queries for:

- workflow completion rate;
- job failure rate;
- agent failure rate;
- human intervention count;
- mean research-to-draft time;
- draft-to-publish time;
- QA rejection rate;
- retry count;
- stalled workflows;
- winner detection;
- culls;
- automatic successor creation;
- incident resolution time;
- automation percentage.

Etsy remains the canonical source for shop commerce data.

### 7. Operator actions

Allow only practical actions:

- inspect;
- retry eligible failed job;
- reconcile uncertain effect;
- supply credential status;
- pause/resume workflow;
- change standing-authority settings;
- manually create customer issue;
- trigger safe schedule run.

Do not expose arbitrary database editing.

### 8. Tests

Prove:

- API schema;
- auth boundary if configured;
- each page renders;
- empty/error states;
- workflow detail;
- blocked item;
- incident flow;
- settings validation;
- telemetry event shape;
- secrets excluded;
- browser E2E navigation;
- accessibility smoke;
- no routine approval queue.

### 9. Review and checkpoint

Use product-design, frontend and observability reviewers. Fix findings.

Commit:

```text
feat(console): add operator UI and PostHog telemetry
```

## Exit criteria

- Operator can understand current system state quickly.
- Console does not require manual orchestration.
- PostHog receives useful operational events.
- Sensitive data is excluded.
- UI and browser tests pass.
- Control files and commit are current.

## Required exit code

```text
SESSION_12_OPERATOR_CONSOLE_COMPLETE
```

Next prompt:

```text
16_SESSION_13_E2E_HARDENING_AND_FAILURE_RECOVERY.md
```
