"""Regression tests of the defects found by the review of 2026-11-11.

Every person, name, place detail and dossier number below is invented; only the shapes met in the
real inventories are reproduced.
"""
import json
import tempfile
import unittest
from pathlib import Path

from decretas.an import build, export, gazetteer, hints, persons, taxonomy

from .support import TIMESTAMP, load_columnar

SAFE = frozenset({"alger", "oran", "constantine", "bone", "blida"})

NOTICE_LINK = "http://www.siv.archives-nationales.culture.gouv.fr/siv/UD/FRAN_IR_900010/{id}"
IMAGE_LINK = "http://www.siv.archives-nationales.culture.gouv.fr/siv/media/FRAN_IR_900010/{id}/"


def hint(name: str, birth_place: str = "", **overrides: object) -> hints.Hint:
    arguments = dict(name=name, birth_place=birth_place, birth_parents="", parents_origin="", residence="",
                     profession="", other_text="", decree_admits=False, safe_localities=SAFE)
    arguments.update(overrides)
    return hints.classify_person(**arguments)  # type: ignore[arg-type]


def person(notice_id: str, name: str, lines: list[str]) -> str:
    content = "".join(f"<p>{line}</p>" for line in lines)
    return (f'<c id="{notice_id}" xlink:type="simple" xlink:href="{NOTICE_LINK.format(id=notice_id)}"><did>'
            f'<unitid type="cote-de-consultation">BB/11/90100</unitid><unitid type="pieces">90100 X 20</unitid>'
            f"<unittitle><persname>{name}</persname></unittitle></did><scopecontent>{content}</scopecontent></c>")


def decree(notice_id: str, title: str, normal: str, text: str, body: str = "") -> str:
    return (f'<c id="{notice_id}" xlink:type="simple" xlink:href="{NOTICE_LINK.format(id=notice_id)}"><did>'
            f'<unitid type="identifiant">BB/34/446</unitid><unittitle>{title}</unittitle>'
            f'<unitdate calendar="gregorian" era="ce" normal="{normal}">{text}</unitdate></did>'
            f'<daogrp><daoloc href="{IMAGE_LINK.format(id=notice_id)}"/></daogrp>{body}</c>')


def inventory(title: str, body: str) -> str:
    return ('<?xml version="1.0" encoding="UTF-8"?><ead xmlns:xlink="http://www.w3.org/1999/xlink">'
            '<!-- Jeu d\'essai SYNTHÉTIQUE : personnes, noms et dossiers inventés. -->'
            '<eadheader><eadid xlink:type="simple" xlink:href="http://www.siv.archives-nationales.culture.gouv.fr/'
            f'siv/IR/FRAN_IR_900010">FRAN_IR_900010</eadid><filedesc><titlestmt><titleproper>{title}</titleproper>'
            '</titlestmt></filedesc></eadheader><archdesc><did><unitid>BB/34/446</unitid><physloc>Pierrefitte'
            f'</physloc></did><dsc>{body}</dsc></archdesc></ead>')


CORPUS = inventory("Décrets de naturalisation de l'année 1920 (janvier à mars)", "".join([
    decree("D1", "Décret de naturalisations du 5 janvier 1920", "1920-01-05", "5 janvier 1920", "".join([
        # one residence line, written after the spouse: the household's residence
        person("p-menage", "Factice, Pierre", [
            "Naissance : 3 mai 1880 (Turin, Italie)",
            "Épouse : Modele, Lucie, née le 4 juin 1885 (Gênes, Italie)",
            "Lieu de résidence : Blida ( Alger )"]),
        # born in Tunisia of an Algerian father
        person("p-parents", "Testaoui, Amar ben Exemple", [
            "Naissance : 7 février 1890, Tunis, Tunisie, de père algérien.",
            "Lieu de résidence : Lyon, Rhône, France."]),
        # born in France of Italian parents; a spouse whose year cannot be right; a child born after the decree
        person("p-suspect", "Postiche, Jean", [
            "Naissance : 9 mars 1885, Lyon, Rhône, France, de parents italiens.",
            "Lieu de résidence : Lyon, Rhône, France.",
            "Épouse : Postiche née Inventee, Anne, née le 2 avril 1988 à Lyon, Rhône, France.",
            "Enfants : Paul (6 juin 1925), Rose (8 août 1912)"]),
    ])),
    decree("D2", "Décret de rejet de demandes de naturalisation (Tunisie, Maroc, colonies), d’admission aux droits "
                 "de citoyen français, de naturalisations à l’étranger du 9 février 1920", "1920-02-09",
           "9 février 1920"),
    decree("D3", "Décret de rejet de demandes de naturalisation (France), d'admission aux droits de citoyen "
                 "français (Madagascar, Cochinchine, colonies) du 11 mars 1920", "1920-03-11", "11 mars 1920"),
]))


class ResidenceTest(unittest.TestCase):
    def test_the_only_residence_line_written_after_the_spouse_is_the_household_residence(self) -> None:
        fields = persons.parse_person_lines([
            "Naissance : 3 mai 1880 (Turin, Italie)",
            "Épouse : Modele, Lucie, née le 4 juin 1885 (Gênes, Italie)",
            "Lieu de résidence : Blida ( Alger )"])
        self.assertEqual((fields.residence, fields.residence_from_spouse_line), ("Blida ( Alger )", True))
        self.assertEqual(fields.relatives[0].residence, "Blida ( Alger )")      # the spouse keeps it

    def test_an_empty_residence_line_of_the_principal_does_not_hide_the_household_residence(self) -> None:
        fields = persons.parse_person_lines([
            "Naissance : 04/05/1905 (Tunis Tunisie)", "Lieu de résidence :", "Épouse : MODELE, Lucette",
            "Naissance : 08/12/1911 (Tunis)", "Lieu de résidence : Oran"])
        self.assertEqual((fields.residence, fields.residence_from_spouse_line), ("Oran", True))

    def test_two_residences_stay_with_their_owner(self) -> None:
        fields = persons.parse_person_lines([
            "Naissance : 3 mai 1880 (Turin, Italie)", "Lieu de résidence : Marseille",
            "Épouse : Modele, Lucie, née le 4 juin 1885 (Gênes, Italie)", "Lieu de résidence : Blida"])
        self.assertEqual((fields.residence, fields.residence_from_spouse_line), ("Marseille", False))
        self.assertEqual(fields.relatives[0].residence, "Blida")

    def test_a_second_residence_line_of_the_principal_is_kept_and_counts_for_algeria(self) -> None:
        fields = persons.parse_person_lines([
            "Naissance : 3 mai 1860, Turin, Italie.", "Lieu de résidence : Paris, Seine, France.",
            "Lieu de résidence : Blida, département d'Alger, Algérie."])
        self.assertEqual(fields.residence, "Paris, Seine, France.")
        self.assertEqual(fields.other_residences, ["Blida, département d'Alger, Algérie."])
        result = hint("Factice, Pierre", "Turin, Italie", residence=fields.residence,
                      other_residences=tuple(fields.other_residences))
        self.assertEqual(result.lives_in_algeria, "explicite")

    def test_a_list_of_unspecified_components_is_empty(self) -> None:
        fields = persons.parse_person_lines([
            "Naissance : 7 juin 1869, non précisé, non précisé.",
            "Lieu de résidence : non précisé, non précisé, non précisé."])
        self.assertEqual((fields.residence, fields.birth.place, fields.birth.year), ("", "", 1869))
        kept = persons.parse_person_lines(["Lieu de résidence : non précisé, non précisé ; Algérie."])
        self.assertEqual(kept.residence, "non précisé, non précisé ; Algérie.")


class BirthLineLeakTest(unittest.TestCase):
    def test_only_a_text_that_reads_like_a_profession_is_taken_from_the_birth_line(self) -> None:
        cases = {
            "journalier, 7 mai 1865, Alger, Alger, Algérie.": "journalier",
            "maître d'hôtel, 7 mai 1865, Paris, Seine, France.": "maître d'hôtel",
            "marin, 7 mai 1865, Bône, Constantine, Algérie.": "marin",
            "octobre ou novembre 1842, Fictiveville, Russie.": "",
            "'1853, Fictiveville, département d'Alger, Algérie.": "",
            "trouvée près de Fictiveville le 13 avril 1852, Fictiveville, France.": "",
        }
        for line, profession in cases.items():
            fields = persons.parse_person_lines(["Naissance : " + line])
            self.assertEqual((fields.profession, fields.profession_from_birth_line), (profession, bool(profession)), line)
            self.assertIsNotNone(fields.birth.year, line)


class ParentsClauseTest(unittest.TestCase):
    def test_the_adjective_algerien_is_not_a_place_of_birth(self) -> None:
        for place in ("Tunis, Tunisie, de père algérien", "Tunis, Tunisie: de parents algériens",
                      "Alexandrie, De père algérien [Egypte]",
                      "Fictiveville, Haut-Rhin, France employé au chemin de fer de l'Ouest algérien"):
            self.assertEqual(gazetteer.algeria_rule(place, SAFE), "", place)

    def test_born_abroad_of_algerian_parents(self) -> None:
        result = hint("Testaoui, Amar ben Exemple", "Tunis, Tunisie, de père algérien",
                      birth_parents="de père algérien")
        self.assertEqual((result.code, result.born_in_algeria, result.algerian_parents), ("M", "", True))
        self.assertEqual(result.rule, "parents-algeriens+ne-tunisie+prenom-musulman+filiation")
        plain = hint("Factice, Pierre", "Alexandrie, Egypte, de père algérien", birth_parents="de père algérien")
        self.assertEqual((plain.code, plain.rule, plain.born_in_algeria, plain.algerian_parents),
                         ("I", "parents-algeriens+ne-ailleurs", "", True))

    def test_natnum_form_country_of_the_parents_then_country_of_birth_between_brackets(self) -> None:
        abroad = hint("Testaoui, Amar", "Tunis, Algérie ( père ) [Tunisie]", birth_parents="Algérie ( père )")
        self.assertEqual((abroad.born_in_algeria, abroad.algerian_parents, abroad.code), ("", True, "M"))
        local = hint("Fictivo, Jean", "Alger, Espagne ( parents ) [Algérie]", birth_parents="Espagne ( parents )")
        self.assertEqual((local.born_in_algeria, local.code, local.rule),
                         ("explicite", "E", "ne-en-algerie(explicite)+parents-etrangers"))
        town = hint("Fictivo, Jean", "Bône, Italie ( parents )", birth_parents="Italie ( parents )")
        self.assertEqual((town.born_in_algeria, town.code), ("repertoire", "E"))

    def test_the_parents_country_is_not_the_country_of_birth(self) -> None:
        result = hint("Postiche, Jean", "Lyon, Rhône, France, de parents italiens", birth_parents="de parents italiens")
        self.assertEqual((result.code, result.rule), ("E", "ne-france+parents-etrangers"))
        unknown = hint("Postiche, Jean", "Fictiveville, de parents italiens", birth_parents="de parents italiens")
        self.assertEqual((unknown.code, unknown.rule), ("E", "parents-etrangers"))

    def test_moroccan_or_tunisian_parents_are_not_european(self) -> None:
        abroad = hint("Factice, Pierre", "Marseille, Bouches-du-Rhône, France: de parents tunisiens",
                      birth_parents="de parents tunisiens")
        self.assertEqual((abroad.code, abroad.rule), ("T", "ne-france+parents-etrangers"))
        local = hint("Factice, Pierre", "Oran, Maroc (parents)", birth_parents="Maroc (parents)")
        self.assertEqual((local.code, local.rule, local.born_in_algeria),
                         ("T", "ne-en-algerie(repertoire)+parents-etrangers", "repertoire"))

    def test_french_parents_are_not_foreign_parents(self) -> None:
        result = hint("Postiche, Jean", "Alger, Algérie, de parents français", birth_parents="de parents français")
        self.assertEqual((result.code, result.rule), ("N", "ne-en-algerie(explicite)+parents-francais"))

    def test_parsed_birth_feeds_the_hint(self) -> None:
        birth = persons.parse_birth("7 février 1890, Tunis, Tunisie, de père algérien.")
        self.assertEqual(birth.parents, "de père algérien")
        self.assertEqual(hints.birth_place_proper(birth.place, birth.parents).strip(" ,"), "Tunis, Tunisie")


class RejectionOfCitizenRightsTest(unittest.TestCase):
    def test_rejection_of_admissions_without_territory_is_class_r(self) -> None:
        cases = {
            "Décret de rejet de demandes de naturalisation et de réintégration (Tunisie, Maroc, colonies), "
            "d’admission aux droits de citoyen français, de naturalisations à l’étranger du 23 mars 1933": "R",
            "Décret de rejet de demandes d’admission aux droits de citoyen français, de naturalisation (Colonies) "
            "du 26 novembre 1933": "R",
            "Décrets de rejet des demandes de naturalisation en France (Tunisie, Maroc), d'admission aux droits de "
            "citoyen français (Madagascar, Cochinchine, colonies), de réintégration du 19 décembre 1934": "-",
            "Décret de rejet de naturalisations en France du 6 février 1905.": "-",
            "Décret d'admission aux droits de citoyen français (Madagascar) du 6 avril 1933": "-",
            "Décret d’admission aux droits de citoyen français du 2 août 1933": "A2",
        }
        for title, expected in cases.items():
            self.assertEqual(taxonomy.classify_decree(title).algeria_class, expected, title)


class TerritoryTest(unittest.TestCase):
    def test_misspelt_algeria_and_french_africa_are_territories(self) -> None:
        cases = {
            "Décret d'admission aux droits de citoyen français (Aglérie) du 5 septembre 1934": "A1",
            "Décret d’admissions aux droits de citoyens français (Afrique Équatoriale Française) du 28 mai 1935": "-",
            "Décret de rejet de naturalisations en France, en Algérie et en Afrique occidentale française, "
            "du 21 février 1928": "R",
        }
        for title, expected in cases.items():
            self.assertEqual(taxonomy.classify_decree(title).algeria_class, expected, title)


class BuiltCorpusTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.directory = tempfile.TemporaryDirectory()
        # a path with characters that break a naive "file:…?mode=ro" address
        root = Path(cls.directory.name) / "dossier #1 100% ?"
        raw = root / "raw"
        raw.mkdir(parents=True)
        (raw / "FRAN_IR_900010.xml").write_text(CORPUS, encoding="utf-8")
        cls.database = root / "an.sqlite"
        cls.site = root / "site"
        build.build_database(raw, cls.database)
        export.export_site(cls.database, cls.site, include_filae=False, timestamp=TIMESTAMP)
        cls.decree_document, cls.decrees = load_columnar(cls.site / "an-decrets.json")
        cls.person_document, cls.persons = load_columnar(cls.site / "an-personnes.json")
        cls.meta = json.loads((cls.site / "an-meta.json").read_text(encoding="utf-8"))

    @classmethod
    def tearDownClass(cls) -> None:
        cls.directory.cleanup()

    def row(self, notice: str) -> dict:
        return next(p for p in self.persons if p["notice"] == notice)

    def test_household_residence_puts_the_notice_in_the_tier(self) -> None:
        principal = self.row("p-menage")
        tables = self.person_document["tables"]
        self.assertEqual((principal["res"], tables["rea"][principal["rea"]]), ("Blida ( Alger )", "explicite"))
        self.assertEqual(self.persons[principal["id"] + 1]["res"], "Blida ( Alger )")
        connection = build.read_only(self.database)
        try:
            flags = dict(connection.execute("SELECT notice_id, residence_ligne_epouse FROM personne"))
        finally:
            connection.close()
        self.assertEqual(flags, {"p-menage": 1, "p-parents": 0, "p-suspect": 0})

    def test_algerian_parents_put_the_notice_in_the_tier_without_a_false_birth_in_algeria(self) -> None:
        principal = self.row("p-parents")
        tables = self.person_document["tables"]
        self.assertEqual(tables["nea"][principal["nea"]], "")
        self.assertEqual(tables["ind"][principal["ind"]], "M")
        self.assertEqual(tables["regle"][principal["regle"]], "parents-algeriens+ne-tunisie+prenom-musulman+filiation")
        self.assertEqual(principal["lieu"], "Tunis, Tunisie, de père algérien")
        self.assertFalse([p for p in self.persons if p["notice"] == "p-suspect"])      # nothing Algerian: not exported

    def test_impossible_years_of_spouses_and_children_are_flagged(self) -> None:
        connection = build.read_only(self.database)
        try:
            found = connection.execute(
                "SELECT a.role, a.naissance_annee, a.naissance_suspecte FROM apparente a JOIN personne p "
                "USING(personne_id) WHERE p.notice_id = 'p-suspect' ORDER BY a.rang").fetchall()
        finally:
            connection.close()
        self.assertEqual(found, [("epouse", 1988, 1), ("enfant", 1925, 1), ("enfant", 1912, 0)])

    def test_suspect_relative_is_published_as_suspect(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            raw = Path(directory) / "raw"
            raw.mkdir()
            corpus = CORPUS.replace("Décret de naturalisations du 5 janvier 1920",
                                    "Décret de naturalisations algériennes du 5 janvier 1920")
            (raw / "FRAN_IR_900010.xml").write_text(corpus, encoding="utf-8")
            build.build_database(raw, Path(directory) / "an.sqlite")
            export.export_site(Path(directory) / "an.sqlite", Path(directory) / "site", include_filae=False,
                               timestamp=TIMESTAMP)
            document, rows = load_columnar(Path(directory) / "site" / "an-personnes.json")
        principal = next(p for p in rows if p["notice"] == "p-suspect")
        family = rows[principal["id"] + 1:principal["id"] + 4]
        self.assertEqual([(document["tables"]["prec"][p["prec"]], p["an"]) for p in family],
                         [("suspecte", 1988), ("suspecte", 1925), ("jour", 1912)])

    def test_rejections_of_citizen_rights_are_exported_for_the_guided_search(self) -> None:
        classes = self.decree_document["tables"]["classe"]
        states = self.decree_document["tables"]["etat"]
        by_notice = {d["notice"]: d for d in self.decrees}
        self.assertEqual((classes[by_notice["D2"]["classe"]], states[by_notice["D2"]["etat"]]), ("R", "image"))
        self.assertNotIn("D3", by_notice)
        self.assertEqual(set(self.meta["classes"]), {"A1", "A2", "A3", "R", "-"})

    def test_wording_of_what_is_not_covered(self) -> None:
        items = {(item["code"], item["periode"]): item["texte"] for item in self.meta["non_couvert"]}
        self.assertIn(("partiel", "1920, 1er trimestre"), items)
        self.assertIn(("jugements-1919", "1919-1962"), items)
        text = " ".join(items.values())
        self.assertNotIn("1e trimestre", text)
        self.assertNotIn("concernant l'Algérie", text)       # A2, A3 and some R titles do not name Algeria
        self.assertNotIn("imposée par la société Filae", text)
        self.assertEqual(export.quarter_label(1), "1er trimestre")
        self.assertEqual(export.quarter_label(3), "3e trimestre")


class OldDatabaseTest(unittest.TestCase):
    def test_a_database_of_another_format_is_refused_in_french(self) -> None:
        import sqlite3

        from decretas.an import verify
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "an.sqlite"
            connection = sqlite3.connect(database)
            connection.executescript("CREATE TABLE meta(cle TEXT PRIMARY KEY, valeur TEXT NOT NULL);"
                                     "INSERT INTO meta VALUES('format', 'decretas-an-sqlite/1');")
            connection.close()
            with self.assertRaises(export.ExportError) as caught:
                export.export_site(database, Path(directory) / "site", include_filae=False, timestamp=TIMESTAMP)
            self.assertIn("relancer « construire »", str(caught.exception))
            with self.assertRaises(verify.VerifyError):
                verify.verify(Path(directory), database)
            self.assertFalse((Path(directory) / "site" / "an-personnes.json").exists())


if __name__ == "__main__":
    unittest.main()
