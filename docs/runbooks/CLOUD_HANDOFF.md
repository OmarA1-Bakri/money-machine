# Money Machine cloud handoff — 22 October 2026

Cloud coding is stopped at the user's request. No replacement execution
environment has been selected. This is a continuation index, not a product
completion, production execution, merge or deployment authorization.

## Verified application checkpoint

Repository: `OmarA1-Bakri/money-machine`; branch:
`codex/real-product-app-20261021`; draft [PR 127](https://github.com/OmarA1-Bakri/money-machine/pull/127)
targets `build/full-automation`. Application commit:
`d2beb5a884d35eb5d435fdf027755cdb09bfc84f`, tree
`d4b5c3bd0d1bc257463fe675c7298ad6747a4061`.
[CI 39841680372](https://github.com/OmarA1-Bakri/money-machine/actions/runs/39841680372)
was verified completed/success at handoff. Any later documentation-only commit
has separate check status; do not attribute this run to a different SHA.

The latest code projects the selected product's persisted A07 recovery run,
retained database/data-source IDs and exact correlated effect state into the
read-only summary and console. Agent success, effect confirmation, job status
and workflow completion remain distinct. Incidents supply a read-only next step.
Unrelated writes, conflicting database identity and malformed metadata cannot
earn confirmation. No retry button or mutation path was added.

Final local verification on those bytes: 38 Python projection/API checks,
72 frontend tests, Ruff, Pyright, frontend lint/typecheck and production build
passed. The earlier 97-test affected pass preceded the independently reviewed
correlation correction; the 38-check pass followed it. Actual built-console/API
acceptance used isolated synthetic SQL fixtures, the default A07 prompt, real
runner/observer and mock providers. Both outcomes passed desktop and mobile
NOW/Pipeline/Incidents navigation. SUCCESS/CONFIRMED retained one unresolved
operation; UNCERTAIN_EXTERNAL_EFFECT/UNKNOWN retained two. Resource IDs and next
steps were visible, with no browser console errors or outbound requests.
Temporary servers/databases were removed. This does not verify the live product.

## Resume only after a destination is selected

1. Read root `AGENTS.md` and `docs/DEVELOPMENT-GOVERNANCE.md`. Verify the branch,
   exact ancestry, clean/owned diff and remote PR state before making changes.
   Preserve existing history, ignored artifacts and user work. Leave the separately
   denied PR-description update alone unless specifically authorized.
2. Provision development dependencies from `uv.lock` and `pnpm-lock.yaml` using
   the existing repository setup. Follow the selected environment's PostgreSQL
   instructions; do not assume this cloud's processes, paths or caches transfer.
   Do not initialize a production ledger as part of development setup.
3. Relevant committed regressions are
   `tests/integration/test_operator_recovery_projection.py`,
   `tests/integration/test_notification_recovery_{guard,binding,invocation}.py`,
   `tests/e2e/test_operator_{api,artifacts,console}.py` and
   `apps/web/tests/product-proof.test.tsx`. With existing dependencies and a
   disposable test PostgreSQL available, the final narrow API check is:

   ```bash
   .venv/bin/pytest -q tests/integration/test_operator_recovery_projection.py tests/e2e/test_operator_api.py tests/e2e/test_operator_artifacts.py
   ```

   These test fixtures create/drop isolated test databases. They must never use
   a production admin URL. The existing frontend package scripts supply lint,
   typecheck, tests and build. Reuse exact green evidence when bytes are unchanged;
   do not rerun heavyweight checks merely to resume.
4. Recover the private continuation artifacts below through a supported,
   explicitly authorized owner-local transfer when needed. Verify hashes in the
   receiving environment. A path in this cloud is not a transferred file.

## Important files outside Git

These were retained, not uploaded as a bundle or added to Git. Private evidence,
raw stores/logs, secrets, caches and temporary databases must stay out of commits.
The readiness packet includes older checkpoint statuses; this document supersedes
its application-head/CI status only.

| Purpose | Cloud-local path | SHA-256 |
| --- | --- | --- |
| Reviewed canonical read-only procedure, not executed against production | `.omx/proposals/canonical-ledger-readonly-20261022.py` | `06590ecc217124fd0b1fa224318197c2af72c02d547d662bb1565df74da66bea` |
| Its exact owner route, prerequisites, invocation and expected sanitized output | `.omx/proposals/canonical-ledger-readonly-procedure-20261022.md` | `bf590ae157c6b65e389529fb6f03d9aabba19552052da6472ff6e909c55e69a6` |
| Private recovery readiness/provenance packet | `.omx/proposals/notification-recovery-readiness-20261022.md` | `a9e954414133fdeb7bc061f1bf5e4fffe192fb936202e089cd0f3b490b6272ce` |
| Proposed NEW request, not a historical wire receipt or approval | `.omx/evidence/recovered-20261022/proposed-new-notification-request.canonical.json` | `7fc70dca56727ec63b3072bc88890fbf37b5c92fe64e207769e13b7cd91d2253` |
| Synthetic browser harness, optional for replaying the visual evidence | `/tmp/money-machine-ui-projection.py` | `4117a993bec7ba7fb68c775cf0bdee8a704ab283643f5c7edac8e7c162c52029` |

Synthetic screenshots/JSON are under `/tmp/money-machine-ui-projection/` and the
earlier `/tmp/money-machine-ui-acceptance/`. Their index is
`.omx/state/a07-ui-projection.json`; these temporary files are not durable Git
artifacts. Preserve them in this workspace; request an approved evidence transfer
if they are needed elsewhere. Committed fixture tests remain the portable
behavioral regression. No workspace deletion or evidence archive is authorized.

The original 3,857-byte persisted ProductSpec and 6,353-byte reconstructed
schema/provenance JSON have authorized Library copies held by the existing owner.
Their expected SHA-256 values are respectively
`c894bb592c185346a9039b86f9337e32d953be727f9c636da3903ac71a81b251`
and `6a01cc02590450f7f4a5dccee2eb283dc20074f467e36425034c0a9f405cce7f`.
The parent independently verified backing bytes; this cloud validated complete
text projections. This is not a production DB-row read or historical wire request.
Do not manufacture evidence or embed private payloads in this public repository.

## Live product and execution remain held

See [REAL_NOTION_COMPLETION.md](REAL_NOTION_COMPLETION.md) for the implemented
builder, lifecycle, guard and finite consumer contracts. The original Notification
attempt remains UNKNOWN; fourteen confirmed effects and its incident remain
preserved. Current search/child absence never authorizes a retry. Do not run the
ordinary builder with `--execute` or replace the ledger from a fresh database.

The indispensable next checks/actions are:

- Existing production owner recovers the original run's explicit canonical
  database/runtime configuration reference. Login/SSH reachability and the cloud
  development database do not establish ledger access. Then arrange reviewed
  owner-local placement of the bounded read-only procedure: explicit production
  settings, PostgreSQL-only, READ ONLY transaction, bounded SELECTs and rollback;
  no setup, seed, migration, autoflush writes or fallback database.
- Verify actual original job/spec/producer/research/run lineage, fourteen receipt
  mappings, unresolved attempt/incident and active leases/runs in that canonical
  ledger. Missing rows must not be filled from fixtures.
- Verify actual registered A07 identity/trace, production prompt admission and
  commissioning. `prompts/agents/A07/v1.md` exists and is tested, but A07 remains
  DESIGNED in fixtures; a local definition is not thredOS registration.
- Obtain separately authorized deployment/migration/runtime binding and authentic
  exact-operation approval/lease admission. None was issued or executed here.
- Fresh resource/source/schema preflight must use the original authorized Notion
  connection before any separately approved send. The denied alternate account
  remains unavailable. Effect confirmation does not select a canonical replacement,
  complete the job/workflow or close the original incident.

The actual Forest product is unfinished. Approved covers, dashboard/hubs,
Notification, complete variants, native functional/visual QA, media/access PDF
and Etsy draft verification still require completion under applicable authority.
Canonical Playbook PDF byte verification is unresolved. Recovered research is
36 listings plus a 34/40 operator score, not measured customer demand. Do not
repeat collection or create a new scraper as a handoff step.

## Tooling limits at handoff

No successful cloud installation/output is claimed for Graphify, MLflow or
Momentic. Existing `scripts/setup_graphify.sh` and
[GRAPHIFY.md](GRAPHIFY.md) are reproducible preparation, not proof of a graph.
At 20:18 UTC, npm and PyPI each failed proxy CONNECT with HTTP503/curl56 before
an upstream response. At 20:24 UTC, one Docker manifest inspection of
`ghcr.io/mlflow/mlflow:v3.17.2` failed at `https://ghcr.io/v2/` with Service
Unavailable. Docker client/daemon 28.4.0 worked; no MLflow image was cached or
pulled, and no container was started. No policy/proxy/VPN settings were changed.
Do not repeat unchanged failing routes or enable external tracing/hosted tests
as a setup shortcut. No saved-environment installation persistence was established.

The instructions-only Python Scrapfly skill is local and ignored:
`.agents/skills/scrapfly-scraper/SKILL.md`, SHA-256
`987ca797fab812a9e3c718e7ad48c4a2d52a4f90d95b7ad631c022a276c2544d`.
Its [official source](https://github.com/scrapfly/skills/blob/303bf75ae81efb83aab03f7fa06ce461800cc026/skills/scrapfly-scraper/SKILL.md)
is pinned at `303bf75ae81efb83aab03f7fa06ce461800cc026`. It was placed manually,
not installed by a skills CLI. No Scrapfly SDK, account, credentials or paid
collection was configured. Neither this skill nor any credential transfers by
cloning the repository.
