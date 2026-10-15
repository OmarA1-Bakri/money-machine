"""Gift-link refusal. Painted strings are not rewritten.

The raw allowlist runs on gift fields before any fold. Folded checks stay
scheme, ``www.``, host, IPv4, percent, and ``_PAID``. A dotted address may
follow a dot. ``/OpenAction``, ``/AA``, and outline scanning are intentionally
absent.
"""

from __future__ import annotations

import re
import unicodedata

from money_machine.assets.pdf_objects import document_strings, link_annotations

_PAID = re.compile(
    r"checkout|stripe\.com|paypal\.com|paypal\.me|gumroad\.com|"
    r"(?:^|[/?&#.])(?:cart|pay|buy|order|purchase)(?:[/?&#.]|$)",
    re.IGNORECASE,
)
_SCHEME = re.compile(r"://|:/")
_WWW = re.compile(r"www\.", re.IGNORECASE)
_HOST = re.compile(
    r"(?<![A-Za-z0-9])"
    r"(?:[A-Za-z0-9]|[A-Za-z0-9][A-Za-z0-9-]*[A-Za-z0-9])"
    r"\.[A-Za-z]{2,}(?![A-Za-z0-9])",
    re.IGNORECASE,
)
_MARKED_OCTET = r"(?:0[xX][0-9A-Fa-f]+|0\d+)"
_IPV4 = re.compile(
    rf"(?<![A-Za-z0-9:/])(?<!\d\.)(?:"
    rf"\d{{1,3}}(?:\.\d{{1,3}}){{2,3}}"
    rf"|{_MARKED_OCTET}(?:\.(?:0[xX][0-9A-Fa-f]+|\d+)){{1,3}}"
    rf"|(?:\d+\.){{1,3}}{_MARKED_OCTET}"
    rf")(?![A-Za-z0-9])"
)
_PERCENT = re.compile(r"%[0-9A-Fa-f]{2}")
_FOLD_DOTS = str.maketrans({"\u3002": ".", "\uff61": ".", "\uff0e": "."})
_ALLOWED = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789 .,'-!?()[]&")
_FIELD_PREFIXES = ("Free gift: ", "Free community: ")


def fold_gift_text(value: str) -> str:
    """Check-only copy: NFKC, dot folds, then strip Unicode format characters."""
    folded = unicodedata.normalize("NFKC", value).translate(_FOLD_DOTS)
    return _strip_format(folded)


def _strip_format(value: str) -> str:
    return "".join(char for char in value if unicodedata.category(char) != "Cf")


def refuse_gift_charset(text: str) -> str | None:
    """Refuse raw gift fields that use characters outside the allowlist.

    Template prefixes and the trailing sentence period are not part of the field.
    Annotation URIs, document info, and XMP are not scanned here.
    """
    for line in text.split("\n"):
        field = line
        for prefix in _FIELD_PREFIXES:
            if field.startswith(prefix):
                field = field[len(prefix) :]
                break
        if field.endswith("."):
            field = field[:-1]
        if any(char not in _ALLOWED for char in field):
            return "paid_checkout"
    return None


def refuse_raw_charset(text: str) -> str | None:
    """Allowlist on the whole string. No prefix strip and no period trim.

    PDF gift fields use :func:`refuse_gift_charset`, which removes
    ``Free gift: `` before the check. A caption that keeps that prefix
    must not.
    """
    if any(char not in _ALLOWED for char in text):
        return "paid_checkout"
    return None


def refuse_paid_checkout(text: str) -> str | None:
    """Return ``paid_checkout`` when folded gift text looks like a URL or address."""
    folded = fold_gift_text(text)
    if _SCHEME.search(folded) is not None:
        return "paid_checkout"
    if _WWW.search(folded) is not None:
        return "paid_checkout"
    if _HOST.search(folded) is not None:
        return "paid_checkout"
    if _IPV4.search(folded) is not None:
        return "paid_checkout"
    if _PERCENT.search(folded) is not None:
        return "paid_checkout"
    if _PAID.search(folded) is not None:
        return "paid_checkout"
    return None


def refuse_gift_link_annotations(pdf: bytes) -> str | None:
    """Return ``paid_checkout`` when the gift PDF has any link annotation."""
    try:
        count, uris = link_annotations(pdf)
    except ValueError:
        return "paid_checkout"
    for uri in uris:
        if refuse_paid_checkout(uri) is not None:
            return "paid_checkout"
    if count:
        return "paid_checkout"
    return None


def refuse_gift_document_info(pdf: bytes) -> str | None:
    """Return ``paid_checkout`` when info strings or XMP contain a link.

    A ``ValueError`` from a deep or broken ``/Info`` chain is the same refusal.
    Callers then raise ``DeliveryPdfRefusal`` instead of the raw parser error.
    """
    try:
        values = document_strings(pdf)
    except ValueError:
        return "paid_checkout"
    for value in values:
        if refuse_paid_checkout(value) is not None:
            return "paid_checkout"
    return None
