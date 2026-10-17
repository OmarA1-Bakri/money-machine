"""The fixture product paths call the domain and refuse a live publish."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from money_machine.assets.synthetic_paths import (
    BROKEN_LINK_STEPS,
    CULL_STEPS,
    DEDUPE_STEPS,
    MAIN_STEPS,
    REPAIR_STEPS,
    SyntheticPathRefusal,
    run_synthetic_paths,
    simulate_publish,
)
from money_machine.domain.enums import BranchOutcome

_MODULE = Path("src/money_machine/assets/synthetic_paths.py")


def test_main_chain_reaches_a_withheld_successor_build() -> None:
    run = run_synthetic_paths()
    steps = [item.step for item in run.receipts if item.path == "main"]
    assert tuple(steps) == MAIN_STEPS
    assert run.published_live is False
    publish = next(item for item in run.receipts if item.step == "publish_simulation")
    assert publish.outcome == "WITHHELD"
    verification = next(item for item in run.receipts if item.step == "post_publish_verification")
    assert verification.outcome == "BLOCKED_BY_EXTERNAL_CREDENTIAL"
    successor = next(item for item in run.receipts if item.step == "successor_build_job")
    assert successor.outcome == "WITHHELD"


def test_alternate_paths_keep_their_order() -> None:
    run = run_synthetic_paths()
    by_path = {
        path: tuple(item.step for item in run.receipts if item.path == path)
        for path in ("cull", "repair", "broken_link", "dedupe")
    }
    assert by_path["cull"] == CULL_STEPS
    assert by_path["repair"] == REPAIR_STEPS
    assert by_path["broken_link"] == BROKEN_LINK_STEPS
    assert by_path["dedupe"] == DEDUPE_STEPS
    cull = next(item for item in run.receipts if item.step == "deactivation")
    assert cull.outcome == "UNEXECUTED"
    reply = next(item for item in run.receipts if item.step == "response")
    assert reply.outcome == "DRAFT"
    passed = next(item for item in run.receipts if item.path == "dedupe" and item.step == "pass")
    assert passed.outcome == BranchOutcome.PASS.value


def test_a_second_run_matches_the_first() -> None:
    assert run_synthetic_paths() == run_synthetic_paths()


def test_live_publish_is_refused() -> None:
    with pytest.raises(SyntheticPathRefusal, match="live_publish"):
        simulate_publish(mode="live", idempotency_key="live")


def test_the_path_module_imports_no_network_client() -> None:
    tree = ast.parse(_MODULE.read_text(encoding="utf-8"))
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.append(node.module)
    folded = " ".join(modules)
    assert all(token not in folded for token in ("socket", "httpx", "urllib", "requests"))
