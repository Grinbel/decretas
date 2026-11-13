import tempfile
import unittest
from pathlib import Path

from decretas.an import gazetteer, hints, names, search

SAFE = frozenset({"alger", "oran", "constantine", "bone", "blida", "sidi bel abbes", "fort national", "dalmatie"})


def hint(name: str, birth_place: str = "", **overrides: object) -> hints.Hint:
    arguments = dict(name=name, birth_place=birth_place, birth_parents="", parents_origin="", residence="",
                     profession="", other_text="", decree_admits=False, safe_localities=SAFE)
    arguments.update(overrides)
    return hints.classify_person(**arguments)  # type: ignore[arg-type]


class AlgerianPlaceTest(unittest.TestCase):
    def test_explicit_markers(self) -> None:
        for place in ("Alger, Algérie", "Fictiveville, département d'Alger, Algérie", "Beni Fictif, département d'Oran",
                      "Bône ( Constantine )", "Aïn Fictif, Alger", "Fort-Fictif (Alger)", "Beni-Exemple, Constantine",
                      "Fictiveville, Kabylie", "Fictiveville, Agérie", "Bône, département de Constantine, France"):
            self.assertEqual(gazetteer.algeria_rule(place, SAFE), "explicite", place)

    def test_the_word_algerie_is_not_required(self) -> None:
        # The three forms the verification found missing with the single-word test.
        for place in ("Aïn Fictif, Alger", "Fort-Fictif (Alger)", "Beni-Exemple, Constantine"):
            self.assertNotIn("alg", place.lower().replace("alger", ""))
            self.assertTrue(gazetteer.algeria_rule(place, SAFE))

    def test_gazetteer_needs_the_first_component_and_no_other_country(self) -> None:
        self.assertEqual(gazetteer.algeria_rule("Blida", SAFE), "repertoire")
        self.assertEqual(gazetteer.algeria_rule("Sidi-bel-Abbès", SAFE), "repertoire")
        self.assertEqual(gazetteer.algeria_rule("commune mixte de Fort-National", SAFE), "repertoire")
        self.assertEqual(gazetteer.algeria_rule("Oran, Espagne", SAFE), "")
        self.assertEqual(gazetteer.algeria_rule("Vigorac, Dalmatie", SAFE), "")
        self.assertEqual(gazetteer.algeria_rule("Fictiveville", SAFE), "")
        self.assertEqual(gazetteer.algeria_rule("", SAFE), "")

    def test_false_friends(self) -> None:
        for place in ("Constantinople, Turquie", "Orange, Vaucluse", "Algerri, Espagne", "Alghero, Sardaigne"):
            self.assertEqual(gazetteer.algeria_rule(place, SAFE), "", place)

    def test_department_alone_as_first_component_needs_the_gazetteer(self) -> None:
        self.assertEqual(gazetteer.algeria_rule("Alger", frozenset()), "")
        self.assertEqual(gazetteer.algeria_rule("Alger", SAFE), "repertoire")

    def test_country(self) -> None:
        self.assertEqual(gazetteer.country_of("Fictiveville Maroc"), "maroc")
        self.assertEqual(gazetteer.country_of("Tunis, Tunisie"), "tunisie")
        self.assertEqual(gazetteer.country_of("Haguenau, Bas-Rhin"), "alsace-lorraine")
        self.assertEqual(gazetteer.country_of("Fictiveville"), "")

    def test_derive_and_reload(self) -> None:
        places = (["Fictiveville, Algérie"] * 4 + ["Fictiveville"] + ["Ambigu, Algérie"] * 3 + ["Ambigu, Italie"] * 2
                  + ["Rare, Algérie"] + ["Ailleurs, Algérie"] * 3 + ["Ailleurs, France"] * 9)
        rows = {row["nom"]: row for row in gazetteer.derive(places)}
        self.assertEqual(rows["fictiveville"]["statut"], "sur")
        self.assertEqual((rows["fictiveville"]["n_algerie"], rows["fictiveville"]["n_seul"]), ("4", "1"))
        self.assertEqual(rows["ambigu"]["statut"], "ambigu")
        self.assertEqual(rows["ailleurs"]["statut"], "surtout-ailleurs")
        self.assertNotIn("rare", rows)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "g.tsv"
            gazetteer.write(list(rows.values()), path)
            self.assertEqual(gazetteer.load_safe_localities(path), frozenset({"fictiveville"}))
            self.assertEqual(gazetteer.load_safe_localities(Path(directory) / "absent.tsv"), frozenset())

    def test_shipped_gazetteer(self) -> None:
        safe = gazetteer.load_safe_localities()
        self.assertTrue({"alger", "oran", "constantine", "bone", "sidi bel abbes"} <= safe)
        self.assertFalse({"castiglione", "nemours", "mondovi", "saint cloud", "algerie"} & safe)


class HintTest(unittest.TestCase):
    def test_probable_muslim_algerian_keeps_its_rule(self) -> None:
        result = hint("Testaoui, Mohamed ben Fictif", "Alger, Alger, Algérie")
        self.assertEqual(result.code, "M")
        self.assertEqual(result.rule, "ne-en-algerie(explicite)+prenom-musulman+filiation")
        self.assertEqual(result.born_in_algeria, "explicite")

    def test_given_name_also_used_as_a_family_name_elsewhere(self) -> None:
        self.assertEqual(hint("Testaoui, Amar ben Exemple", "Alger, Algérie").code, "M")
        self.assertEqual(hint("AMAR, Isaac", "Alger, Algérie").code, "N")
        self.assertEqual(hint("FICTIVO née COHEN, Fatma", "Alger, Algérie").code, "N")

    def test_born_in_algeria_without_marker(self) -> None:
        result = hint("Postiche, Antoine", "Blida")
        self.assertEqual((result.code, result.rule), ("N", "ne-en-algerie(repertoire)"))

    def test_foreign_parents_make_a_probable_european(self) -> None:
        result = hint("Fictivo, Jean", "Fictiveville, département d'Alger, Algérie, de parents italiens",
                      birth_parents="de parents italiens")
        self.assertEqual((result.code, result.rule), ("E", "ne-en-algerie(explicite)+parents-etrangers"))

    def test_moroccan_tunisian_european_legionnaire(self) -> None:
        self.assertEqual(hint("Specimen, Ali", "Tunis, Tunisie").code, "T")
        self.assertEqual(hint("Inventé, Paul", "Fictiveville Maroc").rule, "ne-maroc")
        self.assertEqual(hint("Factice, Pierre", "Turin, Italie").rule, "ne-italie")
        result = hint("Simulacre, Karl", "Berlin, Prusse", profession="soldat à la légion étrangère")
        self.assertEqual((result.code, result.rule), ("L", "profession-legion"))

    def test_residence_is_reported_next_to_the_hint(self) -> None:
        result = hint("Factice, Odette", "Strasbourg, Bas-Rhin, France", residence="Sidi-bel-Abbès")
        self.assertEqual((result.code, result.lives_in_algeria), ("E", "repertoire"))

    def test_weaker_rule_when_the_birth_place_is_not_recognised(self) -> None:
        result = hint("Testaoui, Akli ould Slimane", "Douar Fictif", decree_admits=True)
        self.assertEqual(result.code, "M")
        self.assertEqual(result.rule, "lieu-de-naissance-non-reconnu+prenom-musulman+filiation+decret-algerie")
        self.assertEqual(hint("Testaoui, Akli ould Slimane", "Douar Fictif").code, "I")
        self.assertEqual(hint("Testaoui, Mohamed", "", residence="Blida").rule,
                         "lieu-de-naissance-non-reconnu+prenom-musulman+reside-en-algerie")

    def test_weaker_rule_never_fires_when_another_country_is_named(self) -> None:
        self.assertNotEqual(hint("Exempli, Ahmed", "Bombay, Indes anglaises", decree_admits=True).code, "M")
        self.assertNotEqual(hint("Exempli, Ahmed", "", residence="Tunis, Tunisie", decree_admits=True).code, "M")

    def test_the_word_indigene_alone_is_not_enough_outside_algeria(self) -> None:
        result = hint("Rafictif", "Tananarive Madagascar", profession="médecin de l'assistance médicale indigène",
                      decree_admits=True)
        self.assertEqual(result.code, "I")

    def test_every_code_has_a_label(self) -> None:
        self.assertEqual(set(hints.HINT_LABELS), {"M", "N", "E", "T", "L", "I"})


class NameKeysTest(unittest.TestCase):
    def test_tokens(self) -> None:
        self.assertEqual(names.tokens("M'Hamed N'Aït Abd-el-Kader"), ["mhamed", "nait", "abd", "el", "kader"])

    def test_k1_safe_equivalences(self) -> None:
        self.assertEqual(names.k1("mohammed"), names.k1("mohamed"))
        self.assertEqual(names.k1("kacem"), names.k1("kassem"))
        self.assertEqual(names.k1("chaabane"), names.k1("chabane"))
        self.assertEqual(names.k1("youcef"), names.k1("youssef"))
        self.assertNotEqual(names.k1("belhadi"), names.k1("belhadj"))

    def test_k2_skeleton(self) -> None:
        self.assertEqual(len({names.k2(w) for w in ("belkacem", "belgacem", "belkassem")}), 1)
        self.assertEqual(names.k2("mahmoud"), names.k2("mohamed"))      # known collision, hence second rank
        self.assertNotEqual(names.k2("belhadi"), names.k2("belhadj"))
        self.assertNotEqual(names.k2("mohand"), names.k2("mohamed"))

    def test_attached_and_detached_forms(self) -> None:
        self.assertIn("belkacem", names.expand(["bel", "kacem"]))
        self.assertIn("chabane", names.expand(["benchabane"]))
        self.assertIn("zemri", names.expand(["ezzemri"]))
        self.assertIn("abdelkader", names.expand(["abd", "el", "kader"]))

    def test_query_never_falls_back_to_a_particle(self) -> None:
        term = search.make_term("Bel Hadi")
        self.assertEqual(term.keys[0], frozenset({"belhadi"}))
        self.assertNotIn(names.k2("hadj"), search.make_term("Belhadj").keys[2])
        self.assertNotIn("hadj", search.make_term("Belhadj").keys[0])

    def test_detached_query_form_is_only_a_loose_key(self) -> None:
        term = search.make_term("Benchabane,Belhadi")
        self.assertEqual(term.variants, ["Benchabane", "Belhadi"])
        self.assertEqual(term.keys[0], frozenset({"benchabane", "belhadi"}))
        self.assertIn(names.k2("chabane"), term.keys[2])
        self.assertIn(names.k2("hadi"), term.keys[2])
        self.assertNotIn(names.k1("hadi"), term.keys[1])

if __name__ == "__main__":
    unittest.main()
