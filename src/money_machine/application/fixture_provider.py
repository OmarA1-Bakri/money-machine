"""Durable fixture-provider data, separate from the existing build checkpoint engine."""

from __future__ import annotations

import dataclasses
import inspect
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from money_machine.assets.fixture_bundle import write_json
from money_machine.integrations.notion import domain
from money_machine.integrations.notion.fixture_adapter import FixtureNotionAdapter

COLLECTIONS = ("workspaces", "pages", "databases", "blocks", "views", "linked_views")
TYPES = {
    name: value
    for name, value in vars(domain).items()
    if isinstance(value, type) and dataclasses.is_dataclass(value)
}


def encode(value: Any) -> Any:
    if dataclasses.is_dataclass(value):
        return {
            "type": type(value).__name__,
            "fields": {
                field.name: encode(getattr(value, field.name))
                for field in dataclasses.fields(value)
            },
        }
    if isinstance(value, datetime):
        return {"datetime": value.isoformat()}
    if isinstance(value, tuple):
        return {"tuple": [encode(item) for item in value]}
    if isinstance(value, list):
        return [encode(item) for item in value]
    if isinstance(value, dict):
        return {key: encode(item) for key, item in value.items()}
    return value


def decode(value: Any) -> Any:
    if isinstance(value, list):
        return [decode(item) for item in value]
    if not isinstance(value, dict):
        return value
    if set(value) == {"datetime"}:
        return datetime.fromisoformat(value["datetime"])
    if set(value) == {"tuple"}:
        return tuple(decode(item) for item in value["tuple"])
    if set(value) == {"type", "fields"}:
        if value["type"] not in TYPES:
            raise ValueError("unknown fixture provider type")
        return TYPES[value["type"]](**{key: decode(item) for key, item in value["fields"].items()})
    return {key: decode(item) for key, item in value.items()}


def durable_probe(path: Path) -> FixtureNotionAdapter:
    probe = FixtureNotionAdapter()
    if path.exists():
        payload = decode(json.loads(path.read_text()))
        if set(payload) != set(COLLECTIONS):
            raise ValueError("fixture provider snapshot shape")
        for name in COLLECTIONS:
            setattr(probe, name, payload[name])

    def persist():
        write_json(path, encode({name: getattr(probe, name) for name in COLLECTIONS}))

    for name in dir(probe):
        original = getattr(probe, name)
        if name.startswith("_") or not inspect.iscoroutinefunction(original):
            continue

        def bind(method):
            async def wrapped(*args, **kwargs):
                result = await method(*args, **kwargs)
                persist()
                return result

            return wrapped

        setattr(probe, name, bind(original))
    persist()
    return probe
