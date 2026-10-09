# Session 07 Prompt Integrity Review — Sandbox run

**Date:** 2026-10-07
**Prompt:** `prompts/implementation/10_SESSION_07_PRODUCT_BUILD_VARIANTS_AND_QA.md`
**Verified SHA-256:** `d52011a6f0b725b16427629dc664cfc9f3432c4b5f71d26ce032d4b6c8ecb39d`
**Workbook authority:** `hands-off-money-machine-full-implementation-workbook.md` appendix row for this prompt
**Scope:** Sandbox-run CLI only. W1–W8 stay merged. W9 (`notion_qa.py`) and W10 are not imported. The prompt file is not amended.

## 1. Prompt authenticity

**Status:** VERIFIED

- The extracted file's SHA-256 equals the workbook appendix value `d52011a6f0b725b16427629dc664cfc9f3432c4b5f71d26ce032d4b6c8ecb39d`.
- The prompt stays the unamended source of record.

## 2. Three-dimensional review

### Fidelity

**Verdict:** CONDITIONAL APPROVE. One high finding, resolved by the addendum.

**F-01 [HIGH] — Section 11 says to run one live sandbox build**

- **Prompt lines:** 186–202, especially the live-build sentence.
- **Authority:** W9 and W10 are not on `build/full-automation`. The merged pipeline is the build phases plus variants. QA, the fact ledger, and the workflow link are later slots.
- **Consequence of literal execution:** A live run now would either skip QA silently or import unmerged modules. Running it from this session would also mutate the sandbox workspace before Grok Bot runs the merged SHA.
- **Amendment:** Ship the runner. Call the merged build and variant functions. Leave `qa`, `fact_ledger`, `workflow_link`, and `w11` as registry slots whose evidence status is `NOT_RUN`. Do not execute the live client in this session.

### Safety and executability

**Verdict:** CONDITIONAL APPROVE. The Wave 1 critical finding stays in force for execution.

**S-01 [CRITICAL] — A live sandbox build mutates Notion.** This slice does not execute it. Tests use a fake client and block sockets. The token is read only from `NOTION_SANDBOX_TOKEN`. Space `89282fb0-af94-8106-809e-0003c027fa07` and parent `3ed82fb0-af94-80dc-8272-f40b16376b81` are constants. The Exit 78 hold is not changed.

**S-02 [HIGH] — Production paths.** The runner does not import an Etsy client, a commission function, the scheduler, or the production Notion router.

### Gameability

**Verdict:** CONDITIONAL APPROVE. One high finding, resolved by the addendum.

**G-01 [HIGH] — An absent stage reported as PASS**

- **Prompt line:** 202, read against the unmerged QA and W10 work.
- **Cheap fake:** Write `PASS` for `qa` when `notion_qa.py` is not importable.
- **Ungameable for this slice:** A registry entry whose runner is missing records `NOT_RUN`. Evidence includes the git SHA, the asserted ids, write counts, and a redaction self-check. Dry-run is the default and performs no writes.

## 3. Corrective addendum

This addendum governs the sandbox-run slice. The prompt remains the unamended source of record.

1. Prove the prompt hash, then implement only the runner below. Do not mark Session 07 complete and do not change `state_revision`.
2. Reuse the Session 06 notion CLI token shape, redaction, and `SystemExit` style. Read the token only from `NOTION_SANDBOX_TOKEN`.
3. Assert the sandbox space and parent constants before any write. Refuse overrides, a missing token, and a mismatched target with a non-zero exit and zero writes.
4. Default to dry-run. `--execute` is the only path that runs build and variants.
5. On execute, call the merged build phases and `build_variants`. Do not import W9 or W10. Absent slots stay `NOT_RUN` and the QA verdict stays `NOT_RUN`.
6. Tests are fake-client only. Block sockets. Do not call the live Notion host from this session.

## 4. Deferrals

| Finding | Owner | Reason |
|---|---|---|
| Live execution of the runner | Grok Bot, at the merged SHA, on its own box | S-01. This slice implements the runner and does not run it |
| W9 QA | Unmerged | Registry slot `qa` stays `NOT_RUN` |
| W10 fact ledger and workflow link | Unmerged | Slots stay `NOT_RUN` |
| W11 close | Later | Slot `w11` stays `NOT_RUN` |
| Exit 78 scheduler hold | Unchanged | This runner does not lift or toggle it |
