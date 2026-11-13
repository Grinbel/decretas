"""End-to-end tests on the synthetic corpus: XML -> SQLite -> site files."""
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from decretas.an import build, export, links, search

from .support import TIMESTAMP, build_all, load_columnar, make_corpus, rows


class DatabaseTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.directory = tempfile.TemporaryDirectory()
        cls.database, cls.site = build_all(Path(cls.directory.name))

    @classmethod
    def tearDownClass(cls) -> None:
        cls.directory.cleanup()

    def one(self, sql: str, *args: object) -> tuple:
        result = rows(self.database, sql, *args)
        self.assertEqual(len(result), 1, sql)
        return result[0]

    def test_inventories_are_in_chronological_order_without_the_root(self) -> None:
        self.assertEqual(rows(self.database, "SELECT inv, annee, trimestre, etat FROM inventaire ORDER BY rang"), [
            ("FRAN_IR_900001", 1883, None, "indexe"), ("FRAN_IR_900002", 1892, None, "partiel"),
            ("FRAN_IR_900003", 1905, None, "partiel"), ("FRAN_IR_900005", 1922, None, "partiel"),
            ("FRAN_IR_900007", 1926, 2, "indexe"), ("FRAN_IR_900004", 1931, None, "partiel"),
            ("FRAN_IR_900006", 1944, None, "image")])
        self.assertEqual(self.one("SELECT valeur FROM meta WHERE cle = 'inventaires_racine'"), ("FRAN_IR_900000",))

    def test_counts(self) -> None:
        self.assertEqual(self.one("SELECT COUNT(*) FROM decret"), (29,))
        self.assertEqual(self.one("SELECT COUNT(*) FROM personne"), (27,))
        self.assertEqual(self.one("SELECT COUNT(*) FROM apparente WHERE role = 'epouse'"), (5,))
        self.assertEqual(self.one("SELECT COUNT(*) FROM apparente WHERE role = 'enfant'"), (13,))

    def test_key_is_inventory_and_notice_id(self) -> None:
        found = rows(self.database, "SELECT inv, annee FROM decret WHERE notice_id = 'D1' ORDER BY inv")
        self.assertEqual(found, [("FRAN_IR_900006", 1944), ("FRAN_IR_900007", 1926)])

    def test_links_are_stored_as_written(self) -> None:
        notice, images = self.one("SELECT lien_notice, lien_images FROM decret WHERE notice_id = 'SB000003'")
        self.assertEqual(notice, "http://www.siv.archives-nationales.culture.gouv.fr/siv/UD/FRAN_IR_900001/SB000003")
        self.assertTrue(images.endswith("/SB000003/DAFANCH94_NUMJ000001_D"))
        self.assertEqual(self.one("SELECT lien_images FROM personne WHERE notice_id = 'c-aaa4'"), ("",))

    def test_decree_cote_is_read_from_both_unitid_types(self) -> None:
        self.assertEqual(self.one("SELECT cote, cote_source FROM decret WHERE notice_id = 'SB000001'"),
                         ("BB/34/387", "identifiant"))
        self.assertEqual(self.one("SELECT cote, cote_source FROM decret WHERE notice_id = 'idd_1892_05_03'"),
                         ("BB/34/402", "cote-de-consultation"))

    def test_suspicious_cote_is_flagged_with_a_suggestion(self) -> None:
        self.assertEqual(
            self.one("SELECT cote, cote_drapeau, cote_suggeree FROM decret WHERE notice_id = 'idd_1931_11_469_1'"),
            ("BB/11/477", "suspecte-bb11", "BB/34/477"))
        self.assertEqual(self.one("SELECT cote_drapeau FROM decret WHERE notice_id = 'idd_1892_11_01'"), ("absente",))

    def test_decree_dates_are_reconciled_with_a_flag(self) -> None:
        expected = {
            "idd_1892_05_03": ("1892-05-02", ""),
            "idd_1892_08_01": ("1892-08-02", "conflit-titre-retenu"),    # @normal says 1897
            "idd_1892_04_96": ("1892-04-23", "conflit-normal-retenu"),   # title says 30 April
            "idd_1892_07_08": ("1892-07-04", "conflit-titre-retenu"),    # text repeats the title
            "idd_1892_D_04_80": ("1892-04-07", "titre-seul"),            # no <unitdate>
            "idd_1892_10_10": ("1892-10-12", ""),                        # truncated title
            "D494": (None, "intervalle"),
        }
        for notice_id, wanted in expected.items():
            self.assertEqual(self.one("SELECT date, date_drapeau FROM decret WHERE notice_id = ?", notice_id), wanted,
                             notice_id)
        self.assertEqual(self.one("SELECT date_normal FROM decret WHERE notice_id = 'idd_1892_08_01'"), ("1897-08-02",))

    def test_algeria_classes(self) -> None:
        found = dict(rows(self.database, "SELECT classe_algerie, COUNT(*) FROM decret GROUP BY 1"))
        self.assertEqual(found, {"A1": 11, "A2": 1, "A3": 1, "R": 3, "-": 13})
        self.assertEqual(self.one("SELECT famille, classe_algerie FROM decret WHERE notice_id = 'idd_1892_09_01'"),
                         ("naturalisation", "A1"))
        self.assertEqual(self.one("SELECT classe_algerie, contexte FROM decret WHERE notice_id = 'E1'"),
                         ("A1", "Décrets de naturalisation de l'année 1944 (Alger)"))

    def test_decree_states(self) -> None:
        for notice_id, wanted in {"SB000001": "indexe", "idd_1905_01_09": "partiel", "AP001236": "image",
                                  "E1": "image"}.items():
            self.assertEqual(self.one("SELECT etat FROM decret WHERE notice_id = ? AND inv != 'FRAN_IR_900007'",
                                      notice_id), (wanted,), notice_id)

    def test_nested_decree_counts_its_own_persons(self) -> None:
        self.assertEqual(self.one("SELECT n_personnes, decret_parent FROM decret WHERE notice_id = 'AP002985'"),
                         (1, "AP002984"))
        self.assertEqual(self.one("SELECT n_personnes FROM decret WHERE notice_id = 'AP002984'"), (1,))

    def test_sub_decree_is_set_aside_and_listed(self) -> None:
        self.assertEqual(rows(self.database, "SELECT inv, notice_id FROM notice_ecartee"),
                         [("FRAN_IR_900005", "c-arm1")])
        self.assertEqual(self.one("SELECT COUNT(*) FROM personne WHERE notice_id = 'c-arm1'"), (0,))
        self.assertEqual(self.one("SELECT n_personnes FROM decret WHERE notice_id = 'YI003349'"), (1,))

    def test_name_not_entered_persons_are_kept(self) -> None:
        self.assertEqual(self.one("SELECT titre_brut, nom_brut, nom_non_saisi, naissance_annee FROM personne "
                                  "WHERE notice_id = 'id_1892_04_0282'"),
                         ("Décret de naturalisations du 14 avril 1892", "", 1, 1829))
        self.assertEqual(self.one("SELECT nom_brut, nom_non_saisi FROM personne WHERE notice_id = 'c-empty1'"), ("", 1))
        self.assertEqual(self.one("SELECT nom_non_saisi FROM personne WHERE notice_id = 'A_19400'"), (0,))

    def test_name_without_persname(self) -> None:
        self.assertEqual(self.one("SELECT nom_brut, nom, prenoms FROM personne WHERE notice_id = 'id_1905_01_0140'"),
                         ("TESTAOUI, Akli Ben Modèle", "TESTAOUI", "Akli Ben Modèle"))

    def test_raw_text_is_kept_next_to_parsed_fields(self) -> None:
        raw, date, place, profession, slipped = self.one(
            "SELECT naissance_brut, naissance_date, naissance_lieu, profession, profession_dans_naissance "
            "FROM personne WHERE notice_id = 'id_1892_05_0060'")
        self.assertEqual(raw, "journalier, 7 mai 1865, Alger, Alger, Algérie.")
        self.assertEqual((date, place, profession, slipped), ("1865-05-07", "Alger, Alger, Algérie", "journalier", 1))

    def test_birth_flags(self) -> None:
        self.assertEqual(self.one("SELECT naissance_conventionnelle FROM personne WHERE notice_id = 'c-aaa1'"), (1,))
        self.assertEqual(self.one("SELECT naissance_conventionnelle, naissance_precision FROM personne "
                                  "WHERE notice_id = 'id_1892_05_0063'"), (1, "annee"))
        self.assertEqual(self.one("SELECT naissance_suspecte, naissance_annee FROM personne "
                                  "WHERE notice_id = 'id_1892_05_0066'"), (1, 1964))
        self.assertEqual(self.one("SELECT naissance_date_corrigee FROM personne WHERE notice_id = 'id_1892_05_0064'"),
                         ("1842-10-08",))

    def test_dossier_and_dossier_cote(self) -> None:
        self.assertEqual(self.one("SELECT dossier_brut, dossier, cote_dossier FROM personne WHERE notice_id = 'c-list1'"),
                         ("90021 X 04 (numéro du dossier à consulter en sous-série BB/11)", "90021 X 04", ""))
        self.assertEqual(self.one("SELECT dossier, cote_dossier FROM personne WHERE notice_id = 'A_19166'"),
                         ("90031 X 31", "19770874/9002"))
        self.assertEqual(self.one("SELECT dossier_brut, dossier FROM personne WHERE notice_id = 'id_1892_04_0282'"),
                         ("Numéro de dossier manquant", ""))

    def test_spouse_and_children(self) -> None:
        found = rows(self.database,
                     "SELECT a.role, a.nom_brut, a.naissance_annee, a.appariement FROM apparente a JOIN personne p "
                     "USING(personne_id) WHERE p.notice_id = 'c-aaa3' ORDER BY a.rang")
        self.assertEqual(found, [("epouse", "Specimen, Odile", 1857, ""), ("enfant", "Paul", 1879, "position"),
                                 ("enfant", "Zohra", 1881, "position")])
        found = rows(self.database,
                     "SELECT a.nom_brut, a.naissance_annee, a.naissance_brut, a.appariement FROM apparente a "
                     "JOIN personne p USING(personne_id) WHERE p.notice_id = 'c-aaa4' ORDER BY a.rang")
        self.assertEqual(found, [(name, None, "1 mai 1870 ; 2 juin 1872", "longueurs-differentes")
                                 for name in ("Anne", "Luc", "Marc")])
        self.assertEqual(self.one("SELECT a.nom_brut, a.naissance_annee, a.residence FROM apparente a JOIN personne p "
                                  "USING(personne_id) WHERE p.notice_id = 'c-list1' AND a.role = 'epouse'"),
                         ("Specimen, Fatma bent Ali", 1875, "Douar des Beni Exemple"))
        self.assertEqual(self.one("SELECT a.naissance_annee FROM apparente a JOIN personne p USING(personne_id) "
                                  "WHERE p.notice_id = 'A_19166' AND a.role = 'epouse'"), (1898,))

    def test_hints_and_tier(self) -> None:
        expected = {
            "id_1892_05_0060": ("M", "ne-en-algerie(explicite)+prenom-musulman+filiation", 1),
            "c-bbb2": ("N", "ne-en-algerie(explicite)", 1),      # born in Algeria, decree of another class
            "c-n1": ("E", "ne-alsace-lorraine", 1),              # lives in Algeria
            "c-bbb1": ("E", "ne-italie", 0),
            "c-ccc1": ("L", "profession-legion", 1),
            "id_1892_05_0065": ("T", "ne-tunisie", 1),
            "A_19200": ("I", "aucune-regle", 0),
            "A_19300": ("I", "aucune-regle", 1),                 # under a rejection naming Algeria
        }
        for notice_id, wanted in expected.items():
            self.assertEqual(self.one("SELECT indice, regle, palier_algerie FROM personne WHERE notice_id = ?",
                                      notice_id), wanted, notice_id)

    def test_unparsed_lines_are_listed(self) -> None:
        self.assertEqual(rows(self.database, "SELECT inv, notice_id, texte FROM ligne_incomprise"),
                         [("FRAN_IR_900002", "id_1892_05_0066", "Texte que l'analyseur ne comprend pas")])

    def test_search(self) -> None:
        connection = sqlite3.connect(self.database)
        try:
            result = search.search(connection, ["testaoui", "tahar", "miloud"])
            self.assertEqual(len(result.correspondences), 1)
            record = search.describe(connection, result.correspondences[0].person_id)
            self.assertEqual((record["notice"], record["decret_notice"]), ("c-n3", "YI003349"))
            # a term found on a child, a variant, a partial correspondence naming the absent term
            result = search.search(connection, ["exempli", "zohra"])
            self.assertEqual([c.hits[1].role for c in result.correspondences], ["enfant", "enfant"])
            result = search.search(connection, ["testaoui", "mohamed,mohammed", "absentissime"])
            self.assertEqual(result.correspondences, [])
            self.assertEqual({tuple(c.missing) for c in result.partial}, {("absentissime",)})
            self.assertEqual(len(result.partial), 3)
            # birth-year filter, +-5 years
            near = search.search(connection, ["testaoui"], born_around=1876)
            self.assertEqual([search.describe(connection, c.person_id)["notice"] for c in near.correspondences],
                             ["c-n3", "c-q1"])
            self.assertEqual(len(search.search(connection, ["testaoui"]).correspondences), 6)
            self.assertEqual(len(search.search(connection, ["factice"]).correspondences), 2)
            self.assertEqual(len(search.search(connection, ["factice"], tier_only=True).correspondences), 1)
        finally:
            connection.close()


class ExportTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.directory = tempfile.TemporaryDirectory()
        cls.database, cls.site = build_all(Path(cls.directory.name))
        cls.decree_document, cls.decrees = load_columnar(cls.site / "an-decrets.json")
        cls.person_document, cls.persons = load_columnar(cls.site / "an-personnes.json")
        cls.meta = json.loads((cls.site / "an-meta.json").read_text(encoding="utf-8"))

    @classmethod
    def tearDownClass(cls) -> None:
        cls.directory.cleanup()

    def decree(self, notice: str, inventory: str | None = None) -> dict:
        tables = self.decree_document["tables"]
        found = [d for d in self.decrees if d["notice"] == notice
                 and (inventory is None or tables["inv"][d["inv"]] == inventory)]
        self.assertEqual(len(found), 1, notice)
        return found[0]

    def person(self, notice: str) -> dict:
        found = [p for p in self.persons if p["notice"] == notice]
        self.assertEqual(len(found), 1, notice)
        return found[0]

    def test_documented_fields(self) -> None:
        self.assertEqual(self.decree_document["champs"], list(export.DECREE_FIELDS))
        self.assertEqual(self.person_document["champs"], list(export.PERSON_FIELDS))
        self.assertEqual(self.decree_document["format"], "decretas-an-decrets/1")
        self.assertEqual(self.person_document["format"], "decretas-an-personnes/1")

    def test_ids_are_row_positions(self) -> None:
        self.assertEqual([d["id"] for d in self.decrees], list(range(len(self.decrees))))
        self.assertEqual([p["id"] for p in self.persons], list(range(len(self.persons))))

    def test_every_algeria_class_decree_is_exported_even_image_only(self) -> None:
        classes = self.decree_document["tables"]["classe"]
        states = self.decree_document["tables"]["etat"]
        counts: dict[str, int] = {}
        for decree in self.decrees:
            counts[classes[decree["classe"]]] = counts.get(classes[decree["classe"]], 0) + 1
        self.assertEqual(counts, {"A1": 11, "A2": 1, "A3": 1, "R": 3, "-": 2})
        self.assertEqual(states[self.decree("E1")["etat"]], "image")
        self.assertEqual(states[self.decree("AP001236")["etat"]], "image")
        self.assertEqual(states[self.decree("AP001237")["etat"]], "image")

    def test_decree_of_another_class_follows_its_exported_person(self) -> None:
        decree = self.decree("SB000002")
        self.assertEqual(self.decree_document["tables"]["classe"][decree["classe"]], "-")
        self.assertEqual((decree["n_pers"], decree["n_exp"]), (2, 1))
        self.assertEqual(self.person("c-bbb2")["dec"], decree["id"])
        self.assertFalse([p for p in self.persons if p["notice"] == "c-bbb1"])

    def test_decree_row(self) -> None:
        tables = self.decree_document["tables"]
        decree = self.decree("idd_1931_11_469_1")
        self.assertEqual(tables["inv"][decree["inv"]], "FRAN_IR_900004")
        self.assertEqual((decree["date"], decree["annee"], decree["trim"]), ("1931-11-18", 1931, None))
        self.assertEqual(decree["titre"], "Décret d’admission aux droits de citoyen français (Algérie) du 18 novembre 1931")
        self.assertEqual(tables["famille"][decree["famille"]], "admission-citoyen")
        self.assertEqual((decree["cote"], tables["drap_cote"][decree["drap_cote"]], decree["cote_sug"]),
                         ("BB/11/477", "suspecte-bb11", "BB/34/477"))
        self.assertIsNone(decree["doc"])
        quarterly = self.decree("D1", "FRAN_IR_900007")
        self.assertEqual((quarterly["annee"], quarterly["trim"], quarterly["doc"]), (1926, 2, "document 12"))
        self.assertEqual(tables["drap_date"][self.decree("idd_1892_04_96")["drap_date"]], "conflit-normal-retenu")
        self.assertEqual(self.decree("E1")["contexte"], "Décrets de naturalisation de l'année 1944 (Alger)")

    def test_person_row(self) -> None:
        tables = self.person_document["tables"]
        person = self.person("id_1892_05_0060")
        self.assertEqual((tables["role"][person["role"]], person["princ"]), ("principal", person["id"]))
        self.assertEqual(person["nom"], "TESTAOUI, Mohamed ben Fictif")
        self.assertEqual((person["an"], tables["prec"][person["prec"]]), (1865, "jour"))
        self.assertEqual(person["naiss"], "journalier, 7 mai 1865, Alger, Alger, Algérie.")
        self.assertEqual((person["lieu"], person["prof"]), ("Alger, Alger, Algérie", "journalier"))
        self.assertEqual((person["dossier"], person["cote"], person["img"]), ("90010 X 92", "BB/11/90010", 0))
        self.assertEqual(tables["ind"][person["ind"]], "M")
        self.assertEqual(tables["regle"][person["regle"]], "ne-en-algerie(explicite)+prenom-musulman+filiation")
        self.assertEqual((tables["nea"][person["nea"]], tables["rea"][person["rea"]]), ("explicite", "explicite"))
        self.assertEqual(self.decrees[person["dec"]]["notice"], "idd_1892_05_03")
        self.assertEqual(self.person("c-aaa1")["img"], 1)

    def test_precision_codes(self) -> None:
        precisions = self.person_document["tables"]["prec"]
        self.assertEqual(precisions[self.person("c-aaa1")["prec"]], "conventionnelle")
        self.assertEqual(precisions[self.person("id_1892_05_0066")["prec"]], "suspecte")
        self.assertEqual(precisions[self.person("id_1931_11_1301")["prec"]], "annee")

    def test_spouse_and_children_follow_their_principal(self) -> None:
        roles = self.person_document["tables"]["role"]
        precisions = self.person_document["tables"]["prec"]
        principal = self.person("c-aaa3")
        family = self.persons[principal["id"] + 1:principal["id"] + 4]
        self.assertEqual([(roles[p["role"]], p["nom"], p["an"], p["princ"]) for p in family], [
            ("epouse", "Specimen, Odile", 1857, principal["id"]), ("enfant", "Paul", 1879, principal["id"]),
            ("enfant", "Zohra", 1881, principal["id"])])
        self.assertEqual([precisions[p["prec"]] for p in family], ["jour", "position", "position"])
        self.assertEqual(family[0]["naiss"], "née le 9 octobre 1857 (Strasbourg, Bas-Rhin)")
        self.assertTrue(all(p["notice"] is None and p["dec"] == principal["dec"] for p in family))
        unpaired = self.persons[self.person("c-aaa4")["id"] + 1]
        self.assertEqual((unpaired["an"], precisions[unpaired["prec"]], unpaired["naiss"]),
                         (None, "liste-non-appariee", "1 mai 1870 ; 2 juin 1872"))

    def test_filae_years_are_withheld_by_default(self) -> None:
        states = self.decree_document["tables"]["etat"]
        self.assertFalse([p for p in self.persons if p["nom"] and "Lounis" in p["nom"]])
        self.assertFalse([p for p in self.persons if p["notice"] in ("id_1905_01_0140", "c-list1", "c-empty1")])
        withheld = self.decree("idd_1905_01_09")
        self.assertEqual((states[withheld["etat"]], withheld["n_pers"], withheld["n_exp"]), ("retenu-filae", 3, 0))
        filae = self.meta["filae"]
        self.assertFalse(filae["noms_inclus"])
        self.assertEqual(filae["individus_concernes"], {
            "notices_de_personnes_du_corpus": 3, "principaux_du_palier_algerie": 3,
            "epouses_et_enfants_du_palier_algerie": 4})
        self.assertIn(1905, filae["annees"])
        self.assertTrue(any(item["code"] == "retenu-filae" and item["periode"] == "1905"
                            for item in self.meta["non_couvert"]))

    def test_link_ids_and_exceptions(self) -> None:
        # an-meta.json names entries of the ONE link table (site/contenu/liens.json); it holds no address
        self.assertEqual(self.meta["table_des_liens"], "contenu/liens.json")
        self.assertEqual(self.meta["liens"], [
            {"nom": "inventaire", "id": "an-inventaire", "variables": {"inventaire": "inv"}},
            {"nom": "notice", "id": "an-notice", "variables": {"inventaire": "inv", "notice": "notice"}},
            {"nom": "images", "id": "an-images-notice", "variables": {"inventaire": "inv", "notice": "notice"}}])
        self.assertNotIn("http", json.dumps(self.meta["liens"]))
        content = {entry["id"]: entry for entry in json.loads(
            links.CONTENT_TABLE_PATH.read_text(encoding="utf-8"))["liens"]}
        table = {}
        for entry in self.meta["liens"]:      # what the site does: take the template, rename its placeholders
            template = content[entry["id"]]["gabarit"]
            for placeholder, data_field in entry["variables"].items():
                template = template.replace("{" + placeholder + "}", "{" + data_field + "}")
            table[entry["nom"]] = {"gabarit": template.replace("https://", "http://", 1)}
        # every link rebuilt from the table equals the link copied from the XML (which writes http://),
        # exceptions aside
        connection = sqlite3.connect(self.database)
        try:
            copied = {(inv, notice): (notice_link, image_link) for inv, notice, notice_link, image_link in
                      connection.execute("SELECT inv, notice_id, lien_notice, lien_images FROM decret")}
        finally:
            connection.close()
        inventories = self.decree_document["tables"]["inv"]
        exceptions = self.decree_document["liens_particuliers"]
        for decree in self.decrees:
            inv = inventories[decree["inv"]]
            notice_link, image_link = copied[(inv, decree["notice"])]
            key = str(decree["id"])
            self.assertEqual(exceptions["notice"].get(key, table["notice"]["gabarit"].format(
                inv=inv, notice=decree["notice"])), notice_link)
            self.assertEqual(exceptions["images"].get(key, table["images"]["gabarit"].format(
                inv=inv, notice=decree["notice"])), image_link)
        odd = self.decree("SB000003")
        self.assertEqual(list(exceptions["images"]), [str(odd["id"])])
        self.assertEqual(self.meta["liens_particuliers_inventaires"], {})
        self.assertEqual(links.TEMPLATES["inventaire"].build_xml_form("FRAN_IR_900001"),
                         "http://www.siv.archives-nationales.culture.gouv.fr/siv/IR/FRAN_IR_900001")

    def test_coverage_per_year_and_quarter(self) -> None:
        fields = self.meta["couverture_annees"]["champs"]
        years = {row[0]: dict(zip(fields, row)) for row in self.meta["couverture_annees"]["lignes"]}
        self.assertEqual(sorted(years), [1883, 1892, 1905, 1922, 1926, 1931, 1944])
        self.assertEqual((years[1883]["etat"], years[1883]["decrets"], years[1883]["decrets_avec_noms"]), ("indexe", 3, 3))
        partial = years[1905]
        self.assertEqual((partial["etat"], partial["decrets"], partial["decrets_avec_noms"]), ("partiel", 4, 1))
        self.assertEqual((partial["alg_decrets"], partial["alg_avec_noms"], partial["a1"], partial["r"]), (3, 1, 2, 1))
        self.assertEqual((partial["filae"], partial["noms_exportes"], partial["personnes_exportees"]), (True, False, 0))
        self.assertEqual((years[1944]["etat"], years[1944]["a3"], years[1944]["personnes"]), ("image", 1, 0))
        quarters = [dict(zip(fields, row)) for row in self.meta["couverture_trimestres"]["lignes"]]
        self.assertEqual([(q["annee"], q["trim"], q["etat"]) for q in quarters], [(1926, 2, "indexe")])
        codes = {(item["code"], item["periode"]) for item in self.meta["non_couvert"]}
        self.assertTrue({("image-seule", "1944"), ("partiel", "1905"), ("jugements-1919", "1919-1962")} <= codes)

    def test_meta_counts_credit_and_integrity(self) -> None:
        self.assertEqual(self.meta["genere_le"], TIMESTAMP)
        exported = self.meta["comptes"]["exporte"]
        self.assertEqual((exported["decrets"], exported["occurrences_de_noms"]), (len(self.decrees), len(self.persons)))
        self.assertEqual(self.meta["comptes"]["corpus"]["notices_ecartees"], 1)
        credit = self.meta["credit"]
        self.assertEqual(credit["gabarit"], "Archives nationales de France ; {cote} ; {lieu} ; {date}")
        self.assertEqual((credit["lieu_de_conservation"], credit["date_des_informations"]), ("Pierrefitte", "2026-10-16"))
        import hashlib
        for name, entry in self.meta["fichiers"].items():
            data = (self.site / name).read_bytes()
            self.assertEqual((entry["octets"], entry["sha256"]), (len(data), hashlib.sha256(data).hexdigest()))


class FilaeIncludedTest(unittest.TestCase):
    def test_include_filae_exports_the_names(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _, site = build_all(Path(directory), include_filae=True)
            document, decrees = load_columnar(site / "an-decrets.json")
            _, persons = load_columnar(site / "an-personnes.json")
            meta = json.loads((site / "an-meta.json").read_text(encoding="utf-8"))
        names = [p["nom"] for p in persons]
        self.assertIn("Exempli, Lounis ben Akli", names)
        self.assertIn("Specimen, Fatma bent Ali", names)
        self.assertIn(None, names)                     # the "name not entered" person of 1905
        decree = next(d for d in decrees if d["notice"] == "idd_1905_01_09")
        self.assertEqual((document["tables"]["etat"][decree["etat"]], decree["n_exp"]), ("partiel", 3))
        self.assertTrue(meta["filae"]["noms_inclus"])
        self.assertEqual(meta["filae"]["individus_concernes"]["principaux_du_palier_algerie"], 3)
        self.assertFalse(any(item["code"] in ("retenu-filae", "clause-filae") for item in meta["non_couvert"]))


class DeterminismTest(unittest.TestCase):
    def test_two_builds_are_byte_identical_apart_from_the_timestamp(self) -> None:
        # same YEAR: the privacy rule depends on the year of the timestamp, and on nothing else of it
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            database_a, site_a = build_all(Path(first), timestamp="2026-01-01T00:00:00Z")
            database_b, site_b = build_all(Path(second), timestamp="2026-12-31T23:59:59Z")
            self.assertEqual(database_a.read_bytes(), database_b.read_bytes())
            for name in ("an-decrets.json", "an-personnes.json"):
                self.assertEqual((site_a / name).read_bytes(), (site_b / name).read_bytes(), name)
            meta_a = json.loads((site_a / "an-meta.json").read_text(encoding="utf-8"))
            meta_b = json.loads((site_b / "an-meta.json").read_text(encoding="utf-8"))
            self.assertNotEqual(meta_a.pop("genere_le"), meta_b.pop("genere_le"))
            self.assertEqual(meta_a, meta_b)

    def test_the_database_does_not_depend_on_the_year_of_the_timestamp(self) -> None:
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            database_a, _ = build_all(Path(first), timestamp="2026-01-01T00:00:00Z")
            database_b, _ = build_all(Path(second), timestamp="2040-01-01T00:00:00Z")
            self.assertEqual(database_a.read_bytes(), database_b.read_bytes())

    def test_same_timestamp_gives_identical_meta(self) -> None:
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            _, site_a = build_all(Path(first))
            _, site_b = build_all(Path(second))
            self.assertEqual((site_a / "an-meta.json").read_bytes(), (site_b / "an-meta.json").read_bytes())


class FailureTest(unittest.TestCase):
    def test_empty_source_and_missing_database(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(build.BuildError):
                build.build_database(Path(directory), Path(directory) / "an.sqlite")
            with self.assertRaises(export.ExportError):
                export.export_site(Path(directory) / "absent.sqlite", Path(directory) / "site",
                                   include_filae=False, timestamp=TIMESTAMP)

    def test_broken_manifest_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            raw = make_corpus(Path(directory))
            (raw / "manifest.jsonl").write_text("{pas du json\n", encoding="utf-8")
            with self.assertRaises(build.BuildError):
                build.build_database(raw, Path(directory) / "an.sqlite")


if __name__ == "__main__":
    unittest.main()
