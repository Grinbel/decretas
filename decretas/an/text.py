"""Small pure text helpers shared by the whole pipeline."""
from __future__ import annotations

import unicodedata


def squash(text: str | None) -> str:
    """Collapse every run of whitespace (including no-break spaces) to one space."""
    return " ".join((text or "").replace(" ", " ").replace(" ", " ").split())


def fold(text: str | None) -> str:
    """Lowercase and strip diacritics. The length of the result is NOT guaranteed."""
    decomposed = unicodedata.normalize("NFD", (text or "").lower())
    return "".join(c for c in decomposed if unicodedata.category(c) != "Mn")


def fold_keep(text: str | None) -> str:
    """Lowercase and strip diacritics, one output character per input character.

    Offsets found in the folded string are valid in the original string, provided the
    original is already NFC (callers pass squashed NFC text).
    """
    out: list[str] = []
    for char in text or "":
        base = unicodedata.normalize("NFD", char)[0].lower()
        out.append(base if len(base) == 1 else char)
    return "".join(out)


def nfc(text: str | None) -> str:
    """Unicode NFC form, so that offsets of ``fold_keep`` line up."""
    return unicodedata.normalize("NFC", text or "")
