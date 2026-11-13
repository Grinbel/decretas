"""Command line of the image-only decree tools: ``python3 -m decretas.an_images``.

Sub-commands and messages are in French, like the rest of the project's tooling.
"""
from __future__ import annotations

import argparse
import datetime
import json
import sys
import time
import urllib.parse
from collections.abc import Sequence
from pathlib import Path

from decretas import net

from . import collecte, lecteurs, lire, metadonnees, plan, rapport, reprise
from .client import SessionClient

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw" / "an-images"
BUILD = ROOT / "data" / "build" / "an-images"
SITE_DATA = ROOT / "site" / "data"
LOCAL_EXPORTS = ROOT / "data" / "raw" / "an"

# Hard ceilings on the real host, whatever the options say (changing them is a code change, on purpose).
MAX_CAP_REAL_HOST = 40
MAX_DAY_CAP_REAL_HOST = 80
AVAILABILITY_PATH = "/siv/IR/FRAN_IR_057268"      # the one address known to answer when the site is up (302)
AVAILABILITY_MIN_DELAY = 60.0


def _say(message: str = "") -> None:
    print(message, flush=True)


def _warn(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


#: One stop file for the host, read and written by every command that sends requests to it.
HOST_STOP = RAW / "arret.json"


def _is_real_host(base: str) -> bool:
    # every host but a local test server gets the limits of the real one (see reprise.is_real_host)
    return reprise.is_real_host(base)


# ----------------------------------------------------------------------------- disponibilite

def command_availability(args: argparse.Namespace) -> int:
    url = args.base.rstrip("/") + AVAILABILITY_PATH
    root = Path(args.racine)
    if args.simulation:
        _say(f"Simulation : une seule requête serait envoyée — GET {url}")
        _say("Rien n'est envoyé, rien n'est écrit.")
        return 0
    stop_path = Path(args.arret)
    host = reprise.normalised_host(args.base)
    refused = reprise.host_refusal(stop_path, host, time.time())
    if refused is not None:
        _say(refused[1] + " Rien n'est envoyé.")
        return refused[0]
    probe = reprise.Probe(reprise.Settings(root=root, base=args.base), [], say=lambda _message: None)
    today = probe.requests_today(time.time())
    if today >= args.max_par_jour:
        _say(f"Déjà {today} vérification(s) aujourd'hui (plafond {args.max_par_jour}) : rien n'est envoyé. Réessayer demain.")
        return reprise.EXIT_CAP
    parts = urllib.parse.urlsplit(args.base)
    real = _is_real_host(args.base)
    policy = net.HostPolicy(min_delay=AVAILABILITY_MIN_DELAY if real else 0.0, budget=1, max_backoffs=0, timeout=args.delai_reponse,
                            allow_http=parts.scheme == "http" and not real)
    client = SessionClient(root=root, policies={(parts.hostname or "").lower(): policy}, count_manifest_in_budget=False,
                           retry_failed=True)
    stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        row, _fresh = client.hop(url, "derniere-reponse.corps", force=True)
    except net.Blocked as error:
        reprise.write_host_stop(stop_path, host, blocage=f"{stamp} — {error}")
        _say(f"{stamp} — REFUS : {error}")
        _say("Le site refuse ce programme (403, 429 ou page anti-robot). Ne rien relancer ; voir docs/decrets-en-images.md.")
        return reprise.EXIT_BLOCKED
    except net.ServerUnavailable:
        reprise.write_host_stop(stop_path, host, pause_jusqu_a=time.time() + reprise.Settings(root=root).pause_seconds)
        status = (client.cached(url) or {}).get("status")
        _say(f"{stamp} — HTTP {status} : le site est toujours en panne. Ne pas lancer la reprise ; revérifier dans 30 minutes au plus tôt.")
        return reprise.EXIT_PAUSED
    except net.TransportError as error:
        reprise.write_host_stop(stop_path, host, pause_jusqu_a=time.time() + reprise.Settings(root=root).pause_seconds)
        _say(f"{stamp} — aucune réponse ({error}). Site injoignable ou très lent : ne pas lancer la reprise.")
        return reprise.EXIT_PAUSED
    except net.NetError as error:
        _say(f"{stamp} — vérification impossible : {error}")
        return reprise.EXIT_ERROR
    status = int(row["status"])
    if status in (200, 301, 302, 303, 307, 308):
        where = f" → {row['location'].split(';jsessionid=')[0]}" if row.get("location") else ""
        _say(f"{stamp} — HTTP {status}{where} en {row.get('elapsed_ms')} ms : le site RÉPOND. La reprise peut être lancée.")
        return 0
    _say(f"{stamp} — HTTP {status} : réponse inattendue pour une adresse connue. Ne pas lancer la reprise sans regarder "
         f"{root / (row.get('corps_hors_2xx') or '')}.")
    return reprise.EXIT_ERROR


# ----------------------------------------------------------------------------- reprise

def _parse_manual(items: Sequence[str]) -> dict[str, list[str]]:
    manual: dict[str, list[str]] = {}
    for item in items:
        case, equals, address = item.partition("=")
        if not equals or case not in plan.CASES or not address:
            raise ValueError(f"--suivre attend CAS=ADRESSE avec CAS parmi {', '.join(plan.CASES)} ; reçu « {item} ».")
        manual.setdefault(case, []).append(address)
    return manual


def command_probe(args: argparse.Namespace) -> int:
    root = Path(args.racine)
    report = Path(args.rapport)
    real = _is_real_host(args.base)
    availability = RAW / "disponibilite" if real else None        # the log of the availability checks is recalled in the report
    if args.rapport_seul:
        planned = plan.plan_from_site_data(Path(args.donnees)).select(None, args.palier)
        _say(f"Rapport écrit : {rapport.write_report(root, report, planned=planned, availability=availability)}")
        return 0
    try:
        manual = _parse_manual(args.suivre or [])
    except ValueError as error:
        _warn(str(error))
        return 2
    cases = None
    if args.cas:
        cases = {item.strip() for item in args.cas.split(",") if item.strip()}
        unknown = cases - set(plan.CASES)
        if unknown:
            _warn(f"Cas inconnu(s) : {', '.join(sorted(unknown))}. Cas existants : {', '.join(plan.CASES)}.")
            return 2
    if real and args.delai < reprise.MIN_DELAY_REAL_HOST:
        _warn(f"Délai refusé : {args.delai:g} s. Le minimum sur cet hôte est {reprise.MIN_DELAY_REAL_HOST:g} s.")
        return 2
    cap = min(args.plafond, MAX_CAP_REAL_HOST) if real else args.plafond
    day_cap = min(args.plafond_jour, MAX_DAY_CAP_REAL_HOST) if real else args.plafond_jour
    if real and (cap != args.plafond or day_cap != args.plafond_jour):
        _say(f"Plafonds ramenés aux maximums de cet hôte : {cap} requêtes par passage, {day_cap} par jour.")
    full = plan.plan_from_site_data(Path(args.donnees))
    steps = full.select(cases, args.palier)
    settings = reprise.Settings(root=root, base=args.base, delay=args.delai, cap=cap, day_cap=day_cap, timeout=args.delai_reponse,
                                lift_block=args.lever_blocage, local_exports=LOCAL_EXPORTS, manual=manual,
                                stop_path=Path(args.arret))
    if args.simulation:
        _say(reprise.describe_plan(steps, full.missing, settings))
        probe = reprise.Probe(settings, steps, missing=full.missing, say=lambda _message: None)
        refused = probe.refusal(time.time())
        _say("")
        _say("État actuel : " + (refused[1] if refused else "aucune pause ni arrêt en cours."))
        return 0
    if not steps and not manual:
        _warn("Aucune étape à exécuter avec ces options.")
        return 2
    for sentence in full.missing:
        _say(f"NON PLANIFIÉ : {sentence}")
    _say(f"Reprise : {len(steps)} adresse(s) de départ, {settings.delay:g} s au moins entre deux requêtes, "
         f"plafond {cap} requêtes. Corps et manifeste : {root}")
    probe = reprise.Probe(settings, steps, missing=full.missing, say=_say)
    try:
        code = probe.run()
    except net.NetError as error:
        _warn(f"Arrêt sur une erreur inattendue du client : {error}")
        code = reprise.EXIT_ERROR
    _say(f"Rapport écrit : {rapport.write_report(root, report, planned=steps, availability=availability)}")
    return code


# ----------------------------------------------------------------------------- metadonnees

def _expand(paths: Sequence[str]) -> list[Path]:
    files: list[Path] = []
    for item in paths:
        path = Path(item)
        if path.is_dir():
            files.extend(sorted((child for child in path.rglob("*")
                                 if child.is_file() and child.suffix.lower() in metadonnees.IMAGE_SUFFIXES),
                                key=lambda child: lire.natural_key(str(child))))
        else:
            files.append(path)
    return files


def command_metadata(args: argparse.Namespace) -> int:
    files = _expand(args.fichiers)
    if not files:
        _warn("Aucun fichier d'image à inspecter.")
        return 2
    if args.url and len(files) != 1:
        _warn("--url ne s'emploie qu'avec un seul fichier.")
        return 2
    cards = [metadonnees.inspecter(path, url=args.url, pil=not args.sans_pil) for path in files]
    document = {"format": "decretas-an-images-metadonnees/1", "fichiers": cards}
    if len(cards) > 1:
        document["suite_des_noms"] = metadonnees.analyser_suite([Path(card["fichier"]).name for card in cards])
    if args.json:
        destination = Path(args.json)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(document, ensure_ascii=False, indent=1, default=str) + "\n", encoding="utf-8")
    if args.format == "json":
        _say(json.dumps(document, ensure_ascii=False, indent=1, default=str))
    else:
        _say(metadonnees.tableau(cards))
        if args.json:
            _say(f"JSON écrit : {args.json}")
    unreadable = [card["fichier"] for card in cards if card.get("format") == "inconnu"]
    return 1 if len(unreadable) == len(cards) else 0


# ----------------------------------------------------------------------------- lire

def command_read(args: argparse.Namespace) -> int:
    folder = Path(args.dossier)
    if not folder.is_dir():
        _warn(f"Dossier introuvable : {folder}")
        return 2
    tesseract = lecteurs.TesseractReader(page_mode=args.psm, language=args.langue)
    try:
        document = lire.read_folder(folder, mode=args.lecteur, config=Path(args.config) if args.config else None,
                                    inventory=args.inventaire, notice=args.notice, date=args.date, tesseract=tesseract)
    except lecteurs.ReaderUnavailable as error:
        _warn(str(error))
        return 1
    summary = document["bilan"]
    _say(f"Dossier : {folder} — {summary['images']} image(s), {summary['decrets']} décret(s).")
    for name, note in document["lecteurs"].items():
        _say(f"  lecteur {name} : {note}")
    if not summary["images"]:
        _warn("Aucune image dans ce dossier (extensions reconnues : " + ", ".join(metadonnees.IMAGE_SUFFIXES) + ").")
        return 2
    for decree in document["decrets"]:
        label = decree["decret"] or "décret non identifié (options --inventaire et --notice absentes)"
        stats = decree["stats"]
        _say(f"  {label} : lecture {decree['lecture']} ; {stats['entrees']} personne(s), {stats['epouses']} épouse(s), "
             f"{stats['enfants']} enfant(s) ; {stats['avec_numero_de_dossier']} numéro(s) de dossier ; "
             f"tampon : {decree['preambule'].get('date_du_tampon', 'non lu')}")
        if decree["numeros_orphelins"]:
            _say(f"    numéros de dossier lus sans personne en regard : {', '.join(decree['numeros_orphelins'])}")
        if stats["lignes_non_rattachees"]:
            _say(f"    {stats['lignes_non_rattachees']} ligne(s) rattachée(s) à aucune personne : gardée(s) en blocs de texte "
                 "cherchables" + ("" if stats["entrees"] else " (AUCUNE personne reconnue : mise en page inconnue de l'analyseur)"))
    for unread in document["non_lues"]:
        _say(f"  NON LUE : {unread['fichier']} — {unread['raison']}")
    if document["non_lues"] and "tesseract" in document["lecteurs"] and "pas installé" in document["lecteurs"]["tesseract"]:
        _say("  Pour lire ces images : écrire leur transcription dans un fichier .txt à côté de chacune, installer "
             "Tesseract, ou brancher une commande externe (--lecteur commande --config …).")
    destination = lire.write(document, Path(args.sortie))
    _say(f"{summary['occurrences']} occurrence(s) écrite(s) dans {destination}"
         f" ({summary['principaux']} personne(s) principale(s), {summary['blocs_de_texte']} bloc(s) de texte non découpé)")
    _say("Chaque occurrence porte la mention « à vérifier sur l'image ». Ce fichier n'est pas publié sur le site.")
    if summary["drapeaux"]:
        _say("Signalements : " + ", ".join(f"{flag} {count}" for flag, count in summary["drapeaux"].items()))
    return 0 if summary["images_lues"] else 3


# ----------------------------------------------------------------------------- plan-collecte

def command_collection_plan(args: argparse.Namespace) -> int:
    source = Path(args.donnees)
    try:
        result = collecte.compute(collecte.load_decrees(source), years=collecte.parse_years(args.annees),
                                  classes=collecte.parse_classes(args.classes), pages_per_decree=args.pages_par_decret,
                                  fixed_requests=args.requetes_fixes, delay=args.delai, hours_per_day=args.heures_par_jour,
                                  born=args.ne_en)
    except collecte.PlanError as error:
        _warn(str(error))
        return 1
    all_decrees = Path(args.tous_les_decrets)
    anchors = collecte.media_anchors(all_decrees)
    result["reperes_de_media"] = anchors
    directory = Path(args.sortie)
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "plan-collecte.json").write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    (directory / "plan-collecte.md").write_text(collecte.markdown(result, source, anchors, all_decrees), encoding="utf-8")
    (directory / "plan-collecte-decrets.csv").write_text(collecte.decrees_csv(result), encoding="utf-8")
    total = result["total"]
    if args.ne_en is not None:
        _say(f"Ancêtre né en {args.ne_en} : décrets datés de {args.ne_en + collecte.MAJORITY} ou après seulement.")
    _say(f"{total['decrets']} décrets en images seules ({', '.join(f'{k} {v}' for k, v in result['par_classe'].items())}).")
    for period in result["periodes"]:
        _say(f"  {period['periode']:<14} {period['decrets']:>5} décrets  {period['requetes']:>6} requêtes  {period['heures']:>6} h")
    _say(f"Avec {args.pages_par_decret} images et {args.requetes_fixes} requêtes fixes par décret (HYPOTHÈSES non mesurées), "
         f"à 1 requête toutes les {args.delai:g} s : {total['requetes']} requêtes, {total['heures']} h, "
         f"{total['jours']} jours de {args.heures_par_jour:g} h.")
    if anchors and anchors["ensemble"]["numeros_par_decret"]:
        _say(f"Indice tiré des {len(anchors['reperes'])} identifiants de média du XML (HYPOTHÈSE d'un compteur continu de vues) : "
             f"{anchors['ensemble']['numeros_par_decret']} numéros par décret en moyenne, tous décrets confondus, de "
             f"{anchors['ensemble']['du']} à {anchors['ensemble']['au']}.")
    else:
        _say(f"Indice des identifiants de média : non calculé ({all_decrees} absent ou sans identifiant).")
    _say("Le collecteur n'est pas écrit : il attend que la reprise ait montré la structure réelle des pages.")
    _say(f"Écrit : {directory / 'plan-collecte.md'}, plan-collecte.json, plan-collecte-decrets.csv")
    return 0


# ----------------------------------------------------------------------------- parser

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python3 -m decretas.an_images",
        description="Décrets conservés en images seules aux Archives nationales : reprise de l'observation du site, "
                    "métadonnées des images, lecture des pages, plan de collecte.")
    commands = parser.add_subparsers(dest="commande", required=True, metavar="commande")

    sub = commands.add_parser("disponibilite", help="une requête polie : le site répond-il ?")
    sub.add_argument("--simulation", action="store_true", help="dire ce qui serait envoyé, sans rien envoyer")
    sub.add_argument("--max-par-jour", type=int, default=6, help="nombre maximal de vérifications par jour (défaut : 6)")
    sub.add_argument("--delai-reponse", type=float, default=60.0, help="secondes d'attente d'une réponse (défaut : 60)")
    sub.add_argument("--racine", default=str(RAW / "disponibilite"), help="dossier du journal de ces vérifications")
    sub.add_argument("--arret", default=str(HOST_STOP), help="fichier d'arrêt partagé avec « reprise » pour cet hôte (défaut : data/raw/an-images/arret.json)")
    sub.add_argument("--base", default=plan.BASE, help="adresse du site (à ne changer que pour un essai sur un serveur local)")
    sub.set_defaults(run=command_availability)

    sub = commands.add_parser("reprise", help="exécuter le plan d'observation (un exemplaire de chaque cas)")
    sub.add_argument("--simulation", action="store_true", help="afficher le plan et l'état ; ne rien envoyer, ne rien écrire")
    sub.add_argument("--cas", help="ne traiter que ces cas, séparés par des virgules (" + ", ".join(plan.CASES) + ")")
    sub.add_argument("--palier", type=int, choices=(1, 2), default=2,
                     help="1 : l'essentiel seulement ; 2 : l'essentiel puis les compléments (défaut)")
    sub.add_argument("--plafond", type=int, default=40, help="requêtes au plus pour ce passage (défaut et maximum : 40)")
    sub.add_argument("--plafond-jour", type=int, default=80, help="requêtes au plus par jour, tous passages confondus (défaut et maximum : 80)")
    sub.add_argument("--delai", type=float, default=6.0, help="secondes entre deux requêtes (défaut et minimum : 6)")
    sub.add_argument("--delai-reponse", type=float, default=90.0, help="secondes d'attente d'une réponse (défaut : 90)")
    sub.add_argument("--suivre", action="append", metavar="CAS=ADRESSE",
                     help="ajouter une adresse lue à la main dans un corps enregistré (répétable)")
    sub.add_argument("--lever-blocage", action="store_true",
                     help="décision humaine : reprendre après un refus enregistré (403, 429, page anti-robot)")
    sub.add_argument("--rapport-seul", action="store_true", help="réécrire le rapport à partir du disque, sans rien envoyer")
    sub.add_argument("--racine", default=str(RAW / "reprise"), help="dossier des corps reçus, du manifeste et de l'état")
    sub.add_argument("--arret", default=str(HOST_STOP), help="fichier d'arrêt partagé avec « disponibilite » pour cet hôte (défaut : data/raw/an-images/arret.json)")
    sub.add_argument("--rapport", default=str(BUILD / "reprise-rapport.md"), help="fichier du rapport")
    sub.add_argument("--donnees", default=str(SITE_DATA), help="dossier des données du site (pour choisir les exemplaires de personnes)")
    sub.add_argument("--base", default=plan.BASE, help="adresse du site (à ne changer que pour un essai sur un serveur local)")
    sub.set_defaults(run=command_probe)

    sub = commands.add_parser("metadonnees", help="ce que disent un fichier d'image, son nom et son adresse")
    sub.add_argument("fichiers", nargs="+", help="fichiers d'images, ou dossiers (parcourus en entier)")
    sub.add_argument("--json", metavar="FICHIER", help="écrire aussi le résultat complet en JSON dans ce fichier")
    sub.add_argument("--format", choices=("tableau", "json"), default="tableau", help="affichage : tableau lisible (défaut) ou JSON")
    sub.add_argument("--url", help="adresse d'où vient le fichier (un seul fichier) : elle est décodée aussi")
    sub.add_argument("--sans-pil", action="store_true", help="ne pas recouper les dimensions avec Pillow, même s'il est installé")
    sub.set_defaults(run=command_metadata)

    sub = commands.add_parser("lire", help="transcrire les images d'un dossier en occurrences de noms à vérifier")
    sub.add_argument("dossier", help="dossier d'images (une page de décret par image)")
    sub.add_argument("--lecteur", choices=("auto", "manuel", "tesseract", "commande"), default="auto",
                     help="auto (défaut) : transcription .txt voisine, sinon Tesseract s'il est installé")
    sub.add_argument("--config", metavar="FICHIER", help="configuration JSON du lecteur « commande »")
    sub.add_argument("--inventaire", help="identifiant de l'inventaire du décret (FRAN_IR_…) si le dossier n'a pas de decret.json")
    sub.add_argument("--notice", help="identifiant de la notice du décret")
    sub.add_argument("--date", help="date du décret (AAAA-MM-JJ) : sert à signaler une année de naissance impossible")
    sub.add_argument("--psm", type=int, default=4, help="mode de découpage de page de Tesseract (défaut : 4, une colonne)")
    sub.add_argument("--langue", default="fra", help="modèle de langue de Tesseract (défaut : fra)")
    sub.add_argument("--sortie", default=str(BUILD / "lectures.json"), help="fichier écrit (défaut : data/build/an-images/lectures.json)")
    sub.set_defaults(run=command_read)

    sub = commands.add_parser("plan-collecte", help="taille d'une collecte des décrets en images seules (calcul, pas collecte)")
    sub.add_argument("--annees", metavar="A-B", help="ne compter que ces années (exemple : 1899-1912)")
    sub.add_argument("--classes", metavar="A1,A2…", help="ne compter que ces classes (parmi A1, A2, A3, R)")
    sub.add_argument("--ne-en", type=int, metavar="ANNEE",
                     help="année de naissance d'un ancêtre : ne compter que les décrets datés de ANNEE + 21 ou après")
    sub.add_argument("--pages-par-decret", type=int, default=6, help="HYPOTHÈSE : images par décret (défaut : 6, non mesuré)")
    sub.add_argument("--requetes-fixes", type=int, default=2, help="HYPOTHÈSE : requêtes hors images par décret (défaut : 2, non mesuré)")
    sub.add_argument("--delai", type=float, default=10.0, help="secondes entre deux requêtes (défaut : 10)")
    sub.add_argument("--heures-par-jour", type=float, default=6.0, help="heures de collecte par jour (défaut : 6)")
    sub.add_argument("--donnees", default=str(SITE_DATA / "an-decrets.json"), help="fichier des décrets du site")
    sub.add_argument("--tous-les-decrets", default=str(ROOT / "data" / "build" / "an-decrets.csv"), metavar="CSV",
                     help="liste à plat de TOUS les décrets (python3 -m decretas.an decrets --csv …) : sert à l'indice "
                          "tiré des identifiants de média ; facultatif")
    sub.add_argument("--sortie", default=str(BUILD), help="dossier où écrire plan-collecte.md, .json et la liste .csv")
    sub.set_defaults(run=command_collection_plan)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.run(args))
