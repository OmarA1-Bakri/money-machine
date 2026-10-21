"""Finite D-0039 consumer of Notion API 2025-09-03 and existing SQL effects.

API shapes are defined by real_product_adapter.py (notion-client 2.7.0).
This module never owns credentials, publication, retries or a second ledger.
"""

from __future__ import annotations

import hashlib
from datetime import date
from typing import Any
from uuid import UUID

from notion_client import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from money_machine.application.real_draft_authority import DraftRunAuthority, DraftRunRefused
from money_machine.application.real_draft_effects import SqlDraftEffects
from money_machine.domain.models.product_spec import ProductSpec
from money_machine.integrations.notion.real_product_adapter import RealPrivateNotionAdapter

Json = dict[str, Any]
# Business architecture: playbook.txt:741-781,1240-1272; source PDF immutable.
# Theme tokens, examples and guide content are original product design choices.
SOURCES = ("Tasks", "Events", "Habits", "Finance", "Meals", "Notes")
TODAY = 'formatDate(prop("Date"), "YYYY-MM-DD") == formatDate(now(), "YYYY-MM-DD")'
THEMES = {"Forest": ("green", "🌿"), "Sand": ("brown", "☀️"), "Slate": ("gray", "🪨")}


def rich(text: str) -> list[Json]:
    return [{"type": "text", "text": {"content": text}}]


def block(text: str, kind: str = "paragraph", color: str = "default") -> Json:
    return {"object": "block", "type": kind, kind: {"rich_text": rich(text), "color": color}}


def title(text: str) -> Json:
    return {"title": rich(text)}


def select(*options: str) -> Json:
    return {"select": {"options": [{"name": name} for name in options]}}


def formula(expression: str) -> Json:
    return {"formula": {"expression": expression}}


def schemas() -> dict[str, Json]:
    """Shared sources; derived properties drive relative views and real rollups."""
    return {
        "Tasks": {
            "Name": {"title": {}},
            "Done": {"checkbox": {}},
            "Date": {"date": {}},
            "Category": select("Home", "Work", "Personal"),
            "Priority": select("High", "Normal", "Low"),
            "Due today": formula(TODAY),
            "Open today": formula('if(not prop("Done") and (' + TODAY + "), 1, 0)"),
        },
        "Events": {
            "Name": {"title": {}},
            "Date": {"date": {}},
            "Type": select("Birthday", "Appointment", "Reminder"),
            "Person": {"rich_text": {}},
            "Due today": formula(TODAY),
            "Birthday today": formula(
                'if(prop("Type") == "Birthday" and formatDate(prop("Date"), '
                '"MM-DD") == formatDate(now(), "MM-DD"), 1, 0)'
            ),
        },
        "Habits": {
            "Name": {"title": {}},
            "Date": {"date": {}},
            **{day: {"checkbox": {}} for day in ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")},
            "Water": {"number": {"format": "number"}},
            "Due today": formula(TODAY),
            "Water today": formula("if(" + TODAY + ', prop("Water"), 0)'),
        },
        "Finance": {
            "Item": {"title": {}},
            "Amount": {"number": {"format": "number"}},
            "Date": {"date": {}},
            "Type": select("Expense", "Income"),
            "Category": select("Food", "Bills", "Other"),
            "Due today": formula(TODAY),
            "Spent today": formula(
                'if(prop("Type") == "Expense" and (' + TODAY + '), prop("Amount"), 0)'
            ),
        },
        "Meals": {
            "Name": {"title": {}},
            "Date": {"date": {}},
            "Meal slot": select("Breakfast", "Lunch", "Dinner", "Snack"),
            "Due today": formula(TODAY),
        },
        "Notes": {
            "Name": {"title": {}},
            "Created date": {"date": {}},
            "Topic": select("Capture", "Weekly review", "Idea"),
        },
    }


def notification_schema(source_ids: dict[str, str], currency: str) -> Json:
    result: Json = {"Name": {"title": {}}, "Water goal": {"number": {"format": "number"}}}
    metrics = {
        "Tasks": ("Open today", "Open tasks"),
        "Events": ("Birthday today", "Birthdays"),
        "Finance": ("Spent today", "Spending"),
        "Habits": ("Water today", "Water logged"),
    }
    for source, (metric, rollup) in metrics.items():
        result[source] = {"relation": {"data_source_id": source_ids[source], "single_property": {}}}
        result[rollup] = {
            "rollup": {
                "relation_property_name": source,
                "rollup_property_name": metric,
                "function": "sum",
            }
        }
    result["Notification"] = formula(
        '"Have a good day, " + prop("Name") + ". Today is " + '
        'formatDate(now(), "dddd, MMMM D, YYYY")'
        ' + ". Open tasks due today: " + format(prop("Open tasks"))'
        ' + ". Birthdays today: " + format(prop("Birthdays"))'
        ' + ". Spent today: ' + currency + ' " + format(prop("Spending"))'
        ' + ". Water glasses left against your editable goal: "'
        ' + format(max(0, prop("Water goal") - prop("Water logged"))) + "."'
    )
    return result


def examples(day: date) -> dict[str, Json]:
    dated = {"date": {"start": day.isoformat()}}
    return {
        "Tasks": {
            "Name": title("EXAMPLE — plan a quiet afternoon"),
            "Done": {"checkbox": False},
            "Date": dated,
            "Category": {"select": {"name": "Personal"}},
            "Priority": {"select": {"name": "Normal"}},
        },
        "Events": {
            "Name": title("EXAMPLE — Alex birthday"),
            "Date": dated,
            "Type": {"select": {"name": "Birthday"}},
            "Person": {"rich_text": rich("Alex (example)")},
        },
        "Habits": {
            "Name": title("EXAMPLE — daily check-in"),
            "Date": dated,
            "Mon": {"checkbox": True},
            "Water": {"number": 2},
        },
        "Finance": {
            "Item": title("EXAMPLE — lunch"),
            "Date": dated,
            "Amount": {"number": 6.5},
            "Type": {"select": {"name": "Expense"}},
            "Category": {"select": {"name": "Food"}},
        },
        "Meals": {
            "Name": title("EXAMPLE — vegetable soup"),
            "Date": dated,
            "Meal slot": {"select": {"name": "Lunch"}},
        },
        "Notes": {
            "Name": title("EXAMPLE — weekly reset"),
            "Created date": dated,
            "Topic": {"select": {"name": "Weekly review"}},
        },
    }


GUIDES = (
    (
        "Choose your next action",
        "Capture tasks in Tasks. Give each task a date and priority. Pick "
        "one small next action. Tick Done when finished.",
        "A gentle daily reset",
        "Check today's priorities, move unfinished tasks deliberately, and "
        "leave tomorrow a short starting list.",
    ),
    (
        "Keep meaningful dates",
        "Add appointments and reminders in Events. Set Type to Birthday and "
        "fill Person for birthday reminders.",
        "Review the week ahead",
        "Scan the next seven days. Add preparation tasks in Tasks and keep "
        "the event date in Events.",
    ),
    (
        "Build a repeatable routine",
        "Use one Habits row per day. Tick the weekday checkbox when you "
        "complete your routine; log your water count.",
        "Adjust your own goals",
        "Change Water goal on the single Notification row to your own "
        "preference. This tracker provides no health advice.",
    ),
    (
        "A simple spending check",
        "Enter positive amounts in Finance and choose Expense or Income. "
        "Set the date. Spending counts today's Expense rows only.",
        "Plan a bill before it arrives",
        "Record a bill as an Events reminder and a Tasks action. Record the "
        "actual payment once in Finance; no bank connection is provided.",
    ),
    (
        "Plan a flexible week",
        "Add meal ideas to Meals with a date and meal slot. Move dates as "
        "plans change; start with meals you already enjoy.",
        "A practical pantry check",
        "Review what you already have, choose a few meals, and add shopping "
        "actions to Tasks. This planner does not prescribe diets.",
    ),
    (
        "Capture without sorting first",
        "Add quick notes in Notes with Topic Capture. Keep a clear title so "
        "you can find the idea later.",
        "Run a useful weekly review",
        "Review completed Tasks, upcoming Events and Finance entries. Write "
        "one observation and one next action in Notes with Topic Weekly review.",
    ),
)


class RealNotionProductBuilder:
    def __init__(
        self,
        authority: DraftRunAuthority,
        *,
        sdk: AsyncClient,
        session_factory: async_sessionmaker[AsyncSession],
        job_id: UUID,
        lease_owner: str,
    ) -> None:
        self.authority = authority
        self.sdk = sdk
        self.factory = session_factory
        self.job_id = job_id
        self.lease_owner = lease_owner

    def _bind(self, authority: DraftRunAuthority, workspace: UUID) -> None:
        self.effects = SqlDraftEffects(
            self.factory, authority, self.job_id, lease_owner=self.lease_owner
        )
        self.adapter = RealPrivateNotionAdapter(
            authority,
            sdk=self.sdk,
            verified_workspace_id=workspace,
            before_write=self.effects.assert_lease,
        )
        self.parent = authority.verified_notion_parent_id

    async def _effect(self, key: str, create: Any, reconcile: Any) -> Json:
        digest = hashlib.sha256(key.encode()).hexdigest()
        return dict(
            await self.effects.execute(
                "real-notion-v1:" + digest,
                provider="notion",
                operation="notion.private_product.write",
                create=create,
                reconcile=reconcile,
                notion_parent_id=self.parent,
            )
        )

    async def _page(
        self, key: str, parent: str, name: str, children: list[Json], icon: str = "📖"
    ) -> Json:
        async def reconcile(known: str | None) -> Json | None:
            page = (
                await self.adapter.get_page(known)
                if known
                else await self.adapter.find_page(parent, name)
            )
            if page is not None:
                if _page_title(page) != name or page.get("parent", {}).get("page_id") != parent:
                    raise DraftRunRefused("product_page_readback_mismatch")
                observed = await self.adapter.list_blocks(page["id"])
                expected_text = [_text(b) for b in children]
                actual_text = [_text(b) for b in observed]
                if any(t not in actual_text for t in expected_text):
                    raise DraftRunRefused("product_page_content_readback_mismatch")
            return page

        return await self._effect(
            key,
            lambda: self.adapter.create_page(
                parent, name, children=children, icon={"type": "emoji", "emoji": icon}
            ),
            reconcile,
        )

    async def _database(
        self, key: str, parent: str, name: str, properties: Json
    ) -> tuple[str, str]:
        async def reconcile(known: str | None) -> Json | None:
            db = (
                await self.adapter.get_database(known)
                if known
                else await self.adapter.find_database(parent, name)
            )
            if db is not None:
                if db.get("parent", {}).get("page_id") != parent:
                    raise DraftRunRefused("database_parent_readback_mismatch")
                sources = db.get("data_sources", [])
                if len(sources) != 1:
                    raise DraftRunRefused("database_single_source_required")
                ds = await self.adapter.get_data_source(sources[0]["id"])
                _schema_matches(properties, ds.get("properties", {}))
            return db

        db = await self._effect(
            key, lambda: self.adapter.create_database(parent, name, properties), reconcile
        )
        return str(db["id"]), str(db["data_sources"][0]["id"])

    async def _row(self, key: str, source: str, properties: Json) -> str:
        name_prop = "Item" if "Item" in properties else "Name"
        name = "".join(t["text"]["content"] for t in properties[name_prop]["title"])

        async def reconcile(known: str | None) -> Json | None:
            rows = await self.adapter.query_rows(source)
            matches = [r for r in rows if _page_title(r) == name]
            if len(matches) > 1:
                raise DraftRunRefused("duplicate_example_row")
            row = matches[0] if matches else None
            if row is not None:
                if known and row["id"] != known:
                    raise DraftRunRefused("row_identity_readback_mismatch")
                _row_matches(properties, row.get("properties", {}))
                return await self.adapter.get_page(row["id"])
            return None

        row = await self._effect(
            key, lambda: self.adapter.create_row(source, properties), reconcile
        )
        return str(row["id"])

    async def _view(
        self, key: str, page: str, source: str, name: str, filter: Json, view_type: str = "table"
    ) -> str:
        async def reconcile(known: str | None) -> Json | None:
            found = await self.adapter.find_linked_view(page, source, name)
            view = await self.adapter.get_view(known) if known else found
            if known and (found is None or found["id"] != known):
                raise DraftRunRefused("linked_view_parent_readback_mismatch")
            if view is not None and (
                view.get("name") != name
                or view.get("data_source_id") != source
                or view.get("type") != view_type
                or view.get("filter") != filter
            ):
                raise DraftRunRefused("linked_view_readback_mismatch")
            if view is not None and view_type == "calendar":
                source_properties = (await self.adapter.get_data_source(source))["properties"]
                configuration = view.get("configuration") or {}
                if (
                    configuration.get("date_property_id") != source_properties["Date"]["id"]
                    or configuration.get("view_range") != "month"
                ):
                    raise DraftRunRefused("calendar_configuration_readback_mismatch")
            return view

        view = await self._effect(
            key,
            lambda: self.adapter.create_linked_view(
                page, source, name, filter=filter, view_type=view_type
            ),
            reconcile,
        )
        return str(view["id"])

    async def build(self, spec: ProductSpec, *, run_id: str, workspace_id: UUID) -> Json:
        if (
            type(spec) is not ProductSpec
            or spec.product_id != self.authority.product_id
            or run_id != self.authority.run_id
            or self.authority.verified_notion_parent_id != workspace_id
            or tuple(spec.shared_databases) != SOURCES
            or len(spec.hubs) != 6
            or tuple(spec.colour_variants) != tuple(THEMES)
        ):
            raise DraftRunRefused("real_product_spec_scope")
        self._bind(self.authority, workspace_id)
        marker = f"mm-real-product:{run_id}:{spec.product_id}:v1"
        folder_title = f"{spec.title} — private build {run_id}"

        async def reconcile(known: str | None) -> Json | None:
            return (
                await self.adapter.get_workspace_product(known, folder_title, marker)
                if known
                else await self.adapter.find_workspace_product(folder_title, marker)
            )

        folder = await self._effect(
            "workspace:" + marker,
            lambda: self.adapter.create_workspace_product(folder_title, children=[block(marker)]),
            reconcile,
        )
        scoped = self.authority.model_copy(update={"verified_notion_parent_id": UUID(folder["id"])})
        self._bind(scoped, workspace_id)
        variants = []
        for variant in spec.colour_variants:
            variants.append(await self._variant(spec, str(folder["id"]), variant, marker))
        roots = [v["root_id"] for v in variants]
        all_sources = [s["data_source_id"] for v in variants for s in v["sources"].values()]
        if len(set(roots)) != 3 or len(set(all_sources)) != 18:
            raise DraftRunRefused("variant_complete_copy_identity")
        return {
            "schema_version": 1,
            "run_id": run_id,
            "product_id": str(spec.product_id),
            "spec_id": str(spec.spec_id),
            "private_folder_id": folder["id"],
            "variants": variants,
            "publication": "private",
            "visual_review": "pending_native_assets_and_human_review",
            "qa": "provider_readback_checked",
            "api_version": "2025-09-03",
        }

    async def _variant(self, spec: ProductSpec, parent: str, variant: str, marker: str) -> Json:
        color, icon = THEMES[variant]
        prefix = marker + ":" + variant
        token = next(t.hex for t in spec.palette_tokens if t.name == variant)
        home = await self._page(
            prefix + ":home",
            parent,
            f"{variant} — {spec.title}",
            [
                block(f"{variant} / {token}", "heading_1", color),
                block(
                    "Your calm place for today. Start with the dashboard, then choose a hub.",
                    color=color,
                ),
                block(
                    "Example rows are labelled EXAMPLE. Replace them and "
                    "connect new rows to the Notification row; its totals include linked rows only."
                ),
            ],
            icon,
        )
        home_id = str(home["id"])
        sources: Json = {}
        seeded: dict[str, str] = {}
        for name, props in schemas().items():
            db, ds = await self._database(prefix + ":source:" + name, home_id, name, props)
            sources[name] = {"database_id": db, "data_source_id": ds}
            seeded[name] = await self._row(
                prefix + ":example:" + name, ds, examples(spec.created_at.date())[name]
            )
        source_ids = {name: obj["data_source_id"] for name, obj in sources.items()}
        notification_db, notification_ds = await self._database(
            prefix + ":notification",
            home_id,
            "Notification",
            notification_schema(source_ids, spec.currency),
        )
        notification_props = {
            "Name": title("EXAMPLE — Alex"),
            "Water goal": {"number": 8},
            **{
                name: {"relation": [{"id": seeded[name]}]}
                for name in ("Tasks", "Events", "Finance", "Habits")
            },
        }
        notification_row = await self._row(
            prefix + ":notification-row", notification_ds, notification_props
        )
        rows = await self.adapter.query_rows(notification_ds)
        if len(rows) != 1 or rows[0]["id"] != notification_row:
            raise DraftRunRefused("notification_exactly_one_row_required")
        observed = rows[0].get("properties", {})
        result = observed.get("Notification", {}).get("formula", {})
        if result.get("type") != "string" or not result.get("string"):
            raise DraftRunRefused("notification_formula_result_missing")
        for metric in ("Open tasks", "Birthdays", "Spending", "Water logged"):
            rollup = observed.get(metric, {}).get("rollup", {})
            if rollup.get("type") != "number" or not isinstance(rollup.get("number"), (int, float)):
                raise DraftRunRefused("notification_rollup_result_missing")
        metric_sources = {
            "Tasks": ("Open today", "Open tasks"),
            "Events": ("Birthday today", "Birthdays"),
            "Finance": ("Spent today", "Spending"),
            "Habits": ("Water today", "Water logged"),
        }
        for name, (metric, rollup_name) in metric_sources.items():
            related = {r["id"] for r in observed[name]["relation"]}
            real_rows = await self.adapter.query_rows(source_ids[name])
            matched = [r for r in real_rows if r["id"] in related]
            if {r["id"] for r in matched} != related:
                raise DraftRunRefused("notification_related_rows_missing")
            total = 0.0
            for source_row in matched:
                computed = source_row["properties"].get(metric, {}).get("formula", {})
                if computed.get("type") != "number" or type(computed.get("number")) not in (
                    int,
                    float,
                ):
                    raise DraftRunRefused("source_formula_result_missing")
                total += computed["number"]
            if abs(total - observed[rollup_name]["rollup"]["number"]) > 0.000001:
                raise DraftRunRefused("notification_rollup_source_mismatch")
        notification_view = await self._view(
            prefix + ":dashboard",
            home_id,
            notification_ds,
            "Your day at a glance",
            {"property": "Name", "title": {"is_not_empty": True}},
            "list",
        )
        hubs = []
        for index, hub in enumerate(spec.hubs):
            name = SOURCES[index]
            page = await self._page(
                prefix + ":hub:" + name,
                home_id,
                hub.name,
                [
                    block(hub.name, "heading_1", color),
                    block(hub.description),
                    block(
                        f"These views use the shared {name} source. Edit a "
                        f"row here and it changes everywhere.",
                        color=color,
                    ),
                ],
                icon,
            )
            page_id = str(page["id"])
            ds = source_ids[name]
            today_filter = (
                {"property": "Topic", "select": {"equals": "Capture"}}
                if name == "Notes"
                else {"property": "Due today", "formula": {"checkbox": {"equals": True}}}
            )
            second_filter = (
                {"property": "Done", "checkbox": {"equals": False}}
                if name == "Tasks"
                else {"property": "Topic", "select": {"equals": "Weekly review"}}
                if name == "Notes"
                else {"property": "Type", "select": {"equals": "Birthday"}}
                if name == "Events"
                else {"property": "Type", "select": {"equals": "Expense"}}
                if name == "Finance"
                else {"property": "Date", "date": {"this_week": {}}}
            )
            view_ids = [
                await self._view(
                    prefix + ":hub-view:" + name + ":today",
                    page_id,
                    ds,
                    "Quick capture" if name == "Notes" else "Today",
                    today_filter,
                ),
                await self._view(
                    prefix + ":hub-view:" + name + ":focus", page_id, ds, "Focus", second_filter
                ),
            ]
            guide = GUIDES[index]
            guide_ids = [
                str(
                    (
                        await self._page(
                            prefix + ":guide:" + name + ":" + str(j),
                            page_id,
                            guide[j],
                            [block(guide[j], "heading_2", color), block(guide[j + 1])],
                            "📖",
                        )
                    )["id"]
                )
                for j in (0, 2)
            ]
            hubs.append(
                {
                    "name": hub.name,
                    "page_id": page_id,
                    "source_id": ds,
                    "view_ids": view_ids,
                    "guide_ids": guide_ids,
                }
            )
        navigation = [block(prefix + ":navigation", color=color)]
        navigation += [
            {
                "object": "block",
                "type": "link_to_page",
                "link_to_page": {"type": "page_id", "page_id": h["page_id"]},
            }
            for h in hubs
        ]

        async def reconcile_navigation(known: str | None) -> Json | None:
            blocks = await self.adapter.list_blocks(home_id)
            matches = [b for b in blocks if _text(b) == prefix + ":navigation"]
            if len(matches) > 1:
                raise DraftRunRefused("navigation_duplicate")
            if not matches:
                return None
            links = {
                b.get("link_to_page", {}).get("page_id")
                for b in blocks
                if b.get("type") == "link_to_page"
            }
            if not {h["page_id"] for h in hubs}.issubset(links):
                raise DraftRunRefused("navigation_readback_incomplete")
            return matches[0]

        async def create_navigation() -> Json:
            response = await self.adapter.append_blocks(home_id, navigation)
            return response["results"][0]

        await self._effect(prefix + ":navigation", create_navigation, reconcile_navigation)
        home_views = [
            await self._view(
                prefix + ":home-tasks",
                home_id,
                source_ids["Tasks"],
                "Today's priorities",
                {
                    "and": [
                        {"property": "Done", "checkbox": {"equals": False}},
                        {"property": "Due today", "formula": {"checkbox": {"equals": True}}},
                    ]
                },
            ),
            await self._view(
                prefix + ":home-calendar",
                home_id,
                source_ids["Events"],
                "This month",
                {"property": "Date", "date": {"this_month": {}}},
                "calendar",
            ),
            await self._view(
                prefix + ":home-notes",
                home_id,
                source_ids["Notes"],
                "Quick notes",
                {"property": "Topic", "select": {"equals": "Capture"}},
                "list",
            ),
        ]
        return {
            "name": variant,
            "palette_hex": token,
            "root_id": home_id,
            "sources": sources,
            "hubs": hubs,
            "home_view_ids": home_views,
            "notification": {
                "database_id": notification_db,
                "data_source_id": notification_ds,
                "row_id": notification_row,
                "view_id": notification_view,
                "formula_result": result["string"],
                "rollups": {
                    k: observed[k]["rollup"]["number"]
                    for k in ("Open tasks", "Birthdays", "Spending", "Water logged")
                },
            },
            "page_count_including_databases": 26,
            "regular_page_count": 19,
        }


def _text(value: Json) -> str:
    return "".join(
        t.get("plain_text", t.get("text", {}).get("content", ""))
        for t in value.get(value.get("type", ""), {}).get("rich_text", [])
    )


def _schema_matches(expected: Json, observed: Json) -> None:
    for name, prop in expected.items():
        kind = next(iter(prop))
        actual = observed.get(name, {})
        if actual.get("type") != kind:
            raise DraftRunRefused("database_schema_readback_mismatch")
        if kind == "select" and sorted(
            option["name"] for option in actual[kind].get("options", [])
        ) != sorted(option["name"] for option in prop[kind]["options"]):
            raise DraftRunRefused("database_select_options_readback_mismatch")
        if kind == "number" and actual[kind].get("format") != prop[kind].get("format"):
            raise DraftRunRefused("database_number_format_readback_mismatch")
        if kind == "formula" and actual[kind].get("expression") != prop[kind]["expression"]:
            raise DraftRunRefused("database_formula_readback_mismatch")
        if (
            kind == "relation"
            and actual[kind].get("data_source_id") != prop[kind]["data_source_id"]
        ):
            raise DraftRunRefused("database_relation_readback_mismatch")
        if kind == "rollup" and any(
            actual[kind].get(key) != val for key, val in prop[kind].items()
        ):
            raise DraftRunRefused("database_rollup_readback_mismatch")


def _row_matches(expected: Json, observed: Json) -> None:
    for name, prop in expected.items():
        kind = next(iter(prop))
        actual = observed.get(name, {}).get(kind)
        wanted = prop[kind]
        if kind == "title" or kind == "rich_text":
            actual = "".join(
                t.get("plain_text", t.get("text", {}).get("content", "")) for t in actual or []
            )
            wanted = "".join(t["text"]["content"] for t in wanted)
        elif kind == "relation":
            actual = sorted(r["id"] for r in actual or [])
            wanted = sorted(r["id"] for r in wanted)
        elif kind == "select":
            actual = (actual or {}).get("name")
            wanted = wanted["name"]
        elif kind == "date":
            actual = (actual or {}).get("start")
            wanted = wanted["start"]
        if actual != wanted:
            raise DraftRunRefused("row_properties_readback_mismatch")


def _page_title(page: Json) -> str:
    for prop in page.get("properties", {}).values():
        if prop.get("type") == "title":
            return "".join(
                t.get("plain_text", t.get("text", {}).get("content", ""))
                for t in prop.get("title", [])
            )
    return ""
