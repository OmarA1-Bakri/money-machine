"""Silent fixture walkthrough for A11. The agent stays DESIGNED and unregistered.

Frames are drawn from the committed listing screenshots and the W2 tokens.
There is no audio and no browser. The encoder is the locked ``imageio-ffmpeg``
wheel: FFV1 in Matroska, one thread, bitexact. The hash is stable for that
wheel. It is not a claim about any other ffmpeg build.

On-screen text is a caption template of the cited claims, then the gift
allowlist and the gift URL refusal. The access URL is not painted.
"""

from __future__ import annotations

import hashlib
import importlib
import os
import re
import subprocess
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, assert_never
from uuid import UUID

from money_machine.agents.contracts.merchandising import (
    VIDEO_BEATS,
    CitedText,
    ListingClaim,
    ListingCopy,
    ListingDraft,
    MerchandisingInput,
    VideoRole,
)
from money_machine.assets.design_tokens import DesignTokens, load_tokens
from money_machine.assets.gift_links import refuse_gift_charset, refuse_paid_checkout
from money_machine.assets.listing_images import merchandising_version
from money_machine.assets.video_paint import blank_rgb, compose_frames, decode_png_rgb, scene_marker
from money_machine.domain.services.claim_validation import validate_claims
from money_machine.domain.services.listing_text import TextSlot, render

VIDEO_TEMPLATE_VERSION = "s08-w4-video-1"
VIDEO_WIDTH = 160
VIDEO_HEIGHT = 90
VIDEO_FPS = 10
SCENE_FRAMES: tuple[int, ...] = (60, 60, 80, 50, 50)
_MIN_SECONDS = 28.0
_MAX_SECONDS = 32.0
_EPOCH = "1767225600"
_MISSING = b"missing-screenshot"
_DURATION = re.compile(r"Duration:\s*(\d+):(\d\d):(\d\d(?:\.\d+)?)")
_FRAME = re.compile(r"(\d+)x(\d+),\s*(\d+(?:\.\d+)?)\s*fps")


class VideoRefusal(ValueError):
    """The walkthrough was refused before a container was returned."""


@dataclass(frozen=True, slots=True)
class WalkthroughLineage:
    """Record bound after the container. QA status is ``passed`` only on return."""

    product_id: UUID
    spec_version: int
    build_version: int
    source_screenshot_sha256: tuple[str, ...]
    merchandising_version: str
    template_version: str
    output_sha256: str
    width_px: int
    height_px: int
    fps: int
    scene_order: tuple[VideoRole, ...]
    scene_frames: tuple[int, ...]
    qa_status: Literal["passed"]


@dataclass(frozen=True, slots=True)
class RenderedWalkthrough:
    """The Matroska bytes, plus the lineage appended after them."""

    video: bytes
    lineage: WalkthroughLineage


def render_walkthrough(
    copy: ListingCopy,
    request: MerchandisingInput,
    screenshots: Mapping[str, Path],
    allowed_screenshot_sha256: frozenset[str],
    tokens: DesignTokens,
    *,
    build_version: int,
    injected_caption: str = "",
) -> RenderedWalkthrough:
    """Render the five beats. ``injected_caption`` is buyer-facing and must pass.

    Production callers leave ``injected_caption`` empty. A non-empty value is
    painted only when the gift charset and the gift URL refusal both allow it.
    """
    load_tokens(tokens.model_dump())
    if refuse_missing_screenshot(screenshots) is not None:
        raise VideoRefusal("missing_screenshot")
    if refuse_unknown_screenshot(screenshots, allowed_screenshot_sha256) is not None:
        raise VideoRefusal("unknown_screenshot")
    if refuse_scene_order(copy.draft) is not None:
        raise VideoRefusal("scene_order")
    blocks = caption_blocks(copy.draft, request.rules.quantity)
    if refuse_unvalidated_copy(copy.draft, request, blocks) is not None:
        raise VideoRefusal("unsupported_claim")
    painted = tuple(block.text for block in blocks)
    visible = painted + ((injected_caption,) if injected_caption else ())
    if refuse_caption_charset(visible) is not None:
        raise VideoRefusal("paid_checkout")
    if refuse_caption_url(visible) is not None:
        raise VideoRefusal("paid_checkout")
    frames = _compose_frames(screenshots, tokens, painted, injected_caption)
    if refuse_scene_markers(frames) is not None:
        raise VideoRefusal("scene_markers")
    encoded = _encode(frames)
    if refuse_frame_size(encoded) is not None:
        raise VideoRefusal("frame_size")
    if refuse_duration(encoded) is not None:
        raise VideoRefusal("duration")
    return _bind(encoded, copy, request, screenshots, build_version=build_version)


def refuse_missing_screenshot(screenshots: Mapping[str, Path]) -> str | None:
    """Return ``missing_screenshot`` when a used fixture file is absent."""
    for role in _screenshot_roles():
        path = screenshots.get(role)
        if path is None or not Path(path).is_file():
            return "missing_screenshot"
    return None


def refuse_unknown_screenshot(
    screenshots: Mapping[str, Path],
    allowed_screenshot_sha256: frozenset[str],
) -> str | None:
    """Return ``unknown_screenshot`` when a used file is outside the allow-list."""
    for role in _screenshot_roles():
        path = screenshots.get(role)
        if path is None or not Path(path).is_file():
            continue
        digest = hashlib.sha256(Path(path).read_bytes()).hexdigest()
        if digest not in allowed_screenshot_sha256:
            return "unknown_screenshot"
    return None


def refuse_scene_order(draft: ListingDraft) -> str | None:
    """Return ``scene_order`` when the beats are not the playbook order."""
    if tuple(beat.role for beat in draft.video_sequence) != VIDEO_BEATS:
        return "scene_order"
    return None


def refuse_unvalidated_copy(
    draft: ListingDraft,
    request: MerchandisingInput,
    blocks: tuple[CitedText, ...],
) -> str | None:
    """Return ``unsupported_claim`` when the copy or the captions fail claims."""
    if not validate_claims(draft, request).passed:
        return "unsupported_claim"
    probed = _with_blocks(draft, blocks)
    if not validate_claims(probed, request).passed:
        return "unsupported_claim"
    return None


def refuse_caption_charset(texts: tuple[str, ...]) -> str | None:
    """Return ``paid_checkout`` when painted text leaves the gift allowlist."""
    for text in texts:
        if refuse_gift_charset(text) is not None:
            return "paid_checkout"
    return None


def refuse_caption_url(texts: tuple[str, ...]) -> str | None:
    """Return ``paid_checkout`` when painted text looks like a URL or address."""
    for text in texts:
        if refuse_paid_checkout(text) is not None:
            return "paid_checkout"
    return None


def refuse_scene_markers(frames: bytes) -> str | None:
    """Return ``scene_markers`` when a decoded pixel is not the pinned marker."""
    stride = VIDEO_WIDTH * VIDEO_HEIGHT * 3
    if len(frames) != stride * sum(SCENE_FRAMES):
        return "scene_markers"
    offset = 0
    for index, count in enumerate(SCENE_FRAMES, start=1):
        shot_count = len(_scene_roles(VIDEO_BEATS[index - 1]))
        for local in range(count):
            base = (offset + local) * stride
            red, green, blue, hub = scene_marker(index, local, count, shot_count)
            if frames[base : base + 3] != bytes((red, green, blue)):
                return "scene_markers"
            if frames[base + 3] != hub:
                return "scene_markers"
        offset += count
    return None


def refuse_frame_size(video: bytes) -> str | None:
    """Return ``frame_size`` when the container is not 160x90 at 10 fps."""
    _seconds, width, height, fps = _probe(video)
    if width != VIDEO_WIDTH or height != VIDEO_HEIGHT or fps != float(VIDEO_FPS):
        return "frame_size"
    return None


def refuse_duration(video: bytes) -> str | None:
    """Return ``duration`` when the container is outside 28-32 seconds."""
    seconds, _width, _height, _fps = _probe(video)
    if seconds < _MIN_SECONDS or seconds > _MAX_SECONDS:
        return "duration"
    return None


def caption_blocks(draft: ListingDraft, quantity: int) -> tuple[CitedText, ...]:
    """The five on-screen sentences, in playbook order, citing the beat claims."""
    beats = {beat.role: beat for beat in draft.video_sequence}
    claims = {claim.claim_id: claim for claim in draft.claims}
    blocks: list[CitedText] = []
    for role in VIDEO_BEATS:
        beat = beats[role]
        cited = tuple(claims[claim_id] for claim_id in beat.claim_ids)
        template_id = _caption_template(role)
        text = render(template_id, _slots(cited), quantity=quantity)
        blocks.append(
            CitedText(template_id=template_id, text=text, claim_ids=beat.claim_ids),
        )
    return tuple(blocks)


def _caption_template(role: VideoRole) -> str:
    if role == "dashboard":
        return "video_dashboard_caption"
    if role == "notification_panel":
        return "video_notification_caption"
    if role == "strongest_hubs":
        return "video_hubs_caption"
    if role == "colour_options":
        return "video_variants_caption"
    if role == "duplication_access":
        return "video_duplication_caption"
    assert_never(role)


def _scene_roles(role: VideoRole) -> tuple[str, ...]:
    if role == "dashboard":
        return ("hero",)
    if role == "notification_panel":
        return ("overview",)
    if role == "strongest_hubs":
        return ("hub_1", "hub_2", "hub_3", "hub_4", "hub_5")
    if role == "colour_options":
        return ("colour_options",)
    if role == "duplication_access":
        return ("how_it_works",)
    assert_never(role)


def _screenshot_roles() -> tuple[str, ...]:
    return tuple(name for role in VIDEO_BEATS for name in _scene_roles(role))


def _slots(claims: tuple[ListingClaim, ...]) -> tuple[TextSlot, ...]:
    return tuple(TextSlot(claim.kind, claim.stated_value) for claim in claims)


def _with_blocks(draft: ListingDraft, blocks: tuple[CitedText, ...]) -> ListingDraft:
    kwargs = {name: getattr(draft, name) for name in ListingDraft.model_fields}
    kwargs["pdf_blocks"] = blocks
    return ListingDraft.model_construct(**kwargs)


def _compose_frames(
    screenshots: Mapping[str, Path],
    tokens: DesignTokens,
    captions: tuple[str, ...],
    injected: str,
) -> bytes:
    scenes: list[tuple[tuple[bytes, int, int], ...]] = []
    for role in VIDEO_BEATS:
        shots = tuple(_shot(screenshots.get(name)) for name in _scene_roles(role))
        scenes.append(shots)
    palette = tokens.palette
    if palette is None:
        raise VideoRefusal("encode")
    return compose_frames(
        captions,
        tuple(scenes),
        _rgb(palette.background),
        _rgb(palette.text),
        _rgb(palette.accent),
        width=VIDEO_WIDTH,
        height=VIDEO_HEIGHT,
        scene_frames=SCENE_FRAMES,
        injected=injected,
    )


def _shot(path: Path | None) -> tuple[bytes, int, int]:
    data = _file_bytes(path)
    try:
        width, height, rgb = decode_png_rgb(data)
    except ValueError:
        return blank_rgb()
    return rgb, width, height


def _file_bytes(path: Path | None) -> bytes:
    if path is None or not Path(path).is_file():
        return _MISSING
    return Path(path).read_bytes()


def _rgb(value: str) -> tuple[int, int, int]:
    return (int(value[1:3], 16), int(value[3:5], 16), int(value[5:7], 16))


def _encode(frames: bytes) -> bytes:
    expected = VIDEO_WIDTH * VIDEO_HEIGHT * 3 * sum(SCENE_FRAMES)
    if len(frames) != expected:
        raise VideoRefusal("encode")
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "walkthrough.mkv"
        command = [
            _ffmpeg_exe(),
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "rgb24",
            "-s",
            f"{VIDEO_WIDTH}x{VIDEO_HEIGHT}",
            "-r",
            str(VIDEO_FPS),
            "-i",
            "pipe:0",
            "-an",
            "-c:v",
            "ffv1",
            "-level",
            "3",
            "-coder",
            "1",
            "-context",
            "1",
            "-g",
            "1",
            "-slices",
            "1",
            "-slicecrc",
            "1",
            "-pix_fmt",
            "rgb24",
            "-fflags",
            "+bitexact",
            "-flags",
            "+bitexact",
            "-map_metadata",
            "-1",
            "-threads",
            "1",
            str(path),
        ]
        completed = subprocess.run(
            command,
            input=frames,
            capture_output=True,
            check=False,
            env=_encode_env(),
        )
        if completed.returncode != 0 or not path.is_file():
            raise VideoRefusal("encode")
        return path.read_bytes()


def _probe(video: bytes) -> tuple[float, int, int, float]:
    if not video.startswith(b"\x1a\x45\xdf\xa3"):
        raise VideoRefusal("container")
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "walkthrough.mkv"
        path.write_bytes(video)
        completed = subprocess.run(
            [_ffmpeg_exe(), "-hide_banner", "-i", str(path)],
            capture_output=True,
            check=False,
            env=_encode_env(),
        )
    text = completed.stderr.decode("utf-8", errors="replace")
    duration = _DURATION.search(text)
    frame = _FRAME.search(text)
    if duration is None or frame is None:
        raise VideoRefusal("container")
    seconds = int(duration.group(1)) * 3600 + int(duration.group(2)) * 60
    seconds += float(duration.group(3))
    return seconds, int(frame.group(1)), int(frame.group(2)), float(frame.group(3))


def _ffmpeg_exe() -> str:
    try:
        module = importlib.import_module("imageio_ffmpeg")
        get_exe = module.get_ffmpeg_exe
    except (AttributeError, ModuleNotFoundError) as exc:
        raise VideoRefusal("encode") from exc
    if not callable(get_exe):
        raise VideoRefusal("encode")
    exe = get_exe()
    if not isinstance(exe, str) or exe == "":
        raise VideoRefusal("encode")
    return exe


def _encode_env() -> dict[str, str]:
    env = dict(os.environ)
    env["SOURCE_DATE_EPOCH"] = _EPOCH
    env["TZ"] = "UTC"
    return env


def _bind(
    encoded: bytes,
    copy: ListingCopy,
    request: MerchandisingInput,
    screenshots: Mapping[str, Path],
    *,
    build_version: int,
) -> RenderedWalkthrough:
    version = merchandising_version(copy.draft)
    source = tuple(
        hashlib.sha256(_file_bytes(screenshots.get(role))).hexdigest()
        for role in _screenshot_roles()
    )
    text = _lineage_text(
        product_id=request.spec.product_id,
        spec_version=request.spec.version,
        build_version=build_version,
        source=source,
        merchandising=version,
    )
    bound = encoded + b"\nmm-lineage\n" + text.encode("ascii")
    return RenderedWalkthrough(
        video=bound,
        lineage=WalkthroughLineage(
            product_id=request.spec.product_id,
            spec_version=request.spec.version,
            build_version=build_version,
            source_screenshot_sha256=source,
            merchandising_version=version,
            template_version=VIDEO_TEMPLATE_VERSION,
            output_sha256=hashlib.sha256(bound).hexdigest(),
            width_px=VIDEO_WIDTH,
            height_px=VIDEO_HEIGHT,
            fps=VIDEO_FPS,
            scene_order=VIDEO_BEATS,
            scene_frames=SCENE_FRAMES,
            qa_status="passed",
        ),
    )


def _lineage_text(
    *,
    product_id: UUID,
    spec_version: int,
    build_version: int,
    source: tuple[str, ...],
    merchandising: str,
) -> str:
    return (
        f"product_id={product_id}\n"
        f"spec_version={spec_version}\n"
        f"build_version={build_version}\n"
        f"screenshots={','.join(source)}\n"
        f"merchandising_version={merchandising}\n"
        f"template_version={VIDEO_TEMPLATE_VERSION}\n"
        f"width={VIDEO_WIDTH}\n"
        f"height={VIDEO_HEIGHT}\n"
        f"fps={VIDEO_FPS}\n"
        f"scene_order={','.join(VIDEO_BEATS)}\n"
        f"scene_frames={','.join(str(count) for count in SCENE_FRAMES)}\n"
        f"qa_status=passed\n"
    )
