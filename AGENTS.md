# Money Machine Repository Rules

- Read `docs/DEVELOPMENT-GOVERNANCE.md` before implementation; it defines mandatory routing, context, verification, review, checkpoint, and stopping discipline.
- Treat `The-Hands-Off-Money-Machine-Playbook.pdf` as the authority for business logic and terminology, and the implementation workbook as the authority for engineering/session contracts. Record contradictions in `docs/control/DECISIONS.md`.
- Do not add commercial revalidation gates that contradict the playbook.
- Maintain one canonical repository and one durable orchestration engine; do not create duplicate trees or shadow state machines.
- Encode business rules in typed code/configuration and tests, not only in prompts or documentation.
- Perform external mutations only through adapters with explicit simulation/draft/live modes, idempotency, and reconciliation.
- Never commit secrets, `.env`, tokens, cookies, browser profiles, customer/provider payloads, generated evidence, runtime state, or the source PDF.
- Never publish, purchase, spend, message customers, or mutate live provider data from tests.
- Preserve user changes and both immutable root source files byte-for-byte. Do not reset, clean, rename, move, or rewrite them.
- Do not claim completion from documentation, mocks, placeholders, or partial tests. Report failed gates and blockers factually.
- Route once per phase/wave and reuse the receipt. Default to one executor; use at most three independent non-overlapping lanes. Never replace a failed team launch with a high-reasoning swarm.
- Use Level 1/2/3 validation: focused RED/GREEN, one affected integration pass, then heavyweight gates only at a session exit or explicit high-risk boundary.
- Resume from a metadata-only checkpoint before replanning or rescanning. Limit retries, reviews, repeated reads, and progress reports per `docs/DEVELOPMENT-GOVERNANCE.md`.
- Every completed session updates the five files in `docs/control/`, passes its exit gates, receives independent review, and is committed before the next session closes.
