# Cloud QA integrated-wave review

Independent read-only reviews were performed by `prompt_fidelity` (functional
integration) and `prompt_safety` (PDF/effect/identity boundaries). Neither owned
implementation or mutated provider data. Final bounded re-review from both:
no remaining blocker/serious defect in the reviewed mechanisms.

Findings corrected before aggregate verification:

1. Failed jobs bypassed attempt budgets. The finite fixture consumer now uses
   existing retry eligibility, increments attempts, enforces exhaustion, and
   validates transitions/releases leases through existing controls.
2. A cached BLOCKED QA verdict could never recover. BLOCKED execution/job state
   now remains explicit and a subsequent invocation runs fresh verification.
3. The variant successor was left pending after variants were already built.
   It now runs the existing idempotent builder to reconcile that real stage.
4. A confirmed effect could repeat after checkpoint failure and later drift.
   Receipt/completed-reservation checks precede mutations; acknowledged drift
   refuses replay. Unfinished intents use exact existing-property readback.

Reviewers confirmed the PDF admission remains restricted to the measured inline
`Type /ViewerPreferences` and `DisplayDocTitle true` dictionary, real adapters
are excluded from these fixture consumers, and persisted local identity records
are not represented as thredOS registration. Production provider code and the
UNKNOWN-operation hold remain untouched.

The integrator owns fresh execution evidence. Ten focused database scenarios
passed after remediation, including a terminal-commit failure probe that preserves
the standard lease-recovery hold and never writes a dangling checkpoint run ID. Aggregate outcomes are recorded in TEST_EVIDENCE.md;
the reviewers did not independently execute the database/browser aggregate.

The affected aggregate subsequently exposed eight historical control-snapshot
assertions that contradicted the already pinned audited revision65, plus one
old PDF-shape assertion. Test-only corrections now require revision65/incomplete,
next Session07, preserved closure/bootstrap identities, all twelve false evidence
keys and no commissioned agents; no control-state bytes changed. The README
shape assertion validates the exact measured preferences while preserving every
page/resource/annotation assertion. No reviewed runtime mechanism changed.

## Workbook completion increment

Bounded diff from `5df61e2b369facd3c119bce1d82a99d6f8e1d8bb` reviewed by the
same independent, read-only reviewers (no implementation delegates):

- `prompt_fidelity`: no blocking functional findings, including observed child
  inventory, missing-created-child refusal, content target excluding linked-view
  inflation, exact hub/guide backlinks and explicit cover inputs/readback.
- `prompt_safety`: no blocking provider/effect finding. The cover exception is
  field-specific; arbitrary external blocks remain forbidden. Scope, lease,
  durable reservations, logical effect keys and UNKNOWN handling are unchanged.
  Missing/different covers or backlinks refuse replacement writes.

Reviewers inspected source only; execution evidence belongs to the integrator.
Cover provenance, image availability, palette fidelity and native visual acceptance
remain unverified. Three approved real cover asset URLs are still needed.
This increment does not claim completed product, source PDF verification,
thredOS registration or production effect reconciliation.

Fresh integrated verification after both reviews: 1,073 affected application,
Notion adapter, cover CLI and real-draft effects/runner checks passed with zero
failures/skips (19.37 seconds). Ruff check and format passed across src/tests;
strict Pyright reported zero errors. Workbook and Session 07 hashes are unchanged;
canonical clean-clone source-register validation passed. No full-suite rerun was
needed for this Level 2 wave; the preceding published commit already has green
CI run 39769233582. New CI status belongs to the new remote commit.

## One-send recovery guard preparation

Independent read-only review of the diff from `bd00b06e` by `prompt_fidelity`
and `prompt_safety` identified three material boundary gaps. The executor fixed
mutable hook/transport sharing, missing-metadata downgrade, and approval expiry
across lock waits. Both reviewers read the corrected code and regressions and
reported no remaining blockers in that changed scope. They did not run tests.

The remediated guard uses existing BuildRepairJob metadata, durable reservations,
lease locks, effect attempts, receipts and persisted agent-run lineage. The wire
body is independently copied and hashed; recovery identity independently requires
a guard; authorization is consumed durably before send, rechecked after locking
and at final permit consumption, and cannot be retried after ABSENT/400/429.
No approval issuer, CLI, scheduler, database migration, canonical-selection
binding, thredOS registration claim or production execution is included.

The original UNKNOWN/incident and fourteen confirmed receipts are preserved in
isolated regression fixtures. Fixture IDs/approvals are synthetic and grant no
production authority. Actual spec/schema/hash-definition and provider execution
remain blocked independently of this code preparation.

After final review, 1,107 affected application/Notion/CLI, recovery-guard,
real-draft effects/runner, observability and existing fixture-repair tests passed
with zero failures/skips (48.26 seconds). Ruff check/format across the CI source
paths, strict Pyright and source-register checks passed. The 22 new database
scenarios cover success/replay and persisted lineage, concurrent dispatch, lost
response, 400/429 refusal, crashes on both sides of durable consumption, missing
authority/metadata/hook, altered request/scope, mutable hook arguments, revocation
and expiry during locking/after consumption. Existing ordinary ABSENT retries
remain green. Preceding bd00b06e has independently confirmed full CI success
(5,525 Python and 61 frontend tests); this increment has separate CI evidence.
