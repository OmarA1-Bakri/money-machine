## 2026-10-10 — Session 07 W12: session close prepared (pending Omar close gate)

Session 07 stays incomplete. This wave prepares the close. SESSION_07 COMPLETE is not in effect until CI, Reviewer and Verifier PASS, a Lead Reviewer LEAD PASS, and Omar's explicit close gate. STATE revision 62 to 63. `head_sha` is `98fc06d2d37b206075b6bc91cf1dc964d2f0258f`, the W13 squash. It is the tip-sync pointer. It is not this commit. The required branch point was `ae2ca6e41a0c6ff87437a53db91feb50bc5a82b3`. `evidence_closure_commit_sha` stays `0f94d585f23d79e5ac18479f01e14f67cbaad332`. `last_verified_commit` stays bootstrap. Twelve session 7 evidence keys stay false. No evidence key flips because of §11. A07, A08, and A09 stay DESIGNED. `commissioned_agents` stays empty. Exit 78 stays HELD. `current_session` stays 7. `next_session` stays 7. `next_prompt` stays `10_SESSION_07_PRODUCT_BUILD_VARIANTS_AND_QA.md`.

Prompt integrity is the Wave 12 addendum in `docs/control/reviews/2026-10-05-session-07-prompt-integrity.md`. The prompt file is unchanged. SHA-256 `d52011a6f0b725b16427629dc664cfc9f3432c4b5f71d26ce032d4b6c8ecb39d`. Item 6 of the Wave 11 addendum is withdrawn there: the three pins pass on `4b899fcf` and kill mutants.

Fixtures only. No live Notion, no Etsy, no `--execute`.

Section 11. Sandbox MM S06 Sandbox only. X1 at 2026-10-10 08:54 ICT created 5 title-only pages. Cleanup at 2026-10-10 09:05 ICT trashed them. `exec-1791597254.json` sha256 `fc642066fa96470ac77b5bc4621945927e6c7265a6e23ff68ffab0ae4b2cea10`. `cleanup/exec.json` sha256 `e3d4a547d6f4a1cf0a4bb3d4934ec89099341bf7779fb4074249fc326820a97d`. Reviewer and Verifier PASS on all three evidence gates. Title-only, QA NOT_RUN. Not citable for `shared_databases_built` or `home_dashboard_built`.

`STAGE_REGISTRY` (`notion_sandbox.py`) keeps `qa`, `fact_ledger`, `workflow_link`, and `w11` as None. The comment that said those waves were not merged is replaced. Wiring them would let a later `--execute` report PASS. `w11` is the session-close gate, not a sandbox runner.

- `os.replace` during a repair record. `write_document` leaves a complete temp when `os.replace` fails. `adopt_checkpoint_temps` (`notion_progress.py`) installs that temp at the start of `run_product_qa`. `test_replace_crash_keeps_the_repair_on_resume` covers `published`, `duplicate_button`, and `search_indexing`. Resume is PASS, the name is stored, and the only later adapter call is `duplicate_page` (the proof). The repair method is not called again.
- `in repairs` at `notion_qa.py` inside `_apply_repairs`. `test_unrequested_repair_is_not_applied` calls the helper with `("published",)` while the page still needs `duplicate_button` and `search_indexing`. Neither method runs. Passes on `ae2ca6e4`. Kills a helper-level force-true of those membership tests.
- Post-loop `record_applied_repairs` after `_apply_repairs` returns. Equivalent. The loop stores every name before it returns. The post-loop call only fills a name the loop returned and had not stored. This loop does not leave one.
- `notion_qa.py:145` `if not stored.variants or stored.next_phase != PHASE_QA`. `load_variant_checkpoint` returns a checkpoint with variants only together with `next_phase == PHASE_QA`, and `_require_records` rejects an empty list. So `not stored.variants` is true exactly when `next_phase != PHASE_QA` at this public entry. `and` instead of `or` is the same on every checkpoint the loader returns. Negating either side raises on the ordinary PASS path, which the existing PASS tests already kill. Not a code change.
- `notion_qa.py:156` `if not plan.blocked and plan.repairs`. `_plan` sets `repairs` to `()` whenever `blocked` is true, so `bool(plan.repairs)` implies `not plan.blocked`. Negating `not plan.blocked` skips every repair. The existing repair tests kill that. `and` to `or`, and negating `plan.repairs`, enter `_apply_repairs(())` on a clean PASS. That calls `guard_operation(OP_QA)` and returns. `_prove_duplicate` calls `guard_operation(OP_QA)` on that same path. No second adapter write is unique to the empty call. Equivalent at the public entry. Not a code change.
- `prose_digest` length-prefixes each field with 4 bytes. That encoding is D-0031, already on `98fc06d`. `test_newline_boundary_does_not_share_a_prose_digest` uses hub descriptions `alpha\nbeta` versus `alpha` plus `beta\n` plus the next description. The newline-join collides. The length prefix does not. Hub builds still refuse a newline (`hub fields must be single lines`), so the ledger test restamps the stored digest. `test_newline_boundary_is_not_the_same_caller` expects `fact ledger caller does not match` and zero writes. The ledger call itself does not re-run QA. A QA re-run happens only for the judged caller (D-0031).
- `_normalised_secret_link` stores `scheme://host` or `missing`. That is D-0031, already on `98fc06d`. The page id, userinfo, port, path, query, and fragment are not stored. `test_query_or_fragment_token_is_not_a_qa_fact` covers `?token=`, `?a=1&token=`, `#token=`, and `?token=#frag`. The QA fact is `https://fixture.notion.site` repeated once per colour. The forged variant row still holds the input URL. That row is the checkpoint input, not the QA fact.
- Dot aliases. `_is_dot_alias` reads the raw `readlink` text. Parts that are only `.` and `..` do not trip `target_key in seen_symlinks`. A proc target is still refused before that exemption. `test_repeated_dot_symlink_is_accepted` (`here -> .` five times) and `test_repeated_dotdot_symlink_is_accepted` (`d/x/up -> ..`, `up/x` five times) expect `under_proc` false. `test_symlink_self_loop_is_refused` and `test_symlink_cycle_is_refused` stay refused. `test_dot_alias_to_proc_is_still_refused` pins the proc check.
- `_WALK_LIMIT` stays 256. A sibling chain of 255 is refused. The same chain is accepted when the limit is 257. `test_real_walk_limit_refuses_a_255_chain` asserts the stock refusal. Measured on this machine before the test was written.
- `test_libc_is_loaded_once` counts `CDLL` calls. Two `_libc()` calls load once. Kills `if _libc_cache is not None` forced false. Passes on `ae2ca6e4`.
- `test_statfs_nonzero_returns_none` makes `statfs` and `fstatfs` return -1 and expects None. Kills `if result != 0` forced false in both helpers. Passes on `ae2ca6e4`. `if lib is None` forced false in those helpers is equivalent: the `AttributeError` handler returns None.
- `guard` `if lib is None or not hasattr(lib, "statfs") or not hasattr(lib, "fstatfs")`. The LF0 that survives on a missing libc is equivalent. `hasattr(None, ...)` is false, and `or` short-circuits, so a missing libc is still not ready. A libc that has `statfs` and lacks `fstatfs` is already refused by `test_libc_without_statfs_symbol_refuses_before_any_post`.
- `test_empty_mountinfo_helper_is_proc` calls `_mountinfo_is_proc` with blank text and expects true. Kills `if not text.strip()` forced false. The public `under_proc` path does not reach it: `_detection_ready` already requires usable mountinfo. Passes on `ae2ca6e4`.
- Mount compare. `test_exact_proc_mount_matches` requires equality with the mount point. `test_unrelated_proc_mount_does_not_match` requires a proc mount on another path to leave this path alone. `test_later_short_proc_mount_does_not_win` already requires the longer non-proc mount to win. Together they kill a forced-false match, a swapped `==`, a failed `startswith`, and `or` changed to `and`.
- `test_proc_parent_is_refused_when_the_leaf_is_not` makes only the parent directory touch proc. Kills the prefix-loop `if` forced false and the component operand forced false. The same check on `current` (`if _is_proc(current) or _component_touches_proc(current)`) is equivalent to the prefix loop, because `_prefixes` includes `current`. One `if` forced false, a swap, or one operand forced false on that line still returns true from the prefix loop. The symlink-target proc check is equivalent for the same reason: the target is appended and the later visit catches `/proc`.
- `test_unreadable_symlink_is_not_a_proc_path` raises `OSError` from `readlink`. Stock skips it. Forcing `if target is None` false calls `_is_proc(None)` and raises. Passes on `ae2ca6e4`.
- `test_resolved_proc_target_is_refused` returns `/proc` from `_safe_realpath` for a plain directory target, with `_component_touches_proc` false. Kills `if target_resolved is not None` forced false. `test_missing_realpath_is_not_appended` returns None and expects false with no exception. Kills the negated condition and the force-true, both of which append None. Passes on `ae2ca6e4`.
- `test_fd_oserror_after_creates_prints_the_ids` raises `OSError` from `_fd_on_procfs` after five creates. Exit 69, `evidence write failed`, and all five ids on stderr. The stock `OSError` path already prints the ids. The gap was the missing test. Passes on `ae2ca6e4`.
- `test_sigint_race_hook_filters_only_the_race_oserror` drops an `OSError` whose text contains `race condition`, and forwards a different `OSError` and a `ValueError` that contains that text. `test_missing_unraisablehook_does_not_raise` sets `__unraisablehook__` to None. Passes on `ae2ca6e4`.
- The r8 "6 CLI-masked and 10 no-libc" rows were a count at `fc9c01c3`, not a list of sites. This repo never records the 16 line and mutant identities. There is no mutant to edit. Named survivors from that era that still have coordinates are the rows above.

`tests/unit/cli/test_notion_sandbox.py` was not split. Sockets stay blocked.

`test_stale_checkpoint_tmp_is_removed_on_the_next_write` used pid 999. CI run 38021335142 had that pid alive, so `_remove_dead_temps` kept the file and the test failed. The test now uses a pid `os.kill` reports as dead. Production cleanup is unchanged.

Full local pytest: `uv run pytest -q -p no:cacheprovider --basetemp /tmp/w12-pytest4`: 12 failed, 3286 passed, 193 skipped, 1 warning, 364.51s. Exit 1. All 12 failures are `test_compose_preserves_the_postgres_password` with `FileNotFoundError` because `docker` is absent. Local-only. CI is the gate. `uv run ruff format --check .` exit 0 (338 files already formatted). `uv run ruff check .` exit 0. ruff 0.16.2, config `pyproject.toml` line-length 100, target-version py312. `uv run pyright` 1.1.411: 0 errors, 0 warnings, 0 informations. The format, check, and pyright commands were run on the tree before this pid selection. The pid selection is in the test file only. `uv run ruff check` on that file after the edit exited 0.

## 2026-10-10 — Session 07 W13: QA caller-trust limits

Session 07 stays incomplete. This wave is not SESSION_07 COMPLETE. State revision 61 → 62. STATE `head_sha` is `48b93bccf1e1688baf287aeb9e0b428caa0761e3`, the W12 commit. It is the tip-sync pointer. It is not this commit. `current_session` stays 7. `completed_sessions` stays `[0, 1, 2, 3, 4, 5, 6]`. `next_session` stays 7. `next_prompt` stays `10_SESSION_07_PRODUCT_BUILD_VARIANTS_AND_QA.md`. `evidence_closure_commit_sha` stays `0f94d585f23d79e5ac18479f01e14f67cbaad332`. `last_verified_commit` stays bootstrap. Twelve session 7 evidence keys stay false. A07, A08, and A09 stay DESIGNED. `commissioned_agents` stays empty. Exit 78 stays HELD. W13 did not start the live sandbox. The close entry records the later title-only run.

Prompt integrity is the Wave 13 addendum in `docs/control/reviews/2026-10-05-session-07-prompt-integrity.md`. The prompt file is unchanged. SHA-256 `d52011a6f0b725b16427629dc664cfc9f3432c4b5f71d26ce032d4b6c8ecb39d`. D-0031 records the contract. D-0029 is amended to point at it.

Fixtures only. No live Notion, no Etsy, no `--execute`. `prose_digest` at `notion_qa.py:264` length-prefixes each field before the sha256. A newline join of the last hub description and the buyer collides; the digest does not (`test_prose_digest_newline_boundary_does_not_collide`). `_saved_holds` at `:332` re-runs QA on a digest change only when `_judged_caller` at `:711` matches the hub names and the notification row Name. A renamed hub set, or identity `Not The Row`, raises `qa caller does not match` and leaves the checkpoint bytes unchanged (`test_mismatched_caller_cannot_refresh_changed_prose`). The judged caller still refreshes and records `PASS` (`test_judged_caller_can_refresh_changed_prose`). `_normalised_secret_link` at `:959` stores `scheme://host` or `missing`. A userinfo password, a query, and a fragment are absent from the QA fact (`test_query_userinfo_and_fragment_are_not_secret_link_facts`). A raw token is `missing` and is not copied into the fact (`test_non_url_secret_link_fact_is_missing`).

`tests/unit/agents/test_notion_product_qa.py`, `test_notion_fact_ledger.py`, and `test_notion_test_matrix.py`: 710 passed. `uv run ruff check` and `uv run pyright` 1.1.411 on `notion_qa.py` and the QA test: 0 errors. The full local pytest suite was not run.

Parked to the next wave: the live sandbox (no credentials, no explicit authorization); in-place formula, linked-view, and section repair (D-0030); action 12 commissioning; the twelve evidence keys; the QA operand survivors, which on this commit were `notion_qa.py:143` and `:154`. This commit did not re-run that sweep. The close entry records those checks as equivalent at the public entry (`notion_qa.py:145` and `:156`).

## 2026-10-10 — Session 07 W12: fixture section 11 test matrix

Session 07 stays incomplete. This wave is not SESSION_07 COMPLETE. State revision 60 → 61. STATE `head_sha` is `ae2ca6e41a0c6ff87437a53db91feb50bc5a82b3`, the W11 squash. It is the tip-sync pointer. It is not this commit. `current_session` stays 7. `completed_sessions` stays `[0, 1, 2, 3, 4, 5, 6]`. `next_session` stays 7. `next_prompt` stays `10_SESSION_07_PRODUCT_BUILD_VARIANTS_AND_QA.md`. `evidence_closure_commit_sha` stays `0f94d585f23d79e5ac18479f01e14f67cbaad332`. `last_verified_commit` stays bootstrap. Twelve session 7 evidence keys stay false. A07, A08, and A09 stay DESIGNED. `commissioned_agents` stays empty. Exit 78 stays HELD. Narrative `next_phase` becomes `sandbox_build` after a recorded matrix. This matrix commit did not start the live sandbox. The close entry records the later title-only run.

Prompt integrity is the Wave 12 addendum in `docs/control/reviews/2026-10-05-session-07-prompt-integrity.md`. The prompt file is unchanged. SHA-256 `d52011a6f0b725b16427629dc664cfc9f3432c4b5f71d26ce032d4b6c8ecb39d`. D-0030 records the repair contract.

Fixtures only. No live Notion, no Etsy, no `--execute`. `run_test_matrix` is async at `notion_test_matrix.py:104`. It requires a passing fact ledger and a passing workflow link whose ready name is ListingCopyJob. It does not create that job. A passing mass or business build records `PASS` with tier `mass` or `business`, ten checks, and `next_phase` `sandbox_build`. Resume of that record writes nothing. A crash inside `write_checkpoint` leaves no `test_matrix` key, and the resume writes once. A wrong formula or a wrong linked view records `BLOCKED` with 0 adapter writes and does not change the formula or the view target. A missing hub section raises `fact ledger section is missing` and writes nothing. A blocked ledger is refused. A catalogue spec and `APINotionAdapter` are refused. A provider `ProviderFailure` whose text is a secret is stored and raised as `provider operation failed`. A local `ValueError` is `test matrix failed in local code` and writes nothing. A `KeyboardInterrupt` leaves as a fresh `KeyboardInterrupt` with empty args and writes nothing. A later QA rewrite keeps the `test_matrix` key.

`tests/unit/agents/test_notion_test_matrix.py`: 18 passed. Affected regression: `test_notion_fact_ledger.py`, `test_notion_product_qa.py`, `test_notion_product_builder_aesthetics.py`, and `test_notion_product_builder_variants.py` together 922 passed. `uv run ruff check` and `uv run pyright` 1.1.411 on the changed modules: 0 errors. The full local pytest suite was not run.

Parked by this matrix commit: the live sandbox; in-place formula, linked-view, and section repair (D-0030); action 12 commissioning; the twelve evidence keys; the W11 QA operand survivors, `_prose_digest` join collision, and the D-0029 QA-rerun limit. The close entry records the title-only sandbox run and closes those QA parks. In-place repair, commissioning, and the twelve evidence keys stay parked.

## 2026-10-09 — Session 07 sandbox run, round 12 (re-sync onto the W10 squash)

Not a session close. This is not SESSION_07 COMPLETE. State revision 58 → 59. `head_sha` is the W10 squash `4b899fcf6bf09730b952bf5517d6bd691b72ba9a`. It is the tip-sync pointer. It is not this commit. W10 (#61) merged first and kept revision 58, so this PR, merging second, takes revision 59 on the new base. `evidence_closure_commit_sha` stays the Session 06 closure tip `0f94d585f23d79e5ac18479f01e14f67cbaad332`. `last_verified_commit` stays bootstrap `1abf0d7cca3a6b8cd7efcd0a45523538fd5bfd9d`. Twelve session 7 evidence keys stay false. `commissioned_agents` stays empty. `session_status` stays incomplete. Exit 78 stays HELD. The §11 sandbox CLI is still not run live. This commit's CI run is not invented here.

Round 12 is one merge commit: `build/full-automation` at `4b899fcf` merged into this branch at `efea4297` (first parent `efea4297`, no rebase, no force-push). It answers Verifier 6080655092 (FAIL at `efea4297`, text only) and carries Reviewer 5469709536 (PASS at `efea4297`) nits.

- Merge: the four sandbox modules are unchanged by the merge. W10's code and tests (`notion_fact_ledger.py`, `notion_progress.py`, `notion_qa.py`, `notion_progress_record.py`, `test_notion_fact_ledger.py`, `test_notion_product_qa.py` and the rest) come in unchanged from `4b899fcf`. Conflicts were in four `docs/control` files only. `IMPLEMENTATION_STATE.json`: both sides kept revision 58 and added a note; resolved to revision 59, `head_sha` `4b899fcf`, the base `session_07_w10` note kept unchanged, this branch's `session_07_sandbox_run` note rewritten for 58 → 59, `updated_at` `2026-10-09T12:15:51Z`. `IMPLEMENTATION_LOG.md` and `TEST_EVIDENCE.md`: both sides inserted new entries at the same point; both kept, this branch's entries first, W10's entry unchanged. `NEXT_SESSION.md`: both sides renamed the W9 heading (this branch to "Wave 9 handoff", W10 to "Wave 10 in progress" with W10 body text); resolved to "Session 07 — Wave 10 handoff" over W10's text unchanged, since W10 is merged. The seven product-builder STATE pins (`HEAD_SHA`, `state_revision`) move to `4b899fcf` / 59.
- Text (Verifier B1): `420 LT1` is dropped from the park list. That return was deleted in round 11; guard:418-427 is now `_detection_ready`.
- Text (Verifier B2): `472 F`, `487:8`, `487:16` were `518d5215` coordinates. At this tip they are guard:479 (`if not text.strip()`) and guard:494 (the mount-point compare). The sweep rows are given tip coordinates too.
- Text (Verifier B3): with `fstatfs` removed after creates, `_detection_ready` is False, so `under_proc` is True and `_refuse_proc_write` (guard:733-736) refuses first and prints `evidence path is refused: <5 ids>` (69, no file, no `.tmp`). `_fd_on_procfs` (guard:822-824, `evidence write failed`) is the `OSError` path, where the symbol exists and `fstatfs` fails. The round-11 body and comment 6079960825 line 13 named the wrong mechanism; the outcome numbers were right. `test_libc_losing_fstatfs_after_creates_exits_69_with_ids` now asserts `evidence path is refused` and its docstring (was `guard:449 via :790`) says so.
- Should-fix (repeated `.`/`..` links, guard:603): parked as Reviewer SF, fail-closed over-refusal. No code change: telling a `.`/`..` alias apart from a real cycle needs a different cycle test than `target_key in seen_symlinks`, which is not a small change to the procfs guard. Direct probe at this tip: `here -> .` ×1-2 and `up/x` ×1-2 accepted; ×3-5 refused; two-node cycle and self-loop refused. Wording corrected: over-refusal can start at 2 repeats (1 of Reviewer's 35 fuzz cases), not only at 3 or more.
- Nit: 425:7 LF0 is added to the park list as an equivalent.

Census at this tip (one AST walk of the four sandbox modules): if 218, boolop 72, and 26, or 46, clause 154, ifexp 8, while 3. Total 1207. Unchanged from `efea4297`. The 1207-row table was not run.

PARKED to the next wave, not fixed: `_WALK_LIMIT = 257` (guard:30); guard 396 F; guard 479 F (`if not text.strip()`); guard 494:8 F and 494:16 ×4 (the mount-point compare); guard 425:7 LF0 (equivalent, Reviewer 5469709536: `hasattr(None, …)` is False, so a missing libc still gives not-ready); guard 437/444/452/459 F (`lib is None` and `result != 0` in the two `statfs` helpers, survived since r8, Reviewer 5469709536); the ids dropped on the first post-open `_fd_on_procfs` raise at guard:823-824 (test gap, not an id loss: the `OSError` path does print the 5 ids, Verifier 6080655092); ns:349 ×10, ns:352 ×3; the r8 6 CLI-masked and 10 no-libc rows (not re-swept); Reviewer 5469228650 sweep survivors at tip coordinates guard 586/589/600 (If F, SWAP, LF0, LF1) ×12, guard 598 F, guard 607 NEG/T/F ×3 (they were 579/582/593, 591 and 600 at `518d5215`). Reviewer SF, fail-closed over-refusal: the `target_key` check at guard:603 refuses a path through a `.` or `..` link repeated in the same path (`here -> .` with `c/here/here/here/ev.json`, `d/x/up -> ..` with `up/x` ×3): 64, 0 reads, 0 creates, no traceback. Over-refusal can start at 2 repeats (1 of Reviewer's 35 fuzz cases, two `.` repeats after a different link); 34 of 35 need 3 or more. A single target string such as `./././x` is accepted.

Results at this tip (box, local): `tests/unit/cli/test_notion_sandbox.py` 355 passed. W10 suites after the merge: `test_notion_fact_ledger.py` 503 passed and `test_notion_product_qa.py` 162 passed (665 together); the seven `test_notion_product_builder_*.py` files 392 passed; `tests/bootstrap` 89 passed, 1 skipped. `uv run ruff format --check src tests scripts migrations`: 336 files already formatted. `uv run ruff check src tests scripts apps migrations`: all checks passed. `uv run pyright` 1.1.411: 0 errors, 0 warnings. Full local pytest `uv run pytest -q -p no:cacheprovider`: 3215 passed, 193 skipped, 12 failed. The 12 failures are `test_compose_preserves_the_postgres_password` because `docker` is absent. Local-only. CI is the gate. The 236-run burst and the mutation probes were not re-run this round; the sandbox modules are byte-identical to `efea4297`.

## 2026-10-09 — Session 07 sandbox run, round 11

Not a session close. This is not SESSION_07 COMPLETE. `state_revision` stays 58. `IMPLEMENTATION_STATE.json` is not edited. `head_sha` stays the W9 squash `a4e9b025021b4effbb2b2879c1db756403cb1676`. Twelve session 7 evidence keys stay false. `commissioned_agents` stays empty. Exit 78 stays HELD. The §11 sandbox CLI is still not run live. This commit's CI run is not invented here.

Round 11 answers Verifier 6079607643 and Reviewer 5469228650, both FAIL at `518d5215` under the frozen criteria on false text only; the round-10 code fix holds. Only the listed items are changed.

- Text: the round-10 park line above is corrected. "All 6 new tests fail on `9d350221`" was false: 5 fail and 1 passes (`test_symlink_self_loop_is_refused`, already refused through `target_key`); it guards against regression. The census at `518d5215` was if 217, total 1201, not 1204 (1204 was the `9d350221` tree). The named-probe row at `518d5215` was 9 rows, 8 killed, 1 survived (Reviewer), not 11/8/3.
- Should-fix (guard:434 via :505): a libc without `statfs` raised `AttributeError` out of `main`. `_detection_ready` now also requires `statfs` and `fstatfs` on the cached libc, so the path is refused (64) before any read or create. `_statfs_f_type` and `_fstatfs_f_type` also catch `AttributeError` and return `None`.
- Should-fix (guard:449 via :790): a libc without `fstatfs` raised `AttributeError` after creates with empty ids. Up front it is now 64 with 0 reads and 0 creates. If `fstatfs` disappears after creates, `commit_evidence` refuses (69), no file, and the created ids are printed on stderr.
- Tests: `test_libc_without_statfs_symbol_refuses_before_any_post[statfs|fstatfs]`, `test_statfs_helpers_return_none_when_the_symbol_is_missing`, `test_libc_losing_fstatfs_after_creates_exits_69_with_ids`. All 4 fail on the `518d5215` source and pass at this tip.

Census at this tip (one AST walk of the four sandbox modules): if 218, boolop 72, and 26, or 46, clause 154, ifexp 8, while 3. Total 1207 (218×3 + 72 + 154 + 308 + 16 + 3). The 1207-row table was not run.

Named serial probes at this tip (one sandbox-test run each): `_WALK_LIMIT = 257` SURVIVES (355 passed); `target_key` `if False` (guard:603) KILLED, 2 failed; new `statfs` operand forced False KILLED, 1 failed; new `fstatfs` operand forced False KILLED, 1 failed; `statfs` `AttributeError` catch dropped KILLED, 1 failed; `fstatfs` `AttributeError` catch dropped KILLED, 1 failed. The other named probes from Reviewer's 9 were not re-run here; their lines are unchanged.

PARKED to the next wave, not fixed and not claimed equivalent: `_WALK_LIMIT = 257` (guard:30); guard 396 F, 479 F, 494:8 F, 494:16 ×4 (corrected in round 12: 420 LT1 was deleted with the old return, and 472/487 were `518d5215` coordinates); ns:349 ×10, ns:352 ×3; the r8 6 CLI-masked and 10 no-libc rows (not re-swept). Also Reviewer 5469228650's changed-region sweep survivors (already present in r8 or r9): guard 579/582/593 (If F, SWAP, LF0, LF1), guard 591 F, guard 600 NEG/T/F (pre-round-11 line numbers; +7 at this tip). Also Reviewer's should-fix: `target_key` (guard:603 at this tip) refuses a path through a repeated `.` or `..` link (`here -> .`, `c/here/here/here/ev.json`). It fails closed (64, 0 POSTs); no code change this round. Corrected in round 12: it can start at 2 repeats in 1 of Reviewer's 35 fuzz cases, not only at three or more.

Nits: `test_nested_relative_symlink_chain_is_accepted` is dry-run only (Verifier ran `--execute` on the same shape: 16 reads, 5 creates). The 236-run burst was not repeated this round.

`tests/unit/cli/test_notion_sandbox.py`: 355 passed. `ruff format --check`, `ruff check`, and `pyright` 1.1.411 (0 errors) are clean. Full local pytest: `uv run pytest -q -p no:cacheprovider`: 2670 passed, 193 skipped, 12 failed. The 12 failures are `test_compose_preserves_the_postgres_password` because `docker` is absent. Local-only. CI is the gate.

## 2026-10-09 — Session 07 sandbox run, round 10

Not a session close. This is not SESSION_07 COMPLETE. `state_revision` stays 58. `IMPLEMENTATION_STATE.json` is not edited. `head_sha` stays the W9 squash `a4e9b025021b4effbb2b2879c1db756403cb1676`. Twelve session 7 evidence keys stay false. `commissioned_agents` stays empty. Exit 78 stays HELD. The §11 sandbox CLI is still not run live. This commit's CI run is not invented here. No Verifier verdict had landed on `9d350221` when this round was written.

Round 10 answers Reviewer 5468752023 on tip `9d350221` under the frozen criteria. Only the listed items are changed.

- Blocker 1 (guard:590-591): the `prefix_key in seen_symlinks` refusal is deleted. It refused an ordinary nested relative chain (`c/s1 -> x1`, `c/x1/s2 -> x2`, path `c/s1/s2/sub/ev.json`) from K=2. Cycles and self-loops stay refused by the `target_key` check. Tests: `test_nested_relative_symlink_chain_is_accepted[2|8|16]` (public entry, exit 0, file written under the physical target, 0 creates), `test_symlink_self_loop_is_refused`, and the existing `test_symlink_cycle_is_refused`. Direct probe: nested K=1..32 `under_proc` False; two-node cycle, self-loop, and nested-to-`/proc/self/root` True.
- Blocker 2: "a K≥16 relative chain is accepted" now holds for the sibling chain and the nested chain.
- ns:363-366: `_raise_interrupt` installs the race-filtering `sys.unraisablehook` before `signal.signal(SIGINT, SIG_IGN)`. `main` saves the original hook and restores it in its `finally`. The docstring no longer says the race traceback is never printed. Tests: `test_raise_interrupt_installs_race_hook_before_sig_ign`, `test_main_restores_unraisablehook_after_interrupt`. Burst harness (r9 `burst8` schedule, fake adapter, sockets blocked): 236 runs, 0 tracebacks (r9 tip: 4/236), all exit 69, ids printed, 0 token leaks. Zero in 236 runs is a measurement, not a guarantee.
- NIT `_detection_ready` redundancy: left as is.

Named probes this round. `target_key` `if False`: KILLED by `test_symlink_cycle_is_refused` and `test_symlink_self_loop_is_refused`. The new nested, hook-order, and hook-restore tests each fail on the `9d350221` source.

PARKED to the next wave, not fixed and not claimed equivalent (corrected in round 11; the original line wrongly parked 590 F and 599 F and counted "23 changed-line survivors"): `_WALK_LIMIT = 257` (guard:30); guard 396 F, 420 LT1, 472 F, 487:8 F, 487:16 ×4 (`518d5215` coordinates; see round 12 for the tip list); ns:349 ×10, ns:352 ×3; the r8 6 CLI-masked and 10 no-libc rows (not re-swept). `target_key` `if False` (old 599 F) is KILLED; 590 F was deleted with the `prefix_key` check.

`tests/unit/cli/test_notion_sandbox.py`: 351 passed. `ruff format --check`, `ruff check`, and `pyright` 1.1.411 (0 errors) are clean. Full local pytest: `uv run pytest -q -p no:cacheprovider`: 2666 passed, 193 skipped, 12 failed. The 12 failures are `test_compose_preserves_the_postgres_password` with `FileNotFoundError` because `docker` is absent. Local-only. CI is the gate.

## 2026-10-09 — Session 07 sandbox run, round 9

Not a session close. This is not SESSION_07 COMPLETE. `state_revision` stays 58. `IMPLEMENTATION_STATE.json` is not edited. `head_sha` stays the W9 squash `a4e9b025021b4effbb2b2879c1db756403cb1676`. Twelve session 7 evidence keys stay false. `commissioned_agents` stays empty. Exit 78 stays HELD. The §11 sandbox CLI is still not run live. This commit's CI run is not invented here. No Verifier verdict had landed on `fc9c01c3` when this round was written.

Round 9 answers Reviewer 5468348253 on tip `fc9c01c3`. Prompt-integrity addendum: `docs/control/reviews/2026-10-09-session-07-round-9-prompt-integrity.md`. **No equivalents are claimed.** The round-8 `_is_proc`→False, walk-limit, and ns:456 EQ claims, and the `11/3 EQ` label, are withdrawn.

Blocker to fix to test.

- Fail-closed: `_detection_ready` requires cached `ctypes.CDLL(None)` and a non-empty mountinfo. Otherwise `under_proc` is True and `open_evidence` is 64 before any POST. `_fd_on_procfs` uses `fstatfs` only; a missing `f_type` is True; `/proc/self/fd/N` is not consulted. Tests: `test_missing_libc_refuses_before_any_post`, `test_empty_mountinfo_refuses_before_any_post`, `test_fd_on_procfs_uses_fstatfs_not_proc_self_fd`.
- Mountinfo unescape: `_unescape_mount_field` decodes `\\040` / `\\011` / `\\012` / `\\134` before the longest-match compare. A later shorter `proc` line does not win. Tests: `test_mountinfo_decodes_octal_escaped_space`, `test_later_short_proc_mount_does_not_win`.
- tmpfs over `/proc`: `_is_proc` still refuses `/proc/ev_p60.json` when `f_type` is tmpfs. Test: `test_literal_proc_is_refused_when_fstype_is_tmpfs`.
- Unique walk: `under_proc` counts unique nodes. A relative chain of 16 is accepted. A two-node cycle is refused. An overlong chain against `_WALK_LIMIT` 8 is refused. Tests: `test_relative_symlink_chain_of_16_is_accepted`, `test_symlink_cycle_is_refused`, `test_unique_walk_limit_refuses_an_overlong_chain`.
- ns:456: `test_publish_interrupted_ki_after_complete_file_returns_69`.

Census on this tree, one AST walk of the four modules: if 218, boolop 72, and 27, or 45, clause 153, ifexp 8, while 3. Mutations: if-flip 218, force-true 218, force-false 218, operator swap 72, clause negation 153, literal clause True/False 306, ifexp True/False 16, while-flip 3. Total 1204. **The 1204-row table was not run. No file-level killed/survived/sum is claimed.**

Serial probes that were actually run (named tests; stock first: 345 passed). Command: `uv run --frozen pytest -q -p no:cacheprovider tests/unit/cli/test_notion_sandbox.py --basetemp /tmp/p60r9mut/<name>/bt -k '<expr>'`.

| Site | Mutant | Result | Failed | Test |
|---|---|---|---|---|
| guard `_is_proc` | `return False` | KILLED | 1 | `test_literal_proc_is_refused_when_fstype_is_tmpfs` |
| guard unique walk limit | `if False` | KILLED | 1 | `test_unique_walk_limit_refuses_an_overlong_chain` |
| ns:456 except complete | `if False` | KILLED | 1 | `test_publish_interrupted_ki_after_complete_file_returns_69` |
| guard mount unescape | raw field | KILLED | 1 | `test_mountinfo_decodes_octal_escaped_space` |
| guard longest-match skip | `if False` | KILLED | 1 | `test_later_short_proc_mount_does_not_win` |
| guard `_detection_ready` | `if False` | KILLED | 1 | missing libc / empty mountinfo |
| guard `_fd_on_procfs` | `/proc/self/fd/N` | KILLED | 1 | `test_fd_on_procfs_uses_fstatfs_not_proc_self_fd` |
| guard both cycle checks | both `if False` | KILLED | 1 | `test_symlink_cycle_is_refused` |

SURVIVORS (named probes this tip; not claimed equivalent).

- `prefix_key in seen_symlinks` `if False` alone: the sibling `target_key` check still refuses a two-node cycle.
- `target_key in seen_symlinks` `if False` alone: the sibling `prefix_key` check still refuses a two-node cycle.
- Walk-limit `+1` on a 16-chain: unique-node count stays far below 256.

The Reviewer 126-row survivor split at `fc9c01c3` (8 public-with-libc, 6 CLI-masked, 10 no-libc, 18 helper-only, 84 no-diff) was not re-swept. The 6 CLI-masked and 10 no-libc rows are SURVIVORS: not re-enumerated this tip. Fail-closed and unescape tests cover the named public blockers. PARTIAL.

`tests/unit/cli/test_notion_sandbox.py`: 345 passed. Sockets stay blocked. `ruff format --check`, `ruff check`, and `pyright` 1.1.411 (0 errors) are clean on the four sandbox modules and the sandbox test. Full local pytest: `uv run --frozen pytest -q -p no:cacheprovider --basetemp /tmp/p60r9all`: 2660 passed, 193 skipped, 12 failed. The 12 failures are `test_compose_preserves_the_postgres_password` with `FileNotFoundError` because `docker` is absent. Local-only. CI is the gate.

## 2026-10-09 — Session 07 sandbox run, round 8

Not a session close. This is not SESSION_07 COMPLETE. `state_revision` stays 58. `IMPLEMENTATION_STATE.json` is not edited. `head_sha` stays the W9 squash `a4e9b025021b4effbb2b2879c1db756403cb1676`. Twelve session 7 evidence keys stay false. `commissioned_agents` stays empty. Exit 78 stays HELD. The §11 sandbox CLI is still not run live. This commit's CI run is not invented here. No Verifier verdict had landed on `e571b8e7` when this round was written.

Round 8 answers Reviewer 5467032904 on tip `e571b8e7`. Prompt-integrity addendum: `docs/control/reviews/2026-10-09-session-07-round-8-prompt-integrity.md`.

Blocker to fix to test.

- B1/B3 procfs by filesystem type: `_on_procfs` (`notion_sandbox_guard.py`) uses `ctypes` `statfs`/`fstatfs` `f_type == PROC_SUPER_MAGIC` `0x9fa0`, else `/proc/self/mountinfo` fstype `proc` for the longest matching mount. It does not compare `st_dev` with `/proc`. `under_proc` walks every lexical and resolved ancestor, follows relative symlink targets joined to the parent, and re-checks at each `_refuse_proc_write` / dirfd point. Tests (fstype injected; no user namespace): `test_on_procfs_uses_filesystem_type_not_st_dev`, `test_bind_mounted_procfs_paths_are_refused`, `test_symlink_to_bind_mounted_procfs_is_refused`, `test_second_procfs_instance_is_refused`, `test_mountinfo_fstype_proc_is_detected`.
- B2 false EQs withdrawn: `_tmp_kind` on a leftover symlink is `"symlink"` (`test_tmp_kind_classifies_a_leftover_symlink`). `_on_procfs`→False is not equivalent; the bind-mount / second-procfs tests fail when it returns False.
- B4 public survivors: relative symlink to a `/proc/self/root` symlink is 64 (`test_relative_symlink_to_proc_self_root_symlink_is_refused`); a symlink cycle finishes and is not proc (`test_symlink_cycle_is_bounded_and_not_proc`); a grandparent symlink to an ordinary directory with a real subdir is accepted dry-run 0 (`test_ancestor_symlink_to_ordinary_dir_is_accepted`); dry-run SIGINT after `os.link` is 69 with `sandbox interrupted` and no traceback (`test_dry_run_sigint_after_link_exits_69`); `workspace_id: null` is absent and execute finishes 0 after 5 (`test_workspace_id_null_is_treated_as_absent`). Namespace-dependent bind-mount / second-procfs paths are the fstype tests above.
- B5: `_raise_interrupt` installs `SIG_IGN` before anything else. Tests: `test_raise_interrupt_sets_sig_ign_before_raising`, `test_gap0_double_sigint_at_post2_keeps_ids_across_runs` (20/20, `dropped == 0`).

Should-fixes and nits that were done.

- LINK-stage ENOENT after creates is 69 with ids (`test_link_enoent_after_creates_exits_69_with_ids`). Other post-create `OSError` with ids, or `_WRITE_ERRNO` / `"race condition"`, is 69. Empty-ids unknown `OSError` stays 64.
- `commit_evidence` opens the parent dirfd and uses `os.open(..., dir_fd=)` / `os.link(..., src_dir_fd=, dst_dir_fd=)`.
- Dry-run gap-0 at WRITE:1 is 69, not -2 (`test_dry_run_gap0_at_first_write_exits_69`).
- Run plan dirty-tree checks use `test -z … || exit 1`.
- `_fsync` raises `SandboxError` `from None`. A leftover regular tmp logs `removing leftover regular evidence tmp`. `_align` is a bounded `for` plus a shrink check, so pipeline:206 is not timeout-only.

Census on this tree, one AST walk of the four modules: if 212, boolop 71, and 26, or 45, clause 151, ifexp 8, while 3. Mutations: if-flip 212, force-true 212, force-false 212, operator swap 71, clause negation 151, literal clause True/False 302, ifexp True/False 16, while-flip 3. Total 1179. **The 1179-row table was not run. No file-level killed/survived/sum is claimed.**

Serial probes that were actually run (named tests; stock first: 336 passed). Command: `uv run --frozen pytest -q -p no:cacheprovider tests/unit/cli/test_notion_sandbox.py --basetemp /tmp/p60r8mut/<name>/bt -k '<expr>'`.

| Site | Mutant | Result | Failed | Test |
|---|---|---|---|---|
| guard `_tmp_kind` `S_ISLNK` | `if False` | KILLED | 1 | `test_tmp_kind_classifies_a_leftover_symlink` |
| guard `_on_procfs` MAGIC | `if False` | KILLED | 3 | fstype / bind / second procfs |
| guard `_on_procfs` | `return False` | KILLED | 4 | those plus mountinfo |
| guard mountinfo fallback | `return False` | KILLED | 1 | `test_mountinfo_fstype_proc_is_detected` |
| guard `_symlink_target` relative join | `if False` | KILLED | 1 | `test_relative_symlink_to_proc_self_root_symlink_is_refused` |
| guard `key in seen` | `if False` | KILLED | 1 | `test_symlink_cycle_is_bounded_and_not_proc` |
| guard symlink ancestor | always `return True` | KILLED | 1 | `test_ancestor_symlink_to_ordinary_dir_is_accepted` |
| guard `ids != ""` after `OSError` | skipped | KILLED | 1 | `test_link_enoent_after_creates_exits_69_with_ids` |
| live `raw is None` | skipped | KILLED | 1 | `test_workspace_id_null_is_treated_as_absent` |
| ns `_raise_interrupt` `SIG_IGN` | removed | KILLED | 1 | `test_raise_interrupt_sets_sig_ign_before_raising` |
| ns `_publish_interrupted` top `_evidence_is_complete` | `if False` | KILLED | 1 | `test_dry_run_sigint_after_link_exits_69` |

Probe-backed equivalents on the named tests only. Both versions produced the same output there.

- `_is_proc` `return False` alone. `_on_procfs` still refuses `/proc` by `f_type`. 3 passed.
- `_WALK_LIMIT` `if False` alone. The seen-set finishes an ordinary cycle. 1 passed.
- `_publish_interrupted` except `_evidence_is_complete` `if False` alone. The top check still prints `sandbox interrupted` and exits 69. 1 passed.

The round-7 EQ claims `_on_procfs`→False and `_tmp_kind` `S_ISLNK`→False are withdrawn. `_scrub_hex` `nxt<=index` and `_write_all` `written<=0` were not re-probed on this tip.

Helper-only survivors from Reviewer 5467032904 at `e571b8e7` (16 rows: guard:357, 363, 411, 414T, 416, 479/481/483F; ns:356F, 367F, and the rest of that split) were not re-swept. They are not claimed as EQ. Line numbers have moved. This tip did not run the 1179-row table.

`tests/unit/cli/test_notion_sandbox.py`: 336 passed. Sockets stay blocked. `ruff format --check`, `ruff check`, and `pyright` 1.1.411 (0 errors) are clean on the four sandbox modules and the sandbox test. Full local pytest: `uv run --frozen pytest -q -p no:cacheprovider --basetemp /tmp/p60r8all`: 2651 passed, 193 skipped, 12 failed. The 12 failures are `test_compose_preserves_the_postgres_password` with `FileNotFoundError` because `docker` is absent. Local-only. CI is the gate.

## 2026-10-09 — Session 07 sandbox run, round 7

Not a session close. This is not SESSION_07 COMPLETE. `state_revision` stays 58. `IMPLEMENTATION_STATE.json` is not edited. `head_sha` stays the W9 squash `a4e9b025021b4effbb2b2879c1db756403cb1676`. Twelve session 7 evidence keys stay false. `commissioned_agents` stays empty. Exit 78 stays HELD. The §11 sandbox CLI is still not run live. This commit's CI run is not invented here. Verifier verdict on `8f77434c` had not landed when this round was written.

Round 7 answers Reviewer 5465945944 on tip `8f77434c`. Prompt-integrity addendum: `docs/control/reviews/2026-10-09-session-07-round-7-prompt-integrity.md`.

Blocker to fix to test.

- B1 `/proc` bypass: `under_proc` (`notion_sandbox_guard.py`) walks every lexical and resolved ancestor. It compares `lstat(component).st_dev` to `lstat('/proc').st_dev`, checks the `/proc` name, and follows symlink targets. `realpath('/proc/self/root')` is `/` and is no longer the only check. `realpath` `OSError`/`PermissionError` is not a crash. `_refuse_proc_write` re-checks immediately before `os.open`, `_write_all`, and `os.link`. Tests: `test_symlink_to_proc_self_root_is_refused`, `test_symlink_to_proc_self_plus_root_dir_is_refused`, `test_grandparent_swapped_to_proc_self_root_does_not_write`.
- B2 four survivors: LF1 (`/proc/self` + `/root/<dir>`) exits 64 with 0 calls; leftover tmp symlink at commit exits 69 and does not write through the target; `under_proc('/proc/1/root/x')` is True and does not raise `PermissionError`. Tests: `test_symlink_to_proc_self_plus_root_dir_is_refused`, `test_leftover_tmp_symlink_after_creates_exits_69_without_writing_through_it`, `test_under_proc_on_foreign_pid_root_does_not_raise`.
- B3 leftover `.ev.json.tmp` (symlink, dir, FIFO) is refused in `open_evidence` before any POST: exit 64, 0 reads, 0 creates. Test: `test_leftover_hostile_tmp_is_refused_before_any_call`.
- B4 gap-0 SIGINT at POST:2: `_run_stages` ignores SIGINT around `redact_text` and the id-bearing row. `_fail` also ignores SIGINT while printing. After an interrupt, `main` leaves SIGINT ignored so a 0.5-100 ms follow-up is not -2. Tests: `test_gap0_sigint_at_post2_prints_ids` (asserts the kill after `os.kill` still ran), `test_double_sigint_at_50ms_exits_69`.

Should-fixes that were done.

- SF5: `EACCES`/`EROFS`/`EPERM`/`EEXIST` during `commit_evidence` after creates exit 69 with ids (`_WRITE_ERRNO`). Unknown `OSError` stays 64. Test: `test_write_errno_after_creates_exits_69_with_ids`.
- SF6: `_emit` uses `commit_evidence` only. A dest that appears after creates exits 69 with ids, not 64. Test: `test_evidence_path_appearing_mid_run_exits_69_with_ids`.
- `explicit_space` raises on a present non-UUID `space_id`/`workspace_id`. Tests: `test_explicit_space_refuses_a_malformed_id`, `test_malformed_space_id_on_a_created_page_is_refused`.
- `_align`, `_scrub_hex`, and `_write_all` are bounded. Tests: `test_align_fails_fast_when_the_list_does_not_shrink`, `test_scrub_hex_fails_fast_when_the_match_does_not_advance`, `test_write_all_fails_fast_on_a_zero_byte_write`.
- FSYNC `EINTR` / `"race condition"` retries once (`_fsync`).
- Dry-run interrupt keeps build `NOT_RUN`. `_HELD` is cleared at the start and end of `main`.

Census on this tree, one AST walk of the four modules: if 190, boolop 65, and 25, or 40, clause 138, ifexp 8, while 4. Mutations: if-flip 190, force-true 190, force-false 190, operator swap 65, clause negation 138, literal clause True/False 276, ifexp True/False 16, while-flip 4. Total 1069. **The 1069-row table was not run. No file-level killed/survived/sum is claimed.**

Serial probes that were actually run (named tests; stock first: 320 passed). Command: `uv run --frozen pytest -q -p no:cacheprovider tests/unit/cli/test_notion_sandbox.py --basetemp /tmp/p60r7mut/<name>/bt -k '<expr>'`. Hanging mutants used `timeout --signal=KILL 5`.

| Site | Mutant | Result | Failed | Test |
|---|---|---|---|---|
| guard symlink follow `if S_ISLNK` | `if False` | KILLED | 1 | `test_symlink_to_proc_self_root_is_refused` |
| guard `_is_proc` + `_on_procfs` | both `return False` | KILLED | 4 | `//proc`, self/root, LF1, `/proc/1/root` |
| guard `_safe_realpath` | no `OSError` catch | KILLED | 1 | `test_under_proc_on_foreign_pid_root_does_not_raise` |
| guard `open_evidence` leftover | `if False` | KILLED | 3 | leftover hostile symlink/dir/fifo |
| guard `_discard_leftover_tmp` `kind != "file"` | `if False` | KILLED | 1 | leftover tmp symlink after creates |
| guard `_tmp_kind` symlink | return `"file"` | KILLED | 2 | leftover hostile symlink + leftover after creates |
| guard `_refuse_proc_write` | `if False` | KILLED | 1 | grandparent swapped to `/proc/self/root` |
| ns `_run_stages` ignore/mask | removed | KILLED | 1 | `test_gap0_sigint_at_post2_prints_ids` (`after` stayed 0) |
| live `explicit_space` `found == ""` | `if False` | KILLED | 1 | `test_explicit_space_refuses_a_malformed_id` |
| pipeline `_align` `guard <= 0` | `if False` | KILLED | timeout 137 | `test_align_fails_fast_when_the_list_does_not_shrink` |
| guard `_scrub_hex` both bounds | both `if False` | KILLED | timeout 137 | `test_scrub_hex_fails_fast_when_the_match_does_not_advance` |
| guard `_write_all` both bounds | both off | KILLED | timeout 137 | `test_write_all_fails_fast_on_a_zero_byte_write` |

Probe-backed equivalents. Both versions produced the same output on the named tests.

- `_on_procfs` force-false alone. `_is_proc` on `/proc/self` and `/proc/1/root` still refuses. 3 passed.
- `_is_proc` force-false alone. `_on_procfs` on the `/proc` prefix still refuses. 3 passed.
- `_tmp_kind` `S_ISLNK` force-false alone (falls through to `"other"`). Hostile leftover is still refused. 4 passed.
- `_scrub_hex` `nxt <= index` force-false alone, or `_write_all` `written <= 0` force-false alone. The sibling `steps > limit` bound still raises. 1 passed each.

`tests/unit/cli/test_notion_sandbox.py`: 320 passed. Sockets stay blocked. `ruff format --check`, `ruff check`, and `pyright` 1.1.411 (0 errors) are clean on the four sandbox modules and the sandbox test. Full local pytest: `uv run --frozen pytest -q -p no:cacheprovider --basetemp /tmp/p60r7all`: 2635 passed, 193 skipped, 12 failed. The 12 failures are `test_compose_preserves_the_postgres_password` with `FileNotFoundError` because `docker` is absent. Local-only. CI is the gate.

## 2026-10-09 — Session 07 sandbox run, round 6

Not a session close. This is not SESSION_07 COMPLETE. `state_revision` stays 58. `IMPLEMENTATION_STATE.json` is not edited. `head_sha` stays the W9 squash `a4e9b025021b4effbb2b2879c1db756403cb1676`. Twelve session 7 evidence keys stay false. `commissioned_agents` stays empty. Exit 78 stays HELD. The §11 sandbox CLI is still not run live. This commit's CI run is not invented here.

Round 6 answers Reviewer 5465433904 and Verifier 6073572255 on tip `bcf9a36c`. Prompt-integrity addendum: `docs/control/reviews/2026-10-09-session-07-round-6-prompt-integrity.md`.

Blocker to test.

- Reviewer B1 / V-B4 residual: `under_proc` now collapses a leading `//` and walks `realpath` of each prefix (`notion_sandbox_guard.py:357`). `//proc/self/root/<dir>/ev.json` and a directory symlink to `/proc` exit 64 with 0 reads and 0 writes. Tests: `test_leading_double_slash_proc_path_is_refused`, `test_symlink_to_proc_is_refused`, `test_proc_path_helper_rejects_proc_itself`. Serial: prefix-walk `if False` fails `test_symlink_to_proc_is_refused` (1). Both checks `if False` fail 5. `under_proc` `return False` fails 5.
- Reviewer B4 / gap-0 SIGINT: `commit_evidence` discards a leftover non-symlink `.tmp` with SIGINT ignored, ignores SIGINT around the final unlink, and maps `EEXIST` to exit 69 with held ids (`_failure_text`). Tests: `test_leftover_tmp_is_replaced`, `test_tmp_eexist_after_creates_exits_69_with_ids`, `test_interrupt_during_tmp_unlink_keeps_ids`. Serial: `EEXIST` clause forced `False` fails 1; leftover treated as a symlink fails 1.
- Verifier B2 survivors, rewritten off IfExp and pinned: `_page_list` (`notion_sandbox.py:280`) so `flagged_pages` / `possible_orphans` / `rejected_pages` stay `[]`; `if client is None` (`:524`); `if opener is None` (`notion_sandbox_live.py:106`); `if not counts` (`notion_sandbox.py:420`); `_interrupted_rows` inlines `runner_name is not None` (`:137`) and the `[build PASS, variants PASS]` prefix is a case of `test_interrupted_rows_keep_finished_stages`. Serial, each replacement `if False`/`if True` fails its named test (1 or 2).

Round-4 Verifier V-B1–B5 on `bcf9a36c` still hold. This round only extends V-B4 (`//proc` and symlink-to-`/proc`) and V-B5 (`:137` qa INTERRUPTED).

Census on this tree, one AST walk of the four modules: if 164, boolop 57, and 23, or 34, clause 121, ifexp 8, while 3. Mutations: if-flip 164, force-true 164, force-false 164, operator swap 57, clause negation 121, literal clause True/False 242, ifexp True/False 16, while-flip 3. Total 931. **The 931-row table was not re-run. No file-level killed/survived/sum is claimed.**

Serial probes that were actually run (full sandbox suite or the named tests; stock first: 300 passed):

| Site | Mutant | Result | Failed | Test |
|---|---|---|---|---|
| `notion_sandbox.py:281` | `if rows is None` → `False` | KILLED | 1 | `test_dry_run_is_the_default_and_writes_nothing` |
| `notion_sandbox.py:524` | `if client is None` → `False` | KILLED | 1 | `test_absent_injected_client_writes_evidence` |
| `notion_sandbox_live.py:106` | `if opener is None` → `False` | KILLED | 2 | `test_live_client_default_opener_is_callable`, `test_production_client_dry_run_uses_sandbox_opener` |
| `notion_sandbox.py:137` | `runner_name is not None` → `True` | KILLED | 1 | `test_interrupted_rows_keep_finished_stages` |
| `notion_sandbox.py:420` | `if not counts` → `True` | KILLED | 1 | `test_second_interrupt_retries_until_a_file_exists` |
| `notion_sandbox_guard.py:520` | `errno.EEXIST` clause → `False` | KILLED | 1 | `test_tmp_eexist_after_creates_exits_69_with_ids` |
| `notion_sandbox_guard.py:373` | prefix-walk `if _is_proc` → `False` | KILLED | 1 | `test_symlink_to_proc_is_refused` |
| `notion_sandbox_guard.py:366`+`:373` | both checks → `False` | KILLED | 5 | `//proc`, symlink, proc-alias, helper |
| leftover tmp | `S_ISLNK` → `True` | KILLED | 1 | `test_leftover_tmp_is_replaced` |
| `notion_sandbox.py:230` IfExp T/F | always `datetime.now` / always `clock()` | KILLED | 42 / 1 | full sandbox suite |
| `notion_sandbox.py:477` IfExp T/F | always `sys.argv[1:]` / always `argv` | KILLED | 136 / 1 | full sandbox suite |
| `notion_sandbox.py:478` IfExp T/F | always `os.environ` / always `environ` | KILLED | 101 / 1 | full sandbox suite |
| `notion_sandbox.py:500` IfExp T/F | always `"execute"` / always `"dry-run"` | KILLED | 12 / 38 | full sandbox suite |
| `notion_sandbox.py:619` IfExp T/F | always default spec / always injected | KILLED | 1 / 47 | full sandbox suite |

Probe-backed equivalents. Both versions produce the same output on the named tests.

- `notion_sandbox_guard.py:366` force-false of the first `under_proc` check only. The prefix walk still refuses `//proc` and a symlink to `/proc`.
- `notion_sandbox_guard.py:348` force-false of `raw.startswith("//")`. The prefix walk still refuses `//proc/self/...`.

The previous mapping claim that `notion_sandbox.py` was 213/213 killed with Failed sum 6371 is withdrawn. On `bcf9a36c` Verifier measured 205 killed / 8 survived, sum 5761; Reviewer measured the same 205/8 split, sum 5704. Those 8 sites are the IfExps and `:137` rewritten above. They are not re-claimed as a 213-row table.

`tests/unit/cli/test_notion_sandbox.py`: 300 passed. Sockets stay blocked. `ruff format --check`, `ruff check`, and `pyright` 1.1.411 (0 errors) are clean on the four sandbox modules and the sandbox test.

## 2026-10-09 — Session 07 sandbox run, round 5

Not a session close. This is not SESSION_07 COMPLETE. `state_revision` stays 58. `IMPLEMENTATION_STATE.json` is not edited. `head_sha` stays the W9 squash `a4e9b025021b4effbb2b2879c1db756403cb1676`. Twelve session 7 evidence keys stay false. `commissioned_agents` stays empty. Exit 78 stays HELD. The §11 sandbox CLI is still not run live. This commit's CI run is not invented here. Whichever PR merges second re-syncs STATE. `origin/build/full-automation` was fetched and is still `a4e9b025021b4effbb2b2879c1db756403cb1676`. The round-4 tip `69a2b421c6d865ed46aa3cf9d1b1c55036a6ac5a` CI verify run 37786526950, job 113342585729, SUCCESS.

Round 5 folds the round-4 Reviewer FAIL, the round-4 Verifier FAIL, and CodeRabbit's CHANGES_REQUESTED at `69a2b421` into one commit. A signal during the evidence write keeps every stage that already passed. A repeated SIGINT during the interrupt publish is ignored until the file is complete. The four round-4 false EQUIVALENTs (guard `:355` force-false, swap, and operand 3; pipeline `:200` force-false) have killing tests. Created time is bounded on both sides.

Census method: one AST walk of `notion_sandbox.py`, `notion_sandbox_guard.py`, `notion_sandbox_live.py`, and `notion_sandbox_pipeline.py`, in source order. It counts `ast.If` (including `elif`), `ast.BoolOp` and each clause in `values`, `ast.IfExp`, and `ast.While`. Result: if 156, boolop 55, and 23, or 32, clause 117, ifexp 14, while 3. Mutations: if-flip 156, force-true 156, force-false 156, operator swap 55, clause negation 117, literal clause True/False 234, ifexp True/False 28, while-flip 3. Total 905. The literal rows replace each clause with `True` and then `False` (the Verifier's sweep). Harness: pytest on `tests/unit/cli/test_notion_sandbox.py` per mutant, 12 workers, 180-second timeout. A row is killed only when that run's pytest exit is non-zero. When the exit is non-zero and the output has no `failed` count, the Failed count is 1. That covers collection errors and timeouts. Round-4 sums are not this tree.

**The final-tree sweep is PARTIAL.** It was stopped at 07:43 (UTC+7) so this round would not block on it. `notion_sandbox.py` is COMPLETE: 213 of 213 mutations, 213 killed, 0 survived, 0 timeouts, Failed sum 6371 (if-flip 32 rows, 32 killed, Failed sum 1475; force-true 32 rows, 32 killed, Failed sum 1157; force-false 32 rows, 32 killed, Failed sum 458; operator swap 13 rows, 13 killed, Failed sum 223; clause negation 28 rows, 28 killed, Failed sum 1221; literal clause True/False 56 rows, 56 killed, Failed sum 1385; ifexp True/False 20 rows, 20 killed, Failed sum 452; while-flip 0 rows, 0 killed, Failed sum 0). `notion_sandbox_guard.py` is PARTIAL: 71 of 286 mutations finished (force_false 12, force_true 12, if 12, negate 10, operand 20, swap 5), 71 killed, 0 survived, Failed sum 2848. Those rows come from the worker log, which has no first-failing-test column. `notion_sandbox_live.py` (225 mutations) and `notion_sandbox_pipeline.py` (181) were NOT swept on this tree. Run so far: 284 of 905 mutations, 284 killed, 0 survived, 0 timeouts, Failed sum 9219. 621 mutations are not run and carry no claim.

The blocker mutants were also applied by hand to this tree and the sandbox suite run: guard `:352` `if under_proc(path)` forced `False` gives 2 failed; pipeline `:205` `if tail == page_id` forced `False` gives 3 failed; `_publish_held` relabelling every stage (`_interrupted_rows([])`) gives 5 failed.

`tests/unit/cli/test_notion_sandbox.py`: 291 passed. Sockets stay blocked. `ruff format --check`, `ruff check`, and `pyright` 1.1.411 (0 errors) are clean. Full local pytest: 2811 collected, 2606 passed, 193 skipped, 12 failed. The failures are `test_compose_preserves_the_postgres_password` with `FileNotFoundError` because the `docker` binary is absent. They are local-only. CI is the gate.

Equivalent rows. Each one was probed and both versions produced the same output.

- None claimed. Every finished row is KILLED. Rows that were not run carry no claim.

Blocker to fix to test.

- Verifier B1, Reviewer B3, CodeRabbit `notion_sandbox.py:604-607`: a SIGINT during the evidence write, or in `asyncio.run` teardown, no longer relabels stages that passed. `_interrupted_rows(done)` (`notion_sandbox.py:127`) replaces `_signal_stages` and `_read_interrupted`. Finished rows stay as they are, the first unfinished available stage is `INTERRUPTED`, and the rest are `NOT_RUN`. `_run_stages` appends each finished row to a list that `_HELD` already holds, and the created, rejected, flagged, and orphan lists are bound live before `asyncio.run`, so `_publish_held` (`:412`) sees every finished row and every id. `run_status` comes from an explicit `interrupted` flag, not from a relabelled row. Tests: `test_real_sigint_during_the_evidence_write_leaves_a_complete_file` and `test_second_interrupt_retries_until_a_file_exists` now assert build and variants stay `PASS`; `test_one_interrupt_during_the_evidence_write_keeps_passed_stages`; `test_interrupt_in_asyncio_teardown_keeps_passed_stages`; `test_interrupted_rows_keep_finished_stages` (4 cases). Run against the round-4 source, each of these fails with `'INTERRUPTED' == 'PASS'` (or the missing helper).
- Verifier B2: the freshness boundary is pinned. `test_created_time_bounds_are_exact` uses clock `12:00:37Z`: `11:58:00Z` accepted, `11:57:59Z` refused, `12:02:37Z` accepted, `12:02:38Z` refused, one day ahead refused. The Verifier's four mutants, each applied by hand to this tree with the sandbox suite run: `<`→`<=` 1 failed, skew 2→0 min 2 failed, no minute floor 1 failed, no subtraction 1 failed. Reviewer S1 adds an upper bound, `_latest` = clock + 2 minutes (`notion_sandbox_pipeline.py:230`). Its `>`→`>=` mutant gives 1 failed and a 2-day bound gives 3 failed. `test_future_created_time_is_refused_end_to_end` exits 69 for a page created one day ahead.
- Verifier B3, Reviewer B2: `pipeline:200` force-false (now `notion_sandbox_pipeline.py:205`, `if tail == page_id`) is not equivalent. `test_interrupt_while_aligning_keeps_the_created_id` hooks `_remember`, `_drop_recorded`, and `_drop_tail` with an interrupt and checks the id the create returned is still recorded. On the round-4 source with `if tail == page_id` forced `False` it gives 3 failed; on the stock round-4 source it passes. On this tree, forcing it `False` by hand gives 3 failed. Pipeline was not reached by the partial sweep.
- Verifier B4, Reviewer B1: `guard:355` force-false, the `or`→`and` swap, and operand 3 forced `False` are not equivalent. `test_proc_alias_of_a_real_directory_is_refused` covers `/proc/self/root/<tmp>/…` and `/proc/<pid>/root/<tmp>/…`: exit 64, no file, no client call. On the round-4 source each of the three mutants gives 2 failed. The dead `str(path) == ""` and `path == Path()` operands are removed (`Path("")` is `Path(".")`, which exists and is refused by the `lstat` below), so the line is now `if under_proc(path):` at `notion_sandbox_guard.py:352`.
- Verifier B5: the literal-operand sweep is now part of the table (234 rows, one per clause per literal). Each of the 65 round-4 survivors was either killed by a new test or its clause was removed because it was dead. Clauses removed as dead: `notion_sandbox.py` `info.st_size <= 0` (an empty file fails `json.loads`), `str(evidence) == ""` and `str(path) != ""` (a `Path` never prints empty); guard `_encoded_forms` `encoded != token` and `digest != token` (a shaped token holds `_`, its url form holds `%5F`, base64 holds neither), `token != ""` in `redact_text` and `leaks` (`_unsafe_exact` already refuses whitespace-only tokens), `token in cleaned` (replacing a missing substring is a no-op), the `S_ISLNK` parent operand (`lstat` never reports a symlink as a directory); live `sent_parent` type checks (the body is a literal dict built two lines above), the two `None` evidence lists (now one tuple), `value == ""` in `parse_created_time` (`fromisoformat("")` raises), the `type(value) is str` operand in `explicit_space` (`canonical_id` already returns `""` for a non-string); pipeline `page_id == ""` and `page_id != ""` in `_align` (`_remember`, `_flag`, and `_drop_recorded` each ignore a blank id). New killing tests: `test_type_checks_refuse_lookalike_values`, `test_unshaped_tokens_have_no_encoded_forms`, `test_json_literal_tokens_are_not_secrets`, `test_hex_token_absent_from_the_text_is_not_a_leak`, `test_created_page_ids_skip_empty_and_non_text_ids`, `test_overlong_write_count_is_refused`, `test_link_replaced_by_a_same_size_symlink_is_refused`, `test_repo_root_needs_both_markers_in_one_directory`, `test_control_ids_refuse_each_mistyped_field`, `test_evidence_argument_reads_only_the_named_flag`, `test_with_ids_skips_empty_and_non_text_ids`, `test_clock_returning_a_non_datetime_is_refused`, `test_publish_held_needs_a_start_and_a_ready_run`, `test_refusal_without_an_evidence_path_is_usage`, `test_live_publish_records_each_id_once`, `test_dashed_plain_token_in_the_url_is_not_sent`, `test_status_200_is_read`, `test_parse_helpers_refuse_mistyped_fields`, `test_proxy_map_keeps_only_text_pairs`, `test_pipeline_helpers_ignore_blank_and_missing_ids`, `test_one_page_keeps_one_flag_per_reason`, `test_chain_refuses_an_archived_sandbox_parent_handed_in`, `test_chain_refuses_a_page_without_an_id`, `test_chain_stops_at_a_foreign_intermediate_page`, `test_chain_cycle_stops_on_the_repeat`, `test_confirm_with_no_evidence_rows_does_not_add_one`, `test_variants_need_a_probe_and_a_product_spec`.
- Reviewer S2: repeated SIGINT no longer loses the evidence. `_publish_held` (`notion_sandbox.py:386`) sets SIGINT to `SIG_IGN` while it writes the interrupt evidence and restores the previous handler afterwards. `test_repeated_sigint_during_the_evidence_write_keeps_one_file` sends real `os.kill(getpid(), SIGINT)` at create 2, once in the first evidence write, and three times in the publish: exit 69, one complete file, ids 1 and 2, build `PASS`, variants `INTERRUPTED`, and the handler is not left at `SIG_IGN`. Without the mask the interrupt escapes `main`; without the restore the handler stays `SIG_IGN`. Both fail the test.
- Reviewer S3: ifexp (28 rows) and while (3 rows) sites are swept in this round's tables.
- Reviewer S4 (TLS half): `default_tls_context` loads the compiled-in `openssl_cafile` when it is a file, else the compiled-in `openssl_capath` directory (Debian 13 ships the directory and no `cert.pem`). `test_ssl_env_is_refused_and_ignored` no longer requires `cert.pem`; `test_tls_context_loads_the_compiled_in_paths` and `test_tls_context_with_non_text_paths_loads_nothing` pin both branches with no host dependence.
- Verifier should-fix `guard:462` (now `:460`) force-true, `tmp_fd >= 0`: `test_temporary_evidence_fd_is_closed` now also asserts `os.close(-1)` is never called, so the row is KILLED rather than EQUIVALENT.
- Reviewer S5 and the run-plan nits: the run plan below uses `set -euo pipefail`, scrubs proxy and CA-bundle env, runs in the foreground with no timeout, reports each exit separately, names the reconcile fields, and keeps `--execute` for after merge.

Open, not blocking.

- The mutation sweep on this tree is partial (see counts). `notion_sandbox_live.py` and `notion_sandbox_pipeline.py`, and 215 of the guard's 286 mutations, have no round-5 rows. The round-4 literal-operand survivors in those files were addressed by new tests and dead-clause removal, but they are not re-swept here.
- Two untracked files named `--dry-run` and `--execute` appeared in the checkout at 06:59 during the sweep. They were made by the mutant that negates clause 0 of `notion_sandbox.py:202` (`not (arg == "--evidence-out") and index + 1 < len(argv)`). With that mutant, `_evidence_argument` returns the argument after the path, and the refusal evidence is written to that relative name in the pytest cwd (the checkout). Reproduced on a fresh clone: 45 failed and both files appear. Stock source writes neither file (full sandbox suite, clean `git status`). They were deleted. This is a harness artefact, not a product bug. The harness still runs pytest with the checkout as cwd.
- Reviewer S4 (deadline half): the real-SIGINT subprocess tests keep their 20 s / 30 s deadlines. Raising them made every mutant that stops the child before its stop point wait the full deadline, which pushed sweep rows past the timeout. They can still flake on a box with load 25–40.
- Verifier should-fix 2: a bad token shape or a set `NOTION_CONFIG` still writes a refusal evidence file before exit 64. The file holds no token in any form. This is kept as designed (a refusal leaves a record) and is not changed here.
- Reviewer nit: a SIGINT after `os.link` or during the final stdout print gives exit 69 while the file says `PASS` and stdout may be empty. The run plan reconciles on any non-zero exit regardless of the file's `run_status`.
- Failed counts move under load (the Verifier saw `guard:260` give 3 in a 3-worker sweep and 2 alone). This sweep ran 12 workers with a 180 s timeout. Kill status is stable; individual Failed counts can differ by a test or two from a serial rerun.
- The full local pytest keeps the 12 `test_compose_preserves_the_postgres_password` failures (no `docker` binary on this box). CI is the gate.

## If-flip (finished rows only)

| # | Site | Mode | Result | Failed | Test | Condition |
|---|---|---|---|---|---|---|
| 1 | `notion_sandbox.py:120` | flip | KILLED | 8 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `runner_name is None` |
| 2 | `notion_sandbox.py:137` | flip | KILLED | 9 | `test_read_base_exceptions_stay_redacted` | `available and not marked` |
| 3 | `notion_sandbox.py:161` | flip | KILLED | 46 | `test_execute_on_the_fake_adapter_writes_evidence` | `not available or failed` |
| 4 | `notion_sandbox.py:165` | flip | KILLED | 46 | `test_execute_on_the_fake_adapter_writes_evidence` | `runner is None` |
| 5 | `notion_sandbox.py:202` | flip | KILLED | 70 | `test_missing_token_ignores_other_sources` | `arg == "--evidence-out" and index + 1 < len(argv)` |
| 6 | `notion_sandbox.py:204` | flip | KILLED | 10 | `test_abbreviations_are_refused` | `arg.startswith("--evidence-out=")` |
| 7 | `notion_sandbox.py:211` | flip | KILLED | 16 | `test_interrupt_writes_redacted_evidence` | `not ids` |
| 8 | `notion_sandbox.py:233` | flip | KILLED | 149 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `type(moment) is not datetime or moment.tzinfo is None` |
| 9 | `notion_sandbox.py:239` | flip | KILLED | 69 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `token is not None and token_shape_ok(token)` |
| 10 | `notion_sandbox.py:344` | flip | KILLED | 4 | `test_real_sigint_records_created_ids[2]` | `current not in (signal.SIG_DFL, signal.default_int_handler)` |
| 11 | `notion_sandbox.py:355` | flip | KILLED | 8 | `test_real_sigint_records_created_ids[2]` | `stat.S_ISLNK(info.st_mode)` |
| 12 | `notion_sandbox.py:408` | flip | KILLED | 13 | `test_real_sigint_records_created_ids[2]` | `path is None or held.started is None or not held.ready` |
| 13 | `notion_sandbox.py:410` | flip | KILLED | 10 | `test_real_sigint_records_created_ids[2]` | `_evidence_is_complete(path)` |
| 14 | `notion_sandbox.py:435` | flip | KILLED | 7 | `test_real_sigint_records_created_ids[2]` | `_evidence_is_complete(path)` |
| 15 | `notion_sandbox.py:475` | flip | KILLED | 104 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `argv_names_a_target(arguments) or environ_names_a_target(env) or cert_env_set(env)` |
| 16 | `notion_sandbox.py:483` | flip | KILLED | 98 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `leaks(str(evidence), secret)` |
| 17 | `notion_sandbox.py:487` | flip | KILLED | 72 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `parsed.execute and parsed.dry_run` |
| 18 | `notion_sandbox.py:493` | flip | KILLED | 71 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `token is None` |
| 19 | `notion_sandbox.py:504` | flip | KILLED | 68 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `secret is None` |
| 20 | `notion_sandbox.py:556` | flip | KILLED | 59 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `type(bot.user_type) is not str` |
| 21 | `notion_sandbox.py:573` | flip | KILLED | 56 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `not target_ok(bot, page)` |
| 22 | `notion_sandbox.py:590` | flip | KILLED | 47 | `test_dry_run_is_the_default_and_writes_nothing` | `mode == "dry-run"` |
| 23 | `notion_sandbox.py:647` | flip | KILLED | 40 | `test_execute_on_the_fake_adapter_writes_evidence` | `interrupted` |
| 24 | `notion_sandbox.py:651` | flip | KILLED | 32 | `test_execute_on_the_fake_adapter_writes_evidence` | `failed` |
| 25 | `notion_sandbox.py:686` | flip | KILLED | 13 | `test_interrupt_after_store_records_the_created_id[0-exc0]` | `bind is None` |
| 26 | `notion_sandbox.py:692` | flip | KILLED | 37 | `test_execute_on_the_fake_adapter_writes_evidence` | `type(bot.user_id) is str` |
| 27 | `notion_sandbox.py:733` | flip | KILLED | 14 | `test_token_in_error_is_redacted` | `error is not None` |
| 28 | `notion_sandbox.py:735` | flip | KILLED | 20 | `test_execute_on_the_fake_adapter_writes_evidence` | `interrupted or any(stage.get("status") == "INTERRUPTED" for stage in stages)` |
| 29 | `notion_sandbox.py:738` | flip | KILLED | 123 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `check == "FAIL"` |
| 30 | `notion_sandbox.py:740` | flip | KILLED | 115 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `code == EXIT_OK` |
| 31 | `notion_sandbox.py:783` | flip | KILLED | 40 | `test_override_env_refuses[-NOTION_CONFIG]` | `path is not None and not leaks(str(path), token)` |
| 32 | `notion_sandbox.py:790` | flip | KILLED | 1 | `collection error` | `__name__ == "__main__"` |
| 33 | `notion_sandbox_guard.py:144` | flip | KILLED | 78 | `(log only)` | `type(value) is not str` |
| 34 | `notion_sandbox_guard.py:147` | flip | KILLED | 78 | `(log only)` | `len(compact) != 32` |
| 35 | `notion_sandbox_guard.py:149` | flip | KILLED | 78 | `(log only)` | `any(character not in "0123456789abcdef" for character in compact)` |
| 36 | `notion_sandbox_guard.py:156` | flip | KILLED | 47 | `(log only)` | `type(bot.user_type) is not str or bot.user_type != "bot"` |
| 37 | `notion_sandbox_guard.py:158` | flip | KILLED | 52 | `(log only)` | `page.archived or page.parent_type in {"database_id", "data_source_id"}` |
| 38 | `notion_sandbox_guard.py:160` | flip | KILLED | 47 | `(log only)` | `canonical_id(bot.space_id) != SANDBOX_SPACE_ID` |
| 39 | `notion_sandbox_guard.py:162` | flip | KILLED | 46 | `(log only)` | `canonical_id(page.page_id) != SANDBOX_PARENT_PAGE_ID` |
| 40 | `notion_sandbox_guard.py:170` | flip | KILLED | 63 | `(log only)` | `candidate == ""` |
| 41 | `notion_sandbox_guard.py:178` | flip | KILLED | 70 | `(log only)` | `type(value) is not str or value == ""` |
| 42 | `notion_sandbox_guard.py:203` | flip | KILLED | 82 | `(log only)` | `head in _OVERRIDE_FLAGS` |
| 43 | `notion_sandbox_guard.py:205` | flip | KILLED | 71 | `(log only)` | `contains_secret_shape(arg)` |
| 44 | `notion_sandbox_guard.py:217` | flip | KILLED | 152 | `(log only)` | `token is None or not token_shape_ok(token)` |

## Force-true (finished rows only)

| # | Site | Mode | Result | Failed | Test | Condition |
|---|---|---|---|---|---|---|
| 1 | `notion_sandbox.py:120` | true | KILLED | 8 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `runner_name is None` |
| 2 | `notion_sandbox.py:137` | true | KILLED | 9 | `test_read_base_exceptions_stay_redacted` | `available and not marked` |
| 3 | `notion_sandbox.py:161` | true | KILLED | 46 | `test_execute_on_the_fake_adapter_writes_evidence` | `not available or failed` |
| 4 | `notion_sandbox.py:165` | true | KILLED | 45 | `test_execute_on_the_fake_adapter_writes_evidence` | `runner is None` |
| 5 | `notion_sandbox.py:202` | true | KILLED | 10 | `test_evidence_out_equals_matches_the_space_form` | `arg == "--evidence-out" and index + 1 < len(argv)` |
| 6 | `notion_sandbox.py:204` | true | KILLED | 9 | `test_abbreviations_are_refused` | `arg.startswith("--evidence-out=")` |
| 7 | `notion_sandbox.py:211` | true | KILLED | 15 | `test_interrupt_writes_redacted_evidence` | `not ids` |
| 8 | `notion_sandbox.py:233` | true | KILLED | 146 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `type(moment) is not datetime or moment.tzinfo is None` |
| 9 | `notion_sandbox.py:239` | true | KILLED | 8 | `test_short_token_is_refused` | `token is not None and token_shape_ok(token)` |
| 10 | `notion_sandbox.py:344` | true | KILLED | 5 | `test_real_sigint_records_created_ids[2]` | `current not in (signal.SIG_DFL, signal.default_int_handler)` |
| 11 | `notion_sandbox.py:355` | true | KILLED | 7 | `test_real_sigint_records_created_ids[2]` | `stat.S_ISLNK(info.st_mode)` |
| 12 | `notion_sandbox.py:408` | true | KILLED | 9 | `test_real_sigint_records_created_ids[2]` | `path is None or held.started is None or not held.ready` |
| 13 | `notion_sandbox.py:410` | true | KILLED | 9 | `test_real_sigint_records_created_ids[2]` | `_evidence_is_complete(path)` |
| 14 | `notion_sandbox.py:435` | true | KILLED | 6 | `test_real_sigint_records_created_ids[2]` | `_evidence_is_complete(path)` |
| 15 | `notion_sandbox.py:475` | true | KILLED | 71 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `argv_names_a_target(arguments) or environ_names_a_target(env) or cert_env_set(env)` |
| 16 | `notion_sandbox.py:483` | true | KILLED | 97 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `leaks(str(evidence), secret)` |
| 17 | `notion_sandbox.py:487` | true | KILLED | 71 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `parsed.execute and parsed.dry_run` |
| 18 | `notion_sandbox.py:493` | true | KILLED | 68 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `token is None` |
| 19 | `notion_sandbox.py:504` | true | KILLED | 65 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `secret is None` |
| 20 | `notion_sandbox.py:556` | true | KILLED | 58 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `type(bot.user_type) is not str` |
| 21 | `notion_sandbox.py:573` | true | KILLED | 45 | `test_dry_run_is_the_default_and_writes_nothing` | `not target_ok(bot, page)` |
| 22 | `notion_sandbox.py:590` | true | KILLED | 38 | `test_execute_on_the_fake_adapter_writes_evidence` | `mode == "dry-run"` |
| 23 | `notion_sandbox.py:647` | true | KILLED | 31 | `test_execute_on_the_fake_adapter_writes_evidence` | `interrupted` |
| 24 | `notion_sandbox.py:651` | true | KILLED | 12 | `test_execute_on_the_fake_adapter_writes_evidence` | `failed` |
| 25 | `notion_sandbox.py:686` | true | KILLED | 12 | `test_interrupt_after_store_records_the_created_id[0-exc0]` | `bind is None` |
| 26 | `notion_sandbox.py:692` | true | KILLED | 6 | `test_non_string_bot_user_id_is_omitted` | `type(bot.user_id) is str` |
| 27 | `notion_sandbox.py:733` | true | KILLED | 10 | `test_execute_on_the_fake_adapter_writes_evidence` | `error is not None` |
| 28 | `notion_sandbox.py:735` | true | KILLED | 8 | `test_execute_on_the_fake_adapter_writes_evidence` | `interrupted or any(stage.get("status") == "INTERRUPTED" for stage in stages)` |
| 29 | `notion_sandbox.py:738` | true | KILLED | 120 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `check == "FAIL"` |
| 30 | `notion_sandbox.py:740` | true | KILLED | 105 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `code == EXIT_OK` |
| 31 | `notion_sandbox.py:783` | true | KILLED | 7 | `test_both_flags_and_secret_evidence_path_refuse` | `path is not None and not leaks(str(path), token)` |
| 32 | `notion_sandbox.py:790` | true | KILLED | 1 | `collection error` | `__name__ == "__main__"` |
| 33 | `notion_sandbox_guard.py:144` | true | KILLED | 78 | `(log only)` | `type(value) is not str` |
| 34 | `notion_sandbox_guard.py:147` | true | KILLED | 79 | `(log only)` | `len(compact) != 32` |
| 35 | `notion_sandbox_guard.py:149` | true | KILLED | 78 | `(log only)` | `any(character not in "0123456789abcdef" for character in compact)` |
| 36 | `notion_sandbox_guard.py:156` | true | KILLED | 46 | `(log only)` | `type(bot.user_type) is not str or bot.user_type != "bot"` |
| 37 | `notion_sandbox_guard.py:158` | true | KILLED | 46 | `(log only)` | `page.archived or page.parent_type in {"database_id", "data_source_id"}` |
| 38 | `notion_sandbox_guard.py:160` | true | KILLED | 46 | `(log only)` | `canonical_id(bot.space_id) != SANDBOX_SPACE_ID` |
| 39 | `notion_sandbox_guard.py:162` | true | KILLED | 46 | `(log only)` | `canonical_id(page.page_id) != SANDBOX_PARENT_PAGE_ID` |
| 40 | `notion_sandbox_guard.py:170` | true | KILLED | 63 | `(log only)` | `candidate == ""` |
| 41 | `notion_sandbox_guard.py:178` | true | KILLED | 70 | `(log only)` | `type(value) is not str or value == ""` |
| 42 | `notion_sandbox_guard.py:203` | true | KILLED | 71 | `(log only)` | `head in _OVERRIDE_FLAGS` |
| 43 | `notion_sandbox_guard.py:205` | true | KILLED | 71 | `(log only)` | `contains_secret_shape(arg)` |
| 44 | `notion_sandbox_guard.py:217` | true | KILLED | 9 | `(log only)` | `token is None or not token_shape_ok(token)` |

## Force-false (finished rows only)

| # | Site | Mode | Result | Failed | Test | Condition |
|---|---|---|---|---|---|---|
| 1 | `notion_sandbox.py:120` | false | KILLED | 8 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `runner_name is None` |
| 2 | `notion_sandbox.py:137` | false | KILLED | 8 | `test_read_base_exceptions_stay_redacted` | `available and not marked` |
| 3 | `notion_sandbox.py:161` | false | KILLED | 6 | `test_absent_stage_failure_stays_not_run` | `not available or failed` |
| 4 | `notion_sandbox.py:165` | false | KILLED | 6 | `test_real_sigint_records_created_ids[2]` | `runner is None` |
| 5 | `notion_sandbox.py:202` | false | KILLED | 38 | `test_override_env_refuses[-NOTION_CONFIG]` | `arg == "--evidence-out" and index + 1 < len(argv)` |
| 6 | `notion_sandbox.py:204` | false | KILLED | 7 | `test_equals_form_records_an_override_refusal` | `arg.startswith("--evidence-out=")` |
| 7 | `notion_sandbox.py:211` | false | KILLED | 7 | `test_real_sigint_records_created_ids[2]` | `not ids` |
| 8 | `notion_sandbox.py:233` | false | KILLED | 8 | `test_naive_clock_is_refused` | `type(moment) is not datetime or moment.tzinfo is None` |
| 9 | `notion_sandbox.py:239` | false | KILLED | 66 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `token is not None and token_shape_ok(token)` |
| 10 | `notion_sandbox.py:344` | false | KILLED | 1 | `test_custom_sigint_handler_is_left_in_place` | `current not in (signal.SIG_DFL, signal.default_int_handler)` |
| 11 | `notion_sandbox.py:355` | false | KILLED | 6 | `test_real_sigint_records_created_ids[2]` | `stat.S_ISLNK(info.st_mode)` |
| 12 | `notion_sandbox.py:408` | false | KILLED | 9 | `test_real_sigint_records_created_ids[2]` | `path is None or held.started is None or not held.ready` |
| 13 | `notion_sandbox.py:410` | false | KILLED | 6 | `test_real_sigint_records_created_ids[2]` | `_evidence_is_complete(path)` |
| 14 | `notion_sandbox.py:435` | false | KILLED | 6 | `test_real_sigint_records_created_ids[2]` | `_evidence_is_complete(path)` |
| 15 | `notion_sandbox.py:475` | false | KILLED | 38 | `test_override_env_refuses[-NOTION_CONFIG]` | `argv_names_a_target(arguments) or environ_names_a_target(env) or cert_env_set(env)` |
| 16 | `notion_sandbox.py:483` | false | KILLED | 6 | `test_encoded_token_evidence_path_writes_nothing` | `leaks(str(evidence), secret)` |
| 17 | `notion_sandbox.py:487` | false | KILLED | 6 | `test_both_flags_and_secret_evidence_path_refuse` | `parsed.execute and parsed.dry_run` |
| 18 | `notion_sandbox.py:493` | false | KILLED | 8 | `test_missing_token_ignores_other_sources` | `token is None` |
| 19 | `notion_sandbox.py:504` | false | KILLED | 8 | `test_short_token_is_refused` | `secret is None` |
| 20 | `notion_sandbox.py:556` | false | KILLED | 6 | `test_non_string_user_type_exits_69` | `type(bot.user_type) is not str` |
| 21 | `notion_sandbox.py:573` | false | KILLED | 16 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `not target_ok(bot, page)` |
| 22 | `notion_sandbox.py:590` | false | KILLED | 14 | `test_dry_run_is_the_default_and_writes_nothing` | `mode == "dry-run"` |
| 23 | `notion_sandbox.py:647` | false | KILLED | 14 | `test_interrupt_writes_redacted_evidence` | `interrupted` |
| 24 | `notion_sandbox.py:651` | false | KILLED | 25 | `test_absent_stage_failure_stays_not_run` | `failed` |
| 25 | `notion_sandbox.py:686` | false | KILLED | 6 | `test_execute_without_bind_created_still_records` | `bind is None` |
| 26 | `notion_sandbox.py:692` | false | KILLED | 36 | `test_execute_on_the_fake_adapter_writes_evidence` | `type(bot.user_id) is str` |
| 27 | `notion_sandbox.py:733` | false | KILLED | 9 | `test_token_in_error_is_redacted` | `error is not None` |
| 28 | `notion_sandbox.py:735` | false | KILLED | 17 | `test_interrupt_writes_redacted_evidence` | `interrupted or any(stage.get("status") == "INTERRUPTED" for stage in stages)` |
| 29 | `notion_sandbox.py:738` | false | KILLED | 8 | `test_failed_redaction_exits_70` | `check == "FAIL"` |
| 30 | `notion_sandbox.py:740` | false | KILLED | 15 | `test_dry_run_is_the_default_and_writes_nothing` | `code == EXIT_OK` |
| 31 | `notion_sandbox.py:783` | false | KILLED | 38 | `test_override_env_refuses[-NOTION_CONFIG]` | `path is not None and not leaks(str(path), token)` |
| 32 | `notion_sandbox.py:790` | false | KILLED | 6 | `test_module_entry_point_runs_main` | `__name__ == "__main__"` |
| 33 | `notion_sandbox_guard.py:144` | false | KILLED | 27 | `(log only)` | `type(value) is not str` |
| 34 | `notion_sandbox_guard.py:147` | false | KILLED | 19 | `(log only)` | `len(compact) != 32` |
| 35 | `notion_sandbox_guard.py:149` | false | KILLED | 6 | `(log only)` | `any(character not in "0123456789abcdef" for character in compact)` |
| 36 | `notion_sandbox_guard.py:156` | false | KILLED | 8 | `(log only)` | `type(bot.user_type) is not str or bot.user_type != "bot"` |
| 37 | `notion_sandbox_guard.py:158` | false | KILLED | 12 | `(log only)` | `page.archived or page.parent_type in {"database_id", "data_source_id"}` |
| 38 | `notion_sandbox_guard.py:160` | false | KILLED | 7 | `(log only)` | `canonical_id(bot.space_id) != SANDBOX_SPACE_ID` |
| 39 | `notion_sandbox_guard.py:162` | false | KILLED | 6 | `(log only)` | `canonical_id(page.page_id) != SANDBOX_PARENT_PAGE_ID` |
| 40 | `notion_sandbox_guard.py:170` | false | KILLED | 6 | `(log only)` | `candidate == ""` |
| 41 | `notion_sandbox_guard.py:178` | false | KILLED | 7 | `(log only)` | `type(value) is not str or value == ""` |
| 42 | `notion_sandbox_guard.py:203` | false | KILLED | 16 | `(log only)` | `head in _OVERRIDE_FLAGS` |
| 43 | `notion_sandbox_guard.py:205` | false | KILLED | 6 | `(log only)` | `contains_secret_shape(arg)` |
| 44 | `notion_sandbox_guard.py:217` | false | KILLED | 152 | `(log only)` | `token is None or not token_shape_ok(token)` |

## Boolean operands (finished rows only)

| # | Site | Operator | Mutation | Result | Failed | Test | Condition |
|---|---|---|---|---|---|---|---|
| 1 | `notion_sandbox.py:137` | and | 1true | KILLED | 5 | `test_real_sigint_records_created_ids[2]` | `available and not marked` |
| 2 | `notion_sandbox.py:137` | and | 1false | KILLED | 8 | `test_read_base_exceptions_stay_redacted` | `available and not marked` |
| 3 | `notion_sandbox.py:137` | and | 2true | KILLED | 8 | `test_read_base_exceptions_stay_redacted` | `available and not marked` |
| 4 | `notion_sandbox.py:137` | and | 2false | KILLED | 8 | `test_read_base_exceptions_stay_redacted` | `available and not marked` |
| 5 | `notion_sandbox.py:137` | and | not1 | KILLED | 8 | `test_read_base_exceptions_stay_redacted` | `available and not marked` |
| 6 | `notion_sandbox.py:137` | and | not2 | KILLED | 9 | `test_read_base_exceptions_stay_redacted` | `available and not marked` |
| 7 | `notion_sandbox.py:137` | and | swap | KILLED | 8 | `test_read_base_exceptions_stay_redacted` | `available and not marked` |
| 8 | `notion_sandbox.py:161` | or | 1true | KILLED | 46 | `test_execute_on_the_fake_adapter_writes_evidence` | `not available or failed` |
| 9 | `notion_sandbox.py:161` | or | 1false | KILLED | 5 | `test_real_sigint_records_created_ids[2]` | `not available or failed` |
| 10 | `notion_sandbox.py:161` | or | 2true | KILLED | 46 | `test_execute_on_the_fake_adapter_writes_evidence` | `not available or failed` |
| 11 | `notion_sandbox.py:161` | or | 2false | KILLED | 6 | `test_absent_stage_failure_stays_not_run` | `not available or failed` |
| 12 | `notion_sandbox.py:161` | or | not1 | KILLED | 46 | `test_execute_on_the_fake_adapter_writes_evidence` | `not available or failed` |
| 13 | `notion_sandbox.py:161` | or | not2 | KILLED | 46 | `test_execute_on_the_fake_adapter_writes_evidence` | `not available or failed` |
| 14 | `notion_sandbox.py:161` | or | swap | KILLED | 6 | `test_absent_stage_failure_stays_not_run` | `not available or failed` |
| 15 | `notion_sandbox.py:202` | and | 1true | KILLED | 6 | `test_real_sigint_records_created_ids[2]` | `arg == "--evidence-out" and index + 1 < len(argv)` |
| 16 | `notion_sandbox.py:202` | and | 1false | KILLED | 38 | `test_override_env_refuses[-NOTION_CONFIG]` | `arg == "--evidence-out" and index + 1 < len(argv)` |
| 17 | `notion_sandbox.py:202` | and | 2true | KILLED | 7 | `test_evidence_out_without_a_value_is_usage` | `arg == "--evidence-out" and index + 1 < len(argv)` |
| 18 | `notion_sandbox.py:202` | and | 2false | KILLED | 38 | `test_override_env_refuses[-NOTION_CONFIG]` | `arg == "--evidence-out" and index + 1 < len(argv)` |
| 19 | `notion_sandbox.py:202` | and | not1 | KILLED | 50 | `test_override_env_refuses[-NOTION_CONFIG]` | `arg == "--evidence-out" and index + 1 < len(argv)` |
| 20 | `notion_sandbox.py:202` | and | not2 | KILLED | 39 | `test_override_env_refuses[-NOTION_CONFIG]` | `arg == "--evidence-out" and index + 1 < len(argv)` |
| 21 | `notion_sandbox.py:202` | and | swap | KILLED | 7 | `test_evidence_out_without_a_value_is_usage` | `arg == "--evidence-out" and index + 1 < len(argv)` |
| 22 | `notion_sandbox.py:210` | and | 1true | KILLED | 6 | `test_real_sigint_records_created_ids[2]` | `type(row.get("id")) is str and row["id"] != ""` |
| 23 | `notion_sandbox.py:210` | and | 1false | KILLED | 15 | `test_interrupt_writes_redacted_evidence` | `type(row.get("id")) is str and row["id"] != ""` |
| 24 | `notion_sandbox.py:210` | and | 2true | KILLED | 7 | `test_real_sigint_records_created_ids[2]` | `type(row.get("id")) is str and row["id"] != ""` |
| 25 | `notion_sandbox.py:210` | and | 2false | KILLED | 15 | `test_interrupt_writes_redacted_evidence` | `type(row.get("id")) is str and row["id"] != ""` |
| 26 | `notion_sandbox.py:210` | and | not1 | KILLED | 15 | `test_interrupt_writes_redacted_evidence` | `type(row.get("id")) is str and row["id"] != ""` |
| 27 | `notion_sandbox.py:210` | and | not2 | KILLED | 16 | `test_interrupt_writes_redacted_evidence` | `type(row.get("id")) is str and row["id"] != ""` |
| 28 | `notion_sandbox.py:210` | and | swap | KILLED | 7 | `test_real_sigint_records_created_ids[2]` | `type(row.get("id")) is str and row["id"] != ""` |
| 29 | `notion_sandbox.py:233` | or | 1true | KILLED | 146 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `type(moment) is not datetime or moment.tzinfo is None` |
| 30 | `notion_sandbox.py:233` | or | 1false | KILLED | 7 | `test_real_sigint_records_created_ids[2]` | `type(moment) is not datetime or moment.tzinfo is None` |
| 31 | `notion_sandbox.py:233` | or | 2true | KILLED | 146 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `type(moment) is not datetime or moment.tzinfo is None` |
| 32 | `notion_sandbox.py:233` | or | 2false | KILLED | 6 | `test_naive_clock_is_refused` | `type(moment) is not datetime or moment.tzinfo is None` |
| 33 | `notion_sandbox.py:233` | or | not1 | KILLED | 148 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `type(moment) is not datetime or moment.tzinfo is None` |
| 34 | `notion_sandbox.py:233` | or | not2 | KILLED | 147 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `type(moment) is not datetime or moment.tzinfo is None` |
| 35 | `notion_sandbox.py:233` | or | swap | KILLED | 8 | `test_naive_clock_is_refused` | `type(moment) is not datetime or moment.tzinfo is None` |
| 36 | `notion_sandbox.py:239` | and | 1true | KILLED | 8 | `test_missing_token_ignores_other_sources` | `token is not None and token_shape_ok(token)` |
| 37 | `notion_sandbox.py:239` | and | 1false | KILLED | 66 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `token is not None and token_shape_ok(token)` |
| 38 | `notion_sandbox.py:239` | and | 2true | KILLED | 8 | `test_short_token_is_refused` | `token is not None and token_shape_ok(token)` |
| 39 | `notion_sandbox.py:239` | and | 2false | KILLED | 66 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `token is not None and token_shape_ok(token)` |
| 40 | `notion_sandbox.py:239` | and | not1 | KILLED | 69 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `token is not None and token_shape_ok(token)` |
| 41 | `notion_sandbox.py:239` | and | not2 | KILLED | 69 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `token is not None and token_shape_ok(token)` |
| 42 | `notion_sandbox.py:239` | and | swap | KILLED | 11 | `test_short_token_is_refused` | `token is not None and token_shape_ok(token)` |
| 43 | `notion_sandbox.py:408` | or | 1true | KILLED | 9 | `test_real_sigint_records_created_ids[2]` | `path is None or held.started is None or not held.ready` |
| 44 | `notion_sandbox.py:408` | or | 1false | KILLED | 6 | `test_real_sigint_records_created_ids[2]` | `path is None or held.started is None or not held.ready` |
| 45 | `notion_sandbox.py:408` | or | 2true | KILLED | 9 | `test_real_sigint_records_created_ids[2]` | `path is None or held.started is None or not held.ready` |
| 46 | `notion_sandbox.py:408` | or | 2false | KILLED | 6 | `test_real_sigint_records_created_ids[2]` | `path is None or held.started is None or not held.ready` |
| 47 | `notion_sandbox.py:408` | or | 3true | KILLED | 9 | `test_real_sigint_records_created_ids[2]` | `path is None or held.started is None or not held.ready` |
| 48 | `notion_sandbox.py:408` | or | 3false | KILLED | 6 | `test_real_sigint_records_created_ids[2]` | `path is None or held.started is None or not held.ready` |
| 49 | `notion_sandbox.py:408` | or | not1 | KILLED | 10 | `test_real_sigint_records_created_ids[2]` | `path is None or held.started is None or not held.ready` |
| 50 | `notion_sandbox.py:408` | or | not2 | KILLED | 10 | `test_real_sigint_records_created_ids[2]` | `path is None or held.started is None or not held.ready` |
| 51 | `notion_sandbox.py:408` | or | not3 | KILLED | 10 | `test_real_sigint_records_created_ids[2]` | `path is None or held.started is None or not held.ready` |
| 52 | `notion_sandbox.py:408` | or | swap | KILLED | 8 | `test_real_sigint_records_created_ids[2]` | `path is None or held.started is None or not held.ready` |
| 53 | `notion_sandbox.py:475` | or | 1true | KILLED | 71 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `argv_names_a_target(arguments) or environ_names_a_target(env) or cert_env_set(env)` |
| 54 | `notion_sandbox.py:475` | or | 1false | KILLED | 6 | `test_token_on_argv_is_refused` | `argv_names_a_target(arguments) or environ_names_a_target(env) or cert_env_set(env)` |
| 55 | `notion_sandbox.py:475` | or | 2true | KILLED | 71 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `argv_names_a_target(arguments) or environ_names_a_target(env) or cert_env_set(env)` |
| 56 | `notion_sandbox.py:475` | or | 2false | KILLED | 36 | `test_override_env_refuses[-NOTION_CONFIG]` | `argv_names_a_target(arguments) or environ_names_a_target(env) or cert_env_set(env)` |
| 57 | `notion_sandbox.py:475` | or | 3true | KILLED | 71 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `argv_names_a_target(arguments) or environ_names_a_target(env) or cert_env_set(env)` |
| 58 | `notion_sandbox.py:475` | or | 3false | KILLED | 6 | `test_ssl_env_is_refused_and_ignored` | `argv_names_a_target(arguments) or environ_names_a_target(env) or cert_env_set(env)` |
| 59 | `notion_sandbox.py:475` | or | not1 | KILLED | 72 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `argv_names_a_target(arguments) or environ_names_a_target(env) or cert_env_set(env)` |
| 60 | `notion_sandbox.py:475` | or | not2 | KILLED | 102 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `argv_names_a_target(arguments) or environ_names_a_target(env) or cert_env_set(env)` |
| 61 | `notion_sandbox.py:475` | or | not3 | KILLED | 72 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `argv_names_a_target(arguments) or environ_names_a_target(env) or cert_env_set(env)` |
| 62 | `notion_sandbox.py:475` | or | swap | KILLED | 38 | `test_override_env_refuses[-NOTION_CONFIG]` | `argv_names_a_target(arguments) or environ_names_a_target(env) or cert_env_set(env)` |
| 63 | `notion_sandbox.py:487` | and | 1true | KILLED | 6 | `test_evidence_out_without_a_value_is_usage` | `parsed.execute and parsed.dry_run` |
| 64 | `notion_sandbox.py:487` | and | 1false | KILLED | 6 | `test_both_flags_and_secret_evidence_path_refuse` | `parsed.execute and parsed.dry_run` |
| 65 | `notion_sandbox.py:487` | and | 2true | KILLED | 58 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `parsed.execute and parsed.dry_run` |
| 66 | `notion_sandbox.py:487` | and | 2false | KILLED | 6 | `test_both_flags_and_secret_evidence_path_refuse` | `parsed.execute and parsed.dry_run` |
| 67 | `notion_sandbox.py:487` | and | not1 | KILLED | 7 | `test_both_flags_and_secret_evidence_path_refuse` | `parsed.execute and parsed.dry_run` |
| 68 | `notion_sandbox.py:487` | and | not2 | KILLED | 59 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `parsed.execute and parsed.dry_run` |
| 69 | `notion_sandbox.py:487` | and | swap | KILLED | 59 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `parsed.execute and parsed.dry_run` |
| 70 | `notion_sandbox.py:615` | or | 1true | KILLED | 34 | `test_execute_on_the_fake_adapter_writes_evidence` | `_user_id(bot) or ""` |
| 71 | `notion_sandbox.py:615` | or | 1false | KILLED | 33 | `test_execute_on_the_fake_adapter_writes_evidence` | `_user_id(bot) or ""` |
| 72 | `notion_sandbox.py:615` | or | 2true | KILLED | 6 | `test_empty_bot_user_id_still_executes` | `_user_id(bot) or ""` |
| 73 | `notion_sandbox.py:615` | or | 2false | KILLED | 6 | `test_empty_bot_user_id_still_executes` | `_user_id(bot) or ""` |
| 74 | `notion_sandbox.py:615` | or | not1 | KILLED | 34 | `test_execute_on_the_fake_adapter_writes_evidence` | `_user_id(bot) or ""` |
| 75 | `notion_sandbox.py:615` | or | not2 | KILLED | 6 | `test_empty_bot_user_id_still_executes` | `_user_id(bot) or ""` |
| 76 | `notion_sandbox.py:615` | or | swap | KILLED | 33 | `test_execute_on_the_fake_adapter_writes_evidence` | `_user_id(bot) or ""` |
| 77 | `notion_sandbox.py:645` | or | 1true | KILLED | 31 | `test_execute_on_the_fake_adapter_writes_evidence` | `signalled or any(stage["status"] == "INTERRUPTED" for stage in stages)` |
| 78 | `notion_sandbox.py:645` | or | 1false | KILLED | 6 | `test_real_sigint_records_created_ids[2]` | `signalled or any(stage["status"] == "INTERRUPTED" for stage in stages)` |
| 79 | `notion_sandbox.py:645` | or | 2true | KILLED | 31 | `test_execute_on_the_fake_adapter_writes_evidence` | `signalled or any(stage["status"] == "INTERRUPTED" for stage in stages)` |
| 80 | `notion_sandbox.py:645` | or | 2false | KILLED | 13 | `test_interrupt_writes_redacted_evidence` | `signalled or any(stage["status"] == "INTERRUPTED" for stage in stages)` |
| 81 | `notion_sandbox.py:645` | or | not1 | KILLED | 32 | `test_execute_on_the_fake_adapter_writes_evidence` | `signalled or any(stage["status"] == "INTERRUPTED" for stage in stages)` |
| 82 | `notion_sandbox.py:645` | or | not2 | KILLED | 39 | `test_execute_on_the_fake_adapter_writes_evidence` | `signalled or any(stage["status"] == "INTERRUPTED" for stage in stages)` |
| 83 | `notion_sandbox.py:645` | or | swap | KILLED | 14 | `test_interrupt_writes_redacted_evidence` | `signalled or any(stage["status"] == "INTERRUPTED" for stage in stages)` |
| 84 | `notion_sandbox.py:735` | or | 1true | KILLED | 8 | `test_execute_on_the_fake_adapter_writes_evidence` | `interrupted or any(stage.get("status") == "INTERRUPTED" for stage in stages)` |
| 85 | `notion_sandbox.py:735` | or | 1false | KILLED | 8 | `test_real_sigint_records_created_ids[2]` | `interrupted or any(stage.get("status") == "INTERRUPTED" for stage in stages)` |
| 86 | `notion_sandbox.py:735` | or | 2true | KILLED | 8 | `test_execute_on_the_fake_adapter_writes_evidence` | `interrupted or any(stage.get("status") == "INTERRUPTED" for stage in stages)` |
| 87 | `notion_sandbox.py:735` | or | 2false | KILLED | 14 | `test_interrupt_writes_redacted_evidence` | `interrupted or any(stage.get("status") == "INTERRUPTED" for stage in stages)` |
| 88 | `notion_sandbox.py:735` | or | not1 | KILLED | 11 | `test_execute_on_the_fake_adapter_writes_evidence` | `interrupted or any(stage.get("status") == "INTERRUPTED" for stage in stages)` |
| 89 | `notion_sandbox.py:735` | or | not2 | KILLED | 17 | `test_execute_on_the_fake_adapter_writes_evidence` | `interrupted or any(stage.get("status") == "INTERRUPTED" for stage in stages)` |
| 90 | `notion_sandbox.py:735` | or | swap | KILLED | 17 | `test_interrupt_writes_redacted_evidence` | `interrupted or any(stage.get("status") == "INTERRUPTED" for stage in stages)` |
| 91 | `notion_sandbox.py:783` | and | 1true | KILLED | 6 | `test_real_sigint_records_created_ids[2]` | `path is not None and not leaks(str(path), token)` |
| 92 | `notion_sandbox.py:783` | and | 1false | KILLED | 38 | `test_override_env_refuses[-NOTION_CONFIG]` | `path is not None and not leaks(str(path), token)` |
| 93 | `notion_sandbox.py:783` | and | 2true | KILLED | 6 | `test_both_flags_and_secret_evidence_path_refuse` | `path is not None and not leaks(str(path), token)` |
| 94 | `notion_sandbox.py:783` | and | 2false | KILLED | 38 | `test_override_env_refuses[-NOTION_CONFIG]` | `path is not None and not leaks(str(path), token)` |
| 95 | `notion_sandbox.py:783` | and | not1 | KILLED | 39 | `test_override_env_refuses[-NOTION_CONFIG]` | `path is not None and not leaks(str(path), token)` |
| 96 | `notion_sandbox.py:783` | and | not2 | KILLED | 39 | `test_override_env_refuses[-NOTION_CONFIG]` | `path is not None and not leaks(str(path), token)` |
| 97 | `notion_sandbox.py:783` | and | swap | KILLED | 7 | `test_both_flags_and_secret_evidence_path_refuse` | `path is not None and not leaks(str(path), token)` |
| 98 | `notion_sandbox_guard.py:156` | or | 1true | KILLED | 46 | `(log only)` | `type(bot.user_type) is not str or bot.user_type != "bot"` |
| 99 | `notion_sandbox_guard.py:156` | or | 1false | KILLED | 6 | `(log only)` | `type(bot.user_type) is not str or bot.user_type != "bot"` |
| 100 | `notion_sandbox_guard.py:156` | or | 2true | KILLED | 46 | `(log only)` | `type(bot.user_type) is not str or bot.user_type != "bot"` |
| 101 | `notion_sandbox_guard.py:156` | or | 2false | KILLED | 7 | `(log only)` | `type(bot.user_type) is not str or bot.user_type != "bot"` |
| 102 | `notion_sandbox_guard.py:156` | or | not1 | KILLED | 46 | `(log only)` | `type(bot.user_type) is not str or bot.user_type != "bot"` |
| 103 | `notion_sandbox_guard.py:156` | or | not2 | KILLED | 47 | `(log only)` | `type(bot.user_type) is not str or bot.user_type != "bot"` |
| 104 | `notion_sandbox_guard.py:156` | or | swap | KILLED | 8 | `(log only)` | `type(bot.user_type) is not str or bot.user_type != "bot"` |
| 105 | `notion_sandbox_guard.py:158` | or | 1true | KILLED | 46 | `(log only)` | `page.archived or page.parent_type in {"database_id", "data_source_id"}` |
| 106 | `notion_sandbox_guard.py:158` | or | 1false | KILLED | 10 | `(log only)` | `page.archived or page.parent_type in {"database_id", "data_source_id"}` |
| 107 | `notion_sandbox_guard.py:158` | or | 2true | KILLED | 46 | `(log only)` | `page.archived or page.parent_type in {"database_id", "data_source_id"}` |
| 108 | `notion_sandbox_guard.py:158` | or | 2false | KILLED | 8 | `(log only)` | `page.archived or page.parent_type in {"database_id", "data_source_id"}` |
| 109 | `notion_sandbox_guard.py:158` | or | not1 | KILLED | 50 | `(log only)` | `page.archived or page.parent_type in {"database_id", "data_source_id"}` |
| 110 | `notion_sandbox_guard.py:158` | or | not2 | KILLED | 48 | `(log only)` | `page.archived or page.parent_type in {"database_id", "data_source_id"}` |
| 111 | `notion_sandbox_guard.py:158` | or | swap | KILLED | 12 | `(log only)` | `page.archived or page.parent_type in {"database_id", "data_source_id"}` |
| 112 | `notion_sandbox_guard.py:178` | or | 1true | KILLED | 70 | `(log only)` | `type(value) is not str or value == ""` |
| 113 | `notion_sandbox_guard.py:178` | or | 1false | KILLED | 6 | `(log only)` | `type(value) is not str or value == ""` |
| 114 | `notion_sandbox_guard.py:178` | or | 2true | KILLED | 70 | `(log only)` | `type(value) is not str or value == ""` |
| 115 | `notion_sandbox_guard.py:178` | or | 2false | KILLED | 6 | `(log only)` | `type(value) is not str or value == ""` |
| 116 | `notion_sandbox_guard.py:178` | or | not1 | KILLED | 70 | `(log only)` | `type(value) is not str or value == ""` |
| 117 | `notion_sandbox_guard.py:178` | or | not2 | KILLED | 70 | `(log only)` | `type(value) is not str or value == ""` |
| 118 | `notion_sandbox_guard.py:178` | or | swap | KILLED | 7 | `(log only)` | `type(value) is not str or value == ""` |
| 119 | `notion_sandbox_guard.py:196` | and | 1true | KILLED | 11 | `(log only)` | `found != "" and found != SANDBOX_SPACE_ID` |
| 120 | `notion_sandbox_guard.py:196` | and | 1false | KILLED | 14 | `(log only)` | `found != "" and found != SANDBOX_SPACE_ID` |
| 121 | `notion_sandbox_guard.py:196` | and | 2true | KILLED | 48 | `(log only)` | `found != "" and found != SANDBOX_SPACE_ID` |
| 122 | `notion_sandbox_guard.py:196` | and | 2false | KILLED | 14 | `(log only)` | `found != "" and found != SANDBOX_SPACE_ID` |
| 123 | `notion_sandbox_guard.py:196` | and | not1 | KILLED | 20 | `(log only)` | `found != "" and found != SANDBOX_SPACE_ID` |
| 124 | `notion_sandbox_guard.py:196` | and | not2 | KILLED | 53 | `(log only)` | `found != "" and found != SANDBOX_SPACE_ID` |
| 125 | `notion_sandbox_guard.py:196` | and | swap | KILLED | 50 | `(log only)` | `found != "" and found != SANDBOX_SPACE_ID` |
| 126 | `notion_sandbox_guard.py:212` | or | 1true | KILLED | 11 | `(log only)` | `token.strip() == "" or token in {"true", "false", "null"}` |
| 127 | `notion_sandbox_guard.py:212` | or | 1false | KILLED | 7 | `(log only)` | `token.strip() == "" or token in {"true", "false", "null"}` |
| 128 | `notion_sandbox_guard.py:212` | or | 2true | KILLED | 11 | `(log only)` | `token.strip() == "" or token in {"true", "false", "null"}` |
| 129 | `notion_sandbox_guard.py:212` | or | 2false | KILLED | 9 | `(log only)` | `token.strip() == "" or token in {"true", "false", "null"}` |
| 130 | `notion_sandbox_guard.py:212` | or | not1 | KILLED | 12 | `(log only)` | `token.strip() == "" or token in {"true", "false", "null"}` |
| 131 | `notion_sandbox_guard.py:212` | or | not2 | KILLED | 14 | `(log only)` | `token.strip() == "" or token in {"true", "false", "null"}` |
| 132 | `notion_sandbox_guard.py:212` | or | swap | KILLED | 10 | `(log only)` | `token.strip() == "" or token in {"true", "false", "null"}` |

## IfExp (finished rows only)

| # | Site | Mode | Result | Failed | Test | Condition |
|---|---|---|---|---|---|---|
| 1 | `notion_sandbox.py:230` | true | KILLED | 39 | `test_execute_on_the_fake_adapter_writes_evidence` | `clock is None` |
| 2 | `notion_sandbox.py:230` | false | KILLED | 6 | `test_module_entry_point_runs_main` | `clock is None` |
| 3 | `notion_sandbox.py:265` | true | KILLED | 10 | `test_wrong_space_on_create_return_stops` | `flagged is None` |
| 4 | `notion_sandbox.py:265` | false | KILLED | 5 | `test_real_sigint_records_created_ids[2]` | `flagged is None` |
| 5 | `notion_sandbox.py:268` | true | KILLED | 5 | `test_real_sigint_records_created_ids[2]` | `orphans is None` |
| 6 | `notion_sandbox.py:268` | false | KILLED | 5 | `test_real_sigint_records_created_ids[2]` | `orphans is None` |
| 7 | `notion_sandbox.py:270` | true | KILLED | 9 | `test_stale_foreign_page_is_not_a_parent` | `rejected is None` |
| 8 | `notion_sandbox.py:270` | false | KILLED | 5 | `test_real_sigint_records_created_ids[2]` | `rejected is None` |
| 9 | `notion_sandbox.py:422` | true | KILLED | 5 | `test_real_sigint_records_created_ids[2]` | `held.counts` |
| 10 | `notion_sandbox.py:422` | false | KILLED | 5 | `test_real_sigint_records_created_ids[2]` | `held.counts` |
| 11 | `notion_sandbox.py:468` | true | KILLED | 129 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `argv is None` |
| 12 | `notion_sandbox.py:468` | false | KILLED | 6 | `test_module_entry_point_runs_main` | `argv is None` |
| 13 | `notion_sandbox.py:469` | true | KILLED | 45 | `test_short_token_is_refused` | `environ is None` |
| 14 | `notion_sandbox.py:469` | false | KILLED | 6 | `test_module_entry_point_runs_main` | `environ is None` |
| 15 | `notion_sandbox.py:491` | true | KILLED | 16 | `test_dry_run_is_the_default_and_writes_nothing` | `parsed.execute` |
| 16 | `notion_sandbox.py:491` | false | KILLED | 38 | `test_execute_on_the_fake_adapter_writes_evidence` | `parsed.execute` |
| 17 | `notion_sandbox.py:515` | true | KILLED | 5 | `test_real_sigint_records_created_ids[2]` | `client is not None` |
| 18 | `notion_sandbox.py:515` | false | KILLED | 63 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `client is not None` |
| 19 | `notion_sandbox.py:607` | true | KILLED | 6 | `test_absent_stage_failure_stays_not_run` | `spec is None` |
| 20 | `notion_sandbox.py:607` | false | KILLED | 44 | `test_execute_on_the_fake_adapter_writes_evidence` | `spec is None` |

## 2026-10-08 — Session 07 sandbox run, round 4

Not a session close. This is not SESSION_07 COMPLETE. `state_revision` stays 58. `IMPLEMENTATION_STATE.json` is not edited. `head_sha` stays the W9 squash `a4e9b025021b4effbb2b2879c1db756403cb1676`. Twelve session 7 evidence keys stay false. `commissioned_agents` stays empty. Exit 78 stays HELD. The §11 sandbox CLI is still not run live. This commit's CI run is not invented here. `origin/build/full-automation` was fetched and is still `a4e9b025021b4effbb2b2879c1db756403cb1676`.

The runner is `python -m money_machine.cli.notion_sandbox`. Evidence is written to a temporary file and linked into place after the bytes are complete. `open_evidence` validates the path and does not truncate the destination. `main` catches `KeyboardInterrupt` and `CancelledError` and publishes `INTERRUPTED` evidence that keeps every created id. A second interrupt during that publish leaves a complete file in place. A created time of `12:00:00Z` with the clock at `12:00:37Z` exits 0: `_earliest` floors the clock to the minute, then subtracts two minutes.

Census method: one AST walk of `notion_sandbox.py`, `notion_sandbox_guard.py`, `notion_sandbox_live.py`, and `notion_sandbox_pipeline.py`, in source order. It counts `ast.If`, `ast.BoolOp` (`ast.And` / `ast.Or`, and each clause in `values`), `ast.IfExp`, and `ast.While`. Result: if 159, boolop 63, and 26, or 37, clause 141, ifexp 16, while 3. The if-flip table is one row per `if` (159). The operand table is one operator swap per boolop plus one negation per clause (63 + 141 = 204). Total mutations 159 × 3 + 204 = 681. A row is killed only when that run's pytest exit is non-zero. When the exit is non-zero and the output has no `failed` count, the Failed count is 1. That covers collection errors and the 90-second timeout. Round-3 sums are not this tree.

If-flip: 159 rows, 159 killed, 0 equivalent, Failed sum 5924. `__name__ == "__main__"` is row 33, `notion_sandbox.py:762`, KILLED, Failed 1 (collection error). The second `if leaks(text, token)` inside `render_evidence` is row 68, `notion_sandbox_guard.py:336`, KILLED, Failed 3. The first leaks check is row 67, Failed 123. Force-true: 159 rows, 154 killed, 5 equivalent, Failed sum 5320. Force-false: 159 rows, 156 killed, 3 equivalent, Failed sum 813. Boolean operands: 204 rows, 200 killed, 4 equivalent, Failed sum 5824.

`tests/unit/cli/test_notion_sandbox.py`: 231 passed. Sockets stay blocked. `ruff format --check`, `ruff check`, and `pyright` 1.1.411 are clean on the four sandbox modules and the sandbox test. Full local pytest: 2751 collected, 2546 passed, 193 skipped, 12 failed. All 12 failures are `test_compose_preserves_the_postgres_password` with `FileNotFoundError` because the `docker` binary is absent. They are local-only. One `StarletteDeprecationWarning` comes from FastAPI's test client. The sandbox modules do not import Starlette. CI is the gate.

Equivalent rows. Each one was probed at the function or subprocess, and both versions produced the same output. A behaviour change was labelled KILLED and given a test.

- `notion_sandbox_guard.py:222` force-true, `encoded != token`. `redact_text` and `leaks` were called with `REDACTED`, `[REDACTED]`, a shaped `secret_` token, an `ntn_` token, the token's own url form, its base64 digest, an uppercase token, a short hex token, and a non-hex token. 0 output diffs. A shaped token contains `_`, and the url form replaces `_` with `%5F`, so the encoded string differs from the token and the append already runs. A token that fails `token_shape_ok` has no encoded forms.
- `notion_sandbox_guard.py:224` force-true, and the `and`→`or` swap, `digest not in forms and digest != token`. The same token set, 0 diffs. Base64 of a shaped token contains no `_`, so the digest differs from the token. The two clauses agree on that set, so the swap does not change the redaction result.
- `notion_sandbox_guard.py:237` force-true, `form in cleaned`. The same token set, 0 diffs. `str.replace` of a missing non-empty substring leaves the text unchanged. Encoded forms of a shaped token are non-empty.
- `notion_sandbox_guard.py:462` force-true, `tmp_fd >= 0`. ENOSPC while stdin is closed makes the temp file fd 0. Force-true still closes fd 0 (`errno` 9) and leaves no destination. The flip and the force-false leave fd 0 open. Those two are KILLED, Failed 1, by `test_disk_error_closes_standard_input`.
- `notion_sandbox_pipeline.py:207` force-true, and the `and`→`or` swap, `space_conflicts(page.space_id) and page_id != ""`. The only disagreement is an empty id whose space conflicts. `_remember("")` and `_flag("", ...)` both return immediately. `created_ids` and `flagged_pages` stay unchanged on both versions.
- `notion_sandbox_guard.py:355` force-false, and the `or`→`and` swap, `str(path) == "" or path == Path() or under_proc(path)`. `Path()`, `Path("")`, `/proc/self/status`, a missing path under `/proc`, and `Path("/tmp")` all refuse with exit 64 and no file. A present path hits `info is not None`. A missing path hits the parent `lstat`.
- `notion_sandbox_guard.py:370` `or`→`and`, `S_ISLNK(parent) or not S_ISDIR(parent)`. A regular-file parent and a fifo refuse at the destination `lstat` with `ENOTDIR` before this check. A symlink to a directory makes both operands true. A real directory makes both false and `open_evidence` returns. The loaded source contained `and`.
- `notion_sandbox_pipeline.py:200` force-false, `tail == page_id`. On a bound `create_under`, dropping the matching tail and then `_remember` restores the same id and url.
- `notion_sandbox_pipeline.py:319` force-false, `type(spec) is not ProductSpec`. A `ProductSpec` makes the condition false. A stand-in fails inside `build_top_level_page_and_design_shell` with `phase 1 requires a validated ProductSpec` before this `if`, with 0 creates.

Probes that changed output, now killed.

- `notion_sandbox.py:398` force-true. Two real SIGINTs: the first during a later create, the second during the evidence write. Original evidence keeps build `PASS` and variants `INTERRUPTED`. Force-true marks both `INTERRUPTED`. `test_real_sigint_preserves_a_passing_stage`, Failed 1.
- `notion_sandbox_guard.py:302` force-false. Token `"AB" * 10` against text `"ab" * 10`: original `leaks` is false and the text is unchanged; force-false folds it to `[REDACTED]`. `test_short_upper_hex_is_not_folded`.
- `notion_sandbox_guard.py:304` force-false, `any(character not in "0123456789abcdefABCDEF" ...)`. A `secret%5F` token and a base64 digest, each lowercased in the text: original leaves the text; force-false redacts it. `test_percent_and_base64_tokens_are_not_folded_hex`, Failed 1. `REDACTED` and `[REDACTED]` are not in `_unsafe_exact`. The second `leaks` check at `:336` is a different row, killed by `test_marker_token_fails_the_redaction_self_check`.
- `notion_sandbox_guard.py:372` force-false, `parent_info.st_mode & 0o200 == 0`. Modes `0o500`, `0o555`, and `0o100` call `os.open` on the mutant and the spy records the temp path. `test_unwritable_parent_mode_is_refused_before_open`. The row's first failure is `test_unwritable_directory_writes_nothing`, Failed 4.
- `notion_sandbox_pipeline.py:203` force-false, and the `or`→`and` swap, `page_id == "" or space_conflicts(page.space_id)`. A later create that returns an earlier id in a foreign space: original drops that id (1 kept); the mutant keeps it (2 kept). `test_later_create_returning_an_earlier_foreign_id_drops_it`, Failed 1 each.
- `notion_sandbox_pipeline.py:146` force-false, `ctx.created_ids.index(page_id) < before`. An earlier id stays. The mutant drops it. `test_drop_keeps_an_earlier_id_and_ignores_a_missing_one`, Failed 1. The if-flip and force-true of this `if` time out and count as Failed 1.
- `notion_sandbox_guard.py:509` force-true. The guard file resolves outside the checkout and the cwd is `docs`: original exits 66 and writes evidence; force-true exits 69 with `control state is unreadable`. `test_repo_root_outside_the_checkout_still_uses_the_repo`. The `and`→`or` swap at `:509` accepts a partial marker (`pyproject.toml` alone, or `docs/control` alone) between the cwd and the repo. `test_partial_marker_between_cwd_and_the_repo_is_not_root`, Failed 2.

Blocker to test.

- Real SIGINT, created ids kept, exit 69, and the process is not signalled (`returncode` is not `-2`, `130`, or `-SIGINT`): `test_real_sigint_records_created_ids` after 2 creates and after the 5th create. `test_real_sigint_during_the_evidence_write_leaves_a_complete_file` interrupts the evidence write and still leaves a complete file. `test_real_sigint_preserves_a_passing_stage` keeps build `PASS` beside variants `INTERRUPTED`, with both created ids.
- Minute floor: `test_off_minute_clock_accepts_the_same_minute` and `test_doc_shaped_off_minute_clock_exits_0`. Clock `12:00:37Z`, page `created_time` `12:00:00Z`, exit 0, five created ids.
- Reviewer guard:304 on this tree is `:304` (hex fold) killed by `test_percent_and_base64_tokens_are_not_folded_hex`, and `:336` (second `leaks`) killed by `test_marker_token_fails_the_redaction_self_check` with tokens `REDACTED` and `[REDACTED]`.
- Reviewer guard:340 on this tree is `:372`, killed by `test_unwritable_parent_mode_is_refused_before_open` for modes `0o500`, `0o555`, and `0o100`. `os.open` is not called.
- Reviewer pipeline:146 on this tree is `:203` (force-false and `or`→`and`), killed by `test_later_create_returning_an_earlier_foreign_id_drops_it`, and `:146` (force-false of `index < before`), killed by `test_drop_keeps_an_earlier_id_and_ignores_a_missing_one`.
- Reviewer guard:459 on this tree is `:509`. Force-true: `test_repo_root_outside_the_checkout_still_uses_the_repo`. `and`→`or`: `test_partial_marker_between_cwd_and_the_repo_is_not_root`.
- Other output changes found while probing the first sweep's equivalents, each now killed: `test_missing_stage_runner_is_not_a_failure`, `test_blank_recorded_id_stays_out_of_the_interrupt_line`, `test_custom_sigint_handler_is_left_in_place`, `test_interrupt_before_ready_exits_69`, `test_unpublished_path_is_an_interrupt`, `test_complete_file_during_the_second_interrupt_returns`, `test_each_foreign_page_is_flagged`, `test_unfresh_reread_survives_a_missing_id`, `test_the_same_unfresh_page_is_rejected_once`, `test_confirm_does_not_replace_a_different_tail`, `test_symlink_at_the_link_is_refused`, `test_short_replacement_is_not_finished_evidence`, `test_absent_cafile_skips_load`, `test_dashed_secret_in_the_live_path_is_not_sent`, `test_blank_id_already_recorded_is_kept`, `test_empty_created_id_raises_not_new`, `test_empty_parent_does_not_flag_the_chain`, `test_parent_read_with_a_different_id_is_refused`, `test_returning_the_requested_id_keeps_it`.

## If-flip

| # | Site | Mode | Result | Failed | Test | Condition |
|---|---|---|---|---|---|---|
| 1 | `notion_sandbox.py:119` | flip | KILLED | 3 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `runner_name is None` |
| 2 | `notion_sandbox.py:142` | flip | KILLED | 1 | `test_read_base_exceptions_stay_redacted` | `available and not marked` |
| 3 | `notion_sandbox.py:164` | flip | KILLED | 42 | `test_execute_on_the_fake_adapter_writes_evidence` | `not available or failed` |
| 4 | `notion_sandbox.py:168` | flip | KILLED | 42 | `test_execute_on_the_fake_adapter_writes_evidence` | `runner is None` |
| 5 | `notion_sandbox.py:205` | flip | KILLED | 63 | `test_missing_token_ignores_other_sources` | `arg == "--evidence-out" and index + 1 < len(argv)` |
| 6 | `notion_sandbox.py:207` | flip | KILLED | 3 | `test_abbreviations_are_refused` | `arg.startswith("--evidence-out=")` |
| 7 | `notion_sandbox.py:214` | flip | KILLED | 8 | `test_interrupt_writes_redacted_evidence` | `not ids` |
| 8 | `notion_sandbox.py:236` | flip | KILLED | 140 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `type(moment) is not datetime or moment.tzinfo is None` |
| 9 | `notion_sandbox.py:242` | flip | KILLED | 69 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `token is not None and token_shape_ok(token)` |
| 10 | `notion_sandbox.py:347` | flip | KILLED | 1 | `timeout` | `current not in (signal.SIG_DFL, signal.default_int_handler)` |
| 11 | `notion_sandbox.py:357` | flip | KILLED | 3 | `test_interrupt_after_the_evidence_link_leaves_that_file` | `stat.S_ISLNK(info.st_mode) or info.st_size <= 0` |
| 12 | `notion_sandbox.py:393` | flip | KILLED | 7 | `test_interrupt_does_not_keep_a_symlink` | `path is None or held.started is None or not held.ready` |
| 13 | `notion_sandbox.py:395` | flip | KILLED | 6 | `test_interrupt_after_the_evidence_link_leaves_that_file` | `_evidence_is_complete(path)` |
| 14 | `notion_sandbox.py:398` | flip | KILLED | 3 | `test_second_interrupt_retries_until_a_file_exists` | `not any(stage.get("status") == "INTERRUPTED" for stage in stages)` |
| 15 | `notion_sandbox.py:421` | flip | KILLED | 2 | `test_second_interrupt_retries_until_a_file_exists` | `_evidence_is_complete(path)` |
| 16 | `notion_sandbox.py:461` | flip | KILLED | 104 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `argv_names_a_target(arguments) or environ_names_a_target(env) or cert_env_set(env)` |
| 17 | `notion_sandbox.py:468` | flip | KILLED | 92 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `str(evidence) == "" or leaks(str(evidence), secret)` |
| 18 | `notion_sandbox.py:472` | flip | KILLED | 72 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `parsed.execute and parsed.dry_run` |
| 19 | `notion_sandbox.py:478` | flip | KILLED | 71 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `token is None` |
| 20 | `notion_sandbox.py:489` | flip | KILLED | 68 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `secret is None` |
| 21 | `notion_sandbox.py:541` | flip | KILLED | 59 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `type(bot.user_type) is not str` |
| 22 | `notion_sandbox.py:558` | flip | KILLED | 56 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `not target_ok(bot, page)` |
| 23 | `notion_sandbox.py:575` | flip | KILLED | 47 | `test_dry_run_is_the_default_and_writes_nothing` | `mode == "dry-run"` |
| 24 | `notion_sandbox.py:621` | flip | KILLED | 36 | `test_execute_on_the_fake_adapter_writes_evidence` | `interrupted` |
| 25 | `notion_sandbox.py:625` | flip | KILLED | 26 | `test_execute_on_the_fake_adapter_writes_evidence` | `failed` |
| 26 | `notion_sandbox.py:659` | flip | KILLED | 11 | `test_interrupt_after_store_records_the_created_id[0-exc0]` | `bind is None` |
| 27 | `notion_sandbox.py:665` | flip | KILLED | 34 | `test_execute_on_the_fake_adapter_writes_evidence` | `type(bot.user_id) is str` |
| 28 | `notion_sandbox.py:705` | flip | KILLED | 9 | `test_token_in_error_is_redacted` | `error is not None` |
| 29 | `notion_sandbox.py:707` | flip | KILLED | 17 | `test_execute_on_the_fake_adapter_writes_evidence` | `any(stage.get("status") == "INTERRUPTED" for stage in stages)` |
| 30 | `notion_sandbox.py:710` | flip | KILLED | 119 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `check == "FAIL"` |
| 31 | `notion_sandbox.py:712` | flip | KILLED | 111 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `code == EXIT_OK` |
| 32 | `notion_sandbox.py:755` | flip | KILLED | 34 | `test_override_env_refuses[-NOTION_CONFIG]` | `path is not None and str(path) != "" and not leaks(str(path), token)` |
| 33 | `notion_sandbox.py:762` | flip | KILLED | 1 | `(collection error)` | `__name__ == "__main__"` |
| 34 | `notion_sandbox_guard.py:144` | flip | KILLED | 78 | `test_canonical_id_normalizes_and_rejects` | `type(value) is not str` |
| 35 | `notion_sandbox_guard.py:147` | flip | KILLED | 78 | `test_canonical_id_normalizes_and_rejects` | `len(compact) != 32` |
| 36 | `notion_sandbox_guard.py:149` | flip | KILLED | 78 | `test_canonical_id_normalizes_and_rejects` | `any(character not in "0123456789abcdef" for character in compact)` |
| 37 | `notion_sandbox_guard.py:156` | flip | KILLED | 47 | `test_target_and_parent_guards` | `type(bot.user_type) is not str or bot.user_type != "bot"` |
| 38 | `notion_sandbox_guard.py:158` | flip | KILLED | 52 | `test_target_and_parent_guards` | `page.archived or page.parent_type in {"database_id", "data_source_id"}` |
| 39 | `notion_sandbox_guard.py:160` | flip | KILLED | 47 | `test_target_and_parent_guards` | `canonical_id(bot.space_id) != SANDBOX_SPACE_ID` |
| 40 | `notion_sandbox_guard.py:162` | flip | KILLED | 46 | `test_target_and_parent_guards` | `canonical_id(page.page_id) != SANDBOX_PARENT_PAGE_ID` |
| 41 | `notion_sandbox_guard.py:170` | flip | KILLED | 58 | `test_target_and_parent_guards` | `candidate == ""` |
| 42 | `notion_sandbox_guard.py:178` | flip | KILLED | 70 | `test_token_env_and_redaction_units` | `type(value) is not str or value == ""` |
| 43 | `notion_sandbox_guard.py:203` | flip | KILLED | 82 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `head in _OVERRIDE_FLAGS` |
| 44 | `notion_sandbox_guard.py:205` | flip | KILLED | 71 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `contains_secret_shape(arg)` |
| 45 | `notion_sandbox_guard.py:217` | flip | KILLED | 137 | `test_token_env_and_redaction_units` | `token is None or not token_shape_ok(token)` |
| 46 | `notion_sandbox_guard.py:222` | flip | KILLED | 3 | `test_token_env_and_redaction_units` | `encoded != token` |
| 47 | `notion_sandbox_guard.py:224` | flip | KILLED | 4 | `test_token_env_and_redaction_units` | `digest not in forms and digest != token` |
| 48 | `notion_sandbox_guard.py:232` | flip | KILLED | 137 | `test_token_env_and_redaction_units` | `token is not None and token != "" and not _unsafe_exact(token) and token in cleaned` |
| 49 | `notion_sandbox_guard.py:234` | flip | KILLED | 137 | `test_token_env_and_redaction_units` | `token is not None and token != "" and not _unsafe_exact(token)` |
| 50 | `notion_sandbox_guard.py:237` | flip | KILLED | 2 | `test_token_env_and_redaction_units` | `form in cleaned` |
| 51 | `notion_sandbox_guard.py:243` | flip | KILLED | 1 | `timeout` | `folded == ""` |
| 52 | `notion_sandbox_guard.py:250` | flip | KILLED | 1 | `test_token_env_and_redaction_units` | `found < 0` |
| 53 | `notion_sandbox_guard.py:260` | flip | KILLED | 25 | `test_target_and_parent_guards` | `runner_name is None` |
| 54 | `notion_sandbox_guard.py:262` | flip | KILLED | 24 | `test_target_and_parent_guards` | `outcome == "PASS"` |
| 55 | `notion_sandbox_guard.py:264` | flip | KILLED | 9 | `test_target_and_parent_guards` | `outcome == "FAILED"` |
| 56 | `notion_sandbox_guard.py:266` | flip | KILLED | 3 | `test_target_and_parent_guards` | `outcome == "BLOCKED"` |
| 57 | `notion_sandbox_guard.py:281` | flip | KILLED | 1 | `test_token_env_and_redaction_units` | `stage.get("name") == "qa" and type(found) is str` |
| 58 | `notion_sandbox_guard.py:283` | flip | KILLED | 6 | `test_token_env_and_redaction_units` | `status == "PASS"` |
| 59 | `notion_sandbox_guard.py:285` | flip | KILLED | 6 | `test_token_env_and_redaction_units` | `status == "FAILED"` |
| 60 | `notion_sandbox_guard.py:287` | flip | KILLED | 6 | `test_token_env_and_redaction_units` | `status == "BLOCKED"` |
| 61 | `notion_sandbox_guard.py:302` | flip | KILLED | 2 | `test_token_env_and_redaction_units` | `len(compact) < 32` |
| 62 | `notion_sandbox_guard.py:304` | flip | KILLED | 2 | `test_token_env_and_redaction_units` | `any(character not in "0123456789abcdefABCDEF" for character in compact)` |
| 63 | `notion_sandbox_guard.py:311` | flip | KILLED | 15 | `test_token_env_and_redaction_units` | `token is not None and token != "" and not _unsafe_exact(token)` |
| 64 | `notion_sandbox_guard.py:312` | flip | KILLED | 128 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `token in text` |
| 65 | `notion_sandbox_guard.py:315` | flip | KILLED | 129 | `test_token_env_and_redaction_units` | `folded != "" and folded in text.lower().replace("-", "")` |
| 66 | `notion_sandbox_guard.py:317` | flip | KILLED | 135 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `any(form in text for form in _encoded_forms(token))` |
| 67 | `notion_sandbox_guard.py:332` | flip | KILLED | 123 | `test_write_evidence_redacts_a_planted_token` | `leaks(text, token)` |
| 68 | `notion_sandbox_guard.py:336` | flip | KILLED | 3 | `test_failed_redaction_exits_70` | `leaks(text, token)` |
| 69 | `notion_sandbox_guard.py:355` | flip | KILLED | 130 | `test_write_evidence_redacts_a_planted_token` | `str(path) == "" or path == Path() or under_proc(path)` |
| 70 | `notion_sandbox_guard.py:363` | flip | KILLED | 132 | `test_write_evidence_redacts_a_planted_token` | `info is not None` |
| 71 | `notion_sandbox_guard.py:370` | flip | KILLED | 131 | `test_write_evidence_redacts_a_planted_token` | `stat.S_ISLNK(parent_info.st_mode) or not stat.S_ISDIR(parent_info.st_mode)` |
| 72 | `notion_sandbox_guard.py:372` | flip | KILLED | 134 | `test_write_evidence_redacts_a_planted_token` | `parent_info.st_mode & 0o200 == 0` |
| 73 | `notion_sandbox_guard.py:387` | flip | KILLED | 6 | `test_enospc_after_creates_prints_ids` | `type(found) is not list` |
| 74 | `notion_sandbox_guard.py:391` | flip | KILLED | 2 | `test_enospc_after_creates_prints_ids` | `type(item) is not dict` |
| 75 | `notion_sandbox_guard.py:394` | flip | KILLED | 2 | `test_enospc_after_creates_prints_ids` | `type(page_id) is str and page_id != ""` |
| 76 | `notion_sandbox_guard.py:403` | flip | KILLED | 1 | `timeout` | `written <= 0 or written > len(pending)` |
| 77 | `notion_sandbox_guard.py:436` | flip | KILLED | 131 | `test_write_evidence_redacts_a_planted_token` | `stat.S_IMODE(opened.st_mode) != 0o600` |
| 78 | `notion_sandbox_guard.py:443` | flip | KILLED | 124 | `test_write_evidence_redacts_a_planted_token` | `_destination_appeared(path)` |
| 79 | `notion_sandbox_guard.py:449` | flip | KILLED | 123 | `test_write_evidence_redacts_a_planted_token` | `stat.S_ISLNK(current.st_mode) or current.st_size != len(encoded)` |
| 80 | `notion_sandbox_guard.py:458` | flip | KILLED | 4 | `test_evidence_write_oserror_is_redacted` | `exc.errno in _DISK_ERRNO` |
| 81 | `notion_sandbox_guard.py:462` | flip | KILLED | 1 | `test_disk_error_closes_standard_input` | `tmp_fd >= 0` |
| 82 | `notion_sandbox_guard.py:505` | flip | KILLED | 145 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `(candidate / "pyproject.toml").is_file() and (candidate / "docs" / "control").is_dir()` |
| 83 | `notion_sandbox_guard.py:509` | flip | KILLED | 4 | `test_repo_root_falls_back_to_cwd` | `(candidate / "pyproject.toml").is_file() and (candidate / "docs" / "control").is_dir()` |
| 84 | `notion_sandbox_guard.py:527` | flip | KILLED | 137 | `test_git_sha_rejects_a_bad_rev_parse` | `completed.returncode != 0 or len(sha) != 40` |
| 85 | `notion_sandbox_guard.py:529` | flip | KILLED | 136 | `test_git_sha_rejects_a_bad_rev_parse` | `any(character not in "0123456789abcdef" for character in sha)` |
| 86 | `notion_sandbox_guard.py:541` | flip | KILLED | 134 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `type(payload) is not dict` |
| 87 | `notion_sandbox_guard.py:546` | flip | KILLED | 134 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `type(revision) is not int or type(session) is not int or type(head) is not str` |
| 88 | `notion_sandbox_live.py:75` | flip | KILLED | 2 | `test_ssl_env_is_refused_and_ignored` | `type(cafile) is str and cafile != ""` |
| 89 | `notion_sandbox_live.py:123` | flip | KILLED | 19 | `test_live_client_reads_without_writing_and_redacts` | `bot is None` |
| 90 | `notion_sandbox_live.py:130` | flip | KILLED | 19 | `test_live_client_reads_without_writing_and_redacts` | `expected == ""` |
| 91 | `notion_sandbox_live.py:135` | flip | KILLED | 18 | `test_live_client_reads_without_writing_and_redacts` | `page is None` |
| 92 | `notion_sandbox_live.py:142` | flip | KILLED | 11 | `test_live_client_reads_without_writing_and_redacts` | `not parent_is_allowed(parent, allowed)` |
| 93 | `notion_sandbox_live.py:153` | flip | KILLED | 11 | `test_live_child_page_does_not_count_its_own_write` | `type(sent_parent) is not dict or sent_parent.get("page_id") != parent or sent_parent.get("type") != "page_id"` |
| 94 | `notion_sandbox_live.py:161` | flip | KILLED | 10 | `test_live_child_page_does_not_count_its_own_write` | `page is None` |
| 95 | `notion_sandbox_live.py:169` | flip | KILLED | 7 | `test_doc_shaped_pages_execute_without_a_space` | `page_id == "" or space_conflicts(page.space_id)` |
| 96 | `notion_sandbox_live.py:171` | flip | KILLED | 5 | `test_doc_shaped_pages_execute_without_a_space` | `page_id not in self._created_ids` |
| 97 | `notion_sandbox_live.py:175` | flip | KILLED | 5 | `test_live_child_page_does_not_count_its_own_write` | `evidence_ids is None or evidence_rows is None or page_id in evidence_ids` |
| 98 | `notion_sandbox_live.py:184` | flip | KILLED | 25 | `test_live_client_reads_without_writing_and_redacts` | `leaks(url, self._token) or leaks(url.replace("-", ""), self._token)` |
| 99 | `notion_sandbox_live.py:190` | flip | KILLED | 2 | `test_live_client_reads_without_writing_and_redacts` | `body is not None` |
| 100 | `notion_sandbox_live.py:195` | flip | KILLED | 2 | `test_redirect_is_not_followed` | `type(status) is not int` |
| 101 | `notion_sandbox_live.py:197` | flip | KILLED | 23 | `test_live_client_reads_without_writing_and_redacts` | `type(status) is int and 300 <= status < 400` |
| 102 | `notion_sandbox_live.py:206` | flip | KILLED | 22 | `test_live_client_reads_without_writing_and_redacts` | `type(raw) is not bytes` |
| 103 | `notion_sandbox_live.py:216` | flip | KILLED | 19 | `test_live_client_reads_without_writing_and_redacts` | `type(payload) is not dict` |
| 104 | `notion_sandbox_live.py:220` | flip | KILLED | 19 | `test_live_client_reads_without_writing_and_redacts` | `type(user_id) is not str or type(user_type) is not str` |
| 105 | `notion_sandbox_live.py:224` | flip | KILLED | 9 | `test_live_client_reads_without_writing_and_redacts` | `type(bot) is dict and type(bot.get("workspace_id")) is str` |
| 106 | `notion_sandbox_live.py:231` | flip | KILLED | 26 | `test_live_client_reads_without_writing_and_redacts` | `key not in payload` |
| 107 | `notion_sandbox_live.py:234` | flip | KILLED | 10 | `test_trashed_parent_writes_nothing[archived]` | `type(value) is not bool` |
| 108 | `notion_sandbox_live.py:241` | flip | KILLED | 27 | `test_live_client_reads_without_writing_and_redacts` | `type(payload) is not dict or payload.get("object") != "page"` |
| 109 | `notion_sandbox_live.py:244` | flip | KILLED | 27 | `test_live_client_reads_without_writing_and_redacts` | `page_id == ""` |
| 110 | `notion_sandbox_live.py:250` | flip | KILLED | 11 | `test_live_child_page_does_not_count_its_own_write` | `type(parent) is dict` |
| 111 | `notion_sandbox_live.py:251` | flip | KILLED | 3 | `test_live_space_fallback_is_only_the_asserted_parent` | `space == ""` |
| 112 | `notion_sandbox_live.py:254` | flip | KILLED | 4 | `test_database_id_parent_is_not_a_page_parent` | `type(found_type) is str` |
| 113 | `notion_sandbox_live.py:256` | flip | KILLED | 7 | `test_live_child_page_does_not_count_its_own_write` | `found_type == "page_id"` |
| 114 | `notion_sandbox_live.py:258` | flip | KILLED | 11 | `test_live_client_reads_without_writing_and_redacts` | `space == "" and page_id == canonical_id(expected_id)` |
| 115 | `notion_sandbox_live.py:261` | flip | KILLED | 1 | `test_parse_page_keeps_a_url_and_fills_a_blank_one` | `type(url) is not str or url == ""` |
| 116 | `notion_sandbox_live.py:266` | flip | KILLED | 27 | `test_live_client_reads_without_writing_and_redacts` | `archived_flag is None or alias_flag is None or trash_flag is None` |
| 117 | `notion_sandbox_live.py:283` | flip | KILLED | 25 | `test_live_client_reads_without_writing_and_redacts` | `type(value) is not str or value == ""` |
| 118 | `notion_sandbox_live.py:289` | flip | KILLED | 6 | `test_doc_shaped_pages_execute_without_a_space` | `parsed.tzinfo is None` |
| 119 | `notion_sandbox_live.py:296` | flip | KILLED | 24 | `test_live_client_reads_without_writing_and_redacts` | `type(actor) is not dict` |
| 120 | `notion_sandbox_live.py:299` | flip | KILLED | 6 | `test_doc_shaped_pages_execute_without_a_space` | `type(found) is not str` |
| 121 | `notion_sandbox_live.py:307` | flip | KILLED | 3 | `test_proxy_map_reads_string_proxy_entries` | `type(handlers) is not list` |
| 122 | `notion_sandbox_live.py:310` | flip | KILLED | 3 | `test_proxy_map_reads_string_proxy_entries` | `isinstance(handler, urllib.request.ProxyHandler)` |
| 123 | `notion_sandbox_live.py:312` | flip | KILLED | 3 | `test_proxy_map_reads_string_proxy_entries` | `type(found) is not dict` |
| 124 | `notion_sandbox_live.py:315` | flip | KILLED | 2 | `test_proxy_map_reads_string_proxy_entries` | `type(key) is str and type(value) is str` |
| 125 | `notion_sandbox_live.py:324` | flip | KILLED | 4 | `test_live_space_fallback_is_only_the_asserted_parent` | `type(value) is str and canonical_id(value) != ""` |
| 126 | `notion_sandbox_pipeline.py:144` | flip | KILLED | 1 | `timeout` | `page_id not in ctx.created_ids` |
| 127 | `notion_sandbox_pipeline.py:146` | flip | KILLED | 1 | `timeout` | `ctx.created_ids.index(page_id) < before` |
| 128 | `notion_sandbox_pipeline.py:153` | flip | KILLED | 1 | `timeout` | `page_id == "" or page_id not in ctx.created_ids` |
| 129 | `notion_sandbox_pipeline.py:160` | flip | KILLED | 9 | `test_wrong_space_on_create_return_stops` | `page_id == ""` |
| 130 | `notion_sandbox_pipeline.py:163` | flip | KILLED | 3 | `test_wrong_space_on_create_return_stops` | `row.get("id") == page_id and row.get("reason") == reason` |
| 131 | `notion_sandbox_pipeline.py:169` | flip | KILLED | 31 | `test_execute_on_the_fake_adapter_writes_evidence` | `page_id == "" or page_id in ctx.created_ids` |
| 132 | `notion_sandbox_pipeline.py:178` | flip | KILLED | 3 | `test_unfresh_page_is_removed_from_the_recorded_ids` | `page_id in ctx.created_ids` |
| 133 | `notion_sandbox_pipeline.py:181` | flip | KILLED | 6 | `test_stale_foreign_page_is_not_a_parent` | `page_id != "" and all(row.get("id") != page_id for row in ctx.rejected_pages)` |
| 134 | `notion_sandbox_pipeline.py:200` | flip | KILLED | 5 | `test_lying_create_id_stops_before_colours` | `tail == page_id` |
| 135 | `notion_sandbox_pipeline.py:203` | flip | KILLED | 7 | `test_lying_create_id_stops_before_colours` | `page_id == "" or space_conflicts(page.space_id)` |
| 136 | `notion_sandbox_pipeline.py:204` | flip | KILLED | 3 | `test_wrong_space_on_create_return_stops` | `page_id in ctx.created_ids[:before]` |
| 137 | `notion_sandbox_pipeline.py:207` | flip | KILLED | 1 | `test_unbound_foreign_create_is_kept_and_flagged` | `space_conflicts(page.space_id) and page_id != ""` |
| 138 | `notion_sandbox_pipeline.py:216` | flip | KILLED | 35 | `test_execute_on_the_fake_adapter_writes_evidence` | `page.created_by != ctx.bot_user_id` |
| 139 | `notion_sandbox_pipeline.py:219` | flip | KILLED | 35 | `test_execute_on_the_fake_adapter_writes_evidence` | `moment is None` |
| 140 | `notion_sandbox_pipeline.py:221` | flip | KILLED | 35 | `test_execute_on_the_fake_adapter_writes_evidence` | `moment.tzinfo is None` |
| 141 | `notion_sandbox_pipeline.py:223` | flip | KILLED | 34 | `test_execute_on_the_fake_adapter_writes_evidence` | `moment < _earliest(ctx.moment)` |
| 142 | `notion_sandbox_pipeline.py:233` | flip | KILLED | 6 | `test_broken_ancestor_stops_later_writes` | `page_id == SANDBOX_PARENT_PAGE_ID` |
| 143 | `notion_sandbox_pipeline.py:234` | flip | KILLED | 27 | `test_execute_on_the_fake_adapter_writes_evidence` | `space_conflicts(current.space_id) or current.archived` |
| 144 | `notion_sandbox_pipeline.py:239` | flip | KILLED | 30 | `test_execute_on_the_fake_adapter_writes_evidence` | `parent_id == "" or page_id == "" or page_id in seen` |
| 145 | `notion_sandbox_pipeline.py:243` | flip | KILLED | 28 | `test_execute_on_the_fake_adapter_writes_evidence` | `canonical_id(current.page_id) != parent_id` |
| 146 | `notion_sandbox_pipeline.py:246` | flip | KILLED | 26 | `test_execute_on_the_fake_adapter_writes_evidence` | `space_conflicts(current.space_id) or current.archived` |
| 147 | `notion_sandbox_pipeline.py:255` | flip | KILLED | 54 | `test_create_under_refuses_a_foreign_parent` | `not parent_is_allowed(requested, allowed)` |
| 148 | `notion_sandbox_pipeline.py:257` | flip | KILLED | 53 | `test_execute_on_the_fake_adapter_writes_evidence` | `canonical_id(ctx.bot_space_id) != SANDBOX_SPACE_ID` |
| 149 | `notion_sandbox_pipeline.py:272` | flip | KILLED | 41 | `test_execute_on_the_fake_adapter_writes_evidence` | `page_id in {"", SANDBOX_PARENT_PAGE_ID, requested}` |
| 150 | `notion_sandbox_pipeline.py:273` | flip | KILLED | 2 | `test_create_that_returns_the_parent_id_is_not_new` | `page_id not in {"", SANDBOX_PARENT_PAGE_ID}` |
| 151 | `notion_sandbox_pipeline.py:278` | flip | KILLED | 36 | `test_execute_on_the_fake_adapter_writes_evidence` | `page_id in ctx.created_ids[:before]` |
| 152 | `notion_sandbox_pipeline.py:280` | flip | KILLED | 37 | `test_execute_on_the_fake_adapter_writes_evidence` | `space_conflicts(page.space_id)` |
| 153 | `notion_sandbox_pipeline.py:283` | flip | KILLED | 38 | `test_execute_on_the_fake_adapter_writes_evidence` | `canonical_id(page.parent_id) != requested` |
| 154 | `notion_sandbox_pipeline.py:287` | flip | KILLED | 32 | `test_execute_on_the_fake_adapter_writes_evidence` | `canonical_id(confirmed.page_id) != page_id` |
| 155 | `notion_sandbox_pipeline.py:289` | flip | KILLED | 31 | `test_execute_on_the_fake_adapter_writes_evidence` | `canonical_id(confirmed.parent_id) != requested` |
| 156 | `notion_sandbox_pipeline.py:291` | flip | KILLED | 31 | `test_execute_on_the_fake_adapter_writes_evidence` | `space_conflicts(confirmed.space_id) or confirmed.archived` |
| 157 | `notion_sandbox_pipeline.py:297` | flip | KILLED | 2 | `test_token_in_created_url_exits_70` | `ctx.created and ctx.created[-1].get("id") == page_id` |
| 158 | `notion_sandbox_pipeline.py:319` | flip | KILLED | 40 | `test_execute_on_the_fake_adapter_writes_evidence` | `type(spec) is not ProductSpec` |
| 159 | `notion_sandbox_pipeline.py:327` | flip | KILLED | 25 | `test_execute_on_the_fake_adapter_writes_evidence` | `ctx.probe is None or ctx.product_page_id is None or type(spec) is not ProductSpec` |

## Force-true

| # | Site | Mode | Result | Failed | Test | Condition |
|---|---|---|---|---|---|---|
| 1 | `notion_sandbox.py:119` | true | KILLED | 3 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `runner_name is None` |
| 2 | `notion_sandbox.py:142` | true | KILLED | 1 | `test_read_base_exceptions_stay_redacted` | `available and not marked` |
| 3 | `notion_sandbox.py:164` | true | KILLED | 42 | `test_execute_on_the_fake_adapter_writes_evidence` | `not available or failed` |
| 4 | `notion_sandbox.py:168` | true | KILLED | 41 | `test_execute_on_the_fake_adapter_writes_evidence` | `runner is None` |
| 5 | `notion_sandbox.py:205` | true | KILLED | 3 | `test_evidence_out_equals_matches_the_space_form` | `arg == "--evidence-out" and index + 1 < len(argv)` |
| 6 | `notion_sandbox.py:207` | true | KILLED | 2 | `test_abbreviations_are_refused` | `arg.startswith("--evidence-out=")` |
| 7 | `notion_sandbox.py:214` | true | KILLED | 7 | `test_interrupt_writes_redacted_evidence` | `not ids` |
| 8 | `notion_sandbox.py:236` | true | KILLED | 139 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `type(moment) is not datetime or moment.tzinfo is None` |
| 9 | `notion_sandbox.py:242` | true | KILLED | 3 | `test_short_token_is_refused` | `token is not None and token_shape_ok(token)` |
| 10 | `notion_sandbox.py:347` | true | KILLED | 1 | `timeout` | `current not in (signal.SIG_DFL, signal.default_int_handler)` |
| 11 | `notion_sandbox.py:357` | true | KILLED | 2 | `test_interrupt_after_the_evidence_link_leaves_that_file` | `stat.S_ISLNK(info.st_mode) or info.st_size <= 0` |
| 12 | `notion_sandbox.py:393` | true | KILLED | 5 | `test_interrupt_does_not_keep_a_symlink` | `path is None or held.started is None or not held.ready` |
| 13 | `notion_sandbox.py:395` | true | KILLED | 5 | `test_interrupt_does_not_keep_a_symlink` | `_evidence_is_complete(path)` |
| 14 | `notion_sandbox.py:398` | true | KILLED | 1 | `test_real_sigint_preserves_a_passing_stage` | `not any(stage.get("status") == "INTERRUPTED" for stage in stages)` |
| 15 | `notion_sandbox.py:421` | true | KILLED | 1 | `test_second_interrupt_retries_until_a_file_exists` | `_evidence_is_complete(path)` |
| 16 | `notion_sandbox.py:461` | true | KILLED | 71 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `argv_names_a_target(arguments) or environ_names_a_target(env) or cert_env_set(env)` |
| 17 | `notion_sandbox.py:468` | true | KILLED | 91 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `str(evidence) == "" or leaks(str(evidence), secret)` |
| 18 | `notion_sandbox.py:472` | true | KILLED | 71 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `parsed.execute and parsed.dry_run` |
| 19 | `notion_sandbox.py:478` | true | KILLED | 68 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `token is None` |
| 20 | `notion_sandbox.py:489` | true | KILLED | 65 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `secret is None` |
| 21 | `notion_sandbox.py:541` | true | KILLED | 58 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `type(bot.user_type) is not str` |
| 22 | `notion_sandbox.py:558` | true | KILLED | 45 | `test_dry_run_is_the_default_and_writes_nothing` | `not target_ok(bot, page)` |
| 23 | `notion_sandbox.py:575` | true | KILLED | 38 | `test_execute_on_the_fake_adapter_writes_evidence` | `mode == "dry-run"` |
| 24 | `notion_sandbox.py:621` | true | KILLED | 26 | `test_execute_on_the_fake_adapter_writes_evidence` | `interrupted` |
| 25 | `notion_sandbox.py:625` | true | KILLED | 7 | `test_execute_on_the_fake_adapter_writes_evidence` | `failed` |
| 26 | `notion_sandbox.py:659` | true | KILLED | 10 | `test_interrupt_after_store_records_the_created_id[0-exc0]` | `bind is None` |
| 27 | `notion_sandbox.py:665` | true | KILLED | 1 | `test_non_string_bot_user_id_is_omitted` | `type(bot.user_id) is str` |
| 28 | `notion_sandbox.py:705` | true | KILLED | 5 | `test_execute_on_the_fake_adapter_writes_evidence` | `error is not None` |
| 29 | `notion_sandbox.py:707` | true | KILLED | 3 | `test_execute_on_the_fake_adapter_writes_evidence` | `any(stage.get("status") == "INTERRUPTED" for stage in stages)` |
| 30 | `notion_sandbox.py:710` | true | KILLED | 116 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `check == "FAIL"` |
| 31 | `notion_sandbox.py:712` | true | KILLED | 101 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `code == EXIT_OK` |
| 32 | `notion_sandbox.py:755` | true | KILLED | 1 | `test_both_flags_and_secret_evidence_path_refuse` | `path is not None and str(path) != "" and not leaks(str(path), token)` |
| 33 | `notion_sandbox.py:762` | true | KILLED | 1 | `(collection error)` | `__name__ == "__main__"` |
| 34 | `notion_sandbox_guard.py:144` | true | KILLED | 78 | `test_canonical_id_normalizes_and_rejects` | `type(value) is not str` |
| 35 | `notion_sandbox_guard.py:147` | true | KILLED | 78 | `test_canonical_id_normalizes_and_rejects` | `len(compact) != 32` |
| 36 | `notion_sandbox_guard.py:149` | true | KILLED | 78 | `test_canonical_id_normalizes_and_rejects` | `any(character not in "0123456789abcdef" for character in compact)` |
| 37 | `notion_sandbox_guard.py:156` | true | KILLED | 46 | `test_target_and_parent_guards` | `type(bot.user_type) is not str or bot.user_type != "bot"` |
| 38 | `notion_sandbox_guard.py:158` | true | KILLED | 46 | `test_target_and_parent_guards` | `page.archived or page.parent_type in {"database_id", "data_source_id"}` |
| 39 | `notion_sandbox_guard.py:160` | true | KILLED | 46 | `test_target_and_parent_guards` | `canonical_id(bot.space_id) != SANDBOX_SPACE_ID` |
| 40 | `notion_sandbox_guard.py:162` | true | KILLED | 46 | `test_target_and_parent_guards` | `canonical_id(page.page_id) != SANDBOX_PARENT_PAGE_ID` |
| 41 | `notion_sandbox_guard.py:170` | true | KILLED | 58 | `test_target_and_parent_guards` | `candidate == ""` |
| 42 | `notion_sandbox_guard.py:178` | true | KILLED | 70 | `test_token_env_and_redaction_units` | `type(value) is not str or value == ""` |
| 43 | `notion_sandbox_guard.py:203` | true | KILLED | 71 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `head in _OVERRIDE_FLAGS` |
| 44 | `notion_sandbox_guard.py:205` | true | KILLED | 71 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `contains_secret_shape(arg)` |
| 45 | `notion_sandbox_guard.py:217` | true | KILLED | 4 | `test_token_env_and_redaction_units` | `token is None or not token_shape_ok(token)` |
| 46 | `notion_sandbox_guard.py:222` | true | EQUIVALENT | 0 |  | `encoded != token` |
| 47 | `notion_sandbox_guard.py:224` | true | EQUIVALENT | 0 |  | `digest not in forms and digest != token` |
| 48 | `notion_sandbox_guard.py:232` | true | KILLED | 137 | `test_token_env_and_redaction_units` | `token is not None and token != "" and not _unsafe_exact(token) and token in cleaned` |
| 49 | `notion_sandbox_guard.py:234` | true | KILLED | 137 | `test_token_env_and_redaction_units` | `token is not None and token != "" and not _unsafe_exact(token)` |
| 50 | `notion_sandbox_guard.py:237` | true | EQUIVALENT | 0 |  | `form in cleaned` |
| 51 | `notion_sandbox_guard.py:243` | true | KILLED | 1 | `test_token_env_and_redaction_units` | `folded == ""` |
| 52 | `notion_sandbox_guard.py:250` | true | KILLED | 1 | `test_token_env_and_redaction_units` | `found < 0` |
| 53 | `notion_sandbox_guard.py:260` | true | KILLED | 23 | `test_target_and_parent_guards` | `runner_name is None` |
| 54 | `notion_sandbox_guard.py:262` | true | KILLED | 21 | `test_target_and_parent_guards` | `outcome == "PASS"` |
| 55 | `notion_sandbox_guard.py:264` | true | KILLED | 3 | `test_target_and_parent_guards` | `outcome == "FAILED"` |
| 56 | `notion_sandbox_guard.py:266` | true | KILLED | 2 | `test_dry_run_is_the_default_and_writes_nothing` | `outcome == "BLOCKED"` |
| 57 | `notion_sandbox_guard.py:281` | true | KILLED | 1 | `test_token_env_and_redaction_units` | `stage.get("name") == "qa" and type(found) is str` |
| 58 | `notion_sandbox_guard.py:283` | true | KILLED | 6 | `test_token_env_and_redaction_units` | `status == "PASS"` |
| 59 | `notion_sandbox_guard.py:285` | true | KILLED | 6 | `test_token_env_and_redaction_units` | `status == "FAILED"` |
| 60 | `notion_sandbox_guard.py:287` | true | KILLED | 6 | `test_token_env_and_redaction_units` | `status == "BLOCKED"` |
| 61 | `notion_sandbox_guard.py:302` | true | KILLED | 1 | `test_token_env_and_redaction_units` | `len(compact) < 32` |
| 62 | `notion_sandbox_guard.py:304` | true | KILLED | 1 | `test_token_env_and_redaction_units` | `any(character not in "0123456789abcdefABCDEF" for character in compact)` |
| 63 | `notion_sandbox_guard.py:311` | true | KILLED | 11 | `test_short_token_is_refused` | `token is not None and token != "" and not _unsafe_exact(token)` |
| 64 | `notion_sandbox_guard.py:312` | true | KILLED | 128 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `token in text` |
| 65 | `notion_sandbox_guard.py:315` | true | KILLED | 128 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `folded != "" and folded in text.lower().replace("-", "")` |
| 66 | `notion_sandbox_guard.py:317` | true | KILLED | 134 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `any(form in text for form in _encoded_forms(token))` |
| 67 | `notion_sandbox_guard.py:332` | true | KILLED | 117 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `leaks(text, token)` |
| 68 | `notion_sandbox_guard.py:336` | true | KILLED | 1 | `test_failed_redaction_exits_70` | `leaks(text, token)` |
| 69 | `notion_sandbox_guard.py:355` | true | KILLED | 130 | `test_write_evidence_redacts_a_planted_token` | `str(path) == "" or path == Path() or under_proc(path)` |
| 70 | `notion_sandbox_guard.py:363` | true | KILLED | 130 | `test_write_evidence_redacts_a_planted_token` | `info is not None` |
| 71 | `notion_sandbox_guard.py:370` | true | KILLED | 130 | `test_write_evidence_redacts_a_planted_token` | `stat.S_ISLNK(parent_info.st_mode) or not stat.S_ISDIR(parent_info.st_mode)` |
| 72 | `notion_sandbox_guard.py:372` | true | KILLED | 130 | `test_write_evidence_redacts_a_planted_token` | `parent_info.st_mode & 0o200 == 0` |
| 73 | `notion_sandbox_guard.py:387` | true | KILLED | 1 | `test_enospc_after_creates_prints_ids` | `type(found) is not list` |
| 74 | `notion_sandbox_guard.py:391` | true | KILLED | 1 | `test_enospc_after_creates_prints_ids` | `type(item) is not dict` |
| 75 | `notion_sandbox_guard.py:394` | true | KILLED | 1 | `test_enospc_ignores_pages_that_are_not_ids` | `type(page_id) is str and page_id != ""` |
| 76 | `notion_sandbox_guard.py:403` | true | KILLED | 126 | `test_write_evidence_redacts_a_planted_token` | `written <= 0 or written > len(pending)` |
| 77 | `notion_sandbox_guard.py:436` | true | KILLED | 130 | `test_write_evidence_redacts_a_planted_token` | `stat.S_IMODE(opened.st_mode) != 0o600` |
| 78 | `notion_sandbox_guard.py:443` | true | KILLED | 122 | `test_write_evidence_redacts_a_planted_token` | `_destination_appeared(path)` |
| 79 | `notion_sandbox_guard.py:449` | true | KILLED | 121 | `test_write_evidence_redacts_a_planted_token` | `stat.S_ISLNK(current.st_mode) or current.st_size != len(encoded)` |
| 80 | `notion_sandbox_guard.py:458` | true | KILLED | 2 | `test_evidence_write_oserror_is_redacted` | `exc.errno in _DISK_ERRNO` |
| 81 | `notion_sandbox_guard.py:462` | true | EQUIVALENT | 0 |  | `tmp_fd >= 0` |
| 82 | `notion_sandbox_guard.py:505` | true | KILLED | 145 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `(candidate / "pyproject.toml").is_file() and (candidate / "docs" / "control").is_dir()` |
| 83 | `notion_sandbox_guard.py:509` | true | KILLED | 3 | `test_repo_root_outside_the_checkout_still_uses_the_repo` | `(candidate / "pyproject.toml").is_file() and (candidate / "docs" / "control").is_dir()` |
| 84 | `notion_sandbox_guard.py:527` | true | KILLED | 135 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `completed.returncode != 0 or len(sha) != 40` |
| 85 | `notion_sandbox_guard.py:529` | true | KILLED | 135 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `any(character not in "0123456789abcdef" for character in sha)` |
| 86 | `notion_sandbox_guard.py:541` | true | KILLED | 133 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `type(payload) is not dict` |
| 87 | `notion_sandbox_guard.py:546` | true | KILLED | 133 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `type(revision) is not int or type(session) is not int or type(head) is not str` |
| 88 | `notion_sandbox_live.py:75` | true | KILLED | 1 | `test_absent_cafile_skips_load` | `type(cafile) is str and cafile != ""` |
| 89 | `notion_sandbox_live.py:123` | true | KILLED | 18 | `test_live_client_reads_without_writing_and_redacts` | `bot is None` |
| 90 | `notion_sandbox_live.py:130` | true | KILLED | 18 | `test_live_client_reads_without_writing_and_redacts` | `expected == ""` |
| 91 | `notion_sandbox_live.py:135` | true | KILLED | 16 | `test_live_client_reads_without_writing_and_redacts` | `page is None` |
| 92 | `notion_sandbox_live.py:142` | true | KILLED | 10 | `test_live_child_page_does_not_count_its_own_write` | `not parent_is_allowed(parent, allowed)` |
| 93 | `notion_sandbox_live.py:153` | true | KILLED | 10 | `test_live_child_page_does_not_count_its_own_write` | `type(sent_parent) is not dict or sent_parent.get("page_id") != parent or sent_parent.get("type") != "page_id"` |
| 94 | `notion_sandbox_live.py:161` | true | KILLED | 9 | `test_live_child_page_does_not_count_its_own_write` | `page is None` |
| 95 | `notion_sandbox_live.py:169` | true | KILLED | 6 | `test_doc_shaped_pages_execute_without_a_space` | `page_id == "" or space_conflicts(page.space_id)` |
| 96 | `notion_sandbox_live.py:171` | true | KILLED | 1 | `test_publish_does_not_repeat_an_id` | `page_id not in self._created_ids` |
| 97 | `notion_sandbox_live.py:175` | true | KILLED | 3 | `test_doc_shaped_interrupt_after_store_records_the_created_id[0-exc0]` | `evidence_ids is None or evidence_rows is None or page_id in evidence_ids` |
| 98 | `notion_sandbox_live.py:184` | true | KILLED | 23 | `test_live_client_reads_without_writing_and_redacts` | `leaks(url, self._token) or leaks(url.replace("-", ""), self._token)` |
| 99 | `notion_sandbox_live.py:190` | true | KILLED | 1 | `test_live_client_reads_without_writing_and_redacts` | `body is not None` |
| 100 | `notion_sandbox_live.py:195` | true | KILLED | 1 | `test_redirect_is_not_followed` | `type(status) is not int` |
| 101 | `notion_sandbox_live.py:197` | true | KILLED | 21 | `test_live_client_reads_without_writing_and_redacts` | `type(status) is int and 300 <= status < 400` |
| 102 | `notion_sandbox_live.py:206` | true | KILLED | 21 | `test_live_client_reads_without_writing_and_redacts` | `type(raw) is not bytes` |
| 103 | `notion_sandbox_live.py:216` | true | KILLED | 18 | `test_live_client_reads_without_writing_and_redacts` | `type(payload) is not dict` |
| 104 | `notion_sandbox_live.py:220` | true | KILLED | 18 | `test_live_client_reads_without_writing_and_redacts` | `type(user_id) is not str or type(user_type) is not str` |
| 105 | `notion_sandbox_live.py:224` | true | KILLED | 2 | `test_missing_workspace_id_writes_nothing` | `type(bot) is dict and type(bot.get("workspace_id")) is str` |
| 106 | `notion_sandbox_live.py:231` | true | KILLED | 4 | `test_trashed_parent_writes_nothing[archived]` | `key not in payload` |
| 107 | `notion_sandbox_live.py:234` | true | KILLED | 9 | `test_trashed_parent_writes_nothing[archived]` | `type(value) is not bool` |
| 108 | `notion_sandbox_live.py:241` | true | KILLED | 26 | `test_live_client_reads_without_writing_and_redacts` | `type(payload) is not dict or payload.get("object") != "page"` |
| 109 | `notion_sandbox_live.py:244` | true | KILLED | 26 | `test_live_client_reads_without_writing_and_redacts` | `page_id == ""` |
| 110 | `notion_sandbox_live.py:250` | true | KILLED | 2 | `test_missing_parent_object_stays_a_page` | `type(parent) is dict` |
| 111 | `notion_sandbox_live.py:251` | true | KILLED | 2 | `test_live_space_fallback_is_only_the_asserted_parent` | `space == ""` |
| 112 | `notion_sandbox_live.py:254` | true | KILLED | 1 | `test_non_string_parent_type_is_ignored` | `type(found_type) is str` |
| 113 | `notion_sandbox_live.py:256` | true | KILLED | 2 | `test_non_string_parent_type_is_ignored` | `found_type == "page_id"` |
| 114 | `notion_sandbox_live.py:258` | true | KILLED | 4 | `test_live_space_fallback_is_only_the_asserted_parent` | `space == "" and page_id == canonical_id(expected_id)` |
| 115 | `notion_sandbox_live.py:261` | true | KILLED | 1 | `test_parse_page_keeps_a_url_and_fills_a_blank_one` | `type(url) is not str or url == ""` |
| 116 | `notion_sandbox_live.py:266` | true | KILLED | 26 | `test_live_client_reads_without_writing_and_redacts` | `archived_flag is None or alias_flag is None or trash_flag is None` |
| 117 | `notion_sandbox_live.py:283` | true | KILLED | 5 | `test_doc_shaped_pages_execute_without_a_space` | `type(value) is not str or value == ""` |
| 118 | `notion_sandbox_live.py:289` | true | KILLED | 5 | `test_doc_shaped_pages_execute_without_a_space` | `parsed.tzinfo is None` |
| 119 | `notion_sandbox_live.py:296` | true | KILLED | 5 | `test_doc_shaped_pages_execute_without_a_space` | `type(actor) is not dict` |
| 120 | `notion_sandbox_live.py:299` | true | KILLED | 5 | `test_doc_shaped_pages_execute_without_a_space` | `type(found) is not str` |
| 121 | `notion_sandbox_live.py:307` | true | KILLED | 2 | `test_proxy_map_reads_string_proxy_entries` | `type(handlers) is not list` |
| 122 | `notion_sandbox_live.py:310` | true | KILLED | 1 | `test_proxy_map_ignores_handlers_that_are_not_proxies` | `isinstance(handler, urllib.request.ProxyHandler)` |
| 123 | `notion_sandbox_live.py:312` | true | KILLED | 2 | `test_proxy_map_reads_string_proxy_entries` | `type(found) is not dict` |
| 124 | `notion_sandbox_live.py:315` | true | KILLED | 1 | `test_proxy_map_drops_non_strings` | `type(key) is str and type(value) is str` |
| 125 | `notion_sandbox_live.py:324` | true | KILLED | 2 | `test_explicit_space_skips_a_non_id` | `type(value) is str and canonical_id(value) != ""` |
| 126 | `notion_sandbox_pipeline.py:144` | true | KILLED | 1 | `timeout` | `page_id not in ctx.created_ids` |
| 127 | `notion_sandbox_pipeline.py:146` | true | KILLED | 1 | `timeout` | `ctx.created_ids.index(page_id) < before` |
| 128 | `notion_sandbox_pipeline.py:153` | true | KILLED | 1 | `timeout` | `page_id == "" or page_id not in ctx.created_ids` |
| 129 | `notion_sandbox_pipeline.py:160` | true | KILLED | 8 | `test_wrong_space_on_create_return_stops` | `page_id == ""` |
| 130 | `notion_sandbox_pipeline.py:163` | true | KILLED | 1 | `test_each_foreign_page_is_flagged` | `row.get("id") == page_id and row.get("reason") == reason` |
| 131 | `notion_sandbox_pipeline.py:169` | true | KILLED | 6 | `test_lying_create_id_stops_before_colours` | `page_id == "" or page_id in ctx.created_ids` |
| 132 | `notion_sandbox_pipeline.py:178` | true | KILLED | 1 | `test_unfresh_reread_survives_a_missing_id` | `page_id in ctx.created_ids` |
| 133 | `notion_sandbox_pipeline.py:181` | true | KILLED | 1 | `test_the_same_unfresh_page_is_rejected_once` | `page_id != "" and all(row.get("id") != page_id for row in ctx.rejected_pages)` |
| 134 | `notion_sandbox_pipeline.py:200` | true | KILLED | 5 | `test_lying_create_id_stops_before_colours` | `tail == page_id` |
| 135 | `notion_sandbox_pipeline.py:203` | true | KILLED | 6 | `test_lying_create_id_stops_before_colours` | `page_id == "" or space_conflicts(page.space_id)` |
| 136 | `notion_sandbox_pipeline.py:204` | true | KILLED | 2 | `test_wrong_space_on_create_return_stops` | `page_id in ctx.created_ids[:before]` |
| 137 | `notion_sandbox_pipeline.py:207` | true | EQUIVALENT | 0 |  | `space_conflicts(page.space_id) and page_id != ""` |
| 138 | `notion_sandbox_pipeline.py:216` | true | KILLED | 34 | `test_execute_on_the_fake_adapter_writes_evidence` | `page.created_by != ctx.bot_user_id` |
| 139 | `notion_sandbox_pipeline.py:219` | true | KILLED | 34 | `test_execute_on_the_fake_adapter_writes_evidence` | `moment is None` |
| 140 | `notion_sandbox_pipeline.py:221` | true | KILLED | 34 | `test_execute_on_the_fake_adapter_writes_evidence` | `moment.tzinfo is None` |
| 141 | `notion_sandbox_pipeline.py:223` | true | KILLED | 34 | `test_execute_on_the_fake_adapter_writes_evidence` | `moment < _earliest(ctx.moment)` |
| 142 | `notion_sandbox_pipeline.py:233` | true | KILLED | 6 | `test_broken_ancestor_stops_later_writes` | `page_id == SANDBOX_PARENT_PAGE_ID` |
| 143 | `notion_sandbox_pipeline.py:234` | true | KILLED | 26 | `test_execute_on_the_fake_adapter_writes_evidence` | `space_conflicts(current.space_id) or current.archived` |
| 144 | `notion_sandbox_pipeline.py:239` | true | KILLED | 28 | `test_execute_on_the_fake_adapter_writes_evidence` | `parent_id == "" or page_id == "" or page_id in seen` |
| 145 | `notion_sandbox_pipeline.py:243` | true | KILLED | 27 | `test_execute_on_the_fake_adapter_writes_evidence` | `canonical_id(current.page_id) != parent_id` |
| 146 | `notion_sandbox_pipeline.py:246` | true | KILLED | 26 | `test_execute_on_the_fake_adapter_writes_evidence` | `space_conflicts(current.space_id) or current.archived` |
| 147 | `notion_sandbox_pipeline.py:255` | true | KILLED | 53 | `test_execute_on_the_fake_adapter_writes_evidence` | `not parent_is_allowed(requested, allowed)` |
| 148 | `notion_sandbox_pipeline.py:257` | true | KILLED | 52 | `test_execute_on_the_fake_adapter_writes_evidence` | `canonical_id(ctx.bot_space_id) != SANDBOX_SPACE_ID` |
| 149 | `notion_sandbox_pipeline.py:272` | true | KILLED | 39 | `test_execute_on_the_fake_adapter_writes_evidence` | `page_id in {"", SANDBOX_PARENT_PAGE_ID, requested}` |
| 150 | `notion_sandbox_pipeline.py:273` | true | KILLED | 1 | `test_create_that_returns_the_parent_id_is_not_new` | `page_id not in {"", SANDBOX_PARENT_PAGE_ID}` |
| 151 | `notion_sandbox_pipeline.py:278` | true | KILLED | 37 | `test_execute_on_the_fake_adapter_writes_evidence` | `page_id in ctx.created_ids[:before]` |
| 152 | `notion_sandbox_pipeline.py:280` | true | KILLED | 36 | `test_execute_on_the_fake_adapter_writes_evidence` | `space_conflicts(page.space_id)` |
| 153 | `notion_sandbox_pipeline.py:283` | true | KILLED | 37 | `test_execute_on_the_fake_adapter_writes_evidence` | `canonical_id(page.parent_id) != requested` |
| 154 | `notion_sandbox_pipeline.py:287` | true | KILLED | 31 | `test_execute_on_the_fake_adapter_writes_evidence` | `canonical_id(confirmed.page_id) != page_id` |
| 155 | `notion_sandbox_pipeline.py:289` | true | KILLED | 31 | `test_execute_on_the_fake_adapter_writes_evidence` | `canonical_id(confirmed.parent_id) != requested` |
| 156 | `notion_sandbox_pipeline.py:291` | true | KILLED | 29 | `test_execute_on_the_fake_adapter_writes_evidence` | `space_conflicts(confirmed.space_id) or confirmed.archived` |
| 157 | `notion_sandbox_pipeline.py:297` | true | KILLED | 1 | `test_confirm_does_not_replace_a_different_tail` | `ctx.created and ctx.created[-1].get("id") == page_id` |
| 158 | `notion_sandbox_pipeline.py:319` | true | KILLED | 40 | `test_execute_on_the_fake_adapter_writes_evidence` | `type(spec) is not ProductSpec` |
| 159 | `notion_sandbox_pipeline.py:327` | true | KILLED | 24 | `test_execute_on_the_fake_adapter_writes_evidence` | `ctx.probe is None or ctx.product_page_id is None or type(spec) is not ProductSpec` |

## Force-false

| # | Site | Mode | Result | Failed | Test | Condition |
|---|---|---|---|---|---|---|
| 1 | `notion_sandbox.py:119` | false | KILLED | 3 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `runner_name is None` |
| 2 | `notion_sandbox.py:142` | false | KILLED | 1 | `test_read_base_exceptions_stay_redacted` | `available and not marked` |
| 3 | `notion_sandbox.py:164` | false | KILLED | 1 | `test_absent_stage_failure_stays_not_run` | `not available or failed` |
| 4 | `notion_sandbox.py:168` | false | KILLED | 1 | `test_missing_stage_runner_is_not_a_failure` | `runner is None` |
| 5 | `notion_sandbox.py:205` | false | KILLED | 32 | `test_override_env_refuses[-NOTION_CONFIG]` | `arg == "--evidence-out" and index + 1 < len(argv)` |
| 6 | `notion_sandbox.py:207` | false | KILLED | 1 | `test_equals_form_records_an_override_refusal` | `arg.startswith("--evidence-out=")` |
| 7 | `notion_sandbox.py:214` | false | KILLED | 1 | `test_blank_recorded_id_stays_out_of_the_interrupt_line` | `not ids` |
| 8 | `notion_sandbox.py:236` | false | KILLED | 1 | `test_naive_clock_is_refused` | `type(moment) is not datetime or moment.tzinfo is None` |
| 9 | `notion_sandbox.py:242` | false | KILLED | 66 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `token is not None and token_shape_ok(token)` |
| 10 | `notion_sandbox.py:347` | false | KILLED | 1 | `test_custom_sigint_handler_is_left_in_place` | `current not in (signal.SIG_DFL, signal.default_int_handler)` |
| 11 | `notion_sandbox.py:357` | false | KILLED | 1 | `test_interrupt_does_not_keep_a_symlink` | `stat.S_ISLNK(info.st_mode) or info.st_size <= 0` |
| 12 | `notion_sandbox.py:393` | false | KILLED | 2 | `test_interrupt_before_ready_exits_69` | `path is None or held.started is None or not held.ready` |
| 13 | `notion_sandbox.py:395` | false | KILLED | 1 | `test_interrupt_after_the_evidence_link_leaves_that_file` | `_evidence_is_complete(path)` |
| 14 | `notion_sandbox.py:398` | false | KILLED | 2 | `test_second_interrupt_retries_until_a_file_exists` | `not any(stage.get("status") == "INTERRUPTED" for stage in stages)` |
| 15 | `notion_sandbox.py:421` | false | KILLED | 1 | `test_complete_file_during_the_second_interrupt_returns` | `_evidence_is_complete(path)` |
| 16 | `notion_sandbox.py:461` | false | KILLED | 33 | `test_override_env_refuses[-NOTION_CONFIG]` | `argv_names_a_target(arguments) or environ_names_a_target(env) or cert_env_set(env)` |
| 17 | `notion_sandbox.py:468` | false | KILLED | 1 | `test_encoded_token_evidence_path_writes_nothing` | `str(evidence) == "" or leaks(str(evidence), secret)` |
| 18 | `notion_sandbox.py:472` | false | KILLED | 1 | `test_both_flags_and_secret_evidence_path_refuse` | `parsed.execute and parsed.dry_run` |
| 19 | `notion_sandbox.py:478` | false | KILLED | 3 | `test_missing_token_ignores_other_sources` | `token is None` |
| 20 | `notion_sandbox.py:489` | false | KILLED | 3 | `test_short_token_is_refused` | `secret is None` |
| 21 | `notion_sandbox.py:541` | false | KILLED | 1 | `test_non_string_user_type_exits_69` | `type(bot.user_type) is not str` |
| 22 | `notion_sandbox.py:558` | false | KILLED | 11 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `not target_ok(bot, page)` |
| 23 | `notion_sandbox.py:575` | false | KILLED | 9 | `test_dry_run_is_the_default_and_writes_nothing` | `mode == "dry-run"` |
| 24 | `notion_sandbox.py:621` | false | KILLED | 10 | `test_interrupt_writes_redacted_evidence` | `interrupted` |
| 25 | `notion_sandbox.py:625` | false | KILLED | 19 | `test_absent_stage_failure_stays_not_run` | `failed` |
| 26 | `notion_sandbox.py:659` | false | KILLED | 1 | `test_execute_without_bind_created_still_records` | `bind is None` |
| 27 | `notion_sandbox.py:665` | false | KILLED | 33 | `test_execute_on_the_fake_adapter_writes_evidence` | `type(bot.user_id) is str` |
| 28 | `notion_sandbox.py:705` | false | KILLED | 4 | `test_token_in_error_is_redacted` | `error is not None` |
| 29 | `notion_sandbox.py:707` | false | KILLED | 14 | `test_interrupt_writes_redacted_evidence` | `any(stage.get("status") == "INTERRUPTED" for stage in stages)` |
| 30 | `notion_sandbox.py:710` | false | KILLED | 3 | `test_failed_redaction_exits_70` | `check == "FAIL"` |
| 31 | `notion_sandbox.py:712` | false | KILLED | 10 | `test_dry_run_is_the_default_and_writes_nothing` | `code == EXIT_OK` |
| 32 | `notion_sandbox.py:755` | false | KILLED | 33 | `test_override_env_refuses[-NOTION_CONFIG]` | `path is not None and str(path) != "" and not leaks(str(path), token)` |
| 33 | `notion_sandbox.py:762` | false | KILLED | 1 | `test_module_entry_point_runs_main` | `__name__ == "__main__"` |
| 34 | `notion_sandbox_guard.py:144` | false | KILLED | 1 | `test_canonical_id_normalizes_and_rejects` | `type(value) is not str` |
| 35 | `notion_sandbox_guard.py:147` | false | KILLED | 11 | `test_canonical_id_normalizes_and_rejects` | `len(compact) != 32` |
| 36 | `notion_sandbox_guard.py:149` | false | KILLED | 1 | `test_canonical_id_normalizes_and_rejects` | `any(character not in "0123456789abcdef" for character in compact)` |
| 37 | `notion_sandbox_guard.py:156` | false | KILLED | 2 | `test_target_and_parent_guards` | `type(bot.user_type) is not str or bot.user_type != "bot"` |
| 38 | `notion_sandbox_guard.py:158` | false | KILLED | 7 | `test_target_and_parent_guards` | `page.archived or page.parent_type in {"database_id", "data_source_id"}` |
| 39 | `notion_sandbox_guard.py:160` | false | KILLED | 2 | `test_target_and_parent_guards` | `canonical_id(bot.space_id) != SANDBOX_SPACE_ID` |
| 40 | `notion_sandbox_guard.py:162` | false | KILLED | 1 | `test_target_and_parent_guards` | `canonical_id(page.page_id) != SANDBOX_PARENT_PAGE_ID` |
| 41 | `notion_sandbox_guard.py:170` | false | KILLED | 1 | `test_target_and_parent_guards` | `candidate == ""` |
| 42 | `notion_sandbox_guard.py:178` | false | KILLED | 1 | `test_token_env_and_redaction_units` | `type(value) is not str or value == ""` |
| 43 | `notion_sandbox_guard.py:203` | false | KILLED | 11 | `test_argv_refused_rejects_each_flag[--api-key]` | `head in _OVERRIDE_FLAGS` |
| 44 | `notion_sandbox_guard.py:205` | false | KILLED | 1 | `test_token_on_argv_is_refused` | `contains_secret_shape(arg)` |
| 45 | `notion_sandbox_guard.py:217` | false | KILLED | 137 | `test_token_env_and_redaction_units` | `token is None or not token_shape_ok(token)` |
| 46 | `notion_sandbox_guard.py:222` | false | KILLED | 3 | `test_token_env_and_redaction_units` | `encoded != token` |
| 47 | `notion_sandbox_guard.py:224` | false | KILLED | 4 | `test_token_env_and_redaction_units` | `digest not in forms and digest != token` |
| 48 | `notion_sandbox_guard.py:232` | false | KILLED | 1 | `test_token_env_and_redaction_units` | `token is not None and token != "" and not _unsafe_exact(token) and token in cleaned` |
| 49 | `notion_sandbox_guard.py:234` | false | KILLED | 1 | `test_token_env_and_redaction_units` | `token is not None and token != "" and not _unsafe_exact(token)` |
| 50 | `notion_sandbox_guard.py:237` | false | KILLED | 2 | `test_token_env_and_redaction_units` | `form in cleaned` |
| 51 | `notion_sandbox_guard.py:243` | false | KILLED | 1 | `timeout` | `folded == ""` |
| 52 | `notion_sandbox_guard.py:250` | false | KILLED | 1 | `(no test name)` | `found < 0` |
| 53 | `notion_sandbox_guard.py:260` | false | KILLED | 2 | `test_token_env_and_redaction_units` | `runner_name is None` |
| 54 | `notion_sandbox_guard.py:262` | false | KILLED | 3 | `test_execute_on_the_fake_adapter_writes_evidence` | `outcome == "PASS"` |
| 55 | `notion_sandbox_guard.py:264` | false | KILLED | 19 | `test_absent_stage_failure_stays_not_run` | `outcome == "FAILED"` |
| 56 | `notion_sandbox_guard.py:266` | false | KILLED | 1 | `test_target_and_parent_guards` | `outcome == "BLOCKED"` |
| 57 | `notion_sandbox_guard.py:281` | false | KILLED | 1 | `test_token_env_and_redaction_units` | `stage.get("name") == "qa" and type(found) is str` |
| 58 | `notion_sandbox_guard.py:283` | false | KILLED | 1 | `test_token_env_and_redaction_units` | `status == "PASS"` |
| 59 | `notion_sandbox_guard.py:285` | false | KILLED | 1 | `test_token_env_and_redaction_units` | `status == "FAILED"` |
| 60 | `notion_sandbox_guard.py:287` | false | KILLED | 1 | `test_token_env_and_redaction_units` | `status == "BLOCKED"` |
| 61 | `notion_sandbox_guard.py:302` | false | KILLED | 1 | `test_short_upper_hex_is_not_folded` | `len(compact) < 32` |
| 62 | `notion_sandbox_guard.py:304` | false | KILLED | 1 | `test_percent_and_base64_tokens_are_not_folded_hex` | `any(character not in "0123456789abcdefABCDEF" for character in compact)` |
| 63 | `notion_sandbox_guard.py:311` | false | KILLED | 4 | `test_token_env_and_redaction_units` | `token is not None and token != "" and not _unsafe_exact(token)` |
| 64 | `notion_sandbox_guard.py:312` | false | KILLED | 2 | `test_marker_token_fails_the_redaction_self_check[REDACTED]` | `token in text` |
| 65 | `notion_sandbox_guard.py:315` | false | KILLED | 1 | `test_token_env_and_redaction_units` | `folded != "" and folded in text.lower().replace("-", "")` |
| 66 | `notion_sandbox_guard.py:317` | false | KILLED | 2 | `test_base64_token_in_evidence_exits_70` | `any(form in text for form in _encoded_forms(token))` |
| 67 | `notion_sandbox_guard.py:332` | false | KILLED | 6 | `test_write_evidence_redacts_a_planted_token` | `leaks(text, token)` |
| 68 | `notion_sandbox_guard.py:336` | false | KILLED | 2 | `test_marker_token_fails_the_redaction_self_check[REDACTED]` | `leaks(text, token)` |
| 69 | `notion_sandbox_guard.py:355` | false | EQUIVALENT | 0 |  | `str(path) == "" or path == Path() or under_proc(path)` |
| 70 | `notion_sandbox_guard.py:363` | false | KILLED | 2 | `test_directory_evidence_path_writes_nothing` | `info is not None` |
| 71 | `notion_sandbox_guard.py:370` | false | KILLED | 1 | `test_symlinked_parent_directory_is_refused` | `stat.S_ISLNK(parent_info.st_mode) or not stat.S_ISDIR(parent_info.st_mode)` |
| 72 | `notion_sandbox_guard.py:372` | false | KILLED | 4 | `test_unwritable_directory_writes_nothing` | `parent_info.st_mode & 0o200 == 0` |
| 73 | `notion_sandbox_guard.py:387` | false | KILLED | 5 | `test_commit_evidence_rejects_a_replaced_inode` | `type(found) is not list` |
| 74 | `notion_sandbox_guard.py:391` | false | KILLED | 1 | `test_enospc_ignores_pages_that_are_not_ids` | `type(item) is not dict` |
| 75 | `notion_sandbox_guard.py:394` | false | KILLED | 1 | `test_enospc_after_creates_prints_ids` | `type(page_id) is str and page_id != ""` |
| 76 | `notion_sandbox_guard.py:403` | false | KILLED | 1 | `timeout` | `written <= 0 or written > len(pending)` |
| 77 | `notion_sandbox_guard.py:436` | false | KILLED | 1 | `test_loose_created_mode_is_refused` | `stat.S_IMODE(opened.st_mode) != 0o600` |
| 78 | `notion_sandbox_guard.py:443` | false | KILLED | 2 | `test_swapped_evidence_file_does_not_exit_ok` | `_destination_appeared(path)` |
| 79 | `notion_sandbox_guard.py:449` | false | KILLED | 2 | `test_symlink_at_the_link_is_refused` | `stat.S_ISLNK(current.st_mode) or current.st_size != len(encoded)` |
| 80 | `notion_sandbox_guard.py:458` | false | KILLED | 2 | `test_enospc_after_creates_prints_ids` | `exc.errno in _DISK_ERRNO` |
| 81 | `notion_sandbox_guard.py:462` | false | KILLED | 1 | `test_disk_error_closes_standard_input` | `tmp_fd >= 0` |
| 82 | `notion_sandbox_guard.py:505` | false | KILLED | 1 | `test_repo_root_needs_both_markers` | `(candidate / "pyproject.toml").is_file() and (candidate / "docs" / "control").is_dir()` |
| 83 | `notion_sandbox_guard.py:509` | false | KILLED | 4 | `test_repo_root_falls_back_to_cwd` | `(candidate / "pyproject.toml").is_file() and (candidate / "docs" / "control").is_dir()` |
| 84 | `notion_sandbox_guard.py:527` | false | KILLED | 2 | `test_git_sha_rejects_a_bad_rev_parse` | `completed.returncode != 0 or len(sha) != 40` |
| 85 | `notion_sandbox_guard.py:529` | false | KILLED | 1 | `test_git_sha_rejects_a_bad_rev_parse` | `any(character not in "0123456789abcdef" for character in sha)` |
| 86 | `notion_sandbox_guard.py:541` | false | KILLED | 1 | `test_control_state_container_exits_69` | `type(payload) is not dict` |
| 87 | `notion_sandbox_guard.py:546` | false | KILLED | 1 | `test_string_revision_is_unreadable` | `type(revision) is not int or type(session) is not int or type(head) is not str` |
| 88 | `notion_sandbox_live.py:75` | false | KILLED | 1 | `test_ssl_env_is_refused_and_ignored` | `type(cafile) is str and cafile != ""` |
| 89 | `notion_sandbox_live.py:123` | false | KILLED | 1 | `test_non_string_bot_id_is_rejected` | `bot is None` |
| 90 | `notion_sandbox_live.py:130` | false | KILLED | 1 | `test_empty_page_id_is_not_read` | `expected == ""` |
| 91 | `notion_sandbox_live.py:135` | false | KILLED | 2 | `test_string_in_trash_is_rejected` | `page is None` |
| 92 | `notion_sandbox_live.py:142` | false | KILLED | 1 | `test_live_client_reads_without_writing_and_redacts` | `not parent_is_allowed(parent, allowed)` |
| 93 | `notion_sandbox_live.py:153` | false | KILLED | 1 | `test_request_body_parent_is_asserted` | `type(sent_parent) is not dict or sent_parent.get("page_id") != parent or sent_parent.get("type") != "page_id"` |
| 94 | `notion_sandbox_live.py:161` | false | KILLED | 1 | `test_unparsed_create_is_not_recorded` | `page is None` |
| 95 | `notion_sandbox_live.py:169` | false | KILLED | 1 | `test_wrong_space_create_is_not_published` | `page_id == "" or space_conflicts(page.space_id)` |
| 96 | `notion_sandbox_live.py:171` | false | KILLED | 5 | `test_doc_shaped_pages_execute_without_a_space` | `page_id not in self._created_ids` |
| 97 | `notion_sandbox_live.py:175` | false | KILLED | 2 | `test_live_child_page_does_not_count_its_own_write` | `evidence_ids is None or evidence_rows is None or page_id in evidence_ids` |
| 98 | `notion_sandbox_live.py:184` | false | KILLED | 2 | `test_hex_token_equal_to_the_page_id_sends_nothing` | `leaks(url, self._token) or leaks(url.replace("-", ""), self._token)` |
| 99 | `notion_sandbox_live.py:190` | false | KILLED | 1 | `test_live_child_page_does_not_count_its_own_write` | `body is not None` |
| 100 | `notion_sandbox_live.py:195` | false | KILLED | 1 | `test_redirect_code_is_refused_without_a_status` | `type(status) is not int` |
| 101 | `notion_sandbox_live.py:197` | false | KILLED | 2 | `test_redirect_is_not_followed` | `type(status) is int and 300 <= status < 400` |
| 102 | `notion_sandbox_live.py:206` | false | KILLED | 1 | `test_non_byte_body_is_an_api_error` | `type(raw) is not bytes` |
| 103 | `notion_sandbox_live.py:216` | false | KILLED | 1 | `test_parse_bot_rejects_a_non_object` | `type(payload) is not dict` |
| 104 | `notion_sandbox_live.py:220` | false | KILLED | 1 | `test_non_string_bot_id_is_rejected` | `type(user_id) is not str or type(user_type) is not str` |
| 105 | `notion_sandbox_live.py:224` | false | KILLED | 7 | `test_live_client_reads_without_writing_and_redacts` | `type(bot) is dict and type(bot.get("workspace_id")) is str` |
| 106 | `notion_sandbox_live.py:231` | false | KILLED | 26 | `test_live_client_reads_without_writing_and_redacts` | `key not in payload` |
| 107 | `notion_sandbox_live.py:234` | false | KILLED | 1 | `test_string_in_trash_is_rejected` | `type(value) is not bool` |
| 108 | `notion_sandbox_live.py:241` | false | KILLED | 1 | `test_database_parent_and_missing_object_write_nothing` | `type(payload) is not dict or payload.get("object") != "page"` |
| 109 | `notion_sandbox_live.py:244` | false | KILLED | 1 | `test_parse_page_rejects_a_non_id` | `page_id == ""` |
| 110 | `notion_sandbox_live.py:250` | false | KILLED | 9 | `test_live_child_page_does_not_count_its_own_write` | `type(parent) is dict` |
| 111 | `notion_sandbox_live.py:251` | false | KILLED | 1 | `test_parent_object_can_carry_the_space` | `space == ""` |
| 112 | `notion_sandbox_live.py:254` | false | KILLED | 3 | `test_database_id_parent_is_not_a_page_parent` | `type(found_type) is str` |
| 113 | `notion_sandbox_live.py:256` | false | KILLED | 5 | `test_live_child_page_does_not_count_its_own_write` | `found_type == "page_id"` |
| 114 | `notion_sandbox_live.py:258` | false | KILLED | 7 | `test_live_client_reads_without_writing_and_redacts` | `space == "" and page_id == canonical_id(expected_id)` |
| 115 | `notion_sandbox_live.py:261` | false | KILLED | 1 | `test_parse_page_keeps_a_url_and_fills_a_blank_one` | `type(url) is not str or url == ""` |
| 116 | `notion_sandbox_live.py:266` | false | KILLED | 1 | `test_string_in_trash_is_rejected` | `archived_flag is None or alias_flag is None or trash_flag is None` |
| 117 | `notion_sandbox_live.py:283` | false | KILLED | 20 | `test_live_client_reads_without_writing_and_redacts` | `type(value) is not str or value == ""` |
| 118 | `notion_sandbox_live.py:289` | false | KILLED | 1 | `test_naive_timestamp_stays_unset` | `parsed.tzinfo is None` |
| 119 | `notion_sandbox_live.py:296` | false | KILLED | 19 | `test_live_client_reads_without_writing_and_redacts` | `type(actor) is not dict` |
| 120 | `notion_sandbox_live.py:299` | false | KILLED | 1 | `test_non_string_created_by_stays_blank` | `type(found) is not str` |
| 121 | `notion_sandbox_live.py:307` | false | KILLED | 1 | `test_proxy_map_ignores_a_missing_handler_list` | `type(handlers) is not list` |
| 122 | `notion_sandbox_live.py:310` | false | KILLED | 2 | `test_proxy_map_reads_string_proxy_entries` | `isinstance(handler, urllib.request.ProxyHandler)` |
| 123 | `notion_sandbox_live.py:312` | false | KILLED | 1 | `test_proxy_map_ignores_a_non_dict_proxy_table` | `type(found) is not dict` |
| 124 | `notion_sandbox_live.py:315` | false | KILLED | 2 | `test_proxy_map_reads_string_proxy_entries` | `type(key) is str and type(value) is str` |
| 125 | `notion_sandbox_live.py:324` | false | KILLED | 4 | `test_live_space_fallback_is_only_the_asserted_parent` | `type(value) is str and canonical_id(value) != ""` |
| 126 | `notion_sandbox_pipeline.py:144` | false | KILLED | 1 | `test_drop_keeps_an_earlier_id_and_ignores_a_missing_one` | `page_id not in ctx.created_ids` |
| 127 | `notion_sandbox_pipeline.py:146` | false | KILLED | 1 | `test_drop_keeps_an_earlier_id_and_ignores_a_missing_one` | `ctx.created_ids.index(page_id) < before` |
| 128 | `notion_sandbox_pipeline.py:153` | false | KILLED | 2 | `test_blank_id_already_recorded_is_kept` | `page_id == "" or page_id not in ctx.created_ids` |
| 129 | `notion_sandbox_pipeline.py:160` | false | KILLED | 1 | `test_drop_keeps_an_earlier_id_and_ignores_a_missing_one` | `page_id == ""` |
| 130 | `notion_sandbox_pipeline.py:163` | false | KILLED | 3 | `test_wrong_space_on_create_return_stops` | `row.get("id") == page_id and row.get("reason") == reason` |
| 131 | `notion_sandbox_pipeline.py:169` | false | KILLED | 25 | `test_execute_on_the_fake_adapter_writes_evidence` | `page_id == "" or page_id in ctx.created_ids` |
| 132 | `notion_sandbox_pipeline.py:178` | false | KILLED | 2 | `test_unfresh_page_is_removed_from_the_recorded_ids` | `page_id in ctx.created_ids` |
| 133 | `notion_sandbox_pipeline.py:181` | false | KILLED | 6 | `test_stale_foreign_page_is_not_a_parent` | `page_id != "" and all(row.get("id") != page_id for row in ctx.rejected_pages)` |
| 134 | `notion_sandbox_pipeline.py:200` | false | EQUIVALENT | 0 |  | `tail == page_id` |
| 135 | `notion_sandbox_pipeline.py:203` | false | KILLED | 1 | `test_later_create_returning_an_earlier_foreign_id_drops_it` | `page_id == "" or space_conflicts(page.space_id)` |
| 136 | `notion_sandbox_pipeline.py:204` | false | KILLED | 1 | `test_later_create_returning_an_earlier_foreign_id_drops_it` | `page_id in ctx.created_ids[:before]` |
| 137 | `notion_sandbox_pipeline.py:207` | false | KILLED | 1 | `test_unbound_foreign_create_is_kept_and_flagged` | `space_conflicts(page.space_id) and page_id != ""` |
| 138 | `notion_sandbox_pipeline.py:216` | false | KILLED | 5 | `test_stale_foreign_page_is_not_a_parent` | `page.created_by != ctx.bot_user_id` |
| 139 | `notion_sandbox_pipeline.py:219` | false | KILLED | 1 | `test_missing_created_time_is_not_new` | `moment is None` |
| 140 | `notion_sandbox_pipeline.py:221` | false | KILLED | 1 | `test_naive_created_time_is_not_new` | `moment.tzinfo is None` |
| 141 | `notion_sandbox_pipeline.py:223` | false | KILLED | 1 | `test_stale_confirm_stops_later_writes` | `moment < _earliest(ctx.moment)` |
| 142 | `notion_sandbox_pipeline.py:233` | false | KILLED | 26 | `test_execute_on_the_fake_adapter_writes_evidence` | `page_id == SANDBOX_PARENT_PAGE_ID` |
| 143 | `notion_sandbox_pipeline.py:234` | false | KILLED | 1 | `test_sandbox_parent_in_a_foreign_space_fails_the_chain` | `space_conflicts(current.space_id) or current.archived` |
| 144 | `notion_sandbox_pipeline.py:239` | false | KILLED | 2 | `test_empty_parent_chain_does_not_read_again` | `parent_id == "" or page_id == "" or page_id in seen` |
| 145 | `notion_sandbox_pipeline.py:243` | false | KILLED | 1 | `test_parent_read_with_a_different_id_is_refused` | `canonical_id(current.page_id) != parent_id` |
| 146 | `notion_sandbox_pipeline.py:246` | false | KILLED | 1 | `test_trashed_product_page_stops_further_writes` | `space_conflicts(current.space_id) or current.archived` |
| 147 | `notion_sandbox_pipeline.py:255` | false | KILLED | 1 | `test_create_under_refuses_a_foreign_parent` | `not parent_is_allowed(requested, allowed)` |
| 148 | `notion_sandbox_pipeline.py:257` | false | KILLED | 1 | `test_foreign_bot_space_creates_nothing` | `canonical_id(ctx.bot_space_id) != SANDBOX_SPACE_ID` |
| 149 | `notion_sandbox_pipeline.py:272` | false | KILLED | 3 | `test_create_that_returns_the_parent_id_is_not_new` | `page_id in {"", SANDBOX_PARENT_PAGE_ID, requested}` |
| 150 | `notion_sandbox_pipeline.py:273` | false | KILLED | 1 | `test_returning_the_requested_id_keeps_it` | `page_id not in {"", SANDBOX_PARENT_PAGE_ID}` |
| 151 | `notion_sandbox_pipeline.py:278` | false | KILLED | 1 | `test_repeated_created_id_is_refused` | `page_id in ctx.created_ids[:before]` |
| 152 | `notion_sandbox_pipeline.py:280` | false | KILLED | 2 | `test_wrong_space_on_create_return_stops` | `space_conflicts(page.space_id)` |
| 153 | `notion_sandbox_pipeline.py:283` | false | KILLED | 1 | `test_lying_response_parent_stops` | `canonical_id(page.parent_id) != requested` |
| 154 | `notion_sandbox_pipeline.py:287` | false | KILLED | 1 | `test_confirm_of_a_different_id_keeps_the_created_page` | `canonical_id(confirmed.page_id) != page_id` |
| 155 | `notion_sandbox_pipeline.py:289` | false | KILLED | 1 | `test_wrong_nesting_stops` | `canonical_id(confirmed.parent_id) != requested` |
| 156 | `notion_sandbox_pipeline.py:291` | false | KILLED | 2 | `test_trashed_confirm_stops_further_writes` | `space_conflicts(confirmed.space_id) or confirmed.archived` |
| 157 | `notion_sandbox_pipeline.py:297` | false | KILLED | 1 | `test_token_in_created_url_exits_70` | `ctx.created and ctx.created[-1].get("id") == page_id` |
| 158 | `notion_sandbox_pipeline.py:319` | false | EQUIVALENT | 0 |  | `type(spec) is not ProductSpec` |
| 159 | `notion_sandbox_pipeline.py:327` | false | KILLED | 1 | `test_variants_without_a_product_page_are_a_sandbox_error` | `ctx.probe is None or ctx.product_page_id is None or type(spec) is not ProductSpec` |

## Boolean operands

| # | Site | Operator | Mutation | Result | Failed | Test | Condition |
|---|---|---|---|---|---|---|---|
| 1 | `notion_sandbox.py:142` | and | swap | KILLED | 1 | `test_read_base_exceptions_stay_redacted` | `available and not marked` |
| 2 | `notion_sandbox.py:142` | and | not1 | KILLED | 1 | `test_read_base_exceptions_stay_redacted` | `available and not marked` |
| 3 | `notion_sandbox.py:142` | and | not2 | KILLED | 1 | `test_read_base_exceptions_stay_redacted` | `available and not marked` |
| 4 | `notion_sandbox.py:164` | or | swap | KILLED | 1 | `test_absent_stage_failure_stays_not_run` | `not available or failed` |
| 5 | `notion_sandbox.py:164` | or | not1 | KILLED | 42 | `test_execute_on_the_fake_adapter_writes_evidence` | `not available or failed` |
| 6 | `notion_sandbox.py:164` | or | not2 | KILLED | 42 | `test_execute_on_the_fake_adapter_writes_evidence` | `not available or failed` |
| 7 | `notion_sandbox.py:205` | and | swap | KILLED | 1 | `test_evidence_out_without_a_value_is_usage` | `arg == "--evidence-out" and index + 1 < len(argv)` |
| 8 | `notion_sandbox.py:205` | and | not1 | KILLED | 44 | `test_override_env_refuses[-NOTION_CONFIG]` | `arg == "--evidence-out" and index + 1 < len(argv)` |
| 9 | `notion_sandbox.py:205` | and | not2 | KILLED | 33 | `test_override_env_refuses[-NOTION_CONFIG]` | `arg == "--evidence-out" and index + 1 < len(argv)` |
| 10 | `notion_sandbox.py:213` | and | swap | KILLED | 1 | `test_blank_recorded_id_stays_out_of_the_interrupt_line` | `type(row.get("id")) is str and row["id"] != ""` |
| 11 | `notion_sandbox.py:213` | and | not1 | KILLED | 7 | `test_interrupt_writes_redacted_evidence` | `type(row.get("id")) is str and row["id"] != ""` |
| 12 | `notion_sandbox.py:213` | and | not2 | KILLED | 8 | `test_interrupt_writes_redacted_evidence` | `type(row.get("id")) is str and row["id"] != ""` |
| 13 | `notion_sandbox.py:236` | or | swap | KILLED | 1 | `test_naive_clock_is_refused` | `type(moment) is not datetime or moment.tzinfo is None` |
| 14 | `notion_sandbox.py:236` | or | not1 | KILLED | 139 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `type(moment) is not datetime or moment.tzinfo is None` |
| 15 | `notion_sandbox.py:236` | or | not2 | KILLED | 140 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `type(moment) is not datetime or moment.tzinfo is None` |
| 16 | `notion_sandbox.py:242` | and | swap | KILLED | 6 | `test_short_token_is_refused` | `token is not None and token_shape_ok(token)` |
| 17 | `notion_sandbox.py:242` | and | not1 | KILLED | 69 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `token is not None and token_shape_ok(token)` |
| 18 | `notion_sandbox.py:242` | and | not2 | KILLED | 69 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `token is not None and token_shape_ok(token)` |
| 19 | `notion_sandbox.py:357` | or | swap | KILLED | 1 | `test_interrupt_does_not_keep_a_symlink` | `stat.S_ISLNK(info.st_mode) or info.st_size <= 0` |
| 20 | `notion_sandbox.py:357` | or | not1 | KILLED | 3 | `test_interrupt_after_the_evidence_link_leaves_that_file` | `stat.S_ISLNK(info.st_mode) or info.st_size <= 0` |
| 21 | `notion_sandbox.py:357` | or | not2 | KILLED | 2 | `test_interrupt_after_the_evidence_link_leaves_that_file` | `stat.S_ISLNK(info.st_mode) or info.st_size <= 0` |
| 22 | `notion_sandbox.py:393` | or | swap | KILLED | 1 | `test_unpublished_path_is_an_interrupt` | `path is None or held.started is None or not held.ready` |
| 23 | `notion_sandbox.py:393` | or | not1 | KILLED | 6 | `test_interrupt_does_not_keep_a_symlink` | `path is None or held.started is None or not held.ready` |
| 24 | `notion_sandbox.py:393` | or | not2 | KILLED | 5 | `test_interrupt_does_not_keep_a_symlink` | `path is None or held.started is None or not held.ready` |
| 25 | `notion_sandbox.py:393` | or | not3 | KILLED | 5 | `test_interrupt_does_not_keep_a_symlink` | `path is None or held.started is None or not held.ready` |
| 26 | `notion_sandbox.py:461` | or | swap | KILLED | 33 | `test_override_env_refuses[-NOTION_CONFIG]` | `argv_names_a_target(arguments) or environ_names_a_target(env) or cert_env_set(env)` |
| 27 | `notion_sandbox.py:461` | or | not1 | KILLED | 72 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `argv_names_a_target(arguments) or environ_names_a_target(env) or cert_env_set(env)` |
| 28 | `notion_sandbox.py:461` | or | not2 | KILLED | 102 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `argv_names_a_target(arguments) or environ_names_a_target(env) or cert_env_set(env)` |
| 29 | `notion_sandbox.py:461` | or | not3 | KILLED | 72 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `argv_names_a_target(arguments) or environ_names_a_target(env) or cert_env_set(env)` |
| 30 | `notion_sandbox.py:468` | or | swap | KILLED | 1 | `test_encoded_token_evidence_path_writes_nothing` | `str(evidence) == "" or leaks(str(evidence), secret)` |
| 31 | `notion_sandbox.py:468` | or | not1 | KILLED | 91 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `str(evidence) == "" or leaks(str(evidence), secret)` |
| 32 | `notion_sandbox.py:468` | or | not2 | KILLED | 92 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `str(evidence) == "" or leaks(str(evidence), secret)` |
| 33 | `notion_sandbox.py:472` | and | swap | KILLED | 59 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `parsed.execute and parsed.dry_run` |
| 34 | `notion_sandbox.py:472` | and | not1 | KILLED | 2 | `test_both_flags_and_secret_evidence_path_refuse` | `parsed.execute and parsed.dry_run` |
| 35 | `notion_sandbox.py:472` | and | not2 | KILLED | 59 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `parsed.execute and parsed.dry_run` |
| 36 | `notion_sandbox.py:600` | or | swap | KILLED | 30 | `test_execute_on_the_fake_adapter_writes_evidence` | `_user_id(bot) or ""` |
| 37 | `notion_sandbox.py:600` | or | not1 | KILLED | 31 | `test_execute_on_the_fake_adapter_writes_evidence` | `_user_id(bot) or ""` |
| 38 | `notion_sandbox.py:600` | or | not2 | KILLED | 1 | `test_empty_bot_user_id_still_executes` | `_user_id(bot) or ""` |
| 39 | `notion_sandbox.py:755` | and | swap | KILLED | 1 | `test_both_flags_and_secret_evidence_path_refuse` | `path is not None and str(path) != "" and not leaks(str(path), token)` |
| 40 | `notion_sandbox.py:755` | and | not1 | KILLED | 33 | `test_override_env_refuses[-NOTION_CONFIG]` | `path is not None and str(path) != "" and not leaks(str(path), token)` |
| 41 | `notion_sandbox.py:755` | and | not2 | KILLED | 33 | `test_override_env_refuses[-NOTION_CONFIG]` | `path is not None and str(path) != "" and not leaks(str(path), token)` |
| 42 | `notion_sandbox.py:755` | and | not3 | KILLED | 34 | `test_override_env_refuses[-NOTION_CONFIG]` | `path is not None and str(path) != "" and not leaks(str(path), token)` |
| 43 | `notion_sandbox_guard.py:156` | or | swap | KILLED | 2 | `test_target_and_parent_guards` | `type(bot.user_type) is not str or bot.user_type != "bot"` |
| 44 | `notion_sandbox_guard.py:156` | or | not1 | KILLED | 46 | `test_target_and_parent_guards` | `type(bot.user_type) is not str or bot.user_type != "bot"` |
| 45 | `notion_sandbox_guard.py:156` | or | not2 | KILLED | 47 | `test_target_and_parent_guards` | `type(bot.user_type) is not str or bot.user_type != "bot"` |
| 46 | `notion_sandbox_guard.py:158` | or | swap | KILLED | 7 | `test_target_and_parent_guards` | `page.archived or page.parent_type in {"database_id", "data_source_id"}` |
| 47 | `notion_sandbox_guard.py:158` | or | not1 | KILLED | 50 | `test_target_and_parent_guards` | `page.archived or page.parent_type in {"database_id", "data_source_id"}` |
| 48 | `notion_sandbox_guard.py:158` | or | not2 | KILLED | 48 | `test_target_and_parent_guards` | `page.archived or page.parent_type in {"database_id", "data_source_id"}` |
| 49 | `notion_sandbox_guard.py:178` | or | swap | KILLED | 1 | `test_token_env_and_redaction_units` | `type(value) is not str or value == ""` |
| 50 | `notion_sandbox_guard.py:178` | or | not1 | KILLED | 70 | `test_token_env_and_redaction_units` | `type(value) is not str or value == ""` |
| 51 | `notion_sandbox_guard.py:178` | or | not2 | KILLED | 70 | `test_token_env_and_redaction_units` | `type(value) is not str or value == ""` |
| 52 | `notion_sandbox_guard.py:196` | and | swap | KILLED | 39 | `test_execute_on_the_fake_adapter_writes_evidence` | `found != "" and found != SANDBOX_SPACE_ID` |
| 53 | `notion_sandbox_guard.py:196` | and | not1 | KILLED | 13 | `test_wrong_space_on_create_return_stops` | `found != "" and found != SANDBOX_SPACE_ID` |
| 54 | `notion_sandbox_guard.py:196` | and | not2 | KILLED | 42 | `test_execute_on_the_fake_adapter_writes_evidence` | `found != "" and found != SANDBOX_SPACE_ID` |
| 55 | `notion_sandbox_guard.py:212` | or | swap | KILLED | 1 | `test_token_env_and_redaction_units` | `token.strip() == "" or token in {"true", "false", "null"}` |
| 56 | `notion_sandbox_guard.py:212` | or | not1 | KILLED | 4 | `test_token_env_and_redaction_units` | `token.strip() == "" or token in {"true", "false", "null"}` |
| 57 | `notion_sandbox_guard.py:212` | or | not2 | KILLED | 4 | `test_token_env_and_redaction_units` | `token.strip() == "" or token in {"true", "false", "null"}` |
| 58 | `notion_sandbox_guard.py:217` | or | swap | KILLED | 137 | `test_token_env_and_redaction_units` | `token is None or not token_shape_ok(token)` |
| 59 | `notion_sandbox_guard.py:217` | or | not1 | KILLED | 137 | `test_token_env_and_redaction_units` | `token is None or not token_shape_ok(token)` |
| 60 | `notion_sandbox_guard.py:217` | or | not2 | KILLED | 4 | `test_token_env_and_redaction_units` | `token is None or not token_shape_ok(token)` |
| 61 | `notion_sandbox_guard.py:224` | and | swap | EQUIVALENT | 0 |  | `digest not in forms and digest != token` |
| 62 | `notion_sandbox_guard.py:224` | and | not1 | KILLED | 4 | `test_token_env_and_redaction_units` | `digest not in forms and digest != token` |
| 63 | `notion_sandbox_guard.py:224` | and | not2 | KILLED | 4 | `test_token_env_and_redaction_units` | `digest not in forms and digest != token` |
| 64 | `notion_sandbox_guard.py:232` | and | swap | KILLED | 137 | `test_token_env_and_redaction_units` | `token is not None and token != "" and not _unsafe_exact(token) and token in cleaned` |
| 65 | `notion_sandbox_guard.py:232` | and | not1 | KILLED | 137 | `test_token_env_and_redaction_units` | `token is not None and token != "" and not _unsafe_exact(token) and token in cleaned` |
| 66 | `notion_sandbox_guard.py:232` | and | not2 | KILLED | 1 | `test_token_env_and_redaction_units` | `token is not None and token != "" and not _unsafe_exact(token) and token in cleaned` |
| 67 | `notion_sandbox_guard.py:232` | and | not3 | KILLED | 1 | `test_token_env_and_redaction_units` | `token is not None and token != "" and not _unsafe_exact(token) and token in cleaned` |
| 68 | `notion_sandbox_guard.py:232` | and | not4 | KILLED | 1 | `test_token_env_and_redaction_units` | `token is not None and token != "" and not _unsafe_exact(token) and token in cleaned` |
| 69 | `notion_sandbox_guard.py:234` | and | swap | KILLED | 137 | `test_token_env_and_redaction_units` | `token is not None and token != "" and not _unsafe_exact(token)` |
| 70 | `notion_sandbox_guard.py:234` | and | not1 | KILLED | 137 | `test_token_env_and_redaction_units` | `token is not None and token != "" and not _unsafe_exact(token)` |
| 71 | `notion_sandbox_guard.py:234` | and | not2 | KILLED | 1 | `test_token_env_and_redaction_units` | `token is not None and token != "" and not _unsafe_exact(token)` |
| 72 | `notion_sandbox_guard.py:234` | and | not3 | KILLED | 1 | `test_token_env_and_redaction_units` | `token is not None and token != "" and not _unsafe_exact(token)` |
| 73 | `notion_sandbox_guard.py:281` | and | swap | KILLED | 1 | `test_token_env_and_redaction_units` | `stage.get("name") == "qa" and type(found) is str` |
| 74 | `notion_sandbox_guard.py:281` | and | not1 | KILLED | 1 | `test_token_env_and_redaction_units` | `stage.get("name") == "qa" and type(found) is str` |
| 75 | `notion_sandbox_guard.py:281` | and | not2 | KILLED | 1 | `test_token_env_and_redaction_units` | `stage.get("name") == "qa" and type(found) is str` |
| 76 | `notion_sandbox_guard.py:311` | and | swap | KILLED | 11 | `test_short_token_is_refused` | `token is not None and token != "" and not _unsafe_exact(token)` |
| 77 | `notion_sandbox_guard.py:311` | and | not1 | KILLED | 15 | `test_token_env_and_redaction_units` | `token is not None and token != "" and not _unsafe_exact(token)` |
| 78 | `notion_sandbox_guard.py:311` | and | not2 | KILLED | 4 | `test_token_env_and_redaction_units` | `token is not None and token != "" and not _unsafe_exact(token)` |
| 79 | `notion_sandbox_guard.py:311` | and | not3 | KILLED | 4 | `test_token_env_and_redaction_units` | `token is not None and token != "" and not _unsafe_exact(token)` |
| 80 | `notion_sandbox_guard.py:315` | and | swap | KILLED | 128 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `folded != "" and folded in text.lower().replace("-", "")` |
| 81 | `notion_sandbox_guard.py:315` | and | not1 | KILLED | 129 | `test_token_env_and_redaction_units` | `folded != "" and folded in text.lower().replace("-", "")` |
| 82 | `notion_sandbox_guard.py:315` | and | not2 | KILLED | 1 | `test_token_env_and_redaction_units` | `folded != "" and folded in text.lower().replace("-", "")` |
| 83 | `notion_sandbox_guard.py:350` | or | swap | KILLED | 1 | `test_proc_path_helper_rejects_proc_itself` | `absolute == Path("/proc") or Path("/proc") in absolute.parents` |
| 84 | `notion_sandbox_guard.py:350` | or | not1 | KILLED | 131 | `test_write_evidence_redacts_a_planted_token` | `absolute == Path("/proc") or Path("/proc") in absolute.parents` |
| 85 | `notion_sandbox_guard.py:350` | or | not2 | KILLED | 131 | `test_write_evidence_redacts_a_planted_token` | `absolute == Path("/proc") or Path("/proc") in absolute.parents` |
| 86 | `notion_sandbox_guard.py:355` | or | swap | EQUIVALENT | 0 |  | `str(path) == "" or path == Path() or under_proc(path)` |
| 87 | `notion_sandbox_guard.py:355` | or | not1 | KILLED | 130 | `test_write_evidence_redacts_a_planted_token` | `str(path) == "" or path == Path() or under_proc(path)` |
| 88 | `notion_sandbox_guard.py:355` | or | not2 | KILLED | 130 | `test_write_evidence_redacts_a_planted_token` | `str(path) == "" or path == Path() or under_proc(path)` |
| 89 | `notion_sandbox_guard.py:355` | or | not3 | KILLED | 130 | `test_write_evidence_redacts_a_planted_token` | `str(path) == "" or path == Path() or under_proc(path)` |
| 90 | `notion_sandbox_guard.py:370` | or | swap | EQUIVALENT | 0 |  | `stat.S_ISLNK(parent_info.st_mode) or not stat.S_ISDIR(parent_info.st_mode)` |
| 91 | `notion_sandbox_guard.py:370` | or | not1 | KILLED | 130 | `test_write_evidence_redacts_a_planted_token` | `stat.S_ISLNK(parent_info.st_mode) or not stat.S_ISDIR(parent_info.st_mode)` |
| 92 | `notion_sandbox_guard.py:370` | or | not2 | KILLED | 130 | `test_write_evidence_redacts_a_planted_token` | `stat.S_ISLNK(parent_info.st_mode) or not stat.S_ISDIR(parent_info.st_mode)` |
| 93 | `notion_sandbox_guard.py:394` | and | swap | KILLED | 1 | `test_enospc_ignores_pages_that_are_not_ids` | `type(page_id) is str and page_id != ""` |
| 94 | `notion_sandbox_guard.py:394` | and | not1 | KILLED | 2 | `test_enospc_after_creates_prints_ids` | `type(page_id) is str and page_id != ""` |
| 95 | `notion_sandbox_guard.py:394` | and | not2 | KILLED | 1 | `test_enospc_after_creates_prints_ids` | `type(page_id) is str and page_id != ""` |
| 96 | `notion_sandbox_guard.py:403` | or | swap | KILLED | 1 | `timeout` | `written <= 0 or written > len(pending)` |
| 97 | `notion_sandbox_guard.py:403` | or | not1 | KILLED | 1 | `timeout` | `written <= 0 or written > len(pending)` |
| 98 | `notion_sandbox_guard.py:403` | or | not2 | KILLED | 126 | `test_write_evidence_redacts_a_planted_token` | `written <= 0 or written > len(pending)` |
| 99 | `notion_sandbox_guard.py:449` | or | swap | KILLED | 1 | `test_short_replacement_is_not_finished_evidence` | `stat.S_ISLNK(current.st_mode) or current.st_size != len(encoded)` |
| 100 | `notion_sandbox_guard.py:449` | or | not1 | KILLED | 121 | `test_write_evidence_redacts_a_planted_token` | `stat.S_ISLNK(current.st_mode) or current.st_size != len(encoded)` |
| 101 | `notion_sandbox_guard.py:449` | or | not2 | KILLED | 122 | `test_write_evidence_redacts_a_planted_token` | `stat.S_ISLNK(current.st_mode) or current.st_size != len(encoded)` |
| 102 | `notion_sandbox_guard.py:505` | and | swap | KILLED | 1 | `test_repo_root_ignores_a_partial_marker` | `(candidate / "pyproject.toml").is_file() and (candidate / "docs" / "control").is_dir()` |
| 103 | `notion_sandbox_guard.py:505` | and | not1 | KILLED | 1 | `test_repo_root_needs_both_markers` | `(candidate / "pyproject.toml").is_file() and (candidate / "docs" / "control").is_dir()` |
| 104 | `notion_sandbox_guard.py:505` | and | not2 | KILLED | 2 | `test_repo_root_needs_both_markers` | `(candidate / "pyproject.toml").is_file() and (candidate / "docs" / "control").is_dir()` |
| 105 | `notion_sandbox_guard.py:509` | and | swap | KILLED | 2 | `test_partial_marker_between_cwd_and_the_repo_is_not_root[pyproject]` | `(candidate / "pyproject.toml").is_file() and (candidate / "docs" / "control").is_dir()` |
| 106 | `notion_sandbox_guard.py:509` | and | not1 | KILLED | 4 | `test_repo_root_falls_back_to_cwd` | `(candidate / "pyproject.toml").is_file() and (candidate / "docs" / "control").is_dir()` |
| 107 | `notion_sandbox_guard.py:509` | and | not2 | KILLED | 4 | `test_repo_root_falls_back_to_cwd` | `(candidate / "pyproject.toml").is_file() and (candidate / "docs" / "control").is_dir()` |
| 108 | `notion_sandbox_guard.py:527` | or | swap | KILLED | 1 | `test_git_sha_rejects_a_bad_rev_parse` | `completed.returncode != 0 or len(sha) != 40` |
| 109 | `notion_sandbox_guard.py:527` | or | not1 | KILLED | 136 | `test_git_sha_rejects_a_bad_rev_parse` | `completed.returncode != 0 or len(sha) != 40` |
| 110 | `notion_sandbox_guard.py:527` | or | not2 | KILLED | 136 | `test_git_sha_rejects_a_bad_rev_parse` | `completed.returncode != 0 or len(sha) != 40` |
| 111 | `notion_sandbox_guard.py:546` | or | swap | KILLED | 1 | `test_string_revision_is_unreadable` | `type(revision) is not int or type(session) is not int or type(head) is not str` |
| 112 | `notion_sandbox_guard.py:546` | or | not1 | KILLED | 134 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `type(revision) is not int or type(session) is not int or type(head) is not str` |
| 113 | `notion_sandbox_guard.py:546` | or | not2 | KILLED | 133 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `type(revision) is not int or type(session) is not int or type(head) is not str` |
| 114 | `notion_sandbox_guard.py:546` | or | not3 | KILLED | 133 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `type(revision) is not int or type(session) is not int or type(head) is not str` |
| 115 | `notion_sandbox_live.py:75` | and | swap | KILLED | 1 | `test_absent_cafile_skips_load` | `type(cafile) is str and cafile != ""` |
| 116 | `notion_sandbox_live.py:75` | and | not1 | KILLED | 2 | `test_ssl_env_is_refused_and_ignored` | `type(cafile) is str and cafile != ""` |
| 117 | `notion_sandbox_live.py:75` | and | not2 | KILLED | 1 | `test_ssl_env_is_refused_and_ignored` | `type(cafile) is str and cafile != ""` |
| 118 | `notion_sandbox_live.py:154` | or | swap | KILLED | 1 | `test_request_body_parent_is_asserted` | `type(sent_parent) is not dict or sent_parent.get("page_id") != parent or sent_parent.get("type") != "page_id"` |
| 119 | `notion_sandbox_live.py:154` | or | not1 | KILLED | 10 | `test_live_child_page_does_not_count_its_own_write` | `type(sent_parent) is not dict or sent_parent.get("page_id") != parent or sent_parent.get("type") != "page_id"` |
| 120 | `notion_sandbox_live.py:154` | or | not2 | KILLED | 11 | `test_live_child_page_does_not_count_its_own_write` | `type(sent_parent) is not dict or sent_parent.get("page_id") != parent or sent_parent.get("type") != "page_id"` |
| 121 | `notion_sandbox_live.py:154` | or | not3 | KILLED | 10 | `test_live_child_page_does_not_count_its_own_write` | `type(sent_parent) is not dict or sent_parent.get("page_id") != parent or sent_parent.get("type") != "page_id"` |
| 122 | `notion_sandbox_live.py:169` | or | swap | KILLED | 1 | `test_wrong_space_create_is_not_published` | `page_id == "" or space_conflicts(page.space_id)` |
| 123 | `notion_sandbox_live.py:169` | or | not1 | KILLED | 6 | `test_doc_shaped_pages_execute_without_a_space` | `page_id == "" or space_conflicts(page.space_id)` |
| 124 | `notion_sandbox_live.py:169` | or | not2 | KILLED | 7 | `test_doc_shaped_pages_execute_without_a_space` | `page_id == "" or space_conflicts(page.space_id)` |
| 125 | `notion_sandbox_live.py:175` | or | swap | KILLED | 2 | `test_live_child_page_does_not_count_its_own_write` | `evidence_ids is None or evidence_rows is None or page_id in evidence_ids` |
| 126 | `notion_sandbox_live.py:175` | or | not1 | KILLED | 3 | `test_doc_shaped_interrupt_after_store_records_the_created_id[0-exc0]` | `evidence_ids is None or evidence_rows is None or page_id in evidence_ids` |
| 127 | `notion_sandbox_live.py:175` | or | not2 | KILLED | 3 | `test_doc_shaped_interrupt_after_store_records_the_created_id[0-exc0]` | `evidence_ids is None or evidence_rows is None or page_id in evidence_ids` |
| 128 | `notion_sandbox_live.py:175` | or | not3 | KILLED | 3 | `test_doc_shaped_interrupt_after_store_records_the_created_id[0-exc0]` | `evidence_ids is None or evidence_rows is None or page_id in evidence_ids` |
| 129 | `notion_sandbox_live.py:184` | or | swap | KILLED | 1 | `test_dashed_secret_in_the_live_path_is_not_sent` | `leaks(url, self._token) or leaks(url.replace("-", ""), self._token)` |
| 130 | `notion_sandbox_live.py:184` | or | not1 | KILLED | 23 | `test_live_client_reads_without_writing_and_redacts` | `leaks(url, self._token) or leaks(url.replace("-", ""), self._token)` |
| 131 | `notion_sandbox_live.py:184` | or | not2 | KILLED | 24 | `test_live_client_reads_without_writing_and_redacts` | `leaks(url, self._token) or leaks(url.replace("-", ""), self._token)` |
| 132 | `notion_sandbox_live.py:197` | and | swap | KILLED | 23 | `test_live_client_reads_without_writing_and_redacts` | `type(status) is int and 300 <= status < 400` |
| 133 | `notion_sandbox_live.py:197` | and | not1 | KILLED | 25 | `test_live_client_reads_without_writing_and_redacts` | `type(status) is int and 300 <= status < 400` |
| 134 | `notion_sandbox_live.py:197` | and | not2 | KILLED | 2 | `test_redirect_is_not_followed` | `type(status) is int and 300 <= status < 400` |
| 135 | `notion_sandbox_live.py:220` | or | swap | KILLED | 1 | `test_non_string_bot_id_is_rejected` | `type(user_id) is not str or type(user_type) is not str` |
| 136 | `notion_sandbox_live.py:220` | or | not1 | KILLED | 19 | `test_live_client_reads_without_writing_and_redacts` | `type(user_id) is not str or type(user_type) is not str` |
| 137 | `notion_sandbox_live.py:220` | or | not2 | KILLED | 18 | `test_live_client_reads_without_writing_and_redacts` | `type(user_id) is not str or type(user_type) is not str` |
| 138 | `notion_sandbox_live.py:224` | and | swap | KILLED | 2 | `test_missing_workspace_id_writes_nothing` | `type(bot) is dict and type(bot.get("workspace_id")) is str` |
| 139 | `notion_sandbox_live.py:224` | and | not1 | KILLED | 8 | `test_live_client_reads_without_writing_and_redacts` | `type(bot) is dict and type(bot.get("workspace_id")) is str` |
| 140 | `notion_sandbox_live.py:224` | and | not2 | KILLED | 8 | `test_live_client_reads_without_writing_and_redacts` | `type(bot) is dict and type(bot.get("workspace_id")) is str` |
| 141 | `notion_sandbox_live.py:241` | or | swap | KILLED | 1 | `test_database_parent_and_missing_object_write_nothing` | `type(payload) is not dict or payload.get("object") != "page"` |
| 142 | `notion_sandbox_live.py:241` | or | not1 | KILLED | 26 | `test_live_client_reads_without_writing_and_redacts` | `type(payload) is not dict or payload.get("object") != "page"` |
| 143 | `notion_sandbox_live.py:241` | or | not2 | KILLED | 27 | `test_live_client_reads_without_writing_and_redacts` | `type(payload) is not dict or payload.get("object") != "page"` |
| 144 | `notion_sandbox_live.py:258` | and | swap | KILLED | 2 | `test_live_space_fallback_is_only_the_asserted_parent` | `space == "" and page_id == canonical_id(expected_id)` |
| 145 | `notion_sandbox_live.py:258` | and | not1 | KILLED | 8 | `test_live_client_reads_without_writing_and_redacts` | `space == "" and page_id == canonical_id(expected_id)` |
| 146 | `notion_sandbox_live.py:258` | and | not2 | KILLED | 8 | `test_live_client_reads_without_writing_and_redacts` | `space == "" and page_id == canonical_id(expected_id)` |
| 147 | `notion_sandbox_live.py:261` | or | swap | KILLED | 1 | `test_parse_page_keeps_a_url_and_fills_a_blank_one` | `type(url) is not str or url == ""` |
| 148 | `notion_sandbox_live.py:261` | or | not1 | KILLED | 1 | `test_parse_page_keeps_a_url_and_fills_a_blank_one` | `type(url) is not str or url == ""` |
| 149 | `notion_sandbox_live.py:261` | or | not2 | KILLED | 1 | `test_parse_page_keeps_a_url_and_fills_a_blank_one` | `type(url) is not str or url == ""` |
| 150 | `notion_sandbox_live.py:266` | or | swap | KILLED | 1 | `test_string_in_trash_is_rejected` | `archived_flag is None or alias_flag is None or trash_flag is None` |
| 151 | `notion_sandbox_live.py:266` | or | not1 | KILLED | 26 | `test_live_client_reads_without_writing_and_redacts` | `archived_flag is None or alias_flag is None or trash_flag is None` |
| 152 | `notion_sandbox_live.py:266` | or | not2 | KILLED | 26 | `test_live_client_reads_without_writing_and_redacts` | `archived_flag is None or alias_flag is None or trash_flag is None` |
| 153 | `notion_sandbox_live.py:266` | or | not3 | KILLED | 27 | `test_live_client_reads_without_writing_and_redacts` | `archived_flag is None or alias_flag is None or trash_flag is None` |
| 154 | `notion_sandbox_live.py:268` | or | swap | KILLED | 3 | `test_trashed_parent_writes_nothing[archived]` | `archived_flag or alias_flag or trash_flag` |
| 155 | `notion_sandbox_live.py:268` | or | not1 | KILLED | 7 | `test_trashed_parent_writes_nothing[archived]` | `archived_flag or alias_flag or trash_flag` |
| 156 | `notion_sandbox_live.py:268` | or | not2 | KILLED | 7 | `test_trashed_parent_writes_nothing[is_archived]` | `archived_flag or alias_flag or trash_flag` |
| 157 | `notion_sandbox_live.py:268` | or | not3 | KILLED | 7 | `test_trashed_parent_writes_nothing[in_trash]` | `archived_flag or alias_flag or trash_flag` |
| 158 | `notion_sandbox_live.py:283` | or | swap | KILLED | 20 | `test_live_client_reads_without_writing_and_redacts` | `type(value) is not str or value == ""` |
| 159 | `notion_sandbox_live.py:283` | or | not1 | KILLED | 25 | `test_live_client_reads_without_writing_and_redacts` | `type(value) is not str or value == ""` |
| 160 | `notion_sandbox_live.py:283` | or | not2 | KILLED | 5 | `test_doc_shaped_pages_execute_without_a_space` | `type(value) is not str or value == ""` |
| 161 | `notion_sandbox_live.py:315` | and | swap | KILLED | 1 | `test_proxy_map_drops_non_strings` | `type(key) is str and type(value) is str` |
| 162 | `notion_sandbox_live.py:315` | and | not1 | KILLED | 2 | `test_proxy_map_reads_string_proxy_entries` | `type(key) is str and type(value) is str` |
| 163 | `notion_sandbox_live.py:315` | and | not2 | KILLED | 2 | `test_proxy_map_reads_string_proxy_entries` | `type(key) is str and type(value) is str` |
| 164 | `notion_sandbox_live.py:324` | and | swap | KILLED | 1 | `test_explicit_space_skips_a_non_id` | `type(value) is str and canonical_id(value) != ""` |
| 165 | `notion_sandbox_live.py:324` | and | not1 | KILLED | 4 | `test_live_space_fallback_is_only_the_asserted_parent` | `type(value) is str and canonical_id(value) != ""` |
| 166 | `notion_sandbox_live.py:324` | and | not2 | KILLED | 4 | `test_live_space_fallback_is_only_the_asserted_parent` | `type(value) is str and canonical_id(value) != ""` |
| 167 | `notion_sandbox_pipeline.py:153` | or | swap | KILLED | 1 | `test_blank_id_already_recorded_is_kept` | `page_id == "" or page_id not in ctx.created_ids` |
| 168 | `notion_sandbox_pipeline.py:153` | or | not1 | KILLED | 1 | `timeout` | `page_id == "" or page_id not in ctx.created_ids` |
| 169 | `notion_sandbox_pipeline.py:153` | or | not2 | KILLED | 1 | `timeout` | `page_id == "" or page_id not in ctx.created_ids` |
| 170 | `notion_sandbox_pipeline.py:163` | and | swap | KILLED | 1 | `test_each_foreign_page_is_flagged` | `row.get("id") == page_id and row.get("reason") == reason` |
| 171 | `notion_sandbox_pipeline.py:163` | and | not1 | KILLED | 3 | `test_wrong_space_on_create_return_stops` | `row.get("id") == page_id and row.get("reason") == reason` |
| 172 | `notion_sandbox_pipeline.py:163` | and | not2 | KILLED | 3 | `test_wrong_space_on_create_return_stops` | `row.get("id") == page_id and row.get("reason") == reason` |
| 173 | `notion_sandbox_pipeline.py:169` | or | swap | KILLED | 25 | `test_execute_on_the_fake_adapter_writes_evidence` | `page_id == "" or page_id in ctx.created_ids` |
| 174 | `notion_sandbox_pipeline.py:169` | or | not1 | KILLED | 6 | `test_lying_create_id_stops_before_colours` | `page_id == "" or page_id in ctx.created_ids` |
| 175 | `notion_sandbox_pipeline.py:169` | or | not2 | KILLED | 31 | `test_execute_on_the_fake_adapter_writes_evidence` | `page_id == "" or page_id in ctx.created_ids` |
| 176 | `notion_sandbox_pipeline.py:181` | and | swap | KILLED | 1 | `test_the_same_unfresh_page_is_rejected_once` | `page_id != "" and all(row.get("id") != page_id for row in ctx.rejected_pages)` |
| 177 | `notion_sandbox_pipeline.py:181` | and | not1 | KILLED | 6 | `test_stale_foreign_page_is_not_a_parent` | `page_id != "" and all(row.get("id") != page_id for row in ctx.rejected_pages)` |
| 178 | `notion_sandbox_pipeline.py:181` | and | not2 | KILLED | 6 | `test_stale_foreign_page_is_not_a_parent` | `page_id != "" and all(row.get("id") != page_id for row in ctx.rejected_pages)` |
| 179 | `notion_sandbox_pipeline.py:203` | or | swap | KILLED | 1 | `test_later_create_returning_an_earlier_foreign_id_drops_it` | `page_id == "" or space_conflicts(page.space_id)` |
| 180 | `notion_sandbox_pipeline.py:203` | or | not1 | KILLED | 6 | `test_lying_create_id_stops_before_colours` | `page_id == "" or space_conflicts(page.space_id)` |
| 181 | `notion_sandbox_pipeline.py:203` | or | not2 | KILLED | 7 | `test_lying_create_id_stops_before_colours` | `page_id == "" or space_conflicts(page.space_id)` |
| 182 | `notion_sandbox_pipeline.py:207` | and | swap | EQUIVALENT | 0 |  | `space_conflicts(page.space_id) and page_id != ""` |
| 183 | `notion_sandbox_pipeline.py:207` | and | not1 | KILLED | 1 | `test_unbound_foreign_create_is_kept_and_flagged` | `space_conflicts(page.space_id) and page_id != ""` |
| 184 | `notion_sandbox_pipeline.py:207` | and | not2 | KILLED | 1 | `test_unbound_foreign_create_is_kept_and_flagged` | `space_conflicts(page.space_id) and page_id != ""` |
| 185 | `notion_sandbox_pipeline.py:234` | or | swap | KILLED | 1 | `test_sandbox_parent_in_a_foreign_space_fails_the_chain` | `space_conflicts(current.space_id) or current.archived` |
| 186 | `notion_sandbox_pipeline.py:234` | or | not1 | KILLED | 27 | `test_execute_on_the_fake_adapter_writes_evidence` | `space_conflicts(current.space_id) or current.archived` |
| 187 | `notion_sandbox_pipeline.py:234` | or | not2 | KILLED | 26 | `test_execute_on_the_fake_adapter_writes_evidence` | `space_conflicts(current.space_id) or current.archived` |
| 188 | `notion_sandbox_pipeline.py:239` | or | swap | KILLED | 2 | `test_empty_parent_chain_does_not_read_again` | `parent_id == "" or page_id == "" or page_id in seen` |
| 189 | `notion_sandbox_pipeline.py:239` | or | not1 | KILLED | 30 | `test_execute_on_the_fake_adapter_writes_evidence` | `parent_id == "" or page_id == "" or page_id in seen` |
| 190 | `notion_sandbox_pipeline.py:239` | or | not2 | KILLED | 28 | `test_execute_on_the_fake_adapter_writes_evidence` | `parent_id == "" or page_id == "" or page_id in seen` |
| 191 | `notion_sandbox_pipeline.py:239` | or | not3 | KILLED | 28 | `test_execute_on_the_fake_adapter_writes_evidence` | `parent_id == "" or page_id == "" or page_id in seen` |
| 192 | `notion_sandbox_pipeline.py:246` | or | swap | KILLED | 1 | `test_trashed_product_page_stops_further_writes` | `space_conflicts(current.space_id) or current.archived` |
| 193 | `notion_sandbox_pipeline.py:246` | or | not1 | KILLED | 26 | `test_execute_on_the_fake_adapter_writes_evidence` | `space_conflicts(current.space_id) or current.archived` |
| 194 | `notion_sandbox_pipeline.py:246` | or | not2 | KILLED | 26 | `test_execute_on_the_fake_adapter_writes_evidence` | `space_conflicts(current.space_id) or current.archived` |
| 195 | `notion_sandbox_pipeline.py:291` | or | swap | KILLED | 2 | `test_trashed_confirm_stops_further_writes` | `space_conflicts(confirmed.space_id) or confirmed.archived` |
| 196 | `notion_sandbox_pipeline.py:291` | or | not1 | KILLED | 30 | `test_execute_on_the_fake_adapter_writes_evidence` | `space_conflicts(confirmed.space_id) or confirmed.archived` |
| 197 | `notion_sandbox_pipeline.py:291` | or | not2 | KILLED | 30 | `test_execute_on_the_fake_adapter_writes_evidence` | `space_conflicts(confirmed.space_id) or confirmed.archived` |
| 198 | `notion_sandbox_pipeline.py:297` | and | swap | KILLED | 1 | `test_confirm_does_not_replace_a_different_tail` | `ctx.created and ctx.created[-1].get("id") == page_id` |
| 199 | `notion_sandbox_pipeline.py:297` | and | not1 | KILLED | 1 | `test_token_in_created_url_exits_70` | `ctx.created and ctx.created[-1].get("id") == page_id` |
| 200 | `notion_sandbox_pipeline.py:297` | and | not2 | KILLED | 2 | `test_token_in_created_url_exits_70` | `ctx.created and ctx.created[-1].get("id") == page_id` |
| 201 | `notion_sandbox_pipeline.py:327` | or | swap | KILLED | 1 | `test_variants_without_a_product_page_are_a_sandbox_error` | `ctx.probe is None or ctx.product_page_id is None or type(spec) is not ProductSpec` |
| 202 | `notion_sandbox_pipeline.py:327` | or | not1 | KILLED | 24 | `test_execute_on_the_fake_adapter_writes_evidence` | `ctx.probe is None or ctx.product_page_id is None or type(spec) is not ProductSpec` |
| 203 | `notion_sandbox_pipeline.py:327` | or | not2 | KILLED | 25 | `test_execute_on_the_fake_adapter_writes_evidence` | `ctx.probe is None or ctx.product_page_id is None or type(spec) is not ProductSpec` |
| 204 | `notion_sandbox_pipeline.py:327` | or | not3 | KILLED | 24 | `test_execute_on_the_fake_adapter_writes_evidence` | `ctx.probe is None or ctx.product_page_id is None or type(spec) is not ProductSpec` |

# Implementation Log

## 2026-10-09 — Session 07 W11: QA coverage matrix and crash-resume repairs

Session 07 stays incomplete. This wave is not SESSION_07 COMPLETE. Round 2 merges `6575c567` (#60, revision 59) and takes revision 60. STATE `head_sha` is `6575c567fcadde636846131f98d7599067babb66`. It is the tip-sync pointer. It is not this commit. `current_session` stays 7. `completed_sessions` stays `[0, 1, 2, 3, 4, 5, 6]`. `next_session` stays 7. `next_prompt` stays `10_SESSION_07_PRODUCT_BUILD_VARIANTS_AND_QA.md`. `evidence_closure_commit_sha` stays `0f94d585f23d79e5ac18479f01e14f67cbaad332`. `last_verified_commit` stays bootstrap. Twelve session 7 evidence keys stay false. A07, A08, and A09 stay DESIGNED. `commissioned_agents` stays empty. Exit 78 stays HELD. Narrative `next_phase` stays `test_matrix` and is not started.

Prompt integrity is the Wave 11 addendum in `docs/control/reviews/2026-10-05-session-07-prompt-integrity.md`. The prompt file is unchanged. SHA-256 `d52011a6f0b725b16427629dc664cfc9f3432c4b5f71d26ce032d4b6c8ecb39d`.

Fixtures only. No live Notion, no Etsy, no `--execute`.

- Home contracts. `_linked_views` (`notion_qa.py:481`) also requires one home Today/Tasks view, one Quick notes/Notes view, and one Month/Events view when Events is a stored kind (`_home_linked_views` at `:495`). `_palette` (`:764`) requires one home callout per palette token. `_teardown` (`:806`) requires the home nav text, one identity callout, and one hub return text per hub. Deleting any one of those records `BLOCKED`, empty repairs, empty proof, and 0 adapter writes. `test_deleted_home_contract_is_blocked` is 14 cases.
- Crash-resume. `record_applied_repairs` (`notion_progress.py:361`) appends kind `qa_repair`, operation `qa.repair`, phase `qa`, before the QA checkpoint write. `run_product_qa` stores the union of those names and the repairs this run applied. `test_crash_resume_keeps_the_earlier_repair_job` crashes `notion_qa.write_checkpoint` after the publish repair and requires the `published` job before resume. Resume stays `PASS` with repairs `("published",)` and the same one job.
- Local bugs. `_local_bug` (`notion_qa.py:207`) is any in-package `Exception` except `ProviderFailure`. The fixed `_CODE_ERRORS` tuple is gone. `test_package_error_outside_the_old_fixed_set_is_local` raises `ValueError` and `RuntimeError` from a frame named as this package. A provider `TypeError` is still one provider job.
- On `4b899fcf`, with these tests and the W10 sources, those 17 tests failed: 14 verdicts were `PASS`, the crash left `repair_jobs` `[]`, and both package errors were `provider operation failed`. On this tree the same 17 passed.

`from None` at `notion_fact_ledger.py:254` and `notion_qa.py:189` is closed. It is killed by `test_interrupt_keeps_its_kind_and_drops_the_secret` (`__suppress_context__ is True` at line 4561) and `test_provider_interrupt_in_qa_becomes_its_built_in_base` (line 2547). Those assertions pass on `4b899fcf` because `from None` is already there.

Round 2 stores each repair inside `_apply_repairs` as soon as that adapter call returns, before the next repair. `test_crash_between_repairs_keeps_the_published_job` publishes, then `set_duplicate_as_template` raises `ConnectionError`. The stored `qa_repair` jobs are `published` before resume, and the resume still lists `published`. On `4b899fcf` those jobs were `[]`.

Hand mutants, one pytest each, then the file restored. No sweep.

- `test_generator_exit_subclass_becomes_the_builtin` kills `notion_progress.py:182` `return type(error)()`. The type was `sk-live-secret`, not `GeneratorExit`.
- `test_system_exit_drops_an_int_subclass_code` kills `notion_progress.py:185` `isinstance(code, int)`. The code type was `_SecretCode`, not `int`.
- `test_exception_group_of_only_exceptions_is_a_local_read_failure` kills `notion_fact_ledger.py:243` with `ExceptionGroup` added to the provider tuple (`provider read failed`) and `:245` re-raising the group (`ExceptionGroup: sk-live-secret`).

Those three pins passed on the `4b899fcf` sources and on this tip. They are not fail-on-base tests.

Parked: `notion_qa.py:143` and `:154` operand survivors, six equivalents. `_prose_digest` join collision and query-string forms. D-0029 QA-rerun limit on a caller mismatch.

Verification on this tip: `uv run pytest -q --tb=line` was 12 failed, 3236 passed, 193 skipped, 1 warning, 363.34s. The 12 failures are `test_compose_preserves_the_postgres_password` with `FileNotFoundError` because `docker` is absent. `uv run ruff format --check .` exit 0, 336 files already formatted. `uv run ruff check .` exit 0. `uv run pyright` 1.1.411 strict, 0 errors, 0 warnings, 0 informations.

## 2026-10-07 — Session 07 sandbox run, round 3

Not a session close. This is not SESSION_07 COMPLETE. `state_revision` stays 58. `IMPLEMENTATION_STATE.json` is not edited. `head_sha` stays the W9 squash `a4e9b025021b4effbb2b2879c1db756403cb1676`. Twelve session 7 evidence keys stay false. `commissioned_agents` stays empty. Exit 78 stays HELD. The §11 sandbox CLI is still not run live. This commit's CI run is not invented here.

The runner is `python -m money_machine.cli.notion_sandbox`. A page with an empty space is accepted when `/v1/users/me` `bot.workspace_id` is `89282fb0-af94-8106-809e-0003c027fa07` and the parent chain reaches `3ed82fb0-af94-80dc-8272-f40b16376b81`. An explicit different space is refused and that page is left out of `created_pages`. An archived confirm or an archived chain read is refused the same way. A later failure of any other kind keeps the id. The id is appended inside `create_child_page` as soon as the create response parses, before confirm and before the chain read. `SANDBOX_SPACE_ID` is not stamped onto created pages. `target_ok` refuses `database_id` and `data_source_id`. `write_counts` is `{"fixture": {...}, "live": {"create_child_page": n}}`. `get_public_url` is in neither section.

Census method: one AST walk of `notion_sandbox.py`, `notion_sandbox_guard.py`, `notion_sandbox_live.py`, and `notion_sandbox_pipeline.py`, in source order. It counts `ast.If`, `ast.BoolOp` (`ast.And` / `ast.Or`, and each clause in `values`), `ast.IfExp`, and `ast.While`. Result: if 133, boolop 52, and 20, or 32, clause 116, ifexp 11, while 2. The if-flip table is one row per `if` (133). The operand table is one operator swap per boolop plus one negation per clause (52 + 116 = 168).

If-flip, after the killing tests. 133 rows. 133 killed. 0 equivalent. The Failed column sums to 4364. A row is killed only when that run's pytest exit is non-zero. When the exit is non-zero and the output has neither a `failed` count nor an `error` count, the Failed count is 1. That is `__name__ == "__main__"`, if-flip row 27, `notion_sandbox.py:595`, Failed 1: the flip runs `main` at import and pytest exits 3 during collection. T45 is row 55, `notion_sandbox_guard.py:304`, the second `if leaks(text, token)` inside `render_evidence`, KILLED, Failed 1. Row 54 is the first leaks check, Failed 104. The earlier 104-row sum 2109 was measured on `df5413ac`, where this tree's extra `if`s did not exist.

Force-true: 133 rows, 128 killed, 5 equivalent, Failed sum 3894. Force-false: 133 rows, 125 killed, 8 equivalent, Failed sum 629. Boolean operands: 168 rows, 162 killed, 6 equivalent, Failed sum 4460.

Equivalent rows, each probe-backed. Both versions of a refusal produce the same exit and write nothing. None of them accepts a bad build.

- `notion_sandbox.py:140` force-false, `runner is None`. The only registry names with a runner are `run_build` and `run_variants`, and those are the keys of `stage_runners()`. The branch does not run. `test_execute_on_the_fake_adapter_writes_evidence` reaches both runners and exits 0.
- `notion_sandbox_guard.py:222` force-true, `encoded != token`. The url form replaces `_` with `%5F`, so it differs from a shaped token and the append already runs. `test_encoded_token_is_redacted_from_info_logs`.
- `notion_sandbox_guard.py:224` force-true, and the `and`→`or` swap. The base64 digest of a shaped token is a different string from the token and from the url form, so the append already runs. `test_base64_token_in_evidence_exits_70` exits 70.
- `notion_sandbox_guard.py:235` force-true, `form in cleaned`. `str.replace` of a missing substring leaves the text unchanged.
- `notion_sandbox_guard.py:304` force-false, the second `leaks(text, token)`. The first redact has already removed the shaped token, so the body does not run. The if-flip of this same `if` is T45, Failed 1. `test_failed_redaction_exits_70` keeps `bot_user_id` as `[REDACTED]`.
- `notion_sandbox_guard.py:323` force-false, and the `or`→`and` swap, `str(path) == "" or path == Path() or under_proc(path)`. `/proc` still fails the following `lstat` (`info is not None`) with exit 64 and no file. `test_proc_path_is_refused_before_open`. `test_proc_path_helper_rejects_proc_itself` pins `under_proc` itself.
- `notion_sandbox_guard.py:331` force-false, `info is not None`. An existing file still fails `os.open` with `O_EXCL`. `test_evidence_refuses_existing_file_and_symlink` keeps the original bytes and exits 64.
- `notion_sandbox_guard.py:338` `or`→`and`, `S_ISLNK(parent) or not S_ISDIR(parent)`. A symlink is not a directory under `lstat`, so both operands are true together and the refusal stays. `test_symlinked_parent_directory_is_refused` exits 64 with 0 reads.
- `notion_sandbox_guard.py:340` force-false, the unwritable-mode check. `os.open` still returns `EACCES` and exit 64. `test_unwritable_directory_writes_nothing`.
- `notion_sandbox_guard.py:388` force-false, `S_ISLNK` on the evidence path. `lstat` of a replaced path has a different inode from the open fd, so `_same_inode` already returns false. `test_swapped_evidence_file_does_not_exit_ok` and `test_commit_evidence_rejects_a_replaced_inode` exit 69.
- `notion_sandbox_guard.py:459` force-true, and the `and`→`or` swap. This is the cwd walk. The file-parent walk returns the checkout first, so the cwd walk does not run. The file-parent copy at `:455` is killed: `test_repo_root_ignores_a_partial_marker` (swap) and `test_repo_root_needs_both_markers` (each operand). `test_repo_root_falls_back_to_cwd` kills both operands of `:459`.
- `notion_sandbox_pipeline.py:146` force-false, and the `or`→`and` swap, `page_id == "" or space_conflicts(page.space_id)` inside `_align`. `create_under` repeats the empty-id refusal at `:202` and the explicit-space refusal at `:207`. `test_wrong_space_on_create_return_stops` exits 69, build `FAILED`, `created_pages` `[]`, one create.
- `notion_sandbox_pipeline.py:223` force-true, and the `and`→`or` swap, `ctx.created and ctx.created[-1].get("id") == page_id`. A create that reaches this line has just been appended, so it is the tail. The two operators agree, and force-true updates that same tail. `test_execute_on_the_fake_adapter_writes_evidence` records five distinct ids. Both operand negations are killed (Failed 1).
- `notion_sandbox_pipeline.py:245` force-false, `type(spec) is not ProductSpec`. The condition is false on the `ProductSpec` the CLI builds. A stand-in object fails inside `build_top_level_page_and_design_shell` with `phase 1 requires a validated ProductSpec` before this `if`, with 0 creates.

`tests/unit/cli/test_notion_sandbox.py`: 185 passed. With `tests/unit/integrations/notion/test_router.py` the router export is included. Sockets stay blocked. `ruff format --check`, `ruff check`, and `pyright` 1.1.411 are clean on the four sandbox modules and the sandbox test. Full local pytest: 2705 collected, 2500 passed, 193 skipped, 12 failed. All 12 failures are `test_compose_preserves_the_postgres_password` with `FileNotFoundError` because the `docker` binary is absent. They are local-only. One `StarletteDeprecationWarning` comes from FastAPI's test client. The sandbox modules do not import Starlette. CI is the gate.

Blocker to test.

- Reviewer B1, doc-shaped execute: `test_doc_shaped_pages_execute_without_a_space` (exit 0, five creates). One failed confirm still records the id: `test_doc_shaped_failure_still_records_the_created_id` (exit 69, one id). `python -m`: `test_module_entry_point_runs_main`.
- Explicit space refused and omitted: `test_wrong_space_on_create_return_stops` (build `FAILED`, `created_pages` `[]`). Archived confirm omitted: `test_trashed_confirm_stops_further_writes`. Archived chain read omitted: `test_trashed_product_page_stops_further_writes`. Empty space on the parent page is filled only for that page: `test_live_space_fallback_is_only_the_asserted_parent` and `test_parse_page_fallback_does_not_fill_a_different_page`.
- V-B1: the if-flip Failed sum above is 4364, and row 27 counts the collection error as Failed 1.
- V-B2, atomic record: `test_interrupt_after_store_records_the_created_id` and `test_doc_shaped_interrupt_after_store_records_the_created_id` interrupt after the create is stored, at indexes 0, 2, and 4, on both fakes. Recorded ids equal created ids. Exit 69, `INTERRUPTED`, token absent. `test_interrupt_writes_redacted_evidence` still raises before the adapter stores the third create.
- V-B3 operands. Evidence path with a base64 or url-encoded token: `test_encoded_token_evidence_path_writes_nothing` (exit 64, no file). Wrong-space ancestor: `test_wrong_space_ancestor_is_not_appended`. Archived or wrong-space re-read: `test_space_only_reread_is_not_appended` and `test_trashed_confirm_stops_further_writes`. Parent-only lie keeps the id: `test_parent_only_reread_stops_without_a_space_lie`. Sandbox parent in a foreign space: `test_sandbox_parent_in_a_foreign_space_fails_the_chain`. `qa_verdict` on a build-only `PASS`: `test_token_env_and_redaction_units`. String `state_revision`: `test_string_revision_is_unreadable` (exit 69, 0 reads). Both repo markers: `test_repo_root_needs_both_markers`. `SystemExit` normalisation: `test_system_exit_status_is_normalized`. Naive clock: `test_naive_clock_is_refused` (exit 69, 0 reads). `--evidence-out` without a value: `test_evidence_out_without_a_value_is_usage`. Non-string bot id: `test_non_string_bot_id_is_rejected` (exit 69, log stays `notion api error`). Missing `bot` object: `test_bot_payload_without_a_bot_object_exits_65` (exit 65, GET GET, 0 POST). Integer proxy value: `test_proxy_map_drops_non_strings`. `explicit_space` of `"nope"`: `test_explicit_space_skips_a_non_id`. Variants without a product page: `test_variants_without_a_product_page_are_a_sandbox_error`.
- Verifier should-fixes. `under_proc(/proc)` and `under_proc(/proc/self)`: `test_proc_path_helper_rejects_proc_itself`. Empty parent chain reads nothing: `test_empty_parent_chain_does_not_read_again`. Confirm that lies about the parent id only: `test_parent_only_reread_stops_without_a_space_lie` (id kept, one create). Fallback widening: `test_parse_page_fallback_does_not_fill_a_different_page`. Read-path `BaseException`: `test_read_base_exceptions_stay_redacted` (exit 69, `notion api error`, evidence written, token absent).
- Reviewer should-fixes. Redirect: `test_redirect_is_not_followed` and `test_redirect_code_is_refused_without_a_status`. `SSL_CERT_FILE` / `SSL_CERT_DIR`: `test_ssl_env_is_refused_and_ignored` (exit 64, 0 reads). ENOSPC prints the ids: `test_enospc_after_creates_prints_ids`. A 0-byte `os.write` exits 69: `test_zero_length_write_exits_69`. Short write stays complete: `test_short_evidence_write_is_complete`. Swapped inode: `test_swapped_evidence_file_does_not_exit_ok`. Freshness: `test_stale_foreign_page_is_not_a_parent`, `test_stale_confirm_stops_later_writes`, `test_missing_created_time_is_not_new`, `test_naive_created_time_is_not_new`. Missing workspace exits 65: `test_missing_workspace_id_writes_nothing`. Base64 in the evidence body exits 70: `test_base64_token_in_evidence_exits_70`. Chain trash stops at two creates: `test_trashed_product_page_stops_further_writes`. Symlinked parent directory: `test_symlinked_parent_directory_is_refused`. Mode 0600 is `os.fchmod` inside `open_evidence` and `commit_evidence`. A successful run is not `INTERRUPTED`: `test_execute_on_the_fake_adapter_writes_evidence`. Non-string bot user id is omitted on a dry-run: `test_non_string_bot_user_id_is_omitted`. `data_source_id`: `test_data_source_parent_writes_nothing`.
- Nits. Control JSON that is a list or a string: `test_control_state_container_exits_69`. `/dev/full` and a non-ASCII path: `test_stdout_full_and_non_ascii_path_are_documented`. Router export: `test_package_exports_the_router`. The expected state revision is read from `docs/control/IMPLEMENTATION_STATE.json` inside the sandbox test. Product-builder tests that pin `a4e9b025` and revision 58 are unchanged.

## If-flip

| # | Site | Result | Failed | Test | Condition |
|---|---|---|---|---|---|
| 1 | `notion_sandbox.py:115` | KILLED | 3 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `runner_name is None` |
| 2 | `notion_sandbox.py:136` | KILLED | 29 | `test_execute_on_the_fake_adapter_writes_evidence` | `not available or failed` |
| 3 | `notion_sandbox.py:140` | KILLED | 29 | `test_execute_on_the_fake_adapter_writes_evidence` | `runner is None` |
| 4 | `notion_sandbox.py:177` | KILLED | 58 | `test_missing_token_ignores_other_sources` | `arg == "--evidence-out" and index + 1 < len(argv)` |
| 5 | `notion_sandbox.py:179` | KILLED | 3 | `test_abbreviations_are_refused` | `arg.startswith("--evidence-out=")` |
| 6 | `notion_sandbox.py:196` | KILLED | 120 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `type(moment) is not datetime or moment.tzinfo is None` |
| 7 | `notion_sandbox.py:202` | KILLED | 57 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `token is not None and token_shape_ok(token)` |
| 8 | `notion_sandbox.py:295` | KILLED | 91 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `argv_names_a_target(arguments) or environ_names_a_target(env) or cert_env_set(env)` |
| 9 | `notion_sandbox.py:302` | KILLED | 73 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `str(evidence) == "" or leaks(str(evidence), secret)` |
| 10 | `notion_sandbox.py:305` | KILLED | 59 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `parsed.execute and parsed.dry_run` |
| 11 | `notion_sandbox.py:310` | KILLED | 58 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `token is None` |
| 12 | `notion_sandbox.py:322` | KILLED | 56 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `secret is None` |
| 13 | `notion_sandbox.py:376` | KILLED | 47 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `type(bot.user_type) is not str` |
| 14 | `notion_sandbox.py:394` | KILLED | 44 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `not target_ok(bot, page)` |
| 15 | `notion_sandbox.py:412` | KILLED | 35 | `test_dry_run_is_the_default_and_writes_nothing` | `mode == "dry-run"` |
| 16 | `notion_sandbox.py:446` | KILLED | 27 | `test_execute_on_the_fake_adapter_writes_evidence` | `interrupted` |
| 17 | `notion_sandbox.py:450` | KILLED | 20 | `test_execute_on_the_fake_adapter_writes_evidence` | `failed` |
| 18 | `notion_sandbox.py:479` | KILLED | 7 | `test_interrupt_after_store_records_the_created_id[0-exc0]` | `bind is None` |
| 19 | `notion_sandbox.py:485` | KILLED | 21 | `test_execute_on_the_fake_adapter_writes_evidence` | `type(bot.user_id) is str` |
| 20 | `notion_sandbox.py:520` | KILLED | 8 | `test_token_in_error_is_redacted` | `error is not None` |
| 21 | `notion_sandbox.py:522` | KILLED | 9 | `test_execute_on_the_fake_adapter_writes_evidence` | `any(stage.get("status") == "INTERRUPTED" for stage in stages)` |
| 22 | `notion_sandbox.py:525` | KILLED | 102 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `check == "FAIL"` |
| 23 | `notion_sandbox.py:527` | KILLED | 98 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `code == EXIT_OK` |
| 24 | `notion_sandbox.py:572` | KILLED | 34 | `test_override_env_refuses[-NOTION_CONFIG]` | `path is not None and str(path) != "" and not leaks(str(path), token)` |
| 25 | `notion_sandbox.py:579` | KILLED | 2 | `test_system_exit_status_is_normalized` | `isinstance(exc, SystemExit)` |
| 26 | `notion_sandbox.py:582` | KILLED | 1 | `test_reraise_preserves_interrupt_and_base_exceptions` | `isinstance(exc, KeyboardInterrupt)` |
| 27 | `notion_sandbox.py:595` | KILLED | 1 | `(collection error)` | `__name__ == "__main__"` |
| 28 | `notion_sandbox_guard.py:144` | KILLED | 65 | `test_canonical_id_normalizes_and_rejects` | `type(value) is not str` |
| 29 | `notion_sandbox_guard.py:147` | KILLED | 65 | `test_canonical_id_normalizes_and_rejects` | `len(compact) != 32` |
| 30 | `notion_sandbox_guard.py:149` | KILLED | 65 | `test_canonical_id_normalizes_and_rejects` | `any(character not in "0123456789abcdef" for character in compact)` |
| 31 | `notion_sandbox_guard.py:156` | KILLED | 36 | `test_target_and_parent_guards` | `type(bot.user_type) is not str or bot.user_type != "bot"` |
| 32 | `notion_sandbox_guard.py:158` | KILLED | 40 | `test_target_and_parent_guards` | `page.archived or page.parent_type in {"database_id", "data_source_id"}` |
| 33 | `notion_sandbox_guard.py:160` | KILLED | 36 | `test_target_and_parent_guards` | `canonical_id(bot.space_id) != SANDBOX_SPACE_ID` |
| 34 | `notion_sandbox_guard.py:162` | KILLED | 35 | `test_target_and_parent_guards` | `canonical_id(page.page_id) != SANDBOX_PARENT_PAGE_ID` |
| 35 | `notion_sandbox_guard.py:170` | KILLED | 38 | `test_target_and_parent_guards` | `candidate == ""` |
| 36 | `notion_sandbox_guard.py:178` | KILLED | 58 | `test_token_env_and_redaction_units` | `type(value) is not str or value == ""` |
| 37 | `notion_sandbox_guard.py:203` | KILLED | 69 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `head in _OVERRIDE_FLAGS` |
| 38 | `notion_sandbox_guard.py:205` | KILLED | 58 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `contains_secret_shape(arg)` |
| 39 | `notion_sandbox_guard.py:217` | KILLED | 117 | `test_token_env_and_redaction_units` | `token is None or not token_shape_ok(token)` |
| 40 | `notion_sandbox_guard.py:222` | KILLED | 3 | `test_token_env_and_redaction_units` | `encoded != token` |
| 41 | `notion_sandbox_guard.py:224` | KILLED | 4 | `test_token_env_and_redaction_units` | `digest not in forms and digest != token` |
| 42 | `notion_sandbox_guard.py:232` | KILLED | 116 | `test_token_env_and_redaction_units` | `token is not None and token != "" and not _unsafe_exact(token) and token in cleaned` |
| 43 | `notion_sandbox_guard.py:235` | KILLED | 2 | `test_token_env_and_redaction_units` | `form in cleaned` |
| 44 | `notion_sandbox_guard.py:242` | KILLED | 20 | `test_target_and_parent_guards` | `runner_name is None` |
| 45 | `notion_sandbox_guard.py:244` | KILLED | 20 | `test_target_and_parent_guards` | `outcome == "PASS"` |
| 46 | `notion_sandbox_guard.py:246` | KILLED | 8 | `test_target_and_parent_guards` | `outcome == "FAILED"` |
| 47 | `notion_sandbox_guard.py:248` | KILLED | 3 | `test_target_and_parent_guards` | `outcome == "BLOCKED"` |
| 48 | `notion_sandbox_guard.py:263` | KILLED | 1 | `test_token_env_and_redaction_units` | `stage.get("name") == "qa" and type(found) is str` |
| 49 | `notion_sandbox_guard.py:265` | KILLED | 6 | `test_token_env_and_redaction_units` | `status == "PASS"` |
| 50 | `notion_sandbox_guard.py:267` | KILLED | 6 | `test_token_env_and_redaction_units` | `status == "FAILED"` |
| 51 | `notion_sandbox_guard.py:269` | KILLED | 6 | `test_token_env_and_redaction_units` | `status == "BLOCKED"` |
| 52 | `notion_sandbox_guard.py:283` | KILLED | 111 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `token is not None and token != "" and not _unsafe_exact(token) and token in text` |
| 53 | `notion_sandbox_guard.py:285` | KILLED | 112 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `any(form in text for form in _encoded_forms(token))` |
| 54 | `notion_sandbox_guard.py:300` | KILLED | 104 | `test_write_evidence_redacts_a_planted_token` | `leaks(text, token)` |
| 55 | `notion_sandbox_guard.py:304` | KILLED | 1 | `test_failed_redaction_exits_70` | `leaks(text, token)` |
| 56 | `notion_sandbox_guard.py:323` | KILLED | 109 | `test_write_evidence_redacts_a_planted_token` | `str(path) == "" or path == Path() or under_proc(path)` |
| 57 | `notion_sandbox_guard.py:331` | KILLED | 109 | `test_write_evidence_redacts_a_planted_token` | `info is not None` |
| 58 | `notion_sandbox_guard.py:338` | KILLED | 110 | `test_write_evidence_redacts_a_planted_token` | `stat.S_ISLNK(parent_info.st_mode) or not stat.S_ISDIR(parent_info.st_mode)` |
| 59 | `notion_sandbox_guard.py:340` | KILLED | 109 | `test_write_evidence_redacts_a_planted_token` | `parent_info.st_mode & 0o200 == 0` |
| 60 | `notion_sandbox_guard.py:361` | KILLED | 2 | `test_enospc_after_creates_prints_ids` | `type(found) is not list` |
| 61 | `notion_sandbox_guard.py:365` | KILLED | 2 | `test_enospc_after_creates_prints_ids` | `type(item) is not dict` |
| 62 | `notion_sandbox_guard.py:368` | KILLED | 2 | `test_enospc_after_creates_prints_ids` | `type(page_id) is str and page_id != ""` |
| 63 | `notion_sandbox_guard.py:377` | KILLED | 1 | `timeout` | `written <= 0 or written > len(pending)` |
| 64 | `notion_sandbox_guard.py:388` | KILLED | 103 | `test_write_evidence_redacts_a_planted_token` | `stat.S_ISLNK(current.st_mode)` |
| 65 | `notion_sandbox_guard.py:404` | KILLED | 105 | `test_write_evidence_redacts_a_planted_token` | `not _same_inode(fd, path)` |
| 66 | `notion_sandbox_guard.py:409` | KILLED | 3 | `test_evidence_write_oserror_is_redacted` | `exc.errno in {errno.ENOSPC, errno.EIO}` |
| 67 | `notion_sandbox_guard.py:455` | KILLED | 117 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `(candidate / "pyproject.toml").is_file() and (candidate / "docs" / "control").is_dir()` |
| 68 | `notion_sandbox_guard.py:459` | KILLED | 1 | `test_repo_root_falls_back_to_cwd` | `(candidate / "pyproject.toml").is_file() and (candidate / "docs" / "control").is_dir()` |
| 69 | `notion_sandbox_guard.py:477` | KILLED | 117 | `test_git_sha_rejects_a_bad_rev_parse` | `completed.returncode != 0 or len(sha) != 40` |
| 70 | `notion_sandbox_guard.py:479` | KILLED | 116 | `test_git_sha_rejects_a_bad_rev_parse` | `any(character not in "0123456789abcdef" for character in sha)` |
| 71 | `notion_sandbox_guard.py:491` | KILLED | 114 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `type(payload) is not dict` |
| 72 | `notion_sandbox_guard.py:496` | KILLED | 114 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `type(revision) is not int or type(session) is not int or type(head) is not str` |
| 73 | `notion_sandbox_live.py:118` | KILLED | 17 | `test_live_client_reads_without_writing_and_redacts` | `bot is None` |
| 74 | `notion_sandbox_live.py:125` | KILLED | 17 | `test_live_client_reads_without_writing_and_redacts` | `expected == ""` |
| 75 | `notion_sandbox_live.py:130` | KILLED | 16 | `test_live_client_reads_without_writing_and_redacts` | `page is None` |
| 76 | `notion_sandbox_live.py:137` | KILLED | 10 | `test_live_client_reads_without_writing_and_redacts` | `not parent_is_allowed(parent, allowed)` |
| 77 | `notion_sandbox_live.py:148` | KILLED | 10 | `test_live_child_page_does_not_count_its_own_write` | `type(sent_parent) is not dict or sent_parent.get("page_id") != parent or sent_parent.get("type") != "page_id"` |
| 78 | `notion_sandbox_live.py:156` | KILLED | 9 | `test_live_child_page_does_not_count_its_own_write` | `page is None` |
| 79 | `notion_sandbox_live.py:164` | KILLED | 6 | `test_doc_shaped_pages_execute_without_a_space` | `page_id == "" or space_conflicts(page.space_id)` |
| 80 | `notion_sandbox_live.py:166` | KILLED | 4 | `test_doc_shaped_pages_execute_without_a_space` | `page_id not in self._created_ids` |
| 81 | `notion_sandbox_live.py:170` | KILLED | 5 | `test_live_child_page_does_not_count_its_own_write` | `evidence_ids is None or evidence_rows is None or page_id in evidence_ids` |
| 82 | `notion_sandbox_live.py:179` | KILLED | 22 | `test_live_client_reads_without_writing_and_redacts` | `leaks(url, self._token) or leaks(url.replace("-", ""), self._token)` |
| 83 | `notion_sandbox_live.py:185` | KILLED | 2 | `test_live_client_reads_without_writing_and_redacts` | `body is not None` |
| 84 | `notion_sandbox_live.py:190` | KILLED | 2 | `test_redirect_is_not_followed` | `type(status) is not int` |
| 85 | `notion_sandbox_live.py:192` | KILLED | 21 | `test_live_client_reads_without_writing_and_redacts` | `type(status) is int and 300 <= status < 400` |
| 86 | `notion_sandbox_live.py:201` | KILLED | 20 | `test_live_client_reads_without_writing_and_redacts` | `type(raw) is not bytes` |
| 87 | `notion_sandbox_live.py:211` | KILLED | 17 | `test_live_client_reads_without_writing_and_redacts` | `type(payload) is not dict` |
| 88 | `notion_sandbox_live.py:215` | KILLED | 17 | `test_live_client_reads_without_writing_and_redacts` | `type(user_id) is not str or type(user_type) is not str` |
| 89 | `notion_sandbox_live.py:219` | KILLED | 8 | `test_live_client_reads_without_writing_and_redacts` | `type(bot) is dict and type(bot.get("workspace_id")) is str` |
| 90 | `notion_sandbox_live.py:226` | KILLED | 19 | `test_live_client_reads_without_writing_and_redacts` | `key not in payload` |
| 91 | `notion_sandbox_live.py:229` | KILLED | 8 | `test_trashed_parent_writes_nothing[archived]` | `type(value) is not bool` |
| 92 | `notion_sandbox_live.py:236` | KILLED | 25 | `test_live_client_reads_without_writing_and_redacts` | `type(payload) is not dict or payload.get("object") != "page"` |
| 93 | `notion_sandbox_live.py:239` | KILLED | 25 | `test_live_client_reads_without_writing_and_redacts` | `page_id == ""` |
| 94 | `notion_sandbox_live.py:245` | KILLED | 10 | `test_live_child_page_does_not_count_its_own_write` | `type(parent) is dict` |
| 95 | `notion_sandbox_live.py:246` | KILLED | 3 | `test_live_space_fallback_is_only_the_asserted_parent` | `space == ""` |
| 96 | `notion_sandbox_live.py:249` | KILLED | 4 | `test_database_id_parent_is_not_a_page_parent` | `type(found_type) is str` |
| 97 | `notion_sandbox_live.py:251` | KILLED | 6 | `test_live_child_page_does_not_count_its_own_write` | `found_type == "page_id"` |
| 98 | `notion_sandbox_live.py:253` | KILLED | 10 | `test_live_client_reads_without_writing_and_redacts` | `space == "" and page_id == canonical_id(expected_id)` |
| 99 | `notion_sandbox_live.py:256` | KILLED | 1 | `test_parse_page_keeps_a_url_and_fills_a_blank_one` | `type(url) is not str or url == ""` |
| 100 | `notion_sandbox_live.py:260` | KILLED | 25 | `test_live_client_reads_without_writing_and_redacts` | `archived_flag is None or trash_flag is None` |
| 101 | `notion_sandbox_live.py:277` | KILLED | 22 | `test_live_client_reads_without_writing_and_redacts` | `type(value) is not str or value == ""` |
| 102 | `notion_sandbox_live.py:283` | KILLED | 4 | `test_doc_shaped_pages_execute_without_a_space` | `parsed.tzinfo is None` |
| 103 | `notion_sandbox_live.py:290` | KILLED | 21 | `test_live_client_reads_without_writing_and_redacts` | `type(actor) is not dict` |
| 104 | `notion_sandbox_live.py:293` | KILLED | 4 | `test_doc_shaped_pages_execute_without_a_space` | `type(found) is not str` |
| 105 | `notion_sandbox_live.py:301` | KILLED | 3 | `test_proxy_map_reads_string_proxy_entries` | `type(handlers) is not list` |
| 106 | `notion_sandbox_live.py:304` | KILLED | 3 | `test_proxy_map_reads_string_proxy_entries` | `isinstance(handler, urllib.request.ProxyHandler)` |
| 107 | `notion_sandbox_live.py:306` | KILLED | 3 | `test_proxy_map_reads_string_proxy_entries` | `type(found) is not dict` |
| 108 | `notion_sandbox_live.py:309` | KILLED | 2 | `test_proxy_map_reads_string_proxy_entries` | `type(key) is str and type(value) is str` |
| 109 | `notion_sandbox_live.py:318` | KILLED | 4 | `test_live_space_fallback_is_only_the_asserted_parent` | `type(value) is str and canonical_id(value) != ""` |
| 110 | `notion_sandbox_pipeline.py:133` | KILLED | 1 | `timeout` | `page_id in ctx.created_ids` |
| 111 | `notion_sandbox_pipeline.py:143` | KILLED | 6 | `test_lying_create_id_stops_before_colours` | `tail == page_id` |
| 112 | `notion_sandbox_pipeline.py:146` | KILLED | 21 | `test_execute_on_the_fake_adapter_writes_evidence` | `page_id == "" or space_conflicts(page.space_id)` |
| 113 | `notion_sandbox_pipeline.py:149` | KILLED | 16 | `test_execute_on_the_fake_adapter_writes_evidence` | `page_id not in ctx.created_ids` |
| 114 | `notion_sandbox_pipeline.py:158` | KILLED | 19 | `test_execute_on_the_fake_adapter_writes_evidence` | `page.created_by != ctx.bot_user_id` |
| 115 | `notion_sandbox_pipeline.py:161` | KILLED | 20 | `test_execute_on_the_fake_adapter_writes_evidence` | `moment is None` |
| 116 | `notion_sandbox_pipeline.py:163` | KILLED | 20 | `test_execute_on_the_fake_adapter_writes_evidence` | `moment.tzinfo is None` |
| 117 | `notion_sandbox_pipeline.py:165` | KILLED | 19 | `test_execute_on_the_fake_adapter_writes_evidence` | `moment < ctx.moment` |
| 118 | `notion_sandbox_pipeline.py:175` | KILLED | 4 | `test_broken_ancestor_stops_later_writes` | `page_id == SANDBOX_PARENT_PAGE_ID` |
| 119 | `notion_sandbox_pipeline.py:176` | KILLED | 16 | `test_execute_on_the_fake_adapter_writes_evidence` | `space_conflicts(current.space_id) or current.archived` |
| 120 | `notion_sandbox_pipeline.py:181` | KILLED | 17 | `test_execute_on_the_fake_adapter_writes_evidence` | `parent_id == "" or page_id == "" or page_id in seen` |
| 121 | `notion_sandbox_pipeline.py:185` | KILLED | 15 | `test_execute_on_the_fake_adapter_writes_evidence` | `space_conflicts(current.space_id) or current.archived` |
| 122 | `notion_sandbox_pipeline.py:194` | KILLED | 34 | `test_create_under_refuses_a_foreign_parent` | `not parent_is_allowed(requested, allowed)` |
| 123 | `notion_sandbox_pipeline.py:196` | KILLED | 33 | `test_execute_on_the_fake_adapter_writes_evidence` | `canonical_id(ctx.bot_space_id) != SANDBOX_SPACE_ID` |
| 124 | `notion_sandbox_pipeline.py:202` | KILLED | 22 | `test_execute_on_the_fake_adapter_writes_evidence` | `page_id in {"", SANDBOX_PARENT_PAGE_ID, requested}` |
| 125 | `notion_sandbox_pipeline.py:205` | KILLED | 19 | `test_execute_on_the_fake_adapter_writes_evidence` | `page_id in ctx.created_ids[:before]` |
| 126 | `notion_sandbox_pipeline.py:207` | KILLED | 24 | `test_execute_on_the_fake_adapter_writes_evidence` | `space_conflicts(page.space_id)` |
| 127 | `notion_sandbox_pipeline.py:210` | KILLED | 21 | `test_execute_on_the_fake_adapter_writes_evidence` | `canonical_id(page.parent_id) != requested` |
| 128 | `notion_sandbox_pipeline.py:214` | KILLED | 19 | `test_execute_on_the_fake_adapter_writes_evidence` | `canonical_id(confirmed.page_id) != page_id` |
| 129 | `notion_sandbox_pipeline.py:216` | KILLED | 20 | `test_execute_on_the_fake_adapter_writes_evidence` | `canonical_id(confirmed.parent_id) != requested` |
| 130 | `notion_sandbox_pipeline.py:218` | KILLED | 17 | `test_execute_on_the_fake_adapter_writes_evidence` | `space_conflicts(confirmed.space_id) or confirmed.archived` |
| 131 | `notion_sandbox_pipeline.py:223` | KILLED | 1 | `test_token_in_created_url_exits_70` | `ctx.created and ctx.created[-1].get("id") == page_id` |
| 132 | `notion_sandbox_pipeline.py:245` | KILLED | 28 | `test_execute_on_the_fake_adapter_writes_evidence` | `type(spec) is not ProductSpec` |
| 133 | `notion_sandbox_pipeline.py:253` | KILLED | 16 | `test_execute_on_the_fake_adapter_writes_evidence` | `ctx.probe is None or ctx.product_page_id is None or type(spec) is not ProductSpec` |

## Force-true and force-false

| # | Site | Mode | Result | Failed | Test | Condition |
|---|---|---|---|---|---|---|
| 1 | `notion_sandbox.py:115` | true | KILLED | 3 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `runner_name is None` |
| 2 | `notion_sandbox.py:115` | false | KILLED | 3 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `runner_name is None` |
| 3 | `notion_sandbox.py:136` | true | KILLED | 29 | `test_execute_on_the_fake_adapter_writes_evidence` | `not available or failed` |
| 4 | `notion_sandbox.py:136` | false | KILLED | 1 | `test_absent_stage_failure_stays_not_run` | `not available or failed` |
| 5 | `notion_sandbox.py:140` | true | KILLED | 29 | `test_execute_on_the_fake_adapter_writes_evidence` | `runner is None` |
| 6 | `notion_sandbox.py:140` | false | EQUIVALENT | 0 | `—` | `runner is None` |
| 7 | `notion_sandbox.py:177` | true | KILLED | 3 | `test_evidence_out_equals_matches_the_space_form` | `arg == "--evidence-out" and index + 1 < len(argv)` |
| 8 | `notion_sandbox.py:177` | false | KILLED | 32 | `test_override_env_refuses[-NOTION_CONFIG]` | `arg == "--evidence-out" and index + 1 < len(argv)` |
| 9 | `notion_sandbox.py:179` | true | KILLED | 2 | `test_abbreviations_are_refused` | `arg.startswith("--evidence-out=")` |
| 10 | `notion_sandbox.py:179` | false | KILLED | 1 | `test_equals_form_records_an_override_refusal` | `arg.startswith("--evidence-out=")` |
| 11 | `notion_sandbox.py:196` | true | KILLED | 119 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `type(moment) is not datetime or moment.tzinfo is None` |
| 12 | `notion_sandbox.py:196` | false | KILLED | 1 | `test_naive_clock_is_refused` | `type(moment) is not datetime or moment.tzinfo is None` |
| 13 | `notion_sandbox.py:202` | true | KILLED | 3 | `test_short_token_is_refused` | `token is not None and token_shape_ok(token)` |
| 14 | `notion_sandbox.py:202` | false | KILLED | 54 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `token is not None and token_shape_ok(token)` |
| 15 | `notion_sandbox.py:295` | true | KILLED | 58 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `argv_names_a_target(arguments) or environ_names_a_target(env) or cert_env_set(env)` |
| 16 | `notion_sandbox.py:295` | false | KILLED | 33 | `test_override_env_refuses[-NOTION_CONFIG]` | `argv_names_a_target(arguments) or environ_names_a_target(env) or cert_env_set(env)` |
| 17 | `notion_sandbox.py:302` | true | KILLED | 72 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `str(evidence) == "" or leaks(str(evidence), secret)` |
| 18 | `notion_sandbox.py:302` | false | KILLED | 1 | `test_encoded_token_evidence_path_writes_nothing` | `str(evidence) == "" or leaks(str(evidence), secret)` |
| 19 | `notion_sandbox.py:305` | true | KILLED | 58 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `parsed.execute and parsed.dry_run` |
| 20 | `notion_sandbox.py:305` | false | KILLED | 1 | `test_both_flags_and_secret_evidence_path_refuse` | `parsed.execute and parsed.dry_run` |
| 21 | `notion_sandbox.py:310` | true | KILLED | 56 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `token is None` |
| 22 | `notion_sandbox.py:310` | false | KILLED | 2 | `test_missing_token_ignores_other_sources` | `token is None` |
| 23 | `notion_sandbox.py:322` | true | KILLED | 53 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `secret is None` |
| 24 | `notion_sandbox.py:322` | false | KILLED | 3 | `test_short_token_is_refused` | `secret is None` |
| 25 | `notion_sandbox.py:376` | true | KILLED | 46 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `type(bot.user_type) is not str` |
| 26 | `notion_sandbox.py:376` | false | KILLED | 1 | `test_non_string_user_type_exits_69` | `type(bot.user_type) is not str` |
| 27 | `notion_sandbox.py:394` | true | KILLED | 34 | `test_dry_run_is_the_default_and_writes_nothing` | `not target_ok(bot, page)` |
| 28 | `notion_sandbox.py:394` | false | KILLED | 10 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `not target_ok(bot, page)` |
| 29 | `notion_sandbox.py:412` | true | KILLED | 29 | `test_execute_on_the_fake_adapter_writes_evidence` | `mode == "dry-run"` |
| 30 | `notion_sandbox.py:412` | false | KILLED | 6 | `test_dry_run_is_the_default_and_writes_nothing` | `mode == "dry-run"` |
| 31 | `notion_sandbox.py:446` | true | KILLED | 20 | `test_execute_on_the_fake_adapter_writes_evidence` | `interrupted` |
| 32 | `notion_sandbox.py:446` | false | KILLED | 7 | `test_interrupt_writes_redacted_evidence` | `interrupted` |
| 33 | `notion_sandbox.py:450` | true | KILLED | 4 | `test_execute_on_the_fake_adapter_writes_evidence` | `failed` |
| 34 | `notion_sandbox.py:450` | false | KILLED | 16 | `test_absent_stage_failure_stays_not_run` | `failed` |
| 35 | `notion_sandbox.py:479` | true | KILLED | 6 | `test_interrupt_after_store_records_the_created_id[0-exc0]` | `bind is None` |
| 36 | `notion_sandbox.py:479` | false | KILLED | 1 | `test_execute_without_bind_created_still_records` | `bind is None` |
| 37 | `notion_sandbox.py:485` | true | KILLED | 1 | `test_non_string_bot_user_id_is_omitted` | `type(bot.user_id) is str` |
| 38 | `notion_sandbox.py:485` | false | KILLED | 20 | `test_execute_on_the_fake_adapter_writes_evidence` | `type(bot.user_id) is str` |
| 39 | `notion_sandbox.py:520` | true | KILLED | 5 | `test_execute_on_the_fake_adapter_writes_evidence` | `error is not None` |
| 40 | `notion_sandbox.py:520` | false | KILLED | 3 | `test_token_in_error_is_redacted` | `error is not None` |
| 41 | `notion_sandbox.py:522` | true | KILLED | 2 | `test_execute_on_the_fake_adapter_writes_evidence` | `any(stage.get("status") == "INTERRUPTED" for stage in stages)` |
| 42 | `notion_sandbox.py:522` | false | KILLED | 7 | `test_interrupt_writes_redacted_evidence` | `any(stage.get("status") == "INTERRUPTED" for stage in stages)` |
| 43 | `notion_sandbox.py:525` | true | KILLED | 99 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `check == "FAIL"` |
| 44 | `notion_sandbox.py:525` | false | KILLED | 3 | `test_failed_redaction_exits_70` | `check == "FAIL"` |
| 45 | `notion_sandbox.py:527` | true | KILLED | 90 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `code == EXIT_OK` |
| 46 | `notion_sandbox.py:527` | false | KILLED | 8 | `test_dry_run_is_the_default_and_writes_nothing` | `code == EXIT_OK` |
| 47 | `notion_sandbox.py:572` | true | KILLED | 1 | `test_both_flags_and_secret_evidence_path_refuse` | `path is not None and str(path) != "" and not leaks(str(path), token)` |
| 48 | `notion_sandbox.py:572` | false | KILLED | 33 | `test_override_env_refuses[-NOTION_CONFIG]` | `path is not None and str(path) != "" and not leaks(str(path), token)` |
| 49 | `notion_sandbox.py:579` | true | KILLED | 1 | `test_reraise_preserves_interrupt_and_base_exceptions` | `isinstance(exc, SystemExit)` |
| 50 | `notion_sandbox.py:579` | false | KILLED | 1 | `test_system_exit_status_is_normalized` | `isinstance(exc, SystemExit)` |
| 51 | `notion_sandbox.py:582` | true | KILLED | 1 | `test_reraise_preserves_interrupt_and_base_exceptions` | `isinstance(exc, KeyboardInterrupt)` |
| 52 | `notion_sandbox.py:582` | false | KILLED | 1 | `test_reraise_preserves_interrupt_and_base_exceptions` | `isinstance(exc, KeyboardInterrupt)` |
| 53 | `notion_sandbox.py:595` | true | KILLED | 1 | `—` | `__name__ == "__main__"` |
| 54 | `notion_sandbox.py:595` | false | KILLED | 1 | `test_module_entry_point_runs_main` | `__name__ == "__main__"` |
| 55 | `notion_sandbox_guard.py:144` | true | KILLED | 65 | `test_canonical_id_normalizes_and_rejects` | `type(value) is not str` |
| 56 | `notion_sandbox_guard.py:144` | false | KILLED | 1 | `test_canonical_id_normalizes_and_rejects` | `type(value) is not str` |
| 57 | `notion_sandbox_guard.py:147` | true | KILLED | 65 | `test_canonical_id_normalizes_and_rejects` | `len(compact) != 32` |
| 58 | `notion_sandbox_guard.py:147` | false | KILLED | 9 | `test_canonical_id_normalizes_and_rejects` | `len(compact) != 32` |
| 59 | `notion_sandbox_guard.py:149` | true | KILLED | 65 | `test_canonical_id_normalizes_and_rejects` | `any(character not in "0123456789abcdef" for character in compact)` |
| 60 | `notion_sandbox_guard.py:149` | false | KILLED | 1 | `test_canonical_id_normalizes_and_rejects` | `any(character not in "0123456789abcdef" for character in compact)` |
| 61 | `notion_sandbox_guard.py:156` | true | KILLED | 35 | `test_target_and_parent_guards` | `type(bot.user_type) is not str or bot.user_type != "bot"` |
| 62 | `notion_sandbox_guard.py:156` | false | KILLED | 2 | `test_target_and_parent_guards` | `type(bot.user_type) is not str or bot.user_type != "bot"` |
| 63 | `notion_sandbox_guard.py:158` | true | KILLED | 35 | `test_target_and_parent_guards` | `page.archived or page.parent_type in {"database_id", "data_source_id"}` |
| 64 | `notion_sandbox_guard.py:158` | false | KILLED | 6 | `test_target_and_parent_guards` | `page.archived or page.parent_type in {"database_id", "data_source_id"}` |
| 65 | `notion_sandbox_guard.py:160` | true | KILLED | 35 | `test_target_and_parent_guards` | `canonical_id(bot.space_id) != SANDBOX_SPACE_ID` |
| 66 | `notion_sandbox_guard.py:160` | false | KILLED | 2 | `test_target_and_parent_guards` | `canonical_id(bot.space_id) != SANDBOX_SPACE_ID` |
| 67 | `notion_sandbox_guard.py:162` | true | KILLED | 35 | `test_target_and_parent_guards` | `canonical_id(page.page_id) != SANDBOX_PARENT_PAGE_ID` |
| 68 | `notion_sandbox_guard.py:162` | false | KILLED | 1 | `test_target_and_parent_guards` | `canonical_id(page.page_id) != SANDBOX_PARENT_PAGE_ID` |
| 69 | `notion_sandbox_guard.py:170` | true | KILLED | 38 | `test_target_and_parent_guards` | `candidate == ""` |
| 70 | `notion_sandbox_guard.py:170` | false | KILLED | 1 | `test_target_and_parent_guards` | `candidate == ""` |
| 71 | `notion_sandbox_guard.py:178` | true | KILLED | 58 | `test_token_env_and_redaction_units` | `type(value) is not str or value == ""` |
| 72 | `notion_sandbox_guard.py:178` | false | KILLED | 1 | `test_token_env_and_redaction_units` | `type(value) is not str or value == ""` |
| 73 | `notion_sandbox_guard.py:203` | true | KILLED | 58 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `head in _OVERRIDE_FLAGS` |
| 74 | `notion_sandbox_guard.py:203` | false | KILLED | 11 | `test_argv_refused_rejects_each_flag[--api-key]` | `head in _OVERRIDE_FLAGS` |
| 75 | `notion_sandbox_guard.py:205` | true | KILLED | 58 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `contains_secret_shape(arg)` |
| 76 | `notion_sandbox_guard.py:205` | false | KILLED | 1 | `test_token_on_argv_is_refused` | `contains_secret_shape(arg)` |
| 77 | `notion_sandbox_guard.py:217` | true | KILLED | 4 | `test_token_env_and_redaction_units` | `token is None or not token_shape_ok(token)` |
| 78 | `notion_sandbox_guard.py:217` | false | KILLED | 117 | `test_token_env_and_redaction_units` | `token is None or not token_shape_ok(token)` |
| 79 | `notion_sandbox_guard.py:222` | true | EQUIVALENT | 0 | `—` | `encoded != token` |
| 80 | `notion_sandbox_guard.py:222` | false | KILLED | 3 | `test_token_env_and_redaction_units` | `encoded != token` |
| 81 | `notion_sandbox_guard.py:224` | true | EQUIVALENT | 0 | `—` | `digest not in forms and digest != token` |
| 82 | `notion_sandbox_guard.py:224` | false | KILLED | 4 | `test_token_env_and_redaction_units` | `digest not in forms and digest != token` |
| 83 | `notion_sandbox_guard.py:232` | true | KILLED | 116 | `test_token_env_and_redaction_units` | `token is not None and token != "" and not _unsafe_exact(token) and token in cleaned` |
| 84 | `notion_sandbox_guard.py:232` | false | KILLED | 1 | `test_token_env_and_redaction_units` | `token is not None and token != "" and not _unsafe_exact(token) and token in cleaned` |
| 85 | `notion_sandbox_guard.py:235` | true | EQUIVALENT | 0 | `—` | `form in cleaned` |
| 86 | `notion_sandbox_guard.py:235` | false | KILLED | 2 | `test_token_env_and_redaction_units` | `form in cleaned` |
| 87 | `notion_sandbox_guard.py:242` | true | KILLED | 19 | `test_target_and_parent_guards` | `runner_name is None` |
| 88 | `notion_sandbox_guard.py:242` | false | KILLED | 1 | `test_token_env_and_redaction_units` | `runner_name is None` |
| 89 | `notion_sandbox_guard.py:244` | true | KILLED | 18 | `test_target_and_parent_guards` | `outcome == "PASS"` |
| 90 | `notion_sandbox_guard.py:244` | false | KILLED | 2 | `test_execute_on_the_fake_adapter_writes_evidence` | `outcome == "PASS"` |
| 91 | `notion_sandbox_guard.py:246` | true | KILLED | 3 | `test_target_and_parent_guards` | `outcome == "FAILED"` |
| 92 | `notion_sandbox_guard.py:246` | false | KILLED | 16 | `test_absent_stage_failure_stays_not_run` | `outcome == "FAILED"` |
| 93 | `notion_sandbox_guard.py:248` | true | KILLED | 2 | `test_dry_run_is_the_default_and_writes_nothing` | `outcome == "BLOCKED"` |
| 94 | `notion_sandbox_guard.py:248` | false | KILLED | 1 | `test_target_and_parent_guards` | `outcome == "BLOCKED"` |
| 95 | `notion_sandbox_guard.py:263` | true | KILLED | 1 | `test_token_env_and_redaction_units` | `stage.get("name") == "qa" and type(found) is str` |
| 96 | `notion_sandbox_guard.py:263` | false | KILLED | 1 | `test_token_env_and_redaction_units` | `stage.get("name") == "qa" and type(found) is str` |
| 97 | `notion_sandbox_guard.py:265` | true | KILLED | 6 | `test_token_env_and_redaction_units` | `status == "PASS"` |
| 98 | `notion_sandbox_guard.py:265` | false | KILLED | 1 | `test_token_env_and_redaction_units` | `status == "PASS"` |
| 99 | `notion_sandbox_guard.py:267` | true | KILLED | 6 | `test_token_env_and_redaction_units` | `status == "FAILED"` |
| 100 | `notion_sandbox_guard.py:267` | false | KILLED | 1 | `test_token_env_and_redaction_units` | `status == "FAILED"` |
| 101 | `notion_sandbox_guard.py:269` | true | KILLED | 6 | `test_token_env_and_redaction_units` | `status == "BLOCKED"` |
| 102 | `notion_sandbox_guard.py:269` | false | KILLED | 1 | `test_token_env_and_redaction_units` | `status == "BLOCKED"` |
| 103 | `notion_sandbox_guard.py:283` | true | KILLED | 111 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `token is not None and token != "" and not _unsafe_exact(token) and token in text` |
| 104 | `notion_sandbox_guard.py:283` | false | KILLED | 1 | `test_hex_token_equal_to_the_page_id_sends_nothing` | `token is not None and token != "" and not _unsafe_exact(token) and token in text` |
| 105 | `notion_sandbox_guard.py:285` | true | KILLED | 111 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `any(form in text for form in _encoded_forms(token))` |
| 106 | `notion_sandbox_guard.py:285` | false | KILLED | 2 | `test_base64_token_in_evidence_exits_70` | `any(form in text for form in _encoded_forms(token))` |
| 107 | `notion_sandbox_guard.py:300` | true | KILLED | 100 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `leaks(text, token)` |
| 108 | `notion_sandbox_guard.py:300` | false | KILLED | 4 | `test_write_evidence_redacts_a_planted_token` | `leaks(text, token)` |
| 109 | `notion_sandbox_guard.py:304` | true | KILLED | 1 | `test_failed_redaction_exits_70` | `leaks(text, token)` |
| 110 | `notion_sandbox_guard.py:304` | false | EQUIVALENT | 0 | `—` | `leaks(text, token)` |
| 111 | `notion_sandbox_guard.py:323` | true | KILLED | 109 | `test_write_evidence_redacts_a_planted_token` | `str(path) == "" or path == Path() or under_proc(path)` |
| 112 | `notion_sandbox_guard.py:323` | false | EQUIVALENT | 0 | `—` | `str(path) == "" or path == Path() or under_proc(path)` |
| 113 | `notion_sandbox_guard.py:331` | true | KILLED | 109 | `test_write_evidence_redacts_a_planted_token` | `info is not None` |
| 114 | `notion_sandbox_guard.py:331` | false | EQUIVALENT | 0 | `—` | `info is not None` |
| 115 | `notion_sandbox_guard.py:338` | true | KILLED | 109 | `test_write_evidence_redacts_a_planted_token` | `stat.S_ISLNK(parent_info.st_mode) or not stat.S_ISDIR(parent_info.st_mode)` |
| 116 | `notion_sandbox_guard.py:338` | false | KILLED | 1 | `test_symlinked_parent_directory_is_refused` | `stat.S_ISLNK(parent_info.st_mode) or not stat.S_ISDIR(parent_info.st_mode)` |
| 117 | `notion_sandbox_guard.py:340` | true | KILLED | 109 | `test_write_evidence_redacts_a_planted_token` | `parent_info.st_mode & 0o200 == 0` |
| 118 | `notion_sandbox_guard.py:340` | false | EQUIVALENT | 0 | `—` | `parent_info.st_mode & 0o200 == 0` |
| 119 | `notion_sandbox_guard.py:361` | true | KILLED | 1 | `test_enospc_after_creates_prints_ids` | `type(found) is not list` |
| 120 | `notion_sandbox_guard.py:361` | false | KILLED | 1 | `test_enospc_ignores_pages_that_are_not_ids` | `type(found) is not list` |
| 121 | `notion_sandbox_guard.py:365` | true | KILLED | 1 | `test_enospc_after_creates_prints_ids` | `type(item) is not dict` |
| 122 | `notion_sandbox_guard.py:365` | false | KILLED | 1 | `test_enospc_ignores_pages_that_are_not_ids` | `type(item) is not dict` |
| 123 | `notion_sandbox_guard.py:368` | true | KILLED | 1 | `test_enospc_ignores_pages_that_are_not_ids` | `type(page_id) is str and page_id != ""` |
| 124 | `notion_sandbox_guard.py:368` | false | KILLED | 1 | `test_enospc_after_creates_prints_ids` | `type(page_id) is str and page_id != ""` |
| 125 | `notion_sandbox_guard.py:377` | true | KILLED | 105 | `test_write_evidence_redacts_a_planted_token` | `written <= 0 or written > len(pending)` |
| 126 | `notion_sandbox_guard.py:377` | false | KILLED | 1 | `timeout` | `written <= 0 or written > len(pending)` |
| 127 | `notion_sandbox_guard.py:388` | true | KILLED | 103 | `test_write_evidence_redacts_a_planted_token` | `stat.S_ISLNK(current.st_mode)` |
| 128 | `notion_sandbox_guard.py:388` | false | EQUIVALENT | 0 | `—` | `stat.S_ISLNK(current.st_mode)` |
| 129 | `notion_sandbox_guard.py:404` | true | KILLED | 103 | `test_write_evidence_redacts_a_planted_token` | `not _same_inode(fd, path)` |
| 130 | `notion_sandbox_guard.py:404` | false | KILLED | 2 | `test_swapped_evidence_file_does_not_exit_ok` | `not _same_inode(fd, path)` |
| 131 | `notion_sandbox_guard.py:409` | true | KILLED | 1 | `test_evidence_write_oserror_is_redacted` | `exc.errno in {errno.ENOSPC, errno.EIO}` |
| 132 | `notion_sandbox_guard.py:409` | false | KILLED | 2 | `test_enospc_after_creates_prints_ids` | `exc.errno in {errno.ENOSPC, errno.EIO}` |
| 133 | `notion_sandbox_guard.py:455` | true | KILLED | 117 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `(candidate / "pyproject.toml").is_file() and (candidate / "docs" / "control").is_dir()` |
| 134 | `notion_sandbox_guard.py:455` | false | KILLED | 1 | `test_repo_root_needs_both_markers` | `(candidate / "pyproject.toml").is_file() and (candidate / "docs" / "control").is_dir()` |
| 135 | `notion_sandbox_guard.py:459` | true | EQUIVALENT | 0 | `—` | `(candidate / "pyproject.toml").is_file() and (candidate / "docs" / "control").is_dir()` |
| 136 | `notion_sandbox_guard.py:459` | false | KILLED | 1 | `test_repo_root_falls_back_to_cwd` | `(candidate / "pyproject.toml").is_file() and (candidate / "docs" / "control").is_dir()` |
| 137 | `notion_sandbox_guard.py:477` | true | KILLED | 115 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `completed.returncode != 0 or len(sha) != 40` |
| 138 | `notion_sandbox_guard.py:477` | false | KILLED | 2 | `test_git_sha_rejects_a_bad_rev_parse` | `completed.returncode != 0 or len(sha) != 40` |
| 139 | `notion_sandbox_guard.py:479` | true | KILLED | 115 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `any(character not in "0123456789abcdef" for character in sha)` |
| 140 | `notion_sandbox_guard.py:479` | false | KILLED | 1 | `test_git_sha_rejects_a_bad_rev_parse` | `any(character not in "0123456789abcdef" for character in sha)` |
| 141 | `notion_sandbox_guard.py:491` | true | KILLED | 113 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `type(payload) is not dict` |
| 142 | `notion_sandbox_guard.py:491` | false | KILLED | 1 | `test_control_state_container_exits_69` | `type(payload) is not dict` |
| 143 | `notion_sandbox_guard.py:496` | true | KILLED | 113 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `type(revision) is not int or type(session) is not int or type(head) is not str` |
| 144 | `notion_sandbox_guard.py:496` | false | KILLED | 1 | `test_string_revision_is_unreadable` | `type(revision) is not int or type(session) is not int or type(head) is not str` |
| 145 | `notion_sandbox_live.py:118` | true | KILLED | 16 | `test_live_client_reads_without_writing_and_redacts` | `bot is None` |
| 146 | `notion_sandbox_live.py:118` | false | KILLED | 1 | `test_non_string_bot_id_is_rejected` | `bot is None` |
| 147 | `notion_sandbox_live.py:125` | true | KILLED | 16 | `test_live_client_reads_without_writing_and_redacts` | `expected == ""` |
| 148 | `notion_sandbox_live.py:125` | false | KILLED | 1 | `test_empty_page_id_is_not_read` | `expected == ""` |
| 149 | `notion_sandbox_live.py:130` | true | KILLED | 14 | `test_live_client_reads_without_writing_and_redacts` | `page is None` |
| 150 | `notion_sandbox_live.py:130` | false | KILLED | 2 | `test_string_in_trash_is_rejected` | `page is None` |
| 151 | `notion_sandbox_live.py:137` | true | KILLED | 9 | `test_live_child_page_does_not_count_its_own_write` | `not parent_is_allowed(parent, allowed)` |
| 152 | `notion_sandbox_live.py:137` | false | KILLED | 1 | `test_live_client_reads_without_writing_and_redacts` | `not parent_is_allowed(parent, allowed)` |
| 153 | `notion_sandbox_live.py:148` | true | KILLED | 9 | `test_live_child_page_does_not_count_its_own_write` | `type(sent_parent) is not dict or sent_parent.get("page_id") != parent or sent_parent.get("type") != "page_id"` |
| 154 | `notion_sandbox_live.py:148` | false | KILLED | 1 | `test_request_body_parent_is_asserted` | `type(sent_parent) is not dict or sent_parent.get("page_id") != parent or sent_parent.get("type") != "page_id"` |
| 155 | `notion_sandbox_live.py:156` | true | KILLED | 8 | `test_live_child_page_does_not_count_its_own_write` | `page is None` |
| 156 | `notion_sandbox_live.py:156` | false | KILLED | 1 | `test_unparsed_create_is_not_recorded` | `page is None` |
| 157 | `notion_sandbox_live.py:164` | true | KILLED | 5 | `test_doc_shaped_pages_execute_without_a_space` | `page_id == "" or space_conflicts(page.space_id)` |
| 158 | `notion_sandbox_live.py:164` | false | KILLED | 1 | `test_wrong_space_create_is_not_published` | `page_id == "" or space_conflicts(page.space_id)` |
| 159 | `notion_sandbox_live.py:166` | true | KILLED | 1 | `test_publish_does_not_repeat_an_id` | `page_id not in self._created_ids` |
| 160 | `notion_sandbox_live.py:166` | false | KILLED | 4 | `test_doc_shaped_pages_execute_without_a_space` | `page_id not in self._created_ids` |
| 161 | `notion_sandbox_live.py:170` | true | KILLED | 3 | `test_doc_shaped_interrupt_after_store_records_the_created_id[0-exc0]` | `evidence_ids is None or evidence_rows is None or page_id in evidence_ids` |
| 162 | `notion_sandbox_live.py:170` | false | KILLED | 2 | `test_live_child_page_does_not_count_its_own_write` | `evidence_ids is None or evidence_rows is None or page_id in evidence_ids` |
| 163 | `notion_sandbox_live.py:179` | true | KILLED | 21 | `test_live_client_reads_without_writing_and_redacts` | `leaks(url, self._token) or leaks(url.replace("-", ""), self._token)` |
| 164 | `notion_sandbox_live.py:179` | false | KILLED | 1 | `test_hex_token_equal_to_the_page_id_sends_nothing` | `leaks(url, self._token) or leaks(url.replace("-", ""), self._token)` |
| 165 | `notion_sandbox_live.py:185` | true | KILLED | 1 | `test_live_client_reads_without_writing_and_redacts` | `body is not None` |
| 166 | `notion_sandbox_live.py:185` | false | KILLED | 1 | `test_live_child_page_does_not_count_its_own_write` | `body is not None` |
| 167 | `notion_sandbox_live.py:190` | true | KILLED | 1 | `test_redirect_is_not_followed` | `type(status) is not int` |
| 168 | `notion_sandbox_live.py:190` | false | KILLED | 1 | `test_redirect_code_is_refused_without_a_status` | `type(status) is not int` |
| 169 | `notion_sandbox_live.py:192` | true | KILLED | 19 | `test_live_client_reads_without_writing_and_redacts` | `type(status) is int and 300 <= status < 400` |
| 170 | `notion_sandbox_live.py:192` | false | KILLED | 2 | `test_redirect_is_not_followed` | `type(status) is int and 300 <= status < 400` |
| 171 | `notion_sandbox_live.py:201` | true | KILLED | 19 | `test_live_client_reads_without_writing_and_redacts` | `type(raw) is not bytes` |
| 172 | `notion_sandbox_live.py:201` | false | KILLED | 1 | `test_non_byte_body_is_an_api_error` | `type(raw) is not bytes` |
| 173 | `notion_sandbox_live.py:211` | true | KILLED | 16 | `test_live_client_reads_without_writing_and_redacts` | `type(payload) is not dict` |
| 174 | `notion_sandbox_live.py:211` | false | KILLED | 1 | `test_parse_bot_rejects_a_non_object` | `type(payload) is not dict` |
| 175 | `notion_sandbox_live.py:215` | true | KILLED | 16 | `test_live_client_reads_without_writing_and_redacts` | `type(user_id) is not str or type(user_type) is not str` |
| 176 | `notion_sandbox_live.py:215` | false | KILLED | 1 | `test_non_string_bot_id_is_rejected` | `type(user_id) is not str or type(user_type) is not str` |
| 177 | `notion_sandbox_live.py:219` | true | KILLED | 2 | `test_missing_workspace_id_writes_nothing` | `type(bot) is dict and type(bot.get("workspace_id")) is str` |
| 178 | `notion_sandbox_live.py:219` | false | KILLED | 6 | `test_live_client_reads_without_writing_and_redacts` | `type(bot) is dict and type(bot.get("workspace_id")) is str` |
| 179 | `notion_sandbox_live.py:226` | true | KILLED | 3 | `test_trashed_parent_writes_nothing[archived]` | `key not in payload` |
| 180 | `notion_sandbox_live.py:226` | false | KILLED | 19 | `test_live_client_reads_without_writing_and_redacts` | `key not in payload` |
| 181 | `notion_sandbox_live.py:229` | true | KILLED | 7 | `test_trashed_parent_writes_nothing[archived]` | `type(value) is not bool` |
| 182 | `notion_sandbox_live.py:229` | false | KILLED | 1 | `test_string_in_trash_is_rejected` | `type(value) is not bool` |
| 183 | `notion_sandbox_live.py:236` | true | KILLED | 24 | `test_live_client_reads_without_writing_and_redacts` | `type(payload) is not dict or payload.get("object") != "page"` |
| 184 | `notion_sandbox_live.py:236` | false | KILLED | 1 | `test_database_parent_and_missing_object_write_nothing` | `type(payload) is not dict or payload.get("object") != "page"` |
| 185 | `notion_sandbox_live.py:239` | true | KILLED | 24 | `test_live_client_reads_without_writing_and_redacts` | `page_id == ""` |
| 186 | `notion_sandbox_live.py:239` | false | KILLED | 1 | `test_parse_page_rejects_a_non_id` | `page_id == ""` |
| 187 | `notion_sandbox_live.py:245` | true | KILLED | 2 | `test_missing_parent_object_stays_a_page` | `type(parent) is dict` |
| 188 | `notion_sandbox_live.py:245` | false | KILLED | 8 | `test_live_child_page_does_not_count_its_own_write` | `type(parent) is dict` |
| 189 | `notion_sandbox_live.py:246` | true | KILLED | 2 | `test_live_space_fallback_is_only_the_asserted_parent` | `space == ""` |
| 190 | `notion_sandbox_live.py:246` | false | KILLED | 1 | `test_parent_object_can_carry_the_space` | `space == ""` |
| 191 | `notion_sandbox_live.py:249` | true | KILLED | 1 | `test_non_string_parent_type_is_ignored` | `type(found_type) is str` |
| 192 | `notion_sandbox_live.py:249` | false | KILLED | 3 | `test_database_id_parent_is_not_a_page_parent` | `type(found_type) is str` |
| 193 | `notion_sandbox_live.py:251` | true | KILLED | 2 | `test_non_string_parent_type_is_ignored` | `found_type == "page_id"` |
| 194 | `notion_sandbox_live.py:251` | false | KILLED | 4 | `test_live_child_page_does_not_count_its_own_write` | `found_type == "page_id"` |
| 195 | `notion_sandbox_live.py:253` | true | KILLED | 4 | `test_live_space_fallback_is_only_the_asserted_parent` | `space == "" and page_id == canonical_id(expected_id)` |
| 196 | `notion_sandbox_live.py:253` | false | KILLED | 6 | `test_live_client_reads_without_writing_and_redacts` | `space == "" and page_id == canonical_id(expected_id)` |
| 197 | `notion_sandbox_live.py:256` | true | KILLED | 1 | `test_parse_page_keeps_a_url_and_fills_a_blank_one` | `type(url) is not str or url == ""` |
| 198 | `notion_sandbox_live.py:256` | false | KILLED | 1 | `test_parse_page_keeps_a_url_and_fills_a_blank_one` | `type(url) is not str or url == ""` |
| 199 | `notion_sandbox_live.py:260` | true | KILLED | 24 | `test_live_client_reads_without_writing_and_redacts` | `archived_flag is None or trash_flag is None` |
| 200 | `notion_sandbox_live.py:260` | false | KILLED | 1 | `test_string_in_trash_is_rejected` | `archived_flag is None or trash_flag is None` |
| 201 | `notion_sandbox_live.py:277` | true | KILLED | 3 | `test_doc_shaped_pages_execute_without_a_space` | `type(value) is not str or value == ""` |
| 202 | `notion_sandbox_live.py:277` | false | KILLED | 19 | `test_live_client_reads_without_writing_and_redacts` | `type(value) is not str or value == ""` |
| 203 | `notion_sandbox_live.py:283` | true | KILLED | 3 | `test_doc_shaped_pages_execute_without_a_space` | `parsed.tzinfo is None` |
| 204 | `notion_sandbox_live.py:283` | false | KILLED | 1 | `test_naive_timestamp_stays_unset` | `parsed.tzinfo is None` |
| 205 | `notion_sandbox_live.py:290` | true | KILLED | 3 | `test_doc_shaped_pages_execute_without_a_space` | `type(actor) is not dict` |
| 206 | `notion_sandbox_live.py:290` | false | KILLED | 18 | `test_live_client_reads_without_writing_and_redacts` | `type(actor) is not dict` |
| 207 | `notion_sandbox_live.py:293` | true | KILLED | 3 | `test_doc_shaped_pages_execute_without_a_space` | `type(found) is not str` |
| 208 | `notion_sandbox_live.py:293` | false | KILLED | 1 | `test_non_string_created_by_stays_blank` | `type(found) is not str` |
| 209 | `notion_sandbox_live.py:301` | true | KILLED | 2 | `test_proxy_map_reads_string_proxy_entries` | `type(handlers) is not list` |
| 210 | `notion_sandbox_live.py:301` | false | KILLED | 1 | `test_proxy_map_ignores_a_missing_handler_list` | `type(handlers) is not list` |
| 211 | `notion_sandbox_live.py:304` | true | KILLED | 1 | `test_proxy_map_ignores_handlers_that_are_not_proxies` | `isinstance(handler, urllib.request.ProxyHandler)` |
| 212 | `notion_sandbox_live.py:304` | false | KILLED | 2 | `test_proxy_map_reads_string_proxy_entries` | `isinstance(handler, urllib.request.ProxyHandler)` |
| 213 | `notion_sandbox_live.py:306` | true | KILLED | 2 | `test_proxy_map_reads_string_proxy_entries` | `type(found) is not dict` |
| 214 | `notion_sandbox_live.py:306` | false | KILLED | 1 | `test_proxy_map_ignores_a_non_dict_proxy_table` | `type(found) is not dict` |
| 215 | `notion_sandbox_live.py:309` | true | KILLED | 1 | `test_proxy_map_drops_non_strings` | `type(key) is str and type(value) is str` |
| 216 | `notion_sandbox_live.py:309` | false | KILLED | 2 | `test_proxy_map_reads_string_proxy_entries` | `type(key) is str and type(value) is str` |
| 217 | `notion_sandbox_live.py:318` | true | KILLED | 2 | `test_explicit_space_skips_a_non_id` | `type(value) is str and canonical_id(value) != ""` |
| 218 | `notion_sandbox_live.py:318` | false | KILLED | 4 | `test_live_space_fallback_is_only_the_asserted_parent` | `type(value) is str and canonical_id(value) != ""` |
| 219 | `notion_sandbox_pipeline.py:133` | true | KILLED | 1 | `test_sandbox_parent_in_a_foreign_space_fails_the_chain` | `page_id in ctx.created_ids` |
| 220 | `notion_sandbox_pipeline.py:133` | false | KILLED | 1 | `timeout` | `page_id in ctx.created_ids` |
| 221 | `notion_sandbox_pipeline.py:143` | true | KILLED | 2 | `test_lying_create_id_stops_before_colours` | `tail == page_id` |
| 222 | `notion_sandbox_pipeline.py:143` | false | KILLED | 4 | `test_interrupt_after_store_records_the_created_id[2-exc1]` | `tail == page_id` |
| 223 | `notion_sandbox_pipeline.py:146` | true | KILLED | 21 | `test_execute_on_the_fake_adapter_writes_evidence` | `page_id == "" or space_conflicts(page.space_id)` |
| 224 | `notion_sandbox_pipeline.py:146` | false | EQUIVALENT | 0 | `—` | `page_id == "" or space_conflicts(page.space_id)` |
| 225 | `notion_sandbox_pipeline.py:149` | true | KILLED | 12 | `test_execute_on_the_fake_adapter_writes_evidence` | `page_id not in ctx.created_ids` |
| 226 | `notion_sandbox_pipeline.py:149` | false | KILLED | 4 | `test_lying_create_id_stops_before_colours` | `page_id not in ctx.created_ids` |
| 227 | `notion_sandbox_pipeline.py:158` | true | KILLED | 19 | `test_execute_on_the_fake_adapter_writes_evidence` | `page.created_by != ctx.bot_user_id` |
| 228 | `notion_sandbox_pipeline.py:158` | false | KILLED | 1 | `test_stale_foreign_page_is_not_a_parent` | `page.created_by != ctx.bot_user_id` |
| 229 | `notion_sandbox_pipeline.py:161` | true | KILLED | 19 | `test_execute_on_the_fake_adapter_writes_evidence` | `moment is None` |
| 230 | `notion_sandbox_pipeline.py:161` | false | KILLED | 1 | `test_missing_created_time_is_not_new` | `moment is None` |
| 231 | `notion_sandbox_pipeline.py:163` | true | KILLED | 19 | `test_execute_on_the_fake_adapter_writes_evidence` | `moment.tzinfo is None` |
| 232 | `notion_sandbox_pipeline.py:163` | false | KILLED | 1 | `test_naive_created_time_is_not_new` | `moment.tzinfo is None` |
| 233 | `notion_sandbox_pipeline.py:165` | true | KILLED | 19 | `test_execute_on_the_fake_adapter_writes_evidence` | `moment < ctx.moment` |
| 234 | `notion_sandbox_pipeline.py:165` | false | KILLED | 1 | `test_stale_confirm_stops_later_writes` | `moment < ctx.moment` |
| 235 | `notion_sandbox_pipeline.py:175` | true | KILLED | 4 | `test_broken_ancestor_stops_later_writes` | `page_id == SANDBOX_PARENT_PAGE_ID` |
| 236 | `notion_sandbox_pipeline.py:175` | false | KILLED | 15 | `test_execute_on_the_fake_adapter_writes_evidence` | `page_id == SANDBOX_PARENT_PAGE_ID` |
| 237 | `notion_sandbox_pipeline.py:176` | true | KILLED | 15 | `test_execute_on_the_fake_adapter_writes_evidence` | `space_conflicts(current.space_id) or current.archived` |
| 238 | `notion_sandbox_pipeline.py:176` | false | KILLED | 1 | `test_sandbox_parent_in_a_foreign_space_fails_the_chain` | `space_conflicts(current.space_id) or current.archived` |
| 239 | `notion_sandbox_pipeline.py:181` | true | KILLED | 16 | `test_execute_on_the_fake_adapter_writes_evidence` | `parent_id == "" or page_id == "" or page_id in seen` |
| 240 | `notion_sandbox_pipeline.py:181` | false | KILLED | 2 | `test_broken_ancestor_stops_later_writes` | `parent_id == "" or page_id == "" or page_id in seen` |
| 241 | `notion_sandbox_pipeline.py:185` | true | KILLED | 15 | `test_execute_on_the_fake_adapter_writes_evidence` | `space_conflicts(current.space_id) or current.archived` |
| 242 | `notion_sandbox_pipeline.py:185` | false | KILLED | 1 | `test_trashed_product_page_stops_further_writes` | `space_conflicts(current.space_id) or current.archived` |
| 243 | `notion_sandbox_pipeline.py:194` | true | KILLED | 33 | `test_execute_on_the_fake_adapter_writes_evidence` | `not parent_is_allowed(requested, allowed)` |
| 244 | `notion_sandbox_pipeline.py:194` | false | KILLED | 1 | `test_create_under_refuses_a_foreign_parent` | `not parent_is_allowed(requested, allowed)` |
| 245 | `notion_sandbox_pipeline.py:196` | true | KILLED | 32 | `test_execute_on_the_fake_adapter_writes_evidence` | `canonical_id(ctx.bot_space_id) != SANDBOX_SPACE_ID` |
| 246 | `notion_sandbox_pipeline.py:196` | false | KILLED | 1 | `test_foreign_bot_space_creates_nothing` | `canonical_id(ctx.bot_space_id) != SANDBOX_SPACE_ID` |
| 247 | `notion_sandbox_pipeline.py:202` | true | KILLED | 21 | `test_execute_on_the_fake_adapter_writes_evidence` | `page_id in {"", SANDBOX_PARENT_PAGE_ID, requested}` |
| 248 | `notion_sandbox_pipeline.py:202` | false | KILLED | 1 | `test_create_that_returns_the_parent_id_is_not_new` | `page_id in {"", SANDBOX_PARENT_PAGE_ID, requested}` |
| 249 | `notion_sandbox_pipeline.py:205` | true | KILLED | 19 | `test_execute_on_the_fake_adapter_writes_evidence` | `page_id in ctx.created_ids[:before]` |
| 250 | `notion_sandbox_pipeline.py:205` | false | KILLED | 1 | `test_repeated_created_id_is_refused` | `page_id in ctx.created_ids[:before]` |
| 251 | `notion_sandbox_pipeline.py:207` | true | KILLED | 23 | `test_execute_on_the_fake_adapter_writes_evidence` | `space_conflicts(page.space_id)` |
| 252 | `notion_sandbox_pipeline.py:207` | false | KILLED | 1 | `test_wrong_space_on_create_return_stops` | `space_conflicts(page.space_id)` |
| 253 | `notion_sandbox_pipeline.py:210` | true | KILLED | 20 | `test_execute_on_the_fake_adapter_writes_evidence` | `canonical_id(page.parent_id) != requested` |
| 254 | `notion_sandbox_pipeline.py:210` | false | KILLED | 1 | `test_lying_response_parent_stops` | `canonical_id(page.parent_id) != requested` |
| 255 | `notion_sandbox_pipeline.py:214` | true | KILLED | 18 | `test_execute_on_the_fake_adapter_writes_evidence` | `canonical_id(confirmed.page_id) != page_id` |
| 256 | `notion_sandbox_pipeline.py:214` | false | KILLED | 1 | `test_confirm_of_a_different_id_keeps_the_created_page` | `canonical_id(confirmed.page_id) != page_id` |
| 257 | `notion_sandbox_pipeline.py:216` | true | KILLED | 18 | `test_execute_on_the_fake_adapter_writes_evidence` | `canonical_id(confirmed.parent_id) != requested` |
| 258 | `notion_sandbox_pipeline.py:216` | false | KILLED | 3 | `test_lying_reread_stops_later_writes` | `canonical_id(confirmed.parent_id) != requested` |
| 259 | `notion_sandbox_pipeline.py:218` | true | KILLED | 15 | `test_execute_on_the_fake_adapter_writes_evidence` | `space_conflicts(confirmed.space_id) or confirmed.archived` |
| 260 | `notion_sandbox_pipeline.py:218` | false | KILLED | 2 | `test_trashed_confirm_stops_further_writes` | `space_conflicts(confirmed.space_id) or confirmed.archived` |
| 261 | `notion_sandbox_pipeline.py:223` | true | EQUIVALENT | 0 | `—` | `ctx.created and ctx.created[-1].get("id") == page_id` |
| 262 | `notion_sandbox_pipeline.py:223` | false | KILLED | 1 | `test_token_in_created_url_exits_70` | `ctx.created and ctx.created[-1].get("id") == page_id` |
| 263 | `notion_sandbox_pipeline.py:245` | true | KILLED | 28 | `test_execute_on_the_fake_adapter_writes_evidence` | `type(spec) is not ProductSpec` |
| 264 | `notion_sandbox_pipeline.py:245` | false | EQUIVALENT | 0 | `—` | `type(spec) is not ProductSpec` |
| 265 | `notion_sandbox_pipeline.py:253` | true | KILLED | 15 | `test_execute_on_the_fake_adapter_writes_evidence` | `ctx.probe is None or ctx.product_page_id is None or type(spec) is not ProductSpec` |
| 266 | `notion_sandbox_pipeline.py:253` | false | KILLED | 1 | `test_variants_without_a_product_page_are_a_sandbox_error` | `ctx.probe is None or ctx.product_page_id is None or type(spec) is not ProductSpec` |

## Boolean operands

| # | Site | Operator | Mutation | Result | Failed | Test | Condition |
|---|---|---|---|---|---|---|---|
| 1 | `notion_sandbox.py:136` | or | swap | KILLED | 1 | `test_absent_stage_failure_stays_not_run` | `not available or failed` |
| 2 | `notion_sandbox.py:136` | or | neg0 | KILLED | 29 | `test_execute_on_the_fake_adapter_writes_evidence` | `not available or failed` |
| 3 | `notion_sandbox.py:136` | or | neg1 | KILLED | 29 | `test_execute_on_the_fake_adapter_writes_evidence` | `not available or failed` |
| 4 | `notion_sandbox.py:177` | and | swap | KILLED | 1 | `test_evidence_out_without_a_value_is_usage` | `arg == "--evidence-out" and index + 1 < len(argv)` |
| 5 | `notion_sandbox.py:177` | and | neg0 | KILLED | 44 | `test_override_env_refuses[-NOTION_CONFIG]` | `arg == "--evidence-out" and index + 1 < len(argv)` |
| 6 | `notion_sandbox.py:177` | and | neg1 | KILLED | 33 | `test_override_env_refuses[-NOTION_CONFIG]` | `arg == "--evidence-out" and index + 1 < len(argv)` |
| 7 | `notion_sandbox.py:196` | or | swap | KILLED | 1 | `test_naive_clock_is_refused` | `type(moment) is not datetime or moment.tzinfo is None` |
| 8 | `notion_sandbox.py:196` | or | neg0 | KILLED | 119 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `type(moment) is not datetime or moment.tzinfo is None` |
| 9 | `notion_sandbox.py:196` | or | neg1 | KILLED | 120 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `type(moment) is not datetime or moment.tzinfo is None` |
| 10 | `notion_sandbox.py:202` | and | swap | KILLED | 5 | `test_short_token_is_refused` | `token is not None and token_shape_ok(token)` |
| 11 | `notion_sandbox.py:202` | and | neg0 | KILLED | 56 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `token is not None and token_shape_ok(token)` |
| 12 | `notion_sandbox.py:202` | and | neg1 | KILLED | 57 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `token is not None and token_shape_ok(token)` |
| 13 | `notion_sandbox.py:295` | or | swap | KILLED | 33 | `test_override_env_refuses[-NOTION_CONFIG]` | `argv_names_a_target(arguments) or environ_names_a_target(env) or cert_env_set(env)` |
| 14 | `notion_sandbox.py:295` | or | neg0 | KILLED | 59 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `argv_names_a_target(arguments) or environ_names_a_target(env) or cert_env_set(env)` |
| 15 | `notion_sandbox.py:295` | or | neg1 | KILLED | 89 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `argv_names_a_target(arguments) or environ_names_a_target(env) or cert_env_set(env)` |
| 16 | `notion_sandbox.py:295` | or | neg2 | KILLED | 59 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `argv_names_a_target(arguments) or environ_names_a_target(env) or cert_env_set(env)` |
| 17 | `notion_sandbox.py:302` | or | swap | KILLED | 1 | `test_encoded_token_evidence_path_writes_nothing` | `str(evidence) == "" or leaks(str(evidence), secret)` |
| 18 | `notion_sandbox.py:302` | or | neg0 | KILLED | 72 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `str(evidence) == "" or leaks(str(evidence), secret)` |
| 19 | `notion_sandbox.py:302` | or | neg1 | KILLED | 73 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `str(evidence) == "" or leaks(str(evidence), secret)` |
| 20 | `notion_sandbox.py:305` | and | swap | KILLED | 49 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `parsed.execute and parsed.dry_run` |
| 21 | `notion_sandbox.py:305` | and | neg0 | KILLED | 2 | `test_both_flags_and_secret_evidence_path_refuse` | `parsed.execute and parsed.dry_run` |
| 22 | `notion_sandbox.py:305` | and | neg1 | KILLED | 49 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `parsed.execute and parsed.dry_run` |
| 23 | `notion_sandbox.py:438` | or | swap | KILLED | 17 | `test_execute_on_the_fake_adapter_writes_evidence` | `_user_id(bot) or ""` |
| 24 | `notion_sandbox.py:438` | or | neg0 | KILLED | 18 | `test_execute_on_the_fake_adapter_writes_evidence` | `_user_id(bot) or ""` |
| 25 | `notion_sandbox.py:438` | or | neg1 | KILLED | 1 | `test_empty_bot_user_id_still_executes` | `_user_id(bot) or ""` |
| 26 | `notion_sandbox.py:572` | and | swap | KILLED | 1 | `test_both_flags_and_secret_evidence_path_refuse` | `path is not None and str(path) != "" and not leaks(str(path), token)` |
| 27 | `notion_sandbox.py:572` | and | neg0 | KILLED | 33 | `test_override_env_refuses[-NOTION_CONFIG]` | `path is not None and str(path) != "" and not leaks(str(path), token)` |
| 28 | `notion_sandbox.py:572` | and | neg1 | KILLED | 33 | `test_override_env_refuses[-NOTION_CONFIG]` | `path is not None and str(path) != "" and not leaks(str(path), token)` |
| 29 | `notion_sandbox.py:572` | and | neg2 | KILLED | 34 | `test_override_env_refuses[-NOTION_CONFIG]` | `path is not None and str(path) != "" and not leaks(str(path), token)` |
| 30 | `notion_sandbox.py:580` | and | swap | KILLED | 1 | `test_system_exit_status_is_normalized` | `type(exc.code) is int and exc.code != 0` |
| 31 | `notion_sandbox.py:580` | and | neg0 | KILLED | 1 | `test_system_exit_status_is_normalized` | `type(exc.code) is int and exc.code != 0` |
| 32 | `notion_sandbox.py:580` | and | neg1 | KILLED | 1 | `test_system_exit_status_is_normalized` | `type(exc.code) is int and exc.code != 0` |
| 33 | `notion_sandbox_guard.py:156` | or | swap | KILLED | 2 | `test_target_and_parent_guards` | `type(bot.user_type) is not str or bot.user_type != "bot"` |
| 34 | `notion_sandbox_guard.py:156` | or | neg0 | KILLED | 35 | `test_target_and_parent_guards` | `type(bot.user_type) is not str or bot.user_type != "bot"` |
| 35 | `notion_sandbox_guard.py:156` | or | neg1 | KILLED | 36 | `test_target_and_parent_guards` | `type(bot.user_type) is not str or bot.user_type != "bot"` |
| 36 | `notion_sandbox_guard.py:158` | or | swap | KILLED | 6 | `test_target_and_parent_guards` | `page.archived or page.parent_type in {"database_id", "data_source_id"}` |
| 37 | `notion_sandbox_guard.py:158` | or | neg0 | KILLED | 38 | `test_target_and_parent_guards` | `page.archived or page.parent_type in {"database_id", "data_source_id"}` |
| 38 | `notion_sandbox_guard.py:158` | or | neg1 | KILLED | 37 | `test_target_and_parent_guards` | `page.archived or page.parent_type in {"database_id", "data_source_id"}` |
| 39 | `notion_sandbox_guard.py:178` | or | swap | KILLED | 1 | `test_token_env_and_redaction_units` | `type(value) is not str or value == ""` |
| 40 | `notion_sandbox_guard.py:178` | or | neg0 | KILLED | 58 | `test_token_env_and_redaction_units` | `type(value) is not str or value == ""` |
| 41 | `notion_sandbox_guard.py:178` | or | neg1 | KILLED | 58 | `test_token_env_and_redaction_units` | `type(value) is not str or value == ""` |
| 42 | `notion_sandbox_guard.py:196` | and | swap | KILLED | 26 | `test_execute_on_the_fake_adapter_writes_evidence` | `found != "" and found != SANDBOX_SPACE_ID` |
| 43 | `notion_sandbox_guard.py:196` | and | neg0 | KILLED | 11 | `test_wrong_space_on_create_return_stops` | `found != "" and found != SANDBOX_SPACE_ID` |
| 44 | `notion_sandbox_guard.py:196` | and | neg1 | KILLED | 26 | `test_execute_on_the_fake_adapter_writes_evidence` | `found != "" and found != SANDBOX_SPACE_ID` |
| 45 | `notion_sandbox_guard.py:212` | or | swap | KILLED | 1 | `test_token_env_and_redaction_units` | `token.strip() == "" or token in {"true", "false", "null"}` |
| 46 | `notion_sandbox_guard.py:212` | or | neg0 | KILLED | 2 | `test_token_env_and_redaction_units` | `token.strip() == "" or token in {"true", "false", "null"}` |
| 47 | `notion_sandbox_guard.py:212` | or | neg1 | KILLED | 2 | `test_token_env_and_redaction_units` | `token.strip() == "" or token in {"true", "false", "null"}` |
| 48 | `notion_sandbox_guard.py:217` | or | swap | KILLED | 117 | `test_token_env_and_redaction_units` | `token is None or not token_shape_ok(token)` |
| 49 | `notion_sandbox_guard.py:217` | or | neg0 | KILLED | 117 | `test_token_env_and_redaction_units` | `token is None or not token_shape_ok(token)` |
| 50 | `notion_sandbox_guard.py:217` | or | neg1 | KILLED | 4 | `test_token_env_and_redaction_units` | `token is None or not token_shape_ok(token)` |
| 51 | `notion_sandbox_guard.py:224` | and | swap | EQUIVALENT | 0 | `—` | `digest not in forms and digest != token` |
| 52 | `notion_sandbox_guard.py:224` | and | neg0 | KILLED | 4 | `test_token_env_and_redaction_units` | `digest not in forms and digest != token` |
| 53 | `notion_sandbox_guard.py:224` | and | neg1 | KILLED | 4 | `test_token_env_and_redaction_units` | `digest not in forms and digest != token` |
| 54 | `notion_sandbox_guard.py:232` | and | swap | KILLED | 116 | `test_token_env_and_redaction_units` | `token is not None and token != "" and not _unsafe_exact(token) and token in cleaned` |
| 55 | `notion_sandbox_guard.py:232` | and | neg0 | KILLED | 116 | `test_token_env_and_redaction_units` | `token is not None and token != "" and not _unsafe_exact(token) and token in cleaned` |
| 56 | `notion_sandbox_guard.py:232` | and | neg1 | KILLED | 1 | `test_token_env_and_redaction_units` | `token is not None and token != "" and not _unsafe_exact(token) and token in cleaned` |
| 57 | `notion_sandbox_guard.py:232` | and | neg2 | KILLED | 1 | `test_token_env_and_redaction_units` | `token is not None and token != "" and not _unsafe_exact(token) and token in cleaned` |
| 58 | `notion_sandbox_guard.py:232` | and | neg3 | KILLED | 1 | `test_token_env_and_redaction_units` | `token is not None and token != "" and not _unsafe_exact(token) and token in cleaned` |
| 59 | `notion_sandbox_guard.py:263` | and | swap | KILLED | 1 | `test_token_env_and_redaction_units` | `stage.get("name") == "qa" and type(found) is str` |
| 60 | `notion_sandbox_guard.py:263` | and | neg0 | KILLED | 1 | `test_token_env_and_redaction_units` | `stage.get("name") == "qa" and type(found) is str` |
| 61 | `notion_sandbox_guard.py:263` | and | neg1 | KILLED | 1 | `test_token_env_and_redaction_units` | `stage.get("name") == "qa" and type(found) is str` |
| 62 | `notion_sandbox_guard.py:283` | and | swap | KILLED | 111 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `token is not None and token != "" and not _unsafe_exact(token) and token in text` |
| 63 | `notion_sandbox_guard.py:283` | and | neg0 | KILLED | 8 | `test_short_token_is_refused` | `token is not None and token != "" and not _unsafe_exact(token) and token in text` |
| 64 | `notion_sandbox_guard.py:283` | and | neg1 | KILLED | 1 | `test_hex_token_equal_to_the_page_id_sends_nothing` | `token is not None and token != "" and not _unsafe_exact(token) and token in text` |
| 65 | `notion_sandbox_guard.py:283` | and | neg2 | KILLED | 1 | `test_hex_token_equal_to_the_page_id_sends_nothing` | `token is not None and token != "" and not _unsafe_exact(token) and token in text` |
| 66 | `notion_sandbox_guard.py:283` | and | neg3 | KILLED | 106 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `token is not None and token != "" and not _unsafe_exact(token) and token in text` |
| 67 | `notion_sandbox_guard.py:318` | or | swap | KILLED | 1 | `test_proc_path_helper_rejects_proc_itself` | `absolute == Path("/proc") or Path("/proc") in absolute.parents` |
| 68 | `notion_sandbox_guard.py:318` | or | neg0 | KILLED | 110 | `test_write_evidence_redacts_a_planted_token` | `absolute == Path("/proc") or Path("/proc") in absolute.parents` |
| 69 | `notion_sandbox_guard.py:318` | or | neg1 | KILLED | 110 | `test_write_evidence_redacts_a_planted_token` | `absolute == Path("/proc") or Path("/proc") in absolute.parents` |
| 70 | `notion_sandbox_guard.py:323` | or | swap | EQUIVALENT | 0 | `—` | `str(path) == "" or path == Path() or under_proc(path)` |
| 71 | `notion_sandbox_guard.py:323` | or | neg0 | KILLED | 109 | `test_write_evidence_redacts_a_planted_token` | `str(path) == "" or path == Path() or under_proc(path)` |
| 72 | `notion_sandbox_guard.py:323` | or | neg1 | KILLED | 109 | `test_write_evidence_redacts_a_planted_token` | `str(path) == "" or path == Path() or under_proc(path)` |
| 73 | `notion_sandbox_guard.py:323` | or | neg2 | KILLED | 109 | `test_write_evidence_redacts_a_planted_token` | `str(path) == "" or path == Path() or under_proc(path)` |
| 74 | `notion_sandbox_guard.py:338` | or | swap | EQUIVALENT | 0 | `—` | `stat.S_ISLNK(parent_info.st_mode) or not stat.S_ISDIR(parent_info.st_mode)` |
| 75 | `notion_sandbox_guard.py:338` | or | neg0 | KILLED | 109 | `test_write_evidence_redacts_a_planted_token` | `stat.S_ISLNK(parent_info.st_mode) or not stat.S_ISDIR(parent_info.st_mode)` |
| 76 | `notion_sandbox_guard.py:338` | or | neg1 | KILLED | 109 | `test_write_evidence_redacts_a_planted_token` | `stat.S_ISLNK(parent_info.st_mode) or not stat.S_ISDIR(parent_info.st_mode)` |
| 77 | `notion_sandbox_guard.py:368` | and | swap | KILLED | 1 | `test_enospc_ignores_pages_that_are_not_ids` | `type(page_id) is str and page_id != ""` |
| 78 | `notion_sandbox_guard.py:368` | and | neg0 | KILLED | 2 | `test_enospc_after_creates_prints_ids` | `type(page_id) is str and page_id != ""` |
| 79 | `notion_sandbox_guard.py:368` | and | neg1 | KILLED | 1 | `test_enospc_after_creates_prints_ids` | `type(page_id) is str and page_id != ""` |
| 80 | `notion_sandbox_guard.py:377` | or | swap | KILLED | 1 | `timeout` | `written <= 0 or written > len(pending)` |
| 81 | `notion_sandbox_guard.py:377` | or | neg0 | KILLED | 1 | `timeout` | `written <= 0 or written > len(pending)` |
| 82 | `notion_sandbox_guard.py:377` | or | neg1 | KILLED | 105 | `test_write_evidence_redacts_a_planted_token` | `written <= 0 or written > len(pending)` |
| 83 | `notion_sandbox_guard.py:390` | and | swap | KILLED | 2 | `test_swapped_evidence_file_does_not_exit_ok` | `opened.st_ino == current.st_ino and opened.st_dev == current.st_dev` |
| 84 | `notion_sandbox_guard.py:390` | and | neg0 | KILLED | 105 | `test_write_evidence_redacts_a_planted_token` | `opened.st_ino == current.st_ino and opened.st_dev == current.st_dev` |
| 85 | `notion_sandbox_guard.py:390` | and | neg1 | KILLED | 103 | `test_write_evidence_redacts_a_planted_token` | `opened.st_ino == current.st_ino and opened.st_dev == current.st_dev` |
| 86 | `notion_sandbox_guard.py:455` | and | swap | KILLED | 1 | `test_repo_root_ignores_a_partial_marker` | `(candidate / "pyproject.toml").is_file() and (candidate / "docs" / "control").is_dir()` |
| 87 | `notion_sandbox_guard.py:455` | and | neg0 | KILLED | 1 | `test_repo_root_needs_both_markers` | `(candidate / "pyproject.toml").is_file() and (candidate / "docs" / "control").is_dir()` |
| 88 | `notion_sandbox_guard.py:455` | and | neg1 | KILLED | 2 | `test_repo_root_needs_both_markers` | `(candidate / "pyproject.toml").is_file() and (candidate / "docs" / "control").is_dir()` |
| 89 | `notion_sandbox_guard.py:459` | and | swap | EQUIVALENT | 0 | `—` | `(candidate / "pyproject.toml").is_file() and (candidate / "docs" / "control").is_dir()` |
| 90 | `notion_sandbox_guard.py:459` | and | neg0 | KILLED | 1 | `test_repo_root_falls_back_to_cwd` | `(candidate / "pyproject.toml").is_file() and (candidate / "docs" / "control").is_dir()` |
| 91 | `notion_sandbox_guard.py:459` | and | neg1 | KILLED | 1 | `test_repo_root_falls_back_to_cwd` | `(candidate / "pyproject.toml").is_file() and (candidate / "docs" / "control").is_dir()` |
| 92 | `notion_sandbox_guard.py:477` | or | swap | KILLED | 1 | `test_git_sha_rejects_a_bad_rev_parse` | `completed.returncode != 0 or len(sha) != 40` |
| 93 | `notion_sandbox_guard.py:477` | or | neg0 | KILLED | 116 | `test_git_sha_rejects_a_bad_rev_parse` | `completed.returncode != 0 or len(sha) != 40` |
| 94 | `notion_sandbox_guard.py:477` | or | neg1 | KILLED | 116 | `test_git_sha_rejects_a_bad_rev_parse` | `completed.returncode != 0 or len(sha) != 40` |
| 95 | `notion_sandbox_guard.py:496` | or | swap | KILLED | 1 | `test_string_revision_is_unreadable` | `type(revision) is not int or type(session) is not int or type(head) is not str` |
| 96 | `notion_sandbox_guard.py:496` | or | neg0 | KILLED | 114 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `type(revision) is not int or type(session) is not int or type(head) is not str` |
| 97 | `notion_sandbox_guard.py:496` | or | neg1 | KILLED | 113 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `type(revision) is not int or type(session) is not int or type(head) is not str` |
| 98 | `notion_sandbox_guard.py:496` | or | neg2 | KILLED | 113 | `test_wrong_space_refuses_with_zero_writes[89282fb0-ffff-8106-809e-0003c027fa07]` | `type(revision) is not int or type(session) is not int or type(head) is not str` |
| 99 | `notion_sandbox_live.py:149` | or | swap | KILLED | 1 | `test_request_body_parent_is_asserted` | `type(sent_parent) is not dict or sent_parent.get("page_id") != parent or sent_parent.get("type") != "page_id"` |
| 100 | `notion_sandbox_live.py:149` | or | neg0 | KILLED | 9 | `test_live_child_page_does_not_count_its_own_write` | `type(sent_parent) is not dict or sent_parent.get("page_id") != parent or sent_parent.get("type") != "page_id"` |
| 101 | `notion_sandbox_live.py:149` | or | neg1 | KILLED | 10 | `test_live_child_page_does_not_count_its_own_write` | `type(sent_parent) is not dict or sent_parent.get("page_id") != parent or sent_parent.get("type") != "page_id"` |
| 102 | `notion_sandbox_live.py:149` | or | neg2 | KILLED | 9 | `test_live_child_page_does_not_count_its_own_write` | `type(sent_parent) is not dict or sent_parent.get("page_id") != parent or sent_parent.get("type") != "page_id"` |
| 103 | `notion_sandbox_live.py:164` | or | swap | KILLED | 1 | `test_wrong_space_create_is_not_published` | `page_id == "" or space_conflicts(page.space_id)` |
| 104 | `notion_sandbox_live.py:164` | or | neg0 | KILLED | 5 | `test_doc_shaped_pages_execute_without_a_space` | `page_id == "" or space_conflicts(page.space_id)` |
| 105 | `notion_sandbox_live.py:164` | or | neg1 | KILLED | 6 | `test_doc_shaped_pages_execute_without_a_space` | `page_id == "" or space_conflicts(page.space_id)` |
| 106 | `notion_sandbox_live.py:170` | or | swap | KILLED | 2 | `test_live_child_page_does_not_count_its_own_write` | `evidence_ids is None or evidence_rows is None or page_id in evidence_ids` |
| 107 | `notion_sandbox_live.py:170` | or | neg0 | KILLED | 3 | `test_doc_shaped_interrupt_after_store_records_the_created_id[0-exc0]` | `evidence_ids is None or evidence_rows is None or page_id in evidence_ids` |
| 108 | `notion_sandbox_live.py:170` | or | neg1 | KILLED | 3 | `test_doc_shaped_interrupt_after_store_records_the_created_id[0-exc0]` | `evidence_ids is None or evidence_rows is None or page_id in evidence_ids` |
| 109 | `notion_sandbox_live.py:170` | or | neg2 | KILLED | 3 | `test_doc_shaped_interrupt_after_store_records_the_created_id[0-exc0]` | `evidence_ids is None or evidence_rows is None or page_id in evidence_ids` |
| 110 | `notion_sandbox_live.py:179` | or | swap | KILLED | 1 | `test_hex_token_equal_to_the_page_id_sends_nothing` | `leaks(url, self._token) or leaks(url.replace("-", ""), self._token)` |
| 111 | `notion_sandbox_live.py:179` | or | neg0 | KILLED | 21 | `test_live_client_reads_without_writing_and_redacts` | `leaks(url, self._token) or leaks(url.replace("-", ""), self._token)` |
| 112 | `notion_sandbox_live.py:179` | or | neg1 | KILLED | 22 | `test_live_client_reads_without_writing_and_redacts` | `leaks(url, self._token) or leaks(url.replace("-", ""), self._token)` |
| 113 | `notion_sandbox_live.py:192` | and | swap | KILLED | 21 | `test_live_client_reads_without_writing_and_redacts` | `type(status) is int and 300 <= status < 400` |
| 114 | `notion_sandbox_live.py:192` | and | neg0 | KILLED | 23 | `test_live_client_reads_without_writing_and_redacts` | `type(status) is int and 300 <= status < 400` |
| 115 | `notion_sandbox_live.py:192` | and | neg1 | KILLED | 2 | `test_redirect_is_not_followed` | `type(status) is int and 300 <= status < 400` |
| 116 | `notion_sandbox_live.py:215` | or | swap | KILLED | 1 | `test_non_string_bot_id_is_rejected` | `type(user_id) is not str or type(user_type) is not str` |
| 117 | `notion_sandbox_live.py:215` | or | neg0 | KILLED | 17 | `test_live_client_reads_without_writing_and_redacts` | `type(user_id) is not str or type(user_type) is not str` |
| 118 | `notion_sandbox_live.py:215` | or | neg1 | KILLED | 16 | `test_live_client_reads_without_writing_and_redacts` | `type(user_id) is not str or type(user_type) is not str` |
| 119 | `notion_sandbox_live.py:219` | and | swap | KILLED | 2 | `test_missing_workspace_id_writes_nothing` | `type(bot) is dict and type(bot.get("workspace_id")) is str` |
| 120 | `notion_sandbox_live.py:219` | and | neg0 | KILLED | 7 | `test_live_client_reads_without_writing_and_redacts` | `type(bot) is dict and type(bot.get("workspace_id")) is str` |
| 121 | `notion_sandbox_live.py:219` | and | neg1 | KILLED | 7 | `test_live_client_reads_without_writing_and_redacts` | `type(bot) is dict and type(bot.get("workspace_id")) is str` |
| 122 | `notion_sandbox_live.py:236` | or | swap | KILLED | 1 | `test_database_parent_and_missing_object_write_nothing` | `type(payload) is not dict or payload.get("object") != "page"` |
| 123 | `notion_sandbox_live.py:236` | or | neg0 | KILLED | 24 | `test_live_client_reads_without_writing_and_redacts` | `type(payload) is not dict or payload.get("object") != "page"` |
| 124 | `notion_sandbox_live.py:236` | or | neg1 | KILLED | 25 | `test_live_client_reads_without_writing_and_redacts` | `type(payload) is not dict or payload.get("object") != "page"` |
| 125 | `notion_sandbox_live.py:253` | and | swap | KILLED | 2 | `test_live_space_fallback_is_only_the_asserted_parent` | `space == "" and page_id == canonical_id(expected_id)` |
| 126 | `notion_sandbox_live.py:253` | and | neg0 | KILLED | 7 | `test_live_client_reads_without_writing_and_redacts` | `space == "" and page_id == canonical_id(expected_id)` |
| 127 | `notion_sandbox_live.py:253` | and | neg1 | KILLED | 7 | `test_live_client_reads_without_writing_and_redacts` | `space == "" and page_id == canonical_id(expected_id)` |
| 128 | `notion_sandbox_live.py:256` | or | swap | KILLED | 1 | `test_parse_page_keeps_a_url_and_fills_a_blank_one` | `type(url) is not str or url == ""` |
| 129 | `notion_sandbox_live.py:256` | or | neg0 | KILLED | 1 | `test_parse_page_keeps_a_url_and_fills_a_blank_one` | `type(url) is not str or url == ""` |
| 130 | `notion_sandbox_live.py:256` | or | neg1 | KILLED | 1 | `test_parse_page_keeps_a_url_and_fills_a_blank_one` | `type(url) is not str or url == ""` |
| 131 | `notion_sandbox_live.py:260` | or | swap | KILLED | 1 | `test_string_in_trash_is_rejected` | `archived_flag is None or trash_flag is None` |
| 132 | `notion_sandbox_live.py:260` | or | neg0 | KILLED | 24 | `test_live_client_reads_without_writing_and_redacts` | `archived_flag is None or trash_flag is None` |
| 133 | `notion_sandbox_live.py:260` | or | neg1 | KILLED | 25 | `test_live_client_reads_without_writing_and_redacts` | `archived_flag is None or trash_flag is None` |
| 134 | `notion_sandbox_live.py:262` | or | swap | KILLED | 2 | `test_trashed_parent_writes_nothing[archived]` | `archived_flag or trash_flag` |
| 135 | `notion_sandbox_live.py:262` | or | neg0 | KILLED | 6 | `test_trashed_parent_writes_nothing[archived]` | `archived_flag or trash_flag` |
| 136 | `notion_sandbox_live.py:262` | or | neg1 | KILLED | 6 | `test_trashed_parent_writes_nothing[in_trash]` | `archived_flag or trash_flag` |
| 137 | `notion_sandbox_live.py:277` | or | swap | KILLED | 19 | `test_live_client_reads_without_writing_and_redacts` | `type(value) is not str or value == ""` |
| 138 | `notion_sandbox_live.py:277` | or | neg0 | KILLED | 22 | `test_live_client_reads_without_writing_and_redacts` | `type(value) is not str or value == ""` |
| 139 | `notion_sandbox_live.py:277` | or | neg1 | KILLED | 3 | `test_doc_shaped_pages_execute_without_a_space` | `type(value) is not str or value == ""` |
| 140 | `notion_sandbox_live.py:309` | and | swap | KILLED | 1 | `test_proxy_map_drops_non_strings` | `type(key) is str and type(value) is str` |
| 141 | `notion_sandbox_live.py:309` | and | neg0 | KILLED | 2 | `test_proxy_map_reads_string_proxy_entries` | `type(key) is str and type(value) is str` |
| 142 | `notion_sandbox_live.py:309` | and | neg1 | KILLED | 2 | `test_proxy_map_reads_string_proxy_entries` | `type(key) is str and type(value) is str` |
| 143 | `notion_sandbox_live.py:318` | and | swap | KILLED | 1 | `test_explicit_space_skips_a_non_id` | `type(value) is str and canonical_id(value) != ""` |
| 144 | `notion_sandbox_live.py:318` | and | neg0 | KILLED | 4 | `test_live_space_fallback_is_only_the_asserted_parent` | `type(value) is str and canonical_id(value) != ""` |
| 145 | `notion_sandbox_live.py:318` | and | neg1 | KILLED | 4 | `test_live_space_fallback_is_only_the_asserted_parent` | `type(value) is str and canonical_id(value) != ""` |
| 146 | `notion_sandbox_pipeline.py:146` | or | swap | EQUIVALENT | 0 | `—` | `page_id == "" or space_conflicts(page.space_id)` |
| 147 | `notion_sandbox_pipeline.py:146` | or | neg0 | KILLED | 21 | `test_execute_on_the_fake_adapter_writes_evidence` | `page_id == "" or space_conflicts(page.space_id)` |
| 148 | `notion_sandbox_pipeline.py:146` | or | neg1 | KILLED | 21 | `test_execute_on_the_fake_adapter_writes_evidence` | `page_id == "" or space_conflicts(page.space_id)` |
| 149 | `notion_sandbox_pipeline.py:176` | or | swap | KILLED | 1 | `test_sandbox_parent_in_a_foreign_space_fails_the_chain` | `space_conflicts(current.space_id) or current.archived` |
| 150 | `notion_sandbox_pipeline.py:176` | or | neg0 | KILLED | 16 | `test_execute_on_the_fake_adapter_writes_evidence` | `space_conflicts(current.space_id) or current.archived` |
| 151 | `notion_sandbox_pipeline.py:176` | or | neg1 | KILLED | 15 | `test_execute_on_the_fake_adapter_writes_evidence` | `space_conflicts(current.space_id) or current.archived` |
| 152 | `notion_sandbox_pipeline.py:181` | or | swap | KILLED | 2 | `test_broken_ancestor_stops_later_writes` | `parent_id == "" or page_id == "" or page_id in seen` |
| 153 | `notion_sandbox_pipeline.py:181` | or | neg0 | KILLED | 17 | `test_execute_on_the_fake_adapter_writes_evidence` | `parent_id == "" or page_id == "" or page_id in seen` |
| 154 | `notion_sandbox_pipeline.py:181` | or | neg1 | KILLED | 16 | `test_execute_on_the_fake_adapter_writes_evidence` | `parent_id == "" or page_id == "" or page_id in seen` |
| 155 | `notion_sandbox_pipeline.py:181` | or | neg2 | KILLED | 16 | `test_execute_on_the_fake_adapter_writes_evidence` | `parent_id == "" or page_id == "" or page_id in seen` |
| 156 | `notion_sandbox_pipeline.py:185` | or | swap | KILLED | 1 | `test_trashed_product_page_stops_further_writes` | `space_conflicts(current.space_id) or current.archived` |
| 157 | `notion_sandbox_pipeline.py:185` | or | neg0 | KILLED | 15 | `test_execute_on_the_fake_adapter_writes_evidence` | `space_conflicts(current.space_id) or current.archived` |
| 158 | `notion_sandbox_pipeline.py:185` | or | neg1 | KILLED | 15 | `test_execute_on_the_fake_adapter_writes_evidence` | `space_conflicts(current.space_id) or current.archived` |
| 159 | `notion_sandbox_pipeline.py:218` | or | swap | KILLED | 2 | `test_trashed_confirm_stops_further_writes` | `space_conflicts(confirmed.space_id) or confirmed.archived` |
| 160 | `notion_sandbox_pipeline.py:218` | or | neg0 | KILLED | 16 | `test_execute_on_the_fake_adapter_writes_evidence` | `space_conflicts(confirmed.space_id) or confirmed.archived` |
| 161 | `notion_sandbox_pipeline.py:218` | or | neg1 | KILLED | 16 | `test_execute_on_the_fake_adapter_writes_evidence` | `space_conflicts(confirmed.space_id) or confirmed.archived` |
| 162 | `notion_sandbox_pipeline.py:223` | and | swap | EQUIVALENT | 0 | `—` | `ctx.created and ctx.created[-1].get("id") == page_id` |
| 163 | `notion_sandbox_pipeline.py:223` | and | neg0 | KILLED | 1 | `test_token_in_created_url_exits_70` | `ctx.created and ctx.created[-1].get("id") == page_id` |
| 164 | `notion_sandbox_pipeline.py:223` | and | neg1 | KILLED | 1 | `test_token_in_created_url_exits_70` | `ctx.created and ctx.created[-1].get("id") == page_id` |
| 165 | `notion_sandbox_pipeline.py:253` | or | swap | KILLED | 1 | `test_variants_without_a_product_page_are_a_sandbox_error` | `ctx.probe is None or ctx.product_page_id is None or type(spec) is not ProductSpec` |
| 166 | `notion_sandbox_pipeline.py:253` | or | neg0 | KILLED | 15 | `test_execute_on_the_fake_adapter_writes_evidence` | `ctx.probe is None or ctx.product_page_id is None or type(spec) is not ProductSpec` |
| 167 | `notion_sandbox_pipeline.py:253` | or | neg1 | KILLED | 16 | `test_execute_on_the_fake_adapter_writes_evidence` | `ctx.probe is None or ctx.product_page_id is None or type(spec) is not ProductSpec` |
| 168 | `notion_sandbox_pipeline.py:253` | or | neg2 | KILLED | 15 | `test_execute_on_the_fake_adapter_writes_evidence` | `ctx.probe is None or ctx.product_page_id is None or type(spec) is not ProductSpec` |

## 2026-10-07 — Session 07 sandbox run: tip-sync onto the W9 squash

Not a session close. This is not SESSION_07 COMPLETE. State revision 57 → 58. `head_sha` is the W9 squash `a4e9b025021b4effbb2b2879c1db756403cb1676`. It is the tip-sync pointer. It is not this commit. `evidence_closure_commit_sha` stays the Session 06 closure tip `0f94d585f23d79e5ac18479f01e14f67cbaad332`. `last_verified_commit` stays bootstrap `1abf0d7cca3a6b8cd7efcd0a45523538fd5bfd9d`. Twelve session 7 evidence keys stay false. `commissioned_agents` stays empty. `session_status` stays incomplete. Exit 78 stays HELD. The §11 sandbox CLI is still not run live. W10 is in flight from `a4e9b025` and will also bump STATE, so whichever PR merges second re-syncs. `updated_at` is `2026-10-07T23:01:03Z`.

The sandbox modules are unchanged from `df5413ac6f3df278d91a5bfc28601760931e62af`. That commit's CI verify run is `37698651795`, job `113056508051`, SUCCESS. The if-flip table below was measured on that commit: 104 rows, 104 killed, 0 equivalent, Failed sum 2109. T45 is row 54, `notion_sandbox_guard.py:288`, Failed 1. Full local pytest on this tip-sync tree: 2630 collected, 2425 passed, 193 skipped, 12 failed. All 12 failures are `test_compose_preserves_the_postgres_password` with `FileNotFoundError` because the `docker` binary is absent. They are local-only. CI is the gate. `ruff format --check`, `ruff check`, and `pyright` 1.1.411 report clean. This tip-sync commit's CI run is not invented here.

## 2026-10-07 — Session 07 sandbox run CLI, round 2

Not a session close. `state_revision` stays 56. `IMPLEMENTATION_STATE.json` is not edited in this round. Twelve session 7 evidence keys stay false. The runner is `python -m money_machine.cli.notion_sandbox`. This session does not execute it against Notion. Prompt-integrity review: `docs/control/reviews/2026-10-07-session-07-prompt-integrity.md`. Fixture tests in `tests/unit/cli/test_notion_sandbox.py`: 111 passed. With `tests/unit/integrations/notion/test_router.py`: 122 passed. Sockets stay blocked. Exit 78 stays HELD.

`get_public_url` is a fixture read. It is not in `PIPELINE_WRITE_METHODS` and it is excluded from `write_counts`. The execute evidence splits fixture counts from the live `create_child_page` count.

Exit codes: 0 ok, 64 usage, a bad token, an evidence-path refusal, or `NOTION_CONFIG` / `NOTION_SANDBOX_CONFIG` / `NOTION_TOKEN_FILE`, 65 target mismatch, 66 missing token, 69 git, control, read, stage, clock, or an interrupted run, 70 redaction self-check failure. A whitespace or junk token (`" "`, `"true"`) exits 64 and the evidence JSON is not rewritten with `[REDACTED]`. A failed redaction self-check exits 70 with stderr `redaction self-check failed` and does not log ok. Base64 and underscore-percent-encoded copies of a shaped token are redacted. `qa_verdict` still returns a supplied `PASS`; the CLI cannot produce that status while the qa runner is None, and `test_token_env_and_redaction_units` pins the mapping. The sandbox tests do not emit `StarletteDeprecationWarning`, and these modules do not import Starlette.

If-flip sweep on this commit, after the killing tests. Every `if` test in `notion_sandbox.py`, `notion_sandbox_guard.py`, `notion_sandbox_live.py`, and `notion_sandbox_pipeline.py` was negated, `tests/unit/cli/test_notion_sandbox.py` was run, and the edit was reverted. 104 flips. 104 killed. 0 equivalent. The Failed column sums to 2109. A row is killed only when that run's pytest exit is non-zero. T45 is row 54, `notion_sandbox_guard.py:288`, the second `if leaks(text, token)` inside `render_evidence`. Failed 1. `test_failed_redaction_exits_70` keeps the redacted document (`bot_user_id` is `[REDACTED]`, `asserted_space_id` stays). The earlier claim of 60 mutations, 58 killed, 2 equivalent, Failed sum 125, and the url-leak EQUIVALENT, are withdrawn. The verifier's 146/46/10 figures were measured on `07f6cb00`, not on this tree. This commit's CI run is not invented here.

Blocker to test. Lying create id: `test_lying_create_id_stops_before_colours` (exit 69, 1 create). Create-return space: `test_wrong_space_on_create_return_stops` (exit 69, 1 create). Response parent: `test_lying_response_parent_stops` (exit 69, 1 create; the re-read parent is the requested parent, so dropping the response check would finish). Database object and missing object: `test_database_parent_and_missing_object_write_nothing` (exit 69, GET GET). `in_trash` and `archived`: `test_trashed_parent_writes_nothing` (exit 65, GET GET). String `in_trash`: `test_string_in_trash_is_rejected` (exit 69). Raw parent body: `test_live_child_page_does_not_count_its_own_write` posts the dashed parent when called with the undashed id. Non-canonical fetch: `test_live_client_reads_without_writing_and_redacts` requests `/v1/pages/` plus the dashed id. Space fallback: `test_live_space_fallback_is_only_the_asserted_parent`. `database_id` parent and `target_ok`: `test_database_id_parent_is_not_a_page_parent` (exit 65, GET GET) and `test_target_and_parent_guards`. Hex token equal to the page id: `test_hex_token_equal_to_the_page_id_sends_nothing` (0 requests). Token in a created URL: `test_token_in_created_url_exits_70` (exit 70, 5 creates). Evidence `OSError`: `test_evidence_write_oserror_is_redacted` (exit 64, no traceback). Clock `RuntimeError`: `test_clock_runtime_error_is_redacted` (exit 69, 0 reads, no traceback). Whitespace token: `test_blank_or_junk_token_exits_64`. Preflight: `test_unwritable_directory_writes_nothing`, `test_evidence_refuses_existing_file_and_symlink`, `test_bad_git_dir_writes_nothing`, `test_git_missing_from_path_writes_nothing` (0 client writes; 64 or 69). Interrupt: `test_interrupt_writes_redacted_evidence` (exit 69, two created ids, `run_status` INTERRUPTED). Ignored config env: `test_override_env_refuses` for `NOTION_CONFIG`, `NOTION_SANDBOX_CONFIG`, and `NOTION_TOKEN_FILE`.


| # | Site | Result | Failed | Condition |
|---|---|---|---|---|
| 1 | `notion_sandbox.py:111` | KILLED | 3 | `runner_name is None` |
| 2 | `notion_sandbox.py:132` | KILLED | 10 | `not available or failed` |
| 3 | `notion_sandbox.py:136` | KILLED | 10 | `runner is None` |
| 4 | `notion_sandbox.py:173` | KILLED | 48 | `arg == "--evidence-out" and index + 1 < len(argv)` |
| 5 | `notion_sandbox.py:175` | KILLED | 1 | `arg.startswith("--evidence-out=")` |
| 6 | `notion_sandbox.py:192` | KILLED | 82 | `type(moment) is not datetime or moment.tzinfo is None` |
| 7 | `notion_sandbox.py:198` | KILLED | 29 | `token is not None and token_shape_ok(token)` |
| 8 | `notion_sandbox.py:281` | KILLED | 61 | `argv_names_a_target(arguments) or environ_names_a_target(env)` |
| 9 | `notion_sandbox.py:288` | KILLED | 38 | `str(evidence) == "" or leaks(str(evidence), secret)` |
| 10 | `notion_sandbox.py:291` | KILLED | 31 | `parsed.execute and parsed.dry_run` |
| 11 | `notion_sandbox.py:296` | KILLED | 30 | `token is None` |
| 12 | `notion_sandbox.py:308` | KILLED | 29 | `secret is None` |
| 13 | `notion_sandbox.py:346` | KILLED | 21 | `type(bot.user_type) is not str` |
| 14 | `notion_sandbox.py:364` | KILLED | 19 | `not target_ok(bot, page)` |
| 15 | `notion_sandbox.py:382` | KILLED | 13 | `mode == "dry-run"` |
| 16 | `notion_sandbox.py:413` | KILLED | 9 | `interrupted` |
| 17 | `notion_sandbox.py:417` | KILLED | 8 | `failed` |
| 18 | `notion_sandbox.py:445` | KILLED | 2 | `type(bot.user_id) is str` |
| 19 | `notion_sandbox.py:480` | KILLED | 1 | `error is not None` |
| 20 | `notion_sandbox.py:482` | KILLED | 1 | `any(stage.get("status") == "INTERRUPTED" for stage in stages)` |
| 21 | `notion_sandbox.py:485` | KILLED | 72 | `check == "FAIL"` |
| 22 | `notion_sandbox.py:487` | KILLED | 70 | `code == EXIT_OK` |
| 23 | `notion_sandbox.py:532` | KILLED | 32 | `path is not None and str(path) != "" and not leaks(str(path), token)` |
| 24 | `notion_sandbox.py:539` | KILLED | 1 | `isinstance(exc, SystemExit)` |
| 25 | `notion_sandbox.py:542` | KILLED | 1 | `isinstance(exc, KeyboardInterrupt)` |
| 26 | `notion_sandbox.py:555` | KILLED | 1 | `__name__ == "__main__"` |
| 27 | `notion_sandbox_guard.py:139` | KILLED | 25 | `type(value) is not str` |
| 28 | `notion_sandbox_guard.py:142` | KILLED | 25 | `len(compact) != 32` |
| 29 | `notion_sandbox_guard.py:144` | KILLED | 25 | `any(character not in "0123456789abcdef" for character in compact)` |
| 30 | `notion_sandbox_guard.py:151` | KILLED | 14 | `type(bot.user_type) is not str or bot.user_type != "bot"` |
| 31 | `notion_sandbox_guard.py:153` | KILLED | 17 | `page.archived or page.parent_type == "database_id"` |
| 32 | `notion_sandbox_guard.py:155` | KILLED | 13 | `canonical_id(bot.space_id) != SANDBOX_SPACE_ID` |
| 33 | `notion_sandbox_guard.py:157` | KILLED | 13 | `canonical_id(page.page_id) != SANDBOX_PARENT_PAGE_ID` |
| 34 | `notion_sandbox_guard.py:165` | KILLED | 11 | `candidate == ""` |
| 35 | `notion_sandbox_guard.py:173` | KILLED | 30 | `type(value) is not str or value == ""` |
| 36 | `notion_sandbox_guard.py:187` | KILLED | 41 | `head in _OVERRIDE_FLAGS` |
| 37 | `notion_sandbox_guard.py:189` | KILLED | 30 | `contains_secret_shape(arg)` |
| 38 | `notion_sandbox_guard.py:201` | KILLED | 81 | `token is None or not token_shape_ok(token)` |
| 39 | `notion_sandbox_guard.py:206` | KILLED | 2 | `encoded != token` |
| 40 | `notion_sandbox_guard.py:208` | KILLED | 2 | `digest not in forms and digest != token` |
| 41 | `notion_sandbox_guard.py:216` | KILLED | 81 | `token is not None and token != "" and not _unsafe_exact(token) and token in cleaned` |
| 42 | `notion_sandbox_guard.py:219` | KILLED | 2 | `form in cleaned` |
| 43 | `notion_sandbox_guard.py:226` | KILLED | 11 | `runner_name is None` |
| 44 | `notion_sandbox_guard.py:228` | KILLED | 11 | `outcome == "PASS"` |
| 45 | `notion_sandbox_guard.py:230` | KILLED | 5 | `outcome == "FAILED"` |
| 46 | `notion_sandbox_guard.py:232` | KILLED | 3 | `outcome == "BLOCKED"` |
| 47 | `notion_sandbox_guard.py:247` | KILLED | 1 | `stage.get("name") == "qa" and type(found) is str` |
| 48 | `notion_sandbox_guard.py:249` | KILLED | 6 | `status == "PASS"` |
| 49 | `notion_sandbox_guard.py:251` | KILLED | 6 | `status == "FAILED"` |
| 50 | `notion_sandbox_guard.py:253` | KILLED | 6 | `status == "BLOCKED"` |
| 51 | `notion_sandbox_guard.py:267` | KILLED | 72 | `token is not None and token != "" and not _unsafe_exact(token) and token in text` |
| 52 | `notion_sandbox_guard.py:269` | KILLED | 72 | `any(form in text for form in _encoded_forms(token))` |
| 53 | `notion_sandbox_guard.py:284` | KILLED | 73 | `leaks(text, token)` |
| 54 | `notion_sandbox_guard.py:288` | KILLED | 1 | `leaks(text, token)` |
| 55 | `notion_sandbox_guard.py:307` | KILLED | 74 | `str(path) == "" or path == Path() or _under_proc(path)` |
| 56 | `notion_sandbox_guard.py:315` | KILLED | 74 | `info is not None` |
| 57 | `notion_sandbox_guard.py:322` | KILLED | 74 | `stat.S_ISLNK(parent_info.st_mode) or not stat.S_ISDIR(parent_info.st_mode)` |
| 58 | `notion_sandbox_guard.py:324` | KILLED | 74 | `parent_info.st_mode & 0o200 == 0` |
| 59 | `notion_sandbox_guard.py:382` | KILLED | 80 | `(candidate / "pyproject.toml").is_file() and (candidate / "docs" / "control").is_dir()` |
| 60 | `notion_sandbox_guard.py:386` | KILLED | 1 | `(candidate / "pyproject.toml").is_file() and (candidate / "docs" / "control").is_dir()` |
| 61 | `notion_sandbox_guard.py:404` | KILLED | 81 | `completed.returncode != 0 or len(sha) != 40` |
| 62 | `notion_sandbox_guard.py:406` | KILLED | 80 | `any(character not in "0123456789abcdef" for character in sha)` |
| 63 | `notion_sandbox_guard.py:421` | KILLED | 79 | `type(revision) is not int or type(session) is not int or type(head) is not str` |
| 64 | `notion_sandbox_live.py:76` | KILLED | 8 | `bot is None` |
| 65 | `notion_sandbox_live.py:83` | KILLED | 8 | `expected == ""` |
| 66 | `notion_sandbox_live.py:88` | KILLED | 8 | `page is None` |
| 67 | `notion_sandbox_live.py:95` | KILLED | 2 | `not parent_is_allowed(parent, allowed)` |
| 68 | `notion_sandbox_live.py:107` | KILLED | 2 | `type(sent_parent) is not dict or sent_parent.get("page_id") != parent or sent_parent.get("type") ...` |
| 69 | `notion_sandbox_live.py:114` | KILLED | 1 | `page is None` |
| 70 | `notion_sandbox_live.py:121` | KILLED | 10 | `leaks(url, self._token) or leaks(url.replace("-", ""), self._token)` |
| 71 | `notion_sandbox_live.py:127` | KILLED | 2 | `body is not None` |
| 72 | `notion_sandbox_live.py:137` | KILLED | 9 | `type(raw) is not bytes` |
| 73 | `notion_sandbox_live.py:147` | KILLED | 8 | `type(payload) is not dict` |
| 74 | `notion_sandbox_live.py:151` | KILLED | 8 | `type(user_id) is not str or type(user_type) is not str` |
| 75 | `notion_sandbox_live.py:155` | KILLED | 1 | `type(bot) is dict and type(bot.get("workspace_id")) is str` |
| 76 | `notion_sandbox_live.py:162` | KILLED | 8 | `key not in payload` |
| 77 | `notion_sandbox_live.py:165` | KILLED | 3 | `type(value) is not bool` |
| 78 | `notion_sandbox_live.py:172` | KILLED | 9 | `type(payload) is not dict or payload.get("object") != "page"` |
| 79 | `notion_sandbox_live.py:175` | KILLED | 8 | `page_id == ""` |
| 80 | `notion_sandbox_live.py:181` | KILLED | 2 | `type(parent) is dict` |
| 81 | `notion_sandbox_live.py:182` | KILLED | 1 | `space == ""` |
| 82 | `notion_sandbox_live.py:185` | KILLED | 1 | `type(found_type) is str` |
| 83 | `notion_sandbox_live.py:187` | KILLED | 1 | `found_type == "page_id"` |
| 84 | `notion_sandbox_live.py:189` | KILLED | 2 | `space == "" and page_id == canonical_id(expected_id)` |
| 85 | `notion_sandbox_live.py:192` | KILLED | 1 | `type(url) is not str or url == ""` |
| 86 | `notion_sandbox_live.py:196` | KILLED | 9 | `archived_flag is None or trash_flag is None` |
| 87 | `notion_sandbox_live.py:212` | KILLED | 1 | `type(handlers) is not list` |
| 88 | `notion_sandbox_live.py:215` | KILLED | 1 | `isinstance(handler, urllib.request.ProxyHandler)` |
| 89 | `notion_sandbox_live.py:217` | KILLED | 1 | `type(found) is not dict` |
| 90 | `notion_sandbox_live.py:220` | KILLED | 1 | `type(key) is str and type(value) is str` |
| 91 | `notion_sandbox_live.py:229` | KILLED | 1 | `type(value) is str and canonical_id(value) != ""` |
| 92 | `notion_sandbox_pipeline.py:134` | KILLED | 1 | `page_id == SANDBOX_PARENT_PAGE_ID` |
| 93 | `notion_sandbox_pipeline.py:135` | KILLED | 5 | `canonical_id(current.space_id) != SANDBOX_SPACE_ID or current.archived` |
| 94 | `notion_sandbox_pipeline.py:139` | KILLED | 5 | `parent_id == "" or page_id == "" or page_id in seen` |
| 95 | `notion_sandbox_pipeline.py:143` | KILLED | 5 | `canonical_id(current.space_id) != SANDBOX_SPACE_ID or current.archived` |
| 96 | `notion_sandbox_pipeline.py:151` | KILLED | 10 | `not parent_is_allowed(requested, allowed)` |
| 97 | `notion_sandbox_pipeline.py:156` | KILLED | 5 | `page_id in {"", SANDBOX_PARENT_PAGE_ID, requested}` |
| 98 | `notion_sandbox_pipeline.py:158` | KILLED | 6 | `canonical_id(page.parent_id) != requested` |
| 99 | `notion_sandbox_pipeline.py:160` | KILLED | 6 | `canonical_id(page.space_id) != SANDBOX_SPACE_ID` |
| 100 | `notion_sandbox_pipeline.py:163` | KILLED | 6 | `canonical_id(confirmed.page_id) != page_id` |
| 101 | `notion_sandbox_pipeline.py:165` | KILLED | 5 | `canonical_id(confirmed.parent_id) != requested` |
| 102 | `notion_sandbox_pipeline.py:167` | KILLED | 5 | `canonical_id(confirmed.space_id) != SANDBOX_SPACE_ID or confirmed.archived` |
| 103 | `notion_sandbox_pipeline.py:190` | KILLED | 9 | `type(spec) is not ProductSpec` |
| 104 | `notion_sandbox_pipeline.py:198` | KILLED | 5 | `ctx.probe is None or ctx.product_page_id is None or type(spec) is not ProductSpec` |


## 2026-10-07 — Session 07 W10: fact ledger and workflow link

Session 07 stays incomplete. This wave is not SESSION_07 COMPLETE. State revision is 58. `current_session` stays 7. `completed_sessions` stays `[0, 1, 2, 3, 4, 5, 6]`. `next_session` stays 7. `next_prompt` stays `10_SESSION_07_PRODUCT_BUILD_VARIANTS_AND_QA.md`. STATE `head_sha` `a4e9b025021b4effbb2b2879c1db756403cb1676` is the intentional tip-sync to the W9 squash. It is not this commit. `evidence_closure_commit_sha` stays the Session 06 closure tip `0f94d585f23d79e5ac18479f01e14f67cbaad332`. `last_verified_commit` stays bootstrap `1abf0d7cca3a6b8cd7efcd0a45523538fd5bfd9d`. `updated_at` is `2026-10-07T23:29:39Z`.

Twelve session 7 evidence keys stay false, including `product_fact_ledger_persisted` and `build_workflow_linked`. No session exit code is recorded. A07, A08, and A09 stay DESIGNED. `commissioned_agents` stays empty. Exit 78 scheduler stays HELD. Narrative `next_phase` is `test_matrix` and it is not started. There is no top-level `next_phase` field. Section 11 is not this wave.

Prompt integrity for this wave is the Wave 10 corrective addendum in `docs/control/reviews/2026-10-05-session-07-prompt-integrity.md`. The prompt file is unchanged. SHA-256 `d52011a6f0b725b16427629dc664cfc9f3432c4b5f71d26ce032d4b6c8ecb39d`. D-0029 records that the section 10 names are labels on `config/workflows.yaml`, not a second engine.

### Round 9 is this commit (2026-10-09)

This commit answers reviewer review 5466065420 (FAIL, one low-severity blocker) on tip `08484bf0`. The verifier had not posted on that tip when this was written. Fixtures only. No live Notion, no Etsy. STATE revision stays 58, `head_sha` stays `a4e9b025`, twelve evidence keys stay false, `commissioned_agents` stays `[]`, Exit 78 stays HELD. Line numbers below are this commit. Tip `08484bf0` lines are in brackets.

Blocker. The Round 8 equivalent `:784` (`:748`) IfExp `title != ""` to `True` in `_hub_names` was false at helper level. Round 8 said `matched` is already false because a stored hub name is never blank. That holds at the public entry only: the loader and `_require_hub_name` refuse a blank hub name first, with 0 writes. At helper level, a stored name `""` and a title `""` give `matched` True on stock (the title becomes `missing`, which the durable loop keeps) and False on the mutant (the durable loop sees `""`). `test_blank_hub_name_with_blank_title_is_matched` asserts stock's `matched` True and `missing`. It fails on the hand-applied mutant and passes on this tree. The row is dropped from the equivalent list, which is now 12.

Other fixes:
- QA provider errors of any kind (`notion_qa.py:140-153`). `run_product_qa` re-raises an own `ProductBuildError` unchanged and maps any other `Exception` from the provider calls to the fixed `ProviderFailure("qa.duplicate", "provider operation failed")`, raised by `raise_recorded` after the handler has returned. `BaseException` is not caught. `load_qa_record` moved before the handler and `_write_qa` after it, so a local read or write error is not recorded as a provider job and propagates as before. `test_any_provider_exception_is_recorded_under_the_fixed_text` (`ConnectionError`, a `RuntimeError` with a note, and a `RuntimeError` caused by an `OSError`, each carrying `sk-live-secret`): message, args, cause, context, notes, attributes, formatted traceback, and the file carry no secret, and there is one provider job with the fixed response. `test_own_refusal_inside_qa_keeps_its_text`: an own refusal keeps its text and writes nothing. `test_duplicate_crash_then_resume_creates_one_proof` and `test_unpublish_publish_crash_then_resume_passes` now expect the fixed text for a provider `RuntimeError`. Resume still passes.
- `_clean_interrupt` (`:258`) keeps the kind. A `BaseExceptionGroup` stays a group of the same kind with the fixed text, and each member is cleaned the same way (an `Exception` member becomes `Exception("fact ledger read failed")`). A custom subclass keeps its own type only when `_safe_kind` (`:295`) finds that its `__new__` and `__init__` both come from `builtins` and its metaclass is `type`, so building it runs no caller code. Otherwise it becomes the nearest built-in base (`CancelledError`, `KeyboardInterrupt`, `GeneratorExit`, `SystemExit`, `BaseExceptionGroup`, or `BaseException`). `test_clean_interrupt_keeps_a_custom_kind_or_its_built_in_base` (7), `test_clean_interrupt_keeps_a_group_and_cleans_every_member` (4, including an `ExceptionGroup` member that stays an `ExceptionGroup`), `test_interrupt_group_from_the_read_keeps_its_kind` (public entry, 0 writes).
- `reject_duplicate_labels` (`notion_progress.py:135`) looks a text up only when it is an exact `str`. `test_forged_str_subclass_refusal_text_is_not_raised` uses a str subclass with a forged `__eq__`, `__ne__`, and `__hash__`.

Hand-applied mutants (`mm-harness/r9/handmut.py`, a copy of `src` per mutant): 10 of 10 fail their listed tests on the mutant and pass on this tree.

Census of `notion_fact_ledger.py` on this commit: if 123, elif 0, compare 185, boolop 56, operand 131, ifexp 13. That is 377 decision sites. 377 + 131 operands = 508.

Mutation results for this commit (operands PARTIAL): 173 rows, 161 killed, 12 equivalent, Failed sum 12345. Ledger if-flips 123 rows, 123 killed, 0 equivalent, Failed sum 11439. Ledger IfExp 26 rows, 25 killed, 1 equivalent, Failed sum 407. Ledger operands and flips, PARTIAL (the 5 rows at the new `:290` and the 11 Round 8 equivalent rows; the full operand sweep was started and stopped, not counted): 16 rows, 5 killed, 11 equivalent, Failed sum 17. Progress `:135`-`:136` 7 rows, 7 killed, 0 equivalent, Failed sum 30. QA `:140`-`:153` 1 rows, 1 killed, 0 equivalent, Failed sum 452. The 12 equivalents are the 11 Round 7 operand rows the verifier probed and IfExp `:850` (`:814`) `type(captured) is str` to `True`. Details are in the PR round body (`BODY_ROUND`).

### Round 8 (tip `08484bf0`, 2026-10-09)

This commit answers reviewer review 5464808945 and verifier comment 6072697310, both FAIL on tip `1e614857`. Fixtures only. No live Notion, no Etsy. STATE revision stays 58, `head_sha` stays `a4e9b025`, twelve evidence keys stay false, `commissioned_agents` stays `[]`, Exit 78 stays HELD. Line numbers below are this commit. Tip `1e614857` lines are in brackets.

Five Round 7 equivalents were false. Each now has a killing test, and each test was run against the hand-applied mutant (fails) and the fixed tree (passes).

- `:487` (`:458`) `type(value) is not str` to `False`. `str()` can return a str subclass. `test_plan_refuses_an_undurable_fact` adds `build_version` `_SelfStr("1")`, `_Lie(" 1")` (padded, with a lying `__eq__`, `__ne__`, and `strip`), and `_StrMaker()` (its `__str__` returns a `_SelfStr`). `test_public_entry_refuses_a_str_subclass_version` runs the same three through `run_fact_ledger` with the loader replaced, and asserts the refusal and unchanged checkpoint bytes.
- `:226` / `:227` (`:223` / `:224`) `saved_ledger is not None` / `saved_link is not None` to `True`. `test_half_a_saved_pair_is_planned_not_a_read_failure` calls `_guarded_read` with the ledger and no link, and with the link and no ledger. Stock returns a plan. Each mutant returns `fact ledger read failed`.
- `:867` (`:837`) `expression is None` to `False`. `test_formula_missing_on_both_sides_is_blocked_missing` makes the expected and the stored expression of one formula both `None`. Stock writes a BLOCKED ledger with `dashboard_outputs` `missing`. The mutant reaches `";" in None` and writes nothing.
- `:869` (`:839`) `";" in expression` to `False`. `test_semicolon_formula_on_both_sides_is_not_stored` makes both expressions the expected one plus `;x`. Stock stores `missing` and no `;x` reaches the file.
- The own-prefix gate at `:283` (`:254`), replaced with `if False`. `test_in_package_error_without_an_own_prefix_is_redacted` raises `ProductBuildError("sk-live-secret")` from a `RuntimeError` in a function whose globals are this module's. Stock raises `fact ledger read failed` with no chain and no reachable secret.

Other fixes:
- Comma colour names. `_colour_names` (`:695`) refuses a name that holds a comma, because the fact joins names with commas. `test_colour_name_with_a_comma_is_refused` (helper and `_plan`) and `test_public_comma_colour_name_is_refused_with_no_write` (`red ,Green,Purple`, `,Green,Purple`, `red,Green`, restamped checkpoint, unchanged bytes).
- QA provider response. `run_product_qa` no longer stores or re-raises the provider response. The handler only marks the failure. After it returns, `raise_recorded` stores and raises the fixed `ProviderFailure("qa.duplicate", "provider operation failed")`. `test_provider_response_is_not_stored_raised_or_chained` (three responses) checks the message, args, cause, cause args, context, formatted traceback, and checkpoint. Three existing QA tests now expect the fixed text.
- `BaseException` in `_guarded_read`. `CancelledError`, `KeyboardInterrupt`, `GeneratorExit`, and `SystemExit` leave as fresh instances of the same type with no text, notes, or chain (`_clean_interrupt` `:256`). `SystemExit` keeps an integer code only. Any other `BaseException` becomes `BaseException("fact ledger read failed")`. `test_interrupt_keeps_its_kind_and_drops_the_secret` (6 cases), `test_task_cancel_message_is_dropped_and_the_task_is_cancelled` (`Task.cancel(secret)`, the task still ends cancelled), and `test_timeout_still_becomes_timeout_error` (`asyncio.timeout` still raises `TimeoutError`).
- IfExp survivors. `:721` (`:691`) `notice is not None` to `True` is killed by `test_missing_notice_is_not_a_read_failure`, and `:876` (`:846`) `type(sample) is NotionPage` to `True` is killed by `test_missing_or_subclass_sample_is_missing` (absent sample, `NotionPage` subclass sample).
- `reject_duplicate_labels` (`notion_progress.py:133`) raises only a known refusal text. Any other text becomes `checkpoint list is duplicated`.

The remaining equivalents are 13: the 11 Round 7 rows the verifier probed as equivalent, plus two IfExp rows. `:748` `title != ""` to `True`: a blank title is turned into `missing` by the durable loop at `:751`, and `matched` is already false because a stored hub name is never blank. `:814` `type(captured) is str` to `True`: the branch is inside `if usable`, which already requires an exact non-empty `str`. `notion_progress_record.py:190` `dict(job) if type(job) is dict else job` is equivalent and is named here: `load_payload` has already validated each job as a dict, and the list is rebuilt from a fresh load, so copying or not copying cannot be observed.

Census of `notion_fact_ledger.py` on this commit: if 119, elif 0, compare 182, boolop 55, operand 129, ifexp 13. That is 369 decision sites. 369 + 129 operands = 498.

Mutation results for this commit are in the PR round body (`BODY_ROUND`). The harness is the Round 7 harness.

### Round 7 (tip `1e614857`, 2026-10-09)

This commit answers verifier comment 6066644759 on tip `0b2007a7`. The tables below are this commit. The Round 6 tables are tip `0b2007a7` and are not these counts. On that tip, 357 decision sites + 128 operands = 485.

Blocker 1, `:430` on tip `0b2007a7`, is `:458` here. `test_plan_refuses_an_undurable_fact` calls `_plan` with `build_version` `""`, `" 1"`, and `"1 "`, and with `database_ids=()`. Stock raises `fact ledger fact is not a durable string` for each. `value == ""` to `False`, `value.strip() != value` to `False`, and both `or` to `and` flips are now KILLED. The public loader still refuses those inputs before `_plan`, with 0 writes. `type(value) is not str` to `False` stays equivalent: every value in `facts` is built by `str(...)`, `",".join(...)`, `";".join(...)` (`_dashboard_outputs`), `",".join(...)` (`_secret_links`), or a literal, so each one is an exact `str` before this loop.

Blockers 2, 3, and 4 share one change. `run_fact_ledger` (`:156`) awaits `_guarded_read` (`:206`), which returns the resumed checkpoint, the plan, or a fixed failure text. No `Exception` leaves `_guarded_read`. The caller raises after that frame has returned, so the raised error has no `__context__`, and no provider or code error object is reachable from it. `_scrub_secret` is gone. Mutating an exception in place did not reach `__notes__`, attributes, or a custom `__str__`.

- A provider failure (`ProviderFailure`, `ConnectionError`, `OSError`) becomes `raise_recorded(path, ..., ProviderFailure("fact_ledger.read", "provider read failed"))`. Its `__cause__` is that fixed `ProviderFailure`, whose own `__context__` is `None`. `test_provider_failure_leaves_no_chain` covers `ConnectionError(secret)`, `ProviderFailure(..., secret)`, `PermissionError` with the secret as `filename`, a `__notes__` secret, and a `RuntimeError(secret)` cause. The test walks `str`, `repr`, `args`, `__notes__`, `vars()`, every cause and context, the formatted traceback, and the traceback frame locals outside the test file. The secret is in none of them and not in the checkpoint. One provider job is stored.
- An own refusal is kept only when the text starts with an own prefix, its `__cause__` is not a `ProviderFailure`, and the innermost traceback frame is in `money_machine.agents.implementations` (`_own_message` `:247`, `_raised_in_package` `:261`). It is raised again as a new `ProductBuildError` with the same text and no chain (`test_own_refusal_is_raised_without_a_chain`). An error that was never raised has no traceback and is not own (`test_error_without_a_traceback_is_not_own`).
- A `ProductBuildError` that starts with `qa `, `checkpoint `, `fact ledger `, `progress `, or `workflow link ` but was raised outside the package, with a `RuntimeError(secret)` cause, becomes `fact ledger read failed` with no chain (`test_provider_error_with_an_own_prefix_is_redacted`, 5 prefixes). A provider response re-raised by `raise_recorded` is package code, but its cause is a `ProviderFailure`, so `qa sk-live-secret`, `fact ledger sk-live-secret`, and a bare secret also become `fact ledger read failed` (`test_recorded_provider_response_is_not_an_own_refusal`).
- A code error with the secret in `__str__`, in a `.token` attribute, in a note, and on a chained cause becomes `fact ledger read failed` with no chain (`test_code_error_attributes_do_not_survive`). No provider job is stored and the checkpoint bytes are unchanged.

On tip `0b2007a7`, 15 of these new test cases fail. The four `_plan` cases pass there, because they kill mutants rather than a defect.

Blocker 5, the QA Failed sum. The verifier measured 3674 serially on tip `0b2007a7`, with `notion_qa.py:255` if-flip at 15 and the `:451` type conjunct at 5. Re-running that tip here with this harness gave 3514 with 4 workers, and those two rows were 11 and 1 when run one at a time. The difference is not explained here. This commit publishes every QA, progress, and variant row below, from a run with 1 worker, so each Failed count can be checked row by row.

Census of `notion_fact_ledger.py` on this commit: if 115, elif 0, compare 180, boolop 55, operand 128, ifexp 12. That is 362 decision sites. 362 decision sites + 128 operands = 490. Operand rows are each operand replaced with `True` and with `False`, plus one flip per `and` or `or` token: 329 rows. If-flips are the 115 `if` tests. The progress, QA, and variant lines are the Round 6 lines. Those three files are unchanged.

Sweep method. Harness `/workspace/mm-harness/run.py` with mutants from `muts.py`. Each worker copies `src` and `config` into `.mutants/<run>/w<pid>/` inside the checkout, so `repo_root()` and git still resolve, sets `PYTHONPATH` to that `src`, and runs `.venv/bin/python -m pytest -q --tb=no -rfE -p no:cacheprovider <tests>` from the checkout. Ledger operands and ledger if-flips ran with 4 workers. QA, progress, and variant lines ran with 1 worker, one pytest at a time. The ledger suite is `tests/unit/agents/test_notion_fact_ledger.py`. QA lines add `tests/unit/agents/test_notion_product_qa.py`. Variant lines use the same four variant tests as Round 6. Failed is the count of lines starting with `FAILED` or `ERROR`. A non-zero exit with zero such lines is still a kill. None occurred. Every exit was 0 or 1. Timeout 300 seconds, none hit. Python 3.12.3. pytest 8.4.2. ruff 0.16.2. pyright 1.1.411.

| Sweep | Rows | Killed | Equivalent | Failed sum |
|---|---:|---:|---:|---:|
| Ledger operands (non-if) | 329 | 313 | 16 | 10283 |
| Ledger if-flips | 115 | 115 | 0 | 10551 |
| Progress `:215`, `:236`, `:239`, `:300`, dedupe, `:432` | 40 | 40 | 0 | 1579 |
| QA changed lines | 42 | 42 | 0 | 3687 |
| Variants `:280`, `:519`, `:904` | 13 | 13 | 0 | 13 |
| Combined | 539 | 523 | 16 | 26113 |

Progress split, 1 worker: `:215` 1 killed, Failed 3. `:236` 6 killed, Failed sum 13. `:239` 6 killed, Failed sum 15. `:300` 1 killed, Failed 16. Dedupe `:313`, `:316`, `:318`, and `:319`–`:322` is 14 killed, Failed sum 35. `:432` is 12 killed, Failed sum 1497. Total 1579.

QA and progress counts moved because the 19 new ledger tests that build a QA checkpoint also fail when QA is broken. Against the per-row QA run of tip `0b2007a7` with this harness, every changed row moved by 19 or by 1, and no other row moved. `notion_qa.py:255` if-flip is 11 here and the `:451` `type(found.expression) is not str` to `False` row is 1, as on that tip. The QA sum here is 3687. The Round 6 QA figure 3514 and the verifier's 3674 were both tip `0b2007a7`.

Ledger: `:458` `value == ""` to `False` fails 2. `value.strip() != value` to `False` fails 2. The first `or` to `and` fails 2. The second fails 4. The first failing test in each is `test_plan_refuses_an_undurable_fact`. The new `if failure == _PROVIDER_FAILED` (`:184`) flip fails 211. `if plan is None` (`:190`) fails 201.

The 16 equivalents, all in `notion_fact_ledger.py`. Each row ran with Failed 0. Fifteen are the Round 6 rows at new line numbers (tip `0b2007a7` line in brackets). The sixteenth is `:458` `type(value) is not str`, the one `:430` row the verifier agreed is equivalent.

| Line | Mutation | Helper probe | Public probe |
|---|---|---|---|
| `:223` (`:181`) | `saved_ledger is not None` to `True` | `_stored_pair` returns both or neither. One `None` never arrives. | `test_missing_qa_and_half_a_pair_write_nothing` writes nothing until both records exist, then the resume writes nothing more. |
| `:224` (`:182`) | `saved_link is not None` to `True` | Same pair. | Same test. |
| `:458` (`:430`) | `type(value) is not str` to `False` | Every value in `facts` is `str(...)`, a `",".join` or `";".join` result, or a literal, so it is an exact `str` before this loop. | The public loader refuses a bad version or variant before `_plan`. |
| `:649` (`:621`) | `len(block.content) > len(prefix)` to `True` | Prefix-only content yields detail `""` either way. `_durable_detail` raises the same `ProductBuildError`. `test_prefix_only_section_is_the_same_refusal`. | The same test's unnamed caller raises that error and leaves the bytes unchanged. |
| `:703` (`:675`) | `page.title == ""` to `False` | An empty title is returned by the `if` and by the fall-through. Both are `""`. | `test_blank_hub_title_is_missing`. |
| `:721` (`:693`) | `type(name) is str` to `True` | `_page_title` already returned a `str`. | `test_hub_title_that_is_not_text_is_blocked`. |
| `:721` (`:693`) | `name == ""` to `False` | The first loop already stored `missing` for `""`. | `test_blank_hub_title_is_missing`. |
| `:752` (`:724`) | `type(title) is str` to `True` | The preceding ternary already produced a `str`. | `test_database_title_integer_is_missing` and `test_blank_database_title_is_missing_and_blocked`. |
| `:773` (`:745`) | `captured != ""` to `True` | `_redacted_url("")` returns `missing`. Agreed stays false. | `test_empty_or_missing_public_url_blocks_secret_links`. |
| `:797` (`:769`) | `captured == ""` to `False` | `""` falls through. `separator == ""` still returns `missing`. | `test_untrusted_scheme_or_host_is_stored_as_missing`. |
| `:804` (`:776`) | `separator == ""` to `False` | `notaurl` has rest `""`. `rest == ""` still returns `missing`. | Same public test. |
| `:804` (`:776`) | `rest == ""` to `False` | `http://` has an empty host. `host == ""` still returns `missing`. | Same public test. |
| `:809` (`:781`) | `host.strip() != host` to `False` | Any space returns `missing` before the host is parsed. | A query token is `missing` and the secret is absent. |
| `:837` (`:809`) | `expression is None` to `False` | `None` still fails `expression != wanted[1]`. | `test_blank_formula_blocks_dashboard_outputs`. |
| `:839` (`:811`) | `";" in expression` to `False` | `test_seminame_formula_is_missing` still returns `missing` on the name conjunct. | `test_semicolon_in_a_formula_expression_is_missing` is `BLOCKED` because `expression != wanted[1]` fires first. |
| `:920` (`:892`) | `allowed is None` to `False` | A predecessor in `_GRAPH` has an allowed set. A mismatched set still fails `frozenset(...) != allowed`. | `test_renamed_workflow_refuses` writes nothing. |

QA changed lines, all 42 rows, 1 worker. Failed sum 3687.

| # | Site | Mutation | Result | Failed |
|---|---|---|---|---:|
| 1 | `notion_qa.py:170` | `if-flip: verdict == "PASS" and any(passed is False for _name, passed in parsed_checks)` | KILLED | 284 |
| 2 | `notion_qa.py:170` | `and operand 0 -> True: verdict == "PASS"` | KILLED | 13 |
| 3 | `notion_qa.py:170` | `and operand 0 -> False: verdict == "PASS"` | KILLED | 1 |
| 4 | `notion_qa.py:170` | `and operand 1 -> True: any(passed is False for _name, passed in parsed_checks)` | KILLED | 271 |
| 5 | `notion_qa.py:170` | `and operand 1 -> False: any(passed is False for _name, passed in parsed_checks)` | KILLED | 1 |
| 6 | `notion_qa.py:170` | `and->or #0` | KILLED | 283 |
| 7 | `notion_qa.py:175` | `if-flip: type(digest) is not str or len(digest) != 64 or not _hex_digest(digest)` | KILLED | 286 |
| 8 | `notion_qa.py:175` | `or operand 0 -> True: type(digest) is not str` | KILLED | 281 |
| 9 | `notion_qa.py:175` | `or operand 0 -> False: type(digest) is not str` | KILLED | 1 |
| 10 | `notion_qa.py:175` | `or operand 1 -> True: len(digest) != 64` | KILLED | 281 |
| 11 | `notion_qa.py:175` | `or operand 1 -> False: len(digest) != 64` | KILLED | 2 |
| 12 | `notion_qa.py:175` | `or operand 2 -> True: not _hex_digest(digest)` | KILLED | 281 |
| 13 | `notion_qa.py:175` | `or operand 2 -> False: not _hex_digest(digest)` | KILLED | 2 |
| 14 | `notion_qa.py:175` | `or->and #0` | KILLED | 3 |
| 15 | `notion_qa.py:175` | `or->and #1` | KILLED | 4 |
| 16 | `notion_qa.py:255` | `if-flip: saved.prose_digest != prose_digest(spec)` | KILLED | 11 |
| 17 | `notion_qa.py:451` | `if-flip: found is None or type(found.expression) is not str or found.expression != expression` | KILLED | 101 |
| 18 | `notion_qa.py:451` | `or operand 0 -> True: found is None` | KILLED | 101 |
| 19 | `notion_qa.py:451` | `or operand 0 -> False: found is None` | KILLED | 7 |
| 20 | `notion_qa.py:451` | `or operand 1 -> True: type(found.expression) is not str` | KILLED | 101 |
| 21 | `notion_qa.py:451` | `or operand 1 -> False: type(found.expression) is not str` | KILLED | 1 |
| 22 | `notion_qa.py:451` | `or operand 2 -> True: found.expression != expression` | KILLED | 101 |
| 23 | `notion_qa.py:451` | `or operand 2 -> False: found.expression != expression` | KILLED | 2 |
| 24 | `notion_qa.py:451` | `or->and #0` | KILLED | 8 |
| 25 | `notion_qa.py:451` | `or->and #1` | KILLED | 3 |
| 26 | `notion_qa.py:639` | `if-flip: type(content) is not str` | KILLED | 420 |
| 27 | `notion_qa.py:641` | `if-flip: "No access" in content` | KILLED | 103 |
| 28 | `notion_qa.py:737` | `if-flip: isinstance(database, NotionDatabase) and type(database.title) is str` | KILLED | 102 |
| 29 | `notion_qa.py:737` | `and operand 0 -> True: isinstance(database, NotionDatabase)` | KILLED | 1 |
| 30 | `notion_qa.py:737` | `and operand 0 -> False: isinstance(database, NotionDatabase)` | KILLED | 100 |
| 31 | `notion_qa.py:737` | `and operand 1 -> True: type(database.title) is str` | KILLED | 1 |
| 32 | `notion_qa.py:737` | `and operand 1 -> False: type(database.title) is str` | KILLED | 100 |
| 33 | `notion_qa.py:737` | `and->or #0` | KILLED | 2 |
| 34 | `notion_qa.py:856` | `if-flip: page.is_published is not True or not _is_trusted_link(page.public_url, page.id)` | KILLED | 4 |
| 35 | `notion_qa.py:856` | `or operand 0 -> True: page.is_published is not True` | KILLED | 1 |
| 36 | `notion_qa.py:856` | `or operand 0 -> False: page.is_published is not True` | KILLED | 1 |
| 37 | `notion_qa.py:856` | `or operand 1 -> True: not _is_trusted_link(page.public_url, page.id)` | KILLED | 1 |
| 38 | `notion_qa.py:856` | `or operand 1 -> False: not _is_trusted_link(page.public_url, page.id)` | KILLED | 2 |
| 39 | `notion_qa.py:856` | `or->and #0` | KILLED | 3 |
| 40 | `notion_qa.py:916` | `if-flip: envelope.payload is not None` | KILLED | 1 |
| 41 | `notion_qa.py:918` | `if-flip: type(prior) is dict` | KILLED | 1 |
| 42 | `notion_qa.py:920` | `if-flip: key in prior` | KILLED | 414 |

Ledger if-flips, all 115. Every row is killed. Failed sum 10551. The first failing test is the first `FAILED` or `ERROR` line pytest printed.

| Line | Failed | First failing test |
|---|---:|---|
| `175` | 256 | `test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub]` |
| `184` | 211 | `test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub]` |
| `190` | 201 | `test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub]` |
| `191` | 82 | `test_resume_of_pass_makes_no_second_write` |
| `222` | 201 | `test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub]` |
| `237` | 69 | `test_stored_blocked_verdict_replans_a_passing_plan` |
| `254` | 60 | `test_stored_blocked_verdict_replans_a_passing_plan` |
| `256` | 62 | `test_stored_blocked_verdict_replans_a_passing_plan` |
| `264` | 61 | `test_stored_blocked_verdict_replans_a_passing_plan` |
| `274` | 47 | `test_resume_of_pass_makes_no_second_write` |
| `277` | 47 | `test_resume_of_pass_makes_no_second_write` |
| `281` | 211 | `test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub]` |
| `283` | 211 | `test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub]` |
| `290` | 50 | `test_resume_of_pass_makes_no_second_write` |
| `293` | 60 | `test_resume_of_pass_makes_no_second_write` |
| `297` | 47 | `test_resume_of_pass_makes_no_second_write` |
| `300` | 46 | `test_resume_of_pass_makes_no_second_write` |
| `307` | 39 | `test_resume_of_pass_makes_no_second_write` |
| `310` | 42 | `test_resume_of_pass_makes_no_second_write` |
| `313` | 36 | `test_resume_of_pass_makes_no_second_write` |
| `316` | 36 | `test_resume_of_pass_makes_no_second_write` |
| `319` | 36 | `test_resume_of_pass_makes_no_second_write` |
| `327` | 46 | `test_resume_of_pass_makes_no_second_write` |
| `331` | 47 | `test_resume_of_pass_makes_no_second_write` |
| `335` | 47 | `test_resume_of_pass_makes_no_second_write` |
| `343` | 45 | `test_resume_of_pass_makes_no_second_write` |
| `345` | 21 | `test_blocked_qa_records_blocked_and_holds_with_no_adapter_writes` |
| `353` | 152 | `test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub]` |
| `355` | 155 | `test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub]` |
| `362` | 23 | `test_resume_of_pass_makes_no_second_write` |
| `364` | 6 | `test_resume_of_pass_makes_no_second_write` |
| `380` | 24 | `test_resume_of_pass_makes_no_second_write` |
| `382` | 25 | `test_resume_of_pass_makes_no_second_write` |
| `383` | 16 | `test_blocked_qa_records_blocked_and_holds_with_no_adapter_writes` |
| `385` | 16 | `test_blocked_qa_records_blocked_and_holds_with_no_adapter_writes` |
| `387` | 14 | `test_blocked_qa_records_blocked_and_holds_with_no_adapter_writes` |
| `388` | 12 | `test_blocked_ledger_replans_when_the_defect_is_gone` |
| `392` | 10 | `test_resume_of_pass_makes_no_second_write` |
| `394` | 6 | `test_resume_of_pass_makes_no_second_write` |
| `395` | 6 | `test_resume_of_pass_makes_no_second_write` |
| `397` | 5 | `test_resume_of_pass_makes_no_second_write` |
| `399` | 3 | `test_resume_of_pass_makes_no_second_write` |
| `413` | 210 | `test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub]` |
| `425` | 191 | `test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub]` |
| `453` | 52 | `test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub]` |
| `458` | 159 | `test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub]` |
| `493` | 8 | `test_caller_spec_fields_are_not_the_facts` |
| `499` | 3 | `test_oversized_hub_description_is_not_adopted` |
| `501` | 18 | `test_edited_hub_prose_is_blocked_not_self_compared[purpose-one]` |
| `518` | 14 | `test_unnamed_caller_cannot_adopt_a_live_hub_edit[forged-purpose-one]` |
| `537` | 206 | `test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub]` |
| `544` | 204 | `test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub]` |
| `551` | 3 | `test_oversized_hub_description_is_not_adopted` |
| `554` | 202 | `test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub]` |
| `580` | 2 | `test_unnamed_sixty_four_character_hub_name_passes` |
| `583` | 4 | `test_unnamed_caller_cannot_adopt_a_live_hub_edit[forged-purpose-all]` |
| `590` | 9 | `test_qa_pass_persists_one_ledger_and_one_link[business-Studio Ledger-Studio Home-Desk]` |
| `592` | 4 | `test_caller_tier_does_not_override_stored_kinds[mass]` |
| `602` | 214 | `test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub]` |
| `605` | 215 | `test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub]` |
| `608` | 215 | `test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub]` |
| `611` | 216 | `test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub]` |
| `623` | 209 | `test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub]` |
| `626` | 25 | `test_oversized_hub_description_is_not_adopted` |
| `629` | 209 | `test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub]` |
| `631` | 210 | `test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub]` |
| `645` | 19 | `test_unnamed_caller_cannot_adopt_a_live_hub_edit[forged-purpose-one]` |
| `649` | 19 | `test_unnamed_caller_cannot_adopt_a_live_hub_edit[forged-purpose-one]` |
| `656` | 21 | `test_unnamed_caller_cannot_adopt_a_live_hub_edit[forged-purpose-one]` |
| `666` | 209 | `test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub]` |
| `677` | 49 | `test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub]` |
| `693` | 3 | `test_missing_page_writes_nothing` |
| `696` | 217 | `test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub]` |
| `703` | 179 | `test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub]` |
| `716` | 49 | `test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub]` |
| `721` | 51 | `test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub]` |
| `734` | 51 | `test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub]` |
| `747` | 215 | `test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub]` |
| `752` | 50 | `test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub]` |
| `754` | 49 | `test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub]` |
| `774` | 58 | `test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub]` |
| `783` | 4 | `test_forged_captured_url_blocks_secret_links` |
| `797` | 5 | `test_forged_captured_url_blocks_secret_links` |
| `799` | 11 | `test_forged_captured_url_blocks_secret_links` |
| `801` | 3 | `test_forged_captured_url_blocks_secret_links` |
| `804` | 4 | `test_forged_captured_url_blocks_secret_links` |
| `809` | 5 | `test_forged_captured_url_blocks_secret_links` |
| `816` | 51 | `test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub]` |
| `818` | 50 | `test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub]` |
| `820` | 50 | `test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub]` |
| `830` | 51 | `test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub]` |
| `837` | 57 | `test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub]` |
| `839` | 52 | `test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub]` |
| `841` | 177 | `test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub]` |
| `848` | 50 | `test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub]` |
| `852` | 179 | `test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub]` |
| `854` | 176 | `test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub]` |
| `856` | 50 | `test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub]` |
| `874` | 52 | `test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub]` |
| `877` | 52 | `test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub]` |
| `880` | 52 | `test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub]` |
| `883` | 53 | `test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub]` |
| `886` | 53 | `test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub]` |
| `906` | 227 | `test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub]` |
| `911` | 226 | `test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub]` |
| `913` | 226 | `test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub]` |
| `915` | 226 | `test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub]` |
| `917` | 226 | `test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub]` |
| `920` | 226 | `test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub]` |
| `922` | 226 | `test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub]` |
| `925` | 226 | `test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub]` |
| `927` | 227 | `test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub]` |
| `966` | 149 | `test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub]` |
| `968` | 149 | `test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub]` |
| `970` | 149 | `test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub]` |

Product-build tests: 879 passed in 59.97s (the Round 6 set plus 20 new cases). `test_notion_fact_ledger.py`: 306 passed. `ruff format --check`, `ruff check`, and `pyright` 1.1.411 are clean on the whole tree, as CI runs them. Full local `uv run pytest`: 2637 passed, 193 skipped, 12 failed. All 12 failures are `test_compose_preserves_the_postgres_password`, because the `docker` binary is absent here. Sockets stay blocked. No production Notion or Etsy. No commissioning. Revision stays 58. `head_sha` stays `a4e9b025021b4effbb2b2879c1db756403cb1676`. `updated_at` stays `2026-10-07T23:29:39Z`. Exit 78 stays HELD. This is not SESSION_07 COMPLETE.

Not changed this round, all non-blocking: a single variant name that itself holds commas (`red ,Green,Purple`) is still accepted and joined into the colour fact; the `asyncpg`-absent integration failures; and the IfExp `dict(job) if type(job) is dict else job`. The `:649` `>` to `>=` nit stays as described. This commit's CI run is not invented here.

### Round 6 record at tip `0b2007a7` (2026-10-08)

This round answered verifier comment 6060511391 and reviews 5455831580 and 5457879480, all on tip `45818d9e`. The tables below are tip `0b2007a7`. The Round 5 tables are tip `45818d9e` and are not these counts. On that tip, 338 decision sites + 125 operands = 463. Its ledger if-flip run was 104 rows, all killed, Failed sum 8131. The reviewer finished 80 of those 104 under load. This commit does not republish 8845, 8131, or 17052.

`run_fact_ledger` is async at `notion_fact_ledger.py:156`. `_plan` at `:377` awaits `live_qa_passed` (`notion_qa.py:521`) before `_write` at `:929`, which calls `write_checkpoint` at `:969`. `_colour_names` at `:633` checks each variant name on its own (exact `str`, non-empty, stripped) before the joined colour fact. `""`, `" red"`, and `"red "` raise `fact ledger fact is not a durable string` (`test_plan_refuses_an_undurable_colour_name`). A `str` subclass, `5`, and `None` raise that same `ProductBuildError` (`test_plan_refuses_a_non_string_colour_name`). They are not `AttributeError`. The public loader refuses the strings, the int, and null with `checkpoint variant must be a non-empty string` and 0 writes (`test_public_variant_name_is_refused_before_the_plan`, `test_public_non_string_variant_name_is_refused`). A `str` subclass cannot survive the JSON reload. `variants=()` raises the same product error inside `_plan` (`test_empty_variants_are_a_product_error`). The public entry still raises `fact ledger requires the qa checkpoint` before `_plan`.

The semicolon return at `:811` stays first. `type(name) is not str` at `:813` is the next statement. `SemiName("current_date")` returns `missing` (`test_seminame_formula_is_missing`, helper only). Forcing `";" in name` to `False`, or the `or` to `and`, falls through and raises, so both are killed (Failed 1 each). Forcing `";" in expression` to `False` stays equivalent: `SemiName` still hits the name conjunct, a real `x;y` fails `expression != wanted[1]` first (`test_semicolon_in_a_formula_expression_is_missing`), and `Liar("x;y")` is `None` before this line (`test_lying_formula_expression_is_blocked`). `_PlainName` kills the type guard.

`_require_shape` at `notion_progress.py:432` refuses `""`, `" test_matrix"`, `"tést"`, `5`, and `None` as `progress record is tampered` (`test_next_phase_must_be_an_unpadded_ascii_token`). `5` and `None` are `ProductBuildError`, not `AttributeError`. Empty kills `== ""` (Failed 1). Padding kills the strip conjunct (Failed 1). `tést` kills `isascii` (Failed 1). `5` and `None` kill the str-type conjunct (Failed 2). The three `or` to `and` flips fail 3, 2, and 2. The if-flip and the four operand-True rows are killed as well. The whole `:432` group is 12 rows, 12 killed, Failed sum 1402.

QA stores `prose_digest` (`notion_qa.py:187`), the sha256 of the hub descriptions in order, then `buyer_problem`, then `flagship_feature`. Hub names and the row identity are not in it. `_plan` compares it at `:397` before `live_qa_passed` and before any write. A mismatch raises `fact ledger caller does not match` with 0 writes. `_saved_holds` in QA returns false at `:255`, so QA runs again. `test_changed_prose_does_not_pass_without_a_new_qa` covers a description, the buyer, and the flagship. `test_prose_digest_must_be_lowercase_hex` refuses a non-str, a short digest, `""`, a non-hex digest, and uppercase hex, at the helper and at the public restamp, with 0 writes. D-0029 records the limit. The 64-character unnamed path still PASSes when that prose is the prose QA judged.

`_notification_values` at `notion_qa.py:451` requires `type(found.expression) is str`. `test_lying_formula_expression_is_not_a_string` installs a `str` subclass whose text equals the spec expression, so `!=` does not refuse it (`str.__ne__` ignores a lying `__eq__` when the text differs). The helper returns false and the public verdict is `BLOCKED` with 0 adapter writes. Replacing that type conjunct with `False` fails 1.

A provider `ProductBuildError` whose message is not one of this module's refusals is scrubbed. `_scrub_secret` clears `__cause__` and `__context__` and sets `__suppress_context__`, then the handler raises `fact ledger read failed` from `None` (`test_provider_product_error_does_not_carry_a_secret`, `test_chained_secret_is_not_left_on_the_context`). The secret is not in the message and not on the chain. It is not a provider job.

Buyer text of 501 to 1000 characters passes on the named path and the unnamed path. `_durable_detail` uses 1000 for `buyer` and 500 for purpose and practice. `test_long_buyer_passes_on_named_and_unnamed_paths` uses 600 characters. Both public calls PASS, and the helper returns that buyer.

`_require_hub_name` at `:516` accepts 64 and refuses 65 on both paths. `test_legal_bounds_pass_and_one_past_refuses` kills that conjunct: `len(name) > 64` replaced with `False` fails 2. `test_unnamed_sixty_four_character_hub_name_passes` is the 64-character PASS. The same conjunct inside `_durable_detail` at `:617` is killed by `test_detail_bounds_are_a_product_error` (Failed 1), which calls the helper. A 65-character name on the public path does not reach `:617`, because `:516` already returned. The earlier claim that `:580` was the check the unnamed 64-character PASS killed, and that the named path did not reach the detail rule, was only half true. `:516` dominates both paths.

`_teardown` (`notion_qa.py:699`) says it is true when hub prose still matches the spec. The sleep child in `test_keyboard_interrupt_still_exits_130` uses `sys.executable`.

Round-4 temp cleanup and URL checks, re-gated on this tree. `test_temp_names_are_matched_literally` monkeypatches `_pid_alive`. `:236` and `:239` are 12 rows, 12 killed, Failed sum 28. `if pid <= 0` at `:215` is killed, Failed 3. `test_non_positive_pid_is_not_alive` asserts `_pid_alive(0)` is false. PermissionError still means the pid is alive. `_redacted_url` (`:763`) stores scheme and host. `test_redacted_url_drops_a_bare_token` (helper) and `test_untrusted_scheme_or_host_is_stored_as_missing` (public) cover userinfo, a path, a query, a fragment, a port, a bare token, `ftp://example.com`, `https://@`, `https://evil;example`, and `notaurl`. `https://user:sk-live-…@evil.example/p` becomes `https://evil.example` with the secret absent.

`:359` and `:364`, `saved.checks != plan.checks` replaced with `False`, are killed (Failed 2 and 3). They are not equivalent. `test_saved_pass_checks_must_match_the_plan` raises `fact ledger does not match` for a renamed, reordered, or short PASS. The public entry rejects that record in `_require_ledger` (`:260`) before the helper. On tip `45818d9e` the same conjunct was `:333` and failed 3.

`_postgres_available` builds the engine inside the try. A missing `asyncpg` driver raises while the dialect loads, and the function returns false before connect. `unreachable_client` skips on `ModuleNotFoundError`, because those two tests need the driver to prove a refused connection. This round blocked `asyncpg` with a `meta_path` finder and ran `pytest -q tests/integration`: 21 passed, 193 skipped, exit 0. On tip `45818d9e` a missing driver errored instead of skipping. The product suite cannot be collected under `pytest -n 4` (`test_bad_checkpoint_does_not_create_a_page` puts `uuid4()` in its node id). Sums below are one serial pass of this tree, on a quiet machine, with `ProcessPoolExecutor` and 4 workers. They are not a `pytest -n` run.

Product-build tests: 859 passed in 45.01s (`test_notion_fact_ledger.py`, `test_notion_product_qa.py`, the variants file, the progress file, and the six phase files). The 826 figure was tip `45818d9e`. `ruff format --check` and `ruff check` are clean on the changed modules. `pyright` 1.1.411 reports 0 errors on those modules and on the two touched test files. The notice that 1.1.414 exists is not a failure. SQLAlchemy is 2.0.52. `asyncpg` is 0.31.0. Sockets stay blocked. No production Notion or Etsy. No commissioning. Revision stays 58. `head_sha` stays `a4e9b025021b4effbb2b2879c1db756403cb1676`. `updated_at` stays `2026-10-07T23:29:39Z`. Exit 78 stays HELD. This is not SESSION_07 COMPLETE. `test_session_seven_stays_incomplete_with_false_evidence` passed.

Census of `notion_fact_ledger.py` on this commit: if 112, elif 0, compare 178, boolop 55, operand 128, ifexp 12. That is 357 decision sites. 357 decision sites + 128 operands = 485. Progress sites 183. QA sites 288. Variant sites 264. Operand rows are each operand replaced with `True` and with `False`, plus one flip per `and` or `or`. If-flips are the 112 `if` tests. Progress rows are `notion_progress.py:215`, `:236`, `:239`, `:300`, `:313`, `:316`, `:318`, `:319` through `:322`, and `:432`. QA rows are `notion_qa.py:170`, `:175`, `:255`, `:451`, `:639`, `:641`, `:737`, `:856`, `:916`, `:918`, and `:920`. Variant rows are `notion_variants.py:280`, `:519`, and `:904`.

Sweep method. One uninterrupted pass after the killing tests were in the tree. Command: `python /tmp/sweep_operands.py` from `/workspace`, 4 workers (`nproc` 4). Each worker copied `src` and `config` to its own directory, set `PYTHONPATH` to that `src`, and ran `pytest -q --tb=no -rfE -p no:cacheprovider -o pythonpath=`. The editable install was not the mutant. A canary import checked the copy. The ledger and progress suite was `tests/unit/agents/test_notion_fact_ledger.py`. QA lines used that file and `tests/unit/agents/test_notion_product_qa.py`. Variant lines used `test_aligned_pairs_refuse_a_duplicated_palette_name`, `test_non_workspace_home_is_refused_by_the_source_check`, `test_spec_page_must_be_the_stored_home`, and `test_duplicate_palette_token_names_refuse_before_any_write`. The Failed column is the count of lines starting with `FAILED` or `ERROR`. A non-zero exit with zero such lines is still a kill. A syntax error is not a kill. None occurred. Timeout was 300 seconds. None occurred. Python 3.12.3. pytest 8.4.2. ruff 0.16.2.

| Sweep | Rows | Killed | Equivalent | Failed sum |
|---|---:|---:|---:|---:|
| Ledger operands (non-if) | 329 | 309 | 20 | 9826 |
| Ledger if-flips | 112 | 112 | 0 | 9328 |
| Progress `:215`, `:236`, `:239`, `:300`, dedupe, `:432` | 40 | 40 | 0 | 1479 |
| QA changed lines | 42 | 42 | 0 | 3514 |
| Variants `:280`, `:519`, `:904` | 13 | 13 | 0 | 13 |
| Combined | 536 | 516 | 20 | 24160 |

Progress split: `:215` is 1 killed, Failed sum 3. `:236` and `:239` are 12 killed, Failed sum 28. `:300` is 1 killed, Failed sum 11. Dedupe `:313`, `:316`, `:318`, and `:319`–`:322` is 14 killed, Failed sum 35. `:432` is 12 killed, Failed sum 1402.

The 20 equivalents, all in `notion_fact_ledger.py`. Each one was run. Failed is 0. The helper and the public entry agree.

| Line | Mutation | Helper probe | Public probe |
|---|---|---|---|
| `:181` | `saved_ledger is not None` to `True` | `_stored_pair` returns both or neither. One `None` never arrives. | `test_missing_qa_and_half_a_pair_write_nothing` writes nothing until both records exist, then the resume writes nothing more. |
| `:182` | `saved_link is not None` to `True` | Same pair. | Same test. |
| `:430` | `type(value) is not str` to `False`, `value == ""` to `False`, `value.strip() != value` to `False`, and both `or` flips | Bad names raise in `_colour_names` (`test_plan_refuses_an_undurable_colour_name`, `test_plan_refuses_a_non_string_colour_name`) and never reach this loop. A durable plan still passes. Five rows. | `test_public_variant_name_is_refused_before_the_plan` and `test_public_non_string_variant_name_is_refused` refuse before `_plan`. The 64-character unnamed PASS still passes. |
| `:621` | `len(block.content) > len(prefix)` to `True` | Prefix-only content yields detail `""` either way. `_durable_detail` raises the same `ProductBuildError`. `test_prefix_only_section_is_the_same_refusal`. | The same test's unnamed caller (`identity` `Not The Row`) raises that error and leaves the bytes unchanged. It does not kill a literal `>=`. |
| `:675` | `page.title == ""` to `False` | An empty title is returned by the `if` and by the fall-through. Both are `""`. | `test_blank_hub_title_is_missing`. The hub fact is `missing` either way. |
| `:693` | `type(name) is str` to `True` | `_page_title` already returned a `str`. | `test_hub_title_that_is_not_text_is_blocked`. |
| `:693` | `name == ""` to `False` | The first loop already stored `missing` for `""`. | `test_blank_hub_title_is_missing`. |
| `:724` | `type(title) is str` to `True` | The preceding ternary already produced a `str` (`missing` or the title). | `test_database_title_integer_is_missing` and `test_blank_database_title_is_missing_and_blocked`. |
| `:745` | `captured != ""` to `True` | `""` becomes usable. `_redacted_url("")` returns `missing`. Agreed stays false. | `test_empty_or_missing_public_url_blocks_secret_links`. The fact component is `missing`. |
| `:769` | `captured == ""` to `False` | `""` falls through. `separator == ""` still returns `missing`. `test_redacted_url_drops_a_bare_token`. | `test_untrusted_scheme_or_host_is_stored_as_missing`. |
| `:776` | `separator == ""` to `False` | `notaurl` has rest `""`. `rest == ""` still returns `missing`. | Same public test. `notaurl` is `missing`. |
| `:776` | `rest == ""` to `False` | `http://` has an empty host. `host == ""` still returns `missing`. | Same public test. |
| `:781` | `host.strip() != host` to `False` | Any space returns `missing` before the host is parsed (`:773`). | A query token is `missing` and the secret is absent. |
| `:809` | `expression is None` to `False` | `None` still fails `expression != wanted[1]`. `test_blank_formula_expression_is_missing` returns `missing`. | `test_blank_formula_blocks_dashboard_outputs`. |
| `:811` | `";" in expression` to `False` | `test_seminame_formula_is_missing` still returns `missing` on the name conjunct. A matching expression has no semicolon. | `test_semicolon_in_a_formula_expression_is_missing` is `BLOCKED` because `expression != wanted[1]` fires first. `test_lying_formula_expression_is_blocked` never reaches this line. |
| `:892` | `allowed is None` to `False` | A predecessor in `_GRAPH` has an allowed set. A mismatched set still fails `frozenset(...) != allowed`. | `test_renamed_workflow_refuses` writes nothing. |

Killing-test map for the rows that are not equivalent.

| Input | Site | Killing test | Sweep |
|---|---|---|---|
| `""`, `" red"`, `"red "` | `:638` | `test_plan_refuses_an_undurable_colour_name` | `name == ""` to `False` fails 1. `strip` to `False` fails 1. |
| Subclass `"Red"`, `5`, `None` | `:638` | `test_plan_refuses_a_non_string_colour_name` | `type(name) is not str` to `False` fails 3. The subclass does not raise. `5` and `None` raise `AttributeError` on the mutant. Stock raises `ProductBuildError`. |
| `""`, `" test_matrix"`, `"tést"`, `5`, `None` | `notion_progress.py:432` | `test_next_phase_must_be_an_unpadded_ascii_token` | Seven weakenings killed, as above. Failed sums 2, 1, 1, 1, 3, 2, 2. |
| `SemiName("current_date")` | `:811` name and `or` | `test_seminame_formula_is_missing` | Each fails 1. The expression conjunct stays equivalent. |
| `_PlainName` | `:813` | `test_plain_subclass_formula_name_is_refused` | The type guard raises. |
| Lying formula whose text equals the spec | `notion_qa.py:451` | `test_lying_formula_expression_is_not_a_string` | `type(found.expression) is not str` to `False` fails 1. |
| Description, buyer, or flagship changed after QA | `:397`, `notion_qa.py:255` | `test_changed_prose_does_not_pass_without_a_new_qa` | `:255` if-flip fails 11. |
| Digest not 64 lowercase hex | `notion_qa.py:175` | `test_prose_digest_must_be_lowercase_hex` | Nine rows, all killed, Failed sum 1065. |
| Provider `ProductBuildError("sk-live-secret")` | `:193` | `test_provider_product_error_does_not_carry_a_secret` | Message is `fact ledger read failed`. 0 writes. Not a provider job. |
| Chained `RuntimeError("sk-live-secret")` | `:205` | `test_chained_secret_is_not_left_on_the_context` | `__context__.__cause__` is cleared. |
| Buyer of 600 characters | `:627` | `test_long_buyer_passes_on_named_and_unnamed_paths` | Named PASS, then unnamed PASS. |
| 65-character hub name | `:516` | `test_legal_bounds_pass_and_one_past_refuses` | `len(name) > 64` to `False` fails 2. |
| 65-character name inside `_durable_detail` | `:617` | `test_detail_bounds_are_a_product_error` | `len(name) > 64` to `False` fails 1. |
| 64-character unnamed hub | both length checks allow 64 | `test_unnamed_sixty_four_character_hub_name_passes` | PASS, 1 write. |
| PASS checks renamed, reordered, or one short | `:359`, `:364` | `test_saved_pass_checks_must_match_the_plan` | `saved.checks != plan.checks` to `False` fails 2 at `:359` and 3 at `:364`. |
| Prefix-only section | `:621` operand `True` | `test_prefix_only_section_is_the_same_refusal` | That operand stays equivalent. The if-flip fails 19. |
| pid 0 | `notion_progress.py:215` | `test_non_positive_pid_is_not_alive` | If-flip fails 3. |
| Dead temp, live pid, literal name | `:236`, `:239` | `test_temp_names_are_matched_literally` | 12 of 12 killed, Failed sum 28. |

Ledger if-flips, all 112. Every row is killed. Failed sum 9328. The first failing test is the first `FAILED` or `ERROR` line pytest printed.

| Line | Failed | First failing test |
|---|---:|---|
| `175` | 241 | `test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub]` |
| `180` | 186 | `test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub]` |
| `194` | 60 | `test_stored_blocked_verdict_replans_a_passing_plan` |
| `228` | 6 | `test_code_errors_are_redacted_and_not_provider_jobs[RuntimeError]` |
| `237` | 8 | `test_runtime_error_is_not_a_provider_job` |
| `239` | 8 | `test_runtime_error_is_not_a_provider_job` |
| `246` | 47 | `test_resume_of_pass_makes_no_second_write` |
| `249` | 47 | `test_resume_of_pass_makes_no_second_write` |
| `253` | 196 | `test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub]` |
| `255` | 196 | `test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub]` |
| `262` | 50 | `test_resume_of_pass_makes_no_second_write` |
| `265` | 60 | `test_resume_of_pass_makes_no_second_write` |
| `269` | 47 | `test_resume_of_pass_makes_no_second_write` |
| `272` | 46 | `test_resume_of_pass_makes_no_second_write` |
| `279` | 39 | `test_resume_of_pass_makes_no_second_write` |
| `282` | 42 | `test_resume_of_pass_makes_no_second_write` |
| `285` | 36 | `test_resume_of_pass_makes_no_second_write` |
| `288` | 36 | `test_resume_of_pass_makes_no_second_write` |
| `291` | 36 | `test_resume_of_pass_makes_no_second_write` |
| `299` | 46 | `test_resume_of_pass_makes_no_second_write` |
| `303` | 47 | `test_resume_of_pass_makes_no_second_write` |
| `307` | 47 | `test_resume_of_pass_makes_no_second_write` |
| `315` | 45 | `test_resume_of_pass_makes_no_second_write` |
| `317` | 21 | `test_blocked_qa_records_blocked_and_holds_with_no_adapter_writes` |
| `325` | 152 | `test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub]` |
| `327` | 155 | `test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub]` |
| `334` | 23 | `test_resume_of_pass_makes_no_second_write` |
| `336` | 6 | `test_resume_of_pass_makes_no_second_write` |
| `352` | 24 | `test_resume_of_pass_makes_no_second_write` |
| `354` | 25 | `test_resume_of_pass_makes_no_second_write` |
| `355` | 16 | `test_blocked_qa_records_blocked_and_holds_with_no_adapter_writes` |
| `357` | 16 | `test_blocked_qa_records_blocked_and_holds_with_no_adapter_writes` |
| `359` | 14 | `test_blocked_qa_records_blocked_and_holds_with_no_adapter_writes` |
| `360` | 12 | `test_blocked_ledger_replans_when_the_defect_is_gone` |
| `364` | 10 | `test_resume_of_pass_makes_no_second_write` |
| `366` | 6 | `test_resume_of_pass_makes_no_second_write` |
| `367` | 6 | `test_resume_of_pass_makes_no_second_write` |
| `369` | 5 | `test_resume_of_pass_makes_no_second_write` |
| `371` | 3 | `test_resume_of_pass_makes_no_second_write` |
| `385` | 195 | `test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub]` |
| `397` | 172 | `test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub]` |
| `425` | 52 | `test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub]` |
| `430` | 159 | `test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub]` |
| `465` | 7 | `test_caller_spec_fields_are_not_the_facts` |
| `471` | 3 | `test_oversized_hub_description_is_not_adopted` |
| `473` | 18 | `test_edited_hub_prose_is_blocked_not_self_compared[purpose-one]` |
| `490` | 14 | `test_unnamed_caller_cannot_adopt_a_live_hub_edit[forged-purpose-one]` |
| `509` | 191 | `test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub]` |
| `516` | 189 | `test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub]` |
| `523` | 3 | `test_oversized_hub_description_is_not_adopted` |
| `526` | 187 | `test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub]` |
| `552` | 2 | `test_unnamed_sixty_four_character_hub_name_passes` |
| `555` | 4 | `test_unnamed_caller_cannot_adopt_a_live_hub_edit[forged-purpose-all]` |
| `562` | 9 | `test_qa_pass_persists_one_ledger_and_one_link[business-Studio Ledger-Studio Home-Desk]` |
| `564` | 4 | `test_caller_tier_does_not_override_stored_kinds[mass]` |
| `574` | 195 | `test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub]` |
| `577` | 196 | `test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub]` |
| `580` | 196 | `test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub]` |
| `583` | 197 | `test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub]` |
| `595` | 190 | `test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub]` |
| `598` | 25 | `test_oversized_hub_description_is_not_adopted` |
| `601` | 190 | `test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub]` |
| `603` | 191 | `test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub]` |
| `617` | 19 | `test_unnamed_caller_cannot_adopt_a_live_hub_edit[forged-purpose-one]` |
| `621` | 19 | `test_unnamed_caller_cannot_adopt_a_live_hub_edit[forged-purpose-one]` |
| `628` | 21 | `test_unnamed_caller_cannot_adopt_a_live_hub_edit[forged-purpose-one]` |
| `638` | 194 | `test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub]` |
| `649` | 49 | `test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub]` |
| `665` | 3 | `test_missing_page_writes_nothing` |
| `668` | 198 | `test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub]` |
| `675` | 162 | `test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub]` |
| `688` | 49 | `test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub]` |
| `693` | 51 | `test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub]` |
| `706` | 51 | `test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub]` |
| `719` | 197 | `test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub]` |
| `724` | 50 | `test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub]` |
| `726` | 49 | `test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub]` |
| `746` | 58 | `test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub]` |
| `755` | 4 | `test_forged_captured_url_blocks_secret_links` |
| `769` | 5 | `test_forged_captured_url_blocks_secret_links` |
| `771` | 11 | `test_forged_captured_url_blocks_secret_links` |
| `773` | 3 | `test_forged_captured_url_blocks_secret_links` |
| `776` | 4 | `test_forged_captured_url_blocks_secret_links` |
| `781` | 5 | `test_forged_captured_url_blocks_secret_links` |
| `788` | 51 | `test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub]` |
| `790` | 50 | `test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub]` |
| `792` | 50 | `test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub]` |
| `802` | 51 | `test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub]` |
| `809` | 56 | `test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub]` |
| `811` | 52 | `test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub]` |
| `813` | 163 | `test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub]` |
| `820` | 50 | `test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub]` |
| `824` | 162 | `test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub]` |
| `826` | 162 | `test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub]` |
| `828` | 50 | `test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub]` |
| `846` | 52 | `test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub]` |
| `849` | 52 | `test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub]` |
| `852` | 52 | `test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub]` |
| `855` | 53 | `test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub]` |
| `858` | 53 | `test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub]` |
| `878` | 208 | `test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub]` |
| `883` | 207 | `test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub]` |
| `885` | 207 | `test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub]` |
| `887` | 207 | `test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub]` |
| `889` | 207 | `test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub]` |
| `892` | 207 | `test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub]` |
| `894` | 207 | `test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub]` |
| `897` | 207 | `test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub]` |
| `899` | 208 | `test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub]` |
| `938` | 149 | `test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub]` |
| `940` | 149 | `test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub]` |
| `942` | 149 | `test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub]` |


### Round 5 record at tip `45818d9e` (2026-10-08)

Round 5 is tip `45818d9e`, not the round 6 commit. It answers reviewer review 5454105031 and verifier comment 6056684351, both on tip `5dc55814`. The tables in this section are tip `45818d9e`. The Round 4 tables below are tip `5dc55814` and are not these counts. The round-3 tables are tip `9eff481e`. This tip's CI run is not invented here. The verifier later showed that four colour-name weakenings and two semicolon weakenings in this record were false equivalents. Round 6 kills them. The counts below stay the published tip `45818d9e` pass.

`run_fact_ledger` is async at `notion_fact_ledger.py:155`. `_plan` at `:346` awaits `live_qa_passed` (`notion_qa.py:496`) before `_write` at `:876`, which calls `write_checkpoint` at `:915`. `qa_verdict` is `stored_pass and qa_live` at `:382`. A matching caller keeps the caller hubs (`_comparison_spec` `:437`). A live purpose, buyer, or practice edit on that caller is `BLOCKED` (`test_edited_hub_prose_is_blocked_not_self_compared`). A mismatched caller is the else branch at `:441`. It parses live section text with `_durable_detail` (`:572`) and refuses when that text is not the caller's prose (`_caller_prose_matches` `:506`), raising `fact ledger caller does not match` with 0 writes. Identity `Not The Row`, hubs named `Other ` plus the judged name, and rotated hubs are the three callers. One purpose edit is hub 2. All-purpose, all-buyer, and all-practice are the other three. That is 12 combinations (`test_unnamed_caller_cannot_adopt_a_live_hub_edit`). An honest named `BLOCKED` is not overwritten to `PASS` on resume (`test_stored_blocked_is_not_overwritten_on_a_forged_resume`). The first mismatched call does not write `PASS`. A mismatched caller whose descriptions still equal the live text can `PASS`. An unnamed 64-character hub name does (`test_unnamed_sixty_four_character_hub_name_passes`, 1 write). `>=` on that length raises `ProductBuildError` and writes nothing. The named path uses `_require_hub_name` (`:480`) and does not execute `_durable_detail`. D-0029 records the caller-trust limit: a caller who rewrites descriptions to the edited pages still matches.

`_formula_expression` (`:781`) returns `None` unless `type(expression) is str` (`:805`). `Liar("x;y")` on `current_date` is `BLOCKED`, the dashboard fact is `missing`, `x;y` is not stored, adapter writes are 0, and the checkpoint write is 1 (`test_lying_formula_expression_is_blocked`). The semicolon BoolOp at `:760` is not reached for that value. Forcing `";" in expression` to `False`, `";" in name` to `False`, or the `or` to `and` leaves both the stock code and the mutant `BLOCKED`. Those three rows are equivalent. The exact-str check is killed: `type(expression) is not str` replaced with `False` fails 1, and replaced with `True` fails 47.

`_saved_holds` (`:310`) raises `fact ledger does not match` when a stored `PASS` has checks that are all true but renamed, reordered, or one short (`:333`, `test_saved_pass_checks_must_match_the_plan`). Replacing `saved.checks != plan.checks` with `False` fails 3. The public entry rejects that record in `_require_ledger` (`:229`) before the helper. The `BLOCKED` branch at `:328` still returns false when the checks changed (`test_a_changed_blocked_check_is_replanned`).

`_redacted_url` (`:712`) stores scheme and host. Userinfo, the path, the query, the fragment, a port, and a bare token are not stored. `ftp://example.com`, `https://@`, and `https://evil;example` are `missing` at the helper and at the public entry (`test_redacted_url_drops_a_bare_token`, `test_untrusted_scheme_or_host_is_stored_as_missing`). A provider read failure is `ProviderFailure`, `ConnectionError`, or `OSError` (`:194`). `RuntimeError`, `Exception`, `LookupError`, `ValueError`, and `KeyError` are redacted to `fact ledger read failed` and are not provider jobs (`:201`, `test_code_errors_are_redacted_and_not_provider_jobs`).

The on-disk progress record stores `next_phase` (`notion_progress_record.py:220`). `_require_shape` requires it (`notion_progress.py:431`). A named `BLOCKED` ledger's in-memory `next_phase` is that same value, `test_matrix`. `test_legal_bounds_pass_and_one_past_refuses` runs a 64-character name, a 500-character purpose, and 8 hubs to `PASS`, then a 65-character name in `_require_hub_name` and on the public restamp, and 9 hubs in `_require_hub_count` and on the public loader (`checkpoint hubs must be six to eight`). `test_temp_names_are_matched_literally` monkeypatches `_pid_alive` (`notion_progress.py:209`) so only a `sleep` pid is alive. `.bx.json.999.tmp` is not parsed as a pid. The child script in `test_keyboard_interrupt_still_exits_130` maps an escaped `KeyboardInterrupt` to exit 130. This VM's Python 3.12.3 reports an uncaught interrupt as 130. The verifier VM reported 1. The script no longer depends on that default. Four cases passed. `asyncpg` 0.31.0 is installed. The suite skips 193 tests when it is present. Without it those tests error instead of skipping. The 12 `test_compose_preserves_the_postgres_password` failures are the absent `docker` binary. They are local-only. CI is the gate.

Product-build tests: 826 passed (`test_notion_fact_ledger.py`, `test_notion_product_qa.py`, the variants file, the progress file, and the six phase files), in 42.76s. `ruff format --check` and `ruff check` are clean on the changed modules. `pyright` 1.1.411 reports 0 errors on those modules. The notice that 1.1.414 exists is not a failure. SQLAlchemy is 2.0.52. Sockets stay blocked. No production Notion or Etsy. No commissioning. Revision stays 58. `head_sha` stays `a4e9b025021b4effbb2b2879c1db756403cb1676`. Exit 78 stays HELD. This is not SESSION_07 COMPLETE.

Census of `notion_fact_ledger.py` on tip `45818d9e`: if 104, elif 0, compare 169, boolop 54, operand 125, ifexp 11. That is 338 decision sites. 338 decision sites + 125 operands = 463. Operand rows are each operand replaced with `True` and with `False`, plus one flip per `and` or `or` (125 times 2, plus 71 flips, which is 321). If-flips are the 104 `if` tests. Progress rows are `notion_progress.py:236`, `:239`, `:313`, `:316`, `:318`, and the BoolOp whose operands are `:319` through `:322`. Variant rows are `notion_variants.py:280`, `:519`, and `:904`.

Sweep method. One uninterrupted pass. Command: `python /tmp/sweep_operands.py` from `/workspace`, 4 workers (`nproc` 4). Each worker copied `src` and `config` to its own directory, set `PYTHONPATH` to that `src`, and ran `pytest -q --tb=no -rfE -p no:cacheprovider -o pythonpath=`. The editable install was not the mutant. The ledger and progress suite was `tests/unit/agents/test_notion_fact_ledger.py`. Variant lines used `test_aligned_pairs_refuse_a_duplicated_palette_name`, `test_non_workspace_home_is_refused_by_the_source_check`, `test_spec_page_must_be_the_stored_home`, and `test_duplicate_palette_token_names_refuse_before_any_write`. The Failed column is the count of lines starting with `FAILED` or `ERROR`. A non-zero exit with zero such lines is still a kill. A syntax error is not a kill. None occurred. Python 3.12.3. pytest 8.4.2. `asyncpg` 0.31.0 is what lets the collected suite skip rather than error. `_pid_alive` is monkeypatched in `test_temp_names_are_matched_literally`.

The Failed sums published for tip `5dc55814` (7464, 6756, and 14261) do not reproduce. The reviewer and the verifier both measured 7591, 6861, and 14493 on that tip. Rows, kills, and the 20 equivalent names matched. The gap is 127 operand failures and 105 if-flip failures. That published merge was an earlier suite, overlaid by later equivalent re-runs, and only one of those equivalents was remeasured after tests were added. It was not one pass of that tip. This commit does not claim those sums. The sums below are one pass of this tree.

| Sweep | Rows | Killed | Equivalent | Failed sum |
|---|---:|---:|---:|---:|
| Ledger operands (non-if) | 321 | 299 | 22 | 8845 |
| Ledger if-flips | 104 | 104 | 0 | 8131 |
| Progress `:236` and `:239` | 12 | 12 | 0 | 28 |
| Progress dedupe `:313`, `:316`, `:318`, `:319`–`:322` | 14 | 14 | 0 | 35 |
| Variants `:280`, `:519`, `:904` | 13 | 13 | 0 | 13 |
| Combined | 464 | 442 | 22 | 17052 |

The 22 equivalents, all in `notion_fact_ledger.py`. Each one was run. Failed is 0. The probe is the helper call and the public entry. Both agree.

The BoolOp at `:180` is one site. Its node lineno is 180. The second operand's own lineno is 181. The previous log's separate `:181` row is that operand. They are folded here onto `:180`.

| Line | Mutation | Probe |
|---|---|---|
| `:180` | `saved_ledger is not None` to `True`, and `saved_link is not None` to `True` (operand lineno 181) | `_stored_pair` returns both or neither. One `None` never arrives. Forcing either conjunct to `True` still short-circuits when the pair is absent, and still calls `_saved_holds` when both exist. |
| `:394` | `type(value) is not str` to `False`, `value == ""` to `False`, `value.strip() != value` to `False`, and both `or` flips | Facts built above the loop are non-empty stripped strings. `identity_hubs=()` raises in `_require_hub_count` (`:470`) before this loop. Helper and public entry both refuse the empty hub list. |
| `:584` | `len(block.content) > len(prefix)` to `True` | Prefix-only content yields detail `""` either way, and the empty-detail check raises the same `ProductBuildError` with 0 writes. |
| `:624` | `page.title == ""` to `False` | An empty title is returned by the `if` and by the fall-through. Both are `""`. The public hub fact is `missing` either way. |
| `:642` | `type(name) is str` to `True` | `_page_title` already returned a `str`. |
| `:642` | `name == ""` to `False` | The first loop already stored `missing` for `""`. |
| `:673` | `type(title) is str` to `True` | The preceding ternary already produced a `str` (`missing` or the title). |
| `:694` | `captured != ""` to `True` | `""` becomes usable. `_redacted_url("")` returns `missing`. The fact component is `missing` either way, and agreed stays false. |
| `:718` | `captured == ""` to `False` | `""` falls through. `separator == ""` still returns `missing`. |
| `:725` | `separator == ""` to `False` | A string with no `://` has rest `""`. `rest == ""` still returns `missing`. Helper `notaurl` is `missing` either way. |
| `:725` | `rest == ""` to `False` | `http://` has an empty host. `host == ""` still returns `missing`. |
| `:730` | `host.strip() != host` to `False` | Any space in the captured string returns `missing` before the host is parsed (`:722`). The strip conjunct is not reached. |
| `:758` | `expression is None` to `False` | `None` still fails `expression != wanted[1]`. The dashboard fact is `missing`. The helper returns `None` for a blank formula (`test_blank_formula_expression_is_missing`). |
| `:760` | `";" in name` to `False`, `";" in expression` to `False`, and `or` to `and` | A non-str never reaches this line. `Liar("x;y")` on `current_date` is `None` at `:805`, so stock and mutant are both `BLOCKED`, dashboard `missing`, 1 checkpoint write, 0 adapter writes. A matching canonical expression has no semicolon. |
| `:839` | `allowed is None` to `False` | A predecessor in `_GRAPH` has an allowed set. A mismatched set still fails `frozenset(...) != allowed`. The public renamed workflow refuses with 0 writes. |

Killing-test map for this commit.

| Input | Site | Killing test | Sweep |
|---|---|---|---|
| Identity `Not The Row`, hubs `Other ` plus the name, or rotated hubs, after one purpose (hub 2), all purposes, all buyer, or all practice | `:441`–`:455` | `test_unnamed_caller_cannot_adopt_a_live_hub_edit` (12). QA does not pass the same pair. 0 writes. | The refusal is the prose compare, not one operand row. |
| Honest named `BLOCKED`, then the same mismatched caller | `:328` returns false only when the caller matches | `test_stored_blocked_is_not_overwritten_on_a_forged_resume`. Verdict stays `BLOCKED`. `next_phase` is `test_matrix` in memory and on disk. | |
| Stored `PASS`, then a live edit, then the mismatched caller | `:441` | `test_forged_caller_does_not_return_a_stale_pass`. Bytes unchanged. Verdict stays `PASS`. | |
| Named caller, live purpose (one and all), buyer, or practice | `:437` | `test_edited_hub_prose_is_blocked_not_self_compared`. `BLOCKED`, `qa_verdict` false, `next_phase` matches the file. | |
| `Liar("x;y")` on `current_date` | `:805` | `test_lying_formula_expression_is_blocked`. Helper returns `None`. Public `BLOCKED`, dashboard `missing`, `x;y` absent, 1 checkpoint write. | `type(expression) is not str` to `False` fails 1. To `True` fails 47. The `:760` weakenings are the equivalent rows above. |
| PASS checks renamed, reordered, or one short | `:333` | `test_saved_pass_checks_must_match_the_plan`. Helper raises `fact ledger does not match`. Public `_require_ledger` (`:229`) rejects the record first. | `saved.checks != plan.checks` to `False` fails 3. |
| Unnamed 64-character hub name | `:580` `len(name) > 64` | `test_unnamed_sixty_four_character_hub_name_passes`. `PASS`, 1 write. `>=` raises and writes nothing. Named 64 uses `:480`. | Operand to `True` fails 18. Operand to `False` fails 1 (`test_detail_bounds_are_a_product_error`). |
| 65-character name and 9 hubs | `:480`, `:470`, loader | `test_legal_bounds_pass_and_one_past_refuses` calls `_require_hub_name("N"*65)` and `_require_hub_count` of 9, restamps a 65-character public name, and appends hubs until the loader raises `checkpoint hubs must be six to eight`. | |
| Provider stream counts 2, 2, 2, 1 | `:313`, `:319`–`:321` | `test_provider_stream_job_counts_are_exact`. DIFF_PHASE, DIFF_OP, DIFF_KIND, SAME. | Kind `True` `:319` fails 1. Operation `True` `:320` fails 2. Phase `True` `:321` fails 2. The three `and` to `or` flips fail 4. The kind guard `:313` fails 2. |
| Dead temp deleted, live pid kept, literal name | `:236`, `:239` | `test_temp_names_are_matched_literally` monkeypatches `_pid_alive`. | 12 of 12 killed, Failed sum 28. |
| Scheme, empty host, delimiter host | `:725`, `:730` | `test_redacted_url_drops_a_bare_token` and `test_untrusted_scheme_or_host_is_stored_as_missing`. | `scheme not in` to `False` fails 2. `host == ""` to `False` fails 2. The delimiter `any` to `False` fails 2. The three `or` flips fail 2. `separator == ""`, `rest == ""`, and `host.strip()` stay equivalent, as the table says. |
| Code errors and provider errors | `:194`, `:201` | `test_live_read_failure_is_a_redacted_job` (`ConnectionError`, `OSError`, `TimeoutError`). `test_code_errors_are_redacted_and_not_provider_jobs` (`RuntimeError`, `Exception`, `LookupError`, `ValueError`, `KeyError`). | |
| Keyboard interrupt | child script | `test_keyboard_interrupt_still_exits_130`. Four cases, exit 130. The secret is not in stdout or stderr. | |

### Round 4 record at tip 5dc55814

Round 4 is tip `5dc55814`, not this commit. It answers the verifier FAIL on tip `9eff481e` (comment 6053693235, CI run 37729558421, job 113155351185) and the reviewer FAIL on the same tip. The tables below this paragraph are tip `5dc55814`. The verifier recorded CI verify run 37745545575, job 113206034345, on that tip. The round-3 tables later in this section are tip `9eff481e` and are not these counts. The Failed sums in this record (7464, 6756, 14261) are the merged earlier suite described in the sweep paragraph. They are not a single pass of tip `5dc55814`. The reviewer and the verifier measured 7591, 6861, and 14493 on that tip.

`run_fact_ledger` is async at `notion_fact_ledger.py:155`. `_plan` at `:342` awaits `live_qa_passed` (`notion_qa.py:496`) before `_write` at `:829`, which calls `write_checkpoint` at `:868`. `qa_verdict` is `stored_pass and qa_live` at `:378`. `stored_pass` is the stored verdict and the stored checks, at `:376`. A stored non-PASS whose live state would pass raises `qa record does not match` in `_require_stored_qa` at `:287`, with 0 writes. A `BLOCKED` ledger whose checks changed is re-planned (`_saved_holds` returns false at `:327`). A check-equal fact change stays a refusal. When the caller names the same hub names and `spec.identity` equals the notification row Name, `_comparison_spec` at `:408` keeps the caller hubs, buyer, and flagship. A live purpose edit on one hub, the same edit on every hub, or a buyer or practice edit is then `BLOCKED`, with ready `""` and `qa_verdict` false (`test_edited_hub_prose_is_blocked_not_self_compared`). A caller that does not name that identity is not a fact source. Stored blocks are parsed, and a missing block id is a refusal. Tier follows the stored database kinds (`_tier_from_kinds` at `:493`). A whitespace-only purpose suffix raises `ProductBuildError` (`fact ledger fact is not a durable string`) with 0 writes, not `ValidationError`. A `NotionPage` subclass on the notification row raises `fact ledger identity is missing` (`_stable_identity` at `:504`). `_formula_expression` at `:737` returns `str | None`. A missing or empty expression is `None`, never `""`. The workflow link still checks each of the ten edges three ways. Successor sets are exact (`_walk_chain` at `:765`). An extra successor or a cycle refuses. Known ids only. The proof copy is not a known id, and `page_count` stays 15. `_write_qa` keeps a stored ledger and link at `notion_qa.py:869`. Exit 78 stays HELD. This is not SESSION_07 COMPLETE.

Product-build tests: 791 passed (`test_notion_fact_ledger.py`, `test_notion_product_qa.py`, the variants file, the progress file, and the six phase files), in 41.23s. `ruff format --check` and `ruff check` are clean on the five changed modules. `pyright` 1.1.411 reports 0 errors on those modules. The notice that 1.1.414 exists is not a failure. SQLAlchemy in this workspace is 2.0.52. Sockets stay blocked. No production Notion or Etsy. No commissioning. `IMPLEMENTATION_STATE.json` is not in this commit. Revision stays 58. `head_sha` stays `a4e9b025021b4effbb2b2879c1db756403cb1676`.

Census of `notion_fact_ledger.py` on this tip, counted the same way as round 3 (an `If` that is not an `elif`, an `elif`, a `Compare`, a `BoolOp`, each `BoolOp` value, and an `IfExp`). The counts are if 97, elif 0, compare 160, boolop 52, operand 120, ifexp 11. That is 440 sites. The operand sweep replaces each operand with `True` and with `False`, and flips each `and` or `or`. Ledger non-if rows: 308 (120 times 2, plus 68 operator flips). If-flips: one `not` wrapped around each of the 97 `if` tests. Progress rows are the bool operands and if-flips at `notion_progress.py:235` and `:238`. Variant rows are the bool operands and if-flips at `notion_variants.py:280`, `:519`, and `:904`.

Sweep method. Each worker imported a copy of `src` (`PYTHONPATH` set to that copy, pytest `-o pythonpath=`), with `config` copied beside it. The editable install was not the mutant. The owning suite for ledger and progress mutants was `tests/unit/agents/test_notion_fact_ledger.py`. Variant lines used `test_aligned_pairs_refuse_a_duplicated_palette_name`, `test_non_workspace_home_is_refused_by_the_source_check`, `test_spec_page_must_be_the_stored_home`, and `test_duplicate_palette_token_names_refuse_before_any_write`. The Failed column is the count of lines starting with `FAILED` or `ERROR`. A non-zero exit with zero such lines is still a kill. A syntax error is not a kill. None occurred. The 430-row merge is round 1, overlaid by the re-run of the then-equivalent keys, overlaid by the seven `:547` mutants. After that merge, `:758` `formula.expression == ""` replaced with `False` was still equivalent. `test_blank_formula_expression_is_missing` now requires the helper to return `None`. That one mutant was remeasured and is killed (Failed 1). The other 20 equivalents were not re-run after that assertion. The assertion does not call the sites those 20 mutate.

| Sweep | Rows | Killed | Equivalent | Failed sum |
|---|---:|---:|---:|---:|
| Ledger operands (non-if) | 308 | 288 | 20 | 7464 |
| Ledger if-flips | 97 | 97 | 0 | 6756 |
| Progress `:235` and `:238` | 12 | 12 | 0 | 28 |
| Variants `:280`, `:519`, `:904` | 13 | 13 | 0 | 13 |
| Combined | 430 | 410 | 20 | 14261 |

The 20 equivalents, all in `notion_fact_ledger.py`. Each one was run. Failed is 0. The probe is the input that used to distinguish the old line, or the reachable case on this tip.

| Line | Mutation | Probe |
|---|---|---|
| `:180` | `saved_ledger is not None` to `True` | `_stored_pair` returns both or neither. One `None` still fails the `and`. |
| `:181` | `saved_link is not None` to `True` | Same pair. |
| `:329` | PASS-branch `saved.checks != plan.checks` to `False` | A foreign check name raises `fact ledger record is incomplete` at `:234` (`test_permuted_check_names_are_incomplete`). A PASS with a false saved check raises in `_verdict_agrees`. A PASS whose live plan has a false check raises `fact ledger does not match` at `plan.blocked` (`:332`), with 0 writes. The BLOCKED-branch twin at `:324` is killed by `test_a_changed_blocked_check_is_replanned`. |
| `:390` | `type(value) is not str` to `False` | Facts built above the loop are non-empty stripped strings. `identity_hubs=()` raises in `_require_hub_count` at `:465` before this loop. |
| `:390` | `value == ""` to `False` | Same. The empty fact never arrives. |
| `:390` | `value.strip() != value` to `False` | Same. |
| `:390` | first `or` to `and` | Same. The strip conjunct is not what keeps the fact out. |
| `:390` | second `or` to `and` | Same. |
| `:551` | `len(block.content) > len(prefix)` to `True` | Prefix-only content yields detail `""` either way, and `:555` raises. |
| `:591` | `page.title == ""` to `False` | The empty title is returned by the `if` and by the fall-through. Both are `""`. |
| `:609` | `type(name) is str` to `True` | The first loop and `_page_title` already produce a `str`. |
| `:609` | `name == ""` to `False` | The first loop already stores `missing` for `""`. |
| `:640` | `type(title) is str` to `True` | The preceding line already coerces a non-str title to `missing`. |
| `:661` | `captured != ""` to `True` | `""` becomes usable, `_redacted_url("")` returns `missing`, and agreed stays false. The fact component is `missing` either way. |
| `:681` | `captured == ""` to `False` | Stock returns `missing`. The mutant falls through and `bare == ""` returns `missing`. |
| `:714` | `expression is None` to `False` | `None` still fails `expression != wanted[1]`. The dashboard fact is `missing`. |
| `:716` | `";" in name` to `False` | A wanted expression has no semicolon. A live semicolon already failed equality at `:714`. |
| `:716` | `";" in expression` to `False` | Same. |
| `:716` | `or` to `and` | Same. |
| `:792` | `allowed is None` to `False` | An unknown predecessor still has `frozenset(...) != None`, so the same raise happens. |

Killing-test map for the verifier's distinguishing inputs on tip `9eff481e`. The old line is the verifier's line. The new line is this tip. Where the old mutant is gone, the test is the one that runs the distinguishing input.

| Verifier input | Old line | This tip | Killing test |
|---|---|---|---|
| Purpose edit on one hub, on every hub, or a buyer edit, with stored QA PASS and no QA re-run | `:345`, `:424-426` | `_comparison_spec` `:408` | `test_edited_hub_prose_is_blocked_not_self_compared` |
| `_require_pairs([])` | `:253` | `:264` | `test_empty_pair_list_is_incomplete` |
| Stored PASS with a false check | `:279` ×2 | `:290` | `test_pass_with_a_false_check_is_not_stored` |
| All-true checks under a foreign name | `:318` | `:234` | `test_permuted_check_names_are_incomplete`. The PASS-branch checks operand at `:329` is the equivalent row above. |
| Stored BLOCKED with every check true | `:363` ×3, `:365` | `:376` | `test_blocked_all_true_checks_are_not_a_pass` |
| `identity_hubs=()` | `:377` | `:465` before `:390` | `test_hub_count_accepts_six_through_eight`. The `:390` weakenings are the equivalent rows above. |
| Blank notification row, cleared buyer or feature | `:403-:405` | `:408`, `:504` | `test_row_name_must_be_a_token`, `test_edited_hub_prose_is_blocked_not_self_compared`, `test_caller_identity_must_match_the_row` |
| Duplicate or non-catalogue kinds, and the business tier | `:407`, `:409` ×5 | `:493` | `test_tier_follows_the_stored_kind_set`, `test_caller_tier_does_not_override_stored_kinds`, `test_caller_tier_does_not_override_mass_kinds`, `test_verifier_shapes_are_refused` |
| Notification subclass | `:437` | `:510` | `test_row_subclass_is_a_missing_identity` |
| Padded row Name | `:439` | `:513` | `test_padded_row_name_is_a_missing_identity`, `test_row_name_must_be_a_token` |
| List section, 3-tuple, wrong role | `:468` ×2, `:471` ×4 | `:528` | `test_section_shape_is_a_pair` |
| Non-text purpose block, `content=5` | `:474` ×3 | `:531`, `:533` | `test_non_text_purpose_block_is_refused`, `test_numeric_purpose_content_is_a_product_error` |
| 65-character name, 501-character detail, and the legal bounds | `:491` | `:472`, `:547`, `:555` | `test_hub_name_bounds_are_a_product_error`, `test_detail_bounds_are_a_product_error`, `test_legal_bounds_pass_and_one_past_refuses` |
| Five hubs and nine hubs, and a legal eight | `:494` | `:465` | `test_hub_count_accepts_six_through_eight`, `test_verifier_shapes_are_refused`, `test_legal_bounds_pass_and_one_past_refuses` |
| Hub title `"Hub 1 "` | `:540` | `:609` strip | `test_trailing_space_in_a_hub_title_can_be_repaired`, `test_database_title_with_edge_space_is_missing` for the database twin. `name == ""` and `type(name) is str` on the second loop stay equivalent, as the table says. |
| `_safe_label(1)` | `:612` | `_safe_label` `:691` | `test_numeric_sample_title_is_missing` |
| Palette name duplicated | `:280` if-flip | `:280` | `test_aligned_pairs_refuse_a_duplicated_palette_name`. The public build still raises `checkpoint aesthetics accent is duplicated` first. |
| Home id | `:904` if-flip | `:904` | `test_spec_page_must_be_the_stored_home` |
| Parent type | `:519` if-flip | `:519` | `test_non_workspace_home_is_refused_by_the_source_check` |
| Dead temp deleted, live pid kept, literal name | progress `:229`, `:232` | `:235`, `:238` | `test_stale_checkpoint_tmp_is_removed_on_the_next_write`, `test_foreign_pid_temp_is_kept`, `test_temp_cleanup_keeps_unrelated_names`, `test_temp_names_are_matched_literally`. 12 of 12 killed, Failed sum 28. |
| Empty formula returns `None` | `:671` | `:758` | `test_blank_formula_expression_is_missing` |

`test_inconsistent_stored_qa_writes_nothing` covers an inconsistent stored QA record. Its docstring says a forged but consistent PASS with a live defect writes one `BLOCKED` ledger. That name does not claim the consistent case writes nothing.

Legal bounds that must pass: a 64-character hub name, a 500-character purpose detail, and 8 hubs. One past each bound must refuse: 65, 501, and 9. `test_legal_bounds_pass_and_one_past_refuses` runs the public path. The direct helpers cover 6 and 8 against 5 and 9, and 64 against 65.

### Round 3 record at tip 9eff481e

These counts are not this commit. Round 2's 176-row and 39-row counts were an earlier tip. They are not these counts either.

`run_fact_ledger` on that tip was async at `notion_fact_ledger.py:144`. The plan at `_plan` (`:331`) awaited `live_qa_passed` (`notion_qa.py:476`) before `_write` (`:739`), which called `write_checkpoint` at `:778`. The observed spec was read from the stored pages. That is the behaviour the verifier rejected.

Empty captured URL is two contracts. QA still skips `""` the same as a missing URL (`notion_qa.py:557`). `test_empty_captured_url_repairs_like_a_missing_url` records `PASS` with repairs `("published",)`. The ledger does not skip `""` or `None` on a published page. `test_empty_or_missing_public_url_blocks_secret_links` records `BLOCKED`, the secret-link fact component `missing`, and 0 adapter writes.

`write_checkpoint` keeps earlier `repair_jobs` when the file already exists (`notion_progress_record.py:185`). A garbage, empty, or forged prior is refused and the file is left unchanged. `write_document` matches a sibling temp by the literal prefix `.{name}.` and the suffix `.tmp` (`notion_progress.py:219`). A character class in the file name is not a glob. A temp whose middle is a live pid is kept. A provider that publishes and then leaves the URL untrusted stays `BLOCKED` after one `publish_page`, records repairs `("published",)`, and does not call `duplicate_page` (`notion_qa.py:787`).

The ledger covers known ids only. Popping a page that is not a known id before the first ledger run stays `PASS` with one checkpoint write. The proof page is the only extra page and it is not a known id. `test_unknown_page_before_the_ledger_is_not_a_fact` pins that. An extra `NotionPage` subclass is a page and blocks. A known id replaced by a subclass raises `fact ledger page is missing`.

SQLAlchemy in this workspace is 2.0.52, the same version as `uv.lock`. A verifier environment on a different SQLAlchemy build is not a product defect. `pyright` 1.1.411 reports 0 errors on the changed modules. The notice that 1.1.414 exists is not a failure.

Blocker map. Reviewer A and verifier 1, stored QA verdict: `test_blocked_qa_with_a_live_pass_writes_nothing`, `test_fresh_duplicate_block_is_not_a_ledger_pass`, and `test_forged_qa_verdict_writes_nothing`. Reviewer B and verifier 4, edge whitespace before persist: `test_edge_whitespace_is_refused_before_persist`. Verifier 2, each of ten edges three ways: `test_each_edge_is_read_three_ways`. Verifier 3, padded sample and padded row recover: `test_padded_sample_title_recovers_after_the_trim` and the whitespace test. Verifier 5, exact `str`: `test_captured_url_must_be_exact_str`. Verifier 6, secret-fact component, QA publish guard, and the prior rebuild job: `test_wrong_host_path_is_stored_as_the_captured_url`, `test_lying_publish_stays_blocked_without_a_duplicate`, `test_unpublished_and_duplicate_off_repairs_both`, `test_untrusted_publish_does_not_set_the_duplicate`, `test_publish_that_stays_unpublished_does_not_set_duplicate`, and `test_prior_rebuild_job_survives_the_ledger_write`. SF1 per-field dashboard: `test_blank_dashboard_row_title_refuses`, `test_blank_sample_title_is_missing`, `test_invisible_sample_mark_is_missing`, and `test_dashboard_delimiter_is_not_a_fact`. SF2 permuted names, `maybe`, forged repair, renamed workflow, and the false QA flag in the ledger file: `test_permuted_check_names_are_incomplete`, `test_permuted_fact_names_are_incomplete`, `test_check_flag_maybe_is_incomplete`, `test_forged_repair_required_on_a_pass_refuses`, `test_renamed_workflow_refuses`, and `test_blocked_qa_records_blocked_and_holds_with_no_adapter_writes`. SF3 missing hub: `test_missing_hub_in_the_spec_is_a_product_error` (`notion_hubs.py:145`). SF4 caller narrative: `test_caller_spec_fields_are_not_the_facts`. SF5 shape change stays refused: `test_wrong_hub_shape_stays_refused_until_the_name_matches`. SF6 redacted read failure: `test_live_read_failure_is_a_redacted_job`. SF7 applied repairs: the four QA publish-guard tests above. SF8 PASS plus a false check: `test_pass_with_a_false_check_is_refused`. Page subclass: `test_page_subclass_is_not_accepted` and `test_extra_page_subclass_blocks_the_ledger`. Direct `_write`: `test_missing_record_raises_product_error`. Literal temp names: `test_temp_names_are_matched_literally`. Oversized hub description: `test_oversized_hub_description_is_not_adopted`.

Product-build tests: 732 passed (`test_notion_fact_ledger.py`, `test_notion_product_qa.py`, the variants file, the progress file, and the six phase files). `ruff format --check`, `ruff check`, and `pyright` 1.1.411 report 0 errors on the changed modules. Sockets stay blocked. No production Notion or Etsy. No commissioning.

Census of `notion_fact_ledger.py` on tip `9eff481e`. An AST walk counts an `If` that is not an `elif`, an `elif` (`If` that is the sole `orelse` of another `If`), a `Compare`, a `BoolOp`, each `BoolOp` value as an operand, and an `IfExp`. The counts are if 85, elif 1, compare 136, boolop 49, operand 109, ifexp 9. That is 389 sites. The operand sweep replaces each operand span with `True` and with `False`, and flips the first ` or ` or ` and ` token of each `BoolOp`. That is 109 times 2 plus 49, which is 267 mutants. The owning file is `tests/unit/agents/test_notion_fact_ledger.py`, run with `pytest -q --tb=line`. The Failed column is the FAILED-line count. A syntax error is not a kill. None occurred. Workers imported a copy of `src` so the workspace file was not the mutant. The round-2 176 and the verifier's earlier 174 are not the counts of tip `9eff481e`.

Operand sweep: 267 rows, 212 killed, 55 equivalent. The Failed column sums to 3610. The equivalents are probe-backed in the table. The `:377` `strip` conjunct is killed (Failed 2). The same line's `or` to `and` flip is equivalent because every fact is a non-empty `str` and `and` binds tighter, so the strip conjunct still raises. Probe `test_edge_whitespace_is_refused_before_persist`. The old `:546` `None` `or` was split into three separate `if`s (`:748-753`) and is not a row. `test_missing_record_raises_product_error` raises `ProductBuildError`.

If-flip table: 49 rows, 46 killed, 3 equivalent. The Failed column sums to 273. The 17 variant-file rows were remeasured. Their Failed counts sum to 20. Three of them are equivalent. Ten rows were added for the admitted-event check, the successor-type check, the prior-file check, the secret-fact compare, the secret-fact if-exp, and the five `notion_qa.py:787` publish-guard mutants.

| Mutation | Site (file:line) | Failing tests | Failed |
|---|---|---|---|
| delete secret-link compare | `notion_variants.py:847` | test_replay_rejects_a_changed_secret_link | 1 |
| delete accent and vocabulary id compare | `notion_variants.py:844` | test_replay_rejects_a_moved_accent_block_id | 1 |
| delete saved-path _require_original | `notion_variants.py:837` | test_saved_home_original_flag_refuses[duplicate_as_template-True] | 2 |
| replace navigation block type check with False | `notion_aesthetics.py:346` | test_navigation_callout_fails_the_created_hub_pair | 1 |
| delete palette token name uniqueness | `notion_variants.py:280` | Equivalent. `test_duplicate_palette_token_names_refuse_before_any_write` still raises `checkpoint aesthetics accent is duplicated`. 0 writes. | 0 |
| delete variant name dedup | `notion_variants.py:198` | test_replay_rejects_a_duplicated_variant_label[name] | 1 |
| delete variant page-id dedup | `notion_variants.py:202` | test_replay_rejects_a_duplicated_variant_label[page_id] | 1 |
| delete len(children) != 2 | `notion_variants.py:895` | test_replay_rejects_an_extra_variant_child | 1 |
| delete home id check | `notion_variants.py:904` | Equivalent. `test_replay_rejects_a_home_without_the_spec_id` still raises `checkpoint page is missing from the fixture probe`. 0 writes. | 0 |
| delete _source_page parent_type | `notion_variants.py:519` | Equivalent. `test_replay_rejects_a_home_that_is_not_workspace` still raises `checkpoint page is not the stored top-level page`. 0 writes. | 0 |
| delete _find_titled len(matches) > 1 | `notion_variants.py:534` | test_two_colour_titles_refuse_before_any_write | 1 |
| delete _find_copy len(matches) > 1 | `notion_variants.py:548` | test_two_copy_titles_refuse_before_any_write | 1 |
| publish before blocks | `notion_variants.py:738` | test_each_variant_step_crash_resumes_without_a_second_page[add_callout_block] | 2 |
| skip retained created ids | `notion_progress_record.py:192` | test_reversed_dashboard_created_ids_survive_variants | 1 |
| delete plan nested-database refuse | `notion_variants.py:388` | test_database_under_a_structure_block_refuses_before_any_write[home] | 3 |
| drop hub and home blocks from nested parents | `notion_variants.py:624` | test_saved_database_under_a_structure_block_refuses[home] | 2 |
| exact type instead of isinstance | `notion_variants.py:584` | test_database_subclass_under_a_hub_block_is_refused | 2 |
| fresh-duplicate title is True | `notion_qa.py:574` on tip `9eff481e` | Replace `page.title == title` with True. test_renamed_variant_page_fails_fresh_duplicate. Re-checked: `:574` is the title compare. `:572` is the title assignment, not this conjunct | 1 |
| fresh-duplicate spec id is True | `notion_qa.py:576` on tip `9eff481e` | Replace `SPEC_ID_PROPERTY not in page.properties` with True. test_forged_spec_id_fails_fresh_duplicate. Re-checked: the spec-id conjunct is `:576`, not `:572` | 1 |
| empty captured url is checked | `notion_qa.py:557` | Delete `captured != ""`. QA only. test_empty_captured_url_repairs_like_a_missing_url | 1 |
| qa verdict check is True | `notion_fact_ledger.py:365` | Replace `stored_pass and qa_live` with True. test_blocked_qa_records_blocked_and_holds_with_no_adapter_writes | 21 |
| ready is always ListingCopyJob | `notion_fact_ledger.py:383` | test_blocked_qa_records_blocked_and_holds_with_no_adapter_writes | 13 |
| repair_required is always false | `notion_fact_ledger.py:382` | test_repaired_publish_keeps_the_listing_ready | 1 |
| supported_devices is desktop | `notion_fact_ledger.py:355` | test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub] | 2 |
| free_update_policy is free | `notion_fact_ledger.py:357` | test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub] | 2 |
| build_version is a constant | `notion_fact_ledger.py:358` | test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub] | 3 |
| colour names ignore the adapter title | `notion_fact_ledger.py:372` | test_renamed_variant_page_blocks_qa_facts | 3 |
| hubs_present is True | `notion_fact_ledger.py:367` | test_renamed_hub_is_blocked_with_no_adapter_writes | 5 |
| databases_present is True | `notion_fact_ledger.py:368` | test_renamed_database_blocks_the_database_check | 4 |
| dashboard_outputs check is True | `notion_fact_ledger.py:369` | test_blank_formula_blocks_dashboard_outputs | 11 |
| secret_links check is True | `notion_fact_ledger.py:370` | test_forged_captured_url_blocks_secret_links | 8 |
| blocked is False | `notion_fact_ledger.py:381` | test_blocked_qa_records_blocked_and_holds_with_no_adapter_writes | 53 |
| stored facts are not compared | `notion_fact_ledger.py:318` | test_forged_fact_does_not_match_and_writes_nothing | 1 |
| stored steps are not compared | `notion_fact_ledger.py:323` | test_forged_step_does_not_match_and_writes_nothing | 1 |
| blocked ledger does not replan | `notion_fact_ledger.py:316` | The check-diff `return False` becomes `return True`. test_blocked_ledger_replans_when_the_defect_is_gone | 10 |
| event-map route check is False | `notion_fact_ledger.py:704` | Replace the event-map compare with False. test_broken_workflow_graph_writes_nothing | 20 |
| ListingPackage output is skipped | `notion_fact_ledger.py:709` | test_missing_listing_package_refuses | 1 |
| stop stripping fact_ledger and workflow_link | `notion_aesthetics.py:151` | test_resume_of_pass_makes_no_second_write | 53 |
| qa rewrite drops the ledger keys | `notion_qa.py:845` | test_blocked_ledger_replans_when_the_defect_is_gone | 1 |
| admitted event check is False | `notion_fact_ledger.py:700` | Dropping the admitted-event check. Killed on every edge. test_each_edge_is_read_three_ways[admitted-edge0] | 10 |
| successor job types check is False | `notion_fact_ledger.py:702` | Dropping the successor-type check. Killed on every edge. test_each_edge_is_read_three_ways[successor-edge0] | 10 |
| prior file check is flipped | `notion_progress_record.py:185` | `is_file` flipped. A prior `rebuild_refused` job must survive. test_prior_rebuild_job_survives_the_ledger_write | 1 |
| secret shown compare is flipped | `notion_fact_ledger.py:603` | Compare flip stores a leading empty component. Killed. test_forged_captured_url_blocks_secret_links | 4 |
| secret shown ifexp is flipped | `notion_fact_ledger.py:603` | If-exp flip stores a leading empty component. Killed. test_forged_captured_url_blocks_secret_links | 4 |
| publish guard or becomes and | `notion_qa.py:787` | or to and. An untrusted URL must not set duplicate. test_lying_publish_stays_blocked_without_a_duplicate | 3 |
| publish guard left is True | `notion_qa.py:787` | Left conjunct forced True. An honest publish must still repair duplicate. test_unpublished_and_duplicate_off_repairs_both | 1 |
| publish guard left is False | `notion_qa.py:787` | Left conjunct forced False. An unpublished page must not set duplicate. test_publish_that_stays_unpublished_does_not_set_duplicate | 1 |
| publish guard right is True | `notion_qa.py:787` | Right conjunct forced True. An honest publish must still repair duplicate. test_unpublished_and_duplicate_off_repairs_both | 1 |
| publish guard right is False | `notion_qa.py:787` | Right conjunct forced False. An untrusted URL must not set duplicate. test_lying_publish_stays_blocked_without_a_duplicate | 2 |

Per-operand sweep of `notion_fact_ledger.py`. Site, operator, mutation, killing test or probe, Failed.

| Site | Op | Mutation | Failing tests | Failed |
|---|---|---|---|---|
| `notion_fact_ledger.py:163` | or | replace operand with True `qa is None` | test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub] | 165 |
| `notion_fact_ledger.py:163` | or | replace operand with False `qa is None` | test_missing_qa_and_half_a_pair_write_nothing | 1 |
| `notion_fact_ledger.py:163` | or | replace operand with True `not stored.variants` | test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub] | 165 |
| `notion_fact_ledger.py:163` | or | replace operand with False `not stored.variants` | Equivalent. `load_variant_checkpoint` returns only after variants exist, or it raises. Probe `test_qa_pass_persists_one_ledger_and_one_link`. | 0 |
| `notion_fact_ledger.py:163` | or | flip or to and `boolop or` | test_missing_qa_and_half_a_pair_write_nothing | 1 |
| `notion_fact_ledger.py:168` | and | replace operand with True `saved_ledger is not None` | Equivalent. `_stored_pair` returns both records or neither. A half pair raises first. Probe `test_missing_qa_and_half_a_pair_write_nothing`. | 0 |
| `notion_fact_ledger.py:168` | and | replace operand with False `saved_ledger is not None` | test_resume_of_pass_makes_no_second_write | 16 |
| `notion_fact_ledger.py:169` | and | replace operand with True `saved_link is not None` | Equivalent. `_stored_pair` returns both records or neither. A half pair raises first. Probe `test_missing_qa_and_half_a_pair_write_nothing`. | 0 |
| `notion_fact_ledger.py:169` | and | replace operand with False `saved_link is not None` | test_resume_of_pass_makes_no_second_write | 16 |
| `notion_fact_ledger.py:170` | and | replace operand with True `await _saved_holds(fixture, stored, validated, qa, saved_ledger, saved_link, ...` | test_blocked_ledger_replans_when_the_defect_is_gone | 23 |
| `notion_fact_ledger.py:170` | and | replace operand with False `await _saved_holds(fixture, stored, validated, qa, saved_ledger, saved_link, ...` | test_resume_of_pass_makes_no_second_write | 16 |
| `notion_fact_ledger.py:168` | and | flip and to or `boolop and` | test_blocked_ledger_replans_when_the_defect_is_gone | 23 |
| `notion_fact_ledger.py:216` | or | replace operand with True `type(value) is not dict` | test_resume_of_pass_makes_no_second_write | 38 |
| `notion_fact_ledger.py:216` | or | replace operand with False `type(value) is not dict` | test_wrong_record_shapes_refuse[ledger-number-fact ledger record is incomplete] | 1 |
| `notion_fact_ledger.py:216` | or | replace operand with True `not exact_keys(value, _LEDGER_KEYS)` | test_resume_of_pass_makes_no_second_write | 38 |
| `notion_fact_ledger.py:216` | or | replace operand with False `not exact_keys(value, _LEDGER_KEYS)` | test_extra_key_is_incomplete[ledger-fact ledger record is incomplete] | 1 |
| `notion_fact_ledger.py:216` | or | flip or to and `boolop or` | test_extra_key_is_incomplete[ledger-fact ledger record is incomplete] | 2 |
| `notion_fact_ledger.py:219` | or | replace operand with True `type(verdict) is not str` | test_resume_of_pass_makes_no_second_write | 46 |
| `notion_fact_ledger.py:219` | or | replace operand with False `type(verdict) is not str` | test_wrong_record_shapes_refuse[verdict-list-fact ledger verdict is unsupported] | 1 |
| `notion_fact_ledger.py:219` | or | replace operand with True `verdict not in _VERDICTS` | test_resume_of_pass_makes_no_second_write | 46 |
| `notion_fact_ledger.py:219` | or | replace operand with False `verdict not in _VERDICTS` | test_unsupported_verdict_writes_nothing | 1 |
| `notion_fact_ledger.py:219` | or | flip or to and `boolop or` | test_unsupported_verdict_writes_nothing | 2 |
| `notion_fact_ledger.py:233` | or | replace operand with True `type(value) is not dict` | test_resume_of_pass_makes_no_second_write | 27 |
| `notion_fact_ledger.py:233` | or | replace operand with False `type(value) is not dict` | test_wrong_record_shapes_refuse[link-number-workflow link record is incomplete] | 1 |
| `notion_fact_ledger.py:233` | or | replace operand with True `not exact_keys(value, _LINK_KEYS)` | test_resume_of_pass_makes_no_second_write | 27 |
| `notion_fact_ledger.py:233` | or | replace operand with False `not exact_keys(value, _LINK_KEYS)` | test_extra_key_is_incomplete[link-workflow link record is incomplete] | 1 |
| `notion_fact_ledger.py:233` | or | flip or to and `boolop or` | test_extra_key_is_incomplete[link-workflow link record is incomplete] | 2 |
| `notion_fact_ledger.py:236` | or | replace operand with True `type(verdict) is not str` | test_resume_of_pass_makes_no_second_write | 31 |
| `notion_fact_ledger.py:236` | or | replace operand with False `type(verdict) is not str` | test_wrong_record_shapes_refuse[link-verdict-list-workflow link verdict is unsupported] | 1 |
| `notion_fact_ledger.py:236` | or | replace operand with True `verdict not in _VERDICTS` | test_resume_of_pass_makes_no_second_write | 31 |
| `notion_fact_ledger.py:236` | or | replace operand with False `verdict not in _VERDICTS` | test_link_verdict_maybe_is_unsupported | 1 |
| `notion_fact_ledger.py:236` | or | flip or to and `boolop or` | test_link_verdict_maybe_is_unsupported | 2 |
| `notion_fact_ledger.py:239` | or | replace operand with True `type(ready) is not str` | test_resume_of_pass_makes_no_second_write | 25 |
| `notion_fact_ledger.py:239` | or | replace operand with False `type(ready) is not str` | test_wrong_record_shapes_refuse[ready-list-workflow link record is incomplete] | 1 |
| `notion_fact_ledger.py:239` | or | replace operand with True `ready not in {"", _READY_JOB}` | test_resume_of_pass_makes_no_second_write | 25 |
| `notion_fact_ledger.py:239` | or | replace operand with False `ready not in {"", _READY_JOB}` | test_ready_nope_is_incomplete | 1 |
| `notion_fact_ledger.py:239` | or | flip or to and `boolop or` | test_ready_nope_is_incomplete | 2 |
| `notion_fact_ledger.py:242` | or | replace operand with True `type(repair) is not str` | test_resume_of_pass_makes_no_second_write | 25 |
| `notion_fact_ledger.py:242` | or | replace operand with False `type(repair) is not str` | test_repair_required_list_is_incomplete | 1 |
| `notion_fact_ledger.py:242` | or | replace operand with True `repair not in {"true", "false"}` | test_resume_of_pass_makes_no_second_write | 25 |
| `notion_fact_ledger.py:242` | or | replace operand with False `repair not in {"true", "false"}` | test_wrong_record_shapes_refuse[repair-word-workflow link record is incomplete] | 1 |
| `notion_fact_ledger.py:242` | or | flip or to and `boolop or` | test_repair_required_list_is_incomplete | 2 |
| `notion_fact_ledger.py:245` | or | replace operand with True `type(steps) is not list` | test_resume_of_pass_makes_no_second_write | 25 |
| `notion_fact_ledger.py:245` | or | replace operand with False `type(steps) is not list` | test_wrong_record_shapes_refuse[steps-string-workflow link record is incomplete] | 1 |
| `notion_fact_ledger.py:245` | or | replace operand with True `not steps` | test_resume_of_pass_makes_no_second_write | 25 |
| `notion_fact_ledger.py:245` | or | replace operand with False `not steps` | test_empty_steps_are_incomplete | 1 |
| `notion_fact_ledger.py:245` | or | flip or to and `boolop or` | test_empty_steps_are_incomplete | 2 |
| `notion_fact_ledger.py:253` | or | replace operand with True `type(value) is not list` | test_resume_of_pass_makes_no_second_write | 36 |
| `notion_fact_ledger.py:253` | or | replace operand with False `type(value) is not list` | test_facts_json_number_is_incomplete | 1 |
| `notion_fact_ledger.py:253` | or | replace operand with True `not value` | test_resume_of_pass_makes_no_second_write | 36 |
| `notion_fact_ledger.py:253` | or | replace operand with False `not value` | Equivalent. An empty list still fails the name-tuple check with `fact ledger record is incomplete`. | 0 |
| `notion_fact_ledger.py:253` | or | flip or to and `boolop or` | test_facts_json_number_is_incomplete | 1 |
| `notion_fact_ledger.py:257` | or | replace operand with True `type(item) is not dict` | test_resume_of_pass_makes_no_second_write | 36 |
| `notion_fact_ledger.py:257` | or | replace operand with False `type(item) is not dict` | test_wrong_record_shapes_refuse[check-number-fact ledger record is incomplete] | 1 |
| `notion_fact_ledger.py:257` | or | replace operand with True `not exact_keys(item, frozenset({left, right}))` | test_resume_of_pass_makes_no_second_write | 36 |
| `notion_fact_ledger.py:257` | or | replace operand with False `not exact_keys(item, frozenset({left, right}))` | test_extra_key_is_incomplete[check-fact ledger record is incomplete] | 1 |
| `notion_fact_ledger.py:257` | or | flip or to and `boolop or` | test_extra_key_is_incomplete[check-fact ledger record is incomplete] | 2 |
| `notion_fact_ledger.py:261` | or | replace operand with True `type(label) is not str` | test_resume_of_pass_makes_no_second_write | 36 |
| `notion_fact_ledger.py:261` | or | replace operand with False `type(label) is not str` | test_wrong_record_shapes_refuse[check-label-number-fact ledger record is incomplete] | 1 |
| `notion_fact_ledger.py:261` | or | replace operand with True `type(stored) is not str` | test_resume_of_pass_makes_no_second_write | 36 |
| `notion_fact_ledger.py:261` | or | replace operand with False `type(stored) is not str` | test_check_flag_number_is_incomplete | 1 |
| `notion_fact_ledger.py:261` | or | flip or to and `boolop or` | test_check_flag_number_is_incomplete | 2 |
| `notion_fact_ledger.py:279` | and | replace operand with True `qa.verdict == "PASS"` | test_blocked_qa_records_blocked_and_holds_with_no_adapter_writes | 9 |
| `notion_fact_ledger.py:279` | and | replace operand with False `qa.verdict == "PASS"` | Equivalent. `load_qa_record` already raises `qa record does not match` for PASS plus a false check. Probe `test_pass_with_a_false_check_is_refused`. | 0 |
| `notion_fact_ledger.py:279` | and | replace operand with True `failed` | test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub] | 105 |
| `notion_fact_ledger.py:279` | and | replace operand with False `failed` | Equivalent. `load_qa_record` already raises `qa record does not match` for PASS plus a false check. Probe `test_pass_with_a_false_check_is_refused`. | 0 |
| `notion_fact_ledger.py:279` | and | flip and to or `boolop and` | test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub] | 113 |
| `notion_fact_ledger.py:281` | and | replace operand with True `qa.verdict != "PASS"` | test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub] | 73 |
| `notion_fact_ledger.py:281` | and | replace operand with False `qa.verdict != "PASS"` | test_blocked_qa_with_a_live_pass_writes_nothing | 4 |
| `notion_fact_ledger.py:281` | and | replace operand with True `live_pass` | test_blocked_qa_records_blocked_and_holds_with_no_adapter_writes | 9 |
| `notion_fact_ledger.py:281` | and | replace operand with False `live_pass` | test_blocked_qa_with_a_live_pass_writes_nothing | 4 |
| `notion_fact_ledger.py:281` | and | flip and to or `boolop and` | test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub] | 81 |
| `notion_fact_ledger.py:309` | or | replace operand with True `link.verdict != "BLOCKED"` | test_blocked_qa_records_blocked_and_holds_with_no_adapter_writes | 12 |
| `notion_fact_ledger.py:309` | or | replace operand with False `link.verdict != "BLOCKED"` | test_blocked_ledger_with_a_pass_link_refuses | 1 |
| `notion_fact_ledger.py:309` | or | replace operand with True `link.ready != ""` | test_blocked_qa_records_blocked_and_holds_with_no_adapter_writes | 12 |
| `notion_fact_ledger.py:309` | or | replace operand with False `link.ready != ""` | test_blocked_link_ready_job_refuses | 1 |
| `notion_fact_ledger.py:309` | or | flip or to and `boolop or` | test_blocked_ledger_with_a_pass_link_refuses | 2 |
| `notion_fact_ledger.py:311` | or | replace operand with True `link.steps != plan.steps` | test_blocked_qa_records_blocked_and_holds_with_no_adapter_writes | 12 |
| `notion_fact_ledger.py:311` | or | replace operand with False `link.steps != plan.steps` | test_blocked_forged_step_refuses | 1 |
| `notion_fact_ledger.py:311` | or | replace operand with True `link.repair_required != plan.repair_required` | test_blocked_qa_records_blocked_and_holds_with_no_adapter_writes | 12 |
| `notion_fact_ledger.py:311` | or | replace operand with False `link.repair_required != plan.repair_required` | test_blocked_ledger_with_forged_repair_required_refuses | 1 |
| `notion_fact_ledger.py:311` | or | flip or to and `boolop or` | test_blocked_ledger_with_forged_repair_required_refuses | 2 |
| `notion_fact_ledger.py:313` | or | replace operand with True `saved.facts != plan.facts` | test_blocked_qa_records_blocked_and_holds_with_no_adapter_writes | 1 |
| `notion_fact_ledger.py:313` | or | replace operand with False `saved.facts != plan.facts` | test_forged_blocked_fact_does_not_match_and_writes_nothing | 2 |
| `notion_fact_ledger.py:313` | or | replace operand with True `saved.checks != plan.checks` | test_blocked_qa_records_blocked_and_holds_with_no_adapter_writes | 1 |
| `notion_fact_ledger.py:313` | or | replace operand with False `saved.checks != plan.checks` | test_blocked_ledger_replans_when_the_defect_is_gone | 1 |
| `notion_fact_ledger.py:313` | or | flip or to and `boolop or` | test_blocked_ledger_replans_when_the_defect_is_gone | 3 |
| `notion_fact_ledger.py:318` | or | replace operand with True `saved.facts != plan.facts` | test_resume_of_pass_makes_no_second_write | 5 |
| `notion_fact_ledger.py:318` | or | replace operand with False `saved.facts != plan.facts` | test_forged_fact_does_not_match_and_writes_nothing | 1 |
| `notion_fact_ledger.py:318` | or | replace operand with True `saved.checks != plan.checks` | test_resume_of_pass_makes_no_second_write | 5 |
| `notion_fact_ledger.py:318` | or | replace operand with False `saved.checks != plan.checks` | Equivalent. A PASS whose checks disagree raises in `_verdict_agrees` before this compare. | 0 |
| `notion_fact_ledger.py:318` | or | flip or to and `boolop or` | test_forged_fact_does_not_match_and_writes_nothing | 1 |
| `notion_fact_ledger.py:323` | or | replace operand with True `link.verdict != "PASS"` | test_resume_of_pass_makes_no_second_write | 1 |
| `notion_fact_ledger.py:323` | or | replace operand with False `link.verdict != "PASS"` | test_forged_link_verdict_on_a_pass_refuses | 1 |
| `notion_fact_ledger.py:323` | or | replace operand with True `link.ready != plan.ready` | test_resume_of_pass_makes_no_second_write | 1 |
| `notion_fact_ledger.py:323` | or | replace operand with False `link.ready != plan.ready` | test_forged_ready_on_a_pass_refuses | 1 |
| `notion_fact_ledger.py:323` | or | replace operand with True `link.steps != plan.steps` | test_resume_of_pass_makes_no_second_write | 1 |
| `notion_fact_ledger.py:323` | or | replace operand with False `link.steps != plan.steps` | test_forged_step_does_not_match_and_writes_nothing | 1 |
| `notion_fact_ledger.py:323` | or | flip or to and `boolop or` | test_forged_ready_on_a_pass_refuses | 2 |
| `notion_fact_ledger.py:363` | and | replace operand with True `qa.verdict == "PASS"` | Equivalent. A loaded PASS already has every check true. A non-PASS live success raises before a write. Probe `test_blocked_qa_with_a_live_pass_writes_nothing`. | 0 |
| `notion_fact_ledger.py:363` | and | replace operand with False `qa.verdict == "PASS"` | test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub] | 33 |
| `notion_fact_ledger.py:363` | and | replace operand with True `all(passed is True for _name, passed in qa.checks)` | Equivalent. A loaded PASS already has every check true. Probe `test_pass_with_a_false_check_is_refused`. | 0 |
| `notion_fact_ledger.py:363` | and | replace operand with False `all(passed is True for _name, passed in qa.checks)` | test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub] | 33 |
| `notion_fact_ledger.py:363` | and | flip and to or `boolop and` | Equivalent. The two conjuncts agree on every loaded QA record that reaches a write. | 0 |
| `notion_fact_ledger.py:365` | and | replace operand with True `stored_pass` | Equivalent. A write happens only when `stored_pass` equals `qa_live`. A live pass on a non-PASS verdict raises first. Probe `test_blocked_qa_with_a_live_pass_writes_nothing`. | 0 |
| `notion_fact_ledger.py:365` | and | replace operand with False `stored_pass` | test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub] | 33 |
| `notion_fact_ledger.py:365` | and | replace operand with True `qa_live` | test_live_state_qa_rejects_is_not_a_pass[unpublished] | 12 |
| `notion_fact_ledger.py:365` | and | replace operand with False `qa_live` | test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub] | 33 |
| `notion_fact_ledger.py:365` | and | flip and to or `boolop and` | test_live_state_qa_rejects_is_not_a_pass[unpublished] | 12 |
| `notion_fact_ledger.py:377` | or | replace operand with True `type(value) is not str` | test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub] | 117 |
| `notion_fact_ledger.py:377` | or | replace operand with False `type(value) is not str` | Equivalent. Every fact value is built with `str` or `join`. The strip conjunct is the live one. | 0 |
| `notion_fact_ledger.py:377` | or | replace operand with True `value == ""` | test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub] | 117 |
| `notion_fact_ledger.py:377` | or | replace operand with False `value == ""` | Equivalent. Loaded joins are non-empty (`missing`, a count, or a token list). Edge whitespace still raises. | 0 |
| `notion_fact_ledger.py:377` | or | replace operand with True `value.strip() != value` | test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub] | 117 |
| `notion_fact_ledger.py:377` | or | replace operand with False `value.strip() != value` | test_edge_whitespace_is_refused_before_persist[leading-url] | 2 |
| `notion_fact_ledger.py:377` | or | flip or to and `boolop or` | Equivalent. `and` binds tighter, and the only reachable failure is `strip`. Probe `test_edge_whitespace_is_refused_before_persist` still raises. | 0 |
| `notion_fact_ledger.py:402` | and | replace operand with True `type(home_title) is str` | test_home_title_integer_keeps_live_qa | 1 |
| `notion_fact_ledger.py:402` | and | replace operand with False `type(home_title) is str` | test_renamed_home_title_fails_live_qa | 1 |
| `notion_fact_ledger.py:402` | and | replace operand with True `home_title != ""` | test_blank_home_title_keeps_live_qa | 1 |
| `notion_fact_ledger.py:402` | and | replace operand with False `home_title != ""` | test_renamed_home_title_fails_live_qa | 1 |
| `notion_fact_ledger.py:402` | and | flip and to or `boolop and` | test_blank_home_title_keeps_live_qa | 2 |
| `notion_fact_ledger.py:403` | or | replace operand with True `_row_identity(probe, stored)` | test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub] | 37 |
| `notion_fact_ledger.py:403` | or | replace operand with False `_row_identity(probe, stored)` | test_caller_spec_fields_are_not_the_facts | 1 |
| `notion_fact_ledger.py:403` | or | replace operand with True `spec.identity` | Equivalent. A loaded row title is the identity. A title that does not parse raises in the dashboard check before a write. | 0 |
| `notion_fact_ledger.py:403` | or | replace operand with False `spec.identity` | Equivalent. A loaded row title is the identity. A title that does not parse raises in the dashboard check before a write. | 0 |
| `notion_fact_ledger.py:403` | or | flip or to and `boolop or` | test_caller_spec_fields_are_not_the_facts | 1 |
| `notion_fact_ledger.py:404` | or | replace operand with True `_role_detail(probe, stored, identity, "buyer")` | test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub] | 37 |
| `notion_fact_ledger.py:404` | or | replace operand with False `_role_detail(probe, stored, identity, "buyer")` | test_caller_spec_fields_are_not_the_facts | 1 |
| `notion_fact_ledger.py:404` | or | replace operand with True `spec.buyer_problem` | Equivalent. The stored section detail is the buyer text on a checkpoint that returns. Caller text is not the fact. Probe `test_caller_spec_fields_are_not_the_facts`. | 0 |
| `notion_fact_ledger.py:404` | or | replace operand with False `spec.buyer_problem` | Equivalent. The stored section detail is the buyer text on a checkpoint that returns. Caller text is not the fact. Probe `test_caller_spec_fields_are_not_the_facts`. | 0 |
| `notion_fact_ledger.py:404` | or | flip or to and `boolop or` | test_caller_spec_fields_are_not_the_facts | 1 |
| `notion_fact_ledger.py:405` | or | replace operand with True `_role_detail(probe, stored, identity, "practice")` | test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub] | 37 |
| `notion_fact_ledger.py:405` | or | replace operand with False `_role_detail(probe, stored, identity, "practice")` | test_caller_spec_fields_are_not_the_facts | 1 |
| `notion_fact_ledger.py:405` | or | replace operand with True `spec.flagship_feature` | Equivalent. The stored section detail is the flagship text on a checkpoint that returns. Probe `test_caller_spec_fields_are_not_the_facts`. | 0 |
| `notion_fact_ledger.py:405` | or | replace operand with False `spec.flagship_feature` | Equivalent. The stored section detail is the flagship text on a checkpoint that returns. Probe `test_caller_spec_fields_are_not_the_facts`. | 0 |
| `notion_fact_ledger.py:405` | or | flip or to and `boolop or` | test_caller_spec_fields_are_not_the_facts | 1 |
| `notion_fact_ledger.py:407` | and | replace operand with True `set(kinds) == set(PLANNER_SHARED_DATABASES)` | test_qa_pass_persists_one_ledger_and_one_link[business-Studio Ledger-Studio Home-Desk] | 1 |
| `notion_fact_ledger.py:407` | and | replace operand with False `set(kinds) == set(PLANNER_SHARED_DATABASES)` | test_caller_spec_fields_are_not_the_facts | 1 |
| `notion_fact_ledger.py:407` | and | replace operand with True `len(kinds) == len(PLANNER_SHARED_DATABASES)` | Equivalent. Stored kinds are unique, so set equality has the same length. | 0 |
| `notion_fact_ledger.py:407` | and | replace operand with False `len(kinds) == len(PLANNER_SHARED_DATABASES)` | test_caller_spec_fields_are_not_the_facts | 1 |
| `notion_fact_ledger.py:407` | and | flip and to or `boolop and` | test_qa_pass_persists_one_ledger_and_one_link[business-Studio Ledger-Studio Home-Desk] | 1 |
| `notion_fact_ledger.py:409` | and | replace operand with True `set(kinds) == set(BUSINESS_SHARED_DATABASES)` | Equivalent. A mass checkpoint takes the planner branch. A business checkpoint already matches this set, and `spec.tier` is `business`. Probe the business pass. | 0 |
| `notion_fact_ledger.py:409` | and | replace operand with False `set(kinds) == set(BUSINESS_SHARED_DATABASES)` | Equivalent. Falling through uses `spec.tier`, which is `business` on that checkpoint. Probe the business pass. | 0 |
| `notion_fact_ledger.py:409` | and | replace operand with True `len(kinds) == len( BUSINESS_SHARED_DATABASES )` | Equivalent. The business set match already implies this length. Probe the business pass. | 0 |
| `notion_fact_ledger.py:409` | and | replace operand with False `len(kinds) == len( BUSINESS_SHARED_DATABASES )` | Equivalent. Falling through uses `spec.tier`, which is `business` on that checkpoint. Probe the business pass. | 0 |
| `notion_fact_ledger.py:409` | and | flip and to or `boolop and` | Equivalent. Both sides are true together on a business checkpoint, and a mass checkpoint never reaches this branch. | 0 |
| `notion_fact_ledger.py:437` | or | replace operand with True `type(page) is not NotionPage` | test_caller_spec_fields_are_not_the_facts | 1 |
| `notion_fact_ledger.py:437` | or | replace operand with False `type(page) is not NotionPage` | Equivalent. `_require_pages` already rejected a subclass. Probe `test_page_subclass_is_not_accepted`. | 0 |
| `notion_fact_ledger.py:438` | or | replace operand with True `type(page.title) is not str` | test_caller_spec_fields_are_not_the_facts | 1 |
| `notion_fact_ledger.py:438` | or | replace operand with False `type(page.title) is not str` | test_blank_dashboard_row_title_refuses[None] | 1 |
| `notion_fact_ledger.py:439` | or | replace operand with True `page.title.strip() != page.title` | test_caller_spec_fields_are_not_the_facts | 1 |
| `notion_fact_ledger.py:439` | or | replace operand with False `page.title.strip() != page.title` | Equivalent. A padded row raises in `_dashboard_outputs` before a write. Probe `test_edge_whitespace_is_refused_before_persist`. | 0 |
| `notion_fact_ledger.py:437` | or | flip or to and `boolop or` | test_blank_dashboard_row_title_refuses[None] | 1 |
| `notion_fact_ledger.py:468` | or | replace operand with True `type(sections) is not tuple` | test_caller_spec_fields_are_not_the_facts | 1 |
| `notion_fact_ledger.py:468` | or | replace operand with False `type(sections) is not tuple` | Equivalent. Loaded hub sections are tuples. A bad shape never arrives from the checkpoint loader. | 0 |
| `notion_fact_ledger.py:468` | or | replace operand with True `type(name) is not str` | test_caller_spec_fields_are_not_the_facts | 1 |
| `notion_fact_ledger.py:468` | or | replace operand with False `type(name) is not str` | Equivalent. Loaded hub names are strings. | 0 |
| `notion_fact_ledger.py:468` | or | flip or to and `boolop or` | Equivalent. Both type checks are true together on a loaded hub. | 0 |
| `notion_fact_ledger.py:471` | or | replace operand with True `type(item) is not tuple` | test_caller_spec_fields_are_not_the_facts | 1 |
| `notion_fact_ledger.py:471` | or | replace operand with False `type(item) is not tuple` | Equivalent. Loaded section rows are pairs. Probe `test_caller_spec_fields_are_not_the_facts`. | 0 |
| `notion_fact_ledger.py:471` | or | replace operand with True `len(item) != 2` | test_caller_spec_fields_are_not_the_facts | 1 |
| `notion_fact_ledger.py:471` | or | replace operand with False `len(item) != 2` | Equivalent. Loaded section rows are pairs. | 0 |
| `notion_fact_ledger.py:471` | or | replace operand with True `item[0] != role` | test_caller_spec_fields_are_not_the_facts | 1 |
| `notion_fact_ledger.py:471` | or | replace operand with False `item[0] != role` | Equivalent. The role loop still skips other roles, and a missing role returns empty before a caller fallback is persisted as a fact. | 0 |
| `notion_fact_ledger.py:471` | or | flip or to and `boolop or` | Equivalent. The three checks are false together on a loaded pair for the requested role. | 0 |
| `notion_fact_ledger.py:474` | or | replace operand with True `type(block) is not NotionTextBlock` | test_caller_spec_fields_are_not_the_facts | 1 |
| `notion_fact_ledger.py:474` | or | replace operand with False `type(block) is not NotionTextBlock` | Equivalent. The purpose block on a loaded hub is a text block. | 0 |
| `notion_fact_ledger.py:474` | or | replace operand with True `type(block.content) is not str` | test_caller_spec_fields_are_not_the_facts | 1 |
| `notion_fact_ledger.py:474` | or | replace operand with False `type(block.content) is not str` | Equivalent. Loaded text-block content is a string. | 0 |
| `notion_fact_ledger.py:474` | or | flip or to and `boolop or` | Equivalent. Both type checks are true together on a loaded text block. | 0 |
| `notion_fact_ledger.py:477` | and | replace operand with True `block.content.startswith(prefix)` | Equivalent. A matching block still returns the same slice. Section detail is not itself a ledger fact. | 0 |
| `notion_fact_ledger.py:477` | and | replace operand with False `block.content.startswith(prefix)` | test_caller_spec_fields_are_not_the_facts | 1 |
| `notion_fact_ledger.py:477` | and | replace operand with True `len(block.content) > len(prefix)` | Equivalent. A matching stored section is longer than the prefix. Probe `test_caller_spec_fields_are_not_the_facts`. | 0 |
| `notion_fact_ledger.py:477` | and | replace operand with False `len(block.content) > len(prefix)` | test_caller_spec_fields_are_not_the_facts | 1 |
| `notion_fact_ledger.py:477` | and | flip and to or `boolop and` | Equivalent. Both sides are true on a matching stored section. | 0 |
| `notion_fact_ledger.py:491` | or | replace operand with True `description == ""` | test_caller_spec_fields_are_not_the_facts | 1 |
| `notion_fact_ledger.py:491` | or | replace operand with False `description == ""` | test_dashboard_delimiter_is_not_a_fact | 1 |
| `notion_fact_ledger.py:491` | or | replace operand with True `len(hub.name) > 64` | test_caller_spec_fields_are_not_the_facts | 1 |
| `notion_fact_ledger.py:491` | or | replace operand with False `len(hub.name) > 64` | Equivalent. A loaded hub name fits `Hub.name` max length 64. The description bound is the killed conjunct. | 0 |
| `notion_fact_ledger.py:491` | or | replace operand with True `len(description) > 500` | test_caller_spec_fields_are_not_the_facts | 1 |
| `notion_fact_ledger.py:491` | or | replace operand with False `len(description) > 500` | test_oversized_hub_description_is_not_adopted | 1 |
| `notion_fact_ledger.py:491` | or | flip or to and `boolop or` | test_dashboard_delimiter_is_not_a_fact | 1 |
| `notion_fact_ledger.py:494` | or | replace operand with True `len(rows) < 6` | test_caller_spec_fields_are_not_the_facts | 1 |
| `notion_fact_ledger.py:494` | or | replace operand with False `len(rows) < 6` | Equivalent. A loaded checkpoint has 6 to 8 hubs, so this bound is false. | 0 |
| `notion_fact_ledger.py:494` | or | replace operand with True `len(rows) > 8` | test_caller_spec_fields_are_not_the_facts | 1 |
| `notion_fact_ledger.py:494` | or | replace operand with False `len(rows) > 8` | Equivalent. A loaded checkpoint has 6 to 8 hubs, so this bound is false. | 0 |
| `notion_fact_ledger.py:494` | or | flip or to and `boolop or` | Equivalent. Both bounds are false on a loaded checkpoint, and `and` stays false. | 0 |
| `notion_fact_ledger.py:522` | or | replace operand with True `type(page.title) is not str` | test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub] | 33 |
| `notion_fact_ledger.py:522` | or | replace operand with False `type(page.title) is not str` | test_hub_title_that_is_not_text_is_blocked | 2 |
| `notion_fact_ledger.py:522` | or | replace operand with True `page.title == ""` | test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub] | 33 |
| `notion_fact_ledger.py:522` | or | replace operand with False `page.title == ""` | Equivalent. An empty title is a str and both versions return `""`. Probe `test_blank_dashboard_row_title_refuses`. | 0 |
| `notion_fact_ledger.py:522` | or | flip or to and `boolop or` | test_hub_title_that_is_not_text_is_blocked | 2 |
| `notion_fact_ledger.py:540` | and | replace operand with True `type(name) is str` | Equivalent. Titles are already strings or the word `missing`. | 0 |
| `notion_fact_ledger.py:540` | and | replace operand with False `type(name) is str` | test_trailing_space_in_a_hub_title_can_be_repaired | 1 |
| `notion_fact_ledger.py:540` | and | replace operand with True `name == "" or name.strip() != name` | test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub] | 33 |
| `notion_fact_ledger.py:540` | and | replace operand with False `name == "" or name.strip() != name` | test_trailing_space_in_a_hub_title_can_be_repaired | 1 |
| `notion_fact_ledger.py:540` | and | flip and to or `boolop and` | test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub] | 33 |
| `notion_fact_ledger.py:540` | or | replace operand with True `name == ""` | test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub] | 33 |
| `notion_fact_ledger.py:540` | or | replace operand with False `name == ""` | Equivalent. An empty title is replaced with `missing` before this `or`. Probe `test_blank_hub_title_is_missing`. | 0 |
| `notion_fact_ledger.py:540` | or | replace operand with True `name.strip() != name` | test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub] | 33 |
| `notion_fact_ledger.py:540` | or | replace operand with False `name.strip() != name` | test_trailing_space_in_a_hub_title_can_be_repaired | 1 |
| `notion_fact_ledger.py:540` | or | flip or to and `boolop or` | test_trailing_space_in_a_hub_title_can_be_repaired | 1 |
| `notion_fact_ledger.py:566` | or | replace operand with True `not isinstance(database, NotionDatabase)` | test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub] | 119 |
| `notion_fact_ledger.py:566` | or | replace operand with False `not isinstance(database, NotionDatabase)` | test_missing_database_writes_nothing | 1 |
| `notion_fact_ledger.py:566` | or | replace operand with True `database.parent_id != stored.page_id` | test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub] | 119 |
| `notion_fact_ledger.py:566` | or | replace operand with False `database.parent_id != stored.page_id` | test_database_parent_other_than_home_writes_nothing | 1 |
| `notion_fact_ledger.py:566` | or | flip or to and `boolop or` | test_database_parent_other_than_home_writes_nothing | 2 |
| `notion_fact_ledger.py:569` | and | replace operand with True `type(database.title) is str` | test_database_title_integer_is_missing | 1 |
| `notion_fact_ledger.py:569` | and | replace operand with False `type(database.title) is str` | test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub] | 31 |
| `notion_fact_ledger.py:569` | and | replace operand with True `database.title != ""` | test_blank_database_title_is_missing_and_blocked | 1 |
| `notion_fact_ledger.py:569` | and | replace operand with False `database.title != ""` | test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub] | 31 |
| `notion_fact_ledger.py:569` | and | flip and to or `boolop and` | test_blank_database_title_is_missing_and_blocked | 2 |
| `notion_fact_ledger.py:571` | and | replace operand with True `type(title) is str` | Equivalent. The title was already narrowed to str or replaced with `missing`. Probe `test_database_title_integer_is_missing`. | 0 |
| `notion_fact_ledger.py:571` | and | replace operand with False `type(title) is str` | test_database_title_with_edge_space_is_missing | 1 |
| `notion_fact_ledger.py:571` | and | replace operand with True `title.strip() != title` | test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub] | 31 |
| `notion_fact_ledger.py:571` | and | replace operand with False `title.strip() != title` | test_database_title_with_edge_space_is_missing | 1 |
| `notion_fact_ledger.py:571` | and | flip and to or `boolop and` | test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub] | 31 |
| `notion_fact_ledger.py:592` | and | replace operand with True `type(captured) is str` | test_empty_or_missing_public_url_blocks_secret_links[None] | 3 |
| `notion_fact_ledger.py:592` | and | replace operand with False `type(captured) is str` | test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub] | 33 |
| `notion_fact_ledger.py:592` | and | replace operand with True `captured != ""` | test_empty_or_missing_public_url_blocks_secret_links[] | 1 |
| `notion_fact_ledger.py:592` | and | replace operand with False `captured != ""` | test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub] | 33 |
| `notion_fact_ledger.py:592` | and | flip and to or `boolop and` | test_empty_or_missing_public_url_blocks_secret_links[] | 4 |
| `notion_fact_ledger.py:594` | and | replace operand with True `page.is_published is True` | test_unpublished_trusted_url_blocks_secret_links | 1 |
| `notion_fact_ledger.py:594` | and | replace operand with False `page.is_published is True` | test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub] | 31 |
| `notion_fact_ledger.py:595` | and | replace operand with True `usable` | test_captured_url_must_be_exact_str[subclass] | 2 |
| `notion_fact_ledger.py:595` | and | replace operand with False `usable` | test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub] | 31 |
| `notion_fact_ledger.py:596` | and | replace operand with True `captured == trusted` | test_forged_captured_url_blocks_secret_links | 4 |
| `notion_fact_ledger.py:596` | and | replace operand with False `captured == trusted` | test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub] | 31 |
| `notion_fact_ledger.py:597` | and | replace operand with True `record.secret_link == trusted` | test_forged_stored_secret_link_blocks | 1 |
| `notion_fact_ledger.py:597` | and | replace operand with False `record.secret_link == trusted` | test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub] | 31 |
| `notion_fact_ledger.py:594` | and | flip and to or `boolop and` | test_forged_captured_url_blocks_secret_links | 10 |
| `notion_fact_ledger.py:612` | or | replace operand with True `type(value) is not str` | test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub] | 32 |
| `notion_fact_ledger.py:612` | or | replace operand with False `type(value) is not str` | Equivalent. `_page_title` returns a str. Empty and padded titles are the killed conjuncts. Probe `test_blank_sample_title_is_missing`. | 0 |
| `notion_fact_ledger.py:612` | or | replace operand with True `value == ""` | test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub] | 32 |
| `notion_fact_ledger.py:612` | or | replace operand with False `value == ""` | test_blank_sample_title_is_missing | 1 |
| `notion_fact_ledger.py:612` | or | replace operand with True `value.strip() != value` | test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub] | 32 |
| `notion_fact_ledger.py:612` | or | replace operand with False `value.strip() != value` | test_padded_sample_title_recovers_after_the_trim[SAMPLE Tasks ] | 3 |
| `notion_fact_ledger.py:612` | or | flip or to and `boolop or` | test_blank_sample_title_is_missing | 1 |
| `notion_fact_ledger.py:616` | or | replace operand with True `"\u200b" in value` | test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub] | 32 |
| `notion_fact_ledger.py:616` | or | replace operand with False `"\u200b" in value` | test_invisible_sample_mark_is_missing[\u200b] | 1 |
| `notion_fact_ledger.py:616` | or | replace operand with True `"\ufeff" in value` | test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub] | 32 |
| `notion_fact_ledger.py:616` | or | replace operand with False `"\ufeff" in value` | test_invisible_sample_mark_is_missing[\ufeff] | 1 |
| `notion_fact_ledger.py:616` | or | flip or to and `boolop or` | test_invisible_sample_mark_is_missing[\u200b] | 2 |
| `notion_fact_ledger.py:633` | or | replace operand with True `expression is None` | test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub] | 32 |
| `notion_fact_ledger.py:633` | or | replace operand with False `expression is None` | Equivalent. `None != wanted[1]` still returns missing. Probe `test_blank_formula_expression_is_missing`. | 0 |
| `notion_fact_ledger.py:633` | or | replace operand with True `wanted is None` | test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub] | 32 |
| `notion_fact_ledger.py:633` | or | replace operand with False `wanted is None` | test_unknown_formula_name_is_missing | 1 |
| `notion_fact_ledger.py:633` | or | replace operand with True `wanted[0] != kind` | test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub] | 32 |
| `notion_fact_ledger.py:633` | or | replace operand with False `wanted[0] != kind` | test_formula_recorded_on_the_wrong_database_is_missing | 1 |
| `notion_fact_ledger.py:633` | or | replace operand with True `expression != wanted[1]` | test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub] | 32 |
| `notion_fact_ledger.py:633` | or | replace operand with False `expression != wanted[1]` | test_one_fixed_defect_replans_the_other | 2 |
| `notion_fact_ledger.py:633` | or | flip or to and `boolop or` | test_unknown_formula_name_is_missing | 1 |
| `notion_fact_ledger.py:635` | or | replace operand with True `";" in name` | test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub] | 32 |
| `notion_fact_ledger.py:635` | or | replace operand with False `";" in name` | Equivalent. A formula name from the checkpoint has no semicolon, and a changed expression already fails equality. | 0 |
| `notion_fact_ledger.py:635` | or | replace operand with True `";" in expression` | test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub] | 32 |
| `notion_fact_ledger.py:635` | or | replace operand with False `";" in expression` | Equivalent. An expression that contains `;` already fails `expression != wanted[1]` first. Probe `test_semicolon_in_a_formula_expression_is_missing`. | 0 |
| `notion_fact_ledger.py:635` | or | flip or to and `boolop or` | Equivalent. Generated names and matching expressions do not contain `;`, so both sides are false together. | 0 |
| `notion_fact_ledger.py:668` | or | replace operand with True `prop.id != property_id` | test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub] | 32 |
| `notion_fact_ledger.py:668` | or | replace operand with False `prop.id != property_id` | test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub] | 32 |
| `notion_fact_ledger.py:668` | or | replace operand with True `prop.type != "formula"` | test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub] | 32 |
| `notion_fact_ledger.py:668` | or | replace operand with False `prop.type != "formula"` | test_text_property_is_not_a_dashboard_formula | 1 |
| `notion_fact_ledger.py:668` | or | flip or to and `boolop or` | test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub] | 33 |
| `notion_fact_ledger.py:671` | or | replace operand with True `type(formula) is not NotionFormula` | test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub] | 32 |
| `notion_fact_ledger.py:671` | or | replace operand with False `type(formula) is not NotionFormula` | test_non_formula_config_is_missing | 1 |
| `notion_fact_ledger.py:671` | or | replace operand with True `formula.expression == ""` | test_qa_pass_persists_one_ledger_and_one_link[mass-Weekly Planner-Home Dashboard Planner-Hub] | 32 |
| `notion_fact_ledger.py:671` | or | replace operand with False `formula.expression == ""` | Equivalent. `"" != wanted[1]` still returns missing. Probe `test_blank_formula_expression_is_missing`. | 0 |
| `notion_fact_ledger.py:671` | or | flip or to and `boolop or` | test_non_formula_config_is_missing | 1 |

Parked for the W11 test matrix, not fixed here: QA still records PASS when the home nav text, the 3 palette callouts, the identity callout, the 6 hub "returns to Home" texts, or the 3 home linked views are deleted. Uncovered code is `_linked_views` (`notion_qa.py:368`), `_palette` (`:603`), and `_teardown` (`:634`). The pull request lists the `docs/control` edits.

## 2026-10-07 — Session 07 W9: product QA

Session 07 stays incomplete. This wave is not SESSION_07 COMPLETE. State revision stays 57. `current_session` stays 7. `completed_sessions` stays `[0, 1, 2, 3, 4, 5, 6]`. `next_session` stays 7. `next_prompt` stays `10_SESSION_07_PRODUCT_BUILD_VARIANTS_AND_QA.md`. STATE `head_sha` `6b087370eaaf1a5e09d9868643cca7b3654ddc4a` is the intentional tip-sync to the W8 squash. It is not `9bc56b2c`. It is not the revision that produced the test or mutation figures below. Those figures were measured on this commit, the child of `1a18b932987f709e66a5a158171c0a4505e39ef7`. Commit `1a18b93` CI verify run is `37682862874`, job `113003102755`, SUCCESS. Commit `8cf3e2b` CI verify run is `37641427600`, job `112861113785`, SUCCESS. Commit `548ed86d` CI verify run is `37626840209`, job `112810680638`, SUCCESS. Commit `ef7366e0` CI verify run is `37614528839`, job `112769557533`, SUCCESS. This commit's CI run is not invented here. `evidence_closure_commit_sha` stays the Session 06 closure tip `0f94d585f23d79e5ac18479f01e14f67cbaad332`. `last_verified_commit` stays bootstrap `1abf0d7cca3a6b8cd7efcd0a45523538fd5bfd9d`. `updated_at` is `2026-10-07T21:59:24Z`.

Twelve session 7 evidence keys stay false, including `product_qa_implemented` and `variant_builder_implemented`. No session exit code is recorded. A07, A08, and A09 stay DESIGNED. `commissioned_agents` stays empty. Exit 78 scheduler stays HELD. Narrative `next_phase` is `fact_ledger` and it is not started. There is no top-level `next_phase` field. Section 9 and the workflow link are not this wave.

Fixture QA lives in `notion_qa.py`. `run_product_qa` (`notion_qa.py:101`) loads the variants checkpoint through `load_variant_checkpoint` (`:113`). `require_same_spec` is `:114`. A missing variants list, or a loader phase other than `qa`, raises at `:115` before any adapter write and does not append a repair job. The plan (`_plan` at `:245`, call at `:121`) runs before any adapter write. `_public_links` (`:509`) checks each variant against the fixture shape, published or not. The host is `_FIXTURE_LINK_HOST` at `:497` (`fixture.notion.site`). `_trusted_secret_link` (`:500`) builds `"https" + "://" + host + "/" + page_id`. `_is_trusted_link` (`:505`) requires that exact string. The stored secret link is `:514`. Stranger access must be `True` (`:516-518`). A published live URL from `get_public_url` is `:521`. A non-empty unpublished captured URL is `:525`. Empty or missing `public_url` is skipped, so a real `unpublish_page` can still repair. None of those checks compares a link with the captured value. A stored link and a captured URL that are the same forgery record `BLOCKED` with 0 adapter writes and `repair_jobs` `[]` (`test_matching_forged_unpublished_url_does_not_publish`). The cases are `https://evil.notion.site/{id}`, `https://fixture.notion.site/x/{id}`, `https://user:pw@fixture.notion.site/{id}`, `https://fixture.notion.site@evil.notion.site/{id}`, a query `?x=1`, and a fragment `#frag`. `test_unpublished_captured_url_must_match_the_fixture_shape` keeps the stored link trusted and forges only `public_url`, including those four shapes plus `http://fixture.notion.site/{id}`. Each one records `BLOCKED` with 0 writes and `repair_jobs` `[]`. `_is_trusted_link` was not changed. Exact equality already refuses userinfo, the credential-host trick, a query, a fragment, and `http`. No scheme, host, or path parser was added. Repairable defects are only an unpublished variant, `duplicate_as_template` off, and search indexing on (`:266-268`). Those use `publish_page`, `set_duplicate_as_template`, and `set_search_indexing` inside `_apply_repairs` (`:738`, call at `:124`), then the plan runs again (`:126`). A clean rerun records `PASS` with the repairs tuple. A repair that does not change the flag records `BLOCKED` (`:127-129`) and does not call `duplicate_page`. Structural defects record `BLOCKED` with zero adapter writes. A passing run calls `duplicate_page` once (`_prove_duplicate` at `:754`, call at `:763`) on the first variant. The proof title is `{spec.title} / {first colour} (Copy)`. Resume adopts that page and does not duplicate again. `guard_operation(probe, OP_QA)` runs before repairs (`:743`) and before `duplicate_page` (`:762`). `OP_QA` is `qa.duplicate` (`notion_progress.py:48`). A `ProviderFailure` from the plan read or the proof duplicate uses `raise_recorded` (`notion_qa.py:137`) with phase `BUILD_PHASES[-1]`. QA is not a seventh checkpoint name. `write_checkpoint` (`notion_qa.py:807`) stays the single progress writer. `get_public_url` (`:520`) and `verify_stranger_access` (`:516`) are reads. They are not in `_WRITE_METHODS` (`tests/unit/agents/test_notion_product_builder_variants.py:172`). The module does not contain a contiguous `https://` or `http://`, nor `httpx`, `requests`, `notion_client`, `APINotionAdapter`, `etsy`, `socket`, `urllib`, or `playwright`. `test_qa_does_not_open_a_socket` patches `socket.socket.connect`, `socket.socket.connect_ex`, and `socket.create_connection`. It does not patch `sendto` or `getaddrinfo`. It is a tripwire, not a claim that the process cannot open a socket.

After `unpublish_page`, `public_url` is `None`. `_accounted_facts` (`:633`) uses the live URL only when `public_url` is a non-empty string. Otherwise it uses the stored secret link (`:651`). `_facts` (`:680`) still reads that stored link, so the two sides agree and `published` is the only repair. `test_unpublish_page_is_repaired_then_passes` records `PASS`, repairs `("published",)`, and calls `["publish_page", "duplicate_page"]`. `test_unpublish_publish_crash_then_resume_passes` raises once inside `publish_page`, leaves the page unpublished and the qa key absent, then resumes to `PASS` with a proof. `test_unpublish_checkpoint_crash_after_repair_resumes_to_pass` publishes, duplicates, then raises inside `write_checkpoint`. Resume records `PASS` with the existing proof and adapter `calls == []`.

Facts are a snapshot on `provider_object_references["qa"]`. Secret links are normalised by `_normalised_secret_link` (`:668`), which strips a trailing `/{page_id}`. `_facts_persisted` is defined at `:625` and returns at `:631`. The return compares `dict(_facts(...))` with `_accounted_facts`. On `548ed86d` that return was `:618` and the definition started at `:612`. `test_secret_link_facts_match_across_fresh_runs` pins the whole normalised record: verdict `PASS`, equal checks, repairs `()`, and equal facts. The two proof page ids are non-empty and unequal. Saved QA (`_saved_holds` at `:217`) replans. A stored `BLOCKED` with the cause still present keeps the record and makes 0 writes (`:226-233`). A stored `BLOCKED` whose new plan is not blocked returns false (`:229`) and QA plans again. Probe: `test_fixed_access_block_is_rerun_as_a_pass`. A stored `PASS` compares facts and checks (`:234`), then refuses when the live plan is blocked or still has repairs (`:237`), then compares the proof id (`:239`). Forging the stored check to `"false"` so it matches the live failure is `test_forged_pass_matching_a_failed_check_is_refused`, for `published` and for `no_access_blocks`. Both raise `qa record does not match` and make 0 writes. A stored `FAIL_REPAIRABLE` parses (`_VERDICTS` at `:77`) and resume raises `qa record does not match`. That refusal is `test_stored_fail_repairable_is_an_accepted_shape`. It does not grep the source. The aesthetics parser strips the `qa` key (`notion_aesthetics.py:150`). Re-entering variants after QA does not rewrite the file. The stored path allows the first colour's proof title (`notion_variants.py:480-481`).

`passed` is only `"true"` or `"false"` (`_require_passed` at `:202`). `repairs` must be unique members of `_REPAIRABLE` (`:212`). Database subclass checks use `isinstance`: `_is_database` (`:302`), shared databases (`:333`), notification values (`:399`), the kind lookup (`:460`), and accounted database titles (`:642`).

Carried must-fixes. The secret-link compare is `notion_variants.py:847`. The accent and vocabulary id compare is `:844`. The saved-path `_require_original` call is `:837`. The plan call at `:387` and the end-of-ensure call at `:441` were already killed in W8. The navigation block check is `notion_aesthetics.py:345`. The palette token-name check is `notion_variants.py:280`. The two `reject_duplicate_labels` calls are `:198` and `:202`. `len(children) != 2` is `:895`. The home id check is `:904`. `_source_page` `parent_type` is `:519`. `_find_titled` `len(matches) > 1` is `:534`. `_find_copy` `len(matches) > 1` is `:548`. Publish stays after the accent and vocabulary blocks (`:738-748`). `if retained_created_ids is not None` is `notion_progress_record.py:180`. A database under a hub or home block is refused on the empty path by `_refuse_structure_block_databases` (`notion_variants.py:612`, call at `:388`) and on the saved path by `_has_nested_child` parents (`:624`), which include `_home_and_hub_block_ids` (`:587`). Shared databases stay parented to the home page id. `_is_database` uses `isinstance` (`:584`). The unpublished-after-crash assert is `tests/unit/agents/test_notion_product_builder_variants.py:2555`, inside `test_each_variant_step_crash_resumes_without_a_second_page` (`:2527`).

Eight rows are equivalent. Deleting the palette token-name check (`notion_variants.py:280`) still raises `checkpoint aesthetics accent is duplicated` from `notion_aesthetics.py:203` during load, before `_aligned_pairs`. Probe: `test_duplicate_palette_token_names_refuse_before_any_write` (`tests/unit/agents/test_notion_product_builder_variants.py:3202`). Adapter writes stay empty and the file stays unchanged. Deleting the home id check (`notion_variants.py:904`) still raises `checkpoint page is missing from the fixture probe` from `notion_dashboard.py:301`. Probe: `test_replay_rejects_a_home_without_the_spec_id` (`:3280`). Deleting `_source_page` `parent_type != "workspace"` (`notion_variants.py:519`) still raises `checkpoint page is not the stored top-level page` from `notion_dashboard.py:307`. Probe: `test_replay_rejects_a_home_that_is_not_workspace` (`:3300`). Deleting the `next_phase` conjunct (`notion_qa.py:115`) still passes `test_loaded_variants_checkpoint_is_already_in_qa`, because `load_variant_checkpoint` sets `next_phase` to `qa` whenever variants exist. Deleting `if blocked: repairs = ()` (`notion_qa.py:256-257`) still records `repairs == ()` on `test_structural_block_keeps_flag_repairs_off_the_record`, because `:123` copies repairs only when the plan is not blocked. Verdict stays `BLOCKED` and adapter writes stay empty. Deleting `type(item) is not str` (`notion_qa.py:196`) still refuses an integer repair. `require_token` (`notion_product_builder.py:561`) raises `checkpoint qa repair must be a non-empty string`. Probe: `test_integer_repair_item_is_refused_before_any_write`. Adapter writes stay empty and the file stays unchanged. Deleting `if envelope.payload is None` (`notion_qa.py:143`) is dead on the public entry. `load_variant_checkpoint` already refuses a missing payload before `_stored_qa`. Deleting `if record is None` (`notion_qa.py:794`) is dead on the public entry. `_with_qa` sets `qa` before `_write_qa`. Probe for both: `test_public_entry_payload_and_qa_record_are_present`. It passes on both versions, writes one `duplicate_page`, and leaves a qa object. Each probe refuses or keeps the same verdict on both versions and does not accept a bad build. The PASS `plan.blocked or plan.repairs` guard (`:237`) is not equivalent. It is killed.

Prompt-integrity review: `docs/control/reviews/2026-10-05-session-07-prompt-integrity.md` (Wave 9 addendum). Product-build tests: 556 passed across the QA file, the variants file, the progress file, and the six phase files. Full local pytest: 2519 collected, 2314 passed, 193 skipped, 12 failed. All 12 failures are `test_compose_preserves_the_postgres_password` with `FileNotFoundError` because the `docker` binary is absent. They are local-only. CI is the gate. Tests make no socket or other network access beyond the tripwire above. `ruff format --check` and `ruff check` are clean on `notion_qa.py` and `test_notion_product_qa.py`. `pyright` 1.1.411 (`uv.lock` and CI) reports 0 errors on those two files with SQLAlchemy 2.0.52. Docstring coverage is 14.95%, measured by Eng Ops. This session did not re-measure it. `notion_qa.py` was not edited. The new tests pass on the existing checks.

Mutation checks. 110 mutations were each applied, the owning test file was run, and the edit was reverted. 102 were killed. 8 are equivalent. The Failed column is the real pytest failure count for that mutant. A syntax error is not a kill. The foreign linked-view mutant replaces the source check with `continue` and fails 1 test. The Failed column sums to 255. The 17 variant-file rows were not re-run. `tests/unit/agents/test_notion_product_builder_variants.py` and those source files are unchanged from `1a18b93`, so their Failed counts stay the round-3 measurements (14 killed, 3 equivalent, Failed sum 20). The 84 earlier QA rows, the two cross-file rows, and the 7 new QA rows were remeasured against `test_notion_product_qa.py`: 88 killed, 5 equivalent, Failed sum 235. Versus the table on `1a18b93` (103 rows, 95 killed, 8 equivalent, Failed sum 235), seven rows were added and eight existing counts moved. `force shared_databases true` moved from 2 to 3. `force notification_values true` moved from 3 to 4. `force page_count true` moved from 2 to 3. `force fresh_duplicate true` moved from 1 to 5. `force palette true` moved from 3 to 6. `force facts_persisted true` moved from 1 to 2. `delete accent count` moved from 1 to 2. `delete known page count` moved from 1 to 2. Each new row fails 1. 235 + 13 + 7 = 255. The round-2 table claimed 85 rows, 79 killed, 6 equivalent, and a Failed sum of 166. That claim labeled the PASS guard equivalent and counted a verdict mutant that deleted the whole if. This table does not. `qa verdict skips the allowed set` deletes only `or verdict not in _VERDICTS` and fails 1 (`verdict-word`). Each of the 16 structural checks is one row that forces the check true. Public-link conjuncts, proof-match conjuncts, parser conjuncts, saved-record conjuncts, and each `isinstance` site are their own rows.

| Mutation | Site (file:line) | Failing tests | Failed |
|---|---|---|---|
| delete secret-link compare | `notion_variants.py:847`. Delete `if link != record.secret_link` | `test_replay_rejects_a_changed_secret_link` | 1 |
| delete accent and vocabulary id compare | `notion_variants.py:844`. Delete the accent and vocabulary id compare | `test_replay_rejects_a_moved_accent_block_id` | 1 |
| delete saved-path `_require_original` | `notion_variants.py:837`, the call in `_require_saved` | `test_saved_home_original_flag_refuses` for `duplicate_as_template` and `search_indexing` | 2 |
| delete navigation block type check | `notion_aesthetics.py:345`. Delete `type(block) is not NotionTextBlock or block.parent_id != page_id` | `test_navigation_callout_fails_the_created_hub_pair` | 1 |
| delete palette token name uniqueness | `notion_variants.py:280`. Delete `len({token.name for token in tokens}) != len(tokens)` | Equivalent. `test_duplicate_palette_token_names_refuse_before_any_write` still raises `checkpoint aesthetics accent is duplicated`. 0 writes | 0 |
| delete variant name dedup | `notion_variants.py:198`. Delete the name `reject_duplicate_labels` call | `test_replay_rejects_a_duplicated_variant_label` for `name` | 1 |
| delete variant page-id dedup | `notion_variants.py:202`. Delete the page-id `reject_duplicate_labels` call | `test_replay_rejects_a_duplicated_variant_label` for `page_id` | 1 |
| delete `len(children) != 2` | `notion_variants.py:895`. Delete `len(children) != 2 or` | `test_replay_rejects_an_extra_variant_child` | 1 |
| delete home id check | `notion_variants.py:904`. Delete `if home is None or home.id != stored.page_id` | Equivalent. `test_replay_rejects_a_home_without_the_spec_id` still raises `checkpoint page is missing from the fixture probe`. 0 writes | 0 |
| delete `_source_page` parent_type | `notion_variants.py:519`. Delete `or page.parent_type != "workspace"` | Equivalent. `test_replay_rejects_a_home_that_is_not_workspace` still raises `checkpoint page is not the stored top-level page`. 0 writes | 0 |
| delete `_find_titled` `len(matches) > 1` | `notion_variants.py:534` | `test_two_colour_titles_refuse_before_any_write` | 1 |
| delete `_find_copy` `len(matches) > 1` | `notion_variants.py:548` | `test_two_copy_titles_refuse_before_any_write` | 1 |
| publish before blocks | `notion_variants.py:748` moved to just before the accent match at `:738` | `test_each_variant_step_crash_resumes_without_a_second_page` for `add_callout_block` and `add_text_block` | 2 |
| skip retained created ids | `notion_progress_record.py:180`. Replace `if retained_created_ids is not None` with `if False` | `test_reversed_dashboard_created_ids_survive_variants` | 1 |
| delete plan nested-database refuse | `notion_variants.py:388`. Delete `_refuse_structure_block_databases(probe)` | `test_database_under_a_structure_block_refuses_before_any_write` for home and hub, and `test_database_subclass_under_a_hub_block_is_refused` | 3 |
| drop hub and home blocks from nested parents | `notion_variants.py:624`. Drop `*_home_and_hub_block_ids(probe)` | `test_saved_database_under_a_structure_block_refuses` for home and hub | 2 |
| exact type instead of isinstance | `notion_variants.py:584`. Replace `isinstance(database, NotionDatabase)` with `type(database) is NotionDatabase` | `test_database_subclass_under_a_hub_block_is_refused` and `test_database_subclass_under_a_copy_page_is_refused` | 2 |
| skip flag repairs | `notion_qa.py:123`. Replace `if not plan.blocked and plan.repairs` with `if False` | `test_unpublished_variant_is_repaired_then_passes`, `test_lying_template_repair_records_blocked`, `test_unpublish_page_is_repaired_then_passes`, both unpublish crash resumes, `test_search_indexing_on_is_repaired_then_passes`, and `test_repair_guard_refuses_before_publish` | 7 |
| skip proof duplicate | `notion_qa.py:762`. Return `""` after `guard_operation` and before `duplicate_page` | including `test_finished_variants_pass_and_duplicate_once` for mass and business, and `test_duplicate_with_the_wrong_title_is_refused` | 20 |
| delete saved PASS facts compare | `notion_qa.py:234`. Compare checks only | `test_tampered_fact_is_refused` | 1 |
| drop `FAIL_REPAIRABLE` verdict | `notion_qa.py:77`. Drop `FAIL_REPAIRABLE` from `_VERDICTS` | `test_stored_fail_repairable_is_an_accepted_shape` | 1 |
| stop stripping the qa reference | `notion_aesthetics.py:150`. Change the strip set to `{_AESTHETICS_KEY, "variants"}` | including `test_variants_after_qa_does_not_drop_the_qa_key` and both `test_forged_pass_matching_a_failed_check_is_refused` cases | 31 |
| ignore the qa proof title | `notion_variants.py:481`. Delete `or page.title == proof_title` | `test_variants_after_qa_does_not_drop_the_qa_key` | 1 |
| delete next_phase conjunct | `notion_qa.py:115`. Delete `or stored.next_phase != PHASE_QA` | Equivalent. `test_loaded_variants_checkpoint_is_already_in_qa` still passes. The loader already sets `next_phase` to `qa` | 0 |
| delete require_same_spec | `notion_qa.py:114`. Delete `require_same_spec(stored, validated)` | `test_other_spec_is_refused_before_a_plan` | 1 |
| delete blocked rerun | `notion_qa.py:229`. Delete `if not plan.blocked: return False` | `test_fixed_access_block_is_rerun_as_a_pass` | 1 |
| delete blocked proof-id guard | `notion_qa.py:227`. Delete `if saved.proof_page_id != ""` | `test_blocked_record_with_a_proof_id_is_refused` | 1 |
| delete blocked facts compare | `notion_qa.py:231`. Compare checks only on a stored `BLOCKED` | `test_tampered_blocked_fact_is_refused` | 1 |
| keep flag repairs while structurally blocked | `notion_qa.py:256`. Delete `if blocked: repairs = ()` | Equivalent. `test_structural_block_keeps_flag_repairs_off_the_record` still records `repairs == ()` and 0 writes | 0 |
| force search_indexing check true | `notion_qa.py:268` | `test_search_indexing_on_is_repaired_then_passes` | 1 |
| force published check true | `notion_qa.py:266` | `test_unpublished_variant_is_repaired_then_passes`, `test_unpublish_page_is_repaired_then_passes`, both unpublish crash resumes, `test_structural_block_keeps_flag_repairs_off_the_record`, and `test_stored_pass_with_a_new_unpublished_page_is_refused` | 6 |
| force duplicate_button check true | `notion_qa.py:267` | `test_lying_template_repair_records_blocked` | 1 |
| force spec_coverage true | `notion_qa.py:283` | `test_token_name_drift_fails_spec_coverage_only`, `test_dropped_variant_row_fails_variant_count`, `test_colour_and_token_length_mismatch_is_blocked`, and `test_renamed_variant_fails_palette` | 4 |
| force shared_databases true | `notion_qa.py:284` | `test_renamed_database_fails_shared_databases_only`, `test_business_database_order_fails_shared_databases`, and `test_shared_database_off_the_home_page_is_blocked` | 3 |
| force duplicate_databases true | `notion_qa.py:285` | `test_extra_database_is_blocked_with_no_adapter_writes` and `test_database_subclass_is_an_extra_database` | 2 |
| force hubs_present true | `notion_qa.py:286` | `test_renamed_hub_fails_hubs_present_only` and `test_reordered_hubs_fail_hubs_present` | 2 |
| force linked_views true | `notion_qa.py:287` | `test_linked_view_pointed_at_another_known_database_is_blocked` and `test_missing_linked_view_is_blocked` | 2 |
| force formulas_compile true | `notion_qa.py:288` | `test_missing_formula_input_fails_compile_only` and `test_missing_formula_database_is_blocked` | 2 |
| force notification_values true | `notion_qa.py:289` | `test_wrong_formula_expression_is_blocked`, `test_renamed_notification_database_fails_notification_values`, `test_missing_formula_database_is_blocked`, and `test_notification_row_subclass_fails_notification_values` | 4 |
| force page_count true | `notion_qa.py:290` | `test_extra_page_fails_page_count_only`, `test_missing_known_page_fails_page_count`, and `test_notification_row_subclass_fails_notification_values` | 3 |
| force variant_count true | `notion_qa.py:291` | `test_dropped_variant_row_fails_variant_count` | 1 |
| force public_links true | `notion_qa.py:292` | `test_unpublished_variants_block_without_writes` for forged and stranger at 1, 2, and 3, all six matching-forgery cases, all seven captured-shape cases, the cleared link, the page-id captured URL, the live URL, and the provider failure | 23 |
| force fresh_duplicate true | `notion_qa.py:293` | `test_moved_variant_fails_fresh_duplicate_only`, `test_renamed_variant_page_fails_fresh_duplicate`, `test_forged_spec_id_fails_fresh_duplicate`, and both `test_fresh_duplicate_icon_and_cover_stay_in_the_false_set` cases | 5 |
| force no_access_blocks true | `notion_qa.py:294` | including `test_no_access_block_is_blocked_with_no_adapter_writes` | 4 |
| force cross_catalogue true | `notion_qa.py:295` | `test_foreign_relation_is_blocked`, `test_subclass_database_foreign_relation_fails_cross_catalogue`, and `test_foreign_linked_view_fails_cross_catalogue` | 3 |
| force palette true | `notion_qa.py:296` | `test_changed_icon_fails_palette`, `test_removed_blue_accent_fails_palette`, `test_renamed_variant_fails_palette`, `test_vocabulary_callout_fails_palette`, and both `test_fresh_duplicate_icon_and_cover_stay_in_the_false_set` cases | 6 |
| force teardown_quality true | `notion_qa.py:297` | `test_edited_hub_section_fails_teardown_only` and `test_empty_evidence_fails_teardown` | 2 |
| force facts_persisted true | `notion_qa.py:631`. `return True` | `test_published_live_url_must_match_the_stored_link` and `test_notification_row_subclass_fails_notification_values` | 2 |
| delete trusted secret-link check | `notion_qa.py:514`. Delete `if not _is_trusted_link(link, page.id)` | `test_unpublished_variants_block_without_writes` for `forged` at 1, 2, and 3, `test_cleared_public_url_forged_link_does_not_publish`, and `test_unpublished_link_with_page_id_still_must_match_captured_url`. The matching-forgery cases stay blocked by the captured-url check | 5 |
| delete stranger-access check | `notion_qa.py:516-518` | `test_unpublished_variants_block_without_writes` for `stranger` at counts 1, 2, and 3 | 3 |
| delete published live-url compare | `notion_qa.py:521`. Delete `if not _is_trusted_link(live, page.id)` | `test_published_live_url_must_match_the_stored_link` | 1 |
| delete unpublished captured-url compare | `notion_qa.py:525` | all seven `test_unpublished_captured_url_must_match_the_fixture_shape` cases, including userinfo, the credential-host trick, `?x=1`, `#frag`, and `http`. The flag `public_links` flips. Verdict stays `BLOCKED` because facts disagree, so the flag assert is the kill | 7 |
| exact type instead of `_is_database` | `notion_qa.py:303`. `type(value) is NotionDatabase` | including `test_database_subclasses_still_pass` and `test_database_subclass_is_an_extra_database` | 3 |
| shared databases reject subclasses | `notion_qa.py:333`. `type(database) is not NotionDatabase` | `test_database_subclasses_still_pass` and `test_subclass_database_foreign_relation_fails_cross_catalogue` | 2 |
| delete ambiguous proof guard | `notion_qa.py:708` | `test_two_proof_copies_are_ambiguous` | 1 |
| delete existing proof match guard | `notion_qa.py:712` | `test_existing_proof_that_does_not_match` (parent, published, icon, cover, spec_id) and `test_proof_name_must_be_the_first_colour` | 6 |
| delete proof id inequality | `notion_qa.py:728` | `test_duplicate_that_returns_the_source_page_is_refused` | 1 |
| delete proof unpublished guard | `notion_qa.py:730` | `test_existing_proof_that_does_not_match` for `published` and `test_published_duplicate_is_not_accepted_as_proof` | 2 |
| delete proof icon guard | `notion_qa.py:731` | `test_existing_proof_that_does_not_match` for `icon` | 1 |
| delete proof cover guard | `notion_qa.py:732` | `test_existing_proof_that_does_not_match` for `cover` | 1 |
| delete proof spec-id guard | `notion_qa.py:733` | `test_existing_proof_that_does_not_match` for `spec_id` | 1 |
| delete proof colour-name guard | `notion_qa.py:734` | `test_proof_name_must_be_the_first_colour` | 1 |
| delete proof workspace parent guard | `notion_qa.py:729` | `test_existing_proof_that_does_not_match` for `parent` | 1 |
| delete fresh-duplicate workspace parent | `notion_qa.py:543` | `test_moved_variant_fails_fresh_duplicate_only` | 1 |
| delete repair guard | `notion_qa.py:743` | `test_repair_guard_refuses_before_publish` | 1 |
| delete post-duplicate proof match | `notion_qa.py:764` | including `test_published_duplicate_is_not_accepted_as_proof` and `test_duplicate_with_the_wrong_title_is_refused` | 3 |
| drop recorded_at | `notion_qa.py:785` | including `test_fixed_access_block_is_rerun_as_a_pass` | 4 |
| keep raw secret links | `notion_qa.py:668`. `_normalised_secret_link` returns the link unchanged | including `test_secret_link_facts_match_across_fresh_runs` | 3 |
| qa record accepts a non-object | `notion_qa.py:152` | `test_incomplete_qa_record_is_refused` for `object` | 1 |
| qa record skips exact keys | `notion_qa.py:155` | `test_incomplete_qa_record_is_refused` for `missing` and `extra` | 2 |
| qa verdict skips the allowed set | `notion_qa.py:158`. Delete only `or verdict not in _VERDICTS`. The `type(verdict) is not str` check stays | `test_incomplete_qa_record_is_refused` for `verdict-word` only. `verdict-type` still fails the type check. Deleting the whole if is a different mutant and is not this row | 1 |
| qa proof skips the string check | `notion_qa.py:161` | `test_incomplete_qa_record_is_refused` for `proof-type` | 1 |
| passed accepts any token | `notion_qa.py:202`. `_require_passed` returns `value == "true"` | `test_incomplete_qa_record_is_refused` for `passed-yes` and `passed-true-word` | 2 |
| repairs accept any token | `notion_qa.py:212` | `test_incomplete_qa_record_is_refused` for `repairs-dup` and `repairs-word` | 2 |
| pairs accept an empty list | `notion_qa.py:177`. Delete `or not value` | `test_incomplete_qa_record_is_refused` for `checks-empty` | 1 |
| notification isinstance to type | `notion_qa.py:399` | `test_database_subclasses_still_pass` | 1 |
| kind database isinstance to type | `notion_qa.py:460` | `test_database_subclasses_still_pass` | 1 |
| accounted database isinstance to type | `notion_qa.py:642` | `test_database_subclasses_still_pass` | 1 |
| delete PASS blocked-or-repairs guard | `notion_qa.py:237`. Delete `if plan.blocked or plan.repairs` | `test_forged_pass_matching_a_failed_check_is_refused` for `no_access_blocks` and `published`. Both raise `qa record does not match` and make 0 writes. Killed. Not equivalent | 2 |
| delete PASS proof-id guard | `notion_qa.py:239` | `test_tampered_pass_proof_id_is_refused` for `page_forged` and `""` | 2 |
| delete pair item shape | `notion_qa.py:181` | `test_incomplete_qa_record_is_refused` for `checks-item` | 1 |
| delete pair value types | `notion_qa.py:185` | `test_incomplete_qa_record_is_refused` for `fact-type` | 1 |
| delete repairs list type | `notion_qa.py:192` | `test_incomplete_qa_record_is_refused` for `repairs-int` | 1 |
| delete repair item type | `notion_qa.py:196`. Delete `type(item) is not str` | Equivalent. `test_integer_repair_item_is_refused_before_any_write` still raises. `require_token` (`notion_product_builder.py:561`) refuses the same input with `checkpoint qa repair must be a non-empty string`. 0 writes. The file stays unchanged | 0 |
| delete proof title compare | `notion_qa.py:724` | `test_duplicate_with_the_wrong_title_is_refused` | 1 |
| delete recorded kinds compare | `notion_qa.py:328`. Delete `if recorded != kinds` | `test_business_database_order_fails_shared_databases`. `shared_databases` is False. 0 writes | 1 |
| delete notification title compare | `notion_qa.py:401`. Delete `database.title != _NOTIFICATION_TITLE` | `test_renamed_notification_database_fails_notification_values` | 1 |
| delete foreign linked-view source check | `notion_qa.py:561`. Replace the source check with `continue` | `test_foreign_linked_view_fails_cross_catalogue`. The mutant is valid Python. `cross_catalogue` stays True. Not a syntax error | 1 |
| delete accent count | `notion_qa.py:601`. Delete `len(accents) != 1 or len(samples) != 1` | `test_removed_blue_accent_fails_palette` and `test_vocabulary_callout_fails_palette` | 2 |
| delete empty evidence check | `notion_qa.py:609`. Delete `if not spec.evidence` | `test_empty_evidence_fails_teardown` | 1 |
| delete known page count | `notion_qa.py:479`. Delete `len(known_present) != len(known)` | `test_missing_known_page_fails_page_count` and `test_notification_row_subclass_fails_notification_values`. `page_count` stays False on the missing-page case | 2 |
| delete missing variant page check | `notion_qa.py:308`. Delete `type(page) is not NotionPage` | `test_missing_variant_page_is_a_product_build_error`. The good path raises `ProductBuildError` matching `qa variant page is missing`. The mutant raises `AttributeError` | 1 |
| delete formula database none | `notion_qa.py:421`. Delete `if database is None: return False` in `_formulas_compile` | `test_missing_formula_database_is_blocked`. The good path records `BLOCKED`. The mutant raises `AttributeError` | 1 |
| delete colour token length check | `notion_qa.py:316`. Delete the length compare in `_spec_coverage` | `test_colour_and_token_length_mismatch_is_blocked`. The good path records `BLOCKED` with `spec_coverage` False. The mutant raises `ValueError` from `zip(..., strict=True)` | 1 |
| delete missing notification check | `notion_qa.py:395`. Delete `if notice is None: return False` | `test_missing_notification_dashboard_is_blocked`. The good path raises `ProductBuildError` matching `notification dashboard is missing`. The mutant raises `AttributeError` | 1 |
| delete formula property database none | `notion_qa.py:442`. Delete `if database is None: return None` | `test_missing_formula_database_is_blocked`. The good path records `BLOCKED`. The mutant raises `AttributeError` | 1 |
| delete hub name order | `notion_qa.py:352` | `test_reordered_hubs_fail_hubs_present`. `hubs_present` is False | 1 |
| delete notification database from known set | `notion_qa.py:558-559`. Delete `known.add(notice.database_id)` | `test_view_of_the_notification_database_stays_in_catalogue`. The good path is `PASS`. The mutant records `cross_catalogue` False | 1 |
| delete skip non-database | `notion_qa.py:564`. Delete `if not _is_database(database): continue` | `test_non_database_value_is_skipped`. The good path is `PASS`. The mutant raises `AttributeError` | 1 |
| delete palette colour name | `notion_qa.py:584`. Delete `if record.name != colour` | `test_renamed_variant_fails_palette`. `palette` is False | 1 |
| delete linked-view kind guard | `notion_qa.py:371` | `test_missing_linked_view_is_blocked`. The good path records `BLOCKED`. The mutant raises `AttributeError` | 1 |
| delete payload none return | `notion_qa.py:143`. Delete `if envelope.payload is None: return None` | Equivalent. Dead on the public entry. `load_variant_checkpoint` already refuses a missing payload before `_stored_qa`. Probe `test_public_entry_payload_and_qa_record_are_present` passes on both versions, with one `duplicate_page` and a written qa object | 0 |
| delete missing qa record check | `notion_qa.py:794`. Delete `if record is None` | Equivalent. Dead on the public entry. `_with_qa` sets `qa` before `_write_qa`. The same probe passes on both versions | 0 |
| delete shared database parent check | `notion_qa.py:335`. Delete `or database.parent_id != stored.page_id` | `test_shared_database_off_the_home_page_is_blocked`. The good path records `BLOCKED` with false checks `("shared_databases",)` and 0 writes. The mutant records `PASS` and calls `duplicate_page` | 1 |
| replace fresh-duplicate title compare with True | `notion_qa.py:574` on tip `9eff481e`. Replace `page.title == title` with `True`. The earlier `:543` citation does not match that file | `test_renamed_variant_page_fails_fresh_duplicate`. The good path records `BLOCKED` with false checks `("fresh_duplicate",)` and 0 writes. Re-checked against tip `9eff481e` | 1 |
| replace fresh-duplicate spec-id check with True | `notion_qa.py:576` on tip `9eff481e`. Replace `SPEC_ID_PROPERTY not in page.properties` with `True`. The earlier `:545` and `:572` citations do not match that conjunct | `test_forged_spec_id_fails_fresh_duplicate`. The good path records `BLOCKED` with false checks `("fresh_duplicate",)` and 0 writes. Re-checked against tip `9eff481e` | 1 |
| delete vocabulary sample type check | `notion_qa.py:598`. Delete `type(block) is NotionTextBlock` on the SAMPLE block | `test_vocabulary_callout_fails_palette`. The good path records `BLOCKED` with false checks `("palette",)` and 0 writes. The mutant records `PASS` and calls `duplicate_page` | 1 |
| delete fresh-duplicate icon check | `notion_qa.py:545`. Delete `page.icon == hub_icon(token)` | `test_fresh_duplicate_icon_and_cover_stay_in_the_false_set` for `icon`. The good path's false checks are `("fresh_duplicate", "palette")`. The mutant drops `fresh_duplicate` from that set | 1 |
| delete fresh-duplicate cover check | `notion_qa.py:546`. Delete `page.cover == hub_cover(token)` | `test_fresh_duplicate_icon_and_cover_stay_in_the_false_set` for `cover`. The good path's false checks are `("fresh_duplicate", "palette")`. The mutant drops `fresh_duplicate` from that set | 1 |
| delete notification row type check | `notion_qa.py:399`. Delete `type(row) is not NotionPage` and keep the database `isinstance` | `test_notification_row_subclass_fails_notification_values`. The good path's false checks are `("notification_values", "page_count", "facts_persisted")`. The mutant drops `notification_values` from that set. Still `BLOCKED` | 1 |

## 2026-10-07 — Session 07 W8: variants

Session 07 stays incomplete. This wave is not SESSION_07 COMPLETE. State revision stays 56. `current_session` stays 7. `completed_sessions` stays `[0, 1, 2, 3, 4, 5, 6]`. `next_session` stays 7. `next_prompt` stays `10_SESSION_07_PRODUCT_BUILD_VARIANTS_AND_QA.md`. `head_sha` stays the W7 squash `9bc56b2c839f66fce13bebf55cb30e88474f526e`. It is the tip-sync pointer. It is not the revision that produced the test or mutation figures below. Those figures were measured on this commit, the child of `6ce54e5b77da506232bac35465201a1a7b04dd08`. Parent commit `3b025c9f` CI verify run is `37561761627`, job `112600387175`, SUCCESS. Commit `af7c94bc` CI verify run is `37569007743`, job `112623180909`, SUCCESS. Commit `6ce54e5b` CI verify run is `37575983592`, job `112644873001`, SUCCESS. This commit's CI run is not invented here. `evidence_closure_commit_sha` stays the Session 06 closure tip `0f94d585f23d79e5ac18479f01e14f67cbaad332`. `last_verified_commit` stays bootstrap `1abf0d7cca3a6b8cd7efcd0a45523538fd5bfd9d`. `updated_at` is `2026-10-07T06:46:04Z`.

Twelve session 7 evidence keys stay false, including `variant_builder_implemented`. No session exit code is recorded. A07, A08, and A09 stay DESIGNED. `commissioned_agents` stays empty. Exit 78 scheduler stays HELD. Narrative `next_phase` is `qa` (A09) and it is not started. There is no top-level `next_phase` field.

Fixture variants live in `notion_variants.py`. `build_variants` (`notion_variants.py:82`) writes one shallow `duplicate_page` per `colour_variants` entry, zipped in index order with `palette_tokens`. Lengths must match and must be 3 or 4. Validate stays first (`_validate_earlier_phases` at `notion_variants.py:98`). On an empty variants list, `await _plan_variants` (`notion_variants.py:353`, call at `:103`) runs inside the try (`:102`) and before any adapter write. A `ProviderFailure` from the plan `get_public_url` is handled by `raise_recorded` (`notion_progress.py:133`). A `ProductBuildError` from the plan is not caught and does not append a repair job. The plan reads `get_public_url` for an already published adoption (`:394`). That method is not in `_WRITE_METHODS` (`tests/unit/agents/test_notion_product_builder_variants.py:172` and `tests/unit/agents/test_notion_product_build_progress.py:68`). It is a read, so a plan refusal still has adapter `calls == []`. The plan checks every adoption, finished colours included: `_require_original` at `:369`, `_require_adoptable` at `:385` (shell copy `:635`, spec value `:637-638`, foreign child `:639`, and the duplicate-block raises in `_matching_accent` `:712-713` and `_matching_vocabulary` `:736-737`), and `_require_published_link` at `:386`. The plan skips `page_id == ""` at `:379`, which is why a page created later by `duplicate_page` is checked only in `_finish_variant`. In-play pages are `(Copy)` leftovers and `/ <Colour>` leftovers only (`_page_in_play` at `:273`, `_in_play_pages` at `:280`). The release title filter is deleted. `_page_in_play` already admits only those titles for every input, so the filter could not change the drop set. The adoption lookup uses `probe.pages.get` and raises `planned variant page is missing` when the id is absent (`:381-383`), before any write. The old subscript type guard stays deleted. `pages` is `dict[str, NotionPage]`, so a successful subscript is a `NotionPage`. The `found is None` disjunct in `_require_unique_after_drops` stays deleted (`:332` raises only when `found is not None and found.id != source.id`). The `source_spec is None` early return is deleted. It is not a mutation row. A home spec that is missing, None, the string `"None"`, or `""` is refused earlier, on both versions, before this function runs. A `(Copy)` whose spec id is the string `"None"`, with the home spec left intact, raises `variant page does not match` on both versions. No `build_variants` test separates those two versions. The source is excluded from `drop_ids` and still holds a string spec id on the path that reaches find, so `find_spec_page` cannot return None for that id. A non-string spec id raises in `_property` before find returns None. The dead plan clauses stay deleted: the recorded-id return inside `_page_in_play`, the spec-id return, and the in-play guards in `_plan_adoptions`. ProductSpec uniqueness uses `find_spec_page` (`_require_unique_after_drops` at `:324`, call at `:376`). Execution applies that plan: `_release_copied_spec_ids` (`:104`), `_bind_earlier_phases` (`:105`), then `_ensure_planned` (`:106`). The finish drop is `:670-671`. `publish_page` (`:688-689`), `set_duplicate_as_template` (`:690-691`), and `set_search_indexing` (`:692-693`) run only on that variant page, and only for a step that is still missing. The finish secret link is `get_public_url` at `:694`. An empty or non-string link raises `ProviderFailure` at `:695-696`, which the try records as a repair job. Replay compares the call at `:786` with the stored link at `:787`. The module does not contain an `https://` literal. `write_checkpoint` stays the single progress writer. The no-record rule is unchanged (`notion_progress.py:250`).

Unpublished, `duplicate_as_template`, `search_indexing`, icon, and cover drift on an adopted page is repaired by `_finish_variant`, not refused. That repair is intended. A bad shell, a foreign spec id, a foreign or nested child, a duplicate accent or vocabulary block, and a missing secret link on a page that is already published are refused in the plan, before any write. An unused `(Copy)` that still holds the source spec id, after all three colours are finished, is refused by the release loop (`:373-375`) before any drop. A `(Copy)` and a `{title} / Green` that both hold the source spec id are both adopted, by design (`test_copy_and_green_holding_the_spec_id_are_both_adopted`). A `duplicate_page` that returns `parent_type="page_id"` stops at exactly `["duplicate_page"]` (`test_lying_duplicate_parent_stops_after_duplicate_page`, `:1885`).

Checkpoint names stay the six build phases. `created_notion_ids["variants"]` stays `None` until `provider_object_references["variants"]` exists, then `notion_progress_record.py:258-269` writes the list. A successful write keeps the loaded created ids and replaces only the variants key (`notion_progress_record.py:180-188`). Page and block counts add the variant pages at `notion_progress_record.py:303-304`. `write_document` is still called only from `write_checkpoint`. A provider failure of `variants.duplicate`, including a `ProviderFailure` from the release `drop_page_property`, from the plan `get_public_url`, or from an empty finish link, leaves a `provider_response` job only when a prior record exists. A first phase-1 failure with no record raises and writes no job and no file (`notion_progress.py:250`). The job phase stays `aesthetics_and_content_completion`.

On the stored path, `build_variants` returns after `_require_saved` (`:99-101`) and does not plan or release. A variant or nested id is a recorded page id (`:450-455`). A hub child titled `{title} (Copy)` or `/ Blue` is not that id. An extra workspace `/ Blue` passes replay even with a child database or page under it. A forgery with the recorded title and a different id is rejected, because the lookup is `probe.pages.get(record.page_id)` inside `_require_saved` at `:779`, not a title scan and not the `pages.get` in `_ensure_planned` at `:416`. The empty path still opens an unrecorded `{title} (Copy)` or `/ <Colour>` page so resume can adopt it. Adoption is planned by `_plan_adoptions` (`:336`): `_find_copy` at `:341` and `_find_titled` at `:345`.

`test_finished_variant_child_refuses_before_release_drop` (`tests/unit/agents/test_notion_product_builder_variants.py:926`) is B1 case 1. `test_finished_purple_child_refuses_before_blue_copy_is_published` (`:987`) is B1 case 2. `test_copy_plus_another_spec_holder_refuses_before_any_drop` (`:1061`) is B2. `test_child_under_a_page_block_writes_nothing` (`:892`) is the depth-3 nest. `test_finished_green_different_spec_wrong_parent_or_product_refuses` (`:1345`) refuses a finished Green whose spec id differs, or whose parent or product id is wrong, before Blue is published. `test_finished_green_missing_secret_link_refuses_before_any_write` (`:1664`) covers a cleared `public_url` and a `get_public_url` that returns `''`. `test_copy_with_duplicate_blocks_refuses_before_any_drop` (`:1698`) covers two matching accent blocks and two matching vocabulary blocks on a `(Copy)`. `test_spec_less_copy_with_nested_child_refuses_before_any_write` (`:1739`) pins the traceback to `_plan_variants` and `_require_adoptable`, and asserts `_refuse_unadoptable_release` is absent. `test_unused_copy_holding_the_spec_id_refuses_before_any_drop` (`:1776`) covers a bad shell, a bad parent, and a child database on an unused `(Copy)` that still holds the spec id. `test_home_original_flag_refuses_before_any_write` (`:1435`) refuses home `duplicate_as_template=True` and `search_indexing=False` on an empty checkpoint. `test_lying_duplicate_source_flag_refuses_at_end_of_ensure` (`:1816`) parametrizes `is_published`, `duplicate_as_template`, and `search_indexing`. A lying `duplicate_page` sets that flag on the source after the copy is created. `build_variants` raises `ProductBuildError` matching `variant page does not match`. The traceback includes `_ensure_planned` and `_require_original` and excludes `_plan_variants`. Checkpoint bytes stay unchanged. `test_plan_refuses_a_missing_adoption_before_any_write` (`:1861`) plants a missing Blue page id, expects `planned variant page is missing`, and asserts adapter `calls == []`. `test_plan_secret_link_provider_failure_records_a_repair_job` (`:1916`) records one `provider_response` job when the plan read raises. `test_empty_secret_link_after_publish_records_a_repair_job` (`:1952`) records one job after publish when the finish link is empty. The zero-write refusals assert adapter `calls == []`, identical checkpoint bytes, identical fixture bytes, and no repair job. `test_replay_rejects_a_recorded_page_id_that_is_not_the_variant` (`:1232`) expects `ProductBuildError` matching `variant page does not match` for a missing id, the hub id, the home id, and a decoy. The same match is on `test_recorded_variant_id_stays_open_when_the_title_changes` (`:1131`) and `test_saved_variant_is_read_by_recorded_page_id` (`:1206`). `test_crash_inside_write_checkpoint_before_the_file_lands` (`:2699`) and `test_crash_after_write_checkpoint_resumes_without_a_second_page` (`:2613`) stay green. The eleven-step crash-resume matrix is `test_each_variant_step_crash_resumes_without_a_second_page` (`:2489`, parametrize `:2473-2488`). The `get_public_url` step raises `RuntimeError`, so the file stays unchanged.

Known limits, parked. Provenance here is the title plus those copyable shell fields. An unrelated empty workspace page that carries the source `product_id` and `design_shell_block_id` would be adopted. `parent_id` compares equal when both values are `None`. This wave does not claim a proven lineage. An extra workspace `/ Blue` passes replay even with a child database or page under it. A forgery with the recorded title and a different id is rejected on the saved path. A database under a hub or home block is accepted on every path (`_has_nested_child` parents at `:564`, walk at `:545`). The reviewer measured 29 normal writes on the empty path, none touching that database, and 0 writes on replay. This session did not re-measure that write count. `type(database) is NotionDatabase` at `:566` misses subclasses. The crash matrix at `:2489` does not assert the page stays unpublished when a block step crashes. Those three stay parked.

Prompt-integrity review: `docs/control/reviews/2026-10-05-session-07-prompt-integrity.md` (Wave 8 addendum). Product-build tests: 413 passed across the variants file, the progress file, and the six phase files. Full local pytest: 2376 collected, 2171 passed, 193 skipped, 12 failed. All 12 failures are `test_compose_preserves_the_postgres_password` with `FileNotFoundError` because the `docker` binary is absent. They are local-only. CI is the gate. Tests make no socket or other network access. Figures were measured on this commit, the child of `6ce54e5b`. `head_sha` stays the W7 squash and is not that commit. Parent commit `3b025c9f` CI verify run is `37561761627`, job `112600387175`, SUCCESS. Commit `af7c94bc` CI verify run is `37569007743`, job `112623180909`, SUCCESS. Commit `6ce54e5b` CI verify run is `37575983592`, job `112644873001`, SUCCESS. `ruff format --check` and `ruff check` are clean. `pyright` 1.1.411 (`uv.lock` and CI) reports 0 errors on the changed modules with SQLAlchemy 2.0.52. Docstring coverage is 14.95%, measured by Eng Ops. This session did not re-measure it. The socket tripwire patches `connect`, `connect_ex`, and `create_connection`. It does not patch `sendto` or `getaddrinfo`.

Carried must-fixes. CI-1 is the replay call `_require_created_ids` at `notion_aesthetics.py:104` (the `if stored.checkpoint_names` block is `:102-105`). CI-2 is the database pair check at `notion_aesthetics.py:276-277`. CI-3 is the hub pair check at `notion_aesthetics.py:281-282`. CI-4 is the accent and sample inequality at `notion_aesthetics.py:299-300`. Replay compares `hubs[].navigation_block_id` on both sides of the hub tuple (`notion_aesthetics.py:279` and `pairs.append` at `notion_aesthetics.py:347`). `reject_duplicate_labels` in aesthetics `_require_pairs` (`notion_aesthetics.py:203`), `_ensure_row` `client_name` (`notion_notifications.py:1195`), and the `_adopted_database` conjunct `title.type != "title"` (`notion_notifications.py:924`) are killed. The W7 created-ids prose partial is closed.

Mutation checks. 70 mutations were each applied, the owning test files were run, and the edit was reverted. 70 were killed. 0 are equivalent. No row is PARTIAL. A row is killed only when at least one test failed. The Failed column is the real pytest failure count for that mutant. The Failed column sums to 982. The `source_spec is None` early return is deleted and is not a row. Versus the table on `6ce54e5b` (70 rows, 68 killed, 2 equivalent, Failed sum 962): the end-of-ensure `_require_original` call moved from Failed 0 to Failed 3; the definition body moved from Failed 2 to Failed 5; the adoption loop moved from Failed 26 to Failed 27; the spec-id drop, `set_duplicate_as_template`, and `set_search_indexing` each moved from Failed 68 to Failed 71; `publish_page` moved from Failed 70 to Failed 73; the planned-page missing check is a new killed row, Failed 1. The removed guard is not in the sum. 962 + 20 = 982. Figures were measured on this commit, the child of `6ce54e5b`. Parent commit `3b025c9f` CI verify run `37561761627`, job `112600387175`, SUCCESS. Commit `af7c94bc` CI verify run `37569007743`, job `112623180909`, SUCCESS. Commit `6ce54e5b` CI verify run `37575983592`, job `112644873001`, SUCCESS.

| Mutation | Site (file:line) | Failing tests | Failed |
|---|---|---|---|
| CI-1 delete the replay call | `notion_aesthetics.py:104` (block `:102-105`). Delete `_require_created_ids(fixture, created, stored)` | `test_replay_rejects_a_tampered_top_level_page_id` and the other five aesthetics replay tampers | 6 |
| delete the page, workspace, and shell id check | `notion_aesthetics.py:268-275`. Delete the `top_level_page_id`, `workspace_id`, and `design_shell_block_id` comparison | `test_replay_rejects_a_tampered_top_level_page_id` | 1 |
| CI-2 delete the database pair check | `notion_aesthetics.py:276-277`. Delete `_created_database_pairs(created, probe) != stored.database_ids` | `test_replay_rejects_a_tampered_database_id` and the database leftover tampers | 7 |
| CI-3 delete the hub pair check | `notion_aesthetics.py:281-282`. Delete `_created_hub_pairs(created, probe) != hub_ids` | `test_replay_rejects_a_tampered_hub_page_id`, hub leftover tampers, and the drop-crash resume | 9 |
| delete the notification database id check | `notion_aesthetics.py:285-291`. Delete the notification `database_id` comparison | `test_replay_rejects_a_tampered_notification_database_id` and the notification leftover tampers | 5 |
| CI-4 delete the accent and sample pair check | `notion_aesthetics.py:299-300`. Delete `accents != record.accents or samples != record.samples` | `test_replay_rejects_a_tampered_accent_block_id` | 1 |
| drop `navigation_block_id` from both hub tuples | `notion_aesthetics.py:279` and `:347`. Drop `navigation_block_id` from the stored tuple and from `pairs.append` | `test_replay_rejects_a_tampered_navigation_block_id` | 1 |
| delete `reject_duplicate_labels` in aesthetics `_require_pairs` | `notion_aesthetics.py:203`. Delete the `reject_duplicate_labels(names, ...)` call | `test_replay_rejects_a_duplicated_accent_token` | 1 |
| delete the variants reference strip | `notion_aesthetics.py:150`. Change `{_AESTHETICS_KEY, "variants"}` to `{_AESTHETICS_KEY}` | stored-path replay and tamper tests | 46 |
| delete `_ensure_row` `client_name` | `notion_notifications.py:1195`. Delete `or "client_name" in page.properties` | `test_ensure_row_rejects_client_name_on_an_adopted_database` | 1 |
| delete `_adopted_database` `title.type != "title"` | `notion_notifications.py:924`. Delete `or title.type != "title"` | `test_adopted_database_rejects_a_text_title` | 1 |
| delete the variants created-id comparison | `notion_variants.py:131`. Delete `_require_variant_created_ids(created, records)` | `test_replay_rejects_a_tampered_variant_page_id` | 1 |
| delete the `product_spec_id` drop | `notion_variants.py:670-671`. Delete the finish `drop_page_property` | the mass, business, and four-colour builds, stored tampers, crash-resume, and the three lying-source-flag cases | 71 |
| delete `set_duplicate_as_template` | `notion_variants.py:690-691`. Delete `set_duplicate_as_template(page.id, True)` | the same build and replay set as the spec-id drop, except the child-database crash case | 71 |
| delete `set_search_indexing` False | `notion_variants.py:692-693`. Delete `set_search_indexing(page.id, False)` | the same 71 tests as `set_duplicate_as_template` | 71 |
| delete `publish_page` | `notion_variants.py:688-689`. Delete `publish_page(page.id)` | those 71 tests, plus `test_finish_does_not_record_a_page_that_stays_indexed` and `test_empty_secret_link_after_publish_records_a_repair_job` | 73 |
| delete the variants guard | `notion_variants.py:412-413`. Delete `guard_operation(probe, OP_VARIANTS)` | `test_provider_failure_resumes_without_a_second_copy` | 1 |
| B1 replace the `_find_titled` call with `existing = None` | `notion_variants.py:345`. Replace `_find_titled(...)` with `existing = None` | provider-failure resume, unrelated titled adoption, the plan secret-link failure, and the finish-step crash cases | 20 |
| B2 delete adopt of the (Copy) page | `notion_variants.py:341`. Replace `copy = _find_copy(probe, source)` with `copy = None` | unrelated copy adoption, foreign-child adoption, the release keep test, and the drop crash steps | 25 |
| skip writing variants into created ids | `notion_progress_record.py:258-269`. Replace `if checkpoint.variants:` with `if False:`. This is the progress writer, not `build_variants` `if stored.variants:` at `notion_variants.py:99` | stored replay and stored zero-write cases | 38 |
| skip variant page and block counts | `notion_progress_record.py:303-304`. Delete `pages += len(checkpoint.variants)` and `blocks += 2 * len(checkpoint.variants)` | `test_mass_tier_publishes_one_page_per_colour` | 1 |
| B-V1 read `page.public_url` instead of `get_public_url` | `notion_variants.py:694`, inside `_finish_variant`, the call after `set_search_indexing`. Not the plan read at `:394` and not the replay read at `:786` | `test_secret_link_comes_from_get_public_url`, `test_empty_secret_link_after_publish_records_a_repair_job`, and the `get_public_url` crash step | 3 |
| B-V2 delete the colour and token tuple compare | `notion_variants.py:772-775`. Delete the `(record.name, record.token_name)` comparison | `test_replay_rejects_a_swapped_colour_token` | 1 |
| B-V2 delete the variant length check | `notion_variants.py:769-770`. Delete `len(stored.variants) != len(pairs)` | `test_replay_rejects_a_dropped_colour` | 1 |
| B3 skip the created-id validator call | `notion_variants.py:175`. Delete `require_aesthetics_created_ids(probe, created, stored)` | hub and database earlier-phase tampers and the drop-crash resume | 17 |
| B3 skip the created-id validator when variants are empty | `notion_variants.py:175`. Call `require_aesthetics_created_ids` only when `stored.variants` is set | the empty-checkpoint hub, database, and notification tampers | 9 |
| B3 move the created-id validator after `_require_saved` and `_ensure_planned` | `notion_variants.py:175`, then after `:100` and after `:106`. Delete the call in `_check_earlier_phases` and call it after `_require_saved` and after `_ensure_planned` | empty and stored leftover tampers and the drop-crash resume | 15 |
| B3 delete the aesthetics saved check before variants | `notion_variants.py:166-174`. Delete the `require_completed_aesthetics(...)` call | accent tampers, unrelated replay, and the release keep tests | 14 |
| replace the validate call with the ProductSpec uniqueness bind | `notion_variants.py:98`. Replace `_validate_earlier_phases(...)` with `_bind_earlier_phases(...)`. Separate from the release/bind swap | leftover tampers, nested children, finished-variant children, the unused-copy refusals, and shell refusals | 90 |
| swap release and the uniqueness bind inside the try | `notion_variants.py:104` and `:105`. Swap `await _release_copied_spec_ids(...)` with `_bind_earlier_phases(...)`. Validate at `:98` and the plan at `:103` still run first. Separate from the SF3 move | `test_release_provider_failure_records_a_repair_job`, the `drop_page_property` crash step, and the drop-crash resume | 5 |
| title-only adoption | `notion_variants.py:668`. Delete `_require_adoptable(...)` at the start of `_finish_variant` | `test_lying_duplicate_parent_stops_after_duplicate_page`. Killed. The plan skips `page_id == ""` at `:379`, so this check is the first one that sees the lying duplicate | 1 |
| publish-before-validate | `notion_variants.py:668` moved to just before `:694`. Move the finish `_require_adoptable` to just before the finish `get_public_url` | `test_lying_duplicate_parent_stops_after_duplicate_page`. Calls stop at exactly `["duplicate_page"]`. Killed | 1 |
| delete `_require_variant_page` after finish writes | `notion_variants.py:697`, the call in `_finish_variant` after the finish secret-link check at `:695-696`. Not the saved-path call at `:782` | `test_finish_does_not_record_a_page_that_stays_indexed` | 1 |
| move the plan step to after the first unchecked drop | `notion_variants.py:103`. Call `_collect_drop_ids` and `_release_copied_spec_ids` inside the try, then `await _plan_variants` | the zero-write refusals that must happen before any `drop_page_property`, including the three unused-copy faults | 68 |
| drop the uniqueness-after-planned-drops check | `notion_variants.py:376`. Delete `_require_unique_after_drops(probe, source, drop_ids)` | the B2 holders and `test_spec_holder_under_a_block_refuses_before_any_drop` | 6 |
| drop finished variants from the in-play set | `notion_variants.py:277`. Replace `return _colour_from_title(spec, page) is not None` with `return False` | finished-variant and titled leftover refusals | 29 |
| release checks spec-id presence instead of the value | `notion_variants.py:303`. Replace the value compare with `SPEC_ID_PROPERTY not in page.properties` | `test_non_string_spec_id_refuses_before_any_drop` | 1 |
| delete `_require_shell_copy` parent_type | `notion_variants.py:537`. Delete `page.parent_type != "workspace"` | the parent_type adoption cases, the lying duplicate, and the unpublished Blue copy | 5 |
| delete `_require_shell_copy` parent_id | `notion_variants.py:538`. Delete `page.parent_id != source.parent_id` | the wrong-parent adoption cases and the unused-copy parent fault | 5 |
| delete `_require_shell_copy` product_id | `notion_variants.py:539`. Delete the `PRODUCT_ID_PROPERTY` compare | the wrong-product-id cases and `release_shell` | 5 |
| delete `_require_shell_copy` shell block | `notion_variants.py:540`. Delete the `SHELL_BLOCK_PROPERTY` compare | the shell_block adoption cases and the unused-copy shell fault | 5 |
| delete `_has_foreign_child` inside `_require_adoptable` | `notion_variants.py:639`, the call after the spec-value compare in `_require_adoptable`. Not the call in `_refuse_titled_children` at `:320` and not the call in `_refuse_unadoptable_release` at `:656` | foreign-child and nested adoption cases that reach `_require_adoptable` | 9 |
| delete the `_require_shell_copy` call in release | `notion_variants.py:649`. Delete `_require_shell_copy(source, page)` inside `_refuse_unadoptable_release` | `test_unused_copy_holding_the_spec_id_refuses_before_any_drop` for `shell_block` and `parent_id`. Killed. The child-database case still raises at `:652` | 2 |
| delete nested child detection | `notion_variants.py:562`. Insert `return False` immediately after the `_has_nested_child` docstring | nested database and page cases, including depth-3, the spec-less copy, and the unused-copy child database | 61 |
| Q1 delete the `_has_nested_child` call inside `_has_foreign_child` | `notion_variants.py:583-584`. Delete only `if _has_nested_child(probe, page): return True` inside `_has_foreign_child` | empty-path and copy-path block children. The stored path still calls `_has_nested_child` from `_require_variant_page` | 36 |
| Q7 nest stored-path title matches that are not workspace pages | `notion_variants.py:460-463`. On the stored path, also append a non-workspace `_title_open` page to `nested_ids` | both `test_replay_refuses_a_hub_child_with_a_variant_title` cases | 2 |
| delete the stored-variants early return | `notion_variants.py:99-101`. Delete `if stored.variants: await _require_saved(...); return stored` | stored replay, the extra-workspace pins, and crash-after-checkpoint | 13 |
| ignore stored variants (`if False`) | `notion_variants.py:99`, the `build_variants` condition that gates `_require_saved` at `:100`. Not the `if stored.variants:` in `_open_variant_ids` at `:460`, and not `if checkpoint.variants:` in `notion_progress_record.py:258` | the same 13 tests as deleting the stored-variants early return | 13 |
| delete the recorded-id branch | `notion_variants.py:450-455`. Delete `if page.id in recorded:` through its `continue` | `test_recorded_variant_id_stays_open_when_the_title_changes`, `test_saved_variant_is_read_by_recorded_page_id`, and `test_replay_rejects_a_recorded_page_id_that_is_not_the_variant[decoy]`. Killed. `match="variant page does not match"` rejects the different message. Not equivalent | 3 |
| delete the `_title_open` spec-id disjunct | `notion_variants.py:445`. Delete `or holds_source_spec` | the B2 holders and `test_source_spec_id_keeps_a_retitled_page_open_until_bind` | 4 |
| replace `probe.pages.get(record.page_id)` with a title scan | `notion_variants.py:779`, inside `_require_saved`, the lookup after `for record, (colour, token) in aligned`. Not `probe.pages.get(page_id)` in `_ensure_planned` at `:416` | `test_replay_rejects_a_recorded_page_id_that_is_not_the_variant` for hub, home, and decoy | 5 |
| drop `child.id != page.id` | `notion_variants.py:571`. Delete `child.id != page.id` from the page scan in `_has_nested_child` | `test_recorded_page_may_use_its_own_id_or_block_as_parent` for self and own block. Killed. Not equivalent | 2 |
| block-parent-only nested check | `notion_variants.py:564`. Replace `parents = {page.id, *_page_block_ids(probe, page)}` with `parents = {page.id}`. Not `parents = {page.id}` in `_page_block_ids` at `:548` | accent, text, callout, and depth-3 children | 45 |
| delete the saved type guard | `notion_variants.py:780-781`. Delete `if type(page) is not NotionPage` inside `_require_saved`, after `probe.pages.get(record.page_id)`. Not the ensure guard at `:417-418` | `test_replay_rejects_a_recorded_page_id_that_is_not_the_variant[missing]`, which expects `ProductBuildError` only. Killed. Not equivalent | 1 |
| delete plan `_require_original` | `notion_variants.py:369`. Delete the plan call. The definition at `:848` and the `_require_saved` call at `:777` stay | `test_home_original_flag_refuses_before_any_write` for both flags | 2 |
| delete adoption `_require_adoptable` | `notion_variants.py:378-386`. Delete the plan loop that calls `_require_adoptable`, the missing-page check, and `_require_published_link` | finished Green tampers, the secret-link cases, the duplicate-block cases, the plan provider-failure case, and `test_plan_refuses_a_missing_adoption_before_any_write` | 27 |
| SF2 swap foreign child for nested child in titled refusal | `notion_variants.py:320`. Inside `_refuse_titled_children` only, replace `_has_foreign_child(...)` with `_has_nested_child(probe, page)`. Not the 4-space calls at `:639` and `:656` | `test_finished_green_text_block_is_refused_by_the_titled_child_check` | 1 |
| SF3 delete the bind call | `notion_variants.py:105`. Delete `_bind_earlier_phases(...)` between release and ensure | `test_bind_runs_after_release_and_before_ensure` | 1 |
| SF3 move `_ensure_planned` before the bind | `notion_variants.py:105-106`. Run `_ensure_planned` before `_bind_earlier_phases`. Separate from the release/bind swap at `:104-105` | `test_bind_runs_after_release_and_before_ensure` | 1 |
| delete the `_ensure_planned` type guard | `notion_variants.py:417-418`. Delete `if type(found) is not NotionPage` before `page = found`. Not the saved guard at `:780-781` | `test_ensure_refuses_a_missing_page_id_before_any_write` | 1 |
| delete `page.id != source.id` in `_in_play_pages` | `notion_variants.py:289`. Delete `page.id != source.id` from the in-play filter. Not the same compare in `_find_titled` at `:512` or `_find_copy` at `:526` | `test_home_retitled_as_blue_is_not_adopted` | 1 |
| delete the published secret-link pre-check | `notion_variants.py:386`. Delete `await _require_published_link(probe, found)`. The finish read at `:694` stays | `test_finished_green_missing_secret_link_refuses_before_any_write` for cleared and empty reader, and `test_plan_secret_link_provider_failure_records_a_repair_job` | 3 |
| delete the accent duplicate-block raise | `notion_variants.py:712-713`. Delete `if len(matches) > 1` in `_matching_accent`. Not the vocabulary raise at `:736-737` and not `_find_titled` at `:514` | `test_copy_with_duplicate_blocks_refuses_before_any_drop[accent]` | 1 |
| delete the vocabulary duplicate-block raise | `notion_variants.py:736-737`. Delete `if len(matches) > 1` in `_matching_vocabulary` | `test_copy_with_duplicate_blocks_refuses_before_any_drop[vocabulary]` | 1 |
| delete the drop-refusal loop | `notion_variants.py:373-375`. Delete `for page_id in drop_ids: _refuse_unadoptable_release(...)` | `test_unused_copy_holding_the_spec_id_refuses_before_any_drop` for `shell_block`, `parent_id`, and `child_db`. Killed | 3 |
| delete the copy unrecognized-child raise | `notion_variants.py:652-653`. Delete `if _has_unrecognized_child(...): raise` inside the `colour is None` branch of `_refuse_unadoptable_release` | `test_unused_copy_holding_the_spec_id_refuses_before_any_drop[child_db]`. Shell and parent still fail at `:649`. Killed | 1 |
| delete the `_require_original` definition body | `notion_variants.py:848-850`. Replace the flag check with `return` | `test_home_original_flag_refuses_before_any_write` for both flags, and `test_lying_duplicate_source_flag_refuses_at_end_of_ensure` for all three flags. Killed | 5 |
| delete the end-of-ensure `_require_original` call | `notion_variants.py:422`. Delete `_require_original(source)` after `_require_one_spec_page`. The plan call at `:369` and the saved call at `:777` stay | `test_lying_duplicate_source_flag_refuses_at_end_of_ensure` for `is_published`, `duplicate_as_template`, and `search_indexing`. Killed. Checkpoint bytes stay unchanged. Deleting only this call lets the build succeed: 29 writes when the lie sets `is_published`, 27 when it sets `duplicate_as_template`, and 27 when it sets `search_indexing`. Those write counts are not the Failed column | 3 |
| delete the finish empty-link check | `notion_variants.py:695-696`. Delete `if type(link) is not str or link == "": raise ProviderFailure(...)` after the finish `get_public_url` | `test_empty_secret_link_after_publish_records_a_repair_job`. Killed | 1 |
| delete the planned-page missing check | `notion_variants.py:381-383`. Replace `probe.pages.get(page_id)`, the `type(found) is not NotionPage` check, and `raise ProductBuildError("planned variant page is missing")` with `found = probe.pages[page_id]`. Not the ensure guard at `:416-418` | `test_plan_refuses_a_missing_adoption_before_any_write`. The mutant raises `KeyError`. Killed | 1 |
| Total | | 70 killed, 0 equivalent | 982 |

The accent and sample block-membership loop is deleted. It is not a mutation row. The release title filter is deleted. It is not a row. `_page_in_play` admits only `(Copy)` and `/ <Colour>` titles for every input. The old subscript type guard and the `found is None` disjunct stay deleted. They are not rows. The `source_spec is None` early return is deleted. It is not a row and it is not equivalent. The dead plan clauses (recorded id in `_page_in_play`, the spec-id return, and the in-play guards in `_plan_adoptions`) stay deleted.

| Item | Disposition | Reason |
|---|---|---|
| CI-1 through CI-4, navigation, aesthetics dedup, client_name, title.type | Closed | Failed counts are in the table. The W7 created-ids prose partial stays closed. |
| B-V1 secret link | Closed | Finish `get_public_url` at `notion_variants.py:694`. Failed 3. The published secret-link pre-check at `:386` is a separate killed row, Failed 3. The empty-link check at `:695-696` is a separate killed row, Failed 1. |
| B-V2 colour, token, and length | Closed | `:772-775` failed 1. `:769-770` failed 1. |
| B3 validator order | Closed | Skipping `:175` failed 17. Skipping it on an empty variants list failed 9. Moving it failed 15. Deleting `:166-174` failed 14. |
| B1 and B2 adoption | Closed | `_find_titled` at `:345` failed 20. `_find_copy` at `:341` failed 25. |
| Validate, release/bind swap, plan order | Closed | Replacing validate at `:98` failed 90. Swapping `:104` and `:105` failed 5. Moving the plan at `:103` failed 68. Dropping uniqueness at `:376` failed 6. |
| Plan adoption gate | Closed | Deleting the plan `_require_adoptable` loop at `:378-386` failed 27. Deleting plan `_require_original` at `:369` failed 2. The secret-link pre-check at `:386` failed 3. The planned-page missing check at `:381-383` failed 1. |
| Title-only finish check | Closed | `:668`. Failed 1. `test_lying_duplicate_parent_stops_after_duplicate_page`. The plan skips `page_id == ""`. |
| Publish-before-validate | Closed | Moving `:668` to just before `:694`. Failed 1. The same test. Calls stop at `["duplicate_page"]`. |
| Release `_require_shell_copy` | Closed | `:649`. Failed 2. Unused `(Copy)` with a bad shell or a bad parent. |
| Drop-refusal loop and copy child | Closed | `:373-375` failed 3. `:652-653` failed 1. |
| `_require_original` definition | Closed | `:848-850`. Failed 5. The saved call at `:777` remains the one W9 survivor site of this check. The end-of-ensure call at `:422` is killed, Failed 3. |
| Finish empty link | Closed | `:695-696`. Failed 1. A `ProviderFailure` records a repair job. |
| `child.id != page.id` | Closed | `notion_variants.py:571`. Failed 2. A recorded page may use its own id or its own block id as `parent_id`. Not equivalent. |
| Saved type guard | Closed | `notion_variants.py:780-781`. Failed 1. The missing-id replay expects `ProductBuildError` only. Not equivalent. |
| Recorded-id branch | Closed | `:450-455`. Failed 3. `match="variant page does not match"` kills the message change. Not equivalent. |
| Ensure type guard, source exclusion | Closed | `:417-418` failed 1. `_in_play_pages` `:289` failed 1. |
| End-of-ensure `_require_original` | Closed | `:422`. Failed 3. `test_lying_duplicate_source_flag_refuses_at_end_of_ensure`. A lying `duplicate_page` changes a source flag after the plan call. Checkpoint bytes stay unchanged. Not equivalent. |
| Planned-page missing check | Closed | `:381-383`. Failed 1. `test_plan_refuses_a_missing_adoption_before_any_write`. Adapter `calls == []`. Not the ensure guard at `:416-418`. |
| `source_spec is None` early return | Deleted | Was `:331-332`. No current test; probes differ only in refusal message, never in writes or acceptance. A home spec that is missing, None, `"None"`, or `""` is refused earlier on both versions. Not a row. Not equivalent. |
| Duplicate blocks | Closed | Accent `:712-713` failed 1. Vocabulary `:736-737` failed 1. |
| SF2 and SF3 | Closed | The titled-child swap at `:320` failed 1. Deleting the bind at `:105` failed 1. Moving ensure before the bind failed 1. |
| Title compare `page.title != _variant_title` | Closed earlier | `notion_variants.py:801`. Killed by `test_recorded_variant_id_stays_open_when_the_title_changes`. Not a W9 survivor. |
| Release title filter | Deleted | Was `:305-306`. `_page_in_play` already admits only `(Copy)` and `/ <Colour>` for every input. Not a row. |
| Old subscript type guard and `found is None` | Deleted | The subscript guard was unreachable. `probe.pages[page_id]` is a `NotionPage`. The adoption lookup now uses `.get` (`:381-383`), which is a killed row. Find cannot return None while the source still holds the string spec id and is excluded from `drop_ids`. |
| Single writer through `write_checkpoint` | Closed | `test_write_checkpoint_is_the_only_progress_writer` still passes. |
| Refused rebuild | Closed | Zero Notion writes. One `write_checkpoint`, appending one `rebuild_refused` job. |
| A08 commissioning | Closed as not done | `commissioned_agents` stays `[]`. A08 stays DESIGNED. `variant_builder_implemented` stays false. |
| Adopted-page drift | Intended repair | Unpublished, template, indexing, icon, and cover drift on an adopted page is repaired by `_finish_variant`, not refused. |
| Docstring coverage | Parked | 14.95%, measured by Eng Ops. This session did not re-measure it. |
| One home page per probe | Parked | Dashboard and hub builders still require one top-level page. |
| Deep clone of databases | Parked | Rejected. `duplicate_page` is shallow. |
| Provenance beyond title and copyable shell fields | Parked | Not a proven lineage. Live wave. |
| Extra workspace `/ Blue` on replay | Parked | Passes even with a nested child. A different-id forgery is rejected at `:779`. |
| Database under a hub or home block | Parked | Parents at `:564`, walk at `:545`. Reviewer measured 29 empty-path writes. Not re-measured. |
| `NotionDatabase` subclass check | Parked | `type(database) is NotionDatabase` at `:566`. |
| Unpublished after a crash | Parked | The crash matrix at `:2489` does not assert the page stays unpublished. |
| W9 must-fix survivors | Parked | 13 items and 14 sites, named in `NEXT_SESSION.md`. Item 6 is the two `reject_duplicate_labels` calls. The definition of `_require_original`, the end-of-ensure call, and the finish empty-link check are killed. The `source_spec is None` guard is deleted. The saved-path call at `:777` remains the one survivor site of `_require_original`. |
| QA, fact ledger, workflow, commissioning | Parked | Narrative next phase is `qa` (A09), not started. |

## 2026-10-06 — Session 07 W7: progress and repair

Session 07 stays incomplete. This wave is not SESSION_07 COMPLETE. State revision 54 → 55. `current_session` stays 7. `completed_sessions` stays `[0, 1, 2, 3, 4, 5, 6]`. `next_session` stays 7. `next_prompt` stays `10_SESSION_07_PRODUCT_BUILD_VARIANTS_AND_QA.md`. `head_sha` is the W6 squash `3f0a30a8e52b183f10799128d4fd7b17c1b74495`. `evidence_closure_commit_sha` stays the Session 06 closure tip `0f94d585f23d79e5ac18479f01e14f67cbaad332`. `last_verified_commit` stays bootstrap `1abf0d7cca3a6b8cd7efcd0a45523538fd5bfd9d`. `updated_at` is `2026-10-06T03:44:56Z`.

Twelve session 7 evidence keys stay false. No session exit code is recorded. A07, A08, and A09 stay DESIGNED. `commissioned_agents` stays empty. Exit 78 scheduler stays HELD.

One typed progress record (`notion_progress.py`, written only by `notion_progress_record.write_checkpoint`) stores completed operations, deferred operations, created Notion ids, property mappings, page counts, and formula state for all six build phases. `write_document` is called from `write_checkpoint` and from nowhere else. `record_provider_failure` and `append_refused_rebuild` both go through `write_checkpoint`. A missing prior record is an error and writes nothing: a provider failure with no file raises and the record file stays absent. A recoverable `ProviderFailure` against an existing record appends one repair job and does not advance `checkpoint_names`. A failure leaves a repair job only when a prior record exists. A first phase-1 failure with no record raises and writes no job and no file (notion_progress.py:248), which narrows prompt §6's 'create a repair job'. The fixture has no screenshots, so the job kind is `provider_response`. A job whose kind is `screenshot` is forged. A record with no `progress` key fails closed with "progress record is missing".

The integrity digest covers the whole checkpoint payload, excluding `record_digest` itself. It detects accidental corruption. It is not a signature and it is not tamper-proof against someone who can recompute it. A recomputed digest is accepted by design. Keyed HMAC for the live-credentials wave is parked.

A refused rebuild makes zero Notion writes: no page, database, or block create, no marker strip, no icon or cover change, and nothing on the adapter. It writes the checkpoint exactly once, through `write_checkpoint`, appending exactly one repair job with kind `rebuild_refused` and a reason that names the later-phase objects it found. Every other field of the record is byte-identical. The integrity digest covers the whole payload, so it is recomputed. That recomputed digest is the only other permitted difference. `test_refused_rebuild_appends_one_job_and_writes_no_fixture_objects` keeps workspace page, database, and block counts unchanged, records zero adapter write calls, and diffs the old and new records down to the appended repair job plus the recomputed digest.

A phase-1-only record (no later-phase objects) rebuilds in place on the same page and continues through phase 6 for both the mass and business specs: exactly one top-level page and exactly one catalogue. Later phases on a refused record raise and do not write again. Checkpoint `next_phase` stays `build_phases_complete`. The narrative next phase is variants (A08) and it is not started.

O1, O7, O8, and O9 were named in the W6 verifier/reviewer notes and were not defined there as source edits. This wave defines them as `_repairable_catalogue` edits: O1 deletes the `len(properties) >= len(schema.properties)` guard (`notion_shared_databases.py:333`); O7 skips `found.type != expected.type` (`notion_shared_databases.py:342`); O8 skips `found.config != _property_config(...)` (`notion_shared_databases.py:344`); O9 drops `database.icon is not None` (`notion_shared_databases.py:335`).

Prompt-integrity review: `docs/control/reviews/2026-10-05-session-07-prompt-integrity.md` (Wave 7 addendum). A recomputed digest is accepted. Legacy progress files with no progress fail closed. Product-build tests: 211 passed across the progress file and the six phase files. Full local pytest: 2171 collected, 1966 passed, 193 skipped, 12 failed. The 12 failures are `test_compose_preserves_the_postgres_password` with `FileNotFoundError` for the `docker` binary. `ruff format --check` and `ruff check` are clean. `pyright` 1.1.411 (`uv.lock` and CI) reports 0 errors on the changed modules with SQLAlchemy 2.0.52. A local SQLAlchemy 2.1.3 install reported 2 errors in `persistence/repositories/_base.py`; those are outside this wave and are absent on 2.0.52.

Mutation checks. 47 mutations were each applied, the owning test files were run, and the edit was reverted. 47 were killed. A row is killed only when at least one test failed. The Failed column is the real pytest failure count for that mutant. The Failed column sums to 97.

| Mutation | Site | Failing tests | Failed |
|---|---|---|---|
| O1 drop `len(properties) >= len(schema.properties)` | `notion_shared_databases.py:333` | `test_full_catalogue_plus_junk_column_cannot_be_repaired` | 1 |
| O7 skip `found.type != expected.type` | `notion_shared_databases.py:342` | `test_wrong_catalogue_type_cannot_be_repaired` | 1 |
| O8 skip `found.config != _property_config(...)` | `notion_shared_databases.py:344` | `test_wrong_catalogue_options_cannot_be_repaired` | 1 |
| O9 drop `database.icon is not None` | `notion_shared_databases.py:335` | `test_catalogue_icon_cannot_be_repaired` | 1 |
| Notification repair ignores a junk icon | `notion_notifications.py:1069` | `test_notification_junk_icon_cannot_be_repaired` | 1 |
| `sample_content` appends `client_` + `name` | `notion_aesthetics.py:75` | `test_mass_tier_adds_palette_accents_and_sample_hub_text` | 1 |
| Phase-1 source contains `ETSY` | `notion_product_builder.py:527` | `test_phase_one_module_does_not_name_a_live_client`, `test_shared_databases_module_does_not_name_a_live_client` | 2 |
| Shared-database source contains `ETSY` | `notion_shared_databases.py:488` | `test_shared_databases_module_does_not_name_a_live_client` | 1 |
| Dashboard source contains `ETSY` | `notion_dashboard.py:625` | `test_dashboard_module_does_not_name_a_live_client` | 1 |
| Hubs source contains `ETSY` | `notion_hubs.py:853` | `test_hubs_module_does_not_name_a_live_client_or_later_phase` | 1 |
| Notification source contains `ETSY` | `notion_notifications.py:1230` | `test_notification_module_does_not_name_a_live_client` | 1 |
| Aesthetics source contains `ETSY` | `notion_aesthetics.py:507` | `test_aesthetics_module_does_not_name_a_live_client` | 1 |
| Skip `_require_contents` | `notion_aesthetics.py:362` | `test_phase6_resume_rejects_tampered_accent_content` | 1 |
| Buyer check is the literal `Buyer` only | `notion_notifications.py:702` | `test_buyer_placeholder_variants_write_nothing` (7 parameter rows) | 7 |
| Junk and Buyer checks run after formula writes | `notion_notifications.py:784` | the 7 Buyer rows plus `test_junk_notification_database_writes_nothing` | 8 |
| Hub icon/cover window is not resumed | `notion_aesthetics.py:606` | `test_hub_icon_cover_crash_resumes` | 1 |
| Notification icon/cover window is not resumed | `notion_notifications.py:762` | `test_notification_icon_cover_crash_resumes` | 1 |
| Provider failure writes no repair job | `notion_progress.py:233` | shared, dashboard, hub, notification, and aesthetics resume tests, `test_phase1_rebuild_failure_records_a_repair_job`, plus `test_provider_failure_with_no_prior_record_leaves_the_file_absent` | 7 |
| Unrecoverable phase 1 does not rebuild | `notion_product_builder.py:208` replace `guard_operation(probe, OP_REBUILD)` with a raise | `test_unrecoverable_phase1_rebuilds_in_place_and_later_phases_do_not`, `test_phase1_only_rebuild_continues_through_phase_6` (mass and business), `test_phase1_rebuild_failure_records_a_repair_job` | 4 |
| Any phase-1 failure rebuilds the product | `notion_product_builder.py:178` | `test_phase1_page_failure_resumes_without_rebuilding_prior_ids`, `test_phase1_shell_failure_keeps_the_page_and_adds_one_block` | 2 |
| Screenshot evidence kind is accepted | `notion_progress.py:49` | `test_screenshot_kind_is_forged` | 1 |
| Progress digest is not checked | `notion_progress.py:329` | `test_forged_and_tampered_progress_records_are_rejected`, `test_payload_edit_with_a_stale_digest_is_forged`, `test_forged_unrecoverable_flag_with_a_stale_digest_does_not_rebuild` | 3 |
| Sample marker is not required | `notion_notifications.py:622` | `test_sample_marker_tamper_is_not_overwritten` | 1 |
| No-prior-record writes a file | `notion_progress.py:248` | `test_provider_failure_with_no_prior_record_leaves_the_file_absent` | 1 |
| `write_document` called outside `write_checkpoint` | `notion_progress_record.py:156` | `test_write_checkpoint_is_the_only_progress_writer` | 1 |
| Missing progress key is accepted | `notion_progress.py:163` | `test_deleted_progress_key_is_rejected` | 1 |
| Alignment is not checked | `notion_progress.py:370` | `test_progress_alignment_with_checkpoint_names_is_required` | 1 |
| Refused rebuild still rebuilds | `notion_product_builder.py:203` | `test_refused_rebuild_appends_one_job_and_writes_no_fixture_objects` | 1 |
| Phase 1 always creates a page | `notion_product_builder.py:166` | phase-1 create and shell-failure tests | 8 |
| Dashboard always adds a greeting | `notion_dashboard.py:449` | dashboard failure and replay tests | 2 |
| Hubs always add a child page | `notion_hubs.py:669` | hub failure and replay tests | 2 |
| Notification always creates a database | `notion_notifications.py:791` | notification failure and replay tests | 3 |
| Shared databases always create | `notion_shared_databases.py:419` | shared-database failure and replay tests | 3 |
| Aesthetics always add accents | `notion_aesthetics.py:564` | aesthetics failure and replay tests | 3 |
| Page counts are zero | `notion_progress_record.py:258` | `test_phase1_only_rebuild_continues_through_phase_6` (mass and business) | 2 |
| Buyer mapping is omitted | `notion_progress_record.py:235` | `test_phase1_only_rebuild_continues_through_phase_6` (mass and business) | 2 |
| Formula state is empty | `notion_progress_record.py:263` | `test_phase1_only_rebuild_continues_through_phase_6` (mass and business) | 2 |
| Saved row allows `client_name` | `notion_notifications.py:645` | `test_saved_notification_rejects_loose_adopt_fields_and_client_name` | 1 |
| Saved database skips title type | `notion_notifications.py:480` | `test_saved_notification_rejects_loose_adopt_fields_and_client_name` | 1 |
| Saved database skips buyer config | `notion_notifications.py:489` | `test_saved_notification_rejects_loose_adopt_fields_and_client_name` | 1 |
| Saved database skips icon | `notion_notifications.py:471` | `test_saved_notification_rejects_loose_adopt_fields_and_client_name` | 1 |
| Sample marker is not moved last | `notion_notifications.py:1034` | `test_sample_marker_column_is_moved_to_the_end` | 1 |
| Sample marker is not last on resume | `notion_shared_databases.py:287` delete `not marker_last` | `test_sample_marker_not_last_is_rejected_on_resume` | 1 |
| Created database ids are emptied | `notion_progress_record.py:183` `created["databases"] = []` | `test_phase1_only_rebuild_continues_through_phase_6` (mass and business), aesthetics `test_replay_keeps_the_same_checkpoint_bytes_and_ids` | 3 |
| Created hub ids are emptied | `notion_progress_record.py:189` `created["hubs"] = []` | `test_phase1_only_rebuild_continues_through_phase_6` (mass and business), aesthetics `test_replay_keeps_the_same_checkpoint_bytes_and_ids` | 3 |
| Created notion ids field is emptied | `notion_progress_record.py:225` `return empty_created_ids()` | `test_phase1_only_rebuild_continues_through_phase_6` (mass and business), aesthetics `test_replay_keeps_the_same_checkpoint_bytes_and_ids` | 3 |
| Rebuild guard is deleted | `notion_product_builder.py:208` delete `guard_operation(probe, OP_REBUILD)` | `test_phase1_rebuild_failure_records_a_repair_job` | 1 |

Should-fix dispositions for the Reviewer #56 list:

| Item | Disposition | Reason |
|---|---|---|
| One progress record / six checkpoint writers | Closed | `write_checkpoint` is the only caller of `write_document`. `test_write_checkpoint_is_the_only_progress_writer` is the grep guard. A provider failure with no prior record raises and the file stays absent. |
| Integrity digest | Closed | The digest covers the whole payload. It detects accidental corruption. It is not a signature and it is not tamper-proof against someone who can recompute it. A recomputed digest is accepted by design. Skipping the comparison killed 3 tests. |
| Phase-6 resume tamper tests | Closed | `test_phase6_resume_rejects_tampered_accent_content`. Skipping `_require_contents` failed 1 test. |
| `_repairable_catalogue` gaps | Closed | Full catalogue plus junk, wrong type, wrong options, and a junk icon each fail and leave bytes unchanged. |
| #55 re-parent | Closed | `test_reparented_design_shell_is_not_rebuilt`. |
| #55 forged business checkpoint | Closed | `test_forged_business_events_relation_is_rejected`. |
| #55 `_require_pairs` duplicates | PARTIAL | Deleting `reject_duplicate_labels(names, ...)` in aesthetics `_require_pairs` (`notion_aesthetics.py:198`) survived. The notification call at `notion_notifications.py:266` is killed by `test_duplicate_notification_relation_is_rejected`. |
| Block-count delta | Closed | Each phase injects the failure after at least one object exists. Resume asserts zero new objects for operations that had already completed, and the id of that completed object stays stable. |
| CI runner pin | Closed | `ci.yml`, `release.yml`, and `e2e.yml` use `ubuntu-24.04`. |
| Mutation-log failure counts | Closed | The table above records the real pytest failure count for each mutant. 47 killed rows. The Failed column sums to 97. |
| Loose adopt checks on the saved path | Closed | `_database_ok` title type (`notion_notifications.py:480`), Buyer name config `{}` (`:489`), and icon (`:471`) each killed 1. `_row_ok` rejects `client_name` (`:645`) and that mutant killed 1. |
| `_view_matches` dedupe | Closed | `notion_linked_views.view_matches`. Dashboard and hubs call it. |
| `_one_workspace` / `_workspace_id` dedupe | Closed | `require_workspace_id` in `notion_product_builder.py`. The dashboard calls it. |
| Notification `_ensure` ordering | Closed | Junk-database and Buyer checks run before any write. Moving them after formula writes failed 8 tests. |
| Icon/cover stuck windows | Closed | Hub `set_icon` then `set_cover`, and the notification database icon then cover, both resume. Dropping either branch failed 1 test. |
| `sample_marker` resume | Closed | Deleting `not marker_last` in `_schema_matches` (`notion_shared_databases.py:287`) failed `test_sample_marker_not_last_is_rejected_on_resume` (1). The column move at `notion_notifications.py:1034` is a separate killed row. |
| Buyer variants | Closed | `BUYER`, ` Buyer `, `buyer name`, `client`, `{{buyer}}`, `[buyer]`, `<buyer>`. Narrowing the check to the literal `Buyer` failed 7 tests. |
| Repair-path mutants O1, O7, O8, O9 | Closed | Defined above. Each killed 1 test. |
| Sample text excludes `client_name` | Closed | The aesthetics test compares the literal sample string and asserts `client_name` is absent. Appending `client_` + `name` failed 1 test. |
| Case-insensitive source bans | Closed | All six module ban lists use `casefold`. Inserting `ETSY` failed the owning ban test in each module. |
| Fixture-only shortcuts | Parked | The fixture stores values on `page.properties`. It has no separate property-value write. The zero-write test wraps the adapter methods that do exist. |
| Fixed `SAMPLE_DATE` | Parked | `SAMPLE_DATE` stays `"2026-10-06"`. This wave did not replace that constant with a clock. |
| CodeRabbit docstring coverage | Parked | Not remeasured this wave. |
| Nav as a page link | Parked | Fixture blocks are paragraph and callout only. Navigation stays paragraph text. |
| One home page per probe | Parked | `notion_dashboard.py:275` rejects a probe with more than one page. `notion_hubs.py:494` requires the only top-level page to be the home page. The phase-1 rebuild stays on that page. |
| `_ensure_row` `client_name` disjunct | PARTIAL | Removing `"client_name" in page.properties` from `_ensure_row` (`notion_notifications.py:1179`) failed 0 tests. The saved-row check in `_row_ok` is the killed row. |
| `_adopted_database` title type | PARTIAL | Removing `title.type != "title"` from `_adopted_database` (`notion_notifications.py:908`) failed 0 tests. Buyer-config and icon on that adopt function were not separately measured. |
| Keyed HMAC | Parked | Keyed HMAC waits for the live-credentials wave. A recomputed integrity digest is accepted by design until then. |
| S04–S06 nits | Parked | Unchanged from prior waves. |

PARTIAL, still named: deleting `reject_duplicate_labels(names, ...)` in aesthetics `_require_pairs` (`notion_aesthetics.py:198`); `_ensure_row` `client_name` at `notion_notifications.py:1179`; `_adopted_database` title type at `notion_notifications.py:908`; skipping _require_created_ids or any of its checks (CI-1..CI-4) survives; phase-6 replay test with tampered created_notion_ids is a W8 must-fix.

## 2026-10-06 — Session 07 W6: fixture aesthetics and content completion

Session 07 stays incomplete. This wave is not SESSION_07 COMPLETE. State revision 53 → 54. `current_session` stays 7. `completed_sessions` stays `[0, 1, 2, 3, 4, 5, 6]`. `next_session` stays 7. `next_prompt` stays `10_SESSION_07_PRODUCT_BUILD_VARIANTS_AND_QA.md`. `head_sha` moves to the post-merge W5 tip `0793e73147c0a3e50b6e27be2c74d3084ab1bfd5`. `evidence_closure_commit_sha` stays the Session 06 closure tip `0f94d585f23d79e5ac18479f01e14f67cbaad332`: an incomplete session may record a later `head_sha`, and this wave is not the completion candidacy that would move the closure SHA. `last_verified_commit` stays bootstrap `1abf0d7cca3a6b8cd7efcd0a45523538fd5bfd9d`. `updated_at` is `2026-10-06T03:00:00Z`.

Twelve session 7 evidence keys stay false. No session exit code is recorded. A07, A08, and A09 stay DESIGNED. `commissioned_agents` stays empty.

Aesthetics and content completion only, in `notion_aesthetics.py`, resuming the notification-dashboard checkpoint on an exact `FixtureNotionAdapter` from an exact `product_spec.ProductSpec`. The home page gains one callout per palette token. Each hub page gains one text block that starts with `SAMPLE` and uses that hub's name and description. Hub icon and cover are set from the palette token. The home page icon and cover from the dashboard phase are left as stored. Sample rows stay marked SAMPLE. A second call keeps the same checkpoint bytes and ids. A missing notification checkpoint is an error and nothing is rebuilt. `next_phase` is `build_phases_complete`. This is the last `BUILD_PHASES` entry. Variants, QA, the fact ledger, and the workflow link are not started.

The hashed view-name token is `sha256` of the full UTF-8 name, first 8 hex characters, at `notion_hubs.py:161`. A `hash()` substitute and an `id()` substitute both fail. A long-name replay keeps the same bytes and view ids. Design-shell resume requires the icon: missing shell says `is missing` (`notion_dashboard.py:318`, `notion_product_builder.py:335`); content or icon mismatch says `does not match` (`notion_dashboard.py:319`, `notion_product_builder.py:336`). The dead notification reference-length check is gone; the remaining guard is `notion_notifications.py:181`.

Shared database titles are looked up on the parent page (`notion_shared_databases.py:239`). A proper catalogue prefix is repaired in place (`notion_shared_databases.py:425`). A non-prefix schema raises `shared database schema cannot be repaired`. Notification formula prefixes are completed and the sample marker stays last (`notion_notifications.py:752`). A proper notification-database prefix is repaired in place (`notion_notifications.py:670`); junk raises `notification database cannot be repaired`. `sample_marker` is a select column (`notion_notifications.py:891`). Sample rows store catalogue values (`notion_notifications.py:902`). Buyer name on the saved row and on an existing row must equal the ProductSpec identity (`notion_notifications.py:619`, `notion_notifications.py:1046`). Hub names longer than 64 characters are rejected (`notion_hubs.py:209`). `filter_pairs` and `create_named_linked_view` live in `notion_linked_views.py`. That dedupe is partial: `_view_matches` and `_one_workspace` / `_workspace_id` are still duplicated, and six checkpoint writers remain. A deleted hub section block is an error (`notion_hubs.py:763`). Published pages are rejected in phase 1 (`notion_product_builder.py:259`, `notion_product_builder.py:331`). A missing checkpoint file stays absent: each later phase asserts that after the error (`notion_aesthetics.py:103`, `notion_notifications.py:145`, `notion_dashboard.py:183`, `notion_hubs.py:260`, `notion_shared_databases.py:129`). Phase 1 already asserts that in `test_existing_published_page_is_rejected` (`notion_product_builder.py:372`).

Prompt-integrity review: `docs/control/reviews/2026-10-05-session-07-prompt-integrity.md` (Wave 6 addendum). Focused tests, re-run on this fix: 242 passed, 1 skipped across the aesthetics, notification, hubs, dashboard, shared-database, phase-1, prompt-integrity, and control-state files. The skip is the pre-existing case-variant control-state case on this case-sensitive filesystem. Full local pytest: 2125 collected, 1920 passed, 193 skipped, 12 failed. The 12 failures are `test_compose_preserves_the_postgres_password` with `FileNotFoundError` for the `docker` binary. They are outside this wave's files. `ruff format --check`, `ruff check`, and `pyright` are clean.

Mutation checks. The prior wave applied 21 mutations; each owning test failed and each edit was reverted. Those 21 were not re-run on this fix. This fix re-applied 12 missing-checkpoint writes on the `if not path.exists()` branch: write `{}` plus a newline and then raise the same `ProductBuildError`, and write `{}` plus a newline and then fall through. Each of the 12 failed the owning test (pytest exit 1, one failed) and was reverted. The earlier row that recorded a missing-checkpoint empty-object write at `notion_aesthetics.py:104` as killed was wrong: that write survived until the post-raise absence assert. 33 rows: 21 from the prior wave, 12 from this fix.

| Mutation | Site | Failing test |
|---|---|---|
| Skip aesthetics replay return | `notion_aesthetics.py:95` | `test_replay_keeps_the_same_checkpoint_bytes_and_ids` |
| Sample text drops SAMPLE | `notion_aesthetics.py:66` | `test_mass_tier_adds_palette_accents_and_sample_hub_text` |
| Drop the last palette accent | `notion_aesthetics.py:463` | `test_mass_tier_adds_palette_accents_and_sample_hub_text` |
| next_phase stays the phase name | `notion_aesthetics.py:225` | `test_mass_tier_adds_palette_accents_and_sample_hub_text` |
| Hub icon ignores the token | `notion_aesthetics.py:71` | `test_mass_tier_adds_palette_accents_and_sample_hub_text` |
| Hub cover ignores the token | `notion_aesthetics.py:76` | `test_mass_tier_adds_palette_accents_and_sample_hub_text` |
| View token uses hash() | `notion_hubs.py:161` | `test_linked_view_name_token_is_the_sha256_prefix` |
| View token uses id() | `notion_hubs.py:161` | `test_linked_view_name_token_is_the_sha256_prefix` and `test_long_view_name_replay_keeps_the_same_bytes_and_ids` |
| Drop the dashboard shell icon check | `notion_dashboard.py:319` | `test_icon_only_design_shell_tamper_is_not_rebuilt` |
| Drop the phase-1 shell icon check | `notion_product_builder.py:336` | `test_icon_only_design_shell_tamper_is_not_rebuilt` |
| Database title lookup is probe-global | `notion_shared_databases.py:239` | `test_foreign_tasks_database_does_not_collide` |
| Catalogue prefix is not repaired | `notion_shared_databases.py:425` | `test_catalogue_prefix_is_repaired_in_place` |
| sample_marker column is not added | `notion_notifications.py:891` | `test_mass_tier_builds_one_notification_row` |
| Sample values are not filled | `notion_notifications.py:902` | `test_mass_tier_builds_one_notification_row` |
| Formula prefix is not completed | `notion_notifications.py:752` | `test_formula_prefix_is_completed_and_keeps_the_first_id` |
| Notification database prefix is not repaired | `notion_notifications.py:670` | `test_notification_database_prefix_is_repaired_in_place` |
| Existing-row Buyer name is not checked | `notion_notifications.py:1046` | `test_buyer_name_placeholder_on_an_existing_row_is_not_overwritten` |
| Saved Buyer name is not checked | `notion_notifications.py:619` | `test_buyer_name_placeholder_is_rejected_on_resume` |
| Hub name length is not enforced | `notion_hubs.py:209` | `test_hub_name_longer_than_64_characters_creates_nothing` |
| Existing published page is accepted | `notion_product_builder.py:259` | `test_existing_published_page_is_rejected` |
| Checkpoint published page is accepted | `notion_product_builder.py:331` | `test_published_checkpoint_page_is_not_rebuilt` |
| Missing aesthetics checkpoint writes `{}` then raises | `notion_aesthetics.py:103` | `test_missing_checkpoint_creates_nothing` |
| Missing aesthetics checkpoint writes `{}` then falls through | `notion_aesthetics.py:103` | `test_missing_checkpoint_creates_nothing` |
| Missing notification checkpoint writes `{}` then raises | `notion_notifications.py:145` | `test_missing_checkpoint_creates_nothing` |
| Missing notification checkpoint writes `{}` then falls through | `notion_notifications.py:145` | `test_missing_checkpoint_creates_nothing` |
| Missing dashboard checkpoint writes `{}` then raises | `notion_dashboard.py:183` | `test_missing_checkpoint_creates_nothing` |
| Missing dashboard checkpoint writes `{}` then falls through | `notion_dashboard.py:183` | `test_missing_checkpoint_creates_nothing` |
| Missing hubs checkpoint writes `{}` then raises | `notion_hubs.py:260` | `test_missing_checkpoint_creates_nothing` |
| Missing hubs checkpoint writes `{}` then falls through | `notion_hubs.py:260` | `test_missing_checkpoint_creates_nothing` |
| Missing shared-database checkpoint writes `{}` then returns None | `notion_shared_databases.py:129` | `test_missing_checkpoint_does_not_create_databases` |
| Missing shared-database checkpoint writes `{}` then falls through | `notion_shared_databases.py:129` | `test_missing_checkpoint_does_not_create_databases` |
| Missing phase-1 checkpoint writes `{}` then returns None | `notion_product_builder.py:372` | `test_existing_published_page_is_rejected` |
| Missing phase-1 checkpoint writes `{}` then falls through | `notion_product_builder.py:372` | `test_existing_published_page_is_rejected` |

Exit 78 scheduler stays HELD. Linked-view helper dedupe is PARTIAL: `_view_matches` and `_one_workspace` / `_workspace_id` are still duplicated, and six checkpoint writers remain. Partial notification-database repair is PARTIAL: the prefix repair works, and `_ensure` still writes before the junk-database and Buyer checks. Notification tamper and parser tests are PARTIAL. Parked for the next wave: navigation stays paragraph text because the fixture has paragraph and callout blocks and no page-link block; dashboard build still rejects a probe with more than one page (`notion_dashboard.py:279`); hub build still requires exactly one top-level page (`notion_hubs.py:484`, `notion_hubs.py:510`); S04–S06 nits; CodeRabbit docstring coverage at 10.88% (W6, stale; not remeasured); notification `_ensure` writing before the junk-database and Buyer checks; loose adopt checks (`_adopted_database` / `_database_ok`); the stuck window between `set_icon` and `set_cover`, and the notification-database icon/cover window; the `sample_marker` resume test, Buyer variants, and repair-path mutants.

## 2026-10-06 — Session 07 W5: tip-sync and fixture notification dashboard

Session 07 stays incomplete. This wave is not SESSION_07 COMPLETE. State revision 52 → 53. `current_session` stays 7. `completed_sessions` stays `[0, 1, 2, 3, 4, 5, 6]`. `next_session` stays 7. `next_prompt` stays `10_SESSION_07_PRODUCT_BUILD_VARIANTS_AND_QA.md`. `head_sha` moves to the post-merge W4 tip `91a33eba7961ea2819dcc695f73ffe9a45e37b33`. `evidence_closure_commit_sha` stays the Session 06 closure tip `0f94d585f23d79e5ac18479f01e14f67cbaad332`: an incomplete session may record a later `head_sha`, and this wave is not the completion candidacy that would move the closure SHA. `last_verified_commit` stays bootstrap `1abf0d7cca3a6b8cd7efcd0a45523538fd5bfd9d`. `updated_at` is `2026-10-06T00:30:00Z`.

Twelve session 7 evidence keys stay false, including `notification_dashboard_built`, `identity_hubs_built`, `home_dashboard_built`, `product_build_tests_pass`, `control_files_and_checkpoint_current`, and `evidence_closure_commit_recorded`. No session exit code is recorded. A07, A08, and A09 stay DESIGNED. `commissioned_agents` stays empty.

Notification dashboard only, in `notion_notifications.py`, resuming the checkpoint `top_level_page_and_design_shell` + `shared_databases` + `dashboard_and_navigation` + `identity_specific_hubs` on an exact `FixtureNotionAdapter` from an exact `product_spec.ProductSpec`. One database, title `Notification dashboard`, holds one buyer row. Buyer name is the ProductSpec identity. Current date is the formula `now()`. Open tasks due today are always present. Birthday status, money spent today, and water glasses remaining appear only when that catalogue database is in the tier. Sample rows are titled `SAMPLE {kind}` and carry `sample_marker` `SAMPLE`. The buyer row is not a sample and does not store `client_name`. A second call keeps the same checkpoint bytes and ids. A missing prior checkpoint object is an error and nothing is rebuilt. The checkpoint records `notification_dashboard`. The next phase is `aesthetics_and_content_completion` and this wave does not run it.

Hub view names that would exceed Notion's 64-character cap are shortened in `linked_view_name` (`notion_hubs.py:161`). The slug and an 8-character hash of the full name stay on the end, so two realistic hubs that share a 64-character prefix do not collide. The builder rejects a hub list outside six to eight before it loads a checkpoint (`notion_hubs.py:202`), including a `model_copy` that skips the field bounds. A deleted navigation block on resume is an error (`notion_hubs.py:765`). A deleted design shell (`notion_dashboard.py:318`) and a tampered design shell (`notion_dashboard.py:319`) are errors on hub resume and on notification entry, and nothing is rebuilt. The section-block delete test landed in Wave 6 (`test_deleted_section_block_on_resume_is_not_rebuilt`, `notion_hubs.py:763`).

Prompt-integrity review: `docs/control/reviews/2026-10-05-session-07-prompt-integrity.md` (Wave 5 addendum). Focused tests: 207 passed, 1 skipped across the notification, hubs, dashboard, shared-database, phase-1, prompt-integrity, and control-state files. The skip is the pre-existing case-variant control-state case on this case-sensitive filesystem. `ruff format`, `ruff check`, and `pyright` are clean on the touched paths.

Mutation checks (25 rows; each applied, the owning test file run, then reverted; 25 killed). The two design-shell rows were killed by both `test_notion_product_builder_notifications.py` and `test_notion_product_builder_hubs.py`.

| Mutation | Site | Failing test |
|---|---|---|
| Skip replay return | `notion_notifications.py:108` | `test_replay_keeps_the_same_checkpoint_bytes_and_ids` |
| Drop the buyer property | `notion_notifications.py:794` | `test_mass_tier_builds_one_notification_row` |
| Date expression becomes today() | `notion_notifications.py:69` | `test_mass_tier_builds_one_notification_row` |
| Drop the sample marker | `notion_notifications.py:778` | `test_mass_tier_builds_one_notification_row` |
| Sample title drops SAMPLE | `notion_notifications.py:774` | `test_mass_tier_builds_one_notification_row` |
| Buyer row marked SAMPLE | `notion_notifications.py:840` | `test_mass_tier_builds_one_notification_row` |
| Buyer row stores client_name | `notion_notifications.py:840` | `test_mass_tier_builds_one_notification_row` |
| Every rollup uses sum | `notion_notifications.py:984` | `test_mass_tier_builds_one_notification_row` |
| Skip the water rollup | `notion_notifications.py:984` | `test_mass_tier_builds_one_notification_row` |
| Skip the open-tasks rollup | `notion_notifications.py:984` | `test_mass_tier_builds_one_notification_row` |
| Missing checkpoint is not an error | `notion_notifications.py:138` | `test_missing_checkpoint_creates_nothing` |
| Write next_phase is the current phase | `notion_notifications.py:259` | `test_mass_tier_builds_one_notification_row` |
| Parse next_phase is the current phase | `notion_notifications.py:179` | `test_replay_keeps_the_same_checkpoint_bytes_and_ids` |
| Create a second notification row | `notion_notifications.py:839` | `test_mass_tier_builds_one_notification_row` |
| Plan always includes Events | `notion_notifications.py:129` | `test_business_tier_omits_unsupported_claims` |
| Never adopt existing formulas | `notion_notifications.py:666` | `test_existing_formulas_are_adopted` |
| Junk formula shape is ignored | `notion_notifications.py:610` | `test_junk_property_creates_no_notification_database` |
| Missing sample is ignored | `notion_notifications.py:501` | `test_deleted_sample_on_resume_is_not_rebuilt` |
| Deleted formula is ignored | `notion_notifications.py:371` | `test_deleted_formula_on_resume_is_not_rebuilt` |
| View name ignores the 64 cap | `notion_hubs.py:159` | `test_a_realistic_long_view_name_stays_unique_and_within_the_cap` |
| View name truncates without a token | `notion_hubs.py:161` | `test_a_realistic_long_view_name_stays_unique_and_within_the_cap` |
| Hub count is not enforced | `notion_hubs.py:196` | `test_fewer_or_more_than_six_to_eight_hubs_create_nothing` |
| Deleted navigation is accepted | `notion_hubs.py:746` | `test_deleted_navigation_block_is_not_rebuilt` |
| Missing design shell is accepted | `notion_dashboard.py:318` | `test_deleted_design_shell_is_not_rebuilt` |
| Tampered design shell is accepted | `notion_dashboard.py:319` | `test_tampered_design_shell_is_not_rebuilt` |

Exit 78 scheduler stays HELD. The section-block delete test landed in Wave 6. Parked S06 nits stay parked.

## 2026-10-05 — Session 07 W4: tip-sync and fixture identity hubs

Session 07 stays incomplete. This wave is not SESSION_07 COMPLETE. State revision 51 → 52. `current_session` stays 7. `completed_sessions` stays `[0, 1, 2, 3, 4, 5, 6]`. `next_session` stays 7. `next_prompt` stays `10_SESSION_07_PRODUCT_BUILD_VARIANTS_AND_QA.md`. `head_sha` moves to the post-merge W3 tip `0f67dc92d5c4bdc105a3801ed5b5f7b517c66283`. `evidence_closure_commit_sha` stays the Session 06 closure tip `0f94d585f23d79e5ac18479f01e14f67cbaad332`: an incomplete session may record a later `head_sha`, and this wave is not the completion candidacy that would move the closure SHA. `last_verified_commit` stays bootstrap `1abf0d7cca3a6b8cd7efcd0a45523538fd5bfd9d`. `updated_at` is `2026-10-05T23:45:00Z`.

Twelve session 7 evidence keys stay false, including `home_dashboard_built`, `identity_hubs_built`, `notification_dashboard_built`, `product_build_tests_pass`, `control_files_and_checkpoint_current`, and `evidence_closure_commit_recorded`. No session exit code is recorded. A07, A08, and A09 stay DESIGNED. `commissioned_agents` stays empty.

Identity hubs only, in `notion_hubs.py`, resuming the checkpoint `top_level_page_and_design_shell` + `shared_databases` + `dashboard_and_navigation` on an exact `FixtureNotionAdapter` from an exact `product_spec.ProductSpec`. Each spec hub is one unpublished child of the dashboard. It stores two linked views of canonical databases that exist for the tier, three static sections (purpose, practice, buyer) in that product's vocabulary, and one navigation block back to the dashboard title. The mass tier can link Events. The business tier has no Events database and no Events view. A second call does not create another hub, view, or page. A missing page, database, dashboard piece, or hub piece behind the saved checkpoint is an error. The checkpoint records `identity_specific_hubs`. The next phase is `notification_dashboard` and this wave does not run it. Aesthetics, variants, QA, the fact ledger, and the workflow link are not built. No live HTTP, no real Notion workspace, no Etsy listing.

Prompt-integrity review: `docs/control/reviews/2026-10-05-session-07-prompt-integrity.md` (Wave 4 addendum). Focused tests: 115 passed across the hubs, dashboard, shared-database, phase-1, and prompt-integrity files. `ruff format`, `ruff check`, and `pyright` are clean on the touched paths.

Mutation checks (40 rows; each applied to `notion_hubs.py`, the hubs test file run, then reverted; 40 killed):

| Mutation | Site | Failing test |
|---|---|---|
| Section drops the identity | `notion_hubs.py:134` | `test_business_tier_does_not_invent_events` |
| Navigation drops the dashboard title | `notion_hubs.py:139` | `test_mass_tier_builds_identity_hubs_once` |
| View name drops the identity | `notion_hubs.py:144` | `test_mass_tier_builds_identity_hubs_once` |
| Linked view stores no filters | `notion_hubs.py:624` | `test_mass_tier_builds_identity_hubs_once` |
| Events recipe is used on every tier | `notion_hubs.py:185` | `test_business_tier_does_not_invent_events` |
| Skip resume of stored hubs | `notion_hubs.py:164` | `test_replay_does_not_create_another_hub` |
| Skip the stored database check | `notion_hubs.py:356` | `test_missing_database_is_not_rebuilt` |
| Skip the stored dashboard check | `notion_hubs.py:357` | `test_missing_dashboard_view_is_not_rebuilt` |
| Skip the single-line field check | `notion_hubs.py:178` | `test_newline_in_a_hub_description_creates_nothing` |
| Skip unique hub names | `notion_hubs.py:181` | `test_duplicate_hub_names_are_rejected` |
| Accept a published hub page | `notion_hubs.py:447` | `test_published_hub_page_is_rejected` |
| Linked view name is blank | `notion_hubs.py:623` | `test_mass_tier_builds_identity_hubs_once` |
| Next phase on write skips hubs | `notion_hubs.py:372` | `test_mass_tier_builds_identity_hubs_once` |
| Next phase on parse skips hubs | `notion_hubs.py:271` | `test_replay_does_not_create_another_hub` |
| Module names notification_dashboard | `notion_hubs.py:765` | `test_hubs_module_does_not_name_a_live_client_or_later_phase` |
| Module names publish_page | `notion_hubs.py:765` | `test_hubs_module_does_not_name_a_live_client_or_later_phase` |
| Module names create_database | `notion_hubs.py:765` | `test_hubs_module_does_not_name_a_live_client_or_later_phase` |
| Module names notion_client | `notion_hubs.py:765` | `test_hubs_module_does_not_name_a_live_client_or_later_phase` |
| Section roles drop buyer | `notion_hubs.py:62` | `test_mass_tier_builds_identity_hubs_once` |
| Resume requires three views | `notion_hubs.py:333` | `test_replay_does_not_create_another_hub` |
| Always create a hub page | `notion_hubs.py:591` | `test_matching_section_is_adopted` |
| Always create a section block | `notion_hubs.py:594` | `test_matching_section_is_adopted` |
| Junk hub block is ignored | `notion_hubs.py:511` | `test_unexpected_hub_block_is_not_rewritten` |
| A duplicate hub page is adopted | `notion_hubs.py:441` | `test_duplicate_hub_page_is_rejected` |
| Skip the ProductSpec check | `notion_hubs.py:155` | `test_catalogue_spec_and_live_probes_are_rejected` |
| Skip the fixture probe check | `notion_hubs.py:156` | `test_catalogue_spec_and_live_probes_are_rejected` |
| Skip the same-spec check | `notion_hubs.py:161` | `test_other_spec_does_not_build_hubs` |
| Accept a naive recorded_at | `notion_hubs.py:158` | `test_naive_recorded_at_leaves_the_checkpoint_unchanged` |
| Resume ignores tampered filters | `notion_hubs.py:705` | `test_tampered_hub_filter_is_not_rewritten` |
| An extra page is allowed | `notion_hubs.py:717` | `test_extra_page_on_resume_is_not_removed` |
| A missing hub page is ignored | `notion_hubs.py:655` | `test_missing_hub_page_on_resume_is_not_rebuilt` |
| Checkpoint may omit identity hubs | `notion_hubs.py:258` | `test_hubs_checkpoint_without_records_is_rejected` |
| Swapped section roles are accepted | `notion_hubs.py:327` | `test_swapped_section_roles_are_rejected` |
| Every linked view is a table | `notion_hubs.py:622` | `test_mass_tier_builds_identity_hubs_once` |
| Every hub view is created from Tasks | `notion_hubs.py:604` | `test_mass_tier_builds_identity_hubs_once` |
| Project views are tables | `notion_hubs.py:95` | `test_business_tier_does_not_invent_events` |
| Five hub records are accepted | `notion_hubs.py:279` | `test_five_hub_records_are_rejected` |
| Checkpoint omits the identity hubs key | `notion_hubs.py:739` | `test_mass_tier_builds_identity_hubs_once` |
| A phase-2 checkpoint is parsed as a dashboard | `notion_hubs.py:245` | `test_dashboard_phase_is_required` |
| Skip the home page check | `notion_hubs.py:355` | `test_missing_page_is_not_rebuilt` |

Exit 78 scheduler stays HELD. Parked S06 nits stay parked. The #51 published-page mutant, the #52 shared-database nits, and the #53 dashboard nits stay parked.

## 2026-10-05 — Session 07 W3: tip-sync and fixture dashboard

Session 07 stays incomplete. This wave is not SESSION_07 COMPLETE. State revision 50 → 51. `current_session` stays 7. `completed_sessions` stays `[0, 1, 2, 3, 4, 5, 6]`. `next_session` stays 7. `next_prompt` stays `10_SESSION_07_PRODUCT_BUILD_VARIANTS_AND_QA.md`. `head_sha` moves to the post-merge W2 tip `676fabef5bd1b36018f1d2d539d282225d860a99`. `evidence_closure_commit_sha` stays the Session 06 closure tip `0f94d585f23d79e5ac18479f01e14f67cbaad332`: an incomplete session may record a later `head_sha`, and this wave is not the completion candidacy that would move the closure SHA. `last_verified_commit` stays bootstrap `1abf0d7cca3a6b8cd7efcd0a45523538fd5bfd9d`. `updated_at` is `2026-10-05T22:30:00Z`.

Twelve session 7 evidence keys stay false, including `shared_databases_built`, `home_dashboard_built`, `notification_dashboard_built`, `product_build_tests_pass`, `control_files_and_checkpoint_current`, and `evidence_closure_commit_recorded`. No session exit code is recorded. A07, A08, and A09 stay DESIGNED. `commissioned_agents` stays empty.

Home dashboard only, in `notion_dashboard.py`, resuming the checkpoint `top_level_page_and_design_shell` + `shared_databases` on an exact `FixtureNotionAdapter` from an exact `product_spec.ProductSpec`. The page gains a palette cover and header, a greeting, hub navigation as text, a Today linked view on Tasks, a Quick notes linked view on Notes, and two identity callouts. The mass tier also stores a Month calendar linked to Events. The business tier has no Events database and no monthly calendar. A second call does not create another block or view. A missing page, database, or dashboard piece behind the saved checkpoint is an error. The checkpoint records `dashboard_and_navigation`. The next phase is `identity_specific_hubs` and this wave does not run it. The one-row notification dashboard, identity hubs, variants, QA, the fact ledger, and the workflow link are not built. No live HTTP, no real Notion workspace, no Etsy listing.

Prompt-integrity review: `docs/control/reviews/2026-10-05-session-07-prompt-integrity.md`. Focused tests: 80 passed across the dashboard, shared-database, and phase-1 files. `ruff format`, `ruff check`, and `pyright` are clean on the touched paths.

Mutation checks (34 rows; each applied to `notion_dashboard.py`, the dashboard test file run, then reverted; 34 killed):

| Mutation | Site | Failing test |
|---|---|---|
| Greeting drops the identity | `notion_dashboard.py:116` | `test_mass_tier_builds_the_home_dashboard_once` |
| Greeting is hardcoded to Weekly Planner | `notion_dashboard.py:116` | `test_business_tier_omits_the_event_calendar` |
| Navigation returns only the word navigate | `notion_dashboard.py:121` | `test_mass_tier_builds_the_home_dashboard_once` |
| Cover uses an https URL | `notion_dashboard.py:105` | `test_mass_tier_builds_the_home_dashboard_once` |
| Header is the design-shell icon | `notion_dashboard.py:111` | `test_mass_tier_builds_the_home_dashboard_once` |
| Monthly calendar is never linked | `notion_dashboard.py:324` | `test_mass_tier_builds_the_home_dashboard_once` |
| Monthly calendar is linked for every tier | `notion_dashboard.py:324` | `test_business_tier_omits_the_event_calendar` |
| Linked view stores no filters | `notion_dashboard.py:476` | `test_mass_tier_builds_the_home_dashboard_once` |
| Every linked view is a table | `notion_dashboard.py:474` | `test_mass_tier_builds_the_home_dashboard_once` |
| Every linked view is created from Tasks | `notion_dashboard.py:466` | `test_mass_tier_builds_the_home_dashboard_once` |
| Classify matches a linked view against Tasks | `notion_dashboard.py:415` | `test_matching_month_view_is_adopted` |
| Callout icon is the design shell icon | `notion_dashboard.py:62` | `test_mass_tier_builds_the_home_dashboard_once` |
| Skip the fixture probe check | `notion_dashboard.py:143` | `test_catalogue_spec_and_live_probes_are_rejected` |
| Skip resume of a stored dashboard | `notion_dashboard.py:153` | `test_replay_does_not_create_another_dashboard` |
| Skip the stored database check | `notion_dashboard.py:152` | `test_missing_database_is_not_rebuilt` |
| Accept a published page | `notion_dashboard.py:294` | `test_published_page_is_rejected` |
| Skip the single-line field check | `notion_dashboard.py:146` | `test_newline_in_the_buyer_problem_creates_nothing` |
| Allow a second page | `notion_dashboard.py:269` | `test_hub_page_is_not_created` |
| Resume ignores tampered filters | `notion_dashboard.py:598` | `test_tampered_today_filter_is_not_rewritten` |
| Always create a new greeting | `notion_dashboard.py:454` | `test_matching_pieces_are_adopted` |
| Skip the ProductSpec check | `notion_dashboard.py:142` | `test_catalogue_spec_and_live_probes_are_rejected` |
| Skip the same-spec check | `notion_dashboard.py:148` | `test_other_spec_does_not_build_a_dashboard` |
| Accept a naive recorded_at | `notion_dashboard.py:145` | `test_naive_recorded_at_leaves_the_checkpoint_unchanged` |
| Linked view name is blank | `notion_dashboard.py:475` | `test_mass_tier_builds_the_home_dashboard_once` |
| Resume rejects the stored view set | `notion_dashboard.py:555` | `test_replay_does_not_create_another_dashboard` |
| Checkpoint always records a month piece | `notion_dashboard.py:497` | `test_business_tier_omits_the_event_calendar` |
| Next phase skips identity hubs | `notion_dashboard.py:252` | `test_mass_tier_builds_the_home_dashboard_once` |
| Wrong cover is overwritten | `notion_dashboard.py:434` | `test_wrong_cover_is_not_rewritten` |
| Quick notes view is omitted | `notion_dashboard.py:325` | `test_mass_tier_builds_the_home_dashboard_once` |
| Piece kinds always follow the mass tier | `notion_dashboard.py:307` | `test_business_tier_omits_the_event_calendar` |
| A duplicate greeting is adopted | `notion_dashboard.py:375` | `test_duplicate_greeting_is_rejected` |
| Module names notion_client | `notion_dashboard.py:630` | `test_dashboard_module_does_not_name_a_live_client` |
| Module names publish_page | `notion_dashboard.py:630` | `test_dashboard_module_does_not_name_a_live_client` |
| Module names create_database | `notion_dashboard.py:630` | `test_dashboard_module_does_not_name_a_live_client` |

Exit 78 scheduler stays HELD. Parked S06 nits stay parked. The #51 published-page mutant and the #52 shared-database nits stay parked.

## 2026-10-05 — Session 07 W2: tip-sync and fixture shared databases

Session 07 stays incomplete. This wave is not SESSION_07 COMPLETE. State revision 49 → 50. `current_session` stays 7. `completed_sessions` stays `[0, 1, 2, 3, 4, 5, 6]`. `next_session` stays 7. `next_prompt` stays `10_SESSION_07_PRODUCT_BUILD_VARIANTS_AND_QA.md`. `head_sha` moves to the post-merge W1 tip `b0536cd0fea41018be8f7561a7f2193752cd5f24`. `evidence_closure_commit_sha` stays the Session 06 closure tip `0f94d585f23d79e5ac18479f01e14f67cbaad332`: an incomplete session may record a later `head_sha`, and this wave is not the completion candidacy that would move the closure SHA. `last_verified_commit` stays bootstrap `1abf0d7cca3a6b8cd7efcd0a45523538fd5bfd9d`. `updated_at` is `2026-10-05T20:00:00Z`.

Twelve session 7 evidence keys stay false, including `shared_databases_built`, `product_build_tests_pass`, `control_files_and_checkpoint_current`, and `evidence_closure_commit_recorded`. No session exit code is recorded. A07, A08, and A09 stay DESIGNED. `commissioned_agents` stays empty.

Shared databases only, in `notion_shared_databases.py`, resuming the W1 checkpoint `top_level_page_and_design_shell` on `FixtureNotionAdapter` from an exact `product_spec.ProductSpec`. Mass tier stores Tasks, Events, Habits, Finance, Meals, and Notes. Business tier stores Clients, Projects, Content, Invoices, Tasks, and Notes. Each database is parented to the unpublished top-level page and uses the catalogue schema. A second call does not create another database. A missing database behind the saved checkpoint is an error. The checkpoint records both phase names and the provider ids. The next phase is `dashboard_and_navigation` and this wave does not run it. Dashboards, hubs, the notification dashboard, variants, QA, the fact ledger, and the workflow link are not built. No live HTTP, no real Notion workspace, no Etsy listing.

Exit 78 scheduler stays HELD. Parked S06 nits stay parked. The published-page mutant from #51 stays parked.

## 2026-10-03 — Session 07 W1: activation and fixture phase 1

Session 07 is activated and incomplete. This wave does not close the session. State revision 48 → 49. `current_session` is 7. `completed_sessions` stays `[0, 1, 2, 3, 4, 5, 6]`. `next_session` stays 7. `next_prompt` stays `10_SESSION_07_PRODUCT_BUILD_VARIANTS_AND_QA.md`. `head_sha` and `evidence_closure_commit_sha` stay the Session 06 closure tip `0f94d585f23d79e5ac18479f01e14f67cbaad332`. `last_verified_commit` stays bootstrap `1abf0d7cca3a6b8cd7efcd0a45523538fd5bfd9d`. `updated_at` is `2026-10-03T00:30:00Z`.

Twelve session 7 evidence keys are installed and each one is false, including `notion_product_builder_implemented`, `product_build_tests_pass`, `control_files_and_checkpoint_current`, and `evidence_closure_commit_recorded`. No session exit code is recorded. A07, A08, and A09 stay DESIGNED. `commissioned_agents` stays empty.

Phase 1 only, on `FixtureNotionAdapter`: one unpublished workspace-parent page titled from `product_spec.ProductSpec`, plus one palette callout. The checkpoint records `top_level_page_and_design_shell` and the provider ids. A second call does not create another page. A missing page behind that checkpoint is an error. The catalogue `products.ProductSpec` is rejected. Shared databases, dashboards, hubs, the notification dashboard, variants, QA, the fact ledger, and the workflow link are not built. No live HTTP, no real Notion workspace, no Etsy listing.

Exit 78 scheduler stays HELD. Parked S06 nits stay parked. Prompt-integrity review: `docs/control/reviews/2026-10-03-session-07-prompt-integrity.md`.

## 2026-10-02 — Session 06 W11: SESSION_06 COMPLETE control flip (post-W10 @ 0f94d585)

Parallel control lane only (`docs/control/*`). No feature code, no Session 07 features, no Exit 78 scheduler lift, no production Notion or Etsy mutation. The default Notion CLI probe remains `FakeNotionProbe` (no network).

- Candidacy commit `f946772bfe190b3812005924ba5c0d42545995cd` first recorded `head_sha` and `evidence_closure_commit_sha` at the W10 squash tip `0f94d585f23d79e5ac18479f01e14f67cbaad332` (#49) with the session still incomplete and `evidence_closure_commit_recorded` false. This later state-pointer commit flips SESSION_06 COMPLETE. State revision 47 → 48. `head_sha` stays the W10 tip and does not claim this commit. `last_verified_commit` stays bootstrap `1abf0d7cca3a6b8cd7efcd0a45523538fd5bfd9d` because `tests/bootstrap/test_control_state.py` requires that equality, the same pointer #38 kept. `updated_at` is `2026-10-02T00:51:41Z`, the W10 commit time.
- Evidence keys: ALL EIGHT TRUE. Confirmed in tree before the flag flip: `notion_capability_inspected` (`docs/architecture/PLATFORM_COMPATIBILITY.md` method matrix, API limits, Composio absent, browser-only ops); `platform_compatibility_documented` (31 tagged operations); `notion_adapter_interface_defined` (`NotionAdapter`, 31 async operations); `fixture_adapter_implemented` (`FixtureNotionAdapter` in-memory CRUD; `config/integrations.yaml` `adapter_mode: fixture`); `adapter_router_implemented` (`NotionAdapterRouter` selects fixture and API; browser and combined config modes still raise `NotImplementedError` per the W4a contract). `adapter_unit_tests_pass` stays true (W10 recorded 1959 collected, 1958 passed, 1 skipped). `control_files_and_checkpoint_current` true. `evidence_closure_commit_recorded` set true by this flip.
- Session 06 status: COMPLETE. `completed_sessions` advanced to `[0, 1, 2, 3, 4, 5, 6]`; `next_session` set to 7; `next_prompt` set to `10_SESSION_07_PRODUCT_BUILD_VARIANTS_AND_QA.md`. `transition_contract.completion_requires_next_session` was left at 4 while `next_session` is 7. That drift is corrected to 7. `src/money_machine/control/state.py` rejects a completion unless those match. The value 4 was not precedent from the S04 and S05 closes.
- The session prompt's required exit code is `SESSION_06_NOTION_INTEGRATION_COMPLETE`.
- External sandbox smoke, run once outside the repo and not re-run here (Grok, `2026-10-02T22:13:12Z`, repo tip `0f94d585`): workspace display name "MM S06 Sandbox"; bot "MM S06 Smoke"; parent page `3ed82fb0-af94-80dc-8272-f40b16376b81`; created then archived page `3ed82fb0-af94-81af-87c4-e302ca06f973` and database `3ed82fb0-af94-8166-bb5c-d91e42dc2234`; `before_count` 0; `after_count` 0; `call_count` 9/15; all HTTP 200; `pass` true. This is the approved one-shot for the live-connection criterion. It does not make production Notion or Etsy true. No token is recorded.
- Parked nits, non-blocking, not fixed in this close: (1) an int-subclass `SystemExit` code maps to 1; (2) the False `SystemExit` row needs an isinstance-style mutant; (3) backtick formatting of `__context__` in the #49 PR body; (4) CodeRabbit APPROVED tip lag on #49; (5) `connected: true` in fake mode (`notion.py` connect payload); (6) argparse echoing a token passed as an extra argument. Items 5 and 6 are still open from review 5328507848. They were omitted from the first close list, not fixed.
- Continuity pin: `tests/bootstrap/test_control_state.py` requires `last_verified_commit` to be bootstrap `1abf0d7cca3a6b8cd7efcd0a45523538fd5bfd9d`, and, while session 6 is complete, requires `head_sha` and `evidence_closure_commit_sha` to be the W10 tip `0f94d585f23d79e5ac18479f01e14f67cbaad332` and not the commit that contains the state file. Rewriting both closure SHAs to the close commit fails that test. Those STATE fields stay on the #38 shape.
- Exit 78: worker remains conditionally lifted (D-0028 gates). Scheduler stays HELD.
- W11 control flip review recorded at `docs/control/reviews/2026-10-02-session-06-wave-11-control-flip.md`.

## 2026-09-20 — Session 05 Lane 1: Etsy research adapters

- **Session 05 minimal activation** (revision 28→29): `current_session` advanced to 5, `session_status` set to incomplete, ten Session 05 evidence keys installed all-false per state.py contract addition.
- **Etsy fixture adapter** implemented as primary safe-for-CI research data source; loads synthetic observations from `tests/fixtures/etsy_search_results.json`. Captures all required workbook fields: search phrase, rank, title, prices, shop signals (sales/age), badges, urgency signals, review count, identity niche, base category, URL, evidence timestamp.
- **Browser and API adapter stubs** created with explicit `NotImplementedError` - no external calls, no browser launches, no API keys consumed. Safe boundaries preserved.
- **Config-driven seed phrases**: `config/research.yaml` defines the ten playbook seed phrases (digital planner, printable wall art, custom pet portrait, wedding invitation template, vintage logo design, social media templates, budget spreadsheet, meal planner printable, business card template, resume template). Not hardcoded in business logic.
- **Synthetic fixture data**: 30 observations per seed phrase (300 total), demonstrating thin evidence principle - some optional fields (anchor_price_cents, shop_sales_count, shop_age_years, review_count) are None where appropriate; all required fields present.
- **Comprehensive tests** in `tests/integrations/etsy/test_research_adapter.py`: fixture adapter field validation, target_count compliance, stub NotImplementedError safety, config loading, fixture-config key matching, thin evidence verification, real fixture integration. Tests written; CI run pending environment setup.
- **Prompt integrity review** recorded at `docs/control/reviews/2026-09-20-session-05-lane-1-etsy-adapters.md` - lane-scoped review of Session 05 Section 1 only; agent logic (A03-A06), workflow linking, and commissioning deferred to L2-L4.
- **Control update**: `etsy_adapters_implemented` evidence key flipped TRUE; remaining S05 keys FALSE. Worker Exit 78 conditional lift preserved (no regression). Commit `02211ff`.
- **OUT OF SCOPE** (as specified): paid Etsy purchase, live teardown, A03/A05/A06 agent implementations, Scheduler Exit 78 lift, Session 06 work.

## 2026-09-21 — Session 05 Lane 2: A03 Market Research Agent (fixture-only)

- **A03 Market Research agent** implemented with fixture-only research (no live Etsy API/browser). Agent consumes 10 seed phrases from `config/research.yaml`, loads synthetic ListingObservations and ShopObservations from Etsy fixture adapter, extracts identity×category candidates, scores by observation count + young-fast shop signals (< 12 months, > 400 sales), returns top 5 candidates as ShortlistAnalysis.
- **ResearchReport domain model** extended with ShortlistAnalysis field; CandidateProfile carries identity, base_category, price_range, observation_count, shop_count, young_fast_shop_count, risk_notes.
- **Prompt integrity review** recorded at `docs/control/reviews/2026-09-20-session-05-wave-01-a03-prompt-integrity.md` - A03 prompt verified against workbook Appendix, one high finding (missing explicit young-fast threshold), addendum executed.
- **Integration tests** in `tests/integration/test_market_research_agent.py`: A03 invocation with fixture data, ResearchReport validation, ShortlistAnalysis top-5 constraint, candidate ranking, thin evidence handling, idempotent re-runs.
- **Control update**: `research_agent_implemented` and `shortlist_analysis_implemented` evidence keys flipped TRUE. Commit `c64bf58`.
- **OUT OF SCOPE**: paid Etsy API, live browser scraping, candidate scoring beyond observation count + young-fast signals.

## 2026-09-24 — Session 05 Lane 3: A05 Product Strategy Scorer + ProductSpec

- **A05 Product Strategy agent** implemented with four-criterion scoring: (1) price attractiveness (higher = better up to $25 USD); (2) demand signal (observation count); (3) young-fast shop count (< 12 months, > 400 sales); (4) thin evidence (fewer competing products). Qualification gate at ≥20/40 points; refuses HOLD if unqualified.
- **ProductSpec generation**: Primary qualified candidate → ProductSpec with concept_fingerprint (SHA256 of identity:category), buyer_problem, title, tier (mass), real_price, anchor_price, palette (3 colour tokens), hubs (6 with page counts), colour_variants (3), flagship_feature, shared_databases (empty), page_target_min/max (45-55), feature_targets, experiment_hypothesis, experiment_tags (new-front). Stub generation; production would be richer.
- **EvidenceReference collection**: Scoring evidence attached to ProductSpec; evidence_id generated with uuid4(), sha256 field reuses concept_fingerprint (parked nit: evidence self-dump).
- **Unit tests** in `tests/unit/test_product_strategy.py`: four-criterion scoring, qualification gate enforcement (HOLD < 20 points, RUN ≥ 20), ProductSpec generation from qualified candidate, concept_fingerprint SHA256 validation, EvidenceReference attachment.
- **Control update**: `scoring_agent_implemented` and `product_spec_generation_implemented` evidence keys flipped TRUE. Commit `a7c9521`.
- **Parked nit**: A05 concept_fingerprint = SHA256(identity:category), but L4 fixtures hash buyer_problem only — cross-lane drift in fingerprint contract. Recorded in carry_forward.

## 2026-09-24 — Session 05 Lane 4: A06 Catalogue Dedupe + Fixture Teardown Workflow

- **A06 Catalogue Dedupe agent** implemented with three-rule dedupe check: (1) Exact identity×category match → EXACT_IDENTITY_CATEGORY collision; (2) Title similarity ≥0.7 Jaccard threshold → TITLE_SIMILARITY collision; (3) Concept fingerprint match → CONCEPT_FINGERPRINT collision. Outcome: PASS (no collisions) or TOO_CLOSE (≥1 collision). Differentiation evidence generated for PASS outcomes (parked nit: describes candidate's own fields — self-description rather than comparative).
- **Workflow linking**: DEDUPE_PASSED event → ProductBuildJob (A07), DEDUPE_FAILED event → ReconceptProductJob via EventDispatcher and SuccessorFactory reading config/workflows.yaml event_successor_map. Orchestrator wire proven in tests/integration/test_event_driven_successors.py (successor workflows start at DEDUPE_CHECK).
- **Fixture teardown workflow**: Synthetic competitor ProductSpecs generated in tests/fixtures/products.py with buyer_problem-based concept_fingerprints (parked nit: L4 fixtures hash buyer_problem only, A05 hashes identity:category — cross-lane drift).
- **DedupeResult domain model**: result_id (parked nit: reuses spec_id, could be distinct UUID), workflow_id, spec_id, outcome (PASS/TOO_CLOSE), rule_version, normalized_title, concept_fingerprint, title_similarity_threshold, compared_spec_ids, collisions (DedupeCollision with other_spec_id, reason, similarity, evidence), differentiation_evidence, completed_at.
- **Integration tests** in `tests/integration/test_dedupe_workflow.py`: PASS path (empty catalogue → ProductBuildJob), TOO_CLOSE path (title collision → ReconceptProductJob), exact identity×category collision, concept fingerprint collision, fixture-based workflow integration.
- **Parked nit**: catalogue_dedupe.py:115 uses `contextlib.suppress(Exception)` on invalid spec parsing — fail-open suppression instead of fail-closed refusal.
- **Control update**: `dedupe_agent_implemented`, `teardown_workflow_implemented`, and `workflow_linking_complete` evidence keys flipped TRUE. Commit `9b791d45`.
- **OUT OF SCOPE**: live product catalogue, paid Etsy teardown, ReconceptProductJob implementation (A08 scope).

## 2026-09-24 — Session 05 W11: SESSION_05 COMPLETE control flip (post-L4 @ 9b791d45)

Parallel control lane only (`docs/control/*`). No feature code, no S06 features, no live Notion/Etsy, no Exit78 changes.

- Updated `IMPLEMENTATION_STATE.json` to mark SESSION_05 COMPLETE. State revision 30 → 31.
- Evidence keys: ALL TEN TRUE. `evidence_closure_commit_recorded` set TRUE by W11 control flip.
- Session 05 status: COMPLETE. `completed_sessions` advanced to `[0, 1, 2, 3, 4, 5]`; `next_session` set to 6; `next_prompt` set to SESSION_06.
- `head_sha` and `evidence_closure_commit_sha` remain at `9b791d45f9461030f09eda8a46838afc5447416c` (L4 squash tip).
- `last_verified_commit` remains at bootstrap `1abf0d7cca3a6b8cd7efcd0a45523538fd5bfd9d` (session-complete continuity per S04 pattern).
- Exit 78 status UNCHANGED: worker lifted conditionally (D-0028 gates), scheduler held.
- Parked L2-L4 nits remain in carry_forward as non-blocking.
- L1–L4 complete: Etsy adapters, A03 research, A05 scoring/ProductSpec, A06 dedupe/workflow linking. No S06 features, no live production/Notion/Etsy.


## 2026-09-24 — Session 05 control tip-sync (post-L4 @ 9b791d45)

- Parallel control lane only (`docs/control/*`). No feature code, no S06 work, no live Etsy/Notion mutations.
- Refreshed `head_sha` and `evidence_closure_commit_sha` to `9b791d45f9461030f09eda8a46838afc5447416c` (L4 squash tip on `build/full-automation`); `last_verified_commit` stayed at bootstrap `1abf0d7cca3a6b8cd7efcd0a45523538fd5bfd9d` (session incomplete continuity). State revision 29 → 30.
- Evidence keys flipped TRUE for L2-L4 lanes: `research_agent_implemented` (L2 A03), `shortlist_analysis_implemented` (L2 shortlist), `scoring_agent_implemented` (L3 A05), `product_spec_generation_implemented` (L3 ProductSpec), `dedupe_agent_implemented` (L4 A06), `teardown_workflow_implemented` (L4 fixtures), `workflow_linking_complete` (L4 EventDispatcher → SuccessorFactory wire). Nine of ten S05 evidence keys now TRUE; `evidence_closure_commit_recorded` remains FALSE (S05 not yet complete).
- Parked L2-L4 nits recorded in `carry_forward` as non-blocking improvement opportunities: (1) A05 concept_fingerprint = identity:category vs L4 fixtures = buyer_problem (cross-lane drift); (2) A05 evidence SHA reuses concept_fingerprint (self-dump); (3) Dedupe differentiation_evidence describes candidate's own fields (self-desc); (4) A06 contextlib.suppress(Exception) in spec parsing (fail-open); (5) Dedupe result_id = spec_id (could use distinct UUID).
- Exit 78 unchanged: worker lifted conditionally (D-0028 commissioning gates), scheduler held. Session 05 remains `incomplete`; `completed_sessions` unchanged at `[0, 1, 2, 3, 4]`. No S06 advance, no live provider calls, no commissioning claims.

## 2026-09-24 — Session 06 Wave 1: Notion integration foundation stubs

- **Session 06 minimal activation** (revision 31→32): `current_session` advanced to 6, `session_status` set to incomplete, eight Session 06 evidence keys installed all-false per state.py contract addition (notion_capability_inspected, platform_compatibility_documented, notion_adapter_interface_defined, fixture_adapter_implemented, adapter_router_implemented, adapter_unit_tests_pass, control_files_and_checkpoint_current, evidence_closure_commit_recorded).
- **Prompt integrity review** recorded at `docs/control/reviews/2026-09-24-session-06-prompt-integrity.md` with three-dimensional review (Fidelity, Safety & Executability, Gameability) and corrective addendum for W1 bounded execution. Full Session 06 prompt reviewed; W1 implements ONLY sections 1-2 (capability inspection + adapter stubs). Deferred to W2+: browser sessions, receipts persistence, formula builders, live connection, publishing helpers.
- **Notion capability inspection**: Researched Notion Official API (DIRECT_API), browser automation patterns (BROWSER), and combined methods. NO live API calls, NO browser launches, NO credentials. Documentation-only research.
- **PLATFORM_COMPATIBILITY.md**: Created `docs/architecture/PLATFORM_COMPATIBILITY.md` with 31 Notion operations tagged by method (DIRECT_API | COMPOSIO | BROWSER | COMBINED), mutates, requires_auth, idempotent, reconcilable, w1_status. Method selection rationale documented. All operations tagged w1_status: stub or deferred.
- **NotionAdapter interface**: Defined abstract protocol in `src/money_machine/integrations/notion/adapter.py` with 31 async method signatures, typed arguments/returns (Pydantic domain models), docstrings stating method/mutates/idempotency per PLATFORM_COMPATIBILITY.md.
- **Domain models**: Created `src/money_machine/integrations/notion/domain.py` with typed dataclasses: NotionPage, NotionDatabase, NotionDatabaseProperty, NotionRelation, NotionRollup, NotionFormula, NotionView, NotionLinkedView, NotionBlock, NotionTextBlock, NotionCalloutBlock, NotionWorkspace, NotionFilter, NotionSort.
- **FixtureNotionAdapter**: Implemented in-memory CRUD stub in `src/money_machine/integrations/notion/fixture_adapter.py`. Ephemeral state (workspaces, pages, databases, blocks, views, linked_views dicts). Operations return typed domain objects with generated IDs. Sufficient for unit tests; NO live Notion calls, NO persistence.
- **Adapter router**: Implemented config-driven router in `src/money_machine/integrations/notion/router.py`. Reads `config/integrations.yaml` notion.adapter_mode (fixture | api | browser | combined). Returns appropriate adapter instance. Created `config/integrations.yaml` with fixture as W1 default.
- **Stub adapters**: Created API/Browser/Combined adapter stubs in `api_adapter.py`, `browser_adapter.py`, `combined_adapter.py`. All methods raise `NotImplementedError("Real {method} adapter deferred to Session 06 Wave 2+/3+. Use FixtureNotionAdapter for testing.")`. Clear defer messages distinguish DIRECT_API ops (W2+) from BROWSER/COMBINED ops (W3+).
- **Control files**: Updated state.json (session 6 active, S06 evidence all-false, S05 complete in history), state.py (SESSION_EVIDENCE_KEYS[6] added), IMPLEMENTATION_LOG.md (this entry). S05 parked nits remain in carry_forward. Exit 78 unchanged (worker lifted conditionally via D-0028, scheduler held).
- **OUT OF SCOPE** (W1 hard boundaries): Live Notion API/browser calls, browser session management, formula builders beyond stubs, Notion receipts table/persistence, publishing helpers, relation/linked-view helpers, live connection CLI, Exit78 scheduler lift, SESSION_06 COMPLETE marking.
- Unit tests pending CI run. Next: write unit tests for adapter interface, router selection, fixture CRUD, stub NotImplementedError behavior; run `bash scripts/test.sh` to green.

## 2026-09-24 — Session 06 Wave 2: APINotionAdapter real implementation (DIRECT_API ops only)

- **APINotionAdapter real implementation** in `src/money_machine/integrations/notion/api_adapter.py` for 18 DIRECT_API operations tagged in PLATFORM_COMPATIBILITY.md: connection_status, workspace_discovery, create_page, rename_page, move_page, set_icon, set_cover, add_text_block, add_callout_block, create_database, add_property, create_relation, create_rollup, add_filter, add_sort, add_child_page, inspect_page, inspect_database, get_public_url.
- **Dependency added**: `notion-client>=2.2,<3` in `pyproject.toml` for Notion Official API access. All adapter methods use AsyncClient from notion-client SDK. No credentials in repo; uses `NOTION_API_TOKEN` env var with deferred validation (token checked on first API call, not at initialization).
- **Domain object mapping**: All API responses converted to typed domain models (NotionPage, NotionDatabase, NotionBlock, etc.) via helper methods `_map_page` and `_map_database`. Consistent field extraction from Notion API JSON.
- **Error handling**: Generic `Exception` catching in connection_status and workspace_discovery for robustness; re-raised with context chaining (`raise ... from e`) per Ruff B904.
- **Unit tests**: 21 new mocked unit tests in `tests/unit/integrations/notion/test_api_adapter.py` using `respx` for HTTP request mocking. **Zero live Notion API calls** in tests. Tests cover all 18 implemented operations plus error cases (connection failure, workspace discovery failure). All W1 fixture/router/stub tests remain green (69 total tests passing).
- **Configuration preserved**: Fixture adapter remains default in `config/integrations.yaml` (notion.adapter_mode=fixture). API mode selectable via config only.
- **Stub operations unchanged**: BROWSER/COMBINED operations remain `NotImplementedError` stubs as required. Only DIRECT_API operations implemented per W2 scope.
- **Code quality**: Ruff formatting applied (removed trailing whitespace, reformatted long lines), Pyright type checking clean. No linting errors.
- **Control update**: `adapter_unit_tests_pass` evidence key flipped TRUE (commit 45dc656); `control_files_and_checkpoint_current` flipped TRUE (commit 9d88e53, then corrected to match tip in this entry). State revision 32 → 35. Remaining six Session 06 evidence keys remain FALSE (W1 design keys, evidence_closure_commit_recorded).
- **Exit 78 verification**: Zero diffs in `src/money_machine/orchestration/` (worker/scheduler untouched). `git diff 73704c57..HEAD -- src/money_machine/orchestration/` output empty.
- **OUT OF SCOPE** (W2 hard boundaries): BrowserNotionAdapter / CombinedNotionAdapter real impl, receipts persistence, live product builds, publish-to-web production, Exit78 scheduler lift, live Notion/Etsy product mutations, SESSION_06 COMPLETE marking.

## 2026-09-24 — Session 06 Wave 3: BrowserNotionAdapter (BROWSER ops only)

- **BrowserNotionAdapter real implementation** in `src/money_machine/integrations/notion/browser_adapter.py` for 12 BROWSER-tagged operations per PLATFORM_COMPATIBILITY.md: duplicate_page, create_formula, create_linked_view, create_calendar_view, create_table_view, create_board_view, set_view_title_visibility, publish_page, unpublish_page, set_duplicate_as_template, set_search_indexing, verify_stranger_access.
- **Dependency injection pattern**: BrowserSession protocol abstraction allows testing with FakeBrowserSession (no real Playwright). Production will use real Playwright-backed session; tests inject synthetic browser responses. Protocol methods: navigate, click, fill, get_attribute, is_visible, wait_for_selector, get_current_url.
- **UI automation patterns**: All BROWSER operations navigate to Notion URLs, interact via data-testid selectors, handle visibility checks for idempotent toggles (publish/unpublish, view visibility, page settings). Formula editor, view creation, page duplication, and publishing settings implemented per UI interaction sequences.
- **Unit tests**: 18 test functions in `tests/unit/integrations/notion/test_browser_adapter.py` (36 collected items: 1 parametrized refusal test covering 18 DIRECT_API + 1 COMBINED operations, plus 17 BROWSER operation tests) using FakeBrowserSession. **Zero live browser launches, zero Playwright, zero real Notion UI**. Tests cover all 12 BROWSER operations plus idempotency checks (toggles skip when already in desired state), comprehensive API/COMBINED operation refusal (parametrized NotImplementedError test for all non-BROWSER operations), verify_stranger_access timeout handling.
- **Configuration preserved**: Fixture adapter remains default in `config/integrations.yaml`. APINotionAdapter from W2 stays intact. BrowserNotionAdapter selectable via router when browser mode configured.
- **API/COMBINED operations unchanged**: DIRECT_API operations (connection_status, create_page, rename_page, etc.) raise NotImplementedError with clear message ("uses API method, not BROWSER"). COMBINED operations (get_public_url) also raise NotImplementedError (CombinedAdapter scope).
- **Code quality**: Imports follow existing patterns (Protocol from typing for browser abstraction, uuid4 for ID generation, datetime UTC for timestamps). Consistent error messages for out-of-scope operations.
- **Exit 78 verification**: Zero diffs in `src/money_machine/orchestration/` (worker/scheduler untouched).
- **OUT OF SCOPE** (W3 hard boundaries): CombinedNotionAdapter full implementation (tiny stub wiring OK if needed), receipts persistence, live product builds, publish-to-web production, Exit78 scheduler lift, live Notion/Etsy product mutations, SESSION_06 COMPLETE marking, real Playwright integration.


## 2026-09-24 — Session 06 Wave 4a: BrowserNotionAdapter defect fixes (PR #41 review)

- **All 7 defects fixed** from PR #41 review: (1) publish_page/unpublish_page idempotency (check state before clicking); (2) create_formula & create_*_view read real IDs from DOM/URL, raise RuntimeError on failure; (3) duplicate_page verifies new ID differs from source, reads real title or raises; (4) set_view_title_visibility uses proper Notion URL shape (?v=), returns full NotionView, raises if not on notion.so page with real database/page ID; (5) verify_stranger_access uses separate anonymous BrowserSession via factory, catches specific errors (ConnectionError/TimeoutError/ValueError), lets unknown errors propagate; (6) router.set_adapter_mode validates before clearing cache (preserves adapter when rejecting browser/combined); (7) router selectability wording: correction recorded in this W4a entry; W3 entry left as originally written.
- **Correction to W3 entry**: Router actually refuses browser/combined modes (NotImplementedError); W3 incorrectly stated "selectable via router when browser mode configured". W3 used uuid4 for ID generation; W4a replaced with real ID reads from DOM/URL.
- **Eng Ops fixes** (CodeRabbit review, 4 items): (a) router test breakdown corrected to 9 existing + 2 new = 11 total (not 8+3); (b) create_calendar_view/create_table_view/create_board_view capture initial ?v= ID before create click, raise RuntimeError if ?v= missing OR unchanged after click (detects failed creation); (c) set_view_title_visibility minimal fix: remove generic fallback, only build URL when current page is notion.so with real database/page ID, raise RuntimeError otherwise; no interface change (database_id parameter deferred to W4b/Combined pending Reviewer ruling); (d) set_view_title_visibility URL validation bug (r4098768957): replace substring checks with urllib.parse.urlparse, require hostname exactly notion.so or ending with .notion.so (reject evilnotion.so, notion.so.evil.com), require https scheme (reject http://), require non-empty path, build URL as scheme://netloc/path?v=view_id, parametrized tests for 6 rejection cases (non-notion.so, bare notion.so, bare notion.so/, notion.so.evil.com, evilnotion.so, http://www.notion.so/abc).
- **Verifier blocker and small fixes** (Round 5): (a) Verifier blocker: added test where anon session's wait_for_selector raises RuntimeError (not TimeoutError), confirmed error propagates and does NOT return False, mutation-checked by temporarily restoring except Exception: (new test FAILED with broad except, as expected), renamed test_verify_stranger_access_propagates_unexpected_errors to test_verify_stranger_access_wraps_navigate_value_error to reflect what it actually tests; (b) publish_page: removed fallback `or f"https://www.notion.so/{page_id}"`, now raises RuntimeError if public URL cannot be read, never sets is_published=True without valid URL, added test; (c) set_view_title_visibility URL guard: moved urlparse import to module level, removed dead try/except around urlparse, added https scheme requirement; (d) duplicate_page: removed dead else branch; (e) docs restored W3 LOG entry and STATE session_06_w3 to original wording from base 348161fb.
- **Drift check programmatic**: DIRECT_API and COMBINED operation sets derived by parsing PLATFORM_COMPATIBILITY.md (regex match on table rows), asserted equal to parametrized test lists (set equality + diff reporting on mismatch).
- **Test coverage expanded**: Browser adapter 37 test functions (60 collected items: 1 parametrized refusal test covering 19 DIRECT_API + COMBINED ops, plus 36 BROWSER operation tests including success/failure/unchanged-ID/URL-validation paths for view creation, both starting states for idempotent toggles, anonymous session usage verification, title read failure, public URL read failure, notion.so URL validation with 6 parametrized rejection cases including http:// rejection, RuntimeError propagation from wait_for_selector). Router 11 test functions (9 existing from base 348161fb + 2 new cache-preservation tests, 11 collected items).
- **FakeBrowserSession enhancements**: Deterministic IDs (prop_abc123, view_def456) for property/view creation tests. Anonymous session factory support for verify_stranger_access isolation testing.
- **BrowserNotionAdapter constructor updated**: Added optional `anon_session_factory` parameter for anonymous session injection (required for verify_stranger_access).
- **Test results**: CI on the PR tip: 1043 collected, 1042 passed, 1 skipped. Local: browser adapter 37 functions / 60 collected, router 11 functions / 11 collected (9 existing + 2 new), all pass. Zero orchestration/ diffs, api_adapter.py untouched, fixture adapter default preserved.
- **W4b items deferred** (Reviewer-conditioned, must land before real browser session): (i) database_id parameter on set_view_title_visibility; (ii) close() on session interface for anon sessions; (iii) real session translating Playwright exceptions into TimeoutError and ConnectionError.
- **OUT OF SCOPE** (W4a hard boundaries): CombinedNotionAdapter implementation, receipts persistence, live Playwright integration, SESSION_06 COMPLETE marking.


## 2026-09-25 — Session 06 Wave 4b: BrowserNotionAdapter carry-forward fixes (PR #43)

- **SPEC CHANGE** (decorator removed): `TranslatingBrowserSession` wraps both `self._browser` in `__init__` and every anonymous session from the factory in `verify_stranger_access`. `translate_browser_exceptions` is gone from `browser_adapter.py`; the translation tests call the wrapper.
- **Carry-forward from the W4a review** (no new scope):
  - **(i)** `set_view_title_visibility(database_id, view_id, visible)` on `adapter.py`, `fixture_adapter.py`, `api_adapter.py`, `browser_adapter.py`, and `combined_adapter.py`. The view URL is built from the normalized database id. The returned `NotionView.database_id` is that input-derived lowercase undashed id, including when the post-navigate URL is a `Title-<id>` slug whose last segment differs.
  - **(ii)** `BrowserSession` gains `close()`. `verify_stranger_access` closes the anonymous session in `finally` under `contextlib.suppress(Exception)`, so a close error does not mask the original error.
  - **(iii)** The wrapper maps a Playwright-style `TimeoutError` to built-in `TimeoutError`, and a Playwright-style `Error` whose message mentions navigation, connection, `net::`, or network to `ConnectionError`. `verify_stranger_access` catches only `(ConnectionError, TimeoutError, ValueError)` around `navigate` and re-raises those as `RuntimeError` with that exception as `__cause__`. A plain `RuntimeError` from `navigate` propagates unwrapped. Tests use fake Playwright classes only (no `playwright` import, `uv.lock` untouched).
- **SHOULD-FIX**:
  - **(1)** Fixture `database_id` validation requires exactly 12 or 32 hex characters after stripping a `db_` prefix and dashes and lowercasing. Fixture ids are 12-hex on purpose; real Notion ids are 32-hex. A 20-hex id is rejected. View ownership compares the normalized ids.
  - **(2)** `duplicate_page` strips dashes and lowercases the id read from the page URL before comparing it with the source and before returning it. An upper-case dashed URL returns the lower-case undashed id.
  - **(4)** Host allowlist, covered by separate tests: accepts `notion.so`, `www.notion.so`, `notion.site`, `www.notion.site`, and a single-label `*.notion.site` (`omar.notion.site`). Rejects `http`, `evil.notion.so`, `notion.so.evil.com`, userinfo, a non-URL, `a.b.notion.site`, and an empty label (`https://.notion.site/x`). HTTPS only.
- **Pytest**: 1088 collected, 1087 passed, 1 skipped. W4a baseline: 1043 collected, 1042 passed, 1 skipped. Delta +45 collected.
- **Cause tests**: `test_translating_session_keeps_original_playwright_error_as_cause` is 1 function and 1 collected case. A fake Playwright `TimeoutError` raised through `TranslatingBrowserSession.navigate` comes out as a built-in `TimeoutError` whose `__cause__` is that same Playwright error object. `test_translating_session_preserves_cause_of_untranslated_exception` is 1 parametrized function with 8 collected cases, one per `TranslatingBrowserSession` method: `navigate`, `click`, `fill`, `get_attribute`, `is_visible`, `wait_for_selector`, `get_current_url`, `close`. Each case raises an untranslated `RuntimeError` that already has a `KeyError` `__cause__` and asserts that cause is still a `KeyError`.
- **Per-file counts**:

  | File | Functions (base → tip) | Collected (base → tip) | Delta collected |
  |---|---|---|---|
  | `tests/unit/integrations/notion/test_browser_adapter.py` | 37 → 75 | 60 → 100 | +40 |
  | `tests/unit/integrations/notion/test_fixture_adapter.py` | 35 → 40 | 35 → 40 | +5 |
  | `tests/unit/integrations/notion/test_api_adapter.py` | 21 → 21 | 21 → 21 | 0 |
  | Remaining files | unchanged | 927 → 927 | 0 |
  | **Total** | | **1043 → 1088** | **+45** |
- **Mutation checks** (each applied, pytest run, then reverted):

  | Mutation | Failing test |
  |---|---|
  | B1a: drop the wrapper on the anonymous factory | `test_verify_stranger_access_translates_playwright_timeout` |
  | B1b: drop the wrapper on `self._browser` | `test_publish_page_translates_playwright_timeout` |
  | Fixture length check widened to `12<=len<=32` | `test_fixture_set_view_title_visibility_rejects_20_hex` |
  | Fixture length check narrowed to `len<12` | `test_fixture_set_view_title_visibility_rejects_20_hex` |
  | Remove fixture id validation | `test_fixture_set_view_title_visibility_rejects_20_hex`, `test_fixture_set_view_title_visibility_rejects_invalid_database_id` |
  | `duplicate_page` returns the raw URL segment | `test_duplicate_page_returns_lowercase_undashed_from_uppercase_dashed_url` |
  | `duplicate_page` compare skips lowercase | `test_duplicate_page_raises_when_uppercase_source_matches` |
  | `set_view_title_visibility` returns the last segment of `current_url` | `test_set_view_title_visibility_returns_input_id_not_url_slug` |
  | Drop the wrapper so a Playwright navigation error is not translated | `test_verify_stranger_access_translates_playwright_navigation_error` |
  | Widen the navigate catch to `Exception` | `test_verify_stranger_access_propagates_navigate_runtime_error` |
  | Allowlist as a suffix match | `test_verify_stranger_access_rejects_subdomain`, `test_verify_stranger_access_rejects_deep_nesting_notion_site` |
  | Remove the single-label `*.notion.site` rule | `test_verify_stranger_access_accepts_single_label_notion_site` |
  | Let a `close()` error propagate | `test_verify_stranger_access_close_error_doesnt_mask_original` |
  | Build the view URL from the current page | `test_set_view_title_visibility_uses_given_database_not_current_page` |
  | Remove `close()` from `finally` | `test_verify_stranger_access_close_called_on_error` |
  | Remove `TimeoutError` from the navigate catch tuple | `test_verify_stranger_access_wraps_playwright_navigate_timeout` |
  | Re-raise an untranslated exception with `raise translated from e` on one method | `test_translating_session_preserves_cause_of_untranslated_exception[<method>]` for that method (`navigate`, `click`, `fill`, `get_attribute`, `is_visible`, `wait_for_selector`, `get_current_url`, `close`) |
  | Change `raise translated from e` to `raise translated from None` | `test_translating_session_keeps_original_playwright_error_as_cause` |

- **Control update**: `docs/control/IMPLEMENTATION_STATE.json` `session_06_w4b` and this log entry. `control_files_and_checkpoint_current` stays false. The session stays incomplete.
- **Hard boundaries**: fixtures and mocks only. No live Notion or Etsy, no real browser, no Playwright import. Fixture adapter stays the default. `src/money_machine/orchestration/` untouched. `uv.lock` untouched. Exit 78 held.


## 2026-09-26 — Session 06 Wave 5: combined adapter delegation, receipt stub, cause-test parametrization

- **Combined adapter**: `CombinedNotionAdapter` routes API-tagged operations to the injected API adapter and browser-tagged operations to the injected browser adapter. `reports_unsupported` is checked before the call and may route to the other adapter, including for a non-idempotent write, because nothing has been invoked yet. `OperationUnsupportedError` is raised before any side effect and selects the other adapter only for a read or other idempotent operation. After a non-idempotent write has been invoked, no exception selects the other adapter, including `NotImplementedError`, its subclasses, and `OperationUnsupportedError`. A write that raises (`RuntimeError`, `ValueError`, `ConnectionError`, `KeyError`, `AttributeError`, or any other exception), a `TypeError`, and an auth-style error propagate, and the other adapter is not called. A read or other idempotent operation that raises `RuntimeError`, `ConnectionError`, `ValueError`, `KeyError`, `AttributeError`, `LookupError`, or `NotImplementedError` propagates that same error object, and the other adapter is not called. `TypeError` and `PermissionError` on a non-idempotent write, including a browser-preferred write, propagate the same way. The API adapter reports browser operations unsupported. The browser adapter reports API and combined operations unsupported. Expected channels are parsed from `PLATFORM_COMPATIBILITY.md`. When the fallback also fails, the second error is chained from the first. `get_public_url` is COMBINED: the API delegate returns the public URL, then the browser delegate verifies stranger access; `None` from the API skips the browser, and a failed stranger check returns `None`. `set_view_title_visibility(database_id, view_id, visible)` passes those three arguments through unchanged and returns the delegate's `NotionView`. A non-bool `reports_unsupported` result is rejected before either adapter runs. A public URL that is not a string is rejected before the browser runs. The fixture adapter stays the default.
- **Receipts stub**: `NotionOperationReceipt` and `NotionOperationReceiptLog` follow Session 06 prompt section "### 4. Implement Notion operation receipts" (`prompts/implementation/09_SESSION_06_NOTION_INTEGRATION_FOUNDATION.md`). Fields: job ID, operation, workspace, page/database target, pre-state when available, post-state, provider response, screenshot or response evidence, timestamp, idempotency key, status. Status is `Success`, `Unknown`, or `Failure`. Timestamps must be timezone-aware. A repeated idempotency key is rejected before append, including when a second log instance re-reads the same path. A torn trailing line that is not newline-terminated and is not JSON is skipped on load and truncated before the next append, including when several valid lines precede it. An incomplete UTF-8 tail is skipped the same way. A torn tail of deeply nested brackets is skipped rather than raising `RecursionError`. A complete JSON line with no trailing newline is kept, and a newline is added before the next append. A newline-terminated corrupt line is rejected. Caller mappings are copied before store. Nested mappings, lists, and tuples are frozen at every depth into new containers, so a frozen mapping can be snapshotted again without deepcopy. `dataclasses.replace` keeps nested `pre_state`, `post_state`, and `provider_response` frozen and equal. Mutating the caller's nested dict and list leaves the receipt unchanged. A caller `MappingProxyType`, including one nested inside another mapping, is copied into fresh containers, so mutating its inner list leaves the receipt unchanged. A reference cycle raises `ValueError`. More than 32 levels below the field mapping is rejected (33 nested containers are accepted, counting the field mapping as level 0; 34 are rejected). `record()` writes pure ASCII, including when a field contains non-ASCII text. A `threading.Lock` inside state raises `ValueError`. Mapping keys must be strings at every level. `NaN` and `Inf` are rejected. The path must be a `pathlib.Path` whose parent directory already exists; a string path and a missing parent are rejected, and the stub does not create directories. Writers of one resolved path in this process share one lock object, held weakly in a registry: each log keeps a strong reference for its lifetime, a different path gets a different lock, and a discarded path leaves the registry. Writes happen only at a path the caller injects. No database table and no network.
- **Cause test**: `test_translating_session_keeps_original_playwright_error_as_cause` is parametrized over the eight `TranslatingBrowserSession` methods (`navigate`, `click`, `fill`, `get_attribute`, `is_visible`, `wait_for_selector`, `get_current_url`, `close`). `TranslatingBrowserSession` is unchanged.
- **Pytest collected**: 1257 collected, 1256 passed, 1 skipped. W4b baseline: 1088 collected, 1087 passed, 1 skipped. Delta +169 collected and +169 passed.
- **Per-file counts**:

  | File | Functions (base → tip) | Collected (base → tip) | Delta collected |
  |---|---|---|---|
  | `tests/unit/integrations/notion/test_browser_adapter.py` | 75 → 75 | 100 → 107 | +7 |
  | `tests/unit/integrations/notion/test_stub_adapters.py` | 2 → 1 | 2 → 1 | -1 |
  | `tests/unit/integrations/notion/test_combined_adapter.py` | 0 → 29 | 0 → 109 | +109 |
  | `tests/unit/observability/test_receipts.py` | 0 → 46 | 0 → 54 | +54 |
  | Remaining files | unchanged | 986 → 986 | 0 |
  | **Total** | | **1088 → 1257** | **+169** |

- **Mutation checks** (82 rows; each applied, pytest run, then reverted):

  | Mutation | Failing test |
  |---|---|
  | Swap `create_page` from the API operation set into the browser set | `test_operation_uses_api_adapter[create_page]` |
  | Fall back on `except Exception` after a non-idempotent write is invoked | `test_write_error_is_not_retried_on_the_other_adapter[RuntimeError]` |
  | Catch `RuntimeError` after a non-idempotent write and fall back | `test_write_error_is_not_retried_on_the_other_adapter[RuntimeError]` |
  | Catch `ValueError` after a non-idempotent write and fall back | `test_write_error_is_not_retried_on_the_other_adapter[ValueError]` |
  | Fall back on `TypeError` from a read | `test_type_error_propagates_unchanged` |
  | Fall back on `PermissionError` from a read | `test_auth_error_propagates_unchanged` |
  | Remove the `reports_unsupported` pre-check | `test_fallback_when_preferred_reports_unsupported[create_page-api]` |
  | Drop the `reports_unsupported` bool check | `test_reports_unsupported_must_return_bool` |
  | Drop the `get_public_url` str check | `test_get_public_url_rejects_a_non_str_url` |
  | Fall back on `NotImplementedError` after a non-idempotent write is invoked | `test_write_not_implemented_error_is_not_retried` |
  | Fall back on a `NotImplementedError` subclass after a non-idempotent write is invoked | `test_write_not_implemented_subclass_is_not_retried` |
  | Fall back on `OperationUnsupportedError` after a non-idempotent write is invoked | `test_write_operation_unsupported_error_is_not_retried` |
  | Drop the read-side `OperationUnsupportedError` fallback | `test_read_operation_unsupported_error_falls_back` |
  | Skip `OperationUnsupportedError` fallback for an idempotent write | `test_idempotent_operation_unsupported_error_falls_back` |
  | Widen the read/idempotent `except` with `RuntimeError` | `test_read_and_idempotent_error_propagates[inspect_page-RuntimeError]` |
  | Widen the read/idempotent `except` with `ConnectionError` | `test_read_and_idempotent_error_propagates[inspect_page-ConnectionError]` |
  | Widen the read/idempotent `except` with `ValueError` | `test_read_and_idempotent_error_propagates[inspect_page-ValueError]` |
  | Widen the read/idempotent `except` with `KeyError` | `test_read_and_idempotent_error_propagates[inspect_page-KeyError]` |
  | Widen the read/idempotent `except` with `AttributeError` | `test_read_and_idempotent_error_propagates[inspect_page-AttributeError]` |
  | Widen the read/idempotent `except` with `NotImplementedError` | `test_read_and_idempotent_error_propagates[inspect_page-NotImplementedError]` |
  | Widen the read/idempotent `except` with `LookupError` | `test_read_and_idempotent_error_propagates[inspect_page-LookupError]` |
  | Catch `TypeError` after a non-idempotent write and fall back | `test_write_type_and_permission_errors_propagate[create_page-TypeError]` |
  | Catch `TypeError` after a browser-preferred write and fall back | `test_write_type_and_permission_errors_propagate[duplicate_page-TypeError]` |
  | Catch `PermissionError` after a non-idempotent write and fall back | `test_write_type_and_permission_errors_propagate[create_page-PermissionError]` |
  | Catch `PermissionError` after a browser-preferred write and fall back | `test_write_type_and_permission_errors_propagate[duplicate_page-PermissionError]` |
  | Return the API public URL without stranger verification | `test_get_public_url_returns_none_when_stranger_access_fails` |
  | Turn a stranger-check error into `None` | `test_get_public_url_does_not_hide_stranger_access_errors` |
  | Drop the stranger-check bool type check | `test_get_public_url_rejects_a_non_bool_stranger_check` |
  | Raise the fallback error without `from first` | `test_unsupported_fallback_error_is_chained_from_the_first_error[operation_unsupported]` |
  | Pass `parent_id=None` from `create_page` | `test_operation_forwards_every_argument[create_page]` |
  | Drop `icon=` in `create_page` | `test_operation_forwards_every_argument[create_page]` |
  | Drop `new_parent_type=` in `move_page` | `test_operation_forwards_every_argument[move_page]` |
  | Hard-code `enabled=True` in `set_search_indexing` | `test_operation_forwards_every_argument[set_search_indexing]` |
  | Hard-code `icon="💡"` in `add_callout_block` | `test_operation_forwards_every_argument[add_callout_block]` |
  | Pass `new_title=page_id` from `rename_page` | `test_operation_forwards_every_argument[rename_page]` |
  | Drop `visible=` in `set_view_title_visibility` | `test_operation_forwards_every_argument[set_view_title_visibility]` |
  | Change `raise translated from e` to `raise translated from None` on `fill` | `test_translating_session_keeps_original_playwright_error_as_cause[fill]` |
  | Change `raise translated from e` to `raise translated from None` on `close` | `test_translating_session_keeps_original_playwright_error_as_cause[close]` |
  | Write `job_id` from `operation` | `test_reloaded_receipt_round_trips_every_field` |
  | Write `operation` from `workspace` | `test_reloaded_receipt_round_trips_every_field` |
  | Write `workspace` from `target` | `test_reloaded_receipt_round_trips_every_field` |
  | Write `target` from `job_id` | `test_reloaded_receipt_round_trips_every_field` |
  | Write `idempotency_key` from `evidence` | `test_reloaded_receipt_round_trips_every_field` |
  | Remove the in-file duplicate idempotency-key check | `test_load_rejects_duplicate_idempotency_key` |
  | Remove the `timestamp` datetime check | `test_timestamp_must_be_a_datetime` |
  | Store `post_state` without the mapping check | `test_post_state_must_be_a_mapping` |
  | Accept a naive timestamp | `test_naive_timestamp_is_rejected` |
  | Accept a timestamp whose `utcoffset()` is `None` | `test_timestamp_with_null_utcoffset_is_rejected` |
  | Accept a status outside Success, Unknown, and Failure | `test_status_rejects_values_outside_the_enum` |
  | Accept a case-folded status | `test_lowercase_success_status_is_rejected` |
  | Reject a torn trailing line | `test_torn_trailing_line_is_skipped` |
  | Skip a complete JSON tail that has no newline | `test_complete_json_tail_without_newline_is_kept` |
  | Skip tail repair before append (torn tail) | `test_record_after_torn_tail_round_trips` |
  | Skip tail repair before append (complete line without newline) | `test_record_after_complete_line_without_newline_round_trips` |
  | Skip the pre-append re-read | `test_two_logs_reject_a_duplicate_key_without_corrupting_the_file` |
  | Allow `NaN` in receipt JSON | `test_non_finite_numbers_are_rejected[nan]` |
  | Remove the `record()` duplicate idempotency-key guard | `test_duplicate_idempotency_key_is_rejected_and_not_appended` |
  | Store the caller mapping without copying it | `test_caller_dict_mutation_does_not_change_the_stored_receipt` |
  | Return a tuple from `_freeze_value` without freezing its elements | `test_tuple_nested_mapping_is_frozen` |
  | Leave nested lists mutable | `test_nested_list_and_mapping_are_frozen` |
  | Re-introduce deepcopy of a frozen mapping | `test_replace_keeps_nested_state_frozen` |
  | Accept non-string mapping keys | `test_non_string_mapping_keys_are_rejected` |
  | Accept a non-string key nested in a tuple | `test_nested_non_string_mapping_keys_are_rejected` |
  | per-instance lock instead of shared path lock | `test_same_resolved_path_shares_one_lock` |
  | `record()` does not take the path lock | `test_record_waits_for_the_path_lock` |
  | Keep discarded path locks in a strong registry | `test_discarded_log_drops_its_path_lock` |
  | Accept a missing parent directory | `test_missing_parent_directory_is_rejected` |
  | Accept a `str` path | `test_string_path_is_rejected` |
  | Pass a caller MappingProxyType through unchanged | `test_caller_mapping_proxy_list_mutation_does_not_change_the_receipt` |
  | Drop the receipt cycle and depth guards | `test_cycles_and_deep_nesting_raise_value_error` |
  | Never discard ids from the cycle-tracking set | `test_shared_subcontainers_round_trip` |
  | Set the nesting limit to 31 | `test_nesting_accepts_33_containers_and_rejects_34` |
  | Set the nesting limit to 33 | `test_nesting_accepts_33_containers_and_rejects_34` |
  | Set the nesting limit to 39 | `test_nesting_accepts_33_containers_and_rejects_34` |
  | Compare nesting depth with `>=` instead of `>` | `test_nesting_accepts_33_containers_and_rejects_34` |
  | Lists do not add a depth level | `test_deep_list_nest_raises_value_error` |
  | Let `json.loads` `RecursionError` escape on load | `test_deeply_nested_json_line_raises_value_error` |
  | Decode an incomplete UTF-8 tail as part of the log | `test_incomplete_utf8_tail_is_skipped` |
  | Write receipts with ensure_ascii=False | `test_recorded_lines_are_ascii` |
  | Use find instead of rfind when decoding a torn tail | `test_incomplete_utf8_tail_is_skipped` |
  | Use find instead of rfind when repairing a torn tail | `test_record_after_torn_tail_round_trips` |
  | Let a deeply nested torn tail raise RecursionError | `test_deeply_nested_torn_tail_is_skipped` |

- **Control update**: `docs/control/IMPLEMENTATION_STATE.json` `session_06_w5` and this log entry. `state_revision` went from 38 to 40 against base. The `session_06_w4b` note was changed. `updated_at` was refreshed. `control_files_and_checkpoint_current` stays false. The session stays incomplete.
- **Hard boundaries**: fixtures and mocks only. No live Notion or Etsy, no real browser, no Playwright import. Fixture adapter stays the default. `src/money_machine/orchestration/` untouched. `uv.lock` untouched. Exit 78 held.


## 2026-09-26 — Session 06 Wave 6: formula and schema builders

- **Heading**: `### 5. Implement formula and schema builders` in `prompts/implementation/09_SESSION_06_NOTION_INTEGRATION_FOUNDATION.md` and `hands-off-money-machine-full-implementation-workbook.md`.
- **Narrow reading**: Reusable in-memory builders that return a typed schema for each named kind, each kind its own typed record rather than one agent prompt; plus a notification-dashboard formula generator. Each formula is attached to one catalogue database and may reference only properties of that database, with verified names and types. No relations, rollups, views, publishing, adapter calls, or live Notion. Formula language is a call subset (`prop`, `if`, `and`, `or`, `not`, `empty`, `now`, `formatDate`, `equal`, `subtract`), not Notion's full formula language. `equal` and `subtract` exist only because the dashboard formulas need a comparison and a subtraction. Session 07 section 4 names a configured buyer name and does not name `client_name`. That buyer name is deferred to Session 07 and is not emitted, and `client_name` is not emitted either. That is the simpler faithful option: this wave does not add a configured text property. `current_date` is `now()` on Tasks. `task_open_and_due_today` is this Tasks row (not a count) whose Due calendar day equals today. That per-row rename is a justified correction because a formula evaluates per row and the count belongs in a section 6 rollup. `birthday_status` is this Events row whose month and day equal today so it recurs yearly. A February 29 birthday matches only when today is February 29, so it fires only in leap years; the expression does not special-case that date. `money_spent_today` is this Finance row's amount when its calendar date is today otherwise 0 (not a sum). Those three compare `formatDate` calendar values. `water_glasses_remaining` is Goal minus Glasses on Habits and is omitted when Habits is not verified. A dashboard formula is omitted when its database is not in the verified map, so each personal-only preset generates a dashboard on its own and water glasses are omitted when Habits is absent. A database key that is not in schema_definitions() is rejected and the error names that key and the valid keys. A known database that is simply absent is still skipped, and an empty formula result is not an error. The February 29 test helper compares month-day strings only. The helper does not evaluate the Birthday checkbox. Names reject surrounding tab, newline, NBSP, and ideographic space, plus U+200B and U+FEFF anywhere in the name. Formula number literals accept only ASCII digits. A February 29 birthday matches only on February 29, so it does not fire on February 28 or March 1 in a non-leap year. Surrounding whitespace is rejected and does not count toward the 128-character limit; characters inside the expression do. Section 6 (relations and linked views) and section 7 (publishing) are out of scope.
- **Builders**: `build_database_schema` and `schema_definitions` return one frozen `DatabaseSchema` per kind, in heading order. Personal kinds are Tasks, Events, Habits, Finance, Meals, and Notes. Business kinds are Clients, Projects, Content, and Invoices. `build_schema` copies the caller property sequence and option sequence before validation. Names are strings of length 1 through 64 with no surrounding whitespace. A schema has 1 through 12 properties and exactly one title. Property types are title, text, number, select, multi_select, date, checkbox, formula, url, and email. Select and multi_select options number 1 through 8, are unique, and are rejected on every other type. A formula property requires an expression and a result type and is compiled against sibling property names and types, excluding its own name. Cycles across formula properties are rejected at build time. A non-formula property rejects those fields. `compile_formula` accepts expressions of length 5 through 128 and call depth 1 through 4. Surrounding whitespace is rejected. Result types are text, number, checkbox, and date, and the declared result type must match the expression for literals, `prop()` of a known type, and the top-level function return type. `prop` names must be in the copied verified mapping for that database. `generate_notification_dashboard_formulas` rejects an empty verified mapping, then compiles current_date, task_open_and_due_today, birthday_status, money_spent_today, and water_glasses_remaining against the properties of the database each formula is attached to. Session 07 section 4 names a configured buyer name and does not name `client_name`. Neither name is compiled. Due and money dates use `formatDate` with `YYYY-MM-DD`. Birthday uses `MM-DD`, so a February 29 birthday fires only in leap years. A dashboard formula whose database is absent from the verified map is omitted. A database key outside schema_definitions() is rejected. An empty formula result is not an error. The cycle check visits every formula, including a cycle that the first formula does not reach. `multi_select` and `date` keep their formula value types. `build_schema` defaults the family to personal. A formula property's result type propagates to formulas that reference it. Invalid input raises `SchemaBuilderError`. An unverified `prop` name raises `UnverifiedPropertyNameError`.
- **Pytest collected**: 1454 collected, 1453 passed, 1 skipped. W5 baseline: 1257 collected, 1256 passed, 1 skipped. Delta +197 collected and +197 passed.
- **Per-file counts**:

  | File | Functions (base → tip) | Collected (base → tip) | Delta collected |
  |---|---|---|---|
  | `tests/unit/integrations/notion/test_schema_builder.py` | 0 → 60 | 0 → 96 | +96 |
  | `tests/unit/integrations/notion/test_formulas.py` | 0 → 68 | 0 → 101 | +101 |
  | Remaining files | unchanged | 1257 → 1257 | 0 |
  | **Total** | | **1257 → 1454** | **+197** |

- **Mutation checks** (156 rows; each applied, pytest run, then reverted):

  | Mutation | Failing test |
  |---|---|
  | Set the name length limit to 63 | `test_property_name_length_within_limit[64]` |
  | Set the name length limit to 65 | `test_property_name_one_past_max_is_rejected` |
  | Compare name length with >= | `test_property_name_length_within_limit[64]` |
  | Remove the name length check | `test_property_name_one_past_max_is_rejected` |
  | Remove the empty-name check | `test_empty_database_name_is_rejected` |
  | Remove the surrounding-whitespace check | `test_property_name_whitespace_is_rejected` |
  | Remove the name type check | `test_property_name_must_be_a_string` |
  | Set the minimum formula length to 6 | `test_formula_length_within_limit[5]` |
  | Set the minimum formula length to 4 | `test_formula_length_one_under_min_is_rejected` |
  | Compare formula length with <= on the minimum | `test_formula_length_within_limit[5]` |
  | Set the maximum formula length to 127 | `test_formula_length_within_limit[128]` |
  | Set the maximum formula length to 129 | `test_formula_length_one_past_max_is_rejected` |
  | Compare formula length with >= | `test_formula_length_within_limit[128]` |
  | Remove the empty-expression check | `test_empty_formula_expression_is_rejected` |
  | Remove the expression type check | `test_formula_expression_must_be_a_string` |
  | Set the formula depth limit to 3 | `test_formula_depth_within_limit[4]` |
  | Set the formula depth limit to 5 | `test_formula_depth_one_past_limit_is_rejected` |
  | Compare formula depth with >= | `test_formula_depth_within_limit[4]` |
  | Remove the formula depth check | `test_formula_depth_one_past_limit_is_rejected` |
  | Remove the depth-zero rejection | `test_formula_literal_depth_zero_is_rejected` |
  | Function calls do not add a depth level | `test_formula_depth_within_limit[1]` |
  | Count an empty call as depth 0 | `test_now_call_is_accepted_at_depth_one` |
  | Drop formula type text | `test_allowed_formula_type_is_accepted[text]` |
  | Drop formula type number | `test_allowed_formula_type_is_accepted[number]` |
  | Drop formula type checkbox | `test_allowed_formula_type_is_accepted[checkbox]` |
  | Drop formula type date | `test_allowed_formula_type_is_accepted[date]` |
  | Drop the allowed formula-type check | `test_disallowed_formula_type_is_rejected[select]` |
  | Accept an unverified property name | `test_missing_verified_name_is_rejected` |
  | Store the verified set as the referenced names | `test_referenced_names_are_the_prop_names_only` |
  | Allow an empty verified-name set | `test_empty_verified_names_are_rejected` |
  | Drop the verified-properties mapping check | `test_verified_names_reject_a_string` |
  | Accept a list as the verified property mapping | `test_verified_properties_reject_a_list` |
  | Accept a non-string verified name | `test_verified_names_must_be_strings` |
  | Store the caller verified-name collection | `test_caller_verified_names_are_isolated` |
  | Return a mutable expression mapping | `test_dashboard_mappings_are_immutable` |
  | Return a mutable result-type mapping | `test_dashboard_mappings_are_immutable` |
  | Return a mutable database mapping | `test_dashboard_mappings_are_immutable` |
  | Return a mutable per-database property mapping | `test_dashboard_mappings_are_immutable` |
  | Insert client_name into the dashboard key list | `test_dashboard_formulas_use_verified_property_names` |
  | Change current_date result type to text | `test_dashboard_formulas_use_verified_property_names` |
  | Replace task_open_and_due_today with prop("Due") | `test_dashboard_formulas_use_verified_property_names` |
  | Replace birthday_status with prop("Birthday") | `test_dashboard_formulas_use_verified_property_names` |
  | Replace money_spent_today with prop("Amount") | `test_dashboard_formulas_use_verified_property_names` |
  | Compare task due date to raw now() | `test_dashboard_formulas_use_verified_property_names` |
  | Compare birthday date to raw now() | `test_dashboard_formulas_use_verified_property_names` |
  | Compare money date to raw now() | `test_dashboard_formulas_use_verified_property_names` |
  | Use YYYY-MM-DD for birthday_status | `test_dashboard_formulas_use_verified_property_names` |
  | Compare a birthday to the literal 02-29 | `test_february_29_birthday_matches_only_in_a_leap_year` |
  | Match a February 29 birthday on February 28 | `test_february_29_birthday_matches_only_in_a_leap_year` |
  | Replace water_glasses_remaining with prop("Glasses") | `test_dashboard_formulas_use_verified_property_names` |
  | Set prop() arity to 2 | `test_prop_rejects_two_arguments` |
  | Set now() arity to 1 | `test_now_rejects_an_argument` |
  | Set not() arity to 0 | `test_formula_depth_within_limit[2]` |
  | Set empty() arity to 0 | `test_format_date_and_empty_are_accepted` |
  | Set if() arity to 2 | `test_if_rejects_two_arguments` |
  | Drop formatDate from the allowed functions | `test_format_date_and_empty_are_accepted` |
  | Drop or from the allowed functions | `test_or_accepts_two_arguments` |
  | Allow and() with one argument | `test_and_rejects_one_argument` |
  | Allow an unknown formula function | `test_unknown_function_is_rejected` |
  | Accept trailing formula input | `test_trailing_input_is_rejected` |
  | Allow escapes in formula strings | `test_formula_string_escape_is_rejected` |
  | Accept an unclosed formula string | `test_unclosed_string_is_rejected` |
  | Accept an unclosed formula call | `test_unclosed_call_is_rejected` |
  | Allow a non-string prop() argument | `test_prop_requires_a_string` |
  | Skip the result-type check | `test_result_type_must_match_the_expression` |
  | Treat every prop() as text | `test_prop_uses_the_verified_type` |
  | Drop the if() checkbox condition check | `test_if_condition_must_be_checkbox` |
  | Allow if() branches of different types | `test_if_branches_must_have_the_same_type` |
  | Allow equal() arguments of different types | `test_equal_rejects_different_types` |
  | Drop the subtract() number checks | `test_subtract_rejects_a_non_number` |
  | Drop the formatDate() date check | `test_format_date_rejects_a_non_date` |
  | Drop the formatDate() text check | `test_format_date_rejects_a_non_text_pattern` |
  | Drop the and/or checkbox check | `test_and_rejects_a_non_checkbox` |
  | Drop the not() checkbox check | `test_not_rejects_a_non_checkbox` |
  | Drop the subtract() second number check | `test_subtract_rejects_a_non_number_subtrahend` |
  | Map multi_select to number | `test_multi_select_formula_value_is_text` |
  | Map date to text | `test_date_formula_value_is_date` |
  | Accept an Arabic-Indic digit as a number | `test_arabic_indic_digit_is_rejected` |
  | Accept a fullwidth digit inside a number | `test_fullwidth_digit_is_rejected` |
  | Drop equal from the allowed functions | `test_dashboard_formulas_use_verified_property_names` |
  | Drop subtract from the allowed functions | `test_dashboard_formulas_use_verified_property_names` |
  | Accept surrounding whitespace on a formula | `test_formula_surrounding_whitespace_is_rejected` |
  | Strip only an ASCII space from a name | `test_name_unicode_whitespace_is_rejected[leading-nbsp]` |
  | Ignore trailing whitespace on a name | `test_name_trailing_space_is_rejected` |
  | Strip only an ASCII space from a formula | `test_formula_unicode_whitespace_is_rejected[trailing-tab]` |
  | Allow U+200B in a name | `test_invisible_characters_in_names_are_rejected[zwsp]` |
  | Reject a BOM only at the edges of a name | `test_invisible_characters_in_names_are_rejected[bom-interior]` |
  | Look up a missing property on another database | `test_cross_database_property_is_rejected` |
  | Skip a missing database only for Clients and Habits | `test_each_personal_only_preset_generates_a_dashboard[Meals]` |
  | Require the Clients database for every dashboard | `test_personal_only_presets_generate_a_dashboard` |
  | Drop the missing-database skip | `test_habits_formula_is_skipped_when_habits_is_not_verified` |
  | Drop the unknown-database-key check | `test_unknown_database_key_is_rejected` |
  | Skip every dashboard formula | `test_each_personal_only_preset_generates_a_dashboard[Tasks]` |
  | Skip the catalogue property-type check | `test_dashboard_property_type_must_match_the_catalogue` |
  | Drop property type title | `test_allowed_property_type_is_accepted[title]` |
  | Drop property type text | `test_allowed_property_type_is_accepted[text]` |
  | Drop property type number | `test_allowed_property_type_is_accepted[number]` |
  | Drop property type select | `test_allowed_property_type_is_accepted[select]` |
  | Drop property type multi_select | `test_allowed_property_type_is_accepted[multi_select]` |
  | Drop property type date | `test_allowed_property_type_is_accepted[date]` |
  | Drop property type checkbox | `test_allowed_property_type_is_accepted[checkbox]` |
  | Drop property type formula | `test_allowed_property_type_is_accepted[formula]` |
  | Drop property type url | `test_allowed_property_type_is_accepted[url]` |
  | Drop property type email | `test_allowed_property_type_is_accepted[email]` |
  | Accept a property type outside the allowed set | `test_disallowed_property_type_is_rejected[relation]` |
  | Set the minimum property count to 2 | `test_property_count_within_limit[1]` |
  | Set the minimum property count to 0 | `test_empty_properties_are_rejected` |
  | Compare property count with <= on the minimum | `test_property_count_within_limit[1]` |
  | Set the maximum property count to 11 | `test_property_count_within_limit[12]` |
  | Set the maximum property count to 13 | `test_property_count_one_past_max_is_rejected` |
  | Compare property count with >= | `test_property_count_within_limit[12]` |
  | Set the minimum option count to 2 | `test_option_count_within_limit[1]` |
  | Set the minimum option count to 0 | `test_empty_select_options_are_rejected` |
  | Compare option count with <= on the minimum | `test_option_count_within_limit[1]` |
  | Set the maximum option count to 7 | `test_option_count_within_limit[8]` |
  | Set the maximum option count to 9 | `test_option_count_one_past_max_is_rejected` |
  | Compare option count with >= | `test_option_count_within_limit[8]` |
  | Allow duplicate select options | `test_duplicate_option_is_rejected` |
  | Allow options on a non-select property | `test_options_on_a_non_select_are_rejected` |
  | Reject an empty option tuple on every property | `test_property_count_within_limit[1]` |
  | Drop multi_select from the option types | `test_multi_select_accepts_options` |
  | Return the caller option sequence without copying | `test_caller_option_list_mutation_does_not_change_the_schema` |
  | Accept a string as the property sequence | `test_properties_must_be_a_sequence_of_mappings` |
  | Accept a property that is not a mapping | `test_property_must_be_a_mapping` |
  | Accept an unknown property field | `test_unknown_property_field_is_rejected` |
  | Accept a string as the option sequence | `test_options_must_be_a_sequence` |
  | Allow a duplicated property name | `test_duplicate_property_name_is_rejected` |
  | Allow a schema with no title | `test_schema_without_a_title_is_rejected` |
  | Allow two title properties | `test_schema_with_two_titles_is_rejected` |
  | Allow a formula expression on a text property | `test_formula_expression_on_text_is_rejected` |
  | Allow a formula result type on a text property | `test_formula_result_type_on_text_is_rejected` |
  | Allow a formula property with no expression | `test_formula_property_requires_an_expression` |
  | Allow a formula property with no result type | `test_formula_property_requires_a_result_type` |
  | Treat a formula property name as verified for itself | `test_formula_property_rejects_its_own_name` |
  | Treat every formula property as text | `test_equal_rejects_a_number_formula_compared_with_text` |
  | Treat every formula property as a number | `test_checkbox_formula_is_accepted_as_an_if_condition` |
  | Visit only the first formula when checking cycles | `test_cycle_behind_an_acyclic_formula_is_rejected` |
  | Visit only the last formula when checking cycles | `test_cycle_in_the_middle_of_the_formula_list_is_rejected` |
  | Remove the formula cycle check | `test_two_formula_cycle_is_rejected` |
  | Only reject mutual formula pairs | `test_three_formula_cycle_is_rejected` |
  | Treat a non-formula reference as a cycle | `test_acyclic_formula_chain_is_accepted` |
  | Accept a schema family outside personal and business | `test_schema_family_must_be_personal_or_business` |
  | Default the schema family to business | `test_schema_family_defaults_to_personal` |
  | Look up a database kind case-insensitively | `test_unknown_database_kind_is_rejected` |
  | Swap personal and business families | `test_catalogue_schema[Clients]` |
  | Return one prompt string instead of separate schema records | `test_each_database_definition_is_its_own_record` |
  | Change the Tasks Status options | `test_catalogue_schema[Tasks]` |
  | Change Events Birthday from checkbox to text | `test_catalogue_schema[Events]` |
  | Change Habits Glasses from number to text | `test_catalogue_schema[Habits]` |
  | Change Finance Amount from number to text | `test_catalogue_schema[Finance]` |
  | Change Meals Day from date to text | `test_catalogue_schema[Meals]` |
  | Change Notes Body from text to number | `test_catalogue_schema[Notes]` |
  | Change Clients Email from email to text | `test_catalogue_schema[Clients]` |
  | Change the Projects Status options | `test_catalogue_schema[Projects]` |
  | Change Content URL from url to text | `test_catalogue_schema[Content]` |
  | Change the Invoices Status options | `test_catalogue_schema[Invoices]` |

- **Control update**: `docs/control/IMPLEMENTATION_STATE.json` `session_06_w6` and this log entry. `state_revision` 40 to 42 vs base. `updated_at` was refreshed. `control_files_and_checkpoint_current` stays false. The session stays incomplete.
- **Hard boundaries**: fixtures and mocks only. No live Notion or Etsy, no real browser, no Playwright import. Fixture adapter stays the default. `src/money_machine/orchestration/` untouched. `uv.lock` untouched. `pyproject.toml` untouched. `src/money_machine/integrations/notion/router.py` untouched. Exit 78 held.

## 2026-09-26 — Session 06 Wave 7: relation and linked-view helpers

- **Heading**: `### 6. Implement relation and linked-view helpers` in `prompts/implementation/09_SESSION_06_NOTION_INTEGRATION_FOUNDATION.md` and `hands-off-money-machine-full-implementation-workbook.md`.
- **Narrow reading**: One canonical database per catalogue data type. Hub views link to that database and do not create a second store. Filters are date, category, or status, the condition is equals, and a view has at most 3 filters. The home dashboard has a today view (open tasks due today), a monthly calendar, and quick notes. The notification dashboard is one row of relations and rollups over the section 5 formulas: Tasks `open_tasks_due_today` counts checked `task_open_and_due_today`, Events `birthday_status` counts checked `birthday_status`, Finance `money_spent_today` sums `money_spent_today`, and Habits `water_glasses_remaining` sums `water_glasses_remaining`. The relation must include today's row, and the formula contributes only today's row, so the rollup sum is today's value. `water_glasses_remaining` subtracts Glasses from Goal only when the Habits Date calendar day is today and is otherwise 0. A missing database omits its relation and rollup, so water glasses are omitted when Habits is absent. A filter property must exist and its type must fit the dimension. A status value and a category value must be options of that property. A date filter on the `current_date` formula is rejected. A rollup source must exist on the schema or as a dashboard formula, and the rollup function must fit the property type. Notes, Meals, and the business kinds do not add relations. `client_name`, the configured buyer name, and `current_date` are not emitted. No publishing, fixture-parity expansion, live connect, adapter calls, or Session 07 product build. No Notion, network, or browser calls.
- **Carry-forward**: Names reject U+200C, U+200D, U+2060, and U+00AD in the interior and at either edge. Notion evaluates now() and formatDate in the viewer's local time zone, API reads return UTC, and 'today' can differ near midnight. A formula that references itself, such as `A = prop("A")`, raises the formula-cycle error rather than the unverified-property error.
- **Helpers**: `build_canonical_databases` copies the caller sequence, rejects a string, a non-sequence, an empty sequence, a non-string item, an unknown kind (the error names the key and the valid keys), a case difference, and a duplicate. The registry mapping is immutable. `build_filter` accepts date, category, and status with condition equals, and validates the property name and value. A date value must be today, matched exactly, or an ASCII YYYY-MM-DD calendar date. `build_linked_view` requires the canonical registry, a registered data type, and a view type of table, calendar, or board. Hub and view names are validated. Filters are copied. `dashboard_today_view` is Dashboard / Tasks / table / Today with Due equals today and Status equals Open. `monthly_calendar` is Dashboard / Events / calendar / Month with no filters. `quick_notes` is Dashboard / Notes / table / Quick notes with no filters. `build_notification_dashboard` returns one row. Relation names are the data types. Rollups use checked for the two checkbox formulas and sum for the two number formulas. `CanonicalDatabase` and `CanonicalDatabases` reject an unknown data type in `__post_init__`. Each key must equal its entry data type, data types must not repeat, and the key set must equal `data_types`. `by_type` is stored as a copy. `ViewFilter` validates dimension, condition, property name, and value in `__post_init__`. Linked views and rollups are checked against `schema_definitions()` plus that database's own dashboard formulas. A category value must be an option of that property. A date filter on the `current_date` formula is rejected. The relation must include today's row, and the formula contributes only today's row, so the rollup sum is today's value. `DashboardRelation` rejects a blank name and an unknown data type in `__post_init__`. `NotificationDashboard` rejects a row count other than 1, relations that are not a tuple, rollups that are not a tuple, and a rollup that is not a `DashboardRollup`. An unknown rollup function is rejected. Invalid input raises `SchemaBuilderError`.
- **Pytest collected**: 1558 collected, 1557 passed, 1 skipped. W6 baseline: 1454 collected, 1453 passed, 1 skipped. Delta +104 collected and +104 passed.
- **Per-file counts**:

  | File | Functions (base → tip) | Collected (base → tip) | Delta collected |
  |---|---|---|---|
  | `tests/unit/integrations/notion/test_schema_builder.py` | 60 → 61 | 96 → 97 | +1 |
  | `tests/unit/integrations/notion/test_formulas.py` | 68 → 70 | 101 → 114 | +13 |
  | `tests/unit/integrations/notion/test_relations.py` | 0 → 85 | 0 → 90 | +90 |
  | Remaining files | unchanged | 1257 → 1257 | 0 |
  | **Total** | | **1454 → 1558** | **+104** |

- **Mutation checks** (123 rows; each applied, pytest run, then reverted):

| Mutation | Failing test |
|---|---|
| Drop U+200C from the invisible set | `test_added_invisible_characters_in_names_are_rejected[leading-zwnj]` |
| Drop U+200D from the invisible set | `test_added_invisible_characters_in_names_are_rejected[leading-zwj]` |
| Drop U+2060 from the invisible set | `test_added_invisible_characters_in_names_are_rejected[leading-word-joiner]` |
| Drop U+00AD from the invisible set | `test_added_invisible_characters_in_names_are_rejected[leading-soft-hyphen]` |
| Reject the added invisible characters only at the edges | `test_added_invisible_characters_in_names_are_rejected[interior-zwnj]` |
| Reject the added invisible characters only in the interior | `test_added_invisible_characters_in_names_are_rejected[trailing-zwnj]` |
| Exclude the formula's own name so a self-reference raises the unverified-property error | `test_self_referential_formula_raises_formula_cycle` |
| Accept a string as the data-type sequence | `test_data_types_reject_a_string` |
| Accept a non-sequence as the data types | `test_data_types_reject_a_non_sequence` |
| Remove the empty data-type check | `test_empty_data_types_are_rejected` |
| Accept a non-string data type | `test_data_type_must_be_a_string` |
| Accept an unknown data type | `test_unknown_data_type_is_rejected` |
| Omit the valid keys from the unknown data-type error | `test_unknown_data_type_is_rejected` |
| Look up a data type case-insensitively | `test_data_type_case_must_match` |
| Treat Invoices as an unknown data type | `test_each_catalogue_kind_is_its_own_canonical_database` |
| Allow a duplicated data type | `test_duplicate_data_type_is_rejected` |
| Store the caller data-type list | `test_caller_data_type_list_is_copied` |
| Sort the canonical data types | `test_each_catalogue_kind_is_its_own_canonical_database` |
| Store by_type as a plain dict in `CanonicalDatabases.__post_init__` | `test_canonical_mapping_is_immutable` |
| Drop date from the filter dimensions | `test_filter_dimension_is_accepted[date]` |
| Drop category from the filter dimensions | `test_filter_dimension_is_accepted[category]` |
| Drop status from the filter dimensions | `test_filter_dimension_is_accepted[status]` |
| Accept a filter dimension outside the set | `test_other_filter_dimension_is_rejected` |
| Accept a filter condition other than equals | `test_filter_condition_must_be_equals` |
| Skip filter property-name validation | `test_filter_property_name_must_be_present` |
| Skip filter value validation | `test_filter_value_must_be_present` |
| Drop table from the view types | `test_dashboard_today_view` |
| Drop calendar from the view types | `test_monthly_calendar` |
| Drop board from the view types | `test_two_hubs_link_to_one_canonical_database` |
| Accept a view type outside the set | `test_disallowed_view_type_is_rejected` |
| Link a view to a data type that is not canonical | `test_linked_view_rejects_a_database_that_is_not_canonical` |
| Accept a mapping in place of the canonical registry | `test_linked_view_requires_the_canonical_registry` |
| Skip hub name validation | `test_linked_view_rejects_an_empty_hub` |
| Skip view name validation | `test_linked_view_rejects_an_empty_name` |
| Set the filter limit to 2 | `test_three_filter_dimensions_are_accepted` |
| Set the filter limit to 4 | `test_four_filters_are_rejected` |
| Compare the filter count with >= | `test_three_filter_dimensions_are_accepted` |
| Allow a duplicated filter dimension | `test_duplicate_filter_dimension_is_rejected` |
| Accept a filter that is not a view filter | `test_filter_must_be_a_view_filter` |
| Return the caller filter sequence | `test_caller_filter_list_is_copied` |
| Accept a non-sequence of filters | `test_filters_must_be_a_sequence` |
| Change the today view to a calendar | `test_dashboard_today_view` |
| Point the today view at Events | `test_dashboard_today_view` |
| Drop the today date filter | `test_dashboard_today_view` |
| Drop the today status filter | `test_dashboard_today_view` |
| Compare the today status filter to Done | `test_dashboard_today_view` |
| Change the monthly calendar to a table | `test_monthly_calendar` |
| Point the monthly calendar at Tasks | `test_monthly_calendar` |
| Rename the monthly calendar | `test_monthly_calendar` |
| Add a filter to the monthly calendar | `test_monthly_calendar` |
| Change quick notes to a calendar | `test_quick_notes` |
| Point quick notes at Tasks | `test_quick_notes` |
| Rename quick notes | `test_quick_notes` |
| Set the dashboard row count to 2 | `test_notification_dashboard_is_one_row` |
| Return a list of dashboard rollups | `test_notification_dashboard_is_one_row` |
| Drop the Tasks rollup | `test_each_dashboard_database_adds_its_rollup[Tasks]` |
| Drop the Events rollup | `test_each_dashboard_database_adds_its_rollup[Events]` |
| Drop the Finance rollup | `test_each_dashboard_database_adds_its_rollup[Finance]` |
| Drop the Habits rollup | `test_each_dashboard_database_adds_its_rollup[Habits]` |
| Use sum for open_tasks_due_today | `test_each_dashboard_database_adds_its_rollup[Tasks]` |
| Use checked for money_spent_today | `test_each_dashboard_database_adds_its_rollup[Finance]` |
| Use sum for birthday_status | `test_each_dashboard_database_adds_its_rollup[Events]` |
| Use checked for water_glasses_remaining | `test_each_dashboard_database_adds_its_rollup[Habits]` |
| Roll up Due instead of task_open_and_due_today | `test_each_dashboard_database_adds_its_rollup[Tasks]` |
| Name the dashboard relation after the rollup | `test_each_dashboard_database_adds_its_rollup[Tasks]` |
| Point the rollup relation at the rollup name | `test_each_dashboard_database_adds_its_rollup[Tasks]` |
| Emit a rollup when its database is absent | `test_notes_does_not_add_a_dashboard_relation` |
| Skip a missing database only for Habits | `test_each_dashboard_database_adds_its_rollup[Tasks]` |
| Emit client_name on the dashboard | `test_dashboard_does_not_emit_client_name_or_current_date` |
| Emit current_date as a rollup | `test_dashboard_does_not_emit_client_name_or_current_date` |
| Accept a mapping in place of the dashboard registry | `test_notification_dashboard_requires_the_canonical_registry` |
| Skip ViewFilter validation | `test_hand_built_view_filter_is_rejected` |
| Look up a filter dimension before checking it is a string | `test_unhashable_filter_dimension_is_rejected` |
| Look up a data type before checking it is a string | `test_unhashable_data_type_is_rejected` |
| Look up a view type before checking it is a string | `test_unhashable_view_type_is_rejected` |
| Accept a string of filters | `test_filters_reject_a_string` |
| Reverse the copied filters | `test_filter_order_is_preserved` |
| Allow a filter on a missing property | `test_filter_on_a_missing_property_is_rejected` |
| Allow a date filter on a select property | `test_date_filter_on_a_select_property_is_rejected` |
| Allow a category filter on a date property | `test_category_filter_on_a_date_property_is_rejected` |
| Skip the status option check | `test_invalid_status_value_is_rejected` |
| Allow a calendar without a date property | `test_calendar_view_requires_a_date_property` |
| Allow a rollup whose source is missing | `test_missing_rollup_source_is_rejected` |
| Allow a rollup function that does not fit the property | `test_mismatched_rollup_function_is_rejected` |
| Drop the water date gate | `test_water_glasses_remaining_contributes_only_todays_row` |
| Accept a canonical key outside the catalogue | `test_canonical_key_must_be_catalogue` |
| Accept an entry data type outside the catalogue | `test_canonical_entry_data_type_must_be_catalogue` |
| Accept a key that does not match its entry | `test_canonical_key_must_match_entry_data_type` |
| Allow a repeated canonical data type | `test_canonical_data_types_must_not_repeat` |
| Allow canonical keys that do not match data types | `test_canonical_keys_must_match_data_types` |
| Hash a canonical data type before checking it is a string | `test_unhashable_canonical_data_type_is_rejected` |
| Accept a list of canonical data types | `test_canonical_data_types_must_be_a_tuple` |
| Accept a non-mapping canonical registry | `test_canonical_by_type_must_be_a_mapping` |
| Accept a canonical entry that is not a database | `test_canonical_entry_must_be_a_database` |
| Look up a catalogue data type before checking it is a string | `test_catalogue_data_type_must_be_a_string` |
| Keep the caller's by_type mapping | `test_caller_by_type_mutation_has_no_effect` |
| Accept an unknown CanonicalDatabase data type | `test_canonical_database_rejects_an_unknown_data_type` |
| Accept an unknown relation data type | `test_relation_data_type_must_be_canonical` |
| Skip relation name validation | `test_relation_name_must_not_be_blank` |
| Skip the notification dashboard row count check | `test_hand_built_notification_dashboard_rejects_a_row_count_other_than_one` |
| Accept a date filter value that is not a date | `test_date_filter_value_must_be_today_or_an_iso_date` |
| Accept the rollup function average | `test_unknown_rollup_function_is_rejected` |
| Look up an unknown rollup data type in the schema | `test_unknown_rollup_data_type_is_rejected` |
| Hash a rollup function before checking it is a string | `test_unhashable_rollup_function_is_rejected` |
| Skip rollup-name validation | `test_rollup_name_must_be_present` |
| Skip rollup-source validation | `test_rollup_source_name_must_be_present` |
| Attach every dashboard formula to the rollup database | `test_finance_formula_rollup_is_rejected_on_tasks` |
| Skip the category option check | `test_invalid_category_value_is_rejected` |
| Allow a date filter on a formula | `test_date_filter_on_current_date_formula_is_rejected` |
| Treat only an empty filters string as a string | `test_filters_reject_a_non_empty_string` |
| Treat only a row count above 1 as invalid | `test_hand_built_notification_dashboard_rejects_a_row_count_other_than_one` |
| Treat only a row count of 2 or more as invalid | `test_hand_built_notification_dashboard_rejects_a_row_count_other_than_one` |
| Accept an ISO-shaped date that is not a calendar date | `test_date_filter_value_must_be_today_or_an_iso_date` |
| Replace the calendar date check with return True | `test_date_filter_value_must_be_today_or_an_iso_date` |
| Compare today case-insensitively | `test_date_filter_value_must_be_today_or_an_iso_date` |
| Accept a junk dashboard relation | `test_hand_built_notification_dashboard_rejects_a_junk_relation` |
| Accept null dashboard rollups | `test_hand_built_notification_dashboard_rejects_null_rollups` |
| Accept a rollup with no matching relation | `test_hand_built_notification_dashboard_rejects_a_rollup_with_no_relation` |
| Accept a today prefix | `test_date_filter_value_must_be_today_or_an_iso_date` |
| Accept non-ASCII digits in an ISO date | `test_date_filter_value_must_be_today_or_an_iso_date` |
| Accept dashboard relations that are not a tuple | `test_hand_built_notification_dashboard_rejects_relations_that_are_not_a_tuple` |
| Treat only null rollups as the wrong type | `test_hand_built_notification_dashboard_rejects_a_list_of_rollups` |
| Accept a junk dashboard rollup | `test_hand_built_notification_dashboard_rejects_a_junk_rollup` |

- **Control update**: `docs/control/IMPLEMENTATION_STATE.json` `session_06_w7` and this log entry. `state_revision` 42 to 43 vs base. `updated_at` was refreshed. `control_files_and_checkpoint_current` stays false. The session stays incomplete.
- **Hard boundaries**: fixtures and mocks only. No live Notion or Etsy, no real browser, no Playwright import. Fixture adapter stays the default. `src/money_machine/orchestration/` untouched. `uv.lock` untouched. `pyproject.toml` untouched. `src/money_machine/integrations/notion/router.py` untouched. Exit 78 held.

## 2026-09-26 — Session 06 Wave 8: publishing and isolation helpers

- **Heading**: `### 7. Implement publishing and isolation helpers` in `prompts/implementation/09_SESSION_06_NOTION_INTEGRATION_FOUNDATION.md` and `hands-off-money-machine-full-implementation-workbook.md`.
- **Narrow reading**: A catalogue page is top level, published to the web, duplicate as template is on, and search indexing is off. The secret link is captured. Public access is verified. No link reaches a page that belongs to another catalogue. No fixture-parity expansion, live connect, adapter calls, or Session 07 product build. No Notion, network, or browser calls.
- **W7 cleanups folded in**: Deleted the unused `_decimal_digits` helper and the `unicodedata` import from `relations.py`. `_is_calendar_date` parses the original text with `date.fromisoformat`, so a non-ASCII digit is still rejected. The W7 row Accept non-ASCII digits in an ISO date is equivalent after that deletion, and that disposition is a new line in this entry. Deleted `isinstance(relations, str) or` from the notification-dashboard relations check. A string is not a tuple, so that clause changed no result; it is W8 row 1: re-add isinstance(relations, str) or. `NotificationDashboard` rejects a duplicated relation name, including a non-adjacent duplicate, with `SchemaBuilderError`. `DashboardRollup.__post_init__` rejects a blank name, a blank source, an unknown or non-string function, a data type outside the catalogue, a missing source, and a function that does not fit the source type. The unknown-function check says the function is not allowed. The fit check says the function does not fit or is not on the source type. Each check dies on its own test.
- **Helpers**: `build_published_page` returns a `PublishedPage`. The parent must be `workspace`, matched exactly. Published to web, duplicate as template, and public access must be `True`. Search indexing must be `False`. The page id, each link, and each other-catalogue page are stored as a lowercase undashed 32-hex id. A plain id is 32 hex with no dashes, or exactly the 8-4-4-4-12 layout, lowercased. A page-id URL must be https, with no userinfo, no query string, no empty question mark, no fragment, no parameters, and a port of none or 443, on `notion.so` or `www.notion.so` only. A bare `https://notion.so/<id>` is accepted and stored as the canonical id. Page references reject Unicode categories Cc, Cf, Zl, and Zp, and they reject padding that urlsplit would strip. `notion.site` is rejected in those fields. The id is the last path segment: an undashed 32-hex slug, a title plus one 32-hex tail, or a trailing 8-4-4-4-12. Uppercase hex is lowercased before isolation. Hex from a title is not joined onto a short id. A non-id, a host outside that pair, and a page that lists itself as another catalogue page are rejected. The same page is one id across uppercase, dashed, and URL forms. The same link written three ways is stored once, in first-seen order. The secret link must be a trimmed https URL with no userinfo and no character in Unicode categories Cc, Cf, Zl, Zp, or Zs. Its host may be `notion.so`, `www.notion.so`, `notion.site`, or a single label under `notion.site`. Its port is none or 443, and its path is not empty after stripping slashes. A malformed URL and a bad port raise `SchemaBuilderError`. Link and other-catalogue sequences are copied in canonical form. A link whose canonical id is in the other-catalogue pages is rejected, including when it is not the first link. Invalid input raises `SchemaBuilderError`.
- **Pytest collected**: 1718 collected, 1717 passed, 1 skipped. W7 baseline: 1558 collected, 1557 passed, 1 skipped. Delta +160 collected and +160 passed.
- **Per-file counts**:

| File | Functions (base → tip) | Collected (base → tip) | Passed (base → tip) | Failed (base → tip) | Skipped (base → tip) |
|---|---|---|---|---|---|
| `tests/unit/integrations/notion/test_relations.py` | 85 → 92 | 90 → 97 | 90 → 97 | 0 → 0 | 0 → 0 |
| `tests/unit/integrations/notion/test_publishing.py` | 0 → 81 | 0 → 153 | 0 → 153 | 0 → 0 | 0 → 0 |
| Remaining files | unchanged | 1468 → 1468 | 1467 → 1467 | 0 → 0 | 1 → 1 |
| **Total** | | **1558 → 1718** | **1557 → 1717** | **0 → 0** | **1 → 1** |

- **Mutation checks** (112 rows; each applied, pytest run, then reverted; 110 killed and 2 equivalent):

| Mutation | Site | Failing test |
|---|---|---|
| W8 row 1: re-add isinstance(relations, str) or | `relations.py:219` | equivalent: a string is not a tuple, so the remaining check already rejects it |
| Accept a duplicated dashboard relation name | `relations.py:228` | `test_notification_dashboard_rejects_duplicate_relation_names` |
| Skip hand-built rollup name validation | `relations.py:198` | `test_hand_built_rollup_name_must_be_present` |
| Skip hand-built rollup source validation | `relations.py:199` | `test_hand_built_rollup_source_must_be_present` |
| Look up a rollup function before checking it is a string | `relations.py:202` | `test_hand_built_rollup_function_must_be_known` |
| Accept an unknown rollup function on a hand-built rollup | `relations.py:202` | `test_hand_built_rollup_function_must_be_known` |
| Skip hand-built rollup data-type validation | `relations.py:200` | `test_hand_built_rollup_data_type_must_be_canonical` |
| Skip page id validation | `publishing.py:55` | `test_page_id_must_be_present` |
| Accept a parent that is not the workspace | `publishing.py:101` | `test_page_must_be_top_level` |
| Accept a published-to-web flag other than True | `publishing.py:106` | `test_page_must_be_published_to_web` |
| Accept a duplicate-as-template flag other than True | `publishing.py:111` | `test_duplicate_as_template_must_be_on` |
| Accept search indexing other than False | `publishing.py:116` | `test_search_indexing_must_be_off` |
| Accept public access other than True | `publishing.py:121` | `test_public_access_must_be_verified` |
| Accept a secret link that is not a string | `publishing.py:126` | `test_secret_link_must_be_a_string` |
| Accept an empty secret link | `publishing.py:128` | `test_secret_link_must_be_present` |
| Accept a padded secret link | `publishing.py:128` | `test_secret_link_must_be_present` |
| Accept a secret link whose scheme is not https | `publishing.py:136` | `test_secret_link_must_use_https` |
| Accept secret-link userinfo when only one of username or password is set | `publishing.py:138` | `test_secret_link_must_not_contain_userinfo` |
| Accept a secret-link host outside the allowlist | `publishing.py:143` | `test_secret_link_host_must_be_allowed` |
| Drop notion.so from the exact secret-link hosts | `publishing.py:27` | `test_secret_link_host_is_allowed[notion.so]` |
| Drop www.notion.so from the exact secret-link hosts | `publishing.py:27` | `test_secret_link_host_is_allowed[www.notion.so]` |
| Drop notion.site from the exact secret-link hosts | `publishing.py:27` | `test_secret_link_host_is_allowed[notion.site]` |
| Reject every single-label notion.site host | `publishing.py:168` | `test_secret_link_host_is_allowed[fixture.notion.site]` |
| Reject the www label on notion.site | `publishing.py:171` | `test_secret_link_host_is_allowed[www.notion.site]` |
| Allow a dotted notion.site prefix | `publishing.py:171` | `test_secret_link_rejects_a_nested_notion_site_label` |
| Allow an empty notion.site prefix | `publishing.py:171` | `test_secret_link_rejects_an_empty_notion_site_label` |
| Accept a secret link with an empty path | `publishing.py:145` | `test_secret_link_must_name_a_page` |
| Accept a secret link whose path is only / | `publishing.py:145` | `test_secret_link_must_name_a_page` |
| Accept links that are not a sequence | `publishing.py:175` | `test_links_must_be_a_sequence` |
| Accept a string of links | `publishing.py:175` | `test_links_reject_a_string` |
| Skip link page-id validation | `publishing.py:62` | `test_link_must_be_a_page_id` |
| Skip other-catalogue page-id validation | `publishing.py:64` | `test_other_catalogue_page_must_be_a_page_id` |
| Accept other catalogue pages that are not a sequence | `publishing.py:64` | `test_other_catalogue_pages_must_be_a_sequence` |
| Store the caller link sequence | `publishing.py:71` | `test_caller_link_list_is_copied` |
| Store the caller other-catalogue sequence | `publishing.py:72` | `test_caller_other_catalogue_list_is_copied` |
| Reverse the copied links | `publishing.py:71` | `test_link_order_is_preserved` |
| Accept a link that reaches another catalogue | `publishing.py:295` | `test_a_later_link_to_another_catalogue_is_rejected` |
| Check only the first link against other catalogue pages | `publishing.py:294` | `test_a_later_link_to_another_catalogue_is_rejected` |
| W7 non-ASCII ISO date row | `relations.py:46` | equivalent: deleting _decimal_digits still rejects a non-ASCII digit |
| Reset seen relation names instead of adding | `relations.py:230` | `test_notification_dashboard_rejects_non_adjacent_duplicate_relation_names` |
| Skip the hand-built rollup source and fit check | `relations.py:204` | `test_hand_built_rollup_source_must_fit` |
| Compare the parent case-insensitively | `publishing.py:101` | `test_page_must_be_top_level` |
| Strip the parent before comparing it | `publishing.py:101` | `test_page_must_be_top_level` |
| Treat only None as a non-string secret link | `publishing.py:126` | `test_secret_link_must_be_a_string` |
| Accept a control character in the secret link | `publishing.py:130` | `test_secret_link_rejects_a_control_character` |
| Accept a secret-link port other than 443 | `publishing.py:140` | `test_secret_link_rejects_a_port_other_than_443` |
| Let a bad secret-link port raise ValueError | `publishing.py:161` | `test_secret_link_rejects_a_port_other_than_443` |
| Reject secret-link port 443 | `publishing.py:140` | `test_secret_link_allows_port_443` |
| Accept a secret link whose path is // | `publishing.py:145` | `test_secret_link_rejects_a_double_slash_path` |
| Do not lowercase a page id | `publishing.py:213` | `test_isolation_catches_an_uppercase_id` |
| Do not remove dashes from a page id | `publishing.py:211` | `test_isolation_catches_a_dashed_id` |
| Do not read a page id from a URL | `publishing.py:198` | `test_isolation_catches_a_notion_so_url` |
| Accept a notion.site page URL | `publishing.py:237` | `test_page_url_rejects_a_notion_site_host` |
| Accept a page reference that is not a 32-hex id | `publishing.py:214` | `test_page_reference_rejects_a_non_id` |
| Accept a page that lists itself as another catalogue | `publishing.py:291` | `test_page_rejects_itself_as_another_catalogue_page` |
| Widen a plain page id to 31-33 characters | `publishing.py:214` | `test_plain_page_id_length_and_hex_are_required` |
| Accept word characters as a plain page id | `publishing.py:214` | `test_plain_page_id_length_and_hex_are_required` |
| Drop the plain page-id hex check | `publishing.py:214` | `test_plain_page_id_length_and_hex_are_required` |
| Accept an http page URL | `publishing.py:237` | `test_page_url_must_use_https` |
| Accept any page-id host | `publishing.py:237` | `test_page_url_host_must_be_allowed` |
| Do not lowercase a page id taken from a URL | `publishing.py:264` | `test_isolation_lowercases_an_uppercase_url_id` |
| Do not lowercase an uppercase-hex slug | `publishing.py:283` | `test_isolation_lowercases_an_uppercase_slug` |
| Do not strip a trailing slash from a page URL | `publishing.py:239` | `test_isolation_keeps_a_trailing_slash_on_the_page_id` |
| Read the first path segment as the page id | `publishing.py:239` | `test_isolation_catches_a_nested_page_path` |
| Drop the longer-than-32 slug guard | `publishing.py:265` | `test_page_url_rejects_a_slug_longer_than_32_hex` |
| Drop the undashed slug hex check | `publishing.py:269` | `test_page_url_rejects_a_non_hex_slug` |
| Accept a non-hex slug part | `publishing.py:281` | `test_page_url_rejects_a_non_hex_slug` |
| Reject a titled page slug | `publishing.py:258` | `test_isolation_catches_a_titled_slug` |
| Store the original page id | `publishing.py:70` | `test_page_references_are_stored_in_canonical_form` |
| Drop the page-id string check | `publishing.py:192` | `test_page_reference_must_be_a_string` |
| Drop the page-id padding check | `publishing.py:196` | `test_page_url_rejects_padding` |
| Let a malformed secret link raise ValueError | `publishing.py:132` | `test_secret_link_rejects_a_malformed_url` |
| Let a malformed page URL raise ValueError | `publishing.py:220` | `test_page_url_rejects_a_malformed_url` |
| Let a bad page-url port raise ValueError | `publishing.py:247` | `test_page_url_rejects_a_port` |
| Drop Unicode category Cc | `publishing.py:151` | `test_secret_link_rejects_del` |
| Drop Unicode category Zl | `publishing.py:151` | `test_secret_link_rejects_a_line_separator` |
| Drop Unicode category Cf | `publishing.py:151` | `test_secret_link_rejects_a_format_character` |
| Accept an empty secret-link port | `publishing.py:140` | `test_secret_link_rejects_an_empty_port` |
| Accept secret-link port 80 | `publishing.py:140` | `test_secret_link_rejects_a_port_other_than_443` |
| Accept a secret link whose path is /// | `publishing.py:145` | `test_secret_link_rejects_a_triple_slash_path` |
| Accept page-url userinfo when only one of username or password is set | `publishing.py:224` | `test_page_url_rejects_userinfo` |
| Accept a page-url port other than 443 | `publishing.py:226` | `test_page_url_rejects_a_port` |
| Accept an empty page-url port | `publishing.py:226` | `test_page_url_rejects_an_empty_port` |
| Join hex title words onto a short page id | `publishing.py:260` | `test_page_url_rejects_a_glued_hex_title` |
| Accept dashes that are not the 8-4-4-4-12 layout | `publishing.py:209` | `test_plain_page_id_dashes_must_be_uuid_layout` |
| Keep the same link each time it is repeated | `publishing.py:63` | `test_repeated_link_forms_are_stored_once` |
| Accept a trailing slug whose groups are not 8-4-4-4-12 | `publishing.py:279` | `test_page_url_rejects_a_bad_uuid_layout` |
| Do not lowercase a dashed plain page id | `publishing.py:211` | `test_isolation_catches_an_uppercase_dashed_id` |
| Read six slug groups instead of the trailing uuid | `publishing.py:278` | `test_isolation_catches_a_titled_uuid` |
| Accept page-url port 80 | `publishing.py:226` | `test_page_url_rejects_a_port` |
| Reject page-url port 443 | `publishing.py:226` | `test_page_url_port_443_is_canonical` |
| Drop Unicode category Zp | `publishing.py:151` | `test_secret_link_rejects_a_paragraph_separator` |
| Accept a page-url query string | `publishing.py:234` | `test_page_url_rejects_a_query` |
| Sort deduped links | `publishing.py:188` | `test_deduped_link_order_is_preserved` |
| Treat g as a hex digit | `publishing.py:32` | `test_page_reference_rejects_g` |
| Drop notion.so from the page-url hosts | `publishing.py:28` | `test_notion_so_page_url_is_canonical` |
| Accept a page-url fragment | `publishing.py:228` | `test_page_url_rejects_a_fragment` |
| Accept page-url parameters | `publishing.py:230` | `test_page_url_rejects_parameters` |
| Accept an empty page-url query | `publishing.py:232` | `test_page_url_rejects_an_empty_query` |
| Skip forbidden characters in a page reference | `publishing.py:194` | `test_page_reference_rejects_a_forbidden_character` |
| Drop Cc from page-reference categories | `publishing.py:155` | `test_page_reference_rejects_a_forbidden_character` |
| Drop Cf from page-reference categories | `publishing.py:155` | `test_page_reference_rejects_a_forbidden_character` |
| Drop Zl from page-reference categories | `publishing.py:155` | `test_page_reference_rejects_a_forbidden_character` |
| Drop Zp from page-reference categories | `publishing.py:155` | `test_page_reference_rejects_a_forbidden_character` |
| Drop Unicode category Zs | `publishing.py:151` | `test_secret_link_rejects_a_space_separator` |
| Cf reduced to U+200B only | `publishing.py:155` | `test_page_reference_rejects_a_forbidden_character` |
| Exempt C1 0x80-0x9F | `publishing.py:155` | `test_page_reference_rejects_a_forbidden_character` |
| Exempt U+009F in the secret link | `publishing.py:151` | `test_secret_link_rejects_u009f` |
| Replace rpartition with partition | `publishing.py:257` | `test_page_url_accepts_a_multi_word_slug` |
| Allow a notion.so subdomain | `publishing.py:237` | `test_page_url_host_must_be_allowed` |
| Strip a trailing dot from a page-url host | `publishing.py:237` | `test_page_url_host_must_be_allowed` |
| Ignore a trailing U+200B on the secret link | `publishing.py:130` | `test_secret_link_rejects_a_trailing_zero_width_space` |
- **Control update**: `docs/control/IMPLEMENTATION_STATE.json` `session_06_w8` and this log entry. Against base, STATE changes only these things: `state_revision` 43 to 44, the `session_06_w7` trailing comma, `session_06_w8`, and `updated_at`. `updated_at` moves forward from `2026-09-26T17:46:39Z`. `control_files_and_checkpoint_current` stays false. The session stays incomplete.
- **Hard boundaries**: fixtures and mocks only. No live Notion or Etsy, no real browser, no Playwright import. Fixture adapter stays the default. `src/money_machine/orchestration/` untouched. `uv.lock` untouched. `pyproject.toml` untouched. `src/money_machine/integrations/notion/router.py` untouched. Exit 78 held.

## 2026-09-26 — Session 06 Wave 9: browser session management

- **Heading**: `### 3. Implement browser session management` in `prompts/implementation/09_SESSION_06_NOTION_INTEGRATION_FOUNDATION.md` and `hands-off-money-machine-full-implementation-workbook.md`.
- **Narrow reading**: Profiles stay under `runtime/browser-profiles`, which git ignores. A profile is reused only while it is authenticated, open, and healthy. A read makes 3 attempts in total on a timeout and does not retry a connection failure. Any other read error is wrapped, recorded with screenshot reason error, and taints the session. An uncertain click is reconciled by observing and is not clicked twice. Any observe error is Unknown and taints the session. A click that raises any Exception is observed once, recorded as Unknown with the observe result, and taints the session. The observe value is kept only when it is applied, absent, or unknown. Observe returning applied does not make that receipt Success, and absent does not make it Failure. If that observe also raises, one Unknown receipt is still returned. KeyboardInterrupt, SystemExit, and GeneratorExit from click, observe, or a screenshot still record one Unknown receipt before they propagate. A repeated screenshot interrupt still leaves that one receipt, with evidence screenshot-failed, and a same-key replay does not click again. A captcha, verification, or unknown page fails closed, with a screenshot and a tainted session. A page-kind timeout, connection error, or other error records one failure and does not click. Each mutation records one `NotionOperationReceipt`. The idempotency key is bound to the profile, operation, workspace, target, and job. Selectors are a catalogue of data-testid strings. The driver is injected. The prompt-integrity review is already recorded at `docs/control/reviews/2026-09-24-session-06-prompt-integrity.md` and is not rewritten. No network, live Notion, live Etsy, or browser launch.
- **W8 deferred fixes folded in**: Page references reject Unicode categories Cc, Cf, Zl, Zp, and Zs. `test_page_reference_rejects_a_space_separator` covers ASCII space, NBSP U+00A0, U+1680, U+2002, U+202F, U+205F, and U+3000, in titled, plain, leading, and trailing shapes, for page_id, links, and other_catalogue_pages. The forbidden scan reads the raw value before the padding check, includes the first character, and includes a leading C0 run. W8 row 71, drop the page-id padding check at `publishing.py:196`, is equivalent. Re-checked on the publishing file after the wider Zs set: deleting that check still passes, including `test_page_url_rejects_padding`, because every character strip() removes is already rejected as Cc, Zl, Zp, or Zs.
- **Session policy**: `BrowserSessionManager` opens an authenticated profile or reuses its healthy session. `profile_path` runs before the driver opens or restarts. `ProfileStatus` is compared by identity, so a string status is rejected. A session id that is not a slug is closed. If that close fails, the profile is locked and the original session-id error is re-raised with the close error as its cause; the next open fails with the locked error. If that close succeeds, the profile is not locked and the next open is allowed. A failed restart close locks the profile, and both mutate and read then fail closed. Reads of public_url and share_menu make 3 attempts in total on TimeoutError and fail on ConnectionError without another try. Any other read error is wrapped in BrowserSessionError, recorded with screenshot reason error, and taints the session. Mutations are publish_page, unpublish_page, set_duplicate_as_template, and set_search_indexing. The same idempotency key returns the same receipt only when the profile, operation, workspace, target, and job match, and it does not click again, including after a failure. A mismatch raises `BrowserSessionError` before the session is required. An applied click is Success with evidence applied. An uncertain click or a click TimeoutError observes once: applied is Success with evidence reconciled and no taint; absent is Failure; any other observe result, including RuntimeError, ValueError, OSError, TimeoutError, and ConnectionError, is Unknown and taints the session. A click that raises any Exception is observed once and recorded as Unknown with the observe result, and the session is tainted even when observe returns applied or absent. The observe value is kept only when it is applied, absent, or unknown; any other value, including None, an object, or a 5000-character string, is stored as unknown. That receipt is not Success and it is not Failure. If that observe also raises, the call still returns one Unknown receipt. A KeyboardInterrupt, SystemExit, or GeneratorExit from click, from observe after an uncertain click, or from a screenshot records one Unknown receipt and taints the session before it propagates. The screenshot interrupt stores evidence screenshot-failed and the observed value, including when the screenshot raises every time. The finally block does not record a second receipt when the key is already stored. An unexpected click string is one error receipt. A page-kind TimeoutError, ConnectionError, or other exception is one Failure with page kind unknown and reason timeout, connection, or error. A screenshot failure still records one receipt with evidence screenshot-failed. The screenshot-reason guard is equivalent because every caller reason is already in the screenshot set. Receipts are a tuple. Invalid input raises `BrowserSessionError`. The module does not name Playwright, urllib, or socket.
- **Pytest collected**: 1854 collected, 1853 passed, 1 skipped. W8 baseline: 1718 collected, 1717 passed, 1 skipped. Delta +136 collected and +136 passed.
- **Per-file counts**:

| File | Functions (base → tip) | Collected (base → tip) | Passed (base → tip) | Failed (base → tip) | Skipped (base → tip) |
|---|---|---|---|---|---|
| `tests/unit/integrations/notion/test_publishing.py` | 81 → 86 | 153 → 178 | 153 → 178 | 0 → 0 | 0 → 0 |
| `tests/unit/integrations/notion/test_browser_session.py` | 0 → 61 | 0 → 111 | 0 → 111 | 0 → 0 | 0 → 0 |
| Remaining files | unchanged | 1565 → 1565 | 1564 → 1564 | 0 → 0 | 1 → 1 |
| **Total** | | **1718 → 1854** | **1717 → 1853** | **0 → 0** | **1 → 1** |

- **Mutation checks** (95 rows; each applied, pytest run, then reverted; 93 killed and 2 equivalent):

| Mutation | Site | Failing test |
|---|---|---|
| Check padding before forbidden characters | `publishing.py:194` | `test_forbidden_characters_are_checked_before_padding` |
| Forbidden check applied on strip() | `publishing.py:194` | `test_forbidden_check_reads_characters_strip_would_remove` |
| Skip the first character | `publishing.py:194` | `test_page_reference_rejects_a_leading_control_character` |
| Skip a leading C0 run | `publishing.py:194` | `test_page_reference_rejects_a_leading_control_run` |
| Drop Zs from page-reference categories | `publishing.py:30` | `test_page_reference_rejects_a_space_separator` |
| Drop the page-id padding check | `publishing.py:196` | equivalent: W8 row 71 re-checked on the publishing file; it still passes `test_page_url_rejects_padding` because every character strip() removes is already rejected as Cc, Zl, Zp, or Zs |
| Exempt ASCII space | `publishing.py:154` | `test_page_reference_rejects_a_space_separator` |
| Zs only NBSP/U+3000 | `publishing.py:154` | `test_page_reference_rejects_a_space_separator` |
| Store profiles under the screenshot root | `browser_session.py:37` | `test_browser_profiles_stay_outside_git` |
| Store screenshots under the profile root | `browser_session.py:38` | `test_browser_profiles_stay_outside_git` |
| Drop Zs from profile-name categories | `browser_session.py:40` | `test_profile_name_is_rejected` |
| Allow a 65-character profile name | `browser_session.py:156` | `test_profile_name_is_rejected` |
| Allow a profile name that ends with a hyphen | `browser_session.py:158` | `test_profile_name_is_rejected` |
| Reject a digit in a profile slug | `browser_session.py:165` | `test_profile_slug_is_accepted` |
| Accept an uppercase profile slug | `browser_session.py:165` | `test_profile_name_is_rejected` |
| Skip the authenticated-profile check | `browser_session.py:211` | `test_open_requires_an_authenticated_profile` |
| Compare profile status by its text | `browser_session.py:211` | `test_string_status_is_not_authenticated` |
| Open a new session instead of reusing a healthy one | `browser_session.py:218` | `test_healthy_session_is_reused` |
| Reuse the first open session for every profile | `browser_session.py:212` | `test_two_profiles_are_not_the_same_session` |
| Store a session id that is not a slug | `browser_session.py:222` | `test_open_rejects_a_bad_session_id` |
| Drop publish_page from the operation map | `browser_session.py:61` | `test_mutation_clicks_the_operation_selector` |
| Drop unpublish_page from the operation map | `browser_session.py:62` | `test_mutation_clicks_the_operation_selector` |
| Click the logical name instead of the selector | `browser_session.py:637` | `test_mutation_clicks_the_operation_selector` |
| Skip the idempotency lookup | `browser_session.py:307` | `test_replay_returns_the_same_receipt` |
| Do not store the receipt under its idempotency key | `browser_session.py:607` | `test_replay_returns_the_same_receipt` |
| Look up the idempotency key after requiring an open session | `browser_session.py:307` | `test_replay_after_failure_does_not_click` |
| Skip the captcha check | `browser_session.py:334` | `test_challenge_page_fails_closed[captcha]` |
| Skip the verification check | `browser_session.py:336` | `test_challenge_page_fails_closed[verification]` |
| Click a page that is not normal | `browser_session.py:340` | `test_unknown_page_kind_is_not_clicked` |
| Treat a click timeout as a connection failure | `browser_session.py:393` | `test_click_timeout_is_reconciled` |
| Do not observe a raised connection click | `browser_session.py:392` | `test_connection_error_click_is_one_unknown_receipt` |
| Do not observe a raised runtime click | `browser_session.py:392` | `test_raised_click_is_one_unknown_receipt[RuntimeError]` |
| Restore the narrow raised-click catch | `browser_session.py:392` | `test_raised_click_is_one_unknown_receipt[DriverError]` |
| Click again before reconciling | `browser_session.py:489` | `test_uncertain_click_is_reconciled_when_applied` |
| Record an absent reconciliation as Success | `browser_session.py:510` | `test_uncertain_click_absent_is_a_failure` |
| Record an unknown reconciliation as Success | `browser_session.py:512` | `test_uncertain_click_unknown_stays_unknown` |
| Taint a reconciled applied click | `browser_session.py:507` | `test_uncertain_click_is_reconciled_when_applied` |
| Do not taint a blocked mutation | `browser_session.py:557` | `test_challenge_page_fails_closed[captcha]` |
| Let a screenshot failure skip the receipt | `browser_session.py:570` | `test_screenshot_failure_still_records_one_receipt` |
| Do not append the receipt | `browser_session.py:606` | `test_mutation_clicks_the_operation_selector` |
| Return the receipt list | `browser_session.py:201` | `test_receipts_property_is_a_tuple` |
| Retry a read only once | `browser_session.py:39` | `test_read_retries_timeout_then_returns` |
| Retry a read four times | `browser_session.py:39` | `test_read_stops_after_three_timeouts` |
| Leave a timed-out read healthy | `browser_session.py:561` | `test_read_stops_after_three_timeouts` |
| Retry a read connection error | `browser_session.py:276` | `test_read_does_not_retry_a_connection_error` |
| Read the logical name instead of the selector | `browser_session.py:269` | `test_read_retries_timeout_then_returns` |
| Allow a mutation selector to be read | `browser_session.py:66` | `test_read_rejects_a_mutation_selector` |
| Do not lock the profile when close fails | `browser_session.py:252` | `test_failed_restart_locks_the_profile` |
| Drop the session before close | `browser_session.py:252` | `test_failed_restart_locks_the_profile` |
| Skip the profile bool check | `browser_session.py:127` | `test_profile_status_requires_bool_flags` |
| Allow an absent profile to be authenticated | `browser_session.py:129` | `test_absent_profile_cannot_be_authenticated` |
| Treat an unauthenticated profile as authenticated | `browser_session.py:133` | `test_profile_status_values` |
| Accept a naive timestamp | `browser_session.py:177` | `test_naive_timestamp_is_rejected` |
| Accept a padded mutation token | `browser_session.py:169` | `test_mutation_tokens_must_be_present` |
| Accept an unknown operation | `browser_session.py:635` | `test_unknown_operation_is_rejected` |
| Reuse a tainted session | `browser_session.py:216` | `test_tainted_session_is_not_reused_until_restart` |
| Skip the open-session lock check | `browser_session.py:214` | `test_failed_restart_locks_the_profile` |
| Catch only TimeoutError from observe | `browser_session.py:491` | `test_observe_exception_is_one_unknown_receipt[ConnectionError]` |
| Restore the narrow observe catch | `browser_session.py:491` | `test_observe_exception_is_one_unknown_receipt[RuntimeError]` |
| Skip the page-kind timeout branch | `browser_session.py:322` | `test_page_kind_error_records_one_receipt[timeout]` |
| Skip the page-kind connection branch | `browser_session.py:326` | `test_page_kind_error_records_one_receipt[connection]` |
| Skip the page-kind error branch | `browser_session.py:330` | `test_page_kind_error_records_one_receipt[error]` |
| Drop the locked check in _require_open | `browser_session.py:383` | `test_locked_profile_blocks_mutate_and_read` |
| Pass a garbage click result through | `browser_session.py:396` | `test_unknown_click_result_is_one_error_receipt` |
| Taint only on Failure | `browser_session.py:591` | `test_uncertain_click_unknown_stays_unknown` |
| Unknown page not tainted | `browser_session.py:557` | `test_unknown_page_kind_is_not_clicked` |
| Skip close on a bad session id | `browser_session.py:224` | `test_open_rejects_a_bad_session_id` |
| Let close raise on a bad session id | `browser_session.py:224` | `test_open_rejects_a_bad_session_id_when_close_fails` |
| Drop lock on failed cleanup | `browser_session.py:231` | `test_open_rejects_a_bad_session_id_when_close_fails` |
| Accept an idempotency key bound to a different call | `browser_session.py:622` | `test_idempotency_key_is_bound_to_the_call` |
| Drop profile from the idempotency binding | `browser_session.py:623` | `test_idempotency_key_is_bound_to_the_call` |
| Drop operation from the idempotency binding | `browser_session.py:624` | `test_idempotency_key_is_bound_to_the_call` |
| Drop workspace from the idempotency binding | `browser_session.py:625` | `test_idempotency_key_is_bound_to_the_call` |
| Drop target from the idempotency binding | `browser_session.py:626` | `test_idempotency_key_is_bound_to_the_call` |
| Drop job from the idempotency binding | `browser_session.py:627` | `test_idempotency_key_is_bound_to_the_call` |
| Drop profile_path in open_session | `browser_session.py:210` | `test_open_rejects_an_invalid_profile_name` |
| Drop profile_path in restart | `browser_session.py:245` | `test_restart_rejects_an_invalid_profile_name` |
| Drop the operation string check | `browser_session.py:632` | `test_operation_must_be_a_string` |
| Drop the timestamp type check | `browser_session.py:175` | `test_timestamp_must_be_a_datetime` |
| Drop the session-id type check | `browser_session.py:183` | `test_open_rejects_a_non_string_session_id` |
| Drop the screenshot reason check | `browser_session.py:565` | equivalent: every caller reason is already in the screenshot set |
| Record every blocked click as not-clicked | `browser_session.py:543` | `test_page_kind_error_records_one_receipt[error]` |
| Drop session_id from the receipt pre_state | `browser_session.py:598` | `test_mutation_clicks_the_operation_selector` |
| Drop the finally | `browser_session.py:375` | `test_base_exception_still_records_an_unknown_receipt[click-KeyboardInterrupt]` |
| Do not wrap a read error | `browser_session.py:279` | `test_read_other_error_is_wrapped_and_taints` |
| Do not taint a connection read | `browser_session.py:277` | `test_read_connection_error_taints_the_session` |
| Drop suppress(Exception) | `browser_session.py:413` | `test_raised_click_observe_error_returns_one_unknown_receipt[RuntimeError-RuntimeError]` |
| Swallow a screenshot interrupt | `browser_session.py:443` | `test_screenshot_interrupt_propagates[KeyboardInterrupt]` |
| Label a read error as a timeout screenshot | `browser_session.py:280` | `test_read_other_error_is_wrapped_and_taints` |
| Drop the observe result on a raised click | `browser_session.py:425` | `test_connection_error_click_is_one_unknown_receipt` |
| Treat applied after a raised click as Success | `browser_session.py:416` | `test_raised_click_stays_unknown_when_observe_returns_applied` |
| Drop the BaseException branch | `browser_session.py:445` | `test_screenshot_interrupt_records_one_unknown_receipt[always-raised]` |
| Drop the seen-key guard | `browser_session.py:376` | `test_screenshot_interrupt_records_one_unknown_receipt[once-raised]` |
| Record Failure when a raised click observes absent | `browser_session.py:470` | `test_raised_click_stays_unknown_for_any_observe_result[absent]` |
| Skip the observe whitelist on a raised click | `browser_session.py:415` | `test_raised_click_observe_value_is_whitelisted[object]` |

- **Control update**: `docs/control/IMPLEMENTATION_STATE.json` `session_06_w9` and this log entry. Against base, STATE changes only these things: `state_revision` 44 to 45, the `session_06_w8` trailing comma, `session_06_w9`, and `updated_at`. `updated_at` moves forward from `2026-09-26T20:41:44Z`. `control_files_and_checkpoint_current` stays false. The session stays incomplete.
- **Hard boundaries**: fixtures and mocks only. No live Notion or Etsy, no real browser, no Playwright import. Fixture adapter stays the default. `src/money_machine/orchestration/` untouched. `uv.lock` untouched. `pyproject.toml` untouched. `src/money_machine/integrations/notion/router.py` untouched. Exit 78 held.

## 2026-09-27 — Session 06 Wave 10: observe whitelist, receipt recording, and notion CLI

- **Heading**: `### 9. Live connection path` in `prompts/implementation/09_SESSION_06_NOTION_INTEGRATION_FOUNDATION.md` and `hands-off-money-machine-full-implementation-workbook.md`. Wave 9 deferred browser-session items are included.
- **Narrow reading**: `integrations notion connect`, `status`, and `test` read the notion token only to check its shape. Connect and test pass it to an injected probe. Status only checks the shape. The default probe is in-process and does not open a network connection, a browser, or a live Notion workspace. A missing token exits 78. A token that is not `secret_` or `ntn_` plus 43 or more ASCII alphanumerics exits 64, including an underscore or a non-ASCII body. A probe error exits 69 and the exception text is not printed. A workspace must match `[A-Za-z0-9 _.-]{1,100}` and its type must be `str`. It is rejected when it contains `secret_` or `ntn_` in any case, or any 12-character window of the token body after `-`, `.`, `_`, and spaces are removed. An 11-character body fragment is accepted. Hex, reversed, rot13, base64, and sha copies are a non-goal, as are 11-character fragments and non-contiguous fragments: only an injected probe can produce the encoded copies, and this check does not scan them. Sandbox steps must be the exact tuple of plain strings page, database, publish, unpublish, and archive. A tuple subclass or a str subclass exits 69. A KeyboardInterrupt, SystemExit, GeneratorExit, or other BaseException from the probe is re-raised without the token. A non-zero int SystemExit code is kept. SystemExit(0), SystemExit(False), and any code that is not a non-zero int become 1. A constructor that raises, including a KeyboardInterrupt subclass whose constructor raises ValueError, falls back to KeyboardInterrupt, GeneratorExit, or BaseException, and that interrupt still exits 130. A BaseExceptionGroup that contains a KeyboardInterrupt is re-raised as KeyboardInterrupt and exits 130. The token is absent from the traceback, `__context__`, and `__cause__`. A no-arg constructor that embeds the token is a boundary this helper does not scan. Success prints JSON with mode fake and does not print or log the token. The prompt-integrity review at `docs/control/reviews/2026-09-24-session-06-prompt-integrity.md` is not rewritten. S-01 still holds: no live Notion mutation.
- **W9 deferred**: A raised-click observe value is kept only when its type is exactly `str` and the value is applied, absent, or unknown. A dict, a list, a token URL, or a str subclass with a forged equality is stored as unknown, the session is tainted, and a replay does not click again. The recorded flag is gone. The finally block writes a receipt only when the key is not already stored, including after `_record_unknown` on BaseException. `_seen` is the only receipt store. `receipts` returns that map's values in insertion order, so a store interrupt cannot leave the key and the receipt tuple out of sync.
- **Deferred follow-up**: The unhashable observe read uses an exact string type check. The redundant recorded flag is removed. A screenshot RuntimeError after a raised click is caught in `_record_unknown` and does not propagate. The receipt is Unknown, evidence is screenshot-failed, the observed value is kept, the session is tainted, and a replay does not click again. A reconcile screenshot interrupt still stores observed unknown rather than absent. That path stays fail-safe.
- **Pytest collected**: 1959 collected, 1958 passed, 1 skipped. W9 baseline: 1854 collected, 1853 passed, 1 skipped. Delta +105 collected and +105 passed.
- **Per-file counts**:

| File | Functions (base → tip) | Collected (base → tip) | Passed (base → tip) | Failed (base → tip) | Skipped (base → tip) |
|---|---|---|---|---|---|
| `tests/unit/integrations/notion/test_browser_session.py` | 61 → 66 | 111 → 119 | 111 → 119 | 0 → 0 | 0 → 0 |
| `tests/unit/cli/test_notion_commands.py` | 0 → 18 | 0 → 97 | 0 → 97 | 0 → 0 | 0 → 0 |
| Remaining files | unchanged | 1743 → 1743 | 1742 → 1742 | 0 → 0 | 1 → 1 |
| **Total** | | **1854 → 1959** | **1853 → 1958** | **0 → 0** | **1 → 1** |

- **Mutation checks** (82 rows; each applied, pytest run, then reverted; 80 killed and 2 equivalent):

| Mutation | Site | Test | Result |
|---|---|---|---|
| Drop the observe type check | `browser_session.py:410` | `test_raised_click_observe_value_is_whitelisted[dict]` | killed |
| Accept every string as an observe value | `browser_session.py:410` | `test_raised_click_observe_value_is_whitelisted[token-url]` | killed |
| Drop unknown from the observe whitelist | `browser_session.py:410` | `test_raised_click_observe_value_is_whitelisted` | equivalent: the string unknown is stored as unknown by the else branch, and the browser-session file still passes |
| Finally always records a receipt | `browser_session.py:371` | `test_finally_does_not_write_a_second_receipt_after_unknown` | killed |
| Restore the recorded flag beside the seen-key guard | `browser_session.py:371` | `test_finally_does_not_write_a_second_receipt_after_unknown` | equivalent: the flag is set only after the key is stored, and the browser-session file still passes |
| Return receipts from a list appended after the seen key | `browser_session.py:200` | `test_interrupt_during_store_keeps_receipts_aligned` | killed |
| Return receipts in reverse insertion order | `browser_session.py:200` | `test_receipts_follow_insertion_order` | killed |
| Accept a str subclass observe value | `browser_session.py:410` | `test_forged_observe_subclass_is_unknown` | killed |
| Drop except Exception in _record_unknown | `browser_session.py:441` | `test_raised_click_screenshot_runtime_error_does_not_propagate` | killed |
| Skip the missing-token check | `notion.py:110` | `test_notion_commands_fail_when_config_is_missing[connect]` | killed |
| Skip the token-shape check | `notion.py:112` | `test_bad_token_shape_is_redacted[plain-connect]` | killed |
| Match the token with search instead of fullmatch | `notion.py:81` | `test_bad_token_shape_is_redacted[token-url-connect]` | killed |
| Match the token with match instead of fullmatch | `notion.py:81` | `test_bad_token_shape_is_redacted[suffix-connect]` | killed |
| Drop ntn_ from the token pattern | `notion.py:26` | `test_notion_commands_succeed[status]` | killed |
| Drop secret_ from the token pattern | `notion.py:26` | `test_notion_commands_succeed[connect]` | killed |
| Allow a 42-character token body | `notion.py:26` | `test_bad_token_shape_is_redacted[short-connect]` | killed |
| Require a 44-character token body | `notion.py:26` | `test_notion_commands_succeed[connect]` | killed |
| Require a token body of exactly 43 characters | `notion.py:26` | `test_notion_commands_succeed[connect-44]` | killed |
| Match the token body with a word class | `notion.py:26` | `test_bad_token_shape_is_redacted[unicode-connect]` | killed |
| Echo the connect exception | `notion.py:194` | `test_fake_api_error_is_redacted[value-connect]` | killed |
| Echo the test exception | `notion.py:237` | `test_fake_api_error_is_redacted[value-test]` | killed |
| Catch only RuntimeError on connect | `notion.py:194` | `test_fake_api_error_is_redacted[value-connect]` | killed |
| Catch only RuntimeError on test | `notion.py:237` | `test_fake_api_error_is_redacted[os-test]` | killed |
| Log the raw token when the shape is invalid | `notion.py:113` | `test_bad_token_shape_is_redacted[plain-connect]` | killed |
| Put the token in the connect payload | `notion.py:207` | `test_notion_commands_succeed[connect]` | killed |
| Skip the workspace leak check | `notion.py:199` | `test_probe_workspace_that_echoes_the_token_is_redacted` | killed |
| Accept a non-string workspace | `notion.py:126` | `test_unsafe_workspace_is_an_api_error[non-string]` | killed |
| Accept an empty workspace | `notion.py:31` | `test_unsafe_workspace_is_an_api_error[empty]` | killed |
| Drop the workspace pattern | `notion.py:128` | `test_workspace_token_variant_is_rejected[base64-mark]` | killed |
| Match the workspace token case-sensitively | `notion.py:130` | `test_workspace_token_variant_is_rejected[mixed]` | killed |
| Require the full token in the workspace | `notion.py:131` | `test_workspace_token_variant_is_rejected[partial]` | killed |
| Require the full token body | `notion.py:138` | `test_workspace_token_variant_is_rejected[body-42]` | killed |
| Raise the body window to 13 | `notion.py:32` | `test_workspace_token_variant_is_rejected[body-12]` | killed |
| Raise the body window to 22 | `notion.py:32` | `test_workspace_token_variant_is_rejected[half]` | killed |
| Reject an 11-character body fragment | `notion.py:32` | `test_bounded_workspace_names_connect[body-11]` | killed |
| Keep a dash inside a body window | `notion.py:33` | `test_workspace_token_variant_is_rejected[dash]` | killed |
| Keep a dot inside a body window | `notion.py:33` | `test_workspace_token_variant_is_rejected[dot]` | killed |
| Keep an underscore inside a body window | `notion.py:33` | `test_workspace_token_variant_is_rejected[underscore]` | killed |
| Keep a space inside a body window | `notion.py:33` | `test_workspace_token_variant_is_rejected[space]` | killed |
| Drop casefold on the token body | `notion.py:134` | `test_mixed_token_workspace_is_rejected[body]` | killed |
| Skip the last token-body window | `notion.py:138` | `test_mixed_token_workspace_is_rejected[tail]` | killed |
| Skip the first token-body window | `notion.py:138` | `test_mixed_token_workspace_is_rejected[head]` | killed |
| Match secret_ and ntn_ only at the start | `notion.py:131` | `test_mixed_token_workspace_is_rejected[shop-secret]` | killed |
| Skip the secret_ prefix check | `notion.py:131` | `test_workspace_token_variant_is_rejected[lower]` | killed |
| Skip the ntn_ prefix check | `notion.py:131` | `test_workspace_token_variant_is_rejected[ntn-lower]` | killed |
| Raise the workspace length cap to 101 | `notion.py:31` | `test_workspace_token_variant_is_rejected[len-101]` | killed |
| Lower the workspace length cap to 99 | `notion.py:31` | `test_bounded_workspace_names_connect[len-100]` | killed |
| Accept a str subclass workspace | `notion.py:126` | `test_workspace_str_subclass_is_rejected` | killed |
| Skip the sandbox step check | `notion.py:146` | `test_incomplete_sandbox_steps_fail` | killed |
| Drop the exact step tuple check | `notion.py:142` | `test_equal_tuple_subclass_is_rejected` | killed |
| Accept a str subclass sandbox step | `notion.py:144` | `test_token_str_subclass_step_is_rejected` | killed |
| Report an API error as success | `notion.py:23` | `test_fake_api_error_is_redacted[value-connect]` | killed |
| Report missing config as success | `notion.py:24` | `test_notion_commands_fail_when_config_is_missing[connect]` | killed |
| Report a bad token as success | `notion.py:22` | `test_bad_token_shape_is_redacted[plain-connect]` | killed |
| Return the sandbox steps without calling the probe | `notion.py:237` | `test_notion_commands_succeed[test]` | killed |
| Hardcode the connect workspace | `notion.py:194` | `test_notion_commands_succeed[connect]` | killed |
| Status calls the probe | `notion.py:215` | `test_notion_commands_succeed[status]` | killed |
| Drop archive from the sandbox steps | `notion.py:34` | `test_notion_commands_succeed[test]` | killed |
| Label connect mode as live | `notion.py:205` | `test_notion_commands_succeed[connect]` | killed |
| Default probe is None | `notion.py:87` | `test_default_probe_uses_the_fixture[connect]` | killed |
| Default probe raises | `notion.py:76` | `test_default_probe_uses_the_fixture[test]` | killed |
| Re-raise the connect interrupt unchanged | `notion.py:194` | `test_probe_base_exception_traceback_has_no_token[keyboard-connect]` | killed |
| Re-raise the test interrupt unchanged | `notion.py:237` | `test_probe_base_exception_traceback_has_no_token[keyboard-test]` | killed |
| Blank a connect interrupt with type() | `notion.py:194` | `test_probe_base_exception_traceback_has_no_token[exit-2-connect]` | killed |
| Blank a test interrupt with type() | `notion.py:237` | `test_probe_base_exception_traceback_has_no_token[exit-2-test]` | killed |
| Map every SystemExit code to 1 | `notion.py:165` | `test_probe_base_exception_traceback_has_no_token[exit-2-connect]` | killed |
| Keep a non-integer SystemExit code | `notion.py:165` | `test_probe_base_exception_traceback_has_no_token[system-connect]` | killed |
| Keep SystemExit code 0 | `notion.py:166` | `test_probe_base_exception_traceback_has_no_token[exit-0-connect]` | killed |
| Keep SystemExit(False) | `notion.py:166` | `test_probe_base_exception_traceback_has_no_token[exit-false-connect]` | killed |
| Leave the original interrupt as __context__ | `notion.py:181` | `test_probe_base_exception_traceback_has_no_token[keyboard-connect]` | killed |
| Propagate TypeError from a required argument | `notion.py:170` | `test_probe_base_exception_traceback_has_no_token[needs-arg-connect]` | killed |
| Fall back to BaseException for every constructor error | `notion.py:172` | `test_probe_base_exception_traceback_has_no_token[needs-keyboard-connect]` | killed |
| Catch only TypeError while blanking an interrupt | `notion.py:171` | `test_keyboard_interrupt_still_exits_130[value-keyboard-connect]` | killed |
| Ignore a KeyboardInterrupt inside BaseExceptionGroup | `notion.py:149` | `test_keyboard_interrupt_still_exits_130[group-keyboard-connect]` | killed |
| Skip the GeneratorExit fallback | `notion.py:175` | `test_probe_base_exception_traceback_has_no_token[needs-generator-connect]` | killed |
| Re-raise a BaseExceptionGroup | `notion.py:177` | `test_probe_base_exception_traceback_has_no_token[group-connect]` | killed |
| Keep a GeneratorExit message | `notion.py:171` | `test_probe_base_exception_traceback_has_no_token[generator-connect]` | killed |
| Replace a probe interrupt with KeyboardInterrupt | `notion.py:171` | `test_probe_base_exception_traceback_has_no_token[subclass-connect]` | killed |
| Catch only KeyboardInterrupt from the test probe | `notion.py:237` | `test_probe_base_exception_traceback_has_no_token[system-test]` | killed |
| Do not pass the injected probe | `main.py:619` | `test_notion_commands_succeed[connect]` | killed |
| Wire connect to the status handler | `main.py:593` | `test_notion_commands_succeed[connect]` | killed |
| Echo the notion exception from main | `main.py:627` | `test_main_does_not_echo_a_notion_exception` | killed |
- **Control update**: `docs/control/IMPLEMENTATION_STATE.json` `session_06_w10` and this log entry. Against base, STATE changes only these things: `state_revision` 45 to 46, the `session_06_w9` trailing comma, `session_06_w10`, and `updated_at`. `updated_at` moves forward from `2026-09-26T23:45:13Z`. `control_files_and_checkpoint_current` stays false. The session stays incomplete.
- **Hard boundaries**: fixtures and mocks only. No live Notion or Etsy, no real browser, no Playwright import. Fixture adapter stays the default. `src/money_machine/orchestration/` untouched. `uv.lock` untouched. `pyproject.toml` untouched. `src/money_machine/integrations/notion/router.py` untouched. Exit 78 held.

## 2026-09-11 — Startup repair wave after recovery review

- Repaired migration-head/schema compatibility readiness, encoded database credentials/IPv6, and production environment selection. Compose now carries raw passwords separately; a bounded independent review identified literal-percent and surrounding-whitespace cases, both reproduced and repaired with regression coverage. Development external-URL overrides retain their credentials.
- Final affected verification: **125 passed, no skips**, 121.37 seconds, including real isolated-database API/CLI tests and rendered Compose credential checks; formatting, Ruff and Pyright clean. Review/remediation details are in `docs/control/reviews/2026-09-11-startup-repair.md`.
- This is a recoverable foundation repair checkpoint, not another session closure. Session02 remains complete, Session03 prompt integrity/activation is next, no agents are commissioned and worker/scheduler still exit 78. Preserved `CLAUDE.md`, historical worktrees, sources and the shared application database. No provider mutations, deployment or push.

## 2026-09-11 — Recovery review and ordered delivery plan

- Recovered canonical `build/full-automation` at `3720653`, Session02 complete, next Session03; preserved untracked `CLAUDE.md`. Wrote metadata-only recovery checkpoint `.omx/state/review-resume-20260911.json`.
- Reconciled the older integration branch as reference material: 49 unique commits versus 10 canonical commits, historical Session07 closure, and protected uncommitted Session08 work. No history, source, database or old worktree was replaced.
- Two independent read-only reviews identified current startup defects and a session-scoped reuse strategy. The durable review and plan are `docs/control/reviews/2026-09-11-recovery-review-and-finish-plan.md`; it records findings, sources, milestone acceptance and the next repair/Session03 wave.
- Live Docker inventory showed only the project's PostgreSQL container running. Worker/scheduler remain intentionally unimplemented beyond the Session02 exit-78 boundary. No provider action, commissioning or session transition was performed.

## 2026-08-08T13:43:51Z — Session 00 source/control lane

- Adopted the sole canonical root at `/mnt/d/Money Machine`; the old lowercase root is absent and `wslpath` maps the root to `D:\Money Machine`.
- Rehashed both immutable sources and recorded post-rename byte-identity evidence.
- Deterministically extracted the 21-file canonical prompt pack from COPY markers and verified Appendix hashes/bytes plus calculated source lines and output line counts.
- Added copyright-safe continuous PDF page coverage and exhaustive Chapter 12-16 step, Prompt 1-13, and Workbook Page 1-6 mappings.
- Initialized fail-closed control state as `incomplete`. Runtime, review, Git, and outer verification gates remain pending and must not be inferred from this documentation slice.

## 2026-08-08T14:47:04Z — Session 00 integrated local verification

- Reconfirmed the canonical WSL/Windows root and immutable source hashes; the 21-file prompt pack remains verified.
- Passed the full Python gates: Ruff, strict Pyright, and all 17 Pytest tests.
- Received HTTP 200 from the live API `/health` endpoint and passed Bash and PowerShell parser checks.
- Passed isolated frozen `uv` and `pnpm` installs plus the clean bootstrap and complete web lint, typecheck, test, and build sequence.
- Confirmed Compose resolves `postgres`, `api`, `scheduler`, `web`, and `worker`.
- `timeout 15 docker info` exited 124. Docker-backed PostgreSQL health/runtime is therefore unverified.
- No Git remote exists. Independent reviews, the bootstrap commit, and the distinct evidence-closure commit remain pending; Session 00 stays fail-closed and `next_session` remains `0`.

## 2026-08-08T15:53:49Z — Session 00 review remediation

- Reconciled Compose to one interpolated database credential contract and added authenticated TCP PostgreSQL smoke scripts for Bash and PowerShell.
- Moved completion-transition validation into the shipped `money-machine-control` entry point with atomic persistence and rejection tests against the real CLI.
- Replaced the committed detailed rename receipt with a safe source identity register; detailed receipts remain ignored runtime evidence.
- Added Appendix B line-count validation and a copyright-safe deterministic PDF page-tree/content-stream verifier.
- Reran the full canonical Python gates and a source-only clean bootstrap: Ruff, strict Pyright, 23 Pytest tests, prompt/source verification, frozen installs, web lint/typecheck/2 tests/build, Compose interpolation, and Bash/PowerShell parsing passed.
- Docker daemon responsiveness and authenticated PostgreSQL runtime remain unproven. Fresh post-remediation reviews and Git checkpoints remain pending, so Session 00 remains `incomplete`.
- The latest bounded `docker info` attempt returned exit 1 with `Cannot connect to the Docker daemon at unix:///var/run/docker.sock`; this supersedes the earlier timeout as the current blocker evidence.

## 2026-08-08T17:26:54Z — Session 00 full-scaffold and second-review repair

- Added every file and directory declared by the canonical repository structure: the deterministic verifier reports 293 files and 96 directories, with inert Python placeholders and fail-closed uncommissioned operational surfaces.
- Repaired completion semantics to require real Git commit objects, exact bootstrap subject, ancestry, branch/HEAD agreement, clean tracked state, and a non-self-referential closure followed by a separate state-pointer commit.
- Isolated Compose contract tests from developer `.env` files and stale ambient `DATABASE_URL` values; static contract checks remain runnable when Docker Desktop is unavailable, while the real CLI check skips with an explicit infrastructure reason.
- Recorded exact Windows, WSL, PowerShell, Git/GitHub CLI, Docker/Compose, Python/uv, Node/pnpm, Chromium, and Playwright availability evidence.
- Integrated canonical gates passed: Ruff across 271 files, strict Pyright with zero findings, 27 Pytest tests with one Docker-CLI skip, scaffold/prompt/PDF verifiers, Bash syntax and fail-closed exits, and PowerShell AST parsing/fail-closed exits.
- A fresh source-only clean copy excluded both private PDF locations and `.omx`; frozen Python/Node installs, the same Python gates, 27 tests with one Docker-CLI skip, clean-clone source verification, web lint/typecheck/2 tests, and a nine-route production build passed.
- Docker Desktop's WSL CLI mount now returns `Input/output error`; Compose CLI, PostgreSQL runtime, and health remain externally blocked. Post-repair review and Git checkpoints remain pending, so Session 00 remains `incomplete`.

## 2026-08-08T17:54:20Z — Session 00 Docker runtime restored

- Docker server `29.4.2` became available. A WSL-only credential-helper PATH mismatch was handled process-locally and then repaired in `scripts/verify_postgres.sh` without changing global Docker configuration.
- Pulled PostgreSQL 16 Alpine, created the Compose network and data volume, reached container `healthy`, and passed an authenticated TCP `psql` query returning exactly `1`.
- Built the API, web, worker, and scheduler images from the repository Dockerfiles. PostgreSQL, API, and web all reached Compose health.
- Container API `/health` returned HTTP 200 with the typed `api` payload; container web `/api/health` returned `dependencies: unverified` and `externalActions: false`.
- Worker and scheduler containers both exited exactly 78 with restart disabled, proving the intended fail-closed uncommissioned boundary.
- Reran the full Python suite with the real Compose CLI: **28 passed** with no skips. A fresh source-only bootstrap also passed its Docker Compose configuration step.
- Runtime gates are now closed. Fresh implementation/adversarial review and the Git checkpoint sequence remain; Session 00 stays `incomplete` until those receipts exist.

## 2026-08-08T20:33:22Z — Session 00 final remediation and implementation approval

- Repaired the bootstrap scripts so both Python and web dependencies are installed from frozen lockfiles; added strict-deny root rules and adversarial ignore probes for tokens, cookies, browser profiles, screenshots, receipts, customer data, and provider payloads.
- Prevented production restart loops by explicitly setting worker and scheduler restart policies to `no`; fresh containers exited intentionally with code 78 and zero restarts.
- Hardened the completion transition so the committed pre-transition state must already contain every non-Git evidence fact, continuity fields cannot be rewritten by the candidate, exactly one outer-gates blocker may be removed, and the closure commit's state must exactly equal the live pre-transition state.
- Fresh canonical and source-only runs passed Ruff across 271 files, strict Pyright with zero findings, **53 Pytest tests**, web lint/typecheck/**2 tests**/nine-route build, Bash and PowerShell parsing/fail-closed checks, development and production Compose resolution, authenticated PostgreSQL, API/web health, and worker/scheduler fail-closed runtime.
- Independent focused re-review changed the implementation verdict from REJECT to **APPROVE** after both HIGH findings were repaired. Adversarial clearance and the three-commit local closure sequence remain pending; the remote blocker remains push-only.
- Independent adversarial re-audit then issued **CLEAR** for the leader-owned local closure sequence after 35 fresh focused tests and a 375-path staging projection with no forbidden paths. This clearance is not itself a completion or push claim; the three required local commits and atomic transition remain.
- Created the exact 375-path bootstrap commit `1abf0d7cca3a6b8cd7efcd0a45523538fd5bfd9d` with subject `chore(bootstrap): initialise money machine autonomous monorepo`. The staged-path manifest matched the adversarial projection, contained no forbidden path or symlink, and immutable source hashes were unchanged immediately before commit.

## 2026-08-08T20:57:00Z — Session 00 atomic completion

- Created evidence-closure commit `50350b9937ad97dabf4be3762a00638d62aaa5b9`, a direct descendant of bootstrap `1abf0d7cca3a6b8cd7efcd0a45523538fd5bfd9d`, containing the exact still-incomplete pre-transition state.
- Ran the shipped `money_machine.control apply-completion` entry point while branch `build/full-automation` was clean and attached at that closure commit. The validator resolved both commit objects, checked the exact bootstrap subject and ancestry, compared the closure document with the live state, and atomically advanced state revision 9 to 10.
- Session 00 is now locally complete: `completed_sessions` is `[0]`, `next_session` is `1`, the canonical Session 01 prompt is selected, all completion evidence is true, and only the precise push-only `REMOTE_NOT_CONFIGURED` blocker remains.
- This completed state and the four companion control documents are checkpointed by the later state-pointer commit containing this entry; the state intentionally does not claim that commit's own object ID.

## 2026-08-08T23:36:23Z — Public GitHub publication and CodeRabbit review

- Acting on explicit operator authorization, created public repository `OmarA1-Bakri/money-machine`, configured `origin`, and pushed `build/full-automation`. Remote HEAD for that branch exactly matched local `ef4a2039d976285d295e429cebbfdd9951bd7bf4`; GitHub reported visibility `PUBLIC` and selected the pushed branch as default.
- The public-visibility instruction supersedes the earlier private-remote assumption for this repository only. The immutable PDF, `.omx`, runtime evidence, secrets, browser state, customer/provider payloads, dependency caches, and local knowledge graph were not tracked or pushed.
- CodeRabbit's all-file CLI attempt was rejected by the 150-file limit, so the review was split into bounded scopes using an isolated empty Git metadata baseline without changing the canonical worktree/index/history.
- CodeRabbit completed agents, domain, integrations, control, and orchestration reviews. It raised four issues: one critical and one major in `control/state.py`, plus trivial locking and logging findings. Persistence, API, tests, apps, and scripts retries were blocked by a 51-52 minute account rate limit because the selected organization lacks an assigned seat/API key.
- No CodeRabbit-suggested change was applied automatically. The issues and incomplete scopes are carried into Session 01 for validation and an authorized fix/re-review cycle.

## 2026-09-06T18:30:01Z — Session 01 activation and adversarial-review remediation (in progress)

- Session 01 work had accumulated in the worktree since 2026-08-09 without a ledger entry; this entry records it. A three-lane adversarial review on 2026-09-07 returned NOT CLEAR (one critical, seven high); the record is `docs/control/reviews/2026-09-07-session-01-adversarial-review.md`.
- Implemented the D-0010 activation transition (`money-machine-control activate`) with fail-closed tests for wrong-session, double, evidence-claiming, and pointer-rewriting activations, and generalised completion beyond Session 00 with a Session 01 closure test. Applied the activation to the live state through the shipped CLI: revision 11 → 12, `current_session` 1, `session_status` incomplete, Session 01 evidence keys installed as false.
- Implemented D-0009 filesystem identity (`same_file` on the canonical directory entry) so the lowercase WSL spelling of the root is accepted and hard-linked aliases are rejected.
- Made `MULTIPLY` a workflow boundary: the winner returns to `OBSERVING`, `require_successor_spawn` admits a distinct-workflow successor at `DEDUPE_CHECK`, and the same-workflow edge is rejected. Transition tests are now exhaustive over every state pair.
- Bound playbook shape rules into `ListingPackage` and `ProductSpec` (D-0022), typed the fifteen-per-week machine cap as an invariant, added `config/autonomy.yaml` (git-ignored) as the only production authority with `APP_ENV` environment resolution (D-0020), and recorded state-machine deviations (D-0021).
- Governance scripts `scripts/write_resume_checkpoint.py` and `scripts/omx_task_metrics.py` are now on this branch (copied byte-for-byte from `integration/first-product-vertical-slice`); `scripts/run_affected_tests.sh` remains conditional in governance because its database helpers are not on this branch.
- Worktree register (status relative to `build/full-automation` HEAD `0827baa`, all under ignored `.omx/`, none deleted): `integration/first-product-vertical-slice` unmerged, 49 commits ahead, last 2026-08-28, active reference source; `wave1/orchestration-task-4` (5 ahead), `wave1/research-task-5` (4), `wave1/build-task-6` (4), `wave1/build-task-6-clean` (4), `wave1/build-task-6-clean-r5` (4), `wave1/build-task-6-r7` (5), `wave1/listing-task-7` (13), all last touched 2026-08-09/10, inactive; two detached `worker-*` trees (1 ahead each, 2026-08-09), inactive. Their unmerged content has not been reconciled into this branch and is not claimed as Session 01 evidence.
- CodeRabbit's four Session 00 issues are fixed in `control/state.py` and tested; the `CODERABBIT_REVIEW_OPEN` blocker and the OPEN rows in `TEST_EVIDENCE.md` stay until the remaining scopes are re-reviewed. Session 01 remains `incomplete`.

## 2026-09-06T20:52:51Z — Session 01 review findings 9 to 13 remediated

- Canonical `bash scripts/test.sh` now exits 0 on this tree: frozen sync, Ruff format and lint across the repository scope, strict Pyright with zero findings, **149 Pytest tests passed** with one filesystem-dependent skip, and Compose configuration. Tool directories and Markdown are excluded from Ruff; tool directories and the operator autonomy file are git-ignored.
- Workflow graph validated for reachability and effect-mode consistency (D-0023); `CullDecisionJob` removed, `LinkVerificationJob` and `NotionRepairJob` added, `ScaleEvaluationJob` wired through the monthly deep pass, provisioning writes admit simulation.
- Telemetry typed and loaded (`TelemetryEventName`, `TelemetryConfig`); commissioning evidence typed as locatable references; `DedupeResult` records rule version and compared catalogue; real subprocess tests prove fail-closed exit 78.
- CodeRabbit disposition recorded in `TEST_EVIDENCE.md`; the blocker remains until the vendor re-review completes. Web gates remain environment-blocked (`pnpm` EACCES on `/mnt/d`). Session 01 remains `incomplete`; remaining closure work is the Session 01 exit criteria evidence, the independent final reviews, and the closure commit sequence.
- Independent re-review of this wave found an unreproduced Ruff panic in the root-scope format walk plus doc/config drift and an event-ordering defect; remediated per D-0024 (explicit-path gate, `REPAIR_APPLIED` before `REPAIR_COMPLETED`, doc-versus-config drift test, traversal guard). Final canonical gate result is recorded in `TEST_EVIDENCE.md`.

## 2026-09-07T00:54:17Z — Session 01 closure wave

- Ran the two closure reviews the Session 01 prompt requires. They raised three HIGH findings, all remediated: `AgentResult` now carries `agent_run_id`, `agent_id`, `agent_definition_version`, `prompt_reference`, and `prompt_sha256` with artifact-to-run binding; `NOTION_LINK_PUBLISH` moved to `BROWSER` and `NOTION_WORKSPACE_PROVISION` to `MANUAL_EXTERNAL_BLOCKER`; reconciliation of uncertain external effects is designed with a typed `EffectReference` and per-job idempotency-key templates (D-0025).
- Also closed the accompanying mediums: the integration matrix names the `capability_operation` code on every row and a test asserts codes and channels match configuration; the entity diagram corrects product-to-spec and listing-to-metrics cardinality and adds the idempotency, receipt, research, asset and incident edges; `ProductQAResult` names the artifacts it checked and `PreflightResult` pins the package hash; `DEPLOYMENT.md` states the five-step go-live procedure and `AUTONOMY_MODEL.md` names the second publication switch.
- Web gates passed after the install failure was diagnosed: the pnpm hardlink rename fails on the 9p `/mnt/d` mount, so the install used `--package-import-method copy`. Lint, typecheck, two tests and a nine-route production build all exited 0. The first build attempt failed with a Turbopack out-of-memory error and passed on one rerun; both are recorded in `TEST_EVIDENCE.md`.
- **Integrator error recorded:** `git checkout -- docs/architecture/INTEGRATION_MATRIX.md` discarded that file's uncommitted Session 01 content and restored the committed placeholder. The file was reconstructed in full from content read earlier in the session, improved with operation codes, and is now covered by a test. No other file and no committed history was affected. The lost bytes were never committed and are unrecoverable; the reconstruction is content-equivalent by review, not byte-identical.
- Final full gate on the frozen bytes: `bash scripts/test.sh` exit 0 with Ruff format and lint clean, strict Pyright zero findings, **152 Pytest tests passed** with one filesystem-dependent skip, and Docker Compose configuration valid; canonical scaffold verification passed; web lint, typecheck, tests and nine-route build all green.

## 2026-09-07T00:56:53Z — Session 01 atomic completion

- Implementation commit `156e279` carries the canonical subject `docs(architecture): define playbook automation contracts` and 75 paths with no secret, private source, runtime evidence, provider payload, symlink, or tool-directory content.
- Evidence-closure commit `15b5df45c3a535548fe24698a590fc16c5757829` contains the exact still-incomplete pre-transition state at revision 14.
- The shipped `money-machine-control apply-completion` entry point validated both commit objects, ancestry from the prior closure, branch and HEAD agreement, a clean tracked tree, and the closure document's byte equality with the live state, then advanced revision 14 to 15 atomically.
- Session 01 is locally complete: `completed_sessions` is `[0, 1]`, `next_session` is 2, the canonical Session 02 prompt is selected, and all nine Session 01 evidence keys are true. The `CODERABBIT_REVIEW_OPEN` blocker is retained because the vendor re-review is still rate-limited.
- This completed state and its four companion control documents are checkpointed by the later state-pointer commit that contains this entry; the state does not claim that commit's own object ID.

## 2026-09-07T01:01:06Z — Post-transition regression repair

- The post-transition full gate failed: 45 control-state tests broke because their Session 00 fixtures deep-copy the live state, which now carries `transition_contract.completion_requires_next_session: 2`. The fixtures, not the transition, were wrong; the applied Session 01 completion is unaffected and was not rewritten.
- Fixed by pinning the Session 00 fixture and its candidate to their own transition contract, so programme advance can no longer break session-scoped fixtures. Re-ran the canonical gate: `bash scripts/test.sh` exit 0 with Ruff clean, strict Pyright zero findings, **152 Pytest tests passed** with one filesystem-dependent skip, and Compose configuration valid.
- Recorded rather than hidden: the earlier 152-test green predates the control-file update, so it did not bind these bytes. The lesson is that the final gate must run after the control files are written, not before.

## 2026-09-07T04:36:32Z — Session 02 activation

- Added Session 02's completion-evidence contract to `SESSION_EVIDENCE_KEYS` from the prompt's own exit criteria: fresh bootstrap path documented, schema and migrations work, seeds idempotent, runtime containers start, CI configuration complete, foundation tests pass, control files current, plus the evidence-closure key. A test now asserts every session's contract is contiguous and carries the closure key, so a future session cannot be activated without one.
- Ran `money-machine-control activate`: revision 15 to 16, `current_session` 2, `session_status` incomplete, `completed_sessions` `[0, 1]` and the next-session pointer unchanged, all eight Session 02 evidence keys installed as false. `head_sha` still records the Session 01 evidence-closure commit, as the contract requires.
- No Session 02 implementation work has started. Provider effects remain in simulation; nothing is commissioned.

## 2026-09-07T04:51:00Z — Prompt-integrity review becomes a standing gate

- Every session now proves its own prompt before obeying it. `docs/PROMPT_INTEGRITY_REVIEW.md` defines the adversarial review across fidelity, safety and executability, and gameability, followed by a corrective exercise that produces the addendum the session actually executes. `AGENTS.md`, `CLAUDE.md`, and governance section 0 carry the standing rule; D-0026 records why it cannot live inside the prompt files, which are hash-verified extracts of an immutable source.
- `tests/bootstrap/test_prompt_integrity.py` enforces it: the procedure must be published and referenced from all three rule documents, every session from 02 onward must have a record, each record must carry its prompt's verified hash and a corrective addendum, and every extracted prompt must still match the workbook appendix so amendments can never be made in place. The gate was observed failing closed for Session 02 before its record existed.
- Ran the review for Session 02 and recorded it at `docs/control/reviews/2026-09-07-session-02-prompt-integrity.md`. The prompt is byte-faithful and still defective: one critical finding that would remove the fail-closed worker and scheduler boundary before the durable orchestrator exists, five high findings including the loss of every Session 01 lineage field at the schema boundary and the absence of any QA, preflight, or dedupe result table, and exit criteria that are satisfiable by stubs. The ten-point corrective addendum now governs Session 02 execution, with three deferrals recorded against named owners.
- No Session 02 implementation work has started.

## 2026-09-07T07:41:19Z — Session 02 engineering foundation implemented

- Executed the ten-point corrective addendum from the Session 02 prompt-integrity review in four bounded slices: tooling and settings; schema, migrations and persistence; seed, command line and interface; containers, continuous integration and documentation.
- Added the database dependencies and a `money-machine` console script distinct from the fail-closed `money-machine-control`. Runtime settings cover database, interface, worker, scheduler, storage and five providers, with a `Secret` type that redacts in every representation and a URL that never holds a credential.
- Implemented 45 tables: the workbook's 33 logical entities plus twelve the addendum and its reviews required so Session 01's contracts persist, one reviewed Alembic revision, an async session and unit of work, and typed repositories with bounded pages and real optimistic locking.
- Seeding is idempotent, convergent and concurrency-safe. Interfaces expose liveness, a readiness check that actually fails, version, database status, workflow and job pages, and an integration status that reports presence only.
- Worker and scheduler keep their fail-closed contract: a read-only connectivity check, then exit 78, with no claim path anywhere in the source. Verified in containers.
- Two independent closure reviews both returned NOT CLEAR with two critical and ten high findings between them. All were remediated and pinned by tests: evidence has a table, optimistic locking is enforced by the mapper, lineage is foreign-keyed, verdicts cannot cite what does not exist, composite keys stop a lineage record lying, append-only tables carry refusal triggers, and taxonomies agree with the contracts. Recorded as D-0027.
- Final gates: `bash scripts/test.sh` exit 0 with **370 Pytest tests passed** and one filesystem-dependent skip; web lint, typecheck, two tests and a nine-route build all 0; canonical scaffold verification passed.
- Recorded rather than acted on: the shared development database and roughly four hundred leftover test databases belong to other branches and were left untouched. One verification command of mine briefly pointed the stack at that shared database; the migration aborted before any statement and the database was confirmed unchanged.

## 2026-09-07T07:43:45Z — Session 02 atomic completion

- Implementation commit `05695fa` carries the canonical subject `feat(foundation): add database runtime and project tooling` across 74 paths with no secret, private source, runtime evidence, operator authority, tool directory or symlink.
- Evidence-closure commit `e75b31745beef8d0368e9a21c437176edafb46a2` contains the exact still-incomplete pre-transition state at revision 18.
- The shipped `money-machine-control apply-completion` entry point validated both commit objects, ancestry from the Session 01 closure, branch and HEAD agreement, a clean tracked tree, and the closure document's byte equality with the live state, then advanced revision 18 to 19 atomically.
- Session 02 is locally complete: `completed_sessions` is `[0, 1, 2]`, `next_session` is 3, the canonical Session 03 prompt is selected, and all eight Session 02 evidence keys are true. The `CODERABBIT_REVIEW_OPEN` blocker is retained because the vendor re-review is still rate-limited.
- This completed state and its four companion control documents are checkpointed by the later state-pointer commit containing this entry.

## 2026-09-20 — Session 04 control tip-sync (W1–W3 + Phase A)

- Parallel control lane only (`docs/control/*`). No feature code, no AgentRunner/roster/observability implementation, no Exit 78 lift, no live Notion/Etsy.
- Refreshed `IMPLEMENTATION_STATE.json` to repository tip `3cbe39bf7284da5b4a013b41c2521f0fdb9a0fa6` (post #21 Phase A on `build/full-automation`). State revision 23 → 24.
- Evidence keys updated to match delivered waves: `provider_abstraction_implemented` and `prompt_registry_and_hashes_implemented` set true after W2 (#19) and W3 (`726437d`); `control_files_and_checkpoint_current` set true by this tip-sync. Six keys remain false: agent runner integration, sixteen-agent roster, uncommissioned-agent documentation, full contract/runtime suite, and closure candidacy.
- Phase A (Jev client, registry, FakeJev, persistence, shadow dry-run @ `3cbe39b`) recorded in state notes as library-complete but outside the eight Session 04 exit-criteria keys.
- Exit 78 unchanged. Session 04 remains `incomplete`; `completed_sessions` unchanged at `[0, 1, 2, 3]`.
- Local verification of affected suites: **85 passed** across W2/W3/Phase A tests plus **61 passed, 12 skipped** in `tests/bootstrap/test_control_state.py` (279 s total on cloud agent VM).

## 2026-09-20 — Session 04 control tip-sync (W4–W8 + Phase A)

- Parallel control lane only (`docs/control/*`). No feature code, no Exit 78 lift, no live Notion/Etsy, no W9 decision record.
- Refreshed `IMPLEMENTATION_STATE.json` to repository tip `d9eb8e282078aea0436025ad254ca24bfb52bfbe` (post-W6 on `build/full-automation`). State revision 24 → 25.
- Fixed parked transition-contract drift: `completion_requires_next_session` aligned from 3 to 4 to match `next_session` while Session 04 remains active.
- Evidence keys updated to match delivered waves: `sixteen_agents_registered` and `uncommissioned_agents_documented` set true after W5 (`827272b`) and W8 (`44d554f`); `agent_runner_integrated_with_jobs` and `contract_and_runtime_tests_pass` remain false — W4 proves library runner receipts and commissioning gates only; orchestrator-lease → successor runtime integration and full exit-criteria suite are not yet delivered. `control_files_and_checkpoint_current` set true by this tip-sync.
- W4–W8 and Phase A recorded in state notes. Exit 78 unchanged. Session 04 remains `incomplete`; `completed_sessions` unchanged at `[0, 1, 2, 3]`.
- Local verification of affected suites: **162 passed, 4 skipped** across W4–W8 tests plus **146 passed, 12 skipped** across W2/W3/Phase A and `tests/bootstrap/test_control_state.py` (279 s total on cloud agent VM).

## 2026-09-20 — Session 04 control tip-bump (post-Lane C @ `744cc36b`)

- Rebased PR #30 onto post-C tip `744cc36ba162ac780bd14df75856d5a9cbd7e760` on `build/full-automation`. Docs/control only; no feature code, no Exit 78 lift, no W9 decision record.
- Refreshed `head_sha` and `evidence_closure_commit_sha` to `744cc36b`. State revision 25 → 26.
- `contract_and_runtime_tests_pass` set true: Lane C `tests/integration/test_runtime_integration.py` present on tip (lease → run → persist → event → successor library path; **2 passed, 2 skipped** locally) plus W8 roster contracts (**135 passed**).
- `agent_runner_integrated_with_jobs` remains false — Lane A orchestrator wire not delivered; library runtime tests alone do not earn production job integration.
- Exit 78 unchanged. Session 04 remains `incomplete`; `completed_sessions` unchanged at `[0, 1, 2, 3]`.

## 2026-09-20 — Session 04 W9: Exit 78 lift (worker) + production claim path (@ `14da7fe`)

| Claim | Evidence | Verdict |
|---|---|---|
| W9 scope | Exit 78 lift for WORKER (conditionally, behind D-0028 commissioning gates). Production claim path: claim READY jobs → AgentRunner.execute() → persist → emit events → spawn successors. Scheduler remains Exit 78 (W9 out of scope) | Merge commit `14da7fe` | PASS |
| Worker claim loop | `src/money_machine/orchestration/worker.py` 471 lines; production claim cycle with commissioning gate check, lease acquisition (`FOR UPDATE SKIP LOCKED`), AgentRunner invocation, result persistence, event emission, successor creation | 7 integration/unit tests | PASS |
| Commissioning gates (D-0028) | Seven-gate evidence check: (1) runtime settings valid, (2) agent registry loads, (3) at least one TESTED/COMMISSIONED agent, (4) tool registry loads, (5) prompt integrity (file exists, hash match, sections present, no secrets), (6) AgentRunner functional, (7) lease/claim functions available. Returns true only if ALL gates pass | `_check_commissioning_gates()` in worker.py | PASS |
| Uncommissioned fail-closed | Agents in state DESIGNED refuse execution; worker checks `commissioning_state` before invoking AgentRunner; raises `AgentNotCommissionedError` and fails job with event `AGENT_NOT_COMMISSIONED` | `test_foundation_processes.py` +81 lines | PASS |
| Concurrent claim safety | Idempotent re-claim: two workers claim same job concurrently; exactly one succeeds with `READY → RUNNING → SUCCESS`, second gets lease collision and finds job complete. Double-execution prevention: `FOR UPDATE SKIP LOCKED` ensures only one worker acquires lease. Reconciliation: crash after execute but before event → lease expires → re-claim → idempotency keys prevent duplicate effects | `tests/integration/test_concurrent_claims.py` 339 lines | PASS |
| Runtime integration | Worker claim path integration: claim → execute → persist → event → successor; deterministic fake provider; real database transactions | `tests/integration/test_runtime_integration.py` +139 lines | PASS |
| Scheduler unchanged | Scheduler entrypoint remains `uncommissioned_process("scheduler")` → Exit 78. Cycle (promote due jobs, detect stalled jobs, rebalance) deferred | `scheduler.py` main() docstring | HELD |
| Exit 78 status | Worker: lifted conditionally (D-0028 gates). Scheduler: held (W9 out of scope) | D-0028 in DECISIONS.md | RECORDED |
| `agent_runner_integrated_with_jobs` | Production claim path delivered; not just library tests | W9 evidence @ `14da7fe` | EARNED TRUE |

W9 closes `agent_runner_integrated_with_jobs` evidence key. Seven of eight Session 04 evidence keys are now true. Scheduler Exit 78 remains; W9 scope was worker claim path only. No live provider calls, no Notion/Etsy mutations claimed.

## 2026-09-20 — Session 04 W10: SESSION_04 COMPLETE control flip (post-W9 @ `14da7fe`)

Parallel control lane only (`docs/control/*`). No feature code, no scheduler Exit 78 lift, no S05 features, no live Notion/Etsy.

- Updated `IMPLEMENTATION_STATE.json` to repository tip `14da7fe6e7893e79d6993720ae9413343931bfb0` (post-W9 on `build/full-automation`). State revision 26 → 28.
- Evidence keys: ALL EIGHT TRUE. `agent_runner_integrated_with_jobs` set TRUE after W9 production claim path; `evidence_closure_commit_recorded` set TRUE by W10 control flip.
- Session 04 status: COMPLETE. `completed_sessions` advanced to `[0, 1, 2, 3, 4]`; `next_session` set to 5.
- Exit 78 status recorded honestly: worker lifted conditionally (D-0028 commissioning gates), scheduler held (W9 out of scope).
- Parked #31 SFs noted as carry-forward nits (structural gates env-specific, stale test docstrings cosmetic) — non-blocking.
- Updated `head_sha` and `evidence_closure_commit_sha` to `14da7fe`.
- W1–W9, Phase A, Lane C complete. No S05 features, no scheduler Exit 78 lift, no live production/Notion/Etsy claimed.
- W10 control flip review recorded at `docs/control/reviews/2026-09-20-session-04-wave-10-control-flip.md`.
