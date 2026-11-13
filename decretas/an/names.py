"""Normalisation of French transliterations of Arabic and Berber names.

Three comparison levels, from strict to loose:

* k0 -- folded word: lowercase, no accent, inner apostrophe removed (M'Hamed -> mhamed);
* k1 -- safe spelling equivalences (Mohammed = Mohamed, Kassem = Kacem, Chaabane = Chabane);
* k2 -- consonant skeleton, loose (Belkacem = Belgacem = Belkassem). Known collisions
  (Mahmoud = Mohamed, Slimane = Salomon): k2 is a second-rank level only.

Used by the debugging search (``chercher``) and by the person-level hints.
"""
from __future__ import annotations

import re
from functools import lru_cache

from .text import fold

# Words a correspondence never requires (CONTEXT.md: "Particule").
PARTICLES: frozenset[str] = frozenset({
    "ben", "bent", "bint", "bin", "ibn", "ould", "oulid", "oult", "ou", "u", "ait", "at", "ath", "nait", "n",
    "b", "bn", "bt", "fils", "fille", "de",
    "el", "al", "l", "ed", "es", "en", "er", "ez", "et", "ech", "si", "sid", "sidi", "hadj", "hadja", "lalla",
    "moulay", "dit", "dite", "nee", "ne", "veuve", "femme", "epouse",
})
# Prefixes written either attached or detached: Bel Kacem / Belkacem, Ben Chabane / Benchabane.
ATTACHABLE: tuple[str, ...] = ("ben", "bel", "bou", "abou", "bu", "abd", "abdel", "abdal", "abdoul", "el", "al",
                               "ould", "ait", "nait", "si", "ou", "bent")
_ARTICLES_AFTER_ABD = ("el", "al", "er", "es", "en", "ed", "ez")


def tokens(text: str | None) -> list[str]:
    """Folded words of a name. An apostrophe inside a word disappears; anything else separates."""
    folded = fold(text).replace("’", "'").replace("`", "'")
    folded = re.sub(r"(?<=[a-z])'(?=[a-z])", "", folded)
    return re.sub(r"[^a-z]+", " ", folded).split()


@lru_cache(maxsize=200_000)
def k1(token: str) -> str:
    """Spelling key: safe French transliteration equivalences."""
    key = re.sub(r"sch|tch|sh", "ch", token)
    key = key.replace("ph", "f")
    key = key.replace("ou", "u").replace("oo", "u").replace("w", "u")
    key = key.replace("y", "i")
    key = re.sub(r"c(?=[ei])", "s", key)
    key = re.sub(r"ck|cq|q(?:u(?=[aeio]))?|c(?!h)", "k", key)
    key = re.sub(r"(.)\1+", r"\1", key)
    key = re.sub(r"(?<=[a-z]{3})e$", "", key)
    return re.sub(r"(?<=[aeiu])h$", "", key)


@lru_cache(maxsize=200_000)
def k2(token: str) -> str:
    """Consonant skeleton: loose key, to be presented as an approximate spelling."""
    key = k1(token)
    key = key.replace("kh", "k").replace("gh", "g").replace("dj", "j").replace("dh", "d").replace("th", "t")
    key = re.sub(r"gu(?=[aeiu])", "g", key)
    key = re.sub(r"g(?=[aou]|[^aeiou]|$)", "k", key)
    key = key.replace("z", "s")
    key = re.sub(r"a?[uo]i$", "wi", key)
    tail = ""
    if len(key) > 3 and key[-1] in "aeiou":
        tail = "i" if key[-1] in "ie" else key[-1]
        key = key[:-1]
    return key[:1] + re.sub(r"[aeiou]", "", key[1:]) + tail


def split_forms(token: str) -> list[str]:
    """Forms obtained by detaching an attached prefix: benchabane -> chabane, ezzemri -> zemri."""
    forms = [token[len(p):] for p in ATTACHABLE if token.startswith(p) and len(token) - len(p) >= 4]
    assimilated = re.match(r"^[ea]([dnrstzc])\1([a-z]{3,})$", token)
    if assimilated:
        forms.append(assimilated.group(1) + assimilated.group(2))
    return forms


def expand(words: list[str]) -> set[str]:
    """Every searchable form of a word list: the words, joined prefixes, detached prefixes."""
    forms: set[str] = set()
    for index, word in enumerate(words):
        forms.add(word)
        if word in ATTACHABLE and index + 1 < len(words):
            forms.add(word + words[index + 1])
            if word == "abd" and words[index + 1] in _ARTICLES_AFTER_ABD and index + 2 < len(words):
                forms.add("abd" + words[index + 1] + words[index + 2])
                forms.add("abdel" + words[index + 2])
        forms.update(split_forms(word))
    return forms
