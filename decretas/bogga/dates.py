"""Dates as the OCR gives them: reading, digit repair, and sanity checks.

The typeface of the bulletin has a serifed '1' that Tesseract often reads '4':
'44 juillet 1865', '4873', 'le 45 décembre'. A repair is applied only when the value
read is impossible (day > 31, year outside the plausible range); a '4' that gives a
possible value is kept as read — the scanned page remains the proof. A day read '44'
is impossible but has two repairs (11 with both digits misread, 14 with one): it is given
as 14 and marked suspect. A year read with a doubled first digit ('41879', '14874') is
repaired by dropping the stray digit.

States (`etat`) carried by every exported date:
  0  read as printed by the OCR;
  1  repaired (digit 1 read as 4, or year re-established from the issue that publishes it);
  2  suspect: fails a sanity check, to be read on the page image.
"""
from __future__ import annotations

import datetime
import re
from dataclasses import dataclass

from decretas.bogga.texte import fold, levenshtein

READ, REPAIRED, SUSPECT = 0, 1, 2

MONTHS = ("janvier", "fevrier", "mars", "avril", "mai", "juin", "juillet", "aout",
          "septembre", "octobre", "novembre", "decembre")

_DIGITISH = r"[\dOoIlSs?$%*#]"
# day [er|°] month [year]; the year is optional ('du 10 novembre dernier').
DATE_RE = re.compile(
    r"(?<![\w$?])(?P<day>[\d?][\dOoIl?$*%#]{0,2})\s?(?P<first>er|°{1,2}|ᵉʳ|\*|[\"'‘’“”«»]{1,2})?[,.]?\s+"
    r"(?P<month>[A-Za-zéûôèêÉÛ][A-Za-zéûôèêÉÛ:.\-]{2,10})\.?\s*"
    r"(?:(?P<year>[14Il]{1,2}\s?[5-9SsOo$]" + _DIGITISH + r"{2})(?![\dA-Za-z])|(?P<rel>dernier|courant))?",
    re.UNICODE,
)
_DAY_BEFORE = re.compile(r"(?<![\w$?])(\d[\dOoIl?$*]{0,2})\s?(?:er|°|\*)?\s*(?:,|et)\s+$")
_DAY_MONTH_BEFORE = re.compile(
    r"(?<![\w$?])(\d[\dOoIl?$*]{0,2})\s?(?:er|°|\*)?\s+([A-Za-zéûôèêÉ]{3,10})\.?\s+et\s+$")


@dataclass(frozen=True)
class OcrDate:
    """A date read in the text. `day`/`year` are None when unreadable; `repaired` is True
    when a digit was changed to make the value possible; `ambiguous` is True when the
    repair chosen is not the only one ('44' given as 14 may be 11); `raw` is the OCR text."""

    day: int | None
    month: int
    year: int | None
    raw: str
    repaired: bool = False
    relative: bool = False
    ambiguous: bool = False

    def iso(self) -> str | None:
        if self.day is None or self.year is None:
            return None
        try:
            return datetime.date(self.year, self.month, self.day).isoformat()
        except ValueError:
            return None

    def date(self) -> datetime.date | None:
        text = self.iso()
        return datetime.date.fromisoformat(text) if text else None


def month_of(token: str) -> int | None:
    """Month number of a word, tolerant to OCR damage ('moi' -> mai, 'ocToBrE' -> octobre)."""
    word = re.sub(r"[^a-z]", "", fold(token))
    if len(word) < 3:
        return None
    best = min(range(12), key=lambda i: levenshtein(word, MONTHS[i]))
    distance = levenshtein(word, MONTHS[best])
    tolerance = 1 if len(MONTHS[best]) <= 5 else 2
    if distance > tolerance:
        return None
    if distance and len(word) <= 4:
        # short words: only accept known OCR confusions, never an ordinary word ('mais', 'jour')
        if word not in {"moi", "mal", "mat", "mars", "mai", "jnin", "juiu", "jain", "aoat", "aoot", "aont"}:
            return None
    return best + 1


def _clean_digits(raw: str) -> tuple[str, bool]:
    """Map look-alike characters to digits. Returns (digits with '?' for unknown, changed)."""
    table = {"O": "0", "o": "0", "I": "1", "l": "1", "S": "8", "s": "8", "$": "?", "*": "?", "#": "?", "%": "?"}
    out = []
    changed = False
    for char in raw:
        if char.isdigit() or char == "?":
            out.append(char)
        elif char in table:
            out.append(table[char])
            changed = True
        elif char.isspace():
            continue
        else:
            out.append("?")
            changed = True
    return "".join(out), changed


def repair_day(raw: str) -> tuple[int | None, bool]:
    """Day of month from OCR digits: '45' -> 15 (repaired), '8' -> 8, '?6' -> None."""
    digits, changed = _clean_digits(raw)
    if not digits or "?" in digits:
        return None, changed
    if len(digits) == 3 and digits[0] == "4":      # '414' for 14: a stray leading 4
        digits, changed = digits[1:], True
    value = int(digits)
    if 1 <= value <= 31:
        return value, changed
    if len(digits) == 2 and digits[0] == "4":
        value = int("1" + digits[1])
        if 1 <= value <= 31:
            return value, True
    return None, changed


def repair_year(raw: str, lowest: int = 1830, highest: int = 1962) -> tuple[int | None, bool]:
    """Year from OCR digits: '4873' -> 1873 (repaired). None when it cannot be made plausible."""
    digits, changed = _clean_digits(raw)
    if len(digits) == 5 and digits[0] in "14" and digits[1] in "14":
        digits, changed = digits[1:], True          # '41879', '14874': the serifed 1 read twice
    if len(digits) != 4 or "?" in digits:
        return None, changed
    value = int(digits)
    if lowest <= value <= highest:
        return value, changed
    if digits[0] == "4":
        value = int("1" + digits[1:])
        if lowest <= value <= highest:
            return value, True
    return None, changed


def find_dates(text: str, *, allow_bare: bool = False) -> list[OcrDate]:
    """Every date of a passage, in order, including the compact forms
    'des 5 et 16 décembre 1872' and 'des 30 mars et 7 avril 1873'.

    `allow_bare` also accepts a day and month without a year ('Décret du 14 décembre'),
    returned as relative dates whose year is to be settled from the context."""
    found: list[OcrDate] = []
    for match in DATE_RE.finditer(text):
        month = month_of(match.group("month"))
        if month is None:
            continue
        if match.group("year") is None and match.group("rel") is None and not allow_bare:
            continue
        year, year_repaired = (repair_year(match.group("year")) if match.group("year") else (None, False))
        relative = match.group("year") is None
        before = text[max(0, match.start() - 60):match.start()]
        extra: list[OcrDate] = []
        pending = before
        while True:
            lead = _DAY_MONTH_BEFORE.search(pending) or _DAY_BEFORE.search(pending)
            if lead is None:
                break
            lead_month = month_of(lead.group(2)) if lead.re is _DAY_MONTH_BEFORE else month
            if lead_month is None:
                break
            lead_day, lead_repaired = repair_day(lead.group(1))
            extra.insert(0, OcrDate(lead_day, lead_month, year, (lead.group(0) + match.group(0)).strip(),
                                    lead_repaired or year_repaired, relative))
            pending = pending[:lead.start()]
        day_raw = match.group("day")
        ambiguous = False
        if match.group("first") and day_raw in {"4", "44", "l", "I", "1"}:
            day, day_repaired = 1, day_raw != "1"      # '1er' read '4er' or '44'
        elif day_raw[-1:] == "*" and day_raw[:-1] in {"4", "l", "I", "1"}:
            day, day_repaired = 1, day_raw != "1*"     # '1er' read '4*'
        else:
            day, day_repaired = repair_day(day_raw)
            ambiguous = _clean_digits(day_raw)[0] == "44"
        found.extend(extra)
        found.append(OcrDate(day, month, year, match.group(0).strip(), day_repaired or year_repaired, relative,
                             ambiguous))
    return found


_DAMAGED_RE = re.compile(
    r"\bd(?:u|es|n)\s?(?P<day>\S{1,8}?)\s?(?P<month>[A-Za-zéûôèêÉÛ]{3,10})\.?\s+(?P<year>[14Il]{0,2}\s?[5-9SsOo$]\S{2})(?!\w)")


def find_damaged_date(text: str) -> OcrDate | None:
    """« du 2t octobre 1876 », « duM16 juin 4880 », « du # mai 4880 »: a date whose day the
    OCR destroyed. The month and year are kept, the day is None; the caller marks it suspect."""
    for match in _DAMAGED_RE.finditer(text):
        month = month_of(match.group("month"))
        if month is None:
            continue
        year, _repaired = repair_year(match.group("year"))
        if year == 1865 and month == 7:
            continue                                   # the sénatus-consulte, not the decree
        raw = match.group(0)[match.start("day") - match.start():].strip()
        return OcrDate(None, month, year, raw, False, False)
    return None


def settle_year(date: OcrDate, not_after: datetime.date, max_delay_days: int = 400) -> tuple[OcrDate, int]:
    """Check a decree date against the date of the issue that publishes it.

    A decree cannot be later than its publication and is normally published within a few
    months (`max_delay_days`; some volumes publish older decrees in bulk, the caller then
    widens it). Returns the date (possibly with its year re-established) and its state.
    """
    if date.day is None:
        return date, SUSPECT
    own = date.date()
    if own is not None and not date.relative:
        delay = (not_after - own).days
        if 0 <= delay <= max_delay_days:
            if date.ambiguous:
                return date, SUSPECT            # '44': given as 14, may be 11
            return date, REPAIRED if date.repaired else READ
        if delay > max_delay_days and own.year >= 1865:
            # far older than its publication: kept as read, to be checked on the page
            return date, SUSPECT
    # year missing ('dernier', 'Décret du 14 décembre'), unreadable, or impossible against
    # the issue date: take the latest year that puts the decree on or before its publication.
    for year in (not_after.year, not_after.year - 1):
        try:
            candidate = datetime.date(year, date.month, date.day)
        except ValueError:
            continue
        if 0 <= (not_after - candidate).days <= 400:
            settled = OcrDate(date.day, date.month, year, date.raw, True, date.relative, date.ambiguous)
            return settled, SUSPECT if date.ambiguous else REPAIRED
    return date, SUSPECT


def state_without_issue(date: OcrDate, volume_year: int) -> int:
    """State of a decree date when no issue date is available: only the year range is checked."""
    if date.iso() is None or date.year is None or date.ambiguous:
        return SUSPECT
    if not (volume_year - 2 <= date.year <= volume_year):
        return SUSPECT
    return REPAIRED if date.repaired else READ


def pull_back_into_volume(date: OcrDate, volume_year: int) -> OcrDate:
    """A decree printed in the volume of year Y cannot be dated after Y. When the year read
    is later ('31 août 1884' in the 1881 volume) and no issue date is there to settle it,
    the latest possible year is given; the caller keeps the date suspect."""
    if date.year is None or date.day is None or date.year <= volume_year:
        return date
    try:
        datetime.date(volume_year, date.month, date.day)
    except ValueError:
        return date
    return OcrDate(date.day, date.month, volume_year, date.raw, True, date.relative, date.ambiguous)
