"""The ordered probe plan to run when the reading-room site answers again.

It is the 30-request list of the research report of 2026-11-11 (kept local, § 9), amended as
its verification asked: it starts with the four links of the XML exports that carry a media
identifier (``DAFANCH94_NUMJ<n>_D``), then asks ``/siv/UD/`` and ``/siv/media/`` for one
exemplar of each case, then the rest of the site questions.

Two tiers (``palier``):

1. what decides the strategy for image-only decrees: redirect chains, landing pages, media
   names and order, "does a person's own link open the exact page?", sizes, and the look of a
   page of 1899-1912, of 1928, of 1933-1948 and of an admission decree of 1946;
2. complements: the notice pages of the other exemplars, the viewer script, the two tabs,
   search by GET, help sheets, terms of use, freshness of two exports, the OAI question.

Decree exemplars are public documents and are named here by inventory and notice
identifier. Person exemplars are NOT written in this file: they are resolved at run time
from the locally generated site data (git-ignored), as "the first person of this decree".
Every address is the form the Archives nationales write in their own XML exports
(``xlink:href`` and ``daoloc/@href``), with ``https`` instead of ``http`` (the 301 from one
to the other was observed on 2026-11-11).
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

BASE = "https://www.siv.archives-nationales.culture.gouv.fr"
ALLOWED_HOST = "www.siv.archives-nationales.culture.gouv.fr"

CASES = {
    "lots": "Les quatre liens du XML qui portent un identifiant de média (DAFANCH94_NUMJ…_D)",
    "personne-avec-images": "Personne ayant son propre lien d'images (décret du 11 janvier 1913)",
    "personne-sans-images": "Personne sans lien d'images (décret du 11 janvier 1897)",
    "image-1899-1912": "Décret en images seules de 1899-1912 (5 février 1905, BB/34/424, document 21)",
    "image-1928": "Décret en images seules d'avril-décembre 1928 (1er mai 1928, BB/34/463, document 50)",
    "image-1933-1948": "Décret en images seules de 1933-1948 (2 janvier 1935, BB/34/487)",
    "admission-1946-1947": "Décret d'admission aux droits de citoyen français de 1946-1947 (17 juillet 1946, BB/34/510)",
    "site": "Questions générales sur le site (onglets, recherche, aide, conditions, exports, OAI)",
}

# (inventory, decree notice) of the two decrees whose first person serves as exemplar.
DECREE_WITH_PERSON_LINKS = ("FRAN_IR_057268", "AP002722")
DECREE_WITHOUT_PERSON_LINKS = ("FRAN_IR_056878", "idd_1897_01-01")

# A neutral search word for the two "search by GET" probes: a place, never a person's name.
SEARCH_WORD = "Constantine"


@dataclass(frozen=True)
class Step:
    """One starting request of the plan. Redirect hops and follow-ups are added at run time."""

    id: str
    case: str
    path: str                 # path and query on the site, starting with "/"
    kind: str                 # "images" | "notice" | "page" | "script" | "export" | "sonde"
    question: str             # what the answer must tell (French, printed in the plan and the report)
    tier: int = 1
    images: int = 0           # page images that may be downloaded from what this step reveals
    decree: tuple[str, str] | None = None

    def url(self, base: str = BASE) -> str:
        return base.rstrip("/") + self.path


@dataclass(frozen=True)
class Plan:
    steps: tuple[Step, ...]
    missing: tuple[str, ...] = ()       # French sentences: what could not be planned, and why

    def select(self, cases: set[str] | None = None, tier: int | None = None) -> tuple[Step, ...]:
        return tuple(step for step in self.steps
                     if (cases is None or step.case in cases) and (tier is None or step.tier <= tier))


def first_person_of(site_data: Path, decree: tuple[str, str], with_images: bool) -> str | None:
    """Notice identifier of the first principal person of a decree in the generated site data,
    having (or not having) their own image link. None when the data cannot answer."""
    try:
        decrees = json.loads((site_data / "an-decrets.json").read_text(encoding="utf-8"))
        persons = json.loads((site_data / "an-personnes.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    try:
        d_fields = {name: rank for rank, name in enumerate(decrees["champs"])}
        p_fields = {name: rank for rank, name in enumerate(persons["champs"])}
        inventories = decrees["tables"]["inv"]
        roles = persons["tables"]["role"]
        decree_id = next((row[d_fields["id"]] for row in decrees["lignes"]
                          if inventories[row[d_fields["inv"]]] == decree[0] and row[d_fields["notice"]] == decree[1]), None)
        if decree_id is None:
            return None
        for row in persons["lignes"]:
            if (row[p_fields["dec"]] == decree_id and roles[row[p_fields["role"]]] == "principal"
                    and bool(row[p_fields["img"]]) == with_images and row[p_fields["notice"]]):
                return str(row[p_fields["notice"]])
    except (KeyError, IndexError, TypeError):
        return None
    return None


def _media(inventory: str, notice: str, lot: str | None = None) -> str:
    return f"/siv/media/{inventory}/{notice}/" + (lot or "")


def _notice(inventory: str, notice: str) -> str:
    return f"/siv/UD/{inventory}/{notice}"


def build_plan(person_with_images: str | None, person_without_images: str | None) -> Plan:
    """The full ordered plan. Steps about a person are left out (and reported in `missing`)
    when the corresponding identifier is None."""
    steps: list[Step] = []
    missing: list[str] = []
    lots = (("FRAN_IR_056731", "idd_1889_12_22", "DAFANCH94_NUMJ011088_D", "décembre 1889"),
            ("FRAN_IR_056871", "idd_1891_01_20", "DAFANCH94_NUMJ014520_D", "janvier 1891"),
            ("FRAN_IR_056877", "idd_1896_05-25", "DAFANCH94_NUMJ023847_D", "mai 1896"),
            ("FRAN_IR_057667", "idd_1927_03_08", "DAFANCH94_NUMJ064396_D", "mars 1927"))
    for rank, (inventory, notice, lot, when) in enumerate(lots, start=1):
        steps.append(Step(
            id=f"L{rank}", case="lots", path=_media(inventory, notice, lot), kind="images",
            question=(f"Lien d'images avec identifiant de média ({when}) : code, redirection, page d'arrivée ; que désigne "
                      "« _D » (un lot de vues ou un fichier) ; noms et ordre des médias du décret."),
            images=1 if rank in (1, 4) else 0, decree=(inventory, notice)))

    inventory, decree = DECREE_WITH_PERSON_LINKS
    if person_with_images:
        steps.append(Step("P1", "personne-avec-images", _notice(inventory, person_with_images), "notice",
                          "Notice d'une personne : redirection, structure de la page, la personne est-elle montrée dans son décret ?"))
        steps.append(Step("P2", "personne-avec-images", _media(inventory, person_with_images), "images",
                          "QUESTION CENTRALE : le lien d'images d'une personne ouvre-t-il la page exacte où elle figure, "
                          "ou tout le décret ?", images=1, decree=(inventory, decree)))
    else:
        missing.append("Cas « personne avec images » : identifiant de la personne introuvable dans site/data "
                       "(lancer d'abord `python3 -m decretas.an construire`) ; étapes P1 et P2 non planifiées.")
    steps.append(Step("P3", "personne-avec-images", _media(inventory, decree), "images",
                      "Lien d'images du décret de cette personne : liste complète des vues, à comparer à celle de P2.",
                      images=1, decree=(inventory, decree)))

    inventory, decree = DECREE_WITHOUT_PERSON_LINKS
    if person_without_images:
        steps.append(Step("S1", "personne-sans-images", _notice(inventory, person_without_images), "notice",
                          "Notice d'une personne sans lien d'images : la page propose-t-elle les images du décret parent ?"))
    else:
        missing.append("Cas « personne sans images » : identifiant de la personne introuvable dans site/data ; "
                       "étape S1 non planifiée.")

    steps.append(Step("B1", "image-1899-1912", _notice("FRAN_IR_057220", "AP001236"), "notice",
                      "Notice d'un décret sans noms saisis : titre, cote, numéro de document, bloc d'images."))
    steps.append(Step("B2", "image-1899-1912", _media("FRAN_IR_057220", "AP001236"), "images",
                      "Nombre de vues ; MANUSCRIT OU DACTYLOGRAPHIÉ ? forme d'une ligne de personne ; place du numéro de dossier.",
                      images=2, decree=("FRAN_IR_057220", "AP001236")))
    steps.append(Step("E1", "image-1928", _media("FRAN_IR_057672", "YI004589"), "images",
                      "Décret de 1928 : nombre de vues, noms des fichiers (même numérotation que les autres liasses ?), aspect.",
                      images=2, decree=("FRAN_IR_057672", "YI004589")))
    steps.append(Step("C1", "image-1933-1948", _media("FRAN_IR_058672", "D4"), "images",
                      "Décret de 1935 (numérisation récente, sans numéro de document) : vues, noms, taille, lisibilité.",
                      images=2, decree=("FRAN_IR_058672", "D4")))
    steps.append(Step("F1", "admission-1946-1947", _media("FRAN_IR_058664", "D32"), "images",
                      "Décret d'admission de 1946 : phrase de fondement, forme des noms (« X ben Y » ?), numéro de dossier.",
                      images=2, decree=("FRAN_IR_058664", "D32")))

    # ---- tier 2: complements
    consultation = "/siv/rechercheconsultation/consultation/ir/consultationIR.action"
    global_search = "/siv/rechercheconsultation/recherche/ir/rechercheConsultationGlobal.action"
    help_guide = "/siv/cms/content/helpGuide.action"
    second = [
        Step("A1", "personne-avec-images", _notice(*DECREE_WITH_PERSON_LINKS), "notice",
             "Notice d'un décret dont les noms sont saisis : liste des personnes, ordre, bloc d'images."),
        Step("S2", "personne-sans-images", _media(*DECREE_WITHOUT_PERSON_LINKS), "images",
             "Lien d'images du décret parent de la personne sans images : même forme que les autres ?",
             decree=DECREE_WITHOUT_PERSON_LINKS),
        Step("E2", "image-1928", _notice("FRAN_IR_057672", "YI004589"), "notice", "Notice du décret de 1928."),
        Step("C2", "image-1933-1948", _notice("FRAN_IR_058672", "D4"), "notice",
             "Notice sans numéro de document : comment la page distingue les décrets de même date."),
        Step("F2", "admission-1946-1947", _notice("FRAN_IR_058664", "D32"), "notice", "Notice du décret d'admission de 1946."),
        Step("J1", "site", "/siv/resources/js/consultation.js", "script",
             "Script de la page : noms des actions de la visionneuse, construction des adresses d'images."),
        Step("T1", "site", consultation + "?irId=FRAN_IR_057220&details=true&gotoArchivesNums=false&udId=root&auSeinIR=true",
             "page", "Onglet « Détail du contenu » d'un inventaire (1905)."),
        Step("T2", "site", global_search + "?irId=FRAN_IR_058672&details=false&gotoArchivesNums=true&searchUdOnly=true",
             "page", "Onglet « Archives numérisées » d'un inventaire (1935)."),
        Step("G1", "site", consultation + f"?irId=FRAN_IR_057268&fullText={SEARCH_WORD}&optionFullText=ET&auSeinIR=true&details=true",
             "page", "Une recherche par GET sans jeton est-elle acceptée (paramètres fullText / optionFullText) ?"),
        Step("G2", "site", global_search + f"?irId=FRAN_IR_057268&details=true&rechercheconsultation.fulltext={SEARCH_WORD}"
             "&rechercheconsultation.optionfulltext=ET", "page", "Même question avec l'autre action de recherche."),
        Step("H1", "site", help_guide + "?uuid=8dc87e75-c0f2-4b5b-be8e-a6999f19bb6a&version=1&preview=false&typeSearch=&searchString=",
             "page", "Fiche d'aide « cas particuliers liés à l'Algérie » : à citer mot pour mot."),
        Step("H2", "site", help_guide + "?uuid=804c95a9-6550-4b00-b97b-78b0d52816cd", "page",
             "Fiche « Vous recherchez un dossier de demande de naturalisation ? » : méthode officielle du décret au dossier."),
        Step("H3", "site", help_guide + "?uuid=cb55f7f0-03d1-430c-86e8-3418c003c30e&version=4&preview=false&typeSearch=&searchString=",
             "page", "Fiche experte « Les dossiers de demande de naturalisation »."),
        Step("U1", "site", "/siv/conditions-generales-d-utilisation", "page",
             "Conditions d'utilisation : ce qu'elles disent de l'usage automatisé et de la réutilisation."),
        Step("X1", "site", "/siv/rechercheconsultation/consultation/ir/exportXML.action?irId=FRAN_IR_058670", "export",
             "Export XML de 1933 : taille et empreinte à comparer à la copie du 2026-10-16 (des noms sont-ils arrivés ?)."),
        Step("X2", "site", "/siv/rechercheconsultation/consultation/ir/exportXML.action?irId=FRAN_IR_057397", "export",
             "Export XML de l'inventaire racine : de nouvelles années indexées sont-elles annoncées ?"),
        Step("O1", "site", "/oai/OAIHandler?verb=Identify", "sonde",
             "Existence d'un entrepôt OAI-PMH. Adresse hypothétique : un 404 clôt la question."),
    ]
    steps.extend(Step(step.id, step.case, step.path, step.kind, step.question, 2, step.images, step.decree) for step in second)
    return Plan(tuple(steps), tuple(missing))


def plan_from_site_data(site_data: Path) -> Plan:
    """The plan with its two person exemplars resolved from the generated site data."""
    return build_plan(first_person_of(site_data, DECREE_WITH_PERSON_LINKS, True),
                      first_person_of(site_data, DECREE_WITHOUT_PERSON_LINKS, False))
