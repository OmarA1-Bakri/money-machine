"""Publishing and isolation helpers from Session 06 prompt section 7.

No network, no Notion, no browser.
"""

from __future__ import annotations

from typing import cast

import pytest

from money_machine.integrations.notion.errors import SchemaBuilderError
from money_machine.integrations.notion.publishing import PublishedPage, build_published_page

_LINK = "https://fixture.notion.site/Home"
_PAGE = "a" * 32
_NOTES = "b" * 32
_OTHER = "c" * 32
_TODAY = "d" * 32
_DASHED_OTHER = "cccccccc-cccc-cccc-cccc-cccccccccccc"


def _publish(**overrides: object) -> PublishedPage:
    values: dict[str, object] = {
        "page_id": _PAGE,
        "parent_type": "workspace",
        "published_to_web": True,
        "duplicate_as_template": True,
        "search_indexing": False,
        "secret_link": _LINK,
        "public_access": True,
        "links": (_NOTES,),
        "other_catalogue_pages": (_OTHER,),
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
    assert page.page_id == _PAGE
    assert page.parent_type == "workspace"
    assert page.published_to_web is True
    assert page.duplicate_as_template is True
    assert page.search_indexing is False
    assert page.secret_link == _LINK
    assert page.public_access is True
    assert page.links == (_NOTES,)
    assert page.other_catalogue_pages == (_OTHER,)


def test_page_must_be_top_level() -> None:
    for parent_type in ("page_id", "database_id", "", None, "Workspace", " workspace"):
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
    for value in (None, 1):
        with pytest.raises(SchemaBuilderError, match="secret link must be a string"):
            _publish(secret_link=value)


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


def test_secret_link_rejects_a_double_slash_path() -> None:
    with pytest.raises(SchemaBuilderError, match="must name a page"):
        _publish(secret_link="https://fixture.notion.site//")


def test_secret_link_rejects_a_port_other_than_443() -> None:
    for value in (
        "https://fixture.notion.site:8080/Home",
        "https://fixture.notion.site:80/Home",
        "https://fixture.notion.site:abc/Home",
        "https://fixture.notion.site:99999/Home",
    ):
        with pytest.raises(SchemaBuilderError, match="port is not allowed"):
            _publish(secret_link=value)


def test_secret_link_allows_port_443() -> None:
    page = _publish(secret_link="https://fixture.notion.site:443/Home")
    assert page.secret_link == "https://fixture.notion.site:443/Home"


@pytest.mark.parametrize("code", range(32))
def test_secret_link_rejects_a_control_character(code: int) -> None:
    with pytest.raises(SchemaBuilderError, match="control character"):
        _publish(secret_link=f"https://fix{chr(code)}ture.notion.site/Home")


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
    links = [_NOTES, _TODAY]
    page = _publish(links=links)
    links.append(_OTHER)
    links[0] = "changed"
    assert page.links == (_NOTES, _TODAY)


def test_caller_other_catalogue_list_is_copied() -> None:
    other = [_OTHER]
    page = _publish(other_catalogue_pages=other)
    other.append(_NOTES)
    assert page.other_catalogue_pages == (_OTHER,)


def test_link_order_is_preserved() -> None:
    page = _publish(links=(_NOTES, _TODAY))
    assert page.links == (_NOTES, _TODAY)


def test_a_later_link_to_another_catalogue_is_rejected() -> None:
    with pytest.raises(SchemaBuilderError, match=_OTHER):
        _publish(links=(_NOTES, _OTHER))


def test_isolation_catches_an_uppercase_id() -> None:
    with pytest.raises(SchemaBuilderError, match=_OTHER):
        _publish(links=(_OTHER.upper(),))


def test_isolation_catches_a_dashed_id() -> None:
    with pytest.raises(SchemaBuilderError, match=_OTHER):
        _publish(links=(_DASHED_OTHER,))


def test_isolation_catches_a_notion_so_url() -> None:
    with pytest.raises(SchemaBuilderError, match=_OTHER):
        _publish(links=(f"https://www.notion.so/Title-{_OTHER}",))


def test_page_url_rejects_a_notion_site_host() -> None:
    for value in (
        f"https://notion.site/{_TODAY}",
        f"https://www.notion.site/{_TODAY}",
        f"https://x.notion.site/{_TODAY}",
        f"https://fixture.notion.site/{_TODAY}",
    ):
        with pytest.raises(SchemaBuilderError, match="page id"):
            _publish(page_id=value)
        with pytest.raises(SchemaBuilderError, match="link"):
            _publish(links=(value,))
        with pytest.raises(SchemaBuilderError, match="other catalogue page"):
            _publish(other_catalogue_pages=(value,))


def test_page_reference_rejects_a_non_id() -> None:
    for value in ("Home", "abcd", "https://www.notion.so/Home"):
        with pytest.raises(SchemaBuilderError, match="page id"):
            _publish(page_id=value)
        with pytest.raises(SchemaBuilderError, match="link"):
            _publish(links=(value,))
        with pytest.raises(SchemaBuilderError, match="other catalogue page"):
            _publish(other_catalogue_pages=(value,))


def test_page_rejects_itself_as_another_catalogue_page() -> None:
    with pytest.raises(SchemaBuilderError, match="lists itself"):
        _publish(
            page_id=_PAGE.upper(),
            links=(_NOTES,),
            other_catalogue_pages=(_PAGE,),
        )


def test_other_catalogue_pages_must_be_a_sequence() -> None:
    with pytest.raises(SchemaBuilderError, match="other catalogue pages must be a sequence"):
        _publish(other_catalogue_pages=cast(tuple[str, ...], None))


def test_other_catalogue_page_must_be_a_page_id() -> None:
    with pytest.raises(SchemaBuilderError, match="other catalogue page"):
        _publish(other_catalogue_pages=(" ",))


def test_secret_link_rejects_a_malformed_url() -> None:
    for value in (
        "https://[fixture.notion.site/Home",
        "https://fixture.notion.site]/Home",
    ):
        with pytest.raises(SchemaBuilderError, match="valid url"):
            _publish(secret_link=value)


def test_page_url_rejects_a_malformed_url() -> None:
    value = f"https://[www.notion.so/{_OTHER}"
    with pytest.raises(SchemaBuilderError, match="page id"):
        _publish(page_id=value)
    with pytest.raises(SchemaBuilderError, match="link"):
        _publish(links=(value,))
    with pytest.raises(SchemaBuilderError, match="other catalogue page"):
        _publish(other_catalogue_pages=(value,))


def test_plain_page_id_length_and_hex_are_required() -> None:
    for value in ("a" * 31, "a" * 33, "z" * 32):
        with pytest.raises(SchemaBuilderError, match="page id"):
            _publish(page_id=value)
        with pytest.raises(SchemaBuilderError, match="link"):
            _publish(links=(value,))
        with pytest.raises(SchemaBuilderError, match="other catalogue page"):
            _publish(other_catalogue_pages=(value,))


def test_page_url_must_use_https() -> None:
    with pytest.raises(SchemaBuilderError, match="link"):
        _publish(links=(f"http://www.notion.so/{_TODAY}",))


def test_page_url_host_must_be_allowed() -> None:
    for value in (
        f"https://evil.com/{_TODAY}",
        f"https://notion.so.evil.com/{_TODAY}",
        f"https://evilnotion.so/{_TODAY}",
        f"https://a.b.notion.site/{_TODAY}",
        f"https://app.notion.so/{_TODAY}",
        f"https://www.notion.so./{_TODAY}",
    ):
        with pytest.raises(SchemaBuilderError, match="link"):
            _publish(links=(value,))


def test_isolation_lowercases_an_uppercase_url_id() -> None:
    for value in (
        f"https://www.notion.so/{_OTHER.upper()}",
        f"https://www.notion.so/Title-{_OTHER.upper()}",
    ):
        with pytest.raises(SchemaBuilderError, match=_OTHER):
            _publish(links=(value,))


def test_isolation_lowercases_an_uppercase_slug() -> None:
    dashed = _DASHED_OTHER.upper()
    with pytest.raises(SchemaBuilderError, match=_OTHER):
        _publish(links=(f"https://www.notion.so/{dashed}",))


def test_isolation_keeps_a_trailing_slash_on_the_page_id() -> None:
    with pytest.raises(SchemaBuilderError, match=_OTHER):
        _publish(links=(f"https://www.notion.so/{_OTHER}/",))


def test_page_url_rejects_a_slug_longer_than_32_hex() -> None:
    with pytest.raises(SchemaBuilderError, match="link"):
        _publish(links=(f"https://www.notion.so/{'a' * 33}",))


def test_page_url_rejects_a_non_hex_slug() -> None:
    for value in (
        f"https://www.notion.so/{'z' * 32}",
        "https://www.notion.so/zzzzzzzz-zzzz-zzzz-zzzz-zzzzzzzzzzzz",
    ):
        with pytest.raises(SchemaBuilderError, match="link"):
            _publish(links=(value,))


def test_isolation_catches_a_titled_slug() -> None:
    with pytest.raises(SchemaBuilderError, match=_OTHER):
        _publish(links=(f"https://www.notion.so/Title-{_OTHER}",))


def test_page_url_accepts_a_multi_word_slug() -> None:
    page = _publish(
        page_id=f"https://www.notion.so/My-Page-Title-{_PAGE}",
        links=(f"https://www.notion.so/My-Notes-Title-{_NOTES}",),
        other_catalogue_pages=(f"https://www.notion.so/My-Other-Title-{_OTHER}",),
    )
    assert page.page_id == _PAGE
    assert page.links == (_NOTES,)
    assert page.other_catalogue_pages == (_OTHER,)


def test_isolation_catches_a_nested_page_path() -> None:
    with pytest.raises(SchemaBuilderError, match=_OTHER):
        _publish(links=(f"https://www.notion.so/ws/Title-{_OTHER}",))


def test_page_references_are_stored_in_canonical_form() -> None:
    dashed_notes = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
    page = _publish(
        page_id=_PAGE.upper(),
        links=(dashed_notes,),
        other_catalogue_pages=(f"https://www.notion.so/T-{_OTHER}",),
    )
    assert page.page_id == _PAGE
    assert page.links == (_NOTES,)
    assert page.other_catalogue_pages == (_OTHER,)


def test_page_reference_must_be_a_string() -> None:
    for value in (1, None):
        with pytest.raises(SchemaBuilderError, match="page id"):
            _publish(page_id=value)
        with pytest.raises(SchemaBuilderError, match="link"):
            _publish(links=(value,))
        with pytest.raises(SchemaBuilderError, match="other catalogue page"):
            _publish(other_catalogue_pages=(value,))


def test_page_reference_must_not_be_padded() -> None:
    for value in (" " + _PAGE, _PAGE + " ", " https://www.notion.so/" + _PAGE):
        with pytest.raises(SchemaBuilderError, match="page id"):
            _publish(page_id=value)
        with pytest.raises(SchemaBuilderError, match="link"):
            _publish(links=(value,))
        with pytest.raises(SchemaBuilderError, match="other catalogue page"):
            _publish(other_catalogue_pages=(value,))


def test_secret_link_rejects_del() -> None:
    with pytest.raises(SchemaBuilderError, match="control character"):
        _publish(secret_link="https://fixture.notion.site/\x7fHome")


def test_secret_link_rejects_an_empty_port() -> None:
    with pytest.raises(SchemaBuilderError, match="port is not allowed"):
        _publish(secret_link="https://fixture.notion.site:/Home")


def test_secret_link_rejects_next_line() -> None:
    with pytest.raises(SchemaBuilderError, match="control character"):
        _publish(secret_link="https://fix\u0085ture.notion.site/Home")


def test_secret_link_rejects_u009f() -> None:
    with pytest.raises(SchemaBuilderError, match="control character"):
        _publish(secret_link="https://fix\u009fture.notion.site/Home")


def test_secret_link_rejects_a_zero_width_space() -> None:
    with pytest.raises(SchemaBuilderError, match="control character"):
        _publish(secret_link="https://fix\u200bture.notion.site/Home")


def test_secret_link_rejects_a_trailing_zero_width_space() -> None:
    with pytest.raises(SchemaBuilderError, match="control character"):
        _publish(secret_link="https://fixture.notion.site/Home\u200b")


def test_secret_link_rejects_a_triple_slash_path() -> None:
    with pytest.raises(SchemaBuilderError, match="must name a page"):
        _publish(secret_link="https://fixture.notion.site///")


def test_page_url_rejects_userinfo() -> None:
    with pytest.raises(SchemaBuilderError, match="link"):
        _publish(links=(f"https://user@www.notion.so/{_TODAY}",))


def test_page_url_rejects_an_empty_port() -> None:
    with pytest.raises(SchemaBuilderError, match="link"):
        _publish(links=(f"https://www.notion.so:/{_TODAY}",))


def test_page_url_rejects_a_port() -> None:
    for value in (
        f"https://www.notion.so:80/{_TODAY}",
        f"https://www.notion.so:8080/{_TODAY}",
        f"https://www.notion.so:abc/{_TODAY}",
    ):
        with pytest.raises(SchemaBuilderError, match="link"):
            _publish(links=(value,))


def test_page_url_rejects_a_glued_hex_title() -> None:
    with pytest.raises(SchemaBuilderError, match="link"):
        _publish(links=(f"https://www.notion.so/Dead-beef-{'a' * 24}",))


def test_plain_page_id_dashes_must_be_uuid_layout() -> None:
    for value in ("a" * 4 + "-" + "a" * 28, "cccc-cccccccc-cccc-cccc-cccccccccccc"):
        with pytest.raises(SchemaBuilderError, match="32-hex"):
            _publish(page_id=value)
        with pytest.raises(SchemaBuilderError, match="32-hex"):
            _publish(links=(value,))
        with pytest.raises(SchemaBuilderError, match="32-hex"):
            _publish(other_catalogue_pages=(value,))


def test_isolation_catches_an_uppercase_dashed_id() -> None:
    with pytest.raises(SchemaBuilderError, match=_OTHER):
        _publish(links=("CCCCCCCC-CCCC-CCCC-CCCC-CCCCCCCCCCCC",))


def test_isolation_catches_a_titled_uuid() -> None:
    with pytest.raises(SchemaBuilderError, match=_OTHER):
        _publish(links=("https://www.notion.so/My-Title-cccccccc-cccc-cccc-cccc-cccccccccccc",))


def test_page_url_rejects_a_bad_uuid_layout() -> None:
    for value in (
        "https://www.notion.so/T-cccc-cccccccc-cccc-cccc-cccccccccccc",
        "https://www.notion.so/T-a-b-c-d-e",
        "https://notion.so/Title-1234abcd-1234-abcd-1234-abcd1234abc",
    ):
        with pytest.raises(SchemaBuilderError, match="32-hex"):
            _publish(page_id=value)
        with pytest.raises(SchemaBuilderError, match="32-hex"):
            _publish(links=(value,))
        with pytest.raises(SchemaBuilderError, match="32-hex"):
            _publish(other_catalogue_pages=(value,))


def test_page_url_port_443_is_canonical() -> None:
    with pytest.raises(SchemaBuilderError, match=_OTHER):
        _publish(links=(f"https://www.notion.so:443/{_OTHER}",))


@pytest.mark.parametrize(
    "value",
    [
        f" https://www.notion.so/{_TODAY}",
        f"\thttps://www.notion.so/T-{_TODAY}",
        f"https://www.notion.so/{_TODAY}\n",
        f"\rhttps://www.notion.so/{_TODAY}",
        f"https://www.notion.so/{_TODAY}\r",
        f"https://www.notion.so/\r{_TODAY}",
        f"\x1fhttps://www.notion.so/{_TODAY}",
        f"https://www.notion.so/{_TODAY}\x1f",
        f"https://www.notion.so/\x1f{_TODAY}",
    ],
)
def test_page_url_rejects_padding(value: str) -> None:
    with pytest.raises(SchemaBuilderError, match="page id"):
        _publish(page_id=value)
    with pytest.raises(SchemaBuilderError, match="link"):
        _publish(links=(value,))
    with pytest.raises(SchemaBuilderError, match="other catalogue page"):
        _publish(other_catalogue_pages=(value,))


@pytest.mark.parametrize(
    "char",
    ["\u00ad", "\u200b", "\u202e", "\u2060", "\ufeff", "\x7f", "\u2028", "\u2029"],
)
def test_secret_link_rejects_a_format_character(char: str) -> None:
    with pytest.raises(SchemaBuilderError, match="control character"):
        _publish(secret_link=f"https://fix{char}ture.notion.site/Home")


@pytest.mark.parametrize("char", ["\u00a0", "\u2002", "\u2003", "\u202f", "\u3000"])
def test_secret_link_rejects_a_space_separator(char: str) -> None:
    with pytest.raises(SchemaBuilderError, match="control character"):
        _publish(secret_link=f"https://fixture.notion.site/Ho{char}me")


def test_notion_so_page_url_is_canonical() -> None:
    page = _publish(
        page_id=f"https://notion.so/{_PAGE}",
        links=(f"https://notion.so/{_NOTES}",),
        other_catalogue_pages=(f"https://notion.so/{_OTHER}",),
    )
    assert page.page_id == _PAGE
    assert page.links == (_NOTES,)
    assert page.other_catalogue_pages == (_OTHER,)


@pytest.mark.parametrize("query", [f"p={_OTHER}", "pvs=4", f"v={_OTHER}", "a=b"])
def test_page_url_rejects_a_query(query: str) -> None:
    value = f"https://www.notion.so/{_TODAY}?{query}"
    with pytest.raises(SchemaBuilderError, match="page id"):
        _publish(page_id=value)
    with pytest.raises(SchemaBuilderError, match="link"):
        _publish(links=(value,))
    with pytest.raises(SchemaBuilderError, match="other catalogue page"):
        _publish(other_catalogue_pages=(value,))


@pytest.mark.parametrize("suffix", ["#section", "#"])
def test_page_url_rejects_a_fragment(suffix: str) -> None:
    value = f"https://www.notion.so/{_TODAY}{suffix}"
    with pytest.raises(SchemaBuilderError, match="page id"):
        _publish(page_id=value)
    with pytest.raises(SchemaBuilderError, match="link"):
        _publish(links=(value,))
    with pytest.raises(SchemaBuilderError, match="other catalogue page"):
        _publish(other_catalogue_pages=(value,))


@pytest.mark.parametrize("suffix", [";p=1", ";"])
def test_page_url_rejects_parameters(suffix: str) -> None:
    value = f"https://www.notion.so/{_TODAY}{suffix}"
    with pytest.raises(SchemaBuilderError, match="page id"):
        _publish(page_id=value)
    with pytest.raises(SchemaBuilderError, match="link"):
        _publish(links=(value,))
    with pytest.raises(SchemaBuilderError, match="other catalogue page"):
        _publish(other_catalogue_pages=(value,))


def test_page_url_rejects_an_empty_query() -> None:
    value = f"https://www.notion.so/{_TODAY}?"
    with pytest.raises(SchemaBuilderError, match="page id"):
        _publish(page_id=value)
    with pytest.raises(SchemaBuilderError, match="link"):
        _publish(links=(value,))
    with pytest.raises(SchemaBuilderError, match="other catalogue page"):
        _publish(other_catalogue_pages=(value,))


@pytest.mark.parametrize(
    "char",
    [
        "\x00",
        "\t",
        "\n",
        "\x1f",
        "\x7f",
        "\x85",
        "\x9f",
        "\u00ad",
        "\u200b",
        "\u202e",
        "\u2060",
        "\ufeff",
        "\u2028",
        "\u2029",
    ],
)
def test_page_reference_rejects_a_forbidden_character(char: str) -> None:
    leading = f"{char}https://www.notion.so/{_TODAY}"
    trailing = f"https://www.notion.so/{_TODAY}{char}"
    titled = f"https://www.notion.so/T{char}x-{_TODAY}"
    plain = _TODAY[:16] + char + _TODAY[16:]
    for value in (leading, trailing, titled, plain):
        with pytest.raises(SchemaBuilderError, match="control character"):
            _publish(page_id=value)
        with pytest.raises(SchemaBuilderError, match="control character"):
            _publish(links=(value,))
        with pytest.raises(SchemaBuilderError, match="control character"):
            _publish(other_catalogue_pages=(value,))


def test_forbidden_characters_are_checked_before_padding() -> None:
    value = f"\thttps://www.notion.so/T\x00-{_TODAY}"
    with pytest.raises(SchemaBuilderError, match="control character"):
        _publish(page_id=value)
    with pytest.raises(SchemaBuilderError, match="control character"):
        _publish(links=(value,))
    with pytest.raises(SchemaBuilderError, match="control character"):
        _publish(other_catalogue_pages=(value,))


def test_forbidden_check_reads_characters_strip_would_remove() -> None:
    for value in (
        f"\thttps://www.notion.so/{_TODAY}",
        f"https://www.notion.so/{_TODAY}\n",
        f"\u00a0{_TODAY}",
        f"{_TODAY}\u3000",
    ):
        with pytest.raises(SchemaBuilderError, match="control character"):
            _publish(page_id=value)


def test_page_reference_rejects_a_leading_control_character() -> None:
    value = f"\x00https://www.notion.so/{_TODAY}"
    with pytest.raises(SchemaBuilderError, match="control character"):
        _publish(page_id=value)
    with pytest.raises(SchemaBuilderError, match="control character"):
        _publish(links=(value,))
    with pytest.raises(SchemaBuilderError, match="control character"):
        _publish(other_catalogue_pages=(value,))


def test_page_reference_rejects_a_leading_control_run() -> None:
    value = f"\x00\x00https://www.notion.so/{_TODAY}"
    with pytest.raises(SchemaBuilderError, match="control character"):
        _publish(page_id=value)
    with pytest.raises(SchemaBuilderError, match="control character"):
        _publish(links=(value,))
    with pytest.raises(SchemaBuilderError, match="control character"):
        _publish(other_catalogue_pages=(value,))


@pytest.mark.parametrize("char", ["\u00a0", "\u3000"])
@pytest.mark.parametrize("field", ["page_id", "links", "other_catalogue_pages"])
def test_page_reference_rejects_a_space_separator(char: str, field: str) -> None:
    titled = f"https://www.notion.so/T{char}x-{_TODAY}"
    plain = _TODAY[:16] + char + _TODAY[16:]
    for value in (titled, plain):
        payload: object = value if field == "page_id" else (value,)
        with pytest.raises(SchemaBuilderError, match="control character"):
            _publish(**{field: payload})


def test_deduped_link_order_is_preserved() -> None:
    dashed_notes = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
    page = _publish(links=(_TODAY, _NOTES, dashed_notes, _TODAY))
    assert page.links == (_TODAY, _NOTES)


def test_page_reference_rejects_g() -> None:
    value = "g" + "a" * 31
    with pytest.raises(SchemaBuilderError, match="page id"):
        _publish(page_id=value)
    with pytest.raises(SchemaBuilderError, match="link"):
        _publish(links=(value,))
    with pytest.raises(SchemaBuilderError, match="other catalogue page"):
        _publish(other_catalogue_pages=(value,))


def test_secret_link_rejects_a_line_separator() -> None:
    with pytest.raises(SchemaBuilderError, match="control character"):
        _publish(secret_link="https://fix\u2028ture.notion.site/Home")


def test_secret_link_rejects_a_paragraph_separator() -> None:
    with pytest.raises(SchemaBuilderError, match="control character"):
        _publish(secret_link="https://fix\u2029ture.notion.site/Home")


def test_repeated_link_forms_are_stored_once() -> None:
    dashed_notes = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
    page = _publish(
        links=(
            _NOTES,
            dashed_notes,
            f"https://www.notion.so/Title-{_NOTES}",
        )
    )
    assert page.links == (_NOTES,)
