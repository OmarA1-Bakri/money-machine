from decimal import Decimal
from uuid import UUID

import pytest
from pydantic import ValidationError

from money_machine.domain.models.product_export import (
    ProductExportFile,
    ProductExportManifest,
    ProductExportResult,
)


def _file(path: str = "research/packet.json") -> ProductExportFile:
    return ProductExportFile(
        relative_path=path,
        media_type="application/json",
        byte_count=2,
        sha256="0" * 64,
        source_kind="durable_result",
        source_id="packet-1",
    )


def _results() -> tuple[ProductExportResult, ...]:
    steps = (
        "ADMIT_RESEARCH_PACKET",
        "QUALIFY_CANDIDATES",
        "CREATE_PRODUCT_SPEC",
        "CHECK_CATALOGUE_DEDUPE",
        "BUILD_PRODUCT",
        "RUN_PRODUCT_QA",
        "CREATE_LISTING_PACKAGE",
        "RUN_PREFLIGHT",
    )
    return tuple(
        ProductExportResult(
            step=step,
            result_type=f"result-{index}",
            result_id=f"id-{index}",
            sha256=f"{index:064x}",
        )
        for index, step in enumerate(steps, start=1)
    )


@pytest.mark.parametrize(
    "path",
    ("/private/file", "../escape", "nested/../escape", "C:/private/file", "bad\\file"),
)
def test_product_export_file_rejects_noncanonical_paths(path: str) -> None:
    with pytest.raises(ValidationError, match="canonical POSIX-relative"):
        _file(path)


def test_product_export_manifest_rejects_duplicate_inventory_and_nonzero_effects() -> None:
    with pytest.raises(ValidationError, match="export file paths must be unique"):
        ProductExportManifest(
            product_id="PS-0123456789abcdef01234567",
            product_spec_id="PS-0123456789abcdef01234567",
            workflow_run_id=UUID(int=1),
            packet_id="packet-1",
            terminal_state="DRAFT_READY",
            results=_results(),
            research_rows=30,
            candidates_scored=5,
            candidates_shortlisted=5,
            hubs=6,
            variants=3,
            tags=13,
            images=10,
            videos=1,
            access_pdfs=1,
            files=(_file(), _file()),
            external_mutations=0,
            spend_usd=Decimal("0.00"),
        )

    with pytest.raises(ValidationError):
        ProductExportManifest(
            product_id="PS-0123456789abcdef01234567",
            product_spec_id="PS-0123456789abcdef01234567",
            workflow_run_id=UUID(int=1),
            packet_id="packet-1",
            terminal_state="DRAFT_READY",
            results=_results(),
            research_rows=30,
            candidates_scored=5,
            candidates_shortlisted=5,
            hubs=6,
            variants=3,
            tags=13,
            images=10,
            videos=1,
            access_pdfs=1,
            files=(_file(),),
            external_mutations=1,  # pyright: ignore[reportArgumentType]
            spend_usd=Decimal("1.00"),
        )
