"""FFV1 walkthrough encoder. The locked imageio-ffmpeg wheel, one thread.

The raw frames are rgb24. The stored FFV1 sample format is whatever that
wheel writes; this module does not relabel it. ``+bitexact`` is part of the
pinned linux x86_64 bytes. On this wheel, deleting ``-map_metadata -1`` left
those bytes unchanged.
"""

from __future__ import annotations

import importlib
import os
import re
import subprocess
import tempfile
from pathlib import Path

_DURATION = re.compile(r"Duration:\s*(\d+):(\d\d):(\d\d(?:\.\d+)?)")
_FRAME = re.compile(r"(\d+)x(\d+),\s*(\d+(?:\.\d+)?)\s*fps")


class VideoRefusal(ValueError):
    """The walkthrough was refused before a container was returned."""


def encode_frames(
    frames: bytes,
    *,
    width: int,
    height: int,
    fps: int,
    frame_count: int,
    epoch: str,
) -> bytes:
    """Encode raw rgb24 frames to FFV1 in Matroska. No audio."""
    if len(frames) != width * height * 3 * frame_count:
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
            env=_encode_env(epoch),
        )
        if completed.returncode != 0 or not path.is_file():
            raise VideoRefusal("encode")
        return path.read_bytes()


def probe_container(video: bytes) -> tuple[float, int, int, float]:
    """Duration, width, height, and fps from the container banner."""
    if not video.startswith(b"\x1a\x45\xdf\xa3"):
        raise VideoRefusal("container")
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "walkthrough.mkv"
        path.write_bytes(video)
        completed = subprocess.run(
            [_ffmpeg_exe(), "-hide_banner", "-i", str(path)],
            capture_output=True,
            check=False,
            env=_encode_env("0"),
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


def _encode_env(epoch: str) -> dict[str, str]:
    env = dict(os.environ)
    env["SOURCE_DATE_EPOCH"] = epoch
    env["TZ"] = "UTC"
    return env
