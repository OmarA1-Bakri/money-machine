"""Product specification, dedupe, build, and QA repositories."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from money_machine.domain.models.product import BuildResult, ProductQAResult
from money_machine.domain.models.product_spec import DedupeResult, ProductSpec
from money_machine.persistence.database import JsonModelRepository
from money_machine.persistence.tables import (
    build_results,
    dedupe_results,
    product_qa_results,
    product_specs,
)


class ProductRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._specs = JsonModelRepository(session, product_specs, "product_spec_id", ProductSpec)
        self._dedupe = JsonModelRepository(
            session, dedupe_results, "dedupe_result_id", DedupeResult
        )
        self._builds = JsonModelRepository(session, build_results, "build_id", BuildResult)
        self._qa = JsonModelRepository(
            session, product_qa_results, "product_qa_result_id", ProductQAResult
        )

    async def add_spec(self, spec: ProductSpec) -> None:
        await self._specs.add(spec, identity=spec.product_spec_id)

    async def get_spec(self, product_spec_id: str) -> ProductSpec | None:
        return await self._specs.get(product_spec_id)

    async def add_dedupe(self, result: DedupeResult) -> None:
        await self._dedupe.add(
            result,
            identity=result.dedupe_result_id,
            extra_values={"product_spec_id": result.product_spec_id},
        )

    async def get_dedupe(self, dedupe_result_id: str) -> DedupeResult | None:
        return await self._dedupe.get(dedupe_result_id)

    async def add_build(self, result: BuildResult) -> None:
        await self._builds.add(
            result,
            identity=result.build_id,
            extra_values={"product_spec_id": result.product_spec_id},
        )

    async def get_build(self, build_id: str) -> BuildResult | None:
        return await self._builds.get(build_id)

    async def add_qa(self, result: ProductQAResult) -> None:
        await self._qa.add(
            result,
            identity=result.qa_result_id,
            extra_values={"build_id": result.build_id},
        )

    async def get_qa(self, qa_result_id: str) -> ProductQAResult | None:
        return await self._qa.get(qa_result_id)
