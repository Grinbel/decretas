import unittest

from decretas.an import taxonomy


class FamilyTest(unittest.TestCase):
    def test_families(self) -> None:
        cases = {
            "Décret de naturalisations algériennes du 13 janvier 1883.": "naturalisation",
            "Décret d'admissions à domicile du 12 octobre 1913.": "admission-domicile",
            "Décret de réintégrations d'Alsaciens-Lorrains du 12 octobre 1913.": "reintegration",
            "Décret de naturalisations et de réintégrations françaises (Algérie) du 2 août 1933": "naturalisation+reintegration",
            "Décret d’admission aux droits de citoyen français du 2 août 1933": "admission-citoyen",
            "Décret de naturalisations, réintégrations françaises et admission aux droits de citoyen français du 5 janvier 1944": "composite-avec-citoyen",
            "Décret de rejet de naturalisations en France et en Algérie du 6 février 1905.": "rejet",
            "Décret de révocation de naturalisation du 3 mars 1920": "revocation-retrait",
            "Décret rapportant un décret de naturalisation du 3 mars 1920": "revocation-retrait",
            "Décret d'autorisation de naturalisation à l'étranger du 13 novembre 1897": "autorisation-etranger",
            "Décret de naturalisations à l’étranger du 24 mai 1931": "autorisation-etranger",   # curly apostrophe
            "Décrets de libérations des liens d'allégeance du 21 mars 1941": "liberation-allegeance",
            "Arrêté d'investiture d'un titre du 18 août 1928": "titre-nom-dispense",
            "Décrets, arrêtés et rapports divers de 1931": "divers",
        }
        for title, family in cases.items():
            self.assertEqual(taxonomy.family_of(title), family, title)

    def test_title_is_never_tested_by_its_first_word(self) -> None:
        for title in ("écret de naturalisations algériennes du 5 septembre 1892",
                      "FDécret de naturalisations algériennes du 5 septembre 1892",
                      ">Décret de naturalisations algériennes du 5 septembre 1892",
                      "naturalisations algériennes du 13 juillet 1937"):
            self.assertEqual(taxonomy.classify_decree(title).algeria_class, "A1", title)

    def test_lost_title_is_a_rejection(self) -> None:
        title = "(concerne aussi des rejets de changements de noms et de dispense pour mariage)."
        self.assertEqual(taxonomy.classify_decree(title), taxonomy.DecreeClass("rejet", (), "-"))


class AlgeriaClassTest(unittest.TestCase):
    def test_classes(self) -> None:
        cases = {
            "Décret de naturalisations algériennes du 13 janvier 1883.": "A1",
            "Décret de naturalisations françaises (Algérie) du 13 août 1933": "A1",
            "Décret d'admission aux droits de citoyen français (Algérie) du 16 mars 1939": "A1",
            "Décret d'admission aux droits de citoyen français d'un indigène musulman algérien du 30 mars 1944": "A1",
            "Décret de réintégrations de femmes d'étrangers naturalisés français en Algérie, du 29 mars 1887": "A1",
            "Décret d’admission aux droits de citoyen français du 2 août 1933": "A2",
            "Décret d'admission aux droits de citoyen français (colonies) du 15 octobre 1931": "-",
            "Décret d’admission aux droits de citoyen français (Madagascar) du 6 avril 1933": "-",
            "Décret de naturalisations, réintégrations françaises et admission aux droits de citoyen français du 5 janvier 1944": "A3",
            "Décret de rejet de naturalisations en France et en Algérie du 6 février 1905.": "R",
            "Décret de révocation de naturalisation algérienne du 3 mars 1920": "R",
            "Décret de rejet de naturalisations en France du 6 février 1905.": "-",
            "Décret de naturalisations du 7 février 1905.": "-",
            "Décret de naturalisations tunisiennes du 29 juillet 1927": "-",
        }
        for title, expected in cases.items():
            self.assertEqual(taxonomy.classify_decree(title).algeria_class, expected, title)

    def test_territories(self) -> None:
        result = taxonomy.classify_decree("Décret de naturalisations algériennes et tunisiennes du 2 mai 1892")
        self.assertEqual(result.territories, ("algerie", "tunisie"))


class CoteTest(unittest.TestCase):
    def test_cote_is_read_from_either_unitid(self) -> None:
        self.assertEqual(taxonomy.check_cote("BB/34/387", ""), ("BB/34/387", "identifiant", "", ""))
        self.assertEqual(taxonomy.check_cote("", "19780549/461"), ("19780549/461", "cote-de-consultation", "", ""))

    def test_suspicious_cote_is_flagged_never_replaced(self) -> None:
        check = taxonomy.check_cote("BB/11/477", "")
        self.assertEqual((check.cote, check.flag, check.suggestion), ("BB/11/477", "suspecte-bb11", "BB/34/477"))

    def test_missing_cote(self) -> None:
        self.assertEqual(taxonomy.check_cote("", "").flag, "absente")


if __name__ == "__main__":
    unittest.main()
