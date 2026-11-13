import unittest

from decretas.an import persons


class ParseBirthTest(unittest.TestCase):
    def test_natnum_form(self) -> None:
        birth = persons.parse_birth("6 février 1842 (Strasbourg, Bas-Rhin)")
        self.assertEqual((birth.date, birth.precision, birth.year), ("1842-02-06", "jour", 1842))
        self.assertEqual(birth.place, "Strasbourg, Bas-Rhin")
        self.assertEqual(birth.raw, "6 février 1842 (Strasbourg, Bas-Rhin)")
        self.assertFalse(birth.conventional)

    def test_collaborative_form_with_parents(self) -> None:
        birth = persons.parse_birth("20 octobre 1844, Alger, département d'Alger, Algérie, de père maltais.")
        self.assertEqual(birth.date, "1844-10-20")
        self.assertEqual(birth.place, "Alger, département d'Alger, Algérie, de père maltais")
        self.assertEqual(birth.parents, "de père maltais")

    def test_profession_slipped_before_the_date_in_1892(self) -> None:
        birth = persons.parse_birth("journalier, 7 mai 1865, Alger, Alger, Algérie.")
        self.assertEqual((birth.date, birth.leak, birth.place), ("1865-05-07", "journalier", "Alger, Alger, Algérie"))

    def test_date_words_are_not_a_leak(self) -> None:
        for text in ("Né(e) le 19 mars 1868 (Gênes, Italie)", "en 1856, Fictiveville, Algérie.",
                     "Née le 27 août 1862 (Strasbourg, Bas-Rhin)"):
            self.assertEqual(persons.parse_birth(text).leak, "", text)

    def test_conventional_dates(self) -> None:
        self.assertTrue(persons.parse_birth("1 janvier 1883 (Fictiveville Constantine, Algérie)").conventional)
        self.assertTrue(persons.parse_birth("présumé né en 1884 (Fictiveville Maroc)").conventional)
        self.assertTrue(persons.parse_birth("vers 1890 (Fictiveville)").conventional)
        self.assertFalse(persons.parse_birth("2 janvier 1882 (Fictiveville)").conventional)
        self.assertFalse(persons.parse_birth("1882, Fictiveville, Algérie.").conventional)

    def test_year_only_and_numeric(self) -> None:
        birth = persons.parse_birth("1867, El Fictif, Tunisie.")
        self.assertEqual((birth.date, birth.precision, birth.place), ("1867", "annee", "El Fictif, Tunisie"))
        birth = persons.parse_birth("13/11/1898 (Valence, Espagne)")
        self.assertEqual((birth.date, birth.place), ("1898-11-13", "Valence, Espagne"))

    def test_corrected_date_between_brackets(self) -> None:
        birth = persons.parse_birth("18 octobre 1842 [8 octobre 1842] (Lodz, Pologne)")
        self.assertEqual((birth.date, birth.alt_date, birth.place), ("1842-10-18", "1842-10-08", "Lodz, Pologne"))

    def test_nested_parentheses_are_kept(self) -> None:
        birth = persons.parse_birth("Né(e) le 1 janvier 1870 (Aït Fictif (Aïn Exemple mixte) (Alger))")
        self.assertEqual(birth.place, "Aït Fictif (Aïn Exemple mixte) (Alger)")

    def test_place_without_date_and_unspecified(self) -> None:
        birth = persons.parse_birth(", Fictiveville, Moselle, France.")
        self.assertEqual((birth.date, birth.year, birth.place), ("", None, "Fictiveville, Moselle, France"))
        self.assertEqual(persons.parse_birth("Né(e) à (Alger)").place, "Alger")
        empty = persons.parse_birth("non précisée.")
        self.assertEqual((empty.date, empty.place, empty.raw), ("", "", "non précisée."))


class ParseNameTest(unittest.TestCase):
    def test_plain(self) -> None:
        name = persons.parse_name("  Testaoui,   Amar ben Exemple ")
        self.assertEqual((name.raw, name.surname, name.given), ("Testaoui, Amar ben Exemple", "Testaoui", "Amar ben Exemple"))

    def test_married_name_then_birth_name(self) -> None:
        name = persons.parse_name("Fictivo née Modèle, Rosa Lucie")
        self.assertEqual((name.surname, name.maiden, name.given), ("Fictivo", "Modèle", "Rosa Lucie"))
        name = persons.parse_name("FICTIVO, née MODELE, Lucie Jeanne")
        self.assertEqual((name.surname, name.maiden, name.given), ("FICTIVO", "MODELE", "Lucie Jeanne"))

    def test_birth_name_first(self) -> None:
        name = persons.parse_name("MODELE femme FICTIVO, Rosa")
        self.assertEqual((name.surname, name.married, name.given), ("MODELE", "FICTIVO", "Rosa"))
        self.assertIn("nom-de-naissance-en-premier", name.flags)

    def test_birth_name_alone(self) -> None:
        name = persons.parse_name("Née Modèle, Anne Lucie")
        self.assertEqual((name.surname, name.maiden, name.given), ("Modèle", "Modèle", "Anne Lucie"))
        self.assertIn("nom-de-naissance-seul", name.flags)

    def test_alias_variant_and_postposed_particle(self) -> None:
        self.assertEqual(persons.parse_name("FICTIF, Antoine dit Tonin").given, "Antoine dit Tonin")
        name = persons.parse_name("Modèle [Modelski], Luc")
        self.assertEqual((name.surname, name.variants), ("Modèle", "Modelski"))
        name = persons.parse_name("Exemple (di), Tonin")
        self.assertEqual(name.surname, "di Exemple")

    def test_mention_between_parentheses(self) -> None:
        name = persons.parse_name("Testaoui ( rejet en date du 3 mai 1870 ), Ahmed ben Fictif")
        self.assertEqual((name.surname, name.given), ("Testaoui", "Ahmed ben Fictif"))
        self.assertEqual(name.mention, "rejet en date du 3 mai 1870")

    def test_no_comma_and_trailing_comma(self) -> None:
        name = persons.parse_name("Mohamed Ben Fictif")
        self.assertEqual((name.surname, name.given), ("Mohamed Ben Fictif", ""))
        self.assertIn("sans-virgule", name.flags)
        name = persons.parse_name("BEN FICTIF BEN EXEMPLE,")
        self.assertEqual((name.raw, name.surname, name.given), ("BEN FICTIF BEN EXEMPLE,", "BEN FICTIF BEN EXEMPLE", ""))
        self.assertIn("virgule-finale", name.flags)

    def test_empty(self) -> None:
        self.assertEqual(persons.parse_name("").flags, ["vide"])


class SpouseAndChildrenTest(unittest.TestCase):
    def test_spouse_on_one_line(self) -> None:
        spouse = persons.parse_spouse("FICTIVO née SPECIMEN, Marie, née le 17 mars 1853 à Gênes, Italie.")
        self.assertEqual(spouse.role, "epouse")
        self.assertEqual(spouse.name_raw, "FICTIVO née SPECIMEN, Marie")
        self.assertEqual((spouse.name.surname, spouse.name.maiden), ("FICTIVO", "SPECIMEN"))
        self.assertEqual((spouse.birth.date, spouse.birth.place), ("1853-03-17", "Gênes, Italie"))
        self.assertEqual(spouse.birth.raw, "née le 17 mars 1853 à Gênes, Italie.")

    def test_spouse_name_only(self) -> None:
        spouse = persons.parse_spouse("MODELE, Lucette Anne")
        self.assertEqual((spouse.name_raw, spouse.birth.raw), ("MODELE, Lucette Anne", ""))

    def test_children_with_dates_in_parentheses(self) -> None:
        children = persons.parse_children("Lucette (8 novembre 1883), Odile (2 février 1886)")
        self.assertEqual([(c.name_raw, c.birth.date, c.pairing) for c in children],
                         [("Lucette", "1883-11-08", ""), ("Odile", "1886-02-02", "")])
        children = persons.parse_children("Aldo (07/10/1921, Paris) ; Remo Luc (19/02/1925)")
        self.assertEqual([(c.name_raw, c.birth.date, c.birth.place) for c in children],
                         [("Aldo", "1921-10-07", "Paris"), ("Remo Luc", "1925-02-19", "")])

    def test_children_as_parallel_lists_are_paired_by_rank_and_flagged(self) -> None:
        children = persons.parse_children("Paul ; Zohra né(e)(s) le 2 décembre 1879 ; 4 mai 1881")
        self.assertEqual([(c.name_raw, c.birth.date, c.pairing) for c in children],
                         [("Paul", "1879-12-02", "position"), ("Zohra", "1881-05-04", "position")])

    def test_children_lists_of_different_lengths_get_no_date(self) -> None:
        children = persons.parse_children("Anne ; Luc ; Marc né(e)(s) le 1 mai 1870 ; 2 juin 1872")
        self.assertEqual([c.name_raw for c in children], ["Anne", "Luc", "Marc"])
        for child in children:
            self.assertEqual((child.birth.date, child.birth.year, child.pairing), ("", None, "longueurs-differentes"))
            self.assertEqual(child.birth.raw, "1 mai 1870 ; 2 juin 1872")

    def test_unreadable_child_date_is_not_a_place(self) -> None:
        child = persons.parse_children("Aldo (26 avril 18790)")[0]
        self.assertEqual((child.birth.date, child.birth.place, child.birth.raw), ("", "", "26 avril 18790"))

    def test_bare_children(self) -> None:
        children = persons.parse_children("Jean ; Marie née le 3 mai 1890")
        self.assertEqual([(c.name_raw, c.birth.date) for c in children], [("Jean", ""), ("Marie", "1890-05-03")])


class DossierTest(unittest.TestCase):
    def test_forms(self) -> None:
        cases = {
            "90010 X 92": "90010 X 92",
            "90011 x 92": "90011 X 92",
            "90012X92": "90012 X 92",
            "10 001 X 93": "10001 X 93",
            "149 BX 30": "149 BX 30",
            "109bis X 12": "109 bis X 12",
            "2307 X 1902": "2307 X 1902",
            "90021 X 04 (numéro du dossier à consulter en sous-série BB/11)": "90021 X 04",
            "316 X 27 ; 3161 X 27": "316 X 27 ; 3161 X 27",
            "Numéro de dossier manquant": "",
            "": "",
        }
        for raw, expected in cases.items():
            self.assertEqual(persons.normalise_dossier(raw), expected, raw)


class PersonLinesTest(unittest.TestCase):
    def test_format_f1_natnum(self) -> None:
        fields = persons.parse_person_lines([
            "Naissance : 14 février 1851 (Strasbourg, Bas-Rhin)", "Lieu de résidence : Bône ( Constantine )",
            "Profession : tonnelier",
            "Épouse : Specimen, Odile, née le 9 octobre 1857 (Strasbourg, Bas-Rhin)",
            "Enfants : Paul ; Zohra né(e)(s) le 2 décembre 1879 ; 4 mai 1881"])
        self.assertEqual((fields.birth.year, fields.residence, fields.profession),
                         (1851, "Bône ( Constantine )", "tonnelier"))
        self.assertEqual([r.role for r in fields.relatives], ["epouse", "enfant", "enfant"])
        self.assertEqual(fields.unparsed, [])
        self.assertEqual(fields.line_count, 5)

    def test_format_f2_with_profession_from_the_birth_line(self) -> None:
        fields = persons.parse_person_lines([
            "Naissance : journalier, 7 mai 1865, Alger, Alger, Algérie.",
            "Lieu de résidence : Akbou, département de Constantine, Algérie."])
        self.assertEqual((fields.profession, fields.profession_from_birth_line), ("journalier", True))
        self.assertEqual(fields.birth.raw, "journalier, 7 mai 1865, Alger, Alger, Algérie.")

    def test_a_profession_line_wins_over_the_leak(self) -> None:
        fields = persons.parse_person_lines(["Naissance : journalier, 7 mai 1865, Alger.", "Profession : maçon."])
        self.assertEqual((fields.profession, fields.profession_from_birth_line), ("maçon.", False))

    def test_format_f3_list(self) -> None:
        fields = persons.parse_person_lines([
            "Né(e) le 1 janvier 1870 (Aït Fictif (Alger))", "Lieu de résidence : Douar des Beni Exemple (Alger)",
            "Profession : Cultivateur", "Épouse", "Specimen, Fatma bent Ali", "Née le 25 mai 1875 (Aït Fictif (Alger))",
            "Lieu de résidence : Douar des Beni Exemple", "Enfants",
            "Omar ; Zohra né(e)(s) le 12 septembre 1899 ; 23 octobre 1901"])
        self.assertEqual((fields.birth.year, fields.birth.conventional), (1870, True))
        self.assertEqual(fields.residence, "Douar des Beni Exemple (Alger)")
        spouse, first, second = fields.relatives
        self.assertEqual((spouse.name_raw, spouse.birth.year, spouse.residence),
                         ("Specimen, Fatma bent Ali", 1875, "Douar des Beni Exemple"))
        self.assertEqual([(c.name_raw, c.birth.year) for c in (first, second)], [("Omar", 1899), ("Zohra", 1901)])
        self.assertEqual(fields.unparsed, [])

    def test_format_f4_second_birth_line_belongs_to_the_spouse(self) -> None:
        fields = persons.parse_person_lines([
            "Naissance : 29/08/1895 (El-Fictif Constantine, Algérie)", "", "Profession : caporal",
            "Lieu de résidence : Alger (Alger)", "Épouse : MODELE, Lucette Anne",
            "Naissance : 13/11/1898 (Valence, Espagne)", "Origine(s) des parents : espagnole",
            "Enfant(s) : Aldo (07/10/1921), Remo Luc (19/02/1925)",
            "Mention de retrait : Décret du 05 mai 1942, J.O. du 15 mai 1942"])
        self.assertEqual((fields.birth.year, fields.birth.place), (1895, "El-Fictif Constantine, Algérie"))
        self.assertEqual(fields.relatives[0].birth.year, 1898)
        self.assertEqual(fields.parents_origin, "")
        self.assertEqual(len(fields.relatives), 3)
        self.assertIn("Mention de retrait : Décret du 05 mai 1942, J.O. du 15 mai 1942", fields.notes)
        self.assertEqual(fields.line_count, 8)

    def test_label_broken_by_a_colon_inside_the_place(self) -> None:
        fields = persons.parse_person_lines(["Né(e) le 10 septembre 1885 (Fictiveville, Seine : auj. Hauts-de-Seine)"])
        self.assertEqual(fields.birth.year, 1885)
        self.assertEqual(fields.unparsed, [])

    def test_birth_line_without_le(self) -> None:
        self.assertEqual(persons.parse_person_lines(["Né(e) 24 novembre 1866 (Paris)"]).birth.year, 1866)

    def test_unspecified_values_become_empty(self) -> None:
        fields = persons.parse_person_lines(["Naissance : non précisée.", "Profession : non précisé.",
                                             "Lieu de résidence : non précisé"])
        self.assertEqual((fields.birth.year, fields.profession, fields.residence), (None, "", ""))

    def test_lines_not_understood_are_kept(self) -> None:
        fields = persons.parse_person_lines(["Naissance : 3 mars 1845 (Paris)", "Texte que l'analyseur ne comprend pas"])
        self.assertEqual(fields.unparsed, ["Texte que l'analyseur ne comprend pas"])


if __name__ == "__main__":
    unittest.main()
