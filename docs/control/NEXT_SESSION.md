# Next Session

**Session 04 is IN PROGRESS** (2026-09-20) — agent runtime and roster. Exit 78 remains in place per Session 03/04 contracts; worker and scheduler process entrypoints stay fail-closed with no production claim path.

## Session 04 progress (post-Lane C @ `744cc36b`)

| Wave | Status | Commit | Evidence key(s) |
|---|---|---|---|
| W1 — prompt integrity + activation | **COMPLETE** | `0ce1400` (#18) | governance only; eight keys installed all-false |
| W2 — LLM provider abstraction | **COMPLETE** | `d187fb2` (#19) | `provider_abstraction_implemented` = true |
| W3 — PromptStore + A01/A02 prompts | **COMPLETE** | `726437d` | `prompt_registry_and_hashes_implemented` = true |
| Phase A — Jev client/library | **COMPLETE** | `3cbe39b` | library only; not a Session 04 exit-criteria key |
| W4 — AgentRunner + registry + receipts | **COMPLETE** | `b87c547` | library runner + receipt integration |
| W5 — ToolRegistry + sixteen-agent roster | **COMPLETE** | `827272b` | `sixteen_agents_registered` = true |
| W6 — bounded review subagent | **COMPLETE** | `d9eb8e2` | artifact-only; fail-closed mutate |
| W7 — agent-run observability | **COMPLETE** | `4ee63ce` | logs + PostHog-shaped offline queue |
| W8 — roster contract tests A01–A16 | **COMPLETE** | `44d554f` | `uncommissioned_agents_documented` = true |
| Lane C — runtime integration tests | **COMPLETE** | `744cc36` | `contract_and_runtime_tests_pass` = true |
| Remainder — orchestrator wire + exit | **OPEN** | — | `agent_runner_integrated_with_jobs`, `evidence_closure_commit_recorded` false |

**Exit 78 held.** No worker claiming, no commissioning, no live Notion/Etsy. Lane C proves the library lease → run → persist → event → successor path only; `agent_runner_integrated_with_jobs` requires the orchestrator wire (Lane A), not tests alone.

## Next work (Session 04 remainder)

Per `docs/control/reviews/2026-09-20-session-04-prompt-integrity.md` addendum slices still open:

1. **Agent runner integrated with durable jobs** — Lane A orchestrator wire connecting production job path to `AgentRunner` (library runtime-integration tests alone do not earn this key).
2. **Session 04 exit** — two independent reviews, all eight evidence keys true, closure commit sequence. Exit 78 removal remains a **post-session gate** (decision record + commissioning evidence), not Session 04 closure.

## Session 03 completion (reference)

Session 03 closed 2026-09-19 after Verifier FINAL PASS (#17). Gap-close implementation validated: real `dependency_resolver`, scheduler library functions, operator surface (CLI + API), entry-job spawn. Worker/scheduler processes remain fail-closed until commissioning gates pass.

## Carry-forward work

- Prove idempotency uniqueness under a concurrent claim path (only after commissioning).
- Refuse an unreconciled `MetricsSnapshot` as a decision input (Session 02 review, deferred).
- Install Playwright with the first browser-channel work, not before.
- Relate listing description sections and tags as rows rather than checked JSON arrays when merchandising is built (Session 08).
- Vendor capability for every `DIRECT_API` selection, and Etsy field-length limits, remain UNVERIFIED until the owning session reads and cites the vendor reference.
- The CodeRabbit vendor re-review of the Session 00 fixes is still rate-limited; the blocker stays in state.

## Environment notes

- The shared development database `money_machine` holds another branch's schema at its own Alembic revision, and the instance carries roughly four hundred leftover test databases from other branches. Nothing on this branch touches them: database-backed tests create and drop their own throwaway databases, and `MONEY_MACHINE_TEST_ADMIN_DATABASE_URL` selects the maintenance connection.
- `pnpm install` needs `--package-import-method copy` on this filesystem: the hardlink rename fails on the 9p `/mnt/d` mount.
- Host port 3000 is occupied by an unrelated development server; set `WEB_PORT` to verify the web container.
