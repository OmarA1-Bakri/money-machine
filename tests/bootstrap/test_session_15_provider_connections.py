"""The provider-connection key flips only through the proof-gated transition."""

from __future__ import annotations

import pytest

from money_machine.control.session_15_proof import EARNED_EVIDENCE_KEYS, prove_session_15
from money_machine.integrations.provider_connections import (
    ProviderConnectionRefusal,
    select_provider_connections,
)


def test_fixture_adapters_are_selected() -> None:
    selected = select_provider_connections()
    assert selected.etsy == "fixture"
    assert selected.notion == "fixture"
    assert selected.listing_count >= 1
    assert selected.notion_connected is True
    assert selected.live_call is False
    assert selected.credential_read is False


@pytest.mark.parametrize("mode", ["api", "browser", "combined", "live", ""])
def test_a_live_etsy_adapter_is_refused(mode: str) -> None:
    with pytest.raises(ProviderConnectionRefusal, match="live_etsy"):
        select_provider_connections(etsy_mode=mode)


@pytest.mark.parametrize("mode", ["api", "browser", "combined", "live", ""])
def test_a_live_notion_adapter_is_refused(mode: str) -> None:
    with pytest.raises(ProviderConnectionRefusal, match="live_notion"):
        select_provider_connections(notion_mode=mode)


def test_proof_earns_the_provider_connection_key() -> None:
    assert prove_session_15() == EARNED_EVIDENCE_KEYS
    assert "provider_connections_fail_closed" in EARNED_EVIDENCE_KEYS
    assert "deployed_state_checked" in EARNED_EVIDENCE_KEYS
