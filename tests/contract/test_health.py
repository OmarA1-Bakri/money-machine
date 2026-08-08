from typing import cast

import httpx
from fastapi.testclient import TestClient

from money_machine.api.main import app


def test_health_contract() -> None:
    response = cast(
        httpx.Response,
        TestClient(app).get("/health"),  # pyright: ignore[reportUnknownMemberType]
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "api",
        "version": "0.1.0",
    }


def test_health_openapi_schema_is_typed() -> None:
    operation = app.openapi()["paths"]["/health"]["get"]
    success_schema = operation["responses"]["200"]["content"]["application/json"]["schema"]

    assert success_schema == {"$ref": "#/components/schemas/HealthResponse"}
