"""Reading of the XML-EAD inventory exports of the Archives nationales.

The exports are untrusted data: they are parsed, never executed, and a file that declares
XML entities is refused before it reaches the parser.

Everything here is *structure*: which ``<c>`` is a decree, a group, a person-level notice,
a link of the root inventory. Nothing is decided from the first words of a title.

Facts measured on the 85 exports of 2026-10-16 (docs/research/sources-2026-11/an-local.md):

* tags carry no default namespace; links live in the xlink namespace, so the attribute is
  ``{http://www.w3.org/1999/xlink}href`` whatever prefix a serialiser wrote;
* a notice id is unique inside one inventory only: the key is (inventory, notice id);
* ``xlink:href`` (notice page) and ``daoloc/@href`` (images) are copied, never rebuilt.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

from .dates import has_full_date
from .text import fold, squash

XLINK_NS = "http://www.w3.org/1999/xlink"
XLINK_HREF = f"{{{XLINK_NS}}}href"

KIND_DECREE = "decret"
KIND_GROUP = "groupe"
KIND_PERSON = "personne"
KIND_LINK = "lien"
KIND_NOT_NOMINATIVE = "non-nominative"

UNITID_IDENTIFIER = "identifiant"
UNITID_CONSULTATION = "cote-de-consultation"
UNITID_PIECES = "pieces"

_INVENTORY_ID = re.compile(r"FRAN_IR_\d{6}")
_YEAR_IN_TITLE = re.compile(r"\b(1[89]\d\d)\b")
_QUARTER_MONTHS = {"janvier": 1, "avril": 2, "juillet": 3, "octobre": 4}
_PROLOG_LIMIT = 65536


class EadError(Exception):
    """An inventory file cannot be read safely or is not an EAD inventory."""


@dataclass(slots=True)
class RawLine:
    """One line of ``<scopecontent>``: a ``<p>`` or an ``<item>`` of a ``<list>``."""

    kind: str   # 'p' | 'item'
    text: str   # whitespace-squashed text, as written


@dataclass(slots=True)
class RawNotice:
    """One ``<c>`` element, flattened, in document order."""

    inventory: str
    notice_id: str
    seq: int
    depth: int
    parent_seq: int | None
    href: str                       # xlink:href, copied
    title: str                      # squashed text of <unittitle>
    persname_count: int             # number of <persname> inside <unittitle>
    unitids: list[tuple[str, str]]  # (type, squashed text) in document order
    has_unitdate: bool
    unitdate_normal: str | None
    unitdate_text: str
    image_links: list[str]          # daogrp/daoloc/@href, copied
    lines: list[RawLine]
    has_archref: bool
    child_count: int
    kind: str = ""
    decree_seq: int | None = None   # nearest enclosing decree, for person-level notices

    def unitid(self, kind: str) -> str:
        """The ``<unitid>`` of the given type, as written; several distinct values are joined by ' ; '."""
        values: list[str] = []
        for unitid_type, value in self.unitids:
            if unitid_type == kind and value and value not in values:
                values.append(value)
        return " ; ".join(values)


@dataclass(slots=True)
class RawInventory:
    """Header of one inventory plus its flattened notices."""

    inventory: str
    title: str
    subtitle: str
    author: str
    link: str                # eadid/@xlink:href, copied
    period_normal: str
    period_text: str
    cotes: str
    repository: str
    physloc: str
    userestrict: str
    accessrestrict: str
    year: int | None
    quarter: int | None
    is_root: bool = False
    notices: list[RawNotice] = field(default_factory=list)


def _text(element: ET.Element | None) -> str:
    return squash("".join(element.itertext())) if element is not None else ""


def _refuse_entities(path: Path) -> None:
    """Refuse a file whose prolog declares a DOCTYPE or an entity (entity-expansion attacks)."""
    with path.open("rb") as handle:
        head = handle.read(_PROLOG_LIMIT)
    prolog = head.split(b"<ead", 1)[0]
    if b"<!DOCTYPE" in prolog or b"<!ENTITY" in prolog:
        raise EadError(f"{path.name} : déclaration DOCTYPE ou ENTITY refusée")


def inventory_year(title: str) -> int | None:
    """Year named by an inventory title ('… de l'année 1928 (avril à juin)')."""
    match = _YEAR_IN_TITLE.search(title)
    return int(match.group(1)) if match else None


def inventory_quarter(title: str) -> int | None:
    """Quarter named between parentheses in an inventory title, or None for a yearly one."""
    match = re.search(r"\(([^)]*)\)", fold(title))
    if not match:
        return None
    first_word = re.split(r"[\s\-]+", match.group(1).strip())[0]
    return _QUARTER_MONTHS.get(first_word)


def _lines_of(notice: ET.Element) -> tuple[list[RawLine], bool]:
    lines: list[RawLine] = []
    has_archref = False
    for scope in notice.findall("scopecontent"):
        if scope.find(".//archref") is not None:
            has_archref = True
        for element in scope:
            if element.tag == "list":
                lines.extend(RawLine("item", _text(item)) for item in element.findall("item"))
            else:
                lines.append(RawLine("p", _text(element)))
    return lines, has_archref


def _flatten(inventory: str, dsc: ET.Element) -> list[RawNotice]:
    notices: list[RawNotice] = []
    # Explicit stack instead of recursion: (element, depth, parent sequence number).
    stack: list[tuple[ET.Element, int, int | None]] = [
        (child, 1, None) for child in reversed([c for c in dsc if c.tag == "c"])
    ]
    while stack:
        element, depth, parent_seq = stack.pop()
        seq = len(notices) + 1
        did = element.find("did")
        unittitle = did.find("unittitle") if did is not None else None
        unitdate = did.find("unitdate") if did is not None else None
        unitids = [(u.get("type") or "", _text(u)) for u in did.findall("unitid")] if did is not None else []
        lines, has_archref = _lines_of(element)
        children = [c for c in element if c.tag == "c"]
        notices.append(RawNotice(
            inventory=inventory,
            notice_id=element.get("id") or "",
            seq=seq,
            depth=depth,
            parent_seq=parent_seq,
            href=element.get(XLINK_HREF) or "",
            title=_text(unittitle),
            persname_count=len(unittitle.findall("persname")) if unittitle is not None else 0,
            unitids=unitids,
            has_unitdate=unitdate is not None,
            unitdate_normal=unitdate.get("normal") if unitdate is not None else None,
            unitdate_text=_text(unitdate),
            image_links=[d.get("href") or "" for d in element.findall("./daogrp/daoloc") if d.get("href")],
            lines=lines,
            has_archref=has_archref,
            child_count=len(children),
        ))
        stack.extend((child, depth + 1, seq) for child in reversed(children))
    return notices


def classify(notices: list[RawNotice]) -> None:
    """Set ``kind`` and ``decree_seq`` on every notice, from structure alone.

    * link: the notice points to another inventory (``<archref>``) -- root inventory;
    * decree: the notice carries a ``<unitdate>``, or is a top-level notice with children
      whose title holds a complete date (one decree of 1891 lost its ``<unitdate>``);
    * group: a notice with children that is not a decree (the two registers of 1944);
    * person-level: everything else, attached to the nearest enclosing decree;
    * not nominative: a person-level notice with a title but no ``<persname>``, no content
      line and no image link -- seven regulatory decrees and coats of arms filed among the
      persons. A person whose title is empty stays a person ("name not entered").
    """
    by_seq = {notice.seq: notice for notice in notices}
    for notice in notices:
        if notice.has_archref:
            notice.kind = KIND_LINK
        elif notice.has_unitdate or (notice.depth == 1 and notice.child_count and has_full_date(notice.title)):
            notice.kind = KIND_DECREE
            notice.decree_seq = notice.seq
        elif notice.child_count:
            notice.kind = KIND_GROUP
        else:
            parent = by_seq.get(notice.parent_seq) if notice.parent_seq is not None else None
            while parent is not None and parent.kind != KIND_DECREE:
                parent = by_seq.get(parent.parent_seq) if parent.parent_seq is not None else None
            notice.decree_seq = parent.seq if parent is not None else None
            not_nominative = (bool(notice.title) and notice.persname_count == 0
                              and not notice.lines and not notice.image_links)
            notice.kind = KIND_NOT_NOMINATIVE if not_nominative else KIND_PERSON


def read_inventory(path: Path) -> RawInventory:
    """Parse one export into a ``RawInventory`` with classified notices."""
    _refuse_entities(path)
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError as error:
        raise EadError(f"{path.name} : XML illisible ({error})") from error
    if root.tag != "ead":
        raise EadError(f"{path.name} : la racine n'est pas <ead> mais <{root.tag}>")
    eadid = root.find("eadheader/eadid")
    inventory = squash(eadid.text if eadid is not None else "") or path.stem
    if not _INVENTORY_ID.fullmatch(inventory):
        raise EadError(f"{path.name} : identifiant d'inventaire inattendu « {inventory} »")
    archdesc = root.find("archdesc")
    if archdesc is None:
        raise EadError(f"{path.name} : <archdesc> absent")
    did = archdesc.find("did")
    title = _text(root.find("eadheader/filedesc/titlestmt/titleproper"))
    period = did.find("unitdate") if did is not None else None
    result = RawInventory(
        inventory=inventory,
        title=title,
        subtitle=_text(root.find("eadheader/filedesc/titlestmt/subtitle")),
        author=_text(root.find("eadheader/filedesc/titlestmt/author")),
        link=(eadid.get(XLINK_HREF) or "") if eadid is not None else "",
        period_normal=(period.get("normal") or "") if period is not None else "",
        period_text=_text(period),
        cotes=" ; ".join(_text(u) for u in did.findall("unitid")) if did is not None else "",
        repository=_text(did.find("repository")) if did is not None else "",
        physloc=_text(did.find("physloc")) if did is not None else "",
        userestrict=_text(archdesc.find("userestrict")),
        accessrestrict=_text(archdesc.find("accessrestrict")),
        year=inventory_year(title),
        quarter=inventory_quarter(title),
    )
    dsc = archdesc.find("dsc")
    if dsc is not None:
        result.notices = _flatten(inventory, dsc)
        classify(result.notices)
    kinds = {notice.kind for notice in result.notices}
    # The root inventory lists the yearly inventories (links, grouped by year): it holds no decree.
    result.is_root = KIND_LINK in kinds and KIND_DECREE not in kinds
    return result


def inventory_files(source: Path) -> list[Path]:
    """The inventory exports of a directory, in a stable order."""
    return sorted(path for path in source.glob("FRAN_IR_*.xml") if _INVENTORY_ID.fullmatch(path.stem))
