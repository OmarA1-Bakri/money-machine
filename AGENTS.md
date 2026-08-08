# Money Machine Repository Rules

- Treat `The-Hands-Off-Money-Machine-Playbook.pdf` as the authority for business logic and terminology, and the implementation workbook as the authority for engineering/session contracts. Record contradictions in `docs/control/DECISIONS.md`.
- Do not add commercial revalidation gates that contradict the playbook.
- Maintain one canonical repository and one durable orchestration engine; do not create duplicate trees or shadow state machines.
- Encode business rules in typed code/configuration and tests, not only in prompts or documentation.
- Perform external mutations only through adapters with explicit simulation/draft/live modes, idempotency, and reconciliation.
- Never commit secrets, `.env`, tokens, cookies, browser profiles, customer/provider payloads, generated evidence, runtime state, or the source PDF.
- Never publish, purchase, spend, message customers, or mutate live provider data from tests.
- Preserve user changes and both immutable root source files byte-for-byte. Do not reset, clean, rename, move, or rewrite them.
- Do not claim completion from documentation, mocks, placeholders, or partial tests. Report failed gates and blockers factually.
- Every completed session updates the five files in `docs/control/`, passes its exit gates, receives independent review, and is committed before the next session closes.

