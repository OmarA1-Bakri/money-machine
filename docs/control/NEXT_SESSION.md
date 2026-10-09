# Next Session

**Session 06 is COMPLETE** (2026-10-02, W11 control flip @ `0f94d585`) — Notion integration foundation delivered W1–W10 (#39–#49). All eight evidence keys TRUE. Exit 78 unchanged: worker conditional lift (D-0028 gates), scheduler held. No production Notion or Etsy mutation. Default CLI probe remains `FakeNotionProbe`.

**Session 05 is COMPLETE** (2026-09-24, W11 control flip @ `9b791d45`) — domain agent implementation delivered L1-L4 (Etsy adapters, A03 research, A05 scoring/ProductSpec, A06 dedupe/workflow linking).

## Session 05 completion status (post-W11 @ `9b791d45`)

| Lane | Status | Commit | Evidence key(s) |
|---|---|---|---|
| **L1 — Etsy adapters** | **COMPLETE** | `02211ff` | `etsy_adapters_implemented` = true |
| **L2 — A03 Market Research** | **COMPLETE** | `c64bf58` | `research_agent_implemented`, `shortlist_analysis_implemented` = true |
| **L3 — A05 Product Strategy** | **COMPLETE** | `a7c9521` | `scoring_agent_implemented`, `product_spec_generation_implemented` = true |
| **L4 — A06 Catalogue Dedupe + workflow** | **COMPLETE** | `9b791d45` | `dedupe_agent_implemented`, `teardown_workflow_implemented`, `workflow_linking_complete` = true |
| W11 — control flip to COMPLETE | **COMPLETE** | — | `control_files_and_checkpoint_current`, `evidence_closure_commit_recorded` = true |

**All ten evidence keys TRUE.** Session 05 complete at W11 control flip.

**Exit 78 status UNCHANGED:**
- **Worker:** LIFTED conditionally (D-0028 commissioning gates). Claims READY jobs, executes via AgentRunner, persists results, emits events, creates successors. Uncommissioned agents (DESIGNED) refuse execution.
- **Scheduler:** HELD (W9 out of scope). Cycle (promote due jobs, detect stalled jobs, rebalance) remains fail-closed, deferred to future work.

**Parked L2-L4 nits (non-blocking):** concept_fingerprint drift, evidence SHA self-dump, differentiation self-desc, fail-open suppress, result_id=spec_id. Noted as carry-forward improvement opportunities.

## Session 06 completion status (post-W11 @ `0f94d585`)

| Wave | Status | Evidence key(s) |
|---|---|---|
| W1 — capability matrix, interface, fixture, router | **COMPLETE** | `notion_capability_inspected`, `platform_compatibility_documented`, `notion_adapter_interface_defined`, `fixture_adapter_implemented`, `adapter_router_implemented` |
| W2–W10 — adapters, builders, browser session, fake CLI | **COMPLETE** | `adapter_unit_tests_pass` (1958 passed, 1 skipped at W10) |
| W11 — control flip | **COMPLETE** | `control_files_and_checkpoint_current`, `evidence_closure_commit_recorded` |

Router browser and combined config modes still raise `NotImplementedError` (W4a). Fixture mode stays the default.

## Session 07 — sandbox run, rounds 10–12

**Status**: Incomplete (2026-10-09, state revision 59). This is not a session close and it is not SESSION_07 COMPLETE. Twelve evidence keys stay false. `next_session` stays 7. `next_prompt` stays `10_SESSION_07_PRODUCT_BUILD_VARIANTS_AND_QA.md`. `commissioned_agents` stays empty. STATE `head_sha` `4b899fcf6bf09730b952bf5517d6bd691b72ba9a` is the W10 squash. It is not this commit. `evidence_closure_commit_sha` stays the Session 06 closure tip. `last_verified_commit` stays bootstrap. Exit 78 scheduler stays HELD. The §11 sandbox CLI is still not run live; it comes after W11 and before W12.

Round 12 merges `build/full-automation` at `4b899fcf` (W10) into this branch and takes STATE revision 59. It relabels Verifier 6080655092's three text items (420 LT1 dropped; 472/487 are guard:479/:494; a missing `fstatfs` after creates is refused by `_refuse_proc_write`, `_fd_on_procfs` is the `OSError` path). The repeated `.`/`..` over-refusal at guard:603 is parked as Reviewer SF, fail-closed over-refusal (it can start at 2 repeats). Sandbox tests: 355 passed. Full local pytest: 3215 passed, 193 skipped, 12 failed (`docker` absent).

Rounds 10–11 status (superseded by round 12): incomplete, state revision 58. This is not a session close and it is not SESSION_07 COMPLETE. Twelve evidence keys stay false. `next_session` stays 7. `commissioned_agents` stays empty. STATE `head_sha` `a4e9b025021b4effbb2b2879c1db756403cb1676` stays the W9 squash. Exit 78 scheduler stays HELD. The §11 sandbox CLI is still not run live.

Round 11 answers Verifier 6079607643 and Reviewer 5469228650 at `518d5215` (text only). Body and log claims are relabelled. A libc without `statfs` or `fstatfs` is refused (64) before any read; `fstatfs` lost after creates is 69 with ids printed. Sandbox tests: 355 passed. Full local pytest: 2670 passed, 193 skipped, 12 failed (`docker` absent).

Round 10 answers Reviewer 5468752023 at `9d350221`. The guard no longer refuses a nested relative symlink chain (K=2, 8, 16 accepted at the public entry). Cycles and self-loops stay refused. The SIGINT race hook is installed before `SIG_IGN` and restored by `main`. Parked (corrected in round 11; `518d5215` coordinates, see round 12): `_WALK_LIMIT = 257`, guard 396 F, 420 LT1, 472 F, 487:8 F, 487:16 ×4, ns:349 ×10, ns:352 ×3, plus the r8 CLI-masked and no-libc sets. Sandbox tests: 351 passed. Full local pytest: 2666 passed, 193 skipped, 12 failed (`docker` absent).

## Session 07 — sandbox run, round 9

**Status**: Incomplete (2026-10-09, state revision 58). This is not a session close and it is not SESSION_07 COMPLETE. Twelve evidence keys stay false. `next_session` stays 7. `next_prompt` stays `10_SESSION_07_PRODUCT_BUILD_VARIANTS_AND_QA.md`. A07, A08, and A09 stay DESIGNED. `commissioned_agents` stays empty. STATE `head_sha` `a4e9b025021b4effbb2b2879c1db756403cb1676` stays the W9 squash. It is not this commit. `evidence_closure_commit_sha` stays the Session 06 closure tip. `last_verified_commit` stays bootstrap. Exit 78 scheduler stays HELD. The §11 sandbox CLI is still not run live. `origin/build/full-automation` is still `a4e9b025`.

Round 9 answers Reviewer 5468348253 at `fc9c01c3`. Missing libc or empty mountinfo is 64 before any POST. libc is cached `CDLL(None)`. Mountinfo octal escapes are decoded. Unique walk nodes accept K≥16 and refuse a cycle. **No equivalents are claimed.** The `_is_proc`→False, walk-limit, and ns:456 EQ claims and the `11/3 EQ` label are withdrawn. Census: if 218, boolop 72, and 27, or 45, clause 153, ifexp 8, while 3. Total 1204. **The 1204-row table was not run.** Named probes are in `IMPLEMENTATION_LOG.md`. Sandbox tests: 345 passed. Full local pytest: 2660 passed, 193 skipped, 12 failed (`docker` absent).

## Session 07 — sandbox run, round 8

**Status**: Incomplete (2026-10-09, state revision 58). This is not a session close and it is not SESSION_07 COMPLETE. Twelve evidence keys stay false. `next_session` stays 7. `next_prompt` stays `10_SESSION_07_PRODUCT_BUILD_VARIANTS_AND_QA.md`. A07, A08, and A09 stay DESIGNED. `commissioned_agents` stays empty. STATE `head_sha` `a4e9b025021b4effbb2b2879c1db756403cb1676` stays the W9 squash. It is not this commit. `evidence_closure_commit_sha` stays the Session 06 closure tip. `last_verified_commit` stays bootstrap. Exit 78 scheduler stays HELD. The §11 sandbox CLI is still not run live. `origin/build/full-automation` is still `a4e9b025`. Whichever PR merges second re-syncs STATE.

Round 8 answers Reviewer 5467032904 at `e571b8e7`. `under_proc` detects procfs by `statfs` `f_type == 0x9fa0` or mountinfo fstype `proc`, not by `st_dev` versus `/proc`. Bind-mounted `/proc` and a second procfs instance are refused via monkeypatched fstype. `_raise_interrupt` installs `SIG_IGN` first. LINK ENOENT after creates is 69 with ids. Evidence writes use parent-dirfd `openat`/`linkat`. The false EQs `_on_procfs`→False and `_tmp_kind` S_ISLNK→False are withdrawn. Census: if 212, boolop 71, and 26, or 45, clause 151, ifexp 8, while 3. Total 1179. **The 1179-row table was not run; no file-level sum is claimed.** Named serial probes are in `IMPLEMENTATION_LOG.md`. Sandbox tests: 336 passed. Full local pytest: 2651 passed, 193 skipped, 12 failed (`docker` absent). This commit's CI is not invented here. Verifier verdict on `e571b8e7` had not landed.

## Session 07 — sandbox run, round 7

**Status**: Incomplete (2026-10-09, state revision 58). This is not a session close and it is not SESSION_07 COMPLETE. Twelve evidence keys stay false. `next_session` stays 7. `next_prompt` stays `10_SESSION_07_PRODUCT_BUILD_VARIANTS_AND_QA.md`. A07, A08, and A09 stay DESIGNED. `commissioned_agents` stays empty. STATE `head_sha` `a4e9b025021b4effbb2b2879c1db756403cb1676` stays the W9 squash. It is not this commit. `evidence_closure_commit_sha` stays the Session 06 closure tip. `last_verified_commit` stays bootstrap. Exit 78 scheduler stays HELD. The §11 sandbox CLI is still not run live. `origin/build/full-automation` is still `a4e9b025`. Whichever PR merges second re-syncs STATE.

Round 7 answers Reviewer 5465945944 at `8f77434c`. `under_proc` uses procfs `st_dev` plus symlink-target walks so `realpath('/proc/self/root') == '/'` is not a bypass. Leftover hostile `.tmp` is refused before any POST. A leftover tmp symlink after creates is 69 and is not followed. Gap-0 SIGINT at POST:2 still prints ids. A 50 ms second SIGINT exits 69, not -2. Census: if 190, boolop 65, and 25, or 40, clause 138, ifexp 8, while 4. Total 1069. **The 1069-row table was not run; no file-level sum is claimed.** Named serial probes are in `IMPLEMENTATION_LOG.md`. Sandbox tests: 320 passed. Full local pytest: 2635 passed, 193 skipped, 12 failed (`docker` absent). This commit's CI is not invented here. Verifier verdict on `8f77434c` had not landed.

## Session 07 — sandbox run, round 6

**Status**: Incomplete (2026-10-09, state revision 58). This is not a session close and it is not SESSION_07 COMPLETE. Twelve evidence keys stay false. `next_session` stays 7. `next_prompt` stays `10_SESSION_07_PRODUCT_BUILD_VARIANTS_AND_QA.md`. A07, A08, and A09 stay DESIGNED. `commissioned_agents` stays empty. STATE `head_sha` `a4e9b025021b4effbb2b2879c1db756403cb1676` stays the W9 squash. It is not this commit. `evidence_closure_commit_sha` stays the Session 06 closure tip. `last_verified_commit` stays bootstrap. Exit 78 scheduler stays HELD. The §11 sandbox CLI is still not run live. `origin/build/full-automation` is still `a4e9b025`. Whichever PR merges second re-syncs STATE.

Round 6 answers Reviewer 5465433904 and Verifier 6073572255 at `bcf9a36c`. `under_proc` refuses `//proc/...` and a symlink to `/proc`. A leftover `.tmp` or `O_EXCL` EEXIST after creates exits 69 with ids. The eight behaviour-changing survivors from `bcf9a36c` were rewritten off IfExp and each replacement has a serial killing test. Census: if 164, boolop 57, and 23, or 34, clause 121, ifexp 8, while 3. Total 931. **The 931-row table was not re-run; no 213/213 or Failed-sum claim is made.** The withdrawn `bcf9a36c` claim was 213/213 sum 6371; Verifier measured 205/8 sum 5761 and Reviewer 205/8 sum 5704. Sandbox tests: 300 passed. This commit's CI is not invented here.

## Session 07 — sandbox run, round 5

**Status**: Incomplete (2026-10-09, state revision 58). This is not a session close and it is not SESSION_07 COMPLETE. Twelve evidence keys stay false. `next_session` stays 7. `next_prompt` stays `10_SESSION_07_PRODUCT_BUILD_VARIANTS_AND_QA.md`. A07, A08, and A09 stay DESIGNED. `commissioned_agents` stays empty. STATE `head_sha` `a4e9b025021b4effbb2b2879c1db756403cb1676` stays the W9 squash. It is not this commit. `evidence_closure_commit_sha` stays the Session 06 closure tip. `last_verified_commit` stays bootstrap. Exit 78 scheduler stays HELD. The §11 sandbox CLI is still not run live. `origin/build/full-automation` is still `a4e9b025`. Whichever PR merges second re-syncs STATE.

Round 5 folds the round-4 Reviewer FAIL, the round-4 Verifier FAIL, and CodeRabbit's CHANGES_REQUESTED at `69a2b421` into one commit. A SIGINT during the evidence write keeps every stage that passed. Repeated SIGINTs during the interrupt publish are ignored until the file is complete. The four round-4 false EQUIVALENTs have killing tests, and created time is bounded on both sides. Census: if 156, boolop 55, and 23, or 32, clause 117, ifexp 14, while 3. Mutations: if-flip 156, force-true 156, force-false 156, operator swap 55, clause negation 117, literal clause True/False 234, ifexp True/False 28, while-flip 3. Total 905. **The final-tree sweep is PARTIAL.** It was stopped at 07:43 (UTC+7) so this round would not block on it. `notion_sandbox.py` is COMPLETE: 213 of 213 mutations, 213 killed, 0 survived, 0 timeouts, Failed sum 6371 (if-flip 32 rows, 32 killed, Failed sum 1475; force-true 32 rows, 32 killed, Failed sum 1157; force-false 32 rows, 32 killed, Failed sum 458; operator swap 13 rows, 13 killed, Failed sum 223; clause negation 28 rows, 28 killed, Failed sum 1221; literal clause True/False 56 rows, 56 killed, Failed sum 1385; ifexp True/False 20 rows, 20 killed, Failed sum 452; while-flip 0 rows, 0 killed, Failed sum 0). `notion_sandbox_guard.py` is PARTIAL: 71 of 286 mutations finished (force_false 12, force_true 12, if 12, negate 10, operand 20, swap 5), 71 killed, 0 survived, Failed sum 2848. Those rows come from the worker log, which has no first-failing-test column. `notion_sandbox_live.py` (225 mutations) and `notion_sandbox_pipeline.py` (181) were NOT swept on this tree. Run so far: 284 of 905 mutations, 284 killed, 0 survived, 0 timeouts, Failed sum 9219. 621 mutations are not run and carry no claim. The finished rows and the blocker-to-test map are in `IMPLEMENTATION_LOG.md`. Sandbox tests: 291 passed. Full local pytest: 2811 collected, 2606 passed, 193 skipped, 12 failed. This commit's CI is not invented here.

## Session 07 — sandbox run, round 4

**Status**: Incomplete (2026-10-08, state revision 58). This is not a session close and it is not SESSION_07 COMPLETE. Twelve evidence keys stay false. `next_session` stays 7. `next_prompt` stays `10_SESSION_07_PRODUCT_BUILD_VARIANTS_AND_QA.md`. A07, A08, and A09 stay DESIGNED. `commissioned_agents` stays empty. STATE `head_sha` `a4e9b025021b4effbb2b2879c1db756403cb1676` stays the W9 squash. It is not this commit. `evidence_closure_commit_sha` stays the Session 06 closure tip. `last_verified_commit` stays bootstrap. Exit 78 scheduler stays HELD. The §11 sandbox CLI is still not run live. `origin/build/full-automation` is still `a4e9b025`. Whichever PR merges second re-syncs STATE.

Round 4 folds the Reviewer FAIL and the Verifier FAIL at `9cf574c0` into one commit. A real SIGINT writes `INTERRUPTED` evidence that keeps every created id and exits 69. A created time on the same floored minute exits 0. Census is one AST walk: if 159, boolop 63, and 26, or 37, clause 141, ifexp 16, while 3. If-flip: 159 killed, 0 equivalent, Failed sum 5924. Force-true: 154 killed, 5 equivalent, Failed sum 5320. Force-false: 156 killed, 3 equivalent, Failed sum 813. Boolean operands: 200 killed, 4 equivalent, Failed sum 5824. The tables and the probes are in `IMPLEMENTATION_LOG.md`. Sandbox tests: 231 passed. Full local pytest: 2751 collected, 2546 passed, 193 skipped, 12 failed (docker absent). This commit's CI is not invented here.

## Session 07 — sandbox run, round 3

**Status**: Incomplete (2026-10-07, state revision 58). This is not a session close and it is not SESSION_07 COMPLETE. Twelve evidence keys stay false. `next_session` stays 7. `next_prompt` stays `10_SESSION_07_PRODUCT_BUILD_VARIANTS_AND_QA.md`. A07, A08, and A09 stay DESIGNED. `commissioned_agents` stays empty. STATE `head_sha` `a4e9b025021b4effbb2b2879c1db756403cb1676` stays the W9 squash. It is not this commit. `evidence_closure_commit_sha` stays the Session 06 closure tip. `last_verified_commit` stays bootstrap. Exit 78 scheduler stays HELD. The §11 sandbox CLI is still not run live. W10 is in flight from `a4e9b025` and will also bump STATE, so whichever PR merges second re-syncs.

Round 3 folds the Reviewer FAIL and the Verifier FAIL at `6dc72f1e` into one commit. Created page ids are appended inside `create_child_page` as soon as the response parses. An empty page space is accepted when the bot workspace matches and the parent chain reaches the sandbox parent. An explicit different space, and an archived confirm or chain read, are refused and left out of `created_pages`. Other later failures keep the id. Census is one AST walk: if 133, boolop 52, and 20, or 32, clause 116, ifexp 11, while 2. If-flip: 133 killed, 0 equivalent, Failed sum 4364. T45 is row 55, `notion_sandbox_guard.py:304`, Failed 1. `__name__ == "__main__"` is row 27, Failed 1. Force-true: 128 killed, 5 equivalent, Failed sum 3894. Force-false: 125 killed, 8 equivalent, Failed sum 629. Boolean operands: 162 killed, 6 equivalent, Failed sum 4460. The tables and the probes are in `IMPLEMENTATION_LOG.md`. Sandbox tests: 185 passed. Full local pytest: 2705 collected, 2500 passed, 193 skipped, 12 failed (docker absent). This commit's CI is not invented here.

## Session 07 — Wave 10 handoff

**Status**: Incomplete (2026-10-07, W10, state revision 58). This is not a session close and it is not SESSION_07 COMPLETE. Twelve evidence keys stay false, including `product_fact_ledger_persisted` and `build_workflow_linked`. `next_session` stays 7. `next_prompt` stays `10_SESSION_07_PRODUCT_BUILD_VARIANTS_AND_QA.md`. A07, A08, and A09 stay DESIGNED. `commissioned_agents` stays empty. STATE `head_sha` `a4e9b025021b4effbb2b2879c1db756403cb1676` is the intentional tip-sync to the W9 squash. It is not this commit. `evidence_closure_commit_sha` stays the Session 06 closure tip. `last_verified_commit` stays bootstrap. Exit 78 scheduler stays HELD.

W10 handoff. Counts and sites are in `IMPLEMENTATION_LOG.md` and `TEST_EVIDENCE.md`.

- Fixture fact ledger and workflow link over the QA checkpoint, through `FixtureNotionAdapter` only. `run_fact_ledger` is async at `notion_fact_ledger.py:156`. `_plan` at `:377` awaits `live_qa_passed` before `_write` at `:929` and `write_checkpoint` at `:969`. When the caller names the checkpoint, a live purpose, buyer, or practice edit is `BLOCKED`. A mismatched caller after that edit raises `fact ledger caller does not match` and writes nothing. A stored `BLOCKED` is not overwritten. An unnamed 64-character hub name still passes. On-disk `next_phase` matches memory (`test_matrix`). Tier follows the stored database kinds. `qa_verdict` is `stored_pass and qa_live`. A `BLOCKED` record whose checks changed can be re-planned when the caller matches. A forged fact on an unchanged check row writes nothing. Each of ten edges is checked on admitted events, successor types, and `event_successor_map`. The link is ready at ListingCopyJob and does not create a job. No ListingCopyJob reads the ledger. Known ids only, so the proof copy is not counted and `page_count` stays 15. Narrative `next_phase` is `test_matrix` and is not started.
- Empty captured URL `""` is skipped in QA and repairs like a missing URL (`notion_qa.py:557`). On the ledger, `""` and `None` for a published page are `BLOCKED` and the fact component is `missing`.
- Earlier `repair_jobs` are kept across `write_checkpoint` (`notion_progress_record.py:185`). A stale checkpoint tmp is removed by a literal name match (`notion_progress.py:219`). A live pid's temp is kept.
- Mutation checks are in `IMPLEMENTATION_LOG.md`. Round 9 (operands PARTIAL): 173 rows, 161 killed, 12 equivalent, Failed sum 12345. If-flips 123/123, Failed 11439. IfExp 26 rows, 25 killed, 1 equivalent. Operands and flips PARTIAL, 16 rows, 5 killed, 11 equivalent, Failed 17. There are 12 equivalents in total. Census 377 decision sites + 131 operands = 508. Round 8 (tip `08484bf0`, operands PARTIAL): if-flips 119/119, Failed 11346. IfExp 26 rows, 24 killed, 2 equivalent. The 16 Round 7 equivalents re-run: 5 killed, 11 equivalent. Progress 43/43, Failed 2050. QA 43/43, Failed 4396. Variants 13/13. There are 13 equivalents in total. Census 369 decision sites + 129 operands = 498. Round 7 (tip `1e614857`): 539 rows, 523 killed, 16 equivalent, Failed sum 26113. Ledger operands: 329 rows, 313 killed, 16 equivalent, Failed sum 10283. Ledger if-flips: 115 killed, Failed sum 10551. Progress 40 killed, Failed sum 1579. QA changed lines 42 killed, Failed sum 3687. Variants 13 killed, Failed sum 13. QA, progress, and variant lines ran with 1 worker. Census of `notion_fact_ledger.py`: 362 decision sites + 128 operands = 490. Product-build tests: 879 passed. Tip `0b2007a7` (Round 6) was one pass of 536 rows, 516 killed, 20 equivalent, Failed sum 24160. Ledger operands: 329 rows, 309 killed, 20 equivalent, Failed sum 9826. Ledger if-flips: 112 killed, Failed sum 9328. Census of `notion_fact_ledger.py`: 357 decision sites + 128 operands = 485. On tip `45818d9e`, 338 decision sites + 125 operands = 463, and that tip's if-flip run was 104 killed, Failed sum 8131. The 859-passed figure was tip `0b2007a7`. The 826 figure and the 8845/8131/17052 sums were tip `45818d9e`. The 791 figure and the 7464/6756/14261 sums were tip `5dc55814` (the sums were a merged earlier suite; the reviewer and the verifier measured 7591/6861/14493 on that tip). The 732 and 55-equivalent figures were tip `9eff481e`. SQLAlchemy here is lockfile 2.0.52. Without `asyncpg`, `tests/integration` is 21 passed and 193 skipped.
- `docs/control` edits this wave: `IMPLEMENTATION_STATE.json` (not bumped this round), `IMPLEMENTATION_LOG.md`, `NEXT_SESSION.md`, `TEST_EVIDENCE.md`, `DECISIONS.md`, and `docs/control/reviews/2026-10-05-session-07-prompt-integrity.md`.

### Parked for the W11 test matrix

QA records PASS even when these are deleted: the home nav text, the 3 palette callouts, the identity callout, the 6 hub "returns to Home" texts, and the 3 home linked views (Tasks, Events, Notes). Uncovered code: `_linked_views` at `notion_qa.py:406`, `_palette` at `:667`, and `_teardown` at `:699`. Scheduled for the W11 test matrix. Not fixed in W10.

Popping a page that is not a known id before the first ledger run is pinned as `PASS` with one checkpoint write (`test_unknown_page_before_the_ledger_is_not_a_fact`). The proof page is not a known id. That is intended.

The pull request body lists the `docs/control` edits. This handoff lists them above.


W9 counts stay in `IMPLEMENTATION_LOG.md`. The 17 variant-file rows from that table were remeasured in W10. An extra workspace `/ Blue` still passes variants replay even with a child under it. Provenance beyond title and copyable shell fields stays parked. One home page per probe stays parked. Deep clone of databases stays rejected. Docstring coverage 14.95% was measured by Eng Ops and was not re-measured.

W8 counts stay in `IMPLEMENTATION_LOG.md`. Adopted-page unpublished, template, indexing, icon, and cover drift is still repaired by `_finish_variant`, and that repair is intended.

## Later sessions

**Session 05 delivered scope**:
- L1: Etsy fixture adapter, browser/API stubs, config-driven seed phrases, comprehensive tests
- L2: A03 Market Research agent (fixture-only), ResearchReport with ShortlistAnalysis (top 5 candidates)
- L3: A05 Product Strategy scorer (four-criterion: price/demand/young-fast shops/thin evidence), qualification gate (≥20/40), ProductSpec generation
- L4: A06 Catalogue Dedupe agent (three-rule: exact identity×category, title Jaccard ≥0.7, concept fingerprint), PASS/TOO_CLOSE branching, EventDispatcher workflow linking, fixture teardown

**Remaining domain agent scope** (Session 07+):
- Concept agent (A04): concept definition, differentiation, design specification
- Notion Build agent (A07): workspace setup, database schema, draft pages (successor to DEDUPE_PASSED)
- Variant agent (A08): colour/hub expansion, SKU generation
- Reconcept agent (A08 alt): reconcept loop (successor to DEDUPE_FAILED, L4 out of scope)
- Merchandising agent (A10): description copy, SEO tags, pricing strategy
- QA agent (A11): build artifact validation, preflight checks
- Publisher agent (A12): Etsy draft creation, publication, link verification
- Analytics agent (A14): metrics collection, performance analysis

Later sessions will promote remaining domain agents from DESIGNED to TESTED with:
- Agent-specific prompts (v1)
- Integration tests (real database, fake providers)
- Contract tests (prompt integrity, tool permissions, commissioning refusal)
- Commissioning evidence gates per D-0028
- No live Notion/Etsy mutations until commissioning approval

Those sessions do NOT include:
- Scheduler Exit 78 lift (deferred; promote/stalled-detection/rebalance cycle scope)
- Live production claims
- Commissioning approval to COMMISSIONED state (requires operator decision record)

Session 04 closed 2026-09-20 after W10 control flip (#29, `14da7fe`). Agent runtime delivered, Exit 78 lifted for worker (conditionally, behind D-0028 commissioning gates).

Session 03 closed 2026-09-19 after Verifier FINAL PASS (#17). Gap-close implementation validated: real `dependency_resolver`, scheduler library functions, operator surface (CLI + API), entry-job spawn.

## Carry-forward work

- Prove idempotency uniqueness under a concurrent claim path (only after commissioning).
- Refuse an unreconciled `MetricsSnapshot` as a decision input (Session 02 review, deferred).
- Install Playwright with the first browser-channel work, not before.
- Relate listing description sections and tags as rows rather than checked JSON arrays when merchandising is built (Session 08).
- Vendor capability for every `DIRECT_API` selection, and Etsy field-length limits, remain UNVERIFIED until the owning session reads and cites the vendor reference.
- The CodeRabbit vendor re-review of the Session 00 fixes is still rate-limited; the blocker stays in state.
- **S05 L2-L4 parked nits** (non-blocking, recorded for future lane improvement):
  1. **Concept fingerprint drift**: A05 hashes identity:category (product_strategy.py:278), L4 fixtures hash buyer_problem only (products.py:97) — cross-lane contract inconsistency
  2. **Evidence SHA self-dump**: A05 evidence SHA reuses concept_fingerprint (product_strategy.py:328) instead of independent hash
  3. **Differentiation self-description**: Dedupe differentiation_evidence describes candidate's own fields (dedupe.py:216-225) rather than comparative differentiation from catalogue
  4. **Fail-open suppression**: A06 uses contextlib.suppress(Exception) on invalid spec parsing (catalogue_dedupe.py:115) instead of fail-closed refusal
  5. **Result ID reuse**: Dedupe result_id = spec_id (dedupe.py:231) — could use distinct UUID for audit trail clarity
- **S06 parked nits** (non-blocking, not fixed in the close):
  1. An int-subclass SystemExit code maps to 1
  2. The False SystemExit row needs an isinstance-style mutant
  3. Backtick formatting of `__context__` in the #49 PR body
  4. CodeRabbit APPROVED tip lag on #49
  5. `connected: true` in fake mode (`notion.py` connect payload), still open from review 5328507848
  6. argparse echoing a token passed as an extra argument, still open from review 5328507848

## Environment notes

- The shared development database `money_machine` holds another branch's schema at its own Alembic revision, and the instance carries roughly four hundred leftover test databases from other branches. Nothing on this branch touches them: database-backed tests create and drop their own throwaway databases, and `MONEY_MACHINE_TEST_ADMIN_DATABASE_URL` selects the maintenance connection.
- `pnpm install` needs `--package-import-method copy` on this filesystem: the hardlink rename fails on the 9p `/mnt/d` mount.
- Host port 3000 is occupied by an unrelated development server; set `WEB_PORT` to verify the web container.
