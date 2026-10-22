"""Gift-PDF surfaces read by walking objects, not by searching bytes.

``link_annotations`` counts ``/Link`` annotations and returns each action
``/URI``. ``delivery_link_uris`` is that walk for link validation. A link is
exactly ``Type``, ``Subtype``, ``Rect``, ``Border``, ``F``, and ``A``, with
``/Subtype /Link``. ``/S`` must be ``/URI``. Any other ``/URI`` must be an
accepted link. The catalog is trailer ``/Root`` and equals ``Type`` and
``Pages``, optionally with Chromium's exact inert ``ViewerPreferences``.
A page equals the Chromium keys, plus ``Annots`` when present.
``/Resources`` equals the measured set ``ExtGState``, ``Font``, and
``ProcSet``. Role checks see the resolved value. A ``/URI`` is deferred only
for a ``/Annots`` link on a page the ``/Kids`` walk reached. A ``/Kids``
chain past depth 64 raises ``pdf kids depth``.
"""

from __future__ import annotations

from money_machine.assets.pdf_reader import (
    PdfDocument,
    PdfName,
    PdfObject,
    PdfRef,
    PdfStream,
    PdfText,
)


def _name_is(value: PdfObject | None, expected: str) -> bool:
    return isinstance(value, PdfName) and value.value == expected


def _once(doc: PdfDocument, value: PdfObject | None) -> PdfObject | None:
    """Resolve one indirect reference. A second hop stays a reference."""
    if isinstance(value, PdfRef):
        return doc.get(value.number)
    return value


def _dict(value: PdfObject | None) -> dict[str, PdfObject]:
    if isinstance(value, dict):
        return value
    return {}


def _pages(
    doc: PdfDocument,
    node: PdfObject | None,
    seen: frozenset[int] = frozenset(),
    depth: int = 0,
    numbers: set[int] | None = None,
) -> tuple[dict[str, PdfObject], ...]:
    if depth > _MAX_DEPTH:
        raise ValueError("pdf kids depth")
    number: int | None = None
    if isinstance(node, PdfRef):
        if node.number in seen:
            raise ValueError("pdf page")
        seen = seen | {node.number}
        number = node.number
    found = doc.deref(node)
    page = _dict(found)
    if _name_is(page.get("Type"), "Page"):
        if numbers is not None and number is not None:
            numbers.add(number)
        return (page,)
    kids = doc.deref(page.get("Kids"))
    if not isinstance(kids, tuple):
        raise ValueError("pdf page")
    return tuple(item for kid in kids for item in _pages(doc, kid, seen, depth + 1, numbers))


def _text_of(value: PdfObject | None) -> str | None:
    if isinstance(value, PdfText):
        return value.text
    return None


def link_annotations(pdf: bytes) -> tuple[int, tuple[str, ...]]:
    """Count ``/Link`` annotations and return each ``/URI`` string.

    The gift check uses this count. It does not refuse catalog actions.
    """
    doc = PdfDocument(pdf)
    root = _dict(doc.deref(doc.trailer.get("Root")))
    count = 0
    uris: list[str] = []
    for page in _pages(doc, root.get("Pages")):
        annots = doc.deref(page.get("Annots"))
        if not isinstance(annots, tuple):
            continue
        for item in annots:
            annot = _dict(doc.deref(item))
            if not _name_is(annot.get("Subtype"), "Link"):
                continue
            count += 1
            action = _dict(doc.deref(annot.get("A")))
            uri = _text_of(action.get("URI"))
            if uri is not None:
                uris.append(uri)
    return count, tuple(uris)


_LINK_KEYS = frozenset({"Type", "Subtype", "Rect", "Border", "F", "A"})
_ACTION_BARE = frozenset({"S", "URI"})
_ACTION_WITH_TYPE = frozenset({"Type", "S", "URI"})
_CATALOG_KEYS = frozenset({"Pages", "Type"})
_PAGE_KEYS = frozenset({"Contents", "MediaBox", "Parent", "Resources", "Tabs", "Type"})
_PAGE_WITH_ANNOTS = _PAGE_KEYS | {"Annots"}
_ANNOT_ALLOW_EXTRA: frozenset[str] = frozenset()
_ACTION_ALLOW_EXTRA: frozenset[str] = frozenset()
_CATALOG_ALLOW_EXTRA: frozenset[str] = frozenset()
_PAGE_ALLOW_EXTRA: frozenset[str] = frozenset()
# Measured from Chromium README and gift output: the only /S name is URI.
_ALLOWED_S: frozenset[str] = frozenset({"URI"})
# Measured page /Resources keys. README has two pages, the gift one. Both match.
_RESOURCE_KEYS = frozenset({"ExtGState", "Font", "ProcSet"})
_MAX_DEPTH = 64


class EmbeddedUriRefusal(ValueError):
    """A ``/URI`` outside a link action failed the delivery-link rules."""

    def __init__(self, code: str, uri: str) -> None:
        super().__init__(code)
        self.code = code
        self.uri = uri


def delivery_link_uris(pdf: bytes, *, accepted: frozenset[str] = frozenset()) -> tuple[str, ...]:
    """Return each link URI from the page walk, or raise ``ValueError``.

    Annotation keys must equal the Chromium set. The action is ``S`` and
    ``URI``, with ``Type /Action`` when ``Type`` is present. ``/S`` must be
    ``/URI``. An indirect action or URI resolves one hop. A URI stream is
    refused. The catalog is checked from the trailer ``/Root`` before the
    walk. A page must equal the generator's keys. ``/Resources`` must equal
    the measured Chromium set. Annotation roles are the graph walk's check.
    """
    doc = PdfDocument(pdf)
    _refuse_graph(doc, accepted)
    root = _dict(doc.deref(doc.trailer.get("Root")))
    uris: list[str] = []
    for page in _pages(doc, root.get("Pages")):
        annots = doc.deref(page.get("Annots"))
        if not isinstance(annots, tuple):
            continue
        for item in annots:
            uris.append(_uri_action(doc, _dict(doc.deref(item))))
    return tuple(uris)


def _refuse_graph(doc: PdfDocument, accepted: frozenset[str]) -> None:
    """Refuse a bad catalog, a bad page, a non-URI ``/S``, and an unvalidated ``/URI``.

    The catalog is ``trailer["Root"]``, checked before the walk so an earlier
    ``/Info`` or ``/Foo`` cannot hide it. The walk's seen set is
    ``(object, role)``. Role checks run after a reference is resolved, so an
    inline dictionary hits the same check. A page is an object ``_pages``
    reached from ``/Root`` through ``/Pages`` and ``/Kids``. Objects that
    nothing references are walked afterwards. Nesting deeper than
    ``_MAX_DEPTH`` is refused.
    """
    _refuse_trailer_root(doc)
    real_pages: set[int] = set()
    root = _dict(doc.deref(doc.trailer.get("Root")))
    _pages(doc, root.get("Pages"), numbers=real_pages)
    seen: set[tuple[int, str | None]] = set()

    def scan(
        value: PdfObject | None,
        parent_key: str | None,
        depth: int,
        *,
        in_link_action: bool = False,
        under_page_annots: bool = False,
        action_of_annot: bool = False,
    ) -> None:
        if depth > _MAX_DEPTH:
            raise ValueError("pdf depth")
        role = parent_key
        number: int | None = None
        if isinstance(value, PdfRef):
            number = value.number
            if (value.number, role) in seen:
                return
            seen.add((value.number, role))
            value = doc.get(value.number)
        if isinstance(value, dict):
            _refuse_resolved_role(
                value,
                role=role,
                in_link_action=in_link_action,
                action_of_annot=action_of_annot,
            )
            _refuse_dict(doc, value, accepted, in_link_action=in_link_action)
            annot = _name_is(value.get("Type"), "Annot")
            link = annot and _name_is(value.get("Subtype"), "Link")
            defer = _defer_page_annots(value, number=number, real_pages=real_pages)
            for key, child in value.items():
                scan(
                    child,
                    key,
                    depth + 1,
                    in_link_action=under_page_annots and link and key == "A",
                    under_page_annots=defer and key == "Annots",
                    action_of_annot=annot and key == "A",
                )
            return
        if isinstance(value, tuple):
            for item in value:
                scan(
                    item,
                    parent_key,
                    depth + 1,
                    in_link_action=in_link_action,
                    under_page_annots=under_page_annots,
                    action_of_annot=action_of_annot,
                )
            return
        if isinstance(value, PdfStream):
            scan(
                value.fields,
                parent_key,
                depth + 1,
                in_link_action=in_link_action,
                under_page_annots=under_page_annots,
                action_of_annot=action_of_annot,
            )

    scan(doc.trailer, None, 0)
    reached = {number for number, _role in seen}
    for number in list(doc.entries):
        if number not in reached:
            scan(PdfRef(number, 0), None, 0)
            reached.add(number)


def _refuse_trailer_root(doc: PdfDocument) -> None:
    """Check the trailer catalog itself, independent of walk order."""
    root = doc.deref(doc.trailer.get("Root"))
    if not isinstance(root, dict):
        raise ValueError("pdf catalog keys")
    keys = frozenset(root) - _CATALOG_ALLOW_EXTRA
    if keys == _CATALOG_KEYS | {"ViewerPreferences"}:
        # Full Chromium 153 emits this inline dictionary; the matching
        # headless shell omits it. Do not resolve references or admit other
        # viewer options: only the measured, non-executable shape is supported.
        preferences = root["ViewerPreferences"]
        if (
            not isinstance(preferences, dict)
            or frozenset(preferences) != frozenset({"Type", "DisplayDocTitle"})
            or not _name_is(preferences.get("Type"), "ViewerPreferences")
            or preferences.get("DisplayDocTitle") is not True
        ):
            raise ValueError("pdf viewer preferences")
    elif keys != _CATALOG_KEYS:
        raise ValueError("pdf catalog keys")
    _refuse_root_names(doc, root)


def _refuse_root_names(doc: PdfDocument, fields: dict[str, PdfObject]) -> None:
    """Refuse ``/JavaScript`` or ``/EmbeddedFiles`` on the root ``/Names`` object."""
    names = fields.get("Names")
    if isinstance(names, PdfRef):
        names = doc.get(names.number)
    if not isinstance(names, dict):
        return
    if "JavaScript" in names or "EmbeddedFiles" in names:
        raise ValueError("pdf names entry")


def _refuse_resolved_role(
    fields: dict[str, PdfObject],
    *,
    role: str | None,
    in_link_action: bool,
    action_of_annot: bool,
) -> None:
    """Apply the role check to one dictionary, inline or just resolved."""
    if role == "Annots":
        _refuse_annot_role(fields)
        return
    if role == "Resources":
        if frozenset(fields) != _RESOURCE_KEYS:
            raise ValueError("pdf resource keys")
        return
    if role == "AA":
        raise ValueError("pdf additional action")
    if role == "A" and not in_link_action and not action_of_annot:
        raise ValueError("pdf action role")
    if _name_is(fields.get("Subtype"), "Link"):
        raise ValueError("pdf link lookalike")


def _defer_page_annots(
    fields: dict[str, PdfObject],
    *,
    number: int | None,
    real_pages: set[int],
) -> bool:
    """Defer link URIs only for a page object the page tree reached."""
    if not _name_is(fields.get("Type"), "Page"):
        return False
    return number is not None and number in real_pages


def _refuse_annot_role(fields: dict[str, PdfObject]) -> None:
    """Check an annotation reached under ``Annots``."""
    if frozenset(fields) - _ANNOT_ALLOW_EXTRA != _LINK_KEYS:
        raise ValueError("pdf link keys")
    if not _name_is(fields.get("Subtype"), "Link"):
        raise ValueError("pdf annot subtype")


def _refuse_dict(
    doc: PdfDocument,
    fields: dict[str, PdfObject],
    accepted: frozenset[str],
    *,
    in_link_action: bool,
) -> None:
    _refuse_page(fields)
    action = fields.get("S")
    if isinstance(action, PdfName) and action.value not in _ALLOWED_S:
        raise ValueError("pdf action s")
    if isinstance(action, PdfName):
        _refuse_action_uri(doc, fields, accepted, in_link_action=in_link_action)


def _refuse_page(fields: dict[str, PdfObject]) -> None:
    if not _name_is(fields.get("Type"), "Page"):
        return
    if "AA" in fields:
        raise ValueError("pdf page additional action")
    keys = frozenset(fields) - _PAGE_ALLOW_EXTRA
    if keys != _PAGE_KEYS and keys != _PAGE_WITH_ANNOTS:
        raise ValueError("pdf page keys")


def _refuse_action_uri(
    doc: PdfDocument,
    fields: dict[str, PdfObject],
    accepted: frozenset[str],
    *,
    in_link_action: bool,
) -> None:
    """Validate a ``/URI`` the link extractor will not return.

    A link annotation's own action is left to ``validate_pdf_links``, which
    records that URI by index. Every other ``/S /URI`` uses the same rules.
    A stream stays unresolved here so the link path owns that refusal.
    """
    if in_link_action or "URI" not in fields:
        return
    resolved = _once(doc, fields.get("URI"))
    if isinstance(resolved, PdfStream):
        return
    uri = _text_of(resolved)
    if uri is None:
        return
    reason = _graph_uri_reason(uri, accepted)
    if reason is not None:
        raise EmbeddedUriRefusal(reason, uri)


def _graph_uri_reason(uri: str, accepted: frozenset[str]) -> str | None:
    # link_validation imports this module, so a top-level import cycles.
    from money_machine.assets.link_validation import refuse_graph_uri

    return refuse_graph_uri(uri, accepted=accepted)


def _uri_action(doc: PdfDocument, annot: dict[str, PdfObject]) -> str:
    """Return the URI of one already-decoded link annotation."""
    if frozenset(annot) - _ANNOT_ALLOW_EXTRA != _LINK_KEYS:
        raise ValueError("pdf link keys")
    if not _name_is(annot.get("Type"), "Annot"):
        raise ValueError("pdf link type")
    action = _dict(_once(doc, annot.get("A")))
    keys = frozenset(action) - _ACTION_ALLOW_EXTRA
    if keys == _ACTION_WITH_TYPE and not _name_is(action.get("Type"), "Action"):
        raise ValueError("pdf action type")
    if keys != _ACTION_WITH_TYPE and keys != _ACTION_BARE:
        raise ValueError("pdf action keys")
    resolved = _once(doc, action.get("URI"))
    if isinstance(resolved, PdfStream):
        raise ValueError("pdf uri stream")
    uri = _text_of(resolved)
    if uri is None:
        raise ValueError("pdf uri")
    return uri


def document_strings(pdf: bytes) -> tuple[str, ...]:
    """Info-dictionary strings and the catalog XMP packet, when one is present."""
    doc = PdfDocument(pdf)
    found: list[str] = []
    info = _dict(doc.deref(doc.trailer.get("Info")))
    for value in info.values():
        text = _text_of(doc.deref(value))
        if text is not None:
            found.append(text)
    root = _dict(doc.deref(doc.trailer.get("Root")))
    metadata = doc.deref(root.get("Metadata"))
    if isinstance(metadata, PdfStream):
        found.append(metadata.data.decode("utf-8", errors="replace"))
    return tuple(found)


def read_dict(value: PdfObject | None) -> dict[str, PdfObject]:
    """Return a dictionary object, or an empty dictionary."""
    return _dict(value)


def read_pages(
    doc: PdfDocument,
    node: PdfObject | None,
) -> tuple[dict[str, PdfObject], ...]:
    """Return the page dictionaries reached from ``/Pages``."""
    return _pages(doc, node)
