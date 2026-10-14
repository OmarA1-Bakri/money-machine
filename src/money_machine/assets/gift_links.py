"""Folded check for URL-like gift text. Painted strings are not rewritten.

``/OpenAction``, ``/AA``, and outline scanning are intentionally absent.
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
_PERCENT = re.compile(r"%[0-9A-Fa-f]{2}")
_FOLD_DOTS = str.maketrans({"\u3002": ".", "\uff61": ".", "\uff0e": "."})


def fold_gift_text(value: str) -> str:
    """Check-only copy: NFKC, dot folds, then strip Unicode format characters."""
    folded = unicodedata.normalize("NFKC", value).translate(_FOLD_DOTS)
    return "".join(char for char in folded if unicodedata.category(char) != "Cf")


def refuse_paid_checkout(text: str) -> str | None:
    """Return ``paid_checkout`` when folded gift text looks like a URL or domain."""
    folded = fold_gift_text(text)
    if _SCHEME.search(folded) is not None or _WWW.search(folded) is not None:
        return "paid_checkout"
    if _HOST.search(folded) is not None or _PERCENT.search(folded) is not None:
        return "paid_checkout"
    if _PAID.search(folded) is not None:
        return "paid_checkout"
    return None


def refuse_gift_link_annotations(pdf: bytes) -> str | None:
    """Return ``paid_checkout`` when the gift PDF has any link annotation."""
    count, uris = link_annotations(pdf)
    for uri in uris:
        if refuse_paid_checkout(uri) is not None:
            return "paid_checkout"
    if count:
        return "paid_checkout"
    return None


def refuse_gift_document_info(pdf: bytes) -> str | None:
    """Return ``paid_checkout`` when info strings or XMP contain a link."""
    for value in document_strings(pdf):
        if refuse_paid_checkout(value) is not None:
            return "paid_checkout"
    return None
