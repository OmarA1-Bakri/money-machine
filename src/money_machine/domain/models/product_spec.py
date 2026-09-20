"""ProductSpec domain contract and supporting records for S05 L3."""

from typing import Literal
from uuid import UUID

from pydantic import Field

from money_machine.domain.models._base import (
    ContractModel,
    CurrencyCode,
    NonEmptyStr,
    PositiveDecimal,
    PositiveInt,
    UtcDatetime,
)
from money_machine.domain.models.common import EvidenceReference


class ColourToken(ContractModel):
    """One colour variant definition with hex/name tokens."""

    name: NonEmptyStr
    hex: NonEmptyStr = Field(pattern=r"^#[0-9A-Fa-f]{6}$")


class Hub(ContractModel):
    """One hub (chapter/section) in the product specification."""

    name: NonEmptyStr
    description: NonEmptyStr = Field(max_length=500)
    page_count: PositiveInt


class ProductSpec(ContractModel):
    """Immutable product specification from A05 ProductStrategy agent."""

    spec_id: UUID
    product_id: UUID
    workflow_id: UUID
    version: PositiveInt
    producing_job_id: UUID
    producing_agent_run_id: UUID
    research_run_id: UUID | None = None
    teardown_report_id: UUID | None = None
    lineage_kind: Literal["ORIGINAL", "RECONCEPT", "SUCCESSOR"] = "ORIGINAL"
    parent_spec_id: UUID | None = None
    parent_product_id: UUID | None = None
    parent_decision_id: UUID | None = None
    parent_workflow_id: UUID | None = None

    identity: NonEmptyStr
    base_category: NonEmptyStr
    buyer_problem: NonEmptyStr = Field(max_length=1000)
    title: NonEmptyStr = Field(max_length=500)
    tier: NonEmptyStr = Field(max_length=64)
    real_price: PositiveDecimal
    anchor_price: PositiveDecimal
    currency: CurrencyCode

    palette_name: NonEmptyStr
    palette_tokens: tuple[ColourToken, ...] = Field(min_length=3, max_length=4)
    hubs: tuple[Hub, ...] = Field(min_length=6, max_length=8)
    colour_variants: tuple[NonEmptyStr, ...] = Field(min_length=3, max_length=4)
    flagship_feature: NonEmptyStr = Field(max_length=500)
    shared_databases: tuple[NonEmptyStr, ...] = ()
    page_target_min: PositiveInt
    page_target_max: PositiveInt
    feature_targets: tuple[NonEmptyStr, ...] = ()

    experiment_hypothesis: NonEmptyStr = Field(max_length=1000)
    experiment_tags: tuple[NonEmptyStr, ...] = ()
    concept_fingerprint: NonEmptyStr = Field(pattern=r"^[0-9a-f]{64}$")
    rule_version: NonEmptyStr
    evidence: tuple[EvidenceReference, ...] = Field(min_length=1)
    created_at: UtcDatetime
