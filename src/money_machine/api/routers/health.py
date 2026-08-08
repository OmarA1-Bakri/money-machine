"""Process liveness endpoint."""

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

from money_machine.version import __version__

router = APIRouter(tags=["system"])


class HealthResponse(BaseModel):
    """Typed liveness response for the API process.

    This response deliberately makes no database or provider-readiness claim.
    """

    model_config = ConfigDict(frozen=True)

    status: Literal["ok"]
    service: Literal["api"]
    version: str


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Report that this API process is alive."""
    return HealthResponse(status="ok", service="api", version=__version__)
