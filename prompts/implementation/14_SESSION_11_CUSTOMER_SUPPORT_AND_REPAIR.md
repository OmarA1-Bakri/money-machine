# SESSION 11 — CUSTOMER SUPPORT, INCIDENTS AND AUTOMATED REPAIR

Execute under the Master Control Prompt and recovery protocol.

## Objective

Implement the troubleshooting and customer-support side of the playbook as linked incident workflows. Buyer issues must create reproducible repairs, update the original product/listing and close with verified resolution.

## Actions

### 1. Implement customer issue intake

Support intake through:

- Etsy messages where accessible;
- manual/API issue creation;
- operator console;
- webhook or polling where available.

Persist:

- buyer/message reference;
- listing;
- product;
- variant;
- issue text;
- attachments;
- received time;
- urgency;
- current status.

Never expose credentials or unrelated buyer data in logs.

### 2. Implement incident classification

Classify:

```text
BROKEN_DELIVERY_LINK
NOTION_PAGE_UNPUBLISHED
WRONG_VARIANT_LINK
NO_ACCESS_BLOCK
LINKED_VIEW_BROKEN
FORMULA_ERROR
DOWNLOAD_FILE_MISSING
LISTING_DEACTIVATED
ACCOUNT_VERIFICATION
DEDUPE_REJECTION
AGENT_RUN_INTERRUPTED
NO_SALES_DIAGNOSIS
OTHER_PRODUCT_DEFECT
```

Create the appropriate repair workflow automatically.

### 3. Implement A16 Customer Support & Repair Agent

The agent must:

- reproduce the reported problem;
- inspect the original product/listing;
- form one hypothesis at a time;
- execute or route the source repair;
- update the original published artifact;
- verify with a fresh view/duplicate;
- update the Etsy listing where required;
- draft or send the buyer response according to autonomy settings;
- close only after verified resolution.

### 4. Broken-link workflow

Implement:

```text
CUSTOMER_ISSUE_RECEIVED
→ REPRODUCE_LINK
→ LOCATE_FAILURE
→ REPAIR_NOTION_OR_PDF
→ REPLACE_ETSY_FILE
→ VERIFY_BUYER_PATH
→ RESPOND
→ CLOSE_INCIDENT
```

Prioritise this workflow above routine research/build jobs.

### 5. Broken duplicated-template workflow

Check:

- all subpages published;
- linked views point to the duplicate's intended data source;
- relations and formulas reference current properties;
- no accidental references to inaccessible originals;
- public settings;
- duplicate-as-template.

Repair the original published variant so future buyers receive the corrected version.

### 6. Listing-deactivation workflow

Support:

- ingest provider notice;
- inspect listing version;
- identify likely trigger from actual fields/assets;
- create repair changes;
- update or request reactivation/relist according to available provider path;
- preserve original evidence.

Do not build a large compliance bureaucracy. Handle the concrete provider issue.

### 7. Interrupted-agent recovery

When an agent run is interrupted:

- recover from job, artifacts and phase state;
- re-lease if safe;
- resume from incomplete operation;
- do not restart the entire product unnecessarily.

### 8. No-sales troubleshooting

After the playbook's maturity rule:

- inspect the full listing log;
- distinguish search, conversion and demand patterns using configured playbook logic;
- create a concrete two-week repair/research plan as executable jobs;
- do not merely return advice.

### 9. Customer response control

Support:

```text
support_mode: draft | auto
```

In auto mode, send bounded factual support responses after repair verification.

Responses must:

- acknowledge once;
- state the fix;
- include the working access path where appropriate;
- avoid invented claims;
- invite the buyer to reply if the issue remains.

### 10. Tests

Prove:

- broken PDF link;
- unpublished Notion variant;
- wrong colour link;
- no-access block;
- formula error;
- listing file replacement;
- interrupted run recovery;
- repair verification failure;
- customer response draft;
- auto-response after verified repair;
- incident priority over routine work;
- no duplicate repair side effects.

### 11. Commission agent

Mark A16 commissioned after full workflow and tests.

### 12. Review and checkpoint

Use incident-response and customer-experience reviewers. Fix findings.

Commit:

```text
feat(support): automate buyer incidents and source repairs
```

## Exit criteria

- Customer issues create linked incidents.
- Common playbook troubleshooting paths are executable.
- Repairs update the source product/listing.
- Resolution is verified.
- Support response can draft or send automatically.
- A16 is commissioned.
- Tests and control files are current.

## Required exit code

```text
SESSION_11_SUPPORT_AND_REPAIR_COMPLETE
```

Next prompt:

```text
15_SESSION_12_OPERATOR_CONSOLE_AND_POSTHOG.md
```
