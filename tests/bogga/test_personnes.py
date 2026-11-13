"""Person entries: splitting a list and reading an entry, layout by layout (invented names)."""
from __future__ import annotations

import unittest

from decretas.bogga import personnes as P


def texts(buffer: str) -> list[str]:
    return [fragment.text for fragment in P.split_entries(buffer)]


class SplitEntriesTestCase(unittest.TestCase):
    def test_1873_parenthesis_layout_with_lost_numbers(self) -> None:
        buffer = (". Fictivo (Aldo/, badois, demeurant à Val-Fictif.\n"
                  ". Exemplski (Zygmunt), polonais, demeurant à Val-Modèle. . Modelmann (Ulric), badois, demeurant à Bourg-Essai.")
        got = texts(buffer)
        self.assertEqual(len(got), 3)
        self.assertTrue(got[1].startswith(". Exemplski"))
        self.assertTrue(got[2].startswith(". Modelmann") or got[2].startswith("Modelmann"))

    def test_entry_continued_on_the_next_line_is_not_cut(self) -> None:
        buffer = ". Testaoui ben Exemple, indigène musulman, demeurant à\nBeni-Fictif.\n. Inventi (Paul), sarde, demeurant à Alger."
        got = texts(buffer)
        self.assertEqual(len(got), 2)
        self.assertIn("Beni-Fictif", got[0])

    def test_place_at_line_start_is_not_a_new_entry(self) -> None:
        buffer = "Essaiberg (Jean), colporteur, demeurant à\nSaint-Denis du Sig (province d'Oran).\nModeloff (Paul), suisse, demeurant à Oran."
        self.assertEqual(len(texts(buffer)), 2)

    def test_1872_comma_layout_with_ditto(self) -> None:
        buffer = "Fictif, Antoine, Allemand id. Essaimann, Gaspard, id. id. Modelschneider, Jean, id. id.\nTestberg, Conrad, id. id."
        self.assertEqual(len(texts(buffer)), 4)

    def test_comma_read_as_full_stop_after_the_surname_does_not_cut(self) -> None:
        got = texts("Inventmann, Pierre, allemand, Oran.\nFictlan. Charles, id. id.\nEssaitz. Joseph, id. id.")
        self.assertEqual(got, ["Inventmann, Pierre, allemand, Oran.", "Fictlan. Charles, id. id.", "Essaitz. Joseph, id. id."])

    def test_1866_numbered_sieur_layout(self) -> None:
        buffer = ("1° Le sieur EXEMPLON (Azar), né à Oran en mars 1815, interprète militaire ;\n"
                  "2 Le sieur Fictou Modeloun, dit BEN ESSAI, né à Oran le 1er février 1823, interprète.")
        self.assertEqual(len(texts(buffer)), 2)

    def test_abbreviation_does_not_cut(self) -> None:
        got = texts("Testoni (Marc), né à St. Fictif (Suisse), demeurant à Alger. Modelo (Jean), marin, demeurant à Oran.")
        self.assertEqual(len(got), 2)
        self.assertIn("St. Fictif (Suisse)", got[0])

    def test_four_digit_year_at_line_start_is_not_a_list_number(self) -> None:
        buffer = "Le sieur Essaino (Pierre), propriétaire, né le 8 septembre\n1833 Fictezze (Italie), demeurant à Oran."
        self.assertEqual(len(texts(buffer)), 1)

    def test_comma_after_a_birth_place_in_parentheses(self) -> None:
        buffer = ("Ficter (Michel), soldat de 1re classe au 2° régiment étranger, né le 3 août 1858 à Fictausen (ex-Bas-Rhin), "
                  "Exempleur (Eugène), soldat de 1re classe, né le 4 octobre 1862 à Modelviller (ex-Moselle).")
        self.assertEqual(len(texts(buffer)), 2)

    def test_underscore_read_before_a_name(self) -> None:
        buffer = "Fictalot (Charles), soldat à la légion étrangère, né le 11 novembre 1856, à Oxe (Suisse). _Exemplié (Nicolas), soldat, né le 13 février 1853 à Fictach."
        self.assertEqual(len(texts(buffer)), 2)

    def test_comma_between_two_complete_entries(self) -> None:
        buffer = ("Inventese (Carmela), femme Modelo, née à Fictida (Italie), le 12 novembre 1853, demeurant à Oran, "
                  "Exemplita (Maria-Grazia), femme Testaro, née à Fictida, le 3 mai 1850, demeurant à Oran.")
        self.assertEqual(len(texts(buffer)), 2)


    def test_comma_at_a_line_end_between_two_complete_entries(self) -> None:
        # regression: « …(Turquie),\nNom (Prénom), soldat … » stayed one entry holding two persons
        buffer = ("Fictinet (Aldo-Marcel). sergent, né le 3 mars 1858 à Villefictive (Turquie),\n"
                  "Exempleberg (Ugo-Ulric), soldat de 2° classe, né le 3 mars 1856 à Val-Fictif (ci-devant Haut-Rhin).")
        self.assertEqual(len(texts(buffer)), 2)

    def test_stray_mark_between_a_comma_and_the_next_name(self) -> None:
        buffer = ("Fictato (Ugo), marin, né le 3 mars 1828 à Villafictiva (Italie), demeurant à Alger, "
                  "* Exemplio (Aldo), marin, né à Villafictiva (Italie), le 3 mars 1832, demeurant à Alger.")
        self.assertEqual(len(texts(buffer)), 2)

    def test_tail_of_a_parenthesis_before_a_new_entry(self) -> None:
        # regression: « Bas-Rhin). Nom (Prénom), … » was one fragment, rejected as a whole: the person was lost
        got = texts("Bas-Rhin). _ ” Fictchal (Aldo), soldat de 2° classe à la légion étrangère, né le 3 mars 1857 à Val-Fictif.")
        self.assertEqual(len(got), 2)
        self.assertEqual(got[0], "Bas-Rhin).")
        self.assertTrue(P.looks_like_person(got[1]))

    def test_forenames_cut_by_a_full_stop_inside_the_parenthesis_stay_one_entry(self) -> None:
        # regression: « Nom (Prénom.\nAutre), employé … » was cut in two pieces, both rejected
        got = texts("Fictalme (Aldo.\nMarcel), employé, né le 3 mars 1861 à Val-Fictif, demeurant à Alger.")
        self.assertEqual(len(got), 1)
        self.assertEqual(P.read_entry(got[0].replace("\n", " "), 1883).name, "Fictalme (Aldo. Marcel)")

    def test_brace_read_for_a_parenthesis_does_not_glue_two_entries(self) -> None:
        buffer = ("Fictour (Aldo Marcel}, journalier, né à Villafictiva (Italie), le 3 mars 1851, demeurant à Val-Fictif.\n"
                  "Exempioso {Ugo), journalier, né à Villafictiva (Italie), le 3 mars 1852, demeurant à Val-Modèle.")
        self.assertEqual(len(texts(buffer)), 2)


class LooksLikePersonTestCase(unittest.TestCase):
    def test_accepts_each_layout(self) -> None:
        for text in (
            "7. Testaoui ben Exemple, indigène musulman, demeurant à Beni-Fictif.",
            "Fictif, Paul-Aldo, suisse, demeurant à Val-Fictif.",
            "* Amar ben Inventé, indigène, Alger.",
            "Modelmann, Jean, id. id.",
            "1° Le sieur EXEMPLON (Azar), né à Oran dans le courant du mois de mars 1815 ;",
            "Essaioui (Bel Fictif ben Exemple), indigène monogame, garde champêtre, né en 1838 à Aïn-Fictive (Alger), demeurant à Bourg-Essai.",
            "La nommée Fictiva (Marie-Thérèse), femme Inventon, née le 22 décembre 1836 à Alicante (Espagne), demeurant à Saïda.",
            "Vanderfict, Alberl, belve, Val-Fictif.",
        ):
            with self.subTest(text=text):
                self.assertTrue(P.looks_like_person(text))

    def test_soldier_decorated_with_the_military_medal_is_a_person(self) -> None:
        # regression: every entry holding the word « médaille » was dropped
        for text in ("Amar ould Exemple, sergent au 2° régiment de tirailleurs algériens, célibataire, décoré de la "
                     "médaille militaire, né en 1827, au Maroc.",
                     "Fictindi (Ulric), caporal-sapeur à la légion étrangère, décoré de la médaille militaire, né le 3 mars "
                     "1826 à Villefictive (Bavière)."):
            with self.subTest(text=text[:30]):
                self.assertTrue(P.looks_like_person(text))
        self.assertFalse(P.looks_like_person("Fictard (Aldo), instituteur, à qui est décernée une médaille d'honneur."))

    def test_name_whose_capital_was_lost_is_kept_and_flagged(self) -> None:
        text = "waFicteller (Ulric), tailleur de pierres, né à Villefictive (Grand-duché-de-Bade), le 3 mars 1848, demeurant à Val-Fictif."
        self.assertTrue(P.looks_like_person(text))
        reading = P.read_entry(text, 1877)
        self.assertEqual(reading.name, "waFicteller (Ulric)")
        self.assertTrue(reading.flags & P.F_NOM_INCERTAIN)
        self.assertFalse(P.looks_like_person("par application de l'article 18 du Code civil, les ci-après dénommées :"))

    def test_rejects_an_appointment_notice(self) -> None:
        text = ("Fictard (Aldo-Marcel), principal clerc de notaire, a été nommé notaire à Blida, "
                "en remplacement de M. Inventin, démissionnaire.")
        self.assertFalse(P.looks_like_person(text))

    def test_birth_place_followed_by_a_date_is_not_a_signature(self) -> None:
        self.assertTrue(P.looks_like_person(
            "Fictes (Ramiro), Espagnol, ancien portier de l'hôpital civil, né à Alger, le 3 mars 1851, y demeurant;"))

    def test_rejects_signatures_and_tails_of_parentheses(self) -> None:
        for text in ("LS Le Chef du 7° Bureau CA Ne Alger, le 10 février 1886.",
                     "M. Le Ministre de la justice, Garde des Sceaux, demeurant à Paris.",
                     "Maroc), commerçant à Saint-Denis-du-Sig."):
            with self.subTest(text=text):
                self.assertFalse(P.looks_like_person(text))

    def test_rejects_prose_and_headers(self) -> None:
        for text in ("Le Gouverneur général civil de l'Algérie, vu le décret du 27 septembre 1873,",
                     "Département de Constantine (territoire de commandement).",
                     "Fictin, Pierre, Exemplger Joseph, Modelklé Joseph, Testerer, Jacch, Essaiger, Léopold.",
                     "Beni-Fictif."):
            with self.subTest(text=text):
                self.assertFalse(P.looks_like_person(text))


class ReadEntryTestCase(unittest.TestCase):
    def read(self, text: str, year: int = 1888) -> P.Reading:
        return P.read_entry(text, year)

    def test_name_keeps_the_parentheses(self) -> None:
        reading = self.read("Essaioui (Bel Fictif ben Exemple), indigène monogame, né en 1838 à Aïn-Fictive (Alger), demeurant à Bourg-Essai.")
        self.assertEqual(reading.name, "Essaioui (Bel Fictif ben Exemple)")
        self.assertEqual(reading.birth_year, 1838)
        self.assertEqual(reading.residence, "Bourg-Essai")
        self.assertTrue(reading.markers & P.M_INDIGENE)

    def test_comma_inside_parentheses_does_not_truncate_the_name(self) -> None:
        reading = self.read("Testir (Mohamed ben El-Fictif, dit Bou Essai), indigène musulman, né en 4859 à Biskra, y demeurant.")
        self.assertEqual(reading.name, "Testir (Mohamed ben El-Fictif, dit Bou Essai)")
        self.assertEqual(reading.birth_year, 1859)
        self.assertEqual(reading.residence, "Biskra")
        self.assertEqual(reading.markers & (P.M_INDIGENE | P.M_MUSULMAN), P.M_INDIGENE | P.M_MUSULMAN)

    def test_several_commas_inside_parentheses_do_not_truncate_the_name(self) -> None:
        # regression: « Nom (Prénom, Prénom, Prénom) » was cut at the first comma
        reading = self.read("| Fictotta (Alda, Ugolina, Marcella), femme Exemplès, née le 4° novembre 1843 à Villafictiva (Italie), "
                            "demeurant à Val-Fictif.", 1886)
        self.assertEqual(reading.name, "Fictotta (Alda, Ugolina, Marcella)")
        self.assertEqual(reading.birth_year, 1843)

    def test_full_stop_read_for_a_comma_after_the_parenthesis(self) -> None:
        # regression: the name ran on to the first comma of the entry
        reading = self.read("Fictermié (Ulric). soldat de 2° classe à la légion étrangère, né le 3 mars 1853 à Val-Fictif.", 1880)
        self.assertEqual(reading.name, "Fictermié (Ulric)")

    def test_stray_second_parenthesis(self) -> None:
        reading = self.read("6. Le sieur Fictoux ([Azar), né à Villefictive (Maroc) en 1831, demeurant à Val-Fictif.", 1868)
        self.assertEqual(reading.name, "Fictoux ([Azar)")

    def test_marks_before_the_honorific_are_not_the_name(self) -> None:
        # regression: « F4 4. Le sieur Nom (…) » gave the name 'F4 4. Le sieur Nom (…)'
        self.assertEqual(self.read("F4 4. Le sieur Fictager (Azar), indigène israélite, né à Alger en 1828.", 1868).name,
                         "Fictager (Azar)")
        self.assertEqual(self.read("RUE 12° Le sieur Exemplilo (Ugo-Aldo), patron de cabotage, demeurant à Alger;", 1867).name,
                         "Exemplilo (Ugo-Aldo)")
        self.assertEqual(self.read("A, Fictmitt (Ulrica-Alda), allemande, demeurant a Mustapha.", 1873).name, "Fictmitt (Ulrica-Alda)")
        self.assertEqual(self.read("L 4. Exempltrel (Ulric), allemand, demeurant à Val-Fictif.", 1875).name, "Exempltrel (Ulric)")

    def test_sub_list_header_in_front_of_the_entry_is_not_the_name(self) -> None:
        # regression: the name was 'Est naturalisée Française'
        reading = self.read("Est naturalisée Française, la nommée Fictont (Alda), domestique, née le 3 mars 1856 à Villafictiva "
                            "(Espagne), demeurant à Alger.", 1885)
        self.assertEqual(reading.name, "Fictont (Alda)")
        self.assertTrue(reading.markers & P.M_NATURALISEE)
        again = self.read(".4 Est naturaliste française? : | Exemplañi (Alda-Ugolina), femme Fictorini, née le 3 mars 1837.", 1883)
        self.assertEqual(again.name, "Exemplañi (Alda-Ugolina)")
        self.assertEqual(P.sub_list_status("Sont réintégrées dans la qualité de Française, par application de l'article 18 du Code civil :"),
                         P.M_REINTEGREE)
        self.assertEqual(P.sub_list_status("Fictont (Alda), domestique"), 0)

    def test_birth_year_with_a_doubled_first_digit(self) -> None:
        self.assertEqual(self.read("Ficthen (Azar), négociant, né le 39 juin 41849, à Villefictive (Maroc), demeurant à Oran.", 1885).birth_year,
                         1849)

    def test_two_births_in_one_entry_are_flagged_as_two_persons(self) -> None:
        # regression: the flag was only set above 75 words, and never met in the real volumes
        merged = self.read("Fictira (Ramiro), limonadier, né le 3 mars 1853 à Val-Fictif (Oran), demeurant à Val-Fictif. \\vars "
                           "(Ugo-Aldo), maçon, né le 3 mars 1854 à Val-Modèle (Oran), demeurant à Val-Modèle.", 1885)
        self.assertTrue(merged.flags & P.F_PEUT_ETRE_FUSIONNEE)
        self.assertFalse(self.read("Fictira (Ramiro), limonadier, né le 3 mars 1853 à Val-Fictif (Oran), y demeurant.", 1885).flags
                         & P.F_PEUT_ETRE_FUSIONNEE)
        second_name = self.read(". Fictiefer (Ulric) badois, à Val-Fictif, Exemplann (Aldo), badois, à Val-Modèle.", 1873)
        self.assertTrue(second_name.flags & P.F_PEUT_ETRE_FUSIONNEE)
        for one_person in ("Fictintès (Ramiro), ajusteur, né à Villafictiva, Ile Fictive (Espagne), en 1833, demeurant à Alger.",
                           "Exemplel (Alda), femme Testorini (Ugo-Aldo), née le 3 mars 1837 à Villafictiva (Italie), demeurant à Oran.",
                           "Amar ben Exemple ou Fictif, colporteur, né en 4849, aux Beni-Fictif, Beni-Essai (Val-Fictif), "
                           "demeurant à Constantine."):
            with self.subTest(one_person=one_person[:30]):
                self.assertFalse(self.read(one_person, 1885).flags & P.F_PEUT_ETRE_FUSIONNEE)

    def test_parenthesis_never_closed_by_the_ocr(self) -> None:
        reading = self.read("10. Le sieur Fictezze (Ghislain-Aldo, caporal au 3° bataillon d'Afrique, né à Villefictive en 1832.", 1868)
        self.assertEqual(reading.name, "Fictezze (Ghislain-Aldo")
        self.assertEqual(reading.number, 10)

    def test_closing_brace_read_for_a_parenthesis(self) -> None:
        self.assertEqual(self.read("Inventour (Aldo Marcel}, belge, régiment étranger.", 1873).name, "Inventour (Aldo Marcel}")

    def test_status_right_after_the_parenthesis(self) -> None:
        self.assertEqual(self.read(". Modelès (Ramiro) étranger européen. né à Villafictiva (Espagne) en 1844, marin.", 1869).name,
                         "Modelès (Ramiro)")

    def test_surname_forename_layout(self) -> None:
        reading = self.read("Fictif, Paul-Aldo, suisse, demeurant à Val-Fictif.", 1873)
        self.assertEqual(reading.name, "Fictif, Paul-Aldo")
        self.assertEqual(reading.nationality, "suisse")
        self.assertEqual(reading.residence, "Val-Fictif")

    def test_filiation_name_is_not_extended_by_a_status_field(self) -> None:
        reading = self.read("31. Mohammed ben Exemple ben bel Fictif, indigène musulman, demeurant à Aïn-Fictive.", 1873)
        self.assertEqual(reading.name, "Mohammed ben Exemple ben bel Fictif")
        self.assertEqual(reading.number, 31)

    def test_place_only_layout(self) -> None:
        reading = self.read("* Amar ben Inventé, indigène, Alger.", 1873)
        self.assertEqual((reading.name, reading.residence), ("Amar ben Inventé", "Alger"))

    def test_civility_is_not_part_of_the_name(self) -> None:
        self.assertEqual(self.read("M. Fictulo (Aldo-Ferdinand), commis de négoce, né de parents italiens, à Bône, y demeurant.").name,
                         "Fictulo (Aldo-Ferdinand)")

    def test_sieur_is_not_part_of_the_name(self) -> None:
        self.assertEqual(self.read("2 Le sieur Fictou Modeloun, dit BEN ESSAI, né à Oran le 1er février 1823.", 1866).name,
                         "Fictou Modeloun")

    def test_indigene_marker_survives_ocr_damage(self) -> None:
        for word in ("indigène", "indisène", "irdisène", "indigëne", "indiséne", "Indigène", "indirène"):
            with self.subTest(word=word):
                self.assertTrue(self.read(f"Testaoui ben Exemple, {word} musulman, demeurant à Blida.").markers & P.M_INDIGENE)

    def test_israelite_and_musulman_markers(self) -> None:
        self.assertTrue(self.read("EXEMPLET (Azar), indigène israélite, né le 3 mars 1841 à Oran.").markers & P.M_ISRAELITE)
        self.assertTrue(self.read("Fictou ben Essai, indigène musulmad, Alger.").markers & P.M_MUSULMAN)

    def test_regiment_etranger_is_not_the_status_etranger(self) -> None:
        soldier = self.read("Inventaux (Rodolphe), suisse, régiment étranger.", 1873)
        self.assertFalse(soldier.markers & P.M_ETRANGER)
        self.assertTrue(soldier.markers & P.M_NATIONALITE)
        broken = self.read("Fictenger (Ulric), soldat de 1re classe au 2° régi- EE étranger, né le 3 mars 1857 à Val-Fictif.", 1886)
        self.assertFalse(broken.markers & P.M_ETRANGER)                  # regression: « régi- EE étranger »
        status = self.read("FICTICHE (Azar), étranger israélite, né en 1842 à Villefictive (Maroc), commerçant à Oran.", 1869)
        self.assertEqual(status.markers & (P.M_ETRANGER | P.M_ISRAELITE), P.M_ETRANGER | P.M_ISRAELITE)

    def test_nationality_tolerates_ocr_but_a_country_is_not_a_nationality(self) -> None:
        self.assertEqual(self.read("Modelo (Ugo), itslien, demeurant à Val-Fictif.", 1873).nationality, "italien")
        self.assertEqual(self.read("Essaini (Paul), marin, né à Fictida (Italie), le 6 avril 1844, demeurant à Oran.").nationality, None)
        self.assertEqual(self.read("Testina (Rosa), née de parents espagnols, à Oran, y demeurant.").nationality, "espagnol")

    def test_impossible_birth_year_is_rejected_and_flagged(self) -> None:
        reading = self.read("Fictan (Jean), journalier, né en 1897 à Oran, demeurant à Alger.", 1888)
        self.assertIsNone(reading.birth_year)
        self.assertTrue(reading.flags & P.F_NAISSANCE_DOUTEUSE)

    def test_no_birth_year_printed(self) -> None:
        reading = self.read("Fictan (Ulric), badois, demeurant à Alger.", 1873)
        self.assertIsNone(reading.birth_year)
        self.assertFalse(reading.flags & P.F_NAISSANCE_DOUTEUSE)

    def test_residence_y_demeurant_takes_the_birth_place(self) -> None:
        self.assertEqual(self.read("Testina (Isabelle), femme Modeli, née à Oran de parents espagnols, le 28 janvier 1860, y demeurant.").residence,
                         "Oran")

    def test_ditto_gives_no_residence(self) -> None:
        self.assertIsNone(self.read("Modelmann, Jean, id. id.", 1873).residence)


class NoiseTestCase(unittest.TestCase):
    def test_noise_lines(self) -> None:
        for line in ("— 495 —", "œ 2", "Digitized by", "Google", "8 =. s", "118\" 149: 120°"):
            with self.subTest(line=line):
                self.assertTrue(P.is_noise_line(line))
        self.assertFalse(P.is_noise_line("Fictan (Ulric), badois, demeurant à Alger."))

    def test_number_line(self) -> None:
        self.assertTrue(P.is_number_line("70. 71, 12: 13. 74. 75. 36. 77. 78."))
        self.assertEqual(P.numbers_in_line("70. 71, 12: 13."), [70, 71, 12, 13])
        self.assertFalse(P.is_number_line("— 495 —"))


if __name__ == "__main__":
    unittest.main()
