"""Small pure text helpers shared by the BOGGA parser: folding, OCR-tolerant comparison."""
from __future__ import annotations

import re
import unicodedata


def fold(text: str) -> str:
    """Lower-case and strip accents: 'Sénatus-Consulte' -> 'senatus-consulte'."""
    decomposed = unicodedata.normalize("NFD", text)
    return "".join(c for c in decomposed if unicodedata.category(c) != "Mn").lower()


def levenshtein(a: str, b: str, cap: int = 3) -> int:
    """Edit distance, cut short at cap + 1 when the lengths alone exceed the cap."""
    if abs(len(a) - len(b)) > cap:
        return cap + 1
    previous = list(range(len(b) + 1))
    for i, char_a in enumerate(a, 1):
        current = [i]
        for j, char_b in enumerate(b, 1):
            current.append(min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (char_a != char_b)))
        previous = current
    return previous[-1]


_WORD = re.compile(r"[^\W\d_]+", re.UNICODE)


def words(text: str) -> list[str]:
    """Alphabetic words of a text, in order."""
    return _WORD.findall(text)


def letters(text: str) -> int:
    """Number of alphabetic characters."""
    return sum(1 for c in text if c.isalpha())


def near(token: str, target: str, tolerance: int) -> bool:
    """Is the folded token within `tolerance` edits of `target` (already folded)?"""
    return levenshtein(fold(token), target, tolerance) <= tolerance


_HYPHEN_BREAK = re.compile(r"(?<=[a-zàâçéèêëîïôûùü])- (?=[a-zàâçéèêëîïôûùü])")


def join_hyphenation(line: str) -> str:
    """Re-join a word cut at a line end inside an OCR paragraph: 'demeu- rant' -> 'demeurant'.

    Only lower-case to lower-case joins: 'Saint- Denis' or 'Beni- Méred' keep their hyphen.
    """
    return _HYPHEN_BREAK.sub("", line)


def squeeze(text: str) -> str:
    """Collapse runs of white space."""
    return " ".join(text.split())
