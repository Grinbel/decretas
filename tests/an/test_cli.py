"""The command line, the verification, the CSV listing and the legacy scripts."""
import contextlib
import csv
import io
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from decretas.an import cli, listing, verify

from .support import TIMESTAMP, build_all, make_corpus

ROOT = Path(__file__).resolve().parents[2]


def run_cli(*arguments: str) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = cli.main([str(a) for a in arguments])
    return code, out.getvalue(), err.getvalue()


class CommandLineTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.directory = tempfile.TemporaryDirectory()
        cls.root = Path(cls.directory.name)
        cls.raw = make_corpus(cls.root)
        cls.database = cls.root / "build" / "an.sqlite"
        cls.site = cls.root / "site"
        cls.expected = cls.root / "attendus.tsv"
        cls.build_code, cls.build_out, _ = run_cli(
            "construire", "--source", cls.raw, "--base", cls.database, "--sortie", cls.site, "--horodatage", TIMESTAMP)
        run_cli("attendus", "--base", cls.database, "--fichier", cls.expected)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.directory.cleanup()

    def test_construire_writes_everything_and_reports_in_french(self) -> None:
        self.assertEqual(self.build_code, 0)
        for name in ("an-decrets.json", "an-personnes.json", "an-meta.json"):
            self.assertTrue((self.site / name).exists(), name)
        self.assertIn("7 inventaires, 29 décrets, 27 notices de personnes, 18 épouses et enfants", self.build_out)
        self.assertIn("inventaire racine ignoré", self.build_out)
        self.assertIn("Clause Filae", self.build_out)
        self.assertIn("7 individus du palier Algérie concernés (3 personnes principales, 4 épouses et enfants)",
                      self.build_out)
        self.assertIn("RETENUS", self.build_out)
        self.assertEqual(json.loads((self.site / "an-meta.json").read_text(encoding="utf-8"))["genere_le"], TIMESTAMP)

    def test_inclure_filae_prints_the_same_count_and_a_warning(self) -> None:
        site = self.root / "site-filae"
        code, out, _ = run_cli("construire", "--base", self.database, "--sortie", site, "--export-seul",
                               "--inclure-filae", "--horodatage", TIMESTAMP)
        self.assertEqual(code, 0)
        self.assertIn("7 individus du palier Algérie concernés", out)
        self.assertIn("--inclure-filae : ces noms SONT dans l'export", out)
        self.assertNotIn("Lecture des inventaires XML", out)

    def test_construire_fails_cleanly_without_input(self) -> None:
        code, _, err = run_cli("construire", "--source", self.root / "vide", "--base", self.root / "x.sqlite",
                               "--sortie", self.root / "x")
        self.assertEqual(code, 1)
        self.assertIn("aucun inventaire", err)

    def test_chercher(self) -> None:
        code, out, _ = run_cli("chercher", "--base", self.database, "testaoui", "tahar", "miloud")
        self.assertEqual(code, 0)
        self.assertIn("Correspondances : 1", out)
        self.assertIn("Testaoui, Tahar ould Miloud", out)
        self.assertIn("http://www.siv.archives-nationales.culture.gouv.fr/siv/UD/FRAN_IR_900005/c-n3", out)
        self.assertIn("Bilan de recherche", out)

    def test_chercher_with_variants_birth_year_and_partial(self) -> None:
        code, out, _ = run_cli("chercher", "--base", self.database, "testaoui", "taher,tahar", "--ne-vers", "1875")
        self.assertEqual(code, 0)
        self.assertIn("Terme 2 : taher / tahar", out)
        self.assertIn("Correspondances : 1", out)
        self.assertIn("Correspondances partielles (un terme absent) : 1", out)     # born 1880, within 5 years
        self.assertIn("TERME ABSENT : taher", out)
        code, out, _ = run_cli("chercher", "--base", self.database, "ben fictif", "exemple")
        self.assertIn("cote suspecte ; lire probablement BB/34/477", out)

    def test_chercher_without_database(self) -> None:
        code, _, err = run_cli("chercher", "--base", self.root / "absente.sqlite", "testaoui")
        self.assertEqual(code, 1)
        self.assertIn("base absente", err)

    def test_verifier_is_clean_on_an_intact_corpus(self) -> None:
        report = verify.verify(self.raw, self.database, self.expected)
        self.assertTrue(report.ok, report.file_problems + report.count_problems)
        self.assertEqual((report.files, report.files_ok, report.inventories), (8, 8, 7))
        coverage = {label: (part, whole) for label, part, whole in report.coverage}
        self.assertEqual(coverage["lignes de contenu comprises"], (77, 78))
        self.assertEqual(coverage["notices avec un nom saisi"], (25, 27))
        self.assertEqual(coverage["notices avec une année de naissance"], (26, 27))
        flags = dict(report.flags)
        self.assertEqual(flags["décrets à cote suspecte (BB/11 au lieu de BB/34)"], 2)
        self.assertEqual(flags["liens d'images hors gabarit (publiés comme exceptions)"], 1)
        self.assertEqual(flags["professions lues dans la ligne de naissance"], 1)
        self.assertEqual([(inv, notice) for inv, notice, _, _ in report.discarded], [("FRAN_IR_900005", "c-arm1")])
        self.assertEqual([text for _, _, text in report.unparsed], ["Texte que l'analyseur ne comprend pas"])

    def test_verifier_detects_a_modified_file_and_changed_counts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            raw = make_corpus(Path(directory))
            database, _ = build_all(Path(directory))
            target = raw / "FRAN_IR_900006.xml"
            target.write_text(target.read_text(encoding="utf-8").replace("30 mars 1944", "31 mars 1944"),
                              encoding="utf-8")
            (raw / "FRAN_IR_900007.xml").unlink()
            report = verify.verify(raw, database, self.expected)
            self.assertFalse(report.ok)
            self.assertTrue(any("FRAN_IR_900006.xml" in p and "SHA-256" in p for p in report.file_problems))
            self.assertTrue(any("FRAN_IR_900007.xml" in p and "absent du disque" in p for p in report.file_problems))
            # the expected table disagrees once an inventory changes
            connection = sqlite3.connect(database)
            connection.execute("UPDATE inventaire SET n_personnes = n_personnes + 1 WHERE inv = 'FRAN_IR_900001'")
            connection.commit()
            connection.close()
            report = verify.verify(raw, database, self.expected)
            self.assertTrue(any("FRAN_IR_900001" in p and "8 personnes, 7 attendus" in p for p in report.count_problems))

    def test_verifier_detects_a_truncated_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            raw = make_corpus(Path(directory))
            database, _ = build_all(Path(directory))
            target = raw / "FRAN_IR_900006.xml"
            data = target.read_bytes()
            target.write_bytes(data[:-200])
            report = verify.verify(raw, database, self.expected)
            self.assertTrue(any("FRAN_IR_900006.xml" in p for p in report.file_problems))

    def test_verifier_command(self) -> None:
        code, out, _ = run_cli("verifier", "--source", self.raw, "--base", self.database)
        self.assertIn("Fichiers XML : 8 conformes au manifeste sur 8", out)
        self.assertIn("Notices écartées de l'index des noms : 1", out)
        self.assertNotIn("Texte que l'analyseur ne comprend pas", out)      # personal data: only with --detail
        # the shipped expected table describes the real corpus, not the fixtures
        self.assertEqual(code, 1)
        self.assertIn("inventaire inconnu de la table des effectifs attendus", out)
        code, out, _ = run_cli("verifier", "--source", self.raw, "--base", self.database, "--detail")
        self.assertIn("Texte que l'analyseur ne comprend pas", out)

    def test_decrets_csv(self) -> None:
        target = self.root / "decrets.csv"
        code, out, _ = run_cli("decrets", "--source", self.raw, "--csv", target)
        self.assertEqual(code, 0)
        self.assertIn("29 décrets écrits", out)
        with target.open(encoding="utf-8-sig", newline="") as handle:
            records = list(csv.DictReader(handle))
        self.assertEqual(list(records[0]), list(listing.CSV_FIELDS))
        self.assertEqual(len(records), 29)
        by_notice = {(r["inventaire"], r["notice_id"]): r for r in records}
        row = by_notice[("FRAN_IR_900004", "idd_1931_11_469_1")]
        self.assertEqual((row["classe_algerie"], row["cote"], row["drapeau_cote"], row["cote_suggeree"]),
                         ("A1", "BB/11/477", "suspecte-bb11", "BB/34/477"))
        self.assertEqual(row["lien_notice"],
                         "http://www.siv.archives-nationales.culture.gouv.fr/siv/UD/FRAN_IR_900004/idd_1931_11_469_1")
        row = by_notice[("FRAN_IR_900002", "idd_1892_08_01")]
        self.assertEqual((row["date"], row["drapeau_date"], row["date_normal"]),
                         ("1892-08-02", "conflit-titre-retenu", "1897-08-02"))
        self.assertEqual(by_notice[("FRAN_IR_900001", "SB000001")]["personnes_indexees"], "4")
        self.assertEqual([r["annee"] for r in records], sorted(r["annee"] for r in records))
        code, out, _ = run_cli("decrets", "--source", self.raw, "--csv", target, "--algerie")
        self.assertIn("16 décrets écrits", out)


class LegacyScriptsTest(unittest.TestCase):
    def test_lister_decrets_algeriens_keeps_its_command_line(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            raw = make_corpus(Path(directory))
            target = Path(directory) / "liste.csv"
            files = [str(p) for p in sorted(raw.glob("FRAN_IR_*.xml"))]
            script = str(ROOT / "scripts" / "lister-decrets-algeriens.py")
            done = subprocess.run([sys.executable, script, "-o", str(target), *files], capture_output=True, text=True,
                                  check=False)
            self.assertEqual(done.returncode, 0, done.stderr)
            self.assertIn("16 décrets écrits", done.stdout)
            with target.open(encoding="utf-8-sig", newline="") as handle:
                self.assertEqual(len(list(csv.DictReader(handle))), 16)
            done = subprocess.run([sys.executable, script, "--tous", "--sortie", str(target), *files],
                                  capture_output=True, text=True, check=False)
            self.assertIn("29 décrets écrits", done.stdout)

    def test_downloader_simulation_sends_nothing(self) -> None:
        script = str(ROOT / "scripts" / "telecharger-inventaires.sh")
        self.assertEqual(subprocess.run(["bash", "-n", script], check=False).returncode, 0)
        with tempfile.TemporaryDirectory() as directory:
            environment = dict(os.environ, DECRETAS_AN_DIR=directory)
            environment.pop("DELAY", None)
            environment.pop("DRY_RUN", None)
            done = subprocess.run(["bash", script, "--simulation", "FRAN_IR_900001"], capture_output=True, text=True,
                                  env=environment, check=False)
            self.assertEqual(done.returncode, 0, done.stderr)
            self.assertIn("simulation  FRAN_IR_900001", done.stdout)
            self.assertIn("exportXML.action?irId=FRAN_IR_900001", done.stdout)
            self.assertEqual(os.listdir(directory), [])            # nothing written, nothing fetched
            done = subprocess.run(["bash", script, "--simulation", "--rafraichir", "FRAN_IR_900001"],
                                  capture_output=True, text=True, env=environment, check=False)
            self.assertRegex(done.stdout, r"/rafraichi-\d{4}-\d{2}-\d{2}/FRAN_IR_900001\.xml")
            done = subprocess.run(["bash", script, "--simulation", "--delai", "1", "FRAN_IR_900001"],
                                  capture_output=True, text=True, env=environment, check=False)
            self.assertEqual(done.returncode, 2)
            self.assertIn("5 s au minimum", done.stderr)
            done = subprocess.run(["bash", script, "--simulation", "pas-un-identifiant"], capture_output=True,
                                  text=True, env=environment, check=False)
            self.assertEqual(done.returncode, 2)

    def _fake_download(self, directory: Path, code: str, body: str, *arguments: str,
                       reference: dict[str, str] | None = None) -> tuple[subprocess.CompletedProcess, Path]:
        """Run the downloader with a fake ``curl`` and a fake ``sleep`` first on the PATH: nothing leaves the machine."""
        tools = directory / "outils"
        tools.mkdir(exist_ok=True)
        (directory / "reponse").write_text(body, encoding="utf-8")
        (tools / "curl").write_text(
            "#!/usr/bin/env bash\n"
            'printf \'%s\\n\' "$*" >> "$FAUX_JOURNAL"\n'
            'while [ "$#" -gt 0 ]; do [ "$1" = "-o" ] && sortie="$2"; shift; done\n'
            'cp "$FAUSSE_REPONSE" "$sortie"\n'
            'printf \'%s\' "$FAUX_CODE"\n', encoding="utf-8")
        (tools / "sleep").write_text('#!/usr/bin/env bash\nprintf \'sleep %s\\n\' "$1" >> "$FAUX_JOURNAL"\n',
                                     encoding="utf-8")
        for tool in ("curl", "sleep"):
            (tools / tool).chmod(0o755)
        data = directory / "an"
        data.mkdir(exist_ok=True)
        for name, content in (reference or {}).items():
            (data / name).write_text(content, encoding="utf-8")
        environment = dict(os.environ, DECRETAS_AN_DIR=str(data), PATH=f"{tools}{os.pathsep}{os.environ['PATH']}",
                           FAUX_JOURNAL=str(directory / "journal"), FAUSSE_REPONSE=str(directory / "reponse"),
                           FAUX_CODE=code)
        environment.pop("DELAY", None)
        environment.pop("DRY_RUN", None)
        script = str(ROOT / "scripts" / "telecharger-inventaires.sh")
        done = subprocess.run(["bash", script, *arguments], capture_output=True, text=True, env=environment,
                              check=False)
        return done, data

    @staticmethod
    def _manifest(data: Path) -> list[dict]:
        return [json.loads(line) for line in (data / "manifest.jsonl").read_text(encoding="utf-8").splitlines()]

    GOOD_EXPORT = '<?xml version="1.0" encoding="UTF-8"?><ead><eadheader/></ead>\n'

    def test_downloader_saves_a_good_answer_and_records_the_url(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            directory = Path(name)
            done, data = self._fake_download(directory, "200", self.GOOD_EXPORT, "FRAN_IR_900001", "FRAN_IR_900002")
            self.assertEqual(done.returncode, 0, done.stderr)
            self.assertEqual((data / "FRAN_IR_900001.xml").read_text(encoding="utf-8"), self.GOOD_EXPORT)
            records = self._manifest(data)
            self.assertEqual([(r["id"], r["ok"], r["http"], r["saved_as"]) for r in records],
                             [("FRAN_IR_900001", True, "200", "FRAN_IR_900001.xml"),
                              ("FRAN_IR_900002", True, "200", "FRAN_IR_900002.xml")])
            self.assertTrue(records[0]["url"].endswith("exportXML.action?irId=FRAN_IR_900001"))
            self.assertEqual(len(records[0]["sha256"]), 64)
            journal = (directory / "journal").read_text(encoding="utf-8").splitlines()
            self.assertEqual([line.startswith("sleep") for line in journal], [False, True, False, True])
            self.assertEqual(journal[1], "sleep 5")                               # default delay
            self.assertIn("-A decretas/0.2 (recherche genealogique non commerciale; projet libre et gratuit)", journal[0])
            self.assertNotIn("-L", journal[0].split())                            # redirects are never followed
            # a second run asks for nothing: the files are there
            (directory / "journal").unlink()
            done, _ = self._fake_download(directory, "200", self.GOOD_EXPORT, "FRAN_IR_900001", "FRAN_IR_900002")
            self.assertEqual(done.returncode, 0)
            self.assertFalse((directory / "journal").exists())
            self.assertIn("2 déjà présent(s)", done.stdout)

    def test_downloader_stops_when_the_site_is_down(self) -> None:
        for code in ("503", "502", "504", "000"):
            with tempfile.TemporaryDirectory() as name:
                directory = Path(name)
                done, data = self._fake_download(directory, code, "<html>SIA - Erreur 503</html>",
                                                 "FRAN_IR_900001", "FRAN_IR_900002")
                self.assertEqual(done.returncode, 3, code)
                self.assertIn("SITE EN PANNE", done.stderr)
                self.assertEqual(sorted(p.name for p in data.iterdir()), ["manifest.jsonl"])
                self.assertEqual([(r["id"], r["ok"], r["reason"]) for r in self._manifest(data)],
                                 [("FRAN_IR_900001", False, "site-down")])
                # one request only: no retry, and the second inventory is not asked for
                self.assertEqual(len((directory / "journal").read_text(encoding="utf-8").splitlines()), 1)

    def test_downloader_stops_at_a_refusal_and_keeps_the_answer(self) -> None:
        cases = {"403": ("<html>Accès refusé</html>", "refused"), "429": ("", "refused"),
                 "302": ("", "refused"), "200": ("<html>Vérification du navigateur</html>", "not-xml")}
        for code, (body, reason) in cases.items():
            with tempfile.TemporaryDirectory() as name:
                directory = Path(name)
                done, data = self._fake_download(directory, code, body, "FRAN_IR_900001", "FRAN_IR_900002")
                self.assertEqual(done.returncode, 1, code)
                self.assertIn("REFUS", done.stderr)
                self.assertFalse((data / "FRAN_IR_900001.xml").exists())
                self.assertEqual((data / "FRAN_IR_900001.refus").read_text(encoding="utf-8"), body)
                self.assertEqual([(r["ok"], r["reason"]) for r in self._manifest(data)], [(False, reason)])
                self.assertEqual(len((directory / "journal").read_text(encoding="utf-8").splitlines()), 1)

    def test_downloader_refuses_a_truncated_export(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            directory = Path(name)
            done, data = self._fake_download(directory, "200", '<?xml version="1.0"?><ead><eadheader/>', "FRAN_IR_900001")
            self.assertEqual(done.returncode, 4)
            self.assertIn("TRONQUÉ", done.stderr)
            self.assertFalse((data / "FRAN_IR_900001.xml").exists())
            self.assertTrue((data / "FRAN_IR_900001.tronque").exists())

    def test_downloader_refresh_never_overwrites_the_reference_files(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            directory = Path(name)
            reference = {"FRAN_IR_900001.xml": self.GOOD_EXPORT, "FRAN_IR_900002.xml": "<ead>ancien</ead>\n"}
            done, data = self._fake_download(directory, "200", self.GOOD_EXPORT, "--rafraichir", "FRAN_IR_900001",
                                             "FRAN_IR_900002", reference=reference)
            self.assertEqual(done.returncode, 0, done.stderr)
            self.assertEqual((data / "FRAN_IR_900002.xml").read_text(encoding="utf-8"), "<ead>ancien</ead>\n")
            self.assertFalse((data / "manifest.jsonl").exists())                 # the reference manifest is untouched
            dated = [p for p in data.iterdir() if p.is_dir()]
            self.assertEqual(len(dated), 1)
            self.assertRegex(dated[0].name, r"^rafraichi-\d{4}-\d{2}-\d{2}$")
            self.assertEqual((dated[0] / "FRAN_IR_900002.xml").read_text(encoding="utf-8"), self.GOOD_EXPORT)
            self.assertEqual([(r["id"], r["same_as_reference"]) for r in self._manifest(dated[0])],
                             [("FRAN_IR_900001", True), ("FRAN_IR_900002", False)])
            self.assertIn("DIFFÉRENT du fichier de référence", done.stdout)
            # the refreshed set is not mixed with the reference one when the pipeline lists its inputs
            from decretas.an import ead
            self.assertEqual([p.name for p in ead.inventory_files(data)], ["FRAN_IR_900001.xml", "FRAN_IR_900002.xml"])

    def test_downloader_help_is_in_french(self) -> None:
        done = subprocess.run(["bash", str(ROOT / "scripts" / "telecharger-inventaires.sh"), "--aide"],
                              capture_output=True, text=True, check=False)
        self.assertEqual(done.returncode, 0)
        self.assertIn("Utilisation :", done.stdout)
        self.assertIn("--rafraichir", done.stdout)
        self.assertNotIn("Download", done.stdout)

    def test_downloader_declares_itself_and_goes_slowly(self) -> None:
        text = (ROOT / "scripts" / "telecharger-inventaires.sh").read_text(encoding="utf-8")
        self.assertIn('UA="decretas/0.2 (recherche genealogique non commerciale; projet libre et gratuit)"', text)
        self.assertIn('DELAY="${DELAY:-5}"', text)
        self.assertIn("000|502|503|504)", text)

    def test_inventory_list_matches_the_expected_table(self) -> None:
        listed = []
        for line in (ROOT / "scripts" / "inventaires-decrets.txt").read_text(encoding="utf-8").splitlines():
            identifier = line.split("#", 1)[0].strip()
            if identifier:
                listed.append(identifier)
        self.assertEqual(len(listed), len(set(listed)))
        expected = set(verify.read_expected())
        self.assertEqual(set(listed) - expected, {"FRAN_IR_057397"})      # the root inventory holds no decree
        self.assertEqual(expected - set(listed), set())

    def test_inventory_list_annotations_match_the_measured_coverage(self) -> None:
        import re
        expected = verify.read_expected()
        checked = 0
        for line in (ROOT / "scripts" / "inventaires-decrets.txt").read_text(encoding="utf-8").splitlines():
            found = re.match(r"(FRAN_IR_\d{6})\s+#\s+(\d{4}).* — (indexé|partiel|image seule) \((\d+)/(\d+)"
                             r"(?:, (\d+) personnes?)?\)", line)
            if not found:
                continue
            inventory, year, state, with_names, decrees, person_count = found.groups()
            row = expected[inventory]
            self.assertEqual((year, with_names, decrees), (row["annee"], row["decrets_avec_noms"], row["decrets"]), line)
            if person_count is not None:
                self.assertEqual(person_count, row["personnes"], line)
            share = int(with_names) / int(decrees)
            self.assertEqual(state, "image seule" if with_names == "0" else "indexé" if share >= 0.9 else "partiel", line)
            checked += 1
        self.assertEqual(checked, len(expected))


if __name__ == "__main__":
    unittest.main()
