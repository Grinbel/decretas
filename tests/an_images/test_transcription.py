"""The decree-page parser on synthetic transcriptions (every name here is invented)."""
from __future__ import annotations

import unittest

from decretas.an_images import transcription

from . import fabrique


class KnownLayoutTest(unittest.TestCase):
    def setUp(self) -> None:
        self.result = transcription.analyse_decree([fabrique.PAGE_1, fabrique.PAGE_2], 1932)
        self.entries = self.result["entrees"]

    def test_preamble_stamp_and_ground(self) -> None:
        preamble = self.result["preambule"]
        self.assertEqual(preamble["date_du_tampon"], "1932-01-12")
        self.assertEqual(preamble["tampon_lu"], "12 JANV 1932")
        self.assertEqual(preamble["fondement"],
                         "Sont naturalisés Français par application de l'article 6 § 1er de la loi du 10 août 1927 :")

    def test_one_entry_per_person_in_page_order(self) -> None:
        self.assertEqual([entry["nom"] for entry in self.entries],
                         ["TESTAOUI (Ahmed ben Mohamed)", "FICTIVO (Paul Henri)", "INVENTEE (Rosa)", "SPECIMEN (Paul)"])
        self.assertEqual([entry["nom_famille"] for entry in self.entries], ["TESTAOUI", "FICTIVO", "INVENTEE", "SPECIMEN"])
        self.assertEqual(self.entries[0]["prenoms"], "Ahmed ben Mohamed")
        self.assertEqual([entry["page"] for entry in self.entries], [0, 0, 0, 1])

    def test_dossier_numbers_with_typewriter_lookalikes(self) -> None:
        self.assertEqual([entry["dossier"] for entry in self.entries], ["20001 X 31", "8102 X 31", "10452 X 30", "777 X 31"])
        self.assertEqual(self.entries[0]["dossier_lu"], "20001 X 3I")          # what was read is kept
        self.assertIn("numero-de-dossier-corrige", self.entries[0]["drapeaux"])
        self.assertNotIn("numero-de-dossier-corrige", self.entries[3]["drapeaux"])

    def test_birth_year_profession_place_residence(self) -> None:
        first = self.entries[0]
        self.assertEqual((first["annee"], first["profession"], first["lieu"], first["residence"]),
                         (1885, "cultivateur", "Fictiville (Alger)", "Exempleville (Alger)"))
        self.assertIn("chiffres-corriges", first["drapeaux"])                   # "I885" was read
        self.assertIn("I885", first["naissance"])                               # the reading itself is not rewritten
        self.assertEqual(self.entries[3]["annee"], 1901)                        # "né en 1901", no day
        self.assertIsNone(self.entries[3]["profession"])

    def test_wife_and_children(self) -> None:
        second = self.entries[1]
        self.assertEqual(second["epouse"]["nom"], "EXEMPLMANN (Maria)")
        self.assertEqual(second["epouse"]["annee"], 1890)
        self.assertEqual([(child["nom"], child["annee"]) for child in second["enfants"]], [("Pierre", 1912), ("Louise", 1915)])
        self.assertEqual(second["annee"], 1881)                                 # his own year, not his wife's
        self.assertEqual(second["residence"], "Testbourg (Oran)")
        self.assertEqual(second["sceau"], "Remise des neuf dixièmes.")

    def test_person_across_two_images(self) -> None:
        third = self.entries[2]
        self.assertEqual(third["pages"], [0, 1])
        self.assertIn("a-cheval-sur-deux-images", third["drapeaux"])
        self.assertEqual(third["residence"], "Fabriqueville (Constantine)")     # "demeu-/rant" joined again
        self.assertIn("demeurant à Fabriqueville", third["texte"])

    def test_closing_articles_are_not_persons(self) -> None:
        self.assertEqual(self.result["stats"]["entrees"], 4)
        self.assertEqual(self.result["non_rattache"], [])
        self.assertEqual(self.result["numeros_orphelins"], [])
        self.assertEqual(self.result["stats"]["epouses"], 1)
        self.assertEqual(self.result["stats"]["enfants"], 2)


class SeenOnRealPagesTest(unittest.TestCase):
    """The variations seen on the tutorial screenshots of real decrees of 1932 (see fabrique.PAGE_QUIRKS_1)."""

    def setUp(self) -> None:
        self.result = transcription.analyse_decree([fabrique.PAGE_QUIRKS_1, fabrique.PAGE_QUIRKS_2], 1932)
        self.entries = self.result["entrees"]

    def test_tick_marks_and_missing_comma_do_not_spoil_the_name(self) -> None:
        self.assertEqual([entry["nom"] for entry in self.entries],
                         ["FICTANEL (Aldo)", "ROBATEST (Emile, Octave)", "VULTEST (Otto)",
                          "LONGNOMEST (Remi Jean Marie Joseph Antoine Fictif)"])
        self.assertEqual([entry["dossier"] for entry in self.entries], ["4001 X 32", "4002 X 32", None, None])
        self.assertEqual([entry["profession"] for entry in self.entries], ["mineur", "mécanicien", "cultivateur", "mineur"])
        self.assertNotIn("forme-de-nom-non-reconnue", self.result["stats"]["drapeaux"])
        self.assertEqual(self.result["preambule"]["date_du_tampon"], "1932-02-09")

    def test_capitalised_months_and_residence_without_comma_before_the_children(self) -> None:
        self.assertEqual([entry["annee"] for entry in self.entries], [1890, 1891, 1860, 1886])
        self.assertEqual(self.entries[0]["residence"], "Essai-les-Bains (Jura)")
        self.assertEqual(self.entries[1]["residence"], "Testaux (Jura)")             # « (Jura) ayant six enfants » : no comma

    def test_one_child_per_line_several_given_names_and_ditto_places(self) -> None:
        first, second = self.entries[0], self.entries[1]
        self.assertEqual([(child["nom"], child["annee"]) for child in first["enfants"]],
                         [("Clara", 1920), ("Nina", 1924), ("Dora", 1927), ("Hugo", 1930)])
        self.assertEqual([child["lieu"] for child in first["enfants"]],
                         ["Inventona (Italie)", "Essai-les-Bains (Jura)", "Essai-les-Bains (Jura)", "Essai-les-Bains (Jura)"])
        self.assertEqual(first["enfants"][2]["drapeaux"], ["lieu-repris-de-la-ligne-precedente"])
        self.assertEqual([child["nom"] for child in second["enfants"]], ["Alain, Victor", "Basile, Edgar", "Colette, Irma"])
        self.assertEqual(second["enfants"][2]["lieu"], "Fabriqueux (Suisse)")
        self.assertEqual(self.result["stats"]["enfants"], 7)
        # « ayant six enfants mineurs » and three read (the page ends there): said, not hidden
        self.assertEqual((second["enfants_annonces"], len(second["enfants"])), (6, 3))
        self.assertIn("nombre-d-enfants-different-de-l-annonce", second["drapeaux"])
        self.assertEqual(first["enfants_annonces"], 4)
        self.assertNotIn("nombre-d-enfants-different-de-l-annonce", first["drapeaux"])

    def test_wife_after_a_lone_et_and_name_whose_parenthesis_closes_on_the_next_line(self) -> None:
        third, fourth = self.entries[2], self.entries[3]
        self.assertEqual(third["epouse"]["nom"], "MOINEAU (Odile)")
        self.assertEqual(third["epouse"]["annee"], 1865)
        self.assertEqual(third["residence"], "Essaibourg (Haut-Rhin)")
        self.assertEqual(third["lieu"], "Beurnessai (Suisse)")
        self.assertEqual(fourth["residence"], "Alger")
        self.assertEqual(fourth["page"], 1)
        self.assertEqual(self.result["non_rattache"], [])

    def test_children_are_read_even_when_their_announcement_is_not(self) -> None:
        page = ("Décrète :\n9 X 32  ESSAI (Jean), maçon, né le 2 mai 1890 à Oran, demeurant à Oran, avant deux enfanls mineurs\n"
                "1°) Paul, né le 3 mai 1920 à Oran\n2°) illisible\n3°) Lise, née le 4 mai 1922 à d°\n")
        entry = transcription.analyse_decree([page], 1932)["entrees"][0]
        self.assertEqual([(child["nom"], child["annee"], child["lieu"]) for child in entry["enfants"]],
                         [("Paul", 1920, "Oran"), ("Lise", 1922, "Oran")])
        self.assertIn("enfants-sans-annonce", entry["drapeaux"])
        self.assertIn("enfants-partiellement-lus", entry["drapeaux"])               # « 2°) illisible » is counted, not hidden

    def test_married_woman_written_with_her_husbands_name(self) -> None:
        page = ("Décrète :\n5001 X 32/   / ESSAIZY (Odette, Lucie) femme FICTETTI, née le I7 Juin I905 à Testcourt (Somme), de-\n"
                "meurant à Exempleville (même département).\n      Remise des dix neuf vingtièmes.\n"
                "5002 X 32/   / AVONTEST (Irène, Berthe), femme MARTINEST DUFICTIF\nnée le I4 Mars I879 à Inventeville ( Bouches-du-Rhône). y\ndemeurant .\n")
        first, second = transcription.analyse_decree([page], 1932)["entrees"]
        self.assertEqual((first["nom"], first["nom_epoux"], first["profession"], first["annee"]),
                         ("ESSAIZY (Odette, Lucie)", "FICTETTI", None, 1905))
        self.assertEqual(first["residence"], "Exempleville (même département)")
        self.assertEqual(first["sceau"], "Remise des dix neuf vingtièmes.")
        self.assertEqual((second["nom_epoux"], second["annee"]), ("MARTINEST DUFICTIF", 1879))

    def test_strip_tick(self) -> None:
        self.assertEqual(transcription.strip_tick("  /VULTEST (Otto)"), "VULTEST (Otto)")
        self.assertEqual(transcription.strip_tick("demeurant à Alger"), "demeurant à Alger")
        self.assertEqual(transcription.strip_tick("- 2 -"), "- 2 -")


class UnknownLayoutTest(unittest.TestCase):
    """What the parser does with shapes nobody has seen yet: nothing is dropped silently."""

    def test_margin_numbers_read_as_a_separate_column_are_paired_by_rank(self) -> None:
        page = ("Sont admis aux droits de citoyen français par application de la loi du 4 février 1919 :\n"
                "1234 X 45\n5678 X 45\n"
                "TESTEUR (Ali ben Omar), cultivateur, né en 1890 à Fictiville (Alger), y demeurant.\n"
                "ESSAI (Said), journalier, né le 2 mars 1895 à Exempleville (Oran), demeurant à Oran.\n")
        result = transcription.analyse_decree([page], 1946)
        self.assertEqual([(entry["dossier"], entry["nom_famille"]) for entry in result["entrees"]],
                         [("1234 X 45", "TESTEUR"), ("5678 X 45", "ESSAI")])
        self.assertTrue(all("numero-apparie-par-rang" in entry["drapeaux"] for entry in result["entrees"]))
        self.assertEqual(result["entrees"][0]["residence"], "Fictiville (Alger)")       # « y demeurant »
        self.assertIn("admis aux droits de citoyen français", result["preambule"]["fondement"])

    def test_name_without_parenthesis_is_kept_and_flagged(self) -> None:
        page = ("Sont admis :\n"
                "4321 X 46  Mohamed ben Ali ben Testeur, cultivateur, né présumé en 1888 au douar Fictif (Constantine), y demeurant.\n"
                "9999 X 46\n")
        result = transcription.analyse_decree([page], 1946)
        entry = result["entrees"][0]
        self.assertEqual(entry["nom"], "Mohamed ben Ali ben Testeur")
        self.assertIsNone(entry["nom_famille"])
        self.assertIn("forme-de-nom-non-reconnue", entry["drapeaux"])
        self.assertEqual(entry["annee"], 1888)
        self.assertEqual(result["numeros_orphelins"], ["9999 X 46"])            # a number facing nobody is reported

    def test_layout_without_any_landmark_gives_back_every_line(self) -> None:
        pages = ["Sont admis aux droits de citoyen français :\nMohamed ben Ali ben Testeur, cultivateur, né en 1888, y demeurant ;\n",
                 "Ahmed ben Fictif, né en 1901.\n"]
        result = transcription.analyse_decree(pages, 1946)
        self.assertEqual(result["entrees"], [])
        self.assertEqual([block["page"] for block in result["non_rattache"]], [0, 1])
        self.assertIn("Mohamed ben Ali ben Testeur", result["non_rattache"][0]["texte"])
        self.assertIn("Ahmed ben Fictif", result["non_rattache"][1]["texte"])

    def test_a_stray_line_does_not_swallow_the_next_person(self) -> None:
        page = ("Décrète :\n"
                "EXEMPLE (Jean), maçon, né le 1er janvier 1880 à Testville (Espagne), demeurant à Alger.\n"
                "IO X II tache sur le papier\n"
                "MODELE (Anna), née le I2 juin I90I à Naples (Italie), demeurant à Bône (Constantine).\n"
                "Remise totale.\n"
                "Retrait\nDécret du 05-05-40\n"
                "Fait à Paris, le 5 janvier 1932.\nSignature\n")
        result = transcription.analyse_decree([page], 1932)
        self.assertEqual([entry["nom_famille"] for entry in result["entrees"]], ["EXEMPLE", "MODELE"])
        second = result["entrees"][1]
        self.assertIn("debut-apres-paragraphe-inacheve", second["drapeaux"])
        self.assertIn("sans-numero-de-dossier", second["drapeaux"])
        self.assertEqual(second["annee"], 1901)
        # the margin note written after the seal line is attached to nobody, and handed back
        self.assertEqual(result["non_rattache"], [{"page": 0, "texte": "Retrait Décret du 05-05-40"}])
        self.assertEqual(result["stats"]["lignes_ignorees_apres_la_liste"], 1)  # the signature

    def test_wife_on_her_own_line_is_not_a_new_person(self) -> None:
        page = ("Décrète :\n"
                "12 X 31  EXEMPLE (Jean), maçon, né le 2 mai 1880 à Testville (Espagne), et\n"
                "MODELE (Anna), sa femme, née le 3 juin 1885 à Naples (Italie), demeurant tous deux à Alger.\n")
        result = transcription.analyse_decree([page], 1932)
        self.assertEqual(len(result["entrees"]), 1)
        self.assertEqual(result["entrees"][0]["epouse"]["nom"], "MODELE (Anna)")
        self.assertEqual(result["entrees"][0]["residence"], "Alger")

    def test_impossible_birth_years_are_flagged_not_used(self) -> None:
        page = ("Décrète :\n"
                "1 X 46  ESSAI (Omar), né le 3 mai 1999 à Oran, demeurant à Oran.\n"
                "2 X 46  ESSAI (Ali), né le 3 mai 1950 à Oran, demeurant à Oran.\n"
                "3 X 46  ESSAI (Said), cultivateur, demeurant à Oran.\n")
        result = transcription.analyse_decree([page], 1946)
        self.assertEqual([entry["annee"] for entry in result["entrees"]], [None, None, None])
        self.assertEqual(result["entrees"][0]["annee_lue"], 1999)
        self.assertIn("annee-invraisemblable", result["entrees"][0]["drapeaux"])
        self.assertIn("annee-invraisemblable", result["entrees"][1]["drapeaux"])   # born after the decree
        self.assertIn("naissance-non-lue", result["entrees"][2]["drapeaux"])

    def test_paragraph_much_longer_than_one_person_is_flagged(self) -> None:
        hidden = " ".join(f"Inconnu{rank} ben Fictif, cultivateur, né en 1890 au douar Essai, y demeurant ;" for rank in range(8))
        page = "Décrète :\n77 X 46  ESSAI (Omar), né en 1890 à Oran, demeurant à Oran, " + hidden + "\n"
        result = transcription.analyse_decree([page], 1946)
        self.assertIn("paragraphe-anormalement-long", result["entrees"][0]["drapeaux"])
        self.assertIn("Inconnu7 ben Fictif", result["entrees"][0]["texte"])

    def test_empty_and_garbage_inputs_do_not_raise(self) -> None:
        self.assertEqual(transcription.analyse_decree([], None)["stats"]["entrees"], 0)
        result = transcription.analyse_decree(["\x00\x01 ~~~~ ||||\n\n((((( )))) X X X 12 X 3\n", ""], None)
        self.assertEqual(result["entrees"], [])


class DigitsTest(unittest.TestCase):
    def test_lookalikes_inside_numbers(self) -> None:
        self.assertEqual(transcription.fix_digits("I88I"), ("1881", True))
        self.assertEqual(transcription.fix_digits("1932"), ("1932", False))
        self.assertEqual(transcription.fix_digit_runs("loi du I0 août I927, article II, O et I"),
                         "loi du 10 août 1927, article II, O et I")              # letters-only tokens are left alone

    def test_dossier_forms(self) -> None:
        cases = {"8I02 X 3I": "8102 X 31", "20001X31": "20001 X 31", "123 bis X 30": "123 bis X 30", "4567 BX 46": "4567 BX 46",
                 "I0452 x 30": "10452 X 30"}
        for written, expected in cases.items():
            match = transcription.DOSSIER.search(written)
            self.assertIsNotNone(match, written)
            self.assertEqual(transcription.normalise_dossier(match)[0], expected)
        self.assertIsNone(transcription.DOSSIER.search("EXEMPLE X 31"))
        self.assertIsNone(transcription._dossier_at_start("IO X II suite de texte"))   # letters only, then text: too risky

    def test_birth_forms(self) -> None:
        self.assertEqual(transcription.parse_birth(", née le 1er juin 1915 à Testbourg.")["jour"], 1)
        birth = transcription.parse_birth(", né le I2 juin I90I à Naples (Italie), demeurant à Alger.")
        self.assertEqual((birth["annee"], birth["mois"], birth["jour"], birth["lieu"]), (1901, 6, 12, "Naples (Italie)"))
        self.assertEqual(transcription.parse_birth(", né présumé en 1888 au douar Fictif, y demeurant.")["annee"], 1888)
        self.assertEqual(transcription.parse_birth(", cultivateur")["drapeaux"], ["naissance-non-lue"])


if __name__ == "__main__":
    unittest.main()
