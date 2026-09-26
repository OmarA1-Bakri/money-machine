"""Publishing and isolation helpers.

Session 06 prompt heading "### 7. Implement publishing and isolation helpers"
(``prompts/implementation/09_SESSION_06_NOTION_INTEGRATION_FOUNDATION.md``).

A page is ready when it is top level, published to the web, duplicate as
template is on, and search indexing is off. The secret link is captured and
public access must already be verified. A link must not reach a page that
belongs to another catalogue. This module does not move, publish, or open a
page. It does not call Notion, the network, or a browser.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import cast
from urllib.parse import urlparse

from .errors import SchemaBuilderError
from .formulas import validated_name

_TOP_LEVEL_PARENT = "workspace"
_EXACT_SECRET_HOSTS: frozenset[str] = frozenset({"notion.so", "www.notion.so", "notion.site"})
_NOTION_SITE_SUFFIX = ".notion.site"


@dataclass(frozen=True, slots=True)
class PublishedPage:
    """One catalogue page that passed the publishing and isolation checks."""

    page_id: str
    parent_type: str
    published_to_web: bool
    duplicate_as_template: bool
    search_indexing: bool
    secret_link: str
    public_access: bool
    links: tuple[str, ...]
    other_catalogue_pages: tuple[str, ...]

    def __post_init__(self) -> None:
        validated_name("page id", cast(object, self.page_id))
        _ensure_top_level(cast(object, self.parent_type))
        _ensure_published_to_web(cast(object, self.published_to_web))
        _ensure_duplicate_as_template(cast(object, self.duplicate_as_template))
        _ensure_search_indexing_off(cast(object, self.search_indexing))
        _capture_secret_link(cast(object, self.secret_link))
        _ensure_public_access(cast(object, self.public_access))
        links = _copy_page_ids(cast(object, self.links), "links", "link")
        other = _copy_page_ids(
            cast(object, self.other_catalogue_pages),
            "other catalogue pages",
            "other catalogue page",
        )
        _reject_other_catalogue_links(links, other)
        object.__setattr__(self, "links", links)
        object.__setattr__(self, "other_catalogue_pages", other)


def build_published_page(
    page_id: object,
    parent_type: object,
    published_to_web: object,
    duplicate_as_template: object,
    search_indexing: object,
    secret_link: object,
    public_access: object,
    links: object,
    other_catalogue_pages: object,
) -> PublishedPage:
    """Check one page against the publishing and isolation rules."""
    return PublishedPage(
        page_id=cast(str, page_id),
        parent_type=cast(str, parent_type),
        published_to_web=cast(bool, published_to_web),
        duplicate_as_template=cast(bool, duplicate_as_template),
        search_indexing=cast(bool, search_indexing),
        secret_link=cast(str, secret_link),
        public_access=cast(bool, public_access),
        links=cast(tuple[str, ...], links),
        other_catalogue_pages=cast(tuple[str, ...], other_catalogue_pages),
    )


def _ensure_top_level(parent_type: object) -> None:
    if parent_type != _TOP_LEVEL_PARENT:
        raise SchemaBuilderError("page must be top level")


def _ensure_published_to_web(value: object) -> None:
    if value is not True:
        raise SchemaBuilderError("page must be published to web")


def _ensure_duplicate_as_template(value: object) -> None:
    if value is not True:
        raise SchemaBuilderError("duplicate as template must be on")


def _ensure_search_indexing_off(value: object) -> None:
    if value is not False:
        raise SchemaBuilderError("search indexing must be off")


def _ensure_public_access(value: object) -> None:
    if value is not True:
        raise SchemaBuilderError("public access is not verified")


def _capture_secret_link(value: object) -> str:
    if not isinstance(value, str):
        raise SchemaBuilderError("secret link must be a string")
    if value.strip() == "" or value != value.strip():
        raise SchemaBuilderError("secret link must be present")
    parsed = urlparse(value)
    if parsed.scheme != "https":
        raise SchemaBuilderError("secret link must use https")
    if parsed.username is not None or parsed.password is not None:
        raise SchemaBuilderError("secret link must not contain userinfo")
    host = parsed.hostname
    if not isinstance(host, str) or not _allowed_secret_host(host):
        raise SchemaBuilderError("secret link host is not allowed")
    if parsed.path in ("", "/"):
        raise SchemaBuilderError("secret link must name a page")
    return value


def _allowed_secret_host(host: str) -> bool:
    if host in _EXACT_SECRET_HOSTS:
        return True
    if not host.endswith(_NOTION_SITE_SUFFIX):
        return False
    prefix = host[: -len(_NOTION_SITE_SUFFIX)]
    return prefix != "" and "." not in prefix


def _copy_page_ids(value: object, plural: str, singular: str) -> tuple[str, ...]:
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise SchemaBuilderError(f"{plural} must be a sequence")
    return tuple(validated_name(singular, item) for item in value)


def _reject_other_catalogue_links(links: tuple[str, ...], other: tuple[str, ...]) -> None:
    blocked = set(other)
    for destination in links:
        if destination in blocked:
            raise SchemaBuilderError(f"link {destination!r} reaches another catalogue")
