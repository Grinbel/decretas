"""Links towards the site of the Archives nationales: identifiers only, never an address.

The project has ONE table of external link templates: ``site/contenu/liens.json``. This module
does not repeat it. It says which entry of that table serves each kind of link, and which field
of the data files fills each placeholder of the entry (``an-meta.json`` -> ``liens``).

Links are never invented. The notice link and the image link of every notice are copied from
the XML into the database; the site data carry identifiers only. At export time every copied
link is compared with the form the XML exports normally write (``forme_xml`` below, used for
that comparison and for nothing else): a link that does not follow it is published as written,
as an explicit exception (``liens_particuliers``).

The XML writes ``http://``; the templates of ``site/contenu/liens.json`` say ``https://`` (the
site of the Archives nationales redirects). ``check_content_table`` verifies that this is the
ONLY difference, and that the entries and their placeholders exist: ``verifier`` runs it.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

LINK_INVENTORY = "inventaire"
LINK_NOTICE = "notice"
LINK_IMAGES = "images"

CONTENT_TABLE_PATH = Path(__file__).resolve().parents[2] / "site" / "contenu" / "liens.json"
CONTENT_TABLE_NAME = "contenu/liens.json"      # as seen from the root of the site

_HOST = "www.siv.archives-nationales.culture.gouv.fr"


@dataclass(frozen=True, slots=True)
class LinkReference:
    nom: str
    id: str                                   # id of the entry of site/contenu/liens.json
    variables: tuple[tuple[str, str], ...]    # (placeholder of that entry, field of the data files)
    forme_xml: str                            # the form written in the XML exports ({inv}, {notice})

    def build_xml_form(self, inventory: str, notice: str = "") -> str:
        """The address the XML exports normally write for this notice -- to compare, never to publish."""
        return self.forme_xml.format(inv=inventory, notice=notice)

    def published(self) -> dict[str, object]:
        return {"nom": self.nom, "id": self.id, "variables": dict(self.variables)}


TEMPLATES: dict[str, LinkReference] = {
    LINK_INVENTORY: LinkReference(
        nom=LINK_INVENTORY, id="an-inventaire", variables=(("inventaire", "inv"),),
        forme_xml=f"http://{_HOST}/siv/IR/{{inv}}"),
    LINK_NOTICE: LinkReference(
        nom=LINK_NOTICE, id="an-notice", variables=(("inventaire", "inv"), ("notice", "notice")),
        forme_xml=f"http://{_HOST}/siv/UD/{{inv}}/{{notice}}"),
    LINK_IMAGES: LinkReference(
        nom=LINK_IMAGES, id="an-images-notice", variables=(("inventaire", "inv"), ("notice", "notice")),
        forme_xml=f"http://{_HOST}/siv/media/{{inv}}/{{notice}}/"),
}

# Credit line required by the Archives nationales for any reuse
# ("Archives nationales de France ; cote ; lieu de conservation ; date des informations").
CREDIT_TEMPLATE = "Archives nationales de France ; {cote} ; {lieu} ; {date}"
LICENCE_NOTE = ("Réutilisation libre et gratuite des informations publiques des Archives nationales (décision "
                "2017-11), sous réserve de mentionner l'origine : Archives nationales de France ; cote ; lieu de "
                "conservation ; date des informations. Les inventaires sont « librement réutilisables (hors "
                "introduction) » ; les données personnelles restent soumises au RGPD. Deux mentions des "
                "inventaires eux-mêmes restent à faire préciser par les Archives nationales : la reproduction "
                "« dans le cadre d’un usage privé » et, pour les années indexées par Filae, l'autorisation "
                "préalable de cette société.")


def template_table() -> list[dict[str, object]]:
    """What ``an-meta.json`` publishes: for each kind of link, the id of the entry and its placeholders."""
    return [reference.published() for reference in TEMPLATES.values()]


def check_content_table(path: Path = CONTENT_TABLE_PATH) -> list[str]:
    """Problems (in French) between this module and the link table of the site; [] when they agree.

    For each kind of link: the entry exists, it declares exactly the placeholders mapped here, and
    its template is the form of the XML exports with ``https://`` in place of ``http://``.
    """
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
        entries = {entry["id"]: entry for entry in document["liens"]}
    except FileNotFoundError:
        return [f"table des liens absente : {path}"]
    except (OSError, ValueError, KeyError, TypeError) as error:
        return [f"table des liens illisible : {path} ({error.__class__.__name__})"]
    problems: list[str] = []
    for reference in TEMPLATES.values():
        entry = entries.get(reference.id)
        if not isinstance(entry, dict):
            problems.append(f"lien « {reference.nom} » : l'entrée {reference.id} est absente de {path.name}")
            continue
        placeholders = dict(reference.variables)
        if sorted(entry.get("variables") or []) != sorted(placeholders):
            problems.append(f"lien « {reference.nom} » : l'entrée {reference.id} attend les variables "
                            f"{sorted(entry.get('variables') or [])}, le module fournit {sorted(placeholders)}")
            continue
        template = str(entry.get("gabarit", ""))
        for placeholder, data_field in placeholders.items():
            template = template.replace("{" + placeholder + "}", "{" + data_field + "}")
        if template.replace("https://", "http://", 1) != reference.forme_xml:
            problems.append(f"lien « {reference.nom} » : le gabarit de l'entrée {reference.id} n'est plus la forme "
                            "écrite dans les exports XML (au schéma http/https près)")
    return problems
