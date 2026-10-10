"""Fixed listing sentences and the normalization claim checks share.

Buyer-facing text is a template of cited fact values. The generator and the
validator both call ``render``. Comparison strips markup and format characters,
then folds case, compatibility forms, and Latin lookalikes. A token that mixes
scripts, or whose letters are all Latin lookalikes, is rejected before that
fold. A tag that would drop a symbol, or that does not fit in 20 characters,
is refused whole; it is never cut down to a prefix.
"""

from __future__ import annotations

import html
import re
import unicodedata
from dataclasses import dataclass
from re import Pattern
from typing import Final

_HYPHENS: Final[str] = "\u2010\u2011\u2012\u2013\u2014\u2015\u2212\ufe63\uff0d"
_SPACES: Final[str] = "\u00a0\u2007\u202f"
_CONFUSABLES: Final[dict[str, str]] = {
    "\u0430": "a",
    "\u0435": "e",
    "\u043e": "o",
    "\u0440": "p",
    "\u0441": "c",
    "\u0443": "y",
    "\u0445": "x",
    "\u0456": "i",
    "\u0458": "j",
    "\u0455": "s",
    "\u04bb": "h",
    "\u0501": "d",
    "\u051b": "q",
    "\u051d": "w",
    "\u043c": "m",
    "\u043d": "h",
    "\u0432": "b",
    "\u0442": "t",
    "\u043a": "k",
    "\u04cf": "i",
    "\u03b1": "a",
    "\u03bf": "o",
    "\u03c1": "p",
    "\u03b9": "i",
    "\u03b5": "e",
    "\u03bd": "v",
    "\u03c4": "t",
    "\u03ba": "k",
    **{char: "-" for char in _HYPHENS},
    **{char: " " for char in _SPACES},
}
_TITLE_LIMIT: Final = 140
_MARKUP: Final[Pattern[str]] = re.compile(r"<[^>]*>")
_TAG_SEPARATORS: Final[frozenset[str]] = frozenset("&/+-|")


@dataclass(frozen=True, slots=True)
class TextSlot:
    """One cited claim, in the order the template reads it."""

    kind: str
    value: str


def normalize_text(value: str) -> str:
    """Unescape, strip markup and format characters, then fold for comparison."""
    text = _visible(value)
    text = unicodedata.normalize("NFKC", text).casefold()
    folded = "".join(_CONFUSABLES.get(char, char) for char in text)
    return " ".join(folded.split())


def has_concealment(value: str) -> bool:
    """True when format characters or HTML tags hide the letters buyers read."""
    if any(unicodedata.category(char) == "Cf" for char in value):
        return True
    unescaped = html.unescape(value)
    return _MARKUP.search(value) is not None or _MARKUP.search(unescaped) is not None


def script_rejected(value: str) -> bool:
    """True for a mixed-script token or a token made only of Latin lookalikes."""
    text = unicodedata.normalize("NFKC", value)
    return any(_token_rejected(token) for token in text.split())


def normalize_tag(value: str) -> str:
    """Tag identity used for length and duplicates. Empty means unusable."""
    return normalize_text(value)


def mixed_script(value: str) -> bool:
    """True when one token mixes a Latin letter with a non-Latin letter."""
    text = unicodedata.normalize("NFKC", value)
    return any(_token_mixes_scripts(token) for token in text.split())


def etsy_tag(value: str) -> str:
    """Full lowercase tag, or empty when the phrase drops a symbol or exceeds 20."""
    words: list[str] = []
    current: list[str] = []
    for char in value.casefold():
        if char.isspace() or char in _TAG_SEPARATORS:
            if current:
                words.append("".join(current))
                current = []
            continue
        if not char.isalnum():
            return ""
        current.append(char)
    if current:
        words.append("".join(current))
    tag = " ".join(words)
    if tag == "" or len(tag) > 20:
        return ""
    return tag


def render(template_id: str, slots: tuple[TextSlot, ...], *, quantity: int) -> str:
    """Return the only sentence this template may show for these slots."""
    if template_id == "title":
        return _fit(_pair(slots, "identity", "category", " "))
    if template_id == "hook":
        identity, category, problem = _named(slots, ("identity", "category", "buyer_problem"))
        return f"{identity} {category}. {problem}"
    if template_id == "included":
        page, hubs = _head(slots, "page_count", "hub")
        return f"{page} pages. Hubs: {', '.join(hubs)}."
    if template_id == "audience":
        return _audience(slots)
    if template_id == "access_line":
        (access,) = _named(slots, ("access",))
        return f"Duplicate the template. Access link: {access}."
    if template_id == "features":
        return _features(slots)
    if template_id == "variant_devices":
        return _variant_devices(slots)
    if template_id == "support":
        return _support(slots)
    if template_id == "offer":
        price, currency, anchor = _named(slots, ("price", "currency", "anchor"))
        return (
            f"Price {price} {currency}. Anchor {anchor} {currency}. "
            f"Quantity {quantity}. Digital delivery."
        )
    if template_id == "hero":
        return _pair(slots, "identity", "buyer_problem", ". ")
    if template_id == "overview":
        return _pair(slots, "page_count", "identity", " pages in ") + "."
    if template_id == "hub_frame":
        (hub,) = _named(slots, ("hub",))
        return f"Hub: {hub}."
    if template_id == "variant_line":
        names = _all(slots, "variant")
        return f"Variants: {', '.join(names)}."
    if template_id == "device_line":
        names = _all(slots, "device")
        return f"Devices: {', '.join(names)}."
    if template_id == "video_dashboard":
        (encoded,) = _named(slots, ("dashboard",))
        return f"Dashboard output: {encoded}."
    if template_id == "video_notification":
        (encoded,) = _named(slots, ("dashboard",))
        return f"Notification panel: {encoded}."
    if template_id == "video_hubs":
        names = _all(slots, "hub")
        return f"Hubs: {', '.join(names)}."
    if template_id == "tag":
        if len(slots) != 1:
            raise ValueError("tag template cites one claim")
        return etsy_tag(slots[0].value)
    raise ValueError(f"unknown listing template {template_id}")


def _audience(slots: tuple[TextSlot, ...]) -> str:
    identity, shop = _named(slots, ("identity", "shop"))
    return f"Made for {identity}. Shop {shop}."


def _features(slots: tuple[TextSlot, ...]) -> str:
    features = [slot.value for slot in slots if slot.kind == "feature"]
    dashboards = [slot.value for slot in slots if slot.kind == "dashboard"]
    if not features or len(dashboards) != 1 or len(features) + 1 != len(slots):
        raise ValueError("features template cites features and one dashboard")
    return f"{'; '.join(features)}. {_dashboard_sentence(dashboards[0])}"


def _variant_devices(slots: tuple[TextSlot, ...]) -> str:
    variants = [slot.value for slot in slots if slot.kind == "variant"]
    devices = [slot.value for slot in slots if slot.kind == "device"]
    if not variants or not devices or len(variants) + len(devices) != len(slots):
        raise ValueError("variant template cites variants and devices")
    return f"Variants: {', '.join(variants)}. Devices: {', '.join(devices)}."


def _support(slots: tuple[TextSlot, ...]) -> str:
    support, gift = _named(slots, ("support", "free_gift"))
    return (
        f"{_support_clause(support)} {_gift_clause(gift)} Fact support {support}. Fact gift {gift}."
    )


def _dashboard_sentence(encoded: str) -> str:
    if encoded == "absent":
        return "Notification dashboard is not in this build."
    if encoded == "" or encoded.startswith("|") or encoded.endswith("|") or "||" in encoded:
        raise ValueError("dashboard fact is not a list of outputs")
    outputs = ", ".join(encoded.split("|"))
    return f"Notification dashboard: {outputs}."


def _support_clause(encoded: str) -> str:
    if encoded == "not_offered":
        return "Support is not offered."
    channel = _offered(encoded, "support")
    if "|" in channel:
        raise ValueError("support channel is one value")
    return f"Support channel: {channel}."


def _gift_clause(encoded: str) -> str:
    if encoded == "not_offered":
        return "No free gift is configured."
    rest = _offered(encoded, "free gift")
    parts = rest.split("|")
    if len(parts) == 1:
        return f"Free gift: {parts[0]}."
    if len(parts) == 2:
        return f"Free gift: {parts[0]}. Free community: {parts[1]}."
    raise ValueError("free gift fact is a name and an optional community")


def _offered(encoded: str, label: str) -> str:
    prefix = "offered|"
    if not encoded.startswith(prefix) or encoded == prefix:
        raise ValueError(f"{label} fact is not an offered value")
    return encoded[len(prefix) :]


def _pair(slots: tuple[TextSlot, ...], left: str, right: str, sep: str) -> str:
    first, second = _named(slots, (left, right))
    return f"{first}{sep}{second}"


def _named(slots: tuple[TextSlot, ...], kinds: tuple[str, ...]) -> tuple[str, ...]:
    if tuple(slot.kind for slot in slots) != kinds:
        raise ValueError("template slots are not in citation order")
    return tuple(slot.value for slot in slots)


def _head(slots: tuple[TextSlot, ...], head: str, tail: str) -> tuple[str, tuple[str, ...]]:
    if len(slots) < 2 or slots[0].kind != head:
        raise ValueError("template is missing its first claim")
    return slots[0].value, _all(slots[1:], tail)


def _all(slots: tuple[TextSlot, ...], kind: str) -> tuple[str, ...]:
    if not slots or any(slot.kind != kind for slot in slots):
        raise ValueError(f"template expected only {kind} claims")
    return tuple(slot.value for slot in slots)


def _visible(value: str) -> str:
    text = html.unescape(value)
    text = _MARKUP.sub(" ", text)
    text = "".join(char for char in text if unicodedata.category(char) != "Cf")
    return text.replace("*", "")


def _fit(title: str) -> str:
    if len(title) <= _TITLE_LIMIT:
        return title
    return title[:_TITLE_LIMIT].rstrip()


def _token_rejected(token: str) -> bool:
    if _token_mixes_scripts(token):
        return True
    letters = [char for char in token if unicodedata.category(char).startswith("L")]
    if not letters or any(_latin_letter(char) for char in letters):
        return False
    return all(char.casefold() in _CONFUSABLES for char in letters)


def _token_mixes_scripts(token: str) -> bool:
    latin = False
    other = False
    for char in token:
        if not unicodedata.category(char).startswith("L"):
            continue
        if _latin_letter(char):
            latin = True
        else:
            other = True
    return latin and other


def _latin_letter(char: str) -> bool:
    code = ord(char)
    return (
        0x0041 <= code <= 0x005A
        or 0x0061 <= code <= 0x007A
        or 0x00C0 <= code <= 0x024F
        or 0x1E00 <= code <= 0x1EFF
    )
