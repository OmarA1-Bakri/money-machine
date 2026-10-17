"""Select the fixture provider adapters and refuse a live connection.

The selector constructs the Etsy and Notion fixture adapters and calls them.
An api, browser, combined, or live mode raises before any adapter is built.
No credential, ``.env``, cookie, or browser profile is read. No socket is opened.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from money_machine.integrations.etsy.fixture_adapter import FixtureEtsyAdapter
from money_machine.integrations.notion.fixture_adapter import FixtureNotionAdapter

_FIXTURE = "fixture"


class ProviderConnectionRefusal(ValueError):
    """A live provider adapter was requested."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class ProviderConnections:
    """The selected adapters. A live call did not run and no credential was read."""

    etsy: str
    notion: str
    listing_count: int
    notion_connected: bool
    live_call: bool
    credential_read: bool


def select_provider_connections(
    *,
    etsy_mode: str = _FIXTURE,
    notion_mode: str = _FIXTURE,
) -> ProviderConnections:
    """Return the fixture adapters. Any other mode is a live connection and is refused."""
    if etsy_mode.strip().casefold() != _FIXTURE:
        raise ProviderConnectionRefusal("live_etsy")
    if notion_mode.strip().casefold() != _FIXTURE:
        raise ProviderConnectionRefusal("live_notion")
    etsy = FixtureEtsyAdapter()
    notion = FixtureNotionAdapter()
    if type(etsy) is not FixtureEtsyAdapter or type(notion) is not FixtureNotionAdapter:
        raise ProviderConnectionRefusal("live_adapter")
    listing_count, connected = asyncio.run(_probe(etsy, notion))
    if listing_count < 1 or connected is not True:
        raise ProviderConnectionRefusal("fixture_empty")
    return ProviderConnections(
        etsy=_FIXTURE,
        notion=_FIXTURE,
        listing_count=listing_count,
        notion_connected=True,
        live_call=False,
        credential_read=False,
    )


async def _probe(etsy: FixtureEtsyAdapter, notion: FixtureNotionAdapter) -> tuple[int, bool]:
    listings = await etsy.search_listings("planner", max_results=1)
    status = await notion.connection_status()
    return len(listings), status.get("connected") is True
