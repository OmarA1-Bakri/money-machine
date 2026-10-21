"""Bounded real-private Notion operations for D-0039.

Source contract: notion-client 2.7.0 (installed endpoint/client source), API
2025-09-03; https://developers.notion.com/guides/data-apis/working-with-views
and https://developers.notion.com/reference/post-page. No mutation retries.
The consumer reserves durable intents and reconciles uncertain effects.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping, Sequence
from typing import Any, Literal
from uuid import UUID

from notion_client import AsyncClient
from notion_client.errors import APIResponseError

from money_machine.application.real_draft_authority import DraftRunAuthority, DraftRunRefused

Json = dict[str, Any]
Kind = Literal["pages", "databases", "data_sources", "blocks", "views"]


class NotionEffectUncertain(RuntimeError):
    """A write may have committed. Reconcile the durable intent before retry."""


def _id(value: str | UUID) -> str:
    return str(UUID(str(value)))


def _title(value: str) -> list[Json]:
    if not value.strip() or len(value) > 2000:
        raise DraftRunRefused("invalid_title")
    return [{"type": "text", "text": {"content": value}}]


class RealPrivateNotionAdapter:
    """Only descendants of one verified private root may be accessed.

    Inject an SDK with a mock httpx transport in tests. Production callers own
    the SDK lifecycle and use API 2025-09-03. No request/path proxy is exposed.
    Scope is re-read from the provider, never inferred from a local ID cache.
    public_url checks establish no public web publication; the API does not
    expose the full collaborator ACL, which the caller must verify separately.
    """

    def __init__(
        self,
        authority: DraftRunAuthority,
        *,
        sdk: AsyncClient,
        mode: str = "real-private",
        verified_workspace_id: str | UUID | None = None,
        before_write: Callable[[], Awaitable[None]] | None = None,
    ) -> None:
        if mode != "real-private" or authority.verified_notion_parent_id is None:
            raise DraftRunRefused("real_private_verified_parent_required")
        self.authority = authority
        self._sdk = sdk
        self._root = str(authority.verified_notion_parent_id)
        self._workspace = _id(verified_workspace_id) if verified_workspace_id else None
        self.created_ids: set[str] = set()
        self._before_write = before_write

    def _authorize(self, *, write: bool = False) -> None:
        self.authority.authorize(
            "notion.private_product.write" if write else "notion.private_product.read",
            run_id=self.authority.run_id,
            product_id=self.authority.product_id,
            notion_parent_id=self.authority.verified_notion_parent_id,
        )

    async def _call(
        self,
        method: str,
        path: str,
        *,
        body: Json | None = None,
        query: Json | None = None,
        write: bool = False,
    ) -> Json:
        self._authorize(write=write)
        if write:
            if self._before_write is None:
                raise DraftRunRefused("durable_effect_guard_required")
            try:
                await self._before_write()
            except Exception:
                raise DraftRunRefused("durable_effect_guard_refused") from None
        try:
            result = await self._sdk.request(path=path, method=method, body=body, query=query)
        except APIResponseError as exc:
            if write and exc.status >= 500:
                raise NotionEffectUncertain("provider_write_outcome_unknown") from None
            # Do not disclose provider payloads or headers in adapter errors.
            raise DraftRunRefused(f"notion_provider_refused_{exc.status}") from None
        except Exception:
            if write:
                raise NotionEffectUncertain("provider_write_outcome_unknown") from None
            raise DraftRunRefused("notion_read_failed") from None
        if not isinstance(result, dict):
            if write:
                raise NotionEffectUncertain("provider_write_response_invalid")
            raise DraftRunRefused("provider_read_response_invalid")
        if write and path not in {"data_sources/query"}:
            # Append returns a list; other writes return a resource UUID.
            try:
                if path.endswith("/children"):
                    for child in result["results"]:
                        self.created_ids.add(_id(child["id"]))
                else:
                    self.created_ids.add(_id(result["id"]))
            except (KeyError, TypeError, ValueError):
                raise NotionEffectUncertain("provider_write_response_invalid") from None
        return result

    async def _scope(self, kind: Kind, object_id: str | UUID) -> Json:
        requested = _id(object_id)
        current_kind, current_id = kind, requested
        visited: set[str] = set()
        first: Json | None = None
        for _ in range(32):
            if current_id in visited:
                raise DraftRunRefused("notion_ancestry_cycle")
            visited.add(current_id)
            obj = await self._call("GET", f"{current_kind}/{current_id}")
            if _id(obj.get("id", "")) != current_id:
                raise DraftRunRefused("notion_identity_mismatch")
            if obj.get("archived") or obj.get("in_trash") or obj.get("public_url"):
                raise DraftRunRefused("notion_private_active_object_required")
            if first is None:
                first = obj
            if current_id == self._root:
                if current_kind != "pages":
                    raise DraftRunRefused("notion_private_page_root_required")
                return first
            parent = obj.get("parent", {})
            parent_type = parent.get("type")
            kinds: dict[str, Kind] = {
                "page_id": "pages",
                "database_id": "databases",
                "data_source_id": "data_sources",
                "block_id": "blocks",
            }
            if parent_type not in kinds:
                raise DraftRunRefused("notion_outside_verified_parent")
            current_kind = kinds[parent_type]
            current_id = _id(parent[parent_type])
        raise DraftRunRefused("notion_ancestry_too_deep")

    async def _references(self, value: Any) -> None:
        """Reject destructive controls and validate cross-resource references."""
        if isinstance(value, Mapping):
            for key, item in value.items():
                if key in {"archived", "in_trash", "public_url", "publish", "public", "sharing"}:
                    raise DraftRunRefused("notion_forbidden_control")
                if key in {"external", "embed", "bookmark", "synced_block"}:
                    raise DraftRunRefused("notion_external_resource_forbidden")
                if key in {"page_id", "database_id", "data_source_id", "block_id"}:
                    kind: Kind = {
                        "page_id": "pages",
                        "database_id": "databases",
                        "data_source_id": "data_sources",
                        "block_id": "blocks",
                    }[key]  # type: ignore[assignment]
                    await self._scope(kind, item)
                if key == "relation" and isinstance(item, list):
                    for target in item:
                        await self._scope("pages", target["id"])
                await self._references(item)
        elif isinstance(value, (list, tuple)):
            for item in value:
                await self._references(item)

    async def create_workspace_product(
        self,
        title: str,
        *,
        children: Sequence[Json] = (),
    ) -> Json:
        if self._workspace is None or self._root != self._workspace:
            raise DraftRunRefused("verified_workspace_creation_required")
        me = await self._call("GET", "users/me")
        bot = me.get("bot", {})
        if (
            _id(bot.get("workspace_id", "")) != self._workspace
            or bot.get("owner", {}).get("type") != "user"
        ):
            raise DraftRunRefused("notion_workspace_owner_mismatch")
        await self._references(children)
        return await self._call(
            "POST",
            "pages",
            write=True,
            body={
                "parent": {"workspace": True},
                "properties": {"title": {"type": "title", "title": _title(title)}},
                "children": list(children),
            },
        )

    async def get_page(self, page_id: str | UUID) -> Json:
        return await self._scope("pages", page_id)

    async def create_page(
        self,
        parent_id: str | UUID,
        title: str,
        *,
        children: Sequence[Json] = (),
        icon: Json | None = None,
    ) -> Json:
        parent = _id(parent_id)
        await self._scope("pages", parent)
        await self._references(children)
        body: Json = {
            "parent": {"type": "page_id", "page_id": parent},
            "properties": {"title": {"type": "title", "title": _title(title)}},
            "children": list(children),
        }
        if icon is not None:
            if set(icon) != {"type", "emoji"} or icon["type"] != "emoji":
                raise DraftRunRefused("emoji_icon_required")
            body["icon"] = icon
        return await self._call("POST", "pages", body=body, write=True)

    async def _list(self, path: str, *, body: Json | None = None) -> list[Json]:
        results: list[Json] = []
        cursor: str | None = None
        seen: set[str] = set()
        for _ in range(100):
            params: Json = {"page_size": 100}
            if cursor:
                params["start_cursor"] = cursor
            page = await self._call(
                "POST" if body is not None else "GET",
                path,
                body={**body, **params} if body is not None else None,
                query=params if body is None else None,
            )
            results.extend(page["results"])
            if not page.get("has_more"):
                return results
            cursor = page.get("next_cursor")
            if not cursor or cursor in seen:
                raise DraftRunRefused("notion_invalid_pagination")
            seen.add(cursor)
        raise DraftRunRefused("notion_pagination_limit")

    async def list_blocks(self, page_id: str | UUID) -> list[Json]:
        await self._scope("pages", page_id)
        return await self._list(f"blocks/{_id(page_id)}/children")

    async def append_blocks(self, page_id: str | UUID, children: Sequence[Json]) -> Json:
        await self._scope("pages", page_id)
        if not 1 <= len(children) <= 100:
            raise DraftRunRefused("notion_block_batch_limit")
        await self._references(children)
        return await self._call(
            "PATCH",
            f"blocks/{_id(page_id)}/children",
            body={"children": list(children)},
            write=True,
        )

    async def create_database(
        self,
        parent_id: str | UUID,
        title: str,
        properties: Json,
    ) -> Json:
        await self._scope("pages", parent_id)
        await self._references(properties)
        return await self._call(
            "POST",
            "databases",
            write=True,
            body={
                "parent": {"type": "page_id", "page_id": _id(parent_id)},
                "title": _title(title),
                "is_inline": True,
                "initial_data_source": {"properties": properties},
            },
        )

    async def get_database(self, database_id: str | UUID) -> Json:
        return await self._scope("databases", database_id)

    async def get_data_source(self, data_source_id: str | UUID) -> Json:
        return await self._scope("data_sources", data_source_id)

    async def update_data_source(self, data_source_id: str | UUID, properties: Json) -> Json:
        await self._scope("data_sources", data_source_id)
        if any(value is None for value in properties.values()):
            raise DraftRunRefused("notion_property_deletion_forbidden")
        await self._references(properties)
        return await self._call(
            "PATCH",
            f"data_sources/{_id(data_source_id)}",
            body={"properties": properties},
            write=True,
        )

    async def create_row(self, data_source_id: str | UUID, properties: Json) -> Json:
        await self._scope("data_sources", data_source_id)
        await self._references(properties)
        return await self._call(
            "POST",
            "pages",
            write=True,
            body={
                "parent": {"type": "data_source_id", "data_source_id": _id(data_source_id)},
                "properties": properties,
            },
        )

    async def query_rows(
        self,
        data_source_id: str | UUID,
        *,
        filter: Json | None = None,
    ) -> list[Json]:
        await self._scope("data_sources", data_source_id)
        return await self._list(
            f"data_sources/{_id(data_source_id)}/query", body={"filter": filter} if filter else {}
        )

    async def create_view(
        self,
        database_id: str | UUID,
        data_source_id: str | UUID,
        name: str,
        *,
        view_type: str = "table",
        filter: Json | None = None,
    ) -> Json:
        await self._scope("databases", database_id)
        return await self._create_view(
            {"database_id": _id(database_id)}, data_source_id, name, view_type, filter
        )

    async def create_linked_view(
        self,
        page_id: str | UUID,
        data_source_id: str | UUID,
        name: str,
        *,
        view_type: str = "table",
        filter: Json | None = None,
    ) -> Json:
        await self._scope("pages", page_id)
        return await self._create_view(
            {
                "create_database": {
                    "parent": {"type": "page_id", "page_id": _id(page_id)},
                    "show_data_source_title": False,
                }
            },
            data_source_id,
            name,
            view_type,
            filter,
        )

    async def _create_view(
        self,
        target: Json,
        source: str | UUID,
        name: str,
        view_type: str,
        filter: Json | None,
    ) -> Json:
        if view_type not in {"table", "board", "list", "calendar", "timeline", "gallery"}:
            raise DraftRunRefused("notion_view_type_forbidden")
        _title(name)
        data_source = await self._scope("data_sources", source)
        body = {**target, "data_source_id": _id(source), "name": name, "type": view_type}
        if view_type == "calendar":
            # API2025-09-03 create-view.md calendarViewConfigRequest requires this ID.
            date_property = data_source.get("properties", {}).get("Date", {})
            if date_property.get("type") != "date" or not date_property.get("id"):
                raise DraftRunRefused("calendar_date_property_required")
            body["configuration"] = {
                "type": "calendar",
                "date_property_id": date_property["id"],
                "view_range": "month",
            }
        if filter is not None:
            body["filter"] = filter
        return await self._call("POST", "views", body=body, write=True)

    async def get_view(self, view_id: str | UUID) -> Json:
        return await self._scope("views", view_id)

    @staticmethod
    def _page_title(page: Json) -> str:
        for prop in page.get("properties", {}).values():
            if prop.get("type") == "title":
                return "".join(
                    t.get("plain_text", t.get("text", {}).get("content", ""))
                    for t in prop.get("title", [])
                )
        return ""

    async def _workspace_owner(self) -> None:
        if self._workspace is None or self._root != self._workspace:
            raise DraftRunRefused("verified_workspace_creation_required")
        me = await self._call("GET", "users/me")
        bot = me.get("bot", {})
        if (
            _id(bot.get("workspace_id", "")) != self._workspace
            or bot.get("owner", {}).get("type") != "user"
        ):
            raise DraftRunRefused("notion_workspace_owner_mismatch")

    async def get_workspace_product(self, page_id: str | UUID, title: str, marker: str) -> Json:
        await self._workspace_owner()
        page = await self._call("GET", f"pages/{_id(page_id)}")
        if (
            _id(page.get("id", "")) != _id(page_id)
            or page.get("parent", {}).get("type") != "workspace"
            or page.get("archived")
            or page.get("in_trash")
            or page.get("public_url")
            or self._page_title(page) != title
        ):
            raise DraftRunRefused("workspace_product_identity_mismatch")
        blocks = await self._list(f"blocks/{_id(page_id)}/children")
        contents = [
            "".join(
                t.get("plain_text", t.get("text", {}).get("content", ""))
                for t in b.get(b.get("type", ""), {}).get("rich_text", [])
            )
            for b in blocks
        ]
        if marker not in contents:
            raise DraftRunRefused("workspace_product_marker_missing")
        return page

    async def find_workspace_product(self, title: str, marker: str) -> Json | None:
        await self._workspace_owner()
        pages = await self._list(
            "search", body={"query": title, "filter": {"property": "object", "value": "page"}}
        )
        matches = []
        for page in pages:
            if (
                page.get("parent", {}).get("type") == "workspace"
                and self._page_title(page) == title
            ):
                try:
                    matches.append(await self.get_workspace_product(page["id"], title, marker))
                except DraftRunRefused as exc:
                    if str(exc) != "workspace_product_marker_missing":
                        raise
        if len(matches) > 1:
            raise DraftRunRefused("duplicate_workspace_product")
        return matches[0] if matches else None

    async def find_page(self, parent_id: str | UUID, title: str) -> Json | None:
        parent = _id(parent_id)
        matches = []
        for block in await self.list_blocks(parent):
            if (
                block.get("type") == "child_page"
                and block.get("child_page", {}).get("title") == title
            ):
                page = await self.get_page(block["id"])
                if (
                    page.get("parent", {}).get("type") != "page_id"
                    or _id(page["parent"]["page_id"]) != parent
                    or self._page_title(page) != title
                ):
                    raise DraftRunRefused("child_page_identity_mismatch")
                matches.append(page)
        if len(matches) > 1:
            raise DraftRunRefused("duplicate_child_page")
        return matches[0] if matches else None

    async def find_database(self, parent_id: str | UUID, title: str) -> Json | None:
        parent = _id(parent_id)
        matches = []
        for block in await self.list_blocks(parent):
            if (
                block.get("type") == "child_database"
                and block.get("child_database", {}).get("title") == title
            ):
                database = await self.get_database(block["id"])
                if _id(database.get("parent", {}).get("page_id", "")) != parent:
                    raise DraftRunRefused("child_database_identity_mismatch")
                matches.append(database)
        if len(matches) > 1:
            raise DraftRunRefused("duplicate_child_database")
        return matches[0] if matches else None

    async def list_views(self, database_id: str | UUID) -> list[Json]:
        await self._scope("databases", database_id)
        return await self._list(f"databases/{_id(database_id)}/views")

    async def find_linked_view(
        self, page_id: str | UUID, data_source_id: str | UUID, name: str
    ) -> Json | None:
        source = _id(data_source_id)
        matches = []
        await self._scope("data_sources", source)
        for block in await self.list_blocks(page_id):
            if block.get("type") == "child_database":
                for view in await self.list_views(block["id"]):
                    if view.get("name") == name and _id(view.get("data_source_id", "")) == source:
                        matches.append(await self.get_view(view["id"]))
        if len(matches) > 1:
            raise DraftRunRefused("duplicate_linked_view")
        return matches[0] if matches else None
