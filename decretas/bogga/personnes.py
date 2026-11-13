"""Person entries: splitting a list into entries and reading what each entry says.

An entry is the text printed for one person inside an admission decree, in one of the
layouts met between 1866 and 1888:

  1866-1868  « 1° Le sieur EXEMPLON (Prénom), né à Ville …, interprète … ; »
  1869-1870  « EXEMPLET (Prénom), indigène israélite, né le … à Ville, interprète … »
  1870-1873  « Testard, Prénom-Composé, suisse, demeurant à Ville. »  (Nom, Prénom, nation, lieu)
  1873-1876  « Testowski (Prénom), polonais, demeurant à Ville. »
  1877-1888  « Testaoui (Amar ben Exemple), indigène monogame, …, né en 1838 à …, demeurant à … »

Nothing is corrected in the text kept for an entry: it stays as the OCR gives it. The
examples of this package are invented names: no real person is quoted in the code.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from decretas.bogga.texte import fold, join_hyphenation, letters, levenshtein

# --- marker bits (field `marqueurs` of the export) -------------------------------------
M_INDIGENE = 1          # the word « indigène » is printed in the entry (OCR-tolerant)
M_MUSULMAN = 2          # « musulman(e) »
M_ISRAELITE = 4         # « israélite »
M_ETRANGER = 8          # « étranger / étrangère » as a status (not « régiment étranger »)
M_NATIONALITE = 16      # a nationality word is printed (see field `nationalite`)
M_INDIGENE_ENTETE = 32  # the decree heading itself says « l'indigène / les indigènes dont … »
M_NATURALISEE = 64      # sub-list « Est / Sont naturalisée(s) Française(s) »
M_REINTEGREE = 128      # sub-list « réintégrée(s) dans la qualité de Française »

# --- flag bits (field `drapeaux` of the export) ----------------------------------------
F_PAGE_CALCULEE = 1         # printed page inferred from neighbouring leaves
F_SUR_DEUX_PAGES = 2        # the entry runs over a page break
F_NOM_INCERTAIN = 4         # no clear end of the name part
F_NON_SEGMENTE = 8          # raw text of a page that could not be cut into entries
F_DECRET_REPUBLIE = 16      # belongs to a decree printed a second time (see `doublon_de`)
F_NAISSANCE_DOUTEUSE = 32   # a birth year is printed but its OCR reading is impossible
F_PEUT_ETRE_FUSIONNEE = 64  # may hold two persons: very long, or two births / two homes
F_DANS_ENTETE = 128         # the person is named inside the decree sentence itself

NATIONALITIES: dict[str, str] = {}
for _base, _forms in {
    "allemand": "allemande", "italien": "italienne", "espagnol": "espagnole", "suisse": "suissesse",
    "belge": "", "marocain": "marocaine", "tunisien": "tunisienne", "badois": "badoise",
    "bavarois": "bavaroise", "prussien": "prussienne", "wurtembergeois": "wurtembergeoise",
    "saxon": "saxonne", "polonais": "polonaise", "anglais": "anglaise", "maltais": "maltaise",
    "hollandais": "hollandaise", "autrichien": "autrichienne", "luxembourgeois": "luxembourgeoise",
    "sarde": "", "russe": "", "hessois": "hessoise", "suedois": "suedoise", "mexicain": "mexicaine",
    "grec": "grecque", "portugais": "portugaise", "danois": "danoise", "napolitain": "napolitaine",
    "sicilien": "sicilienne", "hanovrien": "hanovrienne", "hongrois": "hongroise", "turc": "turque",
    "tripolitain": "tripolitaine", "egyptien": "egyptienne", "americain": "americaine",
    "irlandais": "irlandaise", "norvegien": "norvegienne", "roumain": "roumaine",
    "ottoman": "ottomane", "piemontais": "piemontaise", "toscan": "toscane", "syrien": "syrienne",
    "bresilien": "bresilienne", "nassovien": "nassovienne", "mecklembourgeois": "",
}.items():
    NATIONALITIES[_base] = _base
    NATIONALITIES[_base + "s"] = _base
    if _forms:
        NATIONALITIES[_forms] = _base
        NATIONALITIES[_forms + "s"] = _base

_OPEN = "([{"
_CLOSE = ")]}"
_CAPITAL = "A-ZÀÂÄÇÉÈÊËÎÏÔÖÙÛÜŒÆ"
_LEAD = r"(?P<lead>(?:(?:[^\w(]|_){0,5})(?:[\dlI]{1,3}(?:\s[\dlI])?\s?[^\w\s(]{0,3}\s+)?(?:(?:[^\w(]|_){0,3}))"
_HONORIFIC = r"(?P<hon>(?:[Ll][ea]s?\s+)?(?:s[ij]eurs?|dames?|demoiselles?|veuve|nomm[ée]e?s?)\s+)?"
RE_ENTRY_START = re.compile(
    _LEAD + _HONORIFIC
    + r"(?P<name>[" + _CAPITAL + r"][^\s,;(]{0,29}(?:\s+[^\s,;(]{1,25}){0,9}?)\s?(?P<sep>[,(])"
)
_RE_BOUNDARY = re.compile(r"[.;:]\s+|\n|,\s+")
_RE_ABBREVIATION = re.compile(r"(?:\b(?:St|Ste|S|M|MM|Mme|Mlle|Dr|N|D|J|Ch|Vve|art|Art)|\b[" + _CAPITAL + r"])\.\s*$")
_RE_DANGLING = re.compile(
    r"(?:[-,(]|\b(?:à|a|de|du|des|d|le|la|les|en|au|aux|et|ou|né|née|nés|dit|dite|ben|bent|bou|el|ould|par|près|sur|"
    r"dans|province|commune|canton|département|veuve|épouse|régiment|bataillon|sieur|dame))\s*$",
    re.I)
_RE_LEAD_NUMBER = re.compile(r"^[^\w(]{0,5}([\dlI]{1,3}(?:\s[\dlI])?)\s?[^\w\s(]{0,3}\s")
_RE_NUMBER_LINE = re.compile(r"^(?:\s*\(?[\dlI]{1,3}\s?[^\w\s]{0,2})+\s*$")
ARTICLE_CLAUSE = (r"(?:[pn]ar\s+ap[\w,.]{0,3}-?\s?[\w.]{0,3}-?\s?\w{0,3}-?\s?\w{0,2}tion|en\s+ex[ée]-?\s?cu-?\s?tion|en\s+vertu)\s+"
                  r"de\s+l\W{0,2}ar-?\s?t\w{3,5}\s+\S{1,4}\s+du\s+co\w{2}\s+c[il1]\w{2,3}")
# « Est naturalisée Française : », « Sont réintégrées dans la qualité de Française, par
# application de l'article 18 du Code civil : » — the header of a sub-list. It runs to its
# colon when there is one nearby; otherwise only the words of the formula belong to it.
RE_SUBLIST = re.compile(
    r"^[\W\d]{0,5}(?:Est|Sont|A\s+été|Ont\s+été)\s+(?P<what>na\w{1,3}ralis|r[ée]\w{2,3}[éèe]gr)\w*"
    r"(?:\s+fran\w+|\s+dans\s+la\s+qualit\w+\s+de\s+fran\w+)?"
    r"(?:\s*,?\s*" + ARTICLE_CLAUSE + r")?"
    r"(?:(?=[^:(]{0,60}:)[^:(]{0,60}:)?[\s?,;.:|]*", re.I)
# The end of such a header on its own line (« dans la qualité de Française, par application
# de l'article 18 du Code civil, la nommée : »): everything up to the clause is header.
RE_ARTICLE_CLAUSE = re.compile(
    r"^[^(]{0,60}?" + ARTICLE_CLAUSE + r"[\s,;.:|]*\d?[\s|]*"
    r"(?:(?:la|le|les)\s+(?:nomm\w+|n[eo]m\w+|dames?|sieurs?|ci-apr[èeé]s\s+d[ée]nomm\w+)\s*:\s*)?", re.I)
RE_NOT_A_PERSON = re.compile(
    r"^\W{0,3}(?:D[ée]partement|Division|Province|Territoire)\s|en\s+remplacement|\bLe\s+Chef\s+du\b|\bMinistre\s+de\s+la\b|"
    r"Garde\s+des\s+Sceaux|contre-?\s?sign[ée]|(?:\b[ée]t[ée]|\best|\bsont)\s+nomm[ée]|\bfrancs\b|\barr[êeè]t[ée]\b|\bd[ée]cret\b|\bhectares?\b|"
    r"\best\s+autoris[ée]\s+[àa]\s+[ée]tablir|"
    r"\best\s+autoris|\bmédaille\s+d['’]honneur|\bcirculaire\b|\bMonsieur\b|\bl['’]honneur\b", re.I)
_RE_PERSON_HINT = re.compile(
    r"demeur|\bdem\b|domicili|resid|\bn[e]e?s?\b|\bid\b|\b[1il]d\b|regiment|tirailleur|spahi|soldat|zouave|legion|"
    r"chasseur|bataillon|sujet|\bage\b|originaire|veuve|epouse|femme|interprete|marin|cultivateur|"
    r"proprietaire|negociant|commercant|journalier|macon")
_RE_BIRTH = re.compile(r"\bn[ée]e?s?\b.{0,140}?(?<![\d/])(?:[14](?=[14][5-9]\d\d(?!\d)))?([14][5-9]\d\d)(?!\d)")
_RE_BIRTH_CLAUSE = re.compile(r"\bn[ée]e?\s+(?:le|en|à|vers|au|aux)\b")
_RE_HOME_CLAUSE = re.compile(r"demeu-?\s?rant\s+(?:[àa]|au|aux|en)\b")
_RE_BIRTH_ANY = re.compile(r"\bn[ée]e?s?\b.{0,140}?(?<![\d/])([1-9IlO][\dOoSsIl]\d[\dOoSsIl£$?])(?![\dA-Za-z])")
_RE_RESIDENCE = re.compile(
    r"(?:demeu-?\s?r\w*|domi-?\s?cili\w*|r[ée]sid\w*)\s+(?:à|a|au|aux|en|dans)?\s*(?P<place>[^;]{2,70}?)\s*[.;,]?\s*$")
_RE_Y_DEMEURANT = re.compile(r"\b(?:à|au|aux)\s+(?P<place>[^,;]{2,50}?(?:\s?\([^)]{1,30}\))?),?\s+(?:et\s+)?y\s+(?:demeur|domicili|r[ée]sid)")


_RE_CIVILITY = re.compile(r"^(?:MM?\.|Mmes?\.?|Mlles?\.?)\s+(?=[" + _CAPITAL + r"])")
_RE_HONORIFIC_AFTER_NOISE = re.compile(
    r"^.{0,14}?\b(?:[Ll][ea]s?|[a-z]{2})\s+(?:s[ij]e[un]rs?|dames?|demoiselles?|nomm[ée]e?s?)\s+(?=[" + _CAPITAL + r"])")
_RE_NOISE_BEFORE_NAME = re.compile(r"^[^\s,;(]{1,2},\s+(?=[" + _CAPITAL + r"][^\s,;(]{2,29}(?:\s[^\s,;(]{1,20}){0,2}\s?\()")
_RE_NOISE_AND_NUMBER = re.compile(r"^[^\s,;(\d]{1,3}\s\d{1,3}[.°]\s+(?=[" + _CAPITAL + r"][^\s,;(]{2,29}(?:\s[^\s,;(]{1,20}){0,2}\s?\()")
_RE_Y = re.compile(r"\by\s+(?:demeu|domicili|r[ée]sid)")
_PLACE_WORD = r"(?:[" + _CAPITAL + r"][\w'’.-]*|du|de\s+la|des|el|bou|ben|le|la|les|l['’]\w+)"
_RE_BIRTH_PLACE = re.compile(
    r"\bn[ée]e?s?\b.{0,60}?\b(?:à|au|aux)\s+(?P<place>[" + _CAPITAL + r"][\w'’.-]*(?:[ -]" + _PLACE_WORD
    + r"){0,4}(?:\s?\([^)]{1,30}\))?)")
_RE_COMPLETE_BEFORE_COMMA = re.compile(
    r"(?:demeu-?\s?r\w+\s+(?:à|au|aux|a)\s+[^,;.]{2,45}|y\s+demeu-?\s?r\w+),\s+$")
_RE_HAS_BIRTH_OR_HOME = re.compile(r"\bn[ée]e?\s+(?:le|en|à|vers)\b|demeu|domicili")
_RE_UNIT_HEADER = re.compile(r"^\W{0,4}L[ée]gion\s+[ée]trang[èeé]re\W{0,3}$", re.I)     # « Légion étrangère. Nom (…), … »
_RE_DAMAGED_START = re.compile(r"^[^\w(]{0,3}(?:\S{1,2}\s)?[^\W\d_][^\s,;(]{2,29}\s?\([^)(]{2,60}\)\s?,\s")
_RE_NAME_WITH_FORENAME = re.compile(r"[" + _CAPITAL + r"][^\s,;(]{1,29}(?:\s[^\s,;(]{1,20}){0,3}\s?\([^)(]{2,45}\)\s?,")


@dataclass
class Fragment:
    """A piece of a list between two entry boundaries, with its position in the buffer."""

    start: int
    end: int
    text: str


@dataclass
class Reading:
    """What an entry says, as far as the program can tell."""

    name: str
    markers: int
    nationality: str | None
    birth_year: int | None
    residence: str | None
    flags: int
    number: int | None


def is_noise_line(line: str) -> bool:
    """Page headers, stray marks, library stamps: nothing of a list entry."""
    stripped = line.strip()
    if letters(stripped) < 3:
        return True
    if re.fullmatch(r"\W*[—–_-]+\s*\S{1,6}\s*[—–_-]*\W*", stripped):
        return True
    folded = fold(stripped)
    return folded in {"google", "digitized by", "digitized by google"} or folded.startswith("digitized by")


def is_number_line(line: str) -> bool:
    """A line made only of list numbers pushed into the margin by the OCR."""
    return bool(_RE_NUMBER_LINE.match(line)) and sum(c.isdigit() for c in line) >= 2


def numbers_in_line(line: str) -> list[int]:
    out = []
    for token in re.findall(r"[\dlI]{1,3}", line):
        digits = token.replace("l", "1").replace("I", "1")
        if digits.isdigit():
            out.append(int(digits))
    return out


def split_entries(buffer: str) -> list[Fragment]:
    """Cut a list (lines joined by '\\n') into fragments at entry boundaries.

    A boundary is the end of a sentence or of a line, followed by what looks like the
    start of an entry (optional number, capitalised name, then ',' or '('). No boundary
    after an abbreviation, after a line that visibly continues, or while the current
    fragment has not yet reached its own first ',' or '('.
    """
    starts = [0]
    for match in _RE_BOUNDARY.finditer(buffer):
        position = match.end()
        if position >= len(buffer):
            continue
        if match.group(0).startswith(","):
            # « …, demeurant à Ville, Testarita (Prénom), femme … »: a comma printed for a full stop,
            # also at a line end and with a stray mark before the name (« …, * Nom (Prénom), … »)
            current = buffer[starts[-1]:position]
            complete = _RE_COMPLETE_BEFORE_COMMA.search(buffer[max(0, position - 80):position]) \
                or (_RE_HAS_BIRTH_OR_HOME.search(current) and current.rstrip(", \n").endswith((")", "}")))
            if complete and _RE_NAME_WITH_FORENAME.match(buffer, position + _stray_marks(buffer, position)):
                starts.append(position)
            continue
        if not RE_ENTRY_START.match(buffer, position):
            continue
        current = buffer[starts[-1]:match.start() + 1]
        if _inside_parenthesis(current, buffer[position:position + 45]):
            continue                      # « Nom (Prénom.\nAutre-Prénom), employé … »: one person
        is_header = letters(current) >= 6 and not any(char.islower() for char in current)
        if "," not in current and "(" not in current and not is_header and not _is_parenthesis_tail(current) \
                and not _RE_UNIT_HEADER.match(current):
            continue                      # « Fictlan. Prénom, id. » — but a header in capitals does end
        before = buffer[max(0, match.start() - 30):match.start() + 1]
        if match.group(0) == "\n":
            if _RE_DANGLING.search(buffer[max(0, match.start() - 30):match.start()]):
                continue
        elif _RE_ABBREVIATION.search(before):
            continue
        starts.append(position)
    fragments = []
    for i, start in enumerate(starts):
        end = starts[i + 1] if i + 1 < len(starts) else len(buffer)
        text = buffer[start:end].strip()
        if text:
            fragments.append(Fragment(start, end, text))
    return fragments


def _stray_marks(buffer: str, position: int) -> int:
    """Length of the stray marks the OCR put before a name (« * », « , », « | »)."""
    match = re.compile(r"[^\w(\n]{0,4}").match(buffer, position)
    return match.end() - position if match else 0


def _inside_parenthesis(current: str, following: str) -> bool:
    """The fragment ends inside a parenthesis opened a few words ago, and the following
    text closes it before opening another one."""
    last_open = max(current.rfind(char) for char in _OPEN)
    if last_open < 0 or len(current) - last_open > 60 or any(char in current[last_open:] for char in _CLOSE + "|/"):
        return False
    return bool(re.match(r"[^()\[\]{}\n]{0,40}[)\]}]", following))


def _is_parenthesis_tail(fragment: str) -> bool:
    """« Bas-Rhin). »: only the end of the previous entry, cut off by a line break."""
    words = fragment.split()
    return bool(words) and len(words) <= 4 and ")" in words[0] and "(" not in words[0]


def looks_like_person(text: str) -> bool:
    """Does this fragment read like one person of a list (and not prose or a notice)?"""
    flat = join_hyphenation(text.replace("\n", " "))
    count = letters(flat)
    if count < 8 or count < 0.5 * len(flat) or len(flat) > 520:
        return False
    match = RE_ENTRY_START.match(flat)
    if match is None:
        # « waTestler (Prénom), tailleur, né à … »: the capital is lost but the shape is there
        return bool(_RE_DAMAGED_START.match(flat)) and bool(_RE_HAS_BIRTH_OR_HOME.search(flat)) \
            and not RE_NOT_A_PERSON.search(flat) and not _is_several_persons(flat)
    first = match.group("name").split()[0]
    if ")" in first and "(" not in first:          # the tail of a parenthesis, not a name
        return False
    if RE_NOT_A_PERSON.search(flat) or _is_several_persons(flat):
        return False
    if match.group("hon"):
        return True
    folded = fold(flat)
    if _RE_PERSON_HINT.search(folded):
        return True
    if match.group("sep") == "(" and re.match(r"\([^)\]}]{2,60}[)\]}|/]", flat[match.end() - 1:]):
        return True
    markers, nationality = read_markers(flat)
    if markers or nationality is not None:
        return True
    return _has_list_shape(flat[match.start("name"):])


def _is_several_persons(flat: str) -> bool:
    """Names or nation words of several persons run together (columns mixed up by the OCR)."""
    fields = [field.strip() for field in flat.split(",")]
    capitalised = sum(1 for field in fields[1:] if field[:1].isupper() and len(field.split()) <= 3
                      and not any(char.isdigit() for char in field))
    if capitalised >= 5:
        return True
    nations = sum(1 for token in re.findall(r"[^\W\d_]+", fold(flat))
                  if _nationality_of(token) is not None or _is_indigene(token))
    return nations >= 4


def _has_list_shape(body: str) -> bool:
    """« Nom, Prénom, nation, lieu » with the nation word too damaged to be recognised:
    three to five short comma-separated fields and nothing that reads like a sentence."""
    fields = [field.strip(" .;") for field in body.split(",")]
    if not 3 <= len(fields) <= 5 or len(body.split()) > 12 or any(char.isdigit() for char in body):
        return False
    if any(not 1 <= len(field.split()) <= 5 for field in fields):
        return False
    return fields[0][:1].isupper() and fields[1][:1].isupper()


def _is_indigene(token: str) -> bool:
    folded = fold(token)
    return 6 <= len(folded) <= 10 and levenshtein(folded.rstrip("s"), "indigene", 2) <= 2 and folded[:2] in {"in", "ir", "iu", "1n", "ln"}


def read_markers(text: str) -> tuple[int, str | None]:
    """Marker bits and nationality word of an entry (accents and OCR damage tolerated)."""
    flat = join_hyphenation(text.replace("\n", " "))
    tokens = re.findall(r"[^\W\d_]+", flat)
    folded = [fold(token) for token in tokens]
    markers = 0
    nationality = None
    for i, token in enumerate(folded):
        if _is_indigene(token):
            markers |= M_INDIGENE
        elif len(token) >= 7 and levenshtein(token.rstrip("s").removesuffix("e"), "musulman", 1) <= 1:
            markers |= M_MUSULMAN
        elif len(token) >= 8 and levenshtein(token.rstrip("s"), "israelite", 2) <= 2 and token[0] in "ij1l":
            markers |= M_ISRAELITE
        elif len(token) >= 7 and levenshtein(token.rstrip("s").removesuffix("e").removesuffix("er") + "er", "etranger", 1) <= 1:
            previous = " ".join(folded[max(0, i - 2):i])
            if not re.search(r"regi|legion|bataillon|compagnie", previous):
                markers |= M_ETRANGER
        elif nationality is None:
            nationality = _nationality_of(token)
    if nationality is not None:
        markers |= M_NATIONALITE
    return markers, nationality


_COUNTRIES = frozenset({
    "italie", "espagne", "belgique", "maroc", "tunisie", "prusse", "baviere", "allemagne", "malte", "pologne",
    "autriche", "hollande", "russie", "saxe", "angleterre", "portugal", "grece", "hongrie", "sardaigne", "sicile",
    "suede", "turquie", "egypte", "naples", "tunis", "bade", "hesse", "hanovre", "luxembourg", "danemark",
})


def _nationality_of(folded_token: str) -> str | None:
    """Nationality adjective behind a token ('itslien' -> italien); a country name is not one."""
    if folded_token in NATIONALITIES:
        return NATIONALITIES[folded_token]
    if len(folded_token) < 6 or folded_token in _COUNTRIES:
        return None
    tolerance = 1 if len(folded_token) < 9 else 2
    for form, base in NATIONALITIES.items():
        if len(form) >= 6 and form[0] == folded_token[0] and levenshtein(folded_token, form, tolerance) <= tolerance:
            return base
    return None


def strip_lead(text: str) -> tuple[str, int | None]:
    """Remove list number, bullets and « Le sieur » from the start. Returns (rest, number)."""
    number = None
    match = _RE_LEAD_NUMBER.match(text)
    if match:
        digits = match.group(1).replace(" ", "").replace("l", "1").replace("I", "1")
        number = int(digits) if digits.isdigit() else None
    sub_list = RE_SUBLIST.match(text)
    if sub_list and sub_list.end() < len(text):       # « Est naturalisée Française, la nommée Nom (…) »
        text = text[sub_list.end():]
    honorific = _RE_HONORIFIC_AFTER_NOISE.match(text)
    if honorific:                                     # « F4 4. Le sieur Nom (…) »: marks before the honorific
        return _RE_CIVILITY.sub("", text[honorific.end():].strip()), number
    start = RE_ENTRY_START.match(text)
    if start is None:
        return text.strip(), number
    body = text[start.start("name"):].strip()
    noise = _RE_NOISE_BEFORE_NAME.match(body) or _RE_NOISE_AND_NUMBER.match(body)
    if noise:                                         # « A, Nom (Prénom), … », « L 4. Nom (Prénom), … »: stray marks
        body = body[noise.end():]
    return _RE_CIVILITY.sub("", body), number


def sub_list_status(text: str) -> int:
    """Marker carried by an entry that opens on a sub-list header (0 when it does not)."""
    sub_list = RE_SUBLIST.match(text)
    if sub_list is None:
        return 0
    return M_REINTEGREE if re.search(r"[éèe]gr", sub_list.group("what"), re.I) else M_NATURALISEE


_NAME_PARTICLES = frozenset({"ben", "bent", "bou", "bel", "el", "ould", "ou", "de", "di", "da", "du", "dit", "dite",
                             "y", "van", "von", "née", "nee", "veuve", "fils", "aîné", "père"})


def _name_end(text: str) -> tuple[int, bool]:
    """Index where the name part ends; second value False when no clear separator was found.

    The name runs to the first comma outside parentheses. A parenthesis the OCR never
    closed does not swallow the rest: « Nom (Prénom, caporal au … » ends at that comma.
    A status word right after a closed parenthesis (« Nom (Prénom) étranger … ») ends it too.
    """
    depth = 0                       # 0 or 1: a second « ( » inside a parenthesis is OCR noise
    for i, char in enumerate(text):
        if char in _OPEN:
            depth = 1
        elif depth and (char in _CLOSE or (char in "|/\\" and text[i + 1:i + 2] in {",", " ", ""})):
            depth = 0
            following = re.match(r"[.:]?\s+([^\W\d_]+)", text[i + 1:])     # « Nom (Prénom). soldat … »
            if following and following.group(1)[:1].islower() and following.group(1) not in _NAME_PARTICLES:
                return i + 1, True
        elif char in ",;":
            if depth == 0:
                return i, True
            ahead = text[i + 1:i + 61]
            closing = min((ahead.find(c) for c in _CLOSE + "|" if c in ahead), default=-1)
            if closing < 0 or not _only_forenames(ahead[:closing]):
                return i, True              # the parenthesis is never closed: stop here
    marker = re.search(r"\s(?:indig\w+|[ée]trang\w+|isra\w+|musulm\w+|n[ée]e?\s+(?:à|a|le|en|vers|dans)|demeur\w+|sujet)\b", text)
    if marker:
        return marker.start(), True
    period = text.find(". ")
    if 0 < period < 60:
        return period, True
    return min(len(text), 60), False


def _only_forenames(inside: str) -> bool:
    """« Alda, Ugolina, Marcella »: what stands between a comma and the closing parenthesis
    is made of forenames only (capitalised words and name particles)."""
    tokens = re.findall(r"[^\W\d_]+", inside)
    return bool(tokens) and not any(char.isdigit() for char in inside) and all(
        token[:1].isupper() or fold(token) in _NAME_PARTICLES for token in tokens)


def read_name(body: str) -> tuple[str, bool]:
    """Name part as written, parentheses kept: 'Testaoui (Amar ben Exemple)'.

    In the « Nom, Prénom, nation, lieu » layout the forename field is part of the name:
    'Testard, Prénom-Composé'. Returns (name, certain).
    """
    flat = join_hyphenation(body.replace("\n", " "))
    end, certain = _name_end(flat)
    name = flat[:end].strip(" .,;:-—")
    rest = flat[end:].lstrip(" ,;") if end < len(flat) else ""
    fields = [field.strip() for field in rest.split(",")]
    if "(" not in name and len(fields) >= 2 and _looks_like_forename(fields[0]) and _is_status_field(fields[1]):
        name = f"{name}, {fields[0]}"
    return name, certain and bool(name)


def _looks_like_forename(field: str) -> bool:
    tokens = field.split()
    if not 1 <= len(tokens) <= 4 or any(char.isdigit() for char in field):
        return False
    if not field[:1].isupper() or _is_status_field(field):
        return False
    return all(token[:1].isupper() or fold(token) in {"ben", "bent", "bou", "el", "ould", "de", "di", "da", "van", "von"}
               for token in tokens)


def _is_status_field(field: str) -> bool:
    folded = fold(field)
    if re.match(r"^(?:id|[1il]d|sujet|indig|etrang|isra|musulm|nee?\b|veuve|epouse|femme)", folded):
        return True
    first = re.findall(r"[^\W\d_]+", folded)[:2]
    return any(_nationality_of(token) is not None or _is_indigene(token) for token in first)


def read_birth_year(text: str, volume_year: int) -> tuple[int | None, bool]:
    """Birth year when printed after « né(e) ». Returns (year or None, doubtful).

    '4859' is read 1859 (digit 1 read as 4). A year that cannot be a birth year for a
    person of this volume (after the volume, or more than 100 years before) is rejected
    and reported as doubtful rather than passed on.
    """
    flat = join_hyphenation(text.replace("\n", " "))
    match = _RE_BIRTH.search(flat)
    if match:
        year = int("1" + match.group(1)[1:])
        if volume_year - 100 <= year <= volume_year - 10:
            return year, False
        return None, True
    return None, bool(_RE_BIRTH_ANY.search(flat))


def read_residence(text: str) -> str | None:
    """Place after « demeurant à » / « domicilié à », or the birth place for « y demeurant »."""
    flat = join_hyphenation(text.replace("\n", " ")).strip()
    same = _RE_Y_DEMEURANT.search(flat)
    if same:
        return same.group("place").strip(" .,")
    if _RE_Y.search(flat):
        born = _RE_BIRTH_PLACE.search(flat)
        return born.group("place").strip(" .,") if born else None
    match = _RE_RESIDENCE.search(flat)
    if match:
        place = match.group("place").strip(" .,")
        return place or None
    return _list_layout_place(flat)


def _list_layout_place(flat: str) -> str | None:
    """« Nom, Prénom, nation, lieu. »: the last field is the place when it reads like one."""
    fields = [part.strip(" .;") for part in flat.split(",")]
    if not 3 <= len(fields) <= 5 or len(flat.split()) > 14 or re.search(r"\bn[ée]e?\b", flat):
        return None
    last = fields[-1]
    if not last[:1].isupper() or any(char.isdigit() for char in last) or len(last.split()) > 4 or _is_status_field(last):
        return None
    return last


def _second_name_after_punctuation(body: str) -> bool:
    """« …, à Val-Fictif, Autre (Prénom), badois, … »: a second name follows a comma or a
    full stop and is itself followed by a trade or a nation. A place (« né à Ville, Région
    (Pays), le … ») or a husband (« femme Nom (Prénom), née … ») is not one."""
    for match in _RE_NAME_WITH_FORENAME.finditer(body):
        before = body[:match.start()]
        after = re.match(r"\s*([^\W\d_]+)", body[match.end():])
        if match.start() <= 12 or not re.search(r"[.,;]\s+\W{0,3}$", before) or after is None:
            continue
        if fold(after.group(1)) in _AFTER_A_PLACE:
            continue
        if re.search(r"(?:femme|veuve|[ée]pouse|dite?|et|de|du)\W{0,3}\s*$", before.rstrip(" .,;")):
            continue
        return True
    return False


_AFTER_A_PLACE = frozenset({"le", "la", "en", "demeurant", "demeu", "y", "ne", "nee", "de", "et", "a", "au", "canton",
                            "commune", "departement", "province", "arrondissement", "domicilie", "domiciliee"})


def read_entry(text: str, volume_year: int) -> Reading:
    """Everything the export keeps about one entry."""
    body, number = strip_lead(text)
    name, certain = read_name(body)
    markers, nationality = read_markers(body)
    markers |= sub_list_status(text)
    birth_year, doubtful = read_birth_year(body, volume_year)
    flags = 0
    if not certain or not name[:1].isupper():
        flags |= F_NOM_INCERTAIN
    if doubtful:
        flags |= F_NAISSANCE_DOUTEUSE
    if len(body.split()) > 75 or len(_RE_BIRTH_CLAUSE.findall(body)) >= 2 or len(_RE_HOME_CLAUSE.findall(body)) >= 2 \
            or _second_name_after_punctuation(body):
        flags |= F_PEUT_ETRE_FUSIONNEE      # two births, two homes or a second « Nom (Prénom), »: two persons run together
    return Reading(name=name, markers=markers, nationality=nationality, birth_year=birth_year,
                   residence=read_residence(body), flags=flags, number=number)
