"""Loading a volume from its three files, and quality control against the volume's own table."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from decretas.bogga import controle, segmentation as S, volume
from tests.bogga.fabrique import make_pages, one_issue, write_volume_files

SC = "conformément aux dispositions du sénatus-consulte du 14 juillet 1865"
HEADING = ("Par décret présidentiel du 8 mai 1873, contresigné par le Ministre de la Justice, ont été admises à jouir des droits "
           "de citoyen français, " + SC + ", les personnes ci-après désignées :")


class LoadVolumeTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def load(self, doc: str) -> list[volume.Page]:
        return volume.load_volume(self.root / f"{doc}_hocr_searchtext.txt.gz", self.root / f"{doc}_hocr_pageindex.json.gz",
                                  self.root / f"{doc}_page_numbers.json")

    def test_format_version_2(self) -> None:
        texts = ["titre", "page été à\ndeux lignes", "troisième"]
        write_volume_files(self.root, "vol", texts, {1: "1", 2: "2"})
        pages = self.load("vol")
        self.assertEqual([page.text for page in pages], texts)                # offsets count characters, not bytes
        self.assertEqual([page.printed for page in pages], [None, 1, 2])
        self.assertEqual(pages[1].lines, ["page été à", "deux lignes"])

    def test_older_format_numbers_leaves_from_one(self) -> None:
        write_volume_files(self.root, "vol", ["couverture", "a", "b"], {1: "7", 2: "8"}, version2=False)
        self.assertEqual([page.printed for page in self.load("vol")], [None, 7, 8])

    def test_unreadable_file_is_a_clear_error(self) -> None:
        write_volume_files(self.root, "vol", ["a"], {})
        (self.root / "vol_hocr_pageindex.json.gz").write_bytes(b"pas du gzip")
        with self.assertRaises(volume.VolumeFormatError):
            self.load("vol")

    def test_page_number_at_odds_with_its_neighbours_is_recomputed_and_flagged(self) -> None:
        raw = {leaf: str(leaf - 3) for leaf in range(4, 30)}
        raw[10] = "0695"            # misread by the page-number detector
        raw[20] = ""                # not detected at all
        result = volume.reconcile_page_numbers(raw, 30)
        self.assertEqual(result[10], (7, True))
        self.assertEqual(result[20], (17, True))
        self.assertEqual(result[11], (8, False))
        self.assertEqual(result[0], (None, False))

    def test_page_mapping_summary(self) -> None:
        summary = volume.page_mapping_summary(make_pages(["a", "b", "c", "d"], first_printed=1, unnumbered=1))
        self.assertEqual((summary["feuilles"], summary["pages_numerotees"], summary["decalage_dominant"]), (4, 3, 0))


class TableTestCase(unittest.TestCase):
    def read(self, text: str, max_page: int = 1300) -> controle.TableReading:
        return controle._read_numbers(text, max_page)

    def test_1873_style(self) -> None:
        reading = self.read("NATURALISATION. — Admission de divers étrangers et indigènes à jouir des droits de citoyen "
                            "français, D. p. 109, 285, 349, 447, 494, 504, 505 et 506, 605 et 606, 622, 649 et 650")
        self.assertEqual(reading.consistent, [109, 285, 349, 447, 494, 504, 505, 506, 605, 606, 622, 649, 650])
        self.assertEqual((reading.doubtful, reading.unreadable), ([], 0))

    def test_1888_style_with_ocr_damage(self) -> None:
        reading = self.read("NATURALISATION : Décrets : 27%, 60, 89, 116, 40) 645, 692, 517, 350, T2, 851, 4009, 1057 4103, 1933")
        self.assertEqual(reading.consistent, [60, 89, 116, 645, 692, 851, 1009, 1057, 1103])   # 4009 -> 1009
        self.assertEqual(reading.doubtful, [40, 517, 350, 1933])                               # out of order or range
        self.assertEqual(reading.unreadable, 2)

    def test_other_sub_entries_and_dates_are_ignored(self) -> None:
        reading = self.read("NATURALISATION. Règlement d'administration publique pour l'exécution du Sénatus-Consulte du "
                            "14 juillet 1865, D., p. 144, 149. — Admission de deux indigènes à jouir des droits de citoyen "
                            "français, D., p. 679. — Admission de trois indigènes, D., p. 680.")
        self.assertEqual(reading.consistent, [679, 680])

    def test_nominative_table_is_recognised_as_such(self) -> None:
        reading = self.read("NATURALISATIONS (suite).—Sont déclarés naturalisés français: Fictedo (François), cultivateur ...., 195")
        self.assertTrue(reading.nominative)
        self.assertEqual(reading.consistent, [])

    def test_summary_line_with_dotted_leader_is_not_the_table(self) -> None:
        pages = make_pages(["— Naturalisation..... 676\nà\n680", "corps"]) + []
        self.assertIsNone(controle.read_table(pages, 1, 1).leaf)


class ControlVolumeTestCase(unittest.TestCase):
    def volume(self, table: str) -> tuple[S.Segmentation, list[volume.Page]]:
        body = [
            "N° 350. — NATURALISATION.\n" + HEADING.replace("les personnes", "les 3 personnes")
            + "\n1. Fictivo (Aldo), badois, demeurant à Val-Fictif.\n2. Testaoui ben Exemple, indigène musulman, demeurant à Blida.",
            "N° 380. — NATURALISATION.\n" + HEADING.replace("8 mai", "9 juin")
            + "\n1. Modelo (Jean), italien, demeurant à Oran.\n2. Essaimann (Paul), badois, demeurant à Oran.",
            "N° 390. — MILICES.\nArrêté fictif portant nomination.",
            "N° 391. — PÊCHE.\nArrêté fictif.",
        ]
        pages = one_issue(1873, body, closing_date="23 octobre 1873")
        pages = pages + make_pages(["TABLE ALPHABÉTIQUE\nMINES. — Recherches, A. p. 7.\n" + table + "\nPÊCHE. — Voir : Marine."])
        last = pages[-1]
        pages[-1] = volume.Page(leaf=len(pages) - 1, printed=None, printed_raw="", computed=False, text=last.text)
        return S.segment_volume(pages, 1873), pages

    def test_pages_of_the_table_found_and_missed(self) -> None:
        seg, pages = self.volume("NATURALISATION. — Admission de divers étrangers à jouir des droits de citoyen français, D. p. 2, 3")
        record = controle.control_volume(seg, pages)
        table = record["table_alphabetique"]
        self.assertTrue(table["trouvee"])
        self.assertEqual((table["pages_listees_lisibles"], table["pages_retrouvees"], table["taux_pages"]), (2, 2, 1.0))
        self.assertEqual(table["pages_non_retrouvees"], [])

    def test_a_listed_page_without_decree_lowers_the_rate(self) -> None:
        seg, pages = self.volume("NATURALISATION. — Admission de divers étrangers, D. p. 3, 5")
        table = controle.control_volume(seg, pages)["table_alphabetique"]
        self.assertEqual(table["pages_non_retrouvees"], [5])
        self.assertEqual(table["taux_pages"], 0.5)

    def test_title_at_the_foot_of_the_previous_page_counts_as_found(self) -> None:
        seg, pages = self.volume("NATURALISATION. — Admission de divers étrangers, D. p. 2, 3")
        seg.decrees[1].leaf = seg.decrees[1].last_leaf = 2
        seg.decrees[0].leaf = seg.decrees[0].last_leaf = 2             # nothing on leaf 1 (page 2) any more
        table = controle.control_volume(seg, pages)["table_alphabetique"]
        self.assertEqual((table["pages_retrouvees"], table["dont_a_la_page_suivante"]), (2, 1))

    def test_one_read_as_four_in_the_table_is_tolerated_and_counted(self) -> None:
        seg, pages = self.volume("NATURALISATION. — Admission de divers étrangers, D. p. 2, 3")
        seg.decrees[0].leaf = seg.decrees[0].last_leaf = 1
        shifted = [volume.Page(p.leaf, 671 if p.leaf == 1 else (674 if p.leaf == 2 else p.printed), "", False, p.text) for p in pages]
        seg.decrees[1].leaf = seg.decrees[1].last_leaf = 1
        table = controle.control_volume(seg, [volume.Page(p.leaf, p.printed, "", False, p.text.replace("p. 2, 3", "p. 674"))
                                             for p in shifted])["table_alphabetique"]
        self.assertEqual((table["pages_listees_lisibles"], table["pages_retrouvees"], table["dont_avec_confusion_1_4"]), (1, 1, 1))

    def test_announced_totals_and_numbered_lists(self) -> None:
        seg, pages = self.volume("NATURALISATION. — Admission, D. p. 2, 3")
        lists = controle.control_volume(seg, pages)["listes_numerotees"]
        # first decree announces 3 persons and 2 were found; second has a numbered list ending at 2
        self.assertEqual((lists["decrets_avec_total_imprime"], lists["personnes_annoncees"], lists["entrees_trouvees"]), (2, 5, 4))
        self.assertEqual(lists["taux_entrees"], 0.8)

    def test_more_entries_than_announced_never_inflates_the_rate(self) -> None:
        seg, pages = self.volume("NATURALISATION. — Admission, D. p. 2, 3")
        seg.decrees[1].announced = 1
        seg.decrees[1].last_number = None
        lists = controle.control_volume(seg, pages)["listes_numerotees"]
        self.assertEqual((lists["personnes_annoncees"], lists["entrees_trouvees"]), (4, 3))
        self.assertEqual(lists["decrets_avec_plus_d_entrees_que_le_total"], 1)

    def test_volume_without_table(self) -> None:
        seg, pages = self.volume("NAVIGATION. — Voir : Commerce.")
        table = controle.control_volume(seg, pages)["table_alphabetique"]
        self.assertFalse(table["trouvee"])
        self.assertIsNone(table["taux_pages"])


if __name__ == "__main__":
    unittest.main()
