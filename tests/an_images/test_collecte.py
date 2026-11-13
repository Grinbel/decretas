"""The collection plan: counts and arithmetic on a small synthetic decree file."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from decretas.an_images import collecte

FIELDS = ["id", "inv", "notice", "date", "titre", "famille", "classe", "cote", "doc", "etat", "annee"]
TABLES = {"inv": ["FRAN_IR_000001", "FRAN_IR_000002"], "famille": ["naturalisation", "admission-citoyen", "rejet"],
          "classe": ["A1", "A2", "A3", "R", "-"], "etat": ["indexe", "partiel", "image", "retenu-filae"]}


def decree_file(directory: Path, rows: list[list]) -> Path:
    path = directory / "an-decrets.json"
    path.write_text(json.dumps({"format": "essai", "champs": FIELDS, "tables": TABLES, "lignes": rows}), encoding="utf-8")
    return path


def rows() -> list[list]:
    # id, inv, notice, date, titre, famille, classe, cote, doc, etat, annee
    return [
        [0, 0, "D1", "1905-02-05", "Décret fictif A", 0, 0, "BB/34/000", "document 1", 2, 1905],     # image, A1
        [1, 0, "D2", "1905-03-01", "Décret fictif B", 2, 3, "BB/34/000", "document 2", 2, 1905],     # image, R
        [2, 0, "D3", "1905-04-01", "Décret fictif C", 0, 0, "BB/34/000", "document 3", 0, 1905],     # indexed: not counted
        [3, 1, "D4", "1928-05-01", "Décret fictif D", 0, 0, "BB/34/001", "document 4", 2, 1928],     # image, A1
        [4, 1, "D5", "1946-07-17", "Décret fictif E", 1, 1, "BB/34/002", None, 2, 1946],             # image, A2
        [5, 1, "D6", "1946-08-01", "Décret fictif F", 0, 4, "BB/34/002", None, 2, 1946],             # image, not Algeria: not counted
        [6, 1, "D7", "1920-01-01", "Décret fictif G", 0, 0, "BB/34/003", None, 2, 1920],             # image, outside the known periods
    ]


class ComputeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.decrees = collecte.load_decrees(decree_file(Path(self.directory.name), rows()))

    def test_only_image_only_decrees_of_the_algeria_classes_are_counted(self) -> None:
        result = collecte.compute(self.decrees)
        self.assertEqual(result["total"]["decrets"], 5)
        self.assertEqual(result["par_classe"], {"A1": 3, "A2": 1, "A3": 0, "R": 1})
        self.assertEqual([decree["notice"] for decree in result["decrets"]], ["D1", "D2", "D7", "D4", "D5"])   # by date
        self.assertEqual({period["periode"]: period["decrets"] for period in result["periodes"]},
                         {"1899-1912": 2, "1928": 1, "1933-1948": 1, "autres années": 1})

    def test_requests_and_duration_arithmetic(self) -> None:
        result = collecte.compute(self.decrees, pages_per_decree=4, fixed_requests=2, delay=10.0, hours_per_day=5.0)
        # 5 decrees × (2 + 4) requests = 30 requests ; × 10 s = 300 s
        self.assertEqual(result["total"]["requetes"], 30)
        self.assertEqual(result["total"]["heures"], round(300 / 3600, 1))
        self.assertEqual(result["hypotheses"]["pages_par_decret"], 4)
        self.assertIn("PAS mesurés", result["hypotheses"]["note"])
        by_pages = {line["pages_par_decret"]: line["requetes"] for line in result["sensibilite"]}
        self.assertEqual(by_pages[1], 5 * 3)
        self.assertEqual(by_pages[40], 5 * 42)
        year = next(line for line in result["annees"] if line["annee"] == 1905)
        self.assertEqual((year["decrets"], year["classes"]["A1"], year["classes"]["R"], year["requetes"]), (2, 1, 1, 12))

    def test_year_and_class_filters(self) -> None:
        self.assertEqual(collecte.compute(self.decrees, years=(1899, 1912))["total"]["decrets"], 2)
        self.assertEqual(collecte.compute(self.decrees, years=(1928, 1928))["total"]["decrets"], 1)
        only = collecte.compute(self.decrees, classes=("A2", "R"))
        self.assertEqual([decree["notice"] for decree in only["decrets"]], ["D2", "D5"])
        self.assertEqual(only["filtre"]["classes"], ["A2", "R"])
        self.assertEqual(collecte.compute(self.decrees, years=(1800, 1810))["total"]["decrets"], 0)

    def test_birth_year_keeps_the_decrees_from_the_twenty_first_birthday(self) -> None:
        result = collecte.compute(self.decrees, born=1900)                       # from 1921 on
        self.assertEqual([decree["notice"] for decree in result["decrets"]], ["D4", "D5"])
        self.assertEqual((result["filtre"]["ne_en"], result["filtre"]["a_partir_de"]), (1900, 1921))
        self.assertIn("né en 1900", collecte.markdown(result, Path("x.json")))
        self.assertEqual(collecte.compute(self.decrees, born=1884)["total"]["decrets"], 5)    # 1905 = 1884 + 21 is kept
        self.assertEqual(collecte.compute(self.decrees, born=1885)["total"]["decrets"], 3)
        with self.assertRaises(collecte.PlanError):
            collecte.compute(self.decrees, born=1990)

    def test_option_parsing(self) -> None:
        self.assertEqual(collecte.parse_years("1899-1912"), (1899, 1912))
        self.assertEqual(collecte.parse_years("1928"), (1928, 1928))
        self.assertIsNone(collecte.parse_years(None))
        self.assertEqual(collecte.parse_classes("a1, r"), ("A1", "R"))
        self.assertEqual(collecte.parse_classes(None), collecte.CLASSES)
        for bad in ("abc", "1912-1899"):
            with self.assertRaises(collecte.PlanError):
                collecte.parse_years(bad)
        with self.assertRaises(collecte.PlanError):
            collecte.parse_classes("A1,Z9")
        with self.assertRaises(collecte.PlanError):
            collecte.compute(self.decrees, pages_per_decree=0)
        with self.assertRaises(collecte.PlanError):
            collecte.compute(self.decrees, delay=0)

    def test_markdown_states_that_nothing_is_measured_and_no_collector_exists(self) -> None:
        result = collecte.compute(self.decrees)
        text = collecte.markdown(result, Path("site/data/an-decrets.json"))
        self.assertIn("pas un collecteur", text)
        self.assertEqual(text.count("NON MESURÉ"), 2)
        self.assertIn("| 1899-1912 | 2 |", text)
        self.assertIn("| 1905 | 1 | 0 | 0 | 1 | 2 |", text)
        csv_text = collecte.decrees_csv(result)
        self.assertEqual(csv_text.splitlines()[0], "inv,notice,date,annee,classe,famille,cote,doc,titre")
        self.assertIn("FRAN_IR_000002,D5,1946-07-17,1946,A2,admission-citoyen,BB/34/002,,Décret fictif E", csv_text)

    def test_unusable_inputs_give_a_french_reason(self) -> None:
        base = Path(self.directory.name)
        with self.assertRaises(collecte.PlanError) as caught:
            collecte.load_decrees(base / "absent.json")
        self.assertIn("decretas.an construire", str(caught.exception))
        (base / "casse.json").write_text("{", encoding="utf-8")
        with self.assertRaises(collecte.PlanError):
            collecte.load_decrees(base / "casse.json")
        (base / "autre.json").write_text(json.dumps({"lignes": [[1]]}), encoding="utf-8")
        with self.assertRaises(collecte.PlanError) as caught:
            collecte.load_decrees(base / "autre.json")
        self.assertIn("format", str(caught.exception))


class MediaAnchorsTest(unittest.TestCase):
    """The indirect measure drawn from the media identifiers of the XML exports (synthetic list of decrees)."""

    HEADER = "annee,date,titre,cote,personnes_indexees,inventaire,notice_id,lien_notice,lien_images\n"

    def csv_file(self, directory: Path, lines: list[str]) -> Path:
        path = directory / "an-decrets.csv"
        path.write_text("\ufeff" + self.HEADER + "".join(lines), encoding="utf-8")
        return path

    def line(self, date: str, notice: str, persons: int, media: str = "") -> str:
        return (f"{date[:4]},{date},Décret fictif,BB/34/000,{persons},FRAN_IR_000001,{notice},"
                f"http://exemple.invalid/siv/UD/FRAN_IR_000001/{notice},http://exemple.invalid/siv/media/FRAN_IR_000001/{notice}/{media}\n")

    def test_gap_between_two_identifiers_divided_by_the_decrees_between_them(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            lines = [self.line("1890-01-01", "D0", 5),                                    # before the first anchor
                     self.line("1890-02-01", "D1", 10, "LOTX94_NUMJ000100_D"),
                     self.line("1890-03-01", "D2", 20), self.line("1890-04-01", "D3", 0), self.line("1890-05-01", "D4", 10),
                     self.line("1890-06-01", "D5", 3, "LOTX94_NUMJ000140_D"),
                     self.line("1890-07-01", "D6", 1), self.line("", "D7", 1),              # undated: counted nowhere
                     self.line("1890-08-01", "D8", 2, "LOTX94_NUMJ000150_D")]
            anchors = collecte.media_anchors(self.csv_file(Path(directory), lines))
        self.assertEqual([anchor["numero"] for anchor in anchors["reperes"]], [100, 140, 150])
        self.assertTrue(anchors["croissant_avec_la_date"])
        first, second = anchors["intervalles"]
        self.assertEqual((first["ecart_numeros"], first["decrets"], first["numeros_par_decret"]), (40, 4, 10.0))
        self.assertEqual(first["personnes_saisies_par_numero"], 1.0)                      # 40 persons keyed for 40 numbers
        self.assertEqual((second["ecart_numeros"], second["decrets"], second["numeros_par_decret"]), (10, 2, 5.0))
        self.assertEqual(anchors["ensemble"]["numeros_par_decret"], round(50 / 6, 1))
        self.assertEqual(anchors["avant_le_premier_repere"]["decrets"], 1)
        self.assertIn("HYPOTHÈSE non vérifiée", anchors["hypothese"])
        text = "\n".join(collecte.anchors_markdown(anchors, Path("x.csv")))
        self.assertIn("`LOTX94_NUMJ000140_D`", text)
        self.assertIn("Elles ne le remplacent pas", text)

    def test_numbers_that_do_not_grow_with_the_date_are_said(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            lines = [self.line("1890-02-01", "D1", 1, "LOTX94_NUMJ000900_D"), self.line("1890-03-01", "D2", 1),
                     self.line("1890-06-01", "D5", 1, "LOTX94_NUMJ000140_D")]
            anchors = collecte.media_anchors(self.csv_file(Path(directory), lines))
        self.assertFalse(anchors["croissant_avec_la_date"])
        self.assertIsNone(anchors["intervalles"][0]["numeros_par_decret"])                # no average from a negative gap
        self.assertIn("NON — l'hypothèse tombe", "\n".join(collecte.anchors_markdown(anchors, Path("x.csv"))))

    def test_absent_file_or_too_few_identifiers_give_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            self.assertIsNone(collecte.media_anchors(Path(directory) / "absent.csv"))
            one = self.csv_file(Path(directory), [self.line("1890-02-01", "D1", 1, "LOTX94_NUMJ000900_D"), self.line("1890-03-01", "D2", 1)])
            self.assertIsNone(collecte.media_anchors(one))
        text = "\n".join(collecte.anchors_markdown(None, Path("data/build/an-decrets.csv")))
        self.assertIn("Non calculé", text)
        self.assertIn("decretas.an decrets --csv", text)


if __name__ == "__main__":
    unittest.main()
