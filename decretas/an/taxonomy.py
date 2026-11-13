"""Decree taxonomy, relevance to Algeria, and checks on the decree cote.

Before 1931 nothing in a title tells the admission of an "indigène" from the naturalisation
of a foreigner in Algeria: both sit in the same "Décret de naturalisations algériennes".
From 1931 the title "admission aux droits de citoyen français" appears, most often WITHOUT a
territory. Hence four classes of relevance (never a legal qualification):

* ``A1`` -- the title names Algeria and is not a rejection;
* ``A2`` -- "admission aux droits de citoyen" without any territory (1931+): mixes Algerians
  with people of other territories;
* ``A3`` -- composite decree including the admission to citizen's rights (1941-1948);
* ``R``  -- rejection, revocation or withdrawal naming Algeria, or rejecting requests of admission
  to citizen's rights written without a territory (four collective rejections of 1933: the
  counterpart of ``A2`` for refused requests).

Titles are never tested by their first words: 28 decrees start with a typing error
('écret', 'FDécret', '&gt;Décret') or have lost their title.
"""
from __future__ import annotations

import re
from typing import NamedTuple

from .text import fold

FAMILY_REJECTION = "rejet"
FAMILY_REVOCATION = "revocation-retrait"
FAMILY_CITIZEN = "admission-citoyen"
FAMILY_COMPOSITE_CITIZEN = "composite-avec-citoyen"
FAMILY_AUTHORISATION = "autorisation-etranger"
FAMILY_ALLEGIANCE = "liberation-allegeance"
FAMILY_DOMICILE = "admission-domicile"
FAMILY_NATURALISATION = "naturalisation"
FAMILY_NATURALISATION_REINTEGRATION = "naturalisation+reintegration"
FAMILY_REINTEGRATION = "reintegration"
FAMILY_TITLES = "titre-nom-dispense"
FAMILY_OTHER = "divers"

FAMILIES: tuple[str, ...] = (
    FAMILY_REJECTION, FAMILY_REVOCATION, FAMILY_CITIZEN, FAMILY_COMPOSITE_CITIZEN, FAMILY_AUTHORISATION,
    FAMILY_ALLEGIANCE, FAMILY_DOMICILE, FAMILY_NATURALISATION, FAMILY_NATURALISATION_REINTEGRATION,
    FAMILY_REINTEGRATION, FAMILY_TITLES, FAMILY_OTHER,
)

CLASS_A1 = "A1"
CLASS_A2 = "A2"
CLASS_A3 = "A3"
CLASS_R = "R"
CLASS_NONE = "-"
ALGERIA_CLASSES: tuple[str, ...] = (CLASS_A1, CLASS_A2, CLASS_A3, CLASS_R)

COTE_OK = ""
COTE_SUSPECT_BB11 = "suspecte-bb11"   # BB/11 is the sub-series of the dossiers, not of the decrees
COTE_MISSING = "absente"

_TERRITORIES: tuple[tuple[str, str], ...] = (
    ("algerie", r"algeri|aglerie"),          # 'Aglérie': a typing error met in one title of 1934
    ("tunisie", r"tunisi"),
    ("maroc", r"maroc"),
    ("alsace-lorraine", r"alsac"),
    ("madagascar", r"madagascar|malgache"),
    ("indochine", r"cochinchin|tonkin|annam|indochin|cambodg"),
    ("colonies", r"coloni|senegal|dahomey|soudan|gabon|guyan|caledoni|tahiti|reunion|martiniq|guadeloup|togo|"
                 r"cameroun|inde|oceanie|congo|guinee|cote d'ivoire|afrique (?:equatoriale|occidentale)"),
    ("etranger", r"a l'etranger"),
    ("proteges", r"proteges"),
)
_BB11 = re.compile(r"^BB/11/(\d+[A-Za-z/]*)$")
# "citoyen français" NOT followed by a parenthesis of territories: '… d'admission aux droits de citoyen
# français, de naturalisations à l'étranger …' but not '… de citoyen français (Madagascar, Cochinchine)'.
_CITIZEN_WITHOUT_TERRITORY = re.compile(r"citoyens?(?:\s+francais)?(?!\s+francais)(?!\s*\()")


class DecreeClass(NamedTuple):
    family: str
    territories: tuple[str, ...]
    algeria_class: str


class CoteCheck(NamedTuple):
    cote: str          # as written, never replaced
    source: str        # 'identifiant' | 'cote-de-consultation' | ''
    flag: str
    suggestion: str    # 'BB/34/477' when the cote reads 'BB/11/477', else ''


def family_of(title: str) -> str:
    """Family of a decree title (first matching rule wins)."""
    folded = fold(title).replace("’", "'")
    if re.search(r"\brejet", folded):
        return FAMILY_REJECTION
    if re.search(r"revocation|rapportant|retrait|annul", folded):
        return FAMILY_REVOCATION
    if "citoyen" in folded or "statut metropolitain" in folded or "statut de metropolitain" in folded:
        return FAMILY_COMPOSITE_CITIZEN if "naturalisation" in folded else FAMILY_CITIZEN
    if re.search(r"autorisation.*(naturalis|servir)|se faire naturaliser|naturalisations? a l'etranger", folded):
        return FAMILY_AUTHORISATION
    if "liberation" in folded and "naturalisation" not in folded:
        return FAMILY_ALLEGIANCE
    if "admission" in folded and "domicile" in folded:
        return FAMILY_DOMICILE
    if "naturalisation" in folded:
        return FAMILY_NATURALISATION_REINTEGRATION if "reintegr" in folded else FAMILY_NATURALISATION
    if "reintegr" in folded:
        return FAMILY_REINTEGRATION
    if re.search(r"investiture|dotation|titre|majorat|armoiries|\bnoms?\b|dispense", folded):
        return FAMILY_TITLES
    return FAMILY_OTHER


def territories_of(title: str) -> tuple[str, ...]:
    folded = fold(title).replace("’", "'")
    return tuple(name for name, pattern in _TERRITORIES if re.search(pattern, folded))


def classify_decree(title: str) -> DecreeClass:
    """Family, territories and Algeria class of a decree title."""
    family = family_of(title)
    territories = territories_of(title)
    names_algeria = "algerie" in territories
    if family in (FAMILY_REJECTION, FAMILY_REVOCATION):
        folded = fold(title).replace("’", "'")
        concerned = names_algeria or bool(_CITIZEN_WITHOUT_TERRITORY.search(folded))
        algeria_class = CLASS_R if concerned else CLASS_NONE
    elif names_algeria:
        algeria_class = CLASS_A1
    elif family == FAMILY_CITIZEN and not territories:
        algeria_class = CLASS_A2
    elif family == FAMILY_COMPOSITE_CITIZEN and not territories:
        algeria_class = CLASS_A3
    else:
        algeria_class = CLASS_NONE
    return DecreeClass(family, territories, algeria_class)


def check_cote(identifier: str, consultation: str) -> CoteCheck:
    """Cote of a decree, read from both ``<unitid>`` types, flagged when it cannot be right.

    The cote sits in ``type="identifiant"`` for 49 inventories and in
    ``type="cote-de-consultation"`` for 35. 260 decrees of 1927 and 1931 read 'BB/11/4xx'
    where the register is 'BB/34/4xx': the value is kept as written, flagged, and the
    probable cote is offered next to it.
    """
    cote, source = (identifier, "identifiant") if identifier else (consultation, "cote-de-consultation")
    cote = cote.strip()
    if not cote:
        return CoteCheck("", "", COTE_MISSING, "")
    wrong_series = _BB11.match(cote)
    if wrong_series:
        return CoteCheck(cote, source, COTE_SUSPECT_BB11, f"BB/34/{wrong_series.group(1)}")
    return CoteCheck(cote, source, COTE_OK, "")
