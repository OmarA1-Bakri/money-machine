"""Telemetry redaction refuses a secret, a cookie, or a raw buyer message."""

from __future__ import annotations

import pytest

from money_machine.assets.telemetry_redaction import TelemetryRefusal, redact_telemetry


def _safe() -> dict[str, str]:
    return {
        "workflow_id": "w-1",
        "job_type": "ResearchCollectionJob",
        "status": "recorded",
        "environment": "fixture",
    }


def test_operational_properties_stay_in_memory() -> None:
    event = redact_telemetry(event="job_completed", distinct_id="fixture-shop", properties=_safe())
    assert event.sent is False
    assert event.event == "job_completed"
    assert ("status", "recorded") in event.properties


def test_a_status_word_is_not_redaction() -> None:
    with pytest.raises(TelemetryRefusal, match="event"):
        redact_telemetry(
            event="connected",
            distinct_id="fixture-shop",
            properties={"status": "connected"},
        )


@pytest.mark.parametrize(
    ("name", "code"),
    [
        ("secret", "secret"),
        ("api_key", "secret"),
        ("cookie", "cookie"),
        ("buyer_message", "buyer_message"),
        ("raw_buyer_message", "buyer_message"),
    ],
)
def test_forbidden_property_names_are_refused(name: str, code: str) -> None:
    with pytest.raises(TelemetryRefusal, match=code):
        redact_telemetry(
            event="job_completed",
            distinct_id="fixture-shop",
            properties={name: "value"},
        )


def test_a_secret_value_under_an_allowed_name_is_refused() -> None:
    with pytest.raises(TelemetryRefusal, match="secret"):
        redact_telemetry(
            event="job_completed",
            distinct_id="fixture-shop",
            properties={"status": "sk_live_example"},
        )


def test_a_cookie_value_under_an_allowed_name_is_refused() -> None:
    with pytest.raises(TelemetryRefusal, match="cookie"):
        redact_telemetry(
            event="job_completed",
            distinct_id="fixture-shop",
            properties={"status": "cookie=session"},
        )
