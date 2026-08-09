"""Deterministic local listing-image rendering with Pillow."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from money_machine.assets.design_tokens import DEFAULT_TOKENS, DesignTokens


def _fit(value: str, limit: int) -> str:
    words = value.split()
    while words and len(" ".join(words)) > limit:
        words.pop()
    return " ".join(words)


def render_listing_png(
    role: str,
    *,
    index: int,
    title: str = "Listing preview",
    detail: str = "Digital product preview",
    tokens: DesignTokens = DEFAULT_TOKENS,
) -> bytes:
    """Render one product-specific, metadata-free 2000px PNG."""

    image = Image.new("RGB", tokens.canvas_size, tokens.background)
    draw = ImageDraw.Draw(image)
    width, height = tokens.canvas_size
    accent = tokens.accent if index % 2 else tokens.secondary
    draw.rounded_rectangle((120, 120, width - 120, height - 120), 48, fill=tokens.card)
    draw.rounded_rectangle((120, 120, width - 120, 430), 48, fill=accent)
    heading_font = ImageFont.load_default(size=82)
    title_font = ImageFont.load_default(size=58)
    body_font = ImageFont.load_default(size=42)
    draw.text((190, 220), role.replace("-", " ").title(), fill="#FFFFFF", font=heading_font)
    draw.multiline_text(
        (190, 650),
        _fit(title, 58),
        fill=tokens.foreground,
        font=title_font,
        spacing=24,
    )
    draw.multiline_text(
        (190, 1080),
        _fit(detail, 84),
        fill=tokens.foreground,
        font=body_font,
        spacing=18,
    )
    buffer = BytesIO()
    image.save(buffer, format="PNG", optimize=False, compress_level=9)
    return buffer.getvalue()


def png_dimensions(data: bytes) -> tuple[int, int]:
    """Return dimensions after Pillow fully verifies the image."""

    with Image.open(BytesIO(data)) as image:
        image.verify()
    with Image.open(BytesIO(data)) as image:
        return image.size


def write_deterministic_png(
    path: Path,
    role: str,
    *,
    index: int,
    title: str = "Listing preview",
    detail: str = "Digital product preview",
) -> bytes:
    data = render_listing_png(role, index=index, title=title, detail=detail)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return data
