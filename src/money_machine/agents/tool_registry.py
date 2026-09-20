"""Typed tool registry with per-agent allowlist enforcement.

Maps canonical tool identifiers to handlers and declared side-effect classes.
Agent execution must call tools through ``ToolRegistry.invoke`` so disallowed tools
raise ``ToolPermissionError`` fail-closed.

Contract: Session 04 W5/L2 roster lane, prompt-integrity addendum point 5.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, Final

from money_machine.domain.enums import SideEffectClass

ToolHandler = Callable[..., Mapping[str, Any]]

# Read-only orchestration and diagnostics tools permitted during review subagents.
REVIEW_ALLOWED_NONE_TOOLS: Final[frozenset[str]] = frozenset(
    {
        "workflow.inspect",
        "configuration.read",
        "database.read",
        "provider.check_openai",
        "provider.check_anthropic",
        "provider.check_notion",
        "provider.check_etsy",
    }
)
REVIEW_PERMITTED_SIDE_EFFECTS: Final[frozenset[SideEffectClass]] = frozenset(
    {
        SideEffectClass.NONE,
        SideEffectClass.EXTERNAL_READ,
    }
)


class ToolPermissionError(PermissionError):
    """Raised when an agent invokes a tool outside its allowlist."""


class ToolNotFoundError(KeyError):
    """Raised when a tool identifier is not registered."""


@dataclass(frozen=True, slots=True)
class ToolDefinition:
    """One registered tool and its external-effect classification."""

    tool_id: str
    side_effect_class: SideEffectClass
    description: str


def _simulated_handler(tool_id: str, **_kwargs: Any) -> dict[str, Any]:
    """Deterministic simulation stub; never performs external effects."""
    return {"tool_id": tool_id, "simulated": True, "status": "ok"}


# Canonical tool catalogue keyed by identifier.
CANONICAL_TOOLS: Final[tuple[ToolDefinition, ...]] = (
    # Orchestration (A01, A15)
    ToolDefinition("job.create", SideEffectClass.NONE, "Create a typed successor job"),
    ToolDefinition("workflow.inspect", SideEffectClass.NONE, "Read workflow state and history"),
    ToolDefinition("job.retry", SideEffectClass.NONE, "Requeue a failed job within retry policy"),
    ToolDefinition(
        "configuration.read",
        SideEffectClass.NONE,
        "Read shop and agent configuration",
    ),
    ToolDefinition("database.read", SideEffectClass.NONE, "Query durable orchestration state"),
    ToolDefinition(
        "database.write_orchestration",
        SideEffectClass.NONE,
        "Write orchestration-only workflow and job state",
    ),
    # Integration diagnostics (A02)
    ToolDefinition(
        "provider.check_openai",
        SideEffectClass.EXTERNAL_READ,
        "Test OpenAI connection without credential exposure",
    ),
    ToolDefinition(
        "provider.check_anthropic",
        SideEffectClass.EXTERNAL_READ,
        "Test Anthropic connection without credential exposure",
    ),
    ToolDefinition(
        "provider.check_notion",
        SideEffectClass.EXTERNAL_READ,
        "Test Notion connection without credential exposure",
    ),
    ToolDefinition(
        "provider.check_etsy",
        SideEffectClass.EXTERNAL_READ,
        "Test Etsy connection without credential exposure",
    ),
    ToolDefinition(
        "provider.provision_workspace",
        SideEffectClass.EXTERNAL_WRITE,
        "Create provider workspace resources when holder authorized",
    ),
    ToolDefinition(
        "database.write_accounts",
        SideEffectClass.NONE,
        "Persist integration readiness status",
    ),
    ToolDefinition("incident.create", SideEffectClass.NONE, "Create a structured incident record"),
    # Research (A03)
    ToolDefinition("etsy.read_listing", SideEffectClass.EXTERNAL_READ, "Read one Etsy listing"),
    ToolDefinition(
        "etsy.search_listings",
        SideEffectClass.EXTERNAL_READ,
        "Search Etsy listings for research",
    ),
    ToolDefinition("browser.navigate", SideEffectClass.EXTERNAL_READ, "Navigate browser read-only"),
    ToolDefinition("storage.write_blob", SideEffectClass.NONE, "Persist research capture blob"),
    # Competitor teardown (A04)
    ToolDefinition(
        "etsy.purchase_listing",
        SideEffectClass.EXTERNAL_SPEND,
        "Purchase competitor listing for teardown",
    ),
    # Notion build (A07, A08)
    ToolDefinition("notion.create_page", SideEffectClass.EXTERNAL_WRITE, "Create Notion page"),
    ToolDefinition("notion.upload_asset", SideEffectClass.EXTERNAL_WRITE, "Upload asset to Notion"),
    ToolDefinition("notion.update_page", SideEffectClass.EXTERNAL_WRITE, "Update Notion page"),
    ToolDefinition(
        "notion.link_publish",
        SideEffectClass.EXTERNAL_WRITE,
        "Publish Notion variant links",
    ),
    ToolDefinition("notion.read_page", SideEffectClass.EXTERNAL_READ, "Read Notion page content"),
    ToolDefinition("notion.read_links", SideEffectClass.EXTERNAL_READ, "Read Notion link targets"),
    # Creative assets (A11)
    ToolDefinition(
        "renderer.generate_asset",
        SideEffectClass.NONE,
        "Generate deterministic local render artifact",
    ),
    # Etsy publishing (A12, A13)
    ToolDefinition("etsy.read_draft", SideEffectClass.EXTERNAL_READ, "Read Etsy draft listing"),
    ToolDefinition("etsy.publish_listing", SideEffectClass.EXTERNAL_WRITE, "Publish Etsy listing"),
    ToolDefinition("etsy.update_listing", SideEffectClass.EXTERNAL_WRITE, "Update Etsy listing"),
    ToolDefinition(
        "etsy.deactivate_listing",
        SideEffectClass.EXTERNAL_WRITE,
        "Deactivate Etsy listing",
    ),
    ToolDefinition(
        "etsy.upload_media",
        SideEffectClass.EXTERNAL_WRITE,
        "Upload Etsy listing media",
    ),
    # Analytics (A14)
    ToolDefinition(
        "etsy.read_shop_stats",
        SideEffectClass.EXTERNAL_READ,
        "Read Etsy shop statistics",
    ),
    ToolDefinition(
        "etsy.list_transactions",
        SideEffectClass.EXTERNAL_READ,
        "List Etsy shop transactions",
    ),
    # Support (A16)
    ToolDefinition("etsy.read_messages", SideEffectClass.EXTERNAL_READ, "Read Etsy messages"),
    ToolDefinition(
        "etsy.send_message",
        SideEffectClass.EXTERNAL_MESSAGE,
        "Send Etsy customer message",
    ),
)


class ToolRegistry:
    """Registry of tool definitions with allowlist-enforced invocation."""

    def __init__(
        self,
        definitions: Mapping[str, ToolDefinition] | None = None,
        handlers: Mapping[str, ToolHandler] | None = None,
    ) -> None:
        self._definitions: dict[str, ToolDefinition] = dict(definitions or {})
        self._handlers: dict[str, ToolHandler] = dict(handlers or {})

    @classmethod
    def canonical(cls) -> ToolRegistry:
        """Build the default registry with simulation handlers for every canonical tool."""
        registry = cls()
        for definition in CANONICAL_TOOLS:
            registry.register(definition, _simulated_handler)
        return registry

    def register(self, definition: ToolDefinition, handler: ToolHandler) -> None:
        """Register one tool definition and its handler."""
        self._definitions[definition.tool_id] = definition
        self._handlers[definition.tool_id] = handler

    def get(self, tool_id: str) -> ToolDefinition:
        """Return a tool definition or raise ``ToolNotFoundError``."""
        try:
            return self._definitions[tool_id]
        except KeyError as error:
            raise ToolNotFoundError(f"Unknown tool: {tool_id}") from error

    def resolve(self, tool_id: str) -> ToolDefinition:
        """Alias for ``get`` used by contract tests."""
        return self.get(tool_id)

    def known_tool_ids(self) -> frozenset[str]:
        """All registered tool identifiers."""
        return frozenset(self._definitions)

    def invoke(
        self,
        tool_id: str,
        *,
        allowed_tools: frozenset[str],
        agent_id: str,
        **kwargs: Any,
    ) -> Mapping[str, Any]:
        """Invoke a tool after allowlist enforcement.

        Raises:
            ToolPermissionError: When ``tool_id`` is not in ``allowed_tools``.
            ToolNotFoundError: When ``tool_id`` is not registered.
        """
        if tool_id not in allowed_tools:
            msg = (
                f"Agent {agent_id} is not allowed to invoke tool '{tool_id}'. "
                f"Allowed: {sorted(allowed_tools)}"
            )
            raise ToolPermissionError(msg)

        definition = self.get(tool_id)
        handler = self._handlers.get(tool_id)
        if handler is None:
            msg = f"No handler registered for tool: {tool_id}"
            raise ToolNotFoundError(msg)

        result = handler(tool_id=tool_id, agent_id=agent_id, **kwargs)
        return {
            **result,
            "side_effect_class": definition.side_effect_class.value,
        }

    def invoke_for_review(
        self,
        tool_id: str,
        *,
        allowed_tools: frozenset[str],
        agent_id: str,
        **kwargs: Any,
    ) -> Mapping[str, Any]:
        """Invoke a tool from a bounded review subagent.

        Review subagents may only use read-only tools. Mutating or job-spawning tools
        fail closed even when present on the owning agent allowlist.

        Raises:
            ToolPermissionError: When ``tool_id`` is not allowed for review.
            ToolNotFoundError: When ``tool_id`` is not registered.
        """
        if tool_id not in allowed_tools:
            msg = (
                f"Agent {agent_id} is not allowed to invoke tool '{tool_id}' during review. "
                f"Allowed: {sorted(allowed_tools)}"
            )
            raise ToolPermissionError(msg)

        definition = self.get(tool_id)
        if definition.side_effect_class not in REVIEW_PERMITTED_SIDE_EFFECTS:
            msg = (
                f"Review subagent for agent {agent_id} cannot invoke mutating tool "
                f"'{tool_id}' (side_effect_class={definition.side_effect_class.value})"
            )
            raise ToolPermissionError(msg)
        if (
            definition.side_effect_class is SideEffectClass.NONE
            and tool_id not in REVIEW_ALLOWED_NONE_TOOLS
        ):
            msg = (
                f"Review subagent for agent {agent_id} cannot invoke write tool "
                f"'{tool_id}' during review"
            )
            raise ToolPermissionError(msg)

        return self.invoke(
            tool_id,
            allowed_tools=allowed_tools,
            agent_id=agent_id,
            **kwargs,
        )
