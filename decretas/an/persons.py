"""Parsing of person-level notices: name, birth, residence, profession, spouse, children.

Three families of notices are covered by one line-by-line state machine:

* F1 "Natnum" (1883-1887, 1913-1927, 1929-1930): ``Naissance : 5 janvier 1841 (Lieu, Dép.)``,
  children as two parallel lists ``A ; B né(e)(s) le d1 ; d2``;
* F2 "collaborative" (1888-1898, 1905, 1909, 1931, and 1932 with its own twists):
  ``Naissance : 21 mai 1848, Lieu, Pays.``, children as ``Prénom (date)``;
* F3 "list" (fragments of 1900-1912, 1928): unlabelled ``Né(e) le …`` lines and
  ``Épouse`` / ``Enfants`` marker lines followed by the name or the list.

Every parsed field keeps the raw text it came from. Nothing is corrected silently:
doubtful values are flagged.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .dates import PRECISION_DAY, find_date
from .text import fold, fold_keep, nfc, squash

ROLE_SPOUSE = "epouse"
ROLE_CHILD = "enfant"
ROLE_SECOND_APPLICANT = "demandeur"   # 'Deuxième demandeur : NOM, Prénoms' (two notices of 1898)
_ADULT_ROLES = (ROLE_SPOUSE, ROLE_SECOND_APPLICANT)   # roles that may be followed by their own birth and residence lines

# Data-entry debris found where the name of a spouse or of a child is expected. Such a "name" is kept
# in the database with its flag and its raw text, but it is not a searchable name occurrence.
NAME_OK = ""
NAME_EMPTY = "vide"                     # nothing, or no word of two letters ('?')
NAME_DOSSIER = "numero-de-dossier"      # '90100 X 20' typed as the spouse's name
NAME_DATE = "date"                      # '3 mai 1871 ; Paul': a date where a given name is expected
NAME_NUMBER = "chiffre"                 # any other digit: 'Lucie 28', '5 enfants'
NAME_LABEL = "libelle-de-champ"         # 'Lieu de résidence : …': the label of another field
NAME_FLAGS: tuple[str, ...] = (NAME_EMPTY, NAME_DOSSIER, NAME_DATE, NAME_NUMBER, NAME_LABEL)

PAIRING_NONE = ""
PAIRING_BY_POSITION = "position"      # 'A ; B né(e)(s) le d1 ; d2': name/date paired by rank, unverified
PAIRING_IMPOSSIBLE = "longueurs-differentes"  # the two lists do not have the same length

_UNSPECIFIED = {"non precise", "non precisee", "inconnu", "inconnue", "?", "s.d", "sans date",
                "non renseigne", "non renseignee"}
_NOT_A_PROFESSION = re.compile(
    r"\b(le|ou|vers|ne|nee|trouvee?|janvier|fevrier|mars|avril|mai|juin|juillet|aout|septembre|octobre|novembre|"
    r"decembre)\b")
_APPROX = re.compile(r"\b(vers|environ|env\.?|presumee?|approximativement)\b")
_BIRTH_WORDS = re.compile(r"\b(le|en|vers|environ|a|au|dans|courant|presumee?|l'annee|ou)\b")
_BORN_PREFIX = re.compile(r"n[ee]e?\s*(?:\(e\))?\s*(?:\(s\))?")
_PARENTS = re.compile(
    r"(?:n[ee]e?s?\s+)?(?:d['e]\s*un\s+|de\s+|d')(?:pere|mere|parents?)\b[^,\[\]()]*"
    r"|[\w' \-]+\(\s*(?:pere|mere|parents?)\s*\)")
_UNLABELLED_BIRTH = re.compile(r"^n[ee]e?\s*(?:\(e\))?\s*(?:(?:le|en|a|vers)\b|(?=\d))")

_PAREN_STATUS = re.compile(
    r"\(\s*(veuve|veuf|divorc[ée]e?|fille|soeur|sœur|fr[èe]re|p[èe]re|fils|m[èe]re|mineure?|épouse|femme)\s*\)", re.I)
_PAREN_PARTICLE = re.compile(
    r"\(\s*(de la|de l'|de|d'|du|des|di|da|del|della|dell'|de los|de las|van der|van den|van de|van|von der|von|"
    r"le|la|el|ten|ter|mac|o')\s*\)", re.I)

_DOSSIER = re.compile(r"(\d[\d ]*?)\s*(bis)?\s*(B?[Xx])\s*(\d{2,4})(?!\d)")

_LABEL = re.compile(r"^([^:]{1,60}?)\s*:\s*(.*)$")
_BIRTH_LABELS = {"naissance"}
_RESIDENCE_LABELS = {"lieu de residence", "residence"}
_PROFESSION_LABELS = {"profession"}
_SPOUSE_LABELS = {"epouse", "epoux", "conjoint", "conjointe"}
_CHILD_LABELS = {"enfants", "enfant(s)", "enfant"}
_ORIGIN_LABELS = {"origine(s) des parents", "origine des parents"}
_SECOND_APPLICANT_LABELS = {"deuxieme demandeur"}
_NOTE_LABELS = {"remarque", "remarques", "a noter", "note", "mention de retrait", "dossier joint"}
_FIELD_LABELS = (_BIRTH_LABELS | _RESIDENCE_LABELS | _PROFESSION_LABELS | _SPOUSE_LABELS | _CHILD_LABELS
                 | _ORIGIN_LABELS | _NOTE_LABELS | _SECOND_APPLICANT_LABELS)
_DOSSIER_ALONE = re.compile(r"\d[\d ]*\s*(?:bis)?\s*B?[Xx]\s*\d{2,4}")


@dataclass(slots=True)
class Birth:
    """A parsed birth statement, next to its raw text."""

    raw: str = ""
    date: str = ""            # 'AAAA-MM-JJ', 'AAAA-MM' or 'AAAA'
    precision: str = ""       # 'jour' | 'mois' | 'annee' | ''
    year: int | None = None
    conventional: bool = False  # '1 janvier', 'présumé', 'vers': compare the year, never the day
    alt_date: str = ""        # corrected date written between square brackets
    place: str = ""           # what follows the date, outer parentheses removed
    parents: str = ""         # '…, de parents espagnols', 'Italie ( père )'
    leak: str = ""            # text found before the date that is not a date word (1892: the profession)


@dataclass(slots=True)
class Name:
    """Indicative split of a name. ``raw`` is what must be displayed and searched."""

    raw: str = ""
    surname: str = ""
    given: str = ""
    maiden: str = ""          # birth name of a married woman ('X née Y', 'Née Y')
    married: str = ""         # husband's name in the 'Y femme X' form
    alias: str = ""           # 'dit', 'dite', 'alias'
    variants: str = ""        # spellings between square brackets
    mention: str = ""         # any other parenthesis
    flags: list[str] = field(default_factory=list)


@dataclass(slots=True)
class Relative:
    """A spouse, a child or a second applicant named inside a person notice: a searchable name occurrence."""

    role: str
    raw: str                  # the whole raw text the relative comes from
    name_raw: str             # the name as written
    name: Name
    birth: Birth
    residence: str = ""
    pairing: str = PAIRING_NONE


@dataclass(slots=True)
class PersonFields:
    """Everything read from the content lines of one person notice."""

    birth: Birth = field(default_factory=Birth)
    residence: str = ""
    residence_from_spouse_line: bool = False   # the only residence line of the notice came after the spouse
    other_residences: list[str] = field(default_factory=list)   # further residence lines of the principal
    profession: str = ""
    profession_from_birth_line: bool = False
    parents_origin: str = ""
    notes: list[str] = field(default_factory=list)
    relatives: list[Relative] = field(default_factory=list)
    unparsed: list[str] = field(default_factory=list)
    line_count: int = 0       # non-empty lines seen


def is_unspecified(value: str) -> bool:
    """True for '', 'non précisé.' and 'non précisé, non précisé, non précisé.' (every component unspecified)."""
    parts = [part.strip(" .;:[]") for part in fold(value).split(",")]
    return all(not part or part in _UNSPECIFIED for part in parts)


def _leak_is_a_profession(leak: str) -> bool:
    """A text found before the birth date is a profession only when it reads like one.

    'journalier' and 'employé de commerce' are; "'" (a stray quote), 'octobre ou' (the first month of
    'octobre ou novembre 1842') and 'trouvée près du Havre le' are not.
    """
    folded = fold(leak)
    if re.search(r"\d", folded) or not re.search(r"[a-z]{3}", folded):
        return False
    return not _NOT_A_PROFESSION.search(folded)


# ----------------------------------------------------------------------------- birth

def _strip_outer_parenthesis(place: str) -> str:
    if not place.startswith("("):
        return place
    depth = 0
    for index, char in enumerate(place):
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                inner, tail = place[1:index], place[index + 1:]
                return (inner + (" " + tail if tail.strip(" .,") else "")).strip()
    return place[1:]


def parse_birth(value: str) -> Birth:
    """Parse the value of a ``Naissance :`` line or a whole ``Né(e) le …`` line."""
    raw = nfc(squash(value))
    birth = Birth(raw=raw)
    if not raw:
        return birth
    folded = fold_keep(raw)
    found = find_date(folded)
    if found is not None:
        birth.date, birth.precision, birth.year = found.iso, found.precision, int(found.iso[:4])
        prefix = _BORN_PREFIX.sub(" ", folded[:found.start])
        approx = bool(_APPROX.search(prefix)) or bool(re.search(r"\b(vers|environ)\b", folded[found.end:found.end + 12]))
        first_of_january = found.precision == PRECISION_DAY and found.iso.endswith("-01-01")
        birth.conventional = approx or first_of_january
        if _BIRTH_WORDS.sub(" ", prefix).strip(" ,;:.-()"):
            birth.leak = raw[:found.start].strip(" ,;:")
        rest = raw[found.end:]
        bracket = re.match(r"\s*\[([^\]]*)\]", folded[found.end:])
        if bracket:
            alternative = find_date(bracket.group(1))
            if alternative is not None:
                birth.alt_date = alternative.iso
                rest = rest[bracket.end():]
    else:
        rest = re.sub(r"^\s*n[ée]e?\s*(\(e\))?\s*(\(s\))?\s*(le|en|à|a)?\s*", "", raw, flags=re.I)
    place = re.sub(r"^[,;:.\s]+", "", rest.strip())
    place = re.sub(r"^(à|a|au|aux|en)\s+", "", place, flags=re.I).strip()
    place = _strip_outer_parenthesis(place).strip(" .;,")
    if is_unspecified(place):
        place = ""
    birth.place = place
    parents = _PARENTS.search(fold_keep(place))
    if parents:
        birth.parents = place[parents.start():parents.end()].strip(" ,")
    return birth


# ----------------------------------------------------------------------------- names

def parse_name(title: str) -> Name:
    """Split 'NOM [née NOM2] [dit X], Prénoms' into indicative parts.

    The comma is not reliable for Arabic and Berber names ('Amar ben Exemple Testaoui',
    'ben Exemple ben Fictif, Amar'): searching must use every word of ``raw``.
    """
    raw = squash(title)
    name = Name(raw=raw)
    if not raw:
        name.flags.append("vide")
        return name
    text = raw
    variants = re.findall(r"\[([^\]]*)\]", text)
    if variants:
        name.variants = " | ".join(v.strip() for v in variants)
        text = re.sub(r"\s*\[[^\]]*\]", "", text)
    status = _PAREN_STATUS.search(text)
    if status:
        text = text[:status.start()] + text[status.end():]
    particle = ""
    postposed = _PAREN_PARTICLE.search(text)
    if postposed:
        particle = postposed.group(1)
        text = text[:postposed.start()] + text[postposed.end():]
        name.flags.append("particule-postposee")
    others = re.findall(r"\(([^()]*)\)", text)
    if others:
        given_in_parens = ("," in text and "(" in text and text.index("(") > text.index(",")
                           and all(re.fullmatch(r"\s*[A-Za-zÀ-ÿ' \-]+\s*", x) and len(x) < 40 for x in others))
        if given_in_parens:
            text = text.replace("(", "").replace(")", "")   # 'FACTICE, (Pierre)' in 1928
            name.flags.append("prenom-entre-parentheses")
        else:
            name.mention = " | ".join(x.strip() for x in others)
            text = re.sub(r"\s*\([^()]*\)", "", text)
    text = squash(text)
    if text.endswith(","):
        name.flags.append("virgule-finale")
        text = text.rstrip(", ")
    text = re.sub(r"\s*,\s*(n[ée]e)\s+", r" \1 ", text, flags=re.I)
    text = re.sub(r"\s*,\s*(dite?|veuve|épouse|alias)\s+", r" \1 ", text, flags=re.I)
    if "," in text:
        left, right = text.split(",", 1)
        right = squash(right.replace(",", " "))
    else:
        left, right = text, ""
        name.flags.append("sans-virgule")
    left = squash(left)
    has_born = re.search(r"\bn[ée]e\b", left, flags=re.I) is not None
    maiden_first = re.search(r"^(.+?)\s+(veuve|épouse|epouse|femme|divorcée)\s+(?!n[ée]e\b)(.+)$", left, flags=re.I)
    if maiden_first and not has_born:
        name.married = maiden_first.group(3).strip()      # 'MODELE femme FACTICE': birth name first
        left = maiden_first.group(1).strip()
        name.flags.append("nom-de-naissance-en-premier")
    else:
        status_word = re.search(r"\b(veuve|épouse|epouse|femme|divorcée)\b\s*", left, flags=re.I)
        if status_word:
            left = squash(left[:status_word.start()] + " " + left[status_word.end():])
    born = re.search(r"\bn[ée]e\b\s*(.*)$", left, flags=re.I)
    if born:
        name.maiden = born.group(1).strip()
        left = left[:born.start()].strip()
        alias_in_maiden = re.search(r"\bdite?\b\s*(.*)$", name.maiden, flags=re.I)
        if alias_in_maiden:
            name.alias = alias_in_maiden.group(1).strip()
            name.maiden = name.maiden[:alias_in_maiden.start()].strip()
    alias = re.search(r"\b(dite?|alias)\b\s*(.*)$", left, flags=re.I)
    if alias:
        name.alias = (name.alias + " " + alias.group(2)).strip()
        left = left[:alias.start()].strip()
    born_after_given = re.search(r"\bn[ée]e\b\s+(.*)$", right, flags=re.I)
    if born_after_given:
        if not name.maiden:
            name.maiden = born_after_given.group(1).strip()
        right = right[:born_after_given.start()].strip()
        name.flags.append("nee-apres-prenoms")
    if particle:
        left = (particle + " " + left).strip()
    if not left and name.maiden:
        left = name.maiden                                   # 'Née Modele, Lucie Jeanne'
        name.flags.append("nom-de-naissance-seul")
    if fold(right) in _UNSPECIFIED or fold(right) in ("sans prenom", "x"):
        right = ""
        name.flags.append("prenom-non-precise")
    name.surname, name.given = left, right
    return name


# ----------------------------------------------------------------------------- spouse, children

_BORN_CLAUSE = re.compile(r",?\s*\bn[ee]e?\s*(?:\(e\))?\s+(?:le|en|a|vers)\b")


def parse_spouse(value: str, role: str = ROLE_SPOUSE) -> Relative:
    """'FACTICE, née MODELE, Lucie, née le 3 mai 1850 à Gênes, Italie.' -> spouse.

    One form of 1895 puts the date where the given name is expected and the place after 'née le':
    'FACTICE, née MODELE, 3 mai 1850, née le Gênes.' The name is then cut at the date, exactly as it is
    when the line has no 'née le' clause; nothing is rewritten, the raw text keeps the line as written.
    """
    raw = nfc(squash(value))
    folded = fold_keep(raw)
    clause = None
    for match in _BORN_CLAUSE.finditer(folded):
        clause = match
    swapped = None
    if clause is not None:
        before = find_date(folded[:clause.start()])
        # strict: the date ends exactly where the clause begins, and no date follows 'née le'
        if (before is not None and not folded[before.end:clause.start()].strip(" ,")
                and not re.match(r"\s*\d", folded[clause.end():])):
            swapped = before
    if swapped is not None:
        name_part, birth_part = raw[:swapped.start], raw[swapped.start:]
    elif clause is not None:
        name_part, birth_part = raw[:clause.start()], raw[clause.start():].lstrip(", ")
    else:
        found = find_date(folded)
        name_part, birth_part = (raw[:found.start], raw[found.start:]) if found else (raw, "")
    name_raw = name_part.strip(" ,.")
    birth = parse_birth(birth_part)
    if swapped is not None:
        birth.place = re.sub(r"^n[ée]e?\s*(?:\(e\))?\s+(?:le|en|à|a|vers)\s+", "", birth.place, flags=re.I)
    return Relative(role=role, raw=raw, name_raw=name_raw, name=parse_name(name_raw), birth=birth)


def name_flag(name_raw: str, raw: str = "") -> str:
    """Flag of a relative's name that is data-entry debris; '' for a name. Strict rules only.

    A name never holds a digit, so any digit is debris: a dossier number, a date, a count. A name
    with no word of two letters is empty. A name that starts with the label of another field is that
    field, not a name. Free-text remarks written without a digit ("attente d'autorisation") are NOT
    detected: nothing is guessed from a vocabulary.
    """
    name = squash(name_raw)
    if _DOSSIER_ALONE.fullmatch(name) or (not name and _DOSSIER_ALONE.fullmatch(squash(raw).strip(" ."))):
        return NAME_DOSSIER
    if not re.search(r"[^\W\d_]{2}", name):
        return NAME_EMPTY if not re.search(r"\d", name) else NAME_NUMBER
    if re.search(r"\d", name):
        return NAME_DATE if find_date(fold_keep(name)) is not None else NAME_NUMBER
    label, _value = _split_label(name)
    if label in _FIELD_LABELS:
        return NAME_LABEL
    return NAME_OK


def _child(name_raw: str, birth_raw: str, raw: str, pairing: str = PAIRING_NONE, *, parse: bool = True) -> Relative:
    birth = parse_birth(birth_raw) if parse else Birth(raw=squash(birth_raw))
    if not birth.date and re.search(r"\d", birth.place):
        birth.place = ""      # an unreadable date ('27 mars 18789') is not a place; the raw text keeps it
    return Relative(role=ROLE_CHILD, raw=raw, name_raw=name_raw, name=Name(raw=name_raw, given=name_raw),
                    birth=birth, pairing=pairing)


def parse_children(value: str) -> list[Relative]:
    """Children of a notice. Children carry given names only.

    * ``A ; B né(e)(s) le d1 ; d2`` -- two parallel lists. The pairing by rank is NOT verified
      (dates are neither ascending nor descending): each child is flagged ``position``; when the
      lists differ in length no date is attributed and every child keeps the whole date list as
      raw text (``longueurs-differentes``).
    * ``Prénom (date[, lieu])`` separated by ',', ';' or a space.
    * bare names, optionally followed by 'né le …'.
    """
    raw = nfc(squash(value))
    if not raw:
        return []
    folded = fold_keep(raw)
    lists = re.search(r"\bn[ee]e?s?\s*\(e\)\s*\(s\)\s*(?:le\b)?", folded)
    if lists:
        names = [squash(x) for x in re.split(r"\s*;\s*", raw[:lists.start()].strip()) if squash(x)]
        dates_raw = raw[lists.end():].strip()
        dates = [squash(x) for x in re.split(r"\s*;\s*", dates_raw) if squash(x)]
        if len(names) == len(dates):
            return [_child(n, d, raw, PAIRING_BY_POSITION) for n, d in zip(names, dates)]
        return [_child(n, dates_raw, raw, PAIRING_IMPOSSIBLE, parse=False) for n in names]
    groups = list(re.finditer(r"([^()]+?)\s*\(\s*([^()]*)\)", raw))
    if groups:
        children: list[Relative] = []
        for group in groups:
            given = squash(group.group(1)).strip(" ;,.")
            given = re.sub(r"^et\s+|\s+et$", "", given).strip(" ;,.")
            children.append(_child(given, group.group(2), squash(group.group(0)).strip(" ;,")))
        return children
    children = []
    for part in (squash(x) for x in re.split(r"\s*;\s*", raw)):
        if not part:
            continue
        found = find_date(fold_keep(part))
        if found is None:
            children.append(_child(part.strip(" ,."), "", part))
            continue
        given = re.sub(r"\s*,?\s*n[ée]e?\s*(?:\(e\))?\s*(le|en)?\s*$", "", part[:found.start], flags=re.I).strip(" ,")
        children.append(_child(given, part[found.start:], part))
    return children


# ----------------------------------------------------------------------------- dossier

def normalise_dossier(raw: str) -> str:
    """'90010 x 92 (numéro du dossier à consulter…)' -> '90010 X 92'; '' when there is no number.

    Accepted forms: 'N X AA', 'NxAA', '10 001 X 93', 'N BX AA', 'Nbis X AA', four-digit year.
    Several numbers in one notice are all kept, joined by ' ; '.
    """
    found: list[str] = []
    for match in _DOSSIER.finditer(raw or ""):
        number = match.group(1).replace(" ", "")
        dossier = f"{number}{' bis' if match.group(2) else ''} {match.group(3).upper()} {match.group(4)}"
        if dossier not in found:
            found.append(dossier)
    return " ; ".join(found)


# ----------------------------------------------------------------------------- content lines

def _split_label(text: str) -> tuple[str, str]:
    """('naissance', value) for 'Naissance : value'; ('', text) when the line has no label."""
    match = _LABEL.match(text)
    if not match:
        return "", text
    label = fold(match.group(1)).strip()
    if label.startswith(("ne(e)", "nee le", "ne le", "nee en", "ne en")):
        return "", text          # 'Né(e) le 10 septembre 1885 (Aubervilliers, Seine : auj. …'
    return label, match.group(2)


def parse_person_lines(lines: list[str]) -> PersonFields:
    """Run the state machine over the content lines of one person notice."""
    out = PersonFields()
    have_birth = False
    have_residence = False
    mode = ""            # '' | 'spouse-name' | 'spouse' | 'children' | 'children-list'
    for line in lines:
        text = nfc(squash(line))
        if not text:
            continue
        out.line_count += 1
        label, value = _split_label(text)
        folded = fold(text)
        last = out.relatives[-1] if out.relatives else None
        # the spouse or the second applicant just named: the next birth and residence lines may be theirs
        last_spouse = last if last is not None and last.role in _ADULT_ROLES else None

        if label in _BIRTH_LABELS or (not label and _UNLABELLED_BIRTH.match(folded)):
            source = value if label else text
            if mode in ("spouse", "spouse-name") and last_spouse is not None and not last_spouse.birth.raw:
                last_spouse.birth = parse_birth(source)       # 1932 and list format: the spouse's own line
            elif not have_birth:
                out.birth, have_birth = parse_birth(source), True
            else:
                out.notes.append(text)
        elif label in _RESIDENCE_LABELS:
            if last_spouse is not None and (mode == "spouse" or have_residence) and not last_spouse.residence:
                last_spouse.residence = value
            elif not have_residence:
                out.residence, have_residence = value, True
            else:
                out.notes.append(text)
                if not is_unspecified(value):
                    out.other_residences.append(value)
        elif label in _PROFESSION_LABELS:
            if not out.profession:
                out.profession = value
            else:
                out.notes.append(text)
        elif label in _SPOUSE_LABELS:
            out.relatives.append(parse_spouse(value))
            mode = "spouse"
        elif label in _CHILD_LABELS:
            out.relatives.extend(parse_children(value))
            mode = "children"
        elif label in _SECOND_APPLICANT_LABELS:
            # 'Deuxième demandeur : NOM, Prénoms', then that person's own 'Naissance' and 'Lieu de résidence'
            out.relatives.append(parse_spouse(value, ROLE_SECOND_APPLICANT))
            mode = "spouse"
        elif label in _ORIGIN_LABELS:
            if mode == "spouse":
                owner = "deuxième demandeur" if last is not None and last.role == ROLE_SECOND_APPLICANT else "épouse"
                out.notes.append(f"({owner}) " + text)
            else:
                out.parents_origin = value
        elif label in _NOTE_LABELS:
            out.notes.append(text)
        elif folded in _SPOUSE_LABELS:
            mode = "spouse-name"
        elif folded in _CHILD_LABELS:
            mode = "children-list"
        elif mode == "spouse-name":
            out.relatives.append(parse_spouse(text))
            mode = "spouse"
        elif mode == "children-list":
            out.relatives.extend(parse_children(text))
        else:
            out.unparsed.append(text)

    if is_unspecified(out.residence):
        out.residence = ""
    if not out.residence:
        # About 470 notices carry ONE residence line, written after the spouse ('Naissance / Épouse / Lieu de
        # résidence'): it is the household's residence, not the spouse's alone. The principal gets it too
        # (the spouse keeps it), and the origin of the value is recorded.
        households = [r.residence for r in out.relatives if r.role == ROLE_SPOUSE and not is_unspecified(r.residence)]
        if households:
            out.residence, out.residence_from_spouse_line = households[0], True
    if is_unspecified(out.profession):
        out.profession = ""
    if not out.profession and out.birth.leak and _leak_is_a_profession(out.birth.leak):
        # 1892: 'journalier, 7 mai 1865, Alger, Alger, Algérie.' -- the profession slipped before the date
        out.profession = out.birth.leak
        out.profession_from_birth_line = True
    return out
