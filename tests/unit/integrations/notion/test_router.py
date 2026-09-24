"""Unit tests for NotionAdapterRouter — config-driven adapter selection."""

import tempfile
from pathlib import Path

import pytest
import yaml

from money_machine.integrations.notion import NotionAdapterRouter
from money_machine.integrations.notion.api_adapter import APINotionAdapter
from money_machine.integrations.notion.browser_adapter import BrowserNotionAdapter
from money_machine.integrations.notion.combined_adapter import CombinedNotionAdapter
from money_machine.integrations.notion.fixture_adapter import FixtureNotionAdapter


def test_router_defaults_to_fixture_when_config_missing():
    """Router returns FixtureNotionAdapter when config file doesn't exist."""
    with tempfile.TemporaryDirectory() as tmpdir:
        nonexistent_config = Path(tmpdir) / "nonexistent.yaml"
        router = NotionAdapterRouter(config_path=nonexistent_config)

        adapter = router.get_adapter()
        assert isinstance(adapter, FixtureNotionAdapter)


def test_router_loads_fixture_mode_from_config():
    """Router returns FixtureNotionAdapter when config specifies fixture mode."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        config = {"notion": {"adapter_mode": "fixture"}}
        yaml.dump(config, f)
        config_path = f.name

    try:
        router = NotionAdapterRouter(config_path=config_path)
        adapter = router.get_adapter()
        assert isinstance(adapter, FixtureNotionAdapter)
    finally:
        Path(config_path).unlink()


def test_router_loads_api_mode_from_config():
    """Router returns APINotionAdapter when config specifies api mode."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        config = {"notion": {"adapter_mode": "api"}}
        yaml.dump(config, f)
        config_path = f.name

    try:
        router = NotionAdapterRouter(config_path=config_path)
        adapter = router.get_adapter()
        assert isinstance(adapter, APINotionAdapter)
    finally:
        Path(config_path).unlink()


def test_router_rejects_browser_mode_requires_playwright_session():
    """Router raises NotImplementedError for browser mode.

    Browser mode requires Playwright session.
    """
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        config = {"notion": {"adapter_mode": "browser"}}
        yaml.dump(config, f)
        config_path = f.name

    try:
        router = NotionAdapterRouter(config_path=config_path)
        with pytest.raises(
            NotImplementedError, match="Browser adapter requires Playwright"
        ):
            router.get_adapter()
    finally:
        Path(config_path).unlink()


def test_router_rejects_combined_mode_requires_setup():
    """Router raises NotImplementedError for combined mode (requires setup)."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        config = {"notion": {"adapter_mode": "combined"}}
        yaml.dump(config, f)
        config_path = f.name

    try:
        router = NotionAdapterRouter(config_path=config_path)
        with pytest.raises(NotImplementedError, match="Combined adapter requires"):
            router.get_adapter()
    finally:
        Path(config_path).unlink()


def test_router_rejects_invalid_adapter_mode():
    """Router raises ValueError for invalid adapter_mode."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        config = {"notion": {"adapter_mode": "invalid_mode"}}
        yaml.dump(config, f)
        config_path = f.name

    try:
        router = NotionAdapterRouter(config_path=config_path)
        with pytest.raises(ValueError, match=r"Invalid notion\.adapter_mode"):
            router.get_adapter()
    finally:
        Path(config_path).unlink()


def test_router_caches_adapter_instance():
    """Router returns same adapter instance on repeated get_adapter calls."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        config = {"notion": {"adapter_mode": "fixture"}}
        yaml.dump(config, f)
        config_path = f.name

    try:
        router = NotionAdapterRouter(config_path=config_path)
        adapter1 = router.get_adapter()
        adapter2 = router.get_adapter()
        assert adapter1 is adapter2  # Same instance
    finally:
        Path(config_path).unlink()


def test_router_set_adapter_mode_overrides_config():
    """set_adapter_mode() programmatically overrides config file."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        config = {"notion": {"adapter_mode": "fixture"}}
        yaml.dump(config, f)
        config_path = f.name

    try:
        router = NotionAdapterRouter(config_path=config_path)

        # Initially fixture from config
        adapter = router.get_adapter()
        assert isinstance(adapter, FixtureNotionAdapter)

        # Override to API mode
        router.set_adapter_mode("api")
        adapter = router.get_adapter()
        assert isinstance(adapter, APINotionAdapter)
    finally:
        Path(config_path).unlink()


def test_router_set_adapter_mode_rejects_invalid_mode():
    """set_adapter_mode() raises ValueError for invalid mode."""
    router = NotionAdapterRouter()

    with pytest.raises(ValueError, match="Invalid adapter mode"):
        router.set_adapter_mode("invalid_mode")
