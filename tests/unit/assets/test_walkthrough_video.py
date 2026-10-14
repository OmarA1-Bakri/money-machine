"""Silent walkthrough: scene order, duration, frame size, hashes, caption refusal."""

from __future__ import annotations

import hashlib
import importlib
import json
import os
import platform
import re
import subprocess
import sys
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import cast
from uuid import UUID

import pytest

from money_machine.agents.contracts.merchandising import (
    CitedText,
    ListingCopy,
    ListingDraft,
    MerchandisingInput,
    NotificationDashboardBehaviour,
    encode_dashboard,
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
from money_machine.assets.video_font import blit, wrap_caption
from money_machine.assets.video_paint import (
    CAPTION_Y,
    INJECTED_Y,
    LINE_HEIGHT,
    compose_frames,
)
from money_machine.domain.services.claim_validation import validate_claims
from money_machine.domain.services.listing_text import TextSlot, render
from tests.fixtures.listing_screenshots import fixture_screenshot_hashes, fixture_screenshot_paths
from tests.fixtures.merchandising import consistent_request
from tests.fixtures.products import create_fixture_product_spec

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


def _mkv(width: int, height: int, frames: int, fps: int = 10) -> bytes:
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
                str(fps),
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
    assert lineage.build_version == _BUILD
    trailer = _lineage_trailer(
        scene,
        expected,
        hashlib.sha256(encoded.encode()).hexdigest(),
    )
    assert picture.split(b"\nmm-lineage\n", 1)[1] == trailer.encode("ascii")
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


def _lineage_trailer(scene: _Scene, screenshots: tuple[str, ...], merchandising: str) -> str:
    """The trailer text, from fixture literals. Not read back from the lineage object."""
    return (
        f"product_id={scene.request.spec.product_id}\n"
        f"spec_version={scene.request.spec.version}\n"
        "build_version=4\n"
        f"screenshots={','.join(screenshots)}\n"
        f"merchandising_version={merchandising}\n"
        "template_version=s08-w4-video-1\n"
        "width=160\n"
        "height=90\n"
        "fps=10\n"
        "scene_order=dashboard,notification_panel,strongest_hubs,colour_options,duplication_access\n"
        "scene_frames=60,60,80,50,50\n"
        "qa_status=passed\n"
    )


# linux x86_64, imageio-ffmpeg 0.6.0, ffmpeg-linux-x86_64-v7.0.2.
# Pinned product, spec, and workflow ids. Not other wheels or other ids.
_GOLDEN_LINUX_X86_64 = "6318854297cd5d316fdf4c579a73f188ec5f1e2089745534aa9d4ca6245fe248"
_PINNED_PRODUCT = UUID("00000000-0000-4000-8000-0000000000a1")
_PINNED_SPEC = UUID("00000000-0000-4000-8000-0000000000a2")
_PINNED_WORKFLOW = UUID("00000000-0000-4000-8000-0000000000a3")
_HARMLESS_26 = "Notes stay on the frame no"
_HARMLESS_27 = "Notes stay on the frame now"
_LONG_OUTPUT = "aaaaaaaaaaaaaaaaaaetsy.com9"
_ROW_OUTPUTS = tuple(f"{left}{right}" for left in "abcde" for right in "abcde")


def _rgb(value: str) -> tuple[int, int, int]:
    return (int(value[1:3], 16), int(value[3:5], 16), int(value[5:7], 16))


def _dashboard(scene: _Scene, outputs: tuple[str, ...]) -> tuple[MerchandisingInput, ListingCopy]:
    dashboard = NotificationDashboardBehaviour(present=True, outputs=outputs)
    encoded = encode_dashboard(dashboard)
    facts = tuple(
        fact.model_copy(update={"fact_value": encoded})
        if fact.fact_key == "dashboard_outputs"
        else fact
        for fact in scene.request.facts
    )
    request = scene.request.model_copy(
        update={"facts": facts, "notification_dashboard": dashboard},
    )
    return request, merchandise(request)


def _wrong_hub(
    _screenshots: object,
    _tokens: object,
    _captions: object,
    _injected: object,
) -> bytes:
    """Scene index is right. The hub sub-index at frame 120 is 0 instead of 1."""
    raw = bytearray(_WIDTH * _HEIGHT * 3 * sum(_FRAMES))
    stride = _WIDTH * _HEIGHT * 3
    for index, (offset, count) in enumerate(zip(_OFFSETS, _FRAMES, strict=True), start=1):
        hub = 0
        for local in range(count):
            if index == 3:
                hub = 0
            base = (offset + local) * stride
            raw[base : base + 3] = bytes((index, 0, 0))
            raw[base + 3 : base + 6] = bytes((hub, 0, 0))
    return bytes(raw)


def _paint_band(
    caption: str,
    injected: str,
    text: tuple[int, int, int],
    background: tuple[int, int, int],
) -> bytes:
    frame = bytearray(background * (_WIDTH * _HEIGHT))
    for index, line in enumerate(wrap_caption(caption)):
        blit(frame, line, 2, CAPTION_Y + index * LINE_HEIGHT, text, _WIDTH)
    if injected:
        blit(frame, injected, 2, INJECTED_Y, text, _WIDTH)
    return bytes(frame)


def _band(raw: bytes, frame_index: int) -> bytes:
    stride = _WIDTH * _HEIGHT * 3
    start = frame_index * stride + CAPTION_Y * _WIDTH * 3
    end = frame_index * stride + (INJECTED_Y + LINE_HEIGHT) * _WIDTH * 3
    return raw[start:end]


def _expected_band(
    caption: str,
    injected: str,
    text: tuple[int, int, int],
    background: tuple[int, int, int],
) -> bytes:
    painted = _paint_band(caption, injected, text, background)
    start = CAPTION_Y * _WIDTH * 3
    end = (INJECTED_Y + LINE_HEIGHT) * _WIDTH * 3
    return painted[start:end]


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


def test_etsy_suffix_past_column_26_is_refused(scene: _Scene) -> None:
    with pytest.raises(VideoRefusal, match="caption_fit"):
        _render(scene, injected_caption="Notes and more at etsy.com9")


def test_a_long_dashboard_word_is_refused(scene: _Scene) -> None:
    request, copy = _dashboard(scene, (_LONG_OUTPUT,))
    assert validate_claims(copy.draft, request).passed is True
    with pytest.raises(VideoRefusal, match="caption_fit"):
        _render(scene, request=request, copy=copy)


def test_a_harmless_26_character_caption_is_painted(scene: _Scene) -> None:
    assert len(_HARMLESS_26) == 26
    walk = _render(scene, injected_caption=_HARMLESS_26)
    palette = scene.tokens.palette
    assert palette is not None
    text = _rgb(palette.text)
    background = _rgb(palette.background)
    raw = _decode(walk.video)
    captions = tuple(
        block.text for block in caption_blocks(scene.copy.draft, scene.request.rules.quantity)
    )
    for value in (*captions, _HARMLESS_26):
        assert refuse_gift_charset(value) is None
        assert refuse_paid_checkout(value) is None
    for offset, caption in zip(_OFFSETS, captions, strict=True):
        assert _band(raw, offset) == _expected_band(caption, _HARMLESS_26, text, background)


def test_a_harmless_27_character_caption_is_refused(scene: _Scene) -> None:
    assert len(_HARMLESS_27) == 27
    with pytest.raises(VideoRefusal, match="caption_fit"):
        _render(scene, injected_caption=_HARMLESS_27)


def test_too_many_caption_lines_are_refused(scene: _Scene) -> None:
    request, copy = _dashboard(scene, _ROW_OUTPUTS)
    assert validate_claims(copy.draft, request).passed is True
    with pytest.raises(VideoRefusal, match="caption_fit"):
        _render(scene, request=request, copy=copy)


def test_painted_bands_match_the_checked_captions(scene: _Scene, picture: bytes) -> None:
    palette = scene.tokens.palette
    assert palette is not None
    text = _rgb(palette.text)
    background = _rgb(palette.background)
    raw = _decode(picture)
    checked = tuple(
        block.text for block in caption_blocks(scene.copy.draft, scene.request.rules.quantity)
    )
    assert checked == _CAPTIONS
    for value in checked:
        assert refuse_gift_charset(value) is None
        assert refuse_paid_checkout(value) is None
    for offset, caption in zip(_OFFSETS, checked, strict=True):
        assert _band(raw, offset) == _expected_band(caption, "", text, background)


def test_compose_paints_the_twenty_seventh_character() -> None:
    injected = "ABCDEFGHIJKLMNOPQRSTUVWXYZ" + "H"
    background = (0xF6, 0xF3, 0xEE)
    text = (0x1C, 0x19, 0x17)
    accent = (0x1F, 0x3D, 0x32)
    blank = (bytes(32 * 32 * 3), 32, 32)
    frames = compose_frames(
        ("Ready.",) * 5,
        ((blank,),) * 5,
        background,
        text,
        accent,
        width=_WIDTH,
        height=_HEIGHT,
        scene_frames=(1, 1, 1, 1, 1),
        injected=injected,
    )
    start = (INJECTED_Y * _WIDTH + 2 + 26 * 6) * 3
    assert frames[start : start + 3] == bytes(text)


@pytest.mark.parametrize(
    "output",
    ["x.com.", "(x.com)", "x/y", "x@y", "at ko-fi.com/s/x"],
)
def test_claim_captions_refuse_a_url_or_excluded_character(scene: _Scene, output: str) -> None:
    request, copy = _dashboard(scene, (output,))
    assert validate_claims(copy.draft, request).passed is True
    with pytest.raises(VideoRefusal):
        _render(scene, request=request, copy=copy)


def test_a_hyphenated_caption_is_refused(scene: _Scene) -> None:
    with pytest.raises(VideoRefusal, match="caption_glyph"):
        _render(scene, injected_caption="x-.com")


def test_a_33_second_container_is_refused(scene: _Scene, monkeypatch: pytest.MonkeyPatch) -> None:
    long = _mkv(_WIDTH, _HEIGHT, 330, 10)
    monkeypatch.setattr("money_machine.assets.video._encode", _hold(long))
    with pytest.raises(VideoRefusal, match="duration"):
        _render(scene)


def test_a_12_fps_container_is_refused(scene: _Scene, monkeypatch: pytest.MonkeyPatch) -> None:
    fast = _mkv(_WIDTH, _HEIGHT, 360, 12)
    monkeypatch.setattr("money_machine.assets.video._encode", _hold(fast))
    with pytest.raises(VideoRefusal, match="frame_size"):
        _render(scene)


def test_a_160_by_80_container_is_refused(scene: _Scene, monkeypatch: pytest.MonkeyPatch) -> None:
    flat = _mkv(_WIDTH, 80, 300, 10)
    monkeypatch.setattr("money_machine.assets.video._encode", _hold(flat))
    with pytest.raises(VideoRefusal, match="frame_size"):
        _render(scene)


def test_a_wrong_hub_marker_is_refused(scene: _Scene, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("money_machine.assets.video._compose_frames", _wrong_hub)
    with pytest.raises(VideoRefusal, match="scene_markers"):
        _render(scene)


def test_an_unpainted_pdf_block_is_claim_checked(scene: _Scene) -> None:
    claim_id = scene.copy.draft.title.claim_ids[0]
    bad = CitedText(template_id="title", text="Not the title.", claim_ids=(claim_id,))
    draft = scene.copy.draft.model_copy(update={"pdf_blocks": (bad,)})
    copy = scene.copy.model_copy(update={"draft": draft})
    assert validate_claims(copy.draft, scene.request).passed is False
    with pytest.raises(VideoRefusal, match="unsupported_claim"):
        _render(scene, copy=copy)


def test_rendered_captions_are_claim_checked(
    scene: _Scene,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _bad(draft: ListingDraft, quantity: int) -> tuple[CitedText, ...]:
        blocks = caption_blocks(draft, quantity)
        first = blocks[0].model_copy(update={"text": "Not the cited caption."})
        return (first, *blocks[1:])

    monkeypatch.setattr("money_machine.assets.video.caption_blocks", _bad)
    assert validate_claims(scene.copy.draft, scene.request).passed is True
    with pytest.raises(VideoRefusal, match="unsupported_claim"):
        _render(scene)


def _linux_x86_64_wheel() -> bool:
    if sys.platform != "linux" or platform.machine() != "x86_64":
        return False
    return "linux-x86_64" in _ffmpeg()


def _pinned_walk(scene: _Scene) -> RenderedWalkthrough:
    spec = create_fixture_product_spec(
        product_id=_PINNED_PRODUCT,
        spec_id=_PINNED_SPEC,
        workflow_id=_PINNED_WORKFLOW,
    )
    request = consistent_request(spec)
    return _render(scene, request=request, copy=merchandise(request))


def test_linux_x86_64_hash_is_pinned(scene: _Scene) -> None:
    if not _linux_x86_64_wheel():
        pytest.skip("golden hash is pinned for the linux x86_64 wheel")
    assert hashlib.sha256(_pinned_walk(scene).video).hexdigest() == _GOLDEN_LINUX_X86_64


def test_cross_process_hash_matches_the_pin() -> None:
    if not _linux_x86_64_wheel():
        pytest.skip("golden hash is pinned for the linux x86_64 wheel")
    env = dict(os.environ)
    env["PYTHONHASHSEED"] = "7"
    env["TZ"] = "Pacific/Kiritimati"
    env["LANG"] = "C"
    env["LC_ALL"] = "C"
    code = "\n".join(
        (
            "import hashlib",
            "from money_machine.agents.implementations.merchandising import merchandise",
            "from money_machine.assets.design_tokens import listing_token_payload, load_tokens",
            "from money_machine.assets.video import render_walkthrough",
            "from tests.fixtures.listing_screenshots import (",
            "    fixture_screenshot_hashes,",
            "    fixture_screenshot_paths,",
            ")",
            "from tests.fixtures.merchandising import consistent_request",
            "from tests.fixtures.products import create_fixture_product_spec",
            "from uuid import UUID",
            "spec = create_fixture_product_spec(",
            '    product_id=UUID("00000000-0000-4000-8000-0000000000a1"),',
            '    spec_id=UUID("00000000-0000-4000-8000-0000000000a2"),',
            '    workflow_id=UUID("00000000-0000-4000-8000-0000000000a3"),',
            ")",
            "request = consistent_request(spec)",
            "copy = merchandise(request)",
            "walk = render_walkthrough(",
            "    copy,",
            "    request,",
            "    fixture_screenshot_paths(),",
            "    fixture_screenshot_hashes(),",
            "    load_tokens(listing_token_payload()),",
            "    build_version=4,",
            ")",
            "print(hashlib.sha256(walk.video).hexdigest())",
        )
    )
    completed = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        check=False,
        env=env,
        cwd=Path(__file__).resolve().parents[3],
    )
    assert completed.returncode == 0, completed.stderr.decode("utf-8", errors="replace")
    assert completed.stdout.decode().strip() == _GOLDEN_LINUX_X86_64


def test_empty_access_caption_is_refused() -> None:
    with pytest.raises(ValueError, match="access"):
        render("video_duplication_caption", (TextSlot("access", ""),), quantity=1)
