# Next Session

Session 02 is complete. Continue with `prompts/implementation/06_SESSION_03_DURABLE_ORCHESTRATOR.md`.

## 2026-09-11 recovery review

Resume from [the recovery review and finish plan](reviews/2026-09-11-recovery-review-and-finish-plan.md). The canonical branch remains `build/full-automation`; the older integration tree is a protected reuse source, including its unfinished Session08 work. Before Session03 implementation, repair the review's readiness/database-URL/production-environment findings in one focused foundation wave. Then complete Session03 prompt integrity and activation, port the existing durable orchestration behavior to the canonical schema, and prove a persisted workflow survives restart. The review does not advance session state or claim live commissioning.

## Session 03 entry conditions

1. Run the prompt-integrity review and corrective exercise first. It is the standing first instruction of every session prompt (`docs/PROMPT_INTEGRITY_REVIEW.md`, D-0026), and `tests/bootstrap/test_prompt_integrity.py` fails until the record exists.
2. Add Session 03's completion-evidence keys to `SESSION_EVIDENCE_KEYS` in `src/money_machine/control/state.py`, then activate with `money-machine-control activate`. Activation fails closed without that contract.
3. Session 03 owns job claiming. The worker and scheduler currently perform a read-only database connectivity check and exit 78 with no claim path anywhere in the source. Commissioning them is this session's work, and the exit-78 contract may only be lifted deliberately, with a decision record.
4. The schema already carries what the orchestrator needs: `jobs` with an idempotency key, lease owner, lease expiry, heartbeat and partial indexes for the ready-and-due and lease-expiry queries; `job_dependencies`; `events` as an append-only log with a semantic dedupe key; `idempotency_records` for reservations; and `effect_attempts` for reconciliation outcomes. Use them rather than adding a parallel mechanism.
5. Keep provider effects in simulation. Nothing is commissioned; no agent may perform a provider call.

## Carry-forward work

- Prove idempotency uniqueness under a concurrent claim path, which only exists once claiming does (Session 03).
- Refuse an unreconciled `MetricsSnapshot` as a decision input at the decision layer (Session 02 review, deferred).
- Wire `require_successor_spawn` into the orchestrator's MULTIPLY spawn path (Session 01 review, deferred to Session 03).
- Install Playwright with the first browser-channel work, not before.
- Relate listing description sections and tags as rows rather than checked JSON arrays when merchandising is built (Session 08).
- Vendor capability for every `DIRECT_API` selection, and Etsy field-length limits, remain UNVERIFIED until the owning session reads and cites the vendor reference.
- The CodeRabbit vendor re-review of the Session 00 fixes is still rate-limited; the blocker stays in state.

## Environment notes

- The shared development database `money_machine` holds another branch's schema at its own Alembic revision, and the instance carries roughly four hundred leftover test databases from other branches. Nothing on this branch touches them: database-backed tests create and drop their own throwaway databases, and `MONEY_MACHINE_TEST_ADMIN_DATABASE_URL` selects the maintenance connection.
- `pnpm install` needs `--package-import-method copy` on this filesystem: the hardlink rename fails on the 9p `/mnt/d` mount.
- Host port 3000 is occupied by an unrelated development server; set `WEB_PORT` to verify the web container.

Session 02 evidence: 45 tables from one reviewed migration with an exact table set, a proven downgrade and re-upgrade, and no drift; database-enforced taxonomies, uniqueness, composite lineage keys and append-only triggers; an idempotent, convergent, concurrency-safe seed; typed repositories with real optimistic locking; a readiness endpoint that fails when the database does; a command line exercised as real subprocesses; five containers with the worker and scheduler still fail-closed; 370 Python tests, a green web gate, and two independent closure reviews resolved.
