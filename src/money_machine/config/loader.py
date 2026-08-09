"""YAML loaders for the frozen first-product configuration."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path
from typing import cast

import yaml
from yaml.nodes import MappingNode, Node, ScalarNode, SequenceNode

from money_machine.config.validation import (
    AgentsConfig,
    FirstProductConfig,
    ProductRulesConfig,
    WorkflowsConfig,
)


def _reject_duplicate_mapping_keys(node: Node) -> None:
    if isinstance(node, MappingNode):
        seen: set[tuple[str, str]] = set()
        for key_node, value_node in cast(list[tuple[Node, Node]], node.value):
            if not isinstance(key_node, ScalarNode):
                raise ValueError("YAML mapping keys must be scalars")
            if key_node.tag == "tag:yaml.org,2002:merge":
                raise ValueError("YAML merge keys are not permitted")
            identity = (key_node.tag, key_node.value)
            if identity in seen:
                raise ValueError(f"duplicate YAML mapping key: {key_node.value!r}")
            seen.add(identity)
            _reject_duplicate_mapping_keys(value_node)
    elif isinstance(node, SequenceNode):
        for child in cast(list[Node], node.value):
            _reject_duplicate_mapping_keys(child)


def _load_yaml_mapping(path: Path) -> dict[str, object]:
    """Load one YAML document and require a mapping at its root."""

    source = path.read_text(encoding="utf-8")
    compose_yaml = cast(Callable[..., object], vars(yaml)["compose"])
    root_node = cast(Node | None, compose_yaml(source, Loader=yaml.SafeLoader))
    if root_node is not None:
        _reject_duplicate_mapping_keys(root_node)
    loaded = cast(object, yaml.safe_load(source))
    if not isinstance(loaded, Mapping):
        raise ValueError(f"configuration root must be a mapping: {path}")
    mapping = cast(Mapping[object, object], loaded)
    if not all(isinstance(key, str) for key in mapping):
        raise ValueError(f"configuration keys must be strings: {path}")
    return {cast(str, key): value for key, value in mapping.items()}


def load_product_rules(path: Path) -> ProductRulesConfig:
    """Load and strictly validate product rules from one YAML path."""

    return ProductRulesConfig.model_validate(_load_yaml_mapping(path), strict=True)


def load_agents(path: Path) -> AgentsConfig:
    """Load and strictly validate the logical first-slice role registry."""

    return AgentsConfig.model_validate(_load_yaml_mapping(path), strict=True)


def load_workflows(path: Path) -> WorkflowsConfig:
    """Load and strictly validate the first-product workflow template."""

    return WorkflowsConfig.model_validate(_load_yaml_mapping(path), strict=True)


def load_first_product_config(config_root: Path) -> FirstProductConfig:
    """Load the three canonical configuration files as one validated contract."""

    return FirstProductConfig(
        product_rules=load_product_rules(config_root / "product_rules.yaml"),
        agents=load_agents(config_root / "agents.yaml"),
        workflows=load_workflows(config_root / "workflows.yaml"),
    )
