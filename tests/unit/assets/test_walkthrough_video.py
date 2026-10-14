"""Silent walkthrough: scene order, duration, frame size, hashes, caption refusal."""

from __future__ import annotations

import hashlib
import importlib
import json
import re
import subprocess
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import pytest

from money_machine.agents.contracts.merchandising import (
    ListingCopy,
    ListingDraft,
    MerchandisingInput,
)
from money_machine.agents.implementations.merchandising import merchandise
from money_machine.assets.design_tokens import (
    DesignTokens,
    TokenValidationError,
    listing_token_payload,
    load_tokens,
)
from money_machine.assets.gift_links import refuse_gift_charset, refuse_paid_checkout
from money_machine.assets.video import (
    RenderedWalkthrough,
    VideoRefusal,
    caption_blocks,
    render_walkthrough,
)
from money_machine.domain.services.claim_validation import validate_claims
from tests.fixtures.listing_screenshots import fixture_screenshot_hashes, fixture_screenshot_paths
from tests.fixtures.merchandising import consistent_request

_BUILD = 4
_WIDTH = 160
_HEIGHT = 90
_FPS = 10
_FRAMES = (60, 60, 80, 50, 50)
_ROLES = (
    "hero",
    "overview",
    "hub_1",
    "hub_2",
    "hub_3",
    "hub_4",
    "hub_5",
    "colour_options",
    "how_it_works",
)
_CAPTIONS = (
    "Dashboard Today panel, Reminder list.",
    "Notification panel Today panel, Reminder list.",
    "Hubs Daily Planning, Goal Tracking, Habit Builder.",
    "Variants Sage Green, Navy Blue, Rose Gold.",
    "Duplicate the template.",
)
_OFFSETS = (0, 60, 120, 200, 250)


@dataclass(frozen=True, slots=True)
class _Scene:
    request: MerchandisingInput
    copy: ListingCopy
    tokens: DesignTokens
    paths: dict[str, Path]
    allowed: frozenset[str]


def _ffmpeg() -> str:
    module = importlib.import_module("imageio_ffmpeg")
    get_exe = module.get_ffmpeg_exe
    if not callable(get_exe):
        raise AssertionError("ffmpeg")
    exe = get_exe()
    if not isinstance(exe, str) or exe == "":
        raise AssertionError("ffmpeg")
    return exe


def _run(command: list[str], data: bytes | None = None) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(command, input=data, capture_output=True, check=False)


def _probe(video: bytes) -> tuple[float, int, int, float, str]:
    """Duration, width, height, fps, and the ffmpeg banner. Independent of video.py."""
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "walkthrough.mkv"
        path.write_bytes(video)
        completed = _run([_ffmpeg(), "-hide_banner", "-i", str(path)])
    text = completed.stderr.decode("utf-8", errors="replace")
    duration = re.search(r"Duration:\s*(\d+):(\d\d):(\d\d(?:\.\d+)?)", text)
    frame = re.search(r"(\d+)x(\d+),\s*(\d+(?:\.\d+)?)\s*fps", text)
    if duration is None or frame is None:
        raise AssertionError(text)
    total = int(duration.group(1)) * 3600 + int(duration.group(2)) * 60
    total += float(duration.group(3))
    return total, int(frame.group(1)), int(frame.group(2)), float(frame.group(3)), text


def _decode(video: bytes) -> bytes:
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "walkthrough.mkv"
        path.write_bytes(video)
        completed = _run(
            [
                _ffmpeg(),
                "-hide_banner",
                "-loglevel",
                "error",
                "-i",
                str(path),
                "-f",
                "rawvideo",
                "-pix_fmt",
                "rgb24",
                "pipe:1",
            ]
        )
    if completed.returncode != 0:
        raise AssertionError(completed.stderr.decode("utf-8", errors="replace"))
    return completed.stdout


def _png(path: Path) -> bytes:
    completed = _run(
        [
            _ffmpeg(),
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(path),
            "-f",
            "rawvideo",
            "-pix_fmt",
            "rgb24",
            "pipe:1",
        ]
    )
    if completed.returncode != 0:
        raise AssertionError(path.name)
    return completed.stdout


def _mkv(width: int, height: int, frames: int) -> bytes:
    raw = bytes(width * height * 3 * frames)
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "probe.mkv"
        completed = _run(
            [
                _ffmpeg(),
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-f",
                "rawvideo",
                "-pix_fmt",
                "rgb24",
                "-s",
                f"{width}x{height}",
                "-r",
                "10",
                "-i",
                "pipe:0",
                "-an",
                "-c:v",
                "ffv1",
                "-level",
                "3",
                "-pix_fmt",
                "rgb24",
                "-threads",
                "1",
                str(path),
            ],
            raw,
        )
        if completed.returncode != 0 or not path.is_file():
            raise AssertionError(completed.stderr.decode("utf-8", errors="replace"))
        return path.read_bytes()


def _pixel(raw: bytes, frame: int, x: int, y: int) -> tuple[int, int, int]:
    start = (frame * _WIDTH * _HEIGHT + y * _WIDTH + x) * 3
    return raw[start], raw[start + 1], raw[start + 2]


def build_scene() -> _Scene:
    request = consistent_request()
    copy = merchandise(request)
    assert validate_claims(copy.draft, request).passed is True
    return _Scene(
        request=request,
        copy=copy,
        tokens=load_tokens(listing_token_payload()),
        paths=fixture_screenshot_paths(),
        allowed=fixture_screenshot_hashes(),
    )


@pytest.fixture(scope="module")
def scene() -> _Scene:
    return build_scene()


def _render(
    scene: _Scene,
    *,
    request: MerchandisingInput | None = None,
    copy: ListingCopy | None = None,
    paths: dict[str, Path] | None = None,
    allowed: frozenset[str] | None = None,
    tokens: DesignTokens | None = None,
    injected_caption: str = "",
    render: Callable[..., object] | None = None,
) -> RenderedWalkthrough:
    chosen = render_walkthrough if render is None else render
    result = chosen(
        scene.copy if copy is None else copy,
        scene.request if request is None else request,
        scene.paths if paths is None else paths,
        scene.allowed if allowed is None else allowed,
        scene.tokens if tokens is None else tokens,
        build_version=_BUILD,
        injected_caption=injected_caption,
    )
    if isinstance(result, RenderedWalkthrough):
        return result
    if hasattr(result, "video") and hasattr(result, "lineage"):
        return cast(RenderedWalkthrough, result)
    raise AssertionError("walkthrough")


@pytest.fixture(scope="module")
def walk(scene: _Scene) -> RenderedWalkthrough:
    return _render(scene)


@pytest.fixture(scope="module")
def picture(walk: RenderedWalkthrough) -> bytes:
    return walk.video


def test_scenes_are_in_playbook_order(picture: bytes) -> None:
    raw = _decode(picture)
    assert len(raw) == _WIDTH * _HEIGHT * 3 * sum(_FRAMES)
    for index, offset in enumerate(_OFFSETS, start=1):
        assert _pixel(raw, offset, 0, 0) == (index, 0, 0)
    assert _pixel(raw, 120, 1, 0)[0] == 1
    assert _pixel(raw, 136, 1, 0)[0] == 2
    assert _pixel(raw, 152, 1, 0)[0] == 3
    assert _pixel(raw, 168, 1, 0)[0] == 4
    assert _pixel(raw, 184, 1, 0)[0] == 5
    assert _pixel(raw, 200, 1, 0)[0] == 0
    assert _pixel(raw, 0, 0, 89) == (0x1F, 0x3D, 0x32)
    assert _pixel(raw, 0, 2, 2) == (0xF6, 0xF3, 0xEE)


def test_pasted_screenshot_matches_the_fixture_png(scene: _Scene, picture: bytes) -> None:
    raw = _decode(picture)
    hero = _png(scene.paths["hero"])
    hub = _png(scene.paths["hub_2"])
    assert _pixel(raw, 0, 8, 2) == (hero[0], hero[1], hero[2])
    assert _pixel(raw, 136, 8, 2) == (hub[0], hub[1], hub[2])


def test_duration_is_thirty_seconds_inside_the_bound(picture: bytes) -> None:
    seconds, _width, _height, _fps, text = _probe(picture)
    assert 28.0 <= seconds <= 32.0
    assert abs(seconds - 30.0) < 0.001
    assert "Audio:" not in text


def test_frames_are_160_by_90_at_10_fps(picture: bytes) -> None:
    _seconds, width, height, fps, _text = _probe(picture)
    assert (width, height, fps) == (_WIDTH, _HEIGHT, float(_FPS))


def test_the_same_inputs_encode_the_same_bytes(scene: _Scene, picture: bytes) -> None:
    again = _render(scene)
    assert getattr(again, "video", None) == picture


def test_captions_cite_the_claims_and_hide_the_access_url(scene: _Scene, picture: bytes) -> None:
    blocks = caption_blocks(scene.copy.draft, scene.request.rules.quantity)
    assert tuple(block.text for block in blocks) == _CAPTIONS
    for text in _CAPTIONS:
        assert refuse_gift_charset(text) is None
        assert refuse_paid_checkout(text) is None
    assert b"https://" not in picture
    assert b"fixture.notion" not in picture


def test_a_url_like_caption_is_refused(scene: _Scene) -> None:
    with pytest.raises(VideoRefusal, match="paid_checkout"):
        _render(scene, injected_caption="www.example.com")


def test_a_colon_caption_is_refused(scene: _Scene) -> None:
    with pytest.raises(VideoRefusal, match="paid_checkout"):
        _render(scene, injected_caption="a:b")


def test_a_checkout_caption_is_refused(scene: _Scene) -> None:
    with pytest.raises(VideoRefusal, match="paid_checkout"):
        _render(scene, injected_caption="checkout")


def test_lineage_matches_the_fixture_files_and_the_bytes(
    scene: _Scene, walk: RenderedWalkthrough, picture: bytes
) -> None:
    lineage = walk.lineage
    expected = tuple(hashlib.sha256(scene.paths[role].read_bytes()).hexdigest() for role in _ROLES)
    payload = scene.copy.draft.model_dump(mode="json")
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    assert lineage.source_screenshot_sha256 == expected
    assert lineage.output_sha256 == hashlib.sha256(picture).hexdigest()
    assert lineage.merchandising_version == hashlib.sha256(encoded.encode()).hexdigest()
    assert lineage.scene_order == (
        "dashboard",
        "notification_panel",
        "strongest_hubs",
        "colour_options",
        "duplication_access",
    )
    assert lineage.scene_frames == _FRAMES
    assert lineage.template_version == "s08-w4-video-1"
    assert lineage.qa_status == "passed"
    assert lineage.width_px == _WIDTH
    assert lineage.height_px == _HEIGHT
    assert lineage.fps == _FPS
    assert f"spec_version={scene.request.spec.version}\n".encode() in picture
    assert lineage.output_sha256.encode() not in picture


def test_a_higher_spec_version_changes_the_hash(
    scene: _Scene, walk: RenderedWalkthrough, picture: bytes
) -> None:
    spec = scene.request.spec.model_copy(update={"version": scene.request.spec.version + 1})
    request = scene.request.model_copy(update={"spec": spec})
    updated = _render(scene, request=request)
    assert updated.lineage.spec_version == scene.request.spec.version + 1
    assert updated.lineage.merchandising_version == walk.lineage.merchandising_version
    assert updated.video != picture
    assert hashlib.sha256(updated.video).hexdigest() != hashlib.sha256(picture).hexdigest()


def test_a_missing_screenshot_is_refused(scene: _Scene, tmp_path: Path) -> None:
    paths = dict(scene.paths)
    paths["hero"] = tmp_path / "missing.png"
    with pytest.raises(VideoRefusal, match="missing_screenshot"):
        _render(scene, paths=paths)


def test_an_unknown_screenshot_is_refused(scene: _Scene, tmp_path: Path) -> None:
    alien = tmp_path / "alien.png"
    alien.write_bytes(b"\x89PNG-not-an-allow-listed-fixture")
    paths = dict(scene.paths)
    paths["overview"] = alien
    with pytest.raises(VideoRefusal, match="unknown_screenshot"):
        _render(scene, paths=paths)


def test_an_unsupported_claim_is_refused(scene: _Scene) -> None:
    bad = _bad_tag(scene.copy)
    assert validate_claims(bad.draft, scene.request).passed is False
    with pytest.raises(VideoRefusal, match="unsupported_claim"):
        _render(scene, copy=bad)


def test_a_reordered_sequence_is_refused(scene: _Scene) -> None:
    with pytest.raises(VideoRefusal, match="scene_order"):
        _render(scene, copy=_reordered(scene.copy))


def _zero_frames(
    _screenshots: object,
    _tokens: object,
    _captions: object,
    _injected: object,
) -> bytes:
    return bytes(_WIDTH * _HEIGHT * 3 * sum(_FRAMES))


def _hold(payload: bytes) -> Callable[[bytes], bytes]:
    def _encode(_frames: bytes) -> bytes:
        return payload

    return _encode


def test_a_wrong_marker_buffer_is_refused(scene: _Scene, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("money_machine.assets.video._compose_frames", _zero_frames)
    with pytest.raises(VideoRefusal, match="scene_markers"):
        _render(scene)


def test_a_small_container_is_refused(scene: _Scene, monkeypatch: pytest.MonkeyPatch) -> None:
    small = _mkv(16, 16, 300)
    monkeypatch.setattr("money_machine.assets.video._encode", _hold(small))
    with pytest.raises(VideoRefusal, match="frame_size"):
        _render(scene)


def test_a_short_container_is_refused(scene: _Scene, monkeypatch: pytest.MonkeyPatch) -> None:
    short = _mkv(_WIDTH, _HEIGHT, _FPS)
    monkeypatch.setattr("money_machine.assets.video._encode", _hold(short))
    with pytest.raises(VideoRefusal, match="duration"):
        _render(scene)


def test_low_contrast_tokens_are_refused(scene: _Scene) -> None:
    with pytest.raises(TokenValidationError, match="low_contrast"):
        _render(scene, tokens=_white_tokens())


def _bad_tag(copy: ListingCopy) -> ListingCopy:
    first = copy.draft.tags[0]
    updated = first.model_copy(update={"text": "500 sold"})
    draft = copy.draft.model_copy(update={"tags": (updated, *copy.draft.tags[1:])})
    return copy.model_copy(update={"draft": draft})


def _reordered(copy: ListingCopy) -> ListingCopy:
    beats = list(copy.draft.video_sequence)
    swapped = (beats[1], beats[0], *beats[2:])
    fields = {name: getattr(copy.draft, name) for name in ListingDraft.model_fields}
    fields["video_sequence"] = swapped
    draft = ListingDraft.model_construct(**fields)
    return ListingCopy.model_construct(draft=draft, rules=copy.rules)


def _white_tokens() -> DesignTokens:
    payload = listing_token_payload()
    palette = payload["palette"]
    if not isinstance(palette, dict):
        raise AssertionError("palette")
    replaced = dict(palette)
    replaced["text"] = "#FFFFFF"
    replaced["background"] = "#FFFFFF"
    payload["palette"] = replaced
    return DesignTokens.model_validate(payload)
