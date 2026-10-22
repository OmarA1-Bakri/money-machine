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
