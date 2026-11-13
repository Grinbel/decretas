"""From the database to the three site files: an-decrets.json, an-personnes.json, an-meta.json.

The "Algeria tier" is what the static site downloads once and searches in the browser:

* every decree of class A1, A2, A3 or R -- including the image-only ones, which drive the
  guided search -- plus any other decree an exported person belongs to;
* every person notice that is under such a decree, OR born or residing in Algeria, OR carries
  the hint "probable Muslim Algerian", OR whose parents the notice calls Algerian, OR whose
  spouse, child or second applicant is born or resides in Algeria -- with its spouse, children
  and second applicant as searchable name occurrences linked to it.

Three things are NOT exported, each counted in an-meta.json:

* Filae clause: unless ``include_filae`` is set, the person names of the years covered by the
  clause are WITHHELD; their decrees are still exported, in the state ``retenu-filae``.
* Privacy: unless ``include_possibly_living`` is set, the name occurrence of a person who may
  still be alive is WITHHELD (``privacy_reason`` below). The rule depends on the YEAR of the
  generation timestamp, and on nothing else that varies.
* Data-entry debris: a spouse or a child whose "name" is a date, a dossier number, a figure or
  nothing (``persons.name_flag``) is not a name occurrence. The database keeps its raw text.

The format is documented in docs/format-donnees-an.md. Output is deterministic: an-decrets.json
and an-personnes.json depend on the inputs and on the year of the timestamp; the timestamp
itself is isolated in an-meta.json.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import re
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import hints, links, persons, taxonomy
from .build import (DATABASE_FORMAT, FILAE_YEARS, INDEXED_SHARE, STATE_IMAGE, STATE_INDEXED, STATE_PARTIAL,
                    database_format, inventory_state, read_only)

FILE_DECREES = "an-decrets.json"
FILE_PERSONS = "an-personnes.json"
FILE_META = "an-meta.json"

STATE_WITHHELD = "retenu-filae"
STATES: tuple[str, ...] = (STATE_INDEXED, STATE_PARTIAL, STATE_IMAGE, STATE_WITHHELD)
CLASSES: tuple[str, ...] = (*taxonomy.ALGERIA_CLASSES, taxonomy.CLASS_NONE)
COTE_FLAGS: tuple[str, ...] = (taxonomy.COTE_OK, taxonomy.COTE_SUSPECT_BB11, taxonomy.COTE_MISSING)
# The fourth role was added on 2026-11-11 at the END of the table: indexes 0 to 2 are unchanged.
ROLES: tuple[str, ...] = ("principal", persons.ROLE_SPOUSE, persons.ROLE_CHILD, persons.ROLE_SECOND_APPLICANT)
ROLE_COUNT_KEYS: dict[str, str] = {"principal": "principaux", persons.ROLE_SPOUSE: "epouses",
                                   persons.ROLE_CHILD: "enfants", persons.ROLE_SECOND_APPLICANT: "seconds_demandeurs"}
ALGERIA_RULES: tuple[str, ...] = ("", "explicite", "repertoire")

PRECISION_SUSPECT = "suspecte"
PRECISION_CONVENTIONAL = "conventionnelle"
PRECISION_BY_POSITION = "position"
PRECISION_UNPAIRED = "liste-non-appariee"
PRECISIONS: tuple[str, ...] = ("", "jour", "mois", "annee", PRECISION_CONVENTIONAL, PRECISION_BY_POSITION,
                               PRECISION_UNPAIRED, PRECISION_SUSPECT)

DECREE_FIELDS: tuple[str, ...] = (
    "id", "inv", "notice", "date", "drap_date", "titre", "famille", "classe", "cote", "drap_cote", "cote_sug",
    "doc", "etat", "n_pers", "n_exp", "annee", "trim", "contexte")
PERSON_FIELDS: tuple[str, ...] = (
    "id", "role", "princ", "nom", "an", "prec", "naiss", "lieu", "res", "prof", "dec", "dossier", "cote",
    "notice", "img", "ind", "regle", "nea", "rea")
COVERAGE_FIELDS: tuple[str, ...] = (
    "annee", "trim", "etat", "decrets", "decrets_avec_noms", "personnes", "filae", "noms_exportes",
    "alg_decrets", "alg_avec_noms", "a1", "a1_avec_noms", "a2", "a2_avec_noms", "a3", "a3_avec_noms",
    "r", "r_avec_noms", "personnes_exportees")
INVENTORY_FIELDS: tuple[str, ...] = (
    "inv", "annee", "trim", "titre", "cotes", "etat", "decrets", "decrets_avec_noms", "personnes", "filae",
    "noms_exportes")

# ---- privacy: persons who may still be alive
PRIVACY_AGE = 100
REASON_RECENT_BIRTH = "naissance-recente"
REASON_UNKNOWN_BIRTH = "naissance-inconnue"
REASON_IMPOSSIBLE_BIRTH = "naissance-impossible"
REASON_PRINCIPAL_WITHHELD = "notice-du-principal-retenue"
PRIVACY_REASONS: dict[str, str] = {
    REASON_RECENT_BIRTH: ("l'année de naissance écrite dans la notice — pour les enfants cités en deux listes, "
                          "prénoms puis dates, la plus récente de la liste — est égale ou postérieure à l'année seuil"),
    REASON_UNKNOWN_BIRTH: ("l'année de naissance n'est pas connue et le décret est de l'année seuil ou d'une année "
                           "postérieure"),
    REASON_IMPOSSIBLE_BIRTH: ("l'année de naissance écrite est impossible (postérieure au décret, ou antérieure de plus "
                              "de cent ans) et le décret est de l'année seuil ou d'une année postérieure"),
    REASON_PRINCIPAL_WITHHELD: ("la personne principale de la notice est retenue : son épouse et ses enfants, qui "
                                "ne se lisent que sous son nom, le sont avec elle, quel que soit leur âge"),
}
NAME_FLAG_LABELS: dict[str, str] = {
    persons.NAME_EMPTY: "aucun nom à la place attendue (rien, ou un simple signe)",
    persons.NAME_DOSSIER: "un numéro de dossier à la place du nom",
    persons.NAME_DATE: "une date à la place du nom ou du prénom",
    persons.NAME_NUMBER: "un chiffre dans le nom (âge, rang, nombre d'enfants, faute de frappe)",
    persons.NAME_LABEL: "le libellé d'une autre rubrique à la place du nom",
}

FILAE_CLAUSE_SOURCE = ("userestrict des inventaires FRAN_IR_057397 (racine, « Pour les années indexées par "
                       "Filae… ») et FRAN_IR_057213 (1899)")


CLASS_LABELS: dict[str, str] = {
    taxonomy.CLASS_A1: "le titre du décret nomme l'Algérie (hors rejets)",
    taxonomy.CLASS_A2: "admission aux droits de citoyen français, sans territoire dans le titre (à partir de 1931)",
    taxonomy.CLASS_A3: "décret composite incluant l'admission aux droits de citoyen (1941-1948)",
    taxonomy.CLASS_R: ("rejet, révocation ou retrait dont le titre nomme l'Algérie, ou rejet de demandes "
                       "d'admission aux droits de citoyen sans territoire"),
    taxonomy.CLASS_NONE: "autre décret, présent parce qu'une personne exportée en relève",
}


def quarter_label(quarter: int) -> str:
    return "1er trimestre" if quarter == 1 else f"{quarter}e trimestre"


class ExportError(Exception):
    """The site files cannot be produced from this database."""


def generation_year(timestamp: str) -> int:
    """Year of the generation timestamp ('2026-11-11T10:00:00Z' -> 2026): the privacy rule needs it."""
    match = re.match(r"(\d{4})-(\d{2})-(\d{2})(?!\d)", timestamp or "")
    if not match or not (1 <= int(match.group(2)) <= 12 and 1 <= int(match.group(3)) <= 31):
        raise ExportError(f"horodatage illisible : « {timestamp} » (attendu : une date ISO commençant par "
                          "AAAA-MM-JJ, par exemple 2026-11-11T10:00:00Z)")
    return int(match.group(1))


def privacy_reason(birth_year: int | None, suspect: bool, decree_year: int | None, threshold: int) -> str:
    """Why a name occurrence is withheld as "possibly living"; '' when it is not.

    The latest possible birth year of a person is the birth year written in the notice when it is
    plausible; otherwise -- no year, or a year flagged impossible -- it is the year of the decree,
    because nobody is born after the decree that names them. The occurrence is withheld when that
    year is not earlier than ``threshold`` (generation year minus 100): the person may not have
    reached the age of 100.
    """
    if birth_year is not None and not suspect:
        return REASON_RECENT_BIRTH if birth_year >= threshold else ""
    if decree_year is None or decree_year >= threshold:
        return REASON_UNKNOWN_BIRTH if birth_year is None else REASON_IMPOSSIBLE_BIRTH
    return ""


def _relative_reason(relative: tuple, list_year: int | None, decree_year: int | None, threshold: int) -> str:
    """Privacy reason of one relative row (role, name, year, precision, conventional, suspect, …, pairing, flag).

    ``list_year`` is the latest year of the children paired by rank in the same notice, or None when
    one of those years is unusable: it stands for each of them, because that pairing is unverified.
    """
    if relative[9] == persons.PAIRING_BY_POSITION:
        return privacy_reason(list_year, False, decree_year, threshold)
    return privacy_reason(relative[2], bool(relative[5]), decree_year, threshold)


def _role_counts() -> dict[str, int]:
    return {"total": 0, **{key: 0 for key in ROLE_COUNT_KEYS.values()}}


def _count(counts: dict[str, int], role: str) -> None:
    counts["total"] += 1
    counts[ROLE_COUNT_KEYS[role]] += 1


@dataclass(slots=True)
class ExportStats:
    decrees: int = 0
    persons: int = 0
    spouses: int = 0
    children: int = 0
    second_applicants: int = 0
    generation_year: int = 0
    privacy_threshold: int = 0
    privacy_active: bool = True
    privacy: dict[str, int] = field(default_factory=_role_counts)                 # designated by the rule
    privacy_by_reason: dict[str, dict[str, int]] = field(default_factory=dict)    # reason -> counts by role
    debris: dict[str, int] = field(default_factory=_role_counts)                  # relatives' names not exported
    debris_by_flag: dict[str, int] = field(default_factory=dict)
    tier_by_relative: int = 0         # notices of the corpus in the tier only through a spouse or a child
    decrees_by_class: dict[str, int] = field(default_factory=dict)
    decrees_by_state: dict[str, int] = field(default_factory=dict)
    filae_included: bool = False
    filae_notices: int = 0            # person notices of the covered years, whole corpus
    filae_tier_persons: int = 0       # of which in the Algeria tier
    filae_tier_relatives: int = 0     # spouses and children of those
    link_exceptions: int = 0
    sizes: dict[str, tuple[int, int]] = field(default_factory=dict)   # file -> (raw bytes, gzip bytes)


def _none(value: Any) -> Any:
    """Empty strings are published as null."""
    return None if value == "" else value


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def write_columnar(path: Path, head: dict[str, Any], rows: list[list[Any]]) -> None:
    """Write ``{…head…, "lignes": [[…], …]}`` with one row per line, atomically."""
    partial = path.with_name(path.name + ".part")
    with partial.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write("{")
        for key, value in head.items():
            handle.write(f"{_json(key)}:{_json(value)},\n")
        handle.write('"lignes":[\n')
        handle.write(",\n".join(_json(row) for row in rows))
        handle.write("\n]}\n")
    partial.replace(path)


def _precision(precision: str, conventional: int, suspect: int, pairing: str) -> int:
    if suspect:
        code = PRECISION_SUSPECT
    elif pairing == persons.PAIRING_IMPOSSIBLE:
        code = PRECISION_UNPAIRED
    elif pairing == persons.PAIRING_BY_POSITION:
        code = PRECISION_BY_POSITION
    elif conventional:
        code = PRECISION_CONVENTIONAL
    else:
        code = precision or ""
    return PRECISIONS.index(code)


def _state_of_period(decrees: int, with_names: int) -> str:
    return inventory_state(decrees, with_names)


def _coverage(connection: sqlite3.Connection, withheld: set[str], exported_by_inventory: dict[str, int],
              by_quarter: bool) -> list[list[Any]]:
    """Coverage records, one per year, or one per quarter for the quarterly inventories."""
    groups: dict[tuple[int, int | None], dict[str, Any]] = {}
    inventories = connection.execute(
        "SELECT inv, annee, trimestre, n_decrets, n_decrets_avec_noms, n_personnes, annee_filae FROM inventaire "
        "ORDER BY rang").fetchall()
    for inv, year, quarter, decrees, with_names, person_count, filae in inventories:
        if by_quarter and quarter is None:
            continue
        key = (year, quarter if by_quarter else None)
        group = groups.setdefault(key, {"decrets": 0, "avec": 0, "personnes": 0, "filae": False, "retenu": False,
                                        "exportees": 0, "classes": {c: [0, 0] for c in taxonomy.ALGERIA_CLASSES}})
        group["decrets"] += decrees
        group["avec"] += with_names
        group["personnes"] += person_count
        group["filae"] = group["filae"] or bool(filae)
        group["retenu"] = group["retenu"] or inv in withheld
        group["exportees"] += exported_by_inventory.get(inv, 0)
        for algeria_class, total, named in connection.execute(
                "SELECT classe_algerie, COUNT(*), SUM(n_personnes > 0) FROM decret WHERE inv = ? "
                "AND classe_algerie != ? GROUP BY classe_algerie", (inv, taxonomy.CLASS_NONE)):
            group["classes"][algeria_class][0] += total
            group["classes"][algeria_class][1] += named
    rows: list[list[Any]] = []
    for (year, quarter), group in sorted(groups.items(), key=lambda item: (item[0][0], item[0][1] or 0)):
        classes = group["classes"]
        row: list[Any] = [year, quarter, _state_of_period(group["decrets"], group["avec"]), group["decrets"],
                          group["avec"], group["personnes"], group["filae"],
                          bool(group["personnes"]) and not group["retenu"],
                          sum(v[0] for v in classes.values()), sum(v[1] for v in classes.values())]
        for algeria_class in taxonomy.ALGERIA_CLASSES:
            row.extend(classes[algeria_class])
        row.append(group["exportees"])
        rows.append(row)
    return rows


def _privacy_rule_text(year: int, threshold: int) -> str:
    return (
        f"Une occurrence de nom n'est pas publiée quand la personne pourrait être encore en vie, c'est-à-dire "
        f"avoir moins de {PRIVACY_AGE} ans révolus l'année de la génération ({year}). Année retenue pour chaque "
        "personne : l'année de naissance écrite dans la notice ; si elle manque ou si elle est impossible "
        "(postérieure au décret, ou antérieure de plus de cent ans), l'année du décret, puisque nul ne naît après "
        "le décret qui le nomme ; pour les enfants cités en deux listes, prénoms puis dates, dont l'association "
        "n'est pas vérifiée, l'année la plus récente de la liste. L'occurrence est retenue quand cette année est "
        f"{threshold} ou une année postérieure ({year} − {PRIVACY_AGE}). Quand la personne principale d'une notice "
        "est retenue, toute la notice l'est, épouse et enfants compris. Le décret reste listé.")


def _not_covered(year_rows: list[list[Any]], quarter_rows: list[list[Any]], include_filae: bool,
                 stats: ExportStats | None = None) -> list[dict[str, str]]:
    """What a search in these files does NOT cover, in plain French, for the "bilan de recherche"."""
    items: list[dict[str, str]] = []
    quarterly_years = {row[0] for row in quarter_rows}
    detailed = [row for row in year_rows if row[0] not in quarterly_years] + quarter_rows
    for row in sorted(detailed, key=lambda r: (r[0], r[1] or 0)):
        year, quarter, state, decrees, with_names, _persons, filae, names_exported, alg_decrees, alg_named = row[:10]
        period = f"{year}" + (f", {quarter_label(quarter)}" if quarter else "")
        if state == STATE_IMAGE:
            items.append({"code": "image-seule", "periode": period, "texte": (
                f"{period} : aucun nom saisi dans l'inventaire ({decrees} décrets, dont {alg_decrees} "
                "pouvant concerner l'Algérie, classes A1, A2, A3 et R) ; seule la recherche guidée, décret par "
                "décret sur les images, est possible.")})
        elif state == STATE_PARTIAL:
            items.append({"code": "partiel", "periode": period, "texte": (
                f"{period} : l'inventaire ne porte des noms que pour {with_names} décrets sur {decrees} "
                f"({alg_named} sur {alg_decrees} parmi ceux qui peuvent concerner l'Algérie) ; pour les autres "
                "décrets, seule la recherche guidée sur les images est possible, et une absence de "
                "correspondance ne prouve rien.")})
        if filae and not names_exported and state != STATE_IMAGE:
            items.append({"code": "retenu-filae", "periode": period, "texte": (
                f"{period} : des noms existent dans l'inventaire des Archives nationales mais ne sont pas "
                "publiés ici (clause Filae) ; chercher le nom directement sur le site des Archives nationales.")})
    items.extend([
        {"code": "avant-1883", "periode": "1865-1882", "texte": (
            "Avant 1883 : ces inventaires ne couvrent pas les décrets antérieurs à 1883.")},
        {"code": "apres-1948", "periode": "1949-1962", "texte": (
            "Après 1948 : ces inventaires s'arrêtent à 1948.")},
        {"code": "jugements-1919", "periode": "1919-1962", "texte": (
            "Les admissions prononcées par jugement (loi du 4 février 1919) ne sont dans aucun de ces décrets ; "
            "elles ne se signalent que par une mention en marge de l'acte de naissance ou de mariage.")},
        {"code": "pas-une-citation", "periode": "", "texte": (
            "Une notice trouvée ici identifie un décret et un dossier ; ce n'est pas encore une citation : "
            "il manque la date et la page de la publication officielle.")},
        {"code": "homonymes-et-graphies", "periode": "", "texte": (
            "Les noms sont ceux saisis par les indexeurs, avec leurs graphies et leurs erreurs ; une personne "
            "peut figurer sous plusieurs décrets (rejet puis admission) ou sous une graphie inattendue.")},
        {"code": "enfants", "periode": "", "texte": (
            "Pour les enfants cités sous la forme « A ; B né(e)(s) le d1 ; d2 », l'association d'un prénom et "
            "d'une date par leur rang n'est pas vérifiée.")},
    ])
    if not include_filae:
        items.append({"code": "clause-filae", "periode": "1898-1912, 1928", "texte": (
            "Les noms des années 1898 à 1912 et 1928 sont retenus par précaution : une clause de l'inventaire "
            "soumet leur publication en ligne à l'autorisation préalable de la société Filae, et les Archives "
            "nationales n'ont pas encore précisé sa portée ; les décrets de ces années restent listés.")})
    if stats is not None and stats.privacy_active:
        threshold = stats.privacy_threshold
        items.append({"code": "vie-privee", "periode": "", "texte": (
            f"Les noms des personnes qui pourraient être encore en vie ne sont pas publiés : celles nées en "
            f"{threshold} ou après, et celles dont l'année de naissance est inconnue ou impossible sous un décret "
            f"de {threshold} ou d'une année postérieure ({stats.privacy['total']} occurrences de noms retenues). "
            "Leurs décrets restent listés : la recherche guidée sur les images reste possible.")})
    if stats is not None and stats.debris["total"]:
        items.append({"code": "noms-inexploitables", "periode": "", "texte": (
            f"{stats.debris['total']} mentions d'épouses ou d'enfants ne sont pas cherchables : l'inventaire porte, "
            "à la place du nom, une date, un numéro de dossier, un chiffre ou rien. La notice de la personne "
            "principale reste cherchable ; l'image du décret donne le nom.")})
    return items


def export_site(database: Path, site_dir: Path, *, include_filae: bool, timestamp: str,
                include_possibly_living: bool = False) -> ExportStats:
    """Write the three site files from the database."""
    year_of_generation = generation_year(timestamp)
    threshold = year_of_generation - PRIVACY_AGE
    if not database.exists():
        raise ExportError(f"base absente : {database} (lancer d'abord « construire »)")
    site_dir.mkdir(parents=True, exist_ok=True)
    stats = ExportStats(filae_included=include_filae, generation_year=year_of_generation,
                        privacy_threshold=threshold, privacy_active=not include_possibly_living,
                        privacy_by_reason={reason: _role_counts() for reason in PRIVACY_REASONS},
                        debris_by_flag={flag: 0 for flag in persons.NAME_FLAGS})
    connection = read_only(database)
    try:
        found_format = database_format(connection)
        if found_format != DATABASE_FORMAT:
            raise ExportError(f"base d'un autre format ({found_format or 'illisible'}, attendu {DATABASE_FORMAT}) : "
                              f"{database} — relancer « construire » sans --export-seul")
        inventories = connection.execute(
            "SELECT inv, annee, trimestre, titre, cotes, etat, n_decrets, n_decrets_avec_noms, n_personnes, "
            "annee_filae, lien, lieu_conservation, telecharge_le, octets FROM inventaire ORDER BY rang").fetchall()
        if not inventories:
            raise ExportError(f"base vide : {database}")
        inventory_index = {row[0]: index for index, row in enumerate(inventories)}
        filae_inventories = {row[0] for row in inventories if row[9]}
        withheld = set() if include_filae else filae_inventories

        # Individuals concerned by the clause, whatever the option.
        marks = ",".join("?" * len(filae_inventories)) or "''"
        filae_args = sorted(filae_inventories)
        stats.filae_notices = connection.execute(
            f"SELECT COUNT(*) FROM personne WHERE inv IN ({marks})", filae_args).fetchone()[0]
        stats.filae_tier_persons = connection.execute(
            f"SELECT COUNT(*) FROM personne WHERE palier_algerie = 1 AND inv IN ({marks})", filae_args).fetchone()[0]
        stats.filae_tier_relatives = connection.execute(
            f"SELECT COUNT(*) FROM apparente a JOIN personne p USING(personne_id) "
            f"WHERE p.palier_algerie = 1 AND p.inv IN ({marks})", filae_args).fetchone()[0]

        # ---- persons of the tier, with the year of their decree (the privacy rule needs it)
        tier_rows = [row for row in connection.execute(
            "SELECT p.personne_id, p.decret_id, p.inv, p.notice_id, p.nom_brut, p.naissance_annee, "
            "p.naissance_precision, p.naissance_conventionnelle, p.naissance_suspecte, p.naissance_brut, "
            "p.naissance_lieu, p.residence, p.profession, p.dossier, p.dossier_brut, p.cote_dossier, p.lien_notice, "
            "p.lien_images, p.indice, p.regle, p.ne_en_algerie, p.reside_en_algerie, d.annee "
            "FROM personne p JOIN decret d USING(decret_id) WHERE p.palier_algerie = 1 ORDER BY p.personne_id")
            if row[2] not in withheld]
        relatives: dict[int, list[tuple]] = {}
        for row in connection.execute(
                "SELECT a.personne_id, a.role, a.nom_brut, a.naissance_annee, a.naissance_precision, "
                "a.naissance_conventionnelle, a.naissance_suspecte, a.naissance_brut, a.naissance_lieu, a.residence, "
                "a.appariement, a.nom_drapeau "
                "FROM apparente a JOIN personne p USING(personne_id) WHERE p.palier_algerie = 1 "
                "ORDER BY a.personne_id, a.rang"):
            relatives.setdefault(row[0], []).append(row[1:])

        # ---- what is kept: privacy first (a withheld principal takes the whole notice), then debris
        def designate(reason: str, role: str) -> None:
            _count(stats.privacy, role)
            _count(stats.privacy_by_reason[reason], role)

        person_rows_db: list[tuple] = []
        kept_relatives: dict[int, list[tuple]] = {}
        privacy_per_person: dict[int, int] = {}       # personne_id -> relatives withheld as possibly living
        debris_per_person: dict[int, int] = {}        # personne_id -> relatives whose name is debris
        for row in tier_rows:
            person_id, birth_year, suspect, decree_year = row[0], row[5], bool(row[8]), row[22]
            family = relatives.get(person_id, [])
            # children of the form 'A ; B né(e)(s) le d1 ; d2': the pairing by rank is unverified, so the
            # latest year of the list stands for each of them (None when one of those years is unusable)
            listed = [(r[2], bool(r[5])) for r in family if r[9] == persons.PAIRING_BY_POSITION]
            usable = [year for year, flagged in listed if year is not None and not flagged]
            list_year = max(usable) if listed and len(usable) == len(listed) else None
            principal_reason = privacy_reason(birth_year, suspect, decree_year, threshold)
            if principal_reason:
                designate(principal_reason, "principal")
            if principal_reason and stats.privacy_active:
                for relative in family:
                    if not relative[10]:
                        designate(_relative_reason(relative, list_year, decree_year, threshold)
                                  or REASON_PRINCIPAL_WITHHELD, relative[0])
                continue
            person_rows_db.append(row)
            kept = kept_relatives.setdefault(person_id, [])
            for relative in family:
                if relative[10]:
                    _count(stats.debris, relative[0])
                    stats.debris_by_flag[relative[10]] += 1
                    debris_per_person[person_id] = debris_per_person.get(person_id, 0) + 1
                    continue
                reason = (_relative_reason(relative, list_year, decree_year, threshold)
                          or (REASON_PRINCIPAL_WITHHELD if principal_reason else ""))
                if reason:
                    designate(reason, relative[0])
                    if stats.privacy_active:
                        privacy_per_person[person_id] = privacy_per_person.get(person_id, 0) + 1
                        continue
                kept.append(relative)
        exported_per_decree: dict[int, int] = {}
        exported_per_inventory: dict[str, int] = {}
        for row in person_rows_db:
            exported_per_decree[row[1]] = exported_per_decree.get(row[1], 0) + 1
            exported_per_inventory[row[2]] = exported_per_inventory.get(row[2], 0) + 1

        # ---- decrees
        notice_template = links.TEMPLATES[links.LINK_NOTICE]
        image_template = links.TEMPLATES[links.LINK_IMAGES]
        decree_exceptions: dict[str, dict[str, str | None]] = {"notice": {}, "images": {}}
        decree_position: dict[int, int] = {}
        decree_rows: list[list[Any]] = []
        date_flags: list[str] = [""]
        for (decree_id, inv, notice_id, date, date_flag, title, family, algeria_class, cote, cote_flag,
             cote_suggestion, document, person_count, state, year, quarter, context, notice_link,
             image_link) in connection.execute(
                "SELECT decret_id, inv, notice_id, date, date_drapeau, titre, famille, classe_algerie, cote, "
                "cote_drapeau, cote_suggeree, document, n_personnes, etat, annee, trimestre, contexte, lien_notice, "
                "lien_images FROM decret ORDER BY decret_id"):
            if algeria_class == taxonomy.CLASS_NONE and decree_id not in exported_per_decree:
                continue
            position = len(decree_rows)
            decree_position[decree_id] = position
            if date_flag not in date_flags:
                date_flags.append(date_flag)
            if person_count and inv in withheld:
                state = STATE_WITHHELD
            if notice_link != notice_template.build_xml_form(inv, notice_id):
                decree_exceptions["notice"][str(position)] = notice_link or None
            if image_link != image_template.build_xml_form(inv, notice_id):
                decree_exceptions["images"][str(position)] = image_link or None
            decree_rows.append([
                position, inventory_index[inv], notice_id, date, date_flags.index(date_flag), title,
                taxonomy.FAMILIES.index(family), CLASSES.index(algeria_class), _none(cote),
                COTE_FLAGS.index(cote_flag), _none(cote_suggestion), _none(document), STATES.index(state),
                person_count, exported_per_decree.get(decree_id, 0), year, quarter, _none(context)])
            stats.decrees_by_class[algeria_class] = stats.decrees_by_class.get(algeria_class, 0) + 1
            stats.decrees_by_state[state] = stats.decrees_by_state.get(state, 0) + 1
        # The table of date flags is sorted for stability: remap the indexes.
        sorted_flags = sorted(date_flags)
        remap = {date_flags.index(flag): sorted_flags.index(flag) for flag in date_flags}
        for row in decree_rows:
            row[4] = remap[row[4]]

        # ---- persons, each followed by its spouse, children and second applicant
        rules: list[str] = sorted({row[19] for row in person_rows_db})
        hint_codes = list(hints.HINT_LABELS)
        person_exceptions: dict[str, dict[str, str | None]] = {"notice": {}, "images": {}}
        person_rows: list[list[Any]] = []
        privacy_per_row: dict[str, int] = {}      # row id of the principal -> relatives withheld
        debris_per_row: dict[str, int] = {}
        for (person_id, decree_id, inv, notice_id, name, birth_year, precision, conventional, suspect, birth_raw,
             birth_place, residence, profession, dossier, dossier_raw, dossier_cote, notice_link, image_link,
             hint, rule, born, lives, _decree_year) in person_rows_db:
            position = len(person_rows)
            if person_id in privacy_per_person:
                privacy_per_row[str(position)] = privacy_per_person[person_id]
            if person_id in debris_per_person:
                debris_per_row[str(position)] = debris_per_person[person_id]
            decree_at = decree_position[decree_id]
            if notice_link != notice_template.build_xml_form(inv, notice_id):
                person_exceptions["notice"][str(position)] = notice_link or None
            if image_link and image_link != image_template.build_xml_form(inv, notice_id):
                person_exceptions["images"][str(position)] = image_link
            person_rows.append([
                position, 0, position, _none(name), birth_year, _precision(precision or "", conventional, suspect, ""),
                _none(birth_raw), _none(birth_place), _none(residence), _none(profession), decree_at,
                _none(dossier or dossier_raw), _none((dossier_cote or "").strip()), notice_id, int(bool(image_link)),
                hint_codes.index(hint), rules.index(rule), ALGERIA_RULES.index(born), ALGERIA_RULES.index(lives)])
            stats.persons += 1
            for (role, relative_name, relative_year, relative_precision, relative_conventional, relative_suspect,
                 relative_birth_raw, relative_place, relative_residence, pairing,
                 _name_flag) in kept_relatives.get(person_id, []):
                person_rows.append([
                    len(person_rows), ROLES.index(role), position, _none(relative_name), relative_year,
                    _precision(relative_precision or "", relative_conventional, relative_suspect, pairing),
                    _none(relative_birth_raw), _none(relative_place), _none(relative_residence), None, decree_at,
                    None, None, None, 0, None, None, None, None])
                if role == persons.ROLE_SPOUSE:
                    stats.spouses += 1
                elif role == persons.ROLE_SECOND_APPLICANT:
                    stats.second_applicants += 1
                else:
                    stats.children += 1
        stats.decrees = len(decree_rows)
        stats.link_exceptions = sum(len(v) for v in decree_exceptions.values()) + sum(
            len(v) for v in person_exceptions.values())

        decrees_path = site_dir / FILE_DECREES
        persons_path = site_dir / FILE_PERSONS
        write_columnar(decrees_path, {
            "format": "decretas-an-decrets/1",
            "champs": list(DECREE_FIELDS),
            "tables": {"inv": [row[0] for row in inventories], "drap_date": sorted_flags,
                       "famille": list(taxonomy.FAMILIES), "classe": list(CLASSES), "drap_cote": list(COTE_FLAGS),
                       "etat": list(STATES)},
            "liens_particuliers": decree_exceptions,
        }, decree_rows)
        write_columnar(persons_path, {
            "format": "decretas-an-personnes/1",
            "champs": list(PERSON_FIELDS),
            "tables": {"role": list(ROLES), "prec": list(PRECISIONS), "ind": hint_codes, "regle": rules,
                       "nea": list(ALGERIA_RULES), "rea": list(ALGERIA_RULES)},
            "liens_particuliers": person_exceptions,
        }, person_rows)

        year_rows = _coverage(connection, withheld, exported_per_inventory, by_quarter=False)
        quarter_rows = _coverage(connection, withheld, exported_per_inventory, by_quarter=True)
        inventory_link = links.TEMPLATES[links.LINK_INVENTORY]
        inventory_exceptions = {row[0]: row[10] or None for row in inventories
                                if row[10] != inventory_link.build_xml_form(row[0])}
        downloads = sorted(row[12][:10] for row in inventories if row[12])
        place_counts: dict[str, int] = {}
        for row in inventories:
            if row[11]:
                place_counts[row[11]] = place_counts.get(row[11], 0) + 1
        places = sorted(place_counts, key=lambda place: (-place_counts[place], place))
        corpus = connection.execute(
            "SELECT (SELECT COUNT(*) FROM decret), (SELECT COUNT(*) FROM personne), "
            "(SELECT COUNT(*) FROM apparente WHERE role = 'epouse'), (SELECT COUNT(*) FROM apparente WHERE role = 'enfant'), "
            "(SELECT COUNT(*) FROM personne WHERE palier_algerie = 1), (SELECT COUNT(*) FROM personne WHERE nom_non_saisi = 1), "
            "(SELECT COUNT(*) FROM notice_ecartee), (SELECT COUNT(*) FROM personne WHERE naissance_annee IS NOT NULL), "
            "(SELECT COUNT(*) FROM apparente WHERE role = 'demandeur'), "
            "(SELECT COUNT(*) FROM personne WHERE palier_par_apparente = 1), "
            "(SELECT COUNT(*) FROM apparente WHERE nom_drapeau != '')"
        ).fetchone()
        stats.tier_by_relative = corpus[9]
        hint_counts = dict(connection.execute(
            "SELECT indice, COUNT(*) FROM personne WHERE palier_algerie = 1 GROUP BY indice ORDER BY indice"))
        root = dict(connection.execute("SELECT cle, valeur FROM meta")).get("inventaires_racine", "")
    finally:
        connection.close()

    files = {}
    for path in (decrees_path, persons_path):
        data = path.read_bytes()
        files[path.name] = {"octets": len(data), "sha256": hashlib.sha256(data).hexdigest()}
        stats.sizes[path.name] = (len(data), len(gzip.compress(data, compresslevel=9, mtime=0)))
    meta = {
        "format": "decretas-an-meta/1",
        "genere_le": timestamp,
        "source": {
            "producteur": "Archives nationales de France",
            "fonds": "Décrets de naturalisation, sous-série BB/34 (1883-1948), inventaires XML-EAD de la salle de lecture virtuelle",
            "inventaires": len(inventories),
            "inventaire_racine": root.split(",") if root else [],
            "telecharges_du": downloads[0] if downloads else None,
            "telecharges_au": downloads[-1] if downloads else None,
            "octets": sum(row[13] or 0 for row in inventories),
        },
        "fichiers": files,
        "comptes": {
            "corpus": {"decrets": corpus[0], "notices_de_personnes": corpus[1], "epouses": corpus[2],
                       "enfants": corpus[3], "personnes_du_palier_algerie": corpus[4],
                       "noms_non_saisis": corpus[5], "notices_ecartees": corpus[6],
                       "personnes_avec_annee_de_naissance": corpus[7], "seconds_demandeurs": corpus[8],
                       "personnes_du_palier_par_un_apparente": corpus[9],
                       "apparentes_au_nom_inexploitable": corpus[10]},
            "exporte": {"decrets": stats.decrees, "decrets_par_classe": dict(sorted(stats.decrees_by_class.items())),
                        "decrets_par_etat": dict(sorted(stats.decrees_by_state.items())),
                        "occurrences_de_noms": len(person_rows), "principaux": stats.persons,
                        "epouses": stats.spouses, "enfants": stats.children,
                        "seconds_demandeurs": stats.second_applicants},
            "indices_du_palier": hint_counts,
        },
        "filae": {
            "annees": sorted(FILAE_YEARS),
            "noms_inclus": include_filae,
            "clause": ("Pour les années indexées par Filae, toute publication sur internet à des fins de recherche "
                       "nominative, patronymique, ou généalogique, d'un corpus concernant plus de 1000 individus "
                       "devra faire l'objet d'une autorisation préalable de la société Filae."),
            "source_de_la_clause": FILAE_CLAUSE_SOURCE,
            "portee": ("Portée non établie : par précaution, 1898, 1899-1912 et 1928 sont traitées comme couvertes "
                       "tant que les Archives nationales n'ont pas répondu."),
            "individus_concernes": {
                "notices_de_personnes_du_corpus": stats.filae_notices,
                "principaux_du_palier_algerie": stats.filae_tier_persons,
                "epouses_et_enfants_du_palier_algerie": stats.filae_tier_relatives,
            },
        },
        "vie_privee": {
            "active": stats.privacy_active,
            "annee_de_generation": year_of_generation,
            "age": PRIVACY_AGE,
            "annee_seuil": threshold,
            "regle": _privacy_rule_text(year_of_generation, threshold),
            "motifs": PRIVACY_REASONS,
            # designated by the rule in the notices this export could publish (Filae years excluded when
            # they are withheld); "retenus" is what is actually absent from an-personnes.json
            "concernes": stats.privacy,
            "concernes_par_motif": stats.privacy_by_reason,
            "retenus": stats.privacy if stats.privacy_active else _role_counts(),
            "apparentes_retenus_par_principal": privacy_per_row,
        },
        "noms_inexploitables": {
            "regle": ("Une épouse, un enfant ou un second demandeur n'est pas exporté comme nom cherchable quand "
                      "l'inventaire porte, à la place de son nom : rien ou un simple signe ; un numéro de dossier ; "
                      "une date ; un chiffre quelconque (un nom ne contient jamais de chiffre) ; le libellé d'une "
                      "autre rubrique. Le texte de l'inventaire est conservé tel quel dans la base de travail ; "
                      "rien n'est deviné : une remarque écrite sans chiffre à la place d'un prénom n'est pas "
                      "détectée."),
            "motifs": NAME_FLAG_LABELS,
            "non_exportes": stats.debris,
            "non_exportes_par_motif": stats.debris_by_flag,
            "par_principal": debris_per_row,
        },
        "seuil_indexe": INDEXED_SHARE,
        "couverture_annees": {"champs": list(COVERAGE_FIELDS), "lignes": year_rows},
        "couverture_trimestres": {"champs": list(COVERAGE_FIELDS), "lignes": quarter_rows},
        "inventaires": {"champs": list(INVENTORY_FIELDS), "lignes": [
            [row[0], row[1], row[2], row[3], row[4], row[5], row[6], row[7], row[8], bool(row[9]),
             bool(row[8]) and row[0] not in withheld] for row in inventories]},
        "non_couvert": _not_covered(year_rows, quarter_rows, include_filae, stats),
        "table_des_liens": links.CONTENT_TABLE_NAME,
        "liens": links.template_table(),
        "liens_particuliers_inventaires": inventory_exceptions,
        "credit": {
            "gabarit": links.CREDIT_TEMPLATE,
            "lieu_de_conservation": places[0] if places else None,
            "lieux_ecrits_dans_les_inventaires": places,
            "date_des_informations": downloads[-1] if downloads else None,
            "licence": links.LICENCE_NOTE,
        },
        "indices": hints.HINT_LABELS,
        "classes": CLASS_LABELS,
        "avertissements": [
            "Les indices (né en Algérie, musulman algérien probable…) sont des classements heuristiques : ils "
            "ordonnent et expliquent, ils ne prouvent rien et n'excluent personne.",
            "« 1 janvier » et « présumé » signalent une date de naissance conventionnelle : comparer l'année, jamais le jour.",
            "Une cote de décret en BB/11 est une erreur de saisie probable de l'inventaire : la cote suggérée en BB/34 "
            "est donnée à côté, la valeur d'origine n'est jamais remplacée.",
        ],
    }
    meta_path = site_dir / FILE_META
    partial = meta_path.with_name(meta_path.name + ".part")
    partial.write_text(json.dumps(meta, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    partial.replace(meta_path)
    data = meta_path.read_bytes()
    stats.sizes[meta_path.name] = (len(data), len(gzip.compress(data, compresslevel=9, mtime=0)))
    return stats
