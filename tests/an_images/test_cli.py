"""The command line, end to end: every sub-command, its messages and its exit codes.

The network tests talk to the local fictitious site only. A guard makes any attempt to
reach another host fail the test instead of sending a request.
"""
from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from decretas.an_images import cli, client, lecteurs, reprise

from . import fabrique
from .serveur import Answer, Site
from .test_collecte import decree_file, rows

SECRET = "noeud9~FEDCBA9876543210SECRET"
MEDIA = ["LOT_000201_L", "LOT_000202_L", "LOT_000203_L"]
REAL_HTTP_GET = client.SessionClient._http_get


def local_only(self, url, part, policy):
    """Refuse to send anything that is not for the local test server."""
    if not url.startswith("http://127.0.0.1:"):
        raise AssertionError(f"un essai a voulu joindre un hôte réel : {url}")
    return REAL_HTTP_GET(self, url, part, policy)


class CliCase(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.base = Path(self.directory.name)
        guard = mock.patch.object(client.SessionClient, "_http_get", local_only)
        guard.start()
        self.addCleanup(guard.stop)
        # the host-wide stop file of the test, never the real data/raw/an-images/arret.json
        self.stop_file = self.base / "arret.json"
        stop = mock.patch.object(cli, "HOST_STOP", self.stop_file)
        stop.start()
        self.addCleanup(stop.stop)

    def run_cli(self, *arguments: str) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                code = cli.main([str(argument) for argument in arguments])
            except SystemExit as stop:                    # argparse refuses the command line
                code = int(stop.code or 0)
        return code, out.getvalue(), err.getvalue()


class AvailabilityTest(CliCase):
    def setUp(self) -> None:
        super().setUp()
        self.site = Site()
        self.addCleanup(self.site.close)
        self.root = self.base / "disponibilite"

    def check(self, *extra: str) -> tuple[int, str, str]:
        return self.run_cli("disponibilite", "--base", self.site.base, "--racine", self.root, *extra)

    def test_dry_run_sends_nothing(self) -> None:
        code, out, _err = self.check("--simulation")
        self.assertEqual(code, 0)
        self.assertIn("une seule requête serait envoyée", out)
        self.assertEqual(self.site.requests, [])
        self.assertFalse(self.root.exists())

    def test_redirect_means_the_site_answers_and_the_session_is_not_printed(self) -> None:
        self.site.redirect(cli.AVAILABILITY_PATH, f"/siv/consultation.action;jsessionid={SECRET}?irId=FRAN_IR_057268",
                           cookies=(f"JSESSIONID={SECRET}; Path=/siv/",))
        code, out, _err = self.check()
        self.assertEqual(code, 0)
        self.assertIn("HTTP 302", out)
        self.assertIn("le site RÉPOND", out)
        self.assertNotIn(SECRET, out)
        self.assertEqual(self.site.paths(), [cli.AVAILABILITY_PATH])          # one request, the redirect is not followed
        self.assertNotIn(SECRET, (self.root / "manifest.jsonl").read_text(encoding="utf-8"))

    def test_503_says_still_down_and_keeps_the_error_page(self) -> None:
        self.site.routes[cli.AVAILABILITY_PATH] = Answer(503, b"<html><title>SIA - Erreur</title></html>", {"Content-Type": "text/html"})
        code, out, _err = self.check()
        self.assertEqual(code, reprise.EXIT_PAUSED)
        self.assertIn("HTTP 503", out)
        self.assertIn("toujours en panne", out)
        self.assertEqual(len(self.site.requests), 1)                           # no retry
        self.assertTrue((self.root / "derniere-reponse.corps.http503").exists())

    def test_403_is_a_refusal(self) -> None:
        self.site.routes[cli.AVAILABILITY_PATH] = Answer(403, b"<html>interdit</html>", {"Content-Type": "text/html"})
        code, out, _err = self.check()
        self.assertEqual(code, reprise.EXIT_BLOCKED)
        self.assertIn("REFUS", out)

    def test_unexpected_status_is_not_called_a_success(self) -> None:
        code, out, _err = self.check()                                         # the local site answers 404
        self.assertEqual(code, reprise.EXIT_ERROR)
        self.assertIn("réponse inattendue", out)

    def test_daily_cap(self) -> None:
        self.site.redirect(cli.AVAILABILITY_PATH, "/siv/ailleurs")
        self.assertEqual(self.check("--max-par-jour", "2")[0], 0)
        self.assertEqual(self.check("--max-par-jour", "2")[0], 0)              # an availability check is always sent again
        code, out, _err = self.check("--max-par-jour", "2")
        self.assertEqual(code, reprise.EXIT_CAP)
        self.assertIn("rien n'est envoyé", out)
        self.assertEqual(len(self.site.requests), 2)


class ProbeCommandTest(CliCase):
    def setUp(self) -> None:
        super().setUp()
        self.site = Site()
        self.addCleanup(self.site.close)
        self.root = self.base / "reprise"
        self.report = self.base / "rapport.md"
        self.data = self.base / "donnees-absentes"

    def probe(self, *extra: str) -> tuple[int, str, str]:
        return self.run_cli("reprise", "--base", self.site.base, "--racine", self.root, "--rapport", self.report,
                            "--donnees", self.data, "--delai", "0", "--delai-reponse", "5", *extra)

    def decree_1928(self) -> None:
        landing = "/siv/consultation.action?irId=FRAN_IR_057672&udId=YI004589"
        self.site.redirect("/siv/media/FRAN_IR_057672/YI004589/",
                           f"/siv/consultation.action;jsessionid={SECRET}?irId=FRAN_IR_057672&udId=YI004589",
                           cookies=(f"JSESSIONID={SECRET}; Path=/siv/; HttpOnly",))
        self.site.html(landing, fabrique.landing_html(MEDIA))
        for rank, name in enumerate(MEDIA):
            for suffix in ("", "-medium", "-min"):
                self.site.image(f"/mm/media/download/{name}{suffix}.jpg", fabrique.jpeg_bytes(8 + rank, 8))

    def test_dry_run_prints_the_plan_and_touches_nothing(self) -> None:
        code, out, _err = self.probe("--simulation")
        self.assertEqual(code, 0)
        self.assertIn("simulation : rien n'est envoyé, rien n'est écrit", out)
        self.assertIn("/siv/media/FRAN_IR_056731/idd_1889_12_22/DAFANCH94_NUMJ011088_D", out)
        self.assertLess(out.index("DAFANCH94_NUMJ011088_D"), out.index("/siv/media/FRAN_IR_057220/AP001236/"))   # the four lots first
        self.assertIn("NON PLANIFIÉ", out)                                      # person exemplars: site data absent here
        self.assertIn("aucune pause ni arrêt en cours", out)
        self.assertEqual(self.site.requests, [])
        self.assertFalse(self.root.exists())
        self.assertFalse(self.report.exists())

    def test_one_case_run_writes_bodies_manifest_images_and_report(self) -> None:
        self.decree_1928()
        code, out, _err = self.probe("--cas", "image-1928", "--palier", "1")
        self.assertEqual(code, reprise.EXIT_DONE)
        self.assertEqual(self.site.paths(), ["/siv/media/FRAN_IR_057672/YI004589/",
                                             "/siv/consultation.action?irId=FRAN_IR_057672&udId=YI004589",
                                             "/mm/media/download/LOT_000201_L.jpg", "/mm/media/download/LOT_000202_L.jpg"])
        self.assertIn("Rapport écrit", out)
        self.assertNotIn(SECRET, out)
        text = self.report.read_text(encoding="utf-8")
        self.assertIn("## 1. Chaînes de redirection", text)
        self.assertIn("302", text)
        self.assertIn("LOT_000201_L", text)
        self.assertIn("le nom donne l'ordre des vues", text)
        self.assertNotIn(SECRET, text)
        images = sorted(path.name for path in (self.root / "images" / "image-1928").iterdir())
        self.assertEqual(images, ["LOT_000201_L.jpg", "LOT_000202_L.jpg", "decret.json"])
        sidecar = json.loads((self.root / "images" / "image-1928" / "decret.json").read_text(encoding="utf-8"))
        self.assertEqual(sidecar["images"]["LOT_000202_L.jpg"]["notice"], "YI004589")
        self.assertEqual(sidecar["images"]["LOT_000202_L.jpg"]["vue"], 2)

    def test_503_pauses_and_the_next_call_sends_nothing(self) -> None:
        self.site.routes["/siv/media/FRAN_IR_057672/YI004589/"] = Answer(503, b"<html><title>SIA - Erreur</title></html>",
                                                                        {"Content-Type": "text/html"})
        code, out, _err = self.probe("--cas", "image-1928", "--palier", "1")
        self.assertEqual(code, reprise.EXIT_PAUSED)
        self.assertIn("HTTP 503", out)
        self.assertIn("arrêt de 30 minutes", out)
        state = json.loads((self.root / "etat.json").read_text(encoding="utf-8"))
        self.assertIsNotNone(state["pause_jusqu_a"])
        self.assertIn("interrompue par un échec", self.report.read_text(encoding="utf-8"))
        code, out, _err = self.probe("--cas", "image-1928", "--palier", "1")
        self.assertEqual(code, reprise.EXIT_PAUSED)
        self.assertIn("Pause en cours", out)
        self.assertEqual(len(self.site.requests), 1)

    def test_report_alone_is_rewritten_from_disk(self) -> None:
        code, out, _err = self.probe("--rapport-seul")
        self.assertEqual(code, 0)
        self.assertEqual(self.site.requests, [])
        self.assertIn("Non observé", self.report.read_text(encoding="utf-8"))

    def test_bad_options_are_refused_before_any_request(self) -> None:
        self.assertEqual(self.probe("--cas", "cas-inconnu")[0], 2)
        self.assertEqual(self.probe("--suivre", "sans-signe-egal")[0], 2)
        self.assertEqual(self.probe("--suivre", "cas-inconnu=/siv/x")[0], 2)
        self.assertEqual(self.site.requests, [])


class RealHostGuardsTest(CliCase):
    """Limits that hold on the real host whatever the options say. Nothing is sent (see `local_only`)."""

    def test_delay_below_six_seconds_is_refused(self) -> None:
        code, _out, err = self.run_cli("reprise", "--racine", self.base / "r", "--rapport", self.base / "r.md", "--delai", "2")
        self.assertEqual(code, 2)
        self.assertIn("minimum sur cet hôte est 6 s", err)
        self.assertFalse((self.base / "r").exists())

    def test_caps_are_brought_back_to_the_host_maximum(self) -> None:
        code, out, _err = self.run_cli("reprise", "--simulation", "--racine", self.base / "r", "--rapport", self.base / "r.md",
                                       "--donnees", self.base / "absent", "--plafond", "500", "--plafond-jour", "5000")
        self.assertEqual(code, 0)
        self.assertIn("40 requêtes par passage, 80 par jour", out)
        self.assertFalse((self.base / "r").exists())


class MetadataCommandTest(CliCase):
    def setUp(self) -> None:
        super().setUp()
        self.folder = self.base / "images"
        self.folder.mkdir()
        (self.folder / "LOT_000101_L.jpg").write_bytes(fabrique.jpeg_bytes(8, 8, comments=("légende fictive",)))
        (self.folder / "LOT_000102_L.jpg").write_bytes(fabrique.jpeg_bytes(8, 8))
        (self.folder / "page.png").write_bytes(fabrique.png_bytes(text={"Title": "titre fictif"}))
        (self.folder / "notes.txt").write_text("pas une image", encoding="utf-8")

    def test_folder_as_french_table_and_json_file(self) -> None:
        destination = self.base / "sortie" / "meta.json"
        code, out, _err = self.run_cli("metadonnees", self.folder, "--json", destination)
        self.assertEqual(code, 0)
        self.assertIn("Récapitulatif", out)
        self.assertIn("légende fictive", out)
        self.assertIn("titre fictif", out)
        self.assertNotIn("notes.txt", out)                                      # not an image extension: left out of a folder scan
        saved = json.loads(destination.read_text(encoding="utf-8"))
        self.assertEqual(saved["format"], "decretas-an-images-metadonnees/1")
        self.assertEqual(len(saved["fichiers"]), 3)
        self.assertIn("suite_des_noms", saved)

    def test_json_on_standard_output_and_url_decoding(self) -> None:
        code, out, _err = self.run_cli("metadonnees", self.folder / "LOT_000101_L.jpg", "--format", "json", "--sans-pil", "--url",
                                       "https://exemple.invalid/siv/media/FRAN_IR_000001/D1/LOT_000101_L")
        self.assertEqual(code, 0)
        card = json.loads(out)["fichiers"][0]
        self.assertEqual((card["largeur"], card["hauteur"]), (8, 8))
        self.assertEqual(card["url"]["inventaire"], "FRAN_IR_000001")
        self.assertEqual(card["url"]["notice"], "D1")
        self.assertNotIn("controle_pil", card)

    def test_refusals(self) -> None:
        empty = self.base / "vide"
        empty.mkdir()
        self.assertEqual(self.run_cli("metadonnees", empty)[0], 2)
        self.assertEqual(self.run_cli("metadonnees", self.folder, "--url", "https://exemple.invalid/x.jpg")[0], 2)
        code, out, _err = self.run_cli("metadonnees", self.folder / "notes.txt")
        self.assertEqual(code, 1)                                               # nothing readable among the files given
        self.assertIn("format non reconnu", out)


class ReadCommandTest(CliCase):
    def setUp(self) -> None:
        super().setUp()
        self.folder = self.base / "images"
        self.folder.mkdir()
        self.output = self.base / "lectures.json"
        absent = mock.patch.object(lecteurs.shutil, "which", lambda _name: None)   # a machine without Tesseract
        absent.start()
        self.addCleanup(absent.stop)

    def page(self, name: str, text: str | None) -> None:
        (self.folder / name).write_bytes(fabrique.jpeg_bytes(8, 8))
        if text is not None:
            (self.folder / name).with_suffix(".txt").write_text(text, encoding="utf-8")

    def test_manual_transcriptions_are_turned_into_occurrences(self) -> None:
        self.page("vue_1.jpg", fabrique.PAGE_1)
        self.page("vue_2.jpg", fabrique.PAGE_2)
        code, out, _err = self.run_cli("lire", self.folder, "--inventaire", "FRAN_IR_000001", "--notice", "D1", "--date", "1932-01-12",
                                       "--sortie", self.output)
        self.assertEqual(code, 0)
        self.assertIn("FRAN_IR_000001/D1 : lecture complète ; 4 personne(s), 1 épouse(s), 2 enfant(s)", out)
        self.assertIn("tampon : 1932-01-12", out)
        self.assertIn("à vérifier sur l'image", out)
        self.assertIn("n'est pas publié sur le site", out)
        self.assertIn("n'est pas installé", out)                                # Tesseract's absence is said even when not needed
        saved = json.loads(self.output.read_text(encoding="utf-8"))
        self.assertEqual(saved["bilan"]["occurrences"], 7)

    def test_unread_images_are_listed_with_the_ways_out(self) -> None:
        self.page("vue_1.jpg", None)
        code, out, _err = self.run_cli("lire", self.folder, "--sortie", self.output)
        self.assertEqual(code, 3)
        self.assertIn("NON LUE", out)
        self.assertIn("installer Tesseract", out)
        self.assertEqual(json.loads(self.output.read_text(encoding="utf-8"))["occurrences"], [])

    def test_explicit_tesseract_without_the_program_fails_loudly(self) -> None:
        self.page("vue_1.jpg", None)
        code, _out, err = self.run_cli("lire", self.folder, "--lecteur", "tesseract", "--sortie", self.output)
        self.assertEqual(code, 1)
        self.assertIn("sudo apt install tesseract-ocr tesseract-ocr-fra", err)
        self.assertFalse(self.output.exists())

    def test_missing_folder_empty_folder_and_missing_config(self) -> None:
        self.assertEqual(self.run_cli("lire", self.base / "absent", "--sortie", self.output)[0], 2)
        code, _out, err = self.run_cli("lire", self.folder, "--sortie", self.output)
        self.assertEqual(code, 2)
        self.assertIn("Aucune image", err)
        self.page("vue_1.jpg", None)
        code, _out, err = self.run_cli("lire", self.folder, "--lecteur", "commande", "--sortie", self.output)
        self.assertEqual(code, 1)
        self.assertIn("--config", err)

    def test_unknown_layout_is_announced(self) -> None:
        self.page("vue_1.jpg", "Sont admis :\nMohamed ben Ali ben Testeur, cultivateur, né en 1888 ;\n")
        code, out, _err = self.run_cli("lire", self.folder, "--sortie", self.output)
        self.assertEqual(code, 0)
        self.assertIn("AUCUNE personne reconnue", out)
        self.assertIn("1 bloc(s) de texte non découpé", out)

    def test_default_output_is_never_under_site_data(self) -> None:
        self.assertEqual(cli.BUILD.parts[-3:], ("data", "build", "an-images"))
        self.assertNotIn("site", cli.BUILD.relative_to(cli.ROOT).parts)


class CollectionPlanCommandTest(CliCase):
    def test_plan_is_computed_and_written(self) -> None:
        source = decree_file(self.base, rows())
        output = self.base / "plan"
        code, out, _err = self.run_cli("plan-collecte", "--donnees", source, "--sortie", output, "--pages-par-decret", "4",
                                       "--tous-les-decrets", self.base / "absent.csv")
        self.assertEqual(code, 0)
        self.assertIn("Indice des identifiants de média : non calculé", out)
        self.assertIn("Non calculé", (output / "plan-collecte.md").read_text(encoding="utf-8"))
        self.assertIn("5 décrets en images seules", out)
        self.assertIn("HYPOTHÈSES non mesurées", out)
        self.assertIn("Le collecteur n'est pas écrit", out)
        self.assertEqual(sorted(path.name for path in output.iterdir()),
                         ["plan-collecte-decrets.csv", "plan-collecte.json", "plan-collecte.md"])
        saved = json.loads((output / "plan-collecte.json").read_text(encoding="utf-8"))
        self.assertEqual(saved["total"]["requetes"], 5 * 6)

    def test_filters_and_refusals(self) -> None:
        source = decree_file(self.base, rows())
        output = self.base / "plan"
        absent = ("--tous-les-decrets", self.base / "absent.csv")
        code, out, _err = self.run_cli("plan-collecte", "--donnees", source, "--sortie", output, "--annees", "1899-1912", "--classes", "A1", *absent)
        self.assertEqual(code, 0)
        self.assertIn("1 décrets en images seules", out)
        self.assertEqual(self.run_cli("plan-collecte", "--donnees", source, "--sortie", output, "--classes", "Z", *absent)[0], 1)
        self.assertEqual(self.run_cli("plan-collecte", "--donnees", source, "--sortie", output, "--annees", "1912-1899", *absent)[0], 1)
        code, _out, err = self.run_cli("plan-collecte", "--donnees", self.base / "absent.json", "--sortie", output, *absent)
        self.assertEqual(code, 1)
        self.assertIn("illisible", err)


class ParserTest(CliCase):
    def test_unknown_command_is_refused_by_argparse(self) -> None:
        self.assertEqual(self.run_cli("collecter")[0], 2)

    def test_every_command_has_a_help_text(self) -> None:
        code, out, _err = self.run_cli("--help")
        self.assertEqual(code, 0)
        for command in ("disponibilite", "reprise", "metadonnees", "lire", "plan-collecte"):
            self.assertIn(command, out)


if __name__ == "__main__":
    unittest.main()


class SharedStopTest(CliCase):
    """Regression (review of 2026-11-12): a 403 met by « disponibilite » did not stop « reprise »."""

    def setUp(self) -> None:
        super().setUp()
        self.site = Site()
        self.addCleanup(self.site.close)

    def test_a_refusal_met_by_availability_stops_the_probe_before_any_request(self) -> None:
        self.site.routes[cli.AVAILABILITY_PATH] = Answer(status=403, body=b"interdit")
        code, _out, _err = self.run_cli("disponibilite", "--base", self.site.base, "--racine", self.base / "dispo")
        self.assertEqual(code, reprise.EXIT_BLOCKED)
        sent = len(self.site.requests)
        code, out, _err = self.run_cli("reprise", "--base", self.site.base, "--racine", self.base / "reprise",
                                       "--rapport", self.base / "rapport.md", "--donnees", self.base / "rien",
                                       "--delai", "0", "--palier", "1", "--plafond", "3")
        self.assertEqual(code, reprise.EXIT_BLOCKED)
        self.assertEqual(len(self.site.requests), sent, "not one request after the refusal")
        self.assertIn("décision humaine", out)

    def test_a_pause_recorded_by_the_probe_stops_availability(self) -> None:
        host = reprise.normalised_host(self.site.base)
        reprise.write_host_stop(self.stop_file, host, pause_jusqu_a=10 ** 11)
        code, out, _err = self.run_cli("disponibilite", "--base", self.site.base, "--racine", self.base / "dispo")
        self.assertEqual(code, reprise.EXIT_PAUSED)
        self.assertEqual(self.site.requests, [])
        self.assertIn("Rien n'est envoyé", out)

    def test_every_host_but_a_local_server_gets_the_real_limits(self) -> None:
        for base in ("https://www.siv.archives-nationales.culture.gouv.fr./", "https://WWW.SIV.ARCHIVES-NATIONALES.CULTURE.GOUV.FR/",
                     "https://192.0.2.10/", "https://exemple.test/"):
            self.assertTrue(reprise.is_real_host(base), base)
        for base in ("http://127.0.0.1:8811/", "http://localhost:8811/", "http://[::1]:8811/"):
            self.assertFalse(reprise.is_real_host(base), base)
