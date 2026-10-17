"""Read standing authority and keep publish, purchase, and checkout off.

The check loads the tracked autonomy template and applies the development
reduction. It does not invent a cap, read ``.env``, or open a socket.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from money_machine.config.loader import load_yaml_model
from money_machine.config.settings import AutonomyConfig, RuntimeEnvironment
from money_machine.config.validation import apply_environment_safety

_EXAMPLE = Path("config/autonomy.example.yaml")


class StandingAuthorityRefusal(ValueError):
    """Publish, purchase, checkout, or another live authority is enabled."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class StandingAuthority:
    """The fail-closed authority. Every spend and publish switch is false."""

    auto_publish: bool
    auto_deactivate: bool
    auto_multiply: bool
    competitor_purchase_enabled: bool
    live_checkout_test_enabled: bool
    purchase_caps: tuple[Decimal, Decimal]
    checkout_cap: Decimal


def record_standing_authority(
    authority: AutonomyConfig | None = None,
    *,
    root: Path | None = None,
) -> StandingAuthority:
    """Return the template authority. An enabled publish or spend switch raises."""
    if authority is None:
        repo = Path(__file__).resolve().parents[3] if root is None else root
        loaded = load_yaml_model(repo / _EXAMPLE, AutonomyConfig)
        authority = apply_environment_safety(loaded, RuntimeEnvironment.DEVELOPMENT)
    if authority.auto_publish:
        raise StandingAuthorityRefusal("publish")
    if authority.auto_deactivate:
        raise StandingAuthorityRefusal("deactivate")
    if authority.auto_multiply:
        raise StandingAuthorityRefusal("multiply")
    purchase_caps = (
        authority.competitor_purchase_max_each,
        authority.competitor_purchase_monthly_cap,
    )
    if authority.competitor_purchase_enabled or any(cap > 0 for cap in purchase_caps):
        raise StandingAuthorityRefusal("purchase")
    if authority.live_checkout_test_enabled or authority.live_checkout_test_cap > 0:
        raise StandingAuthorityRefusal("checkout")
    if authority.external_mutations_enabled or authority.external_spend_enabled:
        raise StandingAuthorityRefusal("live_authority")
    return StandingAuthority(
        auto_publish=False,
        auto_deactivate=False,
        auto_multiply=False,
        competitor_purchase_enabled=False,
        live_checkout_test_enabled=False,
        purchase_caps=purchase_caps,
        checkout_cap=authority.live_checkout_test_cap,
    )
