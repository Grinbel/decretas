"""Builders of synthetic volumes for the tests.

Every name below is invented (Testaoui, Fictivo, Exemplmann …): the fixtures reproduce the
*formats* of the bulletin and the damage the OCR does to them, never a real person.
"""
from __future__ import annotations

import gzip
import json
from pathlib import Path

from decretas.bogga import volume


def title_page(year: int, number: int) -> str:
    """First page of an issue, as the OCR gives it."""
    return (f"BULLETIN OFFICIEL\nDU\nGOUVERNEMENT GÉNÉRAL\nDE L'ALGÉRIE.\nANNÉE {year}.\nN° {number}.\n"
            "SOMMAIRE.\nN°s DATES. ANALYSE. PAGES.\n1 5 janvier Arrêté fictif .......... 2")


def closing(date_text: str) -> str:
    return f"CERTIFIÉ CONFORME : Alger, le {date_text}.\nLe Conseiller de Gouvernement,\nALGER. — IMPRIMERIE FICTIVE."


def make_pages(texts: list[str], first_printed: int = 1, unnumbered: int = 0) -> list[volume.Page]:
    """Pages from their texts. The first `unnumbered` leaves carry no printed number; the
    following ones are numbered from `first_printed`."""
    pages = []
    for leaf, text in enumerate(texts):
        printed = first_printed + leaf - unnumbered if leaf >= unnumbered else None
        pages.append(volume.Page(leaf=leaf, printed=printed, printed_raw=str(printed or ""), computed=False, text=text))
    return pages


def one_issue(year: int, body_pages: list[str], number: int = 500, closing_date: str | None = None) -> list[volume.Page]:
    """A volume made of one issue: title page, body pages, closing line on the last page."""
    texts = [title_page(year, number)] + list(body_pages)
    texts[-1] = texts[-1] + "\n" + closing(closing_date or f"30 décembre {year}")
    return make_pages(texts)


def write_volume_files(directory: Path, doc: str, texts: list[str], printed: dict[int, str], version2: bool = True) -> None:
    """Write the three Internet Archive derivative files of a synthetic volume."""
    directory.mkdir(parents=True, exist_ok=True)
    full = ""
    index = []
    for text in texts:
        start = len(full)
        full += text + "\n"
        index.append([start, len(full) - 1, 0, 0])
    with gzip.open(directory / f"{doc}_hocr_searchtext.txt.gz", "wb") as handle:
        handle.write(full.encode("utf-8"))
    with gzip.open(directory / f"{doc}_hocr_pageindex.json.gz", "wb") as handle:
        handle.write(json.dumps(index).encode("utf-8"))
    if version2:
        pages = [{"leafNum": leaf, "confidence": None, "pageNumber": printed.get(leaf, ""), "pageProb": None, "wordConf": None}
                 for leaf in range(len(texts))]
        data = {"identifier": "synthetique", "format-version": "2", "confidence": 90, "pages": pages}
    else:                               # older format: leafNum starts at 1, leaf 0 has no row
        pages = [{"leafNum": leaf, "ocr_value": [], "confidence": 100, "pageNumber": printed.get(leaf, "")}
                 for leaf in range(1, len(texts))]
        data = {"identifier": "synthetique", "confidence": 94.2, "pages": len(pages)}
        data["pages"] = pages
    (directory / f"{doc}_page_numbers.json").write_text(json.dumps(data), encoding="utf-8")


def write_metadata(directory: Path, docs: list[str]) -> None:
    files = [{"name": doc + suffix} for doc in docs
             for suffix in ("_hocr_searchtext.txt.gz", "_hocr_pageindex.json.gz", "_page_numbers.json", ".pdf")]
    data = {"dir": "/1/items/synthetique", "workable_servers": ["ia000000.us.archive.org"], "files": files,
            "metadata": {"identifier": "synthetique"}}
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "_metadata.json").write_text(json.dumps(data), encoding="utf-8")
