# 0004 Provider Adapters

**Status:** Accepted

## Context

Etsy, Notion, LLM, PostHog, browser, and storage operations differ in API coverage and can change over time. Some effects are reversible, some spend money, and some have ambiguous outcomes after a timeout. Tests must never use live effects.

## Decision

Define provider-neutral interfaces in `integrations` and select a capability channel per operation:

- `DIRECT_API`: official API/client where supported;
- `COMPOSIO`: admitted connector action where reliable;
- `BROWSER`: Playwright automation for UI-only operations;
- `INTERNAL_RENDERER`: deterministic local asset generation;
- `MANUAL_EXTERNAL_BLOCKER`: no safely admitted automated path.

Channel is independent from adapter implementation, `simulation`/`draft`/`live` autonomy, credential availability, and standing authority. Each adapter advertises operation capabilities and implements fixture/simulation behaviour. Tests use fixture or simulation adapters only.

Every external mutation accepts an idempotency key and returns a structured effect reference. After timeout or transport ambiguity, `RECONCILE_FIRST` operations query provider state before any retry. Spending, checkout, publication, deactivation, and messaging enforce configured authority at execution time. Provider-specific payloads are translated at the adapter boundary and are not the domain model.

Capability assessment records only safe metadata: selected channel, availability state, authority requirement, reconciliation need, and blocker code. Credentials, tokens, cookies, browser-profile contents, customer/provider payloads, and private source text are never recorded in architecture or committed evidence.

## Rationale

Adapters preserve domain stability while allowing the narrowest reliable provider mechanism. Operation-level selection avoids claiming that one channel supports an entire provider.

## Consequences

- Some provider workflows combine API and browser operations.
- Compatibility changes are localized and recorded in `PLATFORM_COMPATIBILITY.md`.
- Browser automation requires deterministic selectors, bounded waits, screenshots/redaction policy, and reconciliation.
- Unknown capability fails closed instead of being guessed.
- Fixture success is not live commissioning evidence.

## Rejected alternatives

- **Direct provider calls from agents:** mixes workflow authority, secrets, and unstable payloads.
- **Browser-only automation:** slower and more fragile where an API exists.
- **API-only requirement:** cannot cover UI-only Notion and marketplace mechanics.
- **Mocking one universal provider as production-ready:** hides capability gaps.
- **Retrying every failure:** can duplicate publication, spend, or messages.

## Revisit when

Revisit an operation when official provider behaviour or admitted connector coverage changes, or when measured reliability requires a different channel. Preserve idempotency, authority checks, and reconciliation through any channel change.