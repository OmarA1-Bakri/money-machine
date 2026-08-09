"""Fixed, dependency-free design tokens for local first-slice rendering."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DesignTokens:
    background: str = "#F7F3EA"
    foreground: str = "#17232B"
    accent: str = "#526E5C"
    secondary: str = "#A95F54"
    card: str = "#FFFFFF"
    spacing: tuple[int, ...] = (8, 16, 24, 32, 48, 64)
    canvas_size: tuple[int, int] = (2000, 2000)
    min_contrast_ratio: float = 4.5


DEFAULT_TOKENS = DesignTokens()


def hex_rgb(value: str) -> tuple[int, int, int]:
    value = value.removeprefix("#")
    if len(value) != 6:
        raise ValueError("colour must be a six-digit hex value")
    return tuple(int(value[index : index + 2], 16) for index in (0, 2, 4))  # type: ignore[return-value]


def _luminance(value: str) -> float:
    channels: list[float] = []
    for channel in hex_rgb(value):
        scaled = channel / 255
        channels.append(scaled / 12.92 if scaled <= 0.04045 else ((scaled + 0.055) / 1.055) ** 2.4)
    return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]


def contrast_ratio(first: str, second: str) -> float:
    """Return the WCAG contrast ratio for two opaque sRGB colours."""

    lighter, darker = sorted((_luminance(first), _luminance(second)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)
