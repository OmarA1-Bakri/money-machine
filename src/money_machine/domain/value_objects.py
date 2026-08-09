"""Shared immutable values, canonical hashing, and transition guards."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from datetime import date, datetime, time
from decimal import Decimal
from enum import Enum
from pathlib import Path
from types import MappingProxyType
from typing import Annotated, Literal, cast
from uuid import UUID

from pydantic import AnyUrl, BaseModel, ConfigDict, StringConstraints

from money_machine.domain.enums import JobState, ProductState

type Sha256 = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
type NonEmptyStr = Annotated[str, StringConstraints(min_length=1)]


class FrozenModel(BaseModel):
    """Strict, immutable base for every first-slice domain contract."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal[1] = 1


def immutable_mapping[Key, Value](value: Mapping[Key, Value]) -> Mapping[Key, Value]:
    """Return an immutable copy without retaining the caller's mapping."""

    return MappingProxyType(dict(value))


def _transform_canonical_value(
    value: object, *, freeze: bool, active_container_ids: set[int]
) -> object:
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("canonical values must contain only finite numbers")
        return value
    if isinstance(value, Mapping):
        mapping = cast(Mapping[object, object], value)
        container_id = id(mapping)
        if container_id in active_container_ids:
            raise ValueError("canonical value cycle detected")
        active_container_ids.add(container_id)
        try:
            transformed: dict[str, object] = {}
            for key, nested in mapping.items():
                if not isinstance(key, str):
                    raise TypeError("canonical mapping keys must be strings")
                transformed[key] = _transform_canonical_value(
                    nested,
                    freeze=freeze,
                    active_container_ids=active_container_ids,
                )
        finally:
            active_container_ids.remove(container_id)
        return MappingProxyType(transformed) if freeze else transformed
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        sequence = cast(Sequence[object], value)
        container_id = id(sequence)
        if container_id in active_container_ids:
            raise ValueError("canonical value cycle detected")
        active_container_ids.add(container_id)
        try:
            transformed_sequence = [
                _transform_canonical_value(
                    nested,
                    freeze=freeze,
                    active_container_ids=active_container_ids,
                )
                for nested in sequence
            ]
        finally:
            active_container_ids.remove(container_id)
        return tuple(transformed_sequence) if freeze else transformed_sequence
    raise TypeError(f"unsupported canonical value type: {type(value).__name__}")


def freeze_canonical_value(value: object) -> object:
    """Validate and recursively freeze one JSON-compatible value."""

    return _transform_canonical_value(value, freeze=True, active_container_ids=set())


def thaw_canonical_value(value: object) -> object:
    """Return a validated plain-dict/list representation for serialization."""

    return _transform_canonical_value(value, freeze=False, active_container_ids=set())


def _canonical_datetime(value: datetime) -> str:
    rendered = value.isoformat()
    return f"{rendered[:-6]}Z" if rendered.endswith("+00:00") else rendered


def _transform_canonical_model_value(value: object, *, active_container_ids: set[int]) -> object:
    if isinstance(value, BaseModel):
        model_type = type(value)
        if model_type.model_computed_fields:
            raise TypeError("canonical models cannot declare computed fields")
        if model_type.__pydantic_decorators__.model_serializers:
            raise TypeError("canonical models cannot declare model serializers")
        container_id = id(value)
        if container_id in active_container_ids:
            raise ValueError("canonical value cycle detected")
        active_container_ids.add(container_id)
        try:
            stored_fields = cast(Mapping[str, object], vars(value))
            transformed: dict[str, object] = {}
            for field_name in model_type.model_fields:
                if field_name in stored_fields:
                    transformed[field_name] = _transform_canonical_model_value(
                        stored_fields[field_name],
                        active_container_ids=active_container_ids,
                    )
            extras = cast(
                Mapping[object, object] | None,
                object.__getattribute__(value, "__pydantic_extra__"),
            )
            if extras is not None:
                for key, nested in extras.items():
                    if not isinstance(key, str):
                        raise TypeError("canonical mapping keys must be strings")
                    transformed[key] = _transform_canonical_model_value(
                        nested,
                        active_container_ids=active_container_ids,
                    )
        finally:
            active_container_ids.remove(container_id)
        return transformed
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("canonical values must contain only finite numbers")
        return value
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise ValueError("canonical values must contain only finite numbers")
        return str(value)
    if isinstance(value, datetime):
        return _canonical_datetime(value)
    if isinstance(value, (date, time, UUID, Path, AnyUrl)):
        return str(value)
    if isinstance(value, Enum):
        return _transform_canonical_model_value(
            value.value,
            active_container_ids=active_container_ids,
        )
    if isinstance(value, (set, frozenset)):
        raise TypeError("unsupported canonical value type: set or frozenset")
    if isinstance(value, Mapping):
        mapping = cast(Mapping[object, object], value)
        container_id = id(mapping)
        if container_id in active_container_ids:
            raise ValueError("canonical value cycle detected")
        active_container_ids.add(container_id)
        try:
            transformed = {}
            for key, nested in mapping.items():
                if not isinstance(key, str):
                    raise TypeError("canonical mapping keys must be strings")
                transformed[key] = _transform_canonical_model_value(
                    nested,
                    active_container_ids=active_container_ids,
                )
        finally:
            active_container_ids.remove(container_id)
        return transformed
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        sequence = cast(Sequence[object], value)
        container_id = id(sequence)
        if container_id in active_container_ids:
            raise ValueError("canonical value cycle detected")
        active_container_ids.add(container_id)
        try:
            return [
                _transform_canonical_model_value(
                    nested,
                    active_container_ids=active_container_ids,
                )
                for nested in sequence
            ]
        finally:
            active_container_ids.remove(container_id)
    raise TypeError(f"unsupported canonical value type: {type(value).__name__}")


def canonical_json(value: BaseModel | Mapping[str, object]) -> bytes:
    """Serialize a model or mapping to deterministic UTF-8 JSON bytes."""

    if isinstance(value, BaseModel):
        serializable = _transform_canonical_model_value(value, active_container_ids=set())
    else:
        serializable = thaw_canonical_value(value)
    return json.dumps(
        serializable,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def canonical_sha256(value: BaseModel | Mapping[str, object]) -> str:
    """Return the lower-case SHA-256 digest of canonical JSON."""

    return hashlib.sha256(canonical_json(value)).hexdigest()


def _build_product_transitions() -> Mapping[ProductState, frozenset[ProductState]]:
    terminal_states = {
        ProductState.DRAFT_READY,
        ProductState.INSUFFICIENT_EVIDENCE,
        ProductState.REJECTED,
        ProductState.FAILED,
    }
    happy_path = {
        ProductState.RESEARCHED: ProductState.QUALIFIED,
        ProductState.QUALIFIED: ProductState.SPECIFIED,
        ProductState.SPECIFIED: ProductState.DEDUPE_PASSED,
        ProductState.DEDUPE_PASSED: ProductState.BUILT,
        ProductState.BUILT: ProductState.QA_PASSED,
        ProductState.QA_PASSED: ProductState.MERCHANDISED,
        ProductState.MERCHANDISED: ProductState.PREFLIGHT_PASSED,
        ProductState.PREFLIGHT_PASSED: ProductState.DRAFT_READY,
    }
    transitions: dict[ProductState, frozenset[ProductState]] = {}
    for state in ProductState:
        if state in terminal_states:
            transitions[state] = frozenset()
            continue
        targets = {
            happy_path[state],
            ProductState.REJECTED,
            ProductState.FAILED,
        }
        if state in {ProductState.RESEARCHED, ProductState.QUALIFIED}:
            targets.add(ProductState.INSUFFICIENT_EVIDENCE)
        transitions[state] = frozenset(targets)
    return MappingProxyType(transitions)


PRODUCT_TRANSITIONS = _build_product_transitions()

JOB_TRANSITIONS: Mapping[JobState, frozenset[JobState]] = MappingProxyType(
    {
        JobState.PENDING: frozenset({JobState.READY, JobState.CANCELLED}),
        JobState.READY: frozenset({JobState.LEASED, JobState.CANCELLED}),
        JobState.LEASED: frozenset({JobState.READY, JobState.RUNNING, JobState.CANCELLED}),
        JobState.RUNNING: frozenset(
            {JobState.RETRY_WAIT, JobState.SUCCEEDED, JobState.FAILED, JobState.CANCELLED}
        ),
        JobState.RETRY_WAIT: frozenset({JobState.READY, JobState.FAILED, JobState.CANCELLED}),
        JobState.SUCCEEDED: frozenset(),
        JobState.FAILED: frozenset(),
        JobState.CANCELLED: frozenset(),
    }
)


def assert_product_transition(current: ProductState, target: ProductState) -> None:
    """Reject any product transition not declared by the frozen table."""

    if target not in PRODUCT_TRANSITIONS[current]:
        raise ValueError(f"invalid product transition: {current.value} -> {target.value}")


def assert_job_transition(current: JobState, target: JobState) -> None:
    """Reject any job transition not declared by the frozen table."""

    if target not in JOB_TRANSITIONS[current]:
        raise ValueError(f"invalid job transition: {current.value} -> {target.value}")
