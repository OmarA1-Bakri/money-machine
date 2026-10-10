"""Fixture PNGs for the ten listing frames. No network and no Notion."""

from __future__ import annotations

import hashlib
from pathlib import Path

from money_machine.agents.contracts.merchandising import IMAGE_ROLES

_ROOT = Path(__file__).resolve().parent / "listing_screenshots"


def fixture_screenshot_paths() -> dict[str, Path]:
    """One committed PNG per listing-image role."""
    paths = {role: _ROOT / f"{role}.png" for role in IMAGE_ROLES}
    missing = [role for role, path in paths.items() if not path.is_file()]
    if missing:
        raise FileNotFoundError("missing fixture screenshots: " + ", ".join(missing))
    return paths


def fixture_screenshot_hashes() -> frozenset[str]:
    """Allow-list of the committed fixture screenshot bytes."""
    return frozenset(
        hashlib.sha256(path.read_bytes()).hexdigest()
        for path in fixture_screenshot_paths().values()
    )
