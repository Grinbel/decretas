"""Find where the page images are, in pages whose structure is not known yet.

No decree page of the reading-room site has been seen (2026-11-11). This module therefore
does not look for *one* layout: it applies several independent, generic strategies to any
HTML, JavaScript or JSON body, and reports which strategy found what:

- ``balise``          URL-carrying attributes of standard tags (img, a, source, iframe, link…);
- ``attribut-data``   any ``data-*`` or non-standard attribute holding a URL or a JSON value;
- ``gestionnaire``    quoted strings inside ``onclick="…"`` and ``javascript:`` links;
- ``json``            strings of JSON blobs (``<script type="application/json">`` or a JSON body);
- ``script``          quoted string literals of inline scripts and of JavaScript bodies;
- ``motif-mm``        the media server pattern ``/mm/media/download/<name>`` anywhere in the text;
- ``motif-fichier``   anything that ends like an image or document file name;
- ``iiif``            ``info.json`` / ``manifest`` hints and IIIF image requests.

It also lists bare media identifiers (``DAFANCH…``, ``FRAN_…``), summarises the structure of
the page, groups image candidates into *views* (one view = one page of a decree, possibly
offered in several sizes) and picks the largest variant with an explicit, documented
heuristic. Bodies are untrusted data: they are parsed, never executed or rendered.
"""
from __future__ import annotations

import html
import json
import re
import urllib.parse
from dataclasses import dataclass, field
from html.parser import HTMLParser

from . import metadonnees
from .client import strip_session

IMAGE_EXTENSIONS = ("jpg", "jpeg", "jpe", "png", "tif", "tiff", "jp2", "j2k", "jpf", "gif", "webp")
DOCUMENT_EXTENSIONS = ("pdf", "xml", "zip")
URL_ATTRIBUTES = {
    ("img", "src"), ("img", "srcset"), ("source", "src"), ("source", "srcset"), ("a", "href"), ("area", "href"),
    ("link", "href"), ("iframe", "src"), ("frame", "src"), ("embed", "src"), ("object", "data"), ("script", "src"),
    ("video", "poster"), ("video", "src"), ("form", "action"), ("image", "href"), ("image", "xlink:href"),
}
STANDARD_ATTRIBUTES = frozenset({
    "id", "class", "style", "title", "alt", "name", "type", "rel", "lang", "dir", "role", "for", "method", "target",
    "width", "height", "charset", "media", "placeholder", "tabindex", "maxlength", "size", "cols", "rows", "colspan",
    "rowspan", "align", "valign", "border", "cellpadding", "cellspacing", "accesskey", "autocomplete", "enctype",
    "http-equiv", "property", "itemprop", "hreflang", "sizes", "loading", "decoding", "crossorigin", "integrity",
    "async", "defer", "checked", "selected", "disabled", "readonly", "multiple", "hidden", "xmlns", "label",
})
CHROME_PATH = re.compile(r"/(resources|img|css|static|themes|theme|assets|fonts|erreur)/", re.I)
CHROME_NAME = re.compile(r"(logo|picto|icon|sprite|loader|favicon|banner|bandeau|franceconnect|marianne|bouton|btn|"
                         r"arrow|fleche|puce|spacer|blank|pixel)", re.I)
VIEWER_WORDS = (("manifest", 9), ("info.json", 9), ("iiif", 8), ("visionneuse", 8), ("viewer", 8), ("galerie", 8),
                ("gallery", 8), ("multimedia", 7), ("diaporama", 6), ("mirador", 6), ("openseadragon", 6),
                ("zoom", 5), ("media", 4), ("image", 3), ("archivesnum", 3), ("numeris", 3))
MIN_VIEWER_SCORE = 4            # below this, a link is ordinary navigation and is not followed
SIZE_PARAMETERS = frozenset({"size", "taille", "width", "height", "w", "h", "largeur", "hauteur", "format", "quality",
                             "qualite", "resolution", "res", "zoom", "scale", "type"})

_FILE_PATTERN = re.compile(r"""(?:https?:)?[A-Za-z0-9_./:~%@+,;=-]*[A-Za-z0-9_%-]\.(?:jpe?g|png|tiff?|jp2|gif|webp|pdf)\b(?:\?[^\s"'<>\\)]*)?""", re.I)
_MM_PATTERN = re.compile(r"""(?:https?://[A-Za-z0-9.-]+)?/mm/media/[^\s"'<>\\)]+""")
_IIIF_HINT = re.compile(r"""(?:https?:)?[A-Za-z0-9_./:~%@+,;=-]*(?:info\.json|manifest(?:\.json)?)\b|(?:https?:)?[A-Za-z0-9_./:~%@+,;=-]*/iiif/[^\s"'<>\\)]*""", re.I)
_STRING_LITERAL = re.compile(r'"((?:[^"\\\n]|\\.){2,1500})"' + r"|'((?:[^'\\\n]|\\.){2,1500})'")
_IDENTIFIER = re.compile(r"\b(?:DAFANCH\d*_[A-Z]+\d+(?:_[A-Z0-9]+)?|FRAN_(?!IR_)[A-Z0-9]+_\d+(?:_[A-Za-z0-9]+)?)\b")
_ACTION = re.compile(r"\.(?:action|do|jsp|php|html?)\b|\?", re.I)


@dataclass
class Candidate:
    """One address found in a body."""

    url: str                       # absolute, without session identifier
    raw: str                       # as written in the body
    position: int                  # rank of first appearance
    context: str                   # where it was first seen (tag and attribute, JSON path…)
    strategies: list[str] = field(default_factory=list)
    kind: str = "autre"            # image | iiif | page | script | style | document | autre
    chrome: bool = False           # site furniture (logo, icon…), not archive material
    same_host: bool = True

    def as_dict(self) -> dict:
        return {"url": self.url, "position": self.position, "contexte": self.context, "strategies": list(self.strategies),
                "genre": self.kind, "habillage": self.chrome, "meme_hote": self.same_host}


@dataclass
class Extraction:
    kind: str                                   # html | json | javascript | xml | texte | image | pdf | binaire
    candidates: list[Candidate] = field(default_factory=list)
    identifiers: list[str] = field(default_factory=list)
    structure: dict = field(default_factory=dict)

    def images(self) -> list[Candidate]:
        return [c for c in self.candidates if c.kind == "image" and not c.chrome]

    def by_strategy(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for candidate in self.candidates:
            for strategy in candidate.strategies:
                counts[strategy] = counts.get(strategy, 0) + 1
        return dict(sorted(counts.items()))


# ----------------------------------------------------------------------------- recognising things

def sniff(body: bytes, content_type: str | None = None) -> str:
    """Kind of a body, from its first bytes first and its declared type second."""
    image = metadonnees.detecter_format(body[:16])
    if image == "PDF":
        return "pdf"
    if image:
        return "image"
    head = body[:2048].lstrip(b"\xef\xbb\xbf \t\r\n").lower()
    declared = (content_type or "").lower()
    if head.startswith((b"<!doctype html", b"<html", b"<head", b"<body")) or b"<html" in head:
        return "html"
    if head.startswith(b"<?xml") or head.startswith(b"<ead") or "xml" in declared:
        return "xml"
    if head[:1] in (b"{", b"["):
        try:
            json.loads(body.decode("utf-8", "replace"))
            return "json"
        except ValueError:
            pass
    if "javascript" in declared or "ecmascript" in declared:
        return "javascript"
    if "json" in declared:
        return "json"
    if "html" in declared or b"<div" in head or b"<script" in head or b"<img" in head:
        return "html"
    if any(marker in head for marker in (b"function", b"var ", b"$(", b"jquery")):
        return "javascript"
    if b"\x00" in body[:1024]:
        return "binaire"
    return "texte"


def looks_like_address(value: str) -> bool:
    """Could this string be a URL or a path to a resource?"""
    value = value.strip()
    if not 2 <= len(value) <= 2000 or any(ch in value for ch in " \t\n\r<>{}|^`\"'") or value in ("/", "#", "//"):
        return False
    if value.startswith(("javascript:", "mailto:", "tel:", "data:", "#", "about:")):
        return False
    if value.startswith(("http://", "https://", "//")):
        return True
    if value.startswith(("/", "./", "../")) and len(value) > 3 and re.search(r"[A-Za-z0-9]", value):
        return "/" in value[1:] or "." in value or "?" in value
    extension = value.split("?", 1)[0].rsplit(".", 1)[-1].lower()
    if "." in value and extension in IMAGE_EXTENSIONS + DOCUMENT_EXTENSIONS + ("json", "action", "js"):
        return bool(re.match(r"^[A-Za-z0-9_./:~%@+,;=?&-]+$", value))
    return False


def _extension(url: str) -> str:
    path = urllib.parse.urlsplit(url).path
    name = path.rsplit("/", 1)[-1]
    return name.rsplit(".", 1)[-1].lower() if "." in name else ""


def classify(url: str) -> tuple[str, bool]:
    """(kind, is site furniture) of an absolute URL."""
    parts = urllib.parse.urlsplit(url)
    path = parts.path
    name = path.rsplit("/", 1)[-1]
    extension = _extension(url)
    chrome = bool(CHROME_PATH.search(path) or CHROME_NAME.search(name))
    if metadonnees._IIIF.search(path):
        return "image", False
    if name.lower() in ("info.json", "manifest", "manifest.json") or "/iiif/" in path.lower():
        return "iiif", False
    if extension in IMAGE_EXTENSIONS:
        return "image", chrome
    if extension == "js":
        return "script", True
    if extension == "css":
        return "style", True
    if extension in DOCUMENT_EXTENSIONS:
        return "document", chrome
    if "/mm/media/" in path:
        return "image", False                 # the media server: assumed to be archive material until seen
    query = urllib.parse.parse_qs(parts.query)
    if any(value.lower() in IMAGE_EXTENSIONS for values in query.values() for value in values):
        return "image", chrome
    if extension in ("ico", "svg", "woff", "woff2", "ttf", "eot"):
        return "autre", True
    return "page", chrome


def viewer_score(url: str) -> int:
    """How much a page address looks like a way to the images (0 = not at all)."""
    lowered = url.lower()
    return sum(weight for word, weight in VIEWER_WORDS if word in lowered)


# ----------------------------------------------------------------------------- HTML parsing

class _PageParser(HTMLParser):
    """Collect URL-like attribute values, inline scripts, JSON blobs and a structure summary."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.found: list[tuple[str, str, str]] = []          # (strategy, context, raw value)
        self.scripts: list[str] = []
        self.json_blobs: list[tuple[str, str]] = []
        self.tags: dict[str, int] = {}
        self.ids: list[str] = []
        self.classes: dict[str, int] = {}
        self.forms: list[dict] = []
        self.headings: dict[str, list[str]] = {"h1": [], "h2": [], "h3": []}
        self.title = ""
        self.script_sources: list[str] = []
        self.frames: list[str] = []
        self.text: list[str] = []
        self.noscript = False
        self._stack: list[str] = []
        self._script_type = ""
        self._script_id = ""
        self._buffer: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.tags[tag] = self.tags.get(tag, 0) + 1
        attributes = {name: (value or "") for name, value in attrs}
        if tag in ("script", "style", "title", "h1", "h2", "h3", "noscript"):
            self._stack.append(tag)
            self._buffer = []
            if tag == "script":
                self._script_type = attributes.get("type", "").lower()
                self._script_id = attributes.get("id", "")
            if tag == "noscript":
                self.noscript = True
        if attributes.get("id"):
            self.ids.append(attributes["id"])
        for name in attributes.get("class", "").split():
            self.classes[name] = self.classes.get(name, 0) + 1
        if tag == "form":
            self.forms.append({"action": attributes.get("action", ""), "methode": attributes.get("method", "get").lower(),
                               "id": attributes.get("id", ""), "champs": []})
        if tag in ("input", "select", "textarea") and self.forms and attributes.get("name"):
            self.forms[-1]["champs"].append(attributes["name"])
        if tag == "script" and attributes.get("src"):
            self.script_sources.append(attributes["src"])
        if tag in ("iframe", "frame") and attributes.get("src"):
            self.frames.append(attributes["src"])
        for name, value in attributes.items():
            value = value.strip()
            if not value:
                continue
            context = f"<{tag} {name}>"
            if (tag, name) in URL_ATTRIBUTES:
                if name == "srcset":
                    for item in value.split(","):
                        address = item.strip().split(" ")[0]
                        if address:
                            self.found.append(("balise", context, address))
                elif value.lower().startswith("javascript:"):
                    self._strings("gestionnaire", context, value)
                elif looks_like_address(value):
                    self.found.append(("balise", context, value))
            elif name.startswith("on"):
                self._strings("gestionnaire", context, value)
            elif tag == "meta" and name == "content" and looks_like_address(value):
                self.found.append(("balise", context, value))
            elif tag == "input" and name == "value" and looks_like_address(value):
                self.found.append(("attribut-data", context, value))
            elif name.startswith("data-") or name not in STANDARD_ATTRIBUTES:
                if value[:1] in "{[":
                    try:
                        _walk_json(json.loads(value), context, self.found, "attribut-data")
                        continue
                    except ValueError:
                        pass
                if looks_like_address(value):
                    self.found.append(("attribut-data", context, value))

    def _strings(self, strategy: str, context: str, text: str) -> None:
        for match in _STRING_LITERAL.finditer(text):
            value = match.group(1) or match.group(2) or ""
            if looks_like_address(value):
                self.found.append((strategy, context, value))

    def handle_endtag(self, tag: str) -> None:
        if not self._stack or self._stack[-1] != tag:
            return
        self._stack.pop()
        content = "".join(self._buffer)
        self._buffer = []
        if tag == "script":
            if "json" in self._script_type:
                self.json_blobs.append((self._script_id or "script", content))
            elif content.strip():
                self.scripts.append(content)
        elif tag == "title":
            self.title = " ".join(content.split())
        elif tag in self.headings:
            text = " ".join(content.split())
            if text:
                self.headings[tag].append(text[:300])

    def handle_data(self, data: str) -> None:
        if self._stack:
            self._buffer.append(data)
            if self._stack[-1] in ("script", "style"):
                return
        if data.strip():
            self.text.append(" ".join(data.split()))


def _walk_json(value, path: str, found: list[tuple[str, str, str]], strategy: str = "json", depth: int = 0) -> None:
    if depth > 12:
        return
    if isinstance(value, dict):
        for key, item in list(value.items())[:2000]:
            _walk_json(item, f"{path}.{key}", found, strategy, depth + 1)
    elif isinstance(value, list):
        for index, item in enumerate(value[:5000]):
            _walk_json(item, f"{path}[{index}]", found, strategy, depth + 1)
    elif isinstance(value, str) and looks_like_address(value):
        found.append((strategy, path, value))


def _unescape_script(value: str) -> str:
    return (value.replace("\\/", "/").replace("\\u002F", "/").replace("\\u002f", "/").replace("\\u0026", "&")
            .replace("\\x2F", "/").replace("\\x26", "&"))


def _scan_text(text: str, found: list[tuple[str, str, str]], *, literals: bool, context: str) -> None:
    """Regular-expression strategies over raw text."""
    if literals:
        for match in _STRING_LITERAL.finditer(text):
            value = _unescape_script(match.group(1) or match.group(2) or "")
            if looks_like_address(value) and (value.startswith(("http", "/")) or _extension(value)):
                found.append(("script", context, value))
    for match in _MM_PATTERN.finditer(text):
        found.append(("motif-mm", context, _unescape_script(match.group(0))))
    for match in _FILE_PATTERN.finditer(text):
        found.append(("motif-fichier", context, _unescape_script(match.group(0))))
    for match in _IIIF_HINT.finditer(text):
        found.append(("iiif", context, _unescape_script(match.group(0))))


def extract(body: bytes, base_url: str, content_type: str | None = None) -> Extraction:
    """Apply every strategy to a body and return the candidates in order of first appearance."""
    kind = sniff(body, content_type)
    result = Extraction(kind=kind)
    if kind in ("image", "pdf", "binaire"):
        return result
    text = body.decode("utf-8", "replace")
    found: list[tuple[str, str, str]] = []
    if kind == "html":
        parser = _PageParser()
        try:
            parser.feed(text)
            parser.close()
        except (AssertionError, ValueError):       # html.parser on very broken markup
            pass
        found.extend(parser.found)
        for name, blob in parser.json_blobs:
            try:
                _walk_json(json.loads(blob), f"json#{name}", found)
            except ValueError:
                _scan_text(blob, found, literals=True, context=f"json#{name} (illisible)")
        for script in parser.scripts:
            _scan_text(script, found, literals=True, context="<script>")
        _scan_text(html.unescape(text), found, literals=False, context="texte brut")
        visible = " ".join(parser.text)
        lowered = text.lower()
        result.structure = {
            "titre": parser.title, "h1": parser.headings["h1"][:5], "h2": parser.headings["h2"][:12],
            "balises": {tag: parser.tags.get(tag, 0) for tag in ("img", "a", "form", "script", "iframe", "frame", "table",
                                                                 "canvas", "object", "embed", "video", "input", "li", "div")},
            "formulaires": [dict(form, champs=form["champs"][:20]) for form in parser.forms[:8]],
            "scripts": [strip_session(src) for src in parser.script_sources[:60]],
            "cadres": [strip_session(src) for src in parser.frames[:10]],
            "identifiants_html": parser.ids[:60],
            "classes_frequentes": [name for name, _count in sorted(parser.classes.items(), key=lambda item: -item[1])[:25]],
            "noscript": parser.noscript, "caracteres_visibles": len(visible), "texte_debut": visible[:700],
            "page_erreur": "sia - erreur" in lowered or "erreur 503" in lowered,
            "formulaire_de_connexion": 'type="password"' in lowered,
        }
    elif kind == "json":
        try:
            _walk_json(json.loads(text), "$", found)
        except ValueError:
            pass
        _scan_text(text, found, literals=False, context="texte brut")
        result.structure = {"caracteres": len(text)}
    else:                                           # javascript, xml, plain text
        _scan_text(text, found, literals=kind == "javascript", context=kind)
        result.structure = {"caracteres": len(text)}
        if kind == "javascript":
            result.structure["mots_cles"] = sorted({word for word in ("media", "visionneuse", "viewer", "galerie", "zoom",
                                                                      "iiif", "download", "diaporama", "vignette")
                                                    if word in text.lower()})
    host = (urllib.parse.urlsplit(base_url).hostname or "").lower()
    by_url: dict[str, Candidate] = {}
    for strategy, context, raw in found:
        raw = raw.strip()
        if not raw:
            continue
        try:
            absolute = strip_session(urllib.parse.urljoin(base_url, raw))
            parts = urllib.parse.urlsplit(absolute)
        except ValueError:
            continue
        if parts.scheme not in ("http", "https") or not parts.hostname:
            continue
        absolute = urllib.parse.urldefrag(absolute)[0]
        candidate = by_url.get(absolute)
        if candidate is None:
            candidate_kind, chrome = classify(absolute)
            candidate = Candidate(url=absolute, raw=raw, position=len(by_url), context=context, kind=candidate_kind,
                                  chrome=chrome, same_host=parts.hostname.lower() == host)
            by_url[absolute] = candidate
        if strategy not in candidate.strategies:
            candidate.strategies.append(strategy)
    result.candidates = list(by_url.values())
    seen: dict[str, None] = {}
    for match in _IDENTIFIER.finditer(text):
        seen.setdefault(match.group(0), None)
    result.identifiers = list(seen)[:500]
    return result


# ----------------------------------------------------------------------------- views and sizes

@dataclass
class View:
    """One page of a decree, possibly offered in several sizes."""

    key: str
    position: int
    variants: list[Candidate] = field(default_factory=list)

    def best(self) -> Candidate:
        return max(self.variants, key=lambda candidate: (size_rank(candidate.url), -candidate.position))

    def as_dict(self) -> dict:
        return {"cle": self.key, "position": self.position,
                "variantes": [{"url": c.url, "rang_taille": size_rank(c.url)} for c in self.variants]}


def size_rank(url: str) -> int:
    """Heuristic rank of the size a URL asks for (higher = larger). Documented guesses:

    IIIF ``full/full`` or ``full/max`` = 100, an explicit pixel width = its tenth capped at 95;
    a size word in the file name or in a query parameter (min 10 … medium 40 … max 90,
    original 100); a name without any size word = 60 (assumed to be the plain, full image:
    larger than "medium", smaller than an explicit "max").
    """
    parts = urllib.parse.urlsplit(url)
    iiif = metadonnees._IIIF.search(parts.path)
    if iiif:
        size = iiif["taille"].lstrip("^!")
        if size in ("full", "max"):
            return 100
        if size.startswith("pct:"):
            try:
                return max(1, min(99, int(float(size[4:]))))
            except ValueError:
                return 50
        width = size.split(",")[0]
        return max(1, min(95, int(width) // 10)) if width.isdigit() else 50
    name = metadonnees.decoder_nom(urllib.parse.unquote(parts.path.rsplit("/", 1)[-1]))
    if name.get("taille"):
        return name["taille"]["rang"]
    for key, values in urllib.parse.parse_qs(parts.query).items():
        if key.lower() in SIZE_PARAMETERS:
            for value in values:
                word = value.lower()
                if word in metadonnees.SIZE_WORDS:
                    return metadonnees.SIZE_WORDS[word]
                if word.isdigit():
                    return max(1, min(95, int(word) // 10))
    return 60


def view_key(url: str) -> str:
    """Identity of a view whatever its size: the URL without size word, size parameter or IIIF request."""
    parts = urllib.parse.urlsplit(url)
    iiif = metadonnees._IIIF.search(parts.path)
    if iiif:
        return parts.path[:iiif.start()] + "/" + iiif["identifiant"]
    directory, _slash, name = parts.path.rpartition("/")
    stem = metadonnees.decoder_nom(urllib.parse.unquote(name))["radical"]
    query = sorted((key, tuple(values)) for key, values in urllib.parse.parse_qs(parts.query).items()
                   if key.lower() not in SIZE_PARAMETERS)
    return f"{directory}/{stem}" + ("?" + urllib.parse.urlencode([(k, v[0]) for k, v in query]) if query else "")


def group_views(candidates: list[Candidate]) -> list[View]:
    """Group image candidates (archive material on the probed host) into views, in page order."""
    views: dict[str, View] = {}
    for candidate in sorted(candidates, key=lambda c: c.position):
        if candidate.kind != "image" or candidate.chrome or not candidate.same_host:
            continue
        key = view_key(candidate.url)
        if key not in views:
            views[key] = View(key=key, position=len(views))
        views[key].variants.append(candidate)
    return list(views.values())


def choose_views(views: list[View], count: int) -> list[View]:
    """The views worth downloading: the first one, then an inner one (the middle of the decree)."""
    if count <= 0 or not views:
        return []
    chosen = [views[0]]
    if count >= 2 and len(views) >= 2:
        chosen.append(views[len(views) // 2] if len(views) > 2 else views[1])
    return chosen[:count]


def follow_up_pages(extraction: Extraction, visited: set[str]) -> list[Candidate]:
    """Pages (viewer, IIIF description) worth one more request, best first."""
    pages = [c for c in extraction.candidates
             if c.kind in ("page", "iiif") and not c.chrome and c.same_host and c.url not in visited and viewer_score(c.url) >= MIN_VIEWER_SCORE]
    return sorted(pages, key=lambda c: (-(viewer_score(c.url) + (5 if c.kind == "iiif" else 0)), c.position))
