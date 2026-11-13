"""The generic strategies that find media addresses in pages of unknown structure."""
from __future__ import annotations

import json
import unittest

from decretas.an_images import extraction

from . import fabrique

BASE = "http://127.0.0.1:9/siv/consultation.action?irId=FRAN_IR_000001&udId=D1"
MEDIA = ["LOT_000101_L", "LOT_000102_L", "LOT_000103_L"]


def urls(found: extraction.Extraction, strategy: str) -> set[str]:
    return {candidate.url for candidate in found.candidates if strategy in candidate.strategies}


class StrategiesTest(unittest.TestCase):
    def test_standard_tags_and_data_attributes(self) -> None:
        found = extraction.extract(fabrique.landing_html(MEDIA).encode(), BASE, "text/html")
        self.assertEqual(found.kind, "html")
        self.assertIn("http://127.0.0.1:9/mm/media/download/LOT_000101_L-min.jpg", urls(found, "balise"))       # img src
        self.assertIn("http://127.0.0.1:9/mm/media/download/LOT_000101_L-medium.jpg", urls(found, "balise"))    # a href
        self.assertIn("http://127.0.0.1:9/mm/media/download/LOT_000101_L.jpg", urls(found, "attribut-data"))    # data-zoom
        self.assertIn("http://127.0.0.1:9/mm/media/download/LOT_000103_L.jpg", urls(found, "motif-mm"))
        self.assertEqual(found.identifiers, [])                    # "LOT_…" is not a known identifier shape

    def test_json_blob_and_json_attribute(self) -> None:
        page = """<html><body>
        <div id="v" data-config='{"pages": [{"src": "/mm/media/download/A_0001.jpg"}, {"src": "/mm/media/download/A_0002.jpg"}]}'></div>
        <script type="application/json">{"manifeste": "/siv/iiif/abc/manifest.json", "vues": ["/img/vue/A_0003.jp2"]}</script>
        </body></html>"""
        found = extraction.extract(page.encode(), BASE)
        self.assertEqual(urls(found, "attribut-data"),
                         {"http://127.0.0.1:9/mm/media/download/A_0001.jpg", "http://127.0.0.1:9/mm/media/download/A_0002.jpg"})
        self.assertIn("http://127.0.0.1:9/siv/iiif/abc/manifest.json", urls(found, "json"))
        self.assertIn("http://127.0.0.1:9/siv/iiif/abc/manifest.json", urls(found, "iiif"))
        kinds = {candidate.url.rsplit("/", 1)[-1]: candidate.kind for candidate in found.candidates}
        self.assertEqual(kinds["manifest.json"], "iiif")
        self.assertEqual(kinds["A_0003.jp2"], "image")

    def test_inline_script_strings_and_handlers(self) -> None:
        page = """<html><head><script>
        var visionneuse = {url: '/siv/multimedia/Galerie.action?mediaParam=xyz', images: ["\\/mm\\/media\\/download\\/B_0001-max.jpg"]};
        </script></head><body>
        <a href="javascript:ouvrir('/siv/visionneuse/afficher.action?id=7')">voir</a>
        <span onclick="zoom('/mm/media/download/B_0002.jpg')">zoom</span></body></html>"""
        found = extraction.extract(page.encode(), BASE)
        self.assertIn("http://127.0.0.1:9/siv/multimedia/Galerie.action?mediaParam=xyz", urls(found, "script"))
        self.assertIn("http://127.0.0.1:9/mm/media/download/B_0001-max.jpg", urls(found, "script"))
        self.assertIn("http://127.0.0.1:9/siv/visionneuse/afficher.action?id=7", urls(found, "gestionnaire"))
        self.assertIn("http://127.0.0.1:9/mm/media/download/B_0002.jpg", urls(found, "gestionnaire"))

    def test_iiif_hints_and_image_requests(self) -> None:
        page = '<html><body><img src="https://images.exemple.invalid/iiif/2/doc%2F12/full/800,/0/default.jpg">' \
               '<a href="/iiif/2/doc%2F12/info.json">description</a></body></html>'
        found = extraction.extract(page.encode(), BASE)
        image = next(c for c in found.candidates if c.url.endswith("default.jpg"))
        self.assertEqual((image.kind, image.same_host), ("image", False))
        self.assertEqual(extraction.size_rank(image.url), 80)
        self.assertEqual(extraction.size_rank(image.url.replace("800,", "full")), 100)
        self.assertEqual(next(c for c in found.candidates if c.url.endswith("info.json")).kind, "iiif")

    def test_identifiers_without_address_are_listed(self) -> None:
        page = "<html><body><p>Lot DAFANCH94_NUMJ011088_D ; pièce FRAN_0123_04567_L ; inventaire FRAN_IR_057268</p></body></html>"
        found = extraction.extract(page.encode(), BASE)
        self.assertEqual(found.identifiers, ["DAFANCH94_NUMJ011088_D", "FRAN_0123_04567_L"])   # the inventory id is not a media

    def test_json_and_javascript_bodies(self) -> None:
        body = json.dumps({"sequences": [{"canvases": [{"images": [{"resource": {"@id": "http://127.0.0.1:9/iiif/x/full/full/0/default.jpg"}}]}]}]})
        found = extraction.extract(body.encode(), BASE, "application/json")
        self.assertEqual(found.kind, "json")
        self.assertEqual([c.kind for c in found.candidates], ["image"])
        script = b"function ouvrir(id){ window.open('/siv/multimedia/Galerie.action?mediaParam=' + id); } var racine = \"/mm/media/download/\";"
        found = extraction.extract(script, BASE, "application/javascript")
        self.assertEqual(found.kind, "javascript")
        self.assertIn("media", found.structure["mots_cles"])
        self.assertTrue(any("Galerie.action" in candidate.url for candidate in found.candidates))

    def test_site_furniture_is_set_aside(self) -> None:
        found = extraction.extract(fabrique.landing_html(MEDIA).encode(), BASE)
        chrome = {candidate.url.rsplit("/", 1)[-1] for candidate in found.candidates if candidate.chrome}
        self.assertEqual(chrome, {"logo.png", "consultation.js", "site.css"})
        self.assertNotIn("logo.png", {candidate.url.rsplit("/", 1)[-1] for candidate in found.images()})

    def test_session_identifier_is_removed_from_addresses(self) -> None:
        page = '<html><body><a href="/siv/multimedia/Galerie.action;jsessionid=SECRET123?mediaParam=1">v</a></body></html>'
        found = extraction.extract(page.encode(), BASE)
        self.assertEqual([candidate.url for candidate in found.candidates], ["http://127.0.0.1:9/siv/multimedia/Galerie.action?mediaParam=1"])

    def test_structure_summary(self) -> None:
        found = extraction.extract(fabrique.landing_html(MEDIA, viewer="/siv/multimedia/Galerie.action?mediaParam=1").encode(), BASE)
        structure = found.structure
        self.assertEqual(structure["titre"], "Décret fictif du 1er janvier 1900 - Salle fictive")
        self.assertEqual(structure["h1"], ["Décret fictif du 1er janvier 1900"])
        self.assertEqual(structure["balises"]["img"], 4)
        self.assertEqual(structure["formulaires"][0]["champs"], ["token", "texte"])     # field names, never their values
        self.assertNotIn("JETON-FICTIF", json.dumps(structure))
        self.assertIn("vignettes", structure["identifiants_html"])
        self.assertFalse(structure["page_erreur"])

    def test_error_page_is_recognised(self) -> None:
        page = b'<!DOCTYPE html><html><head><title>SIA - Erreur 503</title></head><body>Une erreur est survenue.</body></html>'
        self.assertTrue(extraction.extract(page, BASE).structure["page_erreur"])

    def test_broken_markup_and_binary_bodies_do_not_raise(self) -> None:
        for body in (b"<html><img src='/mm/media/download/x.jpg' <a href=", b"\x00\x01\x02\x03" * 50, b"", b"<<<>>>", b"{not json"):
            extraction.extract(body, BASE)
        self.assertEqual(extraction.extract(fabrique.jpeg_bytes(), BASE).kind, "image")
        self.assertEqual(extraction.sniff(b"%PDF-1.4"), "pdf")
        self.assertEqual(extraction.sniff(b"<?xml version='1.0'?><ead/>"), "xml")


class ViewsTest(unittest.TestCase):
    def setUp(self) -> None:
        found = extraction.extract(fabrique.landing_html(MEDIA + ["LOT_000104_L", "LOT_000105_L"]).encode(), BASE)
        self.views = extraction.group_views(found.candidates)

    def test_one_view_per_page_whatever_the_size(self) -> None:
        self.assertEqual([view.key.rsplit("/", 1)[-1] for view in self.views],
                         ["LOT_000101_L", "LOT_000102_L", "LOT_000103_L", "LOT_000104_L", "LOT_000105_L"])
        self.assertEqual({len(view.variants) for view in self.views}, {3})

    def test_best_variant_is_the_largest(self) -> None:
        self.assertEqual(self.views[0].best().url, "http://127.0.0.1:9/mm/media/download/LOT_000101_L.jpg")
        ranks = sorted(extraction.size_rank(variant.url) for variant in self.views[0].variants)
        self.assertEqual(ranks, [10, 40, 60])
        self.assertGreater(extraction.size_rank("http://h/x/a-max.jpg"), extraction.size_rank("http://h/x/a.jpg"))
        self.assertEqual(extraction.size_rank("http://h/dl?id=3&size=min"), 10)
        self.assertEqual(extraction.view_key("http://h/dl?id=3&size=min"), extraction.view_key("http://h/dl?id=3&size=max"))
        self.assertNotEqual(extraction.view_key("http://h/dl?id=3&size=min"), extraction.view_key("http://h/dl?id=4&size=min"))

    def test_first_and_an_inner_view_are_chosen(self) -> None:
        chosen = extraction.choose_views(self.views, 2)
        self.assertEqual([view.position for view in chosen], [0, 2])
        self.assertEqual([view.position for view in extraction.choose_views(self.views[:2], 2)], [0, 1])
        self.assertEqual(len(extraction.choose_views(self.views, 1)), 1)
        self.assertEqual(extraction.choose_views(self.views, 0), [])
        self.assertEqual(extraction.choose_views([], 2), [])

    def test_follow_up_pages_keep_only_likely_viewers_on_the_same_host(self) -> None:
        page = """<html><body><a href="/siv/accueil.action">accueil</a><a href="/siv/aide.action?page=2">aide</a>
        <a href="/siv/multimedia/Galerie.action?mediaParam=9">images</a><a href="https://ailleurs.invalid/viewer?x=1">ailleurs</a>
        <a href="/siv/iiif/doc/manifest.json">manifeste</a></body></html>"""
        found = extraction.extract(page.encode(), BASE)
        pages = [candidate.url.split("9/", 1)[1] for candidate in extraction.follow_up_pages(found, set())]
        self.assertEqual(pages, ["siv/iiif/doc/manifest.json", "siv/multimedia/Galerie.action?mediaParam=9"])
        visited = {"http://127.0.0.1:9/siv/iiif/doc/manifest.json"}
        self.assertEqual(len(extraction.follow_up_pages(found, visited)), 1)


if __name__ == "__main__":
    unittest.main()
