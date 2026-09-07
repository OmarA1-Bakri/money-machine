"""Strict shared primitives for versioned domain contracts."""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, JsonValue, StringConstraints


def normalize_utc(value: datetime) -> datetime:
    """Require a timezone-aware value and normalize it to UTC."""
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime must be timezone-aware")
    return value.astimezone(UTC)


class ContractModel(BaseModel):
    """Base policy shared by every Session 01 domain contract."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        validate_default=True,
        allow_inf_nan=False,
    )

    schema_version: Literal[1] = 1


NonEmptyStr = Annotated[
    str,
    StringConstraints(strict=True, strip_whitespace=True, min_length=1),
]
Sha256Hex = Annotated[
    str,
    StringConstraints(strict=True, pattern=r"^[0-9a-f]{64}$"),
]
CurrencyCode = Annotated[
    str,
    StringConstraints(strict=True, pattern=r"^[A-Z]{3}$"),
]
AgentId = Annotated[
    str,
    StringConstraints(strict=True, pattern=r"^A(?:0[1-9]|1[0-6])$"),
]
NonNegativeInt = Annotated[int, Field(strict=True, ge=0)]
PositiveInt = Annotated[int, Field(strict=True, gt=0)]
NonNegativeDecimal = Annotated[Decimal, Field(ge=Decimal("0"))]
PositiveDecimal = Annotated[Decimal, Field(gt=Decimal("0"))]
UnitDecimal = Annotated[
    Decimal,
    Field(ge=Decimal("0"), le=Decimal("1")),
]
UtcDatetime = Annotated[datetime, AfterValidator(normalize_utc)]
JsonObject = dict[str, JsonValue]
