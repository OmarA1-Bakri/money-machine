"""Validate links injected into an exported delivery PDF.

Extraction is ``link_annotations`` (indirect ``/Annots`` and ``/Kids``,
including compressed object streams). Info and XMP go through
``refuse_gift_document_info``. The raw allowlist runs before any fold.
``refuse_paid_checkout`` is the percent guard. On a full URI it returns at
``://`` before it sees ``%xx``, so the percent guard for a URI is applied to
the path, query, and fragment. The default checker does not open a URL.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass
from urllib.parse import ParseResult, urlparse

from money_machine.assets.gift_links import (
    refuse_gift_document_info,
    refuse_paid_checkout,
    refuse_raw_charset,
)
from money_machine.assets.pdf_objects import document_strings, link_annotations
from money_machine.integrations.notion.publishing import (
    _allowed_secret_host,  # pyright: ignore[reportPrivateUsage]
)

_URL_MARKS = frozenset(":/?#[]@")


class LinkValidationRefusal(ValueError):
    """The PDF did not pass link validation. ``repairs`` names each failed link."""

    def __init__(
        self,
        code: str,
        *,
        records: tuple[LinkRecord, ...] = (),
        repairs: tuple[AssetRepair, ...] = (),
    ) -> None:
        super().__init__(code)
        self.code = code
        self.records = records
        self.repairs = repairs


@dataclass(frozen=True, slots=True)
class AssetRepair:
    """One targeted repair. It names the asset and the link that failed."""

    asset: str
    link: str
    reason: str


@dataclass(frozen=True, slots=True)
class LinkObservation:
    """What the injected checker saw. ``chain`` starts with the exact URI."""

    variant: str
    public: bool
    duplicate_button: bool
    chain: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class LinkRecord:
    """One checked link. The link string is the URI extracted from the PDF."""

    link: str
    variant: str
    resolves: bool
    public: bool
    duplicate_button: bool
    checked_at: str
    pdf_sha256: str
    link_sha256: str


@dataclass(frozen=True, slots=True)
class LinkReport:
    """Passed validation. ``repairs`` is empty."""

    records: tuple[LinkRecord, ...]
    repairs: tuple[AssetRepair, ...]


def default_link_checker(url: str, variant: str) -> LinkObservation:
    """Refuse a live open. Tests inject a fixture checker."""
    del url, variant
    raise LinkValidationRefusal("live_link_check")


def default_clock() -> str:
    """Refuse the system clock. Tests inject a pinned timestamp."""
    raise LinkValidationRefusal("live_clock")


def validate_pdf_links(
    pdf: bytes,
    *,
    asset: str,
    accepted: tuple[tuple[str, str], ...],
    known_variants: frozenset[str],
    checker: Callable[[str, str], LinkObservation] = default_link_checker,
    clock: Callable[[], str] = default_clock,
) -> LinkReport:
    """Check every embedded link. A failure raises and names that link only."""
    info = _info_refusal(pdf, asset)
    if info is not None:
        raise info
    try:
        count, uris = link_annotations(pdf)
    except ValueError as exc:
        raise _repair(asset, "", "malformed") from exc
    if count == 0:
        raise _repair(asset, "", "missing_links")
    if len(uris) != count:
        raise _repair(asset, "", "malformed")
    pdf_sha256 = hashlib.sha256(pdf).hexdigest()
    expected = tuple(uri for _variant, uri in accepted)
    records: list[LinkRecord] = []
    repairs: list[AssetRepair] = []
    for index, uri in enumerate(uris):
        variant = accepted[index][0] if index < len(accepted) else ""
        reason = _refuse_link(uri, variant, known_variants)
        if reason is None and (index >= len(expected) or uri != expected[index]):
            reason = "link_mismatch"
        observation: LinkObservation | None = None
        if reason is None:
            observation = checker(uri, variant)
            reason = _refuse_observation(uri, variant, observation)
        records.append(_record(uri, variant, observation, clock(), pdf_sha256))
        if reason is not None:
            repairs.append(AssetRepair(asset, uri, reason))
    if len(accepted) > len(uris):
        for _variant, uri in accepted[len(uris) :]:
            repairs.append(AssetRepair(asset, uri, "link_mismatch"))
    found = tuple(records)
    if repairs:
        raise LinkValidationRefusal(repairs[0].reason, records=found, repairs=tuple(repairs))
    return LinkReport(records=found, repairs=())


def _info_refusal(pdf: bytes, asset: str) -> LinkValidationRefusal | None:
    if refuse_gift_document_info(pdf) is None:
        return None
    return _repair(asset, _offending_info(pdf), "paid_checkout")


def _offending_info(pdf: bytes) -> str:
    try:
        values = document_strings(pdf)
    except ValueError:
        return ""
    for value in values:
        if refuse_paid_checkout(value) is not None:
            return value
    return ""


def _repair(asset: str, link: str, reason: str) -> LinkValidationRefusal:
    return LinkValidationRefusal(reason, repairs=(AssetRepair(asset, link, reason),))


def _refuse_link(uri: str, variant: str, known_variants: frozenset[str]) -> str | None:
    if variant != "" and refuse_raw_charset(variant) is not None:
        return "paid_checkout"
    if refuse_raw_charset(_allowlist_probe(uri)) is not None:
        return "paid_checkout"
    parsed = _parsed(uri)
    if parsed is None:
        return "malformed"
    tail = parsed.path
    if parsed.query:
        tail = f"{tail}?{parsed.query}"
    if parsed.fragment:
        tail = f"{tail}#{parsed.fragment}"
    if tail and refuse_paid_checkout(tail) is not None:
        return "paid_checkout"
    if any(char.isspace() for char in uri):
        return "malformed"
    if parsed.username is not None or parsed.password is not None:
        return "malformed"
    host = parsed.hostname
    if parsed.scheme == "" or host is None:
        return "malformed"
    if parsed.scheme != "https":
        return "not_https"
    if not _allowed_secret_host(host):  # pyright: ignore[reportPrivateUsage]
        return "host"
    if variant != "" and variant not in known_variants:
        return "unknown_variant"
    return None


def _allowlist_probe(uri: str) -> str:
    """Blank URL marks and ``%xx`` so the raw allowlist sees every other character.

    The percent guard owns ``%xx``. A bare ``%`` is not a percent match, so it
    stays in the probe and the allowlist refuses it. Nothing is folded.
    """
    chars: list[str] = []
    index = 0
    size = len(uri)
    while index < size:
        if uri[index] == "%" and refuse_paid_checkout(uri[index : index + 3]) is not None:
            chars.append(" ")
            index += 3
            continue
        chars.append(" " if uri[index] in _URL_MARKS else uri[index])
        index += 1
    return "".join(chars)


def _parsed(uri: str) -> ParseResult | None:
    try:
        return urlparse(uri)
    except ValueError:
        return None


def _refuse_observation(uri: str, variant: str, observed: LinkObservation) -> str | None:
    if _redirects(uri, observed.chain):
        return "redirect_host"
    if observed.variant != variant:
        return "wrong_variant"
    if observed.public is not True:
        return "auth_wall"
    if observed.duplicate_button is not True:
        return "duplicate_button"
    return None


def _redirects(uri: str, chain: tuple[str, ...]) -> bool:
    origin = urlparse(uri).hostname
    if not chain or chain[0] != uri or origin is None:
        return True
    return any(urlparse(hop).hostname != origin for hop in chain)


def _record(
    uri: str,
    variant: str,
    observed: LinkObservation | None,
    checked_at: str,
    pdf_sha256: str,
) -> LinkRecord:
    if observed is None:
        resolves = False
        public = False
        duplicate = False
    else:
        resolves = observed.variant == variant and not _redirects(uri, observed.chain)
        public = observed.public is True
        duplicate = observed.duplicate_button is True
    return LinkRecord(
        link=uri,
        variant=variant,
        resolves=resolves,
        public=public,
        duplicate_button=duplicate,
        checked_at=checked_at,
        pdf_sha256=pdf_sha256,
        link_sha256=hashlib.sha256(uri.encode()).hexdigest(),
    )
