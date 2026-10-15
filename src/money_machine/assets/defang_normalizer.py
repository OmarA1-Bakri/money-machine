"""One defang normalizer for host, email, and URL detectors.

The order is fixed:

1. NFKC, then fold lookalike letters and dots to ASCII.
2. Find host-like, email-like, and ``hxxp`` candidates.
3. Undo defanging only inside those candidates. A bare ``dot`` or a bare
   ``at`` is undone only when the next token, with spaces removed, is on
   :data:`CURATED_TLDS`. A spaced ``.`` is undone only when that token
   casefolds into ``com``, ``c0m``, ``net``, or ``org``, wherever the
   token sits, including at the end of the text. ``c0m`` is the zero
   spelling of ``com``, and a zero in ``org`` counts. Letter lookalikes
   are already folded. A later word still leaves the spaced form alone.
   Bracket and parenthesis forms also accept the IANA snapshot.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable

from money_machine.assets.defang_tlds import CURATED_TLDS, IANA_TLDS

_LOOKALIKES = str.maketrans(
    {
        "\u0261": "g",
        "\u03bf": "o",
        "\u039f": "o",
        "\u0430": "a",
        "\u0410": "a",
        "\u0435": "e",
        "\u0415": "e",
        "\u0456": "i",
        "\u0406": "i",
        "\u0455": "s",
        "\u0405": "s",
        "\u043e": "o",
        "\u041e": "o",
        "\u0440": "p",
        "\u0420": "p",
        "\u0441": "c",
        "\u0421": "c",
        "\u0443": "y",
        "\u0423": "y",
        "\u0445": "x",
        "\u0425": "x",
        "\u0458": "j",
        "\u0408": "j",
        "\u04bb": "h",
        "\u04ba": "h",
        "\u0501": "d",
        "\u0500": "d",
        "\u051b": "q",
        "\u051a": "q",
        "\u051d": "w",
        "\u051c": "w",
        "\u3002": ".",
        "\uff61": ".",
    }
)
_ZERO_TO_O = str.maketrans({"0": "o"})
_LABEL = r"[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*"
_SPACED_TLD = r"[A-Za-z0-9](?:[ \t]+(?![A-Za-z0-9]{2})[A-Za-z0-9])+"
_TLD = rf"(?:{_SPACED_TLD}|{_LABEL})"
_BRACKET_DOT = (
    r"[ \t]*(?:"
    r"\[[ \t]*(?:\.|dot)[ \t]*\]"
    r"|\([ \t]*(?:\.|dot)[ \t]*\)"
    r"|\{[ \t]*(?:\.|dot)[ \t]*\}"
    r")[ \t]*"
)
_BARE_DOT = r"[ \t]+dot[ \t]+"
_SPACED_DOT = r"(?:[ \t]+\.[ \t]*|[ \t]*\.[ \t]+)"
_ANY_DOT = rf"(?:{_BRACKET_DOT}|{_BARE_DOT}|{_SPACED_DOT}|\.)"
_AT = (
    r"(?:"
    r"[ \t]*\[[ \t]*at[ \t]*\][ \t]*"
    r"|[ \t]*\([ \t]*at[ \t]*\)[ \t]*"
    r"|[ \t]*\{[ \t]*at[ \t]*\}[ \t]*"
    r"|[ \t]+at[ \t]+"
    r"|@"
    r")"
)
_URL_CANDIDATE = re.compile(r"(?<![A-Za-z0-9])hxxps?://\S+", re.IGNORECASE)
_EMAIL_CANDIDATE = re.compile(
    rf"(?<![A-Za-z0-9._%+-])[A-Za-z0-9._%+-]+{_AT}{_LABEL}(?:{_ANY_DOT}{_TLD})+",
    re.IGNORECASE,
)
_HOST_CANDIDATE = re.compile(
    rf"(?<![A-Za-z0-9]){_LABEL}(?:{_BRACKET_DOT}|{_BARE_DOT}|{_SPACED_DOT}){_TLD}",
    re.IGNORECASE,
)
_BRACKET_DOT_RE = re.compile(_BRACKET_DOT, re.IGNORECASE)
_BARE_DOT_RE = re.compile(_BARE_DOT, re.IGNORECASE)
_SPACED_DOT_RE = re.compile(_SPACED_DOT)
_BRACKET_AT_RE = re.compile(
    r"[ \t]*(?:\[[ \t]*at[ \t]*\]|\([ \t]*at[ \t]*\)|\{[ \t]*at[ \t]*\})[ \t]*",
    re.IGNORECASE,
)
_BARE_AT_RE = re.compile(r"[ \t]+at[ \t]+", re.IGNORECASE)
_HOST_TAIL = re.compile(
    r"[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*(?:\.[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*)+",
    re.IGNORECASE,
)
_EXACT_URL = re.compile(r"https?://", re.IGNORECASE)
_EXACT_EMAIL = re.compile(
    r"(?<![A-Za-z0-9._%+-])[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z0-9]{2,}(?![A-Za-z0-9])"
)
_EXACT_HOST = re.compile(
    r"(?<![A-Za-z0-9])"
    r"(?:[A-Za-z0-9]|[A-Za-z0-9][A-Za-z0-9-]*[A-Za-z0-9])"
    r"\.[A-Za-z0-9]{2,}(?![A-Za-z0-9])",
    re.IGNORECASE,
)
_HXXP = re.compile(r"hxxp(s?://)", re.IGNORECASE)
_SPACED_DOT_TLDS = frozenset({"com", "c0m", "net", "org"})
_SPACED_ZERO_TARGETS = frozenset({"org"})


def fold_confusables(text: str) -> str:
    """NFKC, then map lookalike letters and dots onto ASCII."""
    return unicodedata.normalize("NFKC", text).translate(_LOOKALIKES)


def candidate_spans(text: str) -> tuple[tuple[int, int], ...]:
    """Return merged spans that contain a defanged separator between tokens."""
    found: list[tuple[int, int]] = []
    for pattern in (_URL_CANDIDATE, _EMAIL_CANDIDATE, _HOST_CANDIDATE):
        found.extend((match.start(), match.end()) for match in pattern.finditer(text))
    return _merge(found)


def undo_defanging(text: str, spans: tuple[tuple[int, int], ...]) -> str:
    """Undo defanging inside ``spans`` and leave every other character alone."""
    if not spans:
        return text
    parts: list[str] = []
    cursor = 0
    for start, end in spans:
        parts.append(text[cursor:start])
        parts.append(_undo_span(text, start, end))
        cursor = end
    parts.append(text[cursor:])
    return "".join(parts)


def normalize_defanged(text: str) -> str:
    """Fold, find candidates, then undo defanging only inside those candidates."""
    folded = fold_confusables(text)
    spans = candidate_spans(folded)
    return undo_defanging(folded, spans)


def url_matches(text: str) -> bool:
    """Return whether a normalized candidate is an exact ``http`` URL."""
    return _EXACT_URL.search(normalize_defanged(text)) is not None


def email_matches(text: str) -> bool:
    """Return whether a normalized candidate is an exact email address."""
    return _EXACT_EMAIL.search(normalize_defanged(text)) is not None


def host_matches(text: str) -> bool:
    """Return whether a normalized candidate is an exact dotted host."""
    return _EXACT_HOST.search(normalize_defanged(text)) is not None


def bracket_host_matches(text: str) -> bool:
    """Return whether a bracket, parenthesis, or brace defang restores a host."""
    if _BRACKET_DOT_RE.search(fold_confusables(text)) is None:
        return False
    return host_matches(text)


def lookalike_host_matches(text: str) -> bool:
    """Return whether a lookalike fold is what makes a host exact."""
    if fold_confusables(text) == text or _EXACT_HOST.search(text) is not None:
        return False
    return host_matches(text)


def _undo_span(text: str, start: int, end: int) -> str:
    chunk = text[start:end]
    tail = text[end:]
    restored = _HXXP.sub(r"http\1", chunk)
    restored = _replace_dots(restored, _BRACKET_DOT_RE, _bracket_tld, boundary=False, tail=tail)
    restored = _replace_dots(restored, _BARE_DOT_RE, _curated_tld, boundary=False, tail=tail)
    restored = _replace_dots(restored, _SPACED_DOT_RE, _spaced_dot_tld, boundary=True, tail=tail)
    restored = _replace_ats(restored, _BRACKET_AT_RE, bracket=True)
    return _replace_ats(restored, _BARE_AT_RE, bracket=False)


def _replace_dots(
    chunk: str,
    pattern: re.Pattern[str],
    accept: Callable[[str], bool],
    *,
    boundary: bool,
    tail: str,
) -> str:
    parts: list[str] = []
    cursor = 0
    for match in pattern.finditer(chunk):
        if match.start() < cursor:
            continue
        parsed = _read_tld(chunk, match.end())
        if parsed is None:
            continue
        token, token_end, spaced = parsed
        if not accept(token):
            continue
        if boundary and not spaced and _word_follows(chunk, token_end, tail):
            continue
        parts.append(chunk[cursor : match.start()])
        parts.append(".")
        parts.append(token)
        cursor = token_end
    parts.append(chunk[cursor:])
    return "".join(parts)


def _replace_ats(chunk: str, pattern: re.Pattern[str], *, bracket: bool) -> str:
    parts: list[str] = []
    cursor = 0
    for match in pattern.finditer(chunk):
        if match.start() < cursor:
            continue
        host = _HOST_TAIL.match(chunk, match.end())
        if host is None:
            continue
        tld = host.group(0).rsplit(".", 1)[1]
        allowed = _bracket_tld(tld) if bracket else _curated_tld(tld)
        if not allowed:
            continue
        parts.append(chunk[cursor : match.start()])
        parts.append("@")
        cursor = match.end()
    parts.append(chunk[cursor:])
    return "".join(parts)


def _read_tld(text: str, start: int) -> tuple[str, int, bool] | None:
    if start >= len(text) or not text[start].isalnum():
        return None
    end = start + 1
    while end < len(text) and (text[end].isalnum() or text[end] == "-"):
        end += 1
    if end == start + 1:
        letters = [text[start]]
        probe = end
        while len(letters) < 12 and probe < len(text) and text[probe] == " ":
            nxt = probe + 1
            while nxt < len(text) and text[nxt] == " ":
                nxt += 1
            if nxt >= len(text) or not text[nxt].isalnum():
                break
            if nxt + 1 < len(text) and (text[nxt + 1].isalnum() or text[nxt + 1] == "-"):
                break
            letters.append(text[nxt])
            probe = nxt + 1
        if len(letters) >= 2:
            return "".join(letters), probe, True
    return text[start:end], end, False


def _word_follows(chunk: str, index: int, tail: str) -> bool:
    if index < len(chunk):
        return _followed_by_word(chunk, index)
    return _followed_by_word(tail, 0)


def _followed_by_word(text: str, index: int) -> bool:
    while index < len(text) and text[index] in " \t":
        index += 1
    return index < len(text) and text[index].isalnum()


def _spaced_dot_tld(token: str) -> bool:
    """Accept com, c0m, net, or org, in any case, plus a zero lookalike of org."""
    folded = token.casefold()
    if folded in _SPACED_DOT_TLDS:
        return True
    mapped = folded.translate(_ZERO_TO_O)
    return mapped != folded and mapped in _SPACED_ZERO_TARGETS


def _curated_tld(token: str) -> bool:
    folded = token.casefold()
    return folded in CURATED_TLDS or folded.translate(_ZERO_TO_O) in CURATED_TLDS


def _bracket_tld(token: str) -> bool:
    return token.casefold() in IANA_TLDS or _curated_tld(token)


def _merge(spans: list[tuple[int, int]]) -> tuple[tuple[int, int], ...]:
    if not spans:
        return ()
    ordered = sorted(spans)
    merged: list[tuple[int, int]] = [ordered[0]]
    for start, end in ordered[1:]:
        prev_start, prev_end = merged[-1]
        if start <= prev_end:
            merged[-1] = (prev_start, max(prev_end, end))
        else:
            merged.append((start, end))
    return tuple(merged)
