"""Fixture/local-only research packet admission."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Annotated, cast

from pydantic import Field

from money_machine.domain.enums import QualificationDimension
from money_machine.domain.models.research import ResearchObservation, ResearchPacket
from money_machine.domain.value_objects import FrozenModel, canonical_sha256

_PACKET_ROOT_FIELDS = frozenset({"observations", "packet_id", "packet_sha256"})

_CURRENCY = re.compile(r"^[A-Z]{3}$")
_DIMENSIONS = frozenset(QualificationDimension)


class _PacketBody(FrozenModel):
    observations: Annotated[tuple[ResearchObservation, ...], Field(min_length=25, max_length=40)]


class ResearchService:
    """Admit a bounded packet without performing provider or marketplace I/O."""

    def import_packet(self, path: Path, *, now: datetime) -> ResearchPacket:
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("now must be timezone-aware")
        raw = self._load_mapping(path)
        unknown_fields = sorted(set(raw) - _PACKET_ROOT_FIELDS)
        if unknown_fields:
            raise ValueError(f"unknown packet root fields: {', '.join(unknown_fields)}")
        raw_observations = raw.get("observations")
        if not isinstance(raw_observations, list):
            raise ValueError("observations must be a JSON array")
        observation_values = cast(list[object], raw_observations)
        if not 25 <= len(observation_values) <= 40:
            raise ValueError("research packet must contain 25..40 observations")

        observations = tuple(self._parse_observation(value) for value in observation_values)
        self._validate_observations(observations, now=now)
        packet_sha256 = canonical_sha256(_PacketBody(observations=observations))
        packet_id = f"RPK-{packet_sha256[:24]}"

        supplied_hash = raw.get("packet_sha256")
        if supplied_hash is not None and supplied_hash != packet_sha256:
            raise ValueError("supplied packet_sha256 differs from canonical recomputation")
        supplied_id = raw.get("packet_id")
        if supplied_id is not None and supplied_id != packet_id:
            raise ValueError("supplied packet_id differs from derived identity")

        return ResearchPacket(
            packet_id=packet_id,
            imported_at=now,
            observations=observations,
            packet_sha256=packet_sha256,
        )

    @staticmethod
    def _load_mapping(path: Path) -> Mapping[str, object]:
        try:
            value = cast(object, json.loads(path.read_text(encoding="utf-8")))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise ValueError(f"invalid research packet: {path}") from exc
        if not isinstance(value, Mapping):
            raise ValueError("research packet root must be a JSON object")
        mapping = cast(Mapping[object, object], value)
        if not all(isinstance(key, str) for key in mapping):
            raise ValueError("research packet keys must be strings")
        return {cast(str, key): nested for key, nested in mapping.items()}

    @staticmethod
    def _parse_observation(value: object) -> ResearchObservation:
        try:
            return ResearchObservation.model_validate_json(
                json.dumps(value, ensure_ascii=False, separators=(",", ":")), strict=True
            )
        except (TypeError, ValueError) as exc:
            raise ValueError("malformed research observation") from exc

    @staticmethod
    def _validate_observations(
        observations: tuple[ResearchObservation, ...], *, now: datetime
    ) -> None:
        observation_ids: set[str] = set()
        evidence_by_hash: dict[str, bytes] = {}
        for observation in observations:
            if observation.observation_id in observation_ids:
                raise ValueError(f"duplicate observation_id: {observation.observation_id}")
            observation_ids.add(observation.observation_id)

            evidence = observation.evidence
            if evidence.freshness_status != "current":
                raise ValueError("research evidence must be current")
            if evidence.observed_at > now:
                raise ValueError("research evidence cannot be from the future")

            evidence_bytes = evidence.model_dump_json().encode("utf-8")
            previous = evidence_by_hash.setdefault(evidence.content_sha256, evidence_bytes)
            if previous != evidence_bytes:
                raise ValueError("conflicting evidence payloads share one content hash")

            if (observation.price is None) != (observation.currency is None):
                raise ValueError("price and currency must be supplied together")
            if observation.currency is not None and not _CURRENCY.fullmatch(observation.currency):
                raise ValueError("currency must be an upper-case three-letter code")
            if observation.price is not None and observation.price < Decimal("0"):
                raise ValueError("price cannot be negative")

            inputs = observation.qualification_inputs
            if frozenset(inputs) != _DIMENSIONS:
                raise ValueError("qualification inputs must contain exactly four dimensions")
            if any(value < Decimal("0") or value > Decimal("10") for value in inputs.values()):
                raise ValueError("qualification inputs must be within 0..10")


__all__ = ["ResearchService"]
