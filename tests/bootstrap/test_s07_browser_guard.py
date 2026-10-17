"""Test 47: navigation guard refusals perform zero clicks. Navigate wiring is later."""

from __future__ import annotations

import pytest

from money_machine.cli.notion_sandbox_guard import (
    SANDBOX_PARENT_PAGE_ID,
    SANDBOX_SPACE_ID,
    PageView,
)
from money_machine.cli.s07_navigation_guard import (
    NavigationGuardError,
    NavigationRequest,
    SandboxSessionSignedOut,
    guard_navigation,
)

PAGE = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
FOREIGN = "ffffffff-ffff-ffff-ffff-ffffffffffff"
SANDBOX_URL = f"https://www.notion.so/{PAGE.replace('-', '')}"
PUBLIC_URL = f"https://example.notion.site/{PAGE.replace('-', '')}"


def _page(
    *,
    url: str = SANDBOX_URL,
    space_id: str = SANDBOX_SPACE_ID,
    parent_id: str = SANDBOX_PARENT_PAGE_ID,
    page_id: str = PAGE,
) -> PageView:
    return PageView(
        page_id=page_id,
        parent_id=parent_id,
        space_id=space_id,
        url=url,
        archived=False,
        parent_type="page_id",
    )


def _request(
    role: str, page: PageView | None, *, signed_in: bool, listed: frozenset[str]
) -> NavigationRequest:
    return NavigationRequest(
        role=role,
        signed_in=signed_in,
        listed_urls=listed,
        expected_page_id=PAGE,
        page=page,
    )


def _refused(request: NavigationRequest, error: type[Exception]) -> None:
    clicks: list[str] = []
    with pytest.raises(error):
        guard_navigation(request, lambda: clicks.append("click"))
    assert clicks == []


def test_47_foreign_space_chain_redirect_unlisted_signed_out_and_anonymous() -> None:
    """Each bad page raises before click. A matching sandbox page clicks once."""
    listed = frozenset({SANDBOX_URL, PUBLIC_URL})
    good = _page()
    clicks: list[str] = []
    guard_navigation(
        _request("sandbox", good, signed_in=True, listed=listed), lambda: clicks.append("click")
    )
    assert clicks == ["click"]

    _refused(
        _request("sandbox", _page(space_id=FOREIGN), signed_in=True, listed=listed),
        NavigationGuardError,
    )
    _refused(
        _request("sandbox", _page(parent_id=FOREIGN), signed_in=True, listed=listed),
        NavigationGuardError,
    )
    redirected = f"https://www.notion.so/{FOREIGN.replace('-', '')}"
    _refused(
        _request(
            "sandbox",
            _page(url=redirected, page_id=FOREIGN),
            signed_in=True,
            listed=frozenset({redirected}),
        ),
        NavigationGuardError,
    )
    _refused(
        _request("sandbox", good, signed_in=True, listed=frozenset()),
        NavigationGuardError,
    )
    _refused(
        _request("sandbox", good, signed_in=False, listed=listed),
        SandboxSessionSignedOut,
    )
    _refused(
        _request("anonymous", _page(url=PUBLIC_URL), signed_in=True, listed=listed),
        NavigationGuardError,
    )
    evil = f"https://evilnotion.site/{PAGE.replace('-', '')}"
    _refused(
        _request(
            "anonymous",
            _page(url=evil),
            signed_in=False,
            listed=frozenset({evil}),
        ),
        NavigationGuardError,
    )

    public_clicks: list[str] = []
    guard_navigation(
        _request("anonymous", _page(url=PUBLIC_URL), signed_in=False, listed=listed),
        lambda: public_clicks.append("click"),
    )
    assert public_clicks == ["click"]
