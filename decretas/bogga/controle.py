"""Quality control of one segmented volume against the volume's own evidence.

Three independent checks, none of which needs anything outside the volume:

1. the alphabetical table printed at the end of the volume lists, under NATURALISATION,
   the pages of the admission articles: how many of those pages fall inside a decree
   that the program found?
2. numbered lists and announced totals (« les 37 personnes ci-après désignées »): how
   many entries were found against the last number printed?
3. pages of the body where the admission formula is read but no decree was segmented.

The table itself is OCR text: a page number can be damaged. Numbers that break the
increasing order of the table are reported as doubtful, not as missing decrees.
"""
from __future__ import annotations

import re
from bisect import bisect_left
from dataclasses import dataclass, field

from decretas.bogga.segmentation import Decree, Segmentation
from decretas.bogga.texte import squeeze
from decretas.bogga.volume import Page

RE_TABLE_HEAD = re.compile(r"^\W{0,3}NATURALISATIONS?\b\s*[.:,—–-]", re.I)
_RE_IRRELEVANT = re.compile(
    r"collective|r[èe]glement|r[ée]daction|modification|relati[fv]|notori[ée]t[ée]|\bloi\b|\bvoir\b|circulaire|instruction", re.I)
_RE_NOMINATIVE = re.compile(r"d[ée]clar[ée]s\s+naturalis|\(suite\)", re.I)
_RE_DATE = re.compile(r"\b\d{1,2}\s+[a-zéû]{3,9}\s+1[78]\d\d\b")


@dataclass
class TableReading:
    """What the alphabetical table says about admission pages, as the OCR gives it."""

    leaf: int | None = None
    text: str = ""
    consistent: list[int] = field(default_factory=list)   # readable and in increasing order
    doubtful: list[int] = field(default_factory=list)     # readable but out of order or out of range
    unreadable: int = 0
    nominative: bool = False


def read_table(pages: list[Page], first_issue_leaf: int, last_issue_leaf: int,
               table_leaves: frozenset[int] = frozenset()) -> TableReading:
    """Find the NATURALISATION entry of the alphabetical table and read its page numbers.

    The table is looked for outside the issues (before the first one, after the last
    « CERTIFIÉ CONFORME »); summary lines with dotted leaders are not table entries.
    The reading with the most page numbers wins.
    """
    best = TableReading()
    max_page = max((page.printed or 0) for page in pages)
    for position, page in enumerate(pages):
        if first_issue_leaf <= page.leaf <= last_issue_leaf and page.leaf not in table_leaves:
            continue
        lines = [squeeze(line) for line in page.text.split("\n") if line.strip()]
        for index, line in enumerate(lines):
            head = RE_TABLE_HEAD.match(line)
            if not head or re.match(r"\s*\.{3,}", line[head.end():]):
                continue
            following = lines[index + 1:]
            if position + 1 < len(pages):
                following += [squeeze(text) for text in pages[position + 1].text.split("\n") if text.strip()]
            reading = _read_numbers(_entry_text(line, following), max_page)
            reading.leaf = page.leaf
            if len(reading.consistent) > len(best.consistent) or (reading.nominative and best.leaf is None):
                best = reading
    return best


def _entry_text(first: str, following: list[str]) -> str:
    """The table entry with its continuation lines: a line that starts with a digit, a
    dash or a lower-case letter continues it; a capitalised line is the next entry."""
    parts = [first]
    for line in following[:12]:
        if re.fullmatch(r"\W*[—–_-]+\s*\S{1,6}\s*[—–_-]+\W*", line):
            continue                                   # running page header between two pages
        if len(line) < 3 or not (line[0].isdigit() or line[0].islower() or line[0] in "—–-(«"):
            break
        parts.append(line)
    return " ".join(parts)


def _read_numbers(text: str, max_page: int) -> TableReading:
    reading = TableReading(text=text[:900])
    if _RE_NOMINATIVE.search(text[:160]):
        reading.nominative = True          # the table lists persons, not article pages
        return reading
    segments = [segment for segment in re.split(r"\s[—–]\s|\.\s*[—–]\s*", text) if segment.strip()]
    chosen = [s for s in segments if not _RE_IRRELEVANT.search(s)]
    numbers: list[int] = []
    for segment in chosen:
        segment = _RE_DATE.sub(" ", segment)
        for token in segment.replace(",", " ").replace(";", " ").split():
            core = token.strip(".:()[]|")
            if core.isdigit():
                numbers.append(int(core))
            elif any(char.isdigit() for char in core) and not re.fullmatch(r"\d{1,2}(?:er|e|°)", core):
                reading.unreadable += 1
    numbers = [_fix_out_of_range(n, max_page) for n in numbers]
    in_range = [n for n in numbers if 0 < n <= max(max_page, 1)]
    keep = set(_longest_increasing(in_range))
    seen: list[int] = []
    for n in numbers:
        if n in keep and n not in seen:
            seen.append(n)
        elif n not in seen and n not in reading.doubtful:
            reading.doubtful.append(n)
    reading.consistent = seen
    reading.doubtful = [n for n in reading.doubtful if n not in seen]
    return reading


def _fix_out_of_range(number: int, max_page: int) -> int:
    """'4009' in a volume of 1 300 pages is 1009: the leading 1 was read 4."""
    text = str(number)
    if number > max_page and text[0] == "4" and int("1" + text[1:]) <= max_page:
        return int("1" + text[1:])
    return number


def _longest_increasing(values: list[int]) -> list[int]:
    """A longest strictly increasing subsequence (the table lists pages in order)."""
    tails: list[int] = []
    tail_index: list[int] = []
    previous: list[int | None] = []
    for i, value in enumerate(values):
        pos = bisect_left(tails, value)
        previous.append(tail_index[pos - 1] if pos else None)
        if pos == len(tails):
            tails.append(value)
            tail_index.append(i)
        else:
            tails[pos] = value
            tail_index[pos] = i
    out: list[int] = []
    cursor = tail_index[-1] if tail_index else None
    while cursor is not None:
        out.append(values[cursor])
        cursor = previous[cursor]
    return out[::-1]


def _canon_1_4(number: int) -> str:
    """Page number with every 4 read as 1: the OCR confuses the two digits."""
    return str(number).replace("4", "1")


def decree_pages(decrees: list[Decree], pages: list[Page]) -> set[int]:
    """Printed pages covered by the decrees found (from first to last leaf of each)."""
    covered: set[int] = set()
    for decree in decrees:
        for leaf in range(decree.leaf, max(decree.leaf, decree.last_leaf) + 1):
            printed = pages[leaf].printed if leaf < len(pages) else None
            if printed is not None:
                covered.add(printed)
    return covered


def _article_groups(decrees: list[Decree], pages: list[Page]) -> list[set[int]]:
    """Printed pages of each run of decrees that follow one another without a gap: the
    table lists one page per article, and an article may hold several decrees."""
    groups: list[set[int]] = []
    last_leaf = -10
    for decree in sorted(decrees, key=lambda d: d.leaf):
        printed = {pages[leaf].printed for leaf in range(decree.leaf, max(decree.leaf, decree.last_leaf) + 1)
                   if leaf < len(pages) and pages[leaf].printed is not None}
        if decree.leaf > last_leaf + 1 or not groups:
            groups.append(set())
        groups[-1].update(printed)
        last_leaf = max(last_leaf, decree.last_leaf, decree.leaf)
    return [group for group in groups if group]


def expected_size(decree: Decree) -> int | None:
    """Number of persons the printed page itself announces for a decree, when it does."""
    candidates = [n for n in (decree.announced, decree.last_number) if n]
    return max(candidates) if candidates else None


def control_volume(segmentation: Segmentation, pages: list[Page]) -> dict:
    """The quality-control record stored for a volume (keys in French: it is site data)."""
    decrees = segmentation.decrees
    last_issue_leaf = segmentation.issues[-1].close_leaf if segmentation.issues else len(pages) - 1
    table = read_table(pages, segmentation.body_first_leaf, last_issue_leaf, frozenset(segmentation.table_leaves))
    covered = decree_pages(decrees, pages)
    starts = {decree.page for decree in decrees if decree.page is not None}
    canon = {_canon_1_4(page) for page in covered}
    found_exact = [n for n in table.consistent if n in covered]
    rest = [n for n in table.consistent if n not in covered]
    found_next = [n for n in rest if n + 1 in covered]         # article title at the foot of the page before
    found_tolerant = [n for n in rest if n not in found_next and _canon_1_4(n) in canon]
    missing = [n for n in rest if n not in found_next and n not in found_tolerant]
    listed_canon = {_canon_1_4(n) for n in table.consistent + table.doubtful}
    unlisted = []
    for group in _article_groups(decrees, pages):
        if not any(_canon_1_4(page) in listed_canon for page in group):
            unlisted.append(min(group))
    del starts

    sized = [(decree, expected_size(decree)) for decree in decrees]
    sized = [(decree, size) for decree, size in sized if size]
    expected_total = sum(size for _decree, size in sized)
    found_total = sum(min(len(decree.entries), size) for decree, size in sized)
    over = sum(1 for decree, size in sized if len(decree.entries) > size)

    record: dict = {
        "table_alphabetique": {
            "trouvee": table.leaf is not None and bool(table.consistent or table.nominative),
            "feuille": table.leaf,
            "pages_listees_lisibles": len(table.consistent),
            "nominative": table.nominative,
            "pages_retrouvees": len(found_exact) + len(found_next) + len(found_tolerant),
            "dont_a_la_page_suivante": len(found_next),
            "dont_avec_confusion_1_4": len(found_tolerant),
            "pages_non_retrouvees": missing,
            "numeros_douteux": table.doubtful,
            "numeros_illisibles": table.unreadable,
            "taux_pages": _rate(len(found_exact) + len(found_next) + len(found_tolerant), len(table.consistent)),
            "decrets_trouves_hors_table": unlisted,
        },
        "listes_numerotees": {
            "decrets_avec_total_imprime": len(sized),
            "personnes_annoncees": expected_total,
            "entrees_trouvees": found_total,
            "taux_entrees": _rate(found_total, expected_total),
            "decrets_avec_plus_d_entrees_que_le_total": over,
        },
        "formule_hors_decret": segmentation.formula_hits_outside,
        "decrets": len(decrees),
        "decrets_sans_entree": sum(1 for decree in decrees if not decree.entries),
        "decrets_republies": sum(1 for decree in decrees if decree.duplicate_of is not None),
        "entrees": sum(len(decree.entries) for decree in decrees),
        "pages_a_lire_a_la_main": len({page.leaf for page in segmentation.manual_pages}),
    }
    return record


def _rate(found: int, expected: int) -> float | None:
    return round(found / expected, 4) if expected else None
