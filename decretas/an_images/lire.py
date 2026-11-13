"""Transcription harness: a folder of decree page images -> name occurrences to be verified.

For every image a reader (see `lecteurs.py`) returns a transcription; the pages of one decree
are then parsed together (`transcription.py`) and each person, wife and child becomes one
row in the shape the name search engine takes as input::

    {id, nom, anneeNaissance, groupe: "an-images", ocr, …, decret, image, lecteur, confiance}

Text that the parser could not turn into persons is not thrown away: it becomes rows of role
``bloc`` (a piece of page text of at most 200 words, flagged ``texte-non-decoupe``), so that a
name written in a layout nobody has seen yet can still be found by the search engine. Three
triggers: lines of the list attached to nobody, a decree in which no person was recognised
(every page read is then given whole), and a paragraph far longer than one person takes.

The result is written to data/build/an-images/lectures.json — never to site/data: whether
machine readings are published is a later, separate decision.

Which decree an image belongs to comes from the ``decret.json`` the probe writes next to the
images it downloads, or from the ``--inventaire`` / ``--notice`` options (then the whole folder
is one decree, its images in natural name order). Unread images are listed with the reason;
a decree with an unread page is marked partial: an absence in its rows proves nothing.
"""
from __future__ import annotations

import datetime
import json
import re
from pathlib import Path

from . import lecteurs, metadonnees, transcription

FORMAT = "decretas-an-images-lectures/1"
GROUP = "an-images"
BLOCK_WORDS = 200          # the search engine reads at most 250 words of an occurrence
BLOCK_OVERLAP = 20
WARNING = ("Lectures de travail, non publiées. Chaque occurrence est un indice à vérifier sur l'image, jamais une "
           "citation. Un nom absent de ce fichier n'est pas absent du décret. Ne pas copier ce fichier sous site/data "
           "sans décision explicite.")


def natural_key(name: str) -> list:
    return [int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", name)]


def list_images(folder: Path) -> list[Path]:
    """Image files of a folder (not of its sub-folders), in natural name order."""
    return sorted((path for path in folder.iterdir()
                   if path.is_file() and path.suffix.lower() in metadonnees.IMAGE_SUFFIXES), key=lambda p: natural_key(p.name))


def group_by_decree(folder: Path, images: list[Path], inventory: str | None, notice: str | None) -> list[dict]:
    """[{inventaire, notice, images: [paths in view order]}]. A sidecar ``decret.json`` wins over the options."""
    sidecar = folder / "decret.json"
    known: dict = {}
    if sidecar.is_file():
        try:
            known = json.loads(sidecar.read_text(encoding="utf-8")).get("images", {})
        except (OSError, json.JSONDecodeError, AttributeError):
            known = {}
    groups: dict[tuple, dict] = {}
    for image in images:
        info = known.get(image.name) if isinstance(known, dict) else None
        key = (info.get("inventaire"), info.get("notice")) if isinstance(info, dict) else (inventory, notice)
        group = groups.setdefault(key, {"inventaire": key[0], "notice": key[1], "images": []})
        group["images"].append((info.get("vue") if isinstance(info, dict) and isinstance(info.get("vue"), int) else None, image))
    result = []
    for group in groups.values():
        ordered = sorted(group["images"], key=lambda item: (item[0] is None, item[0] or 0, natural_key(item[1].name)))
        result.append({"inventaire": group["inventaire"], "notice": group["notice"],
                       "images": [path for _view, path in ordered], "vues": [view for view, _path in ordered]})
    return result


def choose_readers(mode: str, config: Path | None, *, tesseract: lecteurs.TesseractReader | None = None) -> tuple[list, dict[str, str]]:
    """Readers to try, in order, for every image, and what each says about its availability.

    Raises `lecteurs.ReaderUnavailable` when the reader explicitly asked for cannot work.
    """
    manual = lecteurs.ManualReader()
    tesseract = tesseract or lecteurs.TesseractReader()
    notes: dict[str, str] = {}
    if mode == "manuel":
        notes["manuel"] = manual.available()[1]
        return [manual], notes
    if mode == "tesseract":
        ok, note = tesseract.available()
        notes["tesseract"] = note
        if not ok:
            raise lecteurs.ReaderUnavailable(note)
        return [tesseract], notes
    if mode == "commande":
        if config is None:
            raise lecteurs.ReaderUnavailable("Le lecteur « commande » demande un fichier de configuration : option --config "
                                             "(contrat décrit dans docs/decrets-en-images.md).")
        command = lecteurs.CommandReader.from_config(config)
        ok, note = command.available()
        notes[command.name] = note
        if not ok:
            raise lecteurs.ReaderUnavailable(note)
        return [command], notes
    if mode != "auto":
        raise lecteurs.ReaderUnavailable(f"Lecteur inconnu : {mode} (attendu : auto, manuel, tesseract ou commande).")
    readers: list = [manual]
    notes["manuel"] = manual.available()[1]
    ok, note = tesseract.available()
    notes["tesseract"] = note
    if ok:
        readers.append(tesseract)
    return readers, notes


def _rows_of(entry: dict, decree: dict, images: list[Path], readings: list[lecteurs.Reading], first_id: int) -> list[dict]:
    reading = readings[entry["page"]]
    common = {"groupe": GROUP, "ocr": reading.confidence == lecteurs.AUTOMATIC,
              "decret": f"{decree['inventaire']}/{decree['notice']}" if decree["inventaire"] and decree["notice"] else None,
              "inventaire": decree["inventaire"], "notice": decree["notice"], "date_decret": decree.get("date"),
              "image": images[entry["page"]].name, "vue": entry["page"] + 1, "lecteur": reading.reader,
              "confiance": reading.confidence, "dossier": entry["dossier"]}
    principal = dict(common, id=first_id, nom=entry["nom"], anneeNaissance=entry["annee"], role="principal", princ=first_id,
                     dossier_lu=entry["dossier_lu"], profession=entry["profession"], nom_epoux=entry.get("nom_epoux"),
                     naissance=entry["naissance"],
                     lieu=entry["lieu"], residence=entry["residence"], sceau=entry["sceau"], texte=entry["texte"],
                     drapeaux=entry["drapeaux"])
    rows = [principal]
    relatives = ([("epouse", entry["epouse"])] if entry["epouse"] else []) + [("enfant", child) for child in entry["enfants"]]
    for role, person in relatives:
        rows.append(dict(common, id=first_id + len(rows), nom=person["nom"], anneeNaissance=person["annee"], role=role,
                         princ=first_id, naissance=person["naissance"], lieu=person["lieu"], drapeaux=person["drapeaux"]))
    return rows


def blocks_of(text: str) -> list[str]:
    """Cut a text into pieces the search engine reads whole (it keeps 250 words per occurrence):
    at most `BLOCK_WORDS` words, two consecutive pieces sharing `BLOCK_OVERLAP` words so that a
    name is never cut in two by a boundary."""
    words = text.split()
    if len(words) <= BLOCK_WORDS:
        return [" ".join(words)] if words else []
    pieces = []
    start = 0
    while start < len(words):
        pieces.append(" ".join(words[start:start + BLOCK_WORDS]))
        if start + BLOCK_WORDS >= len(words):
            break
        start += BLOCK_WORDS - BLOCK_OVERLAP
    return pieces


def _block_rows(text: str, page: int, reason: str, decree: dict, images: list[Path], readings: list[lecteurs.Reading],
                first_id: int, partial: bool) -> list[dict]:
    reading = readings[page]
    rows = []
    for piece in blocks_of(text):
        rows.append({
            "id": first_id + len(rows), "nom": piece, "anneeNaissance": None, "groupe": GROUP,
            "ocr": reading.confidence == lecteurs.AUTOMATIC, "role": "bloc", "princ": None,
            "decret": f"{decree['inventaire']}/{decree['notice']}" if decree["inventaire"] and decree["notice"] else None,
            "inventaire": decree["inventaire"], "notice": decree["notice"], "date_decret": decree.get("date"),
            "image": images[page].name, "vue": page + 1, "lecteur": reading.reader, "confiance": reading.confidence,
            "dossier": None, "texte": piece,
            "drapeaux": ["texte-non-decoupe", reason] + (["decret-lu-partiellement"] if partial else [])})
    return rows


def read_folder(folder: Path, *, mode: str = "auto", config: Path | None = None, inventory: str | None = None,
                notice: str | None = None, date: str | None = None, tesseract: lecteurs.TesseractReader | None = None,
                now: datetime.datetime | None = None) -> dict:
    """Read every image of `folder` and return the readings document (see the module docstring)."""
    folder = Path(folder)
    readers, notes = choose_readers(mode, config, tesseract=tesseract)
    images = list_images(folder)
    year = int(date[:4]) if date and re.match(r"^\d{4}", date) else None
    document: dict = {"format": FORMAT, "genere_le": (now or datetime.datetime.now(datetime.timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                      "avertissement": WARNING, "groupe": GROUP, "dossier": str(folder), "lecteur_demande": mode,
                      "lecteurs": notes, "decrets": [], "occurrences": [], "non_lues": []}
    for decree in group_by_decree(folder, images, inventory, notice):
        decree["date"] = date
        readings: list[lecteurs.Reading] = []
        image_reports = []
        for image in decree["images"]:
            reading = None
            reasons = []
            for reader in readers:
                reading = reader.read(image)
                if reading.text:
                    break
                reasons.append(f"{reader.name} : {reading.error}")
            assert reading is not None
            report = {"fichier": image.name, "lecteur": reading.reader if reading.text else None,
                      "etat": "lue" if reading.text else "non-lue", "source": reading.source}
            if reading.text:
                report.update(caracteres=len(reading.text), lignes=len(reading.text.splitlines()), confiance=reading.confidence)
            else:
                report["raison"] = " ; ".join(reasons)
                document["non_lues"].append({"fichier": str(image), "raison": report["raison"]})
            readings.append(reading)
            image_reports.append(report)
        analysis = transcription.analyse_decree([reading.text or "" for reading in readings], year)
        unread = [report["fichier"] for report in image_reports if report["etat"] == "non-lue"]
        for entry in analysis["entrees"]:
            if unread:
                entry["drapeaux"].append("decret-lu-partiellement")
            document["occurrences"].extend(_rows_of(entry, decree, decree["images"], readings, len(document["occurrences"])))
            if "paragraphe-anormalement-long" in entry["drapeaux"]:
                document["occurrences"].extend(_block_rows(entry["texte"], entry["page"], "paragraphe-anormalement-long", decree,
                                                           decree["images"], readings, len(document["occurrences"]), bool(unread)))
        reason = "lignes-non-rattachees" if analysis["entrees"] else "aucune-personne-reconnue"
        for loose in analysis["non_rattache"]:
            document["occurrences"].extend(_block_rows(loose["texte"], loose["page"], reason, decree, decree["images"],
                                                       readings, len(document["occurrences"]), bool(unread)))
        document["decrets"].append({
            "decret": f"{decree['inventaire']}/{decree['notice']}" if decree["inventaire"] and decree["notice"] else None,
            "inventaire": decree["inventaire"], "notice": decree["notice"], "date": date, "images": image_reports,
            "lecture": "complète" if not unread else ("partielle" if len(unread) < len(image_reports) else "aucune"),
            "preambule": analysis["preambule"], "stats": analysis["stats"], "numeros_orphelins": analysis["numeros_orphelins"]})
    flags: dict[str, int] = {}
    for row in document["occurrences"]:
        for flag in row["drapeaux"]:
            flags[flag] = flags.get(flag, 0) + 1
    read_count = sum(1 for decree in document["decrets"] for image in decree["images"] if image["etat"] == "lue")
    document["bilan"] = {"images": len(images), "images_lues": read_count, "images_non_lues": len(images) - read_count,
                         "decrets": len(document["decrets"]), "occurrences": len(document["occurrences"]),
                         "principaux": sum(1 for row in document["occurrences"] if row["role"] == "principal"),
                         "blocs_de_texte": sum(1 for row in document["occurrences"] if row["role"] == "bloc"),
                         "drapeaux": dict(sorted(flags.items()))}
    return document


def write(document: dict, destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(document, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return destination
