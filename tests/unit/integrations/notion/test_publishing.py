"""Publishing and isolation helpers from Session 06 prompt section 7.

No network, no Notion, no browser.
"""

from __future__ import annotations

from typing import cast

import pytest

from money_machine.integrations.notion.errors import SchemaBuilderError
from money_machine.integrations.notion.publishing import PublishedPage, build_published_page

_LINK = "https://fixture.notion.site/Home"


def _publish(**overrides: object) -> PublishedPage:
    values: dict[str, object] = {
        "page_id": "Home",
        "parent_type": "workspace",
        "published_to_web": True,
        "duplicate_as_template": True,
        "search_indexing": False,
        "secret_link": _LINK,
        "public_access": True,
        "links": ("Notes",),
        "other_catalogue_pages": ("OtherHome",),
    }
    values.update(overrides)
    return build_published_page(
        values["page_id"],
        values["parent_type"],
        values["published_to_web"],
        values["duplicate_as_template"],
        values["search_indexing"],
        values["secret_link"],
        values["public_access"],
        values["links"],
        values["other_catalogue_pages"],
    )


def test_published_page_records_the_settings() -> None:
    page = _publish()
    assert page.page_id == "Home"
    assert page.parent_type == "workspace"
    assert page.published_to_web is True
    assert page.duplicate_as_template is True
    assert page.search_indexing is False
    assert page.secret_link == _LINK
    assert page.public_access is True
    assert page.links == ("Notes",)
    assert page.other_catalogue_pages == ("OtherHome",)


def test_page_must_be_top_level() -> None:
    for parent_type in ("page_id", "database_id", "", None):
        with pytest.raises(SchemaBuilderError, match="top level"):
            _publish(parent_type=parent_type)


def test_page_must_be_published_to_web() -> None:
    for value in (False, 1, None):
        with pytest.raises(SchemaBuilderError, match="published to web"):
            _publish(published_to_web=value)


def test_duplicate_as_template_must_be_on() -> None:
    for value in (False, 1, None):
        with pytest.raises(SchemaBuilderError, match="duplicate as template"):
            _publish(duplicate_as_template=value)


def test_search_indexing_must_be_off() -> None:
    for value in (True, 0, None):
        with pytest.raises(SchemaBuilderError, match="search indexing"):
            _publish(search_indexing=value)


def test_public_access_must_be_verified() -> None:
    for value in (False, 1, None):
        with pytest.raises(SchemaBuilderError, match="public access"):
            _publish(public_access=value)


def test_page_id_must_be_present() -> None:
    with pytest.raises(SchemaBuilderError, match="page id"):
        _publish(page_id=" ")


def test_secret_link_must_be_a_string() -> None:
    with pytest.raises(SchemaBuilderError, match="secret link must be a string"):
        _publish(secret_link=None)


def test_secret_link_must_be_present() -> None:
    for value in ("", " " + _LINK, _LINK + " "):
        with pytest.raises(SchemaBuilderError, match="secret link must be present"):
            _publish(secret_link=value)


def test_secret_link_must_use_https() -> None:
    with pytest.raises(SchemaBuilderError, match="https"):
        _publish(secret_link="http://fixture.notion.site/Home")


def test_secret_link_must_not_contain_userinfo() -> None:
    with pytest.raises(SchemaBuilderError, match="userinfo"):
        _publish(secret_link="https://user@fixture.notion.site/Home")


def test_secret_link_host_must_be_allowed() -> None:
    for value in (
        "https://evil.com/Home",
        "https://evil.notion.so/Home",
        "https:///Home",
    ):
        with pytest.raises(SchemaBuilderError, match="host is not allowed"):
            _publish(secret_link=value)


@pytest.mark.parametrize(
    "host",
    ["notion.so", "www.notion.so", "notion.site", "fixture.notion.site", "www.notion.site"],
)
def test_secret_link_host_is_allowed(host: str) -> None:
    page = _publish(secret_link=f"https://{host}/Home")
    assert page.secret_link == f"https://{host}/Home"


def test_secret_link_rejects_a_nested_notion_site_label() -> None:
    with pytest.raises(SchemaBuilderError, match="host is not allowed"):
        _publish(secret_link="https://a.b.notion.site/Home")


def test_secret_link_rejects_an_empty_notion_site_label() -> None:
    with pytest.raises(SchemaBuilderError, match="host is not allowed"):
        _publish(secret_link="https://.notion.site/Home")


def test_secret_link_must_name_a_page() -> None:
    for value in ("https://fixture.notion.site", "https://fixture.notion.site/"):
        with pytest.raises(SchemaBuilderError, match="must name a page"):
            _publish(secret_link=value)


def test_links_must_be_a_sequence() -> None:
    with pytest.raises(SchemaBuilderError, match="links must be a sequence"):
        _publish(links=None)


def test_links_reject_a_string() -> None:
    with pytest.raises(SchemaBuilderError, match="links must be a sequence"):
        _publish(links="Home")


def test_link_must_be_a_page_id() -> None:
    with pytest.raises(SchemaBuilderError, match="link"):
        _publish(links=(" ",))


def test_caller_link_list_is_copied() -> None:
    links = ["Notes", "Today"]
    page = _publish(links=links)
    links.append("OtherHome")
    links[0] = "Changed"
    assert page.links == ("Notes", "Today")


def test_caller_other_catalogue_list_is_copied() -> None:
    other = ["OtherHome"]
    page = _publish(other_catalogue_pages=other)
    other.append("Notes")
    assert page.other_catalogue_pages == ("OtherHome",)


def test_link_order_is_preserved() -> None:
    page = _publish(links=("Notes", "Today"))
    assert page.links == ("Notes", "Today")


def test_a_later_link_to_another_catalogue_is_rejected() -> None:
    with pytest.raises(SchemaBuilderError, match="OtherHome"):
        _publish(links=("Notes", "OtherHome"))


def test_other_catalogue_pages_must_be_a_sequence() -> None:
    with pytest.raises(SchemaBuilderError, match="other catalogue pages must be a sequence"):
        _publish(other_catalogue_pages=cast(tuple[str, ...], None))


def test_other_catalogue_page_must_be_a_page_id() -> None:
    with pytest.raises(SchemaBuilderError, match="other catalogue page"):
        _publish(other_catalogue_pages=(" ",))
