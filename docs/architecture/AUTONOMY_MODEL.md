# Autonomy Model

**Contract status:** standing-authority design. Current repository configurations remain simulation/disabled; no live effect is commissioned.

## Modes

| Mode | Internal work | Provider reads | Provider drafts/writes | Publish/deactivate | Spend/message |
|---|---|---|---|---|---|
| `simulation` | allowed | fixture/simulated only | simulated result only | prohibited | prohibited |
| `draft` | allowed | admitted read adapter | admitted drafts and reversible workspace writes | prohibited | prohibited unless a separate explicit contract says otherwise |
| `live` | allowed | admitted adapter | admitted writes | only when corresponding auto flag and cap allow | only when operation enablement and cap allow |

Tests always force `simulation`, even when the machine has live credentials or browser state.

## Standing-authority contract

```yaml
mode: simulation
auto_publish: false
auto_deactivate: false
auto_multiply: false
external_message_enabled: false
message_monthly_cap: 0
authorized_recipient_scopes: []
recipient_consent_evidence_required: true
competitor_purchase_enabled: false
competitor_purchase_max_each: 0
competitor_purchase_monthly_cap: 0
live_checkout_test_enabled: false
live_checkout_test_cap: 0
weekly_listing_cap: 2
paid_tool_monthly_cap: 0
```

`config/autonomy.example.yaml` is the tracked, fail-closed template and is never production authority. The operator's standing authority lives in the git-ignored `config/autonomy.yaml`; the loader uses it whenever it exists, and production fails closed when it is absent. Development and test always force simulation regardless of which file loaded. The runtime environment comes from `APP_ENV` (`development` by default, `test`, or `production`); an unrecognised value is an error. Numeric currency fields use decimal-safe values plus configured currency in typed settings.

Publication additionally requires `publishing_enabled: true` in `config/publishing_ramp.yaml`. That switch is deliberately separate and tracked: it halts publication for the whole shop without touching standing authority. `DEPLOYMENT.md` states the exact go-live sequence.

## Effect authorization

Before an external effect, the executor verifies in one durable decision:

1. operation capability is admitted and commissioned;
2. current autonomy mode permits the operation;
3. operation-specific flag permits it;
4. job side-effect and retry classes match the adapter operation;
5. idempotency key has no completed conflicting effect;
6. listing/spend/message scope is within standing authority;
7. transactional cap reservation succeeds;
8. dependencies, artifact versions, QA/preflight, and provider account are current.

A failed check moves the job to a typed blocker without changing product state. It does not create a routine approval request when work is simply outside configured bounds.

## Publication ramp

- Initial target is two listings per rolling week.
- Configuration may set a target in the source range two to three and grow it up to the hard cap of fifteen. Fifteen is a typed invariant (`PLAYBOOK_MACHINE_WEEKLY_CAP`): neither `hard_weekly_cap` nor `weekly_listing_cap` can be configured above it.
- Successful reconciled publications count; failed attempts and drafts do not.
- Concurrent jobs reserve capacity transactionally.
- Cap changes affect new reservations only and retain an audit record.

## Spend

Competitor purchase and buyer-chain checkout have distinct enablement and caps. Each effect reserves the amount before execution, records currency and provider reference, and reconciles ambiguity before release or retry. Paid-tool usage shares a monthly cap but does not silently consume purchase authority.

## External messages

Message authority is independent from draft/write authority. A message effect requires `external_message_enabled`, an admitted operation, a positive remaining message cap, a recipient belonging to an explicitly versioned `authorized_recipient_scopes` entry, and consent evidence when `recipient_consent_evidence_required` is true. The durable authorization record stores only safe recipient-scope and consent-reference identifiers, never message-channel credentials or private message content. An empty scope list or zero cap fails closed. Current configuration has no commissioned recipient contract, so proof distribution remains blocked.

## Cull and multiply

- `auto_multiply` permits creation of the internal successor workflow; external effects in that workflow still pass their own checks.
- `auto_deactivate` permits A13 to execute a durable `CULL` deactivation after maturity/decision evidence.
- `CULL` eligibility is not authority and does not itself mutate Etsy.
- Defect repair is immediate internal work; an external repair write still passes effect authorization.

## Human-intervention boundary

Stop only for:

- unavailable/expired credentials;
- holder-only account verification;
- CAPTCHA/provider challenge not solvable by the admitted adapter;
- requested action above a configured cap;
- missing recipient consent/authority (added to the workbook's five; see D-0020);
- genuinely uncertain effect that reconciliation cannot resolve.

The blocker records a code, affected operation, safe detail, and exact operator action. It never records a secret or private payload.

## Configuration precedence and safety

Environment-specific configuration may reduce authority but cannot silently widen it above the explicit standing-authority document. Test/development overrides always force simulation and external mutations false. Unknown keys, invalid ranges, unsupported modes, contradictory flags, and live flags with zero/unset caps fail validation. Configuration changes are versioned evidence for later effects.