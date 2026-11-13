"""Dates as the OCR gives them: reading, repair of the digit 1 read 4, sanity checks."""
from __future__ import annotations

import datetime
import unittest

from decretas.bogga import dates, livraisons


def isos(text: str, **kwargs) -> list[str | None]:
    return [found.iso() for found in dates.find_dates(text, **kwargs)]


class FindDatesTestCase(unittest.TestCase):
    def test_plain_date(self) -> None:
        self.assertEqual(isos("Par décret du 8 mai 1873, contresigné"), ["1873-05-08"])

    def test_month_damaged_by_ocr(self) -> None:
        self.assertEqual(isos("du 8 moi 1873"), ["1873-05-08"])
        self.assertEqual(isos("ARRÊTÉ DU 15 ocToBrE 1873."), ["1873-10-15"])

    def test_ordinary_words_are_not_months(self) -> None:
        self.assertEqual(isos("les 12 mais 1873"), [])
        self.assertEqual(isos("au nombre de 37 personnes 1873"), [])

    def test_digit_one_read_as_four_is_repaired_and_reported(self) -> None:
        found = dates.find_dates("le 45 décembre 4873")[0]
        self.assertEqual(found.iso(), "1873-12-15")
        self.assertTrue(found.repaired)
        self.assertEqual(found.raw, "45 décembre 4873")

    def test_a_possible_four_is_left_as_read(self) -> None:
        found = dates.find_dates("du 4 avril 1874")[0]
        self.assertEqual((found.iso(), found.repaired), ("1874-04-04", False))

    def test_first_of_month_read_as_44(self) -> None:
        self.assertEqual(isos("né le 4° août 1866"), ["1866-08-01"])

    def test_two_days_one_month(self) -> None:
        self.assertEqual(isos("des 5 et 16 décembre 1872, contresignés"), ["1872-12-05", "1872-12-16"])

    def test_two_days_two_months(self) -> None:
        self.assertEqual(isos("des 30 mars et 7 avril 1873,"), ["1873-03-30", "1873-04-07"])

    def test_three_days(self) -> None:
        self.assertEqual(isos("des 3, 12 et 25 juin 1880"), ["1880-06-03", "1880-06-12", "1880-06-25"])

    def test_year_glued_to_month(self) -> None:
        self.assertEqual(isos("Alger, le 23 octobre1873."), ["1873-10-23"])

    def test_unreadable_day_keeps_the_month_and_year(self) -> None:
        found = dates.find_dates("le ?6 février 1888")[0]
        self.assertEqual((found.day, found.month, found.year), (None, 2, 1888))
        self.assertIsNone(found.iso())

    def test_impossible_year_is_not_invented(self) -> None:
        found = dates.find_dates("du 24 mai 1573")[0]
        self.assertIsNone(found.year)

    def test_relative_date(self) -> None:
        found = dates.find_dates("du 10 novembre dernier, rendus")[0]
        self.assertTrue(found.relative)
        self.assertIsNone(found.iso())

    def test_year_with_a_doubled_first_digit(self) -> None:
        # regression: « 27 février 41879 », « 5 mars 14874 » gave no date at all
        for text, iso in (("en date du 27 février 41879, contresigné", "1879-02-27"),
                          ("des 12 février et 5 mars 14874,", "1874-03-05"),
                          ("DÉCRET DU 5 FÉVRIER 41884", "1884-02-05")):
            with self.subTest(text=text):
                found = dates.find_dates(text)[-1]
                self.assertEqual((found.iso(), found.repaired), (iso, True))
        self.assertIsNone(dates.find_dates("du 10 septembre 18892, contre-signé", allow_bare=True)[0].year)

    def test_first_of_month_with_a_damaged_ordinal(self) -> None:
        # regression: « 1“ juillet 1884 » and « 4* août 1881 » were unreadable
        self.assertEqual(isos("Décret du 1“ juillet 1884"), ["1884-07-01"])
        self.assertEqual(isos("Décret du 1” juillet 1884"), ["1884-07-01"])
        found = dates.find_dates("Par décret Présidentiel du 4* août 1881, contresigné")[0]
        self.assertEqual((found.iso(), found.repaired), ("1881-08-01", True))
        self.assertEqual(isos("née le 4°° septembre 1859 à Oran"), ["1859-09-01"])

    def test_day_44_is_ambiguous(self) -> None:
        found = dates.find_dates("en date du 44 mai 1877, rendus")[0]
        self.assertEqual((found.iso(), found.repaired, found.ambiguous), ("1877-05-14", True, True))
        self.assertFalse(dates.find_dates("du 45 mai 1877")[0].ambiguous)
        self.assertFalse(dates.find_dates("du 14 mai 1877")[0].ambiguous)

    def test_damaged_day_keeps_month_and_year_and_the_raw_text(self) -> None:
        # regression: such a heading was exported with an empty `date_brute`
        for text, raw in (("Par décrets présidentiels en date du 2t octobre 1876, rendus", "2t octobre 1876"),
                          ("Par décret présidentiel, en date duM16 juin 4880, contresigné", "M16 juin 4880"),
                          ("Par décret présidentiel du % février 1885, contresigné", "% février 1885")):
            with self.subTest(text=text):
                found = dates.find_damaged_date(text)
                self.assertIsNotNone(found)
                self.assertEqual((found.day, found.raw), (None, raw))
                self.assertIsNone(found.iso())
        self.assertEqual(dates.find_damaged_date("du 2t octobre 1876").year, 1876)
        self.assertIsNone(dates.find_damaged_date("du Sénatus-Consulte du #4 juillet 1865, ont été admis"))

    def test_bare_day_and_month_only_on_request(self) -> None:
        self.assertEqual(dates.find_dates("Décret du 14 décembre"), [])
        found = dates.find_dates("Décret du 14 décembre", allow_bare=True)[0]
        self.assertEqual((found.day, found.month, found.year), (14, 12, None))


class SettleYearTestCase(unittest.TestCase):
    ISSUE = datetime.date(1873, 10, 23)

    def settle(self, text: str, **kwargs):
        found = dates.find_dates(text, **kwargs)[0]
        settled, state = dates.settle_year(found, self.ISSUE)
        return settled.iso(), state

    def test_clean_date_before_its_issue(self) -> None:
        self.assertEqual(self.settle("du 8 mai 1873"), ("1873-05-08", dates.READ))

    def test_repaired_digit_is_flagged(self) -> None:
        self.assertEqual(self.settle("du 45 avril 4873"), ("1873-04-15", dates.REPAIRED))

    def test_unreadable_year_is_re_established_from_the_issue(self) -> None:
        self.assertEqual(self.settle("du 24 mai 1573"), ("1873-05-24", dates.REPAIRED))

    def test_decree_dated_after_its_own_issue_is_corrected_not_trusted(self) -> None:
        self.assertEqual(self.settle("du 15 octobre 1874"), ("1873-10-15", dates.REPAIRED))

    def test_relative_date_takes_the_year_before_when_needed(self) -> None:
        found = dates.find_dates("du 10 novembre dernier")[0]
        settled, state = dates.settle_year(found, datetime.date(1867, 1, 15))
        self.assertEqual((settled.iso(), state), ("1866-11-10", dates.REPAIRED))

    def test_old_decree_is_kept_but_suspect(self) -> None:
        self.assertEqual(self.settle("du 8 mai 1870"), ("1870-05-08", dates.SUSPECT))

    def test_bulk_publication_of_old_decrees_can_be_allowed(self) -> None:
        found = dates.find_dates("du 30 novembre 1871")[0]
        settled, state = dates.settle_year(found, self.ISSUE, max_delay_days=1100)
        self.assertEqual((settled.iso(), state), ("1871-11-30", dates.READ))

    def test_unreadable_day_is_suspect(self) -> None:
        found = dates.find_dates("du ?6 mai 1873")[0]
        self.assertEqual(dates.settle_year(found, self.ISSUE)[1], dates.SUSPECT)

    def test_ambiguous_day_is_suspect_even_when_it_fits(self) -> None:
        self.assertEqual(self.settle("du 44 mai 1873"), ("1873-05-14", dates.SUSPECT))

    def test_year_after_the_volume_is_pulled_back_when_no_issue_date_can_settle_it(self) -> None:
        # regression: « 31 août 1884 » in the 1881 volume was exported as 1884-08-31
        found = dates.find_dates("Par décret Présidentiel du 31 août 1884, contresigné")[0]
        self.assertEqual(dates.pull_back_into_volume(found, 1881).iso(), "1881-08-31")
        same = dates.find_dates("du 31 août 1880")[0]
        self.assertIs(dates.pull_back_into_volume(same, 1881), same)

    def test_without_issue_only_the_year_range_is_checked(self) -> None:
        self.assertEqual(dates.state_without_issue(dates.find_dates("du 8 mai 1873")[0], 1873), dates.READ)
        self.assertEqual(dates.state_without_issue(dates.find_dates("du 8 mai 1860")[0], 1873), dates.SUSPECT)


class IssueDatesTestCase(unittest.TestCase):
    def settle(self, raws: list[str], year: int = 1888):
        return [(date.isoformat() if date else None, state) for date, state in livraisons.settle_issue_dates(raws, year)]

    def test_clean_increasing_dates(self) -> None:
        got = self.settle(["Alger, le 9 février 1888.", "Alger, le 18 février 1888.", "Alger, le 28 février 1888."])
        self.assertEqual(got, [("1888-02-09", 0), ("1888-02-18", 0), ("1888-02-28", 0)])

    def test_unreadable_day_is_repaired_only_when_one_reading_fits(self) -> None:
        got = self.settle(["Alger, le 18 février 1888.", "Alger, le ?6 février 1888.", "Alger, le 28 février 1888."])
        self.assertEqual(got[1], ("1888-02-26", dates.REPAIRED))

    def test_ambiguous_day_is_left_empty_and_suspect(self) -> None:
        got = self.settle(["Alger, le 2 février 1888.", "Alger, le ?6 février 1888.", "Alger, le 28 février 1888."])
        self.assertEqual(got[1], (None, dates.SUSPECT))

    def test_date_going_backwards_is_not_published(self) -> None:
        got = self.settle(["Alger, le 10 mars 1888.", "Alger, le 20 mars 1888.", "Alger, le 6 mars 1888.",
                           "Alger, le 30 mars 1888.", "Alger, le 5 avril 1888."])
        self.assertEqual(got[2], (None, dates.SUSPECT))
        self.assertEqual([state for _d, state in got if state == dates.SUSPECT], [dates.SUSPECT])

    def test_one_read_as_four_breaking_the_order_is_repaired(self) -> None:
        got = self.settle(["Alger, le 10 mars 1888.", "Alger, le 49 mars 1888.", "Alger, le 20 mars 1888."])
        self.assertEqual(got[1], ("1888-03-19", dates.REPAIRED))

    def test_day_44_is_published_as_repaired_only_when_one_of_11_and_14_fits(self) -> None:
        # regression: '44' was always given as 14 with the state « repaired », although 11 is as likely
        one_choice = self.settle(["Alger, le 12 mars 1888.", "Alger, le 44 mars 1888.", "Alger, le 20 mars 1888."])
        self.assertEqual(one_choice[1], ("1888-03-14", dates.REPAIRED))
        two_choices = self.settle(["Alger, le 10 mars 1888.", "Alger, le 44 mars 1888.", "Alger, le 20 mars 1888."])
        self.assertEqual(two_choices[1], ("1888-03-14", dates.SUSPECT))

    def test_impossible_day_ending_in_4_is_first_read_as_ending_in_1(self) -> None:
        # regression: « le 34 juillet » between 20 July and 10 August was published as 24 July; 31 is one misread away
        got = self.settle(["Alger, le 20 juillet 1875.", "Alger, le 34 juillet 1875.", "Alger, le 10 août 1875."], 1875)
        self.assertEqual(got[1], ("1875-07-31", dates.REPAIRED))
        got = self.settle(["Alger, le 2 juin 1869.", "Alger, le 39 juin 1869.", "Alger, le 30 juin 1869."], 1869)
        self.assertEqual(got[1], (None, dates.SUSPECT))                 # 9, 19 or 29: not decided

    def test_damaged_year_is_taken_from_the_volume(self) -> None:
        got = self.settle(["Alger, le 10 juin 1888.", "Alger, le 16 juin 188$", "Alger, le 30 juin 1888."])
        self.assertEqual(got[1], ("1888-06-16", dates.REPAIRED))

    def test_year_outside_the_volume_is_rejected(self) -> None:
        got = self.settle(["Alger, le 10 juin 1888.", "Alger, le 16 juin 1884.", "Alger, le 30 juin 1888."])
        self.assertEqual(got[1], ("1888-06-16", dates.REPAIRED))


if __name__ == "__main__":
    unittest.main()
