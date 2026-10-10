"""Fixture product facts for the A10 merchandising wave. No network calls."""

from __future__ import annotations

from uuid import UUID, uuid5

from money_machine.agents.contracts.merchandising import (
    BuiltVariant,
    FactKey,
    FreeGiftConfig,
    MerchandisingInput,
    NotificationDashboardBehaviour,
    ProductFact,
    SupportConfig,
    encode_dashboard,
    encode_free_gift,
    encode_support,
    money_text,
)
from money_machine.agents.implementations.merchandising import configured_listing_rules
from money_machine.domain.models.products import ProductSpec
from tests.fixtures.products import create_fixture_product_spec

_FACT_NAMESPACE = UUID("a1000000-0000-4000-8000-0000000000a0")
SHOP_NAME = "Fieldnote Shop"
PAGE_COUNT = 42
DEVICES = ("Tablet", "Phone")
SECRET_LINK = "https://fixture.notion.site"


def consistent_request(
    spec: ProductSpec | None = None,
) -> MerchandisingInput:
    """A request whose facts match the built spec, hubs, variants, and price."""
    product = create_fixture_product_spec() if spec is None else spec
    dashboard = NotificationDashboardBehaviour(
        present=True,
        outputs=("Today panel", "Reminder list"),
    )
    support = SupportConfig(offered=True, channel="Email inbox")
    gift = FreeGiftConfig(
        offered=True,
        name="Starter checklist",
        community="Planning circle",
    )
    values: dict[FactKey, str] = {
        "page_count": str(PAGE_COUNT),
        "hubs": "|".join(product.hubs),
        "colour_names": "|".join(product.colour_variants),
        "features": "|".join(product.features),
        "shop_name": SHOP_NAME,
        "price": money_text(product.real_price),
        "anchor_price": money_text(product.anchor_price),
        "currency": product.currency,
        "identity": product.identity,
        "base_category": product.base_category,
        "buyer_problem": product.buyer_problem,
        "support": encode_support(support),
        "free_gift": encode_free_gift(gift),
        "dashboard_outputs": encode_dashboard(dashboard),
        "supported_devices": "|".join(DEVICES),
        "secret_links": SECRET_LINK,
    }
    facts = tuple(
        ProductFact(
            fact_id=uuid5(_FACT_NAMESPACE, key),
            product_id=product.product_id,
            spec_id=product.spec_id,
            fact_key=key,
            fact_value=value,
        )
        for key, value in values.items()
    )
    return MerchandisingInput(
        spec=product,
        facts=facts,
        hubs=product.hubs,
        page_count=PAGE_COUNT,
        variants=tuple(BuiltVariant(name=name) for name in product.colour_variants),
        notification_dashboard=dashboard,
        shop_name=SHOP_NAME,
        price=product.real_price,
        anchor_price=product.anchor_price,
        support=support,
        free_gift=gift,
        rules=configured_listing_rules(),
    )
