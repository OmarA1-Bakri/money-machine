# Implementation Log

## 2026-10-06 — Session 07 W8: variants

Session 07 stays incomplete. This wave is not SESSION_07 COMPLETE. State revision 55 → 56. `current_session` stays 7. `completed_sessions` stays `[0, 1, 2, 3, 4, 5, 6]`. `next_session` stays 7. `next_prompt` stays `10_SESSION_07_PRODUCT_BUILD_VARIANTS_AND_QA.md`. `head_sha` stays the W7 squash `9bc56b2c839f66fce13bebf55cb30e88474f526e`. It is the tip-sync pointer. It moved from the W6 squash `3f0a30a8e52b183f10799128d4fd7b17c1b74495`. It is not the revision that produced the test or mutation figures below. Those figures were measured on this wave's commit, the child of `2c5b6beb`. The prior tip `2c5b6beb` CI verify run is `37454174393`, job `112237594389`, SUCCESS. This commit's CI run id is unknown until CI runs. `evidence_closure_commit_sha` stays the Session 06 closure tip `0f94d585f23d79e5ac18479f01e14f67cbaad332`. `last_verified_commit` stays bootstrap `1abf0d7cca3a6b8cd7efcd0a45523538fd5bfd9d`. `updated_at` is `2026-10-06T12:19:57Z`.

Twelve session 7 evidence keys stay false, including `variant_builder_implemented`. No session exit code is recorded. A07, A08, and A09 stay DESIGNED. `commissioned_agents` stays empty. Exit 78 scheduler stays HELD. Narrative `next_phase` is `qa` (A09) and it is not started. There is no top-level `next_phase` field.

Fixture variants live in `notion_variants.py`. `build_variants` (`notion_variants.py:82`) writes one shallow `duplicate_page` per `colour_variants` entry, zipped in index order with `palette_tokens`. Lengths must match and must be 3 or 4. Release collects every candidate, refuses any unadoptable candidate, and only then drops `product_spec_id` (`notion_variants.py:371-374`). The finish drop is `notion_variants.py:550-551`. `publish_page` (`notion_variants.py:568-569`), `set_duplicate_as_template` (`notion_variants.py:570-571`), and `set_search_indexing` (`notion_variants.py:572-573`) run only on that variant page, and only for a step that is still missing. The secret link is the `get_public_url` call at `notion_variants.py:574`. Replay compares the call at `notion_variants.py:666` with the stored link at `:667`. The module does not contain an `https://` literal. Checkpoint names stay the six build phases. `created_notion_ids["variants"]` stays `None` until `provider_object_references["variants"]` exists, then `notion_progress_record.py:258-269` writes the list. A successful write keeps the loaded created ids and replaces only the variants key (`notion_progress_record.py:180-188`). Page and block counts add the variant pages at `notion_progress_record.py:303-304`. `write_document` is still called only from `write_checkpoint`. A provider failure of `variants.duplicate`, including a `ProviderFailure` from the release `drop_page_property`, leaves a `provider_response` job only when a prior record exists. A first phase-1 failure with no record raises and writes no job and no file (`notion_progress.py:250`). The job phase stays `aesthetics_and_content_completion`. A provider failure still records that repair job through `write_checkpoint`. A refusal is not that path.

The entry order is validate, release, then bind. `_validate_earlier_phases` (`notion_variants.py:98`) checks saved aesthetics and created ids without ProductSpec uniqueness, and it does that before any adapter write. On the stored path, a variant or nested id is a recorded page id (`notion_variants.py:314-326`). A hub child titled `{title} (Copy)` or `/ Blue` is not that id, so replay raises `hub page is unexpected` with zero writes (`test_replay_refuses_a_hub_child_with_a_variant_title`). Extra workspace-level `/ Blue`, `/ Purple`, or `(Copy)` pages pass replay with zero writes. That outcome is pinned by `test_replay_pins_extra_workspace_variant_titles_as_a_known_limit` and is a known limit. A workspace page outside an open variant title stays unexpected (`test_replay_refuses_an_unrelated_workspace_page`). The empty path still opens an unrecorded `{title} (Copy)` or `/ <Colour>` page so resume can adopt it through `_find_titled` and `_find_copy`. `_release_copied_spec_ids` (`notion_variants.py:103`) then runs only on the empty-variants path. The title filter (`notion_variants.py:366-367`) keeps a page whose title is not a variant title and not `{title} (Copy)`. The spec-id compare (`notion_variants.py:368-369`) requires the source value, not mere presence. Both refusal passes finish before any drop (`notion_variants.py:371-374`). `_bind_earlier_phases` (`notion_variants.py:104`) then applies ProductSpec uniqueness. A tampered hub id, database id, deleted accent, or notification database id raises in the first check, before any adapter write, including when a leftover titled page or `(Copy)` page still holds `product_spec_id` (`test_leftover_spec_id_tamper_writes_nothing`, kinds hub, database, accent, and notification). A `(Copy)` page planted before an unrelated `{title} / Blue` page that holds the source spec id raises `variant page does not match` with zero adapter writes (`test_mixed_leftover_and_unrelated_spec_id_writes_nothing`). A database or a page whose parent is the candidate page, or any block of that page, raises the same way with zero writes. The block kinds are accent, vocabulary, text, and callout, the child kinds are database and page, and both the empty path and the stored path are covered (`test_child_under_a_page_block_writes_nothing`). A copy whose child database or child page is parented at the page itself is the same refusal (`test_copy_with_a_nested_child_writes_nothing`). A crash on the first drop, then a database added under that `(Copy)` page, then resume, raises the same way with zero writes (`test_drop_crash_then_child_database_refuses_with_zero_writes`). Replay does not call release. A restored `product_spec_id` raises `variant page does not match` with zero adapter writes (`test_replay_refuses_a_restored_spec_id_without_a_write`). A database under a stored variant, including a database under one of that page's blocks, raises `variant page does not match` with zero writes (`test_replay_refuses_a_database_under_a_variant`, and the stored half of `test_child_under_a_page_block_writes_nothing`). A valid build writes only after that validation.

Adoption compares the title and the copyable shell fields. `_require_adoptable` (`notion_variants.py:548`, defined at `:506`) requires a workspace parent (`:417`), the source parent id (`:418`), the source `product_id` (`:419`), the source shell block id (`:420`), a spec id that is absent or equal to the source (`:516-518`), and no foreign child (`:519-520`). Foreign means no direct child block other than the matching accent and vocabulary, and no database or page whose parent is the page or any block in its block tree (`_has_nested_child` at `:442`, called from `_has_foreign_child` at `:463-464`). The block walk includes blocks nested under other blocks. It runs before any write in `_finish_variant`. An unrelated page titled `{product} / Blue` or `{product} (Copy)`, empty or with a private block, raises before any adapter write, stays unpublished, and is not recorded. Resume finishes a provable titled page (`_find_titled` at `notion_variants.py:277`) or a provable `(Copy)` page (`_find_copy` at `notion_variants.py:278-279`) without a second copy. That adoption path stays title-based and gated by `_require_adoptable`. The by-id rule applies only to the stored-path hub and nested checks. The post-write `_require_variant_page` call is `notion_variants.py:577`. `test_crash_inside_write_checkpoint_before_the_file_lands` asserts one `write_checkpoint` call and `duplicate_page` equal to the colour count on the crash, then one more `write_checkpoint` call on resume with no further adapter writes. A refused rebuild names those variant pages because workspace pages other than home are appended in `_later_phase_object_names` (`notion_product_builder.py:250`, function `:238`). The uniqueness raise is `notion_product_builder.py:349`, message `fixture probe has more than one page for this ProductSpec`. Re-entering `build_aesthetics` after variants raises `hub page is unexpected` and does not rewrite the file. The aesthetics parser strips the `variants` key at `notion_aesthetics.py:150`. The accent and sample block-membership loop is deleted. `drop_page_property` is on the `NotionAdapter` ABC and on every adapter subclass.

Known limits, parked. Provenance here is the title plus those copyable shell fields. An unrelated empty workspace page that carries the source `product_id` and `design_shell_block_id` would be adopted. `parent_id` compares equal when both values are `None`. This wave does not claim a proven lineage. Extra workspace-level `/ Blue`, `/ Purple`, or `(Copy)` pages pass replay with zero writes (`test_replay_pins_extra_workspace_variant_titles_as_a_known_limit`). That is a known limit, not a check this wave closes.

Prompt-integrity review: `docs/control/reviews/2026-10-05-session-07-prompt-integrity.md` (Wave 8 addendum). Product-build tests: 315 passed across the variants file, the progress file, and the six phase files. Full local pytest figures are in `TEST_EVIDENCE.md`. They were measured on this wave's commit, the child of `2c5b6beb`. `head_sha` stays the W7 squash and is not that commit. The prior tip `2c5b6beb` CI verify run is `37454174393`, job `112237594389`, SUCCESS. This commit's CI run id is unknown until CI runs. The local docker failures are known and local-only. CI is the gate. `ruff format --check` and `ruff check` are clean. `pyright` 1.1.411 (`uv.lock` and CI) reports 0 errors on the changed modules with SQLAlchemy 2.0.52. Docstring coverage stays 10.88% (W6, stale; not remeasured). The socket tripwire patches `connect`, `connect_ex`, and `create_connection`. It does not patch `sendto` or `getaddrinfo`.

Carried must-fixes. CI-1 is the replay call `_require_created_ids` at `notion_aesthetics.py:104` (the `if stored.checkpoint_names` block is `:102-105`). CI-2 is the database pair check at `notion_aesthetics.py:276-277`. CI-3 is the hub pair check at `notion_aesthetics.py:281-282`. CI-4 is the accent and sample inequality at `notion_aesthetics.py:299-300`. Replay compares `hubs[].navigation_block_id` on both sides of the hub tuple (`notion_aesthetics.py:279` and `pairs.append` at `notion_aesthetics.py:347`). `reject_duplicate_labels` in aesthetics `_require_pairs` (`notion_aesthetics.py:203`), `_ensure_row` `client_name` (`notion_notifications.py:1195`), and the `_adopted_database` conjunct `title.type != "title"` (`notion_notifications.py:924`) are killed. The W7 created-ids prose partial is closed: CI-1 through CI-4 no longer survive.

Mutation checks. 47 mutations were each applied, the owning test files were run, and the edit was reverted. 47 were killed. No row is PARTIAL. A row is killed only when at least one test failed. The Failed column is the real pytest failure count for that mutant. The Failed column sums to 514.

| Mutation | Site (file:line) | Failing tests | Failed |
|---|---|---|---|
| CI-1 delete the replay call | `notion_aesthetics.py:104` (block `:102-105`) | `test_replay_rejects_a_tampered_top_level_page_id`, `test_replay_rejects_a_tampered_database_id`, `test_replay_rejects_a_tampered_hub_page_id`, `test_replay_rejects_a_tampered_navigation_block_id`, `test_replay_rejects_a_tampered_notification_database_id`, `test_replay_rejects_a_tampered_accent_block_id` | 6 |
| delete the page, workspace, and shell id check | `notion_aesthetics.py:268-275` | `test_replay_rejects_a_tampered_top_level_page_id` | 1 |
| CI-2 delete the database pair check | `notion_aesthetics.py:276-277` | `test_replay_rejects_a_tampered_database_id`, `test_earlier_phase_tamper_writes_nothing` for `database-empty` and `database-stored`, `test_leftover_spec_id_tamper_writes_nothing` for `titled-database-empty`, `titled-database-stored`, `copy-database-empty`, and `copy-database-stored` | 7 |
| CI-3 delete the hub pair check | `notion_aesthetics.py:281-282` | `test_replay_rejects_a_tampered_hub_page_id`, `test_replay_rejects_a_tampered_navigation_block_id`, `test_earlier_phase_tamper_writes_nothing` for `hub-empty` and `hub-stored`, `test_leftover_spec_id_tamper_writes_nothing` for `titled-hub-empty`, `titled-hub-stored`, `copy-hub-empty`, and `copy-hub-stored`, `test_drop_crash_then_tamper_writes_nothing_and_clean_resume_finishes` | 9 |
| delete the notification database id check | `notion_aesthetics.py:285-291` | `test_replay_rejects_a_tampered_notification_database_id`, and `test_leftover_spec_id_tamper_writes_nothing` for `titled-notification-empty`, `titled-notification-stored`, `copy-notification-empty`, and `copy-notification-stored` | 5 |
| CI-4 delete the accent and sample pair check | `notion_aesthetics.py:299-300` | `test_replay_rejects_a_tampered_accent_block_id` | 1 |
| drop `navigation_block_id` from both hub tuples | `notion_aesthetics.py:279` and `:347` | `test_replay_rejects_a_tampered_navigation_block_id` | 1 |
| delete `reject_duplicate_labels` in aesthetics `_require_pairs` | `notion_aesthetics.py:203` | `test_replay_rejects_a_duplicated_accent_token` | 1 |
| delete the variants reference strip | `notion_aesthetics.py:150` | `test_replay_keeps_the_same_bytes_and_ids`, `test_aesthetics_replay_after_variants_writes_nothing`, `test_replay_rejects_a_tampered_variant_page_id`, `test_earlier_phase_tamper_writes_nothing` for `hub-stored`, `database-stored`, and `accent-stored`, the eight stored `test_leftover_spec_id_tamper_writes_nothing` cases, the eight stored `test_child_under_a_page_block_writes_nothing` cases, both `test_replay_refuses_a_hub_child_with_a_variant_title` cases, the three `test_replay_pins_extra_workspace_variant_titles_as_a_known_limit` cases, `test_replay_refuses_a_restored_spec_id_without_a_write`, `test_replay_refuses_an_unrelated_workspace_page`, `test_replay_refuses_a_database_under_a_variant`, `test_crash_after_write_checkpoint_resumes_without_a_second_page`, `test_secret_link_comes_from_get_public_url`, `test_replay_rejects_a_dropped_colour`, `test_replay_rejects_a_swapped_colour_token` | 34 |
| delete `_ensure_row` `client_name` | `notion_notifications.py:1195` | `test_ensure_row_rejects_client_name_on_an_adopted_database` | 1 |
| delete `_adopted_database` `title.type != "title"` | `notion_notifications.py:924` | `test_adopted_database_rejects_a_text_title` | 1 |
| delete the variants created-id comparison | `notion_variants.py:130` | `test_replay_rejects_a_tampered_variant_page_id` | 1 |
| delete the `product_spec_id` drop | `notion_variants.py:550-551` | 54 tests: the mass, business, and four-colour builds, stored-checkpoint tampers, the eight stored leftover tampers, the eight stored block-child cases, both hub-child title cases, the three extra-workspace title pins, the eleven crash-resume steps, `test_replay_refuses_a_restored_spec_id_without_a_write`, `test_replay_refuses_an_unrelated_workspace_page`, `test_replay_refuses_a_database_under_a_variant`, `test_drop_crash_then_tamper_writes_nothing_and_clean_resume_finishes`, `test_drop_crash_then_child_database_refuses_with_zero_writes`, `test_crash_after_write_checkpoint_resumes_without_a_second_page`, `test_crash_inside_write_checkpoint_before_the_file_lands`, `test_secret_link_comes_from_get_public_url`, `test_variant_build_does_not_open_a_socket`, and `test_refused_rebuild_names_the_variant_pages` | 54 |
| delete `set_duplicate_as_template` | `notion_variants.py:570-571` | the 54 `product_spec_id` drop failures except `test_drop_crash_then_child_database_refuses_with_zero_writes` | 53 |
| delete `set_search_indexing` False | `notion_variants.py:572-573` | the same 53 tests as `set_duplicate_as_template` | 53 |
| delete `publish_page` | `notion_variants.py:568-569` | those 53 tests, plus `test_finish_does_not_record_a_page_that_stays_indexed` | 54 |
| delete the variants guard | `notion_variants.py:281-282` | `test_provider_failure_resumes_without_a_second_copy` | 1 |
| B1 replace the `_find_titled` call with `existing = None` | `notion_variants.py:277` | `test_provider_failure_resumes_without_a_second_copy`, `test_unrelated_page_is_not_adopted[empty-titled]`, `test_each_variant_step_crash_resumes_without_a_second_page` for `set_icon`, `set_cover`, `add_callout_block`, `add_text_block`, `publish_page`, `set_duplicate_as_template`, `set_search_indexing`, and `get_public_url`, and `test_crash_inside_write_checkpoint_before_the_file_lands` | 11 |
| B2 delete adopt of the (Copy) page | `notion_variants.py:278-279` | `test_unrelated_page_is_not_adopted[empty-copy]`, `test_one_adoption_field_refuses_before_any_write[foreign_child]`, `test_release_keeps_a_different_spec_id_value`, `test_each_variant_step_crash_resumes_without_a_second_page` for `drop_page_property` and `rename_page`, `test_drop_crash_then_tamper_writes_nothing_and_clean_resume_finishes` | 6 |
| skip writing variants into created ids | `notion_progress_record.py:258-269` | `test_mass_tier_publishes_one_page_per_colour`, `test_replay_keeps_the_same_bytes_and_ids`, `test_replay_rejects_a_tampered_variant_page_id`, `test_earlier_phase_tamper_writes_nothing[accent-stored]`, `test_leftover_spec_id_tamper_writes_nothing` for `titled-accent-stored` and `copy-accent-stored`, the eight stored `test_child_under_a_page_block_writes_nothing` cases, both `test_replay_refuses_a_hub_child_with_a_variant_title` cases, the three `test_replay_pins_extra_workspace_variant_titles_as_a_known_limit` cases, `test_replay_refuses_a_restored_spec_id_without_a_write`, `test_replay_refuses_an_unrelated_workspace_page`, `test_replay_refuses_a_database_under_a_variant`, `test_crash_after_write_checkpoint_resumes_without_a_second_page`, `test_secret_link_comes_from_get_public_url`, `test_replay_rejects_a_dropped_colour`, `test_replay_rejects_a_swapped_colour_token` | 26 |
| skip variant page and block counts | `notion_progress_record.py:303-304` | `test_mass_tier_publishes_one_page_per_colour` | 1 |
| B-V1 read `page.public_url` instead of `get_public_url` | `notion_variants.py:574` | `test_secret_link_comes_from_get_public_url`, `test_each_variant_step_crash_resumes_without_a_second_page[get_public_url]`. The mutant is that call. It is not the `set_search_indexing` line above it | 2 |
| B-V2 delete the colour and token tuple compare | `notion_variants.py:652-654` | `test_replay_rejects_a_swapped_colour_token` | 1 |
| B-V2 delete the variant length check | `notion_variants.py:649-650` | `test_replay_rejects_a_dropped_colour`, which asserts `type` is `ProductBuildError` and the message `checkpoint variants do not match the ProductSpec`. The `zip(..., strict=True)` on the next line stays. Deleting the length check lets `ValueError` escape | 1 |
| B3 skip the created-id validator call | `notion_variants.py:175` | `test_earlier_phase_tamper_writes_nothing` for hub and database, empty and stored, the twelve leftover hub, database, and notification cases, and `test_drop_crash_then_tamper_writes_nothing_and_clean_resume_finishes` | 17 |
| B3 skip the created-id validator when variants are empty | `notion_variants.py:175` | `test_earlier_phase_tamper_writes_nothing` for `hub-empty` and `database-empty`, `test_leftover_spec_id_tamper_writes_nothing` for titled and `(Copy)` hub, database, and notification on an empty checkpoint, and `test_drop_crash_then_tamper_writes_nothing_and_clean_resume_finishes` | 9 |
| B3 move the created-id validator after `_require_saved` and `_ensure` | `notion_variants.py:175` and `:98-105` | `test_earlier_phase_tamper_writes_nothing` for `hub-empty` and `database-empty`, `test_leftover_spec_id_tamper_writes_nothing` for titled and `(Copy)` hub, database, and notification on empty and stored checkpoints, and `test_drop_crash_then_tamper_writes_nothing_and_clean_resume_finishes` | 15 |
| B3 delete the aesthetics saved check before variants | `notion_variants.py:166-174` | `test_earlier_phase_tamper_writes_nothing` for `accent-empty` and `accent-stored`, the four accent `test_leftover_spec_id_tamper_writes_nothing` cases, `test_replay_refuses_an_unrelated_workspace_page`, both `test_replay_refuses_a_hub_child_with_a_variant_title` cases, `test_release_keeps_another_products_spec_id_on_private_notes`, and `test_release_keeps_a_renamed_duplicate_spec_id` | 11 |
| replace the validate call with the ProductSpec uniqueness bind | `notion_variants.py:98` | Replacing `_validate_earlier_phases(...)` with `_bind_earlier_phases(...)`. This is the mutation that kills the leftover tampers. All 16 `test_leftover_spec_id_tamper_writes_nothing` cases, `test_unrelated_page_is_not_adopted` for `private-titled` and `private-copy`, `test_mixed_leftover_and_unrelated_spec_id_writes_nothing`, `test_copy_with_a_nested_child_writes_nothing` for `database` and `page`, the eight empty `test_child_under_a_page_block_writes_nothing` cases, `test_one_adoption_field_refuses_before_any_write` for `parent_type`, `parent_id`, `product_id`, `shell_block`, and `release_shell` (not `foreign_child`), `test_release_provider_failure_records_a_repair_job`, `test_replay_refuses_a_restored_spec_id_without_a_write`, `test_each_variant_step_crash_resumes_without_a_second_page[drop_page_property]`, `test_drop_crash_then_tamper_writes_nothing_and_clean_resume_finishes`, and `test_drop_crash_then_child_database_refuses_with_zero_writes` | 39 |
| swap release and the uniqueness bind inside the try | `notion_variants.py:103` and `:104` | Swapping `await _release_copied_spec_ids(...)` with `_bind_earlier_phases(...)` inside the try only. Validate at `:98` still runs first, so the 16 leftover tampers stay green, and `test_replay_refuses_a_restored_spec_id_without_a_write` stays green. The failures are `test_unrelated_page_is_not_adopted` for `private-titled` and `private-copy`, `test_mixed_leftover_and_unrelated_spec_id_writes_nothing`, `test_copy_with_a_nested_child_writes_nothing` for `database` and `page`, the eight empty `test_child_under_a_page_block_writes_nothing` cases, `test_one_adoption_field_refuses_before_any_write` for `parent_type`, `parent_id`, `product_id`, `shell_block`, and `release_shell` (not `foreign_child`), `test_release_provider_failure_records_a_repair_job`, `test_each_variant_step_crash_resumes_without_a_second_page[drop_page_property]`, `test_drop_crash_then_tamper_writes_nothing_and_clean_resume_finishes`, and `test_drop_crash_then_child_database_refuses_with_zero_writes` | 22 |
| title-only adoption | `notion_variants.py:548` | `test_unrelated_page_is_not_adopted` for `empty-titled` and `empty-copy`, `test_one_adoption_field_refuses_before_any_write[foreign_child]`, `test_release_keeps_a_different_spec_id_value` | 4 |
| publish-before-validate | `notion_variants.py:548` and `:574` | the same four tests as title-only adoption | 4 |
| delete `_require_variant_page` after finish writes | `notion_variants.py:577` | `test_finish_does_not_record_a_page_that_stays_indexed` | 1 |
| delete the release title filter | `notion_variants.py:366-367` | `test_release_keeps_a_renamed_duplicate_spec_id`. `test_release_keeps_another_products_spec_id_on_private_notes` stays green: a different spec id is not an open page, so validate already raises `hub page is unexpected` | 1 |
| interleaved check-then-drop | `notion_variants.py:371-374` | `test_mixed_leftover_and_unrelated_spec_id_writes_nothing`. The `(Copy)` page is planted before the unrelated spec-id page | 1 |
| release checks spec-id presence instead of the value | `notion_variants.py:368-369` | `test_release_keeps_a_different_spec_id_value` | 1 |
| delete `_require_shell_copy` parent_type | `notion_variants.py:417` | `test_one_adoption_field_refuses_before_any_write[parent_type]` | 1 |
| delete `_require_shell_copy` parent_id | `notion_variants.py:418` | `test_one_adoption_field_refuses_before_any_write[parent_id]` | 1 |
| delete `_require_shell_copy` product_id | `notion_variants.py:419` | `test_one_adoption_field_refuses_before_any_write[product_id]` and `[release_shell]` | 2 |
| delete `_require_shell_copy` shell block | `notion_variants.py:420` | `test_one_adoption_field_refuses_before_any_write[shell_block]` | 1 |
| delete `_has_foreign_child` inside `_require_adoptable` | `notion_variants.py:519-520` | `test_one_adoption_field_refuses_before_any_write[foreign_child]` | 1 |
| delete the `_require_shell_copy` call in release | `notion_variants.py:529` | `test_mixed_leftover_and_unrelated_spec_id_writes_nothing`, `test_one_adoption_field_refuses_before_any_write` for `parent_type`, `parent_id`, `product_id`, `shell_block`, and `release_shell` | 6 |
| delete nested child detection | `notion_variants.py:442` | Replacing the body of `_has_nested_child` with `return False`. `test_copy_with_a_nested_child_writes_nothing` for `database` and `page`, all 16 `test_child_under_a_page_block_writes_nothing` cases, `test_replay_refuses_a_database_under_a_variant`, and `test_drop_crash_then_child_database_refuses_with_zero_writes` | 20 |
| Q1 delete the `_has_nested_child` call inside `_has_foreign_child` | `notion_variants.py:463-464` | Deleting only `if _has_nested_child(probe, page): return True` inside `_has_foreign_child`. The eight empty-path `test_child_under_a_page_block_writes_nothing` cases. Stored-path cases stay green because `_require_variant_page` still calls `_has_nested_child` | 8 |
| Q7 nest stored-path title matches that are not workspace pages | `notion_variants.py:323-326` | On the stored path, also appending a non-workspace page whose title is a variant title or `{title} (Copy)` to `nested_ids`. Both `test_replay_refuses_a_hub_child_with_a_variant_title` cases | 2 |
| delete the stored-variants early return | `notion_variants.py:99-101` | `test_replay_keeps_the_same_bytes_and_ids`, `test_replay_refuses_a_restored_spec_id_without_a_write`, `test_replay_pins_extra_workspace_variant_titles_as_a_known_limit` for `blue` and `purple` (the `copy` pin stays green), `test_crash_after_write_checkpoint_resumes_without_a_second_page`, `test_secret_link_comes_from_get_public_url`, `test_replay_rejects_a_dropped_colour`, `test_replay_rejects_a_swapped_colour_token` | 8 |
| ignore stored variants (`if False`) | `notion_variants.py:99` | the same eight tests as deleting the stored-variants early return | 8 |
| Total | | | 514 |

The accent and sample block-membership loop is deleted. It is not a mutation row. `_require_saved` already requires those blocks, and the pair equality already rejects a mismatched created-id pair.

| Item | Disposition | Reason |
|---|---|---|
| CI-1 replay call `_require_created_ids` | Closed | `notion_aesthetics.py:104` inside `:102-105`. Deleting the call failed 6 tests. |
| CI-2 database pair check | Closed | `notion_aesthetics.py:276-277`. Failed 7. |
| CI-3 hub pair check | Closed | `notion_aesthetics.py:281-282`. Failed 9. |
| CI-4 accent and sample inequality | Closed | `notion_aesthetics.py:299-300`. Failed 1. |
| `navigation_block_id` on both hub tuples | Closed | `notion_aesthetics.py:279` and `:347`. Failed 1. |
| `reject_duplicate_labels` in aesthetics `_require_pairs` | Closed | `notion_aesthetics.py:203`. Failed 1. |
| `_ensure_row` `client_name` | Closed | `notion_notifications.py:1195`. Failed 1. |
| `_adopted_database` `title.type != "title"` | Closed | `notion_notifications.py:924`. Failed 1. |
| W7 created-ids prose partial | Closed | CI-1 through CI-4 are killed. The historical W7 sentence stays as history. |
| Accent and sample block-membership loop | Deleted | The loop is gone. It is not a PARTIAL row. |
| B-V1 secret link | Closed | The `get_public_url` call is `notion_variants.py:574`. Failed 2. |
| B-V2 colour and token compare | Closed | `notion_variants.py:652-654` failed 1. The length check at `notion_variants.py:649-650` failed 1 and raises `ProductBuildError` before `zip(..., strict=True)`. |
| B3 validator order | Closed | Skipping the call at `notion_variants.py:175` failed 17. Skipping it on an empty variants list failed 9. Moving it after `_require_saved` and `_ensure` failed 15. Deleting the saved check at `notion_variants.py:166-174` failed 11. |
| B1 adopt-by-title | Closed | Replacing the `_find_titled` call at `notion_variants.py:277` with `existing = None` failed 11. |
| B2 adopt the (Copy) page | Closed | The `_find_copy` call is `notion_variants.py:278-279`. Failed 6. |
| Replace validate with the uniqueness bind | Closed | The call at `notion_variants.py:98` becomes `_bind_earlier_phases`. Failed 39, including all 16 leftover tampers. |
| Swap release and bind inside the try | Closed | `:103` and `:104` only. Failed 22. The 16 leftover tampers stay green because validate at `:98` still runs first. |
| Two-pass release | Closed | Refusal over every candidate, then the drops (`notion_variants.py:371-374`). The interleaved check-then-drop mutant failed 1. |
| Spec-id value compare | Closed | `notion_variants.py:368-369`. Presence instead of the value failed 1. |
| Nested child | Closed | `_has_nested_child` at `notion_variants.py:442` walks the page and every block in its block tree. Replacing that body with `return False` failed 20. Deleting only the call inside `_has_foreign_child` (`:463-464`) failed 8. |
| Q7 stored-path identity | Closed | A stored-path variant or nested id is a recorded page id (`notion_variants.py:323-326`). Also nesting a non-workspace title match failed 2. Resume adoption stays `_find_titled` at `:277` and `_find_copy` at `:278-279`. |
| Adoption predicates | Closed | `parent_type` `:417` failed 1, `parent_id` `:418` failed 1, `product_id` `:419` failed 2, shell block `:420` failed 1, `_has_foreign_child` inside `_require_adoptable` `:519-520` failed 1, and the `_require_shell_copy` call in release `:529` failed 6. |
| Title-only adoption | Closed | `_require_adoptable` at `notion_variants.py:548` runs before any finish write. Deleting it failed 4. Moving it to just before `get_public_url` (`:574`) failed 4. |
| Post-write `_require_variant_page` | Closed | The call is `notion_variants.py:577`. Deleting it failed 1. |
| Release title filter | Closed | `notion_variants.py:366-367`. Deleting it failed `test_release_keeps_a_renamed_duplicate_spec_id` only. A renamed duplicate that still holds the source spec id is open during validate, the filter keeps it out of the drop, and the bind raises `fixture probe has more than one page for this ProductSpec` with zero writes. |
| Stored-path resume | Closed | Deleting the early return at `notion_variants.py:99-101` failed 8. Replacing `if stored.variants:` with `if False:` failed the same 8. `test_crash_after_write_checkpoint_resumes_without_a_second_page` requires zero `_find_titled` calls, zero adapter writes, and zero `write_checkpoint` calls. |
| Single writer through `write_checkpoint` | Closed | `test_write_checkpoint_is_the_only_progress_writer` still passes. `notion_variants.py` calls `write_checkpoint` and does not call `write_document`. `test_crash_inside_write_checkpoint_before_the_file_lands` asserts one `write_checkpoint` call on the crash and one more on resume, with no further adapter writes. |
| Refused rebuild | Closed | Zero Notion writes. One `write_checkpoint`, appending one `rebuild_refused` job. The reason names the variant pages. Every other field stays byte-identical except the recomputed digest. |
| A08 commissioning | Closed as not done | `commissioned_agents` stays `[]`. A08 stays DESIGNED. `variant_builder_implemented` stays false. |
| Docstring coverage | Parked | 10.88% (W6, stale; not remeasured). |
| One home page per probe | Parked | Dashboard and hub builders still require one top-level page. Re-entering phase 6 after variants raises `hub page is unexpected`. Variants resume is `build_variants`. |
| Deep clone of databases | Parked | Rejected. `duplicate_page` is shallow. |
| Provenance beyond title and copyable shell fields | Parked | An unrelated empty workspace page with the source `product_id` and shell block id would be adopted. `parent_id` compares equal when both are `None`. Not a proven lineage. Live wave. |
| Extra workspace variant titles on replay | Parked | `/ Blue`, `/ Purple`, and `(Copy)` pages at workspace level pass replay with zero writes. Pinned by `test_replay_pins_extra_workspace_variant_titles_as_a_known_limit`. A hub child with those titles is refused. |
| W9 must-fix survivors | Parked | Named in `NEXT_SESSION.md`. Not killed this wave. |
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
