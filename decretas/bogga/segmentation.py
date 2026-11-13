"""Segmentation of a volume into admission decrees and person entries.

A decree is recognised by its *formula* — « ont été admis(es) à jouir des droits de
citoyen français », « qui admet à jouir des droits … » — read with tolerance for OCR
damage, and never by the title « NATURALISATION » alone. One exception is documented:
the 1868 volume prints its decrees under « DÉCRETS DE NATURALISATION EN ALGÉRIE » with
one « N° 14. — Décret du 5 juin 1867. » line per decree and no formula at all; there a
decree is accepted on the dated « Décret du … » line *and* the person entries under it.

The text of a list is never rewritten. What cannot be cut into entries is kept as
"unsegmented" text attached to its page, and the page is reported for manual reading.
"""
from __future__ import annotations

import re
from bisect import bisect_right
from dataclasses import dataclass, field

from decretas.bogga import dates, livraisons, personnes
from decretas.bogga.texte import fold, join_hyphenation, letters, levenshtein, squeeze
from decretas.bogga.volume import Page

# ---------------------------------------------------------------- patterns
_DROITS = r"(?:d[eéè]s\s+d[rt].{0,2}[il1]t?[es]?|de\s+la\s+qualit[ée])"
_A_JOUIR = r"\s+(?:[àaâáù]|ii|[il1])\W{0,2}\s?[JjIil1]?\W?o[un]?[il1tï]{0,2}r\W{0,3}\s+" + _DROITS
_CONFERES = r"dr.{0,2}[il1]ts?\s+de\s+c[il1][tl]oyens?\s+fran\w+\s+ont\s+[ée]t[ée]\s+conf[ée]r[ée]s?"
# « a été / ont été / à été » before « naturalisé(e)s » and « réintégré(e)s ». « Est / Sont
# naturalisée(s) » alone is the header of a sub-list, not a decree — unless the sentence
# opens on « Par décret … » (see RE_FORMULA_DAMAGED).
_AUXILIARY = r"(?:\ba|à|\bont)\s*\S{2,4}"
_NATURALISES = _AUXILIARY + r"\s+na\w{1,3}ralis[ée]e?s?\s+fran[cç]ais"
_REINTEGRES = _AUXILIARY + r"\s+r[ée]-?\s?int[éèe]gr[ée]e?s?\s+dans\s+la\s+qualit[ée]"
RE_FORMULA = re.compile(
    r"(?<![êe]tre\s)(?<![êe]tre\s\s)"
    r"(?:(?:\ba[d9]?\W{0,2}\s?[mw][il1][st]\W?\s?(?:e|es)?|\badmet|\badmettent|\bappel[ée]e?s?)" + _A_JOUIR
    + r"|" + _CONFERES + r"|(?P<nat>" + _NATURALISES + r")|(?P<reint>" + _REINTEGRES + r"))", re.I)
# When a sentence opens on « Par décret … » and the verb of the formula is beyond
# recognition, the object of the sentence is enough to know what the decree does. Without
# it the decree would not be opened and its persons would be given to the decree printed
# before, with that decree's date.
RE_FORMULA_DAMAGED = re.compile(
    r"dr.{0,2}[il1]ts?\s+de\s+c[il1][tl]oyens?\s+fran|qualit[ée]\s+de\s+c[il1][tl]oyens?\s+fran"
    r"|(?P<nat>na\w{1,3}ralis[ée]e?s?\s+fran[cç]ais)"
    r"|(?P<reint>r[ée]-?\s?int[éèe]gr[ée]e?s?\s+dans\s+la\s+qualit[ée])", re.I)
NATURE_ADMISSION, NATURE_NATURALISATION, NATURE_REINTEGRATION, NATURE_TITRE = "admission", "naturalisation", "reintegration", "titre"
# Any sentence about the rights of a French citizen in a decree sentence: used to report
# what the strict formula may have missed, never to open a decree.
RE_FORMULA_LOOSE = re.compile(
    r"dr.{0,2}[il1]ts?\s+de\s+(?:c[il1][tl]oyen|fran[cç]ais)|qualit[ée]\s+de\s+(?:c[il1][tl]oyen|fran[cç]ais)|"
    r"naturalis[ée]e?s?\s+fran[cç]ais", re.I)
_RE_WORD_5_8 = re.compile(r"[^\W\d_]{5,8}")
_RE_PAR_WORD = re.compile(r"\b(?:[PFp]ar|P[eu]r)\W{0,2}\s?(?:divers\s+)?(?P<word>[^\W\d_]{5,8})\b")
_RE_PAR_PRESIDENTIEL = re.compile(r"\b(?:[PFp]ar|P[eu]r)\W{0,2}\s?\S{2,6}\s?\S{0,4}\s+(?:pr[ée]s[il]d|[il]mp[ée]r[il])")
_RE_NEW_SENTENCE = re.compile(
    r"(?<=[.;:])\s+(?=(?:[PF]ar|P[eu]r)\s+\S{2,6}\s?\S{0,4}\s+(?:pr[ée]s[il]d|[il]mp[ée]r[il]|du\s+\d|en\s+date))")
_RE_PAR_DECREE_START = re.compile(r"^\W{0,4}[PF][aeu]r\b")
_RE_D_WORD = re.compile(
    r"\b(?:Un\s+)?(?P<word>[Dd][^\W\d_]{4,7})\s+(?:imp[ée]ri|pr[ée]sid|du\s|des\s|en\s+date)")
_RE_SAME_DATE = re.compile(r"\bm[êe]me\s+(?:jour|date)\b|\b[Ll]e\s+m[êe]me\s+d[ée]cret\b")
_RE_DATED_INTRO = re.compile(r"d[ée]\w{3,5}s?\b.{0,40}?\b(?:du|des|en\s+date\s+d[un])\s+\d", re.I)
RE_ARTICLE = re.compile(
    r"^\W{0,4}N\s?[°'’*o.:º»«\"^-]{0,2}\s*(?P<no>[\dA-Za-z%$(&£§]{1,5}(?:\s?bis)?)\s*[.,:]?\s*[—–-]+\s*(?P<rest>.*)$")
RE_TITLE_ONLY = re.compile(r"^\W{0,3}(?:D[ÉE]CRETS?\s+DE\s+)?NATURALISATIONS?(?:\s+EN\s+ALG[ÉE]RIE)?\W*$", re.I)
RE_NATURALISATION = re.compile(r"NATURAL|Naturalis", re.I)
_SUB_NUMBER = r"(?<![^\W\d_])[A-Za-z]{1,2}\s?[°'’*o.:º\d]{0,3}\s*[\dA-Za-z%$&£§]{1,5}\s*[.,]?\s*[—–_-]+\s*"
_RE_SUB_PREFIX = re.compile(r"^\W{0,3}(?:" + _SUB_NUMBER + r")?")
_RE_SUB_INSIDE = re.compile(
    r"(?:" + _SUB_NUMBER + r"|[—–_-]+\s*|(?<=[.;:,])\s+(?:\S{1,2}\s+){0,3})(?P<word>[^\W\d_][\wéÉèÈ@$&]{3,8})\s*:?\s+"
    r"[DdPpBbLl][UuEe][Ss]?\s+\S{1,4}\s+[A-Za-zéûôèêÉÛ]{3,10}\.?\s+[14Il]{1,2}\s?[5-9SsOo$]\S{2}")
_RE_SUB_BODY = re.compile(
    r"(?P<word>[^\W\d_][\wéÉèÈ@$&]{3,8})\s*:?\s+(?:[DdPpBbLl][UuEe][Ss]?|en\s+date\s+du)\s+"
    r"(?P<date>(?:\S{1,4}\s+(?:et\s+)?){1,3}?(?P<month>[A-Za-zéûôèêÉÛ]{3,10})\.?(?:[\s-]+[14Il]{1,2}\s?[5-9SsOo$]\S{2})?)"
    r"\s*[.,:;]?\s*(?P<rest>.*)$")
# Upper-case headers anywhere in a line; « Département d'Alger » only alone on its line.
RE_DEPARTMENT = re.compile(
    r"(?:(?P<kind>[DP][ÉEÈ]PARTEMENT|DIVISION|PROVINCE|TERRITOIRE|SUBDIVISION)|"
    r"^\W{0,3}(?P<kind2>D[ée]partement|Division|Province|Territoire)(?=.{0,60}$))\s+"
    r"(?:MILITAIRE\s+)?[Dd]\s?[EUeu'’\"^]?\s?[’'\"^ -]?\s?(?:[Ll][’' ]\s?)?(?P<name>[A-ZÉa-zé][\wéÉ-]{3,12})\.?")
_RE_INLINE_DEPARTMENT = re.compile(
    r"^\W{0,3}(?P<kind>D[^\W\d_]{9,11}|Division|Province)\s+\(?(?:[dD]\W{0,2}|T)\s?(?P<name>[A-ZÉa-zé][\w-]{1,11}(?:\s[a-z]{2})?)"
    r"[,.]?\s+(?:\d{1,3}\W{0,4}\s+)?[^\w(]{0,4}"
    r"(?=[A-ZÉ][^\s,;(]{1,29}(?:\s[^\s,;(]{1,20}){0,2}\s?\()")
_RE_DEPARTMENT_LINE = re.compile(
    r"^\W{0,3}(?P<kind>[^\W\d_]{7,12})\s+\(?[dD]\W{0,2}[eEuU]?\W{0,2}\s?(?P<name>[A-ZÉa-zé][\w-]{2,11}(?:\s[a-z]{2})?)\W{0,3}$")
RE_INLINE_AFTER = re.compile(
    r"(?:[Ff]ran[cç]aise?s?\s*[,:;.]?\s+(?P<who>(?:[Ll][ea]s?\s+(?:s[ij]eurs?|dames?|demoiselles?|nomm[ée]e?s?)|MM?\.)\s+.{8,})"
    r"|\b(?:au|aux|à\s+la)\s+(?P<who2>(?:s[ij]eurs?|dames?|demoiselles?|nomm[ée]e?s?)\s+.{8,}))$", re.S)
_RE_AFTER_HONORIFIC = re.compile(r"^((?:[Ll][ea]s?\s+)?(?:s[ij]eurs?|dames?|demoiselles?|nomm[ée]e?s?))\s*[:|.\s]+")
MARK_DEPARTMENT = "\x01"
MARK_STATUS = "\x02"
PAGE_BREAK = "\f"
RE_SUBLIST = personnes.RE_SUBLIST
RE_CLOSER = re.compile(
    r"^\W{0,3}(?:Par\s+(?:arr[êèe]t|d[ée]cision|ordonnance|jugement)|ARR[ÊE]T[ÉE]S?\b|D[ÉE]CRET\s*[.:]?$|"
    r"L[ea]\s+(?:Gouverneur|Pr[ée]sident|Ministre|Mar[ée]chal|Directeur|Conseiller|Secr[ée]taire|G[ée]n[ée]ral|Pr[ée]fet)|"
    r"Vu\s|ART(?:ICLE)?\.?\s?\d|Fait\s+[àa]\s|Sign[ée]\s?:|CIRCULAIRE|RAPPORT\b|ERRAT|Monsieur\s|NAPOL[ÉE]ON|"
    r"LOI\b|Consid[ée]rant|AU\s+NOM|TABLE\b|Pour\s+(?:copie|extrait|ampliation)|Alger,\s+le\s|"
    r"Ont\s+été\s+(?:nomm|promu)|Sont\s+(?:nomm|promu)|Est\s+(?:nomm|promu))",
    re.I)
_RE_LEGAL_START = re.compile(r"^\W{0,3}(?:Vu\s|ART(?:ICLE)?\b|Consid[ée]rant|Attendu|Sur\s+le\s+rapport|TITRE\b)", re.I)
_RE_KEPT_CAPITALS = re.compile(r"INDIG|[ÉE]TRANG|MILITAIRE|L[ÉE]GION|TIRAILLEUR|SPAHI|ZOUAVE|TERRITOIRE|FEMME|ENFANT|"
                               r"NATURALIS|D[ÉE]CRET|R[ÉE]INT[ÉE]GR|DIVISION|D[ÉE]PARTEMENT|PROVINCE|CERCLE|SUBDIVISION|ALGER|ORAN|CONSTANTINE")
_LIST_HEADER_WORDS = ("departement", "division", "province", "territoire", "subdivision", "naturalisation",
                      "indigenes", "etrangers", "militaires", "constantine", "decret", "decrets")
RE_ANNOUNCED = re.compile(r"\bles\s+(\d{1,3})\s+personnes", re.I)
RE_HEADING_INDIGENE = re.compile(r"\b(?:l['’]\s?|les\s+)indig\w{2,5}\s+(?:dont|ci-|d[ée]sign|suivant)", re.I)
RE_HEADING_END = re.compile(
    r"(?:d[ée]sign[ée]e?s?|d[ée]nomm[ée]e?s?|nomm[ée]s\s+et\s+d[ée]sign[ée]s?|suivent|suit|sieurs|dames|"
    r"[Ff]ran[cç]aise?s?|1865)\s*[:;.]\s*")
RE_INLINE_BEFORE = re.compile(
    r"(?P<who>(?:\b[Ll][ea]s?\s+(?:s[ij]eurs?|dames?|demoiselles?|nomm[ée]e?s?)|\bMM?\.(?!\s+[LlIÎ1][ea]s?\b))\s+"
    r"(?=[A-ZÉÈ]).{6,400}?),?\s+"
    r"(?:(?:a|à|ont)\s+[ée][tl][ée]|est|sont)\s+(?:ad|appel)",
    re.S)
RE_TRAILING_DATE = re.compile(r"[—–-]\s*(?P<place>[A-Z][\w-]{2,20}(?:[- ]\s?[A-Z][\w-]+)?),\s+(?:le\s+)?(?P<date>\d.{6,30}?)\.?\s*$")

DEPARTMENTS = ("alger", "oran", "constantine")


# ---------------------------------------------------------------- results
@dataclass
class Entry:
    """One person entry. `raw` is the OCR text of the entry, lines joined by a space."""

    raw: str
    name: str
    leaf: int
    page: int | None
    markers: int
    nationality: str | None
    birth_year: int | None
    residence: str | None
    flags: int
    number: int | None = None
    department: str | None = None


@dataclass
class Decree:
    """One admission decree as published. `dates` are the decree dates named by the
    heading (several for « des 5 et 16 décembre 1872 »), each with its state."""

    kind: str                       # "formule" or "titre" (1868 layout)
    nature: str                     # admission, naturalisation, reintegration, titre
    heading: str
    leaf: int
    page: int | None
    page_computed: bool
    article: str | None
    dates: list[tuple[str | None, int]] = field(default_factory=list)   # (ISO or None, state)
    date_raw: str = ""
    issue: livraisons.Issue | None = None
    entries: list[Entry] = field(default_factory=list)
    announced: int | None = None
    last_number: int | None = None
    heading_indigene: bool = False
    duplicate_of: int | None = None
    last_leaf: int = 0
    ocr_dates: list[dates.OcrDate] = field(default_factory=list, repr=False)
    margin_numbers: list[int] = field(default_factory=list, repr=False)

    @property
    def date_state(self) -> int:
        return max((state for _iso, state in self.dates), default=dates.SUSPECT)


@dataclass
class Unsegmented:
    """Text of a decree page that could not be cut into entries."""

    leaf: int
    page: int | None
    text: str
    decree_index: int


@dataclass
class ManualPage:
    leaf: int
    page: int | None
    decree_index: int
    reason: str
    letters_total: int
    letters_in_entries: int


@dataclass
class Segmentation:
    decrees: list[Decree]
    issues: list[livraisons.Issue]
    unsegmented: list[Unsegmented]
    manual_pages: list[ManualPage]
    body_first_leaf: int
    body_last_leaf: int
    formula_hits: list[int]         # leaves of the body where the formula was read
    formula_hits_outside: list[int]  # ... of which no decree covers
    table_leaves: list[int] = field(default_factory=list)   # tables printed between two parts of the body


@dataclass
class _Line:
    text: str
    page: Page
    index: int


@dataclass
class _Context:
    """State while reading one naturalisation article: one heading, one or more decrees."""

    kind: str
    heading: str
    leaf: int
    page: Page
    article: str | None
    heading_dates: list[dates.OcrDate]
    decrees: list[Decree] = field(default_factory=list)
    current: Decree | None = None
    by_date: dict[tuple[int | None, int], Decree] = field(default_factory=dict)
    nature: str = NATURE_ADMISSION
    base_status: int = 0
    buffer: list[_Line] = field(default_factory=list)
    department: str | None = None
    status: int = 0
    heading_indigene: bool = False


# ---------------------------------------------------------------- small helpers
def _is_decree_word(word: str) -> bool:
    """« décret(s) » within two OCR errors: déeret, Jécret, décrel, decrets."""
    folded = fold(word)
    return levenshtein(folded.rstrip("s"), "decret", 2) <= 2 and folded[-1:] in {"t", "l", "s", "r"}


def has_decree_word(text: str) -> bool:
    return any(_is_decree_word(match.group(0)) for match in _RE_WORD_5_8.finditer(text))


def decree_intro(text: str, *, at_start: bool = False) -> bool:
    """Does the text hold « Par décret … » / « Décret impérial du … » (OCR-tolerant)?

    `at_start`: only within the first characters of the text (start of a new act)."""
    limit = 3 if at_start else len(text)
    loose = _RE_PAR_PRESIDENTIEL.search(text)             # « Par déc et présidentiel »: the word itself is lost
    if loose and loose.start() <= limit:
        return True
    for pattern in (_RE_PAR_WORD, _RE_D_WORD):
        for match in pattern.finditer(text):
            if match.start() > limit:
                break
            if at_start and pattern is _RE_D_WORD and not match.group(0)[:1].isupper():
                continue
            if _is_decree_word(match.group("word")):
                return True
    return False


def find_formula(text: str) -> re.Match[str] | None:
    """The admission formula of a decree sentence: the strict form, or — only in a sentence
    that opens on « Par décret … » — its object alone when the OCR destroyed the verb."""
    strict = RE_FORMULA.search(text)
    if strict is not None:
        return strict
    if _RE_PAR_DECREE_START.match(text) and decree_intro(text, at_start=True):
        return RE_FORMULA_DAMAGED.search(text)
    return None


def has_formula(text: str) -> bool:
    return find_formula(join_hyphenation(text)) is not None


def is_foreign_title(text: str) -> bool:
    """A title in capitals that is not part of a list of persons (« PENSIONS CIVILES. »)."""
    if letters(text) < 12 or len(text.split()) < 2 or any(char.islower() for char in text):
        return False
    if _RE_KEPT_CAPITALS.search(text):
        return False
    tokens = re.findall(r"[^\W\d_]{6,}", fold(text))          # « DÉPYRTEMENT D'ALFER » is still a list header
    return not any(levenshtein(token, word, 2) <= 2 for token in tokens for word in _LIST_HEADER_WORDS)


def match_sub_decree(text: str) -> tuple[str, str] | None:
    """Recognise « N° 72. — Décret du 30 novembre 1867. » (number and word may be damaged).

    Returns (date text, rest of the line) or None. The rest, when present, must start an
    entry: « Décret du 11 janvier 1868. EXEMPLA (Prénom), étranger … ».
    """
    prefix = _RE_SUB_PREFIX.match(text)
    body = _RE_SUB_BODY.match(text, prefix.end() if prefix else 0)
    if body is None:
        return None
    word = re.sub(r"[^a-z@$&]", "", fold(body.group("word"))).rstrip("s")
    distance = levenshtein(word, "decret", 2)
    has_year = bool(re.search(r"[14Il]{1,2}\s?[5-9SsOo$]\S{2}\W*$", body.group("date")))
    if distance > 2 or (dates.month_of(body.group("month")) is None and not (distance <= 1 and has_year)):
        return None
    rest = body.group("rest").strip(" )]}|:;.,*—–-")
    if len(rest) <= 3 and letters(rest) <= 2:
        rest = ""                               # « Décret du 4 août 1883 à »: a stray mark, not an entry
    if rest and not RE_DEPARTMENT.match(rest) and not (len(rest) > 20 and personnes.RE_ENTRY_START.match(rest)):
        return None
    return body.group("date"), rest


def _raw_of(found: list[dates.OcrDate]) -> str:
    """OCR text of the dates of a heading, without repeating the compact form."""
    raws: list[str] = []
    for item in found:
        if not any(item.raw in other for other in raws):
            raws = [other for other in raws if other not in item.raw] + [item.raw]
    return "; ".join(raws)


def _is_department_word(token: str) -> bool:
    folded = fold(token)
    return levenshtein(folded, "departement", 3) <= 3 or any(levenshtein(folded, word, 2) <= 2 for word in ("division", "province"))


def department_name(token: str) -> str:
    folded = fold(token)
    for name in DEPARTMENTS:
        if levenshtein(folded, name, 3) <= (1 if len(name) < 6 else 3):
            return name
    return folded


def body_range(pages: list[Page], issues: list[livraisons.Issue]) -> tuple[int, int]:
    """Leaves that hold the issues themselves: from the first issue opening to the tables
    printed after the last issue (or to the end of the volume when no table is found)."""
    if not issues:
        return 0, len(pages) - 1
    opens = [issue.open_leaf for issue in issues if issue.open_leaf is not None]
    first = min(opens) if opens and min(opens) < issues[0].close_leaf else 0
    last = len(pages) - 1
    for page in pages[issues[-1].close_leaf + 1:]:
        if livraisons.RE_TABLE_PAGE.search(squeeze(page.text[:400])):
            last = page.leaf - 1
            break
    return first, max(last, issues[-1].close_leaf)


def table_leaves_inside(pages: list[Page], issues: list[livraisons.Issue], first: int, last: int) -> list[int]:
    """Leaves of the tables printed inside the body (1870: the tables come before the
    « partie supplémentaire »): from a table heading to the next issue title page."""
    if not issues:
        return []
    out: list[int] = []
    in_table = False
    for page in pages[max(first, issues[0].close_leaf + 1):last + 1]:
        if livraisons.is_issue_title_page(page.text):
            in_table = False
        elif livraisons.RE_TABLE_PAGE.search(squeeze(page.text[:400])):
            in_table = True
        if in_table:
            out.append(page.leaf)
    return out


def _clean_lines(page: Page) -> list[str]:
    return [squeeze(line) for line in page.text.split("\n") if line.strip()]


def _heading_tail(heading: str) -> tuple[str, str]:
    """Split a heading line at the end of the formula sentence: (heading, rest of the line)."""
    formula = find_formula(heading)
    if formula is None:
        return heading, ""
    inline = RE_INLINE_AFTER.search(heading, formula.end())
    if inline:
        group = "who" if inline.group("who") else "who2"
        who = _RE_AFTER_HONORIFIC.sub(r"\1 ", inline.group(group).strip())     # « le sieur : | Nom (…) »
        return heading[:inline.start(group)].strip(), who
    end = None
    for match in RE_HEADING_END.finditer(heading, formula.end()):
        end = match.end()
        if heading[match.start():match.end()].rstrip().endswith(":"):
            break
    if end is None or len(heading) - end < 12:
        return heading, ""
    return heading[:end].strip(), heading[end:].strip()


def _not_the_senatus_consulte(found: list[dates.OcrDate], text: str) -> list[dates.OcrDate]:
    """Drop « 14 juillet 1865 » — also when the OCR damaged its day or year ('44 juillet
    1855'): a date printed right after « Sénatus-Consulte du » is never the decree's."""
    kept = []
    for date in found:
        position = text.find(date.raw)
        after_consulte = position >= 0 and re.search(r"onsul\S{0,4}\W{0,3}\s*d\S{0,3}\s*$", text[max(0, position - 24):position])
        if after_consulte or (date.year == 1865 and date.month == 7):
            continue
        kept.append(date)
    return kept


def _decree_dates_of(heading: str) -> list[dates.OcrDate]:
    """Decree dates named before the formula (the 1865 sénatus-consulte date is not one)."""
    formula = find_formula(heading)
    cut = formula.start() if formula else len(heading)
    counter = re.search(r"contre-?\s?s[il]gn|rendus?\s+(?:en|sur)|\(contre", heading[:cut], re.I)
    zone = heading[:counter.start()] if counter else heading[:cut]
    word = next((match for match in _RE_WORD_5_8.finditer(zone) if _is_decree_word(match.group(0))), None)
    if word is not None:
        # « ARRÊTÉS DES 6 ET 14 MARS 1888 [Par] décret présidentiel du 6 mars 1888 … »: a date
        # printed before the word « décret » belongs to the title of another act.
        zone = zone[word.start():]
    found = _not_the_senatus_consulte(dates.find_dates(zone), zone)
    if not found and _RE_DATED_INTRO.search(zone):
        # « Par décret présidentiel, en date du 13 février, contresigné … »: no year printed
        found = [d for d in dates.find_dates(zone, allow_bare=True) if d.year is None]
    if not found and formula:
        # « du 10 novembre dernier » is handled by find_dates itself; here the date stands
        # between « contresigné » and the formula.
        found = _not_the_senatus_consulte(dates.find_dates(heading[:cut]), heading[:cut])
    if not found:
        damaged = dates.find_damaged_date(zone)      # « du 2t octobre 1876 »: kept, day unknown
        found = [damaged] if damaged is not None else []
    return found


# ---------------------------------------------------------------- the reader
class _Reader:
    """Line-by-line state machine over the body of a volume."""

    def __init__(self, pages: list[Page], volume_year: int, issues: list[livraisons.Issue]) -> None:
        self.pages = pages
        self.year = volume_year
        self.issues = issues
        self.decrees: list[Decree] = []
        self.unsegmented: list[Unsegmented] = []
        self.page_letters: dict[tuple[int, int], list[int]] = {}   # (decree idx, leaf) -> [total, in entries]
        self.context: _Context | None = None
        self.article: str | None = None
        self.armed_title = False        # a « NATURALISATION » title was just read (1868 layout)

    # ---- driving
    def run(self, first_leaf: int, last_leaf: int, skip: frozenset[int] = frozenset()) -> None:
        lines: list[_Line] = []
        for page in self.pages[first_leaf:last_leaf + 1]:
            if page.leaf in skip or livraisons.is_issue_title_page(page.text):
                lines.append(_Line(PAGE_BREAK, page, -1))      # a title page closes any context
                continue
            for index, text in enumerate(_clean_lines(page)):
                for part in _RE_NEW_SENTENCE.split(text):      # a decree sentence printed right after an entry
                    lines.append(_Line(part, page, index))
        i = 0
        while i < len(lines):
            i = self._step(lines, i)
        self._close()

    def _step(self, lines: list[_Line], i: int) -> int:
        """Handle line i; return the index of the next line to read."""
        line = lines[i]
        text = line.text
        if text == PAGE_BREAK:
            self._close()
            self.armed_title = False
            return i + 1
        if personnes.is_noise_line(text):
            if self.context is not None and self.context.current is not None and personnes.is_number_line(text):
                self.context.current.margin_numbers.extend(personnes.numbers_in_line(text))
            return i + 1
        certified = livraisons.find_closing(text)
        if certified is not None:
            if self.context is not None and certified > 20:
                self._content(_Line(text[:certified], line.page, line.index))
            self._close()
            self.armed_title = False
            return i + 1
        article = RE_ARTICLE.match(text)
        body = article.group("rest") if article else text
        if article:
            self.article = article.group("no")
        after_heading = self._try_heading(lines, i, body, after_article=article is not None)
        if after_heading is not None:
            return after_heading
        if (self.context is not None or self.armed_title) and match_sub_decree(text) is not None:
            self._sub_decree(line)
            return i + 1
        if article:
            is_title = bool(RE_NATURALISATION.search(body[:60]))
            fresh = self.context is not None and self.context.kind == "formule" and not self.context.buffer \
                and not any(decree.entries for decree in self.context.decrees)
            if not (is_title and fresh):        # a title the OCR read after its own sentence is ignored
                self._close()
                self.armed_title = is_title
            return i + 1
        if RE_TITLE_ONLY.match(text):
            self.armed_title = True
            return i + 1
        if self.context is None:
            if not RE_NATURALISATION.search(text):
                self.armed_title = False
            return i + 1
        if RE_CLOSER.match(text) or (decree_intro(text, at_start=True) and not RE_FORMULA_LOOSE.search(text)) \
                or is_foreign_title(text):
            self._close()
            return i + 1
        self._content(line)
        return i + 1

    def _content(self, line: _Line) -> None:
        """Buffer a line of a list, isolating department headers, sub-lists and dated sub-headings."""
        context = self.context
        if context is None:
            return
        position = 0
        for match in RE_DEPARTMENT.finditer(line.text):
            self._piece(_Line(line.text[position:match.start()], line.page, line.index))
            if self.context is not None:
                self.context.buffer.append(_Line(MARK_DEPARTMENT + department_name(match.group("name")), line.page, line.index))
            position = match.end()
        self._piece(_Line(line.text[position:], line.page, line.index))

    def _piece(self, line: _Line) -> None:
        context = self.context
        text = line.text.strip()
        if context is None or not text:
            return
        if match_sub_decree(text) is not None:
            self._sub_decree(_Line(text, line.page, line.index))
            return
        inside = next((found for found in _RE_SUB_INSIDE.finditer(text, 1)
                       if match_sub_decree(text[found.start("word"):]) is not None), None)
        if inside is not None:
            if is_foreign_title(text[:inside.start("word")].rstrip(" —–_-.")):
                self._close()                  # « PENSIONS CIVILES. — DÉCRET DU 27 JUIN 1877. »: another act
                return
            self._piece(_Line(text[:inside.start()], line.page, line.index))
            self._piece(_Line(text[inside.start("word"):], line.page, line.index))
            return
        if personnes.is_noise_line(text):
            return
        alone = _RE_DEPARTMENT_LINE.match(text)
        if alone and _is_department_word(alone.group("kind")):
            # « DÉPARTEMEriT D'ORAN », « Départemenê d'Oran. »: a header the strict pattern does not know
            context.buffer.append(_Line(MARK_DEPARTMENT + department_name(alone.group("name")), line.page, line.index))
            return
        inline = _RE_INLINE_DEPARTMENT.match(text)
        if inline and levenshtein(fold(inline.group("kind")), "departement", 2) > 2 \
                and fold(inline.group("kind")) not in {"division", "province"}:
            inline = None
        if inline:
            context.buffer.append(_Line(MARK_DEPARTMENT + department_name(inline.group("name")), line.page, line.index))
            text = text[inline.end():]
        sub_list = RE_SUBLIST.match(text)
        if sub_list:
            status = personnes.sub_list_status(text)
            context.buffer.append(_Line(MARK_STATUS + str(status), line.page, line.index))
            text = text[sub_list.end():].strip()
            if not text:
                return
        clause = personnes.RE_ARTICLE_CLAUSE.match(text)
        if clause:                              # end of a sub-list header cut by a line break
            text = text[clause.end():].strip()
            if not text:
                return
        context.buffer.append(_Line(text, line.page, line.index))

    # ---- events
    def _try_heading(self, lines: list[_Line], i: int, first_text: str, after_article: bool = False) -> int | None:
        """If a decree sentence starts on line i, open it and return the next line index."""
        if _RE_LEGAL_START.match(first_text):
            return None
        opening = find_formula(join_hyphenation(first_text))
        # « Ont été admis à jouir … » directly under a title or after an article number
        titled = opening is not None and opening.start() < 20 and (self.armed_title or after_article)
        if not (decree_intro(first_text) or titled or (has_formula(first_text) and has_decree_word(first_text))):
            return None
        look = first_text
        j = i
        used = [lines[i]]
        while not has_formula(look) and j + 1 < len(lines) and len(used) < 5:
            nxt = lines[j + 1]
            if nxt.text == PAGE_BREAK or RE_ARTICLE.match(nxt.text) or decree_intro(nxt.text, at_start=True) \
                    or livraisons.find_closing(nxt.text) is not None:
                break
            if _is_entry_line(nxt.text) and not has_formula(look + " " + nxt.text):
                break
            j += 1
            if personnes.is_noise_line(nxt.text):
                continue
            used.append(nxt)
            look = look + " " + nxt.text
        look = join_hyphenation(look)
        if not has_formula(look):
            resumed = self._resume_heading(lines, j)
            if resumed is None:
                return None
            j = resumed
            used.append(lines[j])
            look = join_hyphenation(look + " " + lines[j].text)
        formula = find_formula(look)
        if formula is None or not (titled or has_decree_word(look[:formula.start()]) or decree_intro(look[:formula.start()])):
            return None
        # the sentence may run on the following line(s) until its colon
        while not RE_HEADING_END.search(look, formula.end()) and j + 1 < len(lines) and len(used) < 7 \
                and not RE_INLINE_AFTER.search(look, formula.end()) and not RE_INLINE_BEFORE.search(look):
            nxt = lines[j + 1]
            if nxt.text == PAGE_BREAK or RE_ARTICLE.match(nxt.text) or RE_DEPARTMENT.search(nxt.text) \
                    or match_sub_decree(nxt.text) is not None or _is_entry_line(nxt.text) \
                    or livraisons.find_closing(nxt.text) is not None or RE_CLOSER.match(nxt.text) \
                    or decree_intro(nxt.text, at_start=True):
                break
            j += 1
            if personnes.is_noise_line(nxt.text):
                continue
            used.append(nxt)
            look = join_hyphenation(look + " " + nxt.text)
        heading, tail = _heading_tail(look)
        found = _decree_dates_of(heading)
        if not found:
            found = self._dates_announced_above()
        if not found and not after_article:
            found = _dated_title_above(lines, i)
        if not found:
            found = self._dates_of_the_decree_before(heading, lines[i].page.leaf)
        self._open("formule", heading, lines[i], found)
        context = self.context
        assert context is not None
        inline = RE_INLINE_BEFORE.search(heading)
        if inline and personnes.RE_NOT_A_PERSON.search(inline.group("who")):
            inline = None                       # « contresigné par M. le Garde des Sceaux, … a été admis »
        if inline and context.current is not None:
            self._add_entry(context, context.current, squeeze(inline.group("who")), lines[i].page, lines[i].page,
                            extra_flags=personnes.F_DANS_ENTETE)
        if tail:
            self._content(_Line(tail, used[-1].page, used[-1].index))
        return j + 1

    def _dates_announced_above(self) -> list[dates.OcrDate]:
        """« DÉCRET DU 28 NOVEMBRE 1883 » printed as a title just above an undated sentence."""
        context = self.context
        if context is None or context.kind != "titre" \
                or any(not line.text.startswith((MARK_DEPARTMENT, MARK_STATUS)) for line in context.buffer):
            return []
        last = context.decrees[-1] if context.decrees else None
        if last is None or last.entries:
            return []
        return list(last.ocr_dates)

    def _dates_of_the_decree_before(self, heading: str, leaf: int) -> list[dates.OcrDate]:
        """« Par décret du même jour … », « Par décret de la même date … », « Par le même
        décret … »: the date is the one of the decree printed just before, when that
        decree has exactly one date. It is reported as re-established, not as read."""
        formula = find_formula(heading)
        zone = heading[:formula.start()] if formula else heading[:160]
        if not _RE_SAME_DATE.search(zone) or not self.decrees:
            return []
        before = self.decrees[-1]
        if not 0 <= leaf - max(before.leaf, before.last_leaf) <= 1 or len(before.ocr_dates) != 1:
            return []
        date = before.ocr_dates[0]
        return [dates.OcrDate(date.day, date.month, date.year, f"même jour que le décret précédent ({date.raw})",
                              True, date.relative, date.ambiguous)]

    def _resume_heading(self, lines: list[_Line], j: int) -> int | None:
        """A decree sentence cut by entries the OCR read out of order: find the line that
        resumes it (« été admises à jouir … ») within the next few lines. The entries
        skipped on the way are handed to the list that was open before."""
        skipped: list[_Line] = []
        for k in range(j + 1, min(j + 9, len(lines))):
            candidate = lines[k]
            if candidate.text == PAGE_BREAK or RE_ARTICLE.match(candidate.text) or decree_intro(candidate.text, at_start=True):
                return None
            if personnes.is_noise_line(candidate.text):
                continue
            formula = RE_FORMULA.search(join_hyphenation(candidate.text))
            if formula and formula.start() < 40:
                for line in skipped:
                    self._content(line)
                return k
            if not _is_entry_line(candidate.text):
                return None
            skipped.append(candidate)
        return None

    def _open(self, kind: str, heading: str, line: _Line, found: list[dates.OcrDate]) -> None:
        self._close()
        context = _Context(kind=kind, heading=heading, leaf=line.page.leaf, page=line.page, article=self.article,
                           heading_dates=found, heading_indigene=bool(RE_HEADING_INDIGENE.search(heading)))
        formula = find_formula(heading)
        if kind == "titre":
            context.nature = NATURE_TITRE
        elif formula is not None and formula.group("nat"):
            context.nature, context.base_status = NATURE_NATURALISATION, personnes.M_NATURALISEE
        elif formula is not None and formula.group("reint"):
            context.nature, context.base_status = NATURE_REINTEGRATION, personnes.M_REINTEGREE
        context.status = context.base_status
        self.context = context
        self.armed_title = False
        if kind == "formule" and (found or not re.search(r"ci-\s?apr[èe]s\s+mentionn", heading, re.I)):
            context.current = self._new_decree(context, line.page, found, heading)

    def _new_decree(self, context: _Context, page: Page, found: list[dates.OcrDate], heading: str) -> Decree:
        announced = RE_ANNOUNCED.search(context.heading)
        decree = Decree(kind=context.kind, nature=context.nature, heading=heading[:600], leaf=page.leaf, page=page.printed,
                        page_computed=page.computed, article=context.article,
                        date_raw=_raw_of(found),
                        announced=int(announced.group(1)) if announced else None,
                        heading_indigene=context.heading_indigene, last_leaf=page.leaf,
                        issue=livraisons.issue_for_leaf(self.issues, page.leaf), ocr_dates=list(found))
        context.decrees.append(decree)
        self.decrees.append(decree)
        return decree

    def _sub_decree(self, line: _Line) -> None:
        """« N° 72. — Décret du 30 novembre 1867. » or « Décret du 14 décembre » inside a list.

        What follows the title on the same line (« Décret du 7 juillet 1883. DÉPARTEMENT DE
        CONSTANTINE Nom (…), … Décret du 11 juillet 1883. ») is read only once the decree
        of the title is the current one: it may itself hold the next dated title."""
        date_text, rest = match_sub_decree(line.text) or (line.text, "")
        title = line.text[:len(line.text) - len(rest)].strip() if rest else line.text
        found = dates.find_dates(date_text, allow_bare=True)
        if self.context is None:
            self._open("titre", title, line, [])
        context = self.context
        assert context is not None
        self._flush(context)
        if RE_ARTICLE.match(line.text):
            context.article = self.article
        self._switch_to_sub_decree(context, line, title, date_text, found)
        if rest:
            self._content(_Line(rest, line.page, line.index))

    def _switch_to_sub_decree(self, context: _Context, line: _Line, title: str, date_text: str,
                              found: list[dates.OcrDate]) -> None:
        named = {(h.day, h.month): h for h in context.heading_dates}
        if context.kind == "formule" and found and (found[0].day, found[0].month) in named:
            # a per-date sub-list of a heading that names several decrees
            key = (found[0].day, found[0].month)
            if key not in context.by_date:
                resolved = [named.get((d.day, d.month), d) for d in found]
                first = context.decrees[0] if context.decrees else None
                if first is not None and not first.entries and not context.by_date:
                    first.ocr_dates = resolved          # reuse the decree opened by the heading
                    first.date_raw = _raw_of(resolved)
                    context.by_date[key] = first
                else:
                    context.by_date[key] = self._new_decree(context, line.page, resolved, context.heading)
            context.current = context.by_date[key]
            return
        heading = title if context.kind == "titre" else f"{context.heading} — {title}"
        opened = context.current
        if context.kind == "formule" and opened is not None and not opened.entries and not opened.ocr_dates \
                and len(context.decrees) == 1:
            opened.ocr_dates = list(found)              # the undated sentence gets its date here
            opened.date_raw = _raw_of(found) if found else squeeze(date_text)
            opened.heading = heading[:600]
            return
        context.current = self._new_decree(context, line.page, found, heading)
        if not found:
            context.current.date_raw = squeeze(date_text)

    def _close(self) -> None:
        if self.context is None:
            return
        context = self.context
        self._flush(context)
        for decree in context.decrees:
            numbers = [entry.number for entry in decree.entries]
            decree.last_number = _last_list_number(numbers, decree.margin_numbers, len(decree.entries))
        self.context = None

    # ---- lists
    def _flush(self, context: _Context) -> None:
        """Cut the buffered lines into entries of the current decree."""
        lines, context.buffer = context.buffer, []
        if not any(not line.text.startswith((MARK_DEPARTMENT, MARK_STATUS)) for line in lines):
            for line in lines:
                self._apply_mark(context, line.text)
            return
        decree = context.current
        if decree is None:
            if context.kind != "formule":
                return
            first = next(line for line in lines if not line.text.startswith((MARK_DEPARTMENT, MARK_STATUS)))
            decree = self._new_decree(context, first.page, context.heading_dates, context.heading)
            context.current = decree
        chunk: list[_Line] = []
        for line in lines:
            if line.text.startswith((MARK_DEPARTMENT, MARK_STATUS)):
                self._emit(context, decree, chunk)
                chunk = []
                self._apply_mark(context, line.text)
            else:
                chunk.append(line)
        self._emit(context, decree, chunk)

    @staticmethod
    def _apply_mark(context: _Context, mark: str) -> None:
        if mark.startswith(MARK_DEPARTMENT):
            context.department = mark[1:]
            context.status = context.base_status
        elif mark.startswith(MARK_STATUS):
            context.status = int(mark[1:])

    def _emit(self, context: _Context, decree: Decree, chunk: list[_Line]) -> None:
        """Turn consecutive list lines into entries, continuations or unsegmented text."""
        if not chunk:
            return
        offsets: list[int] = []
        position = 0
        for line in chunk:
            offsets.append(position)
            position += len(line.text) + 1
        buffer = "\n".join(line.text for line in chunk)

        def line_at(offset: int) -> _Line:
            return chunk[max(0, bisect_right(offsets, offset) - 1)]

        decree_index = len(self.decrees) - 1 - self.decrees[::-1].index(decree)
        previous: Entry | None = None
        for fragment in personnes.split_entries(buffer):
            body_start = fragment.start + (len(buffer[fragment.start:fragment.end]) - len(buffer[fragment.start:fragment.end].lstrip()))
            first = line_at(body_start)
            last = line_at(max(body_start, fragment.start + len(buffer[fragment.start:fragment.end].rstrip()) - 1))
            text = squeeze(fragment.text.replace("\n", " "))
            size = letters(text)
            cell = self.page_letters.setdefault((decree_index, first.page.leaf), [0, 0])
            cell[0] += size
            if personnes.looks_like_person(fragment.text):
                self._trailing_date(decree, text)
                previous = self._add_entry(context, decree, text, first.page, last.page)
                cell[1] += size
            elif self._trailing_date(decree, text) and letters(text) < 45:
                cell[1] += size
            elif previous is not None and _is_continuation(previous.raw, text):
                previous.raw = f"{previous.raw} {text}"
                cell[1] += size
            elif _is_list_header(text) or (_RE_SENTENCE_TAIL.search(text) and "(" not in text):
                cell[1] += size                 # a header, or the end of the decree sentence: no person in it
            elif size >= 12:
                self.unsegmented.append(Unsegmented(first.page.leaf, first.page.printed, text, decree_index))

    def _trailing_date(self, decree: Decree, text: str) -> bool:
        """1866 layout: the decree date closes the list, « … — Paris, 11 juillet 1866. »"""
        match = RE_TRAILING_DATE.search(join_hyphenation(text))
        found = dates.find_dates(match.group("date")) if match else []
        if not (match and found):
            return False
        if not decree.ocr_dates:
            decree.ocr_dates = found[:1]
            decree.date_raw = squeeze(match.group(0)).lstrip("—–- ")
        return True

    def _add_entry(self, context: _Context, decree: Decree, text: str, first: Page, last: Page,
                   extra_flags: int = 0) -> Entry:
        reading = personnes.read_entry(text, self.year)
        flags = reading.flags | extra_flags
        if first.computed:
            flags |= personnes.F_PAGE_CALCULEE
        if last.leaf != first.leaf:
            flags |= personnes.F_SUR_DEUX_PAGES
        markers = reading.markers | context.status
        if context.heading_indigene:
            markers |= personnes.M_INDIGENE_ENTETE
        entry = Entry(raw=text, name=reading.name, leaf=first.leaf, page=first.printed, markers=markers,
                      nationality=reading.nationality, birth_year=reading.birth_year,
                      residence=reading.residence, flags=flags, number=reading.number,
                      department=context.department)
        decree.entries.append(entry)
        decree.last_leaf = max(decree.last_leaf, last.leaf)
        return entry


def _dated_title_above(lines: list[_Line], i: int) -> list[dates.OcrDate]:
    """« DÉCRET DU 28 NOVEMBRE 1883 » printed between the article title and an undated
    decree sentence (a department header or stray marks may stand in between)."""
    for k in range(i - 1, max(-1, i - 6), -1):
        text = lines[k].text
        if text == PAGE_BREAK or RE_ARTICLE.match(text):
            return []
        if personnes.is_noise_line(text) or RE_DEPARTMENT.search(text) or _is_list_header(text):
            continue
        title = match_sub_decree(text)
        if title is not None and not title[1]:
            return dates.find_dates(title[0], allow_bare=True)
        return []                               # anything else: the title, if any, is not ours
    return []


_RE_SENTENCE_TAIL = re.compile(
    r"(?:noms?\s+sui\w+|ci-\s?(?:apr[èeé]s|dessous)\s+(?:d[ée]\w+|nomm\w+)(?:\s+et\s+d[ée]sign\w+)?|d[ée]nomm[ée]e?s|d[ée]sign[ée]e?s)"
    r"\s*[:;.]?\s*$", re.I)
_RE_PARENTHESISED_HEADER = re.compile(r"^\W{0,3}\(?\s?(?:territoire|l[ée]gion|r[ée]giment|division|subdivision|cercle)\b[^,;]{0,40}\)?\.?\W{0,3}$", re.I)


def _is_list_header(text: str) -> bool:
    """A header of a list damaged by the OCR (« DÉRTEMENT D'ALGER », « DIVSION D'ORAN »,
    « (Territoire civil) »): it carries no person and is not kept as unsegmented text."""
    if letters(text) > 40:
        return False
    if _RE_PARENTHESISED_HEADER.match(text):
        return True
    if any(char.islower() for char in text.replace("d'", "").replace("d’", "")):
        return False
    tokens = re.findall(r"[^\W\d_]{5,}", fold(text))
    return any(levenshtein(token, word, 3) <= (2 if len(word) < 9 else 3)
               for token in tokens for word in ("departement", "division", "province", "territoire", "constantine"))


def _is_entry_line(text: str) -> bool:
    return bool(personnes.RE_ENTRY_START.match(text)) and personnes.looks_like_person(text)


def _is_continuation(previous: str, text: str) -> bool:
    """A fragment that only finishes the previous entry (« rant à Alger. », « Beni-Méred. »)."""
    if letters(text) > 70:
        return False
    if text[:1].islower() or text[:1] in "(-":
        return True
    first = text.split()[0] if text.split() else ""
    if ")" in first and "(" not in first:              # « Maroc), commerçant à … »: end of a parenthesis
        return True
    return not previous.rstrip().endswith((".", ";")) and "," not in text[:-1]


def _last_list_number(numbers: list[int | None], margin_numbers: list[int], entries: int) -> int | None:
    """Size of a printed numbered list, as far as the OCR shows it.

    `numbers` is aligned with the entries found (None: no number read). A number is
    trusted when it is compatible with the rank of its entry; a list that restarts at 1
    for each department is summed run by run. When the entries carry no number, the
    numbers the OCR pushed into the margin are used instead.
    """
    if entries == 0:
        return None
    read = [(i, n) for i, n in enumerate(numbers) if n is not None]
    total = 0
    run_start = 0
    recent: list[int] = []
    for k, (i, number) in enumerate(read):
        following = read[k + 1][1] if k + 1 < len(read) else None
        last_seen = recent[-1] if recent else 0
        if number <= 4 and number < last_seen and len(recent) >= 2 and following is not None \
                and following <= number + 3:
            total += max(recent[-5:])             # the numbering restarts (new department)
            run_start, recent = i, []
        rank = i - run_start + 1
        if 0.8 * rank - 3 <= number <= 1.35 * rank + 10:
            recent.append(number)
    from_entries = total + max(recent[-5:], default=0)
    margin = [n for n in margin_numbers if n <= 1.35 * entries + 10]
    from_margin = max(margin) if len(margin) >= 5 else 0
    return max(from_entries, from_margin) or None


# ---------------------------------------------------------------- after reading
def settle_decree_dates(decrees: list[Decree], volume_year: int) -> None:
    """Give every decree its dated, checked list `dates` (see dates.py for the states)."""
    def settle_all(max_delay: int) -> list[int]:
        delays = []
        for decree in decrees:
            decree.dates = []
            issue_date = decree.issue.date if decree.issue is not None and decree.issue.date_state != dates.SUSPECT else None
            for found in decree.ocr_dates:
                if issue_date is not None:
                    settled, state = dates.settle_year(found, issue_date, max_delay)
                    if settled.date() is not None:
                        delays.append((issue_date - settled.date()).days)
                else:
                    settled = dates.pull_back_into_volume(found, volume_year)
                    state = dates.SUSPECT if settled is not found else dates.state_without_issue(found, volume_year)
                    if found.year is None and found.day is not None:
                        guess = dates.OcrDate(found.day, found.month, volume_year, found.raw, True, found.relative)
                        settled, state = guess, dates.SUSPECT
                if (settled.iso(), state) not in decree.dates:
                    decree.dates.append((settled.iso(), state))
            if not decree.ocr_dates:
                decree.dates = []
        return delays

    delays = settle_all(400)
    long_delays = sum(1 for delay in delays if delay > 400)
    if delays and long_delays >= 3 and long_delays >= 0.3 * len(delays):
        settle_all(1100)        # this volume publishes old decrees in bulk (1868, 1869)


def _name_key(name: str) -> str:
    return re.sub(r"[^a-z]", "", fold(name))[:10]


def _shared_names(first: list[str], second: list[str]) -> int:
    """How many names of `first` have a counterpart in `second` (two OCR errors allowed)."""
    remaining = list(second)
    shared = 0
    for key in first:
        match = next((other for other in remaining if other[:1] == key[:1] and levenshtein(key, other, 2) <= 2), None)
        if match is None:
            match = next((other for other in remaining if levenshtein(key, other, 1) <= 1), None)
        if match is not None:
            remaining.remove(match)
            shared += 1
    return shared


def mark_republished(decrees: list[Decree]) -> None:
    """A decree whose list of names repeats an earlier decree of the volume is a
    republication: both citations are kept, the later one points to the first."""
    keys = [[key for entry in decree.entries if len(key := _name_key(entry.name)) >= 4] for decree in decrees]
    prefixes = [{key[:5] for key in decree_keys} for decree_keys in keys]
    for later in range(len(decrees)):
        if len(keys[later]) < 3:
            continue
        for earlier in range(later):
            small, large = sorted((len(keys[earlier]), len(keys[later])))
            if decrees[earlier].duplicate_of is not None or small < 3 or small < 0.6 * large:
                continue
            if len(prefixes[earlier] & prefixes[later]) < 2:      # cheap filter before the fuzzy comparison
                continue
            if _shared_names(keys[later], keys[earlier]) >= max(3, 0.7 * small):
                decrees[later].duplicate_of = earlier
                for entry in decrees[later].entries:
                    entry.flags |= personnes.F_DECRET_REPUBLIE
                break


def _prune_empty_titles(reader: _Reader) -> list[Decree]:
    """Drop « titre » decrees that gathered no entry (a dated title that was not a list),
    and renumber what points to the decrees."""
    keep = [k for k, decree in enumerate(reader.decrees) if decree.entries or decree.kind == "formule"]
    remap = {old: new for new, old in enumerate(keep)}
    reader.unsegmented = [Unsegmented(u.leaf, u.page, u.text, remap[u.decree_index])
                          for u in reader.unsegmented if u.decree_index in remap]
    reader.page_letters = {(remap[k], leaf): cell for (k, leaf), cell in reader.page_letters.items() if k in remap}
    reader.decrees = [reader.decrees[k] for k in keep]
    return reader.decrees


def find_manual_pages(reader: _Reader) -> list[ManualPage]:
    """Pages of a decree where most of the list text could not be turned into entries."""
    out = []
    for (decree_index, leaf), (total, in_entries) in sorted(reader.page_letters.items(), key=lambda kv: (kv[0][1], kv[0][0])):
        lost = total - in_entries
        if lost >= 150 and in_entries < 0.6 * total:
            page = reader.pages[leaf]
            out.append(ManualPage(leaf, page.printed, decree_index,
                                  "liste non découpée (colonnes mélangées ou texte trop abîmé)", total, in_entries))
    return out


def segment_volume(pages: list[Page], volume_year: int) -> Segmentation:
    """Read a whole volume: issues, decrees, entries, pages to read by hand."""
    issues = livraisons.find_issues(pages, volume_year)
    first, last = body_range(pages, issues)
    tables = table_leaves_inside(pages, issues, first, last)
    reader = _Reader(pages, volume_year, issues)
    reader.run(first, last, frozenset(tables))
    decrees = _prune_empty_titles(reader)
    settle_decree_dates(decrees, volume_year)
    mark_republished(decrees)
    manual = find_manual_pages(reader)
    covered = set()
    for decree in decrees:
        covered.update(range(decree.leaf, max(decree.leaf, decree.last_leaf) + 1))
    hits = []
    for page in pages[first:last + 1]:
        if page.leaf in tables or livraisons.is_issue_title_page(page.text):
            continue
        if any(RE_FORMULA_LOOSE.search(join_hyphenation(line)) and decree_intro(line[:60])
               and not _RE_LEGAL_START.match(line)
               and not re.search(r"\bqui\s+adm\w+\s+(?!à)\w+|[êe]tre\s+admis", line)
               for line in _clean_lines(page)):
            hits.append(page.leaf)
    outside = [leaf for leaf in hits if leaf not in covered and leaf - 1 not in covered]
    return Segmentation(decrees=decrees, issues=issues, unsegmented=reader.unsegmented, manual_pages=manual,
                        body_first_leaf=first, body_last_leaf=last, formula_hits=hits, formula_hits_outside=outside,
                        table_leaves=tables)
