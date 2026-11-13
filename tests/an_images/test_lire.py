"""The transcription harness: readers behind one interface, rows for the name search engine.

Every name is invented. External programs are tiny scripts written by the test; nothing is
installed, no network is used.
"""
from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from decretas.an_images import lecteurs, lire

from . import fabrique

ROOT = Path(__file__).resolve().parents[2]


def executable(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return path


class FolderCase(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.base = Path(self.directory.name)
        self.folder = self.base / "images"
        self.folder.mkdir()

    def image(self, name: str, transcription: str | None = None) -> Path:
        path = self.folder / name
        path.write_bytes(fabrique.jpeg_bytes(8, 8))
        if transcription is not None:
            path.with_suffix(".txt").write_text(transcription, encoding="utf-8")
        return path

    def two_pages(self) -> None:
        # natural order: vue_2 before vue_10 would matter; here 1 then 2
        self.image("LOT_000101_L.jpg", fabrique.PAGE_1)
        self.image("LOT_000102_L.jpg", fabrique.PAGE_2)

    def absent_tesseract(self) -> lecteurs.TesseractReader:
        return lecteurs.TesseractReader(binary="tesseract-absent-de-cette-machine")

    def fake_tesseract(self, output: str = fabrique.PAGE_1, languages: str = "List of available languages (2):\nfra\neng\n") -> lecteurs.TesseractReader:
        script = executable(self.base / "faux-tesseract", f"""#!{sys.executable}
import sys
if "--list-langs" in sys.argv:
    sys.stdout.write({languages!r})
    sys.exit(0)
assert sys.argv[2] == "stdout" and sys.argv[3:5] == ["-l", "fra"] and sys.argv[5] == "--psm", sys.argv
sys.stdout.write({output!r})
""")
        return lecteurs.TesseractReader(binary=str(script))


class ManualReaderTest(FolderCase):
    def test_rows_have_the_shape_the_search_engine_takes(self) -> None:
        self.two_pages()
        document = lire.read_folder(self.folder, mode="manuel", inventory="FRAN_IR_000001", notice="D1", date="1932-01-12")
        rows = document["occurrences"]
        self.assertEqual([row["id"] for row in rows], list(range(len(rows))))
        self.assertEqual([(row["nom"], row["role"], row["anneeNaissance"]) for row in rows], [
            ("TESTAOUI (Ahmed ben Mohamed)", "principal", 1885),
            ("FICTIVO (Paul Henri)", "principal", 1881),
            ("EXEMPLMANN (Maria)", "epouse", 1890),
            ("Pierre", "enfant", 1912),
            ("Louise", "enfant", 1915),
            ("INVENTEE (Rosa)", "principal", 1899),
            ("SPECIMEN (Paul)", "principal", 1901)])
        first = rows[0]
        self.assertEqual(first["groupe"], "an-images")
        self.assertEqual(first["decret"], "FRAN_IR_000001/D1")
        self.assertEqual((first["image"], first["vue"]), ("LOT_000101_L.jpg", 1))
        self.assertEqual(rows[6]["image"], "LOT_000102_L.jpg")
        self.assertEqual(first["lecteur"], "manuel")
        self.assertEqual(first["confiance"], "transcription manuelle — à vérifier sur l'image")
        self.assertFalse(first["ocr"])
        self.assertEqual(first["dossier"], "20001 X 31")
        self.assertEqual({row["princ"] for row in rows[1:5]}, {1})              # wife and children point to their principal
        self.assertEqual(document["bilan"]["principaux"], 4)
        self.assertEqual(document["bilan"]["blocs_de_texte"], 0)
        self.assertEqual(document["decrets"][0]["lecture"], "complète")
        self.assertEqual(document["decrets"][0]["preambule"]["date_du_tampon"], "1932-01-12")
        self.assertIn("jamais une citation", document["avertissement"])

    def test_transcription_file_named_after_the_full_image_name(self) -> None:
        image = self.image("page.jpg")
        (self.folder / "page.jpg.txt").write_text(fabrique.PAGE_1, encoding="utf-8")
        reading = lecteurs.ManualReader().read(image)
        self.assertIn("TESTAOUI", reading.text)
        self.assertTrue(reading.source.endswith("page.jpg.txt"))

    def test_missing_page_makes_the_decree_partial_and_says_which_image(self) -> None:
        self.image("LOT_000101_L.jpg", fabrique.PAGE_1)
        self.image("LOT_000102_L.jpg")                                           # no transcription
        document = lire.read_folder(self.folder, mode="manuel", tesseract=self.absent_tesseract())
        self.assertEqual(document["decrets"][0]["lecture"], "partielle")
        self.assertEqual(len(document["non_lues"]), 1)
        self.assertIn("LOT_000102_L.jpg", document["non_lues"][0]["fichier"])
        self.assertIn("pas de transcription", document["non_lues"][0]["raison"])
        self.assertTrue(all("decret-lu-partiellement" in row["drapeaux"] for row in document["occurrences"] if row["role"] == "principal"))
        self.assertEqual(document["bilan"]["images_non_lues"], 1)
        self.assertIsNone(document["occurrences"][0]["decret"])                  # no decree given: said, not invented

    def test_empty_and_latin1_transcriptions(self) -> None:
        empty = self.image("a.jpg", "   \n")
        self.assertEqual(lecteurs.ManualReader().read(empty).error, "transcription vide")
        latin = self.image("b.jpg")
        latin.with_suffix(".txt").write_bytes("5 X 31  ESSAI (René), né le 2 février 1890 à Oran.".encode("latin-1"))
        self.assertIn("René", lecteurs.ManualReader().read(latin).text)

    def test_sidecar_gives_the_decree_and_the_view_order(self) -> None:
        self.image("b-seconde.jpg", fabrique.PAGE_2)
        self.image("a-premiere.jpg", fabrique.PAGE_1)
        self.image("z-autre.jpg", "Décrète :\n9 X 35  AUTRE (Lina), née le 5 mai 1900 à Tunis (Tunisie), demeurant à Alger.\n")
        (self.folder / "decret.json").write_text(json.dumps({"images": {
            "b-seconde.jpg": {"inventaire": "FRAN_IR_000001", "notice": "D1", "vue": 2},
            "a-premiere.jpg": {"inventaire": "FRAN_IR_000001", "notice": "D1", "vue": 1},
            "z-autre.jpg": {"inventaire": "FRAN_IR_000002", "notice": "D9", "vue": 1}}}), encoding="utf-8")
        document = lire.read_folder(self.folder, mode="manuel", inventory="IGNORE", notice="IGNORE")
        self.assertEqual([decree["decret"] for decree in document["decrets"]], ["FRAN_IR_000001/D1", "FRAN_IR_000002/D9"])
        self.assertEqual([image["fichier"] for image in document["decrets"][0]["images"]], ["a-premiere.jpg", "b-seconde.jpg"])
        self.assertEqual(document["occurrences"][-1]["nom"], "AUTRE (Lina)")
        self.assertEqual(document["occurrences"][-1]["decret"], "FRAN_IR_000002/D9")

    def test_natural_order_of_file_names(self) -> None:
        for name in ("vue_10.jpg", "vue_2.jpg", "vue_1.jpg", "notes.txt", "vue_3.PNG"):
            (self.folder / name).write_bytes(b"x")
        self.assertEqual([path.name for path in lire.list_images(self.folder)], ["vue_1.jpg", "vue_2.jpg", "vue_3.PNG", "vue_10.jpg"])

    def test_unknown_layout_becomes_searchable_blocks(self) -> None:
        self.image("p1.jpg", "Sont admis aux droits de citoyen français :\nMohamed ben Ali ben Testeur, cultivateur, né en 1888 ;\n")
        self.image("p2.jpg", "Ahmed ben Fictif, né en 1901.\n")
        document = lire.read_folder(self.folder, mode="manuel", inventory="FRAN_IR_000001", notice="D2")
        rows = document["occurrences"]
        self.assertEqual([row["role"] for row in rows], ["bloc", "bloc"])
        self.assertIn("Mohamed ben Ali ben Testeur", rows[0]["nom"])
        self.assertEqual((rows[1]["image"], rows[1]["vue"]), ("p2.jpg", 2))
        self.assertEqual(rows[0]["drapeaux"], ["texte-non-decoupe", "aucune-personne-reconnue"])
        self.assertIsNone(rows[0]["anneeNaissance"])
        self.assertEqual(document["bilan"]["blocs_de_texte"], 2)
        self.assertEqual(document["decrets"][0]["stats"]["entrees"], 0)

    def test_blocks_never_exceed_what_the_engine_reads_and_overlap(self) -> None:
        words = [f"mot{rank}" for rank in range(450)]
        pieces = lire.blocks_of(" ".join(words))
        self.assertTrue(all(len(piece.split()) <= lire.BLOCK_WORDS for piece in pieces))
        self.assertEqual(pieces[0].split()[-lire.BLOCK_OVERLAP:], pieces[1].split()[:lire.BLOCK_OVERLAP])
        self.assertEqual({word for piece in pieces for word in piece.split()}, set(words))    # nothing lost
        self.assertEqual(lire.blocks_of("  "), [])
        self.assertEqual(lire.blocks_of("un deux"), ["un deux"])

    def test_output_file_is_written_where_asked(self) -> None:
        self.two_pages()
        destination = lire.write(lire.read_folder(self.folder, mode="manuel"), self.base / "sortie" / "lectures.json")
        saved = json.loads(destination.read_text(encoding="utf-8"))
        self.assertEqual(saved["format"], "decretas-an-images-lectures/1")
        self.assertEqual(len(saved["occurrences"]), 7)


class TesseractReaderTest(FolderCase):
    def test_absent_binary_is_said_with_install_instructions(self) -> None:
        reader = self.absent_tesseract()
        ok, note = reader.available()
        self.assertFalse(ok)
        self.assertIn("n'est pas installé", note)
        self.assertIn("sudo apt install tesseract-ocr tesseract-ocr-fra", note)
        self.assertIn("droits", note)                                            # the flags of the command are explained
        self.image("p.jpg")
        with self.assertRaises(lecteurs.ReaderUnavailable) as caught:
            lire.read_folder(self.folder, mode="tesseract", tesseract=reader)
        self.assertIn("n'est pas installé", str(caught.exception))

    def test_auto_mode_reports_the_absence_and_lists_unread_images(self) -> None:
        self.image("p.jpg")
        document = lire.read_folder(self.folder, mode="auto", tesseract=self.absent_tesseract())
        self.assertIn("n'est pas installé", document["lecteurs"]["tesseract"])
        self.assertEqual(document["bilan"]["images_lues"], 0)
        self.assertEqual(len(document["non_lues"]), 1)
        self.assertEqual(document["occurrences"], [])

    def test_missing_language_model_is_said(self) -> None:
        reader = self.fake_tesseract(languages="List of available languages (1):\neng\n")
        ok, note = reader.available()
        self.assertFalse(ok)
        self.assertIn("tesseract-ocr-fra", note)

    def test_fake_binary_output_is_flagged_as_machine_reading(self) -> None:
        self.image("p.jpg")
        reader = self.fake_tesseract()
        self.assertTrue(reader.available()[0])
        document = lire.read_folder(self.folder, mode="tesseract", tesseract=reader)
        first = document["occurrences"][0]
        self.assertEqual(first["nom"], "TESTAOUI (Ahmed ben Mohamed)")
        self.assertEqual(first["lecteur"], "tesseract")
        self.assertEqual(first["confiance"], "lecture automatique — à vérifier sur l'image")
        self.assertTrue(first["ocr"])

    def test_auto_mode_prefers_the_human_transcription(self) -> None:
        self.image("p1.jpg", "Décrète :\n7 X 31  HUMAIN (Lu), né le 2 mai 1890 à Oran, demeurant à Oran.\n")
        self.image("p2.jpg")
        document = lire.read_folder(self.folder, mode="auto", tesseract=self.fake_tesseract(
            "8 X 31  MACHINE (Lue), née le 3 mai 1891 à Oran, demeurant à Oran.\n"))
        self.assertEqual([(row["nom"], row["lecteur"]) for row in document["occurrences"]],
                         [("HUMAIN (Lu)", "manuel"), ("MACHINE (Lue)", "tesseract")])


class CommandReaderTest(FolderCase):
    def config(self, value) -> Path:
        path = self.base / "lecteur.json"
        path.write_text(json.dumps(value), encoding="utf-8")
        return path

    def script(self, body: str) -> Path:
        path = self.base / "lecteur_externe.py"
        path.write_text(body, encoding="utf-8")
        return path

    def test_contract_image_path_in_stdout_out(self) -> None:
        image = self.image("p.jpg")
        script = self.script("import sys\nassert sys.argv[1] == '--image'\n"
                             "print('3 X 31  RECU (' + sys.argv[2].rsplit('/', 1)[-1] + '), né le 2 mai 1890 à Oran.')\n")
        config = self.config({"commande": [sys.executable, str(script), "--image", "{image}"], "delai_s": 30, "nom": "essai"})
        document = lire.read_folder(self.folder, mode="commande", config=config)
        row = document["occurrences"][0]
        self.assertEqual(row["nom"], "RECU (p.jpg)")                             # the absolute path of the image was passed
        self.assertEqual(row["lecteur"], "commande:essai")
        self.assertEqual(row["confiance"], lecteurs.AUTOMATIC)
        self.assertTrue(row["ocr"])
        self.assertTrue(Path(image).is_absolute())

    def test_image_path_is_appended_when_no_placeholder(self) -> None:
        self.image("p.jpg")
        script = self.script("import sys\nprint('4 X 31  DERNIER (' + sys.argv[-1].rsplit('/', 1)[-1] + '), né en 1890 à Oran.')\n")
        reader = lecteurs.CommandReader.from_config(self.config({"commande": [sys.executable, str(script)]}))
        self.assertIn("DERNIER (p.jpg)", reader.read(self.folder / "p.jpg").text)

    def test_failures_are_reported_per_image_never_silently(self) -> None:
        self.image("p.jpg")
        cases = {"import sys\nsys.stderr.write('clef absente\\n')\nsys.exit(7)\n": "code de sortie 7 (clef absente)",
                 "pass\n": "sortie vide",
                 "import time\ntime.sleep(5)\n": "délai de 1 s dépassé"}
        for body, expected in cases.items():
            reader = lecteurs.CommandReader.from_config(self.config({"commande": [sys.executable, str(self.script(body))], "delai_s": 1}))
            reading = reader.read(self.folder / "p.jpg")
            self.assertIsNone(reading.text)
            self.assertEqual(reading.error, expected)
        document = lire.read_folder(self.folder, mode="commande",
                                    config=self.config({"commande": [sys.executable, str(self.script("pass\n"))]}))
        self.assertEqual(document["non_lues"][0]["raison"], "commande : sortie vide")
        self.assertEqual(document["decrets"][0]["lecture"], "aucune")

    def test_no_shell_is_involved(self) -> None:
        self.image("p.jpg")
        marker = self.base / "trace-d-un-shell"
        script = self.script("import sys\nprint('5 X 31  SANS (Shell), né en 1890 à Oran. ' + ' '.join(sys.argv[1:-1]))\n")
        reader = lecteurs.CommandReader.from_config(self.config(
            {"commande": [sys.executable, str(script), f"; touch {marker}", "$(touch " + str(marker) + ")"]}))
        self.assertIn("; touch", reader.read(self.folder / "p.jpg").text)        # passed as plain arguments
        self.assertFalse(marker.exists())

    def test_bad_configurations_are_refused_with_a_reason(self) -> None:
        self.image("p.jpg")
        with self.assertRaises(lecteurs.ReaderUnavailable) as caught:
            lire.read_folder(self.folder, mode="commande")
        self.assertIn("--config", str(caught.exception))
        for value, expected in (({"commande": "mon-lecteur {image}"}, "liste non vide"), ({"commande": []}, "liste non vide"),
                                ({"commande": ["x"], "delai_s": 0}, "delai_s"), (["x"], "liste non vide")):
            with self.assertRaises(lecteurs.ReaderUnavailable) as caught:
                lecteurs.CommandReader.from_config(self.config(value))
            self.assertIn(expected, str(caught.exception))
        broken = self.base / "casse.json"
        broken.write_text("{", encoding="utf-8")
        with self.assertRaises(lecteurs.ReaderUnavailable):
            lecteurs.CommandReader.from_config(broken)
        with self.assertRaises(lecteurs.ReaderUnavailable):
            lecteurs.CommandReader.from_config(self.base / "absent.json")
        with self.assertRaises(lecteurs.ReaderUnavailable) as caught:
            lire.read_folder(self.folder, mode="commande", config=self.config({"commande": ["programme-qui-n-existe-pas"]}))
        self.assertIn("introuvable", str(caught.exception))

    def test_nothing_is_configured_or_called_by_default(self) -> None:
        self.assertEqual(lecteurs.CommandReader().arguments, [])
        self.assertFalse(lecteurs.CommandReader().available()[0])
        readers, _notes = lire.choose_readers("auto", None, tesseract=self.absent_tesseract())
        self.assertEqual([reader.name for reader in readers], ["manuel"])        # no external program in the default chain


@unittest.skipUnless(shutil.which("node"), "node absent : compatibilité avec le moteur de recherche non vérifiée ici")
class SearchEngineCompatibilityTest(FolderCase):
    """The rows written by the harness are accepted as they are by site/js/recherche."""

    def search(self, rows: list[dict], query: dict) -> dict:
        data = self.base / "lectures.json"
        data.write_text(json.dumps({"occurrences": rows}), encoding="utf-8")
        program = f"""
import {{ readFileSync }} from 'node:fs';
import {{ buildIndex }} from {json.dumps((ROOT / 'site/js/recherche/index.js').as_uri())};
import {{ search }} from {json.dumps((ROOT / 'site/js/recherche/chercher.js').as_uri())};
const rows = JSON.parse(readFileSync({json.dumps(str(data))}, 'utf8')).occurrences;
const index = buildIndex(rows);
const found = search(index, {json.dumps(query)});
console.log(JSON.stringify({{ taille: index.size, groupes: index.groups,
  trouves: found.correspondances.map((c) => ({{ nom: c.nom, classe: c.classe, role: c.occurrence.role, image: c.occurrence.image,
    confiance: c.occurrence.confiance, an: c.anneeNaissance }})) }}));
"""
        done = subprocess.run(["node", "--input-type=module", "-e", program], capture_output=True, text=True, timeout=60,
                              check=False, env={**os.environ, "NO_COLOR": "1"})
        self.assertEqual(done.returncode, 0, done.stderr)
        return json.loads(done.stdout)

    def test_a_person_row_is_found_with_its_image_and_its_warning(self) -> None:
        self.two_pages()
        document = lire.read_folder(self.folder, mode="manuel", inventory="FRAN_IR_000001", notice="D1", date="1932-01-12")
        result = self.search(document["occurrences"], {"texte": "Ahmed ben Mohamed Testaoui", "annee": 1885})
        self.assertEqual(result["taille"], 7)
        self.assertEqual(result["groupes"], ["an-images"])
        self.assertTrue(result["trouves"], "aucune correspondance")
        first = result["trouves"][0]
        self.assertEqual((first["nom"], first["role"], first["image"], first["an"]),
                         ("TESTAOUI (Ahmed ben Mohamed)", "principal", "LOT_000101_L.jpg", 1885))
        self.assertIn("à vérifier sur l'image", first["confiance"])

    def test_a_name_inside_an_undivided_block_is_found_too(self) -> None:
        self.image("p1.jpg", "Sont admis aux droits de citoyen français :\nMohamed ben Ali ben Testeur, cultivateur, né en 1888 ;\n")
        document = lire.read_folder(self.folder, mode="manuel")
        result = self.search(document["occurrences"], {"texte": "Mohamed ben Ali Testeur"})
        self.assertTrue(result["trouves"], "aucune correspondance")
        self.assertEqual(result["trouves"][0]["role"], "bloc")
        self.assertEqual(result["trouves"][0]["image"], "p1.jpg")


if __name__ == "__main__":
    unittest.main()
