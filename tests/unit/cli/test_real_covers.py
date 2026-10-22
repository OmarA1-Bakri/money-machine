"""Cover configuration checks use synthetic URLs and never contact a provider."""

import argparse
import json
from typing import cast

import pytest

from money_machine.application.real_draft_authority import DraftRunRefused
from money_machine.cli import real_draft as module


def test_loads_explicit_distinct_variant_assets(tmp_path):
    value = {name: f"https://assets.example/{name.lower()}.png" for name in module.THEMES}
    path = tmp_path / "covers.json"
    path.write_text(json.dumps(value))
    assert module.load_cover_urls(path) == value


@pytest.mark.parametrize(
    "value",
    [
        {},
        [],
        {"Forest": "fixture://palette/Forest"},
        {name: "https://assets.example/same.png" for name in ("Forest", "Sand", "Slate")},
        {name: "https://assets.example/a.png?token=secret" for name in ("Forest", "Sand", "Slate")},
    ],
)
def test_refuses_incomplete_or_unsafe_configuration(tmp_path, value):
    path = tmp_path / "covers.json"
    path.write_text(json.dumps(value))
    with pytest.raises(DraftRunRefused, match="cover"):
        module.load_cover_urls(path)


@pytest.mark.asyncio
async def test_execution_without_assets_stops_before_credentials_or_database(monkeypatch):
    def forbidden(*_args, **_kwargs):
        pytest.fail("credential/database access before cover input validation")

    monkeypatch.setattr(module, "read_private_credential", forbidden)
    monkeypatch.setattr(module, "create_async_engine", forbidden)
    args = argparse.Namespace(covers_json=None)
    with pytest.raises(DraftRunRefused, match="cover"):
        await module.execute(args, cast(module.Spec, object()))
