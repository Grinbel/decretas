"""From the XML exports to the SQLite database ``data/build/an.sqlite``.

The database holds EVERY decree and every person notice of the 84 inventories (not only the
Algeria tier), with the raw text next to each parsed field and the two links copied from
the XML. It contains no timestamp: two builds of the same inputs are byte-identical.

Table and column names are French on purpose: they are a data format, shared with the site
export (docs/format-donnees-an.md), not program identifiers.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from . import ead, gazetteer, hints, persons, taxonomy
from .dates import has_full_date, reconcile_decree_date

# Years whose name index is covered -- until the Archives nationales say otherwise -- by the
# clause of the root inventory FRAN_IR_057397 and of the 1899 inventory FRAN_IR_057213:
# "Pour les années indexées par Filae, toute publication sur internet à des fins de recherche
# nominative […] d'un corpus concernant plus de 1000 individus devra faire l'objet d'une
# autorisation préalable de la société Filae." The root says the indexing of 1898-1912 and
# 1928 was "engagée en partenariat avec Filae"; who keyed 1898 and January-March 1928 is not
# established, so they are treated as covered (verification.md, sections an-local/an-remote).
FILAE_YEARS: frozenset[int] = frozenset(range(1898, 1913)) | {1928}

DATABASE_FORMAT = "decretas-an-sqlite/3"

STATE_INDEXED = "indexe"
STATE_PARTIAL = "partiel"
STATE_IMAGE = "image"
INDEXED_SHARE = 0.9   # an inventory is "indexed" when at least 90 % of its decrees carry names

SCHEMA = """
CREATE TABLE inventaire(
  inv TEXT PRIMARY KEY, rang INTEGER NOT NULL, titre TEXT NOT NULL, annee INTEGER, trimestre INTEGER,
  periode_normal TEXT, periode_texte TEXT, cotes TEXT, lieu_conservation TEXT, depot TEXT, auteur TEXT,
  lien TEXT NOT NULL, reutilisation TEXT, communicabilite TEXT, clause_filae_dans_le_xml INTEGER NOT NULL,
  annee_filae INTEGER NOT NULL, n_decrets INTEGER NOT NULL, n_decrets_avec_noms INTEGER NOT NULL,
  n_personnes INTEGER NOT NULL, n_notices_ecartees INTEGER NOT NULL, etat TEXT NOT NULL,
  octets INTEGER, sha256 TEXT, telecharge_le TEXT);
CREATE TABLE decret(
  decret_id INTEGER PRIMARY KEY, inv TEXT NOT NULL REFERENCES inventaire(inv), notice_id TEXT NOT NULL,
  seq INTEGER NOT NULL, decret_parent TEXT, contexte TEXT, titre TEXT NOT NULL,
  date TEXT, date_drapeau TEXT NOT NULL, date_normal TEXT, date_texte TEXT, date_titre TEXT,
  annee INTEGER, trimestre INTEGER, famille TEXT NOT NULL, territoires TEXT NOT NULL, classe_algerie TEXT NOT NULL,
  cote TEXT NOT NULL, cote_source TEXT NOT NULL, cote_drapeau TEXT NOT NULL, cote_suggeree TEXT NOT NULL,
  document TEXT NOT NULL, n_personnes INTEGER NOT NULL, etat TEXT NOT NULL,
  lien_notice TEXT NOT NULL, lien_images TEXT NOT NULL, UNIQUE(inv, notice_id));
CREATE TABLE personne(
  personne_id INTEGER PRIMARY KEY, decret_id INTEGER NOT NULL REFERENCES decret(decret_id),
  inv TEXT NOT NULL, notice_id TEXT NOT NULL, seq INTEGER NOT NULL,
  titre_brut TEXT NOT NULL, nom_brut TEXT NOT NULL, nom_non_saisi INTEGER NOT NULL,
  nom TEXT, prenoms TEXT, nom_naissance TEXT, nom_marital TEXT, alias TEXT, variantes TEXT, mention TEXT,
  naissance_brut TEXT NOT NULL, naissance_date TEXT, naissance_precision TEXT, naissance_annee INTEGER,
  naissance_conventionnelle INTEGER NOT NULL, naissance_suspecte INTEGER NOT NULL, naissance_date_corrigee TEXT,
  naissance_lieu TEXT, origine_parents TEXT, residence TEXT, residence_ligne_epouse INTEGER NOT NULL,
  profession TEXT, profession_dans_naissance INTEGER NOT NULL,
  mentions TEXT, dossier_brut TEXT, dossier TEXT, cote_dossier TEXT,
  lien_notice TEXT NOT NULL, lien_images TEXT NOT NULL,
  ne_en_algerie TEXT NOT NULL, reside_en_algerie TEXT NOT NULL, indice TEXT NOT NULL, regle TEXT NOT NULL,
  palier_algerie INTEGER NOT NULL, palier_par_apparente INTEGER NOT NULL, UNIQUE(inv, notice_id));
CREATE TABLE apparente(
  apparente_id INTEGER PRIMARY KEY, personne_id INTEGER NOT NULL REFERENCES personne(personne_id),
  rang INTEGER NOT NULL, role TEXT NOT NULL, texte_brut TEXT NOT NULL, nom_brut TEXT NOT NULL,
  nom TEXT, prenoms TEXT, nom_naissance TEXT,
  naissance_brut TEXT, naissance_date TEXT, naissance_precision TEXT, naissance_annee INTEGER,
  naissance_conventionnelle INTEGER NOT NULL, naissance_suspecte INTEGER NOT NULL, naissance_lieu TEXT,
  residence TEXT, appariement TEXT NOT NULL, nom_drapeau TEXT NOT NULL,
  ne_en_algerie TEXT NOT NULL, reside_en_algerie TEXT NOT NULL);
CREATE TABLE ligne_incomprise(inv TEXT NOT NULL, notice_id TEXT NOT NULL, rang INTEGER NOT NULL, texte TEXT NOT NULL);
CREATE TABLE notice_ecartee(inv TEXT NOT NULL, notice_id TEXT NOT NULL, motif TEXT NOT NULL, titre TEXT NOT NULL);
CREATE TABLE meta(cle TEXT PRIMARY KEY, valeur TEXT NOT NULL);
CREATE INDEX personne_decret ON personne(decret_id);
CREATE INDEX apparente_personne ON apparente(personne_id);
CREATE INDEX decret_inv ON decret(inv);
"""

REASON_NOT_NOMINATIVE = "notice sans nom de personne, sans contenu et sans image (décret ou règlement classé parmi les personnes)"
REASON_ORPHAN = "notice de personne sans décret englobant"


class BuildError(Exception):
    """The build cannot proceed (no input, unreadable manifest…)."""


@dataclass(slots=True)
class ManifestEntry:
    sha256: str
    size: int
    downloaded_at: str
    url: str


@dataclass(slots=True)
class InventoryRows:
    """Rows of one inventory, ready for insertion. Decree and person ids are local sequence numbers."""

    inventory: tuple
    decrees: list[tuple] = field(default_factory=list)          # (seq, row without decret_id)
    persons: list[tuple] = field(default_factory=list)          # (decree seq, row, relatives, unparsed)
    discarded: list[tuple] = field(default_factory=list)


@dataclass(slots=True)
class BuildStats:
    inventories: int = 0
    decrees: int = 0
    persons: int = 0
    relatives: int = 0
    discarded: int = 0
    unparsed_lines: int = 0
    lines: int = 0
    root_inventories: list[str] = field(default_factory=list)


def read_only(database: Path) -> sqlite3.Connection:
    """Open a database read-only, whatever characters its path holds ('?', '#', '%'…)."""
    return sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True)


def database_format(connection: sqlite3.Connection) -> str:
    """Format written by the build that produced the database; '' when it cannot be read."""
    try:
        row = connection.execute("SELECT valeur FROM meta WHERE cle = 'format'").fetchone()
    except sqlite3.DatabaseError:
        return ""
    return str(row[0]) if row else ""


# ----------------------------------------------------------------------------- manifest

def read_manifest(path: Path) -> dict[str, ManifestEntry]:
    """Last successful entry of ``manifest.jsonl`` for each inventory. Missing file -> {}."""
    entries: dict[str, ManifestEntry] = {}
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return entries
    for number, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as error:
            raise BuildError(f"{path} ligne {number} : JSON illisible ({error})") from error
        if not isinstance(record, dict) or not record.get("ok") or "id" not in record:
            continue
        saved_as = str(record.get("saved_as") or f"{record['id']}.xml")
        if saved_as != f"{record['id']}.xml":
            continue    # a refreshed copy kept beside the reference file
        entries[str(record["id"])] = ManifestEntry(
            sha256=str(record.get("sha256", "")), size=int(record.get("bytes", 0)),
            downloaded_at=str(record.get("at", "")), url=str(record.get("url", "")))
    return entries


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


# ----------------------------------------------------------------------------- one inventory

def inventory_state(decrees: int, decrees_with_names: int) -> str:
    if decrees_with_names == 0:
        return STATE_IMAGE
    if decrees and decrees_with_names / decrees >= INDEXED_SHARE:
        return STATE_INDEXED
    return STATE_PARTIAL


def _context_of(notice: ead.RawNotice, by_seq: dict[int, ead.RawNotice]) -> tuple[str, str]:
    """(enclosing decree id, title of the enclosing group) of a decree notice."""
    parent_decree, group_title = "", ""
    parent = by_seq.get(notice.parent_seq) if notice.parent_seq is not None else None
    while parent is not None:
        if parent.kind == ead.KIND_DECREE and not parent_decree:
            parent_decree = parent.notice_id
        if parent.kind == ead.KIND_GROUP and not group_title:
            group_title = parent.title
        parent = by_seq.get(parent.parent_seq) if parent.parent_seq is not None else None
    return parent_decree, group_title


def _birth_is_suspect(birth_year: int | None, decree_year: int | None) -> bool:
    """A birth after the decree, or more than a century before it: flagged, never corrected."""
    if birth_year is None or decree_year is None:
        return False
    return birth_year > decree_year or decree_year - birth_year > 100


def process_inventory(raw: ead.RawInventory, safe_localities: frozenset[str], rank: int = 0,
                      manifest: ManifestEntry | None = None, *, parse_persons: bool = True) -> InventoryRows:
    """Turn one parsed inventory into database rows (pure function of its inputs)."""
    by_seq = {notice.seq: notice for notice in raw.notices}
    person_count: dict[int, int] = {}
    for notice in raw.notices:
        if notice.kind == ead.KIND_PERSON and notice.decree_seq is not None:
            person_count[notice.decree_seq] = person_count.get(notice.decree_seq, 0) + 1
    decree_notices = [n for n in raw.notices if n.kind == ead.KIND_DECREE]
    with_names = sum(1 for n in decree_notices if person_count.get(n.seq))
    state = inventory_state(len(decree_notices), with_names)
    filae_year = raw.year in FILAE_YEARS

    decree_class: dict[int, taxonomy.DecreeClass] = {}
    decree_year: dict[int, int | None] = {}
    rows = InventoryRows(inventory=())
    for notice in decree_notices:
        date = reconcile_decree_date(notice.unitdate_normal, notice.unitdate_text, notice.title, raw.year)
        classes = taxonomy.classify_decree(notice.title)
        cote = taxonomy.check_cote(notice.unitid(ead.UNITID_IDENTIFIER), notice.unitid(ead.UNITID_CONSULTATION))
        parent_decree, group_title = _context_of(notice, by_seq)
        count = person_count.get(notice.seq, 0)
        decree_state = STATE_IMAGE if not count else (STATE_INDEXED if state == STATE_INDEXED else STATE_PARTIAL)
        decree_class[notice.seq] = classes
        decree_year[notice.seq] = date.year
        rows.decrees.append((notice.seq, (
            raw.inventory, notice.notice_id, notice.seq, parent_decree, group_title, notice.title,
            date.iso, date.flag, notice.unitdate_normal, notice.unitdate_text, date.title_date,
            raw.year, raw.quarter, classes.family, "+".join(classes.territories), classes.algeria_class,
            cote.cote, cote.source, cote.flag, cote.suggestion, notice.unitid(ead.UNITID_PIECES),
            count, decree_state, notice.href, notice.image_links[0] if notice.image_links else "")))

    discarded = 0
    persons_total = 0
    for notice in raw.notices:
        if notice.kind == ead.KIND_NOT_NOMINATIVE:
            rows.discarded.append((raw.inventory, notice.notice_id, REASON_NOT_NOMINATIVE, notice.title))
            discarded += 1
            continue
        if notice.kind != ead.KIND_PERSON:
            continue
        if notice.decree_seq is None:
            rows.discarded.append((raw.inventory, notice.notice_id, REASON_ORPHAN, notice.title))
            discarded += 1
            continue
        persons_total += 1
        if parse_persons:
            rows.persons.append(_person_rows(raw, notice, decree_class[notice.decree_seq],
                                             decree_year[notice.decree_seq], safe_localities))

    rows.inventory = (
        raw.inventory, rank, raw.title, raw.year, raw.quarter, raw.period_normal, raw.period_text, raw.cotes,
        raw.physloc, raw.repository, raw.author, raw.link, raw.userestrict, raw.accessrestrict,
        int("filae" in raw.userestrict.lower()), int(filae_year), len(decree_notices), with_names,
        persons_total, discarded, state,
        manifest.size if manifest else None, manifest.sha256 if manifest else None,
        manifest.downloaded_at if manifest else None)
    return rows


def _person_rows(raw: ead.RawInventory, notice: ead.RawNotice, decree: taxonomy.DecreeClass,
                 decree_year: int | None, safe_localities: frozenset[str]) -> tuple:
    fields = persons.parse_person_lines([line.text for line in notice.lines])
    # "Name not entered": empty title, or a title without <persname> that holds a complete
    # date -- three persons of 1890 whose name was overwritten by a decree title.
    name_missing = not notice.title or (notice.persname_count == 0 and has_full_date(notice.title))
    name_raw = "" if name_missing else notice.title
    name = persons.parse_name(name_raw)
    birth = fields.birth
    dossier_raw = notice.unitid(ead.UNITID_PIECES) or notice.unitid(ead.UNITID_IDENTIFIER)
    hint = hints.classify_person(
        name=name_raw, birth_place=birth.place, birth_parents=birth.parents, parents_origin=fields.parents_origin,
        residence=fields.residence, profession=fields.profession,
        other_text=" ".join(fields.notes + fields.unparsed),
        decree_admits=decree.algeria_class in (taxonomy.CLASS_A1, taxonomy.CLASS_A2), safe_localities=safe_localities,
        other_residences=tuple(fields.other_residences))
    # Algeria tier: the decree's class, a birth or a residence in Algeria, the hint M -- and parents the
    # notice calls Algerian ('Tunis, Tunisie, de père algérien'), whatever the name looks like.
    own_tier = (decree.algeria_class != taxonomy.CLASS_NONE or bool(hint.born_in_algeria)
                or bool(hint.lives_in_algeria) or hint.code == hints.HINT_MUSLIM_ALGERIAN
                or hint.algerian_parents)
    # A spouse, a child or a second applicant born or residing in Algeria also brings the notice in:
    # the family is searched through any of its members. The principal's own hint is left untouched.
    relative_places = [(
        gazetteer.algeria_rule(hints.birth_place_proper(relative.birth.place, relative.birth.parents), safe_localities),
        gazetteer.algeria_rule(relative.residence, safe_localities)) for relative in fields.relatives]
    by_relative = not own_tier and any(born or lives for born, lives in relative_places)
    in_tier = own_tier or by_relative
    row = (
        raw.inventory, notice.notice_id, notice.seq, notice.title, name_raw, int(name_missing),
        name.surname, name.given, name.maiden, name.married, name.alias, name.variants, name.mention,
        birth.raw, birth.date, birth.precision, birth.year, int(birth.conventional),
        int(_birth_is_suspect(birth.year, decree_year)), birth.alt_date, birth.place,
        fields.parents_origin or birth.parents, fields.residence, int(fields.residence_from_spouse_line),
        fields.profession, int(fields.profession_from_birth_line), " // ".join(fields.notes),
        dossier_raw, persons.normalise_dossier(dossier_raw), notice.unitid(ead.UNITID_CONSULTATION),
        notice.href, notice.image_links[0] if notice.image_links else "",
        hint.born_in_algeria, hint.lives_in_algeria, hint.code, hint.rule, int(in_tier), int(by_relative))
    relatives = [(
        rank, relative.role, relative.raw, relative.name_raw, relative.name.surname, relative.name.given,
        relative.name.maiden, relative.birth.raw, relative.birth.date, relative.birth.precision,
        relative.birth.year, int(relative.birth.conventional),
        int(_birth_is_suspect(relative.birth.year, decree_year)), relative.birth.place, relative.residence,
        relative.pairing, persons.name_flag(relative.name_raw, relative.raw), born, lives)
        for rank, (relative, (born, lives)) in enumerate(zip(fields.relatives, relative_places))]
    unparsed = [(raw.inventory, notice.notice_id, rank, text) for rank, text in enumerate(fields.unparsed)]
    return notice.decree_seq, row, relatives, unparsed, fields.line_count


# ----------------------------------------------------------------------------- whole corpus

def build_database(source: Path, database: Path, *, gazetteer_path: Path = gazetteer.GAZETTEER_PATH,
                   progress: Callable[[str], None] | None = None) -> BuildStats:
    """Parse every inventory of ``source`` and write a fresh database."""
    files = ead.inventory_files(source)
    if not files:
        raise BuildError(f"aucun inventaire FRAN_IR_*.xml dans {source}")
    manifest = read_manifest(source / "manifest.jsonl")
    safe_localities = gazetteer.load_safe_localities(gazetteer_path)
    database.parent.mkdir(parents=True, exist_ok=True)
    partial = database.with_name(database.name + ".part")
    if partial.exists():
        partial.unlink()
    stats = BuildStats()
    # Headers first (cheap), to process the inventories in chronological order whatever their id.
    headers = sorted(((ead.inventory_year(_title_of(path)) or 0, ead.inventory_quarter(_title_of(path)) or 0,
                       path.stem), path) for path in files)
    connection = sqlite3.connect(partial)
    try:
        connection.executescript("PRAGMA journal_mode=OFF; PRAGMA synchronous=OFF;" + SCHEMA)
        decree_id = person_id = 0
        rank = 0
        for _, path in headers:
            raw = ead.read_inventory(path)
            if raw.is_root:
                stats.root_inventories.append(raw.inventory)
                continue
            rank += 1
            rows = process_inventory(raw, safe_localities, rank, manifest.get(raw.inventory))
            connection.execute("INSERT INTO inventaire VALUES(" + ",".join("?" * 24) + ")", rows.inventory)
            ids: dict[int, int] = {}
            for seq, row in rows.decrees:
                decree_id += 1
                ids[seq] = decree_id
                connection.execute("INSERT INTO decret VALUES(" + ",".join("?" * 26) + ")", (decree_id, *row))
            for decree_seq, row, relatives, unparsed, line_count in rows.persons:
                person_id += 1
                connection.execute("INSERT INTO personne VALUES(" + ",".join("?" * 40) + ")",
                                   (person_id, ids[decree_seq], *row))
                connection.executemany("INSERT INTO apparente VALUES(NULL,?," + ",".join("?" * 19) + ")",
                                       [(person_id, *relative) for relative in relatives])
                connection.executemany("INSERT INTO ligne_incomprise VALUES(?,?,?,?)", unparsed)
                stats.relatives += len(relatives)
                stats.unparsed_lines += len(unparsed)
                stats.lines += line_count
            connection.executemany("INSERT INTO notice_ecartee VALUES(?,?,?,?)", rows.discarded)
            stats.inventories += 1
            stats.decrees += len(rows.decrees)
            stats.persons += len(rows.persons)
            stats.discarded += len(rows.discarded)
            if progress:
                progress(f"{raw.inventory}  {raw.year or '?'}{'-T' + str(raw.quarter) if raw.quarter else ''}  "
                         f"{len(rows.decrees)} décrets, {len(rows.persons)} personnes")
        meta = {
            "format": DATABASE_FORMAT,
            "inventaires_racine": ",".join(stats.root_inventories),
            "lignes_lues": str(stats.lines),
            "lignes_incomprises": str(stats.unparsed_lines),
            "localites_du_repertoire": str(len(safe_localities)),
            "annees_filae": ",".join(str(year) for year in sorted(FILAE_YEARS)),
        }
        connection.executemany("INSERT INTO meta VALUES(?,?)", sorted(meta.items()))
        connection.commit()
    finally:
        connection.close()
    partial.replace(database)
    return stats


def _title_of(path: Path) -> str:
    """Inventory title read from the head of the file, without parsing the whole document."""
    with path.open("rb") as handle:
        head = handle.read(8192).decode("utf-8", errors="replace")
    start = head.find("<titleproper")
    if start < 0:
        return ""
    end = head.find("</titleproper>", start)
    inner = head[head.find(">", start) + 1:end if end > 0 else len(head)]
    return " ".join(inner.split())
