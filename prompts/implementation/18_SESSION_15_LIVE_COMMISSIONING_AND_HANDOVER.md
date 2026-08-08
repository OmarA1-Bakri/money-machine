# SESSION 15 — LIVE ACCOUNT COMMISSIONING, FULL ACCEPTANCE AND HANDOVER

Execute under the Master Control Prompt and recovery protocol.

## Objective

Connect the real provider accounts, commission live autonomy, run the first real linked workflow to the furthest authorised external state and complete operational handover.

No new architecture is allowed in this session unless a verified defect requires it.

## Actions

### 1. Confirm deployed exact state

Read control files and verify:

- deployed commit;
- service versions;
- database migration;
- all agent commissioning states;
- full test results;
- open credential blockers;
- configured autonomy mode.

Run production smoke tests.

### 2. Connect LLM provider

Configure and verify:

- provider credentials;
- structured-output call;
- model selection;
- prompt-version logging;
- usage/cost capture;
- redaction.

Run one harmless agent contract smoke.

### 3. Connect Notion

Through the Account & Integration Agent and browser/API adapters:

- authenticate;
- identify the correct workspace;
- verify create/read/update/publish;
- verify persistent browser profile;
- clean temporary test page.

### 4. Connect Etsy

- authenticate OAuth/browser;
- identify shop;
- verify shop status;
- verify draft/read capability;
- verify media/file capability;
- verify stats read;
- verify message path where available;
- clean test draft if one is created.

Do not publish a meaningless test listing.

### 5. Connect Composio and PostHog

- record available actions;
- connect only useful integrations;
- verify PostHog server and web events;
- confirm sensitive fields are absent.

### 6. Configure standing authority once

Set the production values with Omar only where values are genuinely absent:

```text
mode
auto_publish
auto_deactivate
auto_multiply
weekly_listing_cap
competitor_purchase_enabled
competitor_purchase_max_each
competitor_purchase_monthly_cap
live_checkout_test_enabled
live_checkout_test_cap
paid_tool_monthly_cap
weekly_loop_day
```

Ask for all missing values in one compact request, not repeated approvals.

After configuration, routine work inside bounds proceeds automatically.

### 7. Run the first real workflow

Execute:

```text
live Etsy research
→ shortlist
→ Low-Ticket score
→ primary and backup
→ competitor teardown path
→ ProductSpec
→ dedupe
→ live Notion build
→ QA
→ variants
→ listing copy
→ assets
→ PDFs
→ Etsy draft
→ preflight
```

If production authority has `auto_publish: true` and the ramp permits it:

```text
→ publish
→ post-publish verify
→ weekly schedule
→ thirty-day maturity schedule
```

If a real paid competitor purchase or checkout test is enabled within cap, execute it. If not enabled, the workflow must use the configured non-purchase path or stop only that exact job while continuing everything else.

### 8. Verify operational autonomy

Prove from runtime state:

- no manual copy/paste occurred;
- every successor job was created automatically;
- artifacts are versioned;
- provider receipts exist;
- current workflow can resume after restart;
- weekly metrics job is scheduled;
- maturity trigger exists;
- incident path is ready;
- console reflects reality;
- PostHog records the run.

### 9. Final acceptance matrix

Mark every definition-of-done item from the Master Control Prompt:

```text
PASS
FAIL
BLOCKED_EXTERNAL
```

No item may be silently omitted.

Resolve every `FAIL`.

A `BLOCKED_EXTERNAL` item is allowed only for an exact account-holder or provider action that ChatGPT cannot perform and that does not invalidate the implemented system.

### 10. Final documentation and handover

Update:

- README;
- architecture;
- runbooks;
- integration status;
- agent roster;
- test evidence;
- control state.

Create:

```text
docs/FINAL_HANDOVER.md
docs/FINAL_ACCEPTANCE.md
```

Include:

- system purpose;
- exact deployed location;
- service commands;
- console URL;
- current autonomy settings;
- connected accounts;
- first workflow result;
- scheduled jobs;
- backup status;
- remaining external blockers;
- how to pause/resume;
- how to inspect a failure;
- how to update.

### 11. Final review and release

Run the complete quality suite again.

Use an independent final reviewer to compare:

- playbook;
- architecture;
- implementation;
- runtime;
- first real workflow;
- definition of done.

Fix every material mismatch.

Commit:

```text
chore(release): commission hands-off money machine
```

Tag:

```text
v1.0.0
```

Push private remote.

Update `IMPLEMENTATION_STATE.json`:

```text
current_session = 15
completed_sessions = [0..15]
next_session = null
status = COMMISSIONED
```

## Required final exit code

Use only when the implementation and commissioned runtime support the complete linked workflow:

```text
HANDS_OFF_MONEY_MACHINE_COMMISSIONED
```

The final response must include:

```text
HANDS_OFF_MONEY_MACHINE_COMMISSIONED

Repository:
Branch:
Commit:
Release:
Deployment:
Console:

Live workflow:
- current stage
- product/listing identifiers
- schedules created

Verification:
- complete test summary
- provider connection summary
- backup/restore status

External blockers:
- none
or exact non-implementation account/provider actions
```
