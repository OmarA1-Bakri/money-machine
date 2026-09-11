"""Typed API response models. No response ever carries a secret value."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ApiModel(BaseModel):
    """Frozen response base."""

    model_config = ConfigDict(frozen=True, extra="forbid")


class HealthResponse(ApiModel):
    """Process liveness. Makes no dependency claim."""

    status: Literal["ok"]
    service: Literal["api"]
    version: str


class DatabaseStatus(ApiModel):
    """Database reachability and applied migration revision."""

    url: str
    reachable: bool
    migration_revision: str | None
    schema_current: bool = False


class ReadinessResponse(ApiModel):
    """Readiness, which fails when a dependency is unavailable."""

    ready: bool
    service: Literal["api"]
    version: str
    environment: str
    database: DatabaseStatus


class VersionResponse(ApiModel):
    """Build identity."""

    version: str
    environment: str


class WorkflowSummary(ApiModel):
    """One durable workflow."""

    id: UUID
    workflow_type: str
    workflow_version: int
    product_state: str
    parent_workflow_id: UUID | None
    started_at: datetime
    completed_at: datetime | None


class WorkflowPage(ApiModel):
    """A bounded page of workflows."""

    items: tuple[WorkflowSummary, ...]
    total: int
    limit: int
    offset: int


class JobSummary(ApiModel):
    """One durable job."""

    id: UUID
    workflow_id: UUID
    job_type: str
    status: str
    owner_agent_id: str
    side_effect_class: str
    retry_class: str
    attempt: int
    max_attempts: int
    scheduled_at: datetime


class JobPage(ApiModel):
    """A bounded page of jobs."""

    items: tuple[JobSummary, ...]
    total: int
    limit: int
    offset: int


class ProviderStatus(ApiModel):
    """Whether a provider is configured. Never the credential itself."""

    name: str
    configured: bool
    effect_mode: str
    commissioned: bool


class IntegrationStatusResponse(ApiModel):
    """Provider readiness from settings presence only."""

    environment: str
    providers: tuple[ProviderStatus, ...]
