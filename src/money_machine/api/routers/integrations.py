"""Integration readiness.

Reports configured or not configured from settings presence. This endpoint never reads a
credential value, performs a provider call, or opens a browser profile (D-0016,
corrective addendum 5).
"""

from __future__ import annotations

from fastapi import APIRouter

from money_machine.api.dependencies import SettingsDependency
from money_machine.api.schemas import IntegrationStatusResponse, ProviderStatus

router = APIRouter(prefix="/integrations", tags=["integrations"])


@router.get("/status", response_model=IntegrationStatusResponse)
async def integration_status(settings: SettingsDependency) -> IntegrationStatusResponse:
    """Report each provider's configuration presence and effect mode."""
    return IntegrationStatusResponse(
        environment=settings.environment.value,
        providers=tuple(
            ProviderStatus(
                name=provider.name,
                configured=provider.configured,
                effect_mode=provider.effect_mode,
                commissioned=provider.commissioned,
            )
            for provider in settings.providers
        ),
    )
