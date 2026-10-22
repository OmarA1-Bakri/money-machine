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
