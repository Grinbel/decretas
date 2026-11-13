"""Checks of the produced files (`python3 -m decretas.bogga verifier`).

Without option, nothing is sent on the network: the four site files are read back and
checked for internal consistency, and the two notices known from earlier manual work are
looked up by their structure (page, leaf, date, issue, number of entries) — never by a
person's name, which this code does not carry.

With `--liens`, the reader's own page table of up to three volumes is requested from the
Internet Archive (one request per volume) to confirm that `…/page/n<leaf>` addresses the
same leaf as our index.
"""
from __future__ import annotations

import json
import re
import urllib.parse
from collections import Counter
from collections.abc import Callable
from pathlib import Path

from decretas import net
from decretas.bogga import catalogue, export, moisson, personnes, volume

RE_NOT_A_NAME = re.compile(r"Ministre|Garde\s+des\s+Sceaux|Gouverneur|^(?:Est|Sont)\s+(?:naturalis|r[ée]int)|^D[ée]part\w+\s+d|^L[ée]gion\s",
                           re.I)

# Notices found by hand in the earlier research (docs/research/sources-2026-11): structure only.
KNOWN_NOTICES = (
    {"annee": 1873, "page": 494, "feuille": 529, "date": "1873-05-08", "entrees": 37, "indigenes": 5,
     "derniere_feuille": 531, "livraison": None, "livraison_date": "1873-10-23",
     "lien": "https://archive.org/details/algeria_bulletinofficieldugouvernementgeneraldelalgerie_13_1873/page/n529/mode/1up"},
    {"annee": 1888, "page": 60, "feuille": 115, "date": "1887-11-21", "entrees": 27, "indigenes": 1,
     "derniere_feuille": 117, "livraison": 1104, "livraison_date": "1888-02-09",
     "lien": "https://archive.org/details/1922-t.-62/1888%20T.28/page/n115/mode/1up"},
)


class Checker:
    def __init__(self, say: Callable[[str], None]) -> None:
        self.say = say
        self.failures = 0

    def check(self, condition: bool, label: str) -> None:
        if condition:
            self.say(f"  ok     {label}")
        else:
            self.failures += 1
            self.say(f"  ÉCHEC  {label}")


def load_table(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as handle:
        data = json.load(handle)
    return [dict(zip(data["champs"], row)) for row in data["lignes"]]


def check_structure(checker: Checker, volumes: list[dict], decrees: list[dict], entries: list[dict], meta: dict) -> None:
    checker.check([d["id"] for d in decrees] == list(range(len(decrees))), "identifiants des décrets : 0, 1, 2 …")
    checker.check([e["id"] for e in entries] == list(range(len(entries))), "identifiants des entrées : 0, 1, 2 …")
    checker.check(all(0 <= d["volume"] < len(volumes) for d in decrees), "chaque décret renvoie à un volume")
    checker.check(all(0 <= e["decret"] < len(decrees) and decrees[e["decret"]]["volume"] == e["volume"] for e in entries),
                  "chaque entrée renvoie à un décret du même volume")
    checker.check(all(d["feuille"] <= e["feuille"] <= d["derniere_feuille"] + 1
                      for e in entries for d in [decrees[e["decret"]]]
                      if not e["drapeaux"] & personnes.F_NON_SEGMENTE),
                  "chaque entrée est sur une feuille de son décret")
    counted = Counter(e["decret"] for e in entries if not e["drapeaux"] & personnes.F_NON_SEGMENTE)
    checker.check(all(d["entrees"] == counted.get(d["id"], 0) for d in decrees), "le compte d'entrées de chaque décret est exact")
    checker.check(all(d["doublon_de"] is None or (d["doublon_de"] < d["id"] and decrees[d["doublon_de"]]["volume"] == d["volume"])
                      for d in decrees), "un décret republié renvoie à un décret antérieur du même volume")
    checker.check(all("{leaf}" in v["lien_page"] and v["lien_page"].startswith("https://archive.org/details/" + v["item"])
                      for v in volumes), "modèles de lien : forme vérifiée, identifiant copié")
    checker.check(all(d["date_etat"] in (0, 1, 2) and d["livraison_date_etat"] in (0, 1, 2) for d in decrees),
                  "états des dates dans {0, 1, 2}")
    dated = [(d["dates"], d["livraison_date"]) for d in decrees if d["livraison_date"] and d["date_etat"] != 2]
    checker.check(all(iso is None or iso <= issue for isos, issue in dated for iso in isos),
                  "aucune date de décret non suspecte n'est postérieure à sa livraison")
    for index, vol in enumerate(volumes):
        own = [d for d in decrees if d["volume"] == index and d["livraison_date"] and d["livraison_date_etat"] != 2]
        ordered = sorted(own, key=lambda d: d["feuille"])
        if not all(a["livraison_date"] <= b["livraison_date"] for a, b in zip(ordered, ordered[1:])):
            checker.check(False, f"{vol['annee']} : dates de livraison croissantes")
    for index, vol in enumerate(volumes):
        numbered = [d["livraison"] for d in sorted((d for d in decrees if d["volume"] == index), key=lambda d: d["feuille"])
                    if d["livraison"] is not None]
        if not all(a <= b for a, b in zip(numbered, numbered[1:])):
            checker.check(False, f"{vol['annee']} : numéros de livraison croissants")
    persons = [e for e in entries if not e["drapeaux"] & personnes.F_NON_SEGMENTE]
    checker.check(all(e["nom"] for e in persons), "chaque entrée de personne a un nom")
    checker.check(not any(RE_NOT_A_NAME.search(e["nom"]) for e in persons),
                  "aucun nom n'est un titre officiel ni un en-tête de liste")
    checker.check(all(e["nom"] == "" for e in entries if e["drapeaux"] & personnes.F_NON_SEGMENTE),
                  "les blocs non segmentés n'ont pas de nom")
    checker.check(not any(iso == "1865-07-14" for d in decrees for iso in d["dates"]),
                  "aucun décret n'est daté du sénatus-consulte lui-même (14 juillet 1865)")
    checker.check(all(iso is None or (len(iso) == 10 and str(vol_year - 22) <= iso[:4] <= str(vol_year))
                      for d in decrees for iso in d["dates"] for vol_year in [volumes[d["volume"]]["annee"]]),
                  "aucune date de décret n'est postérieure à l'année de son volume")
    years = [row["annee"] for row in meta["couverture"]]
    checker.check(years == list(range(catalogue.FIRST_YEAR, catalogue.LAST_YEAR + 1)), "couverture : une ligne par année 1861-1888")
    checker.check(all(page["lien"].startswith("https://archive.org/details/") for page in meta["pages_a_lire_a_la_main"]),
                  "chaque page à lire à la main a son lien")
    text = json.dumps([volumes, meta], ensure_ascii=False)
    checker.check("@" not in text, "aucune adresse électronique dans les fichiers volumes et meta")


def check_known_notices(checker: Checker, volumes: list[dict], decrees: list[dict], entries: list[dict]) -> None:
    indigene = personnes.M_INDIGENE | personnes.M_INDIGENE_ENTETE
    for notice in KNOWN_NOTICES:
        label = f"{notice['annee']} p. {notice['page']}"
        index = next((i for i, v in enumerate(volumes) if v["annee"] == notice["annee"]), None)
        if index is None:
            checker.check(False, f"{label} : volume absent")
            continue
        found = [d for d in decrees if d["volume"] == index and d["feuille"] == notice["feuille"]]
        if not found:
            checker.check(False, f"{label} : aucun décret à la feuille {notice['feuille']}")
            continue
        decree = found[0]
        own = [e for e in entries if e["decret"] == decree["id"] and not e["drapeaux"] & personnes.F_NON_SEGMENTE]
        link = volumes[index]["lien_page"].replace("{leaf}", str(decree["feuille"]))
        checker.check(decree["page"] == notice["page"], f"{label} : page imprimée {decree['page']}")
        checker.check(notice["date"] in decree["dates"], f"{label} : date du décret {decree['dates']}")
        checker.check(len(own) == notice["entrees"], f"{label} : {len(own)} entrées (attendu {notice['entrees']})")
        marked = sum(1 for e in own if e["marqueurs"] & indigene)
        checker.check(marked == notice["indigenes"], f"{label} : {marked} entrées marquées « indigène » (attendu {notice['indigenes']})")
        checker.check(decree["derniere_feuille"] == notice["derniere_feuille"], f"{label} : dernière feuille {decree['derniere_feuille']}")
        checker.check(decree["livraison_date"] == notice["livraison_date"], f"{label} : livraison du {decree['livraison_date']}")
        if notice["livraison"] is not None:
            checker.check(decree["livraison"] == notice["livraison"], f"{label} : livraison n° {decree['livraison']}")
        checker.check(link == notice["lien"], f"{label} : lien {link}")


def run(raw_root: Path, site_data: Path, say: Callable[[str], None] = print) -> int:
    paths = {name: site_data / f"bogga-{name}.json" for name in ("volumes", "decrets", "entrees", "meta")}
    absent = [str(path) for path in paths.values() if not path.exists()]
    if absent:
        say("fichiers absents : " + ", ".join(absent) + " — lancer d'abord « construire »")
        return 1
    volumes, decrees, entries = (load_table(paths[name]) for name in ("volumes", "decrets", "entrees"))
    with paths["meta"].open(encoding="utf-8") as handle:
        meta = json.load(handle)
    checker = Checker(say)
    say("structure des fichiers")
    check_structure(checker, volumes, decrees, entries, meta)
    say("notices témoins")
    check_known_notices(checker, volumes, decrees, entries)
    totals = meta["totaux"]
    say(f"totaux : {totals['decrets']} décrets, {totals['entrees']} entrées, {totals['entrees_marquees_indigene']} "
        f"marquées « indigène », {totals['pages_a_lire_a_la_main']} pages à lire à la main")
    say("aucun échec" if not checker.failures else f"{checker.failures} échec(s)")
    return 1 if checker.failures else 0


# ---------------------------------------------------------------- reader page table (network)
def reader_table_url(metadata: dict, item: str, doc: str) -> str:
    servers = metadata.get("workable_servers") or []
    directory = metadata.get("dir")
    if not servers or not isinstance(directory, str):
        raise moisson.HarvestError("notice sans « workable_servers » ou sans « dir »")
    return catalogue.READER_TABLE_URL.format(server=servers[0], item=urllib.parse.quote(item, safe=""),
                                             dir=directory, doc=urllib.parse.quote(doc, safe=""))


def parse_reader_table(body: bytes) -> list[int]:
    """Leaf number of each page of the reader, in reader order (index = the `n` of the address)."""
    text = body.decode("utf-8", errors="replace").strip()
    if not text.startswith("{"):
        text = text[text.index("(") + 1:text.rindex(")")]
    data = json.loads(text)
    spreads = data["data"]["brOptions"]["data"]
    return [int(page["leafNum"]) for spread in spreads for page in spread]


def check_links(raw_root: Path, build_dir: Path, client: net.PoliteClient, years: list[int],
                say: Callable[[str], None] = print) -> int:
    """Compare the reader's page table with our leaf index for a few volumes (one request each)."""
    results = export.read_link_checks(build_dir)
    failures = 0
    for year in years[:3]:
        vol = catalogue.volume_for(year)
        files = moisson.local_files(raw_root, vol) if vol else None
        metadata = moisson.load_metadata(raw_root, vol.item) if vol else None
        if vol is None or files is None or metadata is None or not files.complete:
            say(f"{year} : volume non téléchargé")
            failures += 1
            continue
        url = reader_table_url(metadata, vol.item, files.doc)
        try:
            answer = client.fetch(url, f"{vol.item}/_lecteur_{files.doc}.jsonp")
        except net.NetError as exc:
            say(f"{year} : {exc}")
            failures += 1
            if isinstance(exc, (net.Blocked, net.BudgetExhausted)):
                break
            continue
        if answer.dry_run:
            say(f"simulation   {url}")
            continue
        try:
            leaves = parse_reader_table(answer.read_bytes())
        except (ValueError, KeyError, TypeError) as exc:
            say(f"{year} : table du lecteur illisible ({type(exc).__name__})")
            failures += 1
            continue
        ours = len(volume.read_pageindex(files.pageindex))
        identity = leaves == list(range(len(leaves)))
        if identity and len(leaves) == ours:
            state = f"oui : la liseuse numérote ses {len(leaves)} pages comme notre index (contrôle du {_today()})"
        elif identity:
            state = f"partiel : numérotation identique mais {len(leaves)} pages dans la liseuse pour {ours} dans notre index"
            failures += 1
        else:
            shifted = sum(1 for index, leaf in enumerate(leaves) if index != leaf)
            state = f"non : {shifted} pages de la liseuse ne portent pas le numéro de notre index"
            failures += 1
        results[str(year)] = state
        say(f"{year} : {state}")
    if not client.dry_run:                  # a simulation writes nothing
        build_dir.mkdir(parents=True, exist_ok=True)
        with (build_dir / export.LINK_CHECKS_FILE).open("w", encoding="utf-8") as handle:
            json.dump(results, handle, ensure_ascii=False, indent=1, sort_keys=True)
    return 1 if failures else 0


def _today() -> str:
    import datetime

    return datetime.date.today().isoformat()
