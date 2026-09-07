# Platform Compatibility

**Contract status:** compatibility policy and current safe assessment. Provider mechanics are not claimed commissioned until an operation-specific probe and contract test exists.

## Supported execution platforms

| Surface | Baseline | Contract |
|---|---|---|
| Windows host | Windows with WSL2 | Canonical display root `D:\Money Machine`; no second repository tree |
| Linux runtime | WSL2 / standard Linux | Canonical persisted root `/mnt/d/Money Machine`; filesystem-identical casing aliases are verified, not normalized |
| Python | 3.12 | uv lock, Ruff, strict Pyright, explicit UTF-8 and bounded subprocesses |
| Node | 24 | pnpm 10 workspace and strict TypeScript |
| Browser | pinned Playwright Chromium | deterministic selectors/rendering; no untracked profile dependency in tests |
| Database | PostgreSQL 16 | authenticated TCP, migrations, UTC database time |
| Local/production stack | Docker Compose | five approved services; no Kubernetes dependency |

Bash scripts are invoked with `bash` because executable bits are not relied on across Windows/POSIX clones. PowerShell wrappers must preserve the same contracts.

## Provider compatibility rule

Provider documentation and safely observed live behavior govern mechanics only. The playbook remains authoritative for business sequence, outputs, limits, and truthfulness. A provider change may alter an adapter/channel but cannot silently:

- replace Etsy or Notion;
- weaken dedupe, preflight, maturity, cull, or publication-ramp rules;
- turn a draft into publication;
- create repeated approvals inside standing authority;
- infer authority from credentials;
- convert an uncertain external effect into an ordinary retry.

## Compatibility register

| Area | Required product behavior | Selected mechanism | Current evidence | Adaptation rule |
|---|---|---|---|---|
| Etsy listing operations | draft, fields, files/media, publish/update/deactivate, metrics | official API first; browser for visibility/checkout | not safely probed | preserve immutable listing version and reconcile provider state |
| Etsy search evidence | admitted listing/shop observations | isolated browser read | not safely probed | timestamp provenance; block rather than fabricate unavailable rows |
| Notion structured content | pages, databases, properties, relations, rollups, formulas | official API | not safely probed | checkpoint every provider object ID |
| Notion UI-only content | linked views, layouts, publish/indexing/duplication, fresh-view | browser | not safely probed | use deterministic selectors and read-after-write reconciliation |
| Composio | operation-specific alternative | selected only after safe probe | unavailable in this session | never treat connector presence as whole-provider support |
| PostHog | operational observations | SDK/API | repository config disabled | telemetry may lag/drop and cannot drive workflow |
| LLM | strict structured result | OpenAI-compatible abstraction | application provider uncommissioned | provider-specific schema translation stays behind adapter |
| Asset rendering | reproducible images/video/PDF | pinned Playwright internal renderer | not implemented | record renderer/template/font versions and hashes |
| Storage | immutable artifacts and denied runtime evidence | local adapter initially | scaffold only | portable storage references; no secrets in metadata |

## Browser compatibility

- Tests use an isolated temporary profile and simulation/fixture pages.
- Runtime profiles and cookies are denied data and never committed or inspected for architecture evidence.
- Selectors prefer accessibility roles, stable labels, and adapter-owned locator contracts.
- Every write has a postcondition read and screenshot/redaction receipt where safe.
- CAPTCHA, MFA, holder verification, and unsolved provider challenges become `MANUAL_RESUME` blockers.
- Browser timeouts after a mutation become `UNCERTAIN_EXTERNAL_EFFECT` until reconciliation.

## Version-change process

1. Record the affected operation and observed safe metadata.
2. Add or update a fixture reproducing the provider contract without private payloads.
3. Adjust only the adapter/channel translation.
4. Run contract, idempotency, reconciliation, and affected workflow tests.
5. Review for business-rule drift and secret leakage.
6. Update this register and commissioning evidence.

No compatibility claim is made from package installation, a connected development tool, or agent self-report.