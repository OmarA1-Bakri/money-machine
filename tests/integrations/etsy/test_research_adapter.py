"""Tests for Etsy research adapters."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from money_machine.integrations.etsy import (
    EtsyAPIAdapter,
    EtsyBrowserAdapter,
    EtsyFixtureAdapter,
    EtsyResearchObservation,
    get_research_adapter,
)


class TestEtsyFixtureAdapter:
    """Test fixture adapter with synthetic data."""

    @pytest.fixture
    def adapter(self, tmp_path: Path) -> EtsyFixtureAdapter:
        """Create fixture adapter with temporary fixture file."""
        fixture_data = {
            "test phrase": [
                {
                    "rank": 1,
                    "title": "Test Product 1",
                    "current_price_cents": 999,
                    "anchor_price_cents": 1499,
                    "shop_name": "TestShop1",
                    "shop_sales_count": 1000,
                    "shop_age_years": 2,
                    "badges": ["Star Seller"],
                    "urgency_signals": ["Only 3 left"],
                    "review_count": 250,
                    "identity_niche": "test niche",
                    "base_category": "Test Category",
                    "listing_url": "https://www.etsy.com/listing/test-1",
                    "search_timestamp": "2026-09-20T20:00:00Z",
                },
                {
                    "rank": 2,
                    "title": "Test Product 2",
                    "current_price_cents": 599,
                    "anchor_price_cents": None,
                    "shop_name": "TestShop2",
                    "shop_sales_count": None,
                    "shop_age_years": None,
                    "badges": [],
                    "urgency_signals": [],
                    "review_count": None,
                    "identity_niche": "test niche",
                    "base_category": "Test Category",
                    "listing_url": "https://www.etsy.com/listing/test-2",
                    "search_timestamp": "2026-09-20T20:00:00Z",
                },
            ]
        }
        fixture_path = tmp_path / "test_fixtures.json"
        fixture_path.write_text(json.dumps(fixture_data))
        return EtsyFixtureAdapter(fixture_path=fixture_path)

    def test_fixture_adapter_returns_all_required_fields(self, adapter: EtsyFixtureAdapter):
        """Fixture adapter must return all required fields with correct types."""
        observations = adapter.search("test phrase", target_count=10)

        assert len(observations) > 0, "Must return at least one observation"

        for obs in observations:
            # Check all required fields are present
            assert isinstance(obs.search_phrase, str)
            assert isinstance(obs.rank, int)
            assert isinstance(obs.title, str)
            assert isinstance(obs.current_price_cents, int)
            assert obs.anchor_price_cents is None or isinstance(obs.anchor_price_cents, int)
            assert isinstance(obs.shop_name, str)
            assert obs.shop_sales_count is None or isinstance(obs.shop_sales_count, int)
            assert obs.shop_age_years is None or isinstance(obs.shop_age_years, int)
            assert isinstance(obs.badges, list)
            assert isinstance(obs.urgency_signals, list)
            assert obs.review_count is None or isinstance(obs.review_count, int)
            assert isinstance(obs.identity_niche, str)
            assert isinstance(obs.base_category, str)
            assert isinstance(obs.listing_url, str)
            assert obs.evidence_timestamp is not None

    def test_fixture_adapter_respects_target_count(self, adapter: EtsyFixtureAdapter):
        """Fixture adapter must respect target_count parameter."""
        observations = adapter.search("test phrase", target_count=1)
        assert len(observations) == 1

        observations = adapter.search("test phrase", target_count=10)
        assert len(observations) == 2  # Only 2 in fixture

    def test_fixture_adapter_raises_on_missing_phrase(self, adapter: EtsyFixtureAdapter):
        """Fixture adapter must raise KeyError for unknown phrase."""
        with pytest.raises(KeyError, match="not found in fixtures"):
            adapter.search("unknown phrase")

    def test_fixture_adapter_raises_on_missing_file(self, tmp_path: Path):
        """Fixture adapter must raise FileNotFoundError for missing file."""
        adapter = EtsyFixtureAdapter(fixture_path=tmp_path / "nonexistent.json")
        with pytest.raises(FileNotFoundError):
            adapter.search("any phrase")


class TestEtsyBrowserAdapter:
    """Test browser adapter stub."""

    def test_browser_stub_raises_not_implemented(self):
        """Browser adapter must raise NotImplementedError."""
        adapter = EtsyBrowserAdapter()
        with pytest.raises(NotImplementedError, match="Browser adapter not yet implemented"):
            adapter.search("any phrase")


class TestEtsyAPIAdapter:
    """Test API adapter stub."""

    def test_api_stub_raises_not_implemented(self):
        """API adapter must raise NotImplementedError."""
        adapter = EtsyAPIAdapter()
        with pytest.raises(NotImplementedError, match="Etsy API adapter not yet implemented"):
            adapter.search("any phrase")


class TestGetResearchAdapter:
    """Test adapter factory function."""

    def test_get_adapter_fixture_mode(self):
        """Factory must return fixture adapter for 'fixture' mode."""
        adapter = get_research_adapter("fixture")
        assert isinstance(adapter, EtsyFixtureAdapter)

    def test_get_adapter_browser_mode(self):
        """Factory must return browser adapter for 'browser' mode."""
        adapter = get_research_adapter("browser")
        assert isinstance(adapter, EtsyBrowserAdapter)

    def test_get_adapter_api_mode(self):
        """Factory must return API adapter for 'api' mode."""
        adapter = get_research_adapter("api")
        assert isinstance(adapter, EtsyAPIAdapter)

    def test_get_adapter_invalid_mode(self):
        """Factory must raise ValueError for invalid mode."""
        with pytest.raises(ValueError, match="Unknown adapter mode"):
            get_research_adapter("invalid")


class TestResearchConfigIntegration:
    """Test integration with research config."""

    def test_config_loads_ten_seed_phrases(self):
        """Config must define exactly ten seed phrases, not hardcoded."""
        import yaml

        config_path = Path(__file__).resolve().parents[3] / "config" / "research.yaml"
        assert config_path.exists(), "research.yaml must exist in config/"

        with config_path.open() as f:
            config = yaml.safe_load(f)

        seed_phrases = config.get("research", {}).get("seed_phrases", [])
        assert len(seed_phrases) == 10, "Must define exactly 10 seed phrases"
        assert all(isinstance(p, str) for p in seed_phrases), "All phrases must be strings"

        # Verify they're not empty
        assert all(p.strip() for p in seed_phrases), "Phrases must not be empty"

    def test_seed_phrases_match_fixture_keys(self):
        """Seed phrases in config must match fixture data keys."""
        import yaml

        config_path = Path(__file__).resolve().parents[3] / "config" / "research.yaml"
        fixture_path = Path(__file__).resolve().parents[2] / "fixtures" / "etsy_search_results.json"

        with config_path.open() as f:
            config = yaml.safe_load(f)
        seed_phrases = config["research"]["seed_phrases"]

        with fixture_path.open() as f:
            fixtures = json.load(f)

        # All seed phrases must have fixture data
        for phrase in seed_phrases:
            assert phrase in fixtures, f"Fixture missing data for seed phrase: {phrase}"


class TestRealFixtureData:
    """Test the actual fixture data in tests/fixtures."""

    def test_real_fixtures_have_25_to_40_rows(self):
        """Real fixture file must have 25-40 observations per seed phrase."""
        fixture_path = Path(__file__).resolve().parents[2] / "fixtures" / "etsy_search_results.json"

        with fixture_path.open() as f:
            fixtures = json.load(f)

        for phrase, observations in fixtures.items():
            assert 25 <= len(observations) <= 40, (
                f"Phrase '{phrase}' has {len(observations)} observations; "
                f"must have 25-40"
            )

    def test_real_fixtures_thin_evidence(self):
        """Real fixtures must demonstrate thin evidence (some fields can be None)."""
        fixture_path = Path(__file__).resolve().parents[2] / "fixtures" / "etsy_search_results.json"

        with fixture_path.open() as f:
            fixtures = json.load(f)

        # Check that at least some observations have None for optional fields
        all_observations = [obs for observations in fixtures.values() for obs in observations]

        # At least 20% should have None for anchor_price_cents (thin evidence)
        none_anchor = sum(1 for obs in all_observations if obs.get("anchor_price_cents") is None)
        assert none_anchor > len(all_observations) * 0.2, (
            "Thin evidence: at least 20% observations should have None anchor_price_cents"
        )

    def test_real_fixtures_all_required_fields_present(self):
        """Real fixtures must have all required fields for every observation."""
        fixture_path = Path(__file__).resolve().parents[2] / "fixtures" / "etsy_search_results.json"

        with fixture_path.open() as f:
            fixtures = json.load(f)

        required_fields = {
            "rank",
            "title",
            "current_price_cents",
            "shop_name",
            "identity_niche",
            "base_category",
            "listing_url",
            "search_timestamp",
        }

        for phrase, observations in fixtures.items():
            for obs in observations:
                missing = required_fields - set(obs.keys())
                assert not missing, (
                    f"Phrase '{phrase}' observation missing required fields: {missing}"
                )


class TestEtsyFixtureAdapterWithRealData:
    """Test fixture adapter with real fixture file."""

    def test_adapter_loads_real_fixtures(self):
        """Adapter must successfully load real fixture file."""
        adapter = EtsyFixtureAdapter()  # Uses default path
        
        # Should be able to load at least one seed phrase
        observations = adapter.search("digital planner", target_count=30)
        assert 25 <= len(observations) <= 30
        
        # All observations must parse correctly
        for obs in observations:
            assert isinstance(obs, EtsyResearchObservation)
            assert obs.search_phrase == "digital planner"
            assert obs.rank > 0
            assert obs.current_price_cents > 0
