"""Research, product specification, dedupe, build, and QA contracts."""

from typing import Literal, Self
from uuid import UUID

from pydantic import Field, JsonValue, model_validator

from money_machine.domain.enums import BranchOutcome
from money_machine.domain.models._base import (
    ContractModel,
    CurrencyCode,
    JsonObject,
    NonEmptyStr,
    PositiveDecimal,
    PositiveInt,
    Sha256Hex,
    UnitDecimal,
    UtcDatetime,
)
from money_machine.domain.models.common import (
    ArtifactReference,
    CheckResult,
    EvidenceReference,
)
from money_machine.domain.models.rules import ProductShapeRules


class ResearchObservation(ContractModel):
    """One admitted market observation with safe structured facts."""

    observation_id: UUID
    source_reference: NonEmptyStr
    observed_at: UtcDatetime
    title: NonEmptyStr
    shop_reference: NonEmptyStr | None = None
    facts: JsonObject
    evidence: tuple[EvidenceReference, ...] = Field(min_length=1)


class ResearchReport(ContractModel):
    """Cited market-research output for shortlist and qualification work."""

    report_id: UUID
    workflow_id: UUID
    source_policy_version: NonEmptyStr
    query_terms: tuple[NonEmptyStr, ...] = Field(min_length=1)
    observations: tuple[ResearchObservation, ...] = Field(min_length=1)
    summary_facts: dict[str, JsonValue] = Field(default_factory=dict)
    completed_at: UtcDatetime


class TeardownReport(ContractModel):
    """Structure-only competitor teardown with explicit provenance."""

    report_id: UUID
    workflow_id: UUID
    competitor_reference: NonEmptyStr
    purchase_receipt_reference: NonEmptyStr | None = None
    structure_components: tuple[NonEmptyStr, ...] = Field(min_length=1)
    buyer_journey: tuple[NonEmptyStr, ...] = Field(min_length=1)
    mechanics: tuple[NonEmptyStr, ...] = Field(min_length=1)
    copied_protected_content: Literal[False]
    source_evidence: tuple[EvidenceReference, ...] = Field(min_length=1)
    completed_at: UtcDatetime


class ProductSpec(ContractModel):
    """Immutable product concept and build input version."""

    spec_id: UUID
    workflow_id: UUID
    product_id: UUID
    version: PositiveInt
    lineage_kind: Literal["ORIGINAL", "RECONCEPT", "SUCCESSOR"] = "ORIGINAL"
    parent_spec_id: UUID | None = None
    parent_product_id: UUID | None = None
    parent_decision_id: UUID | None = None
    parent_workflow_id: UUID | None = None
    shape_rules: ProductShapeRules
    identity: NonEmptyStr
    base_category: NonEmptyStr
    buyer_problem: NonEmptyStr
    title: NonEmptyStr
    tier: NonEmptyStr
    real_price: PositiveDecimal
    anchor_price: PositiveDecimal
    currency: CurrencyCode
    hubs: tuple[NonEmptyStr, ...] = Field(min_length=1)
    colour_variants: tuple[NonEmptyStr, ...] = Field(min_length=1)
    features: tuple[NonEmptyStr, ...] = Field(min_length=1)
    experiment_plan: NonEmptyStr
    concept_fingerprint: Sha256Hex
    source_evidence: tuple[EvidenceReference, ...] = Field(min_length=1)
    created_at: UtcDatetime

    @model_validator(mode="after")
    def validate_prices_and_lineage(self) -> Self:
        if self.anchor_price < self.real_price:
            raise ValueError("anchor_price must be at least real_price")
        if self.parent_spec_id == self.spec_id:
            raise ValueError("parent_spec_id cannot equal spec_id")

        parent_fields = (
            self.parent_spec_id,
            self.parent_product_id,
            self.parent_decision_id,
            self.parent_workflow_id,
        )
        if self.lineage_kind == "ORIGINAL" and any(value is not None for value in parent_fields):
            raise ValueError("ORIGINAL ProductSpec forbids parent lineage")
        if self.lineage_kind == "RECONCEPT" and self.parent_spec_id is None:
            raise ValueError("RECONCEPT ProductSpec requires parent_spec_id")
        if self.lineage_kind == "SUCCESSOR":
            if any(value is None for value in parent_fields):
                raise ValueError("SUCCESSOR ProductSpec requires complete parent lineage")
            if self.parent_workflow_id == self.workflow_id:
                raise ValueError("successor workflow must differ from parent workflow")
        return self

    @model_validator(mode="after")
    def validate_playbook_shape(self) -> Self:
        """Bind the configured hub and colour-variant ranges (workbook §7) into the spec."""
        rules = self.shape_rules
        hubs = tuple(hub.casefold() for hub in self.hubs)
        if len(set(hubs)) != len(hubs):
            raise ValueError("hubs must be unique")
        if not rules.hubs_minimum <= len(hubs) <= rules.hubs_maximum:
            raise ValueError(
                f"product requires {rules.hubs_minimum}-{rules.hubs_maximum} hubs, got {len(hubs)}"
            )
        variants = tuple(variant.casefold() for variant in self.colour_variants)
        if len(set(variants)) != len(variants):
            raise ValueError("colour variants must be unique")
        if not rules.colour_variants_minimum <= len(variants) <= rules.colour_variants_maximum:
            raise ValueError(
                f"product requires {rules.colour_variants_minimum}-"
                f"{rules.colour_variants_maximum} colour variants, got {len(variants)}"
            )
        return self


class DedupeCollision(ContractModel):
    """One cited exact, title-similarity, or concept collision."""

    other_spec_id: UUID
    reason: Literal["EXACT_IDENTITY_CATEGORY", "TITLE_SIMILARITY", "CONCEPT_FINGERPRINT"]
    similarity: UnitDecimal
    evidence: tuple[EvidenceReference, ...] = Field(min_length=1)


class DedupeResult(ContractModel):
    """Fail-closed catalogue dedupe result selecting pass or reconcept."""

    result_id: UUID
    workflow_id: UUID
    spec_id: UUID
    outcome: BranchOutcome
    rule_version: NonEmptyStr
    normalized_title: NonEmptyStr
    concept_fingerprint: Sha256Hex
    title_similarity_threshold: UnitDecimal
    compared_spec_ids: tuple[UUID, ...]
    collisions: tuple[DedupeCollision, ...] = ()
    differentiation_evidence: tuple[NonEmptyStr, ...] = ()
    completed_at: UtcDatetime

    @model_validator(mode="after")
    def validate_outcome(self) -> Self:
        if self.outcome not in {BranchOutcome.PASS, BranchOutcome.TOO_CLOSE}:
            raise ValueError("DedupeResult outcome must be PASS or TOO_CLOSE")
        if self.title_similarity_threshold <= 0:
            raise ValueError("title_similarity_threshold must be positive")
        if len(set(self.compared_spec_ids)) != len(self.compared_spec_ids):
            raise ValueError("compared_spec_ids must be unique")
        if self.spec_id in self.compared_spec_ids:
            raise ValueError("a spec is not compared with itself")
        for collision in self.collisions:
            if collision.other_spec_id not in self.compared_spec_ids:
                raise ValueError("every collision must cite a compared spec")
            if (
                collision.reason == "TITLE_SIMILARITY"
                and collision.similarity < self.title_similarity_threshold
            ):
                raise ValueError("a TITLE_SIMILARITY collision must meet the configured threshold")
        if self.outcome is BranchOutcome.PASS:
            if self.collisions:
                raise ValueError("PASS forbids collisions")
            if self.compared_spec_ids and not self.differentiation_evidence:
                raise ValueError("PASS against an existing catalogue requires differentiation")
        else:
            if not self.collisions:
                raise ValueError("TOO_CLOSE requires collision evidence")
            if self.differentiation_evidence:
                raise ValueError("TOO_CLOSE cannot claim differentiation; reconcept instead")
        return self


class BuildResult(ContractModel):
    """Versioned product, variant, repair, asset, or delivery build output."""

    result_id: UUID
    workflow_id: UUID
    product_id: UUID
    spec_id: UUID
    build_version: PositiveInt
    build_kind: Literal["PRIMARY", "VARIANT", "REPAIR", "ASSET", "DELIVERY"]
    artifacts: tuple[ArtifactReference, ...] = Field(min_length=1)
    checkpoint_names: tuple[NonEmptyStr, ...] = Field(min_length=1)
    provider_object_references: dict[str, NonEmptyStr] = Field(default_factory=dict)
    completed_at: UtcDatetime

    @model_validator(mode="after")
    def validate_unique_outputs(self) -> Self:
        artifact_ids = tuple(reference.artifact_id for reference in self.artifacts)
        if len(set(artifact_ids)) != len(artifact_ids):
            raise ValueError("build artifacts must be unique")
        if len(set(self.checkpoint_names)) != len(self.checkpoint_names):
            raise ValueError("checkpoint names must be unique")
        return self


class ProductQAResult(ContractModel):
    """Product build QA outcome with check-level evidence."""

    result_id: UUID
    build_result_id: UUID
    checked_artifact_ids: tuple[UUID, ...] = Field(min_length=1)
    outcome: BranchOutcome
    checks: tuple[CheckResult, ...] = Field(min_length=1)
    defect_codes: tuple[NonEmptyStr, ...]
    evidence: tuple[EvidenceReference, ...] = Field(min_length=1)
    completed_at: UtcDatetime

    @model_validator(mode="after")
    def validate_outcome(self) -> Self:
        failed_checks = tuple(check for check in self.checks if not check.passed)
        if len(set(self.checked_artifact_ids)) != len(self.checked_artifact_ids):
            raise ValueError("checked artifact IDs must be unique")
        if self.outcome not in {BranchOutcome.PASS, BranchOutcome.FAIL}:
            raise ValueError("ProductQAResult outcome must be PASS or FAIL")
        if self.outcome is BranchOutcome.PASS and failed_checks:
            raise ValueError("PASS requires every check to pass")
        if self.outcome is BranchOutcome.PASS and self.defect_codes:
            raise ValueError("PASS forbids defect codes")
        if self.outcome is BranchOutcome.FAIL and not failed_checks:
            raise ValueError("FAIL requires a failed check")
        if self.outcome is BranchOutcome.FAIL and not self.defect_codes:
            raise ValueError("FAIL requires defect codes")
        return self
