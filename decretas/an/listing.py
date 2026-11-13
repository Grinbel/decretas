"""Flat list of every decree, straight from the XML exports (no database needed).

Replaces the old ``scripts/lister-decrets-algeriens.py``: every decree with its reconciled
date, family, Algeria class, flags, state and the two links copied from the XML.
"""
from __future__ import annotations

import csv
from collections.abc import Iterable
from pathlib import Path

from . import ead, taxonomy
from .build import process_inventory

CSV_FIELDS: tuple[str, ...] = (
    "annee", "trimestre", "date", "drapeau_date", "date_normal", "date_titre", "titre", "famille", "territoires",
    "classe_algerie", "cote", "drapeau_cote", "cote_suggeree", "document", "etat", "personnes_indexees",
    "contexte", "decret_parent", "inventaire", "notice_id", "lien_notice", "lien_images")


def decree_records(paths: Iterable[Path]) -> list[dict[str, object]]:
    """One record per decree of the given exports, in chronological and register order."""
    inventories = [ead.read_inventory(path) for path in paths]
    inventories.sort(key=lambda raw: (raw.year or 0, raw.quarter or 0, raw.inventory))
    records: list[dict[str, object]] = []
    for raw in inventories:
        if raw.is_root:
            continue
        rows = process_inventory(raw, frozenset(), parse_persons=False)
        for _seq, row in rows.decrees:
            (inventory, notice_id, _notice_seq, parent, context, title, date, date_flag, date_normal, _date_text,
             date_title, year, quarter, family, territories, algeria_class, cote, _cote_source, cote_flag,
             cote_suggestion, document, person_count, state, notice_link, image_link) = row
            records.append({
                "annee": year, "trimestre": quarter or "", "date": date or "", "drapeau_date": date_flag,
                "date_normal": date_normal or "", "date_titre": date_title or "", "titre": title, "famille": family,
                "territoires": territories, "classe_algerie": algeria_class, "cote": cote,
                "drapeau_cote": cote_flag, "cote_suggeree": cote_suggestion, "document": document, "etat": state,
                "personnes_indexees": person_count, "contexte": context, "decret_parent": parent,
                "inventaire": inventory, "notice_id": notice_id, "lien_notice": notice_link,
                "lien_images": image_link})
    return records


def only_algeria(records: list[dict[str, object]]) -> list[dict[str, object]]:
    return [record for record in records if record["classe_algerie"] != taxonomy.CLASS_NONE]


def write_csv(records: list[dict[str, object]], path: Path) -> None:
    """UTF-8 with a byte-order mark, so that spreadsheet programs read the accents."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(records)
