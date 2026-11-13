"""Person-level hints. A hint orders and explains; it is never a fact and never a filter.

One hint per person notice, with the rule that produced it:

* ``M`` probable Muslim Algerian (an "indigène" in the vocabulary of the period): born in Algeria, or
  born elsewhere of parents the notice calls Algerian;
* ``N`` born in Algeria, nothing else known;
* ``E`` probable European foreigner (born in Europe, or of declared foreign parents);
* ``T`` Moroccan or Tunisian (born in Morocco or Tunisia, or of declared Moroccan or Tunisian parents);
* ``L`` legionnaire (profession);
* ``I`` undetermined (including a person born outside Algeria of Algerian parents, without a name marker:
  the rule ``parents-algeriens+…`` says so and the notice enters the Algeria tier).

Limits measured on 2026-11-11: the count of ``M`` is the size of a heuristic class, not a
count of persons admitted; Jewish families of Algeria and of the M'zab are sometimes caught
by the Muslim markers. Markers of a Jewish name are used here ONLY to hold back the hint
``M``; no such class is produced or published.
"""
from __future__ import annotations

import re
from typing import NamedTuple

from . import gazetteer, names, persons
from .text import fold

HINT_MUSLIM_ALGERIAN = "M"
HINT_BORN_IN_ALGERIA = "N"
HINT_EUROPEAN = "E"
HINT_MOROCCAN_TUNISIAN = "T"
HINT_LEGIONNAIRE = "L"
HINT_UNDETERMINED = "I"

HINT_LABELS: dict[str, str] = {
    HINT_MUSLIM_ALGERIAN: "musulman algérien probable (« indigène » de l'époque)",
    HINT_BORN_IN_ALGERIA: "né en Algérie, sans autre indice",
    HINT_EUROPEAN: "étranger européen probable (né en Europe, ou de parents étrangers)",
    HINT_MOROCCAN_TUNISIAN: "Marocain ou Tunisien probable (né au Maroc ou en Tunisie, ou de parents marocains ou tunisiens)",
    HINT_LEGIONNAIRE: "légionnaire",
    HINT_UNDETERMINED: "indéterminé",
}

_MUSLIM_GIVEN = """mohamed mohammed mohand mhamed mahomed mehemed mahmoud ahmed hamed hamid hamida hamou hammou ali amar
ammar omar abdelkader kader abdallah abdellah abdelaziz abderrahmane abderrahman abdesselam abdelhamid abdelmalek
abdelouahab larbi lakhdar lakdar belkacem kacem kaci kassem said saad saadi sadek seddik salah saleh slimane sliman
tahar taieb tayeb rabah rabia ramdane ramdan rachid rezki arezki akli amokrane amrane mokrane meziane idir yahia
youcef youssef brahim braham ibrahim ismail smail smain khelifa khelil khalil kouider kaddour lahcen lahcene hocine
hacene hassen hassan hussein mustapha mostefa moktar mokhtar mouloud miloud messaoud mabrouk embarek mbarek mebarek
bachir boualem boudjema bouzid cherif chabane chaabane djilali djelloul djillali driss dris aissa moussa mouss haroun
nacer nasser noureddine othmane otmane osman zoubir zidane ziane benaissa bouziane ameur amor ferhat laid belaid
lounes lounis mehdi mahdi fatma fatima fathma aicha khadidja kheira zohra halima yamina meriem zineb baya ouardia
tassadit djouher fatiha houria saliha messaouda mebarka rahma rabha safia hadda aldjia dahbia ghalia cherifa
zoulikha khedidja""".split()
_HELD_BACK_GIVEN = """isaac jacob moise abraham salomon david mardochee haim judas elie simon samuel nessim chaloum
joseph esther rachel semha sultana reine messaouda rebecca sarah meyer aaron ruben benjamin ephraim israel josue
eliaou makhlouf maklouf amram mimoun chemouel yaacob ichoua""".split()
_HELD_BACK_SURNAME = """cohen levy levi bensoussan benichou benhaim zaoui touboul darmon dahan dayan amsellem benhamou
benayoun sebbag sebban tordjman chouraqui abitbol azoulay bensimon lascar karsenty kalfon attali nahon elbaz toledano
benguigui bensaid bentolila medioni teboul zerbib partouche benzaken ohayon amar azoulai benisti sarfati benamou zekri
hayoun hanoun gozlan sellam atlan boutboul""".split()

_MUSLIM_GIVEN_KEYS = frozenset(names.k1(word) for word in _MUSLIM_GIVEN)
_HELD_BACK_GIVEN_KEYS = frozenset(names.k1(word) for word in _HELD_BACK_GIVEN)
_HELD_BACK_SURNAME_KEYS = frozenset(names.k1(word) for word in _HELD_BACK_SURNAME)
_FILIATION = frozenset({"ben", "bent", "ould", "bint", "oulid"})

_PARENTS_ALGERIAN = re.compile(
    r"(pere|mere|parents?)\s+(indigenes?\s+)?alg[a-z]*rien|parents?\s+indigenes?|pere\s+indigene"
    r"|algerie\s*\(\s*de\s+parents\s+algeriens|algerie\s*\(\s*(pere|mere|parents?)\s*\)")
_PARENTS_FOREIGN = re.compile(
    r"espagnol|italien|maltais|allemand|belge|suisse|etranger|marocain|tunisien|anglais|grec|autrichien|polonais|"
    r"russe|luxembourgeois")
_PARENTS_FRENCH = re.compile(r"\bfrancais")
_PARENTS_COUNTRY_FORM = re.compile(r"\(\s*(pere|mere|parents?)\s*\)")
_PARENTS_MAGHREB = re.compile(r"marocain|tunisien|\bmaroc\b|\btunisie\b")
_LEGION = re.compile(r"legion etrangere|regiment etranger|legionnaire")
_EUROPE = ("espagne", "italie", "malte", "allemagne", "alsace-lorraine", "belgique", "suisse", "france")


class Hint(NamedTuple):
    code: str
    rule: str           # readable rule, e.g. 'ne-en-algerie(explicite)+prenom-musulman'
    born_in_algeria: str   # '' | 'explicite' | 'repertoire'
    lives_in_algeria: str  # '' | 'explicite' | 'repertoire'
    algerian_parents: bool = False   # the notice calls the parents Algerian ('de père algérien')


def birth_place_proper(birth_place: str, birth_parents: str) -> str:
    """The birth place without its clause on the parents.

    'Tunis, Tunisie, de père algérien' and 'Tunis, Algérie ( père ) [Tunisie]' are births in Tunisia: the
    word naming Algeria belongs to the parents. The bracket of the second form is the country of birth
    and stays ('Alger, Espagne ( parents ) [Algérie]' is a birth in Algeria).
    """
    if birth_parents and birth_parents in birth_place:
        return birth_place.replace(birth_parents, " ", 1)
    return birth_place


def _muslim_markers(name_tokens: list[str], text: str, parents_algerian: bool) -> list[str]:
    markers: list[str] = []
    if any(names.k1(token) in _MUSLIM_GIVEN_KEYS for token in names.expand(name_tokens)):
        markers.append("prenom-musulman")
    if any(token in _FILIATION for token in name_tokens):
        markers.append("filiation")
    if re.search(r"indigene|musulman", text):
        markers.append("mention-indigene")
    if parents_algerian:
        markers.append("parents-algeriens")
    return markers


def _held_back(name: str, name_tokens: list[str], text: str, has_muslim_given: bool) -> bool:
    """True when a marker of a Jewish family name or given name holds back the hint ``M``.

    The family-name list is compared with the family names only -- surname, birth name, husband's
    name -- so that 'AMAR, Isaac' is held back while 'Testaoui, Amar ben Exemple' is not (Amar is
    there a given name). A name written without a comma is taken whole.
    """
    if re.search(r"israelite|rabbin|juif|consistoire", text):
        return True
    parsed = persons.parse_name(name)
    surname_tokens = names.tokens(" ".join((parsed.surname, parsed.maiden, parsed.married)))
    if {names.k1(token) for token in names.expand(surname_tokens)} & _HELD_BACK_SURNAME_KEYS:
        return True
    keys = {names.k1(token) for token in names.expand(name_tokens)}
    return bool(keys & _HELD_BACK_GIVEN_KEYS) and not has_muslim_given


def classify_person(*, name: str, birth_place: str, birth_parents: str, parents_origin: str, residence: str,
                    profession: str, other_text: str, decree_admits: bool,
                    safe_localities: frozenset[str], other_residences: tuple[str, ...] = ()) -> Hint:
    """Hint of one person notice, from its own text and the class of its decree."""
    place = birth_place_proper(birth_place, birth_parents)
    born = gazetteer.algeria_rule(place, safe_localities)
    lives = gazetteer.algeria_rule(residence, safe_localities)
    for other in other_residences:      # a second residence line of the same person (1890)
        lives = lives or gazetteer.algeria_rule(other, safe_localities)
    name_tokens = names.tokens(name)
    text = fold(" ".join((profession, other_text, birth_place, parents_origin)))
    parents_text = fold(" ".join((birth_parents, parents_origin, birth_place)))
    parents_algerian = bool(_PARENTS_ALGERIAN.search(parents_text))
    parents_declared = bool(birth_parents or parents_origin) and not parents_algerian
    parents_foreign = parents_declared and (
        bool(_PARENTS_FOREIGN.search(parents_text))
        # Natnum form 'Alger, Espagne ( parents ) [Algérie]': the parents' country is named, not an adjective.
        or (bool(_PARENTS_COUNTRY_FORM.search(fold(birth_parents)))
            and (gazetteer.names_other_country(birth_parents) or bool(gazetteer.country_of(birth_parents)))))
    parents_french = parents_declared and not parents_foreign and bool(_PARENTS_FRENCH.search(parents_text))
    markers = _muslim_markers(name_tokens, text, parents_algerian)
    held_back = _held_back(name, name_tokens, text, "prenom-musulman" in markers)
    name_markers = [marker for marker in markers if marker in ("prenom-musulman", "filiation")]
    country = "algerie" if born else gazetteer.country_of(place)

    def hint(code: str, rule: str) -> Hint:
        return Hint(code, rule, born, lives, parents_algerian)

    if born and not parents_foreign and not parents_french and markers and not held_back:
        return hint(HINT_MUSLIM_ALGERIAN, f"ne-en-algerie({born})+" + "+".join(markers))
    if not born and parents_algerian:
        # 'Tunis, Tunisie, de père algérien': an Algerian subject born outside Algeria. With a name marker
        # the hint is M; without one nothing more is said than what the notice says.
        origin = f"parents-algeriens+ne-{country or 'ailleurs'}"
        if name_markers and not held_back:
            return hint(HINT_MUSLIM_ALGERIAN, origin + "+" + "+".join(name_markers))
        return hint(HINT_UNDETERMINED, origin)
    if country in ("maroc", "tunisie"):
        return hint(HINT_MOROCCAN_TUNISIAN, f"ne-{country}")
    # Declared foreign parents: European most of the time, Moroccan or Tunisian when the notice says so.
    foreign_code = (HINT_MOROCCAN_TUNISIAN
                    if _PARENTS_MAGHREB.search(fold(" ".join((birth_parents, parents_origin)))) else HINT_EUROPEAN)
    if born and parents_foreign:
        return hint(foreign_code, f"ne-en-algerie({born})+parents-etrangers")
    if born and parents_french:
        return hint(HINT_BORN_IN_ALGERIA, f"ne-en-algerie({born})+parents-francais")
    if born:
        return hint(HINT_BORN_IN_ALGERIA, f"ne-en-algerie({born})")
    if _LEGION.search(text):
        return hint(HINT_LEGIONNAIRE, "profession-legion")
    if parents_foreign:
        # 'Lyon, Rhône, France, de parents italiens': the country of birth is France, not Italy.
        return hint(foreign_code, (f"ne-{country}+" if country else "") + "parents-etrangers")
    if country in _EUROPE:
        return hint(HINT_EUROPEAN, f"ne-{country}")
    # Birth place absent or not recognised: a weaker hint, and the rule says so. It needs a name marker,
    # no other country named anywhere, and either a residence in Algeria or a decree whose title is
    # Algerian (A1) or an admission to citizen's rights (A2) -- never a collective rejection.
    elsewhere = (bool(country) or gazetteer.names_other_country(place)
                 or gazetteer.names_other_country(residence) or bool(gazetteer.country_of(residence)))
    if name_markers and not held_back and not elsewhere and (lives or decree_admits):
        context = "reside-en-algerie" if lives else "decret-algerie"
        return hint(HINT_MUSLIM_ALGERIAN,
                    "lieu-de-naissance-non-reconnu+" + "+".join(name_markers) + f"+{context}")
    return hint(HINT_UNDETERMINED, "aucune-regle")
