"""Read-only ProductSpec route."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from money_machine.api.dependencies import get_unit_of_work
from money_machine.api.schemas import ProductFactResponse, ProductResponse
from money_machine.persistence.unit_of_work import UnitOfWork

router = APIRouter(prefix="/products", tags=["products"])


@router.get("/{product_spec_id}", response_model=ProductResponse)
async def get_product(
    product_spec_id: str,
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> ProductResponse:
    spec = await uow.products.get_spec(product_spec_id)
    if spec is None:
        raise HTTPException(status_code=404, detail="product not found")
    return ProductResponse(
        product_spec_id=spec.product_spec_id,
        candidate_id=spec.candidate_id,
        identity_niche=spec.identity_niche,
        base_category=spec.base_category,
        target_buyer=spec.target_buyer,
        promised_outcome=spec.promised_outcome,
        hubs=spec.hubs,
        colour_variants=spec.colour_variants,
        features=spec.features,
        product_facts=tuple(
            ProductFactResponse(
                claim=fact.claim,
                category=fact.category,
                evidence_ids=fact.evidence_ids,
            )
            for fact in spec.product_facts
        ),
        source_evidence_ids=spec.source_evidence_ids,
        spec_sha256=spec.spec_sha256,
    )
