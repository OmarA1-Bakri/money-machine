"""A06 Catalogue Dedupe Agent — deterministic dedupe with PASS/TOO_CLOSE branching.

Implements D-0013 dedupe rules:
1. Exact identity + category → EXACT_IDENTITY_CATEGORY collision
2. Title Jaccard >= 0.70 → TITLE_SIMILARITY collision
3. Concept fingerprint match → CONCEPT_FINGERPRINT collision

Returns PASS (with differentiation evidence) or TOO_CLOSE (with collision evidence).
Emits DEDUPE_PASSED or DEDUPE_FAILED event for workflow branching.
"""

from __future__ import annotations

import contextlib
from uuid import UUID

from money_machine.agents.base import AgentContext, BaseAgent
from money_machine.domain.enums import AgentRunStatus, BranchOutcome
from money_machine.domain.events import EventName
from money_machine.domain.models._base import JsonObject
from money_machine.domain.models.common import EvidenceReference
from money_machine.domain.models.jobs import AgentResult
from money_machine.domain.models.products import ProductSpec
from money_machine.domain.services.dedupe import check_dedupe


DEDUPE_RULE_VERSION = "1.0.0-D0013"
"""Dedupe rule version identifier per D-0013 decision."""


class CatalogueDedupeAgent(BaseAgent):
    """Check candidate ProductSpec against existing catalogue for conflicts."""

    agent_id = "A06"

    async def execute(self, context: AgentContext) -> AgentResult:
        job = context.job
        job_input = job.input

        # Extract candidate spec_id from job input
        candidate_spec_id_str = job_input.get("spec_id")
        if not candidate_spec_id_str:
            return AgentResult(
                job_id=job.job_id,
                agent_run_id=context.agent_run_id,
                agent_id=self.agent_id,
                agent_definition_version=context.definition.contract_version,
                prompt_reference=context.prompt_reference,
                prompt_sha256=context.prompt_sha256,
                status=AgentRunStatus.FAILURE,
                output={},
                error={
                    "code": "MISSING_SPEC_ID",
                    "message": "Job input must contain spec_id",
                },
            )

        candidate_spec_id = UUID(candidate_spec_id_str)

        # Load candidate ProductSpec from database
        # Using database.read tool to query product_specs table
        candidate_spec_data = context.invoke_tool(
            "database.read",
            table="product_specs",
            spec_id=str(candidate_spec_id),
        )

        if not candidate_spec_data:
            return AgentResult(
                job_id=job.job_id,
                agent_run_id=context.agent_run_id,
                agent_id=self.agent_id,
                agent_definition_version=context.definition.contract_version,
                prompt_reference=context.prompt_reference,
                prompt_sha256=context.prompt_sha256,
                status=AgentRunStatus.FAILURE,
                output={},
                error={
                    "code": "SPEC_NOT_FOUND",
                    "message": f"ProductSpec {candidate_spec_id} not found",
                },
            )

        # Parse candidate ProductSpec from tool result
        candidate_spec = ProductSpec.model_validate(candidate_spec_data)

        # Load all existing ProductSpecs from catalogue
        # Exclude the candidate itself and only get specs from different workflows
        existing_specs_data = context.invoke_tool(
            "database.read",
            table="product_specs",
            exclude_spec_id=str(candidate_spec_id),
        )

        # Parse existing specs
        existing_specs: list[ProductSpec] = []
        if existing_specs_data and isinstance(existing_specs_data, list):
            for spec_data in existing_specs_data:
                with contextlib.suppress(Exception):
                    # Skip invalid specs (shouldn't happen but be defensive)
                    existing_specs.append(ProductSpec.model_validate(spec_data))

        # Run dedupe check
        dedupe_result = check_dedupe(
            candidate_spec=candidate_spec,
            existing_specs=existing_specs,
            rule_version=DEDUPE_RULE_VERSION,
        )

        # Persist DedupeResult to database
        context.invoke_tool(
            "database.write_dedupe_result",
            result_id=str(dedupe_result.result_id),
            workflow_id=str(dedupe_result.workflow_id),
            spec_id=str(dedupe_result.spec_id),
            outcome=dedupe_result.outcome.value,
            rule_version=dedupe_result.rule_version,
            normalized_title=dedupe_result.normalized_title,
            concept_fingerprint=dedupe_result.concept_fingerprint,
            title_similarity_threshold=dedupe_result.title_similarity_threshold,
            compared_spec_ids=[str(sid) for sid in dedupe_result.compared_spec_ids],
            collisions=[
                {
                    "other_spec_id": str(collision.other_spec_id),
                    "reason": collision.reason,
                    "similarity": collision.similarity,
                    "evidence": [
                        {
                            "evidence_id": str(ev.evidence_id),
                            "evidence_kind": ev.evidence_kind,
                            "reference": ev.reference,
                        }
                        for ev in collision.evidence
                    ],
                }
                for collision in dedupe_result.collisions
            ],
            differentiation_evidence=list(dedupe_result.differentiation_evidence),
            completed_at=dedupe_result.completed_at.isoformat(),
        )

        # Determine event to emit based on outcome
        if dedupe_result.outcome is BranchOutcome.PASS:
            emitted_event = EventName.DEDUPE_PASSED
        elif dedupe_result.outcome is BranchOutcome.TOO_CLOSE:
            emitted_event = EventName.DEDUPE_FAILED
        else:
            # Should not happen due to DedupeResult validation
            return AgentResult(
                job_id=job.job_id,
                agent_run_id=context.agent_run_id,
                agent_id=self.agent_id,
                agent_definition_version=context.definition.contract_version,
                prompt_reference=context.prompt_reference,
                prompt_sha256=context.prompt_sha256,
                status=AgentRunStatus.FAILURE,
                output={},
                error={
                    "code": "INVALID_OUTCOME",
                    "message": (
                        f"DedupeResult outcome must be PASS or TOO_CLOSE, "
                        f"got {dedupe_result.outcome}"
                    ),
                },
            )

        # Build agent output with dedupe result
        output: JsonObject = {
            "result_id": str(dedupe_result.result_id),
            "spec_id": str(dedupe_result.spec_id),
            "outcome": dedupe_result.outcome.value,
            "rule_version": dedupe_result.rule_version,
            "compared_specs": len(dedupe_result.compared_spec_ids),
            "collisions": len(dedupe_result.collisions),
            "collision_reasons": [c.reason for c in dedupe_result.collisions],
        }

        # Prepare evidence references
        evidence_refs: list[EvidenceReference] = []
        for collision in dedupe_result.collisions:
            evidence_refs.extend(collision.evidence)

        # Return success with emitted event
        # The orchestration layer will create the successor job based on event_successor_map
        return AgentResult(
            job_id=job.job_id,
            agent_run_id=context.agent_run_id,
            agent_id=self.agent_id,
            agent_definition_version=context.definition.contract_version,
            prompt_reference=context.prompt_reference,
            prompt_sha256=context.prompt_sha256,
            status=AgentRunStatus.SUCCESS,
            output=output,
            emitted_events=(emitted_event,),
            evidence=tuple(evidence_refs) if evidence_refs else (),
        )
