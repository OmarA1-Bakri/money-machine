"""The one-real-draft envelope cannot inherit broader production authority."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any, cast
from uuid import UUID

import pytest
from pydantic import ValidationError

from money_machine.application.real_draft_authority import (
    DraftReadbackProof,
    DraftRunAuthority,
    DraftRunRefused,
)

PRODUCT = UUID("d847d00f-6abc-4ea0-82b7-a98be62c546b")
NOW = datetime(2026, 10, 22, 12, tzinfo=UTC)
COPY_HASH = "a" * 64
PARENT = UUID("e447d00f-6abc-4ea0-82b7-a98be62c546b")


def authority(**changes: object) -> DraftRunAuthority:
    return DraftRunAuthority.model_validate(
        {
            "run_id": "real-draft-20261022",
            "product_id": PRODUCT,
            "shop_name": "QuietlyBuiltStudio",
            "verified_shop_id": 123,
            "verified_notion_parent_id": PARENT,
            **changes,
        }
    )


def proof(**changes: object) -> DraftReadbackProof:
    return DraftReadbackProof.model_validate(
        {
            "run_id": "real-draft-20261022",
            "product_id": PRODUCT,
            "shop_name": "QuietlyBuiltStudio",
            "shop_id": 123,
            "listing_id": 456,
            "state": "draft",
            "source": "real_api",
            "verified": True,
            "observed_at": NOW,
            "copy_sha256": COPY_HASH,
            "image_ids": (11,),
            "video_ids": (12,),
            "file_ids": (13,),
            **changes,
        }
    )


def verify(item: DraftReadbackProof) -> None:
    authority().verify_readback(
        item,
        expected_listing_id=456,
        expected_copy_sha256=COPY_HASH,
        expected_image_count=1,
        expected_video_count=1,
        expected_file_count=1,
        now=NOW,
    )


def test_scope_roundtrip_is_immutable() -> None:
    policy = authority()
    assert DraftRunAuthority.model_validate_json(policy.model_dump_json()) == policy
    with pytest.raises(ValidationError):
        policy.run_id = "another-run"


@pytest.mark.parametrize(
    "operation",
    [
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
    ],
)
def test_authorized_operations(operation: str) -> None:
    authority().authorize(
        operation,
        notion_parent_id=PARENT,
        run_id="real-draft-20261022",
        product_id=PRODUCT,
        shop_name="QuietlyBuiltStudio",
        shop_id=123,
        listing_state="draft",
    )


@pytest.mark.parametrize(
    "operation",
    [
        "etsy.publish",
        "etsy.activate",
        "llm.call",
        "paid_api.call",
        "purchase",
        "checkout",
        "customer.message",
        "schedule.activate",
        "notion.publish",
        "notion.public_product.write",
        "etsy.delete",
        "unknown",
    ],
)
def test_forbidden_operations_cannot_be_enabled(operation: str) -> None:
    with pytest.raises(DraftRunRefused, match="operation_not_authorized"):
        authority().authorize(
            operation,
            notion_parent_id=PARENT,
            run_id="real-draft-20261022",
            product_id=PRODUCT,
            shop_name="QuietlyBuiltStudio",
            shop_id=123,
        )


@pytest.mark.parametrize("value", [True, "live", Decimal("10")])
def test_broader_configuration_cannot_change_envelope(value: object) -> None:
    with pytest.raises(ValidationError):
        authority(auto_publish=value, paid_tool_monthly_cap=value)


@pytest.mark.parametrize(
    "changes",
    [
        {"run_id": "wrong"},
        {"product_id": UUID(int=1)},
        {"shop_id": 999},
        {"shop_name": "OtherShop"},
        {"listing_state": "active"},
        {"cost": Decimal("-1")},
        {"cost": Decimal("0.01")},
        {"cost": Decimal("NaN")},
        {"cost": Decimal("Infinity")},
    ],
)
def test_wrong_scope_or_spend_refused(changes: dict[str, object]) -> None:
    kwargs = {
        "run_id": "real-draft-20261022",
        "product_id": PRODUCT,
        "shop_name": "QuietlyBuiltStudio",
        "shop_id": 123,
        "listing_state": "draft",
        "cost": Decimal("0"),
        **changes,
    }
    reason = (
        "run_product_scope"
        if set(changes) & {"run_id", "product_id"}
        else "zero_spend_required"
        if "cost" in changes
        else "draft_state_required"
        if "listing_state" in changes
        else "shop_scope"
    )
    with pytest.raises(DraftRunRefused, match=reason):
        authority().authorize("etsy.create_draft", **cast(Any, kwargs))


def test_unverified_shop_fails_closed_for_etsy_but_local_work_continues() -> None:
    policy = authority(verified_shop_id=None)
    policy.authorize("local.qa", run_id=policy.run_id, product_id=PRODUCT)
    with pytest.raises(DraftRunRefused):
        policy.authorize(
            "etsy.create_draft",
            run_id=policy.run_id,
            product_id=PRODUCT,
            shop_name=policy.shop_name,
            shop_id=123,
        )
    with pytest.raises(DraftRunRefused):
        policy.verify_readback(
            proof(),
            expected_listing_id=456,
            expected_copy_sha256=COPY_HASH,
            expected_image_count=1,
            expected_video_count=1,
            expected_file_count=1,
            now=NOW,
        )


def test_real_readback_satisfies_exact_product_and_shop() -> None:
    verify(proof())
    verify(proof(source="real_browser"))


@pytest.mark.parametrize(
    "changes",
    [
        {"source": "fixture"},
        {"verified": False},
        {"state": "active"},
        {"shop_id": 999},
        {"shop_name": "OtherShop"},
        {"listing_id": 999},
        {"run_id": "wrong"},
        {"product_id": UUID(int=1)},
        {"copy_sha256": "b" * 64},
        {"image_ids": ()},
        {"file_ids": ()},
        {"video_ids": ()},
        {"observed_at": NOW - timedelta(minutes=6)},
        {"observed_at": NOW + timedelta(seconds=1)},
    ],
)
def test_invalid_or_incomplete_readback_is_refused(changes: dict[str, object]) -> None:
    key = next(iter(changes))
    reason = (
        "real_verified_readback_required"
        if key in {"source", "verified"}
        else "draft_state_required"
        if key == "state"
        else "shop_scope"
        if key in {"shop_id", "shop_name"}
        else "run_product_scope"
        if key in {"run_id", "product_id"}
        else "fresh_readback_required"
        if key == "observed_at"
        else "attachment_count_mismatch"
        if key.endswith("_ids")
        else "listing_copy_mismatch"
    )
    with pytest.raises(DraftRunRefused, match=reason):
        verify(proof(**changes))


@pytest.mark.parametrize(
    "changes",
    [
        {"listing_id": 0},
        {"shop_id": -1},
        {"copy_sha256": "not-a-hash"},
        {"image_ids": (1, 1)},
        {"file_ids": (-1,)},
        {"observed_at": NOW.replace(tzinfo=None)},
        {"verified": "true"},
        {"credentials": "must-not-be-stored"},
        {"price": "-1.00"},
    ],
)
def test_proof_rejects_malformed_or_unnecessary_payload(changes: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        proof(**changes)


@pytest.mark.parametrize(
    "price", [Decimal("-1"), Decimal("0"), Decimal("NaN"), Decimal("Infinity")]
)
def test_invalid_listing_prices_cannot_reach_provider(price: Decimal) -> None:
    with pytest.raises(DraftRunRefused):
        authority().authorize(
            "etsy.create_draft",
            run_id="real-draft-20261022",
            product_id=PRODUCT,
            shop_name="QuietlyBuiltStudio",
            shop_id=123,
            price=price,
        )


def test_attachment_counts_must_match_product_manifest() -> None:
    with pytest.raises(DraftRunRefused):
        authority().verify_readback(
            proof(),
            expected_listing_id=456,
            expected_copy_sha256=COPY_HASH,
            expected_image_count=1,
            expected_video_count=1,
            expected_file_count=2,
            now=NOW,
        )
    authority().verify_readback(
        proof(file_ids=(13, 14)),
        expected_listing_id=456,
        expected_copy_sha256=COPY_HASH,
        expected_image_count=1,
        expected_video_count=1,
        expected_file_count=2,
        now=NOW,
    )


def test_readback_five_minute_boundary_and_untrusted_clock() -> None:
    verify(proof(observed_at=NOW - timedelta(minutes=5)))
    with pytest.raises(DraftRunRefused):
        authority().verify_readback(
            proof(),
            expected_listing_id=456,
            expected_copy_sha256=COPY_HASH,
            expected_image_count=1,
            expected_video_count=1,
            expected_file_count=1,
            now=NOW.replace(tzinfo=None),
        )


def test_persisted_authority_rejects_wrong_shop_and_invalid_id() -> None:
    for changes in (
        {"shop_name": "OtherShop"},
        {"verified_shop_id": True},
        {"verified_shop_id": 0},
        {"run_id": "../outside"},
    ):
        with pytest.raises(ValidationError):
            authority(**changes)


@pytest.mark.parametrize("parent", [None, UUID(int=2)])
def test_private_notion_write_requires_exact_verified_parent(parent: UUID | None) -> None:
    with pytest.raises(DraftRunRefused):
        authority().authorize(
            "notion.private_product.write",
            run_id="real-draft-20261022",
            product_id=PRODUCT,
            notion_parent_id=parent,
        )


def test_unverified_notion_parent_does_not_authorize_external_writes() -> None:
    policy = authority(verified_notion_parent_id=None)
    policy.authorize("local.render", run_id=policy.run_id, product_id=PRODUCT)
    with pytest.raises(DraftRunRefused):
        policy.authorize(
            "notion.private_variant.write",
            run_id=policy.run_id,
            product_id=PRODUCT,
            notion_parent_id=PARENT,
        )
