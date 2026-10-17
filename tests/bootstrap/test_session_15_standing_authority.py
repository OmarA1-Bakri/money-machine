"""The standing-authority key flips only through the proof-gated transition."""

from __future__ import annotations

from pathlib import Path

import pytest

from money_machine.config.loader import load_yaml_model
from money_machine.config.settings import AutonomyConfig
from money_machine.config.standing_authority import (
    StandingAuthorityRefusal,
    record_standing_authority,
)
from money_machine.control.session_15_proof import EARNED_EVIDENCE_KEYS, prove_session_15
from money_machine.domain.enums import AutonomyMode

ROOT = Path(__file__).parents[2]


def test_the_template_keeps_publish_and_spend_off() -> None:
    recorded = record_standing_authority()
    assert recorded.auto_publish is False
    assert recorded.auto_deactivate is False
    assert recorded.auto_multiply is False
    assert recorded.competitor_purchase_enabled is False
    assert recorded.live_checkout_test_enabled is False
    assert all(cap == 0 for cap in recorded.purchase_caps)
    assert recorded.checkout_cap == 0


@pytest.mark.parametrize(
    ("overrides", "code"),
    [
        ({"auto_publish": True}, "publish"),
        ({"auto_deactivate": True}, "deactivate"),
        ({"auto_multiply": True}, "multiply"),
        (
            {
                "competitor_purchase_enabled": True,
                "competitor_purchase_max_each": "1.00",
                "competitor_purchase_monthly_cap": "5.00",
                "external_spend_enabled": True,
            },
            "purchase",
        ),
        (
            {
                "live_checkout_test_enabled": True,
                "live_checkout_test_cap": "1.00",
                "external_spend_enabled": True,
            },
            "checkout",
        ),
        ({}, "live_authority"),
    ],
)
def test_an_enabled_switch_is_refused(overrides: dict[str, object], code: str) -> None:
    with pytest.raises(StandingAuthorityRefusal, match=code):
        record_standing_authority(_enabled(**overrides))


def test_proof_earns_the_standing_authority_key() -> None:
    assert prove_session_15() == EARNED_EVIDENCE_KEYS
    assert "standing_authority_recorded" in EARNED_EVIDENCE_KEYS


def _enabled(**overrides: object) -> AutonomyConfig:
    template = load_yaml_model(ROOT / "config" / "autonomy.example.yaml", AutonomyConfig)
    values = template.model_dump()
    values.update({"mode": AutonomyMode.LIVE, "external_mutations_enabled": True})
    values.update(overrides)
    return AutonomyConfig.model_validate(values)
