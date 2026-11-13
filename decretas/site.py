"""The static site as a whole: build the data of both sources, check the files, serve the site locally.

    python3 -m decretas construire [--export-seul]
    python3 -m decretas servir [--port N]
    python3 -m decretas verifier

Messages are in French, like the rest of the project's tooling. Standard library only.

``construire`` runs, in order, the build step of the Archives nationales pipeline
(``python3 -m decretas.an construire``) and of the printed Bulletin pipeline
(``python3 -m decretas.bogga construire``), then checks that every file the pages need is present
in ``site/``. ``verifier`` runs both verifiers and the tests of the guidance content.
``servir`` serves ``site/`` on 127.0.0.1 only, for local use: it is not a production server.
"""
from __future__ import annotations

import argparse
import functools
import importlib
import io
import sys
import unittest
from collections.abc import Callable, Sequence
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"

#: The files every page of the site needs, relative to site/.
FICHIERS_PAGES = (
    "index.html",
    "js/app.js",
    "js/demarrage.js",
    "js/donnees/worker.js",
    "css/base.css",
    "css/composants.css",
    "css/vues.css",
    "css/impression.css",
    "assets/favicon.svg",
)
#: The guidance content (site/contenu/), written by hand and kept in git.
FICHIERS_CONTENU = tuple(f"contenu/{nom}.json" for nom in
                         ("a-propos", "aiguillage", "bilan", "guides", "liens", "types-d-actes", "vocabulaire"))
#: The generated data (site/data/), rebuilt by ``construire`` and never kept in git.
FICHIERS_DONNEES = tuple(f"data/{nom}.json" for nom in
                         ("an-meta", "an-decrets", "an-personnes",
                          "bogga-meta", "bogga-volumes", "bogga-decrets", "bogga-entrees"))

#: (what, module, arguments) — the build steps, in order.
ETAPES_CONSTRUIRE = (
    ("Archives nationales", "decretas.an.cli", ["construire"]),
    ("Bulletin officiel imprimé", "decretas.bogga.__main__", ["construire"]),
)
#: (what, module, arguments) — the verifiers.
ETAPES_VERIFIER = (
    ("Archives nationales", "decretas.an.cli", ["verifier"]),
    ("Bulletin officiel imprimé", "decretas.bogga.__main__", ["verifier"]),
)

Lanceur = Callable[[str, list[str]], int]
Dire = Callable[[str], None]


def lancer_module(module: str, argv: list[str]) -> int:
    """Run ``main(argv)`` of a pipeline module, as ``python3 -m`` would, and return its exit code."""
    try:
        code = importlib.import_module(module).main(argv)
    except SystemExit as stop:  # argparse and the pipelines may stop this way
        code = stop.code if isinstance(stop.code, int) else (0 if stop.code is None else 1)
    return int(code or 0)


def fichiers_manquants(site: Path = SITE) -> list[str]:
    """The files the site needs that are absent (or empty), relative to ``site``."""
    return [rel for rel in (*FICHIERS_PAGES, *FICHIERS_CONTENU, *FICHIERS_DONNEES)
            if not (site / rel).is_file() or (site / rel).stat().st_size == 0]


def _octets(n: int) -> str:
    return f"{n:,}".replace(",", " ")


def _rapport_fichiers(site: Path, dire: Dire) -> int:
    manquants = fichiers_manquants(site)
    if manquants:
        dire(f"Fichiers absents ou vides dans {site} :")
        for rel in manquants:
            dire(f"  {rel}")
        if any(rel.startswith("data/") for rel in manquants):
            dire("Les fichiers de data/ se fabriquent avec : python3 -m decretas construire")
        return 1
    total = sum((site / rel).stat().st_size for rel in FICHIERS_DONNEES)
    dire(f"Fichiers du site : tous présents ({len(FICHIERS_PAGES) + len(FICHIERS_CONTENU) + len(FICHIERS_DONNEES)}), "
         f"dont {_octets(total)} octets de données (à servir compressées).")
    return 0


def commande_construire(args: argparse.Namespace, *, lancer: Lanceur, dire: Dire, site: Path) -> int:
    for quoi, module, argv in ETAPES_CONSTRUIRE:
        argv = list(argv)
        if args.export_seul and module == "decretas.an.cli":
            argv.append("--export-seul")
        dire(f"== {quoi} : python3 -m {module.removesuffix('.cli').removesuffix('.__main__')} {' '.join(argv)}")
        code = lancer(module, argv)
        if code != 0:
            dire(f"Échec de l'étape « {quoi} » (code {code}) : la construction s'arrête là.")
            return code
    dire("== Contrôle des fichiers du site")
    return _rapport_fichiers(site, dire)


def _tests_du_contenu(dire: Dire) -> int:
    """Run tests/contenu with the standard runner; return 0 when they all pass."""
    chargeur = unittest.TestLoader()
    suite = chargeur.discover(str(ROOT / "tests" / "contenu"), top_level_dir=str(ROOT))
    flux = io.StringIO()
    resultat = unittest.TextTestRunner(stream=flux, verbosity=0).run(suite)
    if resultat.wasSuccessful():
        dire(f"Tests du contenu de guidage : {resultat.testsRun} réussis.")
        return 0
    dire(f"Tests du contenu de guidage : {len(resultat.failures)} échec(s), {len(resultat.errors)} erreur(s) "
         f"sur {resultat.testsRun}.")
    dire(flux.getvalue())
    return 1


def _valeur(fichier: dict, ligne: list, champ: str):
    """Value of a field of a columnar file (an index into ``tables[champ]`` when there is one)."""
    i = fichier["champs"].index(champ)
    v = ligne[i] if i < len(ligne) else None
    table = (fichier.get("tables") or {}).get(champ)
    return table[v] if isinstance(table, list) and isinstance(v, int) and 0 <= v < len(table) else v


def problemes_vie_privee(site: Path) -> list[str]:
    """What, in the published Archives nationales files, breaks the two publication rules.

    The private exports of ``python3 -m decretas.an construire`` (``--inclure-filae``,
    ``--inclure-vivants-possibles``) must never be served: this reads the files as they are in
    ``site/data`` and lists every breach — a meta file that says the rules were off, a name under
    a decree of a Filae inventory, a name of a person who may be alive (the rule of
    ``decretas.an.export.privacy_reason``). Returns [] when everything is in order.
    """
    import json

    from decretas.an.export import privacy_reason

    donnees = site / "data"
    try:
        meta = json.loads((donnees / "an-meta.json").read_text(encoding="utf-8"))
        decrets = json.loads((donnees / "an-decrets.json").read_text(encoding="utf-8"))
        personnes = json.loads((donnees / "an-personnes.json").read_text(encoding="utf-8"))
    except FileNotFoundError:
        return []  # missing files are reported by _rapport_fichiers
    except (OSError, ValueError) as erreur:
        return [f"fichiers de l'index illisibles : {erreur}"]
    if not meta and not personnes.get("lignes"):
        return []  # an empty placeholder, not an export: nothing to check
    if not isinstance(personnes.get("lignes"), list) or not isinstance(decrets.get("lignes"), list):
        return ["an-personnes.json ou an-decrets.json : forme inattendue (pas de « lignes »)"]
    out = []
    vie = meta.get("vie_privee") or {}
    if vie.get("active") is not True:
        out.append("an-meta.json : la règle « vie privée » n'était pas active (export --inclure-vivants-possibles)")
    if (meta.get("filae") or {}).get("noms_inclus") is not False:
        out.append("an-meta.json : les noms des années Filae sont inclus (export --inclure-filae)")
    seuil = vie.get("annee_seuil")
    inventaires = meta.get("inventaires") or {"champs": [], "lignes": []}
    filae = {_valeur(inventaires, l, "inv") for l in inventaires["lignes"] if _valeur(inventaires, l, "filae") is True}
    sous_filae = 0
    vivants = 0
    for ligne in personnes["lignes"]:
        decret = decrets["lignes"][_valeur(personnes, ligne, "dec")]
        if _valeur(decrets, decret, "inv") in filae:
            sous_filae += 1
        if isinstance(seuil, int):
            annee = _valeur(personnes, ligne, "an")
            suspecte = _valeur(personnes, ligne, "prec") == "suspecte"
            if privacy_reason(annee if isinstance(annee, int) else None, suspecte, _valeur(decrets, decret, "annee"), seuil):
                vivants += 1
    if sous_filae:
        out.append(f"an-personnes.json : {sous_filae} nom(s) sous des décrets d'inventaires couverts par la clause Filae")
    if vivants:
        out.append(f"an-personnes.json : {vivants} nom(s) de personnes qui pourraient être encore en vie (seuil {seuil})")
    if not isinstance(seuil, int):
        out.append("an-meta.json : l'année seuil de la règle « vie privée » manque")
    return out


def commande_verifier(args: argparse.Namespace, *, lancer: Lanceur, dire: Dire, site: Path,
                      tests: Callable[[Dire], int] = _tests_du_contenu) -> int:
    echecs = []
    for quoi, module, argv in ETAPES_VERIFIER:
        if getattr(args, "sans_base", False) and module == "decretas.an.cli":
            # the Archives nationales verifier reads data/build/an.sqlite, built from the raw files that
            # never leave this machine: a clean checkout (GitHub Actions) cannot run it
            dire(f"== {quoi} : non lancé (--sans-base : la base locale data/build/an.sqlite n'est pas là)")
            continue
        dire(f"== {quoi} : python3 -m {module.removesuffix('.cli').removesuffix('.__main__')} {' '.join(argv)}")
        if lancer(module, list(argv)) != 0:
            echecs.append(quoi)
    dire("== Contenu de guidage (site/contenu/)")
    if tests(dire) != 0:
        echecs.append("contenu de guidage")
    dire("== Fichiers du site")
    if _rapport_fichiers(site, dire) != 0:
        echecs.append("fichiers du site")
    dire("== Vie privée et clause Filae (site/data/)")
    problemes = problemes_vie_privee(site)
    for probleme in problemes:
        dire(f"  NON PUBLIABLE — {probleme}")
    if problemes:
        echecs.append("vie privée")
    else:
        dire("  Aucun nom d'une année Filae, aucun nom d'une personne qui pourrait être en vie.")
    if echecs:
        dire(f"Vérification : {len(echecs)} partie(s) en échec — {', '.join(echecs)}.")
        return 1
    dire("Vérification : tout est conforme.")
    return 0


class _Gestionnaire(SimpleHTTPRequestHandler):
    """Static files of site/, with the headers a meta tag cannot set, and quiet logs."""

    extensions_map = {**SimpleHTTPRequestHandler.extensions_map,
                      ".js": "text/javascript", ".mjs": "text/javascript", ".json": "application/json",
                      ".svg": "image/svg+xml", ".css": "text/css"}

    def end_headers(self) -> None:
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "frame-ancestors 'none'")
        self.send_header("Cache-Control", "no-cache")
        super().end_headers()

    def log_message(self, format: str, *args) -> None:  # noqa: A002 (the base class names it so)
        pass


def creer_serveur(port: int, site: Path = SITE, adresse: str = "127.0.0.1") -> ThreadingHTTPServer:
    """A server of ``site`` on the loopback address only. ``port`` 0 picks a free port."""
    gestionnaire = functools.partial(_Gestionnaire, directory=str(site))
    return ThreadingHTTPServer((adresse, port), gestionnaire)


def commande_servir(args: argparse.Namespace, *, dire: Dire, site: Path) -> int:
    manquants = fichiers_manquants(site)
    if manquants:
        dire(f"Attention : {len(manquants)} fichier(s) manquant(s) dans {site} ({', '.join(manquants[:3])}"
             f"{' …' if len(manquants) > 3 else ''}). Le site s'ouvrira, mais la recherche ne marchera pas "
             "sans les fichiers de data/ : python3 -m decretas construire")
    try:
        serveur = creer_serveur(args.port, site)
    except OSError as erreur:
        dire(f"Impossible d'écouter sur 127.0.0.1:{args.port} ({erreur.strerror or erreur}). "
             "Choisissez un autre port avec --port.")
        return 1
    port = serveur.server_address[1]
    dire(f"Site servi sur http://127.0.0.1:{port}/ (cette machine seulement). Arrêt : Ctrl+C.")
    dire("Ce serveur ne compresse pas les fichiers : il sert à essayer le site, pas à le publier.")
    try:
        serveur.serve_forever()
    except KeyboardInterrupt:
        dire("Serveur arrêté.")
    finally:
        serveur.server_close()
    return 0


class _Analyseur(argparse.ArgumentParser):
    def __init__(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        kwargs.setdefault("add_help", False)
        super().__init__(*args, **kwargs)
        self._positionals.title = "commandes"
        self._optionals.title = "options"
        self.add_argument("-h", "--aide", action="help", help="afficher cette aide et quitter")

    def error(self, message: str):  # type: ignore[no-untyped-def]
        self.print_usage(sys.stderr)
        self.exit(2, f"{self.prog} : erreur : {message}\n")


def _port(texte: str) -> int:
    try:
        n = int(texte)
    except ValueError:
        raise argparse.ArgumentTypeError(f"port invalide : {texte!r}") from None
    if not 0 <= n <= 65535:
        raise argparse.ArgumentTypeError(f"port hors limites (0 à 65535) : {n}")
    return n


def analyseur() -> argparse.ArgumentParser:
    p = _Analyseur(prog="python3 -m decretas",
                   description="Le site statique : construire les données, les vérifier, servir le site sur cette machine.")
    sub = p.add_subparsers(dest="commande", required=True, metavar="commande", parser_class=_Analyseur)
    c = sub.add_parser("construire", help="construire les données des deux sources, puis contrôler les fichiers du site")
    c.add_argument("--export-seul", action="store_true",
                   help="Archives nationales : refaire seulement les fichiers du site depuis la base, sans relire les XML")
    s = sub.add_parser("servir", help="servir site/ sur 127.0.0.1, pour un usage local")
    s.add_argument("--port", type=_port, default=8765, metavar="N", help="port d'écoute (défaut : 8765 ; 0 : un port libre)")
    v = sub.add_parser("verifier", help="lancer les deux vérificateurs et les tests du contenu de guidage")
    v.add_argument("--sans-base", action="store_true",
                   help="ne pas lancer le vérificateur des Archives nationales, qui lit la base locale "
                        "data/build/an.sqlite (pour une copie propre du dépôt, comme GitHub Actions) ; "
                        "le contrôle vie privée et clause Filae de site/data/ est toujours fait")
    return p


def main(argv: Sequence[str] | None = None, *, lancer: Lanceur = lancer_module, dire: Dire | None = None,
         site: Path = SITE) -> int:
    dire = dire or (lambda texte: print(texte, flush=True))
    args = analyseur().parse_args(argv)
    if args.commande == "construire":
        return commande_construire(args, lancer=lancer, dire=dire, site=site)
    if args.commande == "verifier":
        return commande_verifier(args, lancer=lancer, dire=dire, site=site)
    return commande_servir(args, dire=dire, site=site)
