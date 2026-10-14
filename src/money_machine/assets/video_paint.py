"""Fixture frames for the silent walkthrough. Pixels, not a browser."""

from __future__ import annotations

import struct
import zlib

from money_machine.assets.video_font import blit, wrap_caption

_PASTE_X = 8
_PASTE_Y = 2
_CAPTION_Y = 40
_LINE = 8
_BLANK = 32


def decode_png_rgb(data: bytes) -> tuple[int, int, bytes]:
    """Decode a non-interlaced 8-bit RGB PNG. Anything else is refused."""
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("png")
    pos = 8
    width = 0
    height = 0
    idat = bytearray()
    saw_header = False
    while pos + 8 <= len(data):
        length = int.from_bytes(data[pos : pos + 4], "big")
        kind = data[pos + 4 : pos + 8]
        pos += 8
        end = pos + length
        if end + 4 > len(data):
            raise ValueError("png")
        chunk = data[pos:end]
        pos = end + 4
        if kind == b"IHDR":
            if len(chunk) != 13:
                raise ValueError("png")
            width, height, bit, colour, comp, filt, inter = struct.unpack(">IIBBBBB", chunk)
            if bit != 8 or colour != 2 or comp != 0 or filt != 0 or inter != 0:
                raise ValueError("png")
            if width < 1 or height < 1:
                raise ValueError("png")
            saw_header = True
        elif kind == b"IDAT":
            idat.extend(chunk)
        elif kind == b"IEND":
            break
    if not saw_header or not idat:
        raise ValueError("png")
    raw = zlib.decompress(bytes(idat))
    return width, height, _unfilter(raw, width, height)


def scene_marker(
    scene_index: int,
    local: int,
    frame_count: int,
    shot_count: int,
) -> tuple[int, int, int, int]:
    """``(0,0)`` is the 1-based scene. ``(1,0)`` red is the hub subindex, or 0."""
    hub = local * shot_count // frame_count + 1 if shot_count > 1 else 0
    return scene_index, 0, 0, hub


def compose_frames(
    captions: tuple[str, ...],
    scenes: tuple[tuple[tuple[bytes, int, int], ...], ...],
    background: tuple[int, int, int],
    text: tuple[int, int, int],
    accent: tuple[int, int, int],
    *,
    width: int,
    height: int,
    scene_frames: tuple[int, ...],
    injected: str,
) -> bytes:
    """One RGB buffer. Scene order is the order of ``scenes``."""
    if len(captions) != len(scenes) or len(scenes) != len(scene_frames):
        raise ValueError("scenes")
    frames = bytearray()
    for index, (caption, shots, count) in enumerate(
        zip(captions, scenes, scene_frames, strict=True),
        start=1,
    ):
        for local in range(count):
            frame = bytearray(background * (width * height))
            shot = shots[local * len(shots) // count]
            _paste(frame, shot, width)
            _caption(frame, caption, text, width)
            if injected:
                blit(frame, injected[:26], 2, 72, text, width)
            _bar(frame, accent, width, height)
            red, green, blue, hub = scene_marker(index, local, count, len(shots))
            _paint(frame, 0, 0, (red, green, blue), width)
            _paint(frame, 1, 0, (hub, 0, 0), width)
            frames.extend(frame)
    return bytes(frames)


def _unfilter(raw: bytes, width: int, height: int) -> bytes:
    stride = width * 3
    if len(raw) != height * (stride + 1):
        raise ValueError("png")
    rows: list[bytes] = []
    prev = bytearray(stride)
    pos = 0
    for _ in range(height):
        filter_type = raw[pos]
        pos += 1
        row = bytearray(raw[pos : pos + stride])
        pos += stride
        if filter_type == 1:
            _add_left(row)
        elif filter_type == 2:
            _add_up(row, prev)
        elif filter_type == 3:
            _add_average(row, prev)
        elif filter_type == 4:
            _add_paeth(row, prev)
        elif filter_type != 0:
            raise ValueError("png")
        rows.append(bytes(row))
        prev = row
    return b"".join(rows)


def _add_left(row: bytearray) -> None:
    for index in range(len(row)):
        left = row[index - 3] if index >= 3 else 0
        row[index] = (row[index] + left) & 255


def _add_up(row: bytearray, prev: bytearray) -> None:
    for index in range(len(row)):
        row[index] = (row[index] + prev[index]) & 255


def _add_average(row: bytearray, prev: bytearray) -> None:
    for index in range(len(row)):
        left = row[index - 3] if index >= 3 else 0
        row[index] = (row[index] + ((left + prev[index]) // 2)) & 255


def _add_paeth(row: bytearray, prev: bytearray) -> None:
    for index in range(len(row)):
        left = row[index - 3] if index >= 3 else 0
        up = prev[index]
        upper_left = prev[index - 3] if index >= 3 else 0
        row[index] = (row[index] + _paeth(left, up, upper_left)) & 255


def _paeth(left: int, up: int, upper_left: int) -> int:
    estimate = left + up - upper_left
    left_distance = abs(estimate - left)
    up_distance = abs(estimate - up)
    upper_distance = abs(estimate - upper_left)
    if left_distance <= up_distance and left_distance <= upper_distance:
        return left
    if up_distance <= upper_distance:
        return up
    return upper_left


def _paste(frame: bytearray, shot: tuple[bytes, int, int], width: int) -> None:
    rgb, shot_width, shot_height = shot
    for y in range(shot_height):
        for x in range(shot_width):
            src = (y * shot_width + x) * 3
            _paint(
                frame,
                _PASTE_X + x,
                _PASTE_Y + y,
                (rgb[src], rgb[src + 1], rgb[src + 2]),
                width,
            )


def _caption(frame: bytearray, caption: str, colour: tuple[int, int, int], width: int) -> None:
    for index, line in enumerate(wrap_caption(caption)):
        blit(frame, line, 2, _CAPTION_Y + index * _LINE, colour, width)


def _bar(frame: bytearray, colour: tuple[int, int, int], width: int, height: int) -> None:
    for y in range(height - 4, height):
        for x in range(width):
            _paint(frame, x, y, colour, width)


def _paint(
    frame: bytearray,
    x: int,
    y: int,
    colour: tuple[int, int, int],
    width: int,
) -> None:
    height = len(frame) // (width * 3)
    if x < 0 or y < 0 or x >= width or y >= height:
        return
    start = (y * width + x) * 3
    frame[start] = colour[0]
    frame[start + 1] = colour[1]
    frame[start + 2] = colour[2]


def blank_rgb() -> tuple[bytes, int, int]:
    """A 32x32 stand-in used only after a screenshot guard has already fired."""
    return bytes(_BLANK * _BLANK * 3), _BLANK, _BLANK
