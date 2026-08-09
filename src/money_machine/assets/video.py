"""Explicit first-slice video policy."""

from typing import Literal

VideoStatus = Literal["NOT_GENERATED"]


def video_status() -> VideoStatus:
    """Video is not commissioned for the first-product vertical slice."""

    return "NOT_GENERATED"
