"""Builders of synthetic material for the tests of decretas.an_images.

Everything here is invented: the images are a few grey pixels wrapped in real container
structures carrying known metadata; the HTML pages imitate *plausible* shapes of a viewer
(nothing is known yet about the real one); the names in the transcriptions are fictitious
(Testaoui, Fictivo, Exemplmann…). No real person, no real archive image.
"""
from __future__ import annotations

import struct
import zlib

# ----------------------------------------------------------------------------- TIFF / EXIF


def tiff_bytes(ifd0: list[tuple[int, int, object]], exif: list[tuple[int, int, object]] | None = None,
               order: str = "<") -> bytes:
    """A classic TIFF structure with one directory (and an optional Exif sub-directory).

    Entries are (tag, type, value); supported types: 2 ASCII, 3 SHORT, 4 LONG, 5 RATIONAL
    (value = (numerator, denominator)), 1 BYTE and 7 UNDEFINED (value = bytes).
    """
    def encode(kind: int, value) -> tuple[int, bytes]:
        if kind == 2:
            raw = value.encode("utf-8") + b"\x00"
            return len(raw), raw
        if kind == 3:
            values = value if isinstance(value, (list, tuple)) else [value]
            return len(values), struct.pack(order + "H" * len(values), *values)
        if kind == 4:
            return 1, struct.pack(order + "I", value)
        if kind == 5:
            return 1, struct.pack(order + "II", *value)
        return len(value), bytes(value)

    def directory(entries: list[tuple[int, int, object]], start: int, patch: dict[int, int]) -> bytes:
        entries = sorted(entries)
        table_size = 2 + 12 * len(entries) + 4
        extra = b""
        table = struct.pack(order + "H", len(entries))
        for tag, kind, value in entries:
            if tag in patch:
                value = patch[tag]
            count, raw = encode(kind, value)
            if len(raw) <= 4:
                slot = raw.ljust(4, b"\x00")
            else:
                slot = struct.pack(order + "I", start + table_size + len(extra))
                extra += raw + (b"\x00" if len(raw) % 2 else b"")
            table += struct.pack(order + "HHI", tag, kind, count) + slot
        return table + struct.pack(order + "I", 0) + extra

    header = (b"II*\x00" if order == "<" else b"MM\x00*") + struct.pack(order + "I", 8)
    entries = list(ifd0)
    if exif is None:
        return header + directory(entries, 8, {})
    entries.append((34665, 4, 0))
    first = directory(entries, 8, {})
    exif_offset = 8 + len(first)
    first = directory(entries, 8, {34665: exif_offset})
    return header + first + directory(exif, exif_offset, {})


# ----------------------------------------------------------------------------- JPEG

def _segment(marker: int, body: bytes) -> bytes:
    return b"\xff" + bytes([marker]) + struct.pack(">H", len(body) + 2) + body


def iptc_bytes(datasets: list[tuple[int, int, bytes]]) -> bytes:
    return b"".join(b"\x1c" + bytes([record, dataset]) + struct.pack(">H", len(value)) + value
                    for record, dataset, value in datasets)


def photoshop_bytes(iptc: bytes) -> bytes:
    """An APP13 payload: one 8BIM resource 0x0404 holding IPTC datasets."""
    body = iptc + (b"\x00" if len(iptc) % 2 else b"")
    return b"Photoshop 3.0\x00" + b"8BIM" + struct.pack(">H", 0x0404) + b"\x00\x00" + struct.pack(">I", len(iptc)) + body


def xmp_packet(fields: dict[str, str], title: str | None = None) -> bytes:
    attributes = " ".join(f'{name}="{value}"' for name, value in fields.items())
    inner = f"<dc:title><rdf:Alt><rdf:li xml:lang=\"x-default\">{title}</rdf:li></rdf:Alt></dc:title>" if title else ""
    return (f'<?xpacket begin="" id="W5M0MpCehiHzreSzNTczkc9d"?><x:xmpmeta xmlns:x="adobe:ns:meta/">'
            f'<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
            f'<rdf:Description rdf:about="" xmlns:xmp="http://ns.adobe.com/xap/1.0/" '
            f'xmlns:dc="http://purl.org/dc/elements/1.1/" {attributes}>{inner}</rdf:Description>'
            f'</rdf:RDF></x:xmpmeta><?xpacket end="w"?>').encode("utf-8")


def icc_bytes(description: str = "Profil fictif") -> bytes:
    """A syntactically valid, tiny ICC profile with a 'desc' tag."""
    text = description.encode("ascii") + b"\x00"
    tag = b"desc" + b"\x00" * 4 + struct.pack(">I", len(text)) + text
    tag += b"\x00" * (-len(tag) % 4)
    header = bytearray(128)
    header[8:12] = bytes([2, 0x10, 0, 0])
    header[12:16] = b"scnr"
    header[16:20] = b"GRAY"
    body = bytes(header) + struct.pack(">I", 1) + b"desc" + struct.pack(">II", 144, len(tag)) + tag
    return struct.pack(">I", len(body)) + body[4:]


def jpeg_bytes(width: int = 8, height: int = 8, *, jfif_density: tuple[int, int, int] | None = (1, 300, 300),
               exif: bytes | None = None, xmp: bytes | None = None, iptc: bytes | None = None,
               comments: tuple[str, ...] = (), icc: bytes | None = None, trailer: bytes = b"") -> bytes:
    """A valid baseline greyscale JPEG (uniform grey), with the requested metadata segments.

    The entropy-coded data is the smallest possible: one Huffman code per table, every
    block made of a zero DC difference followed by an end-of-block.
    """
    out = b"\xff\xd8"
    if jfif_density is not None:
        units, x, y = jfif_density
        out += _segment(0xE0, b"JFIF\x00\x01\x01" + bytes([units]) + struct.pack(">HH", x, y) + b"\x00\x00")
    if exif is not None:
        out += _segment(0xE1, b"Exif\x00\x00" + exif)
    if xmp is not None:
        out += _segment(0xE1, b"http://ns.adobe.com/xap/1.0/\x00" + xmp)
    if icc is not None:
        out += _segment(0xE2, b"ICC_PROFILE\x00\x01\x01" + icc)
    if iptc is not None:
        out += _segment(0xED, photoshop_bytes(iptc))
    for comment in comments:
        out += _segment(0xFE, comment.encode("utf-8"))
    out += _segment(0xDB, b"\x00" + bytes([16] * 64))
    out += _segment(0xC0, b"\x08" + struct.pack(">HH", height, width) + b"\x01\x01\x11\x00")
    out += _segment(0xC4, b"\x00" + bytes([1] + [0] * 15) + b"\x00")      # DC table: one code, category 0
    out += _segment(0xC4, b"\x10" + bytes([1] + [0] * 15) + b"\x00")      # AC table: one code, end of block
    out += _segment(0xDA, b"\x01\x01\x00\x00\x3f\x00")
    blocks = ((width + 7) // 8) * ((height + 7) // 8)
    bits = "00" * blocks
    bits += "1" * (-len(bits) % 8)
    out += bytes(int(bits[index:index + 8], 2) for index in range(0, len(bits), 8))
    return out + b"\xff\xd9" + trailer


# ----------------------------------------------------------------------------- PNG

def _chunk(kind: bytes, body: bytes) -> bytes:
    return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body))


def png_bytes(width: int = 4, height: int = 3, *, text: dict[str, str] | None = None,
              compressed_text: dict[str, str] | None = None, international_text: dict[str, str] | None = None,
              pixels_per_metre: int | None = 11811, time: tuple[int, int, int, int, int, int] | None = None,
              exif: bytes | None = None) -> bytes:
    """A valid 8-bit greyscale PNG with the requested ancillary chunks."""
    out = b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0))
    if pixels_per_metre is not None:
        out += _chunk(b"pHYs", struct.pack(">IIB", pixels_per_metre, pixels_per_metre, 1))
    for key, value in (text or {}).items():
        out += _chunk(b"tEXt", key.encode("latin-1") + b"\x00" + value.encode("latin-1"))
    for key, value in (compressed_text or {}).items():
        out += _chunk(b"zTXt", key.encode("latin-1") + b"\x00\x00" + zlib.compress(value.encode("latin-1")))
    for key, value in (international_text or {}).items():
        out += _chunk(b"iTXt", key.encode("latin-1") + b"\x00\x00\x00\x00\x00" + value.encode("utf-8"))
    if time is not None:
        out += _chunk(b"tIME", struct.pack(">HBBBBB", *time))
    if exif is not None:
        out += _chunk(b"eXIf", exif)
    rows = b"".join(b"\x00" + bytes([128] * width) for _ in range(height))
    return out + _chunk(b"IDAT", zlib.compress(rows)) + _chunk(b"IEND", b"")


# ----------------------------------------------------------------------------- JPEG 2000

def _box(kind: bytes, body: bytes) -> bytes:
    return struct.pack(">I", len(body) + 8) + kind + body


def jp2_bytes(width: int = 20, height: int = 30, *, xml: str | None = None, xmp: bytes | None = None) -> bytes:
    """The box structure of a JP2 file (the codestream itself is a stub: only SIZ is real)."""
    out = _box(b"jP  ", b"\r\n\x87\n") + _box(b"ftyp", b"jp2 \x00\x00\x00\x00jp2 ")
    header = _box(b"ihdr", struct.pack(">IIHBBBB", height, width, 1, 7, 7, 0, 0)) + _box(b"colr", b"\x01\x00\x00" + struct.pack(">I", 17))
    header += _box(b"res ", _box(b"resc", struct.pack(">HHHHbb", 11811, 1, 11811, 1, 0, 0)))
    out += _box(b"jp2h", header)
    if xml is not None:
        out += _box(b"xml ", xml.encode("utf-8"))
    if xmp is not None:
        out += _box(b"uuid", bytes.fromhex("be7acfcb97a942e89c71999491e3afac") + xmp)
    siz = b"\xff\x4f\xff\x51" + struct.pack(">HHIIIIIIIIH", 41, 0, width, height, 0, 0, width, height, 0, 0, 1) + b"\x07\x01\x01"
    return out + _box(b"jp2c", siz + b"\xff\xd9")


# ----------------------------------------------------------------------------- HTML pages of a fictitious viewer

def landing_html(media: list[str], *, viewer: str | None = None, title: str = "Décret fictif du 1er janvier 1900",
                 extra: str = "") -> str:
    """A notice page as it *might* look: thumbnails, zoom attributes, a JSON blob, a viewer link."""
    thumbnails = "\n".join(
        f'<li><a class="vignette" href="/mm/media/download/{name}-medium.jpg" data-zoom="/mm/media/download/{name}.jpg">'
        f'<img src="/mm/media/download/{name}-min.jpg" alt="vue {rank + 1}"></a></li>'
        for rank, name in enumerate(media))
    blob = "{\"medias\": [" + ", ".join(f'{{"rang": {rank + 1}, "nom": "{name}"}}' for rank, name in enumerate(media)) + "]}"
    link = f'<a id="ouvrir-visionneuse" href="{viewer}">Ouvrir la visionneuse</a>' if viewer else ""
    return f"""<!DOCTYPE html>
<html lang="fr"><head><meta charset="utf-8"><title>{title} - Salle fictive</title>
<link rel="stylesheet" href="/siv/resources/css/site.css">
<script src="/siv/resources/js/consultation.js"></script></head>
<body><div id="bandeau"><img src="/siv/resources/images/logo.png" alt="logo"></div>
<h1>{title}</h1>
<div class="notice"><span class="cote">BB/34/000</span> <span class="doc">document 1</span></div>
<ul id="vignettes">
{thumbnails}
</ul>
{link}
<script type="application/json" id="donnees-medias">{blob}</script>
{extra}
<form id="recherche" method="post" action="/siv/recherche.action"><input type="hidden" name="token" value="JETON-FICTIF">
<input type="text" name="texte"></form>
</body></html>"""


# ----------------------------------------------------------------------------- transcriptions

PAGE_1 = """Ministère de la Justice          République Française
                                                      12 JANV 1932
Le Président de la République Française,
Sur le Rapport du Garde des Sceaux, Ministre de la Justice,
Décrète :
Article Premier.
Sont naturalisés Français par application de l'article 6 § 1er de la loi du I0 août I927 :

20001 X 3I   TESTAOUI (Ahmed ben Mohamed), cultivateur, né le 6 juin I885 à Fictiville
             (Alger), demeurant à Exempleville (Alger).
             Remise totale.

8I02 X 31    FICTIVO (Paul Henri), tonnelier, né le 7 mars I88I à Inventada (Espagne),
             et EXEMPLMANN (Maria), sa femme, née le 2 février 1890 à Oran (Algérie),
             demeurant tous deux à Testbourg (Oran), ayant deux enfants mineurs :
             I°) Pierre, né le 4 mars I9I2 à Testbourg ; 2°) Louise, née le 1er juin 1915 à Testbourg.
             Remise des neuf dixièmes.

I0452 X 30   INVENTEE (Rosa), couturière, née le 30 novembre 1899 à Imaginaire (Italie), demeu-
"""

PAGE_2 = """                                   - 2 -
             rant à Fabriqueville (Constantine).
             Remise totale.

777 X 31     SPECIMEN (Paul), né en 1901 à Nullepart (Maroc), demeurant à Alger.

Art. 2. - Le Garde des Sceaux, Ministre de la Justice, est chargé de l'exécution du présent décret.
"""


# The quirks of layout seen on the tutorial screenshots of real decrees of 1932. Only the SHAPE is
# kept: every name, number, date and place below is invented. Pencil tick after the number and
# before the name, no comma before the profession, months with a capital, one child per line
# without « ; », several given names, « d° » for a repeated place, « et » alone on its line before
# the wife, a parenthesis that closes on the next line.
PAGE_QUIRKS_1 = """                                                    - 9 FEV 1932
Ministère de la Justice        République Française.
Le Président de la République Française,
Sur le Rapport du Garde des Sceaux, Ministre de la Justice,
DECRETE :
Article Premier.
Sont naturalisés Français par application de
l'article 6 § Ier de la Loi du I0 Août I927 :
4001 X 32/   /FICTANEL (Aldo) mineur, né le 9 Mars
1890 à Inventona (Italie), demeurant à Essai-les-Bains
(Jura), ayant quatre enfants mineurs :
      I°) Clara, née le 2 Octobre 1920 à Inventona
(Italie)
      2°) Nina, née le 7 Avril 1924 à Essai-les-Bains
(Jura)
      3°) Dora, née le 11 Août 1927 à    d°
      4°) Hugo, né le 3 Juin 1930 à      d°
           Remise totale.
4002 X 32/   ROBATEST (Emile, Octave) mécanicien, né le 14
Mai 1891 à La Fictive (Suisse), demeurant à Testaux (Jura)
ayant six enfants mineurs :
      1°) Alain, Victor, né le 12 Juin 1918 à Imaginelles
(Suisse)
      2°) Basile, Edgar, né le 6 Novembre 1921 à d°
      3°) Colette, Irma, née le 9 Février 1923 à
Fabriqueux (Suisse)
"""

PAGE_QUIRKS_2 = """     /VULTEST (Otto), cultivateur, né le 7 octobre
1860 à Beurnessai (Suisse),
                 et
     MOINEAU (Odile), sa femme, née le 17 septembre
1865 à Montessai (Suisse),
demeurant tous deux à Essaibourg (Haut-Rhin).
     Remise totale.
     LONGNOMEST (Remi Jean Marie Joseph Antoine
Fictif), mineur, né le 13 avril 1886 à Borgo-d'Essai (Italie), demeurant à Alger.
"""
