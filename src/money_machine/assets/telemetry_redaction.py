"""Refuse a secret, a cookie, or a raw buyer message. Do not send."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from money_machine.domain.events import TelemetryEventName

_ALLOWED_EVENTS = frozenset(item.value for item in TelemetryEventName)
_ALLOWED_PROPERTIES = frozenset(
    {
        "agent_id",
        "attempt",
        "autonomy_mode",
        "duration",
        "environment",
        "error_classification",
        "job_type",
        "listing_id",
        "product_id",
        "status",
        "workflow_id",
    }
)
_SECRET_MARKS = ("secret", "token", "password", "credential", "api_key", "authorization")
_BUYER_NAMES = frozenset(
    {"buyer_message", "raw_buyer_message", "message", "raw_message", "message_body"}
)
_VALUE_LIMIT = 80


class TelemetryRefusal(ValueError):
    """A property name or value must not enter the telemetry payload."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True, slots=True)
class RedactedTelemetry:
    """An in-memory payload. ``sent`` stays false because nothing is dispatched."""

    event: str
    distinct_id: str
    properties: tuple[tuple[str, str], ...]
    sent: bool


def redact_telemetry(
    *,
    event: str,
    distinct_id: str,
    properties: Mapping[str, str],
) -> RedactedTelemetry:
    """Keep the operational property names. Refuse a secret, a cookie, or a buyer message."""
    folded_event = _fold(event)
    if folded_event not in _ALLOWED_EVENTS:
        raise TelemetryRefusal("event")
    if _identity_refused(distinct_id):
        raise TelemetryRefusal("distinct_id")
    rendered: list[tuple[str, str]] = []
    for name, value in properties.items():
        folded = _fold(name)
        code = _refused_name(folded)
        if code is not None:
            raise TelemetryRefusal(code)
        if folded not in _ALLOWED_PROPERTIES:
            raise TelemetryRefusal("property")
        value_code = _refused_value(value)
        if value_code is not None:
            raise TelemetryRefusal(value_code)
        rendered.append((folded, value))
    return RedactedTelemetry(
        event=folded_event,
        distinct_id=distinct_id,
        properties=tuple(rendered),
        sent=False,
    )


def _fold(name: str) -> str:
    return name.strip().casefold().replace("-", "_").replace(" ", "_")


def _identity_refused(distinct_id: str) -> bool:
    folded = distinct_id.casefold()
    return (
        not distinct_id
        or distinct_id == "connected"
        or "@" in distinct_id
        or "://" in distinct_id
        or "sk_" in folded
        or "bearer" in folded
    )


def _refused_name(folded: str) -> str | None:
    if "cookie" in folded:
        return "cookie"
    if folded in _BUYER_NAMES or "buyer_message" in folded:
        return "buyer_message"
    if any(mark in folded for mark in _SECRET_MARKS):
        return "secret"
    return None


def _refused_value(value: object) -> str | None:
    if not isinstance(value, str) or value == "" or len(value) > _VALUE_LIMIT:
        return "property"
    folded = value.casefold()
    if "sk_" in folded or "bearer" in folded:
        return "secret"
    if "cookie=" in folded:
        return "cookie"
    return None
