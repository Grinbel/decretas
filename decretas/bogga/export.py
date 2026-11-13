"""Build the site data files from the harvested volumes.

    site/data/bogga-volumes.json   one row per yearly volume
    site/data/bogga-decrets.json   one row per decree as published
    site/data/bogga-entrees.json   one row per person entry (and per unsegmented block)
    site/data/bogga-meta.json      generation info, coverage by year, pages to read by hand

Every tabular file has the shape {"champs": [...], "lignes": [[...], ...]}; the field
lists are documented in docs/format-donnees-bogga.md, which must be kept in step with
the `*_FIELDS` constants below.
"""
from __future__ import annotations

import datetime
import gzip
import json
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path

from decretas.bogga import catalogue, controle, dates, livraisons, moisson, personnes, segmentation, volume

VOLUME_FIELDS = ["annee", "item", "doc", "famille", "lien_volume", "lien_page", "image_page", "lien_verifie",
                 "bibliotheque", "droits", "pagination", "livraisons", "controle"]
DECREE_FIELDS = ["id", "volume", "nature", "dates", "date_etat", "date_brute", "entete", "article",
                 "livraison", "livraison_etat", "livraison_date", "livraison_date_etat",
                 "page", "feuille", "derniere_feuille", "entrees", "total_imprime", "doublon_de", "drapeaux"]
ENTRY_FIELDS = ["id", "volume", "decret", "nom", "texte", "marqueurs", "nationalite", "naissance",
                "residence", "page", "feuille", "drapeaux"]

D_PAGE_CALCULEE = 1         # decree flag: first page inferred from neighbouring leaves
D_INDIGENE_ENTETE = 2       # decree flag: the heading itself names « l'indigène / les indigènes »
D_SANS_ENTREE = 4           # decree flag: recognised, but no entry could be cut out of its list
D_ENTETE_MENTIONNE_INDIGENES = 8   # decree flag: the heading mentions « indigènes » among others, without saying who

CREDIT = "Texte et images : Internet Archive (archive.org)"
FORMAT_VERSION = 1
LINK_CHECKS_FILE = "liens-verifies.json"


@dataclass
class Built:
    volumes: list[list] = field(default_factory=list)
    decrees: list[list] = field(default_factory=list)
    entries: list[list] = field(default_factory=list)
    manual_pages: list[dict] = field(default_factory=list)
    coverage: dict[int, dict] = field(default_factory=dict)


def columnar(fields: list[str], rows: list[list]) -> dict:
    for row in rows:
        if len(row) != len(fields):
            raise ValueError(f"ligne de {len(row)} valeurs pour {len(fields)} champs")
    return {"champs": fields, "lignes": rows}


def write_json(path: Path, data: dict) -> tuple[int, int]:
    """Write compact JSON; return (bytes written, bytes once gzip-compressed)."""
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return len(payload), len(gzip.compress(payload, compresslevel=9, mtime=0))


def issue_summary(issues: list[livraisons.Issue]) -> dict:
    numbers = [issue.number for issue in issues if issue.number is not None]
    return {
        "nombre": len(issues),
        "premier_numero": min(numbers) if numbers else None,
        "dernier_numero": max(numbers) if numbers else None,
        "numeros_lus": sum(1 for issue in issues if issue.number_state == livraisons.NUMBER_READ),
        "numeros_calcules": sum(1 for issue in issues if issue.number_state == livraisons.NUMBER_COMPUTED),
        "numeros_incertains": sum(1 for issue in issues if issue.number_state == livraisons.NUMBER_UNCERTAIN),
        "dates_lues": sum(1 for issue in issues if issue.date_state == dates.READ),
        "dates_corrigees": sum(1 for issue in issues if issue.date_state == dates.REPAIRED),
        "dates_suspectes": sum(1 for issue in issues if issue.date_state == dates.SUSPECT),
        "clotures_non_lues": sum(1 for issue in issues if not issue.date_raw),
    }


def volume_row(vol: catalogue.Volume, doc: str, pages: list[volume.Page], issues: list[livraisons.Issue],
               record: dict, link_check: str) -> list:
    return [
        vol.year, vol.item, doc, vol.family,
        catalogue.ITEM_URL.format(item=vol.item),
        catalogue.page_link_template(vol, doc),
        catalogue.image_link_template(vol, doc),
        link_check,
        vol.library, vol.rights,
        volume.page_mapping_summary(pages),
        issue_summary(issues),
        record,
    ]


def decree_row(decree_id: int, volume_index: int, decree: segmentation.Decree, first_id: int) -> list:
    issue = decree.issue
    flags = 0
    if decree.page_computed:
        flags |= D_PAGE_CALCULEE
    if decree.heading_indigene:
        flags |= D_INDIGENE_ENTETE
    if not decree.entries:
        flags |= D_SANS_ENTREE
    if personnes.read_markers(decree.heading)[0] & personnes.M_INDIGENE:
        flags |= D_ENTETE_MENTIONNE_INDIGENES
    return [
        decree_id, volume_index, decree.nature,
        [iso for iso, _state in decree.dates], decree.date_state, decree.date_raw,
        decree.heading[:400], decree.article,
        issue.number if issue else None,
        issue.number_state if issue else livraisons.NUMBER_UNCERTAIN,
        issue.date.isoformat() if issue and issue.date else None,
        issue.date_state if issue else dates.SUSPECT,
        decree.page, decree.leaf, max(decree.leaf, decree.last_leaf),
        len(decree.entries), controle.expected_size(decree),
        first_id + decree.duplicate_of if decree.duplicate_of is not None else None,
        flags,
    ]


def entry_row(entry_id: int, volume_index: int, decree_id: int, entry: segmentation.Entry) -> list:
    return [entry_id, volume_index, decree_id, entry.name, entry.raw, entry.markers, entry.nationality,
            entry.birth_year, entry.residence, entry.page, entry.leaf, entry.flags]


def unsegmented_row(entry_id: int, volume_index: int, decree_id: int, block: segmentation.Unsegmented,
                    computed: bool) -> list:
    markers, nationality = personnes.read_markers(block.text)
    flags = personnes.F_NON_SEGMENTE | (personnes.F_PAGE_CALCULEE if computed else 0)
    return [entry_id, volume_index, decree_id, "", block.text, markers, nationality, None, None,
            block.page, block.leaf, flags]


def leaf_of_page(pages: list[volume.Page], printed: int) -> int | None:
    """The leaf that carries a printed page number, when exactly one does."""
    leaves = [page.leaf for page in pages if page.printed == printed]
    return leaves[0] if len(leaves) == 1 else None


def manual_pages_of(vol: catalogue.Volume, doc: str, volume_index: int, pages: list[volume.Page],
                    seg: segmentation.Segmentation, record: dict, first_decree_id: int) -> list[dict]:
    """Pages a person must read on the image: unsegmented lists, decrees without entries,
    pages listed by the volume's own table where no decree was found."""
    out: list[dict] = []
    seen: set[int] = set()

    def add(leaf: int | None, printed: int | None, reason: str, decree_index: int | None) -> None:
        if leaf is not None and leaf in seen:
            return
        if leaf is not None:
            seen.add(leaf)
        out.append({
            "volume": volume_index, "annee": vol.year, "feuille": leaf, "page": printed,
            "lien": catalogue.page_link(vol, doc, leaf) if leaf is not None else catalogue.ITEM_URL.format(item=vol.item),
            "raison": reason,
            "decret": first_decree_id + decree_index if decree_index is not None else None,
        })

    for page in seg.manual_pages:
        add(page.leaf, page.page, page.reason, page.decree_index)
    for index, decree in enumerate(seg.decrees):
        if not decree.entries:
            add(decree.leaf, decree.page, "décret reconnu à sa formule, liste des personnes non découpée", index)
    for printed in record["table_alphabetique"]["pages_non_retrouvees"]:
        add(leaf_of_page(pages, printed), printed,
            "page indiquée par la table alphabétique du volume, aucun décret d'admission reconnu "
            "(texte illisible pour la machine, ou numéro de page mal lu dans la table)", None)
    for leaf in seg.formula_hits_outside:
        add(leaf, pages[leaf].printed, "phrase de décret d'admission lue hors de tout décret découpé", None)
    return out


def build_volume(built: Built, vol: catalogue.Volume, files: moisson.VolumeFiles, link_checks: dict[str, str]) -> dict:
    """Segment one volume and append its rows. Returns the per-year summary."""
    assert files.searchtext and files.pageindex and files.page_numbers
    pages = volume.load_volume(files.searchtext, files.pageindex, files.page_numbers)
    seg = segmentation.segment_volume(pages, vol.year)
    record = controle.control_volume(seg, pages)
    volume_index = len(built.volumes)
    first_decree_id = len(built.decrees)
    built.volumes.append(volume_row(vol, files.doc, pages, seg.issues, record,
                                    link_checks.get(str(vol.year), catalogue.image_check(vol) or "non vérifié")))
    for index, decree in enumerate(seg.decrees):
        decree_id = first_decree_id + index
        built.decrees.append(decree_row(decree_id, volume_index, decree, first_decree_id))
        for entry in decree.entries:
            built.entries.append(entry_row(len(built.entries), volume_index, decree_id, entry))
    for block in seg.unsegmented:
        built.entries.append(unsegmented_row(len(built.entries), volume_index, first_decree_id + block.decree_index,
                                             block, pages[block.leaf].computed))
    manual = manual_pages_of(vol, files.doc, volume_index, pages, seg, record, first_decree_id)
    record["pages_a_lire_a_la_main"] = len(manual)
    built.manual_pages.extend(manual)
    persons = [entry for decree in seg.decrees for entry in decree.entries]
    indigene = personnes.M_INDIGENE | personnes.M_INDIGENE_ENTETE
    return {
        "annee": vol.year, "etat": "indexé", "volume": volume_index,
        "decrets": len(seg.decrees),
        "decrets_republies": sum(1 for decree in seg.decrees if decree.duplicate_of is not None),
        "entrees": len(persons),
        "entrees_hors_republication": sum(1 for e in persons if not e.flags & personnes.F_DECRET_REPUBLIE),
        "entrees_marquees_indigene": sum(1 for e in persons if e.markers & indigene),
        "blocs_non_segmentes": len(seg.unsegmented),
        "taux_pages_table": record["table_alphabetique"]["taux_pages"],
        "taux_listes_numerotees": record["listes_numerotees"]["taux_entrees"],
        "que_faire": "" if seg.decrees else _no_decree_note(vol.year),
    }


def _no_decree_note(year: int) -> str:
    if year < 1865:
        return ("Volume antérieur au sénatus-consulte du 14 juillet 1865 : il ne peut contenir aucun décret "
                "d'admission.")
    return ("Aucun décret d'admission n'a été reconnu par le programme dans ce volume ; ce n'est pas la preuve "
            "qu'il n'y en a pas : feuilleter la table alphabétique du volume à « Naturalisation ».")


def read_link_checks(build_dir: Path) -> dict[str, str]:
    path = build_dir / LINK_CHECKS_FILE
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as handle:
        data = json.load(handle)
    return {str(year): str(state) for year, state in data.items()} if isinstance(data, dict) else {}


def meta(built: Built, sizes: dict[str, tuple[int, int]], today: datetime.date) -> dict:
    coverage = []
    for year in range(catalogue.FIRST_YEAR, catalogue.LAST_YEAR + 1):
        if year in built.coverage:
            coverage.append(built.coverage[year])
        elif year in catalogue.MISSING_YEARS:
            missing = catalogue.MISSING_YEARS[year]
            coverage.append({"annee": year, "etat": missing["etat"], "volume": None, "decrets": 0, "entrees": 0,
                             "que_faire": missing["que_faire"], "lien": missing["lien"],
                             "lien_verifie": missing["lien_verifie"]})
        else:
            coverage.append({"annee": year, "etat": "non téléchargé", "volume": None, "decrets": 0, "entrees": 0,
                             "que_faire": "Lancer « python3 -m decretas.bogga telecharger » puis « construire »."})
    persons = [row for row in built.entries if not row[ENTRY_FIELDS.index("drapeaux")] & personnes.F_NON_SEGMENTE]
    indigene = personnes.M_INDIGENE | personnes.M_INDIGENE_ENTETE
    markers_at = ENTRY_FIELDS.index("marqueurs")
    return {
        "version_format": FORMAT_VERSION,
        "genere_le": today.isoformat(),
        "source": "Bulletin officiel du Gouvernement général de l'Algérie, volumes annuels 1861-1888",
        "credit": CREDIT,
        "bibliotheques": sorted({row[VOLUME_FIELDS.index("bibliotheque")] for row in built.volumes
                                 if row[VOLUME_FIELDS.index("bibliotheque")]}),
        "avertissements": [
            "Le texte vient d'une lecture automatique (OCR) des pages : il contient des fautes. Seule l'image de la "
            "page, ouverte par le lien, fait foi.",
            "Le chiffre 1 est souvent lu 4 par la machine. Une date n'est corrigée que lorsqu'elle est impossible "
            "telle quelle ; un 4 plausible est laissé tel quel. Un jour lu « 44 » est donné comme 14 mais peut être "
            "11 : il est marqué suspect.",
            "Une date de publication n'est donnée que si la ligne « CERTIFIÉ CONFORME » de la livraison a été lue ; "
            "un numéro de livraison calculé peut être décalé d'une unité (livraisons « bis »).",
            "Un nom absent de cet index n'est pas un nom absent du Bulletin : voir les taux de contrôle par volume "
            "et la liste des pages à lire à la main.",
        ],
        "marqueurs": {
            "1": "le mot « indigène » est imprimé dans l'entrée",
            "2": "« musulman(e) »",
            "4": "« israélite »",
            "8": "« étranger / étrangère » comme statut",
            "16": "un mot de nationalité est imprimé (champ nationalite)",
            "32": "l'en-tête du décret dit lui-même « l'indigène / les indigènes dont … »",
            "64": "personne « naturalisée Française » (sous-liste ou décret de naturalisation)",
            "128": "personne « réintégrée dans la qualité de Française »",
        },
        "drapeaux_entrees": {
            "1": "page imprimée calculée d'après les pages voisines",
            "2": "l'entrée court sur deux pages",
            "4": "nom incertain : fin du nom non reconnue, ou initiale abîmée par la lecture automatique",
            "8": "bloc non segmenté : texte brut d'une page à lire à la main, pas une personne identifiée",
            "16": "appartient à un décret republié (voir doublon_de)",
            "32": "une année de naissance est imprimée mais sa lecture est impossible",
            "64": "peut contenir deux personnes : entrée très longue, deux naissances, deux domiciles ou un second nom",
            "128": "personne nommée dans la phrase même du décret",
        },
        "drapeaux_decrets": {
            "1": "première page calculée d'après les pages voisines",
            "2": "l'en-tête nomme « l'indigène / les indigènes »",
            "4": "décret reconnu mais aucune entrée découpée",
            "8": "l'en-tête mentionne des « indigènes » (souvent « les indigènes et étrangers dont les noms suivent ») "
                 "sans dire lesquels",
        },
        "etats_dates": {"0": "lue telle quelle",
                        "1": "corrigée ou déduite par le programme (chiffre 1 lu 4, année rétablie d'après la livraison, "
                             "ou « même jour » que le décret imprimé juste avant)",
                        "2": "suspecte : à lire sur l'image ; la valeur donnée, s'il y en a une, n'est qu'une lecture possible"},
        "etats_numeros_livraison": {"0": "lu sur la page de titre de la livraison",
                                    "1": "calculé depuis une livraison voisine (une livraison « bis » non reconnue le décale d'une unité)",
                                    "2": "incertain"},
        "couverture": coverage,
        "pages_a_lire_a_la_main": built.manual_pages,
        "totaux": {
            "volumes": len(built.volumes),
            "decrets": len(built.decrees),
            "entrees": len(persons),
            "entrees_marquees_indigene": sum(1 for row in persons if row[markers_at] & indigene),
            "blocs_non_segmentes": len(built.entries) - len(persons),
            "pages_a_lire_a_la_main": len(built.manual_pages),
        },
        "fichiers": {name: {"octets": raw, "octets_gzip": packed} for name, (raw, packed) in sizes.items()},
    }


def build(raw_root: Path, site_data: Path, build_dir: Path, volumes: Iterable[catalogue.Volume],
          say: Callable[[str], None] = print, today: datetime.date | None = None) -> int:
    """Segment every downloaded volume and write the four site files. Returns an exit code."""
    built = Built()
    link_checks = read_link_checks(build_dir)
    missing: list[int] = []
    for vol in volumes:
        try:
            files = moisson.local_files(raw_root, vol)
        except moisson.HarvestError as exc:
            say(f"{vol.year} : notice inutilisable ({exc})")
            files = None
        if files is None or not files.complete:
            missing.append(vol.year)
            say(f"{vol.year} : fichiers absents — lancer d'abord « telecharger »")
            continue
        try:
            summary = build_volume(built, vol, files, link_checks)
        except volume.VolumeFormatError as exc:
            missing.append(vol.year)
            say(f"{vol.year} : fichier illisible ({exc})")
            continue
        built.coverage[vol.year] = summary
        say(f"{vol.year} : {summary['decrets']:3d} décrets, {summary['entrees']:5d} entrées "
            f"(dont {summary['entrees_marquees_indigene']:3d} marquées « indigène »), "
            f"table {_percent(summary['taux_pages_table'])}, listes numérotées {_percent(summary['taux_listes_numerotees'])}")
    if not built.volumes:
        say("rien à construire : aucun volume téléchargé")
        return 1
    sizes = {
        "bogga-volumes.json": write_json(site_data / "bogga-volumes.json", columnar(VOLUME_FIELDS, built.volumes)),
        "bogga-decrets.json": write_json(site_data / "bogga-decrets.json", columnar(DECREE_FIELDS, built.decrees)),
        "bogga-entrees.json": write_json(site_data / "bogga-entrees.json", columnar(ENTRY_FIELDS, built.entries)),
    }
    info = meta(built, sizes, today or datetime.date.today())
    sizes["bogga-meta.json"] = write_json(site_data / "bogga-meta.json", info)
    for name, (raw, packed) in sizes.items():
        say(f"écrit  {site_data / name}  {raw} octets ({packed} une fois compressé en gzip)")
    totals = info["totaux"]
    say(f"total : {totals['volumes']} volumes, {totals['decrets']} décrets, {totals['entrees']} entrées, "
        f"{totals['entrees_marquees_indigene']} marquées « indigène », {totals['blocs_non_segmentes']} blocs non "
        f"segmentés, {totals['pages_a_lire_a_la_main']} pages à lire à la main")
    return 1 if missing else 0


def _percent(rate: float | None) -> str:
    return "—" if rate is None else f"{rate * 100:.0f} %"
