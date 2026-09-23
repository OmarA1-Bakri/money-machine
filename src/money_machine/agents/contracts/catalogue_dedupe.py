"""A06 Catalogue Dedupe Agent contracts.

Input: DedupeJob with spec_id in job.input
Output: DedupeResult with PASS or TOO_CLOSE outcome
Events: DEDUPE_PASSED or DEDUPE_FAILED

Implements D-0013 deterministic dedupe rules.
"""

from uuid import UUID

from pydantic import Field

from money_machine.domain.models._base import ContractModel


class DedupeJobInput(ContractModel):
    """Input for DedupeJob targeting A06 Catalogue Dedupe Agent."""

    spec_id: UUID = Field(description="ProductSpec ID to check against catalogue")
