"""Strict Pydantic contracts for first-product YAML configuration."""

from __future__ import annotations

from typing import Literal, Self, cast

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

FIRST_PRODUCT_ROLE_IDS = (
    "market_research",
    "product_strategy",
    "catalogue_dedupe",
    "notion_product_builder",
    "product_qa",
    "merchandising",
    "creative_assets",
    "preflight",
)

FIRST_PRODUCT_JOB_TYPES = (
    "ADMIT_RESEARCH_PACKET",
    "QUALIFY_CANDIDATES",
    "CREATE_PRODUCT_SPEC",
    "CHECK_CATALOGUE_DEDUPE",
    "BUILD_PRODUCT",
    "RUN_PRODUCT_QA",
    "CREATE_LISTING_PACKAGE",
    "RUN_PREFLIGHT",
)


class StrictConfigModel(BaseModel):
    """Frozen configuration base that rejects unknown fields and coercion."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class ResearchRules(StrictConfigModel):
    min_rows: Literal[25]
    max_rows: Literal[40]

    @model_validator(mode="after")
    def validate_range(self) -> Self:
        if self.min_rows > self.max_rows:
            raise ValueError("min_rows cannot exceed max_rows")
        return self


class QualificationRules(StrictConfigModel):
    shortlist_size: Literal[5]
    minimum_total_score: Literal[30]
    dimension_minimum: Literal[0]
    dimension_maximum: Literal[10]


class ProductRulesSection(StrictConfigModel):
    min_hubs: Literal[6]
    max_hubs: Literal[8]
    min_colour_variants: Literal[3]
    max_colour_variants: Literal[4]

    @model_validator(mode="after")
    def validate_ranges(self) -> Self:
        if self.min_hubs > self.max_hubs:
            raise ValueError("min_hubs cannot exceed max_hubs")
        if self.min_colour_variants > self.max_colour_variants:
            raise ValueError("min_colour_variants cannot exceed max_colour_variants")
        return self


class ListingRules(StrictConfigModel):
    tag_count: Literal[13]
    image_count: Literal[10]
    video_count: Literal[1]


class SafetyRules(StrictConfigModel):
    external_mutations_enabled: Literal[False]
    spend_enabled: Literal[False]


class ProductRulesConfig(StrictConfigModel):
    version: Literal[1]
    research: ResearchRules
    qualification: QualificationRules
    product: ProductRulesSection
    listing: ListingRules
    safety: SafetyRules


class AgentRoleConfig(StrictConfigModel):
    role_id: str
    enabled: Literal[True]
    external_mutations_enabled: Literal[False]


class AgentsConfig(StrictConfigModel):
    version: Literal[1]
    roles: tuple[AgentRoleConfig, ...]

    @field_validator("roles", mode="before")
    @classmethod
    def freeze_roles(cls, value: object) -> object:
        return tuple(cast(list[object], value)) if isinstance(value, list) else value

    @model_validator(mode="after")
    def validate_roles(self) -> Self:
        role_ids = tuple(role.role_id for role in self.roles)
        if len(role_ids) != len(set(role_ids)):
            raise ValueError("duplicate role_id")
        if role_ids != FIRST_PRODUCT_ROLE_IDS:
            raise ValueError("roles must exactly match the first-product role registry")
        return self


class WorkflowStepConfig(StrictConfigModel):
    job_type: str
    role_id: str
    retry_class: Literal["NEVER", "TRANSIENT_INTERNAL", "TRANSIENT_PROVIDER_READ"]


class WorkflowConfig(StrictConfigModel):
    workflow_id: Literal["first-product"]
    external_mutations_enabled: Literal[False]
    spend_enabled: Literal[False]
    steps: tuple[WorkflowStepConfig, ...]

    @field_validator("steps", mode="before")
    @classmethod
    def freeze_steps(cls, value: object) -> object:
        return tuple(cast(list[object], value)) if isinstance(value, list) else value

    @model_validator(mode="after")
    def validate_steps(self) -> Self:
        job_types = tuple(step.job_type for step in self.steps)
        if len(job_types) != len(set(job_types)):
            raise ValueError("duplicate job_type")
        if job_types != FIRST_PRODUCT_JOB_TYPES:
            raise ValueError("steps must exactly match the first-product job sequence")
        return self


class WorkflowsConfig(StrictConfigModel):
    version: Literal[1]
    workflows: tuple[WorkflowConfig, ...]

    @field_validator("workflows", mode="before")
    @classmethod
    def freeze_workflows(cls, value: object) -> object:
        return tuple(cast(list[object], value)) if isinstance(value, list) else value

    @model_validator(mode="after")
    def validate_single_workflow(self) -> Self:
        if len(self.workflows) != 1:
            raise ValueError("exactly one first-product workflow is required")
        return self


class FirstProductConfig(StrictConfigModel):
    product_rules: ProductRulesConfig
    agents: AgentsConfig
    workflows: WorkflowsConfig

    @model_validator(mode="after")
    def validate_registry_links(self) -> Self:
        role_ids = tuple(role.role_id for role in self.agents.roles)
        if len(role_ids) != len(set(role_ids)):
            raise ValueError("duplicate role_id")
        workflow = self.workflows.workflows[0]
        job_types = tuple(step.job_type for step in workflow.steps)
        if len(job_types) != len(set(job_types)):
            raise ValueError("duplicate job_type")
        unknown_roles = {step.role_id for step in workflow.steps}.difference(role_ids)
        if unknown_roles:
            unknown = ", ".join(sorted(unknown_roles))
            raise ValueError(f"workflow references unknown roles: {unknown}")
        return self
