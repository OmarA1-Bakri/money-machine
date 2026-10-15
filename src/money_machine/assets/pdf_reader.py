"""Parse PDF objects from a cross-reference, including compressed object streams."""

from __future__ import annotations

import zlib
from dataclasses import dataclass
from typing import Literal

_WS = b"\x00\t\n\x0c\r "
_DELIM = _WS + b"()<>[]{}/%"
_MAX_DEPTH = 64


@dataclass(frozen=True, slots=True)
class PdfName:
    """A PDF name without the leading slash."""

    value: str


@dataclass(frozen=True, slots=True)
class PdfRef:
    """An indirect reference."""

    number: int
    generation: int


@dataclass(frozen=True, slots=True)
class PdfText:
    """A decoded string. Hex strings also keep their digits for glyph codes."""

    text: str
    hex_digits: str | None = None


@dataclass(frozen=True, slots=True)
class PdfStream:
    """A stream whose bytes are already inflated."""

    fields: dict[str, PdfObject]
    data: bytes


type PdfObject = (
    bool
    | int
    | float
    | PdfName
    | PdfRef
    | PdfText
    | PdfStream
    | tuple[PdfObject, ...]
    | dict[str, PdfObject]
    | None
)


@dataclass(frozen=True, slots=True)
class _XRef:
    kind: Literal["plain", "compressed"]
    a: int
    b: int


@dataclass(frozen=True, slots=True)
class CMap:
    """ToUnicode map used to read painted page text."""

    width: int
    codes: dict[int, str]


class _Reader:
    """Cursor over PDF bytes."""

    def __init__(self, data: bytes) -> None:
        self.data = data
        self.i = 0
        self.n = len(data)

    def _at(self, token: bytes) -> bool:
        return self.data.startswith(token, self.i)

    def _skip(self) -> None:
        while self.i < self.n:
            if self.data[self.i] in _WS:
                self.i += 1
                continue
            if self.data[self.i] == ord("%"):
                self.i += 1
                while self.i < self.n and self.data[self.i] not in b"\n\r":
                    self.i += 1
                continue
            break

    def _word(self) -> bytes:
        start = self.i
        while self.i < self.n and self.data[self.i] not in _DELIM:
            self.i += 1
        return self.data[start : self.i]

    def _number(self) -> int | float:
        start = self.i
        if self.data[self.i] in b"+-":
            self.i += 1
        saw_digit = False
        while self.i < self.n and chr(self.data[self.i]).isdigit():
            saw_digit = True
            self.i += 1
        if self.i < self.n and self.data[self.i] == ord("."):
            self.i += 1
            while self.i < self.n and chr(self.data[self.i]).isdigit():
                saw_digit = True
                self.i += 1
            if not saw_digit:
                raise ValueError("pdf number")
            return float(self.data[start : self.i])
        if not saw_digit:
            raise ValueError("pdf number")
        return int(self.data[start : self.i])

    def skip(self) -> None:
        self._skip()

    def word(self) -> bytes:
        return self._word()

    def number(self) -> int | float:
        return self._number()

    def _name(self) -> PdfName:
        self.i += 1
        start = self.i
        while self.i < self.n and self.data[self.i] not in _DELIM:
            self.i += 1
        raw = self.data[start : self.i].decode("latin-1")
        return PdfName(decode_pdf_name(raw))

    def _literal(self) -> PdfText:
        self.i += 1
        raw = bytearray()
        depth = 1
        while self.i < self.n and depth:
            char = self.data[self.i]
            self.i += 1
            if char == ord("\\"):
                esc = self.data[self.i]
                self.i += 1
                mapped = {
                    ord("n"): 10,
                    ord("r"): 13,
                    ord("t"): 9,
                    ord("b"): 8,
                    ord("f"): 12,
                }
                if esc in mapped:
                    raw.append(mapped[esc])
                elif chr(esc) in "01234567":
                    digits = bytes([esc])
                    for _ in range(2):
                        if self.i < self.n and chr(self.data[self.i]) in "01234567":
                            digits += bytes([self.data[self.i]])
                            self.i += 1
                    raw.append(int(digits, 8) & 0xFF)
                elif esc in b"\n\r":
                    if esc == ord("\r") and self.i < self.n and self.data[self.i] == ord("\n"):
                        self.i += 1
                else:
                    raw.append(esc)
                continue
            if char == ord("("):
                depth += 1
                raw.append(char)
                continue
            if char == ord(")"):
                depth -= 1
                if depth:
                    raw.append(char)
                continue
            raw.append(char)
        return PdfText(_decode_text(bytes(raw)))

    def _hex(self) -> PdfText:
        self.i += 1
        digits: list[str] = []
        while self.i < self.n and self.data[self.i] != ord(">"):
            if self.data[self.i] not in _WS:
                digits.append(chr(self.data[self.i]))
            self.i += 1
        self.i += 1
        hex_digits = "".join(digits)
        if len(hex_digits) % 2:
            hex_digits += "0"
        return PdfText(_decode_text(bytes.fromhex(hex_digits)), hex_digits)

    def _array(self, depth: int) -> tuple[PdfObject, ...]:
        self.i += 1
        items: list[PdfObject] = []
        while True:
            self._skip()
            if self._at(b"]"):
                self.i += 1
                return tuple(items)
            items.append(self.value(depth + 1))

    def _dict(self, depth: int) -> dict[str, PdfObject] | PdfStream:
        self.i += 2
        fields: dict[str, PdfObject] = {}
        while True:
            self._skip()
            if self._at(b">>"):
                self.i += 2
                break
            key = self._name().value
            if key in fields:
                raise ValueError("pdf duplicate name")
            fields[key] = self.value(depth + 1)
        self._skip()
        if not self._at(b"stream"):
            return fields
        self.i += len(b"stream")
        if self._at(b"\r\n"):
            self.i += 2
        elif self.i < self.n and self.data[self.i] in b"\r\n":
            self.i += 1
        length = fields.get("Length")
        if not isinstance(length, int) or isinstance(length, bool):
            raise ValueError("pdf stream length")
        payload = self.data[self.i : self.i + length]
        self.i += length
        return PdfStream(fields, _inflate(fields, payload))

    def value(self, depth: int = 0) -> PdfObject:
        if depth > _MAX_DEPTH:
            raise ValueError("pdf depth")
        self._skip()
        if self.i >= self.n:
            raise ValueError("pdf value")
        if self._at(b"<<"):
            return self._dict(depth)
        if self._at(b"["):
            return self._array(depth)
        if self._at(b"("):
            return self._literal()
        if self._at(b"<"):
            return self._hex()
        if self._at(b"/"):
            return self._name()
        if self.data[self.i] in b"+-." or chr(self.data[self.i]).isdigit():
            number = self._number()
            mark = self.i
            self._skip()
            if self.i < self.n and (chr(self.data[self.i]).isdigit() or self.data[self.i] in b"+-"):
                generation = self._number()
                self._skip()
                if self._at(b"R") and isinstance(number, int) and isinstance(generation, int):
                    self.i += 1
                    return PdfRef(number, generation)
            self.i = mark
            return number
        word = self._word()
        if word == b"true":
            return True
        if word == b"false":
            return False
        if word == b"null":
            return None
        raise ValueError(f"pdf token {word!r}")


PdfReader = _Reader


def token_boundary(byte: int) -> bool:
    return byte in _DELIM


def _decode_text(raw: bytes) -> str:
    if raw.startswith(b"\xfe\xff"):
        return raw[2:].decode("utf-16-be", errors="replace")
    if raw.startswith(b"\xff\xfe"):
        return raw[2:].decode("utf-16-le", errors="replace")
    return raw.decode("latin-1")


def decode_pdf_name(raw: str) -> str:
    """Decode one PDF name's ``#xx`` escapes.

    The reader calls this while storing the name. Key lookups use that stored
    value and do not decode a second time.
    """
    chars: list[str] = []
    index = 0
    while index < len(raw):
        if raw[index] == "#" and index + 2 < len(raw):
            hex_digits = raw[index + 1 : index + 3]
            try:
                chars.append(chr(int(hex_digits, 16)))
            except ValueError:
                chars.append(raw[index])
                index += 1
                continue
            index += 3
            continue
        chars.append(raw[index])
        index += 1
    return "".join(chars)


def _filter_names(fields: dict[str, PdfObject]) -> tuple[str, ...]:
    found = fields.get("Filter")
    if isinstance(found, PdfName):
        return (found.value,)
    if isinstance(found, tuple):
        return tuple(item.value for item in found if isinstance(item, PdfName))
    return ()


def _inflate(fields: dict[str, PdfObject], payload: bytes) -> bytes:
    data = payload
    for name in _filter_names(fields):
        if name != "FlateDecode":
            continue
        try:
            data = zlib.decompress(data)
        except zlib.error:
            data = zlib.decompress(data, wbits=-15)
    return _unpredict(data, fields.get("DecodeParms"))


def _unpredict(data: bytes, params: PdfObject | None) -> bytes:
    if not isinstance(params, dict):
        return data
    predictor = params.get("Predictor", 1)
    columns = params.get("Columns", 1)
    if not isinstance(predictor, int) or predictor <= 1 or not isinstance(columns, int):
        return data
    row = columns + 1
    out = bytearray()
    previous = bytearray(columns)
    for start in range(0, len(data) - columns, row):
        kind = data[start]
        raw = bytearray(data[start + 1 : start + 1 + columns])
        for index in range(columns):
            left = raw[index - 1] if index else 0
            up = previous[index]
            if kind == 1:
                raw[index] = (raw[index] + left) & 255
            elif kind == 2:
                raw[index] = (raw[index] + up) & 255
            elif kind == 3:
                raw[index] = (raw[index] + ((left + up) // 2)) & 255
            elif kind == 4:
                raw[index] = (
                    raw[index] + _paeth(left, up, previous[index - 1] if index else 0)
                ) & 255
        out.extend(raw)
        previous = raw
    return bytes(out)


def _paeth(left: int, up: int, upper_left: int) -> int:
    estimate = left + up - upper_left
    scores = (abs(estimate - left), abs(estimate - up), abs(estimate - upper_left))
    return (left, up, upper_left)[scores.index(min(scores))]


def _parse_at(pdf: bytes, offset: int) -> PdfObject:
    reader = _Reader(pdf)
    reader.i = offset
    reader.skip()
    reader.number()
    reader.skip()
    reader.number()
    reader.skip()
    if reader.word() != b"obj":
        raise ValueError("pdf object")
    return reader.value()


def _startxref(pdf: bytes) -> int:
    marker = pdf.rfind(b"startxref")
    if marker < 0:
        raise ValueError("pdf startxref")
    line = pdf[marker:].splitlines()[1]
    return int(line)


def _trailer_dict(pdf: bytes, index: int) -> tuple[dict[str, PdfObject], int]:
    reader = _Reader(pdf)
    reader.i = index
    reader.skip()
    if reader.word() != b"trailer":
        raise ValueError("pdf trailer")
    found = reader.value()
    if not isinstance(found, dict):
        raise ValueError("pdf trailer")
    return found, reader.i


def _xref_table(pdf: bytes, offset: int) -> tuple[dict[int, _XRef], dict[str, PdfObject]]:
    if not pdf.startswith(b"xref", offset):
        raise ValueError("pdf xref")
    index = pdf.find(b"\n", offset) + 1
    entries: dict[int, _XRef] = {}
    while True:
        index += len(pdf[index:]) - len(pdf[index:].lstrip(_WS))
        if pdf.startswith(b"trailer", index):
            trailer, _end = _trailer_dict(pdf, index)
            return entries, trailer
        line_end = pdf.find(b"\n", index)
        start_text, count_text = pdf[index:line_end].split()
        index = line_end + 1
        start = int(start_text)
        count = int(count_text)
        for number in range(start, start + count):
            row = pdf[index : index + 20]
            index += 20
            if row[17:18] != b"n":
                continue
            entries[number] = _XRef("plain", int(row[0:10]), int(row[11:16]))
    raise ValueError("pdf xref")


def _field(chunk: bytes, width: int) -> int:
    if width == 0:
        return 0
    return int.from_bytes(chunk[:width], "big")


def _xref_stream(stream: PdfStream) -> tuple[dict[int, _XRef], dict[str, PdfObject]]:
    widths = stream.fields.get("W")
    if not isinstance(widths, tuple) or len(widths) != 3:
        raise ValueError("pdf xref width")
    w0, w1, w2 = (item if isinstance(item, int) else 0 for item in widths)
    size = stream.fields.get("Size")
    index = stream.fields.get("Index", (0, size if isinstance(size, int) else 0))
    if not isinstance(index, tuple):
        raise ValueError("pdf xref index")
    pairs: list[tuple[int, int]] = []
    numbers = [item for item in index if isinstance(item, int)]
    for cursor in range(0, len(numbers), 2):
        pairs.append((numbers[cursor], numbers[cursor + 1]))
    width = w0 + w1 + w2
    data = stream.data
    entries: dict[int, _XRef] = {}
    pos = 0
    for origin, count in pairs:
        for number in range(origin, origin + count):
            chunk = data[pos : pos + width]
            pos += width
            kind = _field(chunk, w0) if w0 else 1
            second = _field(chunk[w0:], w1)
            third = _field(chunk[w0 + w1 :], w2)
            if kind == 1:
                entries[number] = _XRef("plain", second, third)
            elif kind == 2:
                entries[number] = _XRef("compressed", second, third)
    return entries, stream.fields


class PdfDocument:
    """One parsed file. References resolve through the cross-reference."""

    def __init__(self, pdf: bytes) -> None:
        offset = _startxref(pdf)
        if pdf.startswith(b"xref", offset):
            self.entries, self.trailer = _xref_table(pdf, offset)
        else:
            found = _parse_at(pdf, offset)
            if not isinstance(found, PdfStream):
                raise ValueError("pdf xref stream")
            self.entries, self.trailer = _xref_stream(found)
        if "Prev" in self.trailer:
            raise ValueError("pdf prev")
        self._pdf = pdf
        self._cache: dict[int, PdfObject] = {}
        self._streams: dict[int, dict[int, PdfObject]] = {}

    def get(self, number: int) -> PdfObject:
        if number in self._cache:
            return self._cache[number]
        entry = self.entries.get(number)
        if entry is None:
            raise ValueError(f"pdf object {number}")
        if entry.kind == "compressed":
            value = self._object_stream(entry.a)[number]
        else:
            value = _parse_at(self._pdf, entry.a)
        self._cache[number] = value
        return value

    def deref(self, value: PdfObject | None) -> PdfObject | None:
        seen = 0
        while isinstance(value, PdfRef) and seen < 8:
            value = self.get(value.number)
            seen += 1
        if isinstance(value, PdfRef):
            raise ValueError("pdf reference")
        return value

    def _object_stream(self, number: int) -> dict[int, PdfObject]:
        cached = self._streams.get(number)
        if cached is not None:
            return cached
        found = self.get(number)
        if not isinstance(found, PdfStream):
            raise ValueError("pdf object stream")
        count = found.fields.get("N")
        first = found.fields.get("First")
        if not isinstance(count, int) or not isinstance(first, int):
            raise ValueError("pdf object stream")
        numbers = [int(part) for part in found.data[:first].split()]
        pairs = list(zip(numbers[0::2], numbers[1::2], strict=True))
        objects: dict[int, PdfObject] = {}
        for index, (obj_num, rel) in enumerate(pairs):
            start = first + rel
            end = first + pairs[index + 1][1] if index + 1 < len(pairs) else len(found.data)
            reader = _Reader(found.data[start:end])
            objects[obj_num] = reader.value()
        self._streams[number] = objects
        return objects
