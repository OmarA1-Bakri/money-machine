"""Immutable durable-job and output contracts for the first-product experiment."""

from dataclasses import dataclass
from types import MappingProxyType
from typing import Final

from money_machine.domain.events import DomainEventName
from money_machine.domain.models.candidate import CandidateShortlist
from money_machine.domain.models.listing import ListingPackage, PreflightResult
from money_machine.domain.models.product import BuildResult, ProductQAResult
from money_machine.domain.models.product_spec import DedupeResult, ProductSpec
from money_machine.domain.models.research import ResearchPacket
from money_machine.domain.value_objects import FrozenModel, canonical_sha256

FIRST_PRODUCT_JOB_SEQUENCE: Final[tuple[str, ...]] = (
    "ADMIT_RESEARCH_PACKET",
    "QUALIFY_CANDIDATES",
    "CREATE_PRODUCT_SPEC",
    "CHECK_CATALOGUE_DEDUPE",
    "BUILD_PRODUCT",
    "RUN_PRODUCT_QA",
    "CREATE_LISTING_PACKAGE",
    "RUN_PREFLIGHT",
)

FIRST_PRODUCT_WORKFLOW_TYPE: Final = "FIRST_PRODUCT_VERTICAL_SLICE"


@dataclass(frozen=True, slots=True)
class StepOutputContract:
    """Exact durable output semantics for one canonical workflow step."""

    result_type: str
    result_model: type[FrozenModel]
    event_name: DomainEventName
    successor_job_type: str | None


FIRST_PRODUCT_STEP_OUTPUTS: Final = MappingProxyType(
    {
        "ADMIT_RESEARCH_PACKET": StepOutputContract(
            "research_packets",
            ResearchPacket,
            DomainEventName.RESEARCH_PACKET_ADMITTED,
            "QUALIFY_CANDIDATES",
        ),
        "QUALIFY_CANDIDATES": StepOutputContract(
            "candidate_shortlists",
            CandidateShortlist,
            DomainEventName.CANDIDATE_SHORTLISTED,
            "CREATE_PRODUCT_SPEC",
        ),
        "CREATE_PRODUCT_SPEC": StepOutputContract(
            "product_specs",
            ProductSpec,
            DomainEventName.PRODUCT_SPEC_CREATED,
            "CHECK_CATALOGUE_DEDUPE",
        ),
        "CHECK_CATALOGUE_DEDUPE": StepOutputContract(
            "dedupe_results",
            DedupeResult,
            DomainEventName.DEDUPE_PASSED,
            "BUILD_PRODUCT",
        ),
        "BUILD_PRODUCT": StepOutputContract(
            "build_results",
            BuildResult,
            DomainEventName.PRODUCT_BUILT,
            "RUN_PRODUCT_QA",
        ),
        "RUN_PRODUCT_QA": StepOutputContract(
            "product_qa_results",
            ProductQAResult,
            DomainEventName.PRODUCT_QA_PASSED,
            "CREATE_LISTING_PACKAGE",
        ),
        "CREATE_LISTING_PACKAGE": StepOutputContract(
            "listing_packages",
            ListingPackage,
            DomainEventName.LISTING_PACKAGE_CREATED,
            "RUN_PREFLIGHT",
        ),
        "RUN_PREFLIGHT": StepOutputContract(
            "preflight_results",
            PreflightResult,
            DomainEventName.DRAFT_READY,
            None,
        ),
    }
)


def success_event_payload(result_type: str, result: FrozenModel) -> dict[str, str]:
    """Return the exact independently persisted identity contract for a successful step."""

    identity_fields: dict[type[FrozenModel], str] = {
        ResearchPacket: "packet_id",
        CandidateShortlist: "shortlist_id",
        ProductSpec: "product_spec_id",
        DedupeResult: "dedupe_result_id",
        BuildResult: "build_id",
        ProductQAResult: "qa_result_id",
        ListingPackage: "listing_package_id",
        PreflightResult: "preflight_result_id",
    }
    identity_field = identity_fields.get(type(result))
    if identity_field is None:
        raise TypeError("unsupported first-product result model")
    identity = getattr(result, identity_field)
    if not isinstance(identity, str) or not identity:
        raise ValueError("first-product result identity is invalid")
    return {
        identity_field: identity,
        "result_type": result_type,
        "result_id": identity,
        "result_sha256": canonical_sha256(result),
    }


def validate_step_output(
    job_type: str,
    result_type: str,
    result: FrozenModel,
    event_name: DomainEventName,
    successor_job_type: str | None,
) -> None:
    """Reject any handler output that differs from its frozen step contract."""

    contract = FIRST_PRODUCT_STEP_OUTPUTS.get(job_type)
    if contract is None:
        raise ValueError(f"unknown first-product job type: {job_type}")
    if result_type != contract.result_type:
        raise ValueError(f"result type mismatch for {job_type}")
    if type(result) is not contract.result_model:
        raise ValueError(f"result model mismatch for {job_type}")
    if event_name is not contract.event_name:
        raise ValueError(f"event name mismatch for {job_type}")
    if successor_job_type != contract.successor_job_type:
        raise ValueError(f"successor mismatch for {job_type}")
