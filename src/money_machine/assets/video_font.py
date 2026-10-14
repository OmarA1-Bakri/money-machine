"""5x7 captions for the walkthrough. No system font and no drawtext."""

from __future__ import annotations

_GLYPHS: dict[str, tuple[int, ...]] = {
    "A": (14, 17, 17, 31, 17, 17, 17),
    "B": (30, 17, 17, 30, 17, 17, 30),
    "C": (14, 17, 16, 16, 16, 17, 14),
    "D": (30, 17, 17, 17, 17, 17, 30),
    "E": (31, 16, 16, 30, 16, 16, 31),
    "F": (31, 16, 16, 30, 16, 16, 16),
    "G": (14, 17, 16, 23, 17, 17, 14),
    "H": (17, 17, 17, 31, 17, 17, 17),
    "I": (31, 4, 4, 4, 4, 4, 31),
    "J": (7, 2, 2, 2, 2, 18, 12),
    "K": (17, 18, 20, 24, 20, 18, 17),
    "L": (16, 16, 16, 16, 16, 16, 31),
    "M": (17, 27, 21, 21, 17, 17, 17),
    "N": (17, 25, 21, 19, 17, 17, 17),
    "O": (14, 17, 17, 17, 17, 17, 14),
    "P": (30, 17, 17, 30, 16, 16, 16),
    "Q": (14, 17, 17, 17, 21, 18, 13),
    "R": (30, 17, 17, 30, 20, 18, 17),
    "S": (15, 16, 16, 14, 1, 1, 30),
    "T": (31, 4, 4, 4, 4, 4, 4),
    "U": (17, 17, 17, 17, 17, 17, 14),
    "V": (17, 17, 17, 17, 17, 10, 4),
    "W": (17, 17, 17, 21, 21, 21, 10),
    "X": (17, 17, 10, 4, 10, 17, 17),
    "Y": (17, 17, 10, 4, 4, 4, 4),
    "Z": (31, 1, 2, 4, 8, 16, 31),
    "0": (14, 17, 19, 21, 25, 17, 14),
    "1": (4, 12, 4, 4, 4, 4, 14),
    "2": (14, 17, 1, 2, 4, 8, 31),
    "3": (14, 17, 1, 6, 1, 17, 14),
    "4": (2, 6, 10, 18, 31, 2, 2),
    "5": (31, 16, 30, 1, 1, 17, 14),
    "6": (6, 8, 16, 30, 17, 17, 14),
    "7": (31, 1, 2, 4, 8, 8, 8),
    "8": (14, 17, 17, 14, 17, 17, 14),
    "9": (14, 17, 17, 15, 1, 2, 12),
    " ": (0, 0, 0, 0, 0, 0, 0),
    ",": (0, 0, 0, 0, 12, 4, 8),
    ".": (0, 0, 0, 0, 0, 12, 12),
}

_WRAP = 26


def wrap_caption(text: str, width: int = _WRAP) -> tuple[str, ...]:
    """Greedy wrap on spaces. A single long word stays one line."""
    words = text.split(" ")
    lines: list[str] = []
    current = ""
    for word in words:
        piece = word if current == "" else f"{current} {word}"
        if len(piece) <= width:
            current = piece
            continue
        if current:
            lines.append(current)
        current = word
    if current:
        lines.append(current)
    return tuple(lines)


def blit(
    frame: bytearray,
    text: str,
    x: int,
    y: int,
    colour: tuple[int, int, int],
    width: int,
) -> None:
    """Paint uppercase 5x7 glyphs. Unknown characters leave a blank cell."""
    cursor = x
    for char in text:
        glyph = _GLYPHS.get(char, _GLYPHS.get(char.upper(), _GLYPHS[" "]))
        for row, bits in enumerate(glyph):
            for col in range(5):
                if bits & (1 << (4 - col)):
                    _set(frame, cursor + col, y + row, colour, width)
        cursor += 6


def _set(
    frame: bytearray,
    x: int,
    y: int,
    colour: tuple[int, int, int],
    width: int,
) -> None:
    height = len(frame) // (width * 3)
    if x < 0 or y < 0 or x >= width or y >= height:
        return
    start = (y * width + x) * 3
    frame[start] = colour[0]
    frame[start + 1] = colour[1]
    frame[start + 2] = colour[2]
