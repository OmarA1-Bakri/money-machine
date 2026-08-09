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
from money_machine.domain.value_objects import FrozenModel

FIRST_PRODUCT_JOB_SEQUENCE: Final[tuple[str, ...]] = (
    "ADMIT_RESEARCH_PACKET",
    "SCORE_AND_SHORTLIST",
    "CREATE_PRODUCT_SPEC",
    "RUN_DEDUPE",
    "BUILD_LOCAL_PRODUCT",
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
            "SCORE_AND_SHORTLIST",
        ),
        "SCORE_AND_SHORTLIST": StepOutputContract(
            "candidate_shortlists",
            CandidateShortlist,
            DomainEventName.CANDIDATE_SHORTLISTED,
            "CREATE_PRODUCT_SPEC",
        ),
        "CREATE_PRODUCT_SPEC": StepOutputContract(
            "product_specs",
            ProductSpec,
            DomainEventName.PRODUCT_SPEC_CREATED,
            "RUN_DEDUPE",
        ),
        "RUN_DEDUPE": StepOutputContract(
            "dedupe_results",
            DedupeResult,
            DomainEventName.DEDUPE_PASSED,
            "BUILD_LOCAL_PRODUCT",
        ),
        "BUILD_LOCAL_PRODUCT": StepOutputContract(
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
