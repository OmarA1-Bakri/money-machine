# Session 09 Prompt Integrity Review

**Date:** 2026-10-16
**Prompt:** `prompts/implementation/12_SESSION_09_ETSY_DRAFT_PUBLISH_AND_PREFLIGHT.md`
**Verified SHA-256:** `eab1e4a5ae05008e06607526a1bf45b0fb35850a5bbf82e4002bd94954f58936`
**Base:** `edc0632fb43777d834053d5dbfe42f31f3478ab7` (`#105` merged). Session 09 is not activated. `current_session` stays 7. `state_revision` stays 64. Exit 78 stays HELD.

The prompt file is not amended. This record is the corrective addendum. Reviews: [S09 fidelity review](https://cursor.com/agents/bc-2ca5fcf5-b945-5812-b23d-b35618cb450c), [S09 safety review](https://cursor.com/agents/bc-8e90835d-1418-579d-a0b2-d805c396551e), [S09 gameability review](https://cursor.com/agents/bc-12603da3-2438-52ab-9ef0-91bad5dcc314). All three returned CONDITIONAL APPROVE.

## 1. Prompt authenticity

**Status:** VERIFIED

The extracted file's SHA-256 equals the workbook appendix entry for `12_SESSION_09_ETSY_DRAFT_PUBLISH_AND_PREFLIGHT.md`. The required exit string in the file is `SESSION_09_ETSY_PUBLISHING_COMPLETE`.

## 2. Three-dimensional review

### Fidelity

**Verdict:** CONDITIONAL APPROVE.

**F-01 [CRITICAL] — Session 09 would close while Session 08 is inactive.** The prompt executes and emits its exit code without requiring `SESSION_08_MERCHANDISING_AND_ASSETS_COMPLETE`. D-0010 separates activation from completion. D-0032 keeps `current_session` at 7 and names Session 08 as next. **Amendment:** This wave does not activate Session 09, does not emit the exit string, and does not edit `IMPLEMENTATION_STATE.json`.

**F-02 [CRITICAL] — Commissioning A12 and A13 after tests.** Both stay `DESIGNED`. D-0028 requires an operator decision and a simulation run through analytics before `COMMISSIONED`. The worker claims `TESTED` or `COMMISSIONED` jobs. **Deferral:** commissioning stays with the operator under D-0028. This wave does not edit `config/agents.yaml`.

**F-03 [CRITICAL] — Action 10's label chain is not the job graph.** D-0029 and D-0033 keep those strings as labels. D-0034 already creates one `DraftListingJob` per product from `ASSETS_COMPLETED`. **Amendment:** Do not add job types, do not edit `config/workflows.yaml`, and do not edit `draft_listing_successor.py` or `event_dispatcher.py`. **Deferral:** a graph proof of the existing jobs waits for a later Session 09 wave. Owner: Session 09 wave 2.

**F-04 [HIGH] — `auto_publish: true` is not sufficient to publish.** D-0020 also requires `external_mutations_enabled` and `publishing_ramp.publishing_enabled`. The committed ramp has `publishing_enabled: false`. **Amendment:** Committed flags stay fail-closed. A later pure function may publish on an in-memory override only after preflight `PASS` and an open ramp, against an adapter double. **Deferral:** that function is not this wave. Owner: Session 09 wave 2.

**F-05 [HIGH] — Action 1 would read secrets and rewrite channel rows.** D-0016 forbids a capability check from reading tokens, cookies, or provider payloads. Composio is absent. The Etsy browser adapter is uncommissioned. **Deferral:** no matrix or compatibility edit this wave. Owner: a later Session 09 inspect slice that cites the pinned public OpenAPI text already named by `draft_client.py` and does not read `.env`, cookies, or `runtime/browser-profiles/`.

**F-06 [HIGH] — Preflight outcomes.** `PreflightResult.outcome` admits only `PASS` and `FAIL`. `FAIL` requires a failed check and a repair job. `BLOCKED` is a job status, not a third outcome. A dummy repair job so the next call returns `PASS` is forbidden. **Amendment:** This wave's preflight slice uses `PASS` and `FAIL` for repairable rows. An unsupported claim is a blocked decision with no `PreflightResult` and no repair job.

**F-07 [HIGH] — Calendar `published_at + 30 days` contradicts D-0014.** Maturity is thirty accumulated live days. Paused time does not count. **Deferral:** no maturity clock and no metrics schedule this wave. Owner: Session 10 for metrics, and a later Session 09 post-publish slice that follows D-0014.

**F-08 [HIGH] — One undifferentiated idempotency key, and a timeout that retries blindly.** D-0025: reconciliation is a read. `UNKNOWN` does not repeat the mutation. **Amendment:** This wave's receipt slice stores operation, target, pre-state, expected post-state, provider id, response hash, idempotency key, and `effect_state`. A timeout reads the fixture first. `UNKNOWN` does not create again.

**F-09 [MEDIUM] — Quantity and description.** D-0022 requires quantity 999 and eight description sections. **Amendment:** The preflight slice refuses quantity other than 999. Eight description sections stay on the existing `ListingPackage` rules and are not re-specified here.

**F-10 [MEDIUM] — Deactivate and metrics do not belong on the publishing update path.** A14 owns metrics. A15 decides cull. A13 deactivates only after `LISTING_CULL_REQUESTED`. **Deferral:** Owner: Session 10 and Session 11, plus an operator-authorized adapter session.

**F-11 [MEDIUM] — Ramp file has no shop-age field.** Unknown YAML keys fail closed. The file's initial cap is 2, inside the 2–3 launch band, hard cap 15, rolling window 7, reconciled-only. **Amendment:** The ramp slice reads those fields as arguments. It does not add `shop_age` and does not set `publishing_enabled: true`.

### Safety and executability

**Verdict:** CONDITIONAL APPROVE.

**S-01 [CRITICAL] — Do not close Session 09 on this tree.** Same resolution as F-01. No push to `build/full-automation`. No merge. PRs #63 and #68 stay untouched. #105 is already merged as `edc0632` and its files stay untouched.

**S-02 [HIGH] — Action 2 must not grow the live allowlist.** Publish, activate, deactivate, file replace, stats, and messages stay unwired. Metrics stay with Session 10. Messages stay with A16. **Deferral:** live transports. Owner: an operator-authorized adapter session after D-0028.

**S-03 [HIGH] — Receipts must not store raw bodies or screenshots.** **Amendment:** Redacted fields only. Reconciliation uses a fixture read.

**S-04 [HIGH] — A13 must not enqueue `DRAFT_CREATED` or call upload and publish tools in this wave.** **Deferral:** the extra fixture-draft case. Owner: Session 09 wave 2. It must stay on `FixtureTransport` and the current allowlist.

**S-05 [HIGH] — Action 5, narrowed, is this wave.** In-memory checklist. `PASS` and `FAIL` only. Repairs are data on the result, not live jobs.

**S-06 [HIGH] — Action 6, narrowed, is this wave.** Pure predicate. Scheduler file stays unchanged. Exit 78 stays HELD.

**S-07 [CRITICAL] — Action 7 does not flip committed flags.** **Deferral:** live enablement. Owner: an operator authority record.

**S-08 [CRITICAL] — No checkout payment client.** **Deferral:** the payment transport. Owner: an operator spend decision after commissioning. Tests must not open a socket.

**S-09 [HIGH] — No live file replace, price repair, or deactivation.** **Deferral:** Owner: the operator-authorized adapter session.

**S-10 [HIGH] — Do not add a parallel job name that can publish in draft mode.** Same resolution as F-03.

**S-11 [CRITICAL] — A present token is not authority for a live draft smoke.** **Amendment:** This wave's tests read no provider credential and open no Etsy socket. A skip is not a pass. **Deferral:** any live draft smoke. Owner: an operator command that passes an explicit live-draft flag with effect mode `draft`, `auto_publish` false, and publish authority false.

**S-12 [CRITICAL] — Leave `commissioning_state: DESIGNED`.** Same resolution as F-02.

**S-13 [HIGH] — Workers do not edit `docs/control/`.** The integrator owns this addendum and the log line. The canonical commit subject waits for a real Session 09 activation. Level 1 does not invent the three named reviewer roles.

**S-14 [MEDIUM] — Three lanes, not the whole prompt.** See the corrective addendum.

### Gameability

**Verdict:** CONDITIONAL APPROVE.

**G-01 through G-06 [CRITICAL] — Live publish, approval deletion, checkout, credential smoke, YAML commissioning, and self-granted authority.** Resolved by the amendments and deferrals in F-02, F-04, S-07, S-08, S-11, and S-12. This wave does not add `publish_if_live`, a payment port, a live smoke, or a commissioning flip. Committed autonomy and ramp flags stay as they are. A test that would only pass by widening them is out of scope until wave 2.

**G-07 [HIGH] — The exit string is not evidence.** **Amendment:** Do not write `SESSION_09_ETSY_PUBLISHING_COMPLETE` in this wave. **Deferral:** control-state evidence keys. Owner: Session 09 Level 3, after Session 08 is closed and an operator activates Session 09.

**G-08 [HIGH] — The commit subject alone is not the session.** **Deferral:** `feat(etsy): automate drafts preflight and publication` waits for Level 3. Owner: Session 09 exit.

**G-09 [HIGH] — Control files are not made current by a new heading.** This wave's log entry names the three slice files. It does not claim the session exit.

**G-10 [HIGH] — A fixture dict is not a draft package.** **Deferral:** `DraftListingJob` against an adapter double. Owner: Session 09 wave 2. That slice must not edit the successor or the dispatcher.

**G-11 [HIGH] — One shared `PASS` does not cover the checklist.** **Amendment:** The preflight slice gives quantity, tag count, image count, video presence, and the unsupported-claim block each their own test. The remaining checklist rows (links from PDF bytes, duplicate-as-template, indexing, nested variant, hero order, blank tag, sale price) stay for the next preflight slice. Owner: Session 09 preflight follow-up.

**G-12 [HIGH] — `count >= 2` is not the ramp.** **Amendment:** The ramp slice reads the cap, the window, reconciled-only counting, and `publishing_enabled` as inputs. Disabled waits at count 0. Count at the cap waits. Count one below the cap may publish. An unreconciled row does not count. The cap does not rise above 15. A caller-supplied initial cap of 3 changes the wait point. The committed file stays `publishing_enabled: false` and `initial_weekly_cap: 2`.

**G-13 [HIGH] — Two appended labels are not schedules.** **Deferral:** Owner: Session 10, under D-0014.

**G-14 [HIGH] — Deduping inside the test is not reconciliation.** **Amendment:** The receipt slice's tests assert create counts on a recording double. Same key, one create. Timeout plus a found listing, zero further creates. Timeout plus an empty read, one create. `UNKNOWN` does not create. A receipt without a provider id or a response hash fails. Raw body and screenshot fields are rejected.

**G-15 [HIGH] — A label list is not the graph.** Same deferral as F-03.

**G-16 [MEDIUM] — Local `updated: true` is not a file replace.** **Deferral:** Owner: the operator-authorized adapter session.

**G-17 [MEDIUM] — One no-op for three modes.** **Deferral:** Owner: Session 09 wave 2, with the in-memory live function. Simulation and draft publish counts stay zero in that slice.

**G-18 [MEDIUM] — Empty dicts for shop status, categories, video, metrics, and messages.** **Deferral:** Owner: the later adapter slice. Messages that the double marks unsupported stay `unsupported` with write count zero.

**G-19 [LOW] — Reviewer headings are not a review.** **Deferral:** Level 3. Owner: Session 09 exit.

## 3. Corrective addendum

1. Prove the prompt hash. It stays `eab1e4a5ae05008e06607526a1bf45b0fb35850a5bbf82e4002bd94954f58936`.
2. Session 09 stays inactive. `current_session` stays 7. `state_revision` stays 64. Exit 78 stays HELD. A12 and A13 stay `DESIGNED`. A10 and A11 stay `DESIGNED`.
3. Do not edit `IMPLEMENTATION_STATE.json`, `config/workflows.yaml`, `config/agents.yaml`, `config/publishing_ramp.yaml`, autonomy files, the scheduler, `draft_listing_successor.py`, or `event_dispatcher.py`.
4. Do not publish, spend, message customers, or call live Etsy, Notion, or S3. Tests open no socket and read no provider credential.
5. Open at most three lanes. Workers do not edit `docs/control/`.
6. Lane `cursor/s09-preflight-checks-7da5` owns only `src/money_machine/assets/etsy_preflight.py` and `tests/unit/assets/test_etsy_preflight.py`. In-memory checklist. `PASS` and `FAIL` for repairable rows. Unsupported claim is blocked with no repair job. Quantity 999, thirteen tags, ten images, and one video are the passing row. Each of those failures kills its own mutant.
7. Lane `cursor/s09-ramp-predicate-7da5` owns only `src/money_machine/assets/publishing_ramp_decision.py` and `tests/unit/assets/test_publishing_ramp_decision.py`. Pure predicate over the existing ramp fields. Disabled waits at count 0. No `shop_age` key. No scheduler edit.
8. Lane `cursor/s09-mutation-receipt-7da5` owns only `src/money_machine/assets/mutation_receipt.py` and `tests/unit/assets/test_mutation_receipt.py`. Redacted receipt and fixture reconciliation. `UNKNOWN` does not create again. No raw body and no screenshot.
9. Each lane is Level 1: failing test first, then the smallest implementation, then the focused file. `ruff format`, `ruff check`, and `pyright` on the touched files. One uniquely killing mutant row per new pin.
10. Sessions 10–15 do not start until this wave is green and each later session has its own prompt-integrity addendum.

## 4. Deferrals

**D-01 — Session 09 activation and the exit string.** Owner: the operator, after Session 08 is closed.

**D-02 — Commissioning A12 and A13.** Owner: the operator, citing D-0028.

**D-03 — Live transport, live draft smoke, checkout payment, file replace, and deactivation.** Owner: an operator authority record. Presence of a token is still a skip.

**D-04 — Job-graph proof, extra fixture draft, and the in-memory live publish function.** Owner: Session 09 wave 2. That wave still does not edit the successor, the dispatcher, or `workflows.yaml`.

**D-05 — Maturity clock and weekly metrics.** Owner: Session 10, under D-0014.

**D-06 — Remaining preflight checklist rows.** Owner: the next preflight slice.

**D-07 — Sessions 10–15.** Owner: each session's own prompt-integrity addendum after this wave.

## 5. What already holds

`PreflightResult` already admits only `PASS` and `FAIL`, and `FAIL` already requires a repair job. `PublishingRampConfig` already rejects an initial cap outside the launch band and a hard cap below that band. The committed ramp file is disabled, initial cap 2, hard cap 15, window 7, reconciled-only. `EffectReference` already rejects a confirmed effect with no provider id and an absent effect that names one. `DraftListingJob` already exists once per product from `ASSETS_COMPLETED`. The draft client allowlist does not publish.
