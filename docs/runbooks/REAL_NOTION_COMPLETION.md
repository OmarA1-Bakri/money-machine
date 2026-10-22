# Private Notion build: covers, navigation and observed counts

This describes code behavior, not a completed or visually approved live product.
The production Notification create remains UNKNOWN. All related provider writes,
retries, publication and spend stay held. Do not run `--execute` to test this change.

## Cover input

The existing private builder now requires one explicit, distinct stable HTTPS
image URL for each `Forest`, `Sand` and `Slate` variant. The existing CLI accepts
`--covers-json <path>` with those three keys and URL string values. It validates
this input before reading credentials or opening a database. Dry-run preflight
continues to perform no effects and does not require cover inputs.

Supply approved, palette-matched, publicly accessible PNG/JPEG/WebP assets.
URL syntax checks do not prove image availability, licensing, colour fidelity,
permanence or visual quality. These still require source and visual review.
Fixture palette URIs, signed/query URLs, credentials in URLs, IP hosts and
non-HTTPS links are refused. No asset host, upload service or dependency is added.
External resources in page blocks remain forbidden; the exception applies only
to the page's cover field, using the documented Notion external-file shape.
See [Notion file objects](https://developers.notion.com/reference/file-object)
and [page cover metadata](https://developers.notion.com/reference/page).

The three approved cover URLs are not available in the current cloud handoff.
No production cover, palette consistency or visual acceptance is claimed.

## Readback and replay

Variant dashboards and hubs receive their own variant's cover. Every page's
emoji icon is checked on readback. Every hub links to its dashboard; its guides
link to both the hub and dashboard. Readback validates exact backlink targets and
rejects duplicate links. IDs always pass the existing private-root ancestry guard.

Logical effect keys, reservations, durable write guard and UNKNOWN reconciliation
are unchanged. A previously confirmed page with a missing/different cover or
backlink is refused; this patch does not silently replace or rewrite it. A later
authorized targeted repair needs its own reconciled existing-control operation.
Changing cover inputs cannot turn an old page into a new create attempt.

## Observed counts

Each variant enumerates the complete paginated static child-page/database tree
through scoped provider reads. Cycles, repeated identities, bad ancestry,
uninspected nested content or omitted planned pages/databases stop verification.
The bounded builder currently renders static page content directly; it refuses
to claim a complete count when unfamiliar nested block content hides children.
Data-source rows and `link_to_page` references do not count as static pages.

The manifest persists sorted observed page/database IDs and distinct counts:

- `regular_page_count`: observed static pages, including the variant dashboard.
- `database_container_count`: canonical and linked database containers.
- `page_count_including_databases`: the sum of those two observed counts.
- `content_page_count_including_source_databases`: static pages plus canonical
  source databases; linked containers cannot inflate the ProductSpec page target.

The synthetic fixture has 19 static pages, 7 canonical databases and 16 linked
containers: 42 total objects and 26 content pages including source databases.
Those are test observations, not claims about the held Forest product. Extra
static pages change the observed count; fixed build-plan constants do not.
The manifest continues to mark publication private and native visual review pending.

## Prepared one-send recovery guard (no execution authority)

The guard is code preparation for a possible operator-approved Notification
replacement. No approval issuer, production configuration, execution command,
replacement resource or canonical-binding override is provided. Existing UNKNOWN
holds remain in force. The original ProductSpec/schema and exact request package
are still required; synthetic tests cannot supply them.

`NotificationReplacementApproval` binds the repair/original jobs, original
UNKNOWN attempt/key, workflow/product/run, exact parent, spec/decision/request
hashes, operator approval reference and deadline. Its serialized value must match
`BuildRepairJob.input.notification_recovery.approval` in the canonical database.
An arbitrary caller-supplied envelope without that persisted match is refused.
Admission of authentic operator approval remains an existing-owner responsibility;
this model does not authenticate a human or register an identity with thredOS.

The body digest is SHA-256 of UTF-8 JSON with sorted keys, separators `,`/`:`,
`ensure_ascii=False`, and NaN disallowed. It covers the actual API body, while
method/path are separately fixed to `POST databases`. It is a canonical JSON body
digest, not a logical-key hash or a claim about byte ordering in SDK transport.

A future approved caller uses `SqlDraftEffects.bind_notification_recovery` with
its actual runner context, canonical session factory, scoped authority, injected
SDK and already persisted approval. The binding verifies the active A07
BuildRepairJob/run, attempt, lease, prompt lineage and exact stored approval,
then returns effects and an adapter with both existing callbacks installed.
It performs no provider call or approval admission. Use the approval's
deterministic operation key. The guard verifies the original UNKNOWN and
active repair lease, then commits `send_consumed_at` in existing repair metadata
before transport. Attempts and receipts cite the existing run; its definition and
prompt foreign keys retain ordinary lineage checks. No telemetry service starts.

Recovery operation keys require this request guard even if both metadata and hook
are absent. The one-use permit is bound to the current task and operation, checks
approval/deadline again at the final lease guard, and is cleared on exit. Validation
and transport use independent copies so callbacks cannot change approved bytes.

Consumption survives provider rejection, lost response and a crash before send.
Even an `ABSENT` result cannot authorize another send for this grant; unrelated
ordinary effects retain their existing retry rules. A consumed grant can therefore
produce zero requests. Do not mint another approval/key automatically. A positive
read can still reconcile the new effect without sending again.

The guard never completes a repair/job, chooses a canonical replacement, closes
an incident, or updates the original UNKNOWN. Those remain separate verified and
explicitly authorized steps. Existing provider visibility, source, identity and
quality requirements also remain in force.

## Durable A07 execution lifecycle (code preparation)

The existing observer can persist a truthful `RUNNING` row in `agent_runs`, with
the original job attempt, lease owner and registered local definition/prompt
lineage. It has no terminal output/error/completion time. The owning unit of work
commits this checkpoint before execution. The terminal result updates that same
row under a lock; mismatched identity and a second terminal write are refused.
`AgentResult` still accepts terminal outcomes only. This is not thredOS registration.

`AgentRunner.execute` requires A07 callers to supply the actual `lease_owner` and
a dedicated job session with implicit transactions. Explicit/nested transactions
are refused before any checkpoint commit or agent invocation. A07 start/terminal
checkpoints commit that owning UoW; callers must not mix unrelated changes into it.
Existing non-A07 transaction behavior is unchanged. The fixture repair consumer
uses this same observer lifecycle and commits its active run before fixture work.

An unresolved active run blocks restart/replay and concurrent second starts.
Cancellation/process interruption leaves `RUNNING`, never a fabricated success or
automatic failure/retry. A separately reconciled terminal result is needed before
another execution. Effects with supplied run lineage require its persisted owner
and attempt to match the current job/worker, so a replacement lease cannot borrow
the previous unresolved run. Historical accepted-effect recording retains the
existing scoped identity path. No UNKNOWN effect is resolved by terminal tracing.

Migration `c3d4e5f6a7b8` extends the existing table, preserves old terminal records,
enforces active/terminal shapes and allows at most one active run per job. Downgrade
refuses unresolved active rows rather than deleting or fabricating execution history.

This closes one code-level lifecycle gap. The default versioned PromptStore does
not currently contain an A07 prompt at `prompts/agents/A07/v1.md`; the existing
fixture library has a separate registered source. Runner lifecycle tests use a
hash-verified synthetic prompt in a temporary fixture directory and simulation
mode. They do not establish commissioned/live A07 execution. Canonical production
ledger/runtime binding, verified recovered source/request bytes, authenticated
approval admission, a finite recovery entrypoint, authorized deployment and actual
thredOS registration remain prerequisites. No execution command is supplied here.

## Runner-to-guard binding (code preparation)

The runner forwards its actual worker lease owner through the existing context.
The binding refuses context drift, expired authority and stored approval mismatch
before returning an adapter. Approval is checked again at the actual send, so
revoking it after binding still prevents transport. This factory neither claims a
lease nor reserves an effect. Caller-provided identity cannot replace persisted
job/run/prompt checks.

Fixture tests use the real runner and observer with a temporary hash-verified
synthetic prompt and mock SDK transport. Success replay performs one POST; a lost
response leaves the new effect UNKNOWN and the next runner execution cannot send
again. These tests preserve the original UNKNOWN, open incident and fourteen
confirmed fixture effects. They do not establish a live production entrypoint.

Canonical approval admission, a finite invocation using this binding, source and
ledger verification, actual registered identity/prompt and authorized deployment
remain required. No live approval or production action is provided by this code.
