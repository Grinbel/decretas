"""The probe runner against a local fictitious site: hops, cookie, follow-ups, images, stop rules, report."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from decretas import net
from decretas.an_images import plan, rapport, reprise

from . import fabrique
from .serveur import Answer, FakeClock, Site

SECRET = "noeud1~0123456789ABCDEFSECRET"
MEDIA = ["LOT_000101_L", "LOT_000102_L", "LOT_000103_L", "LOT_000104_L", "LOT_000105_L"]


def media_step(identifier: str = "B2", case: str = "image-1899-1912", notice: str = "D1", images: int = 2) -> plan.Step:
    return plan.Step(identifier, case, f"/siv/media/FRAN_IR_000001/{notice}/", "images", "question d'essai",
                     images=images, decree=("FRAN_IR_000001", notice))


class ProbeCase(unittest.TestCase):
    def setUp(self) -> None:
        self.site = Site()
        self.addCleanup(self.site.close)
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name) / "reprise"
        self.clock = FakeClock()
        self.said: list[str] = []

    def settings(self, **overrides) -> reprise.Settings:
        values = {"root": self.root, "base": self.site.base, "delay": 0.0, "timeout": 5.0}
        values.update(overrides)
        return reprise.Settings(**values)

    def run_probe(self, steps: list[plan.Step], **overrides) -> tuple[int, reprise.Probe]:
        probe = reprise.Probe(self.settings(**overrides), steps, clock=self.clock, sleep=self.clock.sleep, say=self.said.append)
        return probe.run(), probe

    def observations(self) -> dict:
        return json.loads((self.root / "observations.json").read_text(encoding="utf-8"))

    def decree(self, notice: str = "D1", media: list[str] | None = None, **landing) -> None:
        """Routes of one decree: media link -> 302 (+cookie) -> landing page ; its images."""
        media = MEDIA if media is None else media
        landing_path = f"/siv/consultation.action?irId=FRAN_IR_000001&udId={notice}"
        self.site.redirect(f"/siv/media/FRAN_IR_000001/{notice}/", f"/siv/consultation.action;jsessionid={SECRET}?irId=FRAN_IR_000001&udId={notice}",
                           cookies=(f"JSESSIONID={SECRET}; Path=/siv/; HttpOnly",))
        self.site.html(landing_path, fabrique.landing_html(media, **landing))
        for rank, name in enumerate(media):
            for suffix in ("", "-medium", "-min"):
                self.site.image(f"/mm/media/download/{name}{suffix}.jpg", fabrique.jpeg_bytes(8 + rank, 8, comments=(name + suffix,)))


class HappyPathTest(ProbeCase):
    def test_redirect_cookie_images_and_sidecar(self) -> None:
        self.decree()
        code, probe = self.run_probe([media_step()])
        self.assertEqual(code, reprise.EXIT_DONE)
        self.assertEqual(self.site.paths(), [
            "/siv/media/FRAN_IR_000001/D1/",
            "/siv/consultation.action?irId=FRAN_IR_000001&udId=D1",          # ;jsessionid=… removed from the address
            "/mm/media/download/LOT_000101_L.jpg",                           # first view, largest variant
            "/mm/media/download/LOT_000103_L.jpg"])                          # an inner view
        cookies = [cookie for _path, cookie, _agent in self.site.requests]
        self.assertEqual(cookies, [None, f"JSESSIONID={SECRET}", None, None])  # sent back on /siv/ only (Path)
        self.assertTrue(all(agent == net.USER_AGENT for _path, _cookie, agent in self.site.requests))
        step = self.observations()["etapes"]["B2"]
        self.assertEqual(step["etat"], "ok")
        self.assertEqual([hop["statut"] for hop in step["sauts"]], [302, 200])
        self.assertNotIn("jsessionid", step["sauts"][0]["location"])
        self.assertTrue(step["sauts"][0]["session_dans_adresse"])
        self.assertIn(";jsessionid=***", step["sauts"][0]["en_tetes"]["location"])
        self.assertEqual(step["nombre_de_vues"], 5)
        self.assertTrue(step["suite_des_noms"]["continu"])
        self.assertEqual([image["vue"] for image in step["images"]], [1, 3])
        first = step["images"][0]
        self.assertEqual(first["fichier"], "images/image-1899-1912/LOT_000101_L.jpg")
        self.assertEqual((first["fiche"]["format"], first["fiche"]["largeur"]), ("JPEG", 8))
        self.assertEqual(first["fiche"]["commentaires"], ["LOT_000101_L"])
        self.assertTrue((self.root / first["fichier"]).is_file())
        sidecar = json.loads((self.root / "images" / "image-1899-1912" / "decret.json").read_text(encoding="utf-8"))
        self.assertEqual(sidecar["images"]["LOT_000103_L.jpg"]["notice"], "D1")
        self.assertEqual(sidecar["images"]["LOT_000103_L.jpg"]["vue"], 3)
        self.assertEqual(probe.sent, 4)

    def test_the_session_value_is_written_nowhere_but_the_private_state(self) -> None:
        self.decree()
        self.run_probe([media_step()])
        for path in self.root.rglob("*"):
            if path.is_file() and path.name != "etat.json":
                self.assertFalse(SECRET.encode() in path.read_bytes(), f"valeur de session trouvée dans {path.name}")
        self.assertNotIn(SECRET, "\n".join(self.said))
        state = self.root / "etat.json"
        self.assertEqual(state.stat().st_mode & 0o777, 0o600)
        self.assertEqual(json.loads(state.read_text())["temoins"]["JSESSIONID"]["path"], "/siv/")
        report = rapport.write_report(self.root, self.root.parent / "rapport.md", now=self.clock())
        self.assertNotIn(SECRET, report.read_text(encoding="utf-8"))
        self.assertIn("`JSESSIONID=***`", report.read_text(encoding="utf-8"))

    def test_second_run_sends_nothing(self) -> None:
        self.decree()
        self.run_probe([media_step()])
        before = len(self.site.requests)
        code, probe = self.run_probe([media_step()])
        self.assertEqual((code, probe.sent, len(self.site.requests)), (reprise.EXIT_DONE, 0, before))
        self.assertEqual(len(self.observations()["etapes"]["B2"]["images"]), 2)

    def test_viewer_page_is_followed_when_the_landing_page_has_no_image(self) -> None:
        self.decree(media=[])
        viewer = "/siv/multimedia/Galerie.action?mediaParam=abc"
        self.site.html("/siv/consultation.action?irId=FRAN_IR_000001&udId=D1", fabrique.landing_html([], viewer=viewer))
        self.site.html(viewer, fabrique.landing_html(MEDIA[:2], title="Visionneuse fictive"))
        for name in MEDIA[:2]:
            self.site.image(f"/mm/media/download/{name}.jpg", fabrique.jpeg_bytes())
        code, _probe = self.run_probe([media_step()])
        self.assertEqual(code, reprise.EXIT_DONE)
        self.assertIn(viewer, self.site.paths())
        step = self.observations()["etapes"]["B2"]
        self.assertEqual(len(step["suivis"]), 1)
        self.assertEqual(step["nombre_de_vues"], 2)
        self.assertEqual(len(step["images"]), 2)

    def test_no_image_found_is_said_and_nothing_is_guessed(self) -> None:
        self.decree(media=[])
        code, _probe = self.run_probe([media_step()])
        self.assertEqual(code, reprise.EXIT_DONE)
        step = self.observations()["etapes"]["B2"]
        self.assertEqual(step["images"], [])
        self.assertTrue(any("--suivre" in note for note in step["notes"]))
        self.assertEqual(len(self.site.requests), 2)

    def test_manual_address_is_added_to_the_plan(self) -> None:
        self.decree(media=[])
        self.site.image("/mm/media/download/LOT_000777_L.jpg", fabrique.jpeg_bytes())
        code, _probe = self.run_probe([media_step()], manual={"image-1899-1912": ["/mm/media/download/LOT_000777_L.jpg"]})
        self.assertEqual(code, reprise.EXIT_DONE)
        manual = self.observations()["etapes"]["M1"]
        self.assertEqual(manual["images"][0]["fiche"]["format"], "JPEG")
        self.assertIn("directement une image", manual["notes"][0])

    def test_image_quota_is_two_per_case(self) -> None:
        self.decree("D1")
        self.decree("D2")
        steps = [media_step("L1", "lots", "D1", images=1), media_step("L2", "lots", "D2", images=0),
                 plan.Step("L4", "lots", "/siv/media/FRAN_IR_000001/D2/", "images", "q", images=2, decree=("FRAN_IR_000001", "D2"))]
        self.run_probe(steps)
        etapes = self.observations()["etapes"]
        self.assertEqual([len(etapes[key]["images"]) for key in ("L1", "L2", "L4")], [1, 0, 1])


class RedirectAndStatusTest(ProbeCase):
    def test_redirect_to_another_host_is_recorded_not_followed(self) -> None:
        self.site.redirect("/siv/UD/FRAN_IR_000001/D1", "https://ailleurs.exemple.invalid/connexion")
        code, _probe = self.run_probe([plan.Step("B1", "image-1899-1912", "/siv/UD/FRAN_IR_000001/D1", "notice", "q")])
        self.assertEqual(code, reprise.EXIT_DONE)
        step = self.observations()["etapes"]["B1"]
        self.assertEqual(step["etat"], "hors-hote")
        self.assertIn("non suivie", step["sauts"][0]["note"])
        self.assertEqual(len(self.site.requests), 1)

    def test_a_404_is_an_answer_not_a_failure(self) -> None:
        self.decree()
        steps = [plan.Step("O1", "site", "/oai/OAIHandler?verb=Identify", "sonde", "q", 2), media_step()]
        code, _probe = self.run_probe(steps)
        self.assertEqual(code, reprise.EXIT_DONE)
        etapes = self.observations()["etapes"]
        self.assertEqual(etapes["O1"]["etat"], "http-404")
        self.assertEqual(etapes["O1"]["corps"]["genre"], "html")          # the error body is kept and described
        self.assertTrue((self.root / etapes["O1"]["sauts"][0]["fichier"]).is_file())
        self.assertEqual(etapes["B2"]["etat"], "ok")

    def test_redirect_loop_is_bounded(self) -> None:
        self.site.redirect("/a", "/b")
        self.site.redirect("/b", "/a")
        code, _probe = self.run_probe([plan.Step("T1", "site", "/a", "page", "q")], max_hops=3)
        self.assertEqual(code, reprise.EXIT_DONE)
        self.assertLessEqual(len(self.site.requests), 2)                   # the second visit of /a is read from the cache
        self.assertEqual(self.observations()["etapes"]["T1"]["etat"], "trop-de-redirections")

    def test_export_is_compared_with_the_local_copy(self) -> None:
        exports = Path(self.directory.name) / "an"
        exports.mkdir()
        (exports / "FRAN_IR_000009.xml").write_bytes(b"<?xml version='1.0'?><ead>ancien</ead>")
        self.site.routes["/siv/exportXML.action?irId=FRAN_IR_000009"] = Answer(200, b"<?xml version='1.0'?><ead>nouveau, plus long</ead>",
                                                                                 {"Content-Type": "application/xml"})
        self.run_probe([plan.Step("X1", "site", "/siv/exportXML.action?irId=FRAN_IR_000009", "export", "q", 2)], local_exports=exports)
        comparison = self.observations()["etapes"]["X1"]["comparaison_locale"]
        self.assertFalse(comparison["identique"])
        self.assertGreater(comparison["octets_recus"], comparison["octets_locaux"])


class StopRulesTest(ProbeCase):
    def three_steps(self) -> list[plan.Step]:
        return [plan.Step(f"T{rank}", "site", f"/page{rank}", "page", "q") for rank in (1, 2, 3)]

    def test_first_503_stops_for_thirty_minutes_and_is_resumable(self) -> None:
        self.site.html("/page1", "<html><title>un</title></html>")
        self.site.routes["/page2"] = [Answer(503, b"<html><title>SIA - Erreur 503</title></html>"), Answer(200, b"<html><title>deux</title></html>")]
        self.site.html("/page3", "<html><title>trois</title></html>")
        code, probe = self.run_probe(self.three_steps())
        self.assertEqual(code, reprise.EXIT_PAUSED)
        self.assertEqual(self.site.paths(), ["/page1", "/page2"])           # no retry, the third page is not asked
        self.assertIn("30 minutes", probe.message)
        state = json.loads((self.root / "etat.json").read_text())
        self.assertEqual(state["pause_jusqu_a"], self.clock.now + 1800)
        self.assertEqual(state["echecs"][0]["statut"], 503)
        etapes = self.observations()["etapes"]
        self.assertEqual((etapes["T1"]["etat"], etapes["T2"]["etat"], etapes["T3"]["etat"]), ("ok", "interrompue", "non-atteinte"))
        self.assertTrue(any(path.name.endswith(".http503") for path in (self.root / "pages").iterdir()))   # error body kept

        self.clock.now += 600                                                # ten minutes later: still paused
        code, probe = self.run_probe(self.three_steps())
        self.assertEqual(code, reprise.EXIT_PAUSED)
        self.assertIn("Rien n'a été envoyé", probe.message)
        self.assertEqual(len(self.site.requests), 2)

        self.clock.now += 1300                                               # past the pause: resume where it stopped
        code, probe = self.run_probe(self.three_steps())
        self.assertEqual(code, reprise.EXIT_DONE)
        self.assertEqual(self.site.paths(), ["/page1", "/page2", "/page2", "/page3"])   # page1 is not asked again
        self.assertEqual(probe.sent, 2)
        self.assertEqual([step["etat"] for step in self.observations()["etapes"].values()], ["ok", "ok", "ok"])

    def test_third_failure_of_the_day_stops_until_tomorrow(self) -> None:
        self.site.routes["/page1"] = Answer(503, b"panne")
        for attempt in (1, 2, 3):
            code, probe = self.run_probe(self.three_steps())
            self.assertEqual(code, reprise.EXIT_PAUSED if attempt < 3 else reprise.EXIT_DAY_STOP, attempt)
            self.clock.now += 1801
        self.assertEqual(len(self.site.requests), 3)
        self.assertIn("demain", probe.message)
        code, probe = self.run_probe(self.three_steps())                     # same day, pause elapsed: still refused
        self.assertEqual(code, reprise.EXIT_DAY_STOP)
        self.assertEqual(len(self.site.requests), 3)
        self.clock.now += 24 * 3600                                          # next day: allowed again
        self.site.html("/page1", "<html></html>")
        self.site.html("/page2", "<html></html>")
        self.site.html("/page3", "<html></html>")
        code, _probe = self.run_probe(self.three_steps())
        self.assertEqual(code, reprise.EXIT_DONE)

    def test_502_and_time_out_count_as_failures(self) -> None:
        self.site.routes["/page1"] = Answer(502, b"")
        code, _probe = self.run_probe(self.three_steps())
        self.assertEqual(code, reprise.EXIT_PAUSED)
        self.clock.now += 1801
        self.site.routes["/page1"] = Answer(200, b"<html></html>", delay=1.5)
        code, probe = self.run_probe(self.three_steps(), timeout=0.3)
        self.assertEqual(code, reprise.EXIT_PAUSED)
        self.assertIn("aucune réponse", probe.message)
        failures = json.loads((self.root / "etat.json").read_text())["echecs"]
        self.assertEqual([failure["statut"] for failure in failures], [502, 0])

    def test_403_stops_everything_until_a_human_decides(self) -> None:
        self.site.html("/page1", "<html></html>")
        self.site.routes["/page2"] = [Answer(403, b"interdit"), Answer(200, b"<html></html>")]
        self.site.html("/page3", "<html></html>")
        code, probe = self.run_probe(self.three_steps())
        self.assertEqual(code, reprise.EXIT_BLOCKED)
        self.assertIn("REFUS", probe.message)
        self.clock.now += 48 * 3600
        code, _probe = self.run_probe(self.three_steps())                    # two days later: still refused, nothing sent
        self.assertEqual(code, reprise.EXIT_BLOCKED)
        self.assertEqual(len(self.site.requests), 2)
        code, _probe = self.run_probe(self.three_steps(), lift_block=True)   # explicit human decision
        self.assertEqual(code, reprise.EXIT_DONE)
        self.assertIsNone(json.loads((self.root / "etat.json").read_text())["blocage"])

    def test_antibot_page_is_a_refusal(self) -> None:
        self.site.html("/page1", "<!DOCTYPE html><html><title>Just a moment...</title></html>")
        code, _probe = self.run_probe(self.three_steps())
        self.assertEqual(code, reprise.EXIT_BLOCKED)
        self.assertEqual(len(self.site.requests), 1)

    def test_request_cap_per_run_and_per_day(self) -> None:
        for rank in (1, 2, 3):
            self.site.html(f"/page{rank}", "<html></html>")
        code, probe = self.run_probe(self.three_steps(), cap=2)
        self.assertEqual((code, probe.sent), (reprise.EXIT_CAP, 2))
        self.assertEqual(self.observations()["etapes"]["T3"]["etat"], "plafond")
        code, probe = self.run_probe(self.three_steps(), cap=2, day_cap=2)   # the day cap is already spent
        self.assertEqual((code, probe.sent), (reprise.EXIT_CAP, 0))
        self.assertEqual(len(self.site.requests), 2)
        code, probe = self.run_probe(self.three_steps(), cap=2, day_cap=10)
        self.assertEqual((code, probe.sent), (reprise.EXIT_DONE, 1))

    def test_real_host_never_goes_below_six_seconds(self) -> None:
        settings = reprise.Settings(root=self.root, delay=0.5)
        client = reprise.make_client(settings, {}, clock=self.clock, sleep=self.clock.sleep, budget=1)
        _family, policy = client.policy_for(plan.BASE + "/siv/IR/FRAN_IR_000001")
        self.assertEqual(policy.min_delay, 6.0)
        self.assertEqual(policy.max_backoffs, 0)
        with self.assertRaises(net.HostNotAllowed):
            client.policy_for("https://francearchives.gouv.fr/")
        with self.assertRaises(net.HostNotAllowed):
            client.policy_for("http://www.siv.archives-nationales.culture.gouv.fr/siv/")   # no plain http on the real host

    def test_pacing_between_two_requests(self) -> None:
        self.site.html("/page1", "<html></html>")
        self.site.html("/page2", "<html></html>")
        self.run_probe(self.three_steps()[:2], delay=7.0)
        self.assertEqual(len(self.clock.slept), 1)
        self.assertAlmostEqual(self.clock.slept[0], 7.0, places=3)


class PlanAndReportTest(ProbeCase):
    def test_person_link_verdicts(self) -> None:
        self.decree("AP1")                                                    # the decree: five views
        self.decree("PERS1", media=MEDIA[2:3])                                # the person: only the third view
        steps = [plan.Step("P2", "personne-avec-images", "/siv/media/FRAN_IR_000001/PERS1/", "images", "q", images=1, decree=("FRAN_IR_000001", "AP1")),
                 plan.Step("P3", "personne-avec-images", "/siv/media/FRAN_IR_000001/AP1/", "images", "q", images=1, decree=("FRAN_IR_000001", "AP1"))]
        self.run_probe(steps)
        text = rapport.write_report(self.root, self.root.parent / "r.md", now=self.clock()).read_text(encoding="utf-8")
        self.assertIn("**Page(s) précise(s).**", text)
        self.assertIn("vue(s) n° 3", text)
        self.assertIn("| P2 |", text)
        self.assertIn("donne l'ordre des vues", text)
        self.assertIn("Aucun champ de texte libre", text) if "texte libre : aucun" in text else self.assertIn("texte libre", text)

    def test_person_link_opening_the_whole_decree(self) -> None:
        self.decree("AP1")
        self.decree("PERS1")
        steps = [plan.Step("P2", "personne-avec-images", "/siv/media/FRAN_IR_000001/PERS1/", "images", "q", decree=("FRAN_IR_000001", "AP1")),
                 plan.Step("P3", "personne-avec-images", "/siv/media/FRAN_IR_000001/AP1/", "images", "q", decree=("FRAN_IR_000001", "AP1"))]
        self.run_probe(steps)
        text = rapport.write_report(self.root, self.root.parent / "r.md").read_text(encoding="utf-8")
        self.assertIn("**Tout le décret.**", text)

    def lot_step(self, identifier: str, notice: str, media: list[str]) -> plan.Step:
        path = f"/siv/media/FRAN_IR_000001/{notice}/LOTX94_NUMJ000103_D"
        landing = f"/siv/consultation.action?irId=FRAN_IR_000001&udId={notice}"
        self.site.redirect(path, landing)
        self.site.html(landing, fabrique.landing_html(media))
        return plan.Step(identifier, "lots", path, "images", "q", decree=("FRAN_IR_000001", notice))

    def test_report_says_what_the_identifier_of_a_link_designates(self) -> None:
        steps = [self.lot_step("L1", "N1", ["LOTX94_NUMJ000102_D", "LOTX94_NUMJ000103_D", "LOTX94_NUMJ000104_D"]),   # a file
                 self.lot_step("L2", "N2", ["LOTX94_NUMJ000103_D_0001", "LOTX94_NUMJ000103_D_0002"]),                # a lot
                 self.lot_step("L3", "N3", ["LOTX94_NUMJ000101_L", "LOTX94_NUMJ000105_L"]),                          # same counter
                 self.lot_step("L4", "N4", ["LOTX94_NUMJ000900_L", "LOTX94_NUMJ000901_L"]),                          # unrelated
                 plan.Step("L5", "lots", "/siv/media/FRAN_IR_000001/N5/LOTX94_NUMJ000103_D", "images", "q")]         # 404
        self.run_probe(steps)
        text = rapport.write_report(self.root, self.root.parent / "lots.md").read_text(encoding="utf-8")
        self.assertIn("- L1 : le lien porte `LOTX94_NUMJ000103_D` (numéro 103). C'est exactement le nom de la vue n° 2 sur 3", text)
        self.assertIn("- L2 : le lien porte `LOTX94_NUMJ000103_D` (numéro 103). Les 2 vues ont un nom qui commence par cet identifiant", text)
        self.assertIn("- L3 : le lien porte `LOTX94_NUMJ000103_D` (numéro 103). Son numéro est dans l'intervalle des numéros des vues (101 à 105)", text)
        self.assertIn("- L4 : le lien porte `LOTX94_NUMJ000103_D` (numéro 103). Les vues portent d'autres numéros (900 à 901)", text)
        self.assertIn("- L5 : le lien porte `LOTX94_NUMJ000103_D` (numéro 103). Étape sans réponse 2xx", text)

    def test_report_without_any_answer_says_not_observed(self) -> None:
        text = rapport.write_report(self.root, self.root.parent / "vide.md").read_text(encoding="utf-8")
        self.assertGreaterEqual(text.count("Non observé"), 5)
        self.assertIn("Aucune requête du plan n'a encore été envoyée", text)
        self.assertNotIn("Tout le décret", text)

    def test_report_before_any_run_shows_the_whole_plan_and_the_availability_log(self) -> None:
        checks = self.root.parent / "disponibilite"
        checks.mkdir(parents=True)
        (checks / "manifest.jsonl").write_text(
            json.dumps({"url": "https://exemple.invalid/siv/IR/X", "status": 503, "at": "2026-11-11T17:05:08+00:00", "network": True}) + "\n"
            + json.dumps({"url": "https://exemple.invalid/siv/IR/X", "status": 0, "at": "2026-11-11T18:16:08+00:00", "network": True}) + "\n",
            encoding="utf-8")
        full = plan.build_plan("PERS-A", None)
        text = rapport.write_report(self.root, self.root.parent / "avant.md", planned=full.steps, availability=checks).read_text(encoding="utf-8")
        self.assertIn(f"Étapes en réponse 2xx : 0 sur {len(full.steps)}", text)
        self.assertIn("2026-11-11 17:05 → HTTP 503 ; 2026-11-11 18:16 → aucune réponse", text)
        self.assertIn("| L1 | lots |", text)
        self.assertEqual(text.count("| — | non lancée |"), len(full.steps))        # one line per step in the table of § 1
        self.assertIn("L1 (non lancée)", text)

    def test_report_after_a_failure_lists_what_is_missing(self) -> None:
        self.site.routes["/siv/media/FRAN_IR_000001/D1/"] = Answer(503, b"<html><title>SIA - Erreur 503</title></html>")
        self.run_probe([media_step(), plan.Step("T1", "site", "/page1", "page", "q", 2)])
        text = rapport.write_report(self.root, self.root.parent / "r.md").read_text(encoding="utf-8")
        self.assertIn("B2 (interrompue par un échec)", text)
        self.assertIn("T1 (non atteinte", text)
        self.assertIn("| 503 |", text)

    def test_dry_run_text_lists_every_address_and_sends_nothing(self) -> None:
        full = plan.build_plan("PERS-A", "PERS-B")
        text = reprise.describe_plan(full.steps, full.missing, self.settings(delay=6.0))
        for step in full.steps:
            self.assertIn(step.url(self.site.base), text)
        self.assertIn("rien n'est envoyé", text)
        self.assertEqual(self.site.requests, [])
        self.assertFalse(self.root.exists())


class DefaultPlanTest(unittest.TestCase):
    def test_order_cases_and_tiers(self) -> None:
        full = plan.build_plan("PERS-A", "PERS-B")
        identifiers = [step.id for step in full.steps]
        self.assertEqual(identifiers[:4], ["L1", "L2", "L3", "L4"])
        self.assertTrue(all("DAFANCH94_NUMJ" in step.path and step.path.startswith("/siv/media/") for step in full.steps[:4]))
        first_tier = [step for step in full.steps if step.tier == 1]
        self.assertEqual([step.case for step in first_tier if step.case != "lots"][:1], ["personne-avec-images"])
        self.assertEqual({step.case for step in first_tier},
                         {"lots", "personne-avec-images", "personne-sans-images", "image-1899-1912", "image-1928",
                          "image-1933-1948", "admission-1946-1947"})
        self.assertEqual(len(identifiers), len(set(identifiers)))
        self.assertEqual(len(full.steps), 30)
        self.assertTrue(all(step.path.startswith("/") for step in full.steps))
        self.assertEqual(full.missing, ())
        self.assertLessEqual(sum(step.images for step in full.steps), 12)
        self.assertEqual([step.id for step in full.select({"image-1928"}, 1)], ["E1"])
        self.assertEqual([step.id for step in full.select({"image-1928"}, 2)], ["E1", "E2"])
        self.assertIn("/siv/UD/FRAN_IR_057268/PERS-A", [step.path for step in full.steps])
        self.assertIn("/siv/media/FRAN_IR_057268/PERS-A/", [step.path for step in full.steps])

    def test_person_steps_are_left_out_when_the_data_is_missing(self) -> None:
        full = plan.build_plan(None, None)
        self.assertNotIn("P1", [step.id for step in full.steps])
        self.assertNotIn("S1", [step.id for step in full.steps])
        self.assertIn("P3", [step.id for step in full.steps])
        self.assertEqual(len(full.missing), 2)

    def test_person_exemplars_come_from_the_site_data(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            data = Path(directory)
            (data / "an-decrets.json").write_text(json.dumps({
                "champs": ["id", "inv", "notice"], "tables": {"inv": ["FRAN_IR_057268", "FRAN_IR_056878"]},
                "lignes": [[0, 0, "AUTRE"], [1, 0, "AP002722"], [2, 1, "idd_1897_01-01"]]}), encoding="utf-8")
            (data / "an-personnes.json").write_text(json.dumps({
                "champs": ["id", "role", "dec", "notice", "img"], "tables": {"role": ["principal", "epouse", "enfant"]},
                "lignes": [[0, 0, 0, "ailleurs", 1], [1, 1, 1, None, 1], [2, 0, 1, "fictif-sans", 0], [3, 0, 1, "fictif-avec", 1],
                           [4, 0, 2, "fictif-1897", 0]]}), encoding="utf-8")
            full = plan.plan_from_site_data(data)
            paths = {step.id: step.path for step in full.steps}
            self.assertEqual(paths["P1"], "/siv/UD/FRAN_IR_057268/fictif-avec")
            self.assertEqual(paths["S1"], "/siv/UD/FRAN_IR_056878/fictif-1897")
            self.assertEqual(plan.plan_from_site_data(data / "absent").missing.__len__(), 2)

    def test_no_search_probe_uses_a_person_name(self) -> None:
        full = plan.build_plan("PERS-A", "PERS-B")
        searches = [step.path for step in full.steps if "fullText=" in step.path or "fulltext=" in step.path]
        self.assertEqual(len(searches), 2)
        self.assertTrue(all(f"={plan.SEARCH_WORD}" in path for path in searches))


if __name__ == "__main__":
    unittest.main()
