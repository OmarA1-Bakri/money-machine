"""A spelled-out email is sample data. No browser and no network."""

from __future__ import annotations

from money_machine.assets.screenshot_text import (
    email_rule_matches,
    refuse_fixture_value,
    refuse_rendered_text,
)

_SPELLED = "ceo at acme-corp dot com"


def test_a_spelled_email_rule_matches() -> None:
    assert email_rule_matches(_SPELLED) is True
    assert email_rule_matches("CEO AT ACME-CORP DOT COM") is True
    assert email_rule_matches("ceo@acme-corp.com") is True
    assert email_rule_matches("Meet at the studio") is False
    assert email_rule_matches("x dot com") is False


def test_a_spelled_email_is_refused() -> None:
    assert refuse_rendered_text(_SPELLED) == "sensitive_data"
    assert refuse_fixture_value("Contact ceo at acme-corp dot com today") == "sensitive_data"


def test_a_plain_label_is_allowed() -> None:
    assert refuse_rendered_text("Sage Green") is None
    assert refuse_fixture_value("Meet at the studio") is None
    assert refuse_rendered_text("x dot com") is None
