# Session 11 Prompt Integrity Review

**Date:** 2026-10-16
**Prompt:** `prompts/implementation/14_SESSION_11_CUSTOMER_SUPPORT_AND_REPAIR.md`
**Verified SHA-256:** `f5e5c5a000285286bbc3389ae4dd564b3accd9cc820f01b506b8b1cb536a1428`
**Base:** `c01c7fc8f2894193499fcdcdbb850674419c8e9a` (`#117` merged). Session 11 is not activated. `current_session` stays 7. `state_revision` stays 64. Exit 78 stays HELD.

The prompt file is not amended. This record is the corrective addendum. Reviews: [S11 fidelity review](bc-fe96d15e-629c-59df-a237-5ad23d6697d1), [S11 safety review](bc-e9fc246e-b00c-5266-9c72-d9ab75a84aa4), [S11 gameability review](bc-266ccfef-89bf-5e4f-a084-141f564dedd3). All three returned CONDITIONAL APPROVE.

## 1. Prompt authenticity

**Status:** VERIFIED

The extracted file's SHA-256 equals the workbook appendix entry for `14_SESSION_11_CUSTOMER_SUPPORT_AND_REPAIR.md` (4,556 bytes, 200 lines). The required exit string in the file is `SESSION_11_SUPPORT_AND_REPAIR_COMPLETE`.

## 2. Three-dimensional review

### Fidelity

**Verdict:** CONDITIONAL APPROVE.

**F-01 [CRITICAL] — `support_mode: auto` is not `AutonomyMode`.** The enum is `simulation`, `draft`, and `live`. D-0020 and D-0023 keep buyer messages behind `external_message_enabled`, a positive cap, a recipient scope, and consent. The tracked template has the flag false, the cap at 0, and an empty scope list. **Amendment:** This wave does not send. `auto` returns a send count of 0 and no body. **Deferral:** a live or simulation send. Owner: an operator authority record.

**F-02 [HIGH] — The thirteen labels are not `IncidentType`.** The database check is the existing enum. `DEDUPE_REJECTION` is `DEDUPE_FAILED` to `ReconceptProductJob` (D-0013). `ACCOUNT_VERIFICATION` is `CREDENTIAL_FAILURE`, not an automatic repair. **Amendment:** Map each label onto the existing enum and name an existing job type. Do not add an enum value or a workflow edge.

**F-03 [HIGH] — The arrow chain is not the job graph.** D-0029 voids prompt step names as a second graph. D-0024 lets the verifier emit `REPAIR_COMPLETED`. **Amendment:** The plan names `IncidentRepairJob`, `NotionRepairJob`, `ListingRepairJob`, `LinkVerificationJob`, `ReconceptProductJob`, or `ResearchCollectionJob` and inserts none of them.

**F-04 [HIGH] — Commissioning A16.** A16 is `DESIGNED` with an empty evidence list. Its allowlist includes send, listing update, and page update. D-0028 requires an operator decision. **Amendment:** Do not edit `config/agents.yaml`. A test reads the committed file. **Deferral:** `TESTED` or `COMMISSIONED`. Owner: the operator under D-0028.

**F-05 [HIGH] — The persist list does not match `customer_issues`.** The table stores an opaque `buyer_reference` and a `safe_summary`. It has no product, variant, attachment, urgency, or raw-text column. **Amendment:** The ledger stores the opaque reference, a redacted summary, an attachment hash, and a content type. Product and variant ids are affected-object ids, not buyer text.

**F-06 [HIGH] — Section 5 would rewrite a published page in place.** D-0030 and D-0031 refuse that. **Deferral:** a Notion repair that writes a new version. Owner: the operator adapter session.

**F-07 [HIGH] — Re-lease can repeat an external write.** **Amendment:** An interrupted code echoes the supplied job id and refuses phase 0. It creates no workflow. **Deferral:** production re-lease. Owner: the operator Exit 78 decision.

**F-08 [HIGH] — No-sales work starts before the live maturity clock.** D-0014 is thirty accumulated live periods. **Amendment:** The no-sales code returns two uninserted plan steps at day 0 and day 14. **Deferral:** inserting those jobs. Owner: Session 11 after the maturity clock is running under an operator decision.

**F-09 [HIGH] — The exit string is not a D-0010 completion.** **Amendment:** Do not write `SESSION_11_SUPPORT_AND_REPAIR_COMPLETE`. Do not edit `IMPLEMENTATION_STATE.json`. **Deferral:** activation and the evidence contract. Owner: the operator, after Sessions 08, 09, and 10 are closed.

### Safety

**Verdict:** CONDITIONAL APPROVE.

**S-01 through S-04 [CRITICAL]** match F-01, F-04, and F-09. Literal execution would also start `worker.main` or `scheduler.main`. **Amendment:** Do not edit `worker.py` or `scheduler.py`. Do not insert `READY` or `PENDING` jobs. Tests open no socket and read no credential.

**S-05 [HIGH] — Issue text and attachment bytes.** **Amendment:** Store the hash and the content type. **Deferral:** attachment bytes. Owner: an operator privacy decision.

**S-06 and S-07 [HIGH]** match F-02 and F-03. Webhook, polling, and the operator console are absent. **Amendment:** One in-process function. No new route. **Deferral:** the console. Owner: Session 12. Provider webhooks stay with the operator.

**S-08 [HIGH] — One commit across the live stack.** **Amendment:** This wave owns `src/money_machine/assets/support_intake.py` and `tests/unit/assets/test_support_intake.py`. The integrator owns this review and the control-log lines. **Deferral:** incident-response and customer-experience review of a later diff, and the canonical commit subject. Owner: Session 11 Level 3 after operator activation.

### Gameability

**Verdict:** CONDITIONAL APPROVE.

**G-01, G-02, G-08 [CRITICAL/HIGH] — The exit string, A16 commissioned, and the control-file headings.** **Amendment:** The string, the commit subject `feat(support): automate buyer incidents and source repairs`, and a new completion boolean are absent from this diff. The A16 test reads `config/agents.yaml` and requires `DESIGNED` with an empty evidence list.

**G-03 [CRITICAL] — Two dicts that share a uuid.** **Amendment:** The caller cannot pass an incident id. The ledger key is shop, buyer reference, and received time. A second call returns the first incident id and the first summary.

**G-04, G-09 through G-14, G-16 [CRITICAL/HIGH] — A tuple of class names, or a keyword on "pdf" or "formula".** **Amendment:** The issue code is an argument. Summary text that contains "pdf" or "formula" does not change the code. Each of the thirteen codes has its own expected incident type and plan, so deleting one branch fails that case. **Deferral:** a fresh PDF read, a fresh Notion duplicate, a formula evaluation, and a real re-lease. Owner: the operator adapter session. This wave does not claim those reads.

**G-05, G-06, G-15, G-17, G-21 [CRITICAL] — `updated: true`, a caller-supplied `RESOLVED`, and a second file replace.** **Amendment:** `resolve_issue` returns `RESOLVED` only when the verification job id differs from the repair job id, the hashes match, and the read time is after the repair. Otherwise the status stays `OPEN` and the resolution fields stay empty. `record_repair` keeps one version per idempotency key. Provider write count stays 0. **Deferral:** the recording Etsy adapter and the persisted `NotionRepairJob`. Owner: the operator adapter session.

**G-07, G-18, G-19 [CRITICAL/HIGH] — A function that returns the word "sent".** **Amendment:** Draft, after a matching verification, returns one acknowledgement, the verification's own fix, the verification's own access path, and one reply invitation. Send count stays 0. `auto` returns no body and a send count of 0. A URL that is not the verification access path is not added.

**G-20 [HIGH] — A priority key the scheduler never reads.** **Amendment:** `preempts_routine` comes from the issue code. A caller-supplied integer does not flip it. `scheduler.main` is not called. **Deferral:** claim order inside the worker. Owner: the operator Exit 78 decision.

## 3. Corrective addendum

1. The prompt hash stays `f5e5c5a000285286bbc3389ae4dd564b3accd9cc820f01b506b8b1cb536a1428`. The prompt file stays byte-identical.
2. Session 11 stays inactive. `current_session` stays 7. `state_revision` stays 64. Do not edit `IMPLEMENTATION_STATE.json`. Do not write the exit string or the commit subject `feat(support): automate buyer incidents and source repairs`.
3. Do not edit `config/agents.yaml`, `config/workflows.yaml`, autonomy files, `worker.py`, or `scheduler.py`. A16 stays `DESIGNED` with empty `commissioning_evidence`. Exit 78 stays HELD.
4. Do not publish, spend, message a buyer, change a price, or call live Etsy, Notion, or S3. Tests open no socket and read no provider credential.
5. This wave owns `src/money_machine/assets/support_intake.py` and `tests/unit/assets/test_support_intake.py`.
6. The issue code is an argument. Summary words do not select it. Map the thirteen labels onto the existing `IncidentType`. Name existing job types. Insert no job.
7. The ledger key is shop, opaque buyer reference, and received time. A second call returns the same incident id and the first summary. The caller cannot supply the incident id.
8. Refuse a buyer reference or summary that contains a URL, an email address, `Bearer`, or `sk_`. The refusal code does not echo the value. Store an attachment sha256 and a content type, not bytes.
9. `ACCOUNT_VERIFICATION` is `BLOCKED` with zero writes and zero sends. `DEDUPE_REJECTION` cites the existing product, creates zero product ids, and names `ReconceptProductJob` without inserting it. `AGENT_RUN_INTERRUPTED` echoes the supplied job id, refuses phase 0, and creates no workflow. `NO_SALES_DIAGNOSIS` returns two uninserted steps at day 0 and day 14.
10. `resolve_issue` returns `RESOLVED` only when the verification job differs from the repair job, the hashes match, and the read is later. Otherwise the status stays `OPEN` and the resolution fields stay empty.
11. Draft mode after a matching verification returns the bounded body and a send count of 0. `auto` returns no body and a send count of 0.
12. The same repair idempotency key keeps one version. `preempts_routine` follows the issue code and ignores a caller integer.
13. Level 1: the focused tests, then `ruff format`, `ruff check`, and `pyright` on the two new files.

## 4. Deferrals

**D-01 — Session 11 activation, the exit string, and the evidence contract.** Owner: the operator, after Sessions 08, 09, and 10 are closed. Sessions 09 through 11 still have no `SESSION_EVIDENCE_KEYS` entry.

**D-02 — Commissioning A16 and lifting Exit 78.** Owner: the operator under D-0028.

**D-03 — Live Etsy messages, listing file replacement, Notion page repair, and attachment bytes.** Owner: an operator authority record. A present token is not authority.

**D-04 — Fresh PDF, Notion, formula, and buyer-path reads, and production re-lease.** Owner: the operator adapter session. This wave does not claim those reads.

**D-05 — Worker claim order and inserted no-sales jobs.** Owner: the operator Exit 78 decision.

**D-06 — The operator console and provider webhooks.** Owner: Session 12 for the console. Webhooks stay with the operator.

**D-07 — Incident-response and customer-experience review of a later diff, and the canonical commit subject.** Owner: Session 11 Level 3 after operator activation.

## 5. What already holds

`CUSTOMER_ISSUE_RECEIVED` and `BROKEN_LINK_DETECTED` already map to `IncidentRepairJob`. `IncidentRepairJob` already names `NotionRepairJob` and `ListingRepairJob`. `DEDUPE_FAILED` already maps to `ReconceptProductJob`. `customer_issues` already stores an opaque reference and a safe summary. A16 is already `DESIGNED` with an empty evidence list. `external_message_enabled` stays false.
