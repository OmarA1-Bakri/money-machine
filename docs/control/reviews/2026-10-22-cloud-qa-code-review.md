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


## Durable A07 lifecycle increment

Independent read-only functional/migration review (`prompt_fidelity`) and provider
safety review (`prompt_safety`) found three initial boundary defects: committing
an explicitly managed caller transaction, validating stale cached job fields, and
borrowing an unresolved run after lease/attempt turnover. The executor repaired
all three and both reviewers inspected the changed scope and reported no remaining
blocker. Reviewers did not execute tests or query databases/providers.

The existing agent_runs row now records RUNNING with its actual job attempt and
lease owner before A07 work, then updates that same identity to a terminal result.
A07 caller transaction ownership is explicit, active starts serialize under the
refreshed job lock, and terminal overwrite/identity drift/restart of unresolved
execution are refused. Effect sends require the original owner/attempt; historical
accepted-effect recording retains its scoped lineage path. No approval issuer,
recovery CLI, shadow registry or production binding is introduced.

Focused lifecycle/guard verification passed 46 tests. This includes 20 lifecycle
cases and four guard integration cases added in this increment; all 22 earlier
guard cases remain. Fixtures now use a real observer-persisted active run rather
than a synthetic terminal success row. Runner tests use a hash-verified synthetic
PromptStore and production=False; missing versioned A07 runtime prompt and actual
thredOS registration remain explicit deployment/readiness gaps.

The first affected pass had 332 passing checks and one stale three-revision
assertion. The schema test now checks the four reviewed migrations, the same
canonical root and absence of a new lifecycle table. Its 106-check subset passed.
Final affected and static verification is recorded below after execution.

The lifecycle migration preserves old terminal history and refuses downgrade
with unresolved active rows. Isolated DB tests exercise upgrade/downgrade/schema
drift and truthful terminal shapes. Original production UNKNOWN, its incident
and fourteen confirmed effects remain held; zero provider/production mutations.

Final post-review affected verification: 333 tests passed, zero failures/skips
(117.56 seconds), including migrations/schema/reversal, seed, repositories,
leases, runner/observer, fixture QA/repair and original real-draft controls.
The 12 prompt-pack/integrity checks passed separately. Ruff check across CI paths,
format checks on 440 files, strict Pyright (zero errors) and canonical clean-clone
source verification passed. The private Playbook PDF remains absent; no PDF-byte
identity/coverage verification or session completion is claimed. New commit CI
is tracked separately from the preceding green 22302db run.

## Runner-to-recovery binding increment

Independent read-only functional review (`prompt_fidelity`) and provider-safety
review (`prompt_safety`) found no blockers. Both confirmed the final classmethod
refactor and additional revocation/drift regressions. They performed no tests,
database queries or provider operations. Strict Pyright initially identified
protected method access and a possibly unbound fixture path; moving the factory
inside SqlDraftEffects and assigning the path before its conditional resolved both.

AgentRunner forwards its actual lease owner through the existing context. The
binding checks that context against the persisted active A07 BuildRepairJob,
attempt, job/run/prompt lineage and exact stored approval. It returns existing
effects and an injected SDK adapter with both callbacks installed; it neither
admits an approval nor claims a lease, reserves an effect or invokes a provider.
Approval revocation after binding still refuses the actual transport boundary.

All 16 new binding scenarios passed, including actual runner-created durable run
lineage, success replay, lost-response replay and context/approval drift. The final
affected suite passed 349 tests with zero failures/skips (131.01 seconds), covering
runner/observer, existing guard/effect controls, fixture repair/QA, leases,
repositories, schema/migrations/reversal and seed. The 12 prompt checks passed;
Ruff check/format (441 files), strict Pyright (zero errors) and canonical-source
verification passed. The original Playbook PDF remains absent and unverified.

The preceding 1b68de4 lifecycle head has independently confirmed full CI success:
5,571 Python and 61 frontend tests plus the database/build/static/Compose gates.
New-head CI is separate. No production ledger/provider mutation, deployment,
live approval, canonical-selection binding, finite invocation or session closure
is included. Actual thredOS registration and production prompt remain unverified.

## Screenshot capture CI correction

Independent run39798293205 failed at the unchanged fixture hash test with the raw
Chromium Page.captureScreenshot error after font readiness: 5,586 Python tests
passed, one failed; downstream frontend/Compose gates were skipped. The exact
test passed locally with the already installed Chromium cache. The underlying
browser cause is not reproduced or classified as flaky. Driver inspection shows
the capture error is propagated after readiness, with no local renderer recovery.

The local renderer now recreates the page once for that exact protocol error,
repeating readiness, structure, sensitive-text validation and PNG canonicalization.
Persistent failure, timeout, closed target and validation refusal still fail.
No launch flag, dependency, security/network setting, hash, assertion or provider
retry behavior changed. Five injected scenarios prove fresh-page cleanup, the
original pinned hash, persistent/other-error propagation and second-pass privacy
refusal. The injected one-failure case reproduced RED before the correction.

All 72 screenshot tests passed (22.26 seconds); 128 affected image/video/lineage,
mutant, draft-successor and readiness tests passed (27.41 seconds). Ruff check and
format passed. Independent functional and privacy/provider reviewers found no
blocker, explicitly preserving the underlying-cause limitation. Strict Pyright
verification and the separate new-head CI receipt are recorded at publication.
No provider/production effect, approval issuance, merge or deployment occurred.
