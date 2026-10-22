"""D-0039's immutable one-product authority; callers retain existing durable state.

Serialize the envelope into the existing run/intent record before effects. Every
provider adapter must authorize before writing and obtain fresh readback after
writing. This policy neither performs effects nor authenticates provider evidence.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

PositiveId = Annotated[int, Field(strict=True, gt=0)]
Sha256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]

_ALLOWED_OPERATIONS = frozenset(
    {
        "local.render",
        "local.qa",
        "notion.private_product.read",
        "notion.private_product.write",
        "notion.private_variant.read",
        "notion.private_variant.write",
        "etsy.create_draft",
        "etsy.upload_image",
        "etsy.upload_video",
        "etsy.upload_file",
        "etsy.read_draft",
    }
)
_MAX_READBACK_AGE = timedelta(minutes=5)


class DraftRunRefused(ValueError):
    """The operation or evidence exceeds this run's fixed authority."""


class DraftReadbackProof(BaseModel):
    """Minimal provider observation metadata, never credentials or payloads.

    Only a trusted real adapter may assert provenance and verification. Fixture
    provenance remains representable so admission can explicitly refuse it.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    run_id: Annotated[str, Field(min_length=1, max_length=128)]
    product_id: UUID
    shop_name: Annotated[str, Field(min_length=1, max_length=64)]
    shop_id: PositiveId
    listing_id: PositiveId
    state: Annotated[str, Field(min_length=1, max_length=32)]
    source: Literal["real_api", "real_browser", "fixture"]
    verified: Annotated[bool, Field(strict=True)]
    observed_at: datetime
    copy_sha256: Sha256
    image_ids: tuple[PositiveId, ...]
    video_ids: tuple[PositiveId, ...]
    file_ids: tuple[PositiveId, ...]

    @field_validator("observed_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("readback timestamp must be timezone-aware")
        return value

    @field_validator("image_ids", "video_ids", "file_ids")
    @classmethod
    def unique_attachment_ids(cls, value: tuple[int, ...]) -> tuple[int, ...]:
        if len(set(value)) != len(value):
            raise ValueError("duplicate attachment identifiers")
        return value


class DraftRunAuthority(BaseModel):
    """Fixed run/product/shop scope, with no configurable safety overrides.

    ``verified_shop_id`` is admitted only after authoritative shop readback. An
    unknown shop permits local preparation but no Etsy operation. Private Notion
    operations likewise require a verified parent; adapters prove child ancestry.
    Persist and reload this exact envelope using the existing run ledger.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    run_id: Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")]
    product_id: UUID
    shop_name: Literal["QuietlyBuiltStudio"] = "QuietlyBuiltStudio"
    verified_shop_id: PositiveId | None = None
    verified_notion_parent_id: UUID | None = None

    def authorize(
        self,
        operation: str,
        *,
        run_id: str,
        product_id: UUID,
        shop_name: str | None = None,
        shop_id: int | None = None,
        notion_parent_id: UUID | None = None,
        listing_state: str = "draft",
        cost: Decimal = Decimal("0"),
        price: Decimal | None = None,
    ) -> None:
        """Fail closed before effects; broader settings cannot expand this list."""
        if operation not in _ALLOWED_OPERATIONS:
            raise DraftRunRefused("operation_not_authorized")
        if run_id != self.run_id or product_id != self.product_id:
            raise DraftRunRefused("run_product_scope")
        if type(cost) is not Decimal or not cost.is_finite() or cost != 0:
            raise DraftRunRefused("zero_spend_required")
        if price is not None and (
            type(price) is not Decimal or not price.is_finite() or price <= 0
        ):
            raise DraftRunRefused("positive_listing_price_required")
        if shop_name is not None and shop_name != self.shop_name:
            raise DraftRunRefused("shop_scope")
        if shop_id is not None and (type(shop_id) is not int or shop_id != self.verified_shop_id):
            raise DraftRunRefused("shop_scope")
        if listing_state != "draft":
            raise DraftRunRefused("draft_state_required")
        if operation.startswith("notion.") and (
            self.verified_notion_parent_id is None
            or notion_parent_id != self.verified_notion_parent_id
        ):
            raise DraftRunRefused("verified_notion_parent_required")
        if operation.startswith("etsy.") and (
            self.verified_shop_id is None
            or shop_id != self.verified_shop_id
            or shop_name != self.shop_name
        ):
            raise DraftRunRefused("verified_shop_required")

    def verify_readback(
        self,
        proof: DraftReadbackProof,
        *,
        expected_listing_id: int,
        expected_copy_sha256: str,
        now: datetime,
        expected_image_count: int,
        expected_video_count: int,
        expected_file_count: int,
    ) -> None:
        """Admit only a current real observation with all required attachments.

        Attachment counts follow from unique provider IDs rather than an asserted
        count. The one-product addendum requires images, video and digital files.
        ``now`` comes from the consumer's trusted clock, never the provider body.
        """
        self.authorize(
            "etsy.read_draft",
            run_id=proof.run_id,
            product_id=proof.product_id,
            shop_name=proof.shop_name,
            shop_id=proof.shop_id,
            listing_state=proof.state,
        )
        if proof.source == "fixture" or not proof.verified:
            raise DraftRunRefused("real_verified_readback_required")
        if (
            type(expected_listing_id) is not int
            or expected_listing_id <= 0
            or proof.listing_id != expected_listing_id
            or proof.copy_sha256 != expected_copy_sha256
        ):
            raise DraftRunRefused("listing_copy_mismatch")
        if now.tzinfo is None or now.utcoffset() is None:
            raise DraftRunRefused("trusted_clock_required")
        age = now - proof.observed_at
        if age < timedelta(0) or age > _MAX_READBACK_AGE:
            raise DraftRunRefused("fresh_readback_required")
        for actual, expected in (
            (len(proof.image_ids), expected_image_count),
            (len(proof.video_ids), expected_video_count),
            (len(proof.file_ids), expected_file_count),
        ):
            if type(expected) is not int or expected < 1 or actual != expected:
                raise DraftRunRefused("attachment_count_mismatch")


def notion_request_sha256(body: Mapping[str, object]) -> str:
    """Hash canonical UTF-8 JSON body bytes, not a logical operation key."""
    try:
        canonical = json.dumps(
            dict(body), sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
        ).encode("utf-8")
    except (TypeError, ValueError):
        raise DraftRunRefused("recovery_request_not_json") from None
    return hashlib.sha256(canonical).hexdigest()


class NotificationReplacementApproval(BaseModel):
    """Explicit operator-issued one-operation envelope; this module never issues it.

    Must match canonical BuildRepairJob metadata. No default approval, CLI loader
    or production request is provided. Registration/approval provenance remains
    the caller's existing control responsibility, not a self-issued receipt.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")
    approval_id: UUID
    repair_job_id: UUID
    original_job_id: UUID
    original_attempt_id: UUID
    original_effect_key: Annotated[str, Field(min_length=1, max_length=200)]
    workflow_id: UUID
    product_id: UUID
    run_id: Annotated[str, Field(min_length=1, max_length=128)]
    parent_id: UUID
    request_sha256: Sha256
    spec_sha256: Sha256
    decision_sha256: Sha256
    operator_reference: Annotated[str, Field(min_length=1, max_length=300)]
    approved_at: datetime
    expires_at: datetime
    max_sends: Literal[1] = 1
    operation: Literal["notion.notification.replacement.create"] = (
        "notion.notification.replacement.create"
    )

    @field_validator("approved_at", "expires_at")
    @classmethod
    def aware_approval_time(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("approval time must be timezone-aware")
        return value

    @property
    def operation_key(self) -> str:
        return "notification-replacement:" + str(self.approval_id)
