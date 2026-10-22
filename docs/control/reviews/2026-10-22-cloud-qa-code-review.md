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
