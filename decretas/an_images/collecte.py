"""Size of a future collection of the image-only decrees (a plan, not a collector).

From the generated ``site/data/an-decrets.json`` this module counts the decrees of the
« palier Algérie » whose names are not keyed (state ``image``), per year and class, and turns
the count into requests and hours at one request every 10 seconds.

Two inputs are NOT known on 2026-11-11 and stay parameters until the probe measures them:

- the number of page images per decree (``pages_par_decret``);
- the number of requests needed to reach the images of one decree (``requetes_fixes``:
  landing page, viewer page…).

The collector itself is deliberately not written: its requests depend on the real structure
of the pages, which nobody has seen yet.

One indirect measure exists, and `media_anchors` computes it: four decrees of the XML exports
carry a media identifier whose number grows with the decree date. IF that number is a running
count of views over the whole sub-series (a hypothesis the probe must confirm), the difference
between two identifiers divided by the number of decrees dated between them is an average
number of views per decree. It is printed next to the provisional parameter, never used in
its place.
"""
from __future__ import annotations

import csv
import io
import json
import re
from pathlib import Path

CLASSES = ("A1", "A2", "A3", "R")
PERIODS = (("1899-1912", 1899, 1912), ("1928", 1928, 1928), ("1933-1948", 1933, 1948))
SENSITIVITY = (1, 2, 4, 6, 10, 20, 40)


class PlanError(Exception):
    """The input data cannot be used (French message)."""


def load_decrees(path: Path) -> list[dict]:
    """Decode the column file of the site into one dict per decree."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except OSError as error:
        raise PlanError(f"Fichier illisible : {path} ({error.strerror}). Le produire avec `python3 -m decretas.an construire`.") from error
    except json.JSONDecodeError as error:
        raise PlanError(f"Fichier {path} : JSON invalide ({error.msg}).") from error
    try:
        fields, tables = data["champs"], data["tables"]
        rows = []
        for line in data["lignes"]:
            row = dict(zip(fields, line))
            for name, table in tables.items():
                if name in row and isinstance(row[name], int):
                    row[name] = table[row[name]]
            rows.append(row)
    except (KeyError, TypeError, IndexError) as error:
        raise PlanError(f"Fichier {path} : ce n'est pas le format « decretas-an-decrets » attendu ({type(error).__name__}).") from error
    return rows


def parse_years(text: str | None) -> tuple[int, int] | None:
    if not text:
        return None
    first, _dash, last = text.partition("-")
    try:
        low, high = int(first), int(last or first)
    except ValueError as error:
        raise PlanError(f"Intervalle d'années incompris : « {text} » (attendu : 1899-1912 ou 1928).") from error
    if low > high:
        raise PlanError(f"Intervalle d'années à l'envers : « {text} ».")
    return low, high


def parse_classes(text: str | None) -> tuple[str, ...]:
    if not text:
        return CLASSES
    wanted = tuple(item.strip().upper() for item in text.split(",") if item.strip())
    unknown = [item for item in wanted if item not in CLASSES]
    if unknown:
        raise PlanError(f"Classe(s) inconnue(s) : {', '.join(unknown)} (attendu parmi {', '.join(CLASSES)}).")
    return wanted


def _duration(requests: int, delay: float) -> float:
    return requests * delay / 3600


MAJORITY = 21        # age required to ask for admission by decree (same rule as the site's guidance)


def compute(decrees: list[dict], *, years: tuple[int, int] | None = None, classes: tuple[str, ...] = CLASSES,
            pages_per_decree: int = 6, fixed_requests: int = 2, delay: float = 10.0, hours_per_day: float = 6.0,
            born: int | None = None) -> dict:
    """The collection plan as a dict (see `markdown` for its reading).

    `born`: birth year of the ancestor looked for; only the decrees dated from that year + 21
    are kept (the size of what a person has to read by hand for one ancestor).
    """
    if pages_per_decree < 1 or fixed_requests < 0 or delay <= 0 or hours_per_day <= 0:
        raise PlanError("Paramètres invalides : pages par décret ≥ 1, requêtes fixes ≥ 0, délai et heures par jour > 0.")
    if born is not None and not 1780 <= born <= 1941:
        raise PlanError(f"Année de naissance hors du champ : {born} (attendu entre 1780 et 1941).")
    selected = [row for row in decrees
                if row.get("etat") == "image" and row.get("classe") in classes
                and (years is None or years[0] <= int(row.get("annee") or 0) <= years[1])
                and (born is None or int(row.get("annee") or 0) >= born + MAJORITY)]
    selected.sort(key=lambda row: (row.get("annee") or 0, row.get("date") or "", str(row.get("inv")), str(row.get("notice"))))
    per_year: dict[int, dict[str, int]] = {}
    for row in selected:
        counts = per_year.setdefault(int(row["annee"]), {name: 0 for name in classes})
        counts[row["classe"]] += 1
    per_decree = fixed_requests + pages_per_decree

    def line(count: int) -> dict:
        requests = count * per_decree
        hours = _duration(requests, delay)
        return {"decrets": count, "requetes": requests, "heures": round(hours, 1), "jours": round(hours / hours_per_day, 1)}

    years_table = [dict({"annee": year, "classes": counts}, **line(sum(counts.values()))) for year, counts in sorted(per_year.items())]
    periods = []
    for label, low, high in PERIODS:
        count = sum(sum(counts.values()) for year, counts in per_year.items() if low <= year <= high)
        if count:
            periods.append(dict({"periode": label}, **line(count)))
    others = sum(sum(counts.values()) for year, counts in per_year.items() if not any(low <= year <= high for _l, low, high in PERIODS))
    if others:
        periods.append(dict({"periode": "autres années"}, **line(others)))
    total = len(selected)
    sensitivity = [{"pages_par_decret": pages, "requetes": total * (fixed_requests + pages),
                    "heures": round(_duration(total * (fixed_requests + pages), delay), 1),
                    "jours": round(_duration(total * (fixed_requests + pages), delay) / hours_per_day, 1)} for pages in SENSITIVITY]
    return {
        "format": "decretas-an-images-plan-collecte/1",
        "hypotheses": {"pages_par_decret": pages_per_decree, "requetes_fixes_par_decret": fixed_requests,
                       "delai_s": delay, "heures_par_jour": hours_per_day,
                       "note": "pages_par_decret et requetes_fixes_par_decret ne sont PAS mesurés : paramètres provisoires "
                               "jusqu'à la reprise."},
        "filtre": {"annees": list(years) if years else None, "classes": list(classes), "etat": "image", "ne_en": born,
                   "a_partir_de": born + MAJORITY if born is not None else None},
        "total": line(total), "par_classe": {name: sum(counts.get(name, 0) for counts in per_year.values()) for name in classes},
        "periodes": periods, "annees": years_table, "sensibilite": sensitivity,
        "decrets": [{"inv": row.get("inv"), "notice": row.get("notice"), "date": row.get("date"), "annee": row.get("annee"),
                     "classe": row.get("classe"), "famille": row.get("famille"), "cote": row.get("cote"),
                     "doc": row.get("doc"), "titre": row.get("titre")} for row in selected],
    }


_MEDIA_IN_LINK = re.compile(r"/siv/media/[^/]+/[^/]+/(?P<media>[A-Z]{3,}\d{0,4}_[A-Z]{2,}(?P<numero>\d{3,})_[A-Z]{1,3})/?$")
ANCHOR_HYPOTHESIS = ("HYPOTHÈSE non vérifiée : le numéro de l'identifiant de média est un compteur continu de vues sur toute "
                     "la sous-série, dans l'ordre des dates. Si c'est faux (compteur par lot, par liasse, ou qui compte "
                     "autre chose que des vues), ces moyennes ne valent rien. La reprise (étapes L1 à L4) tranche.")


def media_anchors(all_decrees_csv: Path) -> dict | None:
    """What the media identifiers written in the XML exports imply, from the flat list of ALL
    decrees (``python3 -m decretas.an decrets --csv …``). None when the file is absent or has
    fewer than two identifiers.

    Columns read: ``date``, ``inventaire``, ``notice_id``, ``cote``, ``personnes_indexees``,
    ``lien_images``. A decree counts in the interval [anchor date, next anchor date[.
    """
    try:
        with Path(all_decrees_csv).open(encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
    except (OSError, csv.Error, UnicodeDecodeError):
        return None
    anchors = []
    for row in rows:
        match = _MEDIA_IN_LINK.search(row.get("lien_images") or "")
        if match and re.fullmatch(r"\d{4}-\d{2}-\d{2}", row.get("date") or ""):
            anchors.append({"date": row["date"], "inventaire": row.get("inventaire"), "notice": row.get("notice_id"),
                            "cote": row.get("cote"), "media": match["media"], "numero": int(match["numero"])})
    anchors.sort(key=lambda anchor: (anchor["date"], anchor["numero"]))
    if len(anchors) < 2:
        return None
    dated = [row for row in rows if re.fullmatch(r"\d{4}-\d{2}-\d{2}", row.get("date") or "")]

    def persons(row: dict) -> int:
        value = row.get("personnes_indexees") or "0"
        return int(value) if value.isdigit() else 0

    intervals = []
    for first, second in zip(anchors, anchors[1:]):
        between = [row for row in dated if first["date"] <= row["date"] < second["date"]]
        gap = second["numero"] - first["numero"]
        keyed = sum(persons(row) for row in between)
        intervals.append({"du": first["date"], "au": second["date"], "ecart_numeros": gap, "decrets": len(between),
                          "personnes_saisies": keyed,
                          "numeros_par_decret": round(gap / len(between), 1) if between and gap > 0 else None,
                          "personnes_saisies_par_numero": round(keyed / gap, 1) if gap > 0 and keyed else None})
    span = [row for row in dated if anchors[0]["date"] <= row["date"] < anchors[-1]["date"]]
    total_gap = anchors[-1]["numero"] - anchors[0]["numero"]
    before = [row for row in dated if row["date"] < anchors[0]["date"]]
    return {
        "source": str(all_decrees_csv), "hypothese": ANCHOR_HYPOTHESIS, "reperes": anchors,
        "croissant_avec_la_date": all(a["numero"] < b["numero"] for a, b in zip(anchors, anchors[1:])),
        "intervalles": intervals,
        "ensemble": {"du": anchors[0]["date"], "au": anchors[-1]["date"], "ecart_numeros": total_gap, "decrets": len(span),
                     "numeros_par_decret": round(total_gap / len(span), 1) if span and total_gap > 0 else None},
        "avant_le_premier_repere": {"premiere_date": min((row["date"] for row in before), default=None), "decrets": len(before),
                                    "numero_du_premier_repere": anchors[0]["numero"],
                                    "numeros_par_decret_si_le_compteur_part_de_zero":
                                        round(anchors[0]["numero"] / len(before), 1) if before else None},
    }


def anchors_markdown(anchors: dict | None, source: Path) -> list[str]:
    out = ["## Ce que disent les quatre identifiants de média du XML", ""]
    if anchors is None:
        return out + [f"Non calculé : `{source}` est absent ou ne contient pas deux identifiants de média. Le produire avec "
                      "`python3 -m decretas.an decrets --csv data/build/an-decrets.csv` (`--csv` : fichier à écrire).", ""]
    out += [f"Source : `{anchors['source']}` (tous les décrets, toutes natures). **{anchors['hypothese']}**", "",
            "| Décret du | Inventaire / notice | Cote | Identifiant de média |", "|---|---|---|---|"]
    out += [f"| {a['date']} | {a['inventaire']} / {a['notice']} | {a['cote'] or '—'} | `{a['media']}` |" for a in anchors["reperes"]]
    out += ["", "Le numéro croît avec la date du décret : " + ("oui, sur ces repères." if anchors["croissant_avec_la_date"] else "NON — l'hypothèse tombe."), "",
            "| Entre | et | Écart des numéros | Décrets datés dans l'intervalle | Numéros par décret | Personnes saisies par numéro |",
            "|---|---|---:|---:|---:|---:|"]
    out += [f"| {i['du']} | {i['au']} | {_fr(i['ecart_numeros'])} | {_fr(i['decrets'])} | {_fr(i['numeros_par_decret']) if i['numeros_par_decret'] else '—'} | "
            f"{_fr(i['personnes_saisies_par_numero']) if i['personnes_saisies_par_numero'] else '—'} |" for i in anchors["intervalles"]]
    whole, before = anchors["ensemble"], anchors["avant_le_premier_repere"]
    out += ["", f"Sur l'ensemble ({whole['du']} → {whole['au']}) : {_fr(whole['ecart_numeros'])} numéros pour {_fr(whole['decrets'])} décrets, "
                f"soit **{_fr(whole['numeros_par_decret']) if whole['numeros_par_decret'] else '—'} numéros par décret en moyenne**."]
    if before["decrets"]:
        out.append(f"Recoupement : {_fr(before['decrets'])} décrets sont datés avant le premier repère (depuis le {before['premiere_date']}) "
                   f"et ce repère porte le numéro {_fr(before['numero_du_premier_repere'])} ; si le compteur part de zéro au début de la "
                   f"sous-série, cela fait {_fr(before['numeros_par_decret_si_le_compteur_part_de_zero'])} numéros par décret — même ordre de grandeur.")
    out += ["", "Lecture prudente : ces moyennes portent sur TOUS les décrets (naturalisations de métropole comprises), sur des "
                "années autres que celles à collecter, et reposent sur l'hypothèse ci-dessus. Elles disent seulement que le "
                "paramètre provisoire « images par décret » n'est pas absurde. Elles ne le remplacent pas. La colonne "
                "« personnes saisies par numéro » est minorée dès que l'intervalle contient des années dont les noms ne sont "
                "pas saisis (1899-1912).", ""]
    return out


def _fr(value) -> str:
    if isinstance(value, float):
        return f"{value:,.1f}".replace(",", " ").replace(".", ",")
    return f"{value:,}".replace(",", " ")


def markdown(result: dict, source: Path, anchors: dict | None = None, anchors_source: Path | None = None) -> str:
    hypotheses, total = result["hypotheses"], result["total"]
    classes = result["filtre"]["classes"]
    out = ["# Plan de collecte des décrets en images seules", "",
           f"Calculé à partir de `{source}` (décrets du palier Algérie dont aucun nom n'est saisi : état `image`).", "",
           "**Ceci est un calcul, pas un collecteur.** Le collecteur ne sera écrit qu'après la reprise "
           "(`python3 -m decretas.an_images reprise`), quand la structure réelle des pages sera connue.", "",
           "## Hypothèses (provisoires)", "",
           f"- **{hypotheses['pages_par_decret']} images par décret** — NON MESURÉ. Paramètre `--pages-par-decret`.",
           f"- **{hypotheses['requetes_fixes_par_decret']} requêtes fixes par décret** (page d'arrivée, visionneuse) — NON MESURÉ. "
           "Paramètre `--requetes-fixes`.",
           f"- 1 requête toutes les {_fr(hypotheses['delai_s'])} s ; {_fr(hypotheses['heures_par_jour'])} h de collecte par jour.",
           "- Le temps de réponse du site n'est pas compté (20 à 40 s par page les mauvais jours).", "",
           "## Total", "",
           *([f"Filtre : ancêtre né en {result['filtre']['ne_en']} — seuls les décrets datés de {result['filtre']['a_partir_de']} "
              f"ou après sont comptés (il fallait {MAJORITY} ans pour demander l'admission par décret). C'est la taille de la "
              "lecture à faire pour cet ancêtre, pas celle de la collecte entière.", ""] if result["filtre"].get("ne_en") else []),
           f"**{_fr(total['decrets'])} décrets** ; {_fr(total['requetes'])} requêtes ; {_fr(total['heures'])} heures, soit "
           f"{_fr(total['jours'])} jours de collecte.", "",
           "Par classe : " + ", ".join(f"{name} {_fr(count)}" for name, count in result["par_classe"].items()) + ".", "",
           "## Par période", "", "| Période | Décrets | Requêtes | Heures | Jours |", "|---|---:|---:|---:|---:|"]
    out += [f"| {p['periode']} | {_fr(p['decrets'])} | {_fr(p['requetes'])} | {_fr(p['heures'])} | {_fr(p['jours'])} |" for p in result["periodes"]]
    out += ["", "## Si le nombre d'images par décret est autre", "", "| Images par décret | Requêtes | Heures | Jours |", "|---:|---:|---:|---:|"]
    out += [f"| {s['pages_par_decret']} | {_fr(s['requetes'])} | {_fr(s['heures'])} | {_fr(s['jours'])} |" for s in result["sensibilite"]]
    out.append("")
    if anchors_source is not None:
        out += anchors_markdown(anchors, anchors_source)
    out += ["## Par année", "", "| Année | " + " | ".join(classes) + " | Décrets | Requêtes | Heures |",
            "|---|" + "---:|" * (len(classes) + 3)]
    out += [f"| {y['annee']} | " + " | ".join(_fr(y["classes"].get(name, 0)) for name in classes)
            + f" | {_fr(y['decrets'])} | {_fr(y['requetes'])} | {_fr(y['heures'])} |" for y in result["annees"]]
    out += ["", "Classes : A1 le titre nomme l'Algérie ; A2 « admission aux droits de citoyen français » sans territoire ; "
                "A3 décret composite incluant l'admission ; R rejet, révocation ou retrait.", ""]
    return "\n".join(out)


def decrees_csv(result: dict) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(["inv", "notice", "date", "annee", "classe", "famille", "cote", "doc", "titre"])
    for row in result["decrets"]:
        writer.writerow([row[key] if row[key] is not None else "" for key in ("inv", "notice", "date", "annee", "classe", "famille", "cote", "doc", "titre")])
    return buffer.getvalue()
