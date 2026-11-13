import tempfile
import unittest
from pathlib import Path

from decretas.an import ead

from .support import FIXTURES


def notices_of(name: str) -> dict[str, ead.RawNotice]:
    return {notice.notice_id: notice for notice in ead.read_inventory(FIXTURES / name).notices}


class HeaderTest(unittest.TestCase):
    def test_header_fields(self) -> None:
        inventory = ead.read_inventory(FIXTURES / "FRAN_IR_900001.xml")
        self.assertEqual(inventory.inventory, "FRAN_IR_900001")
        self.assertEqual((inventory.year, inventory.quarter), (1883, None))
        self.assertEqual(inventory.link, "http://www.siv.archives-nationales.culture.gouv.fr/siv/IR/FRAN_IR_900001")
        self.assertEqual(inventory.physloc, "Pierrefitte")
        self.assertIn("usage privé", inventory.userestrict)
        self.assertFalse(inventory.is_root)

    def test_quarterly_inventory(self) -> None:
        inventory = ead.read_inventory(FIXTURES / "FRAN_IR_900007.xml")
        self.assertEqual((inventory.year, inventory.quarter), (1926, 2))
        self.assertEqual(ead.inventory_quarter("Décrets de naturalisation de l'année 1930 (juillet-septembre)"), 3)
        self.assertEqual(ead.inventory_quarter("Décrets de naturalisation de l'année 1925 (octobre à décembre)"), 4)
        self.assertIsNone(ead.inventory_quarter("Décrets de naturalisation de l’année 1913"))

    def test_root_inventory_is_recognised_by_its_links(self) -> None:
        inventory = ead.read_inventory(FIXTURES / "FRAN_IR_900000.xml")
        self.assertTrue(inventory.is_root)
        self.assertEqual({n.kind for n in inventory.notices}, {ead.KIND_LINK, ead.KIND_GROUP})
        self.assertIn("Filae", inventory.userestrict)


class NamespaceAndLinksTest(unittest.TestCase):
    def test_links_are_read_whatever_the_prefix(self) -> None:
        # FRAN_IR_900007 declares the xlink namespace under the prefix "ns0", as a re-serialised file would.
        notices = notices_of("FRAN_IR_900007.xml")
        self.assertEqual(notices["D1"].href,
                         "http://www.siv.archives-nationales.culture.gouv.fr/siv/UD/FRAN_IR_900007/D1")
        self.assertEqual(notices["c-q1"].image_links,
                         ["http://www.siv.archives-nationales.culture.gouv.fr/siv/media/FRAN_IR_900007/c-q1/"])

    def test_links_are_copied_not_rebuilt(self) -> None:
        notices = notices_of("FRAN_IR_900001.xml")
        self.assertEqual(notices["SB000003"].image_links, [
            "http://www.siv.archives-nationales.culture.gouv.fr/siv/media/FRAN_IR_900001/SB000003/DAFANCH94_NUMJ000001_D"])
        self.assertEqual(notices["c-aaa4"].image_links, [])

    def test_the_same_notice_id_lives_in_two_inventories(self) -> None:
        first, second = notices_of("FRAN_IR_900006.xml")["D1"], notices_of("FRAN_IR_900007.xml")["D1"]
        self.assertNotEqual((first.inventory, first.title), (second.inventory, second.title))


class ClassificationTest(unittest.TestCase):
    def test_decree_and_persons(self) -> None:
        notices = notices_of("FRAN_IR_900001.xml")
        self.assertEqual(notices["SB000001"].kind, ead.KIND_DECREE)
        self.assertEqual(notices["c-aaa1"].kind, ead.KIND_PERSON)
        self.assertEqual(notices["c-aaa1"].decree_seq, notices["SB000001"].seq)
        self.assertEqual(notices["c-aaa1"].title, "Testaoui, Amar ben Exemple")

    def test_both_unitid_types_are_read(self) -> None:
        natnum = notices_of("FRAN_IR_900001.xml")["SB000001"]
        self.assertEqual((natnum.unitid("identifiant"), natnum.unitid("pieces")), ("BB/34/387", "document 7"))
        other = notices_of("FRAN_IR_900003.xml")["AP001236"]
        self.assertEqual((other.unitid("identifiant"), other.unitid("cote-de-consultation")), ("", "BB/34/424"))

    def test_decree_with_a_misspelt_title_or_its_title_inside_persname(self) -> None:
        notices = notices_of("FRAN_IR_900002.xml")
        self.assertEqual(notices["idd_1892_09_01"].kind, ead.KIND_DECREE)     # 'écret de naturalisations…'
        self.assertEqual(notices["idd_1892_11_01"].kind, ead.KIND_DECREE)     # whole title in <persname>
        self.assertEqual(notices["idd_1892_11_01"].persname_count, 1)

    def test_decree_that_lost_its_unitdate(self) -> None:
        notices = notices_of("FRAN_IR_900002.xml")
        decree = notices["idd_1892_D_04_80"]
        self.assertFalse(decree.has_unitdate)
        self.assertEqual(decree.kind, ead.KIND_DECREE)
        self.assertEqual(notices["id_1892_04_0282"].decree_seq, decree.seq)

    def test_person_with_a_decree_title_keeps_being_a_person(self) -> None:
        # No <persname>, a decree title instead of the name, but real content lines: a person.
        notice = notices_of("FRAN_IR_900002.xml")["id_1892_04_0282"]
        self.assertEqual(notice.kind, ead.KIND_PERSON)
        self.assertEqual(notice.persname_count, 0)

    def test_person_whose_name_starts_like_a_decree(self) -> None:
        self.assertEqual(notices_of("FRAN_IR_900004.xml")["A_19400"].kind, ead.KIND_PERSON)

    def test_names_without_persname_and_empty_titles_are_persons(self) -> None:
        notices = notices_of("FRAN_IR_900003.xml")
        plain = notices["id_1905_01_0140"]
        self.assertEqual((plain.kind, plain.persname_count, plain.title), (ead.KIND_PERSON, 0, "TESTAOUI, Akli Ben Modèle"))
        self.assertEqual((notices["c-empty1"].kind, notices["c-empty1"].title), (ead.KIND_PERSON, ""))

    def test_list_items_are_content_lines(self) -> None:
        lines = notices_of("FRAN_IR_900003.xml")["c-list1"].lines
        self.assertEqual([line.kind for line in lines], ["p"] * 3 + ["item"] * 6)
        self.assertEqual(lines[3].text, "Épouse")

    def test_sub_decree_is_set_aside_by_structure(self) -> None:
        notices = notices_of("FRAN_IR_900005.xml")
        self.assertEqual(notices["c-arm1"].kind, ead.KIND_NOT_NOMINATIVE)
        self.assertEqual(notices["c-n3"].kind, ead.KIND_PERSON)

    def test_decree_nested_in_a_decree(self) -> None:
        notices = notices_of("FRAN_IR_900005.xml")
        inner = notices["AP002985"]
        self.assertEqual((inner.kind, inner.depth), (ead.KIND_DECREE, 2))
        self.assertEqual(notices["c-n2"].decree_seq, inner.seq)
        self.assertEqual(notices["c-n1"].decree_seq, notices["AP002984"].seq)

    def test_groups_of_1944(self) -> None:
        notices = notices_of("FRAN_IR_900006.xml")
        self.assertEqual((notices["F1"].kind, notices["F2"].kind), (ead.KIND_GROUP, ead.KIND_GROUP))
        self.assertEqual(notices["E1"].kind, ead.KIND_DECREE)


class SafetyTest(unittest.TestCase):
    def write(self, directory: str, name: str, content: str) -> Path:
        path = Path(directory) / name
        path.write_text(content, encoding="utf-8")
        return path

    def test_entity_declarations_are_refused(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = self.write(directory, "FRAN_IR_900099.xml",
                              '<?xml version="1.0"?><!DOCTYPE ead [<!ENTITY a "aaaa">]><ead><eadheader/></ead>')
            with self.assertRaises(ead.EadError):
                ead.read_inventory(path)

    def test_broken_xml_and_wrong_root_raise_a_specific_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ead.EadError):
                ead.read_inventory(self.write(directory, "FRAN_IR_900098.xml", "<ead><eadheader>"))
            with self.assertRaises(ead.EadError):
                ead.read_inventory(self.write(directory, "FRAN_IR_900097.xml", "<html><body/></html>"))

    def test_only_reference_files_are_listed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            for name in ("FRAN_IR_900001.xml", "FRAN_IR_900001.xml.part", "FRAN_IR_900001.2026-12-01.xml",
                         "FRAN_IR_900002.refus", "autre.xml"):
                self.write(directory, name, "")
            self.assertEqual([p.name for p in ead.inventory_files(Path(directory))], ["FRAN_IR_900001.xml"])


if __name__ == "__main__":
    unittest.main()
