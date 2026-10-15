"""AST drops for the screenshot guards. Deselected from the kill count."""

from __future__ import annotations

import ast
import subprocess
import sys
import types
from pathlib import Path
from uuid import UUID

import pytest
from playwright.sync_api import sync_playwright

_SHOTS = Path(__file__).resolve().parents[3] / "src" / "money_machine" / "assets" / "screenshots.py"
_ROOT = Path(__file__).resolve().parents[2] / "fixtures" / "variant_pages"
_LIVE = "https://www.notion.so/private-variant-page"
_PRODUCT = UUID("00000000-0000-4000-8000-0000000000b1")


class _DropRefusal(ast.NodeTransformer):
    """Delete ``if refuse_*(...) is not None``."""

    def __init__(self, callee: str) -> None:
        self.callee = callee
        self.dropped = 0

    def visit_If(self, node: ast.If) -> ast.AST | None:
        call = node.test.left if isinstance(node.test, ast.Compare) else None
        if (
            isinstance(node.test, ast.Compare)
            and len(node.test.ops) == 1
            and isinstance(node.test.ops[0], ast.IsNot)
            and isinstance(call, ast.Call)
            and isinstance(call.func, ast.Name)
            and call.func.id == self.callee
        ):
            self.dropped += 1
            return None
        return self.generic_visit(node)


def _mutant(callee: str) -> types.ModuleType:
    drop = _DropRefusal(callee)
    tree = drop.visit(ast.parse(_SHOTS.read_text(encoding="utf-8")))
    if drop.dropped != 1 or not isinstance(tree, ast.Module):
        raise AssertionError(f"{callee} dropped {drop.dropped}")
    ast.fix_missing_locations(tree)
    return _load(tree, f"screenshot_mutant_{callee}")


def _load(tree: ast.Module, name: str) -> types.ModuleType:
    module = types.ModuleType(name)
    module.__file__ = str(_SHOTS)
    sys.modules[name] = module
    exec(compile(tree, str(_SHOTS), "exec"), module.__dict__)
    return module


def _live_html_mutant() -> types.ModuleType:
    source = _SHOTS.read_text(encoding="utf-8")
    html = (_ROOT / "sage-green.html").read_text(encoding="utf-8")
    literal = repr(html)
    mutated = source.replace(
        'raise ScreenshotRefusal("live_acquisition")',
        f"return {literal}",
        1,
    )
    if mutated == source:
        raise AssertionError("live raise was not replaced")
    parsed = ast.parse(mutated)
    return _load(parsed, "screenshot_mutant_live_fetch")


def _launch_chromium() -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, args=["--no-sandbox"])
        browser.close()


@pytest.fixture(scope="module", autouse=True)
def _browser() -> None:  # pyright: ignore[reportUnusedFunction]
    try:
        _launch_chromium()
    except Exception:
        subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=True)
        _launch_chromium()


def test_sensitive_mutant_accepts(tmp_path: Path) -> None:
    module = _mutant("refuse_sensitive_text")
    path = tmp_path / "email.html"
    path.write_text(
        "<!DOCTYPE html><html data-mm-ready='loaded'><body><p>person@example.com</p></body></html>",
        encoding="utf-8",
    )
    page = module.VariantPage(name="Sample", html_path=path)
    accepted = module.capture_variant_screenshots(
        (page,),
        build_version=5,
        product_id=_PRODUCT,
        spec_version=1,
    )
    assert accepted[0].png.startswith(b"\x89PNG")


def test_unready_mutant_accepts(tmp_path: Path) -> None:
    module = _mutant("refuse_unready")
    path = tmp_path / "blank.html"
    path.write_text(
        "<!DOCTYPE html><html><body><p>Sample fixture</p></body></html>",
        encoding="utf-8",
    )
    page = module.VariantPage(name="Sample", html_path=path)
    accepted = module.capture_variant_screenshots(
        (page,),
        build_version=5,
        product_id=_PRODUCT,
        spec_version=1,
    )
    assert accepted[0].png.startswith(b"\x89PNG")


def test_live_refusal_mutant_accepts() -> None:
    module = _live_html_mutant()
    page = module.VariantPage(name="Sage Green", live_url=_LIVE)
    accepted = module.capture_variant_screenshots(
        (page,),
        build_version=5,
        product_id=_PRODUCT,
        spec_version=1,
    )
    assert accepted[0].png.startswith(b"\x89PNG")
    assert accepted[0].lineage.source == "injected"
