# Session 07 evidence record

P0 adds three control commands and a history replay. It marks nothing done. The checked-in state stays revision 64 with all twelve Session 07 evidence keys false.

Q4 (closure sets both `head_sha` and `evidence_closure_commit_sha` to the new commit C) and Q7 (mistakes are undone only by `revoke-evidence`) are built as specified. Merge waits for Omar's G0, which covers both. Exit 78 stays HELD. Session 08 is not activated.

`validate_activation_transition`, `validate_completion_transition`, and `_require_completed_session_evidence` are unchanged. `src/money_machine/control/state.py` lines 1–598, 399–468, and 471–598 stay byte-identical. New code is after line 598 and in `s07_evidence.py`.

## Commands

`money-machine-control record-evidence`, `record-closure`, and `revoke-evidence` each take `--state` and `--candidate`. A refusal exits 2, writes nothing, and leaves no lock or temporary file.

They run only where the state file's `repo_root` is Omar's WSL checkout (`/mnt/d/Money Machine`), by Omar or through machine-targeted Shell with his approval. Tests use a temporary clone whose first commit rewrites `repo_root` and `branch`. That rewrite is the history's start, never a later step. The real checkout's `repo_root` is never rewritten.

HEAD must be attached to `build/full-automation` with a clean tracked tree. Each record pull request is one squash-merged commit that changes the state by exactly one validated step.

## Allowed proof

Each true non-closure key cites `docs/evidence/s07/<key>/manifest.json`. The manifest blob is `sha256(git cat-file blob <merge_commit>:<path>)`. `merge_commit` must descend from `b782751fdb1b255c436ff7f6fa655e6d783b1e8c` and be an ancestor of HEAD. `README.md` and any path outside that key's prefix are refused. This pull request does not add real manifests.

| Key | Required kinds |
| --- | --- |
| 1–5 product builder, shared databases, home dashboard, notification dashboard, identity hubs | `p2_build_exec` + `p4_qa` |
| 6 `variant_builder_implemented` | `p3_variants_exec` + `p4_qa` |
| 7 `product_qa_implemented` | `p4_qa` + `p4_repair_rerun` |
| 8 `product_fact_ledger_persisted` | `p5_ledger` (`qa_record_sha256` equals the cited `p4_qa` artifact) |
| 9 `build_workflow_linked` | `p6_test_record` |
| 10 `product_build_tests_pass` | `p8a_ci_record` |
| 11 `control_files_and_checkpoint_current` | `p8b_control_record` (sha256 of the four narrative control files). Only after keys 1–10 are already true. |

Run evidence requires `mode == "execute"`, `redaction_self_check == "PASS"`, the sandbox space and parent, and `qa_verdict == "PASS"` for `p4_qa`.

## Closure and revoke

Closure requires keys 1–11 true and cited, the closure key still false, and the pre-transition pins `b782751…` / `0f94d585…`. Commit C's state equals that pre-transition document and does not name C. Both commit fields become C. `0f94d585` and `b782751` are refused. `docs/evidence/s07/commissioning/g7-record.json` at C must match `commissioning_state` for A07–A09 in `config/agents.yaml`, and each locator must resolve at C.

Revoke flips cited keys true to false, removes those citations, and appends `{key, reason, revoked_at, revoked_in_rev}` to `evidence_citations["7_revoked"]`. Record and closure leave that list byte-identical. Revoke is refused once the closure key is true.

## Replay

`replay_state_history` walks `git log --first-parent` from the hardcoded anchor `00b952a83bffcec8d442468223d64dd9b2d3e6df`. The CLI never takes an anchor from argv, the environment, or config. A shallow repository, an unresolvable anchor, or an anchor that is not a first-parent ancestor of HEAD fails closed. Only in-process `_apply_activation_transition`, `_apply_completion_transition`, and `replay_state_history` may inject an anchor.

The window runs through the first first-parent state commit whose `current_session` is not 7. That commit must be a valid activation into 8. While the window is open it runs to HEAD, and the worktree state must equal HEAD. After it closes, later state commits are not replayed. The worktree rule does not apply to a dirty tree on an activation whose `next_session` is not 8 or 9.

The pin helper, activation into 8 (open) and 9 (closed), and completion of session 8 call the replay. Activations 1–7 and completions 0–7 do not.

## WSL record flow

On `/mnt/d/Money Machine`: fetch, switch to `build/full-automation`, require a clean tracked tree, no unpushed commits, and a non-shallow clone, then fast-forward only. Write the candidate outside the repo and run the command. Carry the state change onto `s07/<step>`, commit only the state file, and squash-merge. Fast-forward the checkout back. Do not reset, rebase, or force-push.

## Not in this pull request

The browser guard in `s07_navigation_guard.py` is the testable rule for later navigation wiring. `TranslatingBrowserSession.navigate` is unchanged; that wiring is P1c. The publish-gate file and the per-run lock are the contracts for tests 45 and 46. "Omar notified" means `omar_notified_at` is a non-empty field, not a verified delivery. Carry items 3 and 4 (a pre-publish disk record, and posting the deadline in the go-record plus the coding-team room) are not implemented here.

## Mutant table

| Test | Mutant that dies |
| --- | --- |
| 1 | Accept an incomplete session |
| 2 | Change any fixture field outside the command's mutable set |
| 3 | `record-evidence` flips true to false |
| 4 | Flip a key with no citation |
| 5 | Cite a key that stays false |
| 6 | Top-level citation key other than `7` / `7_revoked`, or a key outside the session 07 contract |
| 7 | Remove `evidence_citations`, or create `7_revoked` on the first record |
| 8 | Revision +0 or +2, or an unchanged `updated_at`, on all three commands |
| 9 | Non-bool evidence, or an extra or missing key |
| 10 | Session 9 raises `ControlStateError`, not `KeyError` |
| 11 | `README.md` accepted as proof |
| 12 | Manifest `key` does not match the cited key |
| 13 | Manifest `session` is not 7 |
| 14 | `merge_commit` does not descend from `b782751` |
| 15 | Evidence exists only at HEAD, not at `merge_commit` |
| 16 | Hash the worktree, or skip the manifest blob hash |
| 17 | Allow a kind outside `S07_EVIDENCE_KINDS` |
| 18 | Accept `qa_verdict` other than PASS, or a mode other than `execute` |
| 19 | Record key 11 before keys 1–10 are true |
| 20 | Close with a non-closure key false or uncited |
| 21 | C's state is not the pre-transition document |
| 22 | C names its own object id |
| 23 | Closure commit is `0f94d585` |
| 24 | Closure commit is `b782751` |
| 25 | `b782751` is not an ancestor of C |
| 26 | HEAD is not C, or the tracked tree is dirty |
| 27 | Only one of the two commit fields equals C |
| 28 | `head_sha` moves to `0f94d585` |
| 29 | `evidence_closure_commit_sha` moves to `b782751` |
| 30 / 42 | G7 record missing, agents.yaml state differs, or a locator does not resolve |
| 31 | `record-evidence` flips the closure key |
| 32 | Revoke an uncited key, revoke after closure, empty reason, revoke while the closure key stays true, move `head_sha`, or close twice |
| 33 | Hand-edited state, hand revert, two steps in one commit, revision gap, dirty worktree while the window is open, non-squash merge, anchor state differs from the fixture |
| 34 | Skip citation re-validation; skip replay on activation into 8; skip a missing or shallow anchor (real CLI, tests 38–39); drop `--first-parent` |
| 35 | Pin helper uses `any()`, drops the citation lookup, or returns before the sha pins |
| 36 | Activation into 8 without a closure is refused; a valid closure then activation is accepted; session 08 completion still uses the unchanged completion validator |
| 37 | #66 mutants re-proved on the frozen rev-64 fixture from `00b952a` |
| 38 | Real CLI: shallow `file://` clone, stderr names shallow, exit 2, zero writes |
| 39 | Real CLI: anchor does not resolve, including when `MM_REPLAY_ANCHOR` is set |
| 40 | Replay is not called when `next_session` is 1 or 2 |
| 41 | Revoke key 3, re-record it, close; `7_revoked` stays byte-identical. Editing it on a later record is refused |
| 43 | Candidates pass their own validators first. A hand-made session 08 activation is refused by completion and by activation into 9, with a replay message. `_apply_completion_transition` accepts an injected anchor |
| 44 | Open window runs to HEAD. A valid activation ends the window. An invalid window end fails closed |
| 45 | Missing, stale, past, or too-far deadline; mode, symlink, missing field, empty `omar_notified_at`, or wrong owner. Zero browser writes. A valid 0600 file allows one write |
| 46 | One lock per run id. A live holder returns false. An old lock without `exec.json` is refused. A completed exec allows a new start |
| 47 | Foreign space, broken parent, redirect, unlisted URL, signed-out sandbox, or a signed-in anonymous session. `evilnotion.site` is refused. A listed `notion.site` URL is allowed |

`evidence_citations cannot be created a second time` is unreachable: a field cannot be both newly added and already present. The reachable refusal is `evidence_citations keys cannot be added or removed`. Replay trigger `current_session == 7` versus `next_session == 8` is equivalent by the activation validator and is parked.
