"""Notion adapter router — config-driven adapter selection.

Reads config/integrations.yaml to determine which adapter implementation
to use: fixture (W1), api (W2+), browser (W3+), or combined (W3+).
"""

from pathlib import Path
from typing import Any

import yaml

from .adapter import NotionAdapter
from .api_adapter import APINotionAdapter
from .browser_adapter import BrowserNotionAdapter
from .combined_adapter import CombinedNotionAdapter
from .fixture_adapter import FixtureNotionAdapter


class NotionAdapterRouter:
    """Routes to appropriate Notion adapter based on configuration.

    Reads adapter_mode from config/integrations.yaml:
    - fixture: FixtureNotionAdapter (in-memory, testing)
    - api: APINotionAdapter (Notion Official API)
    - browser: BrowserNotionAdapter (Playwright)
    - combined: CombinedNotionAdapter (API + browser)

    Default is fixture mode for W1 testing.
    """

    def __init__(self, config_path: str | Path | None = None) -> None:
        """Initialize router with optional config path.

        Args:
            config_path: Path to integrations.yaml
                        (defaults to config/integrations.yaml)
        """
        if config_path is None:
            # Default to repo root / config / integrations.yaml
            repo_root = Path(__file__).parent.parent.parent.parent
            config_path = repo_root / "config" / "integrations.yaml"
        else:
            config_path = Path(config_path)

        self.config_path = config_path
        self._adapter: NotionAdapter | None = None

    def _load_config(self) -> dict[str, Any]:
        """Load integrations config from YAML."""
        if not self.config_path.exists():
            # Default to fixture if config missing
            return {"notion": {"adapter_mode": "fixture"}}

        with open(self.config_path) as f:
            config = yaml.safe_load(f)

        return config or {}

    def get_adapter(self) -> NotionAdapter:
        """Get the configured Notion adapter.

        Returns:
            NotionAdapter instance based on config

        Raises:
            ValueError: If adapter_mode is invalid
        """
        if self._adapter is not None:
            return self._adapter

        config = self._load_config()
        notion_config = config.get("notion", {})
        mode = notion_config.get("adapter_mode", "fixture")

        if mode == "fixture":
            self._adapter = FixtureNotionAdapter()
        elif mode == "api":
            self._adapter = APINotionAdapter()
        elif mode == "browser":
            raise NotImplementedError(
                "Browser adapter requires Playwright session injection. "
                "Production Playwright integration deferred to Session 06 Wave 4+. "
                "Use FixtureNotionAdapter for testing or "
                "APINotionAdapter for API operations."
            )
        elif mode == "combined":
            raise NotImplementedError(
                "Combined adapter requires both API and browser session setup. "
                "Deferred to Session 06 Wave 4+. "
                "Use FixtureNotionAdapter for testing or "
                "APINotionAdapter for API operations."
            )
        else:
            raise ValueError(
                f"Invalid notion.adapter_mode: {mode}. "
                f"Must be one of: fixture, api, browser, combined"
            )

        return self._adapter

    def set_adapter_mode(self, mode: str) -> None:
        """Override adapter mode programmatically (useful for tests).

        Args:
            mode: fixture | api | browser | combined

        Raises:
            ValueError: If mode is invalid
        """
        valid_modes = {"fixture", "api", "browser", "combined"}
        if mode not in valid_modes:
            raise ValueError(
                f"Invalid adapter mode: {mode}. Must be one of: {valid_modes}"
            )

        # Clear cached adapter to force reload
        self._adapter = None

        # Reload with new mode
        if mode == "fixture":
            self._adapter = FixtureNotionAdapter()
        elif mode == "api":
            self._adapter = APINotionAdapter()
        elif mode == "browser":
            raise NotImplementedError(
                "Browser adapter requires Playwright session injection. "
                "Production Playwright integration deferred to Session 06 Wave 4+."
            )
        elif mode == "combined":
            raise NotImplementedError(
                "Combined adapter requires both API and browser session setup. "
                "Deferred to Session 06 Wave 4+."
            )
