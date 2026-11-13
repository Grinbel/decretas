"""Command line of the Archives nationales pipeline: ``python3 -m decretas.an``.

Sub-commands and messages are in French, like the rest of the project's tooling.
"""
from __future__ import annotations

import argparse
import os
import re
import sqlite3
import sys
from collections.abc import Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import NoReturn

from . import build, ead, export, gazetteer, hints, listing, search, verify

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SOURCE = ROOT / "data" / "raw" / "an"
DEFAULT_DATABASE = ROOT / "data" / "build" / "an.sqlite"
DEFAULT_SITE = ROOT / "site" / "data"


def _say(message: str = "") -> None:
    print(message, flush=True)


def _warn(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def _percent(part: int, whole: int) -> str:
    return f"{100 * part / whole:.2f} %".replace(".", ",") if whole else "—"


def _number(value: int) -> str:
    return f"{value:,}".replace(",", " ")


# ----------------------------------------------------------------------------- construire

def _report_export(stats: export.ExportStats, site_dir: Path) -> None:
    _say(f"Décrets exportés : {_number(stats.decrees)}  "
         + ", ".join(f"{k} {_number(v)}" for k, v in sorted(stats.decrees_by_class.items())))
    _say("  par état : " + ", ".join(f"{k} {_number(v)}" for k, v in sorted(stats.decrees_by_state.items())))
    total = stats.persons + stats.spouses + stats.children + stats.second_applicants
    _say(f"Occurrences de noms exportées : {_number(total)}  (principaux {_number(stats.persons)}, "
         f"épouses {_number(stats.spouses)}, enfants {_number(stats.children)}"
         + (f", seconds demandeurs {_number(stats.second_applicants)}" if stats.second_applicants else "") + ")")
    concerned = stats.filae_tier_persons + stats.filae_tier_relatives
    _say("Clause Filae (années 1898 à 1912 et 1928) :")
    _say(f"  {_number(stats.filae_notices)} notices de personnes dans tout le corpus pour ces années ;")
    _say(f"  {_number(concerned)} individus du palier Algérie concernés ({_number(stats.filae_tier_persons)} "
         f"personnes principales, {_number(stats.filae_tier_relatives)} épouses et enfants).")
    if stats.filae_included:
        _say("  --inclure-filae : ces noms SONT dans l'export. Ne pas publier sans l'accord des Archives "
             "nationales ou de la société Filae.")
    else:
        _say("  Ces noms sont RETENUS : leurs décrets sont exportés avec l'état « retenu-filae ». "
             "Ajouter --inclure-filae pour un usage privé ou une fois l'autorisation obtenue.")
    _say(f"Vie privée (personnes pouvant avoir moins de {export.PRIVACY_AGE} ans en {stats.generation_year} : année "
         f"retenue {stats.privacy_threshold} ou postérieure) :")
    _say(f"  {_role_summary(stats.privacy)} ;")
    for reason, counts in stats.privacy_by_reason.items():
        _say(f"    {reason} : {_role_summary(counts)}")
    if stats.privacy_active:
        _say("  Ces noms sont RETENUS : ils ne sont pas dans an-personnes.json. Ajouter "
             "--inclure-vivants-possibles pour un usage privé et local.")
    else:
        _say("  --inclure-vivants-possibles : ces noms SONT dans l'export. Ne pas publier ces fichiers.")
        _warn(f"ATTENTION — --inclure-vivants-possibles : les noms de {_number(stats.privacy['total'])} personnes "
              "pouvant être encore en vie SONT dans l'export. Usage privé et local seulement : ne pas publier "
              "ces fichiers, ne pas les copier sur un serveur (an-meta.json le signale : vie_privee.active = false).")
    _say(f"Noms inexploitables d'épouses et d'enfants, non exportés : {_number(stats.debris['total'])}  ("
         + ", ".join(f"{flag} {count}" for flag, count in stats.debris_by_flag.items()) + ")")
    _say(f"Notices entrées dans le palier Algérie par l'épouse ou un enfant seulement (tout le corpus) : "
         f"{_number(stats.tier_by_relative)}")
    _say(f"Liens hors gabarit publiés comme exceptions : {stats.link_exceptions}")
    _say("Fichiers écrits :")
    for name, (raw_size, gzip_size) in stats.sizes.items():
        _say(f"  {site_dir / name}  {_number(raw_size)} octets ({_number(gzip_size)} en gzip)")


def _role_summary(counts: dict[str, int]) -> str:
    """'118 occurrences de noms (1 principal, 7 épouses, 110 enfants)' -- zero roles omitted."""
    labels = (("principaux", "principal", "principaux"), ("epouses", "épouse", "épouses"),
              ("enfants", "enfant", "enfants"), ("seconds_demandeurs", "second demandeur", "seconds demandeurs"))
    detail = ", ".join(f"{_number(counts[key])} {one if counts[key] == 1 else many}"
                       for key, one, many in labels if counts[key])
    total = counts["total"]
    return f"{_number(total)} occurrence{'' if total == 1 else 's'} de noms" + (f" ({detail})" if detail else "")


def _publie(sortie: Path) -> bool:
    """True when a directory is inside site/, i.e. would be served to the public."""
    return sortie.resolve().is_relative_to((ROOT / "site").resolve())


def command_build(args: argparse.Namespace) -> int:
    # A private export (names of the Filae years, or of people who may be alive) is never written
    # where the site is served from: it must be sent to another directory on purpose.
    privees = [option for option, active in (("--inclure-vivants-possibles", args.inclure_vivants_possibles),
                                              ("--inclure-filae", args.inclure_filae)) if active]
    if privees and _publie(args.sortie):
        _warn(f"Refusé : {' et '.join(privees)} produit un export privé, qui ne doit jamais être écrit dans "
              f"le site ({args.sortie}). Indiquez un autre dossier avec --sortie, par exemple "
              "--sortie data/build/export-prive.")
        return 2
    timestamp = args.horodatage or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        export.generation_year(timestamp)      # refuse an unreadable --horodatage before the long build
    except export.ExportError as error:
        _warn(f"Échec : {error}")
        return 1
    if not args.export_seul:
        _say(f"Lecture des inventaires XML de {args.source} …")
        try:
            stats = build.build_database(args.source, args.base, progress=None if args.silencieux else _say)
        except (build.BuildError, ead.EadError) as error:
            _warn(f"Échec : {error}")
            return 1
        _say(f"Base écrite : {args.base}")
        _say(f"  {stats.inventories} inventaires, {_number(stats.decrees)} décrets, {_number(stats.persons)} notices "
             f"de personnes, {_number(stats.relatives)} épouses et enfants")
        _say(f"  {stats.discarded} notices écartées, {stats.unparsed_lines} lignes non comprises sur "
             f"{_number(stats.lines)} ({_percent(stats.lines - stats.unparsed_lines, stats.lines)} comprises)")
        if stats.root_inventories:
            _say(f"  inventaire racine ignoré (table des inventaires, aucun décret) : {', '.join(stats.root_inventories)}")
    try:
        export_stats = export.export_site(args.base, args.sortie, include_filae=args.inclure_filae,
                                          timestamp=timestamp,
                                          include_possibly_living=args.inclure_vivants_possibles)
    except export.ExportError as error:
        _warn(f"Échec : {error}")
        return 1
    _report_export(export_stats, args.sortie)
    return 0


# ----------------------------------------------------------------------------- verifier

def command_verify(args: argparse.Namespace) -> int:
    try:
        report = verify.verify(args.source, args.base)
    except verify.VerifyError as error:
        _warn(f"Échec : {error}")
        return 1
    _say(f"Fichiers XML : {report.files_ok} conformes au manifeste sur {report.files}")
    for problem in report.file_problems:
        _say(f"  ANOMALIE  {problem}")
    _say(f"Effectifs par inventaire : {report.inventories} inventaires comparés à la table attendue, "
         f"{len(report.count_problems)} écart(s)")
    for problem in report.count_problems:
        _say(f"  ÉCART  {problem}")
    _say("Couverture de l'analyseur :")
    for label, part, whole in report.coverage:
        _say(f"  {_percent(part, whole):>9}  {label} ({_number(part)} sur {_number(whole)})")
    _say("Signalements :")
    for label, count in report.flags:
        _say(f"  {_number(count):>9}  {label}")
    for problem in report.link_problems:
        _say(f"  ANOMALIE  {problem}")
    _say(f"Notices écartées de l'index des noms : {len(report.discarded)}")
    for inv, notice, reason, title in report.discarded:
        _say(f"  {inv} / {notice} : {title[:90]}  [{reason}]")
    _say(f"Lignes non comprises : {len(report.unparsed)}")
    if args.detail:
        for inv, notice, text in report.unparsed:
            _say(f"  {inv} / {notice} : {text}")
    elif report.unparsed:
        _say("  (ajouter --detail pour les lister : elles contiennent des données personnelles)")
    _say("Résultat : " + ("conforme." if report.ok else "ANOMALIES — voir ci-dessus."))
    return 0 if report.ok else 1


# ----------------------------------------------------------------------------- chercher

def _print_correspondence(connection: sqlite3.Connection, result: search.SearchResult,
                          item: search.Correspondence) -> None:
    record = search.describe(connection, item.person_id)
    name = "(nom non saisi dans l'inventaire)" if record["nom_non_saisi"] else record["nom"]
    _say(f"• {name}")
    birth_notes = []
    if record["conventionnelle"]:
        birth_notes.append("date conventionnelle : comparer l'année")
    if record["suspecte"]:
        birth_notes.append("année suspecte")
    _say(f"    naissance : {record['naissance'] or '—'}" + (f"  [{' ; '.join(birth_notes)}]" if birth_notes else ""))
    if record["residence"]:
        _say(f"    résidence : {record['residence']}")
    if record["profession"]:
        _say(f"    profession : {record['profession']}")
    for role, text, pairing in record["apparentes"]:  # type: ignore[union-attr]
        _say(f"    {role} : {text}" + (f"  [appariement prénom/date : {pairing}]" if pairing else ""))
    cote = str(record["decret_cote"] or "cote absente")
    if record["decret_cote_suggeree"]:
        cote += f" (cote suspecte ; lire probablement {record['decret_cote_suggeree']})"
    date = record["decret_date"] or "date non unique"
    if record["decret_drapeau_date"]:
        date = f"{date} [{record['decret_drapeau_date']}]"
    _say(f"    décret : {record['decret_titre']}")
    _say(f"             date {date} ; classe {record['decret_classe']} ; {cote}"
         + (f" ; {record['decret_document']}" if record["decret_document"] else ""))
    _say(f"    dossier : {record['dossier'] or record['dossier_brut'] or '—'} ; cote du dossier : "
         f"{record['cote_dossier'] or '—'}")
    _say(f"    indice : {hints.HINT_LABELS.get(str(record['indice']), record['indice'])}  [règle : {record['regle']}]"
         + ("" if record["palier"] else "  (hors palier Algérie)"))
    for index, hit in sorted(item.hits.items()):
        _say(f"    terme « {result.terms[index].label} » : {search.LEVELS[hit.level]}, mot « {hit.word} » ({hit.role})")
    if item.missing:
        _say(f"    TERME ABSENT : {', '.join(item.missing)}")
    _say(f"    notice : {record['lien_notice']}")
    _say(f"    images : {record['lien_images'] or record['decret_lien_images']}"
         + ("" if record["lien_images"] else "  (images du décret : la personne n'a pas de lien propre)"))
    _say(f"    identifiants : {record['inv']} / {record['notice']} (décret {record['decret_notice']})")


def command_search(args: argparse.Namespace) -> int:
    if not args.base.exists():
        _warn(f"Échec : base absente : {args.base} (lancer d'abord « construire »)")
        return 1
    connection = build.read_only(args.base)
    try:
        result = search.search(connection, args.termes, born_around=args.ne_vers, tolerance=args.tolerance,
                               tier_only=args.algerie)
        for index, term in enumerate(result.terms):
            _say(f"Terme {index + 1} : {' / '.join(term.variants)}  — {_number(result.notices_per_term[index])} notices")
        if args.ne_vers is not None:
            _say(f"Filtre : né(e) vers {args.ne_vers} (± {args.tolerance} ans ; les années inconnues sont gardées)")
        _say(f"Correspondances : {len(result.correspondences)}")
        for item in result.correspondences[:args.limite]:
            _print_correspondence(connection, result, item)
        if len(result.correspondences) > args.limite:
            _say(f"  … {len(result.correspondences) - args.limite} autres (augmenter --limite)")
        if len(result.terms) > 1:
            _say(f"Correspondances partielles (un terme absent) : {len(result.partial)}")
            for item in result.partial[:args.limite]:
                _print_correspondence(connection, result, item)
            if len(result.partial) > args.limite:
                _say(f"  … {len(result.partial) - args.limite} autres (augmenter --limite)")
        states = dict(connection.execute("SELECT etat, COUNT(*) FROM inventaire GROUP BY etat"))
        _say("Bilan de recherche :")
        _say(f"  {_number(result.searched_notices)} notices de personnes fouillées"
             + (" (palier Algérie seulement)" if args.algerie else "") + ", avec leurs épouses et enfants ;")
        _say(f"  inventaires indexés par nom : {states.get(build.STATE_INDEXED, 0)} ; partiels : "
             f"{states.get(build.STATE_PARTIAL, 0)} ; image seule (aucun nom) : {states.get(build.STATE_IMAGE, 0)} ;")
        _say("  non couvert : 1899-1912 et avril-décembre 1928 (quelques noms seulement), 1933-1948 (aucun nom), "
             "les jugements de la loi de 1919, toute graphie très éloignée des variantes saisies.")
    finally:
        connection.close()
    return 0


# ----------------------------------------------------------------------------- decrets

def command_decrees(args: argparse.Namespace) -> int:
    paths = ead.inventory_files(args.source)
    if not paths:
        _warn(f"Échec : aucun inventaire FRAN_IR_*.xml dans {args.source}")
        return 1
    try:
        records = listing.decree_records(paths)
    except ead.EadError as error:
        _warn(f"Échec : {error}")
        return 1
    if args.algerie:
        records = listing.only_algeria(records)
    listing.write_csv(records, args.csv)
    _say(f"{_number(len(records))} décrets écrits dans {args.csv}")
    counts: dict[str, int] = {}
    for record in records:
        key = str(record["classe_algerie"])
        counts[key] = counts.get(key, 0) + 1
    _say("  par classe : " + ", ".join(f"{k} {_number(v)}" for k, v in sorted(counts.items())))
    return 0


# ----------------------------------------------------------------------------- maintenance

def command_gazetteer(args: argparse.Namespace) -> int:
    if not args.base.exists():
        _warn(f"Échec : base absente : {args.base} (lancer d'abord « construire »)")
        return 1
    connection = build.read_only(args.base)
    try:
        places = [row[0] for row in connection.execute(
            "SELECT naissance_lieu FROM personne WHERE naissance_lieu != '' UNION ALL "
            "SELECT residence FROM personne WHERE residence != '' UNION ALL "
            "SELECT naissance_lieu FROM apparente WHERE naissance_lieu != ''")]
    finally:
        connection.close()
    rows = gazetteer.derive(places)
    gazetteer.write(rows, args.fichier)
    safe = sum(1 for row in rows if row["statut"] == gazetteer.STATUS_SAFE)
    _say(f"{len(rows)} localités écrites dans {args.fichier}, dont {safe} sûres. Relancer « construire ».")
    return 0


def command_expected(args: argparse.Namespace) -> int:
    if not args.base.exists():
        _warn(f"Échec : base absente : {args.base} (lancer d'abord « construire »)")
        return 1
    connection = build.read_only(args.base)
    try:
        count = verify.write_expected(connection, args.fichier)
    finally:
        connection.close()
    _say(f"Effectifs de {count} inventaires enregistrés comme attendus dans {args.fichier}")
    return 0


# ----------------------------------------------------------------------------- parser

class _FrenchFormatter(argparse.HelpFormatter):
    def add_usage(self, usage, actions, groups, prefix=None):  # type: ignore[no-untyped-def]
        super().add_usage(usage, actions, groups, prefix="utilisation : " if prefix is None else prefix)


_ARGPARSE_MESSAGES: tuple[tuple[str, str], ...] = (
    (r"the following arguments are required: (.*)", r"arguments obligatoires manquants : \1"),
    (r"unrecognized arguments: (.*)", r"arguments inconnus : \1"),
    (r"argument (.*): invalid choice: (.*) \(choose from (.*)\)", r"argument \1 : choix inconnu \2 (choix possibles : \3)"),
    (r"argument (.*): invalid \w+ value: (.*)", r"argument \1 : valeur invalide \2"),
    (r"argument (.*): expected one argument", r"argument \1 : une valeur est attendue"),
    (r"argument (.*): expected at least one argument", r"argument \1 : au moins une valeur est attendue"),
)


class _FrenchParser(argparse.ArgumentParser):
    """argparse with French usage, section titles and error messages."""

    def __init__(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        kwargs.setdefault("formatter_class", _FrenchFormatter)
        kwargs.setdefault("add_help", False)
        super().__init__(*args, **kwargs)
        self._positionals.title = "arguments"
        self._optionals.title = "options"
        self.add_argument("-h", "--aide", action="help", help="afficher cette aide et quitter")

    def error(self, message: str) -> NoReturn:
        for pattern, replacement in _ARGPARSE_MESSAGES:
            if re.fullmatch(pattern, message):
                message = re.sub(pattern, replacement, message)
                break
        self.print_usage(sys.stderr)
        self.exit(2, f"{self.prog} : erreur : {message}\n")


def make_parser() -> argparse.ArgumentParser:
    parser = _FrenchParser(
        prog="python3 -m decretas.an",
        description="Index des décrets des Archives nationales (BB/34, 1883-1948) : construction, vérification, recherche.")
    commands = parser.add_subparsers(dest="commande", required=True, metavar="commande", title="commandes")

    def common(sub: argparse.ArgumentParser, *, source: bool = True, base: bool = True) -> None:
        if source:
            sub.add_argument("--source", type=Path, default=DEFAULT_SOURCE, metavar="DOSSIER",
                             help="dossier des exports XML et de manifest.jsonl (défaut : data/raw/an)")
        if base:
            sub.add_argument("--base", type=Path, default=DEFAULT_DATABASE, metavar="FICHIER",
                             help="base SQLite (défaut : data/build/an.sqlite)")

    sub = commands.add_parser("construire", help="XML -> base SQLite + fichiers du site",
                              description="Lit les inventaires XML, écrit la base SQLite et les trois fichiers du site.")
    common(sub)
    sub.add_argument("--sortie", type=Path, default=DEFAULT_SITE, metavar="DOSSIER",
                     help="dossier des fichiers du site (défaut : site/data)")
    sub.add_argument("--inclure-filae", action="store_true",
                     help="exporter aussi les noms des années couvertes par la clause Filae (1898-1912, 1928) ; "
                          "usage privé, ou après autorisation ; exige un --sortie hors de site/")
    sub.add_argument("--inclure-vivants-possibles", action="store_true",
                     help="exporter aussi les noms des personnes qui pourraient être encore en vie (moins de "
                          "100 ans l'année de la génération) ; usage privé et local seulement, jamais publié ; "
                          "exige un --sortie hors de site/")
    sub.add_argument("--horodatage", metavar="ISO",
                     help="date de génération à inscrire dans an-meta.json, commençant par AAAA-MM-JJ (défaut : "
                          "maintenant, en UTC) ; son année fixe le seuil de la règle « vie privée »")
    sub.add_argument("--export-seul", action="store_true",
                     help="ne pas relire les XML : refaire seulement les fichiers du site depuis la base")
    sub.add_argument("--silencieux", action="store_true", help="ne pas afficher une ligne par inventaire")
    sub.set_defaults(run=command_build)

    sub = commands.add_parser("verifier", help="intégrité des fichiers, effectifs, couverture de l'analyseur",
                              description="Compare les XML au manifeste (SHA-256), les effectifs à la table attendue, "
                                          "et mesure ce que l'analyseur a compris.")
    common(sub)
    sub.add_argument("--detail", action="store_true",
                     help="lister les lignes non comprises (elles contiennent des données personnelles)")
    sub.set_defaults(run=command_verify)

    sub = commands.add_parser("chercher", help="recherche de mise au point dans la base",
                              description="Chaque argument est un terme ; ses variantes sont séparées par une virgule. "
                                          "Exemple : chercher testaoui,testaouy amar exemple --ne-vers 1876")
    common(sub, source=False)
    sub.add_argument("termes", nargs="+", metavar="terme", help="un terme du nom, variantes séparées par des virgules")
    sub.add_argument("--ne-vers", type=int, metavar="AAAA", help="ne garder que les personnes nées vers cette année")
    sub.add_argument("--tolerance", type=int, default=5, metavar="N", help="écart admis en années (défaut : 5)")
    sub.add_argument("--algerie", action="store_true", help="ne fouiller que le palier Algérie")
    sub.add_argument("--limite", type=int, default=20, metavar="N", help="nombre de notices affichées (défaut : 20)")
    sub.set_defaults(run=command_search)

    sub = commands.add_parser("decrets", help="liste de tous les décrets en CSV",
                              description="Écrit un CSV de tous les décrets : date réconciliée, famille, classe Algérie, "
                                          "drapeaux, état, liens copiés du XML.")
    common(sub, base=False)
    sub.add_argument("--csv", type=Path, required=True, metavar="FICHIER", help="fichier CSV à écrire")
    sub.add_argument("--algerie", action="store_true", help="seulement les décrets de classe A1, A2, A3 ou R")
    sub.set_defaults(run=command_decrees)

    sub = commands.add_parser("repertoire", help="(maintenance) recalculer le répertoire des localités d'Algérie",
                              description="Recalcule decretas/an/reference/gazetteer_algerie.tsv à partir de la base.")
    common(sub, source=False)
    sub.add_argument("--fichier", type=Path, default=gazetteer.GAZETTEER_PATH, metavar="FICHIER",
                     help="fichier TSV à écrire")
    sub.set_defaults(run=command_gazetteer)

    sub = commands.add_parser("attendus", help="(maintenance) enregistrer les effectifs actuels comme attendus",
                              description="Écrit decretas/an/reference/inventaires_attendus.tsv à partir de la base.")
    common(sub, source=False)
    sub.add_argument("--fichier", type=Path, default=verify.EXPECTED_PATH, metavar="FICHIER",
                     help="fichier TSV à écrire")
    sub.set_defaults(run=command_expected)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = make_parser().parse_args(argv)
    try:
        return int(args.run(args))
    except BrokenPipeError:
        # The reader went away (`… | head`): stop quietly, without a traceback.
        sys.stdout = open(os.devnull, "w", encoding="utf-8")  # noqa: SIM115 (kept open until exit)
        return 0
