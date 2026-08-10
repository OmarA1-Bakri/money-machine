"""Contract tests for the frozen first-product domain surface."""

from __future__ import annotations

import os
import subprocess
import sys
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, cast
from uuid import UUID

import pytest
from pydantic import AnyHttpUrl, BaseModel, ValidationError

from money_machine.domain.enums import JobState, ProductState, QualificationDimension, RetryClass
from money_machine.domain.events import DomainEvent, DomainEventName
from money_machine.domain.models.asset import ArtifactReference
from money_machine.domain.models.candidate import CandidateShortlist, QualificationScore
from money_machine.domain.models.job import JobAttempt, JobEnvelope
from money_machine.domain.models.listing import ListingPackage, PreflightResult
from money_machine.domain.models.product import BuildResult, ProductQAResult
from money_machine.domain.models.product_spec import (
    DedupeResult,
    ProductFact,
    ProductFactCategory,
    ProductSpec,
)
from money_machine.domain.models.research import (
    EvidenceReference,
    ResearchObservation,
    ResearchPacket,
)
from money_machine.domain.models.workflow import WorkflowRun
from money_machine.domain.value_objects import canonical_json, canonical_sha256

SHA256 = "a" * 64
NOW = datetime(2026, 8, 9, 8, 0, tzinfo=UTC)
REPO_ROOT = Path(__file__).resolve().parents[3]


def _evidence(index: int = 0) -> EvidenceReference:
    return EvidenceReference(
        evidence_id=f"evidence-{index}",
        source_url=AnyHttpUrl(f"https://example.test/listing/{index}"),
        observed_at=NOW,
        source_mode="fixture",
        freshness_status="current",
        content_sha256=SHA256,
    )


def _observation(index: int = 0) -> ResearchObservation:
    return ResearchObservation(
        observation_id=f"observation-{index}",
        evidence=_evidence(index),
        marketplace="etsy",
        title=f"Planner {index}",
        category="digital-planners",
        identity_niche="adhd-students",
        base_category="planner",
        price=Decimal("12.00"),
        currency="USD",
        demand_proxies={"reviews": Decimal("10")},
        competition_proxies={"result_count": Decimal("100")},
        qualification_inputs={
            QualificationDimension.DEMAND: Decimal("8"),
            QualificationDimension.DIFFERENTIATION: Decimal("7"),
            QualificationDimension.BUILD_FEASIBILITY: Decimal("9"),
            QualificationDimension.BUYER_VALUE: Decimal("8"),
        },
        listing_quality_notes=("Clear benefit-led title",),
    )


def _packet(row_count: int) -> ResearchPacket:
    return ResearchPacket(
        packet_id=f"packet-{row_count}",
        imported_at=NOW,
        observations=tuple(_observation(index) for index in range(row_count)),
        packet_sha256=SHA256,
    )


def _score(total: int = 30) -> QualificationScore:
    base, remainder = divmod(total, 4)
    dimensions = tuple(base + (1 if index < remainder else 0) for index in range(4))
    return QualificationScore(
        candidate_id=f"candidate-{total}",
        demand=dimensions[0],
        differentiation=dimensions[1],
        build_feasibility=dimensions[2],
        buyer_value=dimensions[3],
        evidence_ids=("evidence-0",),
    )


def _spec(**overrides: Any) -> ProductSpec:
    fields: dict[str, object] = {
        "product_spec_id": "spec-1",
        "candidate_id": "candidate-30",
        "identity_niche": "adhd-students",
        "base_category": "planner",
        "target_buyer": "People managing adhd-students",
        "promised_outcome": "A structured planner workspace",
        "hubs": ("home", "courses", "tasks", "notes", "reviews", "archive"),
        "colour_variants": ("ink", "sand", "sage"),
        "features": ("Linked course and task views",),
        "source_evidence_ids": ("evidence-0",),
        "spec_sha256": SHA256,
    }
    fields.update(overrides)
    if "product_facts" not in overrides:
        hubs = cast(tuple[str, ...], fields["hubs"])
        features = cast(tuple[str, ...], fields["features"])
        colour_variants = cast(tuple[str, ...], fields["colour_variants"])
        evidence_ids = cast(tuple[str, ...], fields["source_evidence_ids"])
        fields["product_facts"] = (
            ProductFact(
                claim=f"Configured with {len(hubs)} hubs",
                category="HUB_INVENTORY",
                evidence_ids=evidence_ids,
            ),
            *(
                ProductFact(
                    claim=f"Includes {feature}",
                    category="FEATURE",
                    evidence_ids=evidence_ids,
                )
                for feature in features
            ),
            ProductFact(
                claim=f"Configured with {len(colour_variants)} colour variants",
                category="COLOUR_VARIANTS",
                evidence_ids=evidence_ids,
            ),
            ProductFact(
                claim=cast(str, fields["target_buyer"]),
                category="BUYER_FIT",
                evidence_ids=evidence_ids,
            ),
            ProductFact(
                claim=cast(str, fields["promised_outcome"]),
                category="WORKFLOW_OUTCOME",
                evidence_ids=evidence_ids,
            ),
        )
    return ProductSpec.model_validate(fields, strict=True)


def _all_approved_contracts() -> tuple[BaseModel, ...]:
    artifact = ArtifactReference(
        artifact_id="artifact-1",
        relative_path=Path("products/spec-1/index.html"),
        media_type="text/html",
        byte_count=1,
        content_sha256=SHA256,
    )
    score = _score()
    return (
        _observation(),
        _packet(25),
        score,
        CandidateShortlist(
            shortlist_id="shortlist-1",
            packet_id="packet-25",
            candidates=(score,),
            selected_candidate_id=score.candidate_id,
            shortlist_sha256=SHA256,
        ),
        _spec(),
        DedupeResult(
            dedupe_result_id="dedupe-1",
            product_spec_id="spec-1",
            passed=True,
            matched_product_spec_ids=(),
            reasons=(),
            result_sha256=SHA256,
        ),
        BuildResult(
            build_id="build-1",
            product_spec_id="spec-1",
            root_artifact_path="products/spec-1",
            artifacts=(artifact,),
            manifest_sha256=SHA256,
            renderer_version="1",
        ),
        ProductQAResult(
            qa_result_id="qa-1",
            build_id="build-1",
            passed=True,
            findings=(),
            checked_at=NOW,
            result_sha256=SHA256,
        ),
        ListingPackage(
            listing_package_id="listing-1",
            product_spec_id="spec-1",
            build_id="build-1",
            title="Planner",
            description="A useful planner",
            tags=tuple(f"tag-{index}" for index in range(13)),
            feature_statements=(),
            buyer_fit_statements=(),
            package_sha256=SHA256,
        ),
        PreflightResult(
            preflight_result_id="preflight-1",
            listing_package_id="listing-1",
            passed=True,
            findings=(),
            checked_at=NOW,
            external_effect_mode="simulation",
            incremental_spend=Decimal("0.00"),
            publication_receipt_present=False,
            result_sha256=SHA256,
        ),
        artifact,
        _evidence(),
        JobEnvelope(
            job_id=UUID("00000000-0000-0000-0000-000000000001"),
            workflow_run_id=UUID("00000000-0000-0000-0000-000000000002"),
            job_type="ADMIT_RESEARCH_PACKET",
            state=JobState.READY,
            idempotency_key="first-product:packet-25:admit",
            input_sha256=SHA256,
            retry_class=RetryClass.TRANSIENT_INTERNAL,
            max_attempts=3,
        ),
        JobAttempt(
            attempt_id=UUID("00000000-0000-0000-0000-000000000003"),
            job_id=UUID("00000000-0000-0000-0000-000000000001"),
            attempt_number=1,
            state=JobState.RUNNING,
            started_at=NOW,
            completed_at=None,
        ),
        DomainEvent(
            event_id=UUID("00000000-0000-0000-0000-000000000004"),
            workflow_run_id=UUID("00000000-0000-0000-0000-000000000002"),
            job_id=None,
            name=DomainEventName.RESEARCH_PACKET_ADMITTED,
            occurred_at=NOW,
            payload={},
            payload_sha256=SHA256,
        ),
        WorkflowRun(
            workflow_run_id=UUID("00000000-0000-0000-0000-000000000002"),
            workflow_type="first-product",
            packet_id="packet-25",
            state=ProductState.RESEARCHED,
            idempotency_key="first-product:packet-25",
            created_at=NOW,
            updated_at=NOW,
        ),
    )


def test_required_enums_serialize_to_exact_values() -> None:
    assert [item.value for item in QualificationDimension] == [
        "demand",
        "differentiation",
        "build_feasibility",
        "buyer_value",
    ]
    assert [item.value for item in ProductState] == [
        "RESEARCHED",
        "QUALIFIED",
        "SPECIFIED",
        "DEDUPE_PASSED",
        "BUILT",
        "QA_PASSED",
        "MERCHANDISED",
        "PREFLIGHT_PASSED",
        "DRAFT_READY",
        "INSUFFICIENT_EVIDENCE",
        "REJECTED",
        "FAILED",
    ]
    assert [item.value for item in JobState] == [
        "PENDING",
        "READY",
        "LEASED",
        "RUNNING",
        "RETRY_WAIT",
        "SUCCEEDED",
        "FAILED",
        "CANCELLED",
    ]
    assert [item.value for item in RetryClass] == [
        "NEVER",
        "TRANSIENT_INTERNAL",
        "TRANSIENT_PROVIDER_READ",
        "RECONCILE_EXTERNAL_EFFECT",
        "OPERATOR_REQUIRED",
    ]


def test_frozen_models_reject_unknown_fields_and_mutation() -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        EvidenceReference.model_validate(
            {
                **_evidence().model_dump(),
                "unreviewed": True,
            },
            strict=True,
        )

    evidence = _evidence()
    with pytest.raises(ValidationError, match="Instance is frozen"):
        evidence.evidence_id = "changed"


def test_all_approved_contracts_have_exact_schema_version() -> None:
    contracts = _all_approved_contracts()

    assert len(contracts) == 16
    for contract in contracts:
        dumped = contract.model_dump()
        assert dumped["schema_version"] == 1
        with pytest.raises(ValidationError, match="schema_version"):
            contract.__class__.model_validate({**dumped, "schema_version": 2}, strict=True)


def test_timestamps_must_be_timezone_aware() -> None:
    with pytest.raises(ValidationError, match="timezone"):
        EvidenceReference(
            evidence_id="evidence-naive",
            source_url=AnyHttpUrl("https://example.test/listing/naive"),
            observed_at=datetime(2026, 8, 9, 8, 0),
            source_mode="fixture",
            freshness_status="current",
            content_sha256=SHA256,
        )

    with pytest.raises(ValidationError, match="timezone"):
        ResearchPacket(
            packet_id="packet-naive",
            imported_at=datetime(2026, 8, 9, 8, 0),
            observations=tuple(_observation(index) for index in range(25)),
            packet_sha256=SHA256,
        )


@pytest.mark.parametrize("row_count", [25, 40])
def test_research_packet_accepts_inclusive_row_boundaries(row_count: int) -> None:
    assert len(_packet(row_count).observations) == row_count


@pytest.mark.parametrize("row_count", [24, 41])
def test_research_packet_rejects_rows_outside_target(row_count: int) -> None:
    with pytest.raises(ValidationError):
        _packet(row_count)


@pytest.mark.parametrize("bad_hash", ["a" * 63, "A" * 64, "g" * 64])
def test_contract_hashes_are_lowercase_sha256(bad_hash: str) -> None:
    with pytest.raises(ValidationError, match="string_pattern_mismatch"):
        EvidenceReference(
            evidence_id="evidence-bad-hash",
            source_url=AnyHttpUrl("https://example.test/listing/hash"),
            observed_at=NOW,
            source_mode="fixture",
            freshness_status="current",
            content_sha256=bad_hash,
        )
    with pytest.raises(ValidationError, match="string_pattern_mismatch"):
        _spec(spec_sha256=bad_hash)


def test_score_bounds_and_threshold_are_exact() -> None:
    below = _score(29)
    threshold = _score(30)
    assert below.total == 29
    assert below.meets_threshold is False
    assert threshold.total == 30
    assert threshold.meets_threshold is True

    with pytest.raises(ValidationError):
        QualificationScore(
            candidate_id="candidate-invalid",
            demand=11,
            differentiation=7,
            build_feasibility=7,
            buyer_value=7,
            evidence_ids=("evidence-0",),
        )


def test_shortlist_selection_requires_a_listed_threshold_candidate() -> None:
    scores = tuple(_score(total) for total in range(30, 35))
    shortlist = CandidateShortlist(
        shortlist_id="shortlist-1",
        packet_id="packet-25",
        candidates=scores,
        selected_candidate_id="candidate-34",
        shortlist_sha256=SHA256,
    )
    assert len(shortlist.candidates) == 5

    with pytest.raises(ValidationError, match="selected candidate"):
        CandidateShortlist(
            shortlist_id="shortlist-2",
            packet_id="packet-25",
            candidates=scores,
            selected_candidate_id="candidate-unlisted",
            shortlist_sha256=SHA256,
        )


@pytest.mark.parametrize("hub_count", [6, 8])
def test_product_spec_accepts_inclusive_hub_boundaries(hub_count: int) -> None:
    hubs = tuple(f"hub-{index}" for index in range(hub_count))
    assert len(_spec(hubs=hubs).hubs) == hub_count


@pytest.mark.parametrize("hub_count", [5, 9])
def test_product_spec_rejects_hubs_outside_boundaries(hub_count: int) -> None:
    with pytest.raises(ValidationError):
        _spec(hubs=tuple(f"hub-{index}" for index in range(hub_count)))


@pytest.mark.parametrize("variant_count", [3, 4])
def test_product_spec_accepts_inclusive_variant_boundaries(variant_count: int) -> None:
    variants = tuple(f"variant-{index}" for index in range(variant_count))
    assert len(_spec(colour_variants=variants).colour_variants) == variant_count


@pytest.mark.parametrize("variant_count", [2, 5])
def test_product_spec_rejects_variants_outside_boundaries(variant_count: int) -> None:
    with pytest.raises(ValidationError):
        _spec(colour_variants=tuple(f"variant-{index}" for index in range(variant_count)))


def test_product_spec_requires_typed_fact_specific_evidence() -> None:
    body: dict[str, object] = {
        "candidate_id": "candidate-30",
        "identity_niche": "adhd-students",
        "base_category": "planner",
        "target_buyer": "People managing adhd-students",
        "promised_outcome": "A structured planner workspace",
        "hubs": ("home", "courses", "tasks", "notes", "reviews", "archive"),
        "colour_variants": ("ink", "sand", "sage"),
        "features": ("Linked course and task views",),
        "product_facts": (
            {
                "claim": "Configured with 6 hubs",
                "category": "HUB_INVENTORY",
                "evidence_ids": ("evidence-0",),
            },
            {
                "claim": "Includes Linked course and task views",
                "category": "FEATURE",
                "evidence_ids": ("evidence-0",),
            },
            {
                "claim": "Configured with 3 colour variants",
                "category": "COLOUR_VARIANTS",
                "evidence_ids": ("evidence-0",),
            },
            {
                "claim": "People managing adhd-students",
                "category": "BUYER_FIT",
                "evidence_ids": ("evidence-0",),
            },
            {
                "claim": "A structured planner workspace",
                "category": "WORKFLOW_OUTCOME",
                "evidence_ids": ("evidence-0",),
            },
        ),
        "source_evidence_ids": ("evidence-0",),
    }
    digest = canonical_sha256(body)

    spec = ProductSpec.model_validate(
        {"product_spec_id": f"PS-{digest[:24]}", "spec_sha256": digest, **body},
        strict=True,
    )

    assert spec.product_facts[0].category == "HUB_INVENTORY"
    assert spec.product_facts[0].evidence_ids == ("evidence-0",)


def test_product_spec_rejects_commercial_outcome_even_with_recomputed_identity() -> None:
    body: dict[str, object] = {
        "candidate_id": "candidate-30",
        "identity_niche": "adhd-students",
        "base_category": "planner",
        "target_buyer": "People managing adhd-students",
        "promised_outcome": "Track guaranteed profits",
        "hubs": ("home", "courses", "tasks", "notes", "reviews", "archive"),
        "colour_variants": ("ink", "sand", "sage"),
        "features": ("Linked course and task views",),
        "product_facts": (
            {
                "claim": "People managing adhd-students",
                "category": "BUYER_FIT",
                "evidence_ids": ("evidence-0",),
            },
            {
                "claim": "Track guaranteed profits",
                "category": "WORKFLOW_OUTCOME",
                "evidence_ids": ("evidence-0",),
            },
        ),
        "source_evidence_ids": ("evidence-0",),
    }
    digest = canonical_sha256(body)

    with pytest.raises(ValidationError, match="promised outcome"):
        ProductSpec.model_validate(
            {"product_spec_id": f"PS-{digest[:24]}", "spec_sha256": digest, **body},
            strict=True,
        )


@pytest.mark.parametrize(
    ("category", "claim"),
    (
        ("FEATURE", "Guaranteed sales overnight"),
        ("HUB_INVENTORY", "Trusted by ten thousand buyers"),
        ("COLOUR_VARIANTS", "Passive income guaranteed"),
    ),
)
def test_product_spec_rejects_arbitrary_structural_fact_copy(
    category: ProductFactCategory,
    claim: str,
) -> None:
    original = _spec()
    facts = tuple(
        fact.model_copy(update={"claim": claim}) if fact.category == category else fact
        for fact in original.product_facts
    )
    if not any(fact.category == category for fact in facts):
        facts = (*facts, ProductFact(claim=claim, category=category, evidence_ids=("evidence-0",)))
    body = original.model_dump(
        mode="python",
        exclude={"schema_version", "product_spec_id", "spec_sha256", "product_facts"},
    )
    body["product_facts"] = tuple(fact.model_dump(mode="python") for fact in facts)
    digest = canonical_sha256(body)

    with pytest.raises(ValidationError, match="product facts"):
        ProductSpec.model_validate(
            {"product_spec_id": f"PS-{digest[:24]}", "spec_sha256": digest, **body},
            strict=True,
        )


@pytest.mark.parametrize(
    ("field", "category", "claim"),
    (
        ("promised_outcome", "WORKFLOW_OUTCOME", "Track guaranteed profits"),
        ("promised_outcome", "WORKFLOW_OUTCOME", "Manage passive income"),
        ("promised_outcome", "WORKFLOW_OUTCOME", "Access recurring revenue"),
        ("target_buyer", "BUYER_FIT", "Creators planning guaranteed profits"),
    ),
)
def test_truth_contract_rejects_commercial_claims_after_unvalidated_model_copy(
    field: str,
    category: str,
    claim: str,
) -> None:
    original = _spec()
    forged = original.model_copy(
        update={
            field: claim,
            "product_facts": tuple(
                fact.model_copy(update={"claim": claim}) if fact.category == category else fact
                for fact in original.product_facts
            ),
        }
    )

    with pytest.raises(ValueError, match="derived"):
        forged.ensure_truth_contract()


def test_job_envelope_is_strict_and_bounded() -> None:
    job = JobEnvelope(
        job_id=UUID("00000000-0000-0000-0000-000000000001"),
        workflow_run_id=UUID("00000000-0000-0000-0000-000000000002"),
        job_type="ADMIT_RESEARCH_PACKET",
        state=JobState.READY,
        idempotency_key="first-product:packet-25:admit",
        input_sha256=SHA256,
        retry_class=RetryClass.TRANSIENT_INTERNAL,
        max_attempts=3,
    )
    assert job.state is JobState.READY
    with pytest.raises(ValidationError):
        JobEnvelope.model_validate({**job.model_dump(), "max_attempts": 6}, strict=True)


def test_canonical_json_and_hash_are_stable_and_semantic() -> None:
    left = {"z": 1, "label": "café", "nested": {"b": 2, "a": 1}}
    right = {"nested": {"a": 1, "b": 2}, "label": "café", "z": 1}

    expected = b'{"label":"caf\xc3\xa9","nested":{"a":1,"b":2},"z":1}'
    assert canonical_json(left) == expected
    assert canonical_json(right) == expected
    assert canonical_sha256(left) == canonical_sha256(right)
    assert len(canonical_sha256(_spec())) == 64


def test_domain_mapping_fields_are_recursively_immutable_with_stable_hashes() -> None:
    observation = _observation()
    event = DomainEvent(
        event_id=UUID("00000000-0000-0000-0000-000000000004"),
        workflow_run_id=UUID("00000000-0000-0000-0000-000000000002"),
        job_id=None,
        name=DomainEventName.RESEARCH_PACKET_ADMITTED,
        occurred_at=NOW,
        payload={"nested": {"items": [{"value": 1}]}},
        payload_sha256=SHA256,
    )
    before = canonical_sha256(event), canonical_sha256(observation)

    with pytest.raises(TypeError):
        cast(dict[str, Decimal], observation.demand_proxies)["reviews"] = Decimal("999")
    with pytest.raises(TypeError):
        cast(dict[str, Decimal], observation.competition_proxies)["result_count"] = Decimal("999")
    with pytest.raises(TypeError):
        cast(dict[QualificationDimension, Decimal], observation.qualification_inputs)[
            QualificationDimension.DEMAND
        ] = Decimal("0")
    nested = cast(dict[str, object], event.payload["nested"])
    items = cast(list[object], nested["items"])
    with pytest.raises((AttributeError, TypeError)):
        items.append({"value": 2})
    with pytest.raises(TypeError):
        nested["extra"] = True

    assert (canonical_sha256(event), canonical_sha256(observation)) == before


@pytest.mark.parametrize("serializer", [canonical_json, canonical_sha256])
@pytest.mark.parametrize(
    "value",
    [
        {"nested": {"unordered": {"alpha", "beta"}}},
        {"nested": [frozenset({"alpha", "beta"})]},
        {"nested": {1: "non-string-key"}},
        {"nested": object()},
        {"nested": b"bytes-are-not-json"},
    ],
)
def test_canonical_functions_reject_unsupported_nested_values(
    serializer: Any, value: dict[str, object]
) -> None:
    with pytest.raises((TypeError, ValueError)):
        serializer(value)


@pytest.mark.parametrize("serializer", [canonical_json, canonical_sha256])
def test_canonical_functions_reject_cycles(serializer: Any) -> None:
    cycle: dict[str, object] = {}
    cycle["self"] = cycle

    with pytest.raises((TypeError, ValueError), match="cycle"):
        serializer(cycle)


def test_canonical_functions_are_hash_seed_deterministic_for_accepted_types() -> None:
    script = """
from money_machine.domain.value_objects import canonical_json, canonical_sha256
value = {
    "none": None,
    "bool": True,
    "integer": 7,
    "float": 1.25,
    "text": "café",
    "nested": {"sequence": [1, "two", (False, None)]},
}
print(canonical_json(value).hex())
print(canonical_sha256(value))
"""
    outputs: list[str] = []
    for seed in ("1", "2"):
        environment = {**os.environ, "PYTHONHASHSEED": seed, "PYTHONPATH": "src"}
        completed = subprocess.run(
            [sys.executable, "-c", script],
            cwd=REPO_ROOT,
            env=environment,
            check=True,
            capture_output=True,
            text=True,
        )
        outputs.append(completed.stdout)

    assert outputs[0] == outputs[1]


@pytest.mark.parametrize(
    ("annotation", "literal"),
    [
        ("set[str]", '{"alpha", "beta", "gamma", "delta"}'),
        ("frozenset[str]", 'frozenset({"alpha", "beta", "gamma", "delta"})'),
    ],
)
def test_canonical_functions_reject_unordered_basemodel_fields_across_hash_seeds(
    annotation: str, literal: str
) -> None:
    script = f"""
from pydantic import BaseModel, ConfigDict
from money_machine.domain.value_objects import canonical_json, canonical_sha256

class UnorderedModel(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True)
    values: {annotation}

value = UnorderedModel(values={literal})
for serializer in (canonical_json, canonical_sha256):
    try:
        serializer(value)
    except TypeError:
        print(f"{{serializer.__name__}}:rejected")
    else:
        print(f"{{serializer.__name__}}:accepted")
"""
    outputs: list[str] = []
    for seed in ("1", "2"):
        environment = {**os.environ, "PYTHONHASHSEED": seed, "PYTHONPATH": "src"}
        completed = subprocess.run(
            [sys.executable, "-c", script],
            cwd=REPO_ROOT,
            env=environment,
            check=True,
            capture_output=True,
            text=True,
        )
        outputs.append(completed.stdout)

    expected = "canonical_json:rejected\ncanonical_sha256:rejected\n"
    assert outputs == [expected, expected]


@pytest.mark.parametrize(
    ("annotation", "literal"),
    [
        ("set[str]", '{"alpha", "beta", "gamma", "delta"}'),
        ("frozenset[str]", 'frozenset({"alpha", "beta", "gamma", "delta"})'),
    ],
)
def test_canonical_functions_reject_field_serializer_hidden_unordered_values(
    annotation: str, literal: str
) -> None:
    script = f"""
from pydantic import BaseModel, ConfigDict, field_serializer
from money_machine.domain.value_objects import canonical_json, canonical_sha256

class UnorderedModel(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True)
    values: {annotation}

    @field_serializer("values")
    def serialize_values(self, values):
        return list(values)

value = UnorderedModel(values={literal})
for serializer in (canonical_json, canonical_sha256):
    try:
        serializer(value)
    except TypeError:
        print(f"{{serializer.__name__}}:rejected")
    else:
        print(f"{{serializer.__name__}}:accepted")
"""
    outputs: list[str] = []
    for seed in ("1", "2"):
        environment = {**os.environ, "PYTHONHASHSEED": seed, "PYTHONPATH": "src"}
        completed = subprocess.run(
            [sys.executable, "-c", script],
            cwd=REPO_ROOT,
            env=environment,
            check=True,
            capture_output=True,
            text=True,
        )
        outputs.append(completed.stdout)

    expected = "canonical_json:rejected\ncanonical_sha256:rejected\n"
    assert outputs == [expected, expected]


@pytest.mark.parametrize(
    "custom_serialization",
    [
        """
    @computed_field
    @property
    def unordered(self) -> list[str]:
        return list({"alpha", "beta", "gamma", "delta"})
""",
        """
    @model_serializer(mode="wrap")
    def serialize_model(self, handler):
        serialized = handler(self)
        serialized["unordered"] = list({"alpha", "beta", "gamma", "delta"})
        return serialized
""",
    ],
)
def test_canonical_functions_reject_nested_custom_model_serialization(
    custom_serialization: str,
) -> None:
    script = f"""
from pydantic import BaseModel, ConfigDict, computed_field, model_serializer
from money_machine.domain.value_objects import canonical_json, canonical_sha256

class InnerModel(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True)
    values: tuple[str, ...]
{custom_serialization}

class OuterModel(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True)
    inner: InnerModel

value = OuterModel(inner=InnerModel(values=("alpha", "beta")))
for serializer in (canonical_json, canonical_sha256):
    try:
        serializer(value)
    except TypeError:
        print(f"{{serializer.__name__}}:rejected")
    else:
        print(f"{{serializer.__name__}}:accepted")
"""
    outputs: list[str] = []
    for seed in ("1", "2"):
        environment = {**os.environ, "PYTHONHASHSEED": seed, "PYTHONPATH": "src"}
        completed = subprocess.run(
            [sys.executable, "-c", script],
            cwd=REPO_ROOT,
            env=environment,
            check=True,
            capture_output=True,
            text=True,
        )
        outputs.append(completed.stdout)

    expected = "canonical_json:rejected\ncanonical_sha256:rejected\n"
    assert outputs == [expected, expected]


def test_canonical_functions_ignore_nested_field_serializer() -> None:
    script = """
from pydantic import BaseModel, ConfigDict, field_serializer
from money_machine.domain.value_objects import canonical_json, canonical_sha256

class InnerModel(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True)
    values: tuple[str, ...]

    @field_serializer("values")
    def serialize_values(self, values):
        raise AssertionError("field serializer executed")

class OuterModel(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True)
    inner: InnerModel

value = OuterModel(
    inner=InnerModel(values=("alpha", "beta", "gamma", "delta"))
)
for serializer in (canonical_json, canonical_sha256):
    result = serializer(value)
    print(f"{serializer.__name__}:{result.hex() if isinstance(result, bytes) else result}")
"""
    outputs: list[str] = []
    for seed in ("1", "2"):
        environment = {**os.environ, "PYTHONHASHSEED": seed, "PYTHONPATH": "src"}
        completed = subprocess.run(
            [sys.executable, "-c", script],
            cwd=REPO_ROOT,
            env=environment,
            check=True,
            capture_output=True,
            text=True,
        )
        outputs.append(completed.stdout)

    expected = (
        "canonical_json:"
        "7b22696e6e6572223a7b2276616c756573223a5b22616c706861222c2262657461222c"
        "2267616d6d61222c2264656c7461225d7d7d\n"
        "canonical_sha256:c383101e6a4598038874b552667269a937c7795d5f5c3beaab881cc7c1b58550\n"
    )
    assert outputs == [expected, expected]
