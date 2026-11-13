"""Recognising Algerian places in birth-place and residence strings.

The single word "Algérie" is not enough: the verification of 2026-11-11 measured that it
misses at least 12 % of the Algerian births ('Aïn Bessem, Alger', 'Fort-National (Alger)',
'Beni-Ouidhane, Constantine'). A place is therefore recognised by:

* ``explicite`` -- the country, a department or a region is named ('Algérie', 'département
  d'Oran', 'Kabylie'), or one of the three department names stands alone as a second or later
  component ('Bône ( Constantine )');
* ``repertoire`` -- no other country is named and the FIRST component is a locality of the empirical
  gazetteer ``reference/gazetteer_algerie.tsv`` (derived from the corpus itself: localities
  seen at least 3 times with an explicit Algerian marker, at least 90 % of the time).

Both are hints. Ambiguous names (Castiglione, Nemours, Mondovi, Saint-Cloud…) are never used.
"""
from __future__ import annotations

import csv
import re
from collections import Counter
from collections.abc import Iterable
from functools import lru_cache
from pathlib import Path

from .text import fold

GAZETTEER_PATH = Path(__file__).resolve().parent / "reference" / "gazetteer_algerie.tsv"
GAZETTEER_FIELDS = ("nom", "n_algerie", "n_ailleurs", "n_seul", "part_algerie", "statut")

RULE_EXPLICIT = "explicite"
RULE_GAZETTEER = "repertoire"

STATUS_SAFE = "sur"
STATUS_AMBIGUOUS = "ambigu"
STATUS_ELSEWHERE = "surtout-ailleurs"
MIN_OCCURRENCES = 3
SAFE_SHARE = 0.9

_DEPARTMENTS = ("alger", "oran", "constantine")
# 'algerie' with the misspellings actually met in the inventories ('Agérie', 'Allgérie'…).
# 'Algerri' (Catalonia), 'Almérie' and 'Alghero' are other places and must not match.
# The adjective 'algérien' is NOT a place marker: in the inventories it only qualifies the parents
# ('Tunis, Tunisie, de père algérien') or an employer, never the place of birth.
_EXPLICIT = re.compile(
    r"\b(algerie|agerie|algarie|allgerie|algeire|algeie|algeriea|algeirie|algeroe)\b"
    r"|\bdepartement\s+d['e ]\s*(alger|oran|constantine)\b"
    r"|\bdept?\.?\s+d['e ]\s*(alger|oran|constantine)\b"
    r"|\bprovince\s+d['e ]\s*(alger|oran|constantine)\b"
    r"|\bterritoires?\s+du\s+sud\b|\bsud[- ]oranais\b|\bkabylie\b")
_OTHER_COUNTRY = re.compile(
    r"\b(france|italie|espagne|allemagne|belgique|suisse|tunisie|maroc|malte|russie|pologne|autriche|turquie|"
    r"luxembourg|roumanie|prusse|grece|hongrie|angleterre|hollande|pays-bas|baviere|egypte|syrie|bulgarie|serbie|"
    r"portugal|etats-unis|bresil|argentine|madagascar|indochine|cochinchine|tonkin|annam|vietnam|senegal|liban|"
    r"armenie|alsace-lorraine|bas-rhin|haut-rhin|moselle|seine|nord|corse|bouches-du-rhone|tchecoslovaquie|"
    r"yougoslavie|indes?|albanie|libye|tripolitaine|soudan|haute-volta|dahomey|singapour|ceylan|viet[- ]nam|"
    r"cambodge|laos|caledonie|djibouti|reunion|guinee|perse|irak|palestine|chine|japon|canada|mexique|cuba|haiti|"
    r"chili|perou|uruguay|colombie|venezuela|danemark|suede|norvege|finlande|irlande|ecosse|gibraltar|monaco|"
    r"mauritanie|niger|tchad|congo|gabon|cameroun|togo|martinique|guadeloupe|guyane|tahiti|pondichery|"
    r"ethiopie|abyssinie|georgie|ukraine|lituanie|lettonie|estonie|boheme|croatie|dalmatie|montenegro|"
    r"macedoine|crete|chypre)\b")
_COUNTRY_PATTERNS: tuple[tuple[str, str], ...] = (
    ("tunisie", r"\btunisi|\btunis\b|\bsfax\b|\bsousse\b|\bbizerte\b|\bdjerba\b|\bla goulette\b"),
    ("maroc", r"\bmaroc|\btanger\b|\btetouan\b|\btetuan\b|\bfez\b|\bmarrakech\b|\bmogador\b|\bcasablanca\b"
              r"|\brabat\b|\boudjda\b|\bfiguig\b"),
    ("espagne", r"\bespagne|\bbaleares\b"),
    ("italie", r"\bitalie|\bsicile\b|\bsardaigne\b"),
    ("malte", r"\bmalte\b"),
    ("allemagne", r"\ballemagne|\bprusse\b|\bbaviere\b|\bwurtemberg\b|\bbade\b|\bsaxe\b"),
    ("alsace-lorraine", r"\balsace|\bbas[- ]rhin\b|\bhaut[- ]rhin\b|\bmoselle\b"),
    ("belgique", r"\bbelgique"),
    ("suisse", r"\bsuisse"),
    ("france", r"\bfrance\b"),
)
_COMMUNE_PREFIX = re.compile(
    r"^(a|au|aux|en|la commune de|commune de|commune mixte de|commune mixte d'|commune mixte des|"
    r"commune d'|douar des|douar|tribu des|tribu de|tribu)\s+")
_NOT_A_PLACE = {"algerie", "non precise", "non precisee", "date inconnue", "inconnu", "lieu inconnu"}


def components(place: str) -> list[str]:
    """Folded top-level components of a place string, split on commas and parentheses."""
    folded = re.sub(r"\[[^\]]*\]", " ", fold(place))
    parts = (re.sub(r"\s+", " ", part).strip(" .;:-") for part in re.split(r"[,()]", folded))
    return [part for part in parts if part]


def normalise_locality(component: str) -> str:
    """'commune mixte de Fort-National' -> 'fort national' (comparison key of the gazetteer)."""
    name = _COMMUNE_PREFIX.sub("", component)
    name = name.replace("-", " ").replace("'", " ")
    return re.sub(r"\s+", " ", name).strip()


def is_explicitly_algerian(place: str) -> bool:
    if _EXPLICIT.search(fold(place)):
        return True
    return any(part in _DEPARTMENTS for part in components(place)[1:])


def names_other_country(place: str) -> bool:
    return bool(_OTHER_COUNTRY.search(fold(place)))


def country_of(place: str) -> str:
    """Country suggested by a place string, among a short list; '' when none is recognised."""
    folded = fold(place)
    for country, pattern in _COUNTRY_PATTERNS:
        if re.search(pattern, folded):
            return country
    return ""


@lru_cache(maxsize=4)
def load_safe_localities(path: Path = GAZETTEER_PATH) -> frozenset[str]:
    """Localities of the gazetteer marked safe. An absent file gives an empty set."""
    try:
        with path.open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle, delimiter="\t"))
    except FileNotFoundError:
        return frozenset()
    return frozenset(row["nom"] for row in rows if row["statut"] == STATUS_SAFE and row["nom"] not in _NOT_A_PLACE)


def algeria_rule(place: str, safe: frozenset[str]) -> str:
    """'' | 'explicite' | 'repertoire' for one place string."""
    if not place:
        return ""
    if is_explicitly_algerian(place):
        return RULE_EXPLICIT
    if names_other_country(place):
        return ""
    parts = components(place)
    # First component only: 'Vigorac, Dalmatie' must not match the Algerian village of Dalmatie.
    if parts and normalise_locality(parts[0]) in safe:
        return RULE_GAZETTEER
    return ""


def derive(places: Iterable[str]) -> list[dict[str, str]]:
    """Derive the gazetteer rows from every place string of a build (births and residences).

    The first component of each string is counted three ways: with an explicit Algerian
    marker, with another country named, or alone. Rare names are dropped.
    """
    algerian: Counter[str] = Counter()
    elsewhere: Counter[str] = Counter()
    alone: Counter[str] = Counter()
    for place in places:
        parts = components(place)
        if not parts:
            continue
        first = normalise_locality(parts[0])
        if len(first) < 3 or first in _NOT_A_PLACE:
            continue
        if is_explicitly_algerian(place):
            algerian[first] += 1
        elif names_other_country(place):
            elsewhere[first] += 1
        else:
            alone[first] += 1
    rows: list[dict[str, str]] = []
    for name, count in sorted(algerian.items(), key=lambda item: (-item[1], item[0])):
        if count < MIN_OCCURRENCES and name not in _DEPARTMENTS:
            continue
        share = count / (count + elsewhere[name])
        if name in _DEPARTMENTS or share >= SAFE_SHARE:
            status = STATUS_SAFE
        elif share >= 0.5:
            status = STATUS_AMBIGUOUS
        else:
            status = STATUS_ELSEWHERE
        rows.append({"nom": name, "n_algerie": str(count), "n_ailleurs": str(elsewhere[name]),
                     "n_seul": str(alone[name]), "part_algerie": f"{share:.3f}", "statut": status})
    return rows


def write(rows: list[dict[str, str]], path: Path = GAZETTEER_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=GAZETTEER_FIELDS, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    load_safe_localities.cache_clear()
