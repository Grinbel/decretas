"""Issues of a volume: closing lines and title pages as the OCR damages them, and what
happens to the publication date when one of them is lost. Everything here is synthetic."""
from __future__ import annotations

import unittest

from decretas.bogga import controle, dates, livraisons, segmentation as S
from tests.bogga.fabrique import closing, make_pages, title_page

SC = "conformément aux dispositions du sénatus-consulte du 14 juillet 1865"


def heading(date: str) -> str:
    return (f"Par décret présidentiel du {date}, contresigné par le Ministre de la Justice, ont été admises à jouir des "
            f"droits de citoyen français, {SC}, les personnes ci-après désignées :")


class ClosingLineTestCase(unittest.TestCase):
    def test_closing_lines_damaged_by_the_ocr_are_recognised(self) -> None:
        # regression: 88 closing lines of the real volumes were missed by the strict pattern,
        # and the decrees of those issues were given the date of the following issue
        for text in ("CERTIFIÉ CONFORME : Alger, le 23 octobre 1873.",
                     "demeurant à Val-Fictif. CanTIFIÉ CONFORME : Alger, le 25 février 1879. * Le Chef du 1er Bureau",
                     "CBBTIFIÉ CONFORME .' Alger, le 42 février 4872. Le Directeur général",
                     "OERTIFIÉ CONFORME Alger, le ?? septembre 1883.",
                     "CERTIFI# UONFORME Alger, le 30 septerabre 1883.",
                     "Certifia oonforme : Alger, le 6 juin 1876. * Le Chef de la section",
                     "Certifié  conforme  : Alger,  le  31  octobre  1872.",
                     "CERTIFIÉ CONFORME : alger, lc 40 janvier 1870.",
                     "CERTIFIÉ CONFORME : Aiger. [e 6 mai 1867.",
                     "CERTIFIÉ CONFORME: Alger, Le 19 Janvier 1861.",
                     "CERTIFIÉ CONFORME : NO Alger, le 3 août 1867.",
                     "CEnm RE CONFORE: Alger, le 10 novembre 1879.",
                     "CERRIFIÉ CONFORME:"):
            with self.subTest(text=text):
                self.assertIsNotNone(livraisons.find_closing(text))

    def test_the_offset_is_the_start_of_the_mark(self) -> None:
        text = "demeurant à Val-Fictif. CERTIFIÉ CONFORME : Alger, le 9 février 1888."
        self.assertEqual(livraisons.find_closing(text), text.index("CERTIFIÉ"))
        self.assertTrue(livraisons.closing_text(text).startswith("CERTIFIÉ CONFORME : Alger, le 9 février 1888"))

    def test_other_certifications_are_not_closing_lines(self) -> None:
        for text in ("Certifié conforme au cahier des charges annexé au décret en date du 3 décembre 1878.",
                     "Certifié conforme aux registres des réclamations",
                     "Certifié conforme : Val-Fictif, le 22 avril 1876. L'Administrateur,",
                     "Pour copie certifiée conforme : Alger, le 3 mai 1873.",
                     "Pour extrait certifié conforme",
                     "ont été admis à jouir des droits de citoyen français, conformément aux dispositions",
                     "CONFORMÉMENT aux dispositions : Alger, le 3 mai 1873"):
            with self.subTest(text=text):
                self.assertIsNone(livraisons.find_closing(text))


class TitlePageTestCase(unittest.TestCase):
    def test_masthead_damaged_by_the_ocr(self) -> None:
        for text in (title_page(1880, 784),
                     "— 281 — pu GOUVERNEMENT GÉNÉRAL DE L'ALGÉRIE ANNÉE 1880 5 LÀ. N° 784 SONINEAREIE SE, N° | DATES ANALYSE PAGES",
                     "BULEETINX OFFICIEL DU SOUVERNEMENT GÉNÉRAL DE L'ALGÉRIE ANNÉE 1884 SONNARAEMRE N° | DATES AKALYSE",
                     "97 BULLETIN OFFICIEL DU GOIVËRNËHËNT GÉNÉRAL DE L'ALGERIE N- 47 48 49 DATES 20 janv. 1876 ANALYSE"):
            with self.subTest(text=text[:40]):
                self.assertTrue(livraisons.is_issue_title_page(text))

    def test_pages_that_only_look_like_one(self) -> None:
        second_summary_page = ("— 526 — 317 318 319 DATES 31 oct 1879 4 nov. — Dates div. ANALYSE COMMERCE ET INDUSTRIE. — Service "
                               "des ports. — ARRÊTÉ GOUVERNEMENT GÉNÉRAL DE L'ALGÉRIE. — Le Directeur général est nommé Préfet.")
        chronological_table = ("TABLE CHRONOLOGIQUE DES LOIS, DÉCRETS ET ARRÊTÉS CONTENUS DANS LE TOME VINGTIÈME DU BULLETIN OFFICIEL "
                               "DU GOUVERNEMENT GÉNÉRAL DE L'ALGÉRIE ANNÉE 1880 DATES TITRES PAGES")
        for text in (second_summary_page, chronological_table, "— 12 —\nArrêté fictif du Gouverneur général."):
            with self.subTest(text=text[:40]):
                self.assertFalse(livraisons.is_issue_title_page(text))


class IssuesTestCase(unittest.TestCase):
    def test_lost_closing_line_never_lends_the_date_of_the_next_issue(self) -> None:
        # regression: with the closing of issue 501 unread, its decree was published « le 30 octobre »
        texts = [title_page(1873, 500), "Arrêté fictif.\n" + closing("6 octobre 1873"),
                 title_page(1873, 501), "N° 410. — " + heading("8 mai 1873") + "\n1. Fictietti (Aldo), italien, demeurant à Alger.\n"
                 "CxxxxxÉ CxxxxxxE : Axxxx, le 14 octobre 1873.",
                 title_page(1873, 502), "Arrêté fictif.\n" + closing("30 octobre 1873")]
        seg = S.segment_volume(make_pages(texts), 1873)
        self.assertEqual([(i.number, i.close_leaf) for i in seg.issues], [(500, 1), (501, 3), (502, 5)])
        self.assertEqual((seg.issues[1].date, seg.issues[1].date_state), (None, dates.SUSPECT))
        decree = seg.decrees[0]
        self.assertEqual(decree.issue.number, 501)
        self.assertIsNone(decree.issue.date)
        self.assertEqual(len(decree.entries), 1)

    def test_last_issue_without_closing_line_stops_before_the_tables(self) -> None:
        texts = [title_page(1873, 500), "Arrêté fictif.\n" + closing("6 octobre 1873"),
                 title_page(1873, 501), "Arrêté fictif sans fin lisible.",
                 "TABLE ALPHABÉTIQUE DES MATIÈRES\nNATURALISATION. — Admission, D. p. 2"]
        issues = livraisons.find_issues(make_pages(texts), 1873)
        self.assertEqual([(i.open_leaf, i.close_leaf, i.date) for i in issues][1], (2, 3, None))

    def test_a_bis_issue_shares_the_number_and_does_not_shift_the_count(self) -> None:
        # regression: « N° 764 » then « N° 764 Bis » made every following computed number one too high
        def issue(number: int, date: str, bis: bool = False, readable: bool = True) -> list[str]:
            page = title_page(1879, number)
            if bis:
                page = page.replace(f"N° {number}.", f"N° {number} Bis")
            if not readable:
                page = page.replace(f"N° {number}.", "N° %%")
            return [page, "Arrêté fictif.\n" + closing(date)]

        texts = (issue(764, "6 novembre 1879") + issue(764, "8 novembre 1879", bis=True)
                 + issue(765, "11 novembre 1879", readable=False) + issue(766, "20 novembre 1879"))
        issues = livraisons.find_issues(make_pages(texts), 1879)
        self.assertEqual([i.number for i in issues], [764, 764, 765, 766])
        self.assertEqual(issues[2].number_state, livraisons.NUMBER_COMPUTED)

    def test_a_single_number_read_in_a_volume_is_not_trusted(self) -> None:
        # regression: 1864 had one (misread) number and all its issues were numbered from it as « read / computed »
        texts: list[str] = []
        for k in range(6):
            page = title_page(1864, 102 + k)
            if k != 2:
                page = page.replace(f"N° {102 + k}.", "N- IIO")
            texts += [page, "Arrêté fictif.\n" + closing(f"{k + 1} mars 1864")]
        issues = livraisons.find_issues(make_pages(texts), 1864)
        self.assertEqual([i.number for i in issues], [102, 103, 104, 105, 106, 107])
        self.assertTrue(all(i.number_state == livraisons.NUMBER_UNCERTAIN for i in issues))

    def test_second_page_of_a_summary_does_not_open_an_issue(self) -> None:
        texts = [title_page(1879, 765), title_page(1879, 765), "Arrêté fictif.\n" + closing("11 novembre 1879")]
        issues = livraisons.find_issues(make_pages(texts), 1879)
        self.assertEqual([(i.open_leaf, i.close_leaf) for i in issues], [(0, 2)])


class TablesInsideTheBodyTestCase(unittest.TestCase):
    def test_tables_printed_before_a_supplement_are_not_read_as_lists(self) -> None:
        # regression risk of reading on after the last closing line (1870: tables, then « partie supplémentaire »)
        supplement = title_page(1870, 352).replace("ANNÉE 1870.", "(PARTIE SUPPLÉMENTAIRE)")
        texts = [title_page(1870, 351), "N° 410. — " + heading("8 mai 1870") + "\n1. Fictietti (Aldo), italien, demeurant à Alger.\n"
                 + closing("31 décembre 1870"),
                 "TABLE ANALYTIQUE DES MATIÈRES CONTENUES DANS CE VOLUME\nNATURALISATION. — Admission, D. p. 2\n"
                 "Par décret impérial, ont été admis à jouir des droits de citoyen français, p. 2 :\n"
                 "Exemplino (Ugo), italien, demeurant à Alger.",
                 supplement, "Arrêté fictif sur la propriété."]
        pages = make_pages(texts)
        seg = S.segment_volume(pages, 1870)
        self.assertEqual(seg.table_leaves, [2])
        self.assertEqual([len(decree.entries) for decree in seg.decrees], [1])
        self.assertEqual(controle.read_table(pages, seg.body_first_leaf, seg.issues[-1].close_leaf,
                                               frozenset(seg.table_leaves)).consistent, [2])


if __name__ == "__main__":
    unittest.main()
