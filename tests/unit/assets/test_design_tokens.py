"""Design-token validation and the CSS emitter. No browser and no network."""

from __future__ import annotations

import ast
import sys
import types
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import cast

import pytest
from pydantic import ValidationError

from money_machine.assets.design_tokens import (
    MIN_CONTRAST,
    REQUIRED_TOKEN_KEYS,
    DesignTokens,
    TokenValidationError,
    bundled_font_path,
    contrast_ratio,
    emit_css,
    listing_token_payload,
    load_tokens,
)

_TOKENS = (
    Path(__file__).resolve().parents[3] / "src" / "money_machine" / "assets" / "design_tokens.py"
)
_SELECTORS = (
    ".mm-card",
    ".mm-device-frame",
    ".mm-icon",
    ".mm-hero",
    ".mm-overview",
    ".mm-hub-slide",
    ".mm-colour-options",
    ".mm-how-it-works",
    ".mm-device-compatibility",
    ".mm-pdf-page",
    ".mm-claim",
    ".mm-swatch",
    ".mm-steps",
    ".mm-phone",
    ".mm-tablet",
)


class _DropRefusal(ast.NodeTransformer):
    """Delete ``if refuse_*(...) is not None`` so that refusal can no longer fire."""

    def __init__(self, callee: str) -> None:
        self.callee = callee
        self.dropped = 0

    def visit_If(self, node: ast.If) -> ast.AST | None:
        if _is_refusal(node.test, self.callee):
            self.dropped += 1
            return None
        return self.generic_visit(node)


def _is_refusal(test: ast.expr, callee: str) -> bool:
    call = test.left if isinstance(test, ast.Compare) else None
    return (
        isinstance(test, ast.Compare)
        and len(test.ops) == 1
        and isinstance(test.ops[0], ast.IsNot)
        and isinstance(call, ast.Call)
        and isinstance(call.func, ast.Name)
        and call.func.id == callee
    )


def _mutant_load_tokens(callee: str) -> Callable[[Mapping[str, object]], DesignTokens]:
    drop = _DropRefusal(callee)
    tree = drop.visit(ast.parse(_TOKENS.read_text(encoding="utf-8")))
    if drop.dropped != 1 or not isinstance(tree, ast.Module):
        raise AssertionError(f"{callee} dropped {drop.dropped}")
    ast.fix_missing_locations(tree)
    name = f"token_mutant_{callee}"
    module = types.ModuleType(name)
    module.__file__ = str(_TOKENS)
    sys.modules[name] = module
    exec(compile(tree, str(_TOKENS), "exec"), module.__dict__)
    load = module.__dict__["load_tokens"]
    if not callable(load):
        raise AssertionError(callee)
    return cast(Callable[[Mapping[str, object]], DesignTokens], load)


def _white_on_white() -> dict[str, object]:
    payload = listing_token_payload()
    palette = payload["palette"]
    if not isinstance(palette, dict):
        raise AssertionError("palette")
    replaced = dict(palette)
    replaced["text"] = "#FFFFFF"
    replaced["background"] = "#FFFFFF"
    payload["palette"] = replaced
    return payload


def test_default_tokens_load_and_emit_the_listing_system() -> None:
    payload = listing_token_payload()
    assert tuple(REQUIRED_TOKEN_KEYS) == tuple(payload)
    tokens = load_tokens(payload)
    assert tokens.palette is not None
    assert tokens.typography is not None
    assert tokens.typography.font_family == "MM Listing"
    assert Path(tokens.typography.font_file) == bundled_font_path()
    assert bundled_font_path().is_file()
    pairs = (
        (tokens.palette.text, tokens.palette.background),
        (tokens.palette.text, tokens.palette.surface),
        (tokens.palette.muted, tokens.palette.background),
        (tokens.palette.muted, tokens.palette.surface),
        (tokens.palette.accent_text, tokens.palette.accent),
    )
    assert all(
        contrast_ratio(foreground, background) >= MIN_CONTRAST for foreground, background in pairs
    )
    css = emit_css(tokens)
    for selector in _SELECTORS:
        assert selector in css
    assert "#F6F3EE" in css
    assert "#1C1917" in css
    assert 'font-family: "MM Listing"' in css
    assert "data:font/ttf;base64," in css
    assert "--mm-pdf-width:" in css


def test_lowercase_hex_is_rejected() -> None:
    payload = listing_token_payload()
    palette = payload["palette"]
    if not isinstance(palette, dict):
        raise AssertionError("palette")
    replaced = dict(palette)
    replaced["text"] = "#1c1917"
    payload["palette"] = replaced
    with pytest.raises(ValidationError):
        load_tokens(payload)


def test_missing_token_keys_are_refused_and_the_mutant_accepts(tmp_path: Path) -> None:
    missing_palette = listing_token_payload()
    del missing_palette["palette"]
    missing_font = listing_token_payload()
    typography = missing_font["typography"]
    if not isinstance(typography, dict):
        raise AssertionError("typography")
    replaced = dict(typography)
    replaced["font_file"] = str(tmp_path / "absent.ttf")
    missing_font["typography"] = replaced
    empty_icons = listing_token_payload()
    empty_icons["icons"] = {}
    for payload in (missing_palette, missing_font, empty_icons):
        with pytest.raises(TokenValidationError, match="missing_token"):
            load_tokens(payload)
    mutant = _mutant_load_tokens("refuse_missing_token_keys")
    opened = mutant(missing_palette)
    assert opened.palette is None
    opened_font = mutant(missing_font)
    assert opened_font.typography is not None
    assert Path(opened_font.typography.font_file).is_file() is False


def test_low_contrast_is_refused_and_the_mutant_accepts() -> None:
    payload = _white_on_white()
    with pytest.raises(TokenValidationError, match="low_contrast"):
        load_tokens(payload)
    assert contrast_ratio("#FFFFFF", "#FFFFFF") < MIN_CONTRAST
    opened = _mutant_load_tokens("refuse_low_contrast")(payload)
    assert opened.palette is not None
    assert opened.palette.text == "#FFFFFF"
    assert opened.palette.background == "#FFFFFF"


def test_css_requires_every_section() -> None:
    with pytest.raises(TokenValidationError, match="missing_token"):
        emit_css(DesignTokens())
