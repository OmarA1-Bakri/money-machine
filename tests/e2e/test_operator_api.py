"""Run-scoped operator views prove fresh PostgreSQL reads and access policy."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from money_machine.api.dependencies import ApplicationState
from money_machine.api.main import create_app
from money_machine.config.runtime import DatabaseSettings, RuntimeSettings
from money_machine.config.settings import RuntimeEnvironment
from money_machine.persistence.tables import Product
from tests.integration.alembic_support import upgrade
from tests.integration.factories import make_job, make_shop, make_workflow

RUN_ID = "20261020T211445Z"


@pytest.fixture
async def operator_state(
    test_database: str, repository_root: Path
) -> AsyncGenerator[ApplicationState]:
    await asyncio.to_thread(upgrade, test_database, repository_root)
    state = ApplicationState.create(
        RuntimeSettings(
            environment=RuntimeEnvironment.TEST, database=DatabaseSettings(url=test_database)
        )
    )
    try:
        yield state
    finally:
        await state.dispose()


@pytest.fixture
async def operator_client(operator_state: ApplicationState) -> AsyncGenerator[AsyncClient]:
    app = create_app()
    app.state.application = operator_state
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://api") as client:
        yield client


async def seed_product(factory: async_sessionmaker[AsyncSession], run_id: str = RUN_ID) -> str:
    async with factory() as session:
        shop = await make_shop(session, "fixture:" + run_id)
        workflow = await make_workflow(session, shop)
        job = await make_job(session, workflow)
        product = Product(
            id=uuid4(),
            shop_id=shop.id,
            workflow_id=workflow.id,
            producing_job_id=job.id,
            identity="fixture",
            base_category="planner",
            working_title="Stored planner",
        )
        session.add(product)
        await session.commit()
        return str(product.id)


async def test_operator_view_reads_current_run_rows(
    operator_client: AsyncClient,
    operator_state: ApplicationState,
) -> None:
    product_id = await seed_product(operator_state.session_factory)
    response = await operator_client.get("/operator/now", params={"run_id": RUN_ID})
    assert response.status_code == 200
    assert response.json()["run_id"] == RUN_ID
    assert response.json()["items"][0]["product_id"] == product_id
    assert response.json()["items"][0]["label"] == "Stored planner"


async def seed_views(factory: async_sessionmaker[AsyncSession]) -> dict[str, Any]:
    from datetime import UTC, datetime
    from decimal import Decimal

    from sqlalchemy import select

    from money_machine.persistence.tables import (
        Decision,
        EtsyListing,
        Incident,
        IntegrationAccount,
        Job,
        ListingVersion,
        ProductSpec,
        WorkflowRun,
    )
    from tests.integration.factories import make_agent_run

    product_id = await seed_product(factory)
    async with factory() as session:
        product = await session.get(Product, product_id)
        assert product is not None
        job = await session.scalar(select(Job).where(Job.workflow_id == product.workflow_id))
        assert job is not None
        job.status = "BLOCKED"
        job.input = {"reason": "expected fixture negative", "token": "never-expose"}
        from money_machine.persistence.tables import AgentRun

        existing_run = await session.scalar(select(AgentRun).limit(1))
        if existing_run is None:
            run = await make_agent_run(session, job)
        else:
            values = {
                column.name: getattr(existing_run, column.name)
                for column in AgentRun.__table__.columns
            }
            values.update(id=uuid4(), job_id=job.id)
            run = AgentRun(**values)
            session.add(run)
            await session.flush()
        spec = ProductSpec(
            id=uuid4(),
            product_id=product.id,
            workflow_id=product.workflow_id,
            version=1,
            producing_job_id=job.id,
            producing_agent_run_id=run.id,
            identity="fixture",
            base_category="planner",
            buyer_problem="fixture",
            title="fixture",
            tier="low",
            real_price=Decimal("10"),
            anchor_price=Decimal("20"),
            currency="USD",
            experiment_plan="fixture",
            concept_fingerprint="a" * 64,
            rule_version="fixture",
        )
        session.add(spec)
        await session.flush()
        listing = EtsyListing(id=uuid4(), shop_id=product.shop_id, product_id=product.id)
        session.add(listing)
        await session.flush()
        version = ListingVersion(
            id=uuid4(),
            listing_id=listing.id,
            product_id=product.id,
            spec_id=spec.id,
            producing_job_id=job.id,
            listing_version=1,
            title="Stored listing",
            currency="USD",
            price=Decimal("10"),
            anchor_price=Decimal("20"),
            quantity=999,
            rule_version="fixture",
            package_sha256=uuid4().hex * 2,
        )
        session.add(version)
        await session.flush()
        decision = Decision(
            id=uuid4(),
            workflow_id=product.workflow_id,
            job_id=job.id,
            decision_type="fixture decision",
            branch_outcome="FAIL",
            product_id=product.id,
            rule_version="fixture",
            explanation="expected negative",
            decided_at=datetime.now(UTC),
        )
        incident = Incident(
            id=uuid4(),
            shop_id=product.shop_id,
            incident_type="BUILD_DEFECT",
            affected_object_type="products",
            affected_object_id=product.id,
            workflow_id=product.workflow_id,
            listing_version_id=version.id,
            opened_by_job_id=job.id,
            safe_detail={"reason": "expected fixture refusal", "credentials": "never-expose"},
        )
        account = IntegrationAccount(
            id=uuid4(),
            shop_id=product.shop_id,
            provider="fixture",
            capability_channel="INTERNAL_RENDERER",
            safe_detail={"mode": "simulation", "token": "never-expose"},
            blocker_code="FIXTURE",
        )
        session.add_all([decision, incident, account])
        await session.commit()
        return {
            "now": product,
            "pipeline": job,
            "shop": version,
            "blocked": job,
            "decisions": decision,
            "incidents": incident,
            "settings": account,
            "workflow": await session.get(WorkflowRun, product.workflow_id),
        }


async def test_shop_reads_product_from_same_statement_as_listing(
    operator_state: ApplicationState,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from sqlalchemy import false

    from money_machine.persistence.tables import ListingVersion, WorkflowRun

    rows = await seed_views(operator_state.session_factory)
    await seed_product(operator_state.session_factory, "another-run")
    original_execute = AsyncSession.execute
    empty_product_reads = 0
    listing_reads = 0

    async def execute(session: AsyncSession, statement: Any, *args: Any, **kwargs: Any) -> Any:
        nonlocal empty_product_reads, listing_reads
        entities = [column["entity"] for column in statement.column_descriptions]
        if entities == [Product, WorkflowRun]:
            # Model an earlier READ COMMITTED snapshot before the product became visible.
            empty_product_reads += 1
            statement = statement.where(false())
        elif entities and entities[0] is ListingVersion:
            listing_reads += 1
        return await original_execute(session, statement, *args, **kwargs)

    monkeypatch.setattr(AsyncSession, "execute", execute)
    app = create_app()
    app.state.application = operator_state
    async with AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False), base_url="http://api"
    ) as client:
        response = await client.get("/operator/shop", params={"run_id": RUN_ID})
    assert empty_product_reads == 1
    assert listing_reads == 1
    assert response.status_code == 200
    assert response.json()["run_id"] == RUN_ID
    assert response.json()["items"] == [
        {
            "id": str(rows["shop"].id),
            "label": "Stored listing",
            "state": "DRAFT",
            "detail": "version 1; USD 10.00",
            "product_id": str(rows["now"].id),
            "listing_version_id": str(rows["shop"].id),
        }
    ]


@pytest.mark.parametrize(
    "view", ["now", "pipeline", "shop", "blocked", "decisions", "incidents", "settings"]
)
async def test_each_view_reads_changed_rows(
    operator_client: AsyncClient,
    operator_state: ApplicationState,
    view: str,
) -> None:
    from sqlalchemy import update

    from money_machine.persistence.tables import (
        Decision,
        Incident,
        IntegrationAccount,
        Job,
        ListingVersion,
    )

    rows = await seed_views(operator_state.session_factory)
    await seed_product(operator_state.session_factory, "another-run")
    response = await operator_client.get("/operator/" + view, params={"run_id": RUN_ID})
    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["product_id"] == str(rows["now"].id)
    assert items[0]["listing_version_id"] == str(rows["shop"].id)
    assert set(items[0]) == {"id", "label", "state", "detail", "product_id", "listing_version_id"}
    assert "never-expose" not in response.text
    assert "another-run" not in response.text
    values: dict[str, Any] = {}
    async with operator_state.session_factory() as session:
        if view == "shop":
            old = rows["shop"]
            values = {
                column.name: getattr(old, column.name)
                for column in ListingVersion.__table__.columns
            }
            values.update(
                id=uuid4(),
                listing_version=2,
                title="Changed listing",
                package_sha256=uuid4().hex * 2,
            )
            session.add(ListingVersion(**values))
        else:
            model, field, value = {
                "now": (Product, "working_title", "Changed product"),
                "pipeline": (Job, "job_type", "Changed pipeline"),
                "blocked": (Job, "input", {"reason": "Changed blocker"}),
                "decisions": (Decision, "explanation", "Changed decision"),
                "incidents": (Incident, "safe_detail", {"reason": "Changed incident"}),
                "settings": (IntegrationAccount, "blocker_code", "CHANGED"),
            }[view]
            await session.execute(
                update(model).where(model.id == rows[view].id).values(**{field: value})
            )
        await session.commit()
    changed = await operator_client.get("/operator/" + view, params={"run_id": RUN_ID})
    assert changed.status_code == 200
    assert changed.json() != response.json()
    if view == "shop":
        assert {item["id"] for item in changed.json()["items"]} == {
            str(rows["shop"].id),
            str(values["id"]),
        }


async def test_run_selection_and_input_validation(
    operator_client: AsyncClient,
    operator_state: ApplicationState,
) -> None:
    from datetime import UTC, datetime

    from sqlalchemy import update

    from money_machine.persistence.tables import Shop

    assert (await operator_client.get("/operator/now")).status_code == 404
    await seed_product(operator_state.session_factory)
    assert (await operator_client.get("/operator/now")).json()["run_id"] == RUN_ID
    await seed_product(operator_state.session_factory, "newest")
    async with operator_state.session_factory() as session:
        await session.execute(
            update(Shop)
            .where(Shop.name == "fixture:newest")
            .values(created_at=datetime(2030, 1, 1, tzinfo=UTC))
        )
        await session.commit()
    assert (await operator_client.get("/operator/now")).json()["run_id"] == "newest"
    assert (
        await operator_client.get("/operator/now", params={"run_id": "missing"})
    ).status_code == 404
    for invalid in ("", "../bad", "x" * 81, "fixture:bad", "bad run"):
        assert (
            await operator_client.get("/operator/now", params={"run_id": invalid})
        ).status_code == 422
    assert (await operator_client.get("/operator/other")).status_code == 422


async def test_database_outage_returns_safe_unavailable() -> None:
    app = create_app()
    state = ApplicationState.create(
        RuntimeSettings(
            environment=RuntimeEnvironment.TEST,
            database=DatabaseSettings(
                url="postgresql+asyncpg://private:never-expose@127.0.0.1:1/absent"
            ),
        )
    )
    app.state.application = state
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://api") as client:
            for view in (
                "now",
                "pipeline",
                "shop",
                "blocked",
                "decisions",
                "incidents",
                "settings",
            ):
                response = await client.get("/operator/" + view, params={"run_id": RUN_ID})
                assert response.status_code == 503
                assert response.json() == {"detail": "operator database unavailable"}
    finally:
        await state.dispose()


@pytest.mark.parametrize(
    "path", ["/workflows", "/workflows/{id}/cancel", "/jobs/{id}/retry", "/jobs/{id}/reconcile"]
)
async def test_mutations_require_operator(
    operator_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    path: str,
) -> None:
    monkeypatch.setenv("MONEY_MACHINE_OPERATOR_TOKEN", "test-operator-credential")
    path = path.replace("{id}", str(uuid4()))
    for headers in ({}, {"Authorization": "Bearer wrong"}):
        response = await operator_client.post(path, headers=headers)
        assert response.status_code == 401
        assert "test-operator-credential" not in response.text
    monkeypatch.delenv("MONEY_MACHINE_OPERATOR_TOKEN")
    assert (
        await operator_client.post(
            path, headers={"Authorization": "Bearer test-operator-credential"}
        )
    ).status_code == 401


async def test_authorized_existing_workflow_behavior(
    operator_client: AsyncClient,
    operator_state: ApplicationState,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MONEY_MACHINE_OPERATOR_TOKEN", "test-operator-credential")
    async with operator_state.session_factory() as session:
        shop = await make_shop(session)
        workflow = await make_workflow(session, shop)
        job = await make_job(session, workflow, status="FAILED")
        await session.commit()
    headers = {"Authorization": "Bearer test-operator-credential"}
    response = await operator_client.post(
        "/workflows",
        headers=headers,
        params={
            "shop_id": str(shop.id),
            "workflow_type": "ProductLifecycleWorkflow",
            "product_state": "DISCOVERED",
        },
    )
    assert response.status_code == 201
    assert response.json()["product_state"] == "DISCOVERED"
    retried = await operator_client.post(f"/jobs/{job.id}/retry", headers=headers)
    assert retried.status_code == 200
    assert retried.json()["status"] == "READY"
    cancelled = await operator_client.post(f"/workflows/{workflow.id}/cancel", headers=headers)
    assert cancelled.status_code == 200
    assert cancelled.json()["cancelled_count"] == 1

    from datetime import UTC, datetime

    from money_machine.persistence.tables import EffectAttempt

    async with operator_state.session_factory() as session:
        uncertain = await make_job(session, workflow, status="UNCERTAIN_EXTERNAL_EFFECT")
        session.add(
            EffectAttempt(
                id=uuid4(),
                idempotency_key=uncertain.idempotency_key,
                job_id=uncertain.id,
                provider="fixture",
                operation="fixture",
                effect_state="UNKNOWN",
                observed_at=datetime.now(UTC),
            )
        )
        await session.commit()
    successful = await operator_client.post(
        f"/jobs/{uncertain.id}/reconcile", headers=headers, params={"effect_state": "ABSENT"}
    )
    assert successful.status_code == 200
    assert successful.json()["effect_state"] == "ABSENT"
    # Authorized invalid reconciliation reaches the existing business rule, not the auth wall.
    reconciled = await operator_client.post(
        f"/jobs/{job.id}/reconcile", headers=headers, params={"effect_state": "ABSENT"}
    )
    assert reconciled.status_code == 400
    assert "Cannot reconcile effect" in reconciled.json()["detail"]


async def test_real_runs_scope_every_view_to_selected_workflow(
    operator_client: AsyncClient,
    operator_state: ApplicationState,
) -> None:
    from sqlalchemy import select

    from money_machine.persistence.tables import (
        EtsyListing,
        Incident,
        IntegrationAccount,
        Shop,
        WorkflowRun,
    )

    first = await seed_views(operator_state.session_factory)
    # Reuse a second fixture seed in the same database, then place both workflows in
    # the actual shared-shop topology. Shop-scoped queries would expose both runs.
    async with operator_state.session_factory() as session:
        shop = await session.get(Shop, first["now"].shop_id)
        assert shop is not None
        shop.name = "QuietlyBuiltStudio"
        workflow = await session.get(WorkflowRun, first["now"].workflow_id)
        assert workflow is not None
        workflow.workflow_type = "RealProductDraft:real-one"
        await session.commit()
    second = await seed_views(operator_state.session_factory)
    async with operator_state.session_factory() as session:
        shop = await session.get(Shop, first["now"].shop_id)
        assert shop is not None
        product = await session.get(Product, second["now"].id)
        workflow = await session.get(WorkflowRun, second["now"].workflow_id)
        assert product is not None
        listing = await session.scalar(
            select(EtsyListing).where(EtsyListing.product_id == product.id)
        )
        incident = await session.get(Incident, second["incidents"].id)
        assert product is not None and workflow is not None and listing is not None
        assert incident is not None
        product.shop_id = shop.id
        workflow.shop_id = shop.id
        workflow.workflow_type = "RealProductDraft:real-two"
        listing.shop_id = shop.id
        incident.shop_id = shop.id
        # Shop readiness is shared; it must not be labelled with either product's lineage.
        account = await session.get(IntegrationAccount, first["settings"].id)
        assert account is not None
        account.blocker_code = "AUTH_REQUIRED"
        await session.commit()
    for selected, rows, other in (("real-one", first, second), ("real-two", second, first)):
        for view in ("now", "pipeline", "shop", "blocked", "decisions", "incidents", "settings"):
            response = await operator_client.get("/operator/" + view, params={"run_id": selected})
            assert response.status_code == 200
            body = response.json()
            assert body["execution_mode"] == "real_draft"
            assert body["run_id"] == selected
            assert len(body["items"]) == 1
            assert str(other["now"].id) not in response.text
            if view == "settings":
                assert body["items"][0]["product_id"] is None
                assert body["items"][0]["listing_version_id"] is None
            else:
                assert body["items"][0]["product_id"] == str(rows["now"].id)
                assert body["items"][0]["id"] == str(rows[view].id)
    assert (
        await operator_client.get("/operator/now", params={"run_id": "real-missing"})
    ).status_code == 404
