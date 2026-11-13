import unittest

from decretas.an import dates
from decretas.an.text import fold


class FindDateTest(unittest.TestCase):
    def find(self, text: str) -> tuple[str, str] | None:
        match = dates.find_date(fold(text))
        return (match.iso, match.precision) if match else None

    def test_day_month_year(self) -> None:
        self.assertEqual(self.find("6 février 1842 (Strasbourg, Bas-Rhin)"), ("1842-02-06", "jour"))
        self.assertEqual(self.find("1er août 1887"), ("1887-08-01", "jour"))
        self.assertEqual(self.find("1 er décembre 1925"), ("1925-12-01", "jour"))

    def test_month_glued_to_the_year_or_to_the_day(self) -> None:
        self.assertEqual(self.find("21 juin1846, Fictiveville"), ("1846-06-21", "jour"))
        self.assertEqual(self.find("du 11août 1907."), ("1907-08-11", "jour"))
        self.assertEqual(self.find("9 avril1 1861, Fictiveville"), ("1861-04-09", "jour"))

    def test_misspelt_months(self) -> None:
        self.assertEqual(self.find("11 mail 1919"), ("1919-05-11", "jour"))
        self.assertEqual(self.find("10 octobres 1928"), ("1928-10-10", "jour"))
        self.assertEqual(self.find("16 juilet 1934"), ("1934-07-16", "jour"))
        self.assertEqual(self.find("3 janiver 1890"), ("1890-01-03", "jour"))
        self.assertEqual(self.find("23 mais 1866"), ("1866-05-23", "jour"))

    def test_june_and_july_are_told_apart(self) -> None:
        self.assertEqual(self.find("4 juin 1894"), ("1894-06-04", "jour"))
        self.assertEqual(self.find("4 juillet 1896"), ("1896-07-04", "jour"))

    def test_numeric_month_and_year_forms(self) -> None:
        self.assertEqual(self.find("25/08/1906 (Paris)"), ("1906-08-25", "jour"))
        self.assertEqual(self.find("mars 1858, à Fictiveville"), ("1858-03", "mois"))
        self.assertEqual(self.find("en 1856, Fictiveville"), ("1856", "annee"))

    def test_no_date(self) -> None:
        self.assertIsNone(self.find("non précisé."))
        self.assertIsNone(self.find("du 9 avril 188"))

    def test_first_date_wins(self) -> None:
        self.assertEqual(self.find("18 octobre 1842 [8 octobre 1842]"), ("1842-10-18", "jour"))

    def test_full_dates_lists_every_complete_date(self) -> None:
        title = "Décret du 30 juin 1925 modifiant le décret sur la nationalité du 13 août 1889"
        self.assertEqual(dates.full_dates(title), ["1925-06-30", "1889-08-13"])
        self.assertFalse(dates.has_full_date("Testaoui, Amar ben Exemple"))


class ReconcileDecreeDateTest(unittest.TestCase):
    def test_agreement(self) -> None:
        result = dates.reconcile_decree_date("1919-11-04", "4 novembre 1919", "Décret du 4 novembre 1919.", 1919)
        self.assertEqual((result.iso, result.flag, result.year), ("1919-11-04", "", 1919))

    def test_truncated_title_is_not_a_conflict(self) -> None:
        result = dates.reconcile_decree_date("1888-04-09", "9 avril 1888", "Décret du 9 avril 188", 1888)
        self.assertEqual((result.iso, result.flag), ("1888-04-09", ""))

    def test_second_date_of_the_title_is_not_a_conflict(self) -> None:
        title = "Décret de naturalisations du 29 juillet 1922. (Le décret est daté par erreur du 29 juillet 1926)."
        self.assertEqual(dates.reconcile_decree_date("1922-07-29", "29 juillet 1922", title, 1922).flag, "")

    def test_title_wins_when_only_it_falls_in_the_inventory_year(self) -> None:
        # August 1933: every @normal of the month says 1938.
        result = dates.reconcile_decree_date("1938-08-02", "2 août 1933", "Décret du 2 août 1933", 1933)
        self.assertEqual((result.iso, result.flag, result.year), ("1933-08-02", "conflit-titre-retenu", 1933))

    def test_title_wins_when_the_unitdate_text_repeats_it(self) -> None:
        result = dates.reconcile_decree_date("1896-01-04", "4 juillet 1896", "Décret du 4 juillet 1896", 1896)
        self.assertEqual((result.iso, result.flag), ("1896-07-04", "conflit-titre-retenu"))

    def test_normal_is_kept_and_flagged_when_nothing_decides(self) -> None:
        result = dates.reconcile_decree_date("1898-04-23", "23 avril 1898", "Décret du 30 avril 1898", 1898)
        self.assertEqual((result.iso, result.flag, result.title_date), ("1898-04-23", "conflit-normal-retenu", "1898-04-30"))

    def test_title_year_outside_the_inventory_does_not_win(self) -> None:
        result = dates.reconcile_decree_date("1912-10-26", "26 octobre 1912", "Arrêté du 26 octobre 1920.", 1912)
        self.assertEqual((result.iso, result.flag), ("1912-10-26", "conflit-normal-retenu"))

    def test_interval(self) -> None:
        result = dates.reconcile_decree_date("1934-01-01 / 1934-12-31", "1934", "Arrêtés et décrets divers de 1934", 1934)
        self.assertEqual((result.iso, result.flag, result.year), (None, "intervalle", 1934))

    def test_title_only_and_no_date(self) -> None:
        result = dates.reconcile_decree_date(None, "", "Décret d’admissions à domicile du 7 avril 1891", 1891)
        self.assertEqual((result.iso, result.flag), ("1891-04-07", "titre-seul"))
        result = dates.reconcile_decree_date(None, "", "Décrets divers", 1891)
        self.assertEqual((result.iso, result.flag, result.year), (None, "sans-date", None))

    def test_year_outside_the_inventory_is_flagged(self) -> None:
        result = dates.reconcile_decree_date("1920-10-26", "26 octobre 1920", "Arrêté du 26 octobre 1920.", 1912)
        self.assertEqual((result.iso, result.flag), ("1920-10-26", "hors-inventaire"))


if __name__ == "__main__":
    unittest.main()
