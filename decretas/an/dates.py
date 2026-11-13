"""French date recognition and reconciliation of decree dates.

Two jobs:

* ``find_date`` finds the first date of a folded text (birth lines, children, spouses);
* ``reconcile_decree_date`` confronts the three witnesses of a decree date -- the
  ``unitdate/@normal`` attribute, the text of ``<unitdate>`` and the date written in the
  title -- and never returns a date without saying whether the witnesses agreed.
"""
from __future__ import annotations

import re
from typing import NamedTuple

from .text import fold

_MONTH_PREFIXES: tuple[tuple[str, int], ...] = (
    ("jan", 1), ("fev", 2), ("fer", 2), ("mar", 3), ("avr", 4), ("mai", 5), ("juin", 6),
    ("jui", 7), ("aou", 8), ("sep", 9), ("oct", 10), ("nov", 11), ("dec", 12),
)
# Month words are recognised by prefix: the inventories contain "janiver", "juilet", "mail",
# "octobres", "avril1 1860"... A month glued to the year ("22 juillet1847", "11août 1907") is accepted.
_MONTH = (r"(jan[a-z0-9]*|fev[a-z0-9]*|ferv[a-z0-9]*|mars?|avr[a-z0-9]*|mai[a-z]?|juin|juil[a-z0-9]*|aou[a-z0-9]*|"
          r"sep[a-z0-9]*|oct[a-z0-9]*|nov[a-z0-9]*|dec[a-z0-9]*)")
_YEAR = r"(1[5-9]\d\d)"
_DAY_MONTH_YEAR = re.compile(r"(?<!\d)(\d{1,2})\s*(?:er|ere|e|eme)?\s*" + _MONTH + r"\.?\s*" + _YEAR + r"(?!\d)")
_NUMERIC = re.compile(r"(?<!\d)(\d{1,2})\s*[/.\-]\s*(\d{1,2})\s*[/.\-]\s*" + _YEAR + r"(?!\d)")
_MONTH_YEAR = re.compile(r"(?<![a-z])" + _MONTH + r"\s+" + _YEAR + r"(?!\d)")
_YEAR_ONLY = re.compile(r"(?<!\d)" + _YEAR + r"(?!\d)")
_ISO_DAY = re.compile(r"\d{4}-\d{2}-\d{2}")

PRECISION_DAY = "jour"
PRECISION_MONTH = "mois"
PRECISION_YEAR = "annee"

# Flags of a reconciled decree date (documented in docs/format-donnees-an.md).
FLAG_OK = ""
FLAG_TITLE_KEPT = "conflit-titre-retenu"
FLAG_NORMAL_KEPT = "conflit-normal-retenu"
FLAG_TITLE_ONLY = "titre-seul"
FLAG_RANGE = "intervalle"
FLAG_NONE = "sans-date"
FLAG_OUTSIDE = "hors-inventaire"


class DateMatch(NamedTuple):
    start: int
    end: int
    iso: str          # 'AAAA-MM-JJ', 'AAAA-MM' or 'AAAA'
    precision: str    # PRECISION_DAY | PRECISION_MONTH | PRECISION_YEAR


class DecreeDate(NamedTuple):
    iso: str | None       # reconciled 'AAAA-MM-JJ', or None (interval, no date)
    flag: str             # '' or flags joined by '+'
    year: int | None      # year of the reconciled date (start year for an interval)
    title_date: str | None
    text_date: str | None


def month_number(word: str) -> int | None:
    """Month number of a folded French month word, recognised by its prefix."""
    for prefix, number in _MONTH_PREFIXES:
        if word.startswith(prefix):
            if prefix == "jui":
                return 6 if word.startswith("juin") else 7
            return number
    return None


def _day_month_year(match: re.Match[str]) -> DateMatch | None:
    month = month_number(match.group(2))
    day, year = int(match.group(1)), int(match.group(3))
    if month is None or not 1 <= day <= 31:
        return None
    return DateMatch(match.start(), match.end(), f"{year:04d}-{month:02d}-{day:02d}", PRECISION_DAY)


def _numeric(match: re.Match[str]) -> DateMatch | None:
    day, month, year = int(match.group(1)), int(match.group(2)), int(match.group(3))
    if not (1 <= day <= 31 and 1 <= month <= 12):
        return None
    return DateMatch(match.start(), match.end(), f"{year:04d}-{month:02d}-{day:02d}", PRECISION_DAY)


def _month_year(match: re.Match[str]) -> DateMatch | None:
    month = month_number(match.group(1))
    if month is None:
        return None
    return DateMatch(match.start(), match.end(), f"{int(match.group(2)):04d}-{month:02d}", PRECISION_MONTH)


def _year_only(match: re.Match[str]) -> DateMatch | None:
    return DateMatch(match.start(), match.end(), match.group(1), PRECISION_YEAR)


_PATTERNS = (
    (_DAY_MONTH_YEAR, _day_month_year),
    (_NUMERIC, _numeric),
    (_MONTH_YEAR, _month_year),
    (_YEAR_ONLY, _year_only),
)


def find_date(folded: str, start: int = 0) -> DateMatch | None:
    """First date of an already folded string; the most precise form wins at equal position."""
    best: DateMatch | None = None
    for pattern, build in _PATTERNS:
        for match in pattern.finditer(folded, start):
            candidate = build(match)
            if candidate is None:
                continue
            if best is None or candidate.start < best.start:
                best = candidate
            break
    return best


def full_dates(text: str) -> list[str]:
    """Every complete date (day, month, year) written in a text, in order, as ISO strings."""
    folded = fold(text)
    found: list[str] = []
    for match in _DAY_MONTH_YEAR.finditer(folded):
        candidate = _day_month_year(match)
        if candidate is not None:
            found.append(candidate.iso)
    return found


def has_full_date(text: str) -> bool:
    return bool(full_dates(text))


def _parse_normal(normal: str | None) -> tuple[str, str | None]:
    """Kind of a ``unitdate/@normal`` value: ('jour', iso) | ('intervalle', start) | ('absent', None)."""
    value = (normal or "").strip()
    if not value:
        return "absent", None
    days = _ISO_DAY.findall(value)
    if len(days) == 1 and _ISO_DAY.fullmatch(value):
        return "jour", days[0]
    if days:
        return "intervalle", days[0]
    return "absent", None


def _join_flags(*flags: str) -> str:
    return "+".join(flag for flag in flags if flag)


def reconcile_decree_date(normal: str | None, unitdate_text: str, title: str,
                          inventory_year: int | None) -> DecreeDate:
    """Reconcile the three witnesses of a decree date.

    Rules, in order:

    1. ``@normal`` is a day and the title carries no complete date, or carries that day:
       agreement, no flag.
    2. Conflict, and a title date falls in the inventory year while ``@normal`` does not:
       the title date is kept (``conflit-titre-retenu``). This is the August 1933 case,
       where ``@normal`` says 1938.
    3. Conflict, and the text of ``<unitdate>`` repeats a title date against ``@normal``:
       that date is kept (``conflit-titre-retenu``).
    4. Any other conflict: ``@normal`` is kept and flagged (``conflit-normal-retenu``).
    5. ``@normal`` is an interval: no single date (``intervalle``), the year is the start year.
    6. No ``@normal``: the last title date, flagged ``titre-seul``; else ``sans-date``.

    ``hors-inventaire`` is added when the final year is not the year of the inventory.
    """
    kind, normal_iso = _parse_normal(normal)
    title_candidates = full_dates(title)
    text_candidates = full_dates(unitdate_text)
    text_date = text_candidates[0] if text_candidates else None
    title_date = title_candidates[-1] if title_candidates else None
    in_year = [d for d in title_candidates if inventory_year is not None and int(d[:4]) == inventory_year]

    iso: str | None
    if kind == "jour":
        assert normal_iso is not None
        witnesses = title_candidates or ([text_date] if text_date else [])
        if not witnesses or normal_iso in witnesses:
            iso, flag = normal_iso, FLAG_OK
        elif in_year and int(normal_iso[:4]) != inventory_year:
            iso, flag = in_year[-1], FLAG_TITLE_KEPT
        elif text_date is not None and text_date in title_candidates:
            iso, flag = text_date, FLAG_TITLE_KEPT
        elif (not title_candidates and text_date is not None and inventory_year is not None
              and int(text_date[:4]) == inventory_year and int(normal_iso[:4]) != inventory_year):
            iso, flag = text_date, FLAG_TITLE_KEPT
        else:
            iso, flag = normal_iso, FLAG_NORMAL_KEPT
        year: int | None = int(iso[:4])
    elif kind == "intervalle":
        assert normal_iso is not None
        iso, flag, year = None, FLAG_RANGE, int(normal_iso[:4])
    elif title_candidates:
        iso = in_year[-1] if in_year else title_candidates[-1]
        flag, year = FLAG_TITLE_ONLY, int(iso[:4])
    else:
        iso, flag, year = None, FLAG_NONE, None
    if year is not None and inventory_year is not None and year != inventory_year:
        flag = _join_flags(flag, FLAG_OUTSIDE)
    return DecreeDate(iso, flag, year, title_date, text_date)
