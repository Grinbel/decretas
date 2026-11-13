"""Tests of ``python3 -m decretas`` (decretas/site.py): order of the build steps, stop on failure,
check of the site files, the verifiers, and the local server. No pipeline is really run: the steps
are replaced by a recorder, and the site is a temporary folder.
"""
from __future__ import annotations

import contextlib
import io
import subprocess
import sys
import tempfile
import threading
import unittest
import urllib.request
from pathlib import Path

from decretas import site as cli

ROOT = Path(__file__).resolve().parents[1]


def faux_site(racine: Path, *, sans: tuple[str, ...] = ()) -> Path:
    """A site folder with every file the pages need, except those in ``sans``."""
    for rel in (*cli.FICHIERS_PAGES, *cli.FICHIERS_CONTENU, *cli.FICHIERS_DONNEES):
        if rel in sans:
            continue
        chemin = racine / rel
        chemin.parent.mkdir(parents=True, exist_ok=True)
        chemin.write_text("<!doctype html><title>essai</title>" if rel.endswith(".html") else "{}", encoding="utf-8")
    return racine


class Enregistreur:
    def __init__(self, codes: dict[str, int] | None = None) -> None:
        self.appels: list[tuple[str, list[str]]] = []
        self.codes = codes or {}

    def __call__(self, module: str, argv: list[str]) -> int:
        self.appels.append((module, argv))
        return self.codes.get(module, 0)


class TestConstruire(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.lignes: list[str] = []

    def test_runs_both_builds_in_order_then_checks_the_files(self) -> None:
        site = faux_site(Path(self.tmp.name))
        lancer = Enregistreur()
        code = cli.main(["construire"], lancer=lancer, dire=self.lignes.append, site=site)
        self.assertEqual(code, 0)
        self.assertEqual(lancer.appels, [("decretas.an.cli", ["construire"]), ("decretas.bogga.__main__", ["construire"])])
        self.assertTrue(any("tous présents" in ligne for ligne in self.lignes), self.lignes)
        self.assertTrue(any("python3 -m decretas.an construire" in ligne for ligne in self.lignes), self.lignes)

    def test_export_only_is_passed_to_the_archives_nationales_step_only(self) -> None:
        site = faux_site(Path(self.tmp.name))
        lancer = Enregistreur()
        cli.main(["construire", "--export-seul"], lancer=lancer, dire=self.lignes.append, site=site)
        self.assertEqual(lancer.appels[0], ("decretas.an.cli", ["construire", "--export-seul"]))
        self.assertEqual(lancer.appels[1], ("decretas.bogga.__main__", ["construire"]))

    def test_a_failed_step_stops_the_build(self) -> None:
        site = faux_site(Path(self.tmp.name))
        lancer = Enregistreur({"decretas.an.cli": 3})
        code = cli.main(["construire"], lancer=lancer, dire=self.lignes.append, site=site)
        self.assertEqual(code, 3)
        self.assertEqual(len(lancer.appels), 1, "the Bulletin is not built after a failure")
        self.assertTrue(any("Échec" in ligne for ligne in self.lignes))

    def test_missing_files_are_listed_and_fail(self) -> None:
        site = faux_site(Path(self.tmp.name), sans=("data/an-personnes.json", "index.html"))
        code = cli.main(["construire"], lancer=Enregistreur(), dire=self.lignes.append, site=site)
        self.assertEqual(code, 1)
        texte = "\n".join(self.lignes)
        self.assertIn("data/an-personnes.json", texte)
        self.assertIn("index.html", texte)
        self.assertIn("python3 -m decretas construire", texte)

    def test_an_empty_file_counts_as_missing(self) -> None:
        site = faux_site(Path(self.tmp.name))
        (site / "data" / "bogga-meta.json").write_text("", encoding="utf-8")
        self.assertEqual(cli.fichiers_manquants(site), ["data/bogga-meta.json"])


class TestVerifier(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.lignes: list[str] = []

    def lancer(self, lancer: Enregistreur, tests_code: int = 0) -> int:
        args = cli.analyseur().parse_args(["verifier"])
        return cli.commande_verifier(args, lancer=lancer, dire=self.lignes.append, site=faux_site(Path(self.tmp.name)),
                                     tests=lambda dire: tests_code)

    def test_runs_both_verifiers_and_the_content_tests(self) -> None:
        lancer = Enregistreur()
        self.assertEqual(self.lancer(lancer), 0)
        self.assertEqual(lancer.appels, [("decretas.an.cli", ["verifier"]), ("decretas.bogga.__main__", ["verifier"])])
        self.assertIn("Vérification : tout est conforme.", self.lignes)

    def test_sans_base_skips_only_the_archives_nationales_verifier(self) -> None:
        lancer = Enregistreur()
        args = cli.analyseur().parse_args(["verifier", "--sans-base"])
        code = cli.commande_verifier(args, lancer=lancer, dire=self.lignes.append, site=faux_site(Path(self.tmp.name)),
                                     tests=lambda dire: 0)
        self.assertEqual(code, 0)
        self.assertEqual(lancer.appels, [("decretas.bogga.__main__", ["verifier"])])
        self.assertTrue(any("--sans-base" in ligne for ligne in self.lignes), self.lignes)
        self.assertIn("== Vie privée et clause Filae (site/data/)", self.lignes)

    def test_every_part_is_run_even_after_a_failure_and_the_failures_are_named(self) -> None:
        lancer = Enregistreur({"decretas.an.cli": 1})
        self.assertEqual(self.lancer(lancer, tests_code=1), 1)
        self.assertEqual(len(lancer.appels), 2)
        self.assertTrue(any("Archives nationales" in ligne and "contenu de guidage" in ligne for ligne in self.lignes), self.lignes)


class TestServir(unittest.TestCase):
    def test_serves_the_site_on_the_loopback_address_with_safe_headers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            site = faux_site(Path(tmp))
            serveur = cli.creer_serveur(0, site)
            self.addCleanup(serveur.server_close)
            self.assertEqual(serveur.server_address[0], "127.0.0.1")
            fil = threading.Thread(target=serveur.serve_forever, daemon=True)
            fil.start()
            self.addCleanup(serveur.shutdown)
            port = serveur.server_address[1]
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/index.html", timeout=5) as reponse:
                self.assertEqual(reponse.status, 200)
                self.assertIn(b"essai", reponse.read())
                self.assertEqual(reponse.headers["X-Content-Type-Options"], "nosniff")
                self.assertEqual(reponse.headers["Referrer-Policy"], "no-referrer")
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/js/app.js", timeout=5) as reponse:
                self.assertEqual(reponse.headers.get_content_type(), "text/javascript")

    def test_a_port_out_of_range_is_refused_in_french(self) -> None:
        resultat = subprocess.run([sys.executable, "-m", "decretas", "servir", "--port", "70000"], cwd=ROOT,
                                  capture_output=True, text=True, timeout=30)
        self.assertEqual(resultat.returncode, 2)
        self.assertIn("port hors limites", resultat.stderr)

    def test_help_is_in_french(self) -> None:
        resultat = subprocess.run([sys.executable, "-m", "decretas", "--aide"], cwd=ROOT, capture_output=True, text=True, timeout=30)
        self.assertEqual(resultat.returncode, 0)
        for mot in ("construire", "servir", "verifier", "options"):
            self.assertIn(mot, resultat.stdout)


class TestLanceur(unittest.TestCase):
    def test_a_system_exit_becomes_an_exit_code(self) -> None:
        # argparse of a pipeline stops with SystemExit(2) on a bad option: it must not end this program
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(cli.lancer_module("decretas.bogga.__main__", ["--option-inconnue"]), 2)


if __name__ == "__main__":
    unittest.main()


class ViePriveeTest(unittest.TestCase):
    """Regression (review of 2026-11-12): a private export written into site/data passed « verifier »."""

    @staticmethod
    def donnees(racine: Path, *, active: bool = True, noms_filae: bool = False, an: int | None = 1850,
                inv_filae: bool = False) -> Path:
        import json
        site = racine / "site"
        (site / "data").mkdir(parents=True)
        meta = {
            "vie_privee": {"active": active, "annee_seuil": 1926},
            "filae": {"noms_inclus": noms_filae},
            "inventaires": {"champs": ["inv", "annee", "filae"], "lignes": [["FRAN_IR_000001", 1885, False], ["FRAN_IR_000009", 1905, True]]},
        }
        decrets = {"champs": ["id", "inv", "annee"], "tables": {"inv": ["FRAN_IR_000001", "FRAN_IR_000009"]},
                   "lignes": [[0, 1 if inv_filae else 0, 1905 if inv_filae else 1885]]}
        personnes = {"champs": ["id", "dec", "an", "prec"], "tables": {"prec": ["", "suspecte"]}, "lignes": [[0, 0, an, 0]]}
        for nom, contenu in (("an-meta", meta), ("an-decrets", decrets), ("an-personnes", personnes)):
            (site / "data" / f"{nom}.json").write_text(json.dumps(contenu), encoding="utf-8")
        return site

    def test_a_published_export_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(cli.problemes_vie_privee(self.donnees(Path(tmp))), [])

    def test_each_breach_is_named(self) -> None:
        cas = {
            "règle « vie privée » n'était pas active": {"active": False},
            "années Filae sont inclus": {"noms_filae": True},
            "clause Filae": {"inv_filae": True},
            "pourraient être encore en vie": {"an": 1930},
        }
        for attendu, options in cas.items():
            with self.subTest(attendu), tempfile.TemporaryDirectory() as tmp:
                problemes = cli.problemes_vie_privee(self.donnees(Path(tmp), **options))
                self.assertTrue(any(attendu in p for p in problemes), problemes)

    def test_unknown_birth_under_a_recent_decree_is_a_breach(self) -> None:
        import json
        with tempfile.TemporaryDirectory() as tmp:
            site = self.donnees(Path(tmp), an=None)
            chemin = site / "data" / "an-decrets.json"
            decrets = json.loads(chemin.read_text(encoding="utf-8"))
            decrets["lignes"][0][2] = 1931
            chemin.write_text(json.dumps(decrets), encoding="utf-8")
            self.assertTrue(cli.problemes_vie_privee(site))


class ExportPriveTest(unittest.TestCase):
    """Regression (review of 2026-11-12): --inclure-vivants-possibles wrote into site/data by default."""

    def test_a_private_export_is_refused_inside_the_site(self) -> None:
        from decretas.an import cli as an_cli
        for option in ("--inclure-vivants-possibles", "--inclure-filae"):
            for sortie in ([], ["--sortie", str(ROOT / "site" / "data")], ["--sortie", str(ROOT / "site" / "autre")]):
                with self.subTest(option=option, sortie=sortie):
                    erreurs = io.StringIO()
                    with contextlib.redirect_stderr(erreurs), contextlib.redirect_stdout(io.StringIO()):
                        code = an_cli.main(["construire", "--export-seul", "--base", "/nonexistent/an.sqlite", option, *sortie])
                    self.assertEqual(code, 2)
                    self.assertIn("export privé", erreurs.getvalue())
