"""Finite A07 consumer of an already admitted one-operation recovery approval.

No issuer, CLI, lease claim, registry, canonical replacement selection or further
build execution. Invoke through the existing AgentRunner and dedicated job UoW.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from notion_client import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from money_machine.agents.base import AgentContext, BaseAgent
from money_machine.application.real_draft_authority import (
    DraftRunAuthority,
    DraftRunRefused,
    NotificationReplacementApproval,
    notion_request_sha256,
)
from money_machine.application.real_draft_effects import DraftEffectUncertain, SqlDraftEffects
from money_machine.application.real_notion_build import (
    SOURCES,
    _schema_matches,  # pyright: ignore[reportPrivateUsage]
    notification_schema,
    schemas,
)
from money_machine.domain.enums import AgentRunStatus
from money_machine.domain.models.common import ContractError, EffectReference
from money_machine.domain.models.jobs import AgentResult
from money_machine.domain.models.product_spec import ProductSpec
from money_machine.integrations.notion.real_product_adapter import RealPrivateNotionAdapter
from money_machine.orchestration.idempotency import (
    derive_idempotency_key,
    get_latest_effect_attempt,
)
from money_machine.persistence import tables as t

Json = dict[str, Any]


def _title(database: Json) -> str:
    return "".join(
        part.get("plain_text", part.get("text", {}).get("content", ""))
        for part in database.get("title", [])
    )


@dataclass(frozen=True, slots=True)
class NotificationRecoveryAgent(BaseAgent):
    """One existing A07 BuildRepairJob, one guarded create, verified effect only."""

    session_factory: async_sessionmaker[AsyncSession]
    authority: DraftRunAuthority
    sdk: AsyncClient
    approval: NotificationReplacementApproval
    spec: ProductSpec
    source_database_ids: Mapping[str, str]
    source_data_source_ids: Mapping[str, str]

    async def execute(self, context: AgentContext) -> AgentResult:
        try:
            return await self._execute(context)
        except (DraftRunRefused, DraftEffectUncertain):
            references = await self._effect_references(context)
            uncertain = any(row.effect_state == "UNKNOWN" for row in references)
            return AgentResult(
                job_id=context.job.job_id,
                agent_run_id=context.run_id,
                agent_id="A07",
                agent_definition_version=context.definition.contract_version,
                prompt_reference=context.prompt_reference,
                prompt_sha256=context.prompt_sha256,
                status=AgentRunStatus.UNCERTAIN_EXTERNAL_EFFECT
                if uncertain
                else AgentRunStatus.FAILURE,
                output={
                    "scope": "notification_replacement_effect_only",
                    "canonical_selected": False,
                    "repair_completed": False,
                },
                effects=references,
                error=ContractError(
                    code="NOTIFICATION_RECOVERY_UNCERTAIN"
                    if uncertain
                    else "NOTIFICATION_RECOVERY_REFUSED",
                    message="Notification recovery requires reconciled or corrected inputs.",
                    retryable=False,
                    blocker_action=(
                        "Read canonical recovery metadata and effect references; "
                        "do not resend or clear holds automatically."
                    ),
                ),
            )

    async def _effect_references(self, context: AgentContext) -> tuple[EffectReference, ...]:
        if (
            context.job.job_id != self.approval.repair_job_id
            or context.job.workflow_id != self.approval.workflow_id
            or context.job.object_id != self.approval.product_id
        ):
            return ()
        key = derive_idempotency_key(
            job_type="BuildRepairJob",
            workflow_id=self.approval.workflow_id,
            object_id=self.approval.product_id,
            operation=self.approval.operation_key,
        )
        async with self.session_factory() as session:
            row = await get_latest_effect_attempt(session, idempotency_key=key)
            if row is None or row.job_id != context.job.job_id:
                return ()
            return (
                EffectReference.model_validate(
                    {
                        "idempotency_key": key,
                        "provider": row.provider,
                        "operation": row.operation,
                        "provider_object_id": row.provider_object_id,
                        "effect_state": row.effect_state,
                        "observed_at": row.observed_at,
                        "reconciliation_attempt": row.reconciliation_attempt,
                    }
                ),
            )

    async def _execute(self, context: AgentContext) -> AgentResult:
        databases = {name: str(UUID(value)) for name, value in self.source_database_ids.items()}
        sources = {name: str(UUID(value)) for name, value in self.source_data_source_ids.items()}
        if (
            set(databases) != set(SOURCES)
            or set(sources) != set(SOURCES)
            or len(set(databases.values())) != 6
            or len(set(sources.values())) != 6
            or set(databases.values()) & set(sources.values())
            or tuple(self.spec.shared_databases) != SOURCES
        ):
            raise DraftRunRefused("recovery_source_scope")
        properties = notification_schema(sources, self.spec.currency)
        body = {
            "parent": {"type": "page_id", "page_id": str(self.approval.parent_id)},
            "title": [{"type": "text", "text": {"content": "Notification"}}],
            "is_inline": True,
            "initial_data_source": {"properties": properties},
        }
        if notion_request_sha256(body) != self.approval.request_sha256:
            raise DraftRunRefused("recovery_request_digest_or_scope")

        async def pre_send(adapter: RealPrivateNotionAdapter) -> None:
            await self._canonical_spec(context, databases, sources)
            await self._observe(effects, adapter, databases, sources, properties, None)

        effects, adapter = await SqlDraftEffects.bind_notification_recovery(
            context,
            session_factory=self.session_factory,
            authority=self.authority,
            sdk=self.sdk,
            approval=self.approval,
            before_recovery_send=pre_send,
        )
        await self._canonical_spec(context, databases, sources)

        async def reconcile(known: str | None) -> Json | None:
            return await self._observe(effects, adapter, databases, sources, properties, known)

        async def create() -> Json:
            return await adapter.create_database(
                self.approval.parent_id, "Notification", properties
            )

        database: Json = dict(
            await effects.execute(
                self.approval.operation_key,
                provider="notion",
                operation="notion.private_product.write",
                create=create,
                reconcile=reconcile,
                notion_parent_id=self.approval.parent_id,
            )
        )
        return AgentResult(
            job_id=context.job.job_id,
            agent_run_id=context.run_id,
            agent_id="A07",
            agent_definition_version=context.definition.contract_version,
            prompt_reference=context.prompt_reference,
            prompt_sha256=context.prompt_sha256,
            status=AgentRunStatus.SUCCESS,
            effects=await self._effect_references(context),
            output={
                "scope": "notification_replacement_effect_only",
                "database_id": database["id"],
                "data_source_id": database["data_sources"][0]["id"],
                "request_sha256": self.approval.request_sha256,
                "canonical_selected": False,
                "repair_completed": False,
            },
        )

    async def _canonical_spec(
        self, context: AgentContext, databases: dict[str, str], sources: dict[str, str]
    ) -> None:
        spec = self.spec
        digest = hashlib.sha256(spec.model_dump_json().encode()).hexdigest()
        if (
            digest != self.approval.spec_sha256
            or spec.product_id != self.approval.product_id
            or spec.workflow_id != self.approval.workflow_id
            or spec.lineage_kind != "ORIGINAL"
        ):
            raise DraftRunRefused("recovery_spec_scope_or_hash")
        async with self.session_factory() as session:
            row = await session.get(t.ProductSpec, spec.spec_id)
            original = await session.get(t.Job, self.approval.original_job_id)
            repair = await session.get(t.Job, context.job.job_id)
            producer = await session.get(t.AgentRun, spec.producing_agent_run_id)
            producer_job = await session.get(t.Job, spec.producing_job_id)
            product = await session.get(t.Product, spec.product_id)
            research = (
                await session.get(t.ResearchRun, spec.research_run_id)
                if spec.research_run_id
                else None
            )
            research_job = await session.get(t.Job, research.job_id) if research else None
            if (
                row is None
                or original is None
                or repair is None
                or producer is None
                or producer_job is None
                or product is None
                or product.workflow_id != spec.workflow_id
                or product.producing_job_id != spec.producing_job_id
                or original.input.get("spec_sha256") != digest
                or repair.input.get("spec_sha256") != digest
                or producer.job_id != spec.producing_job_id
                or producer.agent_id != "A05"
                or producer.status != "SUCCESS"
                or producer.input_hash != digest
                or producer_job.workflow_id != spec.workflow_id
                or producer_job.object_id != spec.product_id
                or producer_job.owner_agent_id != "A05"
                or producer_job.job_type != "ProductStrategyJob"
                or producer_job.status != "SUCCEEDED"
                or producer_job.input.get("spec_sha256") != digest
                or (
                    spec.research_run_id is not None
                    and (
                        research is None
                        or research.workflow_id != spec.workflow_id
                        or research_job is None
                        or research_job.workflow_id != spec.workflow_id
                        or research_job.owner_agent_id != "A03"
                        or research_job.job_type != "MarketResearchJob"
                        or research_job.status != "SUCCEEDED"
                    )
                )
            ):
                raise DraftRunRefused("canonical_recovery_spec_lineage_required")
            record = repair.input.get("notification_recovery", {})
            if (
                not isinstance(record, dict)
                or record.get("source_database_ids") != databases
                or record.get("source_data_source_ids") != sources
            ):
                raise DraftRunRefused("canonical_recovery_sources_required")
            fields = (
                "product_id",
                "workflow_id",
                "version",
                "producing_job_id",
                "producing_agent_run_id",
                "research_run_id",
                "lineage_kind",
                "parent_spec_id",
                "parent_product_id",
                "parent_decision_id",
                "parent_workflow_id",
                "identity",
                "base_category",
                "buyer_problem",
                "title",
                "tier",
                "real_price",
                "anchor_price",
                "currency",
                "concept_fingerprint",
                "rule_version",
            )
            projection = spec.model_dump(mode="json")
            if (
                any(getattr(row, name) != getattr(spec, name) for name in fields)
                or row.hubs != projection["hubs"]
                or row.colour_variants != projection["colour_variants"]
                or row.experiment_plan != spec.experiment_hypothesis
                or row.features
                != [
                    {
                        "flagship_feature": spec.flagship_feature,
                        "feature_targets": projection["feature_targets"],
                        "palette_name": spec.palette_name,
                        "palette_tokens": projection["palette_tokens"],
                    }
                ]
            ):
                raise DraftRunRefused("canonical_recovery_spec_projection_mismatch")

    async def _observe(
        self,
        effects: SqlDraftEffects,
        adapter: RealPrivateNotionAdapter,
        databases: dict[str, str],
        sources: dict[str, str],
        properties: Json,
        known: str | None,
    ) -> Json | None:
        parent = str(self.approval.parent_id)

        async def inventory() -> None:
            children = [
                row
                for row in await adapter.list_blocks(parent)
                if row.get("type") == "child_database"
            ]
            child_ids = [str(UUID(row["id"])) for row in children]
            if len(child_ids) != len(set(child_ids)):
                raise DraftRunRefused("recovery_duplicate_database_children")
            candidates = [
                row["id"]
                for row in children
                if (
                    row.get("child_database", {}).get("title", "").strip().casefold()
                    == "notification"
                    and row["id"] != known
                )
            ]
            if candidates:
                await effects.hold_notification_recovery_candidates(self.approval, candidates)
                raise DraftEffectUncertain(
                    "notification_candidate_requires_explicit_reconciliation"
                )
            if set(child_ids) != set(databases.values()) | ({known} if known else set()):
                raise DraftRunRefused("recovery_database_inventory_drift")

        await inventory()
        expected_schemas = schemas()

        async def verify(
            database_id: str, source_id: str | None, name: str, expected: Json
        ) -> Json:
            database = await adapter.get_database(database_id)
            data_sources = database.get("data_sources", [])
            if (
                database.get("parent") != {"type": "page_id", "page_id": parent}
                or _title(database) != name
                or len(data_sources) != 1
                or (source_id is not None and data_sources[0].get("id") != source_id)
            ):
                raise DraftRunRefused("recovery_database_identity_mismatch")
            source = await adapter.get_data_source(data_sources[0]["id"])
            if source.get("parent") != {"type": "database_id", "database_id": database_id} or set(
                source.get("properties", {})
            ) != set(expected):
                raise DraftRunRefused("recovery_data_source_schema_or_parent_mismatch")
            _schema_matches(expected, source["properties"])
            return database

        for name in SOURCES:
            await verify(databases[name], sources[name], name, expected_schemas[name])
        observed = None
        if known:
            async with self.session_factory() as session:
                job = await session.get(t.Job, self.approval.repair_job_id)
                accepted = (
                    job.input.get("notification_recovery", {}).get("accepted_resource", {})
                    if job
                    else {}
                )
            if accepted.get("database_id") != known or not accepted.get("data_source_id"):
                raise DraftEffectUncertain("retained_notification_identity_required")
            observed = await verify(known, accepted["data_source_id"], "Notification", properties)
        await inventory()
        return observed
