"""Issues ("livraisons") of a yearly volume.

Each issue opens on a title page (BULLETIN OFFICIEL / GOUVERNEMENT GÉNÉRAL / ANNÉE 18xx /
N° nnn / SOMMAIRE) and closes on 'CERTIFIÉ CONFORME : Alger, le <date>'. That date is the
publication date used in a citation, so it is validated: issue dates never go backwards
inside a volume. A date that is unreadable or breaks that order is repaired only when one
single reading fits between its neighbours; otherwise it is left empty and marked suspect.

Both marks are read with tolerance for OCR damage ('CBBTIFIÉ CONFORME', 'OERTIFIÉ
CUNFORME'), and the two kinds of evidence are combined: when a title page shows that an
issue started but the closing line of the issue before could not be read, that issue is
still counted, with an empty and suspect date. A decree is thus never handed the date of
the *following* issue because its own closing line was missed.
"""
from __future__ import annotations

import datetime
import re
from bisect import bisect_right
from dataclasses import dataclass

from decretas.bogga import dates
from decretas.bogga.texte import fold, levenshtein, squeeze
from decretas.bogga.volume import Page

NUMBER_READ, NUMBER_COMPUTED, NUMBER_UNCERTAIN = 0, 1, 2

# The closing line of an issue, as the OCR gives it. The second word is looked for first
# (it survives better), then the word before it is compared with « certifié » and what
# follows with « Alger, le <day> ». 'Certifié conforme au cahier des charges', 'Certifié
# conforme : Dra-el-Mizan, le …' and the lower-case 'Pour copie certifiée conforme' that
# end ordinary acts are not closing lines.
_RE_CONFORME = re.compile(r"(?<![^\s(«\"'*|—–-])[CcGOoUu(][O0oUuÔÛ][^\s:;.,]{1,2}[FfPp][^\s:;.,]{2,6}")
_RE_BEFORE_CONFORME = re.compile(r"(?:^|(?<=\s))(\S{5,11})\s+$")
_RE_CITY = re.compile(r"[^\s,;:.]{3,8}")
_RE_MASTHEAD = re.compile(r"BU\w{1,3}ETIN|OFF[IT][CG]IEL")
_RE_GOVERNMENT = re.compile(r"GOU[VY]ERN")
_RE_ALGERIA = re.compile(r"ALG[ÉEÈ]R")
_RE_ISSUE_NUMBER = re.compile(r"\bN\s?[°\"'’*o:.º«»]{1,2}\s*(\d{1,4})\b")
_RE_DAY_DIGITS = re.compile(r"le\s+([\d?$*OoIlS]{1,3})\s?(?:er|°)?\s+[A-Za-zéû]")
_RE_SUMMARY = re.compile(r"SOMMAIRE|ANALYSE|\bDATES\b")
_RE_YEAR_LINE = re.compile(r"\bANN\S{1,3}\s+1\S{3,5}\b")
_RE_CHRONOLOGICAL = re.compile(r"TABLE\s+CHRONO|CONTENUS\s+DANS\s+LE\s+TOME", re.I)
RE_TABLE_PAGE = re.compile(r"\bTABLE\s+(?:ALPHAB|CHRONO|G[ÉE]N[ÉE]RALE|ANALYTIQUE|DES\s+MATI|DES\s+NOMS)")
_MASTHEAD_WORDS = (("bulletin", 2), ("officiel", 2), ("gouvernement", 3), ("general", 2), ("algerie", 2))
_OCR_LETTERS = str.maketrans({"0": "o", "1": "i", "5": "s", "8": "b", "#": "e", "^": "", "'": "", "’": ""})


def _letters_only(token: str) -> str:
    return re.sub(r"[^a-z]", "", fold(token.translate(_OCR_LETTERS)))


def _mostly_upper(token: str) -> bool:
    letters = [char for char in token if char.isalpha()]
    return bool(letters) and sum(1 for char in letters if char.isupper()) >= 0.6 * len(letters)


def _alger_and_day(tail: str) -> bool:
    """« Alger, le 15 … » at the start of `tail`, a few stray marks and OCR damage allowed
    ('Aiger. [e 6 mai', 'alger, lc 40', 'Alser, Je 5')."""
    for token in _RE_CITY.finditer(tail[:34]):
        if token.group(0)[:1].lower() in "aàmu" and levenshtein(_letters_only(token.group(0)), "alger", 2) <= 2:
            return bool(re.match(r"\D{0,9}\d|[,.]?\s*[lI1i\[][eoc]\s", tail[token.end():]))
    return False


def find_closing(text: str) -> int | None:
    """Offset of the closing line of an issue (« CERTIFIÉ CONFORME : Alger, le … ») in
    `text`, or None. `text` may be one line or a whole page with its white space squeezed."""
    for match in _RE_CONFORME.finditer(text):
        second = match.group(0)
        distance_second = levenshtein(_letters_only(second), "conforme", 3)
        if distance_second > 3:
            continue
        tail = text[match.end():match.end() + 60]
        before = _RE_BEFORE_CONFORME.search(text[max(0, match.start() - 14):match.start()])
        first = before.group(1) if before else ""
        start = match.start() - len(before.group(0)) if before else match.start()
        distance_first = levenshtein(_letters_only(first), "certifie", 3) if first[:1].isupper() else 9
        in_alger = _alger_and_day(tail)
        if distance_first <= 3 and in_alger:
            return start
        if distance_first <= 2 and distance_second <= 2 and _mostly_upper(first) and _mostly_upper(second):
            return start                               # the mark in capitals, place and date lost or on the next line
        if in_alger and distance_second <= 1 and _mostly_upper(second):
            return match.start()                       # the first word is beyond recognition
    return None


def closing_text(text: str) -> str | None:
    """The closing line and what follows it (120 characters at most), or None."""
    position = find_closing(text)
    return None if position is None else text[position:position + 120]


@dataclass
class Issue:
    """One issue. `number_state`: 0 read on its own title page, 1 computed by counting from
    a readable neighbour, 2 uncertain (neighbours disagree). `date_state`: see dates.py."""

    index: int
    open_leaf: int | None
    close_leaf: int
    number: int | None
    number_state: int
    date: datetime.date | None
    date_raw: str
    date_state: int


def is_issue_title_page(text: str) -> bool:
    """A page that opens an issue: masthead and summary table.

    The masthead is accepted when the OCR kept « BULLETIN / OFFICIEL » and « GOUVERN… »,
    or when three of its five words are still recognisable in capitals ('SOUVERNEMENT',
    'GOIVËRNËHËNT', 'BULEETINX')."""
    head = squeeze(text[:700])
    top = head[:220]
    if not _RE_SUMMARY.search(head) or _RE_CHRONOLOGICAL.search(head[:260]):
        return False                    # the chronological table of the volume also names the bulletin
    if _RE_MASTHEAD.search(top) and _RE_GOVERNMENT.search(top):
        return True
    found = set()
    for token in re.findall(r"[^\s,;:.'’]{6,14}", head[:260]):
        if not _mostly_upper(token):
            continue
        folded = _letters_only(token)
        for word, tolerance in _MASTHEAD_WORDS:
            if levenshtein(folded, word, tolerance) <= tolerance:
                found.add(word)
    named = bool(found & {"bulletin", "officiel"}) or bool(_RE_YEAR_LINE.search(head[:260]))
    return len(found) >= 3 and named        # the second page of a summary names the Government too


def read_issue_number(text: str) -> int | None:
    """The issue number printed under the masthead, when the OCR kept it."""
    head = squeeze(text[:700])
    anchor = _RE_ALGERIA.search(head)
    if anchor is None:
        return None
    match = _RE_ISSUE_NUMBER.search(head, anchor.end(), anchor.end() + 90)
    return int(match.group(1)) if match else None


def _day_candidates(raw: str) -> list[int]:
    """Possible days for a damaged day-of-month: '?6' -> 6, 16, 26; '98' -> 8, 18, 28;
    '34' -> 31 (a printed 1 is often read 4; the 3 is taken as read)."""
    match = _RE_DAY_DIGITS.search(raw)
    if match is None:
        return []
    token = match.group(1).translate(str.maketrans("OoIlS$*", "00118??"))
    if token.isdigit() and 1 <= int(token) <= 31:
        return [int(token)]
    if not token or len(token) > 2 or not (token[-1].isdigit() or token[-1] == "?") or token == "?" * len(token):
        return []
    last_choices = "0123456789" if token[-1] == "?" else ("14" if token[-1] == "4" else token[-1])
    if len(token) == 1:
        first_choices = ["", "1", "2", "3"]
    elif token[0] in "0123":
        first_choices = [token[0].replace("0", "")]
    elif token[0] == "4":
        first_choices = ["1"]
    else:                                   # '?' or a digit no day starts with: unknown
        first_choices = ["", "1", "2", "3"]
    def days_for(firsts: list[str]) -> list[int]:
        found = {int(first + last) for first in firsts for last in last_choices if (first + last).isdigit()}
        return sorted(day for day in found if 1 <= day <= 31)

    return days_for(first_choices) or days_for(["", "1", "2", "3"])     # '39': the 3 itself is misread


def _variants_1_4(day: int) -> list[int]:
    """Days a printed day may hide when 1 and 4 are confused: 4 -> 1, 14 -> 11, 24 -> 21."""
    text = str(day)
    out = {day}
    for i, char in enumerate(text):
        if char in "14":
            swapped = text[:i] + ("1" if char == "4" else "4") + text[i + 1:]
            if 1 <= int(swapped) <= 31:
                out.add(int(swapped))
    return sorted(out)


def _safe_date(year: int, month: int, day: int) -> datetime.date | None:
    try:
        return datetime.date(year, month, day)
    except ValueError:
        return None


def _longest_non_decreasing(values: list[datetime.date | None]) -> set[int]:
    """Indexes of a longest non-decreasing subsequence of the non-empty values."""
    tails: list[datetime.date] = []
    tail_index: list[int] = []
    previous: dict[int, int | None] = {}
    for i, value in enumerate(values):
        if value is None:
            continue
        pos = bisect_right(tails, value)
        previous[i] = tail_index[pos - 1] if pos else None
        if pos == len(tails):
            tails.append(value)
            tail_index.append(i)
        else:
            tails[pos] = value
            tail_index[pos] = i
    keep: set[int] = set()
    cursor = tail_index[-1] if tail_index else None
    while cursor is not None:
        keep.add(cursor)
        cursor = previous[cursor]
    return keep


def settle_issue_dates(raws: list[str], volume_year: int) -> list[tuple[datetime.date | None, int]]:
    """Validated date of each closing line, in volume order. Returns [(date or None, state)]."""
    parsed = [(dates.find_dates(raw) or [None])[0] for raw in raws]
    primary: list[datetime.date | None] = []
    for item in parsed:
        value = item.date() if item is not None else None
        if value is not None and not (datetime.date(volume_year, 1, 1) <= value <= datetime.date(volume_year + 1, 3, 31)):
            value = None
        primary.append(value)
    trusted = _longest_non_decreasing(primary)
    result: list[tuple[datetime.date | None, int]] = []
    for i, item in enumerate(parsed):
        lower = max((primary[j] for j in trusted if j < i), default=datetime.date(volume_year, 1, 1))
        upper = min((primary[j] for j in trusted if j > i), default=datetime.date(volume_year + 1, 3, 31))
        if i in trusted and primary[i] is not None:
            if item is not None and item.ambiguous:
                # '44': 14 or 11. Publish it as read only when the neighbours leave one choice.
                fits = [candidate for day in (11, 14)
                        if (candidate := _safe_date(primary[i].year, primary[i].month, day)) is not None
                        and lower <= candidate <= upper]
                result.append((fits[0], dates.REPAIRED) if len(fits) == 1 else (primary[i], dates.SUSPECT))
                continue
            result.append((primary[i], dates.REPAIRED if item is not None and item.repaired else dates.READ))
            continue
        if item is None:
            result.append((None, dates.SUSPECT))
            continue
        days = [item.day] if item.day is not None else _day_candidates(raws[i])
        if item.day is not None and primary[i] is not None:
            days = _variants_1_4(item.day)          # readable but out of order: try the 1/4 confusion
        years = [item.year] if item.year is not None and volume_year <= item.year <= volume_year + 1 \
            else [volume_year, volume_year + 1]
        fits = sorted({
            candidate
            for year in years for day in days
            if (candidate := _safe_date(year, item.month, day)) is not None and lower <= candidate <= upper
        })
        result.append((fits[0], dates.REPAIRED) if len(fits) == 1 else (None, dates.SUSPECT))
    return result


def _settle_numbers(anchors: dict[int, int], count: int) -> list[tuple[int | None, int]]:
    """Issue number of each closing from the numbers read on title pages (index -> number)."""
    if anchors:
        # issues are numbered consecutively: number - position is (nearly) constant
        offsets = sorted(number - index for index, number in anchors.items())
        median = offsets[len(offsets) // 2]
        anchors = {index: number for index, number in anchors.items() if abs(number - index - median) <= 3}
    if not anchors:
        return [(None, NUMBER_UNCERTAIN)] * count
    indexes = sorted(anchors)
    if len(indexes) == 1 and count >= 5:
        # one number read in a whole volume cannot be checked against any other: every
        # number counted from it is given, but as uncertain
        only = indexes[0]
        return [(anchors[only] + (i - only), NUMBER_UNCERTAIN) for i in range(count)]
    out: list[tuple[int | None, int]] = []
    for i in range(count):
        if i in anchors and _anchor_is_consistent(i, anchors, indexes):
            out.append((anchors[i], NUMBER_READ))
            continue
        before = [j for j in indexes if j < i and _anchor_is_consistent(j, anchors, indexes)]
        after = [j for j in indexes if j > i and _anchor_is_consistent(j, anchors, indexes)]
        guesses = set()
        if before:
            guesses.add(anchors[before[-1]] + (i - before[-1]))
        if after:
            guesses.add(anchors[after[0]] - (after[0] - i))
        if len(guesses) == 1:
            out.append((guesses.pop(), NUMBER_COMPUTED))
        elif guesses:
            out.append((anchors[before[-1]] + (i - before[-1]), NUMBER_UNCERTAIN))
        else:
            out.append((None, NUMBER_UNCERTAIN))
    return out


def _anchor_is_consistent(i: int, anchors: dict[int, int], indexes: list[int]) -> bool:
    """A read number is kept when it agrees with at least one neighbouring read number
    (issues are numbered consecutively), or when it is the only one."""
    if len(indexes) == 1:
        return True
    pos = indexes.index(i)
    neighbours = [indexes[k] for k in (pos - 1, pos + 1) if 0 <= k < len(indexes)]
    return any(anchors[j] - anchors[i] == j - i for j in neighbours)


def _table_leaf_after(pages: list[Page], leaf: int) -> int | None:
    """First leaf after `leaf` that opens one of the tables printed at the end of a volume."""
    for page in pages[leaf + 1:]:
        if RE_TABLE_PAGE.search(squeeze(page.text[:400])):
            return page.leaf
    return None


def find_issues(pages: list[Page], volume_year: int) -> list[Issue]:
    """Every issue of the volume, in order, with validated number and date.

    An issue ends on its closing line. When a title page is met while the issue opened by
    the previous title page was never closed, that earlier issue is closed on the leaf
    before, without a date (state suspect): its closing line was lost by the OCR.

    Two issues in a row whose title pages carry the same number are an issue and its
    « bis »: they share the number, and the count goes on from there."""
    spans: list[tuple[int | None, int, str, int | None]] = []     # (open leaf, close leaf, raw, number read)
    open_leaf: int | None = None
    number_read: int | None = None
    for page in pages:
        if is_issue_title_page(page.text):
            if open_leaf is not None and page.leaf - open_leaf > 1:
                spans.append((open_leaf, page.leaf - 1, "", number_read))
                open_leaf = None
            if open_leaf is None:              # (a title page right after a title page is its second page)
                open_leaf, number_read = page.leaf, read_issue_number(page.text)
        raw = closing_text(squeeze(page.text))
        if raw is not None:
            spans.append((open_leaf, page.leaf, raw, number_read))
            open_leaf, number_read = None, None
    if open_leaf is not None:                                      # the last issue has no readable closing
        table = _table_leaf_after(pages, open_leaf)
        spans.append((open_leaf, (table - 1) if table is not None else len(pages) - 1, "", number_read))
    settled_dates = settle_issue_dates([raw for _open, _close, raw, _number in spans], volume_year)
    ranks: list[int] = []                                          # position in the numbering: a « bis » does not count
    for index, (_open, _close, _raw, number) in enumerate(spans):
        same = index > 0 and number is not None and number == spans[index - 1][3]
        ranks.append((ranks[-1] if ranks else -1) + (0 if same else 1))
    anchors = {ranks[index]: number for index, (_open, _close, _raw, number) in enumerate(spans) if number is not None}
    numbers = _settle_numbers(anchors, (ranks[-1] + 1) if ranks else 0)
    return [
        Issue(index=index, open_leaf=opened, close_leaf=closed,
              number=numbers[ranks[index]][0], number_state=numbers[ranks[index]][1],
              date=settled_dates[index][0], date_raw=raw, date_state=settled_dates[index][1])
        for index, (opened, closed, raw, _number) in enumerate(spans)
    ]


def issue_for_leaf(issues: list[Issue], leaf: int) -> Issue | None:
    """The issue that contains a leaf: the first one that closes at or after it."""
    for issue in issues:
        if issue.close_leaf >= leaf:
            return issue
    return None
