# 0006 Autonomy Configuration

**Status:** Accepted

## Context

The system must avoid per-listing approval bureaucracy while never inferring authority to publish, deactivate, spend, check out, or message. Tests must stay safe on machines that possess real credentials.

## Decision

Use one validated standing-authority configuration with:

- `mode`: `simulation`, `draft`, or `live`;
- `auto_publish`, `auto_deactivate`, and `auto_multiply`;
- external-message enablement, monthly cap, versioned authorized-recipient scopes, and required consent-evidence references;
- competitor-purchase enablement, per-purchase maximum, and monthly cap;
- live-checkout enablement and cap;
- weekly listing cap;
- paid-tool monthly cap.

Configuration is loaded through strict typed validation. Test and development environments force `simulation` and all external mutations/spend off. Production defaults to disabled/draft until the operator deliberately supplies live authority. Possessing credentials or a browser session does not grant authority.

Every effect checks both operation capability and standing authority immediately before execution. Spend and message caps use durable reservations and receipts so concurrent jobs cannot exceed bounds. Message effects additionally require an admitted recipient scope and the configured consent-evidence reference; an empty scope, missing consent, or zero cap fails closed. Publication-ramp checks use the persisted count of successful publications, not queued intent. `UNCERTAIN_EXTERNAL_EFFECT` suspends ordinary retry until reconciliation.

Routine work inside configured bounds proceeds automatically. Human intervention is limited to unavailable credentials, holder-only verification, unsolved CAPTCHA/provider challenge, cap exceedance, missing recipient consent/authority, or genuinely unreconciled external effect.

## Rationale

A small explicit authority surface provides autonomy without repetitive approvals and protects environments where secrets may already exist.

## Consequences

- Live operation requires a deliberate one-time configuration change and commissioned adapters.
- Lowering authority blocks new effects but does not erase historical receipts.
- Cap calculations require transactional persistence.
- Simulation must model intended outputs without claiming provider mutation.
- Draft mode permits admitted drafts but prohibits publication/deactivation/spend unless separately and explicitly allowed by the contract.

## Rejected alternatives

- **Approval before every listing:** contradicts standing-authority autonomy.
- **Credentials imply live permission:** unsafe and unauditable.
- **Environment name alone controls effects:** too implicit.
- **Unbounded automatic retries:** can duplicate commercial actions.
- **Hard-coded caps:** prevents explicit operator control and source traceability.

## Revisit when

Revisit configuration fields when a new commercial side effect or provider constraint appears. Preserve explicit mode, bounded authority, transactional caps, simulation-only tests, and reconciliation-first ambiguity handling.