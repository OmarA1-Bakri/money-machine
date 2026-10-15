"""Fixture-value text policy for variant screenshots.

Normalise before any pattern runs. Bidirectional controls are refused before
characters in category Cf are stripped: those controls are themselves Cf, and
stripping them first turns a reversed host into ASCII that does not match.
Markup characters are refused on fixture values only. Escaping is a second
layer and does not replace the refusal.
"""

from __future__ import annotations

import html
import re
import unicodedata

_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_NOTION_HOST = re.compile(r"notion\.(?:so|site)", re.IGNORECASE)
_TOKEN = re.compile(
    r"(?:secret|token|api[_-]?key|bearer|ntn|sk)[_-][A-Za-z0-9]{6,}",
    re.IGNORECASE,
)
_NTN_BARE = re.compile(r"\bntn[A-Za-z0-9]{6,}\b", re.IGNORECASE)
_BEARER_SPACE = re.compile(r"\bbearer\s+[A-Za-z0-9._-]{6,}\b", re.IGNORECASE)
_UUID = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
)
_HEX_ID = re.compile(r"\b[0-9a-fA-F]{32}\b")
_MARKUP = frozenset("<>&\"'")
_BIDI = frozenset(chr(code) for code in (*range(0x202A, 0x202F), *range(0x2066, 0x206A)))
_CYRILLIC_O = str.maketrans({"\u043e": "o", "\u041e": "O"})
_PLACEHOLDER = "{{label}}"


class ScreenshotRefusal(ValueError):
    """The variant screenshot was refused before a PNG was returned."""


def email_rule_matches(text: str) -> bool:
    """Return whether the email rule matches. Host and token rules are separate."""
    return _EMAIL.search(text) is not None


def notion_host_rule_matches(text: str) -> bool:
    """Return whether the Notion host rule matches. Case is not folded first."""
    return _NOTION_HOST.search(text) is not None


def token_rule_matches(text: str) -> bool:
    """Return whether the separator token rule matches."""
    return _TOKEN.search(text) is not None


def escape_fixture(value: str) -> str:
    """Escape a fixture value for both text and attribute slots."""
    return html.escape(value, quote=True)


def fill_template(template: str, label: str) -> str:
    """Substitute the escaped label. The template is the only HTML source."""
    if template.count(_PLACEHOLDER) != 2:
        raise ScreenshotRefusal("template")
    return template.replace(_PLACEHOLDER, escape_fixture(label))


def refuse_sensitive_text(text: str) -> str | None:
    """Return ``sensitive_data`` when text is not fixture or sample data."""
    if _EMAIL.search(text) is not None:
        return "sensitive_data"
    if _NOTION_HOST.search(text) is not None:
        return "sensitive_data"
    if _TOKEN.search(text) is not None:
        return "sensitive_data"
    if _NTN_BARE.search(text) is not None:
        return "sensitive_data"
    if _BEARER_SPACE.search(text) is not None:
        return "sensitive_data"
    if _UUID.search(text) is not None:
        return "sensitive_data"
    if _HEX_ID.search(text) is not None:
        return "sensitive_data"
    return None


def refuse_fixture_value(value: str) -> str | None:
    """Refuse a fixture label before it is substituted into the template."""
    return _prepare(value, markup=True)


def refuse_rendered_text(text: str) -> str | None:
    """Refuse rendered text. Visible markup is not itself sensitive."""
    return _prepare(text, markup=False)


def _prepare(text: str, *, markup: bool) -> str | None:
    folded = unicodedata.normalize("NFKC", text)
    if any(char in _BIDI for char in folded):
        return "sensitive_data"
    if markup and any(char in _MARKUP for char in folded):
        return "fixture_markup"
    stripped = "".join(char for char in folded if unicodedata.category(char) != "Cf")
    return refuse_sensitive_text(stripped.translate(_CYRILLIC_O))
