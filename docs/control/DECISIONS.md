# Decisions

## D-0001 — Canonical naming authority

**Status:** accepted for Session 00 bootstrap.

The embedded workbook prompt names `D:\hands-off-money-machine`, `/mnt/d/hands-off-money-machine`, a private remote `hands-off-money-machine`, and commit `chore(bootstrap): create hands-off money machine monorepo`. The later, current PRD/test specification intentionally supersedes those engineering names with:

- canonical roots `D:\Money Machine` and `/mnt/d/Money Machine`;
- remote name exactly `money-machine`;
- bootstrap commit exactly `chore(bootstrap): initialise money machine autonomous monorepo`;
- a distinct evidence-closure commit that contains the still-incomplete pre-transition state;
- a later state-pointer commit that contains the completed state but does not attempt to record its
  own object ID inside that state file.

The PDF remains authoritative for business rules. The current PRD/spec is authoritative for repository/path/remote/commit engineering contracts. The contradiction is recorded rather than silently normalized. No remote currently exists, so no public or incorrectly named remote was created.

## D-0002 — Source preservation and redistribution

Both original root sources remain byte-identical and in place. The PDF is strict-deny Git content. Committed derived maps use short paraphrases and page references rather than reproducing source text. The implementation prompt files are byte-extracted only from explicit workbook COPY markers; embedded plugin labels are inert text.

## D-0003 — Session state is fail-closed

Session 00 remains `incomplete` until every required evidence flag is true, both distinct commit SHAs are recorded, the implementation and adversarial reviews pass, `completed_sessions` includes 0, and `next_session` becomes 1. A focused green slice cannot perform that transition.

`evidence_closure_commit_sha` and `head_sha` identify the real commit at repository `HEAD` immediately
before the atomic completion transition. The bootstrap SHA must resolve to the exact bootstrap
commit and be its ancestor. Once the tool writes the completed state, a separate state-pointer
commit checkpoints that write; the state file never claims that later commit's SHA.

## D-0004 — Source identity versus runtime receipts

The committed source record is the path-relative `docs/source/CANONICAL_SOURCE_REGISTER.json` plus its copyright-safe Markdown summary and coverage map. Detailed rename/preservation receipts contain machine-local observations and remain ignored runtime evidence under `.omx/`. Canonical verification reads the private PDF when present; clean clones may omit only that ignored file and must explicitly select the missing-private-source verification mode.

## D-0005 — Runtime directory markers are not runtime evidence

The canonical scaffold requires the `runtime/` directory tree to exist, but runtime data must never be committed. The repository therefore tracks only scoped, empty `.gitkeep` markers under `runtime/artifacts`, `runtime/browser-profiles`, `runtime/receipts`, `runtime/screenshots`, and `runtime/temp`; all other content below those directories remains denied. These inert markers preserve the single canonical scaffold without weakening the strict-deny rule for generated evidence, browser state, receipts, or payloads.

## D-0006 — Completion candidates cannot manufacture closure evidence

The evidence-closure commit must contain the exact live incomplete state that existed before the completion command. Every non-Git evidence fact and all continuity fields are locked before that commit; the completion candidate may only perform the declared Session 00 transition, record the distinct closure SHA, flip the closure-recorded flag, remove exactly the Session 00 outer-gates blocker, advance the timestamp/revision/session pointer, and preserve unrelated blockers such as the push-only remote blocker. This prevents reviews, tests, service results, or other completion facts from being fabricated after closure.

## D-0007 — Local session completion is distinct from remote publication

The current PRD/test specification permits Session 00 to complete locally when its repository, runtime, review, and Git-evidence gates pass. A missing remote blocks only authenticated private push; it does not invalidate the real local bootstrap, evidence-closure, or state-pointer commits. Accordingly, Session 00 advances to Session 01 while retaining `REMOTE_NOT_CONFIGURED` with scope exactly `push only`. No remote is guessed or created, and no publication authority is inferred.

## D-0008 — Explicit operator authorization for a public remote

After Session 00 closed, the operator explicitly instructed that the GitHub repository be created and kept public. That instruction supersedes D-0001/D-0007's earlier private-remote assumption for `OmarA1-Bakri/money-machine` only. The repository therefore uses public visibility and default branch `build/full-automation`; this does not authorize publishing products, customer/provider data, credentials, runtime evidence, the source PDF, or any live commercial effect. Strict-deny tracking rules remain unchanged.

## D-0009 — A generated preview video is required for the first product milestone

The original first-product design and implementation plan allowed either one short preview video
or an explicit `NOT_GENERATED` receipt while no deterministic renderer existed. The continuation
directive dated 2026-08-10 is a narrower, later engineering contract for
`FIRST_PRODUCT_VERTICAL_SLICE_COMPLETE` and requires one valid video stream in both the fixture
product and canary package.

For this milestone, `NOT_GENERATED` therefore remains a truthful non-ready status but cannot pass
preflight or produce `DRAFT_READY`. Configuration freezes `REQUIRED_GENERATED`, the local renderer
emits one replay-stable H.264 MP4 bound to the exact ProductSpec, build, and listing identities, and
preflight reopens and validates its exact bytes and lineage. This decision changes only the video
fallback; the approved truth-only copy, ten-image, PDF-lineage, local-draft, zero-mutation, and
zero-spend contracts remain unchanged.
