"""Image metadata read with the standard library, on synthetic images with known content."""
from __future__ import annotations

import importlib.util
import io
import tempfile
import unittest
from pathlib import Path

from decretas.an_images import metadonnees

from . import fabrique

EXIF = fabrique.tiff_bytes(
    [(270, 2, "Registre fictif BB/34/000"), (271, 2, "FabricantTest"), (272, 2, "ScanTest 3000"),
     (305, 2, "LogicielTest 1.2"), (306, 2, "2020:03:04 10:11:12"), (33432, 2, "Domaine public"),
     (282, 5, (400, 1)), (283, 5, (400, 1)), (296, 3, 2)],
    exif=[(36867, 2, "2020:03:04 10:11:12"), (40962, 4, 16), (40963, 4, 24)])


class JpegTest(unittest.TestCase):
    def setUp(self) -> None:
        self.data = fabrique.jpeg_bytes(
            16, 24, exif=EXIF, xmp=fabrique.xmp_packet({"xmp:CreatorTool": "OutilTest"}, title="Vue fictive 3"),
            iptc=fabrique.iptc_bytes([(1, 90, b"\x1b%G"), (2, 0, b"\x00\x04"), (2, 120, "Légende fictive".encode()),
                                      (2, 25, b"mot1"), (2, 25, b"mot2")]),
            comments=("commentaire fictif",), icc=fabrique.icc_bytes("Profil fictif"), trailer=b"XY")
        self.card = metadonnees.inspecter_octets(self.data)

    def test_dimensions_density_and_coding(self) -> None:
        card = self.card
        self.assertEqual((card["format"], card["largeur"], card["hauteur"], card["bits"], card["composantes"]), ("JPEG", 16, 24, 8, 1))
        self.assertEqual(card["densite"], {"x": 300, "y": 300, "unite": "ppp", "source": "JFIF"})
        self.assertIn("baseline", card["codage"])
        self.assertEqual(card["taille_physique_cm"], [0.1, 0.2])
        self.assertEqual(card["erreurs"], [])

    def test_exif_fields(self) -> None:
        ifd0 = self.card["exif"]["ifd0"]
        self.assertEqual(ifd0["Make"], "FabricantTest")
        self.assertEqual(ifd0["Model"], "ScanTest 3000")
        self.assertEqual(ifd0["Software"], "LogicielTest 1.2")
        self.assertEqual(ifd0["DateTime"], "2020:03:04 10:11:12")
        self.assertEqual(ifd0["ImageDescription"], "Registre fictif BB/34/000")
        self.assertEqual(ifd0["Copyright"], "Domaine public")
        self.assertEqual(ifd0["XResolution"], 400.0)
        self.assertEqual(self.card["exif"]["exif"]["DateTimeOriginal"], "2020:03:04 10:11:12")
        self.assertEqual(self.card["exif"]["exif"]["PixelXDimension"], 16)

    def test_xmp_iptc_comment_icc(self) -> None:
        card = self.card
        self.assertEqual(card["xmp"]["champs"]["xmp:CreatorTool"], "OutilTest")
        self.assertEqual(card["xmp"]["champs"]["dc:title"], "Vue fictive 3")
        self.assertEqual(card["iptc"]["Caption-Abstract"], "Légende fictive")
        self.assertEqual(card["iptc"]["Keywords"], ["mot1", "mot2"])
        self.assertEqual(card["iptc"]["CodedCharacterSet"], "UTF-8")
        self.assertEqual(card["commentaires"], ["commentaire fictif"])
        self.assertEqual(card["icc"]["description"], "Profil fictif")
        self.assertEqual(card["icc"]["espace"], "GRAY")

    def test_segments_and_trailing_bytes(self) -> None:
        markers = [segment["marqueur"] for segment in self.card["segments"]]
        self.assertEqual(markers, ["APP0", "APP1", "APP1", "APP2", "APP13", "COM", "DQT", "SOF0", "DHT", "DHT", "SOS"])
        self.assertEqual(self.card["octets_apres_fin"], 2)
        self.assertIsInstance(self.card["qualite_estimee"], int)

    def test_free_text_lists_every_descriptive_field(self) -> None:
        free = {(item["source"], item["champ"]): item["valeur"] for item in self.card["texte_libre"]}
        self.assertEqual(free[("EXIF", "ImageDescription")], "Registre fictif BB/34/000")
        self.assertEqual(free[("XMP", "dc:title")], "Vue fictive 3")
        self.assertEqual(free[("IPTC", "Caption-Abstract")], "Légende fictive")
        self.assertEqual(free[("JPEG", "commentaire (COM)")], "commentaire fictif")
        self.assertNotIn(("EXIF", "Software"), free)            # technical, not descriptive

    def test_bare_jpeg_has_no_free_text(self) -> None:
        card = metadonnees.inspecter_octets(fabrique.jpeg_bytes(8, 8, jfif_density=None))
        self.assertEqual(card["texte_libre"], [])
        self.assertNotIn("densite", card)
        self.assertNotIn("exif", card)
        self.assertNotIn("octets_apres_fin", card)

    @unittest.skipUnless(importlib.util.find_spec("PIL"), "Pillow absent : contrôle croisé non exécuté")
    def test_synthetic_jpeg_is_a_valid_image_for_pillow(self) -> None:
        from PIL import Image  # noqa: PLC0415
        with Image.open(io.BytesIO(self.data)) as image:
            image.load()
            self.assertEqual(image.size, (16, 24))


class PngTiffJp2Test(unittest.TestCase):
    def test_png_text_chunks_density_time_exif(self) -> None:
        data = fabrique.png_bytes(5, 7, text={"Title": "Titre fictif", "Software": "LogicielTest"},
                                  compressed_text={"Comment": "texte compressé"},
                                  international_text={"Description": "décrit en UTF-8 ✓"}, time=(2020, 1, 2, 3, 4, 5), exif=EXIF)
        card = metadonnees.inspecter_octets(data)
        self.assertEqual((card["format"], card["largeur"], card["hauteur"], card["couleur"]), ("PNG", 5, 7, "niveaux de gris"))
        self.assertEqual(card["densite"]["x"], 300.0)
        self.assertEqual(card["texte_png"], {"Title": "Titre fictif", "Software": "LogicielTest", "Comment": "texte compressé",
                                             "Description": "décrit en UTF-8 ✓"})
        self.assertEqual(card["date_modification"], "2020-01-02T03:04:05Z")
        self.assertEqual(card["exif"]["ifd0"]["Make"], "FabricantTest")
        fields = {item["champ"] for item in card["texte_libre"] if item["source"] == "PNG"}
        self.assertEqual(fields, {"Title", "Comment", "Description"})   # "Software" is technical
        self.assertEqual(card["blocs"]["tEXt"], 2)
        self.assertEqual(card["erreurs"], [])

    def test_png_with_a_wrong_crc_is_reported(self) -> None:
        data = bytearray(fabrique.png_bytes(text={"Title": "x"}))
        data[data.index(b"tEXt") + 5] ^= 0xFF
        self.assertTrue(any("CRC" in error for error in metadonnees.inspecter_octets(bytes(data))["erreurs"]))

    def test_tiff_tags_both_byte_orders(self) -> None:
        for order in ("<", ">"):
            data = fabrique.tiff_bytes([(256, 4, 100), (257, 4, 200), (258, 3, 8), (277, 3, 1), (270, 2, "cote fictive"),
                                        (282, 5, (300, 1)), (283, 5, (300, 1)), (296, 3, 2), (305, 2, "LogicielTest")], order=order)
            card = metadonnees.inspecter_octets(data)
            self.assertEqual((card["format"], card["largeur"], card["hauteur"], card["pages"]), ("TIFF", 100, 200, 1))
            self.assertEqual(card["densite"]["x"], 300.0)
            self.assertEqual(card["tiff"]["ifd0"]["Software"], "LogicielTest")
            self.assertEqual(card["texte_libre"], [{"source": "TIFF", "champ": "ImageDescription", "valeur": "cote fictive"}])

    def test_jpeg2000_boxes(self) -> None:
        card = metadonnees.inspecter_octets(fabrique.jp2_bytes(20, 30, xml="<note>cote fictive</note>",
                                                               xmp=fabrique.xmp_packet({"dc:source": "Source fictive"})))
        self.assertEqual((card["format"], card["largeur"], card["hauteur"], card["bits"]), ("JPEG 2000", 20, 30, 8))
        self.assertEqual(card["densite"]["x"], 300.0)
        self.assertEqual(card["xmp"]["champs"]["dc:source"], "Source fictive")
        self.assertIn("cote fictive", card["xml"][0])
        self.assertEqual(len(card["texte_libre"]), 2)

    def test_damaged_and_foreign_files_never_raise(self) -> None:
        jpeg = fabrique.jpeg_bytes(exif=EXIF)
        samples = [b"", b"\xff\xd8\xff", jpeg[:40], jpeg[:200], fabrique.png_bytes()[:30], b"II*\x00\x08\x00\x00\x00\xff\xff",
                   b"\xff\xd8\xff\xe1\x00\x10Exif\x00\x00II*\x00\xff\xff\xff\xff", b"GIF89a", b"RIFF\x00\x00\x00\x00WEBP",
                   b"\x00\x00\x00\x0cjP  \r\n\x87\n\x00\x00\x00\x05abcd", b"%PDF-1.4 ...", b"<!DOCTYPE html><html>erreur</html>"]
        for sample in samples:
            card = metadonnees.inspecter_octets(sample)
            self.assertIn("format", card)
            self.assertIsInstance(card["erreurs"], list)
        self.assertEqual(metadonnees.inspecter_octets(b"%PDF-1.4")["format"], "PDF")
        html = metadonnees.inspecter_octets(b"<!DOCTYPE html><html>erreur</html>")
        self.assertEqual(html["format"], "HTML ou XML")
        self.assertIn("pas une image", html["erreurs"][0])


class NamesTest(unittest.TestCase):
    def test_lot_identifier_of_the_xml_exports(self) -> None:
        name = metadonnees.decoder_nom("DAFANCH94_NUMJ011088_D")
        self.assertEqual((name["forme"], name["prefixe"], name["serie"], name["numero"], name["chiffres"], name["suffixe"]),
                         ("lot-de-numerisation", "DAFANCH94", "NUMJ", 11088, 6, "D"))
        self.assertIn("hypothese", name)

    def test_size_suffix_is_separated_from_the_stem(self) -> None:
        name = metadonnees.decoder_nom("FRAN_0000_00123_L-medium.jpg")
        self.assertEqual(name["radical"], "FRAN_0000_00123_L")
        self.assertEqual(name["taille"]["mot"], "medium")
        self.assertEqual(name["extension"], "jpg")
        self.assertEqual(metadonnees.decoder_nom("FRAN_ANX_014014.pdf")["categorie"], "ANX")

    def test_url_roles(self) -> None:
        url = metadonnees.decoder_url("https://exemple.invalid/siv/media/FRAN_IR_000001/D12/DAFANCH94_NUMJ000007_D")
        self.assertEqual((url["forme"], url["inventaire"], url["notice"], url["media"]["numero"]),
                         ("lien d'images d'une notice", "FRAN_IR_000001", "D12", 7))
        iiif = metadonnees.decoder_url("https://exemple.invalid/iiif/abc123/full/full/0/default.jpg")
        self.assertEqual(iiif["iiif"]["identifiant"], "abc123")
        self.assertEqual(iiif["iiif"]["taille"], "full")
        self.assertEqual(metadonnees.decoder_url("https://exemple.invalid/x?a=1&b=2")["parametres"], {"a": "1", "b": "2"})

    def test_sequence_analysis(self) -> None:
        continuous = metadonnees.analyser_suite(["LOT_000101_L", "LOT_000102_L", "LOT_000103_L"])
        self.assertTrue(continuous["continu"])
        self.assertIn("donne l'ordre", continuous["conclusion"])
        gaps = metadonnees.analyser_suite(["LOT_000101_L", "LOT_000105_L", "LOT_000106_L"])
        self.assertFalse(gaps["continu"])
        self.assertEqual(gaps["trous"], [[101, 105]])
        shuffled = metadonnees.analyser_suite(["LOT_000103_L", "LOT_000101_L", "LOT_000102_L"])
        self.assertIn("ne pas trier", shuffled["conclusion"])
        self.assertIn("une seule vue", metadonnees.analyser_suite(["LOT_000101_L"])["conclusion"])
        self.assertIn("pas une suite", metadonnees.analyser_suite(["a.jpg", "zz9.png"])["conclusion"])


class FileAndTableTest(unittest.TestCase):
    def test_inspecter_reads_a_file_its_name_and_its_url(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "DAFANCH94_NUMJ000101_L-medium.jpg"
            path.write_bytes(fabrique.jpeg_bytes(8, 8, comments=("note fictive",)))
            other = Path(directory) / "DAFANCH94_NUMJ000102_L-medium.jpg"
            other.write_bytes(fabrique.jpeg_bytes(8, 8))
            card = metadonnees.inspecter(path, url="https://exemple.invalid/mm/media/download/DAFANCH94_NUMJ000101_L-medium.jpg")
            self.assertEqual(card["nom"]["taille"]["mot"], "medium")
            self.assertEqual(card["url"]["forme"], "fichier du serveur de médias")
            text = metadonnees.tableau([card, metadonnees.inspecter(other)])
            self.assertIn("8 × 8 px", text)
            self.assertIn("TEXTE LIBRE", text)
            self.assertIn("note fictive", text)
            self.assertIn("Récapitulatif", text)
            self.assertIn("donne l'ordre", text)
            missing = metadonnees.inspecter(Path(directory) / "absent.jpg")
            self.assertEqual(missing["format"], "inconnu")
            self.assertTrue(missing["erreurs"])

    def test_a_name_that_contradicts_the_pixels_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "volume-n12_w1000.jpg"                       # the name claims a width of 1000 px
            path.write_bytes(fabrique.jpeg_bytes(8, 8))
            card = metadonnees.inspecter(path, pil=False)
            self.assertEqual(card["nom"]["largeur_demandee"], 1000)
            self.assertTrue(any("le nom annonce une largeur de 1000 px, l'image en fait 8" in error for error in card["erreurs"]))
            self.assertIn("ne pas se fier au nom", metadonnees.tableau([card]))

    def test_table_says_so_when_nothing_descriptive_exists(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "page.png"
            path.write_bytes(fabrique.png_bytes())
            text = metadonnees.tableau([metadonnees.inspecter(path, pil=False)])
            self.assertIn("aucun champ descriptif", text)
            self.assertIn("ne peut venir que de la lecture de l'image", text)


if __name__ == "__main__":
    unittest.main()
