"""Harvest planning (no network), export of the site files and their verification."""
from __future__ import annotations

import datetime
import json
import tempfile
import unittest
from pathlib import Path

from decretas import net
from decretas.bogga import catalogue, export, moisson, personnes as P, verification
from tests.bogga.fabrique import closing, title_page, write_metadata, write_volume_files

SC = "conformément aux dispositions du sénatus-consulte du 14 juillet 1865"
ITEM = "item-synthetique"


def synthetic_volume(year: int = 1873, doc: str = "1873 T.13", multi: bool = True) -> catalogue.Volume:
    return catalogue.Volume(year=year, item=ITEM, doc=doc, family=catalogue.TESSERACT, multi=multi, library=None,
                            rights="Texte officiel (domaine public). Volume synthétique de test.")


def heading(date: str) -> str:
    return (f"Par décret présidentiel du {date}, contresigné par le Ministre de la Justice, ont été admises à jouir des "
            f"droits de citoyen français, {SC}, les personnes ci-après désignées :")


TEXTS = [
    "TABLE CHRONOLOGIQUE\n8 mai Décret qui admet divers étrangers à jouir des droits de citoyen français ... 502 | 3",
    title_page(1873, 502),
    "N° 350. — NATURALISATION.\n" + heading("8 mai 1873")
    + "\n1. Fictivo (Aldo), badois, demeurant à Val-Fictif.\n2. Testaoui ben Exemple, indigène musulman, demeurant à Blida.",
    "N° 351. — " + heading("9 mai 1873") + "\n(liste illisible)\nN° 352. — MILICES.\nArrêté fictif.\n" + closing("23 octobre 1873"),
    "TABLE ALPHABÉTIQUE\nNATURALISATION. — Admission de divers étrangers à jouir des droits de citoyen français, D. p. 1, 2",
]
PRINTED = {2: "1", 3: "2"}


class ExportTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.raw = Path(self.tmp.name) / "raw"
        self.site = Path(self.tmp.name) / "site-data"
        self.build_dir = Path(self.tmp.name) / "build"
        self.volume = synthetic_volume()
        write_metadata(self.raw / ITEM, ["1873 T.13"])
        write_volume_files(self.raw / ITEM, "1873 T.13", TEXTS, PRINTED)
        self.messages: list[str] = []

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def build(self) -> int:
        return export.build(self.raw, self.site, self.build_dir, [self.volume], say=self.messages.append,
                            today=datetime.date(2026, 11, 11))

    def table(self, name: str) -> list[dict]:
        return verification.load_table(self.site / f"bogga-{name}.json")

    def test_four_files_with_the_documented_fields(self) -> None:
        self.assertEqual(self.build(), 0)
        for name, fields in (("volumes", export.VOLUME_FIELDS), ("decrets", export.DECREE_FIELDS), ("entrees", export.ENTRY_FIELDS)):
            data = json.loads((self.site / f"bogga-{name}.json").read_text(encoding="utf-8"))
            self.assertEqual(sorted(data), ["champs", "lignes"])
            self.assertEqual(data["champs"], fields)
            self.assertTrue(all(len(row) == len(fields) for row in data["lignes"]))
        self.assertTrue((self.site / "bogga-meta.json").exists())

    def test_volume_row_carries_verified_link_forms_and_the_control_record(self) -> None:
        self.build()
        row = self.table("volumes")[0]
        self.assertEqual(row["lien_page"], "https://archive.org/details/item-synthetique/1873%20T.13/page/n{leaf}/mode/1up")
        self.assertEqual(row["image_page"], "https://archive.org/download/item-synthetique/1873%20T.13/page/n{leaf}_w{largeur}.jpg")
        self.assertEqual(row["lien_verifie"], "non vérifié")
        self.assertEqual(row["controle"]["table_alphabetique"]["taux_pages"], 1.0)
        self.assertEqual(row["pagination"]["feuilles"], 5)
        self.assertEqual(row["livraisons"]["premier_numero"], 502)

    def test_single_volume_item_uses_the_other_link_form(self) -> None:
        self.volume = synthetic_volume(multi=False)
        self.build()
        self.assertEqual(self.table("volumes")[0]["lien_page"], "https://archive.org/details/item-synthetique/page/n{leaf}/mode/1up")

    def test_decrees_and_entries(self) -> None:
        self.build()
        decrees, entries = self.table("decrets"), self.table("entrees")
        self.assertEqual([d["id"] for d in decrees], [0, 1])
        first = decrees[0]
        self.assertEqual((first["dates"], first["date_etat"], first["date_brute"]), (["1873-05-08"], 0, "8 mai 1873"))
        self.assertEqual((first["page"], first["feuille"], first["entrees"], first["article"]), (1, 2, 2, "350"))
        self.assertEqual((first["livraison"], first["livraison_date"], first["livraison_date_etat"]), (502, "1873-10-23", 0))
        self.assertEqual(first["nature"], "admission")
        self.assertEqual(decrees[1]["drapeaux"] & export.D_SANS_ENTREE, export.D_SANS_ENTREE)
        persons = [e for e in entries if not e["drapeaux"] & P.F_NON_SEGMENTE]
        self.assertEqual([e["nom"] for e in persons], ["Fictivo (Aldo)", "Testaoui ben Exemple"])
        self.assertEqual(persons[1]["texte"], "2. Testaoui ben Exemple, indigène musulman, demeurant à Blida.")
        self.assertEqual(persons[1]["marqueurs"], P.M_INDIGENE | P.M_MUSULMAN)
        self.assertEqual((persons[1]["page"], persons[1]["feuille"], persons[1]["decret"], persons[1]["residence"]), (1, 2, 0, "Blida"))
        self.assertIsNone(persons[1]["naissance"])

    def test_heading_that_mentions_indigenes_among_others_flags_the_decree_not_the_persons(self) -> None:
        mixed = TEXTS[:2] + [TEXTS[2].replace("les personnes ci-après désignées", "les Indigènes et étrangers dont les noms suivent")] + TEXTS[3:]
        write_volume_files(self.raw / ITEM, "1873 T.13", mixed, PRINTED)
        self.build()
        decree = self.table("decrets")[0]
        self.assertTrue(decree["drapeaux"] & export.D_ENTETE_MENTIONNE_INDIGENES)
        self.assertFalse(decree["drapeaux"] & export.D_INDIGENE_ENTETE)
        first = self.table("entrees")[0]
        self.assertEqual(first["marqueurs"] & (P.M_INDIGENE | P.M_INDIGENE_ENTETE), 0)

    def test_meta_covers_every_year_and_lists_pages_to_read_by_hand(self) -> None:
        self.build()
        meta = json.loads((self.site / "bogga-meta.json").read_text(encoding="utf-8"))
        years = {row["annee"]: row for row in meta["couverture"]}
        self.assertEqual(sorted(years), list(range(1861, 1889)))
        self.assertEqual(years[1873]["etat"], "indexé")
        self.assertEqual((years[1873]["decrets"], years[1873]["entrees"], years[1873]["entrees_marquees_indigene"]), (2, 2, 1))
        self.assertEqual(years[1862]["etat"], "absent d'Internet Archive")
        self.assertIn("sénatus-consulte", years[1862]["que_faire"])
        self.assertTrue(years[1887]["que_faire"])
        self.assertEqual(years[1888]["etat"], "non téléchargé")
        manual = meta["pages_a_lire_a_la_main"]
        self.assertEqual([(page["feuille"], page["page"], page["decret"]) for page in manual], [(3, 2, 1)])
        self.assertEqual(manual[0]["lien"], "https://archive.org/details/item-synthetique/1873%20T.13/page/n3/mode/1up")
        self.assertEqual(meta["credit"], export.CREDIT)
        self.assertEqual(meta["genere_le"], "2026-11-11")
        self.assertEqual(meta["totaux"]["entrees"], 2)

    def test_link_check_results_are_carried_into_the_volume_file(self) -> None:
        self.build_dir.mkdir(parents=True)
        (self.build_dir / export.LINK_CHECKS_FILE).write_text(json.dumps({"1873": "oui : contrôle fictif"}), encoding="utf-8")
        self.build()
        self.assertEqual(self.table("volumes")[0]["lien_verifie"], "oui : contrôle fictif")

    def test_link_checked_on_the_image_is_reported_for_that_item_only(self) -> None:
        # regression: 1873 and 1888, the two volumes checked on the page image, were exported as « non vérifié »
        self.assertTrue(catalogue.image_check(catalogue.volume_for(1873)).startswith("oui : image de la feuille 530"))
        self.assertTrue(catalogue.image_check(catalogue.volume_for(1888)).startswith("oui : image de la feuille 116"))
        self.assertIsNone(catalogue.image_check(catalogue.volume_for(1880)))
        self.assertIsNone(catalogue.image_check(synthetic_volume()))        # same year, another item
        self.build()
        self.assertEqual(self.table("volumes")[0]["lien_verifie"], "non vérifié")

    def test_missing_files_are_reported_and_nothing_is_invented(self) -> None:
        absent = synthetic_volume(year=1874, doc="1874 T.14")
        code = export.build(self.raw, self.site, self.build_dir, [self.volume, absent], say=self.messages.append)
        self.assertEqual(code, 1)
        self.assertTrue(any("1874" in message for message in self.messages))
        self.assertEqual(len(self.table("volumes")), 1)

    def test_structure_checks_pass_on_the_built_files(self) -> None:
        self.build()
        lines: list[str] = []
        checker = verification.Checker(lines.append)
        meta = json.loads((self.site / "bogga-meta.json").read_text(encoding="utf-8"))
        verification.check_structure(checker, self.table("volumes"), self.table("decrets"), self.table("entrees"), meta)
        self.assertEqual(checker.failures, 0, lines)

    def test_structure_checks_catch_a_broken_reference(self) -> None:
        self.build()
        entries = self.table("entrees")
        entries[0]["decret"] = 1
        checker = verification.Checker(lambda _line: None)
        meta = json.loads((self.site / "bogga-meta.json").read_text(encoding="utf-8"))
        verification.check_structure(checker, self.table("volumes"), self.table("decrets"), entries, meta)
        self.assertGreater(checker.failures, 0)


class HarvestPlanTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.raw = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_document_prefix_is_checked_against_the_item_file_list(self) -> None:
        write_metadata(self.raw / ITEM, ["1868 T.8_2", "1869 T.9"])
        metadata = moisson.load_metadata(self.raw, ITEM)
        self.assertEqual(moisson.doc_prefixes(metadata), ["1868 T.8_2", "1869 T.9"])
        self.assertEqual(moisson.resolve_doc(synthetic_volume(1868, "1868 T.8_2"), metadata), "1868 T.8_2")
        with self.assertRaises(moisson.HarvestError):
            moisson.resolve_doc(synthetic_volume(1868, "1868 T.8"), metadata)       # a rebuilt name is refused

    def test_single_document_item_reads_its_prefix_from_the_metadata(self) -> None:
        write_metadata(self.raw / ITEM, ["Bulletin fictif 13 1873"])
        volume = catalogue.Volume(1873, ITEM, None, catalogue.TESSERACT, False, None, "droits")
        self.assertEqual(moisson.resolve_doc(volume, moisson.load_metadata(self.raw, ITEM)), "Bulletin fictif 13 1873")

    def test_file_url_uses_a_workable_server_and_encodes_the_name(self) -> None:
        write_metadata(self.raw / ITEM, ["1888 T.28"])
        url = moisson.file_url(moisson.load_metadata(self.raw, ITEM), "1888 T.28_hocr_searchtext.txt.gz")
        self.assertEqual(url, "https://ia000000.us.archive.org/1/items/synthetique/1888%20T.28_hocr_searchtext.txt.gz")

    def test_dry_run_plans_the_metadata_request_and_sends_nothing(self) -> None:
        client = net.PoliteClient(root=self.raw, policies=moisson.ia_policy(), dry_run=True)
        said: list[str] = []
        report = moisson.harvest(client, [synthetic_volume()], say=said.append)
        self.assertEqual(report.planned, ["https://archive.org/metadata/item-synthetique"])
        self.assertEqual(report.fetched, [])
        self.assertFalse((self.raw / "manifest.jsonl").exists())

    def test_policy_never_goes_under_five_seconds(self) -> None:
        self.assertEqual(moisson.ia_policy(delay=1.0)["archive.org"].min_delay, 5.0)
        self.assertEqual(moisson.ia_policy(delay=8.0)["archive.org"].min_delay, 8.0)

    def test_earlier_downloads_are_adopted_instead_of_requested_again(self) -> None:
        earlier = self.raw / "ancien"
        earlier.mkdir()
        (earlier / "meta.json").write_bytes(b'{"files": []}')
        url = "https://archive.org/metadata/item-synthetique"
        log = self.raw / "requests.jsonl"
        log.write_text(json.dumps({"url": url, "status": 200, "bytes": 13, "saved_as": "ancien/meta.json"}) + "\n", encoding="utf-8")
        client = net.PoliteClient(root=self.raw / "cache", policies=moisson.ia_policy())
        self.assertEqual(moisson.adopt_earlier_downloads(client, log, self.raw, {url: "item-synthetique/_metadata.json"}), 1)
        self.assertEqual(client.requests_used("archive.org"), 0)
        self.assertTrue(client.fetch(url, "item-synthetique/_metadata.json").from_cache)


class CatalogueTestCase(unittest.TestCase):
    def test_years_available_and_missing(self) -> None:
        years = [volume.year for volume in catalogue.VOLUMES]
        self.assertEqual(years, [1861] + list(range(1863, 1887)) + [1888])
        self.assertEqual(sorted(catalogue.MISSING_YEARS), [1862, 1887])

    def test_irregular_document_names_are_kept_verbatim(self) -> None:
        docs = {volume.year: volume.doc for volume in catalogue.VOLUMES if volume.item == "1922-t.-62"}
        self.assertEqual((docs[1868], docs[1871], docs[1881], docs[1882]), ("1868 T.8_2", "1871 T.11_2", "1881 T.21_21", "1882 T.22_22"))

    def test_link_templates(self) -> None:
        multi = catalogue.volume_for(1888)
        self.assertEqual(catalogue.page_link(multi, multi.doc, 116), "https://archive.org/details/1922-t.-62/1888%20T.28/page/n116/mode/1up")
        single = catalogue.volume_for(1873)
        self.assertEqual(catalogue.page_link(single, "peu importe", 530),
                         "https://archive.org/details/algeria_bulletinofficieldugouvernementgeneraldelalgerie_13_1873/page/n530/mode/1up")

    def test_reader_table_is_parsed(self) -> None:
        body = b'callback({"data": {"brOptions": {"data": [[{"leafNum": 0}], [{"leafNum": 1}, {"leafNum": 2}]]}}})'
        self.assertEqual(verification.parse_reader_table(body), [0, 1, 2])


if __name__ == "__main__":
    unittest.main()
