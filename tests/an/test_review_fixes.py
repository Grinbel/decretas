"""Tests of the second review of 2026-11-11: possibly living persons, the one link table, the Algeria
tier through a spouse or a child, the second applicant, data-entry debris in relatives' names.

Every person, name, place detail and dossier number below is invented; only the shapes met in the
real inventories are reproduced.
"""
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from decretas.an import build, cli, export, links, persons, search, verify

from .support import TIMESTAMP, load_columnar
from .test_regressions import decree, inventory, person


def build_corpus(directory: Path, corpus: str, **options: object) -> tuple[Path, Path]:
    """Build the database and the site files of a one-inventory corpus. Returns (database, site dir)."""
    raw = directory / "raw"
    raw.mkdir(exist_ok=True)
    (raw / "FRAN_IR_900010.xml").write_text(corpus, encoding="utf-8")
    database = directory / "an.sqlite"
    build.build_database(raw, database)
    arguments: dict = {"include_filae": False, "timestamp": TIMESTAMP}
    arguments.update(options)
    export.export_site(database, directory / "site", **arguments)
    return database, directory / "site"


def load_site(site: Path) -> tuple[dict, list[dict], dict, list[dict], dict]:
    person_document, rows = load_columnar(site / "an-personnes.json")
    decree_document, decrees = load_columnar(site / "an-decrets.json")
    meta = json.loads((site / "an-meta.json").read_text(encoding="utf-8"))
    return person_document, rows, decree_document, decrees, meta


def family_of(rows: list[dict], document: dict, notice: str) -> list[tuple[str, str]]:
    """(role, name) of the rows attached to one principal, the principal first."""
    principal = next(p for p in rows if p["notice"] == notice)
    roles = document["tables"]["role"]
    return [(roles[p["role"]], p["nom"]) for p in rows if p["princ"] == principal["id"]]


# ----------------------------------------------------------------------------- possibly living persons

# A register of 1929, generated in 2026: the threshold year is 1926.
PRIVACY_CORPUS = inventory("Décrets de naturalisation de l'année 1929 (janvier à mars)", "".join([
    decree("D1", "Décret de naturalisations algériennes du 5 janvier 1929", "1929-01-05", "5 janvier 1929", "".join([
        # an old family: only the child born in 1927 is withheld
        person("p-ancien", "Factice, Pierre", [
            "Naissance : 3 mai 1890, Turin, Italie.",
            "Épouse : Factice née Modele, Lucie, née le 4 juin 1895 à Gênes, Italie.",
            "Enfants : Paul (6 juin 1920), Rose (8 août 1927)"]),
        # a principal born in 1926: the whole notice is withheld
        person("p-recent", "Postiche, Jeanne", ["Naissance : 3 mai 1926, Oran, Algérie."]),
        # no birth line under a decree of 1929: the principal may be a child; the spouse goes with the notice
        person("p-inconnu", "Specimen, Louis", [
            "Lieu de résidence : Oran, Algérie.",
            "Épouse : Specimen née Exempli, Marthe, née le 2 février 1900 à Oran, Algérie."]),
        # two parallel lists: the pairing is unverified, the latest year of the list stands for both
        person("p-liste", "Testaoui, Amar ben Exemple", [
            "Naissance : 7 février 1885 (Blida, Alger)",
            "Enfants : Ali ; Omar né(e)(s) le 2 mai 1924 ; 7 juin 1928"]),
        # an impossible year and a child without a date: the year of the decree stands for them
        person("p-impossible", "Exempli, Jean", [
            "Naissance : 9 mars 1880, Oran, Algérie.",
            "Épouse : Exempli née Inventee, Anne, née le 2 avril 1988 à Oran, Algérie.",
            "Enfants : Luc"]),
        # a principal whose year was mistyped
        person("p-faute", "Fictif, Marc", ["Naissance : 21 octobre 1972, Oran, Algérie."]),
    ])),
]))

WITHHELD_NAMES = {"Rose", "Postiche, Jeanne", "Specimen, Louis", "Specimen née Exempli, Marthe", "Ali", "Omar",
                  "Exempli née Inventee, Anne", "Luc", "Fictif, Marc"}


class PrivacyRuleTest(unittest.TestCase):
    def test_generation_year_is_read_from_the_timestamp(self) -> None:
        self.assertEqual(export.generation_year("2026-11-11T10:00:00Z"), 2026)
        self.assertEqual(export.generation_year("2031-01-02"), 2031)
        for bad in ("", "demain", "26-11-11", "2026", "2026-13-01T00:00:00Z", "2026-11-111"):
            with self.assertRaises(export.ExportError, msg=bad):
                export.generation_year(bad)

    def test_the_latest_possible_birth_year_decides(self) -> None:
        reason = export.privacy_reason
        cases = [
            # (birth year, flagged impossible, decree year) -> reason, with the threshold 1926
            ((1925, False, 1929), ""),                               # 101 years old at least
            ((1926, False, 1929), export.REASON_RECENT_BIRTH),       # may still be 99 on the day of the build
            ((1927, False, 1929), export.REASON_RECENT_BIRTH),
            ((None, False, 1925), ""),                               # born in 1925 at the latest
            ((None, False, 1926), export.REASON_UNKNOWN_BIRTH),
            ((None, False, None), export.REASON_UNKNOWN_BIRTH),      # nothing known at all: withheld
            ((1961, True, 1890), ""),                                # a typing error under an old decree
            ((1972, True, 1929), export.REASON_IMPOSSIBLE_BIRTH),
            ((1826, True, 1929), export.REASON_IMPOSSIBLE_BIRTH),    # '1826' typed for '1926'
        ]
        for arguments, wanted in cases:
            self.assertEqual(reason(*arguments, 1926), wanted, arguments)


class PrivacyExportTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.directory = tempfile.TemporaryDirectory()
        cls.database, cls.site = build_corpus(Path(cls.directory.name), PRIVACY_CORPUS)
        cls.person_document, cls.persons, _, cls.decrees, cls.meta = load_site(cls.site)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.directory.cleanup()

    def test_possibly_living_persons_are_not_in_the_site_file(self) -> None:
        names = {p["nom"] for p in self.persons}
        self.assertFalse(names & WITHHELD_NAMES)
        self.assertEqual(names, {"Factice, Pierre", "Factice née Modele, Lucie", "Paul", "Testaoui, Amar ben Exemple",
                                 "Exempli, Jean"})
        text = (self.site / "an-personnes.json").read_text(encoding="utf-8")
        for name in WITHHELD_NAMES - {"Ali", "Luc"}:       # (too short to be searched as substrings)
            self.assertNotIn(name, text)

    def test_the_file_stays_coherent(self) -> None:
        self.assertEqual([p["id"] for p in self.persons], list(range(len(self.persons))))
        self.assertTrue(all(self.persons[p["princ"]]["role"] == 0 for p in self.persons))
        self.assertEqual(family_of(self.persons, self.person_document, "p-ancien"),
                         [("principal", "Factice, Pierre"), ("epouse", "Factice née Modele, Lucie"), ("enfant", "Paul")])
        self.assertEqual((self.decrees[0]["n_pers"], self.decrees[0]["n_exp"]), (6, 3))
        self.assertEqual(self.meta["comptes"]["exporte"]["occurrences_de_noms"], len(self.persons))

    def test_withheld_occurrences_are_counted_by_reason(self) -> None:
        privacy = self.meta["vie_privee"]
        self.assertTrue(privacy["active"])
        self.assertEqual((privacy["annee_de_generation"], privacy["age"], privacy["annee_seuil"]), (2026, 100, 1926))
        self.assertIn("1926", privacy["regle"])
        self.assertEqual(privacy["retenus"], {"total": 9, "principaux": 3, "epouses": 2, "enfants": 4,
                                              "seconds_demandeurs": 0})
        self.assertEqual(privacy["concernes"], privacy["retenus"])
        by_reason = {reason: counts["total"] for reason, counts in privacy["concernes_par_motif"].items()}
        self.assertEqual(by_reason, {"naissance-recente": 4,            # Rose, the principal of 1926, Ali, Omar
                                     "naissance-inconnue": 2,           # the principal without a year, Luc
                                     "naissance-impossible": 2,         # the spouse of '1988', the principal of '1972'
                                     "notice-du-principal-retenue": 1})
        self.assertEqual(set(privacy["motifs"]), set(by_reason))

    def test_the_card_of_a_principal_knows_how_many_relatives_are_withheld_not_who(self) -> None:
        by_notice = {p["notice"]: str(p["id"]) for p in self.persons if p["notice"]}
        self.assertEqual(self.meta["vie_privee"]["apparentes_retenus_par_principal"],
                         {by_notice["p-ancien"]: 1, by_notice["p-liste"]: 2, by_notice["p-impossible"]: 2})
        meta_text = (self.site / "an-meta.json").read_text(encoding="utf-8")
        for name in WITHHELD_NAMES - {"Ali", "Luc"}:
            self.assertNotIn(name, meta_text)

    def test_the_search_report_says_it_without_calling_it_an_absence(self) -> None:
        item = next(item for item in self.meta["non_couvert"] if item["code"] == "vie-privee")
        self.assertIn("9 occurrences de noms retenues", item["texte"])
        self.assertIn("1926", item["texte"])
        self.assertNotIn("n'a pas été admis", item["texte"])

    def test_the_database_keeps_everybody(self) -> None:
        connection = build.read_only(self.database)
        try:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM personne").fetchone(), (6,))
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM apparente").fetchone(), (8,))
        finally:
            connection.close()

    def test_the_rule_follows_the_year_of_the_timestamp(self) -> None:
        # generated in 2030: the threshold is 1930, later than the register and than every plausible birth
        with tempfile.TemporaryDirectory() as directory:
            export.export_site(self.database, Path(directory), include_filae=False, timestamp="2030-06-01T00:00:00Z")
            document, rows, _, _, meta = load_site(Path(directory))
        self.assertTrue(WITHHELD_NAMES <= {p["nom"] for p in rows})
        self.assertEqual((meta["vie_privee"]["annee_seuil"], meta["vie_privee"]["retenus"]["total"]), (1930, 0))
        mistyped = next(p for p in rows if p["notice"] == "p-faute")
        self.assertEqual(document["tables"]["prec"][mistyped["prec"]], "suspecte")     # still flagged, never corrected

    def test_the_rule_can_be_disabled_for_private_use_and_the_meta_says_so(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            export.export_site(self.database, Path(directory), include_filae=False, timestamp=TIMESTAMP,
                               include_possibly_living=True)
            _, rows, _, decrees, meta = load_site(Path(directory))
        self.assertTrue(WITHHELD_NAMES <= {p["nom"] for p in rows})
        privacy = meta["vie_privee"]
        self.assertFalse(privacy["active"])
        self.assertEqual(privacy["retenus"]["total"], 0)
        self.assertEqual(privacy["concernes"], self.meta["vie_privee"]["concernes"])    # same persons designated
        self.assertEqual(privacy["apparentes_retenus_par_principal"], {})
        self.assertFalse([item for item in meta["non_couvert"] if item["code"] == "vie-privee"])
        self.assertEqual(decrees[0]["n_exp"], 6)


class PrivacyCommandTest(unittest.TestCase):
    def run_cli(self, *arguments: object) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main([str(argument) for argument in arguments])
        return code, out.getvalue(), err.getvalue()

    def test_default_withholds_and_the_flag_warns(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "raw").mkdir()
            (root / "raw" / "FRAN_IR_900010.xml").write_text(PRIVACY_CORPUS, encoding="utf-8")
            common = ("construire", "--source", root / "raw", "--base", root / "an.sqlite", "--horodatage", TIMESTAMP,
                      "--silencieux")
            code, out, err = self.run_cli(*common, "--sortie", root / "site")
            self.assertEqual((code, err), (0, ""))
            self.assertIn("Vie privée", out)
            self.assertIn("9 occurrences de noms (3 principaux, 2 épouses, 4 enfants)", out)
            self.assertIn("naissance-recente : 4 occurrences de noms", out)
            self.assertIn("Ces noms sont RETENUS", out)
            self.assertIn("--inclure-vivants-possibles", out)
            code, out, err = self.run_cli(*common, "--sortie", root / "prive", "--inclure-vivants-possibles")
            self.assertEqual(code, 0)
            self.assertIn("ATTENTION", err)
            self.assertIn("9 personnes pouvant être encore en vie SONT dans l'export", err)
            self.assertIn("ne pas publier", err)
            names = {p["nom"] for p in load_columnar(root / "prive" / "an-personnes.json")[1]}
            self.assertIn("Postiche, Jeanne", names)

    def test_an_unreadable_timestamp_is_refused_before_anything_is_written(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            code, _, err = self.run_cli("construire", "--source", root, "--base", root / "an.sqlite", "--sortie",
                                        root / "site", "--horodatage", "hier")
            self.assertEqual(code, 1)
            self.assertIn("horodatage illisible", err)
            self.assertFalse((root / "an.sqlite").exists())

    def test_the_flag_is_documented_in_the_help(self) -> None:
        out = io.StringIO()
        with contextlib.redirect_stdout(out), self.assertRaises(SystemExit):
            cli.main(["construire", "--aide"])
        help_text = " ".join(out.getvalue().split())
        self.assertIn("--inclure-vivants-possibles", help_text)
        self.assertIn("usage privé et local seulement", help_text)
        self.assertIn("son année fixe le seuil", help_text)


# ----------------------------------------------------------------------------- the one link table

class LinkTableTest(unittest.TestCase):
    def test_the_module_agrees_with_the_link_table_of_the_site(self) -> None:
        self.assertEqual(links.check_content_table(), [])

    def test_the_module_holds_no_address_to_publish(self) -> None:
        published = links.template_table()
        self.assertEqual([entry["id"] for entry in published], ["an-inventaire", "an-notice", "an-images-notice"])
        self.assertTrue(all(set(entry) == {"nom", "id", "variables"} for entry in published))
        self.assertNotIn("://", json.dumps(published))

    def test_a_table_that_no_longer_matches_is_reported(self) -> None:
        document = json.loads(links.CONTENT_TABLE_PATH.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "liens.json"
            self.assertIn("absente", links.check_content_table(path)[0])
            path.write_text("{pas du json", encoding="utf-8")
            self.assertIn("illisible", links.check_content_table(path)[0])

            def problems(change) -> list[str]:  # type: ignore[no-untyped-def]
                copy = json.loads(json.dumps(document))
                change({entry["id"]: entry for entry in copy["liens"]}, copy)
                path.write_text(json.dumps(copy), encoding="utf-8")
                return links.check_content_table(path)

            def remove(entries: dict, copy: dict) -> None:
                copy["liens"] = [entry for entry in copy["liens"] if entry["id"] != "an-notice"]

            def other_address(entries: dict, copy: dict) -> None:
                entries["an-images-notice"]["gabarit"] = "https://exemple.invalid/{inventaire}/{notice}"

            def other_placeholders(entries: dict, copy: dict) -> None:
                entries["an-inventaire"]["variables"] = ["ir"]

            self.assertEqual(problems(lambda entries, copy: None), [])
            for change, word in ((remove, "an-notice"), (other_address, "an-images-notice"),
                                 (other_placeholders, "an-inventaire")):
                found = problems(change)
                self.assertEqual(len(found), 1, found)
                self.assertIn(word, found[0])

    def test_verifier_checks_the_link_table(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database, _ = build_corpus(Path(directory), PRIVACY_CORPUS)
            report = verify.verify(Path(directory) / "raw", database, content_table=Path(directory) / "absent.json")
            self.assertTrue(any("table des liens absente" in problem for problem in report.link_problems))
            self.assertFalse(report.ok)
            report = verify.verify(Path(directory) / "raw", database)
            self.assertEqual(report.link_problems, [])


# ----------------------------------------------------------------------------- tier through a relative

TIER_CORPUS = inventory("Décrets de naturalisation de l'année 1920 (janvier à mars)", "".join([
    decree("D1", "Décret de naturalisations du 5 janvier 1920", "1920-01-05", "5 janvier 1920", "".join([
        person("p-epouse-nee", "Factice, Pierre", [
            "Naissance : 3 mai 1880, Turin, Italie.",
            "Lieu de résidence : Lyon, Rhône, France.",
            "Épouse : Factice née Modele, Lucie, née le 4 juin 1885 à Blida, département d'Alger, Algérie."]),
        person("p-epouse-reside", "Postiche, Jean", [
            "Naissance : 9 mars 1885, Lyon, Rhône, France.",
            "Lieu de résidence : Lyon, Rhône, France.",
            "Épouse : Postiche née Inventee, Anne, née le 2 avril 1888 à Lyon, Rhône, France.",
            "Lieu de résidence : Oran, Algérie."]),
        person("p-enfant", "Specimen, Louis", [
            "Naissance : 1 février 1870, Gênes, Italie.",
            "Lieu de résidence : Marseille, Bouches-du-Rhône, France.",
            "Enfants : Paul (6 juin 1910, Oran, Algérie)"]),
        # the word 'algérien' qualifies the spouse's father, not her place of birth
        person("p-pere-de-l-epouse", "Fictif, Marc", [
            "Naissance : 1 février 1870, Gênes, Italie.",
            "Lieu de résidence : Marseille, Bouches-du-Rhône, France.",
            "Épouse : Fictif née Exempli, Rose, née le 2 avril 1888 à Tunis, Tunisie, de père algérien."]),
        person("p-ailleurs", "Exempli, Jean", [
            "Naissance : 1 février 1870, Gênes, Italie.",
            "Lieu de résidence : Marseille, Bouches-du-Rhône, France.",
            "Épouse : Exempli née Factice, Marie, née le 2 avril 1888 à Lyon, Rhône, France."]),
    ])),
]))


class TierThroughRelativeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.directory = tempfile.TemporaryDirectory()
        cls.database, cls.site = build_corpus(Path(cls.directory.name), TIER_CORPUS)
        cls.person_document, cls.persons, cls.decree_document, cls.decrees, cls.meta = load_site(cls.site)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.directory.cleanup()

    def test_a_spouse_or_a_child_born_or_residing_in_algeria_brings_the_notice_in(self) -> None:
        connection = build.read_only(self.database)
        try:
            tier = {notice: (in_tier, by_relative) for notice, in_tier, by_relative in connection.execute(
                "SELECT notice_id, palier_algerie, palier_par_apparente FROM personne")}
            places = connection.execute(
                "SELECT p.notice_id, a.role, a.ne_en_algerie, a.reside_en_algerie FROM apparente a JOIN personne p "
                "USING(personne_id) ORDER BY a.apparente_id").fetchall()
        finally:
            connection.close()
        self.assertEqual(tier, {"p-epouse-nee": (1, 1), "p-epouse-reside": (1, 1), "p-enfant": (1, 1),
                                "p-pere-de-l-epouse": (0, 0), "p-ailleurs": (0, 0)})
        self.assertEqual(places, [("p-epouse-nee", "epouse", "explicite", ""),
                                  ("p-epouse-reside", "epouse", "", "explicite"),
                                  ("p-enfant", "enfant", "explicite", ""),
                                  ("p-pere-de-l-epouse", "epouse", "", ""), ("p-ailleurs", "epouse", "", "")])

    def test_the_notice_is_exported_with_its_decree_and_the_principal_keeps_his_own_hint(self) -> None:
        self.assertEqual({p["notice"] for p in self.persons if p["notice"]},
                         {"p-epouse-nee", "p-epouse-reside", "p-enfant"})
        self.assertEqual(family_of(self.persons, self.person_document, "p-epouse-nee"),
                         [("principal", "Factice, Pierre"), ("epouse", "Factice née Modele, Lucie")])
        tables = self.person_document["tables"]
        principal = next(p for p in self.persons if p["notice"] == "p-epouse-nee")
        self.assertEqual((tables["ind"][principal["ind"]], tables["nea"][principal["nea"]],
                          tables["rea"][principal["rea"]]), ("E", "", ""))
        spouse = self.persons[principal["id"] + 1]
        self.assertEqual(spouse["lieu"], "Blida, département d'Alger, Algérie")
        decree_row = self.decrees[principal["dec"]]
        self.assertEqual((self.decree_document["tables"]["classe"][decree_row["classe"]], decree_row["n_pers"],
                          decree_row["n_exp"]), ("-", 5, 3))
        self.assertEqual(self.meta["comptes"]["corpus"]["personnes_du_palier_par_un_apparente"], 3)


# ----------------------------------------------------------------------------- second applicant

SECOND_APPLICANT_LINES = [
    "Naissance : 24 septembre 1833, Turin, Italie.",
    "Lieu de résidence : Blida, département d'Alger, Algérie.",
    "Deuxième demandeur : MODELE, Marie Louise",
    "Naissance : 18 février 1876",
    "Lieu de résidence : Fictiveville, Creuse, France."]
SECOND_APPLICANT_CORPUS = inventory("Décrets de naturalisation de l'année 1898", "".join([
    decree("D1", "Décret de naturalisations du 5 juin 1898", "1898-06-05", "5 juin 1898",
           person("p-deux", "FACTICE, François", SECOND_APPLICANT_LINES)),
]))


class SecondApplicantTest(unittest.TestCase):
    def test_the_second_applicant_is_a_name_occurrence_with_its_own_birth_and_residence(self) -> None:
        fields = persons.parse_person_lines(SECOND_APPLICANT_LINES)
        self.assertEqual((fields.birth.year, fields.residence), (1833, "Blida, département d'Alger, Algérie."))
        self.assertEqual((fields.notes, fields.other_residences, fields.unparsed), ([], [], []))
        self.assertEqual(len(fields.relatives), 1)
        second = fields.relatives[0]
        self.assertEqual((second.role, second.name_raw, second.birth.year, second.residence),
                         ("demandeur", "MODELE, Marie Louise", 1876, "Fictiveville, Creuse, France."))
        self.assertEqual(second.raw, "MODELE, Marie Louise")

    def test_searchable_if_and_only_if_the_year_is_exported(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database, site = build_corpus(Path(directory), SECOND_APPLICANT_CORPUS)
            # 1898 is a year of the Filae clause: by default no name of that year is in the site files
            document, rows, _, decrees, meta = load_site(site)
            self.assertEqual(rows, [])
            self.assertNotIn("MODELE", (site / "an-personnes.json").read_text(encoding="utf-8"))
            self.assertEqual(document["tables"]["role"], ["principal", "epouse", "enfant", "demandeur"])
            self.assertEqual(meta["comptes"]["corpus"]["seconds_demandeurs"], 1)
            self.assertEqual(meta["comptes"]["exporte"]["seconds_demandeurs"], 0)
            # the database (never published) is searched whole
            connection = build.read_only(database)
            try:
                result = search.search(connection, ["modele"])
                self.assertEqual([hit.role for c in result.correspondences for hit in c.hits.values()], ["demandeur"])
            finally:
                connection.close()
            # with the names of the Filae years, the second applicant follows its principal
            export.export_site(database, site, include_filae=True, timestamp=TIMESTAMP)
            document, rows, _, _, meta = load_site(site)
        self.assertEqual(family_of(rows, document, "p-deux"),
                         [("principal", "FACTICE, François"), ("demandeur", "MODELE, Marie Louise")])
        second = rows[1]
        self.assertEqual((second["an"], second["res"], second["princ"], second["notice"]),
                         (1876, "Fictiveville, Creuse, France.", 0, None))
        self.assertEqual(meta["comptes"]["exporte"]["seconds_demandeurs"], 1)


# ----------------------------------------------------------------------------- data-entry debris

DEBRIS_CORPUS = inventory("Décrets de naturalisation de l'année 1920 (janvier à mars)", "".join([
    decree("D1", "Décret de naturalisations algériennes du 5 janvier 1920", "1920-01-05", "5 janvier 1920", "".join([
        person("p-dossier", "Factice, Pierre", [
            "Naissance : 3 mai 1880, Turin, Italie.",
            "Épouse : 90100 X 20",
            "Enfants : Lucie 28 ; Luc né(e)(s) le 3 mai 1910 ; 4 juin 1912"]),
        person("p-date", "Postiche, Jean", [
            "Naissance : 9 mars 1860, Lyon, Rhône, France.",
            "Enfants : 3 mai 1891 ; Paul (2 mai 1895), Rose (8 août 1897), ? (1 mars 1899)"]),
        person("p-1895", "Specimen, Louis", [
            "Naissance : 1 février 1850, Gênes, Italie.",
            "Épouse : SPECIMEN, née MODELE, 3 mai 1855, née le Bône à département de Constantine, Algérie, de "
            "parents italiens."]),
    ])),
]))


class NameDebrisTest(unittest.TestCase):
    def test_strict_rules(self) -> None:
        cases = {
            "Modele, Lucie": "", "Marie-Lucie": "", "Jo": "", ": Lucie Marie": "", "Le Van Exemple": "",
            "Une fille mineure: Lucie": "",                    # a remark without a digit is not guessed
            "": "vide", "?": "vide", "X": "vide",
            "90100 X 20": "numero-de-dossier", "901x20": "numero-de-dossier", "901 BX 30": "numero-de-dossier",
            "3 mai 1871 ; Paul": "date", "Lucette née 3 mai 1911": "date",
            "Lucie 28": "chiffre", "5 enfants": "chiffre", "Lucie (2 )": "chiffre", "aM2LIE": "chiffre",
            "Lieu de résidence : Marie": "libelle-de-champ",
        }
        for name, wanted in cases.items():
            self.assertEqual(persons.name_flag(name), wanted, name)
        # a dossier number that the date reader took for a year: the raw text decides
        self.assertEqual(persons.name_flag("", "1850 X 20"), "numero-de-dossier")
        self.assertEqual(set(cases.values()) - {""}, set(persons.NAME_FLAGS))

    def test_the_form_of_1895_is_read_not_discarded(self) -> None:
        spouse = persons.parse_spouse("SPECIMEN, née MODELE, 3 mai 1855, née le Gênes.")
        self.assertEqual((spouse.name_raw, spouse.birth.date, spouse.birth.place), ("SPECIMEN, née MODELE", "1855-05-03", "Gênes"))
        self.assertEqual(spouse.birth.raw, "3 mai 1855, née le Gênes.")          # as written
        self.assertEqual(spouse.raw, "SPECIMEN, née MODELE, 3 mai 1855, née le Gênes.")
        self.assertEqual(persons.name_flag(spouse.name_raw, spouse.raw), "")
        year_only = persons.parse_spouse("SPECIMEN, née BEN MODELE, 1843, née le Fictiveville.")
        self.assertEqual((year_only.name_raw, year_only.birth.year, year_only.birth.place),
                         ("SPECIMEN, née BEN MODELE", 1843, "Fictiveville"))
        # the usual form is untouched, and a date that is not at the end of the name does not trigger the rule
        usual = persons.parse_spouse("FACTICE, née MODELE, Lucie, née le 3 mai 1850 à Gênes, Italie.")
        self.assertEqual((usual.name_raw, usual.birth.date, usual.birth.place),
                         ("FACTICE, née MODELE, Lucie", "1850-05-03", "Gênes, Italie"))
        widow = persons.parse_spouse("FACTICE veuve de MODELE Joseph décédé le 3 mars 1890, Jeanne, née le "
                                     "3 mai 1860 à Gênes")
        self.assertEqual(widow.birth.date, "1860-05-03")
        self.assertEqual(persons.name_flag(widow.name_raw, widow.raw), "date")   # known limit: not exported

    def test_debris_is_kept_in_the_database_and_left_out_of_the_names(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database, site = build_corpus(Path(directory), DEBRIS_CORPUS)
            document, rows, _, _, meta = load_site(site)
            connection = build.read_only(database)
            try:
                kept = connection.execute(
                    "SELECT p.notice_id, a.role, a.nom_brut, a.texte_brut, a.nom_drapeau FROM apparente a "
                    "JOIN personne p USING(personne_id) WHERE a.nom_drapeau != '' ORDER BY a.apparente_id").fetchall()
            finally:
                connection.close()
        self.assertEqual(kept, [
            ("p-dossier", "epouse", "90100 X 20", "90100 X 20", "numero-de-dossier"),
            ("p-dossier", "enfant", "Lucie 28", "Lucie 28 ; Luc né(e)(s) le 3 mai 1910 ; 4 juin 1912", "chiffre"),
            ("p-date", "enfant", "3 mai 1891 ; Paul", "3 mai 1891 ; Paul (2 mai 1895)", "date"),
            ("p-date", "enfant", "?", "? (1 mars 1899)", "vide")])
        self.assertEqual(family_of(rows, document, "p-dossier"), [("principal", "Factice, Pierre"), ("enfant", "Luc")])
        self.assertEqual(family_of(rows, document, "p-date"), [("principal", "Postiche, Jean"), ("enfant", "Rose")])
        self.assertEqual(family_of(rows, document, "p-1895"),
                         [("principal", "Specimen, Louis"), ("epouse", "SPECIMEN, née MODELE")])
        spouse = next(p for p in rows if p["nom"] == "SPECIMEN, née MODELE")
        self.assertEqual((spouse["an"], spouse["lieu"]),
                         (1855, "Bône à département de Constantine, Algérie, de parents italiens"))
        self.assertFalse([p for p in rows if p["nom"] and any(char.isdigit() for char in p["nom"])])
        debris = meta["noms_inexploitables"]
        self.assertEqual(debris["non_exportes"], {"total": 4, "principaux": 0, "epouses": 1, "enfants": 3,
                                                  "seconds_demandeurs": 0})
        self.assertEqual(debris["non_exportes_par_motif"], {"vide": 1, "numero-de-dossier": 1, "date": 1, "chiffre": 1,
                                                            "libelle-de-champ": 0})
        self.assertEqual(set(debris["motifs"]), set(persons.NAME_FLAGS))
        by_notice = {p["notice"]: str(p["id"]) for p in rows if p["notice"]}
        self.assertEqual(debris["par_principal"], {by_notice["p-dossier"]: 2, by_notice["p-date"]: 2})
        self.assertEqual(meta["comptes"]["corpus"]["apparentes_au_nom_inexploitable"], 4)
        item = next(item for item in meta["non_couvert"] if item["code"] == "noms-inexploitables")
        self.assertIn("4 mentions", item["texte"])


if __name__ == "__main__":
    unittest.main()
