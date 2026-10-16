"""Action 9 fixture path. Each gate has its own kill."""

from __future__ import annotations

import socket
from dataclasses import replace
from pathlib import Path
from uuid import UUID

import pytest

from money_machine.agents.contracts.merchandising import IMAGE_ROLES
from money_machine.assets.asset_lineage import BoundAsset, bind_asset
from money_machine.assets.delivery_pdfs import DeliveryPdfLineage
from money_machine.assets.etsy_draft import DraftEvidence, DraftGateError, prepare_etsy_draft
from money_machine.assets.listing_images import ListingImageLineage
from money_machine.assets.screenshots import ScreenshotLineage
from money_machine.assets.video import WalkthroughLineage
from money_machine.integrations.etsy.draft_client import DraftLedger, EtsyDraftClient
from tests.unit.integrations.test_etsy_draft_client import Store

_PRODUCT = UUID("00000000-0000-4000-8000-0000000000a8")


@pytest.fixture(autouse=True)
def _block_sockets(monkeypatch: pytest.MonkeyPatch) -> None:  # pyright: ignore[reportUnusedFunction]
    def _blocked(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("socket")

    def _connect(_self: socket.socket, address: object) -> None:
        _blocked(address)

    monkeypatch.setattr(socket, "create_connection", _blocked)
    monkeypatch.setattr(socket.socket, "connect", _connect)


def _shot(digest: str = "shot") -> BoundAsset:
    return bind_asset(
        ScreenshotLineage(
            product_id=_PRODUCT,
            spec_version=2,
            build_version=4,
            screenshot_sha256=digest,
            variant="Sage Green",
            template_version="t1",
            viewport_width=10,
            viewport_height=10,
            crop_x=0,
            crop_y=0,
            crop_width=8,
            crop_height=6,
            qa_status="passed",
            source="fixture",
        )
    )


def _image(digest: str, *, stale: bool = False) -> BoundAsset:
    asset = bind_asset(
        ListingImageLineage(
            product_id=_PRODUCT,
            spec_version=2,
            build_version=4,
            source_screenshot_sha256=("shot",),
            merchandising_version="m1",
            template_version="t1",
            output_sha256=digest,
            width_px=20,
            height_px=10,
            qa_status="passed",
            role="hero",
        )
    )
    if stale:
        return replace(asset, qa_status="stale")
    return asset


def _video(digest: str = "video") -> BoundAsset:
    return bind_asset(
        WalkthroughLineage(
            product_id=_PRODUCT,
            spec_version=2,
            build_version=4,
            source_screenshot_sha256=("shot",),
            merchandising_version="m1",
            template_version="t1",
            output_sha256=digest,
            width_px=20,
            height_px=10,
            fps=12,
            scene_order=("dashboard",),
            scene_frames=(1,),
            qa_status="passed",
        )
    )


def _pdf(digest: str) -> BoundAsset:
    return bind_asset(
        DeliveryPdfLineage(
            product_id=_PRODUCT,
            spec_version=2,
            build_version=4,
            merchandising_version="m1",
            template_version="t1",
            output_sha256=digest,
            page_count=1,
            qa_status="passed",
            role="readme",
        )
    )


def _assets(
    *,
    shots: int = 1,
    images: int | None = None,
    videos: int = 1,
    pdfs: int = 2,
    stale_image: bool = False,
) -> tuple[BoundAsset, ...]:
    image_count = len(IMAGE_ROLES) if images is None else images
    found = [
        _shot("shot" if shots == 1 and index == 0 else f"shot{index}") for index in range(shots)
    ]
    pictures = [
        _image(f"img{index}", stale=stale_image and index == 0) for index in range(image_count)
    ]
    clips = [_video(f"video{index}") for index in range(videos)]
    documents = [_pdf(f"pdf{index}") for index in range(pdfs)]
    return tuple([*found, *pictures, *clips, *documents])


def _evidence(**changes: object) -> DraftEvidence:
    evidence = DraftEvidence(
        product_id=_PRODUCT,
        spec_version=2,
        shop_id=123456,
        product_qa="passed",
        claims_passed=True,
        assets=_assets(),
        pdf_roles=("readme", "free_gift"),
        links_passed=True,
        title="Fixture planner",
        description="A fixture description.",
        price="11.00",
        quantity=999,
        who_made="i_did",
        when_made="2020_2026",
        taxonomy_id=1,
    )
    if not changes:
        return evidence
    return replace(evidence, **changes)


def chain_assets(
    *,
    shots: int = 1,
    images: int | None = None,
    videos: int = 1,
    pdfs: int = 2,
    stale_image: bool = False,
) -> tuple[BoundAsset, ...]:
    """The same asset bundle the gate tests refuse or accept."""
    return _assets(
        shots=shots,
        images=images,
        videos=videos,
        pdfs=pdfs,
        stale_image=stale_image,
    )


def chain_evidence(**changes: object) -> DraftEvidence:
    """The same draft evidence the gate tests pass to ``prepare_etsy_draft``."""
    return _evidence(**changes)


def test_a_passed_chain_is_a_ready_draft(tmp_path: Path) -> None:
    store = Store()
    client = EtsyDraftClient(store, DraftLedger(tmp_path))
    receipt = prepare_etsy_draft(_evidence(), client)
    assert receipt.ready is True
    assert receipt.state == "draft"
    assert store.posts == 1
    assert [call.method for call in store.calls] == ["GET", "GET", "POST"]


@pytest.mark.parametrize(
    ("changes", "gate"),
    [
        ({"product_qa": "failed"}, "product_qa"),
        ({"claims_passed": False}, "claims"),
        ({"assets": _assets(shots=0)}, "screenshots"),
        ({"assets": _assets(images=len(IMAGE_ROLES) - 1)}, "listing_images"),
        ({"assets": _assets(videos=0)}, "video"),
        ({"assets": _assets(videos=2)}, "video"),
        ({"assets": _assets(pdfs=1), "pdf_roles": ("readme",)}, "delivery_pdfs"),
        ({"pdf_roles": ("free_gift", "free_gift")}, "delivery_pdfs"),
        ({"assets": _assets(pdfs=3)}, "delivery_pdfs"),
        ({"links_passed": False}, "links"),
        ({"assets": _assets(stale_image=True)}, "asset_qa"),
    ],
)
def test_each_gate_refuses_on_its_own(
    tmp_path: Path, changes: dict[str, object], gate: str
) -> None:
    store = Store()
    client = EtsyDraftClient(store, DraftLedger(tmp_path))
    with pytest.raises(DraftGateError) as caught:
        prepare_etsy_draft(_evidence(**changes), client)
    assert caught.value.gate == gate
    assert store.calls == []
