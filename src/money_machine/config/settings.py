"""Strict, immutable models for application-owned YAML configuration."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import Annotated, Any, Final, Literal, Self, cast

from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    StringConstraints,
    model_validator,
)

from money_machine.domain.enums import (
    AutonomyMode,
    CapabilityChannel,
    RetryClass,
    SideEffectClass,
)
from money_machine.domain.events import EventName, TelemetryEventName
from money_machine.domain.models._base import (
    AgentId,
    CurrencyCode,
    NonEmptyStr,
    NonNegativeInt,
    PositiveInt,
)
from money_machine.domain.models.rules import ListingRules, ProductShapeRules

PLAYBOOK_MACHINE_WEEKLY_CAP: Final[int] = 15
"""The playbook's machine cap of fifteen publications per week is an invariant, not a value."""


class ConfigModel(BaseModel):
    """Common fail-closed policy for configuration contracts."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        validate_default=True,
        allow_inf_nan=False,
    )


class RuntimeEnvironment(StrEnum):
    """Runtime classes that determine the maximum effective authority."""

    DEVELOPMENT = "development"
    TEST = "test"
    PRODUCTION = "production"


class AgentCommissioningState(StrEnum):
    """Evidence level reached by one configured agent definition."""

    DESIGNED = "DESIGNED"
    IMPLEMENTED = "IMPLEMENTED"
    TESTED = "TESTED"
    COMMISSIONED = "COMMISSIONED"
    SUSPENDED = "SUSPENDED"


def _parse_enum[EnumT: StrEnum](value: Any, enum_type: type[EnumT]) -> Any:
    if isinstance(value, enum_type):
        return value
    if type(value) is str:
        return enum_type(value)
    return value


def _parse_autonomy_mode(value: Any) -> Any:
    return _parse_enum(value, AutonomyMode)


def _parse_capability_channel(value: Any) -> Any:
    return _parse_enum(value, CapabilityChannel)


def _parse_commissioning_state(value: Any) -> Any:
    return _parse_enum(value, AgentCommissioningState)


def _parse_event_name(value: Any) -> Any:
    return _parse_enum(value, EventName)


def _parse_telemetry_event_name(value: Any) -> Any:
    return _parse_enum(value, TelemetryEventName)


def _parse_retry_class(value: Any) -> Any:
    return _parse_enum(value, RetryClass)


def _parse_side_effect_class(value: Any) -> Any:
    return _parse_enum(value, SideEffectClass)


def _parse_decimal(value: Any) -> Any:
    if isinstance(value, Decimal):
        result = value
    elif type(value) in {int, str}:
        try:
            result = Decimal(value)
        except InvalidOperation as error:
            raise ValueError("value must be a decimal amount") from error
    else:
        return value
    if not result.is_finite():
        raise ValueError("value must be finite")
    return result


def _parse_yaml_tuple(value: Any) -> Any:
    if type(value) is list:
        return tuple(cast(list[object], value))
    return value


def _validate_unique_strings(values: tuple[str, ...]) -> tuple[str, ...]:
    if len(set(values)) != len(values):
        raise ValueError("values must be unique")
    return values


AutonomyModeValue = Annotated[AutonomyMode, BeforeValidator(_parse_autonomy_mode)]
CapabilityChannelValue = Annotated[
    CapabilityChannel,
    BeforeValidator(_parse_capability_channel),
]
CommissioningStateValue = Annotated[
    AgentCommissioningState,
    BeforeValidator(_parse_commissioning_state),
]
EventNameValue = Annotated[EventName, BeforeValidator(_parse_event_name)]
TelemetryEventNameValue = Annotated[
    TelemetryEventName,
    BeforeValidator(_parse_telemetry_event_name),
]


def _reject_path_traversal(value: str) -> str:
    if "://" not in value and any(segment in {".", ".."} for segment in value.split("/")):
        raise ValueError("evidence path must not contain '.' or '..' segments")
    return value


EvidenceLocator = Annotated[
    str,
    StringConstraints(
        strict=True,
        strip_whitespace=True,
        pattern=(
            r"^(?:[a-z][a-z0-9+.-]*://\S+"
            r"|(?:docs|tests|scripts)/(?:[A-Za-z0-9._-]+/)*[A-Za-z0-9._-]+)$"
        ),
    ),
    AfterValidator(_reject_path_traversal),
]
"""Commissioning evidence must be a URI or a repository-relative docs/tests/scripts path."""
UniqueEvidenceLocators = Annotated[
    tuple[EvidenceLocator, ...],
    BeforeValidator(_parse_yaml_tuple),
    AfterValidator(_validate_unique_strings),
]
RetryClassValue = Annotated[RetryClass, BeforeValidator(_parse_retry_class)]
SideEffectClassValue = Annotated[
    SideEffectClass,
    BeforeValidator(_parse_side_effect_class),
]
NonNegativeMoney = Annotated[
    Decimal,
    BeforeValidator(_parse_decimal),
    Field(ge=Decimal("0")),
]
Percent = Annotated[
    Decimal,
    BeforeValidator(_parse_decimal),
    Field(gt=Decimal("0"), le=Decimal("100")),
]
CanonicalJobType = Annotated[
    str,
    StringConstraints(strict=True, pattern=r"^[A-Z][A-Za-z0-9]*Job$"),
]
WeeklyCap = Annotated[int, Field(strict=True, gt=0, le=PLAYBOOK_MACHINE_WEEKLY_CAP)]
UniqueStrings = Annotated[
    tuple[NonEmptyStr, ...],
    BeforeValidator(_parse_yaml_tuple),
    AfterValidator(_validate_unique_strings),
]


class InclusiveIntRange(ConfigModel):
    """Inclusive integer range whose lower bound cannot exceed its upper bound."""

    minimum: PositiveInt
    maximum: PositiveInt

    @model_validator(mode="after")
    def validate_order(self) -> Self:
        if self.minimum > self.maximum:
            raise ValueError("minimum cannot exceed maximum")
        return self


class QualificationRules(ConfigModel):
    """Qualification score contract for deciding whether to build."""

    build_threshold: PositiveInt
    maximum_score: PositiveInt

    @model_validator(mode="after")
    def validate_threshold(self) -> Self:
        if self.build_threshold > self.maximum_score:
            raise ValueError("build threshold cannot exceed maximum score")
        return self


class NicheSelectionRules(ConfigModel):
    """Number of primary and backup niches selected from one shortlist."""

    primary: PositiveInt
    backup: PositiveInt


class ProductShapeConfig(ConfigModel):
    """Permitted product structure and visual-variant ranges."""

    hubs: InclusiveIntRange
    colour_variants: InclusiveIntRange

    def to_domain_rules(self, rule_version: str) -> ProductShapeRules:
        """Bind the configured ranges into the domain contract consumed by ``ProductSpec``."""
        return ProductShapeRules(
            rule_version=rule_version,
            hubs_minimum=self.hubs.minimum,
            hubs_maximum=self.hubs.maximum,
            colour_variants_minimum=self.colour_variants.minimum,
            colour_variants_maximum=self.colour_variants.maximum,
        )


class ListingAssetRules(ConfigModel):
    """Required listing metadata, media counts, description shape, and quantity."""

    tags: PositiveInt
    images: PositiveInt
    videos: PositiveInt
    description_sections: PositiveInt
    quantity: PositiveInt
    image_role: NonEmptyStr
    video_role: NonEmptyStr

    def to_domain_rules(self, rule_version: str) -> ListingRules:
        """Bind the configured listing shape into the contract consumed by ``ListingPackage``."""
        return ListingRules(
            rule_version=rule_version,
            tags=self.tags,
            images=self.images,
            videos=self.videos,
            description_sections=self.description_sections,
            quantity=self.quantity,
            image_role=self.image_role,
            video_role=self.video_role,
        )


class PortfolioRules(ConfigModel):
    """Evidence and cadence needed before portfolio actions."""

    maturity_live_days: PositiveInt
    cull_bottom_percent: Percent
    deep_pass_cadence: Literal["monthly"]


class ExperimentRules(ConfigModel):
    """Bounded catalogue experiment contract."""

    new_fronts_per_batch: PositiveInt


class DedupeRules(ConfigModel):
    """Versioned title-comparison policy."""

    rule_version: NonEmptyStr
    title_jaccard_threshold: Annotated[
        Decimal,
        BeforeValidator(_parse_decimal),
        Field(gt=Decimal("0"), le=Decimal("1")),
    ]


class ProductRulesConfig(ConfigModel):
    """Playbook-owned product, portfolio, and experiment defaults."""

    version: Literal[1]
    research_rows: InclusiveIntRange
    shortlisted_candidates: PositiveInt
    qualification: QualificationRules
    niche_selection: NicheSelectionRules
    product_shape: ProductShapeConfig
    listing_assets: ListingAssetRules
    portfolio: PortfolioRules
    experiments: ExperimentRules
    dedupe: DedupeRules

    @model_validator(mode="after")
    def validate_selection_counts(self) -> Self:
        selected = self.niche_selection.primary + self.niche_selection.backup
        if selected > self.shortlisted_candidates:
            raise ValueError("primary and backup counts cannot exceed the shortlist")
        return self

    @property
    def rule_version(self) -> str:
        return f"product-rules-v{self.version}"

    def listing_rules(self) -> ListingRules:
        """Domain listing rules bound from this configuration."""
        return self.listing_assets.to_domain_rules(self.rule_version)

    def product_shape_rules(self) -> ProductShapeRules:
        """Domain product-shape rules bound from this configuration."""
        return self.product_shape.to_domain_rules(self.rule_version)


class PublishingRampConfig(ConfigModel):
    """Transactional publication-cap defaults and accounting semantics."""

    version: Literal[1]
    publishing_enabled: bool
    launch_target: InclusiveIntRange
    initial_weekly_cap: PositiveInt
    hard_weekly_cap: WeeklyCap
    rolling_window_days: PositiveInt
    count_only_reconciled_publications: Literal[True]

    @model_validator(mode="after")
    def validate_caps(self) -> Self:
        if self.initial_weekly_cap > self.hard_weekly_cap:
            raise ValueError("initial weekly cap cannot exceed hard weekly cap")
        if not self.launch_target.minimum <= self.initial_weekly_cap <= self.launch_target.maximum:
            raise ValueError("initial weekly cap must be within the launch target")
        if self.launch_target.maximum > self.hard_weekly_cap:
            raise ValueError("launch target cannot exceed hard weekly cap")
        return self


class AuthorizedRecipientScope(ConfigModel):
    """Versioned safe reference to an admitted recipient class and consent record."""

    scope_id: NonEmptyStr
    version: PositiveInt
    consent_evidence_reference: NonEmptyStr


class AutonomyConfig(ConfigModel):
    """Explicit standing authority; credentials never widen these fields."""

    version: Literal[1]
    mode: AutonomyModeValue
    currency: CurrencyCode
    external_mutations_enabled: bool
    external_spend_enabled: bool
    auto_publish: bool
    auto_deactivate: bool
    auto_multiply: bool
    external_message_enabled: bool
    message_monthly_cap: NonNegativeInt
    authorized_recipient_scopes: Annotated[
        tuple[AuthorizedRecipientScope, ...],
        BeforeValidator(_parse_yaml_tuple),
    ]
    recipient_consent_evidence_required: Literal[True]
    competitor_purchase_enabled: bool
    competitor_purchase_max_each: NonNegativeMoney
    competitor_purchase_monthly_cap: NonNegativeMoney
    live_checkout_test_enabled: bool
    live_checkout_test_cap: NonNegativeMoney
    weekly_listing_cap: WeeklyCap
    paid_tool_monthly_cap: NonNegativeMoney

    @model_validator(mode="after")
    def validate_authority(self) -> Self:
        if self.auto_publish and (
            self.mode is not AutonomyMode.LIVE or not self.external_mutations_enabled
        ):
            raise ValueError("auto_publish requires live external mutations")
        if self.auto_deactivate and (
            self.mode is not AutonomyMode.LIVE or not self.external_mutations_enabled
        ):
            raise ValueError("auto_deactivate requires live external mutations")

        if self.external_message_enabled:
            if self.message_monthly_cap <= 0:
                raise ValueError("message authority requires a positive cap")
            if not self.authorized_recipient_scopes:
                raise ValueError("message authority requires recipient scopes")
        elif self.message_monthly_cap or self.authorized_recipient_scopes:
            raise ValueError("disabled message authority requires zero cap and no scopes")

        purchase_values = (
            self.competitor_purchase_max_each,
            self.competitor_purchase_monthly_cap,
        )
        if self.competitor_purchase_enabled:
            if self.mode is not AutonomyMode.LIVE or not self.external_spend_enabled:
                raise ValueError("competitor purchase requires live spend authority")
            if any(value <= 0 for value in purchase_values):
                raise ValueError("competitor purchase requires positive per-item and monthly caps")
            if self.competitor_purchase_max_each > self.competitor_purchase_monthly_cap:
                raise ValueError("competitor purchase maximum cannot exceed its monthly cap")
        elif any(purchase_values):
            raise ValueError("disabled competitor purchase requires zero caps")

        if self.live_checkout_test_enabled:
            if self.mode is not AutonomyMode.LIVE or not self.external_spend_enabled:
                raise ValueError("live checkout test requires live spend authority")
            if self.live_checkout_test_cap <= 0:
                raise ValueError("live checkout test requires a positive cap")
        elif self.live_checkout_test_cap:
            raise ValueError("disabled live checkout test requires a zero cap")

        if self.paid_tool_monthly_cap and (
            self.mode is not AutonomyMode.LIVE or not self.external_spend_enabled
        ):
            raise ValueError("paid-tool spend requires live spend authority")
        if self.mode is AutonomyMode.SIMULATION and any(
            (
                self.external_mutations_enabled,
                self.external_spend_enabled,
                self.external_message_enabled,
                self.auto_publish,
                self.auto_deactivate,
            )
        ):
            raise ValueError("simulation forbids external authority")
        return self


class AgentDefinition(ConfigModel):
    """One unambiguous A01-A16 ownership and commissioning contract."""

    agent_id: AgentId
    name: NonEmptyStr
    implementation_version: PositiveInt
    contract_version: PositiveInt
    system_prompt_reference: NonEmptyStr
    input_contracts: UniqueStrings
    output_contracts: UniqueStrings
    allowed_tools: UniqueStrings
    provider_operations: UniqueStrings
    allowed_side_effect_classes: Annotated[
        tuple[SideEffectClassValue, ...],
        BeforeValidator(_parse_yaml_tuple),
        Field(min_length=1),
    ]
    default_side_effect_class: SideEffectClassValue
    allowed_retry_classes: Annotated[
        tuple[RetryClassValue, ...],
        BeforeValidator(_parse_yaml_tuple),
        Field(min_length=1),
    ]
    default_retry_class: RetryClassValue
    timeout_seconds: PositiveInt
    model_policy: NonEmptyStr
    commissioning_state: CommissioningStateValue
    commissioning_evidence: UniqueEvidenceLocators

    @model_validator(mode="after")
    def validate_defaults_and_uniqueness(self) -> Self:
        if len(set(self.allowed_side_effect_classes)) != len(self.allowed_side_effect_classes):
            raise ValueError("allowed side-effect classes must be unique")
        if self.default_side_effect_class not in self.allowed_side_effect_classes:
            raise ValueError("default side-effect class must be allowed")
        if len(set(self.allowed_retry_classes)) != len(self.allowed_retry_classes):
            raise ValueError("allowed retry classes must be unique")
        if self.default_retry_class not in self.allowed_retry_classes:
            raise ValueError("default retry class must be allowed")
        if (
            self.commissioning_state is AgentCommissioningState.COMMISSIONED
            and not self.commissioning_evidence
        ):
            raise ValueError("COMMISSIONED requires evidence")
        return self


class AgentsConfig(ConfigModel):
    """Complete current agent roster."""

    version: Literal[1]
    agents: Annotated[
        tuple[AgentDefinition, ...],
        BeforeValidator(_parse_yaml_tuple),
        Field(min_length=16, max_length=16),
    ]

    @model_validator(mode="after")
    def validate_roster(self) -> Self:
        agent_ids = tuple(definition.agent_id for definition in self.agents)
        if len(set(agent_ids)) != len(agent_ids):
            raise ValueError("agent IDs must be unique")
        expected = {f"A{number:02d}" for number in range(1, 17)}
        if set(agent_ids) != expected:
            raise ValueError("agent roster must contain exactly A01 through A16")
        return self


class WorkflowJobDefinition(ConfigModel):
    """Configured owner, effect, retry, capability, and result boundary for one job."""

    job_type: CanonicalJobType
    owner_agent_id: AgentId
    side_effect_class: SideEffectClassValue
    retry_class: RetryClassValue
    allowed_modes: Annotated[
        tuple[AutonomyModeValue, ...],
        BeforeValidator(_parse_yaml_tuple),
        Field(min_length=1),
    ]
    output_contracts: UniqueStrings
    admitted_events: Annotated[
        tuple[EventNameValue, ...],
        BeforeValidator(_parse_yaml_tuple),
        Field(min_length=1),
    ]
    successor_job_types: Annotated[
        tuple[CanonicalJobType, ...],
        BeforeValidator(_parse_yaml_tuple),
    ]
    capability_operation: NonEmptyStr | None = None
    capability_channel: CapabilityChannelValue | None = None

    @model_validator(mode="after")
    def validate_effect_contract(self) -> Self:
        if len(set(self.allowed_modes)) != len(self.allowed_modes):
            raise ValueError("allowed modes must be unique")
        if len(set(self.admitted_events)) != len(self.admitted_events):
            raise ValueError("admitted events must be unique")
        if len(set(self.successor_job_types)) != len(self.successor_job_types):
            raise ValueError("successor job types must be unique")

        capability_fields = (self.capability_operation, self.capability_channel)
        if self.side_effect_class is SideEffectClass.NONE:
            if any(value is not None for value in capability_fields):
                raise ValueError("internal jobs forbid external capability fields")
        elif any(value is None for value in capability_fields):
            raise ValueError("external jobs require operation and capability channel")

        admitted_retries: dict[SideEffectClass, frozenset[RetryClass]] = {
            SideEffectClass.NONE: frozenset({RetryClass.SAFE, RetryClass.IDEMPOTENT}),
            SideEffectClass.EXTERNAL_READ: frozenset(
                {RetryClass.SAFE, RetryClass.IDEMPOTENT, RetryClass.MANUAL_RESUME}
            ),
            SideEffectClass.EXTERNAL_WRITE: frozenset(
                {
                    RetryClass.IDEMPOTENT,
                    RetryClass.RECONCILE_FIRST,
                    RetryClass.MANUAL_RESUME,
                }
            ),
            SideEffectClass.EXTERNAL_SPEND: frozenset({RetryClass.RECONCILE_FIRST}),
            SideEffectClass.EXTERNAL_MESSAGE: frozenset({RetryClass.RECONCILE_FIRST}),
        }
        if self.retry_class not in admitted_retries[self.side_effect_class]:
            raise ValueError("retry class is unsafe for the configured side effect")
        if (
            self.side_effect_class
            in {SideEffectClass.EXTERNAL_SPEND, SideEffectClass.EXTERNAL_MESSAGE}
            and AutonomyMode.DRAFT in self.allowed_modes
        ):
            raise ValueError("draft mode prohibits spend and message effects")
        return self


class WorkflowDefinition(ConfigModel):
    """Versioned durable workflow graph."""

    workflow_type: NonEmptyStr
    version: PositiveInt
    entry_job_types: Annotated[
        tuple[CanonicalJobType, ...],
        BeforeValidator(_parse_yaml_tuple),
        Field(min_length=1),
    ]
    jobs: Annotated[
        tuple[WorkflowJobDefinition, ...],
        BeforeValidator(_parse_yaml_tuple),
        Field(min_length=1),
    ]

    @model_validator(mode="after")
    def validate_graph(self) -> Self:
        job_types = tuple(job.job_type for job in self.jobs)
        if len(set(job_types)) != len(job_types):
            raise ValueError("workflow job types must be unique")
        known = set(job_types)
        unknown_entries = set(self.entry_job_types) - known
        if unknown_entries:
            raise ValueError("workflow entry jobs must exist in the workflow")
        unknown_successors = {
            successor
            for job in self.jobs
            for successor in job.successor_job_types
            if successor not in known
        }
        if unknown_successors:
            raise ValueError("workflow successor jobs must exist in the workflow")

        successors = {job.job_type: set(job.successor_job_types) for job in self.jobs}
        reachable: set[str] = set()
        frontier = list(self.entry_job_types)
        while frontier:
            job_type = frontier.pop()
            if job_type in reachable:
                continue
            reachable.add(job_type)
            frontier.extend(successors[job_type])
        unreachable = sorted(known - reachable)
        if unreachable:
            raise ValueError(
                "workflow jobs must be reachable from an entry job; unreachable: "
                + ", ".join(unreachable)
            )
        return self


class WorkflowsConfig(ConfigModel):
    """Configured workflow definitions."""

    version: Literal[1]
    workflows: Annotated[
        tuple[WorkflowDefinition, ...],
        BeforeValidator(_parse_yaml_tuple),
        Field(min_length=1),
    ]

    @model_validator(mode="after")
    def validate_workflow_types(self) -> Self:
        workflow_types = tuple(workflow.workflow_type for workflow in self.workflows)
        if len(set(workflow_types)) != len(workflow_types):
            raise ValueError("workflow types must be unique")
        return self


class TelemetryConfig(ConfigModel):
    """PostHog observation contract; a separate taxonomy from durable events (D-0012)."""

    version: Literal[1]
    enabled: bool
    allowed_events: Annotated[
        tuple[TelemetryEventNameValue, ...],
        BeforeValidator(_parse_yaml_tuple),
    ]

    @model_validator(mode="after")
    def validate_events(self) -> Self:
        if len(set(self.allowed_events)) != len(self.allowed_events):
            raise ValueError("telemetry events must be unique")
        if self.enabled and not self.allowed_events:
            raise ValueError("enabled telemetry requires an explicit allowed event list")
        return self


class ConfigurationBundle(ConfigModel):
    """Cross-validated effective configuration used by one process."""

    product_rules: ProductRulesConfig
    publishing_ramp: PublishingRampConfig
    autonomy: AutonomyConfig
    agents: AgentsConfig
    workflows: WorkflowsConfig
    telemetry: TelemetryConfig
