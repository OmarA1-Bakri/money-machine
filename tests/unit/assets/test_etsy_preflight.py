"""Etsy preflight checklist. Each repairable miss and the claim block kills one pin."""

from __future__ import annotations

import socket

import pytest

from money_machine.assets.etsy_preflight import (
    EtsyPreflightDraft,
    PreflightBlocked,
    PreflightClaim,
    run_etsy_preflight,
)
from money_machine.domain.enums import BranchOutcome
from money_machine.domain.models.listings import PreflightResult

_IMAGES = (
    "hero",
    "overview",
    "hub_1",
    "hub_2",
    "hub_3",
    "hub_4",
    "hub_5",
    "colour_options",
    "devices",
    "how_it_works",
)
_TAGS = tuple(f"tag {number}" for number in range(1, 14))
_FACT = PreflightClaim("Includes six hubs", "fact:hubs")


def _draft(
    *,
    quantity: int = 999,
    tags: tuple[str, ...] | None = None,
    images: tuple[str, ...] | None = None,
    videos: int = 1,
    claims: tuple[PreflightClaim, ...] | None = None,
) -> EtsyPreflightDraft:
    return EtsyPreflightDraft(
        quantity=quantity,
        tags=_TAGS if tags is None else tags,
        images=_IMAGES if images is None else images,
        videos=videos,
        claims=(_FACT,) if claims is None else claims,
    )


@pytest.fixture(autouse=True)
def _block_sockets(monkeypatch: pytest.MonkeyPatch) -> None:  # pyright: ignore[reportUnusedFunction]
    def _blocked(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("socket")

    def _connect(_self: socket.socket, address: object) -> None:
        _blocked(address)

    monkeypatch.setattr(socket, "create_connection", _blocked)
    monkeypatch.setattr(socket.socket, "connect", _connect)


def test_passing_checklist_is_pass_with_no_repair_job() -> None:
    draft = _draft()
    assert draft.quantity == 999
    assert len(draft.tags) == 13
    assert len(set(draft.tags)) == 13
    assert all(tag.strip() for tag in draft.tags)
    assert len(draft.images) == 10
    assert draft.images[0] == "hero"
    assert draft.videos == 1
    assert draft.claims[0].fact_ref == "fact:hubs"

    result = run_etsy_preflight(draft)
    assert isinstance(result, PreflightResult)
    assert result.outcome is BranchOutcome.PASS
    assert result.repair_job_types == ()
    assert result.checks
    assert all(check.passed for check in result.checks)


def test_quantity_100_fails_with_a_quantity_repair() -> None:
    result = run_etsy_preflight(_draft(quantity=100))
    assert isinstance(result, PreflightResult)
    assert result.outcome is BranchOutcome.FAIL
    assert result.repair_job_types == ("repair_quantity",)
    failed = tuple(check for check in result.checks if not check.passed)
    assert tuple(check.name for check in failed) == ("quantity",)


def test_twelve_tags_fails_with_a_tag_repair() -> None:
    result = run_etsy_preflight(_draft(tags=_TAGS[:12]))
    assert isinstance(result, PreflightResult)
    assert result.outcome is BranchOutcome.FAIL
    assert result.repair_job_types == ("repair_tags",)
    failed = tuple(check for check in result.checks if not check.passed)
    assert tuple(check.name for check in failed) == ("tags",)


def test_nine_images_fails_with_an_image_repair() -> None:
    result = run_etsy_preflight(_draft(images=_IMAGES[:9]))
    assert isinstance(result, PreflightResult)
    assert result.outcome is BranchOutcome.FAIL
    assert result.repair_job_types == ("repair_images",)
    failed = tuple(check for check in result.checks if not check.passed)
    assert tuple(check.name for check in failed) == ("images",)


def test_video_absent_fails_with_a_video_repair() -> None:
    result = run_etsy_preflight(_draft(videos=0))
    assert isinstance(result, PreflightResult)
    assert result.outcome is BranchOutcome.FAIL
    assert result.repair_job_types == ("repair_video",)
    failed = tuple(check for check in result.checks if not check.passed)
    assert tuple(check.name for check in failed) == ("video",)


def test_unsupported_claim_is_blocked_with_no_repair_job() -> None:
    result = run_etsy_preflight(_draft(claims=(PreflightClaim("Ships tomorrow", None),)))
    assert isinstance(result, PreflightBlocked)
    assert not isinstance(result, PreflightResult)
    assert result.blocked is True
    assert result.repair_job_types == ()
