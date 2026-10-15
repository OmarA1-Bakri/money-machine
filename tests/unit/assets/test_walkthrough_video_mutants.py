"""AST drops for the walkthrough guards. Deselected from the kill count."""

from __future__ import annotations

import ast
import sys
import types
from pathlib import Path

import pytest

from tests.unit.assets import test_walkthrough_video as video_tests

_VIDEO = Path(__file__).resolve().parents[3] / "src" / "money_machine" / "assets" / "video.py"


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
    tree = drop.visit(ast.parse(_VIDEO.read_text(encoding="utf-8")))
    if drop.dropped != 1 or not isinstance(tree, ast.Module):
        raise AssertionError(f"{callee} dropped {drop.dropped}")
    ast.fix_missing_locations(tree)
    name = f"video_mutant_{callee}"
    module = types.ModuleType(name)
    module.__file__ = str(_VIDEO)
    sys.modules[name] = module
    exec(compile(tree, str(_VIDEO), "exec"), module.__dict__)
    return module


@pytest.fixture(scope="module")
def scene() -> video_tests._Scene:  # pyright: ignore[reportPrivateUsage]
    return video_tests.build_scene()


def test_missing_screenshot_mutant_accepts(
    scene: video_tests._Scene,  # pyright: ignore[reportPrivateUsage]
    tmp_path: Path,
) -> None:
    paths = dict(scene.paths)
    paths["hero"] = tmp_path / "missing.png"
    accepted = video_tests._render(  # pyright: ignore[reportPrivateUsage]
        scene,
        paths=paths,
        render=_mutant("refuse_missing_screenshot").render_walkthrough,
    )
    assert accepted.video.startswith(b"\x1a\x45\xdf\xa3")


def test_unknown_screenshot_mutant_accepts(
    scene: video_tests._Scene,  # pyright: ignore[reportPrivateUsage]
    tmp_path: Path,
) -> None:
    alien = tmp_path / "alien.png"
    alien.write_bytes(b"\x89PNG-not-an-allow-listed-fixture")
    paths = dict(scene.paths)
    paths["overview"] = alien
    accepted = video_tests._render(  # pyright: ignore[reportPrivateUsage]
        scene,
        paths=paths,
        render=_mutant("refuse_unknown_screenshot").render_walkthrough,
    )
    assert accepted.video.startswith(b"\x1a\x45\xdf\xa3")


def test_colon_caption_dropping_the_charset_check_accepts(
    scene: video_tests._Scene,  # pyright: ignore[reportPrivateUsage]
) -> None:
    accepted = video_tests._render(  # pyright: ignore[reportPrivateUsage]
        scene,
        injected_caption="a:b",
        render=_mutant("refuse_caption_charset").render_walkthrough,
    )
    assert accepted.video.startswith(b"\x1a\x45\xdf\xa3")


def test_checkout_caption_mutant_accepts(
    scene: video_tests._Scene,  # pyright: ignore[reportPrivateUsage]
) -> None:
    accepted = video_tests._render(  # pyright: ignore[reportPrivateUsage]
        scene,
        injected_caption="checkout",
        render=_mutant("refuse_caption_url").render_walkthrough,
    )
    assert accepted.video.startswith(b"\x1a\x45\xdf\xa3")


def test_unsupported_claim_mutant_accepts(
    scene: video_tests._Scene,  # pyright: ignore[reportPrivateUsage]
) -> None:
    accepted = video_tests._render(  # pyright: ignore[reportPrivateUsage]
        scene,
        copy=video_tests._bad_tag(scene.copy),  # pyright: ignore[reportPrivateUsage]
        render=_mutant("refuse_unvalidated_copy").render_walkthrough,
    )
    assert accepted.video.startswith(b"\x1a\x45\xdf\xa3")


def test_reordered_sequence_mutant_accepts(
    scene: video_tests._Scene,  # pyright: ignore[reportPrivateUsage]
) -> None:
    accepted = video_tests._render(  # pyright: ignore[reportPrivateUsage]
        scene,
        copy=video_tests._reordered(scene.copy),  # pyright: ignore[reportPrivateUsage]
        render=_mutant("refuse_scene_order").render_walkthrough,
    )
    assert accepted.video.startswith(b"\x1a\x45\xdf\xa3")


def test_wrong_marker_mutant_accepts(
    scene: video_tests._Scene,  # pyright: ignore[reportPrivateUsage]
) -> None:
    module = _mutant("refuse_scene_markers")
    setattr(module, "_compose_frames", video_tests._zero_frames)  # noqa: B010  # pyright: ignore[reportPrivateUsage]
    accepted = video_tests._render(  # pyright: ignore[reportPrivateUsage]
        scene,
        render=module.render_walkthrough,
    )
    assert accepted.video.startswith(b"\x1a\x45\xdf\xa3")


def test_small_container_mutant_accepts(
    scene: video_tests._Scene,  # pyright: ignore[reportPrivateUsage]
) -> None:
    module = _mutant("refuse_frame_size")
    small = video_tests._mkv(16, 16, 300)  # pyright: ignore[reportPrivateUsage]
    setattr(module, "_encode", video_tests._hold(small))  # noqa: B010  # pyright: ignore[reportPrivateUsage]
    accepted = video_tests._render(  # pyright: ignore[reportPrivateUsage]
        scene,
        render=module.render_walkthrough,
    )
    assert accepted.video.startswith(small)


class _RenameCall(ast.NodeTransformer):
    """Point the caption charset check back at the PDF prefix strip."""

    def __init__(self) -> None:
        self.renamed = 0

    def visit_Call(self, node: ast.Call) -> ast.AST:
        self.generic_visit(node)
        if isinstance(node.func, ast.Name) and node.func.id == "refuse_raw_charset":
            node.func.id = "refuse_gift_charset"
            self.renamed += 1
        return node


def _prefix_strip_mutant() -> types.ModuleType:
    rename = _RenameCall()
    tree = rename.visit(ast.parse(_VIDEO.read_text(encoding="utf-8")))
    if rename.renamed != 1 or not isinstance(tree, ast.Module):
        raise AssertionError(f"prefix strip renamed {rename.renamed}")
    ast.fix_missing_locations(tree)
    name = "video_mutant_prefix_strip"
    module = types.ModuleType(name)
    module.__file__ = str(_VIDEO)
    sys.modules[name] = module
    exec(compile(tree, str(_VIDEO), "exec"), module.__dict__)
    return module


def test_prefix_strip_mutant_accepts_free_gift_hello(
    scene: video_tests._Scene,  # pyright: ignore[reportPrivateUsage]
) -> None:
    accepted = video_tests._render(  # pyright: ignore[reportPrivateUsage]
        scene,
        injected_caption="Free gift: hello",
        render=_prefix_strip_mutant().render_walkthrough,
    )
    assert accepted.video.startswith(b"\x1a\x45\xdf\xa3")


def test_short_container_mutant_accepts(
    scene: video_tests._Scene,  # pyright: ignore[reportPrivateUsage]
) -> None:
    module = _mutant("refuse_duration")
    short = video_tests._mkv(  # pyright: ignore[reportPrivateUsage]
        video_tests._WIDTH,  # pyright: ignore[reportPrivateUsage]
        video_tests._HEIGHT,  # pyright: ignore[reportPrivateUsage]
        video_tests._FPS,  # pyright: ignore[reportPrivateUsage]
    )
    setattr(module, "_encode", video_tests._hold(short))  # noqa: B010  # pyright: ignore[reportPrivateUsage]
    accepted = video_tests._render(  # pyright: ignore[reportPrivateUsage]
        scene,
        render=module.render_walkthrough,
    )
    assert accepted.video.startswith(short)
