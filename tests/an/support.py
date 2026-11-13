"""Shared helpers: a temporary corpus made of the synthetic fixtures, with its manifest."""
from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
from pathlib import Path

from decretas.an import build, export

FIXTURES = Path(__file__).resolve().parent / "fixtures"
TIMESTAMP = "2026-01-01T00:00:00Z"


def make_corpus(directory: Path) -> Path:
    """Copy the fixtures into ``directory/raw`` and write a manifest in the downloader's format."""
    raw = directory / "raw"
    raw.mkdir(parents=True)
    lines = []
    for source in sorted(FIXTURES.glob("FRAN_IR_*.xml")):
        target = raw / source.name
        shutil.copyfile(source, target)
        data = target.read_bytes()
        lines.append(json.dumps({
            "id": source.stem, "http": "200", "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(),
            "at": "2026-10-16T22:01:32+02:00", "url": "https://exemple.invalid/export?irId=" + source.stem,
            "saved_as": source.name, "ok": True}))
    (raw / "manifest.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return raw


def build_all(directory: Path, *, include_filae: bool = False, timestamp: str = TIMESTAMP) -> tuple[Path, Path]:
    """Build the database and the site files of the fixture corpus. Returns (database, site dir)."""
    raw = directory / "raw"
    if not raw.exists():
        make_corpus(directory)
    database = directory / "build" / "an.sqlite"
    site = directory / "site"
    build.build_database(raw, database)
    export.export_site(database, site, include_filae=include_filae, timestamp=timestamp)
    return database, site


def rows(database: Path, sql: str, *args: object) -> list[tuple]:
    connection = sqlite3.connect(database)
    try:
        return connection.execute(sql, args).fetchall()
    finally:
        connection.close()


def load_columnar(path: Path) -> tuple[dict, list[dict]]:
    """A columnar file as (whole document, list of row dictionaries)."""
    document = json.loads(path.read_text(encoding="utf-8"))
    fields = document["champs"]
    return document, [dict(zip(fields, row)) for row in document["lignes"]]
