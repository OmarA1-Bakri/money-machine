from __future__ import annotations

import json
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast

import pytest

from money_machine.application.services.research_service import ResearchService

FIXTURE = Path("tests/fixtures/research/valid_packet_30.json")
NOW = datetime(2026, 8, 9, 12, tzinfo=UTC)


def _payload() -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(FIXTURE.read_text(encoding="utf-8")))


def _write(tmp_path: Path, payload: dict[str, Any]) -> Path:
    path = tmp_path / "packet.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


@pytest.mark.parametrize("row_count", [25, 30, 40])
def test_import_accepts_inclusive_packet_sizes(tmp_path: Path, row_count: int) -> None:
    payload = _payload()
    observations = cast(list[dict[str, Any]], payload["observations"])
    del observations[row_count:]
    while len(observations) < row_count:
        clone = deepcopy(observations[len(observations) % 30])
        clone["observation_id"] = f"OBS-{len(observations) + 1:03d}"
        clone["evidence"]["evidence_id"] = f"EVD-{len(observations) + 1:03d}"
        clone["evidence"]["content_sha256"] = f"{len(observations) + 1:064x}"
        observations.append(clone)
    packet = ResearchService().import_packet(_write(tmp_path, payload), now=NOW)
    assert len(packet.observations) == row_count
    assert packet.packet_id == f"RPK-{packet.packet_sha256[:24]}"


@pytest.mark.parametrize("row_count", [24, 41])
def test_import_rejects_out_of_range_packet_sizes(tmp_path: Path, row_count: int) -> None:
    payload = _payload()
    observations = cast(list[dict[str, Any]], payload["observations"])
    if row_count == 24:
        del observations[24:]
    else:
        while len(observations) < row_count:
            clone = deepcopy(observations[0])
            clone["observation_id"] = f"OBS-{len(observations) + 1:03d}"
            clone["evidence"]["evidence_id"] = f"EVD-{len(observations) + 1:03d}"
            clone["evidence"]["content_sha256"] = f"{len(observations) + 1:064x}"
            observations.append(clone)
    with pytest.raises(ValueError, match=r"25.*40"):
        ResearchService().import_packet(_write(tmp_path, payload), now=NOW)


def test_import_rejects_duplicate_observation_ids(tmp_path: Path) -> None:
    payload = _payload()
    observations = cast(list[dict[str, Any]], payload["observations"])
    observations[1]["observation_id"] = observations[0]["observation_id"]
    with pytest.raises(ValueError, match="duplicate observation_id"):
        ResearchService().import_packet(_write(tmp_path, payload), now=NOW)


def test_import_rejects_conflicting_evidence_for_same_content_hash(tmp_path: Path) -> None:
    payload = _payload()
    observations = cast(list[dict[str, Any]], payload["observations"])
    observations[1]["evidence"]["content_sha256"] = observations[0]["evidence"]["content_sha256"]
    with pytest.raises(ValueError, match="conflicting evidence"):
        ResearchService().import_packet(_write(tmp_path, payload), now=NOW)


@pytest.mark.parametrize("freshness", ["stale", "unknown"])
def test_import_rejects_non_current_evidence(tmp_path: Path, freshness: str) -> None:
    payload = _payload()
    payload["observations"][0]["evidence"]["freshness_status"] = freshness
    with pytest.raises(ValueError, match="current"):
        ResearchService().import_packet(_write(tmp_path, payload), now=NOW)


def test_import_rejects_future_evidence(tmp_path: Path) -> None:
    payload = _payload()
    payload["observations"][0]["evidence"]["observed_at"] = (NOW + timedelta(seconds=1)).isoformat()
    with pytest.raises(ValueError, match="future"):
        ResearchService().import_packet(_write(tmp_path, payload), now=NOW)


@pytest.mark.parametrize("price,currency", [["12.00", "usd"], ["12.00", "US"], [None, "USD"]])
def test_import_rejects_malformed_currency(
    tmp_path: Path, price: str | None, currency: str
) -> None:
    payload = _payload()
    payload["observations"][0]["price"] = price
    payload["observations"][0]["currency"] = currency
    with pytest.raises(ValueError, match="currency"):
        ResearchService().import_packet(_write(tmp_path, payload), now=NOW)


@pytest.mark.parametrize("value", ["-0.1", "10.1"])
def test_import_rejects_qualification_inputs_outside_scale(tmp_path: Path, value: str) -> None:
    payload = _payload()
    payload["observations"][0]["qualification_inputs"]["demand"] = value
    with pytest.raises(ValueError, match=r"0\.\.10"):
        ResearchService().import_packet(_write(tmp_path, payload), now=NOW)


def test_import_rejects_mismatched_caller_hash_and_identity(tmp_path: Path) -> None:
    payload = _payload()
    payload["packet_sha256"] = "f" * 64
    payload["packet_id"] = "RPK-caller-controlled"
    with pytest.raises(ValueError, match="packet_sha256"):
        ResearchService().import_packet(_write(tmp_path, payload), now=NOW)


def test_import_rejects_unknown_packet_root_fields_before_identity(tmp_path: Path) -> None:
    payload = _payload()
    payload["unreviewed"] = True
    payload["packet_sha256"] = "f" * 64

    with pytest.raises(ValueError, match="unknown packet root fields: unreviewed"):
        ResearchService().import_packet(_write(tmp_path, payload), now=NOW)
