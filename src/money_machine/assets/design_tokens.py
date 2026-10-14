"""Reusable listing and PDF tokens, their checks, and one CSS emitter.

Wave 2 does not render PDFs. The PDF page tokens are part of the system so a
later wave can reuse the same palette, type, and page measures. A11 stays
DESIGNED and is not registered here.
"""

from __future__ import annotations

import base64
from collections.abc import Mapping
from pathlib import Path
from typing import Annotated

from pydantic import Field, StringConstraints

from money_machine.domain.models._base import ContractModel, NonEmptyStr

MIN_CONTRAST = 4.5
FONT_FAMILY = "MM Listing"
FONT_FAMILY_PATTERN = r"^[A-Za-z0-9 ]{1,64}$"
REQUIRED_TOKEN_KEYS = (
    "palette",
    "typography",
    "spacing",
    "cards",
    "device_frames",
    "icons",
    "hero_layout",
    "hub_slide",
    "colour_options",
    "how_it_works",
    "device_compatibility",
    "pdf_pages",
)

HexColor = Annotated[str, StringConstraints(strict=True, pattern=r"^#[0-9A-F]{6}$")]
FontFamily = Annotated[str, StringConstraints(strict=True, pattern=FONT_FAMILY_PATTERN)]
PositivePx = Annotated[int, Field(ge=1, le=2000)]
RadiusPx = Annotated[int, Field(ge=0, le=400)]
LineHeight = Annotated[str, StringConstraints(strict=True, pattern=r"^[1-2]\.[0-9]{2}$")]


class TokenValidationError(ValueError):
    """A token set is missing a required section or fails contrast."""


class Palette(ContractModel):
    """Buyer-facing colours. Text pairs are checked at contrast 4.5."""

    background: HexColor
    surface: HexColor
    text: HexColor
    muted: HexColor
    accent: HexColor
    accent_text: HexColor
    border: HexColor


class Typography(ContractModel):
    """Local font file and the type scale. The family name is the CSS name.

    ``font_family`` is letters, digits, and spaces only. ``load_tokens`` applies
    that pattern, so a family cannot close the stylesheet or set ``content``.
    """

    font_family: FontFamily
    font_file: NonEmptyStr
    hero_px: PositivePx
    body_px: PositivePx
    caption_px: PositivePx
    line_height: LineHeight


class Spacing(ContractModel):
    """Page, card, and gap measures in CSS pixels."""

    unit_px: PositivePx
    page_px: PositivePx
    card_px: PositivePx
    gap_px: PositivePx


class Cards(ContractModel):
    """Shared card chrome."""

    radius_px: RadiusPx
    border_px: PositivePx
    padding_px: PositivePx


class DeviceFrames(ContractModel):
    """Bezel and screen radii for phone and tablet frames."""

    bezel_px: PositivePx
    radius_px: RadiusPx
    screen_radius_px: RadiusPx


class Icons(ContractModel):
    """Stroke icon size. Icons carry no buyer-facing words."""

    size_px: PositivePx
    stroke_px: PositivePx


class HeroLayout(ContractModel):
    """Hero text block and the device frame under it."""

    text_block_px: PositivePx
    frame_px: PositivePx


class HubSlide(ContractModel):
    """Caption bar on a hub still."""

    caption_bar_px: PositivePx
    radius_px: RadiusPx


class ColourOptions(ContractModel):
    """Swatch size for the colour-options frame. Swatches are unlabelled."""

    swatch_px: PositivePx
    gap_px: PositivePx
    radius_px: RadiusPx


class HowItWorks(ContractModel):
    """Step mark and connector for the how-it-works frame. No step numbers."""

    step_px: PositivePx
    connector_px: PositivePx


class DeviceCompatibility(ContractModel):
    """Phone and tablet frame sizes on the devices image."""

    phone_px: PositivePx
    tablet_px: PositivePx
    height_px: PositivePx


class PdfPages(ContractModel):
    """Page box for a later PDF wave. This wave only emits the class."""

    width_px: PositivePx
    height_px: PositivePx
    margin_px: PositivePx


class DesignTokens(ContractModel):
    """One token set. Sections stay optional so a missing key can be refused.

    Construction alone is not validation. ``load_tokens`` is.
    """

    palette: Palette | None = None
    typography: Typography | None = None
    spacing: Spacing | None = None
    cards: Cards | None = None
    device_frames: DeviceFrames | None = None
    icons: Icons | None = None
    hero_layout: HeroLayout | None = None
    hub_slide: HubSlide | None = None
    colour_options: ColourOptions | None = None
    how_it_works: HowItWorks | None = None
    device_compatibility: DeviceCompatibility | None = None
    pdf_pages: PdfPages | None = None


def bundled_font_path() -> Path:
    """The vendored DejaVu Sans file shipped with this package."""
    return Path(__file__).resolve().parent / "fonts" / "DejaVuSans.ttf"


def listing_token_payload() -> dict[str, object]:
    """The listing palette and measures this wave renders with."""
    return {
        "palette": {
            "background": "#F6F3EE",
            "surface": "#FFFFFF",
            "text": "#1C1917",
            "muted": "#44403C",
            "accent": "#1F3D32",
            "accent_text": "#F6F3EE",
            "border": "#D6D3D1",
        },
        "typography": {
            "font_family": FONT_FAMILY,
            "font_file": str(bundled_font_path()),
            "hero_px": 40,
            "body_px": 26,
            "caption_px": 18,
            "line_height": "1.35",
        },
        "spacing": {"unit_px": 8, "page_px": 40, "card_px": 20, "gap_px": 16},
        "cards": {"radius_px": 20, "border_px": 2, "padding_px": 20},
        "device_frames": {"bezel_px": 12, "radius_px": 28, "screen_radius_px": 12},
        "icons": {"size_px": 36, "stroke_px": 2},
        "hero_layout": {"text_block_px": 140, "frame_px": 460},
        "hub_slide": {"caption_bar_px": 160, "radius_px": 0},
        "colour_options": {"swatch_px": 64, "gap_px": 16, "radius_px": 32},
        "how_it_works": {"step_px": 56, "connector_px": 4},
        "device_compatibility": {"phone_px": 200, "tablet_px": 340, "height_px": 420},
        "pdf_pages": {"width_px": 800, "height_px": 1100, "margin_px": 48},
    }


def load_tokens(payload: Mapping[str, object]) -> DesignTokens:
    """Refuse a missing section, a font family outside the pattern, or low contrast.

    The family pattern is applied by ``model_validate`` on this path. A value
    with ``;``, ``}``, ``<``, ``\\``, or a newline never becomes a token set.
    """
    if refuse_missing_token_keys(payload) is not None:
        raise TokenValidationError("missing_token")
    tokens = DesignTokens.model_validate(dict(payload))
    if refuse_low_contrast(tokens) is not None:
        raise TokenValidationError("low_contrast")
    return tokens


def refuse_missing_token_keys(payload: Mapping[str, object]) -> str | None:
    """Return ``missing_token`` when a section or the font file is absent."""
    for key in REQUIRED_TOKEN_KEYS:
        value = payload.get(key)
        if not isinstance(value, Mapping) or not value:
            return "missing_token"
    typography = payload.get("typography")
    if not isinstance(typography, Mapping):
        return "missing_token"
    font_file = typography.get("font_file")
    if not isinstance(font_file, str) or not Path(font_file).is_file():
        return "missing_token"
    return None


def refuse_low_contrast(tokens: DesignTokens) -> str | None:
    """Return ``low_contrast`` when a text pair is below ``MIN_CONTRAST``.

    A missing palette is the other rule's job, so this check stays quiet then.
    """
    palette = tokens.palette
    if palette is None:
        return None
    pairs = (
        (palette.text, palette.background),
        (palette.text, palette.surface),
        (palette.muted, palette.background),
        (palette.muted, palette.surface),
        (palette.accent_text, palette.accent),
    )
    for foreground, background in pairs:
        if contrast_ratio(foreground, background) < MIN_CONTRAST:
            return "low_contrast"
    return None


def contrast_ratio(foreground: str, background: str) -> float:
    """WCAG relative-luminance contrast of two ``#RRGGBB`` colours."""
    lighter = max(_luminance(foreground), _luminance(background))
    darker = min(_luminance(foreground), _luminance(background))
    return (lighter + 0.05) / (darker + 0.05)


def emit_css(tokens: DesignTokens) -> str:
    """Emit one stylesheet. Caller has already run ``load_tokens``."""
    palette = tokens.palette
    typography = tokens.typography
    spacing = tokens.spacing
    cards = tokens.cards
    frames = tokens.device_frames
    icons = tokens.icons
    hero = tokens.hero_layout
    hub = tokens.hub_slide
    colour = tokens.colour_options
    steps = tokens.how_it_works
    devices = tokens.device_compatibility
    pdf = tokens.pdf_pages
    if (
        palette is None
        or typography is None
        or spacing is None
        or cards is None
        or frames is None
        or icons is None
        or hero is None
        or hub is None
        or colour is None
        or steps is None
        or devices is None
        or pdf is None
    ):
        raise TokenValidationError("missing_token")
    font = base64.b64encode(Path(typography.font_file).read_bytes()).decode("ascii")
    family = typography.font_family.replace('"', "")
    lines = [
        "@font-face {",
        f'  font-family: "{family}";',
        f'  src: url("data:font/ttf;base64,{font}") format("truetype");',
        "  font-weight: 400;",
        "  font-style: normal;",
        "  font-display: block;",
        "}",
        ":root {",
        f"  --mm-background: {palette.background};",
        f"  --mm-surface: {palette.surface};",
        f"  --mm-text: {palette.text};",
        f"  --mm-muted: {palette.muted};",
        f"  --mm-accent: {palette.accent};",
        f"  --mm-accent-text: {palette.accent_text};",
        f"  --mm-border: {palette.border};",
        f'  --mm-font: "{family}";',
        f"  --mm-hero-size: {typography.hero_px}px;",
        f"  --mm-body-size: {typography.body_px}px;",
        f"  --mm-caption-size: {typography.caption_px}px;",
        f"  --mm-line-height: {typography.line_height};",
        f"  --mm-unit: {spacing.unit_px}px;",
        f"  --mm-page: {spacing.page_px}px;",
        f"  --mm-card-pad: {spacing.card_px}px;",
        f"  --mm-gap: {spacing.gap_px}px;",
        f"  --mm-card-radius: {cards.radius_px}px;",
        f"  --mm-card-border: {cards.border_px}px;",
        f"  --mm-card-padding: {cards.padding_px}px;",
        f"  --mm-bezel: {frames.bezel_px}px;",
        f"  --mm-bezel-radius: {frames.radius_px}px;",
        f"  --mm-screen-radius: {frames.screen_radius_px}px;",
        f"  --mm-icon-size: {icons.size_px}px;",
        f"  --mm-icon-stroke: {icons.stroke_px}px;",
        f"  --mm-hero-text: {hero.text_block_px}px;",
        f"  --mm-hero-frame: {hero.frame_px}px;",
        f"  --mm-hub-caption: {hub.caption_bar_px}px;",
        f"  --mm-hub-radius: {hub.radius_px}px;",
        f"  --mm-swatch-size: {colour.swatch_px}px;",
        f"  --mm-swatch-gap: {colour.gap_px}px;",
        f"  --mm-swatch-radius: {colour.radius_px}px;",
        f"  --mm-step: {steps.step_px}px;",
        f"  --mm-connector: {steps.connector_px}px;",
        f"  --mm-phone: {devices.phone_px}px;",
        f"  --mm-tablet: {devices.tablet_px}px;",
        f"  --mm-device-height: {devices.height_px}px;",
        f"  --mm-pdf-width: {pdf.width_px}px;",
        f"  --mm-pdf-height: {pdf.height_px}px;",
        f"  --mm-pdf-margin: {pdf.margin_px}px;",
        "}",
        "body {",
        "  margin: 0;",
        "  font-family: var(--mm-font), sans-serif;",
        "  font-kerning: none;",
        "  background: var(--mm-background);",
        "  color: var(--mm-text);",
        "}",
        ".mm-claim {",
        "  margin: 0;",
        "  color: var(--mm-text);",
        "  font-size: var(--mm-body-size);",
        "  line-height: var(--mm-line-height);",
        "}",
        ".mm-card {",
        "  background: var(--mm-surface);",
        "  border: var(--mm-card-border) solid var(--mm-border);",
        "  border-radius: var(--mm-card-radius);",
        "  padding: var(--mm-card-padding);",
        "  box-sizing: border-box;",
        "  overflow: hidden;",
        "}",
        ".mm-device-frame {",
        "  background: var(--mm-text);",
        "  border-radius: var(--mm-bezel-radius);",
        "  padding: var(--mm-bezel);",
        "  box-sizing: border-box;",
        "  overflow: hidden;",
        "}",
        ".mm-device-frame img {",
        "  width: 100%;",
        "  height: 100%;",
        "  object-fit: cover;",
        "  border-radius: var(--mm-screen-radius);",
        "  display: block;",
        "}",
        ".mm-icon {",
        "  width: var(--mm-icon-size);",
        "  height: var(--mm-icon-size);",
        "  stroke: var(--mm-accent);",
        "  fill: none;",
        "  stroke-width: var(--mm-icon-stroke);",
        "}",
        ".mm-hero {",
        "  display: flex;",
        "  flex-direction: column;",
        "  gap: var(--mm-gap);",
        "  padding: var(--mm-page);",
        "  box-sizing: border-box;",
        "}",
        ".mm-hero .mm-claim { font-size: var(--mm-hero-size); min-height: var(--mm-hero-text); }",
        ".mm-hero .mm-device-frame { height: var(--mm-hero-frame); }",
        ".mm-overview {",
        "  display: flex;",
        "  gap: var(--mm-gap);",
        "  align-items: center;",
        "  padding: var(--mm-page);",
        "  box-sizing: border-box;",
        "}",
        ".mm-overview .mm-card { flex: 1; height: 70%; }",
        ".mm-overview .mm-card img { width: 100%; height: 100%; object-fit: cover; }",
        ".mm-hub-slide { display: flex; flex-direction: column; }",
        ".mm-hub-slide img {",
        "  width: 100%;",
        "  height: calc(100% - var(--mm-hub-caption));",
        "  object-fit: cover;",
        "  border-radius: var(--mm-hub-radius);",
        "}",
        ".mm-hub-slide .mm-claim {",
        "  height: var(--mm-hub-caption);",
        "  padding: var(--mm-card-padding);",
        "  box-sizing: border-box;",
        "  background: var(--mm-surface);",
        "  font-size: var(--mm-caption-size);",
        "}",
        ".mm-colour-options {",
        "  display: flex;",
        "  flex-direction: column;",
        "  gap: var(--mm-gap);",
        "  padding: var(--mm-page);",
        "  box-sizing: border-box;",
        "}",
        ".mm-swatches { display: flex; gap: var(--mm-swatch-gap); }",
        ".mm-swatch {",
        "  width: var(--mm-swatch-size);",
        "  height: var(--mm-swatch-size);",
        "  border-radius: var(--mm-swatch-radius);",
        "  background: var(--mm-accent);",
        "  display: block;",
        "}",
        ".mm-swatch:nth-child(2) { background: var(--mm-text); }",
        ".mm-swatch:nth-child(3) { background: var(--mm-muted); }",
        ".mm-swatch:nth-child(4) { background: var(--mm-border); }",
        ".mm-colour-options img { width: 100%; height: 360px; object-fit: cover; }",
        ".mm-how-it-works {",
        "  display: flex;",
        "  flex-direction: column;",
        "  gap: var(--mm-gap);",
        "  padding: var(--mm-page);",
        "  box-sizing: border-box;",
        "}",
        ".mm-steps {",
        "  width: 100%;",
        "  height: var(--mm-step);",
        "  stroke: var(--mm-accent);",
        "  fill: var(--mm-accent);",
        "  stroke-width: var(--mm-connector);",
        "}",
        ".mm-how-it-works .mm-device-frame { height: 420px; }",
        ".mm-device-compatibility {",
        "  display: flex;",
        "  gap: var(--mm-gap);",
        "  align-items: flex-end;",
        "  padding: var(--mm-page);",
        "  box-sizing: border-box;",
        "}",
        ".mm-phone { width: var(--mm-phone); height: var(--mm-device-height); }",
        ".mm-tablet { width: var(--mm-tablet); height: calc(var(--mm-device-height) * 0.82); }",
        ".mm-device-compatibility .mm-claim {",
        "  flex-basis: 100%;",
        "  font-size: var(--mm-caption-size);",
        "}",
        ".mm-pdf-page {",
        "  width: var(--mm-pdf-width);",
        "  height: var(--mm-pdf-height);",
        "  padding: var(--mm-pdf-margin);",
        "  background: var(--mm-surface);",
        "  box-sizing: border-box;",
        "}",
        "* { animation: none !important; transition: none !important; }",
    ]
    return "\n".join(lines) + "\n"


def _luminance(color: str) -> float:
    red, green, blue = _rgb(color)
    return 0.2126 * _linear(red) + 0.7152 * _linear(green) + 0.0722 * _linear(blue)


def _rgb(color: str) -> tuple[int, int, int]:
    return (int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16))


def _linear(channel: int) -> float:
    value = channel / 255
    if value <= 0.04045:
        return value / 12.92
    return ((value + 0.055) / 1.055) ** 2.4
