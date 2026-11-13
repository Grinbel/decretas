"""Integrity checks: raw files against the manifest, counts against the expected table,
parser coverage, and the list of what the parser did not understand."""
from __future__ import annotations

import csv
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

from . import ead, links
from .build import DATABASE_FORMAT, database_format, read_manifest, read_only, sha256_of

EXPECTED_PATH = Path(__file__).resolve().parent / "reference" / "inventaires_attendus.tsv"
EXPECTED_FIELDS = ("inv", "annee", "trimestre", "decrets", "decrets_avec_noms", "personnes", "ecartees")


class VerifyError(Exception):
    """The verification cannot run (database absent…)."""


@dataclass(slots=True)
class Report:
    files: int = 0
    files_ok: int = 0
    file_problems: list[str] = field(default_factory=list)
    inventories: int = 0
    count_problems: list[str] = field(default_factory=list)
    coverage: list[tuple[str, int, int]] = field(default_factory=list)   # (label, numerator, denominator)
    flags: list[tuple[str, int]] = field(default_factory=list)
    unparsed: list[tuple[str, str, str]] = field(default_factory=list)   # (inventory, notice, text)
    discarded: list[tuple[str, str, str, str]] = field(default_factory=list)
    link_problems: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not (self.file_problems or self.count_problems or self.link_problems)


def check_files(source: Path, report: Report) -> None:
    """SHA-256 and size of every export against ``manifest.jsonl``; each file must end with </ead>."""
    manifest = read_manifest(source / "manifest.jsonl")
    files = ead.inventory_files(source)
    report.files = len(files)
    if not manifest:
        report.file_problems.append(f"manifeste absent ou vide : {source / 'manifest.jsonl'}")
    seen = set()
    for path in files:
        seen.add(path.stem)
        entry = manifest.get(path.stem)
        problems = []
        if entry is None:
            if manifest:
                problems.append("absent du manifeste")
        else:
            size = path.stat().st_size
            if size != entry.size:
                problems.append(f"taille {size} octets, manifeste {entry.size}")
            elif sha256_of(path) != entry.sha256:
                problems.append("empreinte SHA-256 différente du manifeste")
        with path.open("rb") as handle:
            handle.seek(max(0, path.stat().st_size - 64))
            if b"</ead>" not in handle.read():
                problems.append("le fichier ne se termine pas par </ead> (téléchargement tronqué ?)")
        if problems:
            report.file_problems.append(f"{path.name} : " + " ; ".join(problems))
        else:
            report.files_ok += 1
    for inventory in sorted(set(manifest) - seen):
        report.file_problems.append(f"{inventory}.xml : dans le manifeste, absent du disque")


def read_expected(path: Path = EXPECTED_PATH) -> dict[str, dict[str, str]]:
    try:
        with path.open(encoding="utf-8", newline="") as handle:
            return {row["inv"]: row for row in csv.DictReader(handle, delimiter="\t")}
    except FileNotFoundError:
        return {}


def write_expected(connection: sqlite3.Connection, path: Path = EXPECTED_PATH) -> int:
    """Record the counts of the current database as the expected ones (maintenance)."""
    rows = connection.execute(
        "SELECT inv, annee, trimestre, n_decrets, n_decrets_avec_noms, n_personnes, n_notices_ecartees "
        "FROM inventaire ORDER BY rang").fetchall()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerow(EXPECTED_FIELDS)
        writer.writerows([["" if value is None else value for value in row] for row in rows])
    return len(rows)


def check_counts(connection: sqlite3.Connection, report: Report, expected_path: Path = EXPECTED_PATH) -> None:
    expected = read_expected(expected_path)
    if not expected:
        report.count_problems.append(f"table des effectifs attendus absente : {expected_path}")
        return
    found = set()
    for inv, decrees, with_names, person_count, discarded in connection.execute(
            "SELECT inv, n_decrets, n_decrets_avec_noms, n_personnes, n_notices_ecartees FROM inventaire ORDER BY rang"):
        report.inventories += 1
        found.add(inv)
        row = expected.get(inv)
        if row is None:
            report.count_problems.append(f"{inv} : inventaire inconnu de la table des effectifs attendus")
            continue
        for label, actual, wanted in (("décrets", decrees, row["decrets"]),
                                      ("décrets avec noms", with_names, row["decrets_avec_noms"]),
                                      ("personnes", person_count, row["personnes"]),
                                      ("notices écartées", discarded, row["ecartees"])):
            if str(actual) != wanted:
                report.count_problems.append(
                    f"{inv} : {actual} {label}, {wanted} attendus (l'inventaire a peut-être été mis à jour par "
                    "les Archives nationales)")
    for inv in sorted(set(expected) - found):
        report.count_problems.append(f"{inv} : attendu, absent de la base")


def check_parser(connection: sqlite3.Connection, report: Report) -> None:
    one = lambda sql: connection.execute(sql).fetchone()[0]  # noqa: E731
    persons_total = one("SELECT COUNT(*) FROM personne")
    meta = dict(connection.execute("SELECT cle, valeur FROM meta"))
    lines = int(meta.get("lignes_lues", "0"))
    unparsed = int(meta.get("lignes_incomprises", "0"))
    report.coverage = [
        ("lignes de contenu comprises", lines - unparsed, lines),
        ("notices avec un nom saisi", one("SELECT COUNT(*) FROM personne WHERE nom_non_saisi = 0"), persons_total),
        ("notices avec une ligne de naissance", one("SELECT COUNT(*) FROM personne WHERE naissance_brut != ''"), persons_total),
        ("notices avec une année de naissance", one("SELECT COUNT(*) FROM personne WHERE naissance_annee IS NOT NULL"), persons_total),
        ("notices avec une date de naissance au jour", one("SELECT COUNT(*) FROM personne WHERE naissance_precision = 'jour'"), persons_total),
        ("notices avec un lieu de naissance", one("SELECT COUNT(*) FROM personne WHERE naissance_lieu != ''"), persons_total),
        ("notices avec un numéro de dossier normalisé", one("SELECT COUNT(*) FROM personne WHERE dossier != ''"), persons_total),
        ("notices avec une cote de dossier", one("SELECT COUNT(*) FROM personne WHERE cote_dossier != ''"), persons_total),
        ("notices avec leur propre lien d'images", one("SELECT COUNT(*) FROM personne WHERE lien_images != ''"), persons_total),
        ("épouses avec une année de naissance", one("SELECT COUNT(*) FROM apparente WHERE role = 'epouse' AND naissance_annee IS NOT NULL"),
         one("SELECT COUNT(*) FROM apparente WHERE role = 'epouse'")),
        ("enfants avec une année de naissance", one("SELECT COUNT(*) FROM apparente WHERE role = 'enfant' AND naissance_annee IS NOT NULL"),
         one("SELECT COUNT(*) FROM apparente WHERE role = 'enfant'")),
    ]
    report.flags = [
        ("décrets", one("SELECT COUNT(*) FROM decret")),
        ("décrets dont la date a été départagée (titre retenu)", one("SELECT COUNT(*) FROM decret WHERE date_drapeau LIKE 'conflit-titre-retenu%'")),
        ("décrets dont la date reste en conflit (@normal retenu)", one("SELECT COUNT(*) FROM decret WHERE date_drapeau LIKE 'conflit-normal-retenu%'")),
        ("décrets datés par leur seul titre", one("SELECT COUNT(*) FROM decret WHERE date_drapeau LIKE 'titre-seul%'")),
        ("décrets sans date unique (intervalle ou absente)", one("SELECT COUNT(*) FROM decret WHERE date IS NULL")),
        ("décrets dont l'année n'est pas celle de l'inventaire", one("SELECT COUNT(*) FROM decret WHERE date_drapeau LIKE '%hors-inventaire%'")),
        ("décrets à cote suspecte (BB/11 au lieu de BB/34)", one("SELECT COUNT(*) FROM decret WHERE cote_drapeau = 'suspecte-bb11'")),
        ("décrets sans cote", one("SELECT COUNT(*) FROM decret WHERE cote_drapeau = 'absente'")),
        ("décrets sans numéro de document", one("SELECT COUNT(*) FROM decret WHERE document = ''")),
        ("naissances conventionnelles (1 janvier, présumé, vers)", one("SELECT COUNT(*) FROM personne WHERE naissance_conventionnelle = 1")),
        ("années de naissance suspectes", one("SELECT COUNT(*) FROM personne WHERE naissance_suspecte = 1")),
        ("années de naissance suspectes d'épouses et d'enfants", one("SELECT COUNT(*) FROM apparente WHERE naissance_suspecte = 1")),
        ("résidences lues sur l'unique ligne placée après l'épouse", one("SELECT COUNT(*) FROM personne WHERE residence_ligne_epouse = 1")),
        ("personnes nées hors d'Algérie de parents dits algériens", one("SELECT COUNT(*) FROM personne WHERE regle LIKE 'parents-algeriens%'")),
        ("professions lues dans la ligne de naissance", one("SELECT COUNT(*) FROM personne WHERE profession_dans_naissance = 1")),
        ("noms non saisis", one("SELECT COUNT(*) FROM personne WHERE nom_non_saisi = 1")),
        ("enfants appariés par rang (non vérifié)", one("SELECT COUNT(*) FROM apparente WHERE appariement = 'position'")),
        ("enfants sans date attribuable (listes de longueurs différentes)", one("SELECT COUNT(*) FROM apparente WHERE appariement = 'longueurs-differentes'")),
        ("seconds demandeurs", one("SELECT COUNT(*) FROM apparente WHERE role = 'demandeur'")),
        ("notices du palier Algérie par l'épouse ou un enfant seulement", one("SELECT COUNT(*) FROM personne WHERE palier_par_apparente = 1")),
        ("noms inexploitables d'épouses et d'enfants (non exportés comme noms)", one("SELECT COUNT(*) FROM apparente WHERE nom_drapeau != ''")),
    ]
    report.flags.extend(
        (f"  dont « {flag} »", count) for flag, count in connection.execute(
            "SELECT nom_drapeau, COUNT(*) FROM apparente WHERE nom_drapeau != '' GROUP BY nom_drapeau ORDER BY nom_drapeau"))
    report.unparsed = connection.execute(
        "SELECT inv, notice_id, texte FROM ligne_incomprise ORDER BY inv, notice_id, rang").fetchall()
    report.discarded = connection.execute(
        "SELECT inv, notice_id, motif, titre FROM notice_ecartee ORDER BY inv, notice_id").fetchall()


def check_links(connection: sqlite3.Connection, report: Report) -> None:
    """Every copied link must be either the template form or a recorded exception."""
    notice = links.TEMPLATES[links.LINK_NOTICE]
    images = links.TEMPLATES[links.LINK_IMAGES]
    odd_notice = odd_images = missing_images = 0
    for table in ("decret", "personne"):
        for inv, notice_id, notice_link, image_link in connection.execute(
                f"SELECT inv, notice_id, lien_notice, lien_images FROM {table}"):
            if notice_link != notice.build_xml_form(inv, notice_id):
                odd_notice += 1
            if image_link and image_link != images.build_xml_form(inv, notice_id):
                odd_images += 1
            if table == "decret" and not image_link:
                missing_images += 1
    report.flags.extend([
        ("liens de notice hors gabarit (publiés comme exceptions)", odd_notice),
        ("liens d'images hors gabarit (publiés comme exceptions)", odd_images),
        ("décrets sans lien d'images", missing_images),
    ])
    empty = connection.execute("SELECT COUNT(*) FROM decret WHERE lien_notice = ''").fetchone()[0]
    empty += connection.execute("SELECT COUNT(*) FROM personne WHERE lien_notice = ''").fetchone()[0]
    if empty:
        report.link_problems.append(f"{empty} notices sans lien xlink:href dans le XML")


def check_link_table(report: Report, content_table: Path = links.CONTENT_TABLE_PATH) -> None:
    """The ids published in an-meta.json must exist in the ONE link table of the site."""
    report.link_problems.extend(links.check_content_table(content_table))


def verify(source: Path, database: Path, expected_path: Path = EXPECTED_PATH,
           content_table: Path = links.CONTENT_TABLE_PATH) -> Report:
    if not database.exists():
        raise VerifyError(f"base absente : {database} (lancer d'abord « construire »)")
    report = Report()
    check_files(source, report)
    connection = read_only(database)
    try:
        found_format = database_format(connection)
        if found_format != DATABASE_FORMAT:
            raise VerifyError(f"base d'un autre format ({found_format or 'illisible'}, attendu {DATABASE_FORMAT}) : "
                              f"{database} — relancer « construire »")
        check_counts(connection, report, expected_path)
        check_parser(connection, report)
        check_links(connection, report)
        check_link_table(report, content_table)
    finally:
        connection.close()
    return report
