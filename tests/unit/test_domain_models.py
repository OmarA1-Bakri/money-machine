from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from money_machine.domain.enums import (
    AgentRunStatus,
    BranchOutcome,
    DecisionType,
    IncidentType,
    JobStatus,
    RetryClass,
    SideEffectClass,
)
from money_machine.domain.events import EventName
from money_machine.domain.models import (
    AgentResult,
    ArtifactReference,
    BuildResult,
    CheckResult,
    ContractError,
    DedupeCollision,
    DedupeResult,
    EffectReference,
    EvidenceReference,
    IncidentResult,
    JobEnvelope,
    ListingPackage,
    ListingRules,
    MetricsSnapshot,
    PortfolioDecision,
    PreflightResult,
    ProductQAResult,
    ProductShapeRules,
    ProductSpec,
    ResearchObservation,
    ResearchReport,
    SuccessContract,
    TeardownReport,
)

NON_UTC = timezone(timedelta(hours=2))
OBSERVED_AT = datetime(2026, 8, 26, 12, 0, tzinfo=NON_UTC)
SHA256 = "a" * 64
LISTING_RULES = ListingRules(
    rule_version="product-rules-v1",
    tags=13,
    images=10,
    videos=1,
    description_sections=8,
    quantity=999,
    image_role="listing_image",
    video_role="listing_video",
)
SHAPE_RULES = ProductShapeRules(
    rule_version="product-rules-v1",
    hubs_minimum=6,
    hubs_maximum=8,
    colour_variants_minimum=3,
    colour_variants_maximum=4,
)


def artifact_reference(
    logical_role: str = "product-build",
    *,
    job_id: UUID | None = None,
    agent_run_id: UUID | None = None,
) -> ArtifactReference:
    return ArtifactReference(
        artifact_id=uuid4(),
        logical_role=logical_role,
        media_type="application/json",
        sha256=SHA256,
        byte_size=128,
        storage_reference="artifact://build/1",
        producing_job_id=job_id or uuid4(),
        producing_agent_run_id=agent_run_id or uuid4(),
        created_at=OBSERVED_AT,
        sensitivity="INTERNAL",
        retention_class="LINEAGE",
    )


def evidence_reference() -> EvidenceReference:
    return EvidenceReference(
        evidence_id=uuid4(),
        evidence_type="provider-observation",
        source_reference="receipt://observation/1",
        observed_at=OBSERVED_AT,
        sha256=SHA256,
        safe_summary="Reconciled provider observation",
    )


def agent_result(**overrides: Any) -> AgentResult:
    values: dict[str, Any] = {
        "job_id": uuid4(),
        "agent_run_id": uuid4(),
        "agent_id": "A07",
        "agent_definition_version": 1,
        "prompt_reference": "agent://A07/system/v1",
        "prompt_sha256": SHA256,
        "status": AgentRunStatus.SUCCESS,
        "output": {"built": True},
    }
    values.update(overrides)
    return AgentResult(**values)


def check_result(*, passed: bool = True) -> CheckResult:
    return CheckResult(
        name="required-check",
        passed=passed,
        defect_code=None if passed else "CHECK_FAILED",
        evidence=(evidence_reference(),),
    )


def product_spec(**overrides: Any) -> ProductSpec:
    values: dict[str, Any] = {
        "spec_id": uuid4(),
        "workflow_id": uuid4(),
        "product_id": uuid4(),
        "version": 1,
        "shape_rules": SHAPE_RULES,
        "identity": "Weekly planning system",
        "base_category": "digital planner",
        "buyer_problem": "Weekly priorities are fragmented",
        "title": "Focused Weekly Planner",
        "tier": "core",
        "real_price": Decimal("12.00"),
        "anchor_price": Decimal("18.00"),
        "currency": "USD",
        "hubs": tuple(f"hub-{number}" for number in range(1, 7)),
        "colour_variants": ("navy", "sage", "sand"),
        "features": ("weekly review", "priority board"),
        "experiment_plan": "Test a calendar-first buyer journey",
        "concept_fingerprint": SHA256,
        "source_evidence": (evidence_reference(),),
        "created_at": OBSERVED_AT,
    }
    values.update(overrides)
    return ProductSpec(**values)


def test_canonical_contracts_share_strict_frozen_version_one_policy() -> None:
    contract_types = {
        JobEnvelope,
        AgentResult,
        ArtifactReference,
        EvidenceReference,
        ProductSpec,
        ResearchReport,
        TeardownReport,
        DedupeResult,
        BuildResult,
        ProductQAResult,
        ListingPackage,
        PreflightResult,
        MetricsSnapshot,
        PortfolioDecision,
        IncidentResult,
    }

    assert len(contract_types) == 15
    for contract_type in contract_types:
        assert contract_type.model_config.get("extra") == "forbid"
        assert contract_type.model_config.get("frozen") is True
        assert contract_type.model_config.get("strict") is True
        assert contract_type.model_fields["schema_version"].default == 1


def test_references_normalize_utc_and_reject_unknown_or_coerced_values() -> None:
    reference = artifact_reference()

    assert reference.created_at == datetime(2026, 8, 26, 10, 0, tzinfo=UTC)
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        ArtifactReference.model_validate({**reference.model_dump(), "unknown": "value"})
    with pytest.raises(ValidationError, match="valid integer"):
        ArtifactReference.model_validate({**reference.model_dump(), "byte_size": True})
    with pytest.raises(ValidationError, match="timezone-aware"):
        ArtifactReference.model_validate(
            {**reference.model_dump(), "created_at": datetime(2026, 8, 26)}
        )
    with pytest.raises(ValidationError, match="Instance is frozen"):
        reference.byte_size = 256  # type: ignore[misc]


def test_job_envelope_enforces_attempt_agent_and_json_payload_contracts() -> None:
    job = JobEnvelope(
        job_id=uuid4(),
        workflow_id=uuid4(),
        object_id=uuid4(),
        job_type="BuildProductJob",
        object_type="product",
        owner_agent_id="A07",
        status=JobStatus.READY,
        input={"spec_version": 1, "repair": False},
        required_artifacts=(artifact_reference(),),
        scheduled_at=OBSERVED_AT,
        attempt=1,
        max_attempts=3,
        idempotency_key="build-product:workflow:spec-v1",
        side_effect_class=SideEffectClass.EXTERNAL_WRITE,
        retry_class=RetryClass.RECONCILE_FIRST,
        success_contract=SuccessContract(
            output_model="BuildResult",
            required_artifact_roles=("product-build",),
            required_events=(EventName.BUILD_COMPLETED,),
        ),
    )

    assert job.scheduled_at.tzinfo is UTC
    with pytest.raises(ValidationError, match="attempt cannot exceed max_attempts"):
        JobEnvelope.model_validate({**job.model_dump(), "attempt": 4})
    with pytest.raises(ValidationError, match="String should match pattern"):
        JobEnvelope.model_validate({**job.model_dump(), "owner_agent_id": "A17"})
    with pytest.raises(ValidationError, match="valid string"):
        JobEnvelope.model_validate({**job.model_dump(), "job_type": 7})
    with pytest.raises(ValidationError):
        JobEnvelope.model_validate({**job.model_dump(), "input": {"not_json": uuid4()}})


def test_agent_result_enforces_status_error_and_event_invariants() -> None:
    job_id = uuid4()
    run_id = uuid4()
    success = agent_result(
        job_id=job_id,
        agent_run_id=run_id,
        output={"build_result_id": str(uuid4())},
        artifacts=(artifact_reference(job_id=job_id, agent_run_id=run_id),),
        evidence=(evidence_reference(),),
        emitted_events=(EventName.BUILD_COMPLETED,),
        error=None,
    )

    assert success.error is None
    assert success.prompt_sha256 == SHA256
    with pytest.raises(ValidationError, match="SUCCESS forbids an error"):
        AgentResult.model_validate(
            {
                **success.model_dump(),
                "error": ContractError(code="FAILED", message="unexpected"),
            }
        )
    with pytest.raises(ValidationError, match="non-success result requires an error"):
        AgentResult.model_validate({**success.model_dump(), "status": AgentRunStatus.FAILURE})
    with pytest.raises(ValidationError, match="emitted events must be unique"):
        AgentResult.model_validate(
            {
                **success.model_dump(),
                "emitted_events": (EventName.BUILD_COMPLETED, EventName.BUILD_COMPLETED),
            }
        )


def test_agent_result_carries_the_lineage_chain_and_uncertain_effects() -> None:
    job_id = uuid4()
    run_id = uuid4()
    unknown_effect = EffectReference(
        idempotency_key="ETSY_PUBLISH:1",
        provider="etsy",
        operation="ETSY_PUBLISH",
        effect_state="UNKNOWN",
        observed_at=OBSERVED_AT,
    )

    uncertain = agent_result(
        job_id=job_id,
        agent_run_id=run_id,
        agent_id="A13",
        status=AgentRunStatus.UNCERTAIN_EXTERNAL_EFFECT,
        effects=(unknown_effect,),
        error=ContractError(code="UNCERTAIN", message="publish outcome unknown"),
    )
    assert uncertain.effects[0].effect_state == "UNKNOWN"

    with pytest.raises(ValidationError, match="must cite the unresolved effect"):
        agent_result(
            job_id=job_id,
            agent_run_id=run_id,
            status=AgentRunStatus.UNCERTAIN_EXTERNAL_EFFECT,
            error=ContractError(code="UNCERTAIN", message="publish outcome unknown"),
        )
    with pytest.raises(ValidationError, match="must cite this agent run"):
        agent_result(
            job_id=job_id, agent_run_id=run_id, artifacts=(artifact_reference(job_id=job_id),)
        )
    with pytest.raises(ValidationError, match="must cite this job"):
        agent_result(
            job_id=job_id,
            agent_run_id=run_id,
            artifacts=(artifact_reference(agent_run_id=run_id),),
        )
    with pytest.raises(ValidationError, match="String should match pattern"):
        agent_result(agent_id="A17")
    with pytest.raises(ValidationError, match="a confirmed effect must identify"):
        EffectReference(
            idempotency_key="k",
            provider="etsy",
            operation="ETSY_PUBLISH",
            effect_state="CONFIRMED",
            observed_at=OBSERVED_AT,
        )
    with pytest.raises(ValidationError, match="an absent effect cannot identify"):
        EffectReference(
            idempotency_key="k",
            provider="etsy",
            operation="ETSY_PUBLISH",
            provider_object_id="listing-1",
            effect_state="ABSENT",
            observed_at=OBSERVED_AT,
        )


def test_product_spec_enforces_price_and_lineage_invariants() -> None:
    spec = product_spec()

    assert spec.created_at.tzinfo is UTC
    with pytest.raises(ValidationError, match="anchor_price must be at least real_price"):
        product_spec(anchor_price=Decimal("10.00"))
    with pytest.raises(ValidationError, match="parent_spec_id cannot equal spec_id"):
        product_spec(parent_spec_id=spec.spec_id, spec_id=spec.spec_id)


def test_research_and_teardown_results_require_cited_structured_evidence() -> None:
    observation = ResearchObservation(
        observation_id=uuid4(),
        source_reference="market://listing/1",
        observed_at=OBSERVED_AT,
        title="Weekly Planner",
        shop_reference="market://shop/1",
        facts={"price": 12.0, "digital": True},
        evidence=(evidence_reference(),),
    )
    report = ResearchReport(
        report_id=uuid4(),
        workflow_id=uuid4(),
        source_policy_version="research-policy-v1",
        query_terms=("weekly planner",),
        observations=(observation,),
        completed_at=OBSERVED_AT,
    )
    teardown = TeardownReport(
        report_id=uuid4(),
        workflow_id=report.workflow_id,
        competitor_reference="market://listing/1",
        structure_components=("weekly dashboard", "review flow"),
        buyer_journey=("capture", "prioritize", "review"),
        mechanics=("linked database",),
        copied_protected_content=False,
        source_evidence=(evidence_reference(),),
        completed_at=OBSERVED_AT,
    )

    assert report.completed_at.tzinfo is UTC
    assert teardown.copied_protected_content is False
    with pytest.raises(ValidationError):
        ResearchReport.model_validate({**report.model_dump(), "observations": ()})
    with pytest.raises(ValidationError):
        TeardownReport.model_validate({**teardown.model_dump(), "copied_protected_content": True})


def test_dedupe_result_distinguishes_pass_from_too_close() -> None:
    other_spec_id = uuid4()
    collision = DedupeCollision(
        other_spec_id=other_spec_id,
        reason="TITLE_SIMILARITY",
        similarity=Decimal("0.75"),
        evidence=(evidence_reference(),),
    )
    spec_id = uuid4()
    common: dict[str, Any] = {
        "result_id": uuid4(),
        "workflow_id": uuid4(),
        "spec_id": spec_id,
        "rule_version": "title-jaccard-v1",
        "normalized_title": "focused weekly planner",
        "concept_fingerprint": SHA256,
        "title_similarity_threshold": Decimal("0.70"),
        "compared_spec_ids": (other_spec_id,),
        "completed_at": OBSERVED_AT,
    }

    passed = DedupeResult(
        **common,
        outcome=BranchOutcome.PASS,
        differentiation_evidence=("buyer problem differs",),
    )
    too_close = DedupeResult(**common, outcome=BranchOutcome.TOO_CLOSE, collisions=(collision,))

    def with_compared(compared: tuple[UUID, ...]) -> dict[str, Any]:
        values: dict[str, Any] = dict(common)
        values["compared_spec_ids"] = compared
        return values

    empty_catalogue = DedupeResult(**with_compared(()), outcome=BranchOutcome.PASS)
    assert passed.rule_version == too_close.rule_version == empty_catalogue.rule_version

    with pytest.raises(ValidationError, match="PASS forbids collisions"):
        DedupeResult(
            **common,
            outcome=BranchOutcome.PASS,
            collisions=(collision,),
            differentiation_evidence=("x",),
        )
    with pytest.raises(ValidationError, match="requires differentiation"):
        DedupeResult(**common, outcome=BranchOutcome.PASS)
    with pytest.raises(ValidationError, match="TOO_CLOSE requires collision evidence"):
        DedupeResult(**common, outcome=BranchOutcome.TOO_CLOSE)
    with pytest.raises(ValidationError, match="cannot claim differentiation"):
        DedupeResult(
            **common,
            outcome=BranchOutcome.TOO_CLOSE,
            collisions=(collision,),
            differentiation_evidence=("reworded title",),
        )
    with pytest.raises(ValidationError, match="must cite a compared spec"):
        DedupeResult(
            **with_compared((uuid4(),)),
            outcome=BranchOutcome.TOO_CLOSE,
            collisions=(collision,),
        )
    with pytest.raises(ValidationError, match="not compared with itself"):
        DedupeResult(
            **with_compared((spec_id,)),
            outcome=BranchOutcome.PASS,
            differentiation_evidence=("x",),
        )
    with pytest.raises(ValidationError, match="DedupeResult outcome"):
        DedupeResult(**common, outcome=BranchOutcome.FAIL)
    weak = DedupeCollision.model_validate({**collision.model_dump(), "similarity": Decimal("0.10")})
    with pytest.raises(ValidationError, match="must meet the configured threshold"):
        DedupeResult(**common, outcome=BranchOutcome.TOO_CLOSE, collisions=(weak,))


def test_build_and_product_qa_results_enforce_verification_outcomes() -> None:
    build = BuildResult(
        result_id=uuid4(),
        workflow_id=uuid4(),
        product_id=uuid4(),
        spec_id=uuid4(),
        build_version=1,
        build_kind="PRIMARY",
        artifacts=(artifact_reference(),),
        checkpoint_names=("structure-created", "links-recorded"),
        provider_object_references={"notion_page": "provider://notion/page/1"},
        completed_at=OBSERVED_AT,
    )
    checked = tuple(reference.artifact_id for reference in build.artifacts)
    ProductQAResult(
        result_id=uuid4(),
        build_result_id=build.result_id,
        checked_artifact_ids=checked,
        outcome=BranchOutcome.PASS,
        checks=(check_result(),),
        defect_codes=(),
        evidence=(evidence_reference(),),
        completed_at=OBSERVED_AT,
    )
    with pytest.raises(ValidationError, match="checked artifact IDs must be unique"):
        ProductQAResult(
            result_id=uuid4(),
            build_result_id=build.result_id,
            checked_artifact_ids=(checked[0], checked[0]),
            outcome=BranchOutcome.PASS,
            checks=(check_result(),),
            defect_codes=(),
            evidence=(evidence_reference(),),
            completed_at=OBSERVED_AT,
        )
    with pytest.raises(ValidationError, match="PASS requires every check to pass"):
        ProductQAResult(
            result_id=uuid4(),
            build_result_id=build.result_id,
            checked_artifact_ids=checked,
            outcome=BranchOutcome.PASS,
            checks=(check_result(passed=False),),
            defect_codes=("CHECK_FAILED",),
            evidence=(evidence_reference(),),
            completed_at=OBSERVED_AT,
        )
    with pytest.raises(ValidationError, match="FAIL requires a failed check"):
        ProductQAResult(
            result_id=uuid4(),
            build_result_id=build.result_id,
            checked_artifact_ids=checked,
            outcome=BranchOutcome.FAIL,
            checks=(check_result(),),
            defect_codes=(),
            evidence=(evidence_reference(),),
            completed_at=OBSERVED_AT,
        )


def listing_package(**overrides: Any) -> ListingPackage:
    values: dict[str, Any] = {
        "package_id": uuid4(),
        "workflow_id": uuid4(),
        "product_id": uuid4(),
        "spec_id": uuid4(),
        "listing_version": 1,
        "rules": LISTING_RULES,
        "title": "Focused Weekly Planner",
        "description_sections": tuple(f"section {number}" for number in range(1, 9)),
        "tags": tuple(f"tag {number}" for number in range(1, 14)),
        "currency": "USD",
        "price": Decimal("12.00"),
        "anchor_price": Decimal("18.00"),
        "quantity": 999,
        "digital_product": True,
        "media_artifacts": (
            *(artifact_reference("listing_image") for _ in range(10)),
            artifact_reference("listing_video"),
        ),
        "delivery_artifacts": (artifact_reference("delivery_pdf"),),
        "claim_evidence": (evidence_reference(),),
        "package_sha256": SHA256,
        "created_at": OBSERVED_AT,
    }
    values.update(overrides)
    return ListingPackage(**values)


def test_listing_package_binds_the_configured_playbook_shape() -> None:
    package = listing_package()
    assert len(package.tags) == 13
    assert package.description.count("\n\n") == 7
    assert package.rules.rule_version == "product-rules-v1"

    images = tuple(artifact_reference("listing_image") for _ in range(10))
    video = artifact_reference("listing_video")
    cases: tuple[tuple[str, dict[str, Any]], ...] = (
        ("exactly 13 tags, got 12", {"tags": tuple(f"tag {n}" for n in range(12))}),
        ("exactly 13 tags, got 14", {"tags": tuple(f"tag {n}" for n in range(14))}),
        ("exactly 10 images, got 9", {"media_artifacts": (*images[:9], video)}),
        ("exactly 1 videos, got 0", {"media_artifacts": images}),
        (
            "exactly 1 videos, got 2",
            {"media_artifacts": (*images, video, artifact_reference("listing_video"))},
        ),
        (
            "must all be listing images or videos",
            {"media_artifacts": (*images, video, artifact_reference("mockup"))},
        ),
        ("exactly 8 sections, got 7", {"description_sections": tuple(f"s{n}" for n in range(7))}),
        ("quantity must be 999, got 998", {"quantity": 998}),
        ("quantity must be 999, got 1000", {"quantity": 1000}),
        ("anchor_price must be at least the listing price", {"anchor_price": Decimal("11.99")}),
    )
    for expected, overrides in cases:
        with pytest.raises(ValidationError, match=expected):
            listing_package(**overrides)


def test_product_spec_binds_the_configured_hub_and_variant_ranges() -> None:
    assert len(product_spec().hubs) == 6
    cases: tuple[tuple[str, dict[str, Any]], ...] = (
        ("requires 6-8 hubs, got 2", {"hubs": ("a", "b")}),
        ("requires 6-8 hubs, got 9", {"hubs": tuple(f"hub-{n}" for n in range(9))}),
        ("hubs must be unique", {"hubs": ("Hub", "hub", "c", "d", "e", "f")}),
        ("requires 3-4 colour variants, got 1", {"colour_variants": ("navy",)}),
        ("requires 3-4 colour variants, got 5", {"colour_variants": ("a", "b", "c", "d", "e")}),
        ("colour variants must be unique", {"colour_variants": ("navy", "Navy", "sand")}),
    )
    for expected, overrides in cases:
        with pytest.raises(ValidationError, match=expected):
            product_spec(**overrides)


def test_listing_package_and_preflight_result_are_immutable_launch_snapshots() -> None:
    package = listing_package()
    PreflightResult(
        result_id=uuid4(),
        listing_package_id=package.package_id,
        listing_package_sha256=package.package_sha256,
        outcome=BranchOutcome.PASS,
        checks=(check_result(),),
        repair_job_types=(),
        evidence=(evidence_reference(),),
        completed_at=OBSERVED_AT,
    )
    with pytest.raises(ValidationError, match="PASS forbids repair jobs"):
        PreflightResult(
            result_id=uuid4(),
            listing_package_id=package.package_id,
            listing_package_sha256=package.package_sha256,
            outcome=BranchOutcome.PASS,
            checks=(check_result(),),
            repair_job_types=("ListingRepairJob",),
            evidence=(evidence_reference(),),
            completed_at=OBSERVED_AT,
        )
    with pytest.raises(ValidationError, match="FAIL requires a failed check"):
        PreflightResult(
            result_id=uuid4(),
            listing_package_id=package.package_id,
            listing_package_sha256=package.package_sha256,
            outcome=BranchOutcome.FAIL,
            checks=(check_result(),),
            repair_job_types=("ListingRepairJob",),
            evidence=(evidence_reference(),),
            completed_at=OBSERVED_AT,
        )


def test_metrics_snapshot_rejects_negative_counts_and_normalizes_time() -> None:
    snapshot = MetricsSnapshot(
        snapshot_id=uuid4(),
        listing_id=uuid4(),
        listing_version=1,
        provider="ETSY",
        observed_at=OBSERVED_AT,
        views=12,
        favourites=3,
        orders=1,
        gross_revenue=Decimal("12.00"),
        currency="USD",
        reconciled=True,
        source_evidence=(evidence_reference(),),
    )

    assert snapshot.observed_at.tzinfo is UTC
    with pytest.raises(ValidationError):
        MetricsSnapshot.model_validate({**snapshot.model_dump(), "views": -1})


@pytest.mark.parametrize(
    ("decision", "required_field"),
    [
        (DecisionType.REPAIR, "repair_job_id"),
        (DecisionType.CULL, "deactivation_job_id"),
        (DecisionType.MULTIPLY, "successor_workflow_id"),
    ],
)
def test_portfolio_decision_requires_branch_specific_lineage(
    decision: DecisionType,
    required_field: str,
) -> None:
    with pytest.raises(ValidationError, match=required_field):
        PortfolioDecision(
            decision_id=uuid4(),
            workflow_id=uuid4(),
            product_id=uuid4(),
            listing_id=uuid4(),
            decision=decision,
            metrics_snapshot_ids=(uuid4(),),
            cohort_reference="shop:default:30d",
            rule_version="portfolio-rules-v1",
            explanation="Evidence-backed decision",
            evidence=(evidence_reference(),),
            decided_at=OBSERVED_AT,
        )


def test_multiply_decision_requires_new_workflow_and_spec_identity() -> None:
    parent_workflow_id = uuid4()
    successor_workflow_id = uuid4()
    decision = PortfolioDecision(
        decision_id=uuid4(),
        product_id=uuid4(),
        listing_id=uuid4(),
        workflow_id=parent_workflow_id,
        decision=DecisionType.MULTIPLY,
        metrics_snapshot_ids=(uuid4(),),
        cohort_reference="shop:default:30d",
        rule_version="portfolio-rules-v1",
        explanation="Winner satisfies the multiply contract",
        evidence=(evidence_reference(),),
        successor_workflow_id=successor_workflow_id,
        successor_spec_id=uuid4(),
        decided_at=OBSERVED_AT,
    )

    assert decision.successor_workflow_id != decision.workflow_id
    with pytest.raises(ValidationError, match="successor workflow must differ"):
        PortfolioDecision.model_validate(
            {
                **decision.model_dump(),
                "successor_workflow_id": parent_workflow_id,
            }
        )


def test_incident_result_enforces_resolution_and_uncertainty_evidence() -> None:
    common: dict[str, Any] = {
        "result_id": uuid4(),
        "incident_id": uuid4(),
        "incident_type": IncidentType.BROKEN_LINK,
        "affected_object_type": "listing_version",
        "affected_object_id": uuid4(),
        "affected_version": 1,
        "opening_event": EventName.BROKEN_LINK_DETECTED,
        "opening_job_id": uuid4(),
        "safe_detail": "Delivery link returned a non-success response",
        "evidence": (evidence_reference(),),
        "opened_at": OBSERVED_AT,
    }
    IncidentResult(
        **common,
        status="RESOLVED",
        resolution_job_id=uuid4(),
        resolution_result_reference="result://repair/1",
        resolved_at=OBSERVED_AT,
    )
    with pytest.raises(ValidationError, match="RESOLVED requires"):
        IncidentResult(**common, status="RESOLVED")
    with pytest.raises(ValidationError, match="UNCERTAIN_EXTERNAL_EFFECT requires an error"):
        IncidentResult(**common, status="UNCERTAIN_EXTERNAL_EFFECT")


def test_contract_ids_are_real_uuids_not_coerced_strings() -> None:
    reference = artifact_reference()
    dumped = reference.model_dump()

    assert isinstance(reference.artifact_id, UUID)
    with pytest.raises(ValidationError, match="instance of UUID"):
        ArtifactReference.model_validate({**dumped, "artifact_id": str(reference.artifact_id)})
