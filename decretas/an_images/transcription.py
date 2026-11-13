"""From the transcription of decree pages to name occurrences.

The layout parsed here is the only one seen so far: the typewritten decrees of January,
February and December 1932 shown (as small screenshots) in the official indexing tutorial of
the Archives nationales —

    12345 X 31/  /NOM (Prénoms), profession, né le 6 juin 1885 à Ville (Pays),
                 demeurant à Ville (Département).
                 Remise totale.

one person per paragraph, the dossier number ("N X YY") in the left margin, a wife introduced
by « et NOM (Prénom), sa femme, née le … », children numbered « 1°) … 2°) … », and the
typewriter's capital I for the digit 1 and capital O for 0 inside numbers. Variations seen on
those screenshots, all accepted here: a pencil tick (« / ») after the number and before the
name; no comma between the parenthesis and the profession; months with a capital; « et »
alone on its line before the wife; one child per line without « ; », with several given names
separated by commas, and « d° » (ditto) for a place repeated from the child above; a married
woman written « NOM (Prénoms) femme MARI, née le … ».

Everything else is unknown until real pages are seen (1899-1912; admission decrees of
« indigènes », whose names may well be written without a parenthesis). The parser therefore
never drops what it does not understand: a paragraph that has a dossier number but no
recognisable name is kept with the flag ``forme-de-nom-non-reconnue``, every field keeps
the text it was read from, and the lines of the list that could not be attached to a person
come back under ``non_rattache`` (the harness turns them into searchable blocks of text, so
that a name written in an unknown layout is still found).

A transcription is a reading, not a source: the rows produced are *indices* to be verified
on the image.
"""
from __future__ import annotations

import re

MONTHS = {"janvier": 1, "février": 2, "fevrier": 2, "mars": 3, "avril": 4, "mai": 5, "juin": 6, "juillet": 7,
          "août": 8, "aout": 8, "septembre": 9, "octobre": 10, "novembre": 11, "décembre": 12, "decembre": 12}
STAMP_MONTHS = {"JANV": 1, "FEV": 2, "FÉV": 2, "FEVR": 2, "FÉVR": 2, "MARS": 3, "AVR": 4, "AVRIL": 4, "MAI": 5, "JUIN": 6,
                "JUIL": 7, "AOUT": 8, "AOÛT": 8, "SEPT": 9, "OCT": 10, "NOV": 11, "DEC": 12, "DÉC": 12}
_LOOKALIKES = str.maketrans({"I": "1", "l": "1", "|": "1", "O": "0", "o": "0"})
_NUM = r"[0-9IlO|]"
_UPPER = "A-ZÀ-ÖØ-Þ"

DOSSIER = re.compile(rf"(?<![A-Za-zÀ-ÿ0-9])(?P<n>{_NUM}{{1,6}})\s*(?P<bis>bis|ter)?\s*(?P<x>B\s?X|X|x|×)\s*(?P<yy>{_NUM}{{2}})(?![A-Za-zÀ-ÿ0-9])")
NAME = re.compile(rf"(?P<nom>[{_UPPER}][{_UPPER}' .\-]{{1,60}}?)\s*\((?P<prenoms>[^()]{{1,120}})\)")
_NAME_AT_START = re.compile(rf"^\s*(?P<nom>[{_UPPER}][{_UPPER}' .\-]{{1,60}}?)\s*\((?P<prenoms>[^()]{{1,120}})\)")
_MONTH_WORDS = "|".join(sorted(MONTHS, key=len, reverse=True))
BIRTH = re.compile(
    rf"\bn[ée]e?s?\s+(?:(?:le|présumée?|vers|en)\s+)*(?:(?P<jour>{_NUM}{{1,2}}|1er|Ier|ler)\s+)?(?:(?P<mois>{_MONTH_WORDS})\s+)?(?P<annee>{_NUM}{{4}})(?!{_NUM})",
    re.I)
_PLACE = re.compile(rf"\s+(?:à|au|aux|en)\s+(?P<lieu>.+?)(?=,\s*(?:y\s+demeurant|demeurant|domicilié|résidant|ayant|et\s+[{_UPPER}]{{2}}|sa\s+femme)|\s+demeurant|\s+ayant\b|\s+et\s+[{_UPPER}]{{2}}|\s*;|\.\s|\.$|$)", re.S)
RESIDENCE = re.compile(r"\bdemeurant\s+(?:(?:tous|toutes)\s+(?:les\s+)?(?:deux|trois)\s+|ensemble\s+)?(?:à|au|aux|en)\s+(?P<res>.+?)(?=\.\s|\.$|;|,?\s*ayant\b|$)", re.S)
SPOUSE = re.compile(rf"\bet\s+(?P<nom>[{_UPPER}][{_UPPER}' .\-]{{1,60}}?)\s*\((?P<prenoms>[^()]{{1,120}})\)\s*,?\s*(?:sa\s+femme|son\s+épouse)", re.S)
CHILDREN_MARK = re.compile(r"\bayant\s+(?:(?P<combien>[\w]+)\s+)?enfants?\s+mineure?s?\s*:?", re.I)
NUMBER_WORDS = {"un": 1, "une": 1, "deux": 2, "trois": 3, "quatre": 4, "cinq": 5, "six": 6, "sept": 7, "huit": 8, "neuf": 9,
                "dix": 10, "onze": 11, "douze": 12, "treize": 13, "quatorze": 14, "quinze": 15}
CHILD_MARK = re.compile(rf"(?<![A-Za-zÀ-ÿ0-9])(?:{_NUM}{{1,2}})\s*[°º]\s*\)?")
CHILD_BODY = re.compile(rf"\s*(?P<prenom>[{_UPPER}][^;()°º]{{0,80}}?)\s*,\s*(?P<suite>n[ée]e?\s.*)", re.S)
MARRIED_NAME = re.compile(rf"\s*,?\s*(?:femme|veuve|épouse)\s+(?P<mari>[{_UPPER}][{_UPPER}' .\-]{{1,60}}?)\s*(?=,|\bn[ée]e\b|$)")
DITTO = re.compile(r"^d\s*[°ºo]\.?$", re.I)
_TICK = re.compile(rf"^\s*[/\\|¦'`´‚,.\-–—]{{1,3}}\s*(?=[{_UPPER}])")
_NAME_OPENING = re.compile(rf"^\s*[{_UPPER}][{_UPPER}' .\-]{{1,60}}?\s*\([^()]*$")
SEAL = re.compile(r"^\s*(Remise\s+[^.]{2,80}\.?|Sans\s+remise\.?|Droits?\s+de\s+sceau[^.]{0,80}\.?)\s*$", re.I)
PAGE_NUMBER = re.compile(r"^[\s\-–—.]*\d{1,3}[\s\-–—.]*$")
CLOSING = re.compile(r"^\s*(Art(?:icle)?\.?\s*(?:2|II|3|deux)\b|Fait\s+à\s)", re.I)
STAMP = re.compile(rf"(?<![0-9A-Za-z])(?P<jour>{_NUM}{{1,2}})\s*(?P<mois>JANV|F[EÉ]VR?|MARS|AVR(?:IL)?|MAI|JUIN|JUIL|AO[UÛ]T|SEPT|OCT|NOV|D[EÉ]C)\.?\s*(?P<annee>{_NUM}{{4}})(?!{_NUM})")
GROUND = re.compile(r"\bSont\s+[^:]{10,400}:", re.S)
_BIRTH_WORD = re.compile(r"\bn[ée]e?\s+(?:le|en|vers|présumée?|à|au)\b", re.I)
LONG_PARAGRAPH_WORDS = 45        # one person of the 1932 layout takes about 20 words


def fix_digits(text: str) -> tuple[str, bool]:
    """Typewriter look-alikes -> digits. Returns (digits, was anything corrected?)."""
    fixed = text.translate(_LOOKALIKES)
    return fixed, fixed != text


def normalise_dossier(match: re.Match) -> tuple[str, bool]:
    """'8I02 X 3I' -> ('8102 X 31', True)."""
    number, changed_number = fix_digits(match["n"])
    year, changed_year = fix_digits(match["yy"])
    series = "BX" if "B" in match["x"].upper() else "X"
    middle = f" {match['bis']}" if match["bis"] else ""
    return f"{int(number)}{middle} {series} {year}", changed_number or changed_year


def strip_tick(text: str) -> str:
    """Remove the pencil tick (« / ») that the clerks put before a name: '/NOM (Prénom)' -> 'NOM (Prénom)'."""
    return _TICK.sub("", text, count=1)


def _dossier_at_start(line: str) -> re.Match | None:
    match = DOSSIER.match(line.lstrip())
    if not match:
        return None
    if not any(ch.isdigit() for ch in match["n"] + match["yy"]) and len(line.strip()) != len(match.group(0)):
        return None                     # letters only (e.g. "IO X II …") followed by text: too risky
    return match


def _looks_complete(paragraph: dict) -> bool:
    """Is this paragraph finished (final full stop, or its seal-duty line already read)?"""
    if paragraph.get("seal") or not paragraph["lines"]:
        return True
    last = paragraph["lines"][-1].rstrip()
    return last.endswith(".") and not re.search(r"\bet\s*$", last)


def _join(lines: list[str]) -> str:
    """Join the lines of a paragraph, undoing end-of-line hyphenation."""
    text = ""
    for line in lines:
        line = " ".join(line.split())
        if not line:
            continue
        if text.endswith("-") and line[:1].islower():
            text = text[:-1] + line
        else:
            text = (text + " " + line).strip()
    return text


def parse_birth(text: str, latest_year: int | None = None) -> dict:
    """Birth date and place from the part of a paragraph that concerns one person."""
    match = BIRTH.search(text)
    if not match:
        return {"annee": None, "drapeaux": ["naissance-non-lue"]}
    year_text, corrected = fix_digits(match["annee"])
    year = int(year_text)
    flags = ["chiffres-corriges"] if corrected else []
    result: dict = {"annee_lue": year, "texte": " ".join(match.group(0).split())}
    if match["mois"]:
        result["mois"] = MONTHS[match["mois"].lower()]
    if match["jour"]:
        day_text = match["jour"]
        day = 1 if day_text.lower() in ("1er", "ier", "ler") else int(fix_digits(day_text)[0])
        if 1 <= day <= 31:
            result["jour"] = day
    if not 1750 <= year <= (latest_year or 1962):
        flags.append("annee-invraisemblable")
        result["annee"] = None
    else:
        result["annee"] = year
    place = _PLACE.match(text, match.end())
    if place:
        result["lieu"] = " ".join(place["lieu"].split()).rstrip(",")
        result["texte"] += " à " + result["lieu"]
    result["drapeaux"] = flags
    return result


def _entry_from(paragraph: dict, latest_year: int | None) -> dict | None:
    text = _join(paragraph["lines"])
    flags: list[str] = list(paragraph["flags"])
    entry: dict = {"dossier": paragraph.get("dossier"), "dossier_lu": paragraph.get("dossier_lu"), "page": paragraph["page"],
                   "pages": sorted(set(paragraph["pages"])), "texte": text, "sceau": paragraph.get("seal"),
                   "epouse": None, "enfants": []}
    if len(entry["pages"]) > 1:
        flags.append("a-cheval-sur-deux-images")
    name = _NAME_AT_START.match(text)
    if name:
        entry.update(nom=f"{' '.join(name['nom'].split())} ({' '.join(name['prenoms'].split())})",
                     nom_famille=" ".join(name["nom"].split()), prenoms=" ".join(name["prenoms"].split()))
        rest = text[name.end():]
    else:
        if not entry["dossier"]:
            return None
        head = text.split(",", 1)[0].strip()
        if not head:
            return None
        entry.update(nom=head[:120], nom_famille=None, prenoms=None)
        flags.append("forme-de-nom-non-reconnue")
        rest = text[len(head):]
    spouse = SPOUSE.search(rest)
    children_mark = CHILDREN_MARK.search(rest)
    children_start = children_mark.end() if children_mark else None
    announced = NUMBER_WORDS.get((children_mark["combien"] or "").lower()) if children_mark else None
    entry["enfants_annonces"] = announced
    if children_mark is None:
        # the announcing words were not read, but « 1°) Prénom, né le … » is there all the same
        first = next((mark for mark in CHILD_MARK.finditer(rest) if CHILD_BODY.match(rest, mark.end())), None)
        if first:
            children_mark, children_start = first, first.start()
            flags.append("enfants-sans-annonce")
    own_end = min([m.start() for m in (spouse, children_mark) if m] or [len(rest)])
    own = rest[:own_end]
    profession = re.match(r"\s*,?\s*(?P<prof>[^,()]{2,80}?)\s*,\s*n[ée]e?\b", own)       # the first comma is not always typed
    entry["profession"] = " ".join(profession["prof"].split()) if profession else None
    married = MARRIED_NAME.match(own)
    entry["nom_epoux"] = " ".join(married["mari"].split()) if married else None      # « NOM (Prénoms), femme MARI, née le … »
    if married:
        entry["profession"] = None
    birth = parse_birth(own, latest_year)
    entry.update(annee=birth.get("annee"), annee_lue=birth.get("annee_lue"), naissance=birth.get("texte"), lieu=birth.get("lieu"))
    flags += birth["drapeaux"]
    residence = RESIDENCE.search(rest)
    entry["residence"] = " ".join(residence["res"].split()) if residence else None
    if not residence and re.search(r"\by\s+demeurant\b", own):
        entry["residence"] = entry["lieu"]                 # « y demeurant » : same place as the birth
    if spouse:
        spouse_end = children_mark.start() if children_mark and children_mark.start() > spouse.end() else len(rest)
        spouse_birth = parse_birth(rest[spouse.end():spouse_end], latest_year)
        entry["epouse"] = {"nom": f"{' '.join(spouse['nom'].split())} ({' '.join(spouse['prenoms'].split())})",
                           "annee": spouse_birth.get("annee"), "naissance": spouse_birth.get("texte"),
                           "lieu": spouse_birth.get("lieu"), "drapeaux": spouse_birth["drapeaux"]}
    if children_mark:
        tail = rest[children_start:]
        marks = list(CHILD_MARK.finditer(tail))
        previous_place = None
        unread = 0
        for index, mark in enumerate(marks):
            # one child = the text between its « n°) » and the next one (children are not always separated by « ; »)
            segment = tail[mark.end():marks[index + 1].start() if index + 1 < len(marks) else len(tail)]
            child = CHILD_BODY.match(segment)
            if not child:
                unread += 1
                continue
            child_birth = parse_birth(child["suite"], latest_year)
            child_flags = list(child_birth["drapeaux"])
            place = child_birth.get("lieu")
            if place and DITTO.match(place):
                place = previous_place                    # « d° » : the place of the child above
                child_flags.append("lieu-repris-de-la-ligne-precedente" if place else "lieu-idem-non-resolu")
            previous_place = place or previous_place
            entry["enfants"].append({"nom": " ".join(child["prenom"].split()).rstrip(","), "annee": child_birth.get("annee"),
                                     "naissance": child_birth.get("texte"), "lieu": place, "drapeaux": child_flags})
        if not entry["enfants"]:
            flags.append("enfants-annonces-non-lus")
        elif unread:
            flags.append("enfants-partiellement-lus")
        if announced is not None and entry["enfants"] and len(entry["enfants"]) != announced:
            # « ayant six enfants mineurs » but three read: the list goes on (next image?) or lines were lost
            flags.append("nombre-d-enfants-different-de-l-annonce")
    expected = LONG_PARAGRAPH_WORDS + (30 if entry["epouse"] else 0) + 15 * len(entry["enfants"])
    if len(text.split()) > expected:
        # far more text than one person takes in the known layout: other persons may be hidden in it
        flags.append("paragraphe-anormalement-long")
    entry["drapeaux"] = flags
    return entry


def analyse_decree(pages: list[str], latest_year: int | None = None) -> dict:
    """Parse the transcriptions of the pages of ONE decree, in page order.

    Returns {"preambule": {...}, "entrees": [...], "numeros_orphelins": [...], "stats": {...}}.
    `latest_year`: the year of the decree when known (a birth after it is flagged).
    """
    paragraphs: list[dict] = []
    preamble: list[str] = []
    preamble_pages: list[int] = []
    loose: list[tuple[int, str]] = []                   # lines of the list attached to nobody
    queue: list[tuple[str, str, bool, int]] = []        # dossier numbers read alone on a line
    queue_was_long = False
    current: dict | None = None
    closed = False
    ignored = 0
    for page_index, page in enumerate(pages):
        for line in page.splitlines():
            if not line.strip() or PAGE_NUMBER.match(line):
                continue
            if closed:
                ignored += 1
                continue
            if CLOSING.match(line) and paragraphs:
                closed = True
                current = None
                continue
            dossier = _dossier_at_start(line)
            remainder = strip_tick(line.lstrip()[dossier.end():].lstrip(" /\\|¦'`´‚")) if dossier else line
            if dossier and not remainder.strip():
                number, corrected = normalise_dossier(dossier)
                queue.append((number, dossier.group(0), corrected, page_index))
                queue_was_long = queue_was_long or len(queue) > 1
                if current is not None and current["lines"]:
                    current = None
                continue
            unticked = strip_tick(remainder)
            name = _NAME_AT_START.match(unticked)
            if name:
                remainder = unticked
            uncertain_start = False
            if dossier:
                starts = True
            elif name:
                # a capitalised word followed by a parenthesis also occurs inside a paragraph (a wife whose
                # "et" ended the previous line, a place typed in capitals): it starts a person only when
                # the previous paragraph is finished.
                # Exception: when the same line goes on with a birth ("…), profession, né le …") it IS a
                # person, even after an unfinished paragraph (a stray line, a lost full stop): a name is
                # never swallowed by the paragraph above it. That start is flagged.
                after = remainder[name.end():]
                is_wife = bool(re.match(r"\s*,?\s*(?:sa\s+femme|son\s+épouse)", after))
                complete = current is None or _looks_complete(current)
                starts = not is_wife and (complete or bool(_BIRTH_WORD.search(after)))
                uncertain_start = starts and not complete
            elif _NAME_OPENING.match(unticked) and current is not None and _looks_complete(current):
                # « NOM (Prénoms très longs » whose parenthesis closes on the next line, after a finished
                # paragraph: a person all the same
                remainder = unticked
                starts = True
            else:
                # text that follows a dossier number read alone on its line: a person whose name has
                # an unknown shape (kept, and flagged later)
                starts = current is None and bool(queue)
            if starts:
                current = {"lines": [remainder], "page": page_index, "pages": [page_index], "flags": [], "seal": None}
                if dossier:
                    number, corrected = normalise_dossier(dossier)
                    current.update(dossier=number, dossier_lu=" ".join(dossier.group(0).split()))
                    if corrected:
                        current["flags"].append("numero-de-dossier-corrige")
                elif queue:
                    number, raw, corrected, _page = queue.pop(0)
                    current.update(dossier=number, dossier_lu=" ".join(raw.split()))
                    if corrected:
                        current["flags"].append("numero-de-dossier-corrige")
                    if queue_was_long:
                        current["flags"].append("numero-apparie-par-rang")
                    if not queue:
                        queue_was_long = False
                else:
                    current["flags"].append("sans-numero-de-dossier")
                if uncertain_start:
                    current["flags"].append("debut-apres-paragraphe-inacheve")
                paragraphs.append(current)
                continue
            if current is None:
                if paragraphs:
                    loose.append((page_index, " ".join(line.split())))
                else:
                    preamble.append(line)
                    preamble_pages.append(page_index)
                continue
            seal = SEAL.match(line)
            if seal:
                current["seal"] = " ".join(seal.group(1).split())
                continue
            if current.get("seal"):
                # the seal-duty line closes a person in the known layout: what follows without
                # starting a person (a margin note, a line of an unknown shape) is attached to nobody
                loose.append((page_index, " ".join(line.split())))
                continue
            current["lines"].append(line)
            current["pages"].append(page_index)
    entries = [entry for entry in (_entry_from(paragraph, latest_year) for paragraph in paragraphs) if entry]
    header = "\n".join(preamble)
    stamp = STAMP.search(header)
    ground = GROUND.search(_join(preamble))
    preamble_info: dict = {"lignes": len(preamble)}
    if stamp:
        year = int(fix_digits(stamp["annee"])[0])
        day = int(fix_digits(stamp["jour"])[0])
        month = STAMP_MONTHS.get(stamp["mois"].upper())
        if month and 1 <= day <= 31 and 1800 <= year <= 1970:
            preamble_info["date_du_tampon"] = f"{year:04d}-{month:02d}-{day:02d}"
        preamble_info["tampon_lu"] = " ".join(stamp.group(0).split())
    if ground:
        preamble_info["fondement"] = fix_digit_runs(" ".join(ground.group(0).split()))
    flag_counts: dict[str, int] = {}
    for entry in entries:
        for flag in entry["drapeaux"]:
            flag_counts[flag] = flag_counts.get(flag, 0) + 1
    if not entries:
        # nothing recognised: the layout is not the one this parser knows. Every line read is
        # handed back, page by page, so that the harness can still make the text searchable.
        loose = [(page, " ".join(line.split())) for page, line in zip(preamble_pages, preamble)] + loose
    unattached: list[dict] = []
    for page_index, line in loose:
        if unattached and unattached[-1]["page"] == page_index:
            unattached[-1]["texte"] += " " + line
        else:
            unattached.append({"page": page_index, "texte": line})
    stats = {"pages": len(pages), "entrees": len(entries), "avec_numero_de_dossier": sum(1 for e in entries if e["dossier"]),
             "avec_annee_de_naissance": sum(1 for e in entries if e["annee"]), "epouses": sum(1 for e in entries if e["epouse"]),
             "enfants": sum(len(e["enfants"]) for e in entries), "lignes_non_rattachees": len(loose),
             "lignes_ignorees_apres_la_liste": ignored, "drapeaux": dict(sorted(flag_counts.items()))}
    return {"preambule": preamble_info, "entrees": entries, "stats": stats, "non_rattache": unattached,
            "numeros_orphelins": [number for number, _raw, _corrected, _page in queue]}


_DIGIT_RUN = re.compile(r"(?<![A-Za-zÀ-ÿ])(?=[0-9IlO|]*\d)[0-9IlO|]{2,}(?![A-Za-zÀ-ÿ])")


def fix_digit_runs(text: str) -> str:
    """Correct look-alikes inside tokens that contain at least one true digit ('I0 août I927' -> '10 août 1927';
    a token made of letters only, like 'II', is left alone)."""
    return _DIGIT_RUN.sub(lambda match: match.group(0).translate(_LOOKALIKES), text)
