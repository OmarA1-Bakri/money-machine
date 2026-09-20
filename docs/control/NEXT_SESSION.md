# Next Session

**Session 04 is IN PROGRESS** (2026-09-20) — agent runtime and roster. Exit 78 remains in place per Session 03/04 contracts; worker and scheduler process entrypoints stay fail-closed with no production claim path.

## Session 04 progress (post #21 Phase A @ `3cbe39bf`)

| Wave | Status | Commit | Evidence key(s) |
|---|---|---|---|
| W1 — prompt integrity + activation | **COMPLETE** | `0ce1400` (#18) | governance only; eight keys installed all-false |
| W2 — LLM provider abstraction | **COMPLETE** | `d187fb2` (#19) | `provider_abstraction_implemented` = true |
| W3 — PromptStore + A01/A02 prompts | **COMPLETE** | `726437d` | `prompt_registry_and_hashes_implemented` = true |
| Phase A — Jev client/library | **COMPLETE** | `3cbe39b` | library only; not a Session 04 exit-criteria key |
| W4+ — AgentRegistry, AgentRunner, roster, observability | **OPEN** | — | remaining six evidence keys false |

**Exit 78 held.** No worker claiming, no commissioning, no live Notion/Etsy. Phase A and W2/W3 are library and test slices only.

## Next work (Session 04 remainder)

Per `docs/control/reviews/2026-09-20-session-04-prompt-integrity.md` addendum slices 3–5:

1. **Agent base and registry** — `AgentDefinition`, `AgentContext`, `BaseAgent`, `AgentRegistry`, `ToolRegistry`, `AgentRunner`, commissioning-state checks.
2. **Agent-run observability** — `agent_runs`, artifacts, tool-call tables, structured logs, offline PostHog queue.
3. **Sixteen-agent roster** — `config/agents.yaml` + database seed; A01/A02 to `TESTED`; A03–A16 at `DESIGNED` with contract tests proving production refusal.
4. **Contract and runtime integration tests** — parameterized contract tests (8 per agent) and orchestrator-lease → agent-execute → persist → event → successor flow with fake providers.
5. **Session 04 exit** — two independent reviews, all eight evidence keys true, closure commit sequence. Exit 78 removal remains a **post-session gate** (decision record + commissioning evidence), not Session 04 closure.

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
