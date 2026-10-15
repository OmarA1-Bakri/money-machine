"""Fixture path from product QA to a ready Etsy draft.

Action 8 object storage stays parked. The storage URI on each asset stays
``fixture://``. This module does not open a socket and does not import a
live Etsy or Notion client.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from money_machine.agents.contracts.merchandising import IMAGE_ROLES
from money_machine.assets.asset_lineage import BoundAsset, split_current
from money_machine.integrations.etsy.draft_client import (
    DraftReceipt,
    DraftSpec,
    EtsyDraftClient,
)

_PDF_ROLES: frozenset[str] = frozenset({"readme", "free_gift"})


class DraftGateError(Exception):
    """One chain gate failed. ``gate`` is the step that refused."""

    def __init__(self, gate: str) -> None:
        self.gate = gate
        super().__init__(gate)


@dataclass(frozen=True, slots=True)
class DraftEvidence:
    """Receipts the earlier fixture stages already produced."""

    product_id: UUID
    spec_version: int
    shop_id: int
    product_qa: Literal["passed", "failed"]
    claims_passed: bool
    assets: tuple[BoundAsset, ...]
    pdf_roles: tuple[str, ...]
    links_passed: bool
    title: str
    description: str
    price: str
    quantity: int
    who_made: str
    when_made: str
    taxonomy_id: int


def prepare_etsy_draft(evidence: DraftEvidence, client: EtsyDraftClient) -> DraftReceipt:
    """Walk the action 9 chain and return a ready draft.

    Each refusal names one gate. The client is called only after asset QA.
    """
    if evidence.product_qa != "passed":
        raise DraftGateError("product_qa")
    if not evidence.claims_passed:
        raise DraftGateError("claims")
    shots = tuple(asset for asset in evidence.assets if asset.kind == "screenshot")
    images = tuple(asset for asset in evidence.assets if asset.kind == "listing_image")
    videos = tuple(asset for asset in evidence.assets if asset.kind == "walkthrough")
    pdfs = tuple(asset for asset in evidence.assets if asset.kind == "delivery_pdf")
    if len(shots) < 1:
        raise DraftGateError("screenshots")
    if len(images) != len(IMAGE_ROLES):
        raise DraftGateError("listing_images")
    if len(videos) != 1:
        raise DraftGateError("video")
    if len(pdfs) != len(_PDF_ROLES) or tuple(sorted(evidence.pdf_roles)) != (
        "free_gift",
        "readme",
    ):
        raise DraftGateError("delivery_pdfs")
    if not evidence.links_passed:
        raise DraftGateError("links")
    current, _stale = split_current(
        evidence.assets,
        product_id=evidence.product_id,
        spec_version=evidence.spec_version,
    )
    if len(current) != len(evidence.assets):
        raise DraftGateError("asset_qa")
    return client.create_draft(
        DraftSpec(
            product_id=evidence.product_id,
            spec_version=evidence.spec_version,
            shop_id=evidence.shop_id,
            title=evidence.title,
            description=evidence.description,
            price=evidence.price,
            quantity=evidence.quantity,
            who_made=evidence.who_made,
            when_made=evidence.when_made,
            taxonomy_id=evidence.taxonomy_id,
        )
    )
