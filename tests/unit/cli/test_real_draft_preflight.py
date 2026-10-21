"""Read-only preflight must never mistake supplied scope for provider proof."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).parents[3]


def invoke(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts/real_draft_preflight.py"), *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )


def test_preflight_preserves_zero_effects_and_unknown_provider_identity() -> None:
    result = invoke("--run-id", "real-test", "--product-id", str(uuid4()))
    assert result.returncode == 0, result.stderr
    body = json.loads(result.stdout)
    assert body["provider_verification_performed"] is False
    assert body["effects_performed"] is False
    assert body["publishing_enabled"] is False
    assert body["spending_enabled"] is False
    assert set(body["blockers"]) == {
        "PROVIDER_VERIFICATION_NOT_PERFORMED",
        "NOTION_PARENT_UNVERIFIED",
        "ETSY_NUMERIC_SHOP_ID_UNVERIFIED",
    }


def test_supplied_ids_are_not_reported_as_provider_verification() -> None:
    parent = uuid4()
    result = invoke(
        "--run-id",
        "real-test",
        "--product-id",
        str(uuid4()),
        "--verified-shop-id",
        "123",
        "--notion-parent-id",
        str(parent),
    )
    assert result.returncode == 0, result.stderr
    body = json.loads(result.stdout)
    assert body["provider_verification_performed"] is False
    assert body["effects_performed"] is False
    assert body["authority"]["verified_shop_id"] == 123
    assert body["authority"]["verified_notion_parent_id"] == str(parent)
    assert body["blockers"] == ["PROVIDER_VERIFICATION_NOT_PERFORMED"]


def test_preflight_rejects_publication_override() -> None:
    result = invoke("--run-id", "real-test", "--product-id", str(uuid4()), "--publish")
    assert result.returncode == 2
    assert "unrecognized arguments" in result.stderr


def test_preflight_refuses_malformed_product_without_echoing_input() -> None:
    result = invoke("--run-id", "real-test", "--product-id", "invalid-sensitive-input")
    assert result.returncode == 2
    assert "invalid-sensitive-input" not in result.stderr
