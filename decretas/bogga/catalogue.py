"""The volumes of the Bulletin officiel du Gouvernement général de l'Algérie (BOGGA)
that a program can read on the Internet Archive, and the ONE table of link templates.

Identifiers and file prefixes are copied from the Internet Archive records (research
report docs/research/sources-2026-11/internet-archive.md, checked by verification.md):
they are never rebuilt from a year. The harvest re-checks each of them against the
item's own `/metadata` file list before requesting anything.
"""
from __future__ import annotations

import urllib.parse
from dataclasses import dataclass

FIRST_YEAR = 1861
LAST_YEAR = 1888

TESSERACT = "tesseract"
HARVARD = "harvard"

# --- the single table of URL templates (verified forms, see the report § 6.2) -------------
METADATA_URL = "https://archive.org/metadata/{item}"
FILE_URL = "https://{server}{dir}/{file}"
PAGE_URL_SINGLE = "https://archive.org/details/{item}/page/n{leaf}/mode/1up"
PAGE_URL_MULTI = "https://archive.org/details/{item}/{doc}/page/n{leaf}/mode/1up"
IMAGE_URL_SINGLE = "https://archive.org/download/{item}/page/n{leaf}_w{largeur}.jpg"
IMAGE_URL_MULTI = "https://archive.org/download/{item}/{doc}/page/n{leaf}_w{largeur}.jpg"
ITEM_URL = "https://archive.org/details/{item}"
READER_TABLE_URL = ("https://{server}/BookReader/BookReaderJSIA.php?id={item}&itemPath={dir}"
                    "&server={server}&format=jsonp&subPrefix={doc}")

FILE_SUFFIXES = ("_hocr_searchtext.txt.gz", "_hocr_pageindex.json.gz", "_page_numbers.json")

RIGHTS_TESSERACT_MULTI = (
    "Texte officiel publié de 1861 à 1888 (domaine public par l'âge). Numérisation versée sur "
    "Internet Archive sans mention de licence ; texte lu par machine (Tesseract) par Internet Archive."
)
RIGHTS_1873 = (
    "Texte officiel de 1873 (domaine public). Numérisation versée sur Internet Archive sous la "
    "« Public Domain Mark 1.0 » ; texte lu par machine (Tesseract) par Internet Archive."
)
RIGHTS_HARVARD = (
    "Texte officiel (domaine public ; Internet Archive indique « NOT_IN_COPYRIGHT »). Exemplaire de "
    "la bibliothèque de l'université Harvard numérisé par Google : usage non commercial demandé par "
    "Google, mention de la provenance à conserver."
)


@dataclass(frozen=True)
class Volume:
    """One yearly volume readable on the Internet Archive.

    `doc` is the exact file prefix inside the item (None: the item holds one document and
    the prefix is read from its metadata). `multi` tells which link form applies.
    """

    year: int
    item: str
    doc: str | None
    family: str
    multi: bool
    library: str | None
    rights: str

    @property
    def key(self) -> str:
        return f"{self.year}"


_MULTI_ITEM = "1922-t.-62"
_MULTI_DOCS: tuple[tuple[int, str], ...] = (
    (1861, "1861 T.1"), (1863, "1863 T.3"), (1865, "1865 T.5"), (1866, "1866 T.6"),
    (1867, "1867 T.7"), (1868, "1868 T.8_2"), (1869, "1869 T.9"), (1870, "1870 T.10"),
    (1871, "1871 T.11_2"), (1874, "1874 T.14"), (1875, "1875 T.15"), (1877, "1877 T.17"),
    (1878, "1878 T.18"), (1879, "1879 T.19"), (1880, "1880 T.20"), (1881, "1881 T.21_21"),
    (1882, "1882 T.22_22"), (1883, "1883 T.23"), (1884, "1884 T.24"), (1885, "1885 T.25"),
    (1886, "1886 T.26"), (1888, "1888 T.28"),
)

VOLUMES: tuple[Volume, ...] = tuple(sorted(
    [Volume(year, _MULTI_ITEM, doc, TESSERACT, True, None, RIGHTS_TESSERACT_MULTI) for year, doc in _MULTI_DOCS]
    + [
        Volume(1873, "algeria_bulletinofficieldugouvernementgeneraldelalgerie_13_1873", None,
               TESSERACT, False, None, RIGHTS_1873),
        Volume(1864, "bulletinofficie12algegoog", "bulletinofficie12algegoog", HARVARD, False,
               "Harvard University (numérisation Google)", RIGHTS_HARVARD),
        Volume(1872, "bulletinofficie14algegoog", "bulletinofficie14algegoog", HARVARD, False,
               "Harvard University (numérisation Google)", RIGHTS_HARVARD),
        Volume(1876, "bulletinofficie08algegoog", "bulletinofficie08algegoog", HARVARD, False,
               "Harvard University (numérisation Google)", RIGHTS_HARVARD),
    ],
    key=lambda volume: volume.year,
))

# Years of the period with no machine-readable copy on the Internet Archive, and what a
# person can do instead. HathiTrust identifiers come from its bibliographic API (record
# 100349311); its reader refuses programs, and full view from France was not observed.
MISSING_YEARS: dict[int, dict[str, str]] = {
    1862: {
        "etat": "absent d'Internet Archive",
        "que_faire": (
            "Aucun exemplaire lisible par programme. Année antérieure au sénatus-consulte du 14 juillet "
            "1865 : elle ne peut contenir aucun décret d'admission. Pour la consulter : HathiTrust, "
            "exemplaire Harvard (identifiant hvd.32044075298414), dans un navigateur."
        ),
        "lien": "https://babel.hathitrust.org/cgi/pt?id=hvd.32044075298414",
        "lien_verifie": "non",
    },
    1887: {
        "etat": "absent d'Internet Archive",
        "que_faire": (
            "Aucun exemplaire lisible par programme n'a été trouvé. Les décrets d'admission publiés en "
            "1887 sont à chercher à la main dans le volume de 1887 du Bulletin officiel (bibliothèque "
            "numérique Gallica de la BnF, ou bibliothèque). Les décrets de la fin de 1887 publiés au "
            "début de 1888 sont, eux, dans le volume de 1888, qui est couvert."
        ),
        "lien": "",
        "lien_verifie": "non",
    },
}


# Deep links checked on the page image itself by the research of 2026-11-11 (report § 6.3,
# confirmed by its verification): the image served for the leaf shows the expected printed
# page. Used for `lien_verifie` when no reader-table check exists for the volume.
IMAGE_CHECKS: dict[tuple[str, int], str] = {
    ("algeria_bulletinofficieldugouvernementgeneraldelalgerie_13_1873", 1873):
        "oui : image de la feuille 530 comparée à la page imprimée 495 (contrôle du 2026-11-11)",
    (_MULTI_ITEM, 1888):
        "oui : image de la feuille 116 comparée à la page imprimée 61 (contrôle du 2026-11-11)",
}


def image_check(volume: Volume) -> str | None:
    """Result sentence of the image check of this very item and year, if one was made."""
    return IMAGE_CHECKS.get((volume.item, volume.year))


def volume_for(year: int) -> Volume | None:
    return next((volume for volume in VOLUMES if volume.year == year), None)


def encode_doc(doc: str) -> str:
    """URL-encode a document prefix the way the verified links do: '1888 T.28' -> '1888%20T.28'."""
    return urllib.parse.quote(doc, safe="")


def page_link_template(volume: Volume, doc: str) -> str:
    """Deep link to a leaf of this volume, with '{leaf}' left to fill."""
    if volume.multi:
        return PAGE_URL_MULTI.format(item=volume.item, doc=encode_doc(doc), leaf="{leaf}")
    return PAGE_URL_SINGLE.format(item=volume.item, leaf="{leaf}")


def image_link_template(volume: Volume, doc: str) -> str:
    """Address of a leaf image, with '{leaf}' and '{largeur}' (requested width) left to fill."""
    if volume.multi:
        return IMAGE_URL_MULTI.format(item=volume.item, doc=encode_doc(doc), leaf="{leaf}", largeur="{largeur}")
    return IMAGE_URL_SINGLE.format(item=volume.item, leaf="{leaf}", largeur="{largeur}")


def page_link(volume: Volume, doc: str, leaf: int) -> str:
    return page_link_template(volume, doc).replace("{leaf}", str(leaf))
