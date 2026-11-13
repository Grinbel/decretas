"""Loading one digitised volume: OCR text cut into leaves, with printed page numbers.

Inputs (Internet Archive derivatives, untrusted data — only parsed as text/JSON):
- `<doc>_hocr_searchtext.txt.gz`: the whole OCR text, one hOCR paragraph per line;
- `<doc>_hocr_pageindex.json.gz`: one row per leaf, [char_start, char_end, ...], counted
  in Unicode characters of the decoded search text;
- `<doc>_page_numbers.json`: {"pages": [{"leafNum": n, "pageNumber": "496", ...}]}.

A *leaf* is the image index used in archive.org addresses (`.../page/n<leaf>`); the
*printed page* is the number printed on the paper.
"""
from __future__ import annotations

import gzip
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path


class VolumeFormatError(Exception):
    """One of the three files does not have the expected shape."""


@dataclass(frozen=True)
class Page:
    """One leaf. `printed` is the page number to cite (None when unknown); `printed_raw`
    is what the page-number file says; `computed` is True when `printed` was inferred from
    the neighbouring leaves because the file's own value was missing or inconsistent."""

    leaf: int
    printed: int | None
    printed_raw: str
    computed: bool
    text: str

    @property
    def lines(self) -> list[str]:
        return [line for line in self.text.split("\n") if line.strip()]


def read_searchtext(path: Path) -> str:
    try:
        with gzip.open(path, "rb") as handle:
            return handle.read().decode("utf-8", errors="replace")
    except (OSError, EOFError) as exc:
        raise VolumeFormatError(f"texte illisible : {path.name} ({exc})") from exc


def read_pageindex(path: Path) -> list[tuple[int, int]]:
    try:
        with gzip.open(path, "rb") as handle:
            rows = json.loads(handle.read().decode("utf-8"))
    except (OSError, EOFError, ValueError) as exc:
        raise VolumeFormatError(f"index des pages illisible : {path.name} ({exc})") from exc
    if not isinstance(rows, list):
        raise VolumeFormatError(f"index des pages inattendu : {path.name}")
    spans = []
    for row in rows:
        if not (isinstance(row, list) and len(row) >= 2 and all(isinstance(v, int) for v in row[:2])):
            raise VolumeFormatError(f"ligne d'index inattendue : {path.name}")
        spans.append((row[0], row[1]))
    return spans


def read_page_numbers(path: Path) -> dict[int, str]:
    """leaf -> printed page as written in the file ('' when none). Both format versions."""
    try:
        with path.open(encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError) as exc:
        raise VolumeFormatError(f"numéros de page illisibles : {path.name} ({exc})") from exc
    pages = data.get("pages") if isinstance(data, dict) else None
    if not isinstance(pages, list):
        raise VolumeFormatError(f"numéros de page inattendus : {path.name}")
    printed: dict[int, str] = {}
    for entry in pages:
        if isinstance(entry, dict) and isinstance(entry.get("leafNum"), int):
            printed[entry["leafNum"]] = str(entry.get("pageNumber") or "")
    return printed


def reconcile_page_numbers(raw: dict[int, str], leaves: int, window: int = 6) -> list[tuple[int | None, bool]]:
    """Printed page of each leaf, corrected by its neighbours.

    Within the body of a volume, leaf - page is constant over long runs. A leaf whose own
    number is missing, non numeric or at odds with at least three agreeing neighbours gets
    the neighbours' value and is marked computed. Returns [(page or None, computed)].
    """
    numeric: dict[int, int] = {}
    for leaf, value in raw.items():
        if value.isdigit() and 0 < int(value) < 5000:
            numeric[leaf] = int(value)
    result: list[tuple[int | None, bool]] = []
    for leaf in range(leaves):
        offsets = Counter(
            other - numeric[other]
            for other in range(leaf - window, leaf + window + 1)
            if other != leaf and other in numeric
        )
        own = numeric.get(leaf)
        if not offsets:
            result.append((own, False))
            continue
        offset, support = offsets.most_common(1)[0]
        expected = leaf - offset
        if own is not None and (own == expected or support < 3):
            result.append((own, False))
        elif support >= 3 and expected > 0:
            result.append((expected, True))
        else:
            result.append((own, False))
    return result


def load_volume(searchtext: Path, pageindex: Path, page_numbers: Path) -> list[Page]:
    text = read_searchtext(searchtext)
    spans = read_pageindex(pageindex)
    raw = read_page_numbers(page_numbers)
    reconciled = reconcile_page_numbers(raw, len(spans))
    pages = []
    for leaf, (start, end) in enumerate(spans):
        printed, computed = reconciled[leaf]
        pages.append(Page(leaf=leaf, printed=printed, printed_raw=raw.get(leaf, ""), computed=computed,
                          text=text[start:end]))
    return pages


def page_mapping_summary(pages: list[Page]) -> dict[str, int | None]:
    """Summary of the leaf/page relation: dominant offset and how many leaves follow it."""
    offsets = Counter(page.leaf - page.printed for page in pages if page.printed is not None)
    numbered = sum(offsets.values())
    if not offsets:
        return {"feuilles": len(pages), "pages_numerotees": 0, "decalage_dominant": None,
                "pages_au_decalage_dominant": 0, "pages_calculees": 0}
    offset, count = offsets.most_common(1)[0]
    return {
        "feuilles": len(pages),
        "pages_numerotees": numbered,
        "decalage_dominant": offset,
        "pages_au_decalage_dominant": count,
        "pages_calculees": sum(1 for page in pages if page.computed),
    }
