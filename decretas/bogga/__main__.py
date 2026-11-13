"""Command line of the BOGGA pipeline. Messages and options are in French.

    python3 -m decretas.bogga telecharger [--simulation] [--annees 1873,1888]
    python3 -m decretas.bogga construire  [--annees ...]
    python3 -m decretas.bogga verifier
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from decretas import net
from decretas.bogga import catalogue, moisson

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw" / "ia"
SITE_DATA = ROOT / "site" / "data"
BUILD = ROOT / "data" / "build" / "bogga"
EARLIER_LOG = ROOT / "data" / "samples" / "internet-archive" / "requests.jsonl"


def parse_years(text: str | None) -> list[catalogue.Volume]:
    """Volumes selected by '--annees 1873,1888' (all when absent)."""
    if not text:
        return list(catalogue.VOLUMES)
    chosen = []
    for token in text.split(","):
        token = token.strip()
        if not token.isdigit():
            raise SystemExit(f"année invalide : {token!r}")
        volume = catalogue.volume_for(int(token))
        if volume is None:
            raise SystemExit(f"aucun volume lisible par programme pour {token} "
                             f"(années disponibles : {', '.join(str(v.year) for v in catalogue.VOLUMES)})")
        chosen.append(volume)
    return chosen


def cmd_telecharger(args: argparse.Namespace) -> int:
    client = net.PoliteClient(
        root=RAW, policies=moisson.ia_policy(delay=args.delai, budget=args.plafond),
        dry_run=args.simulation, resume_after_stop=args.reprendre_apres_refus,
        retry_failed=args.reessayer_echecs,
    )
    report = moisson.harvest(client, parse_years(args.annees), earlier_log=EARLIER_LOG, earlier_base=ROOT)
    used = client.requests_used(moisson.IA_FAMILY)
    print(f"\nreçus : {len(report.fetched)}   déjà en cache : {len(report.cached)}   "
          f"à demander (simulation) : {len(report.planned)}")
    print(f"requêtes comptées pour archive.org : {used} sur {args.plafond}")
    for line in report.skipped:
        print(f"non fait : {line}")
    if report.stopped:
        print(f"ARRÊT : {report.stopped}", file=sys.stderr)
        return 3
    return 1 if report.skipped and not args.simulation else 0


def cmd_construire(args: argparse.Namespace) -> int:
    from decretas.bogga import export  # imported late: the harvest must work without it

    return export.build(RAW, SITE_DATA, BUILD, parse_years(args.annees), say=print)


def cmd_verifier(args: argparse.Namespace) -> int:
    from decretas.bogga import verification

    if args.liens:
        years = [volume.year for volume in parse_years(args.liens)]
        if len(years) > 3:
            raise SystemExit("--liens : trois années au plus (une requête par année)")
        client = net.PoliteClient(root=RAW, policies=moisson.ia_policy(budget=args.plafond), dry_run=args.simulation)
        return verification.check_links(RAW, BUILD, client, years, say=print)
    return verification.run(RAW, SITE_DATA, say=print)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python3 -m decretas.bogga",
        description="Bulletin officiel du Gouvernement général de l'Algérie 1861-1888 (Internet Archive) : "
                    "téléchargement du texte, découpage en décrets et en personnes, export pour le site.")
    sub = parser.add_subparsers(dest="commande", required=True)

    tel = sub.add_parser("telecharger", help="télécharger les trois petits fichiers de texte de chaque volume")
    tel.add_argument("--simulation", action="store_true", help="n'envoie rien : affiche ce qui serait demandé")
    tel.add_argument("--annees", help="années séparées par des virgules (défaut : toutes)")
    tel.add_argument("--delai", type=float, default=5.5, help="secondes entre deux requêtes (minimum 5 ; défaut 5,5)")
    tel.add_argument("--plafond", type=int, default=150,
                     help="nombre maximal de requêtes vers archive.org, tous passages confondus (défaut 150)")
    tel.add_argument("--reprendre-apres-refus", action="store_true",
                     help="décision humaine : un refus antérieur (403/429) est levé, on peut redemander")
    tel.add_argument("--reessayer-echecs", action="store_true",
                     help="redemander les adresses restées sans réponse ou en erreur 5xx lors d'un passage précédent")
    tel.set_defaults(run=cmd_telecharger)

    con = sub.add_parser("construire", help="découper les volumes téléchargés et écrire site/data/bogga-*.json")
    con.add_argument("--annees", help="années séparées par des virgules (défaut : toutes)")
    con.set_defaults(run=cmd_construire)

    ver = sub.add_parser("verifier", help="contrôler les fichiers produits (cohérence, notices témoins, liens)")
    ver.add_argument("--liens", metavar="ANNEES",
                     help="demander à Internet Archive la table des pages de sa liseuse pour ces années "
                          "(trois au plus, une requête chacune) et la comparer à notre index")
    ver.add_argument("--simulation", action="store_true", help="avec --liens : n'envoie rien, affiche l'adresse")
    ver.add_argument("--plafond", type=int, default=150, help="avec --liens : plafond de requêtes vers archive.org")
    ver.set_defaults(run=cmd_verifier)

    args = parser.parse_args(argv)
    return args.run(args)


if __name__ == "__main__":
    sys.exit(main())
