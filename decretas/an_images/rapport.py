"""The French report of the probe, written from what is on disk.

`write_report()` reads ``observations.json`` and ``manifest.jsonl`` of the probe cache and
answers, point by point, the questions the image-only decrees raise. Each point says either
what was observed (with the step and the saved file that carries it) or, plainly, that it was
not observed. Nothing is inferred beyond the comparisons spelled out in the text.

The report is written under data/build/ (git-ignored): it may quote page titles that name
persons.
"""
from __future__ import annotations

import datetime
import json
from collections.abc import Sequence
from pathlib import Path

from . import metadonnees, plan
from .reprise import load_json

NOT_SEEN = "**Non observé.**"


def _cell(value) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _table(header: tuple[str, ...], rows: list[tuple]) -> list[str]:
    lines = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    lines += ["| " + " | ".join(_cell(cell) for cell in row) + " |" for row in rows]
    return lines


def _hops_text(hops: list[dict]) -> str:
    parts = []
    for hop in hops:
        status = hop.get("statut")
        text = "non demandé" if status is None else ("aucune réponse" if status == 0 else str(status))
        if hop.get("location"):
            text += " → `" + hop["location"] + "`"
        if hop.get("temoins_poses"):
            text += " (pose " + ", ".join(cookie.split("=")[0] for cookie in hop["temoins_poses"]) + ")"
        if hop.get("note"):
            text += " — " + hop["note"]
        parts.append(text)
    return " ; puis ".join(parts) if parts else "—"


STATE_LABELS = {
    "ok": "réponse 2xx", "non-atteinte": "non atteinte (plan interrompu avant)", "interrompue": "interrompue par un échec",
    "plafond": "interrompue par le plafond de requêtes", "refus": "REFUS du site", "hors-hote": "renvoie vers un autre hôte",
    "inachevee": "inachevée", "trop-de-redirections": "trop de redirections", "en-cours": "inachevée",
    "non-lancee": "non lancée",
}


def _state(step: dict) -> str:
    state = step.get("etat", "?")
    if state.startswith("http-"):
        return "HTTP " + state[5:]
    return STATE_LABELS.get(state, state)


def _view_names(step: dict) -> list[str]:
    return [view["cle"].rsplit("/", 1)[-1] for view in step.get("vues", [])]


def _lot_verdict(identifier: str, step: dict) -> str | None:
    """For a link that carries a media identifier (…/DAFANCH94_NUMJ011088_D): how that identifier
    relates to the views found on the page. None when the link carries no identifier."""
    media = metadonnees.decoder_url(str(step.get("url", ""))).get("media")
    if not media or media.get("forme") != "lot-de-numerisation":
        return None
    name, number = media["radical"], media["numero"]
    head = f"- {identifier} : le lien porte `{name}` (numéro {number}). "
    names = _view_names(step)
    if step.get("etat") != "ok":
        return head + "Étape sans réponse 2xx : rien à comparer."
    seen_in_text = name in ((step.get("extraction") or {}).get("identifiants_de_media") or [])
    tail = " L'identifiant figure aussi dans le texte de la page." if seen_in_text else " L'identifiant ne figure pas dans le texte de la page."
    if not names:
        return head + "Aucune vue relevée sur la page d'arrivée : rien à comparer." + tail
    decoded = [metadonnees.decoder_nom(view) for view in names]
    numbers = [item.get("numero") for item in decoded if item.get("numero") is not None]
    if name in names:
        return head + (f"C'est exactement le nom de la vue n° {names.index(name) + 1} sur {len(names)} : « {media['suffixe']} » "
                       "désignerait un fichier, pas un lot.") + tail
    if all(view.startswith(name) for view in names):
        return head + (f"Les {len(names)} vues ont un nom qui commence par cet identifiant : il désignerait un lot de vues "
                       "(un dossier), les vues étant numérotées à l'intérieur.") + tail
    if numbers and min(numbers) <= number <= max(numbers):
        return head + (f"Son numéro est dans l'intervalle des numéros des vues ({min(numbers)} à {max(numbers)}) sous un autre "
                       "suffixe : même compteur, autre nature de fichier — à regarder de près.") + tail
    if numbers:
        return head + (f"Les vues portent d'autres numéros ({min(numbers)} à {max(numbers)}) : aucun rapport direct visible ; "
                       "l'hypothèse d'un compteur continu de vues n'est pas confirmée par cette page.") + tail
    return head + f"Les {len(names)} vues ont des noms d'une autre forme (`{names[0]}`…) : aucun rapport visible." + tail


def _person_link_verdict(person: dict | None, decree: dict | None) -> list[str]:
    """The central question: exact page or whole decree?"""
    if not person or not decree or person.get("etat") != "ok" or decree.get("etat") != "ok":
        return [NOT_SEEN + " Il faut les deux étapes P2 (lien de la personne) et P3 (lien de son décret) en réponse 2xx."]
    mine, whole = [view["cle"] for view in person.get("vues", [])], [view["cle"] for view in decree.get("vues", [])]
    lines = [f"- Lien de la personne (P2) : {len(mine)} vue(s) ; adresse finale `{(person.get('sauts') or [{}])[-1].get('url', '?')}`.",
             f"- Lien du décret (P3) : {len(whole)} vue(s) ; adresse finale `{(decree.get('sauts') or [{}])[-1].get('url', '?')}`."]
    if not mine or not whole:
        lines.append("- **Indéterminé** : au moins une des deux pages n'a livré aucune adresse d'image aux stratégies "
                     "génériques. Lire les deux corps enregistrés avant de conclure.")
    elif mine == whole and len(whole) > 1:
        lines.append(f"- **Tout le décret.** Les deux liens donnent les mêmes {len(whole)} vues, dans le même ordre : le lien "
                     "d'une personne n'isole pas sa page. Le guidage doit dire « parcourez le décret ».")
    elif mine == whole:
        lines.append("- **Indécidable sur cet exemplaire** : le décret n'a qu'une vue. Refaire la comparaison sur un décret "
                     "de plusieurs pages (option `--suivre`).")
    elif set(mine) < set(whole):
        ranks = [whole.index(key) + 1 for key in mine]
        lines.append(f"- **Page(s) précise(s).** Le lien de la personne donne {len(mine)} vue(s) sur les {len(whole)} du "
                     f"décret : vue(s) n° {', '.join(map(str, ranks))}. Le guidage peut dire « vue n° … ».")
    else:
        lines.append("- **Ensembles différents** : les vues de la personne ne sont pas un sous-ensemble de celles du décret. "
                     "À examiner à la main (les noms figurent au § 3).")
    lines.append("- Preuve : comparaison des clés de vues relevées dans les deux pages (adresse sans suffixe de taille).")
    return lines


def _manifest_rows(path: Path) -> list[dict]:
    rows = []
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict):
                rows.append(row)
    return rows


def write_report(root: Path, destination: Path, *, now: float | None = None, planned: Sequence[plan.Step] = (),
                 availability: Path | None = None) -> Path:
    """Write the Markdown report and return its path.

    `planned`: the steps of the plan; those never launched are listed as such, so that the
    report always shows the whole plan. `availability`: the folder of the availability checks,
    whose log is recalled in § 0.
    """
    observations = load_json(root / "observations.json", {})
    state = load_json(root / "etat.json", {})
    steps: dict[str, dict] = dict(observations.get("etapes", {}))
    base = observations.get("base", plan.BASE)
    for step in planned:
        steps.setdefault(step.id, {"id": step.id, "cas": step.case, "genre": step.kind, "question": step.question,
                                   "palier": step.tier, "url": step.url(base), "etat": "non-lancee", "sauts": [],
                                   "images": [], "suivis": [], "notes": []})
    order = [identifier for identifier in observations.get("ordre", []) if identifier in steps]
    order += [identifier for identifier in steps if identifier not in order]
    stamp = datetime.datetime.fromtimestamp(now) if now is not None else datetime.datetime.now()
    sent = [row for row in _manifest_rows(root / "manifest.jsonl") if row.get("network", True)]
    checks = [row for row in _manifest_rows(availability / "manifest.jsonl") if row.get("network", True)] if availability else []
    done = [identifier for identifier in order if steps[identifier].get("etat") == "ok"]
    out: list[str] = []
    out += ["# Décrets en images : rapport de la reprise", "",
            f"Écrit le {stamp.strftime('%Y-%m-%d à %H:%M')} par `python3 -m decretas.an_images reprise`. "
            f"Hôte interrogé : `{observations.get('base', plan.BASE)}`.", "",
            "Ce rapport ne dit que ce que les réponses enregistrées montrent. Chaque point porte l'étape (L1, P2…) et le "
            "fichier qui le prouve, sous `" + str(root) + "/`. Un point sans réponse est marqué « Non observé ».", ""]
    out += ["## 0. État", ""]
    out.append(f"- Requêtes envoyées (tous passages) : {len(sent)}. Étapes en réponse 2xx : {len(done)} sur {len(order)}.")
    for run in observations.get("passages", [])[-6:]:
        out.append(f"- Passage du {run.get('a')} : {run.get('requetes')} requête(s), code de sortie {run.get('code')} — {run.get('message')}")
    if state.get("blocage"):
        out.append(f"- **Refus enregistré** : {state['blocage']}. Aucune reprise sans décision humaine.")
    if state.get("arret_du_jour"):
        out.append(f"- Arrêt pour la journée du {state['arret_du_jour']} (trois échecs).")
    failures = state.get("echecs", [])
    if failures:
        out.append("- Échecs : " + " ; ".join(f"{f.get('a')} étape {f.get('etape')} "
                                              f"({'HTTP ' + str(f['statut']) if f.get('statut') else 'aucune réponse'})" for f in failures[-9:]))
    for sentence in observations.get("non_planifie", []):
        out.append(f"- Non planifié : {sentence}")
    if checks:
        out.append("- Vérifications de disponibilité (une requête chacune, heure UTC) : "
                   + " ; ".join(f"{str(row.get('at', '?'))[:16].replace('T', ' ')} → "
                                + (f"HTTP {row.get('status')}" if row.get("status") else "aucune réponse") for row in checks[-12:]) + ".")
    if not sent:
        out += ["", "**Aucune requête du plan n'a encore été envoyée : tout ce qui suit est « Non observé ».** Relancer "
                    "`python3 -m decretas.an_images reprise` quand `python3 -m decretas.an_images disponibilite` annonce "
                    "le retour du site (marche à suivre : `docs/decrets-en-images.md`)."]
    out.append("")

    # ---- 1. redirect chains
    out += ["## 1. Chaînes de redirection", ""]
    rows = [(identifier, steps[identifier].get("cas", ""), "`" + str(steps[identifier].get("url", "")) + "`",
             _hops_text(steps[identifier].get("sauts", [])), _state(steps[identifier])) for identifier in order]
    out += _table(("Étape", "Cas", "Adresse de départ", "Réponses, saut par saut", "État"), rows) if rows else [NOT_SEEN]
    cookies = sorted({cookie.split(";")[0] for identifier in order for hop in steps[identifier].get("sauts", [])
                      for cookie in hop.get("temoins_poses") or []})
    out += ["", "Témoins de session posés par le site (valeur masquée) : " + (", ".join(f"`{c}`" for c in cookies) if cookies else "aucun observé") + ".", ""]

    # ---- 2. landing pages
    out += ["## 2. Structure des pages d'arrivée", ""]
    described = 0
    for identifier in order:
        step = steps[identifier]
        found = step.get("extraction")
        if not found:
            continue
        described += 1
        structure = found.get("structure", {})
        body = step.get("corps", {})
        out.append(f"### {identifier} — {plan.CASES.get(step.get('cas'), step.get('cas'))}")
        out.append("")
        out.append(f"- Question : {step.get('question')}")
        out.append(f"- Corps : {body.get('genre')} de {body.get('octets')} octets, fichier `{body.get('fichier')}` ; état : {_state(step)}.")
        if structure.get("titre") is not None:
            out.append(f"- Titre : « {structure.get('titre')} » ; h1 : {structure.get('h1') or '—'} ; h2 : {structure.get('h2') or '—'}.")
            tags = structure.get("balises", {})
            out.append("- Balises : " + ", ".join(f"{name} {count}" for name, count in tags.items() if count) + ".")
            forms = structure.get("formulaires", [])
            if forms:
                out.append("- Formulaires : " + " ; ".join(f"{form.get('methode', '?').upper()} `{form.get('action')}` "
                                                         f"({len(form.get('champs', []))} champs)" for form in forms[:6]) + ".")
            if structure.get("cadres"):
                out.append("- Cadres (iframe) : " + ", ".join(f"`{src}`" for src in structure["cadres"]) + ".")
            flags = [label for key, label in (("page_erreur", "page d'erreur du site"), ("noscript", "bloc noscript"),
                                              ("formulaire_de_connexion", "formulaire de connexion présent")) if structure.get(key)]
            if flags:
                out.append("- Signes : " + ", ".join(flags) + ".")
            if structure.get("texte_debut"):
                out.append(f"- Début du texte visible : « {structure['texte_debut'][:400]} »")
        if structure.get("mots_cles"):
            out.append("- Mots-clés du script : " + ", ".join(structure["mots_cles"]) + ".")
        out.append("- Ce que chaque stratégie a trouvé : " + (", ".join(f"{name} {count}" for name, count in found.get("strategies", {}).items()) or "rien") + f" ; {found.get('habillage', 0)} adresse(s) d'habillage écartée(s).")
        if found.get("identifiants_de_media"):
            out.append("- Identifiants de média vus dans le texte : " + ", ".join(f"`{name}`" for name in found["identifiants_de_media"][:12])
                       + (" …" if len(found["identifiants_de_media"]) > 12 else "") + ".")
        if found.get("pages_possibles"):
            out.append("- Pages qui pourraient mener aux images : " + ", ".join(f"`{page['url']}`" for page in found["pages_possibles"][:5]) + ".")
        if found.get("hors_hote"):
            out.append("- Images ou descriptions sur un AUTRE hôte (non demandées) : " + ", ".join(f"`{url}`" for url in found["hors_hote"][:5]) + ".")
        for follow in step.get("suivis", []):
            out.append(f"- Page suivie : `{follow.get('url')}` ({follow.get('raison')}) → {_hops_text(follow.get('sauts', []))}.")
        for note in step.get("notes", []):
            out.append(f"- Note : {note}.")
        out.append("")
    if not described:
        out += [NOT_SEEN + " Aucune page n'a été reçue.", ""]

    # ---- 3. names and order
    out += ["## 3. Noms et ordre des images", ""]
    image_steps = [identifier for identifier in order if steps[identifier].get("genre") == "images" and steps[identifier].get("vues")]
    if image_steps:
        rows = []
        for identifier in image_steps:
            step = steps[identifier]
            names = _view_names(step)
            sequence = step.get("suite_des_noms") or {}
            rows.append((identifier, "/".join(step.get("decret") or ["?"]), len(names), f"`{names[0]}`", f"`{names[-1]}`",
                         sequence.get("conclusion", "—")))
        out += _table(("Étape", "Décret", "Vues", "Premier nom", "Dernier nom", "Ce que dit la suite des noms"), rows)
        out += ["", "Les noms sont les adresses trouvées, privées de leur suffixe de taille, dans l'ordre de la page. "
                    "« Le nom donne l'ordre » n'est établi que si le nombre variable croît de 1 en 1 ; l'ordre réel des pages "
                    "reste à confirmer à l'œil sur les images téléchargées (§ 6).", "",
                "À comparer aux quatre identifiants du XML : `DAFANCH94_NUMJ011088_D` (décembre 1889), `…014520_D` "
                "(janvier 1891), `…023847_D` (mai 1896), `…064396_D` (mars 1927).", ""]
    else:
        out += [NOT_SEEN + " Aucune liste de vues n'a été relevée.", ""]
    lots = [verdict for verdict in (_lot_verdict(identifier, steps[identifier]) for identifier in order) if verdict]
    if lots:
        out += ["Que désigne l'identifiant écrit dans quatre liens du XML (« …_D ») ?", "", *lots, "",
                "Si ces quatre comparaisons concordent, l'hypothèse du compteur continu (voir `plan-collecte.md`) est "
                "confirmée ou écartée ; si elles divergent, ne rien conclure.", ""]

    # ---- 4. person link
    out += ["## 4. Le lien d'images d'une personne ouvre-t-il sa page, ou tout le décret ?", ""]
    out += _person_link_verdict(steps.get("P2"), steps.get("P3"))
    out.append("")

    # ---- 5. sizes
    out += ["## 5. Tailles offertes", ""]
    any_size = False
    for identifier in image_steps:
        step = steps[identifier]
        variants = step["vues"][0].get("variantes", [])
        if not variants:
            continue
        any_size = True
        out.append(f"- {identifier}, première vue : " + " ; ".join(f"`{v['url'].rsplit('/', 1)[-1]}` (rang {v['rang_taille']})" for v in variants[:8]) + ".")
    downloaded = [(identifier, image) for identifier in order for image in steps[identifier].get("images", [])]
    if downloaded:
        any_size = True
        rows = []
        for identifier, image in downloaded:
            card = image.get("fiche", {})
            density = card.get("densite")
            rows.append((identifier, f"{image.get('vue')}/{image.get('vues_du_decret')}", f"`{Path(str(image.get('fichier'))).name}`",
                         card.get("format"), f"{card.get('largeur')} × {card.get('hauteur')}",
                         f"{density['x']} {density['unite']}" if density else "—", card.get("octets"), card.get("qualite_estimee", "—")))
        out += ["", *_table(("Étape", "Vue", "Fichier", "Format", "Pixels", "Densité", "Octets", "Qualité JPEG estimée"), rows)]
    if any_size:
        out += ["", "Le « rang » est une heuristique sur le nom (min 10, medium 40, sans suffixe 60, max 90, IIIF full 100) : "
                    "c'est la variante de rang le plus élevé qui a été téléchargée. Si une taille supérieure existe sous une "
                    "adresse que la page ne cite pas, cet outil ne la devine pas.", ""]
    else:
        out += [NOT_SEEN, ""]

    # ---- 6. image metadata
    out += ["## 6. Métadonnées des images téléchargées", ""]
    if downloaded:
        for identifier, image in downloaded:
            card = image.get("fiche", {})
            exif = (card.get("exif") or {}).get("ifd0", {})
            technical = [f"{name} = {exif[name]}" for name in ("Make", "Model", "Software", "DateTime") if exif.get(name)]
            free = card.get("texte_libre", [])
            out.append(f"- {identifier}, `{image.get('fichier')}` : {card.get('format')}, {card.get('largeur')} × {card.get('hauteur')} px ; "
                       + ("EXIF : " + " ; ".join(technical) if technical else "pas de champ EXIF notable")
                       + " ; XMP " + ("présent" if card.get("xmp") else "absent") + " ; IPTC " + ("présent" if card.get("iptc") else "absent")
                       + " ; texte libre : " + (" ; ".join(f"{item['source']} {item['champ']} = « {item['valeur'][:120]} »" for item in free) if free else "aucun") + ".")
        total_free = sum(len(image.get("fiche", {}).get("texte_libre", [])) for _identifier, image in downloaded)
        out += ["", ("**Des champs de texte libre existent : les lire ci-dessus, ils peuvent porter une cote ou une légende.**"
                     if total_free else
                     "**Aucun champ de texte libre dans ces images : leurs métadonnées sont techniques. Le nom d'une personne ne "
                     "peut venir que de la lecture de l'image.**"),
                "Détail complet : `python3 -m decretas.an_images metadonnees " + str(root / "images") + "/*/*`.", "",
                "Manuscrit ou dactylographié ? Cet outil ne juge pas l'écriture : ouvrir les fichiers ci-dessus et le constater "
                "à l'œil (c'est ce qui décide entre reconnaissance de caractères et reconnaissance d'écriture manuscrite).", ""]
    else:
        out += [NOT_SEEN + " Aucune image de décret n'a été téléchargée.", ""]

    # ---- 7. complements
    out += ["## 7. Compléments (palier 2)", ""]
    second = [identifier for identifier in order if steps[identifier].get("palier") == 2]
    if second:
        rows = []
        for identifier in second:
            step = steps[identifier]
            structure = (step.get("extraction") or {}).get("structure", {})
            comparison = step.get("comparaison_locale")
            note = structure.get("titre") or ""
            if comparison:
                note = (f"identique à la copie locale ({comparison['octets_locaux']} octets)" if comparison["identique"] else
                        f"DIFFÈRE de la copie locale : {comparison['octets_recus']} octets reçus contre {comparison['octets_locaux']}")
            rows.append((identifier, step.get("question", ""), _state(step), note))
        out += _table(("Étape", "Question", "État", "Titre de la page ou comparaison"), rows)
    else:
        out.append("Aucune étape du palier 2 dans ce plan.")
    out.append("")

    # ---- 8. unknown
    out += ["## 8. Ce qui reste inconnu", ""]
    pending = [identifier for identifier in order if steps[identifier].get("etat") != "ok"]
    out.append("- Étapes sans réponse 2xx : " + (", ".join(f"{identifier} ({_state(steps[identifier])})" for identifier in pending) if pending else "aucune") + ".")
    out += ["- Tout ce que les stratégies génériques n'ont pas su lire dans une page reçue : le corps est enregistré, le lire "
            "et relancer avec `--suivre CAS=ADRESSE`.",
            "- L'écriture des pages (manuscrite, dactylographiée, imprimée) : à constater à l'œil sur les images.",
            "- Le rendu dans un navigateur (JavaScript exécuté) : cet outil lit le HTML reçu, il n'exécute rien.", ""]

    # ---- 9. log
    out += ["## 9. Journal des requêtes", ""]
    if sent:
        rows = [(row.get("at", ""), row.get("status"), row.get("bytes"), row.get("elapsed_ms", ""), "`" + str(row.get("url", "")).split(";jsessionid=")[0] + "`")
                for row in sent]
        out += _table(("Heure (UTC)", "Statut", "Octets", "ms", "Adresse"), rows)
    else:
        out.append("Aucune requête envoyée.")
    out += ["", f"Fichiers : `{root}/manifest.jsonl` (une ligne par requête), `{root}/observations.json`, "
                f"`{root}/pages/` (corps reçus, erreurs comprises), `{root}/images/<cas>/` (images et `decret.json`).", ""]
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text("\n".join(out), encoding="utf-8")
    return destination
