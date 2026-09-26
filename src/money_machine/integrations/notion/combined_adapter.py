"""Combined Notion adapter: route each operation to the API or browser delegate.

Preferred channel follows the method column in
``docs/architecture/PLATFORM_COMPATIBILITY.md``. ``reports_unsupported`` is
checked before the call and may route to the other adapter, including for a
write, because nothing has been invoked yet. ``OperationUnsupportedError`` is
raised before any side effect and selects the other adapter only for a read or
other idempotent operation. After a non-idempotent write has been invoked, no
exception selects the other adapter.

``get_public_url`` is the COMBINED operation: the API delegate returns the
public URL, then the browser delegate verifies stranger access.
"""

from __future__ import annotations

import inspect
from typing import Any

from .adapter import NotionAdapter
from .domain import (
    NotionCalloutBlock,
    NotionDatabase,
    NotionDatabaseProperty,
    NotionFilter,
    NotionFormula,
    NotionLinkedView,
    NotionPage,
    NotionRelation,
    NotionRollup,
    NotionSort,
    NotionTextBlock,
    NotionView,
    NotionWorkspace,
)


class OperationUnsupportedError(NotImplementedError):
    """Raised before any side effect when an adapter cannot perform an operation.

    CombinedNotionAdapter treats this as a fallback signal only for a read or
    other idempotent operation. A non-idempotent write that has already been
    invoked never falls back, including when it raises this class,
    ``NotImplementedError``, or another subclass of ``NotImplementedError``.
    ``reports_unsupported`` is checked before the call, including for writes,
    and may route to the other adapter because nothing has been called yet.
    """


# DIRECT_API operations. get_public_url is COMBINED, not a single-delegate call.
API_OPERATIONS: frozenset[str] = frozenset(
    {
        "connection_status",
        "workspace_discovery",
        "create_page",
        "rename_page",
        "move_page",
        "set_icon",
        "set_cover",
        "add_text_block",
        "add_callout_block",
        "create_database",
        "add_property",
        "create_relation",
        "create_rollup",
        "add_filter",
        "add_sort",
        "add_child_page",
        "inspect_page",
        "inspect_database",
    }
)

COMBINED_OPERATIONS: frozenset[str] = frozenset({"get_public_url"})

# BROWSER operations from PLATFORM_COMPATIBILITY.md.
BROWSER_OPERATIONS: frozenset[str] = frozenset(
    {
        "duplicate_page",
        "create_formula",
        "create_linked_view",
        "create_calendar_view",
        "create_table_view",
        "create_board_view",
        "set_view_title_visibility",
        "publish_page",
        "set_duplicate_as_template",
        "set_search_indexing",
        "unpublish_page",
        "verify_stranger_access",
    }
)

# Idempotent column ``false`` in PLATFORM_COMPATIBILITY.md. After one of these
# has been invoked, no exception selects the other adapter.
NON_IDEMPOTENT_OPERATIONS: frozenset[str] = frozenset(
    {
        "add_callout_block",
        "add_child_page",
        "add_text_block",
        "create_board_view",
        "create_calendar_view",
        "create_database",
        "create_linked_view",
        "create_page",
        "create_table_view",
        "duplicate_page",
    }
)


def _reports_unsupported(adapter: NotionAdapter, operation: str) -> bool:
    """True when the delegate explicitly reports it cannot perform the operation."""
    reporter = getattr(adapter, "reports_unsupported", None)
    if not callable(reporter):
        return False
    reported = reporter(operation)
    if not isinstance(reported, bool):
        raise TypeError(
            f"{type(adapter).__name__}.reports_unsupported({operation!r}) must return bool"
        )
    return reported


async def _invoke(
    adapter: NotionAdapter,
    operation: str,
    /,
    *args: object,
    **kwargs: object,
) -> object:
    method = getattr(adapter, operation)
    if not callable(method):
        raise TypeError(f"{operation} is not callable on {type(adapter).__name__}")
    outcome = method(*args, **kwargs)
    if not inspect.isawaitable(outcome):
        raise TypeError(f"{operation} must be awaitable on {type(adapter).__name__}")
    return await outcome


async def _invoke_fallback(
    fallback: NotionAdapter,
    operation: str,
    first: Exception,
    /,
    *args: object,
    **kwargs: object,
) -> Any:
    """Call the other adapter. A second failure keeps ``first`` as ``__cause__``."""
    try:
        return await _invoke(fallback, operation, *args, **kwargs)
    except Exception as second:
        raise second from first


class CombinedNotionAdapter(NotionAdapter):
    """Route Notion operations to an API delegate or a browser delegate.

    The preferred delegate is selected from ``API_OPERATIONS`` and
    ``BROWSER_OPERATIONS``. ``reports_unsupported(operation)`` is checked
    before the call. ``OperationUnsupportedError`` then selects the other
    delegate only for a read or other idempotent operation, and only when it
    is raised before any side effect. A non-idempotent write that has been
    invoked is never retried. ``get_public_url`` follows the COMBINED contract
    instead of this single-delegate route.
    """

    def __init__(self, api_adapter: NotionAdapter, browser_adapter: NotionAdapter) -> None:
        self._api = api_adapter
        self._browser = browser_adapter

    def _pair(self, operation: str) -> tuple[NotionAdapter, NotionAdapter]:
        if operation in BROWSER_OPERATIONS:
            return self._browser, self._api
        if operation in API_OPERATIONS:
            return self._api, self._browser
        raise ValueError(f"unknown Notion operation: {operation}")

    async def _delegate(
        self,
        operation: str,
        /,
        *args: object,
        **kwargs: object,
    ) -> Any:
        preferred, fallback = self._pair(operation)
        if _reports_unsupported(preferred, operation):
            return await _invoke_fallback(
                fallback,
                operation,
                OperationUnsupportedError(f"{operation} is unsupported on the preferred adapter"),
                *args,
                **kwargs,
            )
        if operation in NON_IDEMPOTENT_OPERATIONS:
            return await _invoke(preferred, operation, *args, **kwargs)
        try:
            return await _invoke(preferred, operation, *args, **kwargs)
        except OperationUnsupportedError as first:
            return await _invoke_fallback(fallback, operation, first, *args, **kwargs)

    async def connection_status(self) -> dict[str, bool | str | int]:
        return await self._delegate("connection_status")

    async def workspace_discovery(self) -> list[NotionWorkspace]:
        return await self._delegate("workspace_discovery")

    async def create_page(
        self,
        title: str,
        parent_id: str | None = None,
        parent_type: str = "workspace",
        icon: str | None = None,
        cover: str | None = None,
    ) -> NotionPage:
        return await self._delegate(
            "create_page",
            title=title,
            parent_id=parent_id,
            parent_type=parent_type,
            icon=icon,
            cover=cover,
        )

    async def duplicate_page(self, page_id: str) -> NotionPage:
        return await self._delegate("duplicate_page", page_id=page_id)

    async def rename_page(self, page_id: str, new_title: str) -> NotionPage:
        return await self._delegate("rename_page", page_id=page_id, new_title=new_title)

    async def move_page(
        self, page_id: str, new_parent_id: str, new_parent_type: str = "workspace"
    ) -> NotionPage:
        return await self._delegate(
            "move_page",
            page_id=page_id,
            new_parent_id=new_parent_id,
            new_parent_type=new_parent_type,
        )

    async def set_icon(self, page_id: str, icon: str) -> NotionPage:
        return await self._delegate("set_icon", page_id=page_id, icon=icon)

    async def set_cover(self, page_id: str, cover_url: str) -> NotionPage:
        return await self._delegate("set_cover", page_id=page_id, cover_url=cover_url)

    async def add_text_block(self, page_id: str, content: str) -> NotionTextBlock:
        return await self._delegate("add_text_block", page_id=page_id, content=content)

    async def add_callout_block(
        self, page_id: str, content: str, icon: str = "💡"
    ) -> NotionCalloutBlock:
        return await self._delegate(
            "add_callout_block", page_id=page_id, content=content, icon=icon
        )

    async def create_database(
        self,
        title: str,
        parent_id: str | None = None,
        parent_type: str = "workspace",
        icon: str | None = None,
        cover: str | None = None,
    ) -> NotionDatabase:
        return await self._delegate(
            "create_database",
            title=title,
            parent_id=parent_id,
            parent_type=parent_type,
            icon=icon,
            cover=cover,
        )

    async def add_property(
        self, database_id: str, name: str, property_type: str, config: dict[str, Any]
    ) -> NotionDatabaseProperty:
        return await self._delegate(
            "add_property",
            database_id=database_id,
            name=name,
            property_type=property_type,
            config=config,
        )

    async def create_relation(
        self,
        database_id: str,
        name: str,
        target_database_id: str,
        synced_property_name: str | None = None,
    ) -> NotionRelation:
        return await self._delegate(
            "create_relation",
            database_id=database_id,
            name=name,
            target_database_id=target_database_id,
            synced_property_name=synced_property_name,
        )

    async def create_rollup(
        self,
        database_id: str,
        name: str,
        relation_property_id: str,
        rollup_property_id: str,
        function: str,
    ) -> NotionRollup:
        return await self._delegate(
            "create_rollup",
            database_id=database_id,
            name=name,
            relation_property_id=relation_property_id,
            rollup_property_id=rollup_property_id,
            function=function,
        )

    async def create_formula(self, database_id: str, name: str, expression: str) -> NotionFormula:
        return await self._delegate(
            "create_formula",
            database_id=database_id,
            name=name,
            expression=expression,
        )

    async def create_linked_view(
        self,
        source_database_id: str,
        parent_page_id: str,
        view_type: str = "table",
    ) -> NotionLinkedView:
        return await self._delegate(
            "create_linked_view",
            source_database_id=source_database_id,
            parent_page_id=parent_page_id,
            view_type=view_type,
        )

    async def add_filter(
        self, database_id: str, view_id: str, filter_spec: NotionFilter
    ) -> dict[str, Any]:
        return await self._delegate(
            "add_filter",
            database_id=database_id,
            view_id=view_id,
            filter_spec=filter_spec,
        )

    async def add_sort(
        self, database_id: str, view_id: str, sort_spec: NotionSort
    ) -> dict[str, Any]:
        return await self._delegate(
            "add_sort",
            database_id=database_id,
            view_id=view_id,
            sort_spec=sort_spec,
        )

    async def create_calendar_view(
        self, database_id: str, name: str, date_property: str
    ) -> NotionView:
        return await self._delegate(
            "create_calendar_view",
            database_id=database_id,
            name=name,
            date_property=date_property,
        )

    async def create_table_view(self, database_id: str, name: str) -> NotionView:
        return await self._delegate("create_table_view", database_id=database_id, name=name)

    async def create_board_view(
        self, database_id: str, name: str, group_by_property: str
    ) -> NotionView:
        return await self._delegate(
            "create_board_view",
            database_id=database_id,
            name=name,
            group_by_property=group_by_property,
        )

    async def set_view_title_visibility(
        self, database_id: str, view_id: str, visible: bool
    ) -> NotionView:
        return await self._delegate(
            "set_view_title_visibility",
            database_id=database_id,
            view_id=view_id,
            visible=visible,
        )

    async def add_child_page(self, parent_page_id: str, title: str) -> NotionPage:
        return await self._delegate("add_child_page", parent_page_id=parent_page_id, title=title)

    async def publish_page(self, page_id: str) -> NotionPage:
        return await self._delegate("publish_page", page_id=page_id)

    async def set_duplicate_as_template(self, page_id: str, enabled: bool) -> NotionPage:
        return await self._delegate("set_duplicate_as_template", page_id=page_id, enabled=enabled)

    async def set_search_indexing(self, page_id: str, enabled: bool) -> NotionPage:
        return await self._delegate("set_search_indexing", page_id=page_id, enabled=enabled)

    async def get_public_url(self, page_id: str) -> str | None:
        """Return the API public URL only when stranger access succeeds.

        ``docs/architecture/PLATFORM_COMPATIBILITY.md`` (COMBINED Operations):
        the API delegate returns ``page.public_url`` when the page is published,
        and the browser delegate verifies logged-out access. ``None`` from the
        API means unpublished, so the browser is not called. A false stranger
        check returns ``None``. Errors from either delegate propagate.
        """
        url = await _invoke(self._api, "get_public_url", page_id=page_id)
        if url is None:
            return None
        if not isinstance(url, str):
            raise TypeError("get_public_url must return a string or None")
        accessible = await _invoke(self._browser, "verify_stranger_access", public_url=url)
        if not isinstance(accessible, bool):
            raise TypeError("verify_stranger_access must return bool")
        if not accessible:
            return None
        return url

    async def unpublish_page(self, page_id: str) -> NotionPage:
        return await self._delegate("unpublish_page", page_id=page_id)

    async def inspect_page(self, page_id: str) -> NotionPage:
        return await self._delegate("inspect_page", page_id=page_id)

    async def inspect_database(self, database_id: str) -> NotionDatabase:
        return await self._delegate("inspect_database", database_id=database_id)

    async def verify_stranger_access(self, public_url: str) -> bool:
        return await self._delegate("verify_stranger_access", public_url=public_url)
