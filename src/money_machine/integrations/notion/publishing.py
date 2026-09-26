"""Publishing and isolation helpers.

Session 06 prompt heading "### 7. Implement publishing and isolation helpers"
(``prompts/implementation/09_SESSION_06_NOTION_INTEGRATION_FOUNDATION.md``).

A page is ready when it is top level, published to the web, duplicate as
template is on, and search indexing is off. The secret link is captured and
public access must already be verified. A link must not reach a page that
belongs to another catalogue. Page ids are compared as lowercase undashed
32-hex ids. A page-id URL is https on notion.so or www.notion.so, with no
query, fragment, or parameters. The secret link may still use notion.site.
This module does not move, publish, or open a page. It does not call Notion,
the network, or a browser.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass
from typing import cast
from urllib.parse import ParseResult, urlparse

from .errors import SchemaBuilderError

_TOP_LEVEL_PARENT = "workspace"
_EXACT_SECRET_HOSTS: frozenset[str] = frozenset({"notion.so", "www.notion.so", "notion.site"})
_PAGE_URL_HOSTS: frozenset[str] = frozenset({"notion.so", "www.notion.so"})
_NOTION_SITE_SUFFIX = ".notion.site"
_FORBIDDEN_PAGE_CATEGORIES: frozenset[str] = frozenset({"Cc", "Cf", "Zl", "Zp"})
_FORBIDDEN_SECRET_CATEGORIES: frozenset[str] = frozenset({"Cc", "Cf", "Zl", "Zp", "Zs"})
_HEX = frozenset("0123456789abcdef")
_PAGE_ID_LENGTH = 32


def _page_id_error(label: str) -> SchemaBuilderError:
    return SchemaBuilderError(f"{label} must be a 32-hex page id")


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
        page_id = _canonical_page_id(cast(object, self.page_id), "page id")
        _ensure_top_level(cast(object, self.parent_type))
        _ensure_published_to_web(cast(object, self.published_to_web))
        _ensure_duplicate_as_template(cast(object, self.duplicate_as_template))
        _ensure_search_indexing_off(cast(object, self.search_indexing))
        _capture_secret_link(cast(object, self.secret_link))
        _ensure_public_access(cast(object, self.public_access))
        links = _copy_page_ids(cast(object, self.links), "links", "link")
        links = _dedupe_page_ids(links)
        other = _copy_page_ids(
            cast(object, self.other_catalogue_pages),
            "other catalogue pages",
            "other catalogue page",
        )
        _reject_other_catalogue_links(page_id, links, other)
        object.__setattr__(self, "page_id", page_id)
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
    if any(_forbidden_secret_char(char) for char in value):
        raise SchemaBuilderError("secret link must not contain a control character")
    try:
        parsed = urlparse(value)
    except ValueError as exc:
        raise SchemaBuilderError("secret link must be a valid url") from exc
    if parsed.scheme != "https":
        raise SchemaBuilderError("secret link must use https")
    if parsed.username is not None or parsed.password is not None:
        raise SchemaBuilderError("secret link must not contain userinfo")
    if parsed.netloc.endswith(":") or _secret_port(parsed) not in (None, 443):
        raise SchemaBuilderError("secret link port is not allowed")
    host = parsed.hostname
    if not isinstance(host, str) or not _allowed_secret_host(host):
        raise SchemaBuilderError("secret link host is not allowed")
    if parsed.path.strip("/") == "":
        raise SchemaBuilderError("secret link must name a page")
    return value


def _forbidden_secret_char(char: str) -> bool:
    return unicodedata.category(char) in _FORBIDDEN_SECRET_CATEGORIES


def _forbidden_page_char(char: str) -> bool:
    return unicodedata.category(char) in _FORBIDDEN_PAGE_CATEGORIES


def _secret_port(parsed: ParseResult) -> int | None:
    try:
        return parsed.port
    except ValueError as exc:
        raise SchemaBuilderError("secret link port is not allowed") from exc


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
    return tuple(_canonical_page_id(item, singular) for item in value)


def _dedupe_page_ids(page_ids: tuple[str, ...]) -> tuple[str, ...]:
    seen: set[str] = set()
    unique: list[str] = []
    for page_id in page_ids:
        if page_id in seen:
            continue
        seen.add(page_id)
        unique.append(page_id)
    return tuple(unique)


def _canonical_page_id(value: object, label: str) -> str:
    if not isinstance(value, str) or value == "":
        raise _page_id_error(label)
    if any(_forbidden_page_char(char) for char in value):
        raise SchemaBuilderError(f"{label} must not contain a control character")
    if value != value.strip():
        raise _page_id_error(label)
    if "://" in value:
        return _page_id_from_url(value, label)
    page_id = _plain_page_id(value)
    if page_id is None:
        raise _page_id_error(label)
    return page_id


def _plain_page_id(value: str) -> str | None:
    if "-" in value:
        parts = value.split("-")
        if tuple(len(part) for part in parts) != (8, 4, 4, 4, 12):
            return None
        compact = "".join(parts).lower()
    else:
        compact = value.lower()
    if len(compact) == _PAGE_ID_LENGTH and all(char in _HEX for char in compact):
        return compact
    return None


def _page_id_from_url(value: str, label: str) -> str:
    try:
        parsed = urlparse(value)
    except ValueError as exc:
        raise _page_id_error(label) from exc
    if parsed.username is not None or parsed.password is not None:
        raise _page_id_error(label)
    if parsed.netloc.endswith(":") or _page_port(parsed, label) not in (None, 443):
        raise _page_id_error(label)
    if "#" in value:
        raise _page_id_error(label)
    if ";" in value:
        raise _page_id_error(label)
    if "?" in value and not parsed.query:
        raise _page_id_error(label)
    if parsed.query:
        raise _page_id_error(label)
    host = parsed.hostname
    if parsed.scheme != "https" or not isinstance(host, str) or host not in _PAGE_URL_HOSTS:
        raise _page_id_error(label)
    segment = parsed.path.rstrip("/").split("/")[-1]
    page_id = _hex_from_segment(segment)
    if page_id is None:
        raise _page_id_error(label)
    return page_id


def _page_port(parsed: ParseResult, label: str) -> int | None:
    try:
        return parsed.port
    except ValueError as exc:
        raise _page_id_error(label) from exc


def _hex_from_segment(segment: str) -> str | None:
    plain = _exact_undashed(segment)
    if plain is not None:
        return plain
    _head, hyphen, tail = segment.rpartition("-")
    if hyphen == "-" and _exact_undashed(tail) is not None:
        return _exact_undashed(tail)
    return _trailing_uuid(segment)


def _exact_undashed(segment: str) -> str | None:
    compact = segment.lower()
    if len(compact) > _PAGE_ID_LENGTH:
        return None
    if len(compact) < _PAGE_ID_LENGTH:
        return None
    if any(char not in _HEX for char in compact):
        return None
    return compact


def _trailing_uuid(segment: str) -> str | None:
    parts = segment.split("-")
    if len(parts) < 5:
        return None
    tail = parts[-5:]
    if tuple(len(part) for part in tail) != (8, 4, 4, 4, 12):
        return None
    if any(any(char not in "0123456789abcdefABCDEF" for char in part) for part in tail):
        return None
    return "".join(tail).lower()


def _reject_other_catalogue_links(
    page_id: str,
    links: tuple[str, ...],
    other: tuple[str, ...],
) -> None:
    if page_id in other:
        raise SchemaBuilderError(f"page {page_id!r} lists itself as another catalogue")
    blocked = set(other)
    for destination in links:
        if destination in blocked:
            raise SchemaBuilderError(f"link {destination!r} reaches another catalogue")
