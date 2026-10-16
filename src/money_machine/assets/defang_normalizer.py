"""One defang normalizer for host, email, and URL detectors.

The order is fixed:

1. Map U+03F2 to ``c``, then NFKC, then fold the other lookalikes and drop format characters.
2. Find host-like, email-like, and ``hxxp`` candidates.
3. Undo defanging only inside those candidates. A bare ``dot`` or a bare
   ``at`` is undone only when the next token, with spaces removed, is on
   :data:`CURATED_TLDS`. A spaced ``.`` is undone only when that token is
   all lowercase or all uppercase and is ``com``, ``c0m``, ``net``, or
   ``org``. Case is read after NFKC. The lookalike fold keeps case. An
   all-uppercase token is casefolded after that check. A lowercase token
   is compared as itself. A mixed-case token stays prose. ``c0m`` is the
   zero spelling of ``com``. A zero in ``org`` is the same digit map,
   so ``0rg`` is ``org``. A later word still leaves a tight spaced form
   alone. Spaced letters that begin one of those TLDs still undo when
   another word or a stray letter follows. A lowercase ``co``, ``io``,
   or ``shop``, including letters split by spaces, undoes after a spaced
   ``.`` only when the label is one character and another word follows.
   A digit label does not take the digit map, so a step number stays
   prose. A bare ``dot`` maps ``1`` to ``i`` and ``3`` to ``e``. A spaced
   ``.`` does the same, and ``1o`` is ``io``. U+03F2 folds to ``c``
   before NFKC. Bracket labels may contain ``--``. ``hxxp[:]`` is a
   scheme defang. Bracket and parenthesis forms also accept the IANA
   snapshot.
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
        "\u039f": "O",
        "\u0430": "a",
        "\u0410": "A",
        "\u0435": "e",
        "\u0415": "E",
        "\u0456": "i",
        "\u0406": "I",
        "\u0455": "s",
        "\u0405": "S",
        "\u043e": "o",
        "\u041e": "O",
        "\u0440": "p",
        "\u0420": "P",
        "\u0441": "c",
        "\u0421": "C",
        "\u043c": "m",
        "\u041c": "M",
        "\u0443": "y",
        "\u0423": "Y",
        "\u0445": "x",
        "\u0425": "X",
        "\u0458": "j",
        "\u0408": "J",
        "\u04bb": "h",
        "\u04ba": "H",
        "\u0501": "d",
        "\u0500": "D",
        "\u051b": "q",
        "\u051a": "Q",
        "\u051d": "w",
        "\u051c": "W",
        "\u3002": ".",
        "\uff61": ".",
    }
)
_LUNATE_SIGMA = str.maketrans({"\u03f2": "c"})
_CURATED_DIGITS = str.maketrans({"0": "o", "1": "i", "3": "e"})
_LABEL = r"[A-Za-z0-9]+(?:-+[A-Za-z0-9]+)*"
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
    r"|[ \t]*@[ \t]*"
    r")"
)
_URL_CANDIDATE = re.compile(
    r"(?<![A-Za-z0-9])hxxps?(?:\[:\]|:)//\S+",
    re.IGNORECASE,
)
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
_SPACED_AT_SIGN = re.compile(r"[ \t]+@[ \t]*|[ \t]*@[ \t]+")
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
_HXXP = re.compile(r"hxxp(s?)(?:\[:\]|:)(//)", re.IGNORECASE)
_DIGIT_TLD = re.compile(r"dot[ \t]+[A-Za-z]*[13][A-Za-z0-9]*", re.IGNORECASE)
_SPACED_LETTERS = re.compile(
    r"(?:dot|\.)[ \t]+[A-Za-z0-9](?:[ \t]+[A-Za-z0-9])+(?![A-Za-z0-9])",
    re.IGNORECASE,
)
_STRAY_LETTER = re.compile(
    r"(?:dot|\.)[ \t]+(?:[A-Za-z0-9][ \t]+){3}[A-Za-z0-9](?![A-Za-z0-9])",
    re.IGNORECASE,
)
_SPACED_DOT_TLDS = frozenset({"com", "c0m", "net", "org"})
_SPACED_DIGIT_TARGETS = _SPACED_DOT_TLDS | frozenset({"io"})


def fold_confusables(text: str) -> str:
    """NFKC, then map lookalike letters and dots onto ASCII, keeping case.

    U+03F2 is replaced first. NFKC would turn that lunate sigma into final sigma.
    Format characters, including a zero-width space inside a scheme, are removed.
    """
    marked = text.translate(_LUNATE_SIGMA)
    folded = unicodedata.normalize("NFKC", marked).translate(_LOOKALIKES)
    return "".join(char for char in folded if unicodedata.category(char) != "Cf")


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
    if _EXACT_HOST.search(text) is not None:
        return False
    folded = fold_confusables(text)
    if folded == text and _DIGIT_TLD.search(folded) is None:
        return False
    return host_matches(text)


def spaced_letter_host_matches(text: str) -> bool:
    """Single letters after ``dot`` or a dot restore that same host.

    ``x dot com`` has no spaced letters, so this helper does not match it.
    The spaced letters and the host are one candidate. A later ``x dot com``
    does not satisfy a spaced-letter run in another clause.
    """
    folded = fold_confusables(text)
    spans = candidate_spans(folded)
    for match in _SPACED_LETTERS.finditer(folded):
        for start, end in spans:
            if start <= match.start() and match.end() <= end and host_matches(folded[start:end]):
                return True
    return False


def stray_spaced_letter_host_matches(text: str) -> bool:
    """Spaced TLD letters with one trailing letter outside the TLD."""
    folded = fold_confusables(text)
    if _STRAY_LETTER.search(folded) is None:
        return False
    return host_matches(text)


def tight_spaced_host_matches(text: str) -> bool:
    """A spaced dot whose restored TLD is com, c0m, net, or org."""
    folded = fold_confusables(text)
    if _SPACED_DOT_RE.search(folded) is None:
        return False
    return host_matches(text)


def _undo_span(text: str, start: int, end: int) -> str:
    chunk = text[start:end]
    tail = text[end:]
    restored = _HXXP.sub(r"http\1:\2", chunk)
    restored = _replace_dots(restored, _BRACKET_DOT_RE, _bracket_tld, boundary=False, tail=tail)
    restored = _replace_dots(restored, _BARE_DOT_RE, _curated_tld, boundary=False, tail=tail)
    restored = _replace_dots(restored, _SPACED_DOT_RE, _spaced_dot_tld, boundary=True, tail=tail)
    restored = _replace_ats(restored, _BRACKET_AT_RE, bracket=True)
    restored = _replace_ats(restored, _BARE_AT_RE, bracket=False)
    return _SPACED_AT_SIGN.sub("@", restored)


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
        chosen = _chosen_tld(chunk, match.end(), accept, boundary=boundary, tail=tail)
        if chosen is None:
            continue
        token, token_end = chosen
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


def _chosen_tld(
    chunk: str,
    start: int,
    accept: Callable[[str], bool],
    *,
    boundary: bool,
    tail: str,
) -> tuple[str, int] | None:
    parsed = _read_tld(chunk, start)
    if parsed is None:
        return None
    token, token_end, spaced = parsed
    accepted = _longest_accepted(chunk, start, token, token_end, spaced, accept)
    if accepted is None:
        return _outside_curated(
            token,
            token_end,
            boundary=boundary,
            chunk=chunk,
            tail=tail,
            tld_start=start,
        )
    token, token_end, spaced = accepted
    if _relies_on_digit_map(token) and _label_before(chunk, start).isdigit():
        return None
    if boundary and not spaced and _word_follows(chunk, token_end, tail):
        return None
    return token, token_end


def _longest_accepted(
    chunk: str,
    start: int,
    token: str,
    token_end: int,
    spaced: bool,
    accept: Callable[[str], bool],
) -> tuple[str, int, bool] | None:
    if not spaced:
        if accept(token):
            return token, token_end, False
        return None
    best: tuple[str, int, bool] | None = None
    for prefix, end in _spaced_prefixes(chunk, start):
        if len(prefix) >= 2 and accept(prefix):
            best = (prefix, end, True)
    return best


def _outside_curated(
    token: str,
    token_end: int,
    *,
    boundary: bool,
    chunk: str,
    tail: str,
    tld_start: int,
) -> tuple[str, int] | None:
    if not boundary or not _word_follows(chunk, token_end, tail):
        return None
    if not token.islower() or token in _SPACED_DOT_TLDS or token not in CURATED_TLDS:
        return None
    if len(_label_before(chunk, tld_start)) != 1:
        return None
    return token, token_end


def _label_before(text: str, tld_start: int) -> str:
    index = tld_start
    while index > 0 and text[index - 1] in " \t":
        index -= 1
    if index >= 3 and text[index - 3 : index].casefold() == "dot":
        index -= 3
        while index > 0 and text[index - 1] in " \t":
            index -= 1
    elif index > 0 and text[index - 1] == ".":
        index -= 1
        while index > 0 and text[index - 1] in " \t":
            index -= 1
    end = index
    while index > 0 and (text[index - 1].isalnum() or text[index - 1] == "-"):
        index -= 1
    return text[index:end]


def _relies_on_digit_map(token: str) -> bool:
    folded = token.casefold()
    if folded in _SPACED_DOT_TLDS or folded in CURATED_TLDS:
        return False
    mapped = folded.translate(_CURATED_DIGITS)
    return mapped != folded and mapped in _SPACED_DIGIT_TARGETS | CURATED_TLDS


def _spaced_prefixes(text: str, start: int) -> list[tuple[str, int]]:
    if start >= len(text) or not text[start].isalnum():
        return []
    if start + 1 < len(text) and (text[start + 1].isalnum() or text[start + 1] == "-"):
        return []
    letters = [text[start]]
    ends = [start + 1]
    probe = start + 1
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
        ends.append(probe)
    if len(letters) < 2:
        return []
    prefixes: list[tuple[str, int]] = []
    acc = ""
    for letter, end in zip(letters, ends, strict=True):
        acc += letter
        prefixes.append((acc, end))
    return prefixes


def _read_tld(text: str, start: int) -> tuple[str, int, bool] | None:
    if start >= len(text) or not text[start].isalnum():
        return None
    prefixes = _spaced_prefixes(text, start)
    if prefixes:
        token, end = prefixes[-1]
        return token, end, True
    end = start + 1
    while end < len(text) and (text[end].isalnum() or text[end] == "-"):
        end += 1
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
    """Accept an all-lowercase or all-uppercase com, c0m, net, or org.

    The token is already NFKC and lookalike-folded. Case is read here.
    An all-uppercase token is casefolded after that check. A lowercase
    token is compared as itself. A mixed-case token stays prose. A
    lowercase zero inside org is the digit map. A 3 that maps to e is
    ``net``. A 1 that maps to i is ``io``, which a tight ``io`` is not.
    """
    if token.isupper():
        token = token.casefold()
    if not token.islower():
        return False
    if token in _SPACED_DOT_TLDS:
        return True
    digit_mapped = token.translate(_CURATED_DIGITS)
    return digit_mapped != token and digit_mapped in _SPACED_DIGIT_TARGETS


def _curated_tld(token: str) -> bool:
    folded = token.casefold()
    if folded in CURATED_TLDS:
        return True
    mapped = folded.translate(_CURATED_DIGITS)
    return mapped != folded and mapped in CURATED_TLDS


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
