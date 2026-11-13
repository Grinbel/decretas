"""What an image file says about itself, read with the standard library only.

`inspecter(path)` returns a plain dict (JSON-serialisable) with:

- the container format, dimensions, bit depth, density (and the physical size it implies);
- JPEG: every marker segment, JFIF, EXIF (IFD0, Exif and GPS sub-directories, thumbnail),
  XMP packet, Photoshop resources with their IPTC datasets, COM comments, ICC profile,
  Adobe segment, an estimate of the compression quality, bytes after the end of image;
- PNG: IHDR, pHYs, tEXt / zTXt / iTXt, tIME, eXIf, iCCP, chunk census, CRC check;
- TIFF: the tags of every directory (classic TIFF; BigTIFF is only recognised);
- JPEG 2000: boxes (ihdr, colr, resolution, xml, uuid with XMP or EXIF) or a bare codestream;
- GIF and WebP: dimensions, comments, embedded EXIF/XMP;
- what the FILE NAME and the URL encode (lot, running number, size suffix, IIIF request);
- `texte_libre`: the short list of fields that hold free text. This is the only place where
  a cote, a decree date or a person's name could hide; everything else is technical.

Input files are untrusted: every offset is bounds-checked, every loop is capped, nothing is
executed, compressed text is inflated under a size limit. A damaged file yields a partial
description plus an `erreurs` list, never an exception.
"""
from __future__ import annotations

import hashlib
import re
import struct
import urllib.parse
import zlib
from pathlib import Path

MAX_BYTES = 512 * 1024 * 1024          # files larger than this are not loaded
MAX_TEXT = 64 * 1024                   # longest text value kept (characters)
MAX_INFLATE = 4 * 1024 * 1024          # compressed text chunks are inflated up to this size
MAX_IFD_ENTRIES = 1024
MAX_DIRECTORIES = 4096

IMAGE_SUFFIXES = (".jpg", ".jpeg", ".jpe", ".png", ".tif", ".tiff", ".jp2", ".j2k", ".jpf", ".jpx", ".gif", ".webp")

# ----------------------------------------------------------------------------- tag names

TIFF_TAGS = {
    254: "NewSubfileType", 256: "ImageWidth", 257: "ImageLength", 258: "BitsPerSample", 259: "Compression",
    262: "PhotometricInterpretation", 269: "DocumentName", 270: "ImageDescription", 271: "Make", 272: "Model",
    273: "StripOffsets", 274: "Orientation", 277: "SamplesPerPixel", 278: "RowsPerStrip", 279: "StripByteCounts",
    282: "XResolution", 283: "YResolution", 284: "PlanarConfiguration", 285: "PageName", 296: "ResolutionUnit",
    297: "PageNumber", 305: "Software", 306: "DateTime", 315: "Artist", 316: "HostComputer", 322: "TileWidth",
    323: "TileLength", 513: "JPEGInterchangeFormat", 514: "JPEGInterchangeFormatLength", 700: "XMP",
    33432: "Copyright", 33723: "IPTC", 34377: "PhotoshopResources", 34665: "ExifIFD", 34675: "ICCProfile",
    34853: "GPSIFD", 40091: "XPTitle", 40092: "XPComment", 40093: "XPAuthor", 40094: "XPKeywords",
    40095: "XPSubject", 50341: "PrintImageMatching",
}
EXIF_TAGS = {
    33434: "ExposureTime", 33437: "FNumber", 34850: "ExposureProgram", 34855: "ISOSpeedRatings",
    36864: "ExifVersion", 36867: "DateTimeOriginal", 36868: "DateTimeDigitized", 37121: "ComponentsConfiguration",
    37377: "ShutterSpeedValue", 37378: "ApertureValue", 37383: "MeteringMode", 37384: "LightSource",
    37385: "Flash", 37386: "FocalLength", 37500: "MakerNote", 37510: "UserComment", 37520: "SubSecTime",
    40960: "FlashpixVersion", 40961: "ColorSpace", 40962: "PixelXDimension", 40963: "PixelYDimension",
    40965: "InteroperabilityIFD", 41486: "FocalPlaneXResolution", 41487: "FocalPlaneYResolution",
    41488: "FocalPlaneResolutionUnit", 41728: "FileSource", 41729: "SceneType", 41985: "CustomRendered",
    41986: "ExposureMode", 41987: "WhiteBalance", 42016: "ImageUniqueID", 42032: "CameraOwnerName",
    42033: "BodySerialNumber", 42034: "LensSpecification", 42035: "LensMake", 42036: "LensModel",
}
GPS_TAGS = {0: "GPSVersionID", 1: "GPSLatitudeRef", 2: "GPSLatitude", 3: "GPSLongitudeRef", 4: "GPSLongitude",
            5: "GPSAltitudeRef", 6: "GPSAltitude", 7: "GPSTimeStamp", 29: "GPSDateStamp"}
IPTC_DATASETS = {
    (1, 90): "CodedCharacterSet", (2, 0): "RecordVersion", (2, 5): "ObjectName", (2, 15): "Category",
    (2, 20): "SupplementalCategory", (2, 25): "Keywords", (2, 40): "SpecialInstructions", (2, 55): "DateCreated",
    (2, 60): "TimeCreated", (2, 62): "DigitalCreationDate", (2, 65): "OriginatingProgram",
    (2, 70): "ProgramVersion", (2, 80): "By-line", (2, 85): "By-lineTitle", (2, 90): "City",
    (2, 92): "Sub-location", (2, 95): "Province-State", (2, 101): "Country", (2, 103): "OriginalTransmissionReference",
    (2, 105): "Headline", (2, 110): "Credit", (2, 115): "Source", (2, 116): "CopyrightNotice",
    (2, 118): "Contact", (2, 120): "Caption-Abstract", (2, 122): "Writer-Editor",
}
# Fields that hold free text, per source: the only places where a description could be stored.
FREE_TEXT_EXIF = frozenset({"ImageDescription", "DocumentName", "PageName", "Artist", "Copyright", "UserComment",
                            "XPTitle", "XPComment", "XPAuthor", "XPKeywords", "XPSubject", "CameraOwnerName",
                            "HostComputer"})
FREE_TEXT_XMP_PREFIXES = ("dc:", "photoshop:", "Iptc4xmpCore:", "Iptc4xmpExt:", "xmpRights:", "pdf:", "lr:")
TECHNICAL_IPTC = frozenset({"RecordVersion", "CodedCharacterSet", "OriginatingProgram", "ProgramVersion"})
TECHNICAL_PNG_TEXT = frozenset({"software", "creation time", "date:create", "date:modify", "date:timestamp",
                                "xml:com.adobe.xmp", "raw profile type exif", "raw profile type iptc",
                                "raw profile type xmp", "raw profile type icc"})

JPEG_MARKERS = {0xC0: "SOF0", 0xC1: "SOF1", 0xC2: "SOF2", 0xC3: "SOF3", 0xC4: "DHT", 0xC5: "SOF5", 0xC6: "SOF6",
                0xC7: "SOF7", 0xC9: "SOF9", 0xCA: "SOF10", 0xCB: "SOF11", 0xCC: "DAC", 0xCD: "SOF13",
                0xCE: "SOF14", 0xCF: "SOF15", 0xD8: "SOI", 0xD9: "EOI", 0xDA: "SOS", 0xDB: "DQT", 0xDC: "DNL",
                0xDD: "DRI", 0xFE: "COM"}
SOF_KINDS = {0: "séquentiel de base (baseline)", 1: "séquentiel étendu", 2: "progressif", 3: "sans perte",
             9: "séquentiel arithmétique", 10: "progressif arithmétique", 11: "sans perte arithmétique"}
# Luminance quantisation table of the JPEG standard (annex K), in zigzag order.
STD_LUMINANCE_ZIGZAG = (16, 11, 12, 14, 12, 10, 16, 14, 13, 14, 18, 17, 16, 19, 24, 40, 26, 24, 22, 22, 24, 49,
                        35, 37, 29, 40, 58, 51, 61, 60, 57, 51, 56, 55, 64, 72, 92, 78, 64, 68, 87, 69, 55, 56,
                        80, 109, 81, 87, 95, 98, 103, 104, 103, 62, 77, 113, 121, 112, 100, 120, 92, 101, 103, 99)

XMP_SIGNATURE = b"http://ns.adobe.com/xap/1.0/\x00"
XMP_EXT_SIGNATURE = b"http://ns.adobe.com/xmp/extension/\x00"
XMP_UUID = bytes.fromhex("be7acfcb97a942e89c71999491e3afac")
EXIF_UUID = b"JpgTiffExif->JP2"


# ----------------------------------------------------------------------------- small helpers

def _text(raw: bytes) -> str:
    """Decode a metadata string: UTF-8 when valid, Latin-1 otherwise; NULs and controls removed."""
    raw = raw.split(b"\x00", 1)[0]
    try:
        value = raw.decode("utf-8")
    except UnicodeDecodeError:
        value = raw.decode("latin-1")
    value = "".join(ch if ch in "\n\t" or ch >= " " else " " for ch in value).strip()
    return value[:MAX_TEXT]


def _summary(raw: bytes) -> str:
    """A short, harmless description of a binary value."""
    printable = sum(1 for b in raw[:64] if 32 <= b < 127)
    if raw and printable >= 0.9 * min(len(raw), 64):
        return _text(raw)[:200]
    return f"<{len(raw)} octets : {raw[:12].hex()}…>" if len(raw) > 12 else f"<{len(raw)} octets : {raw.hex()}>"


def _add_free_text(card: dict, source: str, name: str, value) -> None:
    if value is None:
        return
    text = value if isinstance(value, str) else ", ".join(str(item) for item in value) if isinstance(value, list) else str(value)
    text = text.strip()
    if text:
        card.setdefault("texte_libre", []).append({"source": source, "champ": name, "valeur": text[:2000]})


# ----------------------------------------------------------------------------- TIFF / EXIF

_TYPE_SIZES = {1: 1, 2: 1, 3: 2, 4: 4, 5: 8, 6: 1, 7: 1, 8: 2, 9: 4, 10: 8, 11: 4, 12: 8, 13: 4}
_TYPE_CODES = {1: "B", 3: "H", 4: "I", 6: "b", 8: "h", 9: "i", 11: "f", 12: "d", 13: "I"}


def _ifd_value(data: bytes, order: str, kind: int, count: int, field: bytes, errors: list[str], as_bytes: bool = False):
    """Decode one directory entry. `field` is its 4-byte value/offset slot.

    `as_bytes`: return the raw bytes whatever the declared type (embedded XMP, IPTC, ICC…).
    """
    size = _TYPE_SIZES.get(kind)
    if size is None:
        return None
    total = size * count
    if total <= 4:
        raw = field[:total]
    else:
        offset = struct.unpack(order + "I", field)[0]
        if offset + total > len(data) or total > 16 * 1024 * 1024:
            errors.append(f"valeur EXIF/TIFF hors du fichier (décalage {offset}, {total} octets)")
            return None
        raw = data[offset:offset + total]
    if as_bytes or kind == 7 or (kind == 1 and count > 8):
        return raw
    if kind == 2:
        return _text(raw)
    if kind in (5, 10):
        code = "II" if kind == 5 else "ii"
        values = []
        for index in range(min(count, 64)):
            num, den = struct.unpack(order + code, raw[index * 8:index * 8 + 8])
            values.append(round(num / den, 6) if den else None)
        return values[0] if count == 1 else values
    code = _TYPE_CODES[kind]
    shown = min(count, 64)
    values = list(struct.unpack(order + code * shown, raw[:shown * size]))
    return values[0] if count == 1 else values


def _read_ifd(data: bytes, order: str, offset: int, names: dict[int, str], errors: list[str]) -> tuple[dict, dict, int]:
    """One image file directory -> (named values, raw byte values by name, offset of the next IFD)."""
    values: dict = {}
    blobs: dict = {}
    if offset <= 0 or offset + 2 > len(data):
        return values, blobs, 0
    count = struct.unpack(order + "H", data[offset:offset + 2])[0]
    if count > MAX_IFD_ENTRIES:
        errors.append(f"répertoire TIFF de {count} entrées : lecture limitée à {MAX_IFD_ENTRIES}")
        count = MAX_IFD_ENTRIES
    position = offset + 2
    for _ in range(count):
        entry = data[position:position + 12]
        if len(entry) < 12:
            errors.append("répertoire TIFF tronqué")
            return values, blobs, 0
        tag, kind, number = struct.unpack(order + "HHI", entry[:8])
        position += 12
        embedded = tag in (700, 33723, 34377, 34675) or 40091 <= tag <= 40095
        value = _ifd_value(data, order, kind, number, entry[8:12], errors, as_bytes=embedded)
        if value is None:
            continue
        name = names.get(tag) or TIFF_TAGS.get(tag) or f"tag-{tag}"
        if isinstance(value, bytes):
            blobs[name] = value
            if name.startswith("XP"):                      # Windows fields: UTF-16LE text
                values[name] = value.decode("utf-16-le", "replace").rstrip("\x00")[:MAX_TEXT]
            elif name == "UserComment":
                body = value[8:] if len(value) >= 8 else value
                values[name] = (body.decode("utf-16", "replace") if value[:8].startswith(b"UNICODE")
                                else _text(body.strip(b"\x00 ")))
            elif name in ("ExifVersion", "FlashpixVersion"):
                values[name] = value.decode("ascii", "replace")
            else:
                values[name] = _summary(value)
        else:
            values[name] = value
    following = data[position:position + 4]
    next_offset = struct.unpack(order + "I", following)[0] if len(following) == 4 else 0
    return values, blobs, next_offset


def parse_tiff(data: bytes, card: dict, source: str = "TIFF") -> dict | None:
    """Parse a TIFF structure (a .tif file or an EXIF block). Returns its description or None."""
    errors = card.setdefault("erreurs", [])
    if len(data) < 8 or data[:2] not in (b"II", b"MM"):
        return None
    order = "<" if data[:2] == b"II" else ">"
    magic = struct.unpack(order + "H", data[2:4])[0]
    if magic == 43:
        return {"ordre": "petit-boutiste" if order == "<" else "gros-boutiste", "bigtiff": True,
                "note": "BigTIFF reconnu mais non analysé"}
    if magic != 42:
        return None
    result: dict = {"ordre": "petit-boutiste (II)" if order == "<" else "gros-boutiste (MM)", "repertoires": 0}
    offset = struct.unpack(order + "I", data[4:8])[0]
    seen: set[int] = set()
    index = 0
    while offset and offset not in seen and index < MAX_DIRECTORIES:
        seen.add(offset)
        values, blobs, next_offset = _read_ifd(data, order, offset, {}, errors)
        if index == 0:
            result["ifd0"] = {k: v for k, v in values.items() if k not in ("StripOffsets", "StripByteCounts")}
            for name in ("ExifIFD", "GPSIFD"):
                pointer = values.get(name)
                if isinstance(pointer, int) and pointer not in seen:
                    sub, _blobs, _next = _read_ifd(data, order, pointer, EXIF_TAGS if name == "ExifIFD" else GPS_TAGS, errors)
                    sub.pop("MakerNote", None)
                    result["exif" if name == "ExifIFD" else "gps"] = sub
            for name, raw in blobs.items():
                if name == "XMP":
                    card["xmp"] = parse_xmp(raw, card)
                elif name == "IPTC":
                    card["iptc"] = parse_iptc(raw, card)
                elif name == "PhotoshopResources":
                    parse_photoshop(raw, card)
                elif name == "ICCProfile":
                    card["icc"] = parse_icc(raw)
        elif index == 1 and source == "EXIF":
            result["vignette"] = {k: values[k] for k in ("ImageWidth", "ImageLength", "Compression",
                                                          "JPEGInterchangeFormatLength") if k in values}
        index += 1
        offset = next_offset
    result["repertoires"] = index
    for name, value in result.get("ifd0", {}).items():
        if name in FREE_TEXT_EXIF:
            _add_free_text(card, source, name, value)
    for name, value in result.get("exif", {}).items():
        if name in FREE_TEXT_EXIF:
            _add_free_text(card, source + " (Exif)", name, value)
    return result


def _density_from_tiff(ifd0: dict) -> dict | None:
    x, y, unit = ifd0.get("XResolution"), ifd0.get("YResolution"), ifd0.get("ResolutionUnit", 2)
    if not isinstance(x, (int, float)) or not isinstance(y, (int, float)) or not x or not y:
        return None
    return {"x": x, "y": y, "unite": {2: "ppp", 3: "ppcm"}.get(unit, "sans unité")}


# ----------------------------------------------------------------------------- XMP, IPTC, ICC

_XMP_ELEMENT = re.compile(r"<([A-Za-z][\w.-]*:[A-Za-z][\w.-]*)(?:\s[^<>]*)?>([^<>]{1,4000})</\1\s*>")
_XMP_ATTRIBUTE = re.compile(r"\b([A-Za-z][\w.-]*:[A-Za-z][\w.-]*)\s*=\s*\"([^\"]{0,4000})\"")
_XMP_CONTAINER = re.compile(r"<([A-Za-z][\w.-]*:[A-Za-z][\w.-]*)(?:\s[^<>]*)?>\s*<rdf:(?:Alt|Seq|Bag)[^<>]*>(.*?)</rdf:(?:Alt|Seq|Bag)>",
                            re.S)
_XMP_ITEM = re.compile(r"<rdf:li[^<>]*>([^<>]*)</rdf:li>")


def _unescape(value: str) -> str:
    return (value.replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"').replace("&apos;", "'")
            .replace("&amp;", "&")).strip()


def parse_xmp(raw: bytes, card: dict) -> dict:
    """Read an XMP packet with regular expressions only (no XML parser on untrusted input)."""
    text = raw[:1024 * 1024].decode("utf-8", "replace")
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        text = raw[:1024 * 1024].decode("utf-16", "replace")
    fields: dict[str, object] = {}
    for name, body in _XMP_CONTAINER.findall(text):
        items = [_unescape(item) for item in _XMP_ITEM.findall(body) if item.strip()]
        if items:
            fields[name] = items if len(items) > 1 else items[0]
    for name, value in _XMP_ELEMENT.findall(text):
        if name.startswith(("rdf:", "x:")) or name in fields:
            continue
        if value.strip():
            fields[name] = _unescape(value)
    for name, value in _XMP_ATTRIBUTE.findall(text):
        if name.startswith(("xmlns:", "rdf:", "x:", "xml:")) or name in fields:
            continue
        if value.strip():
            fields[name] = _unescape(value)
    for name, value in fields.items():
        if name.startswith(FREE_TEXT_XMP_PREFIXES) and name not in ("dc:format", "photoshop:ColorMode",
                                                                     "photoshop:ICCProfile"):
            _add_free_text(card, "XMP", name, value)
    return {"octets": len(raw), "champs": dict(sorted(fields.items())), "debut": " ".join(text[:240].split())}


def parse_iptc(raw: bytes, card: dict) -> dict:
    """IPTC-IIM datasets: 0x1C, record, dataset, 2-byte length, value."""
    fields: dict[str, object] = {}
    utf8 = False
    position = 0
    guard = 0
    while position + 5 <= len(raw) and guard < 4096:
        guard += 1
        if raw[position] != 0x1C:
            position += 1
            continue
        record, dataset, length = raw[position + 1], raw[position + 2], struct.unpack(">H", raw[position + 3:position + 5])[0]
        position += 5
        if length & 0x8000:                      # extended length: not used by descriptive fields
            break
        value = raw[position:position + length]
        position += length
        name = IPTC_DATASETS.get((record, dataset), f"{record}:{dataset}")
        if (record, dataset) == (1, 90):
            utf8 = value == b"\x1b%G"
            fields[name] = "UTF-8" if utf8 else _summary(value)
            continue
        if (record, dataset) == (2, 0):
            fields[name] = int.from_bytes(value, "big") if value else None
            continue
        text = value.decode("utf-8", "replace") if utf8 else _text(value)
        if name in fields:
            previous = fields[name]
            fields[name] = previous + [text] if isinstance(previous, list) else [previous, text]
        else:
            fields[name] = text
    for name, value in fields.items():
        if name not in TECHNICAL_IPTC:
            _add_free_text(card, "IPTC", name, value)
    return fields


def parse_photoshop(raw: bytes, card: dict) -> None:
    """Photoshop image resource blocks (8BIM): resource census, IPTC (0x0404), resolution (0x03ED)."""
    resources = []
    position = 0
    guard = 0
    while position + 12 <= len(raw) and guard < 2048:
        guard += 1
        if raw[position:position + 4] != b"8BIM":
            break
        identifier = struct.unpack(">H", raw[position + 4:position + 6])[0]
        name_length = raw[position + 6]
        position += 7 + name_length + (0 if (name_length + 1) % 2 == 0 else 1)
        if position + 4 > len(raw):
            break
        size = struct.unpack(">I", raw[position:position + 4])[0]
        position += 4
        body = raw[position:position + size]
        position += size + (size % 2)
        resources.append({"id": f"0x{identifier:04X}", "octets": size})
        if identifier == 0x0404:
            card["iptc"] = parse_iptc(body, card)
        elif identifier == 0x03ED and len(body) >= 16:
            horizontal = struct.unpack(">I", body[0:4])[0] / 65536
            vertical = struct.unpack(">I", body[8:12])[0] / 65536
            card.setdefault("photoshop", {})["resolution"] = {"x": round(horizontal, 3), "y": round(vertical, 3), "unite": "ppp"}
    card.setdefault("photoshop", {})["ressources"] = resources


def parse_icc(raw: bytes) -> dict:
    """Size, colour space and description of an ICC profile."""
    info: dict = {"octets": len(raw)}
    if len(raw) < 132:
        return info
    info["version"] = f"{raw[8]}.{raw[9] >> 4}"
    info["classe"] = raw[12:16].decode("ascii", "replace").strip()
    info["espace"] = raw[16:20].decode("ascii", "replace").strip()
    count = min(struct.unpack(">I", raw[128:132])[0], 256)
    for index in range(count):
        entry = raw[132 + 12 * index:144 + 12 * index]
        if len(entry) < 12:
            break
        signature, offset, size = entry[:4], *struct.unpack(">II", entry[4:12])
        if signature != b"desc" or offset + size > len(raw) or size < 12:
            continue
        body = raw[offset:offset + size]
        if body[:4] == b"desc":
            length = struct.unpack(">I", body[8:12])[0]
            info["description"] = _text(body[12:12 + min(length, 512)])
        elif body[:4] == b"mluc" and len(body) >= 28:
            length, start = struct.unpack(">II", body[20:28])
            info["description"] = body[start:start + min(length, 1024)].decode("utf-16-be", "replace").strip("\x00")
        break
    return info


# ----------------------------------------------------------------------------- JPEG

def _estimate_quality(table: list[int]) -> int | None:
    """IJG quality that would produce this luminance table (approximation, 1-100)."""
    if len(table) != 64 or not all(table):
        return None
    scale = 100.0 * sum(table) / sum(STD_LUMINANCE_ZIGZAG)
    quality = (200.0 - scale) / 2.0 if scale <= 100.0 else 5000.0 / scale
    return max(1, min(100, round(quality)))


def parse_jpeg(data: bytes, card: dict) -> None:
    errors = card.setdefault("erreurs", [])
    card["format"] = "JPEG"
    segments: list[dict] = []
    comments: list[str] = []
    icc_parts: dict[int, bytes] = {}
    position = 2
    end_of_image = None
    guard = 0
    while position + 2 <= len(data) and guard < 100000:
        guard += 1
        if data[position] != 0xFF:
            errors.append(f"octet inattendu à la position {position} : lecture des segments arrêtée")
            break
        marker = data[position + 1]
        if marker == 0xFF:                                   # fill byte
            position += 1
            continue
        if marker == 0xD9:
            end_of_image = position + 2
            break
        if marker in (0x01, 0xD8) or 0xD0 <= marker <= 0xD7:
            position += 2
            continue
        if position + 4 > len(data):
            break
        length = struct.unpack(">H", data[position + 2:position + 4])[0]
        if length < 2:
            errors.append(f"segment de longueur invalide à la position {position}")
            break
        body = data[position + 4:position + 2 + length]
        name = JPEG_MARKERS.get(marker) or (f"APP{marker - 0xE0}" if 0xE0 <= marker <= 0xEF else f"0x{marker:02X}")
        segment = {"marqueur": name, "octets": length}
        if 0xE0 <= marker <= 0xEF:
            signature = body.split(b"\x00", 1)[0][:40]
            segment["signature"] = signature.decode("latin-1")
        if marker == 0xE0 and body[:5] == b"JFIF\x00" and len(body) >= 14:
            units, x, y = body[7], *struct.unpack(">HH", body[8:12])
            card["jfif"] = {"version": f"{body[5]}.{body[6]:02d}", "x": x, "y": y,
                            "unite": {0: "sans unité (rapport d'aspect)", 1: "ppp", 2: "ppcm"}.get(units, str(units)),
                            "vignette": [body[12], body[13]]}
        elif marker == 0xE1 and body[:6] == b"Exif\x00\x00":
            exif = parse_tiff(body[6:], card, "EXIF")
            if exif is not None:
                card["exif"] = exif
            else:
                errors.append("segment EXIF illisible")
        elif marker == 0xE1 and body.startswith(XMP_SIGNATURE):
            card["xmp"] = parse_xmp(body[len(XMP_SIGNATURE):], card)
        elif marker == 0xE1 and body.startswith(XMP_EXT_SIGNATURE):
            card["xmp_etendu"] = card.get("xmp_etendu", 0) + len(body)
        elif marker == 0xE2 and body[:12] == b"ICC_PROFILE\x00" and len(body) > 14:
            icc_parts[body[12]] = body[14:]
        elif marker == 0xED and body[:14] == b"Photoshop 3.0\x00":
            parse_photoshop(body[14:], card)
        elif marker == 0xEE and body[:5] == b"Adobe" and len(body) >= 12:
            card["adobe"] = {"version": struct.unpack(">H", body[5:7])[0],
                             "transformation": {0: "aucune (RVB ou CMJN)", 1: "YCbCr", 2: "YCCK"}.get(body[11], str(body[11]))}
        elif marker == 0xFE:
            comment = _text(body)
            comments.append(comment)
            _add_free_text(card, "JPEG", "commentaire (COM)", comment)
        elif marker == 0xDB:
            cursor = 0
            while cursor < len(body):
                precision, identifier = body[cursor] >> 4, body[cursor] & 0x0F
                size = 128 if precision else 64
                raw = body[cursor + 1:cursor + 1 + size]
                if len(raw) < size:
                    break
                table = list(struct.unpack(">64H", raw)) if precision else list(raw)
                if identifier == 0:
                    quality = _estimate_quality(table)
                    if quality is not None:
                        card["qualite_estimee"] = quality
                cursor += 1 + size
        elif name.startswith("SOF") and len(body) >= 6:
            precision, height, width, components = struct.unpack(">BHHB", body[:6])
            card.update(largeur=width, hauteur=height, bits=precision, composantes=components)
            card["codage"] = SOF_KINDS.get(marker - 0xC0, name)
            sampling = [f"{body[7 + 3 * i] >> 4}x{body[7 + 3 * i] & 0x0F}" for i in range(components) if 7 + 3 * i < len(body)]
            card["echantillonnage"] = sampling
        segments.append(segment)
        if marker == 0xDA:                                   # entropy-coded data: jump to the next marker
            cursor = position + 2 + length
            while True:
                cursor = data.find(b"\xff", cursor)
                if cursor < 0 or cursor + 1 >= len(data):
                    cursor = len(data)
                    break
                following = data[cursor + 1]
                if following == 0x00 or 0xD0 <= following <= 0xD7 or following == 0xFF:
                    cursor += 1 if following == 0xFF else 2
                    continue
                break
            position = cursor
            continue
        position += 2 + length
    if icc_parts:
        card["icc"] = parse_icc(b"".join(icc_parts[key] for key in sorted(icc_parts)))
    if comments:
        card["commentaires"] = comments
    card["segments"] = segments
    if end_of_image is None:
        errors.append("fin d'image (EOI) non trouvée : fichier tronqué ou structure inhabituelle")
    elif end_of_image < len(data):
        card["octets_apres_fin"] = len(data) - end_of_image
    if "jfif" in card and card["jfif"]["unite"] in ("ppp", "ppcm"):
        card["densite"] = {"x": card["jfif"]["x"], "y": card["jfif"]["y"], "unite": card["jfif"]["unite"], "source": "JFIF"}
    elif "exif" in card:
        density = _density_from_tiff(card["exif"].get("ifd0", {}))
        if density:
            card["densite"] = dict(density, source="EXIF")


# ----------------------------------------------------------------------------- PNG

PNG_COLOR_TYPES = {0: "niveaux de gris", 2: "RVB", 3: "palette", 4: "gris + alpha", 6: "RVB + alpha"}


def _inflate(raw: bytes) -> bytes:
    decompressor = zlib.decompressobj()
    return decompressor.decompress(raw, MAX_INFLATE)


def parse_png(data: bytes, card: dict) -> None:
    errors = card.setdefault("erreurs", [])
    card["format"] = "PNG"
    census: dict[str, int] = {}
    texts: dict[str, str] = {}
    position = 8
    guard = 0
    bad_crc = 0
    while position + 12 <= len(data) and guard < 200000:
        guard += 1
        length = struct.unpack(">I", data[position:position + 4])[0]
        kind = data[position + 4:position + 8]
        body = data[position + 8:position + 8 + length]
        crc = data[position + 8 + length:position + 12 + length]
        if len(body) < length or len(crc) < 4:
            errors.append(f"bloc PNG {kind.decode('latin-1')} tronqué")
            break
        if zlib.crc32(kind + body) != struct.unpack(">I", crc)[0]:
            bad_crc += 1
        name = kind.decode("latin-1")
        census[name] = census.get(name, 0) + 1
        position += 12 + length
        try:
            if kind == b"IHDR" and length >= 13:
                width, height, depth, color, _c, _f, interlace = struct.unpack(">IIBBBBB", body[:13])
                card.update(largeur=width, hauteur=height, bits=depth, couleur=PNG_COLOR_TYPES.get(color, str(color)),
                            entrelace=bool(interlace))
            elif kind == b"pHYs" and length >= 9:
                x, y, unit = struct.unpack(">IIB", body[:9])
                if unit == 1:
                    card["densite"] = {"x": round(x * 0.0254, 2), "y": round(y * 0.0254, 2), "unite": "ppp",
                                       "source": "pHYs (pixels par mètre convertis)"}
                else:
                    card["rapport_aspect"] = [x, y]
            elif kind == b"tEXt":
                key, _sep, value = body.partition(b"\x00")
                texts[key.decode("latin-1")] = value.decode("latin-1")[:MAX_TEXT]
            elif kind == b"zTXt":
                key, _sep, rest = body.partition(b"\x00")
                texts[key.decode("latin-1")] = _inflate(rest[1:]).decode("latin-1")[:MAX_TEXT]
            elif kind == b"iTXt":
                key, _sep, rest = body.partition(b"\x00")
                compressed = rest[0:1] == b"\x01"
                _language, _sep, rest = rest[2:].partition(b"\x00")
                _translated, _sep, value = rest.partition(b"\x00")
                value = _inflate(value) if compressed else value
                texts[key.decode("latin-1")] = value.decode("utf-8", "replace")[:MAX_TEXT]
            elif kind == b"tIME" and length >= 7:
                year, month, day, hour, minute, second = struct.unpack(">HBBBBB", body[:7])
                card["date_modification"] = f"{year:04d}-{month:02d}-{day:02d}T{hour:02d}:{minute:02d}:{second:02d}Z"
            elif kind == b"eXIf":
                exif = parse_tiff(body, card, "EXIF")
                if exif is not None:
                    card["exif"] = exif
            elif kind == b"iCCP":
                profile_name, _sep, rest = body.partition(b"\x00")
                card["icc"] = dict(parse_icc(_inflate(rest[1:])), nom=profile_name.decode("latin-1"))
            elif kind == b"gAMA" and length >= 4:
                card["gamma"] = round(struct.unpack(">I", body[:4])[0] / 100000, 5)
            elif kind == b"sRGB":
                card["srgb"] = True
        except (zlib.error, struct.error, ValueError) as error:
            errors.append(f"bloc PNG {name} illisible ({type(error).__name__})")
        if kind == b"IEND":
            break
    if position < len(data):
        card["octets_apres_fin"] = len(data) - position
    if bad_crc:
        errors.append(f"{bad_crc} bloc(s) PNG dont le code de contrôle (CRC) est faux")
    card["blocs"] = census
    if texts:
        card["texte_png"] = texts
        for key, value in texts.items():
            if key.lower() == "xml:com.adobe.xmp":
                card["xmp"] = parse_xmp(value.encode("utf-8"), card)
            elif key.lower() not in TECHNICAL_PNG_TEXT:
                _add_free_text(card, "PNG", key, value)


# ----------------------------------------------------------------------------- JPEG 2000

def _parse_codestream_size(data: bytes, card: dict) -> None:
    """SIZ marker of a JPEG 2000 codestream: image size and component count."""
    start = data.find(b"\xff\x4f\xff\x51")
    if start < 0 or start + 44 > len(data):
        return
    xsiz, ysiz, xosiz, yosiz = struct.unpack(">IIII", data[start + 8:start + 24])
    components = struct.unpack(">H", data[start + 40:start + 42])[0]
    card.setdefault("largeur", xsiz - xosiz)
    card.setdefault("hauteur", ysiz - yosiz)
    card.setdefault("composantes", components)
    if start + 43 <= len(data):
        card.setdefault("bits", (data[start + 42] & 0x7F) + 1)


def _walk_boxes(data: bytes, start: int, end: int, card: dict, depth: int, boxes: list[str]) -> None:
    position = start
    guard = 0
    while position + 8 <= end and guard < 10000:
        guard += 1
        length, kind = struct.unpack(">I4s", data[position:position + 8])
        header = 8
        if length == 1:
            if position + 16 > end:
                break
            length = struct.unpack(">Q", data[position + 8:position + 16])[0]
            header = 16
        elif length == 0:
            length = end - position
        if length < header or position + length > end:
            card.setdefault("erreurs", []).append(f"boîte JPEG 2000 {kind!r} de taille incohérente")
            break
        body_start, body_end = position + header, position + length
        name = kind.decode("latin-1")
        boxes.append("  " * depth + f"{name} ({length} octets)")
        body = data[body_start:body_end] if kind != b"jp2c" else b""
        if kind in (b"jp2h", b"res ") and depth < 4:
            _walk_boxes(data, body_start, body_end, card, depth + 1, boxes)
        elif kind == b"ftyp" and len(body) >= 8:
            card["marque"] = body[:4].decode("latin-1").strip()
        elif kind == b"ihdr" and len(body) >= 14:
            height, width, components, bpc = struct.unpack(">IIHB", body[:11])
            card.update(largeur=width, hauteur=height, composantes=components, bits=(bpc & 0x7F) + 1)
        elif kind == b"colr" and len(body) >= 7:
            method = body[0]
            if method == 1:
                space = struct.unpack(">I", body[3:7])[0]
                card["couleur"] = {16: "sRVB", 17: "niveaux de gris", 18: "sYCC"}.get(space, f"espace {space}")
            elif method == 2:
                card["icc"] = parse_icc(body[3:])
        elif kind in (b"resc", b"resd") and len(body) >= 10:
            vn, vd, hn, hd, ve, he = struct.unpack(">HHHHbb", body[:10])
            if vd and hd:
                per_metre_y, per_metre_x = vn / vd * 10 ** ve, hn / hd * 10 ** he
                card["densite"] = {"x": round(per_metre_x * 0.0254, 2), "y": round(per_metre_y * 0.0254, 2), "unite": "ppp",
                                   "source": "boîte " + name + (" (capture)" if kind == b"resc" else " (affichage)")}
        elif kind == b"xml ":
            card.setdefault("xml", []).append(_text(body)[:2000])
            _add_free_text(card, "JPEG 2000", "boîte xml", _text(body)[:2000])
        elif kind == b"uuid" and len(body) >= 16:
            if body[:16] == XMP_UUID:
                card["xmp"] = parse_xmp(body[16:], card)
            elif body[:16] == EXIF_UUID:
                payload = body[16:]
                exif = parse_tiff(payload[6:] if payload[:6] == b"Exif\x00\x00" else payload, card, "EXIF")
                if exif is not None:
                    card["exif"] = exif
            else:
                card.setdefault("uuid", []).append(body[:16].hex())
        elif kind == b"jp2c":
            _parse_codestream_size(data[body_start:body_start + 256], card)
        position += length


def parse_jp2(data: bytes, card: dict) -> None:
    card["format"] = "JPEG 2000"
    boxes: list[str] = []
    if data[:4] == b"\xff\x4f\xff\x51":
        card["conteneur"] = "flux de code nu (sans boîtes : aucune métadonnée descriptive possible)"
        _parse_codestream_size(data[:256], card)
        return
    card["conteneur"] = "JP2 (boîtes)"
    _walk_boxes(data, 0, len(data), card, 0, boxes)
    card["boites"] = boxes[:200]


# ----------------------------------------------------------------------------- GIF, WebP, TIFF file

def parse_gif(data: bytes, card: dict) -> None:
    card["format"] = "GIF"
    if len(data) < 13:
        return
    width, height, flags = struct.unpack("<HHB", data[6:11])
    card.update(largeur=width, hauteur=height)
    position = 13 + (3 * (2 << (flags & 7)) if flags & 0x80 else 0)
    frames = 0
    comments = []
    guard = 0

    def skip_sub_blocks(cursor: int) -> tuple[int, bytes]:
        collected = b""
        while cursor < len(data) and data[cursor]:
            size = data[cursor]
            collected += data[cursor + 1:cursor + 1 + size]
            cursor += 1 + size
        return cursor + 1, collected

    while position < len(data) and guard < 100000:
        guard += 1
        block = data[position]
        if block == 0x3B:
            break
        if block == 0x21 and position + 2 < len(data):
            label = data[position + 1]
            position, payload = skip_sub_blocks(position + 2)
            if label == 0xFE:
                comments.append(_text(payload))
            elif label == 0xFF and payload[:11] == b"XMP DataXMP":
                card["xmp"] = parse_xmp(payload[11:], card)
        elif block == 0x2C and position + 10 <= len(data):
            frames += 1
            local = data[position + 9]
            position += 10 + (3 * (2 << (local & 7)) if local & 0x80 else 0) + 1
            position, _payload = skip_sub_blocks(position)
        else:
            break
    card["images"] = frames
    if comments:
        card["commentaires"] = comments
        for comment in comments:
            _add_free_text(card, "GIF", "commentaire", comment)


def parse_webp(data: bytes, card: dict) -> None:
    card["format"] = "WebP"
    position = 12
    census: dict[str, int] = {}
    guard = 0
    while position + 8 <= len(data) and guard < 10000:
        guard += 1
        kind, length = data[position:position + 4], struct.unpack("<I", data[position + 4:position + 8])[0]
        body = data[position + 8:position + 8 + length]
        name = kind.decode("latin-1").strip()
        census[name] = census.get(name, 0) + 1
        if kind == b"VP8X" and len(body) >= 10:
            card.update(largeur=int.from_bytes(body[4:7], "little") + 1, hauteur=int.from_bytes(body[7:10], "little") + 1)
        elif kind == b"VP8 " and len(body) >= 10 and body[3:6] == b"\x9d\x01\x2a":
            width, height = struct.unpack("<HH", body[6:10])
            card.setdefault("largeur", width & 0x3FFF)
            card.setdefault("hauteur", height & 0x3FFF)
        elif kind == b"VP8L" and len(body) >= 5 and body[0] == 0x2F:
            bits = int.from_bytes(body[1:5], "little")
            card.setdefault("largeur", (bits & 0x3FFF) + 1)
            card.setdefault("hauteur", ((bits >> 14) & 0x3FFF) + 1)
        elif kind == b"EXIF":
            exif = parse_tiff(body[6:] if body[:6] == b"Exif\x00\x00" else body, card, "EXIF")
            if exif is not None:
                card["exif"] = exif
        elif kind == b"XMP ":
            card["xmp"] = parse_xmp(body, card)
        elif kind == b"ICCP":
            card["icc"] = parse_icc(body)
        position += 8 + length + (length & 1)
    card["blocs"] = census


def parse_tiff_file(data: bytes, card: dict) -> None:
    card["format"] = "TIFF"
    tiff = parse_tiff(data, card, "TIFF")
    if tiff is None:
        card.setdefault("erreurs", []).append("structure TIFF illisible")
        return
    card["tiff"] = tiff
    ifd0 = tiff.get("ifd0", {})
    if isinstance(ifd0.get("ImageWidth"), int):
        card["largeur"] = ifd0["ImageWidth"]
    if isinstance(ifd0.get("ImageLength"), int):
        card["hauteur"] = ifd0["ImageLength"]
    bits = ifd0.get("BitsPerSample")
    if bits is not None:
        card["bits"] = bits[0] if isinstance(bits, list) else bits
    if isinstance(ifd0.get("SamplesPerPixel"), int):
        card["composantes"] = ifd0["SamplesPerPixel"]
    card["pages"] = tiff.get("repertoires")
    density = _density_from_tiff(ifd0)
    if density:
        card["densite"] = dict(density, source="TIFF")


# ----------------------------------------------------------------------------- file name and URL

SIZE_WORDS = {
    "min": 10, "mini": 10, "thumb": 10, "thumbnail": 10, "vignette": 10, "icon": 10, "preview": 15, "apercu": 15,
    "small": 20, "petit": 20, "low": 20, "medium": 40, "moyen": 40, "med": 40, "normal": 50, "large": 70,
    "grand": 70, "big": 70, "hd": 80, "zoom": 80, "high": 80, "max": 90, "full": 90, "original": 100, "orig": 100,
    "master": 100,
}
_SIZE_SUFFIX = re.compile(r"[-_.](" + "|".join(sorted(SIZE_WORDS, key=len, reverse=True)) + r")$", re.I)
_LOT_AN = re.compile(r"^(?P<prefixe>[A-Z]{3,}\d{0,4})_(?P<serie>[A-Z]{2,})(?P<numero>\d{3,})_(?P<suffixe>[A-Z]{1,3})$")
_FRAN = re.compile(r"^FRAN_(?P<categorie>[A-Z0-9]+)_(?P<numero>\d+)(?:_(?P<suffixe>[A-Za-z0-9]+))?$")
_IA_WIDTH = re.compile(r"^(?P<document>.+?)[-_]n(?P<feuillet>\d+)_w(?P<largeur>\d+)$")
_IIIF = re.compile(r"/(?P<identifiant>[^/]+)/(?P<region>full|square|\d+,\d+,\d+,\d+|pct:[\d.,]+)/"
                   r"(?P<taille>full|max|\^?!?\d*,\d*|\^?pct:[\d.]+)/(?P<rotation>!?[\d.]+)/"
                   r"(?P<qualite>default|native|color|gray|bitonal)\.(?P<format>jpg|png|tif|jp2|gif|webp)$")
_NUMBER_RUN = re.compile(r"\d+")


def decoder_nom(name: str) -> dict:
    """What a media file name (or media identifier) encodes. Interpretations are labelled as
    known facts (`connu`) or as hypotheses to check on real files (`hypothese`)."""
    base = name.rsplit("/", 1)[-1]
    stem, dot, extension = base.rpartition(".")
    if not dot or len(extension) > 5 or not extension.isalnum():
        stem, extension = base, ""
    result: dict = {"nom": base, "extension": extension.lower() or None}
    size = _SIZE_SUFFIX.search(stem)
    if size:
        result["taille"] = {"mot": size.group(1).lower(), "rang": SIZE_WORDS[size.group(1).lower()]}
        stem = stem[:size.start()]
    result["radical"] = stem
    lot = _LOT_AN.match(stem)
    fran = _FRAN.match(stem)
    archive = _IA_WIDTH.match(stem)
    if lot:
        result.update(forme="lot-de-numerisation", prefixe=lot["prefixe"], serie=lot["serie"],
                      numero=int(lot["numero"]), chiffres=len(lot["numero"]), suffixe=lot["suffixe"])
        result["connu"] = ("Forme des quatre identifiants de média présents dans les exports XML des Archives "
                           "nationales (DAFANCH94_NUMJ<6 chiffres>_D) ; dans ces quatre cas le numéro croît avec la "
                           "date du décret.")
        result["hypothese"] = ("Le numéro serait un compteur continu sur toute la numérisation de la sous-série ; le "
                               "sens du suffixe (un lot de vues ou un fichier) reste à constater sur le site.")
    elif fran:
        categories = {"IR": "instrument de recherche (inventaire)", "ANX": "annexe publiée par la Salle de lecture virtuelle"}
        result.update(forme="identifiant-FRAN", categorie=fran["categorie"], numero=int(fran["numero"]),
                      chiffres=len(fran["numero"]))
        if fran["suffixe"]:
            result["suffixe"] = fran["suffixe"]
        if fran["categorie"] in categories:
            result["connu"] = "Catégorie " + fran["categorie"] + " : " + categories[fran["categorie"]] + "."
        else:
            result["hypothese"] = "Identifiant de la forme FRAN_<lot>_<numéro> : sens du lot à constater."
    elif archive:
        result.update(forme="internet-archive", document=archive["document"], feuillet=int(archive["feuillet"]),
                      largeur_demandee=int(archive["largeur"]))
        result["connu"] = "Nom donné par ce projet à une page de l'Internet Archive : feuillet (n) et largeur demandée (w)."
    else:
        result["forme"] = "libre"
    runs = [(match.start(), match.group()) for match in _NUMBER_RUN.finditer(stem)]
    if runs:
        result["nombres"] = [int(text) for _start, text in runs][:8]
        last_start, last = runs[-1]
        result["dernier_nombre"] = {"valeur": int(last), "chiffres": len(last), "position": last_start}
        if "forme" in result and result["forme"] == "libre":
            result["hypothese"] = "Le dernier nombre du nom est souvent le rang de la vue : à vérifier sur une suite de fichiers."
    return result


def decoder_url(url: str) -> dict:
    """What the URL of a media encodes: host, path roles, query parameters, IIIF request."""
    parts = urllib.parse.urlsplit(url)
    segments = [segment for segment in parts.path.split("/") if segment]
    result: dict = {"hote": parts.hostname, "chemin": parts.path, "segments": len(segments)}
    if parts.query:
        result["parametres"] = {key: values[0] if len(values) == 1 else values
                                for key, values in urllib.parse.parse_qs(parts.query, keep_blank_values=True).items()}
    iiif = _IIIF.search(parts.path)
    if iiif:
        result["iiif"] = iiif.groupdict()
        result["forme"] = "requête d'image IIIF"
    elif len(segments) >= 3 and segments[0] == "siv" and segments[1] in ("media", "UD", "IR"):
        result["forme"] = {"media": "lien d'images d'une notice", "UD": "permalien d'une notice",
                           "IR": "permalien d'un inventaire"}[segments[1]]
        result["inventaire"] = segments[2]
        if len(segments) >= 4 and segments[1] != "IR":
            result["notice"] = segments[3]
        if len(segments) >= 5 and segments[1] == "media":
            result["media"] = decoder_nom(segments[4])
    elif "/mm/media/download/" in parts.path:
        result["forme"] = "fichier du serveur de médias"
    if segments:
        result["fichier"] = decoder_nom(urllib.parse.unquote(segments[-1]))
    return result


def analyser_suite(names: list[str]) -> dict:
    """Compare the names of several media of one decree, in the order they were found.

    Finds the numeric field that varies, says whether it grows by one from a view to the
    next, and lists the gaps. The result supports — or refutes — "the name gives the order".
    """
    decoded = [decoder_nom(name) for name in names]
    stems = [item["radical"] for item in decoded]
    result: dict = {"fichiers": len(names)}
    if len(stems) < 2:
        result["conclusion"] = "une seule vue : aucun ordre à déduire"
        return result
    prefix = stems[0]
    for stem in stems[1:]:
        while prefix and not stem.startswith(prefix):
            prefix = prefix[:-1]
    result["prefixe_commun"] = prefix
    if len(prefix) < 3:
        result["conclusion"] = "noms sans radical commun : ces fichiers ne forment pas une suite"
        return result
    token_lists = [_NUMBER_RUN.findall(stem) for stem in stems]
    width = min(len(tokens) for tokens in token_lists)
    varying = [index for index in range(width) if len({tokens[index] for tokens in token_lists}) > 1]
    if not varying:
        result["conclusion"] = "aucun champ numérique ne varie d'un nom à l'autre : le nom ne donne pas l'ordre"
        return result
    index = varying[-1]
    values = [int(tokens[index]) for tokens in token_lists]
    steps = [second - first for first, second in zip(values, values[1:])]
    result.update(champ_variable=index + 1, valeurs=values[:50], premier=values[0], dernier=values[-1])
    result["croissant"] = all(step > 0 for step in steps)
    result["continu"] = all(step == 1 for step in steps)
    result["trous"] = [[first, second] for first, second in zip(values, values[1:]) if second - first > 1][:20]
    if result["continu"]:
        result["conclusion"] = (f"le nombre n° {index + 1} du nom croît de 1 en 1 ({values[0]} à {values[-1]}) dans l'ordre où les "
                                "vues sont listées : le nom donne l'ordre des vues")
    elif result["croissant"]:
        result["conclusion"] = (f"le nombre n° {index + 1} du nom croît ({values[0]} à {values[-1]}) avec des trous : "
                                "ordre donné par le nom, vues manquantes ou numérotation partagée avec d'autres décrets")
    else:
        result["conclusion"] = "le champ numérique variable n'est pas croissant dans l'ordre de la page : ne pas trier par nom"
    return result


# ----------------------------------------------------------------------------- entry points

def detecter_format(head: bytes) -> str | None:
    """Container format from the first bytes, or None."""
    if head[:3] == b"\xff\xd8\xff":
        return "JPEG"
    if head[:8] == b"\x89PNG\r\n\x1a\n":
        return "PNG"
    if head[:4] in (b"II*\x00", b"MM\x00*", b"II+\x00", b"MM\x00+"):
        return "TIFF"
    if head[:12] == b"\x00\x00\x00\x0cjP  \r\n\x87\n" or head[:4] == b"\xff\x4f\xff\x51":
        return "JPEG 2000"
    if head[:6] in (b"GIF87a", b"GIF89a"):
        return "GIF"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "WebP"
    if head[:5] == b"%PDF-":
        return "PDF"
    return None


_PARSERS = {"JPEG": parse_jpeg, "PNG": parse_png, "TIFF": parse_tiff_file, "JPEG 2000": parse_jp2, "GIF": parse_gif,
            "WebP": parse_webp}


def inspecter_octets(data: bytes) -> dict:
    """Describe an image held in memory. Never raises on damaged input."""
    card: dict = {"octets": len(data), "sha256": hashlib.sha256(data).hexdigest(), "erreurs": []}
    kind = detecter_format(data[:16])
    if kind is None and data[:512].lstrip()[:15].lower().startswith((b"<!doctype html", b"<html", b"<head", b"<?xml")):
        card["format"] = "HTML ou XML"
        card["erreurs"].append("ce fichier est une page HTML ou XML, pas une image : le serveur a sans doute répondu "
                               "par une page d'erreur, de connexion ou de visionneuse à la place de l'image")
        return card
    if kind is None:
        card["format"] = "inconnu"
        card["erreurs"].append("format non reconnu (ni JPEG, PNG, TIFF, JPEG 2000, GIF, WebP) : début " + data[:8].hex())
        return card
    if kind == "PDF":
        card["format"] = "PDF"
        card["erreurs"].append("document PDF : ce n'est pas une image, ses pages ne sont pas analysées ici")
        return card
    try:
        _PARSERS[kind](data, card)
    except (struct.error, IndexError, ValueError, OverflowError) as error:
        card["format"] = kind
        card["erreurs"].append(f"structure {kind} endommagée : lecture interrompue ({type(error).__name__})")
    density = card.get("densite")
    if density and density.get("unite") in ("ppp", "ppcm") and card.get("largeur") and density["x"] and density["y"]:
        per_cm = (density["x"] / 2.54, density["y"] / 2.54) if density["unite"] == "ppp" else (density["x"], density["y"])
        card["taille_physique_cm"] = [round(card["largeur"] / per_cm[0], 1), round(card["hauteur"] / per_cm[1], 1)]
    card.setdefault("texte_libre", [])
    return card


def _check_with_pil(path: Path, card: dict) -> None:
    """Optional cross-check of the dimensions with Pillow, when it is installed."""
    try:
        from PIL import Image  # noqa: PLC0415 (optional dependency, imported on demand)
    except ImportError:
        card["controle_pil"] = "Pillow absent : pas de contrôle croisé"
        return
    try:
        with Image.open(path) as image:
            size = [image.width, image.height]
    except Exception as error:  # noqa: BLE001 (Pillow raises many unrelated types on damaged files)
        card["controle_pil"] = f"Pillow n'ouvre pas ce fichier ({type(error).__name__})"
        return
    ours = [card.get("largeur"), card.get("hauteur")]
    card["controle_pil"] = "dimensions concordantes" if size == ours else f"DIVERGENCE : Pillow lit {size[0]} × {size[1]}"


def inspecter(path: Path, url: str | None = None, *, pil: bool = True) -> dict:
    """Describe an image file: content, file name and (when given) the URL it came from."""
    path = Path(path)
    card: dict = {"fichier": str(path)}
    try:
        size = path.stat().st_size
        if size > MAX_BYTES:
            card.update(format="inconnu", octets=size, erreurs=[f"fichier de plus de {MAX_BYTES} octets : non lu"],
                        texte_libre=[])
        else:
            card.update(inspecter_octets(path.read_bytes()))
    except OSError as error:
        card.update(format="inconnu", erreurs=[f"fichier illisible : {error.strerror or type(error).__name__}"], texte_libre=[])
    card["nom"] = decoder_nom(path.name)
    asked = card["nom"].get("largeur_demandee")
    if asked and card.get("largeur") and card["largeur"] != asked:
        # a name is a claim, the pixels are the fact: say so when they disagree
        card.setdefault("erreurs", []).append(
            f"le nom annonce une largeur de {asked} px, l'image en fait {card['largeur']} : ne pas se fier au nom pour la taille")
    if url:
        card["url"] = dict(decoder_url(url), adresse=url)
    if pil and card.get("format") in ("JPEG", "PNG", "TIFF", "GIF", "WebP") and card.get("largeur"):
        _check_with_pil(path, card)
    return card


# ----------------------------------------------------------------------------- French rendering

def _fr(number: float) -> str:
    text = f"{number:,.2f}".rstrip("0").rstrip(".") if isinstance(number, float) else f"{number:,}"
    return text.replace(",", " ").replace(".", ",")


def _dimensions(card: dict) -> str:
    if not card.get("largeur"):
        return "inconnues"
    return f"{card['largeur']} × {card['hauteur']} px"


def _density(card: dict) -> str:
    density = card.get("densite")
    if not density:
        return "non déclarée"
    text = f"{_fr(density['x'])} × {_fr(density['y'])} {density['unite']} ({density['source']})"
    if card.get("taille_physique_cm"):
        text += f" → {_fr(card['taille_physique_cm'][0])} × {_fr(card['taille_physique_cm'][1])} cm"
    return text


def _lines_of(card: dict) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    kind = card.get("format", "inconnu")
    details = [str(card[key]) for key in ("codage", "couleur", "conteneur") if card.get(key)]
    if card.get("bits"):
        details.append(f"{card['bits']} bits")
    if card.get("composantes"):
        details.append(f"{card['composantes']} composante(s)")
    rows.append(("Format", kind + (" — " + ", ".join(details) if details else "")))
    rows.append(("Dimensions", _dimensions(card)))
    rows.append(("Densité", _density(card)))
    rows.append(("Poids", f"{_fr(card.get('octets', 0))} octets"))
    if card.get("qualite_estimee"):
        rows.append(("Qualité JPEG", f"≈ {card['qualite_estimee']} sur 100 (estimation d'après la table de quantification)"))
    if card.get("pages"):
        rows.append(("Pages TIFF", str(card["pages"])))
    if card.get("jfif"):
        rows.append(("JFIF", f"version {card['jfif']['version']}"))
    exif = card.get("exif") or card.get("tiff")
    if exif:
        ifd0 = exif.get("ifd0", {})
        shown = [f"{name} = {ifd0[name]}" for name in ("Make", "Model", "Software", "DateTime", "ImageDescription",
                                                        "DocumentName", "Artist", "Copyright", "HostComputer", "Orientation")
                 if ifd0.get(name) not in (None, "")]
        sub = exif.get("exif", {})
        shown += [f"{name} = {sub[name]}" for name in ("DateTimeOriginal", "DateTimeDigitized", "ColorSpace",
                                                       "PixelXDimension", "PixelYDimension", "UserComment", "LensModel",
                                                       "BodySerialNumber") if sub.get(name) not in (None, "")]
        rows.append(("EXIF" if "exif" in card else "Balises TIFF", " ; ".join(shown) if shown else "présent, sans champ notable"))
        if exif.get("gps"):
            rows.append(("EXIF GPS", ", ".join(f"{k} = {v}" for k, v in exif["gps"].items())))
        if exif.get("vignette"):
            rows.append(("Vignette EXIF", str(exif["vignette"])))
    else:
        rows.append(("EXIF", "absent"))
    if card.get("xmp"):
        fields = card["xmp"]["champs"]
        shown = [f"{name} = {fields[name]}" for name in list(fields)[:14]]
        rows.append(("XMP", f"{card['xmp']['octets']} octets ; " + (" ; ".join(shown) if shown else "aucun champ lu")))
    else:
        rows.append(("XMP", "absent"))
    if card.get("iptc"):
        rows.append(("IPTC", " ; ".join(f"{name} = {value}" for name, value in card["iptc"].items())))
    else:
        rows.append(("IPTC", "absent"))
    if card.get("photoshop", {}).get("ressources"):
        rows.append(("Photoshop", ", ".join(f"{r['id']} ({r['octets']} o)" for r in card["photoshop"]["ressources"][:12])))
    if card.get("commentaires"):
        rows.append(("Commentaires", " | ".join(card["commentaires"])[:400]))
    if card.get("texte_png"):
        rows.append(("Texte PNG", " ; ".join(f"{key} = {value[:120]}" for key, value in card["texte_png"].items())))
    if card.get("icc"):
        icc = card["icc"]
        rows.append(("Profil ICC", f"{icc.get('octets')} octets" + (f", {icc['description']}" if icc.get("description") else "")
                     + (f", espace {icc['espace']}" if icc.get("espace") else "")))
    else:
        rows.append(("Profil ICC", "absent"))
    if card.get("segments"):
        census: dict[str, int] = {}
        for segment in card["segments"]:
            label = segment["marqueur"] + (f"[{segment['signature']}]" if segment.get("signature") else "")
            census[label] = census.get(label, 0) + 1
        rows.append(("Segments", ", ".join(f"{label}×{count}" if count > 1 else label for label, count in census.items())))
    if card.get("blocs"):
        rows.append(("Blocs", ", ".join(f"{name}×{count}" if count > 1 else name for name, count in card["blocs"].items())))
    if card.get("boites"):
        rows.append(("Boîtes", " / ".join(box.strip() for box in card["boites"][:12])))
    if card.get("octets_apres_fin"):
        rows.append(("Après la fin", f"{_fr(card['octets_apres_fin'])} octets suivent la fin de l'image : à examiner"))
    if card.get("controle_pil"):
        rows.append(("Contrôle Pillow", card["controle_pil"]))
    name = card.get("nom", {})
    described = [f"forme « {name.get('forme')} »"]
    for key, label in (("prefixe", "préfixe"), ("serie", "série"), ("categorie", "catégorie"), ("numero", "numéro"),
                       ("suffixe", "suffixe"), ("document", "document"), ("feuillet", "feuillet"),
                       ("largeur_demandee", "largeur demandée")):
        if name.get(key) is not None:
            described.append(f"{label} {name[key]}")
    if name.get("taille"):
        described.append(f"suffixe de taille « {name['taille']['mot']} »")
    if name.get("forme") == "libre" and name.get("dernier_nombre"):
        described.append(f"dernier nombre {name['dernier_nombre']['valeur']}")
    rows.append(("Nom du fichier", ", ".join(described)))
    for key, label in (("connu", "  constaté"), ("hypothese", "  hypothèse")):
        if name.get(key):
            rows.append((label, name[key]))
    if card.get("url"):
        url = card["url"]
        described = [url.get("forme") or "forme non reconnue"]
        for key, label in (("inventaire", "inventaire"), ("notice", "notice")):
            if url.get(key):
                described.append(f"{label} {url[key]}")
        if url.get("iiif"):
            described.append("IIIF " + ", ".join(f"{k}={v}" for k, v in url["iiif"].items()))
        if url.get("parametres"):
            described.append("paramètres " + ", ".join(sorted(url["parametres"])))
        rows.append(("Adresse", ", ".join(described)))
    free = card.get("texte_libre") or []
    if free:
        rows.append(("TEXTE LIBRE", f"{len(free)} champ(s) descriptif(s) — à lire, c'est le seul endroit où une cote ou un nom peut figurer :"))
        for item in free:
            rows.append((f"  {item['source']}", f"{item['champ']} = {item['valeur'][:300]}"))
    else:
        rows.append(("TEXTE LIBRE", "aucun champ descriptif : ce fichier ne porte que des données techniques"))
    for error in card.get("erreurs", []):
        rows.append(("Anomalie", error))
    return rows


def tableau(cards: list[dict]) -> str:
    """French text rendering: one block per file, then a summary table and, for several
    files, the analysis of the name sequence."""
    out: list[str] = []
    for card in cards:
        out.append(f"== {card['fichier']}")
        if card.get("sha256"):
            out.append(f"   sha256 {card['sha256']}")
        rows = _lines_of(card)
        width = max(len(label) for label, _value in rows)
        for label, value in rows:
            out.append(f"   {label.ljust(width)}  {value}")
        out.append("")
    if len(cards) > 1:
        out.append("Récapitulatif")
        header = ("fichier", "format", "dimensions", "densité", "logiciel / appareil", "date", "texte libre")
        table = [header]
        for card in cards:
            exif = (card.get("exif") or card.get("tiff") or {})
            ifd0 = exif.get("ifd0", {})
            maker = " ".join(str(ifd0[name]) for name in ("Make", "Model", "Software") if ifd0.get(name)) or \
                str((card.get("xmp") or {}).get("champs", {}).get("xmp:CreatorTool", "")) or \
                str((card.get("texte_png") or {}).get("Software", "")) or "—"
            date = ifd0.get("DateTime") or exif.get("exif", {}).get("DateTimeOriginal") or card.get("date_modification") or "—"
            density = card.get("densite")
            table.append((Path(card["fichier"]).name[:44], card.get("format", "?"), _dimensions(card),
                          f"{_fr(density['x'])} {density['unite']}" if density else "—", maker[:40], str(date),
                          str(len(card.get("texte_libre") or [])) + " champ(s)"))
        widths = [max(len(row[column]) for row in table) for column in range(len(header))]
        for index, row in enumerate(table):
            out.append("  " + "  ".join(cell.ljust(widths[column]) for column, cell in enumerate(row)).rstrip())
            if index == 0:
                out.append("  " + "  ".join("-" * widths[column] for column in range(len(header))))
        out.append("")
        sequence = analyser_suite([Path(card["fichier"]).name for card in cards])
        out.append("Suite des noms de fichiers (dans l'ordre donné) : " + sequence.get("conclusion", ""))
        if sequence.get("prefixe_commun"):
            out.append(f"  préfixe commun : « {sequence['prefixe_commun']} »")
        out.append("")
    total_free = sum(len(card.get("texte_libre") or []) for card in cards)
    out.append(f"Bilan : {len(cards)} fichier(s) ; {total_free} champ(s) de texte libre au total."
               + ("" if total_free else " Aucune métadonnée descriptive : un nom de personne ne peut venir que de la lecture de l'image."))
    return "\n".join(out)
