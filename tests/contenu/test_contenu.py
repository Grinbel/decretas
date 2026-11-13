"""Validation of the guidance content (site/contenu/*.json).

The content promises that every sentence is true and that every unverified step is visibly
marked. These tests cannot check truth, but they check everything mechanical around it:
shapes, cross-references, the single link table, the vocabulary rules of CONTEXT.md, and the
agreement between the JSON files and docs/contenu-sources.md.

Run from the repository root: python3 -m unittest discover -s tests -t .
"""
from __future__ import annotations

import html
import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path
from typing import Any, Iterator

ROOT = Path(__file__).resolve().parents[2]
CONTENU = ROOT / "site" / "contenu"
SOURCES_DOC = ROOT / "docs" / "contenu-sources.md"

FILES = ("types-d-actes", "aiguillage", "guides", "bilan", "vocabulaire", "liens", "a-propos")
LINK_STATUSES = {"teste-200", "bloque-pour-les-robots-attendu-ok-pour-un-humain", "non-teste"}
LINK_ORIGINS = {"teste-par-nous", "recopie-d-une-page-officielle", "forme-ecrite-par-la-source", "deduction"}
VERIFICATION_STATES = {"verifie", "partiel", "non-verifie"}
STEP_SUPPORTS = {"ecran-vu", "page-officielle-lue", "donnees-locales", "non-vu"}
STEP_FIELDS = ("id", "titre", "instruction", "ce_que_l_ecran_montre", "issues_possibles", "ecrans_communs",
               "liens", "verifie", "appui", "preuves", "a_confirmer")
REQUIRED_GUIDE_CASES = set("abcdefghij")
CONTEXT_TERMS = {
    "Décret d'admission", "Jugement d'admission", "Source primaire", "Citation", "Indice", "Ancêtre recherché",
    "Terme", "Variante", "Correspondance", "Correspondance partielle", "Fenêtre", "Particule", "Bilan de recherche",
}
REQUIRED_ACRONYMS = {"BOGGA", "JORF", "AN", "ANOM", "SDANF", "CNF", "OCR"}

# The only contact details allowed in the content: the official ones listed in
# docs/research/sources-2026-11/other-sources.md (§ 2 and § 5.1).
ALLOWED_EMAILS = {
    "sdanf-accueil@interieur.gouv.fr",
    "sdanf-brupi-communications@interieur.gouv.fr",
    "anom.aix@culture.gouv.fr",
}
ALLOWED_PHONES = {"0240844600"}

# Keys whose values are identifiers, link material or lists of words to avoid: not user-facing prose.
NON_PROSE_KEYS = {
    "id", "schema", "cle", "gabarit", "exemple", "hote", "preuves", "lien", "liens", "repli", "voir", "guides",
    "voie", "voies", "voies_secondaires", "types", "vers", "a_eviter", "ne_pas_dire", "origine", "statut", "appui",
    "etat", "couvertures", "natures", "ecran", "ecrans_communs", "suite", "actes_possibles", "depart", "cas",
    "famille", "sigle", "source_id", "date_test", "maj", "langue",
}
QUOTED = re.compile(r"«[^«»]*»")
URL = re.compile(r"https?://\S+")
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE = re.compile(r"(?<![\d/])(?:\+33[\s.]?\(?0?\)?[\s.]?|0)[1-9](?:[\s.]?\d{2}){4}(?!\d)")
PLACEHOLDER = re.compile(r"\{([a-z_]+)\}")

# Wording that must never appear in the platform's own voice (outside « » quotations).
FORBIDDEN_OUTSIDE_QUOTES = {
    "« référence » employé comme un terme valable": r"\bréférences?\b",
    "« numéro de décret » employé comme un terme valable": r"\bnuméros? de décret\b",
    "« hit »": r"\bhits?\b",
    "« match »": r"\bmatch(?:s|es)?\b",
    "« résultat approchant »": r"\brésultats? approchants?\b",
    "conclusion « n'a pas été admis »": r"n['’](?:a|ont) pas été admis",
    "conclusion « n'était pas français »": r"n['’]étai(?:t|ent) pas français",
    "« a obtenu la nationalité française »": r"\ba obtenu la nationalité\b",
    "« Français de plein droit » / « vrai Français »": r"\bfrançais de plein droit\b|\bvrais? français\b",
    "le mot du droit colonial sans guillemets": r"\bindigènes?\b|\bindigénat\b",
    "« autochtone »": r"\bautochtones?\b",
}
# Cards about routes open to Algerian Muslims: the word must stay inside quotations there.
MUSLIM_CARDS = {"T1", "T7", "T8", "T11", "T12", "T13"}


def load(name: str) -> dict[str, Any]:
    """Load one content file by its base name."""
    with (CONTENU / f"{name}.json").open(encoding="utf-8") as handle:
        return json.load(handle)


def walk(node: Any, path: str = "") -> Iterator[tuple[str, str, str]]:
    """Yield (path, key, string) for every string in a JSON tree; `key` is the nearest object key."""
    def inner(value: Any, where: str, key: str) -> Iterator[tuple[str, str, str]]:
        if isinstance(value, str):
            yield where, key, value
        elif isinstance(value, list):
            for index, item in enumerate(value):
                yield from inner(item, f"{where}[{index}]", key)
        elif isinstance(value, dict):
            for child_key, child in value.items():
                yield from inner(child, f"{where}.{child_key}", child_key)
    yield from inner(node, path, "")


def prose(document: Any, name: str) -> Iterator[tuple[str, str]]:
    """Yield (path, text) for the user-facing strings of a document."""
    for where, key, text in walk(document, name):
        if key not in NON_PROSE_KEYS:
            yield where, text


def outside_quotes(text: str) -> str:
    """Remove URLs and « » quotations: what remains is the platform's own voice."""
    return QUOTED.sub(" ", URL.sub(" ", text))


#: Evidence kept on the machine where it was gathered and left out of the public repository:
#: the research notes quote real persons (git-ignored); .scratch/ names the pilot family
#: (committed locally, excluded by scripts/publier-github.sh).
RESEARCH_NOTES = "docs/research/sources-2026-11/"
PRIVATE_NOTES = (RESEARCH_NOTES, ".scratch/")
LOCAL_EVIDENCE = ("data/", *PRIVATE_NOTES)


def evidence_file(pointer: str) -> Path:
    """Path of the file an evidence pointer designates (report pointers carry a ' § section' suffix)."""
    return ROOT / pointer.split(" § ")[0]


class ContentTestCase(unittest.TestCase):
    """Loads every content file once."""

    docs: dict[str, dict[str, Any]]

    @classmethod
    def setUpClass(cls) -> None:
        cls.docs = {name: load(name) for name in FILES}
        cls.links = {link["id"]: link for link in cls.docs["liens"]["liens"]}
        cls.guides = {guide["id"]: guide for guide in cls.docs["guides"]["guides"]}
        cls.screens = {screen["id"] for screen in cls.docs["guides"]["ecrans_communs"]}
        cls.cards = {card["id"]: card for card in cls.docs["types-d-actes"]["types"]}
        cls.routes = {route["id"]: route for route in cls.docs["aiguillage"]["voies"]}

    def assert_verification(self, block: dict[str, Any], where: str) -> None:
        self.assertEqual(set(block), {"etat", "preuves", "note"}, where)
        self.assertIn(block["etat"], VERIFICATION_STATES, where)
        self.assertIsInstance(block["preuves"], list, where)

    def assert_links_exist(self, ids: list[str], where: str) -> None:
        for link_id in ids:
            self.assertIn(link_id, self.links, f"{where}: lien inconnu « {link_id} »")

    def assert_guides_exist(self, ids: list[str], where: str) -> None:
        for guide_id in ids:
            self.assertIn(guide_id, self.guides, f"{where}: guide inconnu « {guide_id} »")


class FilesTest(ContentTestCase):
    def test_every_file_is_present_and_declares_its_schema(self) -> None:
        for name in FILES:
            document = self.docs[name]
            self.assertEqual(document["schema"], f"decretas.contenu.{name}/1")
            self.assertEqual(document["langue"], "fr")
            self.assertRegex(document["maj"], r"^\d{4}-\d{2}-\d{2}$")

    def test_no_other_file_in_the_directory(self) -> None:
        present = {path.name for path in CONTENU.iterdir()}
        self.assertEqual(present, {f"{name}.json" for name in FILES})


class LinksTest(ContentTestCase):
    def test_link_shape(self) -> None:
        fields = {"id", "libelle", "hote", "gabarit", "variables", "exemple", "statut", "date_test", "origine",
                  "preuves", "observation", "proposer", "avertissement", "repli"}
        for link in self.links.values():
            where = f"liens/{link['id']}"
            self.assertEqual(set(link), fields, where)
            self.assertIn(link["statut"], LINK_STATUSES, where)
            self.assertIn(link["origine"], LINK_ORIGINS, where)
            self.assertIsInstance(link["proposer"], bool, where)
            self.assertTrue(link["preuves"], f"{where}: aucune preuve")
            self.assertTrue(link["gabarit"].startswith("https://"), where)
            self.assertEqual(link["hote"], link["gabarit"].split("/")[2], where)

    def test_link_ids_are_unique(self) -> None:
        ids = [link["id"] for link in self.docs["liens"]["liens"]]
        self.assertEqual(len(ids), len(set(ids)))

    def test_placeholders_are_declared(self) -> None:
        declared = set(self.docs["liens"]["variables"])
        for link in self.links.values():
            found = set(PLACEHOLDER.findall(link["gabarit"]))
            self.assertEqual(found, set(link["variables"]), f"liens/{link['id']}")
            self.assertLessEqual(found, declared, f"liens/{link['id']}: variable non documentée")

    def test_example_matches_template(self) -> None:
        for link in self.links.values():
            pattern = "".join(
                "(.+?)" if index % 2 else re.escape(part)
                for index, part in enumerate(PLACEHOLDER.split(link["gabarit"]))
            )
            self.assertRegex(link["exemple"], f"^{pattern}$", f"liens/{link['id']}")
            self.assertNotRegex(link["exemple"], r"[{}]", f"liens/{link['id']}: variable non remplacée")

    def test_tested_links_carry_a_date_and_untested_ones_do_not(self) -> None:
        for link in self.links.values():
            if link["statut"] == "non-teste":
                self.assertIsNone(link["date_test"], link["id"])
            else:
                self.assertRegex(link["date_test"] or "", r"^\d{4}-\d{2}-\d{2}$", link["id"])

    def test_untested_deduced_links_are_hidden_or_warned(self) -> None:
        for link in self.links.values():
            if link["statut"] == "non-teste" and link["origine"] != "recopie-d-une-page-officielle":
                self.assertTrue(not link["proposer"] or link["avertissement"],
                                f"liens/{link['id']}: lien jamais vu, proposé sans avertissement")

    def test_fallback_links_exist(self) -> None:
        for link in self.links.values():
            if link["repli"] is not None:
                self.assertIn(link["repli"], self.links, link["id"])
                self.assertNotEqual(link["repli"], link["id"])

    def test_statuses_and_origins_are_documented(self) -> None:
        self.assertEqual(set(self.docs["liens"]["statuts"]), LINK_STATUSES)
        self.assertEqual(set(self.docs["liens"]["origines"]), LINK_ORIGINS)

    def test_no_url_outside_the_link_table(self) -> None:
        for name in FILES:
            if name == "liens":
                continue
            for where, _key, text in walk(self.docs[name], name):
                self.assertNotRegex(text, r"https?://", f"{where}: adresse écrite hors de liens.json")

    def test_every_link_reference_exists(self) -> None:
        for name in FILES:
            for where, key, text in walk(self.docs[name], name):
                if key in ("liens", "lien", "repli") and name != "liens":
                    self.assertIn(text, self.links, f"{where}: lien inconnu « {text} »")


class GuidesTest(ContentTestCase):
    def test_required_cases_are_covered(self) -> None:
        cases = {guide["cas"] for guide in self.guides.values()}
        self.assertLessEqual(REQUIRED_GUIDE_CASES, cases)

    def test_guide_shape(self) -> None:
        fields = {"id", "cas", "titre", "pour_qui", "voie", "duree", "ce_qu_il_vous_faut", "etapes", "resultat",
                  "limites", "suite"}
        for guide in self.guides.values():
            self.assertEqual(set(guide), fields, guide["id"])
            self.assertIn(guide["voie"], self.routes, guide["id"])
            self.assertTrue(guide["etapes"], guide["id"])
            self.assert_guides_exist(guide["suite"], f"guides/{guide['id']}/suite")

    def test_every_step_has_the_required_fields(self) -> None:
        for guide in self.guides.values():
            step_ids = [step["id"] for step in guide["etapes"]]
            self.assertEqual(len(step_ids), len(set(step_ids)), guide["id"])
            for step in guide["etapes"]:
                where = f"guides/{guide['id']}/{step['id']}"
                self.assertEqual(tuple(step), STEP_FIELDS, where)
                for field in ("titre", "instruction", "ce_que_l_ecran_montre"):
                    self.assertTrue(step[field].strip(), f"{where}: « {field} » vide")
                self.assertIsInstance(step["verifie"], bool, where)
                self.assertIn(step["appui"], STEP_SUPPORTS, where)
                self.assertTrue(step["preuves"], f"{where}: aucune preuve")

    def test_every_step_lists_its_possible_outcomes(self) -> None:
        for guide in self.guides.values():
            for step in guide["etapes"]:
                where = f"guides/{guide['id']}/{step['id']}"
                self.assertGreaterEqual(len(step["issues_possibles"]), 2, f"{where}: une seule issue prévue")
                for outcome in step["issues_possibles"]:
                    self.assertLessEqual({"si", "signifie", "faire"}, set(outcome), where)
                    self.assertLessEqual(set(outcome), {"si", "signifie", "faire", "ecran"}, where)
                    if "ecran" in outcome:
                        self.assertIn(outcome["ecran"], self.screens, where)
                for screen in step["ecrans_communs"]:
                    self.assertIn(screen, self.screens, where)

    def test_unverified_steps_are_marked(self) -> None:
        for guide in self.guides.values():
            for step in guide["etapes"]:
                where = f"guides/{guide['id']}/{step['id']}"
                if step["verifie"]:
                    self.assertIsNone(step["a_confirmer"], f"{where}: note « à confirmer » sur une étape vérifiée")
                    self.assertNotEqual(step["appui"], "non-vu", where)
                else:
                    self.assertTrue((step["a_confirmer"] or "").strip(),
                                    f"{where}: étape non vérifiée sans note « à confirmer »")

    def test_steps_only_use_links_shown_to_the_public(self) -> None:
        for guide in self.guides.values():
            for step in guide["etapes"]:
                where = f"guides/{guide['id']}/{step['id']}"
                self.assert_links_exist(step["liens"], where)
                for link_id in step["liens"]:
                    self.assertTrue(self.links[link_id]["proposer"], f"{where}: lien non proposable « {link_id} »")

    def test_common_screens(self) -> None:
        fields = {"id", "titre", "ce_que_vous_voyez", "ce_que_cela_veut_dire", "que_faire", "verifie", "preuves",
                  "a_confirmer"}
        for screen in self.docs["guides"]["ecrans_communs"]:
            self.assertEqual(set(screen), fields, screen["id"])
            self.assertTrue(screen["preuves"], screen["id"])
            self.assertEqual(screen["verifie"], screen["a_confirmer"] is None, screen["id"])

    def test_expected_screens_are_described(self) -> None:
        text = json.dumps(self.docs["guides"]["ecrans_communs"], ensure_ascii=False)
        for marker in ("SIA - Erreur 503", "Sorry, you have been blocked", "case à cocher", "non numérisé"):
            self.assertIn(marker, text)

    def test_image_only_years_guide_names_the_three_periods(self) -> None:
        text = self.guides["an-annee-en-images"]["pour_qui"]
        for marker in ("1899", "1912", "avril", "décembre 1928", "1933", "1948"):
            self.assertIn(marker, text)

    def test_dossier_guide_has_the_branch_number_known_cote_unknown(self) -> None:
        text = json.dumps(self.guides["dossier-pierrefitte"], ensure_ascii=False)
        self.assertIn("Vous avez le numéro, mais pas la cote.", text)


class DecisionTreeTest(ContentTestCase):
    def setUp(self) -> None:
        tree = self.docs["aiguillage"]
        self.questions = {question["id"]: question for question in tree["questions"]}
        self.outcomes = {outcome["id"]: outcome for outcome in tree["issues"]}

    def test_answers_point_to_existing_nodes(self) -> None:
        self.assertIn(self.docs["aiguillage"]["depart"], self.questions)
        for question in self.questions.values():
            self.assertGreaterEqual(len(question["reponses"]), 2, question["id"])
            for answer in question["reponses"]:
                target = answer["vers"]
                pool = self.questions if target["type"] == "question" else self.outcomes
                self.assertIn(target["type"], ("question", "issue"), answer["id"])
                self.assertIn(target["id"], pool, f"{question['id']}/{answer['id']}")

    def test_outcomes_point_to_existing_cards_routes_and_guides(self) -> None:
        for outcome in self.outcomes.values():
            where = f"aiguillage/{outcome['id']}"
            for card in outcome["types"]:
                self.assertIn(card, self.cards, where)
            self.assertIn(outcome["voie"], self.routes, where)
            for route in outcome["voies_secondaires"]:
                self.assertIn(route, self.routes, where)
            self.assert_guides_exist(outcome["guides"], where)
            self.assert_links_exist(outcome["liens"], where)
            self.assert_verification(outcome["verification"], where)
            self.assertTrue(outcome["message"].strip(), where)

    def test_routes_point_to_existing_guides(self) -> None:
        for route in self.routes.values():
            self.assert_guides_exist(route["guides"], f"voies/{route['id']}")

    def test_every_question_and_outcome_is_reachable_within_three_questions(self) -> None:
        depths: dict[str, int] = {}

        def visit(question_id: str, depth: int) -> None:
            self.assertLessEqual(depth, 3, f"plus de trois questions pour atteindre {question_id}")
            for answer in self.questions[question_id]["reponses"]:
                target = answer["vers"]
                if target["type"] == "question":
                    visit(target["id"], depth + 1)
                else:
                    depths[target["id"]] = min(depth, depths.get(target["id"], depth))

        visit(self.docs["aiguillage"]["depart"], 1)
        self.assertEqual(set(depths), set(self.outcomes), "issue inaccessible ou inconnue")

    def test_every_route_of_the_brief_is_offered(self) -> None:
        used = {outcome["voie"] for outcome in self.outcomes.values()}
        used |= {route for outcome in self.outcomes.values() for route in outcome["voies_secondaires"]}
        for route in ("recherche-par-nom", "recherche-guidee-images", "bulletin-imprime", "legifrance",
                      "etat-civil-en-algerie", "declaration-recognitive", "hors-perimetre"):
            self.assertIn(route, used)
        self.assertIn("demande-au-ministere", self.routes)

    def test_the_sold_number_case_explains_what_a_citation_is(self) -> None:
        message = self.outcomes["numero-a-verifier"]["message"]
        for marker in ("date du décret", "publication", "page", "« 262-1412 »"):
            self.assertIn(marker, message)

    def test_periods_cover_1865_to_1962_without_gap(self) -> None:
        periods = [p for p in self.docs["aiguillage"]["epoques"] if p["id"] != "e-jugements"]
        years = sorted((p["annees"]["debut"], p["annees"]["fin"]) for p in periods)
        self.assertEqual(years[0][0], 1865)
        self.assertEqual(years[-1][1], 1962)
        for (_start, end), (next_start, _next_end) in zip(years, years[1:]):
            self.assertEqual(next_start, end + 1)
        for period in self.docs["aiguillage"]["epoques"]:
            self.assertIn(period["voie"], self.routes, period["id"])
            self.assert_guides_exist(period["guides"], period["id"])
            for card in period["actes_possibles"]:
                self.assertIn(card, self.cards, period["id"])


class CardsTest(ContentTestCase):
    def test_sixteen_cards(self) -> None:
        self.assertEqual(list(self.cards), [f"T{number}" for number in range(1, 17)])

    def test_card_shape(self) -> None:
        document = self.docs["types-d-actes"]
        fields = {"id", "cle", "titre_court", "periode", "qui", "natures", "nature_texte", "fondement", "nominatif",
                  "publie", "ou_publie", "ou_conserve", "sur_ce_site", "etablit", "n_etablit_pas", "a_savoir",
                  "verification"}
        for card in self.cards.values():
            where = f"types/{card['id']}"
            self.assertEqual(set(card), fields, where)
            self.assertLessEqual(set(card["natures"]), set(document["natures"]), where)
            self.assertIn(card["publie"], document["valeurs_publie"], where)
            self.assertIsInstance(card["nominatif"], bool, where)
            site = card["sur_ce_site"]
            self.assertTrue(site["couvertures"], where)
            self.assertLessEqual(set(site["couvertures"]), set(document["couvertures"]), where)
            for route in site["voies"]:
                self.assertIn(route, self.routes, where)
            self.assert_guides_exist(site["guides"], where)
            self.assert_verification(card["verification"], where)

    def test_statements_are_sourced(self) -> None:
        for card in self.cards.values():
            for field in ("etablit", "n_etablit_pas"):
                for statement in card[field]:
                    where = f"types/{card['id']}/{field}"
                    self.assertEqual(set(statement), {"texte", "source", "preuves", "etat"}, where)
                    self.assertTrue(statement["source"].strip(), where)
                    self.assertTrue(statement["preuves"], where)
                    self.assertIn(statement["etat"], VERIFICATION_STATES, where)

    def test_the_colonial_category_is_explained_once(self) -> None:
        note = self.docs["types-d-actes"]["note_vocabulaire"]
        self.assertIn("« indigène »", note)
        self.assertIn("droit colonial", note)

    def test_admission_of_an_algerian_muslim_is_not_called_naturalisation(self) -> None:
        for card_id in MUSLIM_CARDS:
            for where, text in prose(self.cards[card_id], f"types/{card_id}"):
                self.assertNotRegex(outside_quotes(text).lower(), r"naturalis",
                                    f"{where}: « naturalisation » hors citation dans une carte d'admission")
        glossary = {term["id"]: term for term in self.docs["vocabulaire"]["termes"]}
        self.assertIn("naturalisations-algeriennes", glossary)
        self.assertIn("impropre", glossary["naturalisations-algeriennes"]["definition"])


class ReportTest(ContentTestCase):
    def test_templates_only_use_declared_variables(self) -> None:
        report = self.docs["bilan"]
        declared = set(report["variables"])
        for where, _key, text in walk(report, "bilan"):
            for variable in PLACEHOLDER.findall(text):
                self.assertIn(variable, declared, f"{where}: variable inconnue {{{variable}}}")
        for line in report["ce_qui_a_ete_fouille"]["lignes"]:
            self.assertEqual(set(PLACEHOLDER.findall(line["gabarit"])), set(line["variables"]), line["id"])
        # No second copy of the coverage in the content files: the meta files of the data are the
        # only source of the years read (regression: « 1873 et 1888 » outlived the Bulletin pipeline).
        self.assertNotIn("couverture_de_reference", report)

    def test_searched_sources_are_described_in_the_about_page(self) -> None:
        known = {source["id"] for source in self.docs["a-propos"]["sources"]}
        for line in self.docs["bilan"]["ce_qui_a_ete_fouille"]["lignes"]:
            if line["source_id"] is not None:
                self.assertIn(line["source_id"], known, line["id"])

    def test_empty_result_message_is_dignified(self) -> None:
        message = self.docs["bilan"]["resume"]["aucune"]
        self.assertIn("aucune correspondance dans les sources fouillées", message)
        self.assertIn("6 000", message)
        self.assertIn("rien de défavorable", message)
        # Regression (blocker of 2026-11-12): « Votre ancêtre était français, comme tous les Algériens
        # depuis 1865 » was said after every empty search, also to families of foreigners.
        self.assertNotRegex(message.lower(), r"était français|était de nationalité")

    def test_no_statement_on_the_nationality_of_the_ancestor(self) -> None:
        """The site never says what this ancestor's nationality was (À propos promises it)."""
        pattern = re.compile(r"\b(?:votre ancêtre|il|elle) (?:était|est) (?:donc )?(?:français|de nationalité)")
        for name in FILES:
            for where, text in prose(self.docs[name], name):
                self.assertNotRegex(outside_quotes(text).lower(), pattern, where)

    def test_judgment_reminder_is_constant(self) -> None:
        reminder = self.docs["bilan"]["rappel_jugement"]
        self.assertIn("jugement", reminder["texte"])
        self.assertIn("publiés nulle part", reminder["texte"])
        self.assert_guides_exist(reminder["guides"], "bilan/rappel_jugement")

    def test_three_official_quotations_with_source_and_date(self) -> None:
        quotations = self.docs["bilan"]["citations_officielles"]["principales"]
        self.assertEqual(len(quotations), 3)
        for quotation in quotations + self.docs["bilan"]["citations_officielles"]["autres"]:
            for field in ("texte", "auteur", "source", "date"):
                self.assertTrue(quotation[field].strip(), f"{quotation['id']}: « {field} » vide")
            self.assertIn(quotation["lien"], self.links, quotation["id"])
            self.assertTrue(quotation["preuves"], quotation["id"])

    def test_scale_figures_are_sourced(self) -> None:
        for figure in self.docs["bilan"]["echelle"]["chiffres"]:
            self.assertTrue(figure["source"].strip(), figure["id"])
            self.assertTrue(figure["preuves"], figure["id"])
            self.assertIn(figure["etat"], VERIFICATION_STATES, figure["id"])

    def test_uncovered_items_point_to_routes_and_guides(self) -> None:
        for line in self.docs["bilan"]["ce_qui_n_est_pas_couvert"]["lignes"]:
            self.assertIn(line["voie"], self.routes, line["id"])
            self.assert_guides_exist(line["guides"], line["id"])
            self.assert_verification(line["verification"], line["id"])
        for line in self.docs["bilan"]["demarches_restantes"]["lignes"]:
            self.assert_guides_exist(line["guides"], line["id"])

    def test_absent_name_caveat(self) -> None:
        self.assertEqual(self.docs["bilan"]["mises_en_garde"]["titre"],
                         "Un nom absent n'est pas une absence de décret")


class GlossaryTest(ContentTestCase):
    def test_context_terms_and_acronyms_are_present(self) -> None:
        glossary = self.docs["vocabulaire"]
        self.assertLessEqual(CONTEXT_TERMS, {term["terme"] for term in glossary["termes"]})
        self.assertLessEqual(REQUIRED_ACRONYMS, {entry["sigle"] for entry in glossary["sigles"]})

    def test_term_shape_and_cross_references(self) -> None:
        glossary = self.docs["vocabulaire"]
        ids = [term["id"] for term in glossary["termes"]]
        self.assertEqual(len(ids), len(set(ids)))
        for term in glossary["termes"]:
            self.assertEqual(set(term), {"id", "terme", "definition", "a_eviter", "voir", "famille", "origine"})
            self.assertIn(term["famille"], glossary["familles"], term["id"])
            for other in term["voir"]:
                self.assertIn(other, ids, term["id"])


class AboutTest(ContentTestCase):
    def test_credit_lines(self) -> None:
        sources = {source["id"]: source for source in self.docs["a-propos"]["sources"]}
        self.assertEqual(sources["archives-nationales"]["credit"],
                         "Archives nationales de France ; cote ; lieu de conservation ; date")
        self.assertEqual(sources["gallica"]["credit"], "Source gallica.bnf.fr / BnF")
        self.assertIn("Internet Archive", sources["internet-archive"]["credit"])
        for source in sources.values():
            self.assert_verification(source["verification"], source["id"])

    def test_limits_of_the_platform_are_stated(self) -> None:
        ids = {item["id"] for item in self.docs["a-propos"]["ce_que_le_site_ne_fait_pas"]}
        self.assertLessEqual({"pas-de-certificat", "pas-de-conseil", "pas-de-donnees-gardees"}, ids)

    def test_open_points_on_reuse_are_stated(self) -> None:
        points = {point["id"]: point for point in self.docs["a-propos"]["points_ouverts"]}
        self.assertIn("usage privé", points["usage-prive"]["texte"])
        clause = points["clause-filae"]["texte"]
        for marker in ("Filae", "1898", "1912", "1928", "Archives nationales"):
            self.assertIn(marker, clause)


class WordingTest(ContentTestCase):
    def test_quotation_marks_are_balanced(self) -> None:
        for name in FILES:
            for where, _key, text in walk(self.docs[name], name):
                rest = QUOTED.sub("", text)
                self.assertNotRegex(rest, "[«»]", f"{where}: guillemets non appariés ou imbriqués")

    def test_no_forbidden_wording_in_the_platform_voice(self) -> None:
        for name in FILES:
            for where, text in prose(self.docs[name], name):
                voice = outside_quotes(text).lower()
                for label, pattern in FORBIDDEN_OUTSIDE_QUOTES.items():
                    self.assertNotRegex(voice, pattern, f"{where}: {label}")

    def test_no_conclusion_on_nationality_of_a_descendant(self) -> None:
        for name in FILES:
            for where, text in prose(self.docs[name], name):
                voice = outside_quotes(text).lower()
                self.assertNotRegex(voice, r"\bvous êtes (?:donc )?français", where)
                self.assertNotRegex(voice, r"\bvous n['’]êtes pas français", where)
                self.assertNotRegex(voice, r"\bvous avez droit à la nationalité", where)

    def test_no_algerian_url(self) -> None:
        for name in FILES:
            raw = (CONTENU / f"{name}.json").read_text(encoding="utf-8")
            self.assertNotRegex(raw, r"\.dz\b", f"{name}.json: adresse en .dz")

    def test_only_official_contact_details(self) -> None:
        for name in FILES:
            for where, key, text in walk(self.docs[name], name):
                if key in ("gabarit", "exemple"):
                    continue
                for email in EMAIL.findall(text):
                    self.assertIn(email.lower(), ALLOWED_EMAILS, f"{where}: adresse électronique non officielle")
                for phone in PHONE.findall(URL.sub(" ", text)):
                    digits = re.sub(r"\D", "", phone)
                    self.assertIn(digits, ALLOWED_PHONES, f"{where}: numéro de téléphone non officiel")

    def test_examples_of_names_are_declared_as_invented(self) -> None:
        for name in FILES:
            for where, _key, text in walk(self.docs[name], name):
                if "Testaoui" in text or "TESTAOUI" in text or "ben Exemple" in text:
                    self.assertRegex(text, r"invent", f"{where}: exemple de nom non signalé comme inventé")


class EvidenceTest(ContentTestCase):
    def pointers(self) -> Iterator[tuple[str, str]]:
        for name in FILES:
            for where, key, text in walk(self.docs[name], name):
                if key == "preuves":
                    yield where, text

    def test_evidence_pointers_are_repository_paths(self) -> None:
        for where, pointer in self.pointers():
            self.assertRegex(pointer, r"^(data/|docs/|CONTEXT\.md$|\.scratch/)", f"{where}: {pointer}")
            self.assertNotIn("..", pointer, where)

    def test_committed_evidence_exists(self) -> None:
        for where, pointer in self.pointers():
            if not pointer.startswith(LOCAL_EVIDENCE):
                self.assertTrue(evidence_file(pointer).exists(), f"{where}: fichier absent {pointer}")

    def test_local_evidence_exists_when_the_data_directory_is_present(self) -> None:
        if not (ROOT / "data" / "samples").is_dir():
            self.skipTest("data/samples absent (répertoire ignoré par git)")
        for where, pointer in self.pointers():
            if pointer.startswith("data/"):
                self.assertTrue(evidence_file(pointer).exists(), f"{where}: fichier absent {pointer}")

    def test_private_notes_exist_when_they_are_present(self) -> None:
        # private notes are present only where they were written, never in the public repository
        present = [prefix for prefix in PRIVATE_NOTES if (ROOT / prefix).is_dir()]
        if not present:
            self.skipTest("notes privées absentes (copie publique du dépôt)")
        for where, pointer in self.pointers():
            if pointer.startswith(tuple(present)):
                self.assertTrue(evidence_file(pointer).exists(), f"{where}: fichier absent {pointer}")


class SourcesDocumentTest(ContentTestCase):
    """docs/contenu-sources.md must list everything a human still has to confirm."""

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.text = SOURCES_DOC.read_text(encoding="utf-8")

    def test_every_unverified_step_is_listed(self) -> None:
        for guide in self.guides.values():
            for step in guide["etapes"]:
                if not step["verifie"]:
                    self.assertIn(f"`{guide['id']}/{step['id']}`", self.text)

    def test_every_untested_or_blocked_link_is_listed(self) -> None:
        for link in self.links.values():
            if link["statut"] != "teste-200":
                self.assertIn(f"`{link['id']}`", self.text)

    def test_every_unverified_screen_is_listed(self) -> None:
        for screen in self.docs["guides"]["ecrans_communs"]:
            if not screen["verifie"]:
                self.assertIn(f"`{screen['id']}`", self.text)

    def test_every_file_shape_is_documented(self) -> None:
        for name in FILES:
            self.assertIn(f"{name}.json", self.text)


def normalise_for_comparison(text: str) -> str:
    """Fold typography so that a quotation can be compared with a saved page."""
    text = html.unescape(text)
    for old, new in ((" ", " "), (" ", " "), (" ", " "), ("’", "'"), ("‘", "'"), ("“", '"'),
                     ("”", '"'), ("«", '"'), ("»", '"'), ("œ", "oe"), ("Œ", "OE"), ("…", "...")):
        text = text.replace(old, new)
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r'\s*"\s*', '"', text)
    text = re.sub(r"(\d) (er|re|e)\b", r"\1\2", text)
    return text.lower().strip()


def evidence_text(path: Path) -> str | None:
    """Readable text of a saved evidence file; None when it cannot be read on this machine."""
    try:
        raw = path.read_bytes()
    except OSError:
        return None
    if raw.startswith(b"%PDF-"):
        tool = shutil.which("pdftotext")
        if tool is None:
            return None
        try:
            done = subprocess.run([tool, "-layout", str(path), "-"], capture_output=True, timeout=120, check=True)
        except (OSError, subprocess.SubprocessError):
            return None
        raw = done.stdout
    text = raw.decode("utf-8", "replace")
    if "<" in text[:20000]:
        text = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", text)
        text = re.sub(r"<[^>]+>", " ", text)
    return normalise_for_comparison(text)


class ReviewRegressionTest(ContentTestCase):
    """One test per defect found by the adversarial review of 2026-11-11."""

    QUOTATION_MIN_LENGTH = 30
    # Dossier-number examples must be visibly invented: a real « N X AA » number designates one real person.
    INVENTED_DOSSIER_NUMBERS = {"0000 X 12", "0000 X 19", "0000 X 31"}
    DOSSIER_NUMBER = re.compile(r"\b\d{1,6} ?(?:bis )?B?[Xx] ?\d{2}\b")

    def sourced_statements(self) -> Iterator[tuple[str, list[str], list[str]]]:
        """Yield (where, texts holding quotations, evidence pointers) for every sourced statement."""
        for card in self.cards.values():
            for field in ("etablit", "n_etablit_pas"):
                for index, statement in enumerate(card[field]):
                    yield (f"types/{card['id']}/{field}[{index}]", [statement["texte"], statement["source"]],
                           statement["preuves"])
        quotations = self.docs["bilan"]["citations_officielles"]
        for quotation in quotations["principales"] + quotations["autres"]:
            yield f"bilan/citations/{quotation['id']}", ["« " + quotation["texte"] + " »"], quotation["preuves"]
        for source in self.docs["a-propos"]["sources"]:
            for index, licence in enumerate(source["licence"]):
                if "« " not in licence["source"] or source["id"] != "internet-archive":
                    yield (f"a-propos/{source['id']}/licence[{index}]", ["« " + licence["texte"] + " »"],
                           licence["preuves"])

    def test_quotations_are_found_in_their_own_evidence(self) -> None:
        """A quotation attributed to a document must be readable in the evidence given for it.

        Regression: the sentence on the ascendants' birth records was attributed to the notice of the
        form although it is written on fiche F1051.
        """
        if not (ROOT / "data" / "samples").is_dir():
            self.skipTest("data/samples absent (répertoire ignoré par git)")
        cache: dict[str, str | None] = {}
        checked = 0
        for where, texts, pointers in self.sourced_statements():
            files = [p for p in pointers if p.startswith("data/")]
            if where.startswith("a-propos/internet-archive"):
                continue  # a summary of rights statements, not a quotation
            corpus = []
            for pointer in files:
                if pointer not in cache:
                    cache[pointer] = evidence_text(evidence_file(pointer))
                if cache[pointer] is None:
                    corpus = None
                    break
                corpus.append(cache[pointer])
            if not corpus:
                continue
            haystack = " ".join(corpus)
            for text in texts:
                for quotation in re.findall(r"«\s*([^«»]*?)\s*»", text):
                    for fragment in re.split(r"\s*\[…\]\s*|\s*…\s*", quotation):
                        fragment = fragment.strip(" .,;:")
                        if len(fragment) < self.QUOTATION_MIN_LENGTH:
                            continue
                        checked += 1
                        self.assertIn(normalise_for_comparison(fragment), haystack,
                                      f"{where}: citation absente de ses preuves : « {fragment} »")
        self.assertGreater(checked, 20, "trop peu de citations contrôlées : le test ne voit plus les énoncés")

    def test_the_ascendants_sentence_is_attributed_to_fiche_f1051(self) -> None:
        for name in FILES:
            for where, _key, text in walk(self.docs[name], name):
                if "1er ascendant français inclus" in text:
                    self.assertIn("F1051", text, f"{where}: phrase de la fiche F1051 attribuée à une autre source")
                    self.assertNotIn("52373", text, where)

    def test_dossier_number_examples_are_invented(self) -> None:
        """Regression: two real dossier numbers (each designating one real person) were used as examples."""
        for name in FILES:
            for where, key, text in walk(self.docs[name], name):
                if key in ("gabarit", "exemple", "preuves"):
                    continue
                for number in self.DOSSIER_NUMBER.findall(text):
                    self.assertIn(number, self.INVENTED_DOSSIER_NUMBERS,
                                  f"{where}: numéro de dossier « {number} » non déclaré comme inventé")
                    self.assertIn("invent", text, f"{where}: numéro de dossier donné sans dire qu'il est inventé")

    def test_the_six_thousand_figure_is_attributed(self) -> None:
        """Regression: an historian's count (which excludes some years) was stated as a bare fact."""
        for name in FILES:
            for where, key, text in walk(self.docs[name], name):
                if key != "valeur" and re.search(r"un peu plus de 6[\s  ]?000", text):
                    self.assertIn("Weil", text, f"{where}: chiffre donné sans son auteur")

    def test_verified_steps_do_not_rest_on_a_link_nobody_saw(self) -> None:
        """Regression: step c5 was marked verified while its only link had never been opened."""
        for guide in self.guides.values():
            for step in guide["etapes"]:
                if not step["verifie"]:
                    continue
                for link_id in step["liens"]:
                    link = self.links[link_id]
                    unseen = link["statut"] == "non-teste" and link["origine"] != "recopie-d-une-page-officielle"
                    self.assertFalse(unseen, f"guides/{guide['id']}/{step['id']}: étape « vérifiée » fondée sur le "
                                             f"lien jamais vu « {link_id} »")

    def test_seen_screen_steps_cite_a_saved_page_or_image(self) -> None:
        """Regression: step c4 claimed « ecran-vu » with report sections as its only evidence."""
        for guide in self.guides.values():
            for step in guide["etapes"]:
                if step["appui"] == "ecran-vu":
                    self.assertTrue(any(pointer.startswith("data/") for pointer in step["preuves"]),
                                    f"guides/{guide['id']}/{step['id']}: « ecran-vu » sans page ni image enregistrée")

    def test_the_bulletin_on_gallica_is_never_promised_without_the_1907_gap(self) -> None:
        """Regression: « de 1889 à 1926, il est sur Gallica » omitted the year the catalogue reports missing."""
        pattern = re.compile(r"(?:1889 à 1926|1889-1926)[^.]*Gallica|Bulletin officiel de ces années est sur Gallica")
        for name in ("aiguillage", "guides", "bilan"):
            for where, text in prose(self.docs[name], name):
                for sentence in re.split(r"(?<=[.;])\s+", text):
                    if pattern.search(sentence):
                        self.assertIn("1907", sentence, f"{where}: lacune de 1907 non signalée")

    def test_the_credit_rule_quotes_the_official_wording_of_the_date(self) -> None:
        """Regression: « la date des informations » was silently read as the date of the decree."""
        sources = {source["id"]: source for source in self.docs["a-propos"]["sources"]}
        rule = sources["archives-nationales"]["credit_regle"]
        self.assertIn("« la date des informations »", rule)
        self.assertIn("inventaire", sources["archives-nationales"]["credit_exemple"])

    def test_bulletin_layout_claims_name_the_years_actually_read(self) -> None:
        """Regression: layouts seen in one or two volumes were written as rules for every year."""
        step = {s["id"]: s for s in self.guides["bogga-internet-archive"]["etapes"]}["c5"]
        self.assertNotIn("chaque volume annuel", step["instruction"])
        self.assertFalse(step["verifie"])
        caveats = {point["id"]: point for point in self.docs["bilan"]["mises_en_garde"]["points"]}
        self.assertIn("1873", caveats["sans-nom-de-famille"]["texte"])
        granularity = {s["id"]: s for s in self.guides["gallica-a-la-main"]["etapes"]}["d3"]["instruction"]
        self.assertIn("deux seules notices", granularity)

    def test_document_numbers_are_not_promised_for_the_years_that_have_none(self) -> None:
        """Regression: users were told to compare a « numéro de document » that 1892-1897 and 1931-1948 lack."""
        glossary = {term["id"]: term for term in self.docs["vocabulaire"]["termes"]}
        definition = next(term["definition"] for term in glossary.values() if term["terme"] == "Numéro de document")
        for marker in ("1892 à 1897", "1931"):
            self.assertIn(marker, definition)
        steps = {step["id"]: step for step in self.guides["an-annee-en-images"]["etapes"]}
        self.assertIn("1933 à 1948", steps["b1"]["ce_que_l_ecran_montre"])
        same_date = next(o for o in steps["b4"]["issues_possibles"] if "même date" in o["si"])
        self.assertIn("lisez-les tous les deux", same_date["faire"])

    def test_no_unsourced_legal_effect_in_the_glossary(self) -> None:
        """Regression: « Sans effet sur le passé » was asserted for réintégration, a card marked non-verifie."""
        for term in self.docs["vocabulaire"]["termes"]:
            self.assertNotIn("Sans effet sur le passé", term["definition"], term["id"])

    def test_no_list_of_years_read_is_written_by_hand(self) -> None:
        """Regression: « 1869 à 1873 (les seules … que nous ayons lues) », « 1873 et 1888, les deux que nous
        avons lus », « pour 1900, 1905 et 1909 » contradicted the coverage computed from the data."""
        stale = re.compile(r"seules de cette période que nous ayons lues|les deux que nous avons lus|pour 1900, 1905 et 1909|De janvier à mars, les noms")
        for name in ("aiguillage", "guides", "bilan"):
            for where, text in prose(self.docs[name], name):
                self.assertNotRegex(text, stale, where)
        epoque = {e["id"]: e for e in self.docs["aiguillage"]["epoques"]}["e-1865-1882"]
        self.assertEqual(epoque["voie"], "recherche-par-nom", "the name search reads the Bulletin of 1865-1882")

    def test_a_request_alone_never_promises_an_act(self) -> None:
        """Regression: « Si l'ancêtre a fait cette demande … un acte existe » ignored rejected requests."""
        message = self.outcomes_by_id()["service-militaire-seul"]["message"]
        self.assertIn("acceptée", message)
        self.assertNotIn("ou une demande par décret, un acte existe", message)

    def test_the_cremieux_exception_is_routed_to_the_name_search(self) -> None:
        outcome = self.outcomes_by_id()["famille-juive-du-nord"]
        self.assertIn("recherche-par-nom", outcome["voies_secondaires"])

    def test_no_internal_field_pointer_in_a_status_sentence(self) -> None:
        """Regression: « Voir « observation » et « origine ». » reached the public under unverified links."""
        for status, sentence in self.docs["liens"]["statuts"].items():
            self.assertNotIn("observation", sentence, status)

    def outcomes_by_id(self) -> dict[str, Any]:
        return {outcome["id"]: outcome for outcome in self.docs["aiguillage"]["issues"]}

    def test_decree_size_is_not_called_an_average(self) -> None:
        """Regression: the median (12 persons) was announced as the mean (18)."""
        self.assertNotIn("douzaine de personnes en moyenne", self.guides["an-annee-en-images"]["duree"])


if __name__ == "__main__":
    unittest.main()
