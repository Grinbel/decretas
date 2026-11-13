"""Run the probe plan politely, stop early, and be resumable.

Rules enforced here (on top of those of `decretas.net`):

- one request at a time, at least 6 s apart on the reading-room host, never more than the
  per-run cap (40 by default) nor the per-day cap (80);
- redirects are followed by hand, one logged request per hop, never to another host;
- the first 5xx or missing answer (time-out, connection error) stops the run for 30 minutes;
  the third one of the same day stops it until the next day. Nothing is retried in between;
- a 403, a 429 or an anti-bot page stops everything until a human decides otherwise;
- every body is saved under the cache root with a manifest; a second run sends only what is
  missing (answers already obtained are read back from the cache).

What the run learns goes to ``observations.json`` (machine-readable) from which
`rapport.py` writes the French report. The state of the stop rules and the anonymous
session cookie live in ``etat.json`` (mode 600); the cookie is never printed.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import re
import time
import urllib.parse
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from decretas import net

from . import extraction, metadonnees, plan
from .client import SessionClient, mask_session, strip_session

EXIT_DONE = 0
EXIT_ERROR = 1
EXIT_CAP = 2          # request cap reached: plan incomplete, run again later
EXIT_PAUSED = 3       # a failure: wait 30 minutes
EXIT_DAY_STOP = 4     # third failure of the day: wait until tomorrow
EXIT_BLOCKED = 5      # refusal (403/429/anti-bot): human decision needed

STATE_FORMAT = "decretas-an-images-reprise-etat/1"
OBSERVATIONS_FORMAT = "decretas-an-images-reprise-observations/1"
MIN_DELAY_REAL_HOST = 6.0
IMAGES_PER_CASE = 2
GENERIC_NAMES = frozenset({"default", "native", "color", "gray", "bitonal", "download", "image", "media", "get", "file"})


@dataclass
class Settings:
    root: Path                                   # cache root: bodies, manifest, state, observations
    base: str = plan.BASE
    delay: float = MIN_DELAY_REAL_HOST
    cap: int = 40
    day_cap: int = 80
    timeout: float = 90.0
    pause_seconds: float = 30 * 60
    failures_per_day: int = 3
    follow_pages: int = 2                        # viewer / description pages followed per image step
    max_hops: int = 4
    lift_block: bool = False
    local_exports: Path | None = None            # data/raw/an: copies of the XML exports, for comparison
    manual: dict[str, list[str]] = field(default_factory=dict)   # case -> extra addresses given by a human
    stop_path: Path | None = None                # the stop file shared by every command on this host (arret.json)


# ----------------------------------------------------------------------------- host-wide stop
# A refusal (403, 429, anti-bot page), a pause after a 5xx or a time-out, and the stop for the day
# hold for the HOST, whichever command met them: « disponibilite » and « reprise » keep their own
# folders, but read and write this one file before sending anything. Only a human lifts a block
# (``reprise --lever-blocage``).

TEST_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})


def normalised_host(base: str) -> str:
    """Host name of an address, lower case, without the trailing dot of a fully-qualified name."""
    return (urllib.parse.urlsplit(base).hostname or "").rstrip(".").lower()


def is_real_host(base: str) -> bool:
    """Every host is the real one, with its minimum delay and ceilings, except a local test server.

    The rule is written the other way round on purpose: « www.siv.archives-nationales.culture.gouv.fr. »
    (final dot), an IP address of that server or an upper-case variant must never escape the limits.
    """
    return normalised_host(base) not in TEST_HOSTS


def read_host_stop(path: Path | None, host: str) -> dict:
    if path is None:
        return {}
    entry = load_json(path, {}).get(host)
    return entry if isinstance(entry, dict) else {}


def write_host_stop(path: Path | None, host: str, **patch) -> None:
    if path is None:
        return
    data = load_json(path, {})
    if not isinstance(data, dict):
        data = {}
    entry = data.get(host) if isinstance(data.get(host), dict) else {}
    entry.update(patch)
    data[host] = entry
    write_json(path, data, private=True)


def host_refusal(path: Path | None, host: str, now: float, *, lift_block: bool = False) -> tuple[int, str] | None:
    """Why nothing may be sent to this host now, according to the shared stop file, or None."""
    stop = read_host_stop(path, host)
    if stop.get("blocage") and not lift_block:
        return EXIT_BLOCKED, ("Arrêt maintenu pour cet hôte : il a refusé une requête (" + str(stop["blocage"]) + "). "
                              "Aucune nouvelle tentative, par aucune commande, sans décision humaine "
                              "(python3 -m decretas.an_images reprise --lever-blocage).")
    if stop.get("arret_du_jour") == local_day(now):
        return EXIT_DAY_STOP, ("Arrêt pour la journée sur cet hôte (" + str(stop["arret_du_jour"]) + ") : reprendre demain, pas avant.")
    until = stop.get("pause_jusqu_a")
    if isinstance(until, (int, float)) and now < until:
        minutes = int((until - now + 59) // 60)
        return EXIT_PAUSED, (f"Pause en cours sur cet hôte après un échec : rien n'est envoyé avant {local_time(until)} "
                             f"(dans {minutes} min).")
    return None


def load_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def write_json(path: Path, value, *, private: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    if private:
        os.chmod(temporary, 0o600)
    os.replace(temporary, path)


def local_day(epoch: float) -> str:
    return datetime.datetime.fromtimestamp(epoch).strftime("%Y-%m-%d")


def local_time(epoch: float) -> str:
    return datetime.datetime.fromtimestamp(epoch).strftime("%Y-%m-%d %H:%M")


def safe_name(url: str) -> str:
    """A file name that keeps the media name of the URL (it is evidence) and cannot escape the cache."""
    parts = urllib.parse.urlsplit(url)
    iiif = metadonnees._IIIF.search(parts.path)
    name = urllib.parse.unquote(parts.path.rstrip("/").rsplit("/", 1)[-1])
    stem, dot, extension = name.rpartition(".")
    if not dot:
        stem, extension = name, ""
    if iiif:
        stem = iiif["identifiant"]
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:8]  # noqa: S324 (a short label, not a security hash)
    if iiif or parts.query or stem.lower() in GENERIC_NAMES or not stem:
        stem = f"{stem or 'media'}_{digest}"
    stem = re.sub(r"[^A-Za-z0-9._-]", "_", stem).strip("._")[:120] or f"media_{digest}"
    extension = re.sub(r"[^A-Za-z0-9]", "", extension)[:5]
    return stem + ("." + extension if extension else "")


def make_client(settings: Settings, jar: dict, *, clock: Callable[[], float], sleep: Callable[[float], None],
                budget: int) -> SessionClient:
    parts = urllib.parse.urlsplit(settings.base)
    host = (parts.hostname or "").lower()
    real = is_real_host(settings.base)
    policy = net.HostPolicy(
        min_delay=max(settings.delay, MIN_DELAY_REAL_HOST) if real else settings.delay,
        budget=budget, max_backoffs=0, timeout=settings.timeout, max_redirects=settings.max_hops,
        allow_http=parts.scheme == "http" and not real, follow_cross_domain=False)
    return SessionClient(root=settings.root, policies={host: policy}, count_manifest_in_budget=False,
                         retry_failed=True, resume_after_stop=settings.lift_block, clock=clock, sleep=sleep, jar=jar)


class Probe:
    """One run of the plan. `run()` returns an exit code and never raises on network trouble."""

    def __init__(self, settings: Settings, steps: Sequence[plan.Step], *, missing: Sequence[str] = (),
                 clock: Callable[[], float] = time.time, sleep: Callable[[float], None] = time.sleep,
                 say: Callable[[str], None] = print) -> None:
        self.settings = settings
        self.steps = list(steps)
        self.missing = list(missing)
        self.clock = clock
        self.sleep = sleep
        self.say = say
        self.state_path = settings.root / "etat.json"
        self.observations_path = settings.root / "observations.json"
        self.state = load_json(self.state_path, {})
        self.state.setdefault("format", STATE_FORMAT)
        self.state.setdefault("echecs", [])
        self.state.setdefault("temoins", {})
        previous = load_json(self.observations_path, {})
        self.observations: dict = {"format": OBSERVATIONS_FORMAT, "base": settings.base,
                                   "etapes": previous.get("etapes", {}) if previous.get("base") == settings.base else {},
                                   "non_planifie": self.missing, "passages": previous.get("passages", [])}
        self.host = (urllib.parse.urlsplit(settings.base).hostname or "").lower()
        self.sent = 0
        self._requesting = ""
        self.message = ""
        self.client: SessionClient | None = None

    # ------------------------------------------------------------------ stop rules
    def refusal(self, now: float) -> tuple[int, str] | None:
        """Why a run must not start now (pause, day stop, block — its own or the host's), or None."""
        shared = host_refusal(self.settings.stop_path, normalised_host(self.settings.base), now, lift_block=self.settings.lift_block)
        if shared is not None:
            return shared
        if self.state.get("blocage") and not self.settings.lift_block:
            return EXIT_BLOCKED, ("Arrêt maintenu : le site a refusé une requête (" + self.state["blocage"] + "). "
                                  "Aucune nouvelle tentative sans décision humaine (option --lever-blocage).")
        if self.state.get("arret_du_jour") == local_day(now):
            return EXIT_DAY_STOP, ("Arrêt pour la journée : trois échecs le " + self.state["arret_du_jour"]
                                   + ". Reprendre demain, pas avant.")
        until = self.state.get("pause_jusqu_a")
        if isinstance(until, (int, float)) and now < until:
            minutes = int((until - now + 59) // 60)
            return EXIT_PAUSED, (f"Pause en cours après un échec : reprise possible à {local_time(until)} "
                                 f"(dans {minutes} min). Rien n'a été envoyé.")
        return None

    def requests_today(self, now: float) -> int:
        manifest = self.settings.root / "manifest.jsonl"
        if not manifest.exists():
            return 0
        today = local_day(now)
        count = 0
        for line in manifest.read_text(encoding="utf-8").splitlines():
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if row.get("network", True) and local_day(float(row.get("epoch", 0))) == today:
                count += 1
        return count

    def _record_failure(self, step_id: str, url: str, now: float) -> tuple[int, str]:
        row = self.client.cached(net._without_fragment(url)) if self.client else None
        status = int(row.get("status") or 0) if row else 0
        today = local_day(now)
        self.state["echecs"].append({"jour": today, "a": local_time(now), "etape": step_id, "url": mask_session(url),
                                     "statut": status, "erreur": (row or {}).get("error")})
        today_failures = [failure for failure in self.state["echecs"] if failure.get("jour") == today]
        what = f"HTTP {status}" if status else f"aucune réponse ({(row or {}).get('error') or 'délai dépassé'})"
        if len(today_failures) >= self.settings.failures_per_day:
            self.state["arret_du_jour"] = today
            self.state["pause_jusqu_a"] = None
            return EXIT_DAY_STOP, (f"Étape {step_id} : {what}. C'est le {len(today_failures)}ᵉ échec du jour : arrêt jusqu'à "
                                   "demain. Relancer la même commande demain ; ce qui est acquis ne sera pas redemandé.")
        until = now + self.settings.pause_seconds
        self.state["pause_jusqu_a"] = until
        return EXIT_PAUSED, (f"Étape {step_id} : {what}. Échec n° {len(today_failures)} du jour : arrêt de "
                             f"{int(self.settings.pause_seconds // 60)} minutes. Relancer la même commande à partir de "
                             f"{local_time(until)} ; ce qui est acquis ne sera pas redemandé.")

    # ------------------------------------------------------------------ requests
    def _chain(self, url: str, save_as: str) -> dict:
        """Request `url` and follow its redirects on the same host. Returns
        {"sauts": [...], "final": manifest line or None, "url_finale": str, "etat": str}."""
        hops: list[dict] = []
        current = strip_session(url)
        outcome = {"sauts": hops, "final": None, "url_finale": current, "etat": "inachevee"}
        for index in range(self.settings.max_hops + 1):
            self._requesting = current
            try:
                row, fresh = self.client.hop(current, save_as if index == 0 else f"{save_as}.saut{index}")
            except net.HostNotAllowed as error:
                hops.append({"url": mask_session(current), "statut": None, "note": f"non demandé : {error}"})
                outcome["etat"] = "hors-hote"
                return outcome
            if fresh:
                self.sent += 1
            status = int(row.get("status") or 0)
            hop = {"url": mask_session(current), "statut": status, "octets": row.get("bytes"), "sha256": row.get("sha256"),
                   "ms": row.get("elapsed_ms"), "type": row.get("content_type"), "a": row.get("at"),
                   "depuis_cache": not fresh, "fichier": row.get("file") or row.get("corps_hors_2xx"),
                   "en_tetes": row.get("en_tetes"), "temoins_poses": row.get("temoins_poses"),
                   "temoin_envoye": bool(row.get("temoin_envoye"))}
            hops.append(hop)
            outcome["final"] = row
            outcome["url_finale"] = current
            if status in net.REDIRECT_STATUSES and row.get("location"):
                target = strip_session(urllib.parse.urljoin(current, row["location"]))
                hop["location"] = mask_session(target)
                hop["session_dans_adresse"] = bool(row.get("session_dans_adresse"))
                target_parts = urllib.parse.urlsplit(target)
                if (target_parts.hostname or "").lower() != self.host:
                    hop["note"] = "redirection vers un autre hôte : notée, non suivie"
                    outcome["etat"] = "hors-hote"
                    return outcome
                current = target
                continue
            outcome["etat"] = "ok" if 200 <= status < 300 else f"http-{status}"
            return outcome
        outcome["etat"] = "trop-de-redirections"
        return outcome

    def _body(self, hop: dict) -> bytes | None:
        if not hop.get("fichier"):
            return None
        try:
            return (self.settings.root / hop["fichier"]).read_bytes()
        except OSError:
            return None

    @staticmethod
    def _summary(found: extraction.Extraction) -> dict:
        views = extraction.group_views(found.candidates)
        return {
            "genre": found.kind, "strategies": found.by_strategy(), "identifiants_de_media": found.identifiers[:100],
            "structure": found.structure,
            "candidats": [c.as_dict() for c in found.candidates if not c.chrome][:400],
            "habillage": sum(1 for c in found.candidates if c.chrome),
            "hors_hote": [c.url for c in found.candidates if not c.same_host and c.kind in ("image", "iiif")][:40],
            "pages_possibles": [{"url": c.url, "score": extraction.viewer_score(c.url)}
                                for c in extraction.follow_up_pages(found, set())][:15],
            "nombre_de_vues": len(views),
        }

    def _image_record(self, url: str, hop: dict, rank: int | None, total: int | None) -> dict:
        path = self.settings.root / hop["fichier"]
        card = metadonnees.inspecter(path, url=url)
        record = {"url": mask_session(url), "fichier": hop["fichier"], "vue": rank, "vues_du_decret": total,
                  "rang_taille": extraction.size_rank(url), "fiche": card}
        return record

    def _images_in_case(self, case: str) -> list[dict]:
        return [image for step in self.observations["etapes"].values() if step.get("cas") == case
                for image in step.get("images", [])]

    def _process(self, step: plan.Step, url: str | None = None) -> None:
        url = url or step.url(self.settings.base)
        obs: dict = {"id": step.id, "cas": step.case, "genre": step.kind, "question": step.question, "palier": step.tier,
                     "url": mask_session(url), "decret": list(step.decree) if step.decree else None,
                     "etat": "en-cours", "suivis": [], "images": [], "notes": []}
        self.observations["etapes"][step.id] = obs
        chain = self._chain(url, f"pages/{step.id}.corps")
        obs["sauts"] = chain["sauts"]
        obs["etat"] = chain["etat"]
        last = chain["sauts"][-1] if chain["sauts"] else {}
        body = self._body(last)
        if body is None:
            if chain["etat"] == "ok":
                obs["notes"].append("réponse 2xx sans corps enregistré")
            return
        declared = last.get("type")
        kind = extraction.sniff(body, declared)
        obs["corps"] = {"genre": kind, "octets": len(body), "fichier": last.get("fichier")}
        if step.kind == "export":
            self._compare_export(url, body, obs)
        if kind == "image":
            obs["notes"].append("l'adresse renvoie directement une image")
            if chain["etat"] == "ok":
                obs["images"].append(self._image_record(chain["url_finale"], last, 1, 1))
            return
        found = extraction.extract(body, chain["url_finale"], declared)
        obs["extraction"] = self._summary(found)
        if step.kind != "images" or chain["etat"] != "ok":
            return
        visited = {hop["url"] for hop in chain["sauts"]} | {chain["url_finale"], url}
        merged = list(found.candidates)
        views = extraction.group_views(merged)
        followed = 0
        while not views and followed < self.settings.follow_pages:
            pages = extraction.follow_up_pages(extraction.Extraction(kind="html", candidates=merged), visited)
            if not pages:
                break
            page = pages[0]
            visited.add(page.url)
            followed += 1
            sub = self._chain(page.url, f"pages/{step.id}-suivi{followed}.corps")
            record: dict = {"url": mask_session(page.url), "raison": "page susceptible de mener aux images "
                            f"(score {extraction.viewer_score(page.url)})", "sauts": sub["sauts"], "etat": sub["etat"]}
            obs["suivis"].append(record)
            sub_body = self._body(sub["sauts"][-1]) if sub["sauts"] else None
            if sub_body is None:
                continue
            sub_found = extraction.extract(sub_body, sub["url_finale"], sub["sauts"][-1].get("type"))
            record["extraction"] = self._summary(sub_found)
            offset = len(merged)
            for candidate in sub_found.candidates:
                candidate.position += offset
            merged.extend(sub_found.candidates)
            views = extraction.group_views(merged)
        obs["vues"] = [view.as_dict() for view in views][:600]
        obs["nombre_de_vues"] = len(views)
        obs["suite_des_noms"] = metadonnees.analyser_suite([view.key.rsplit("/", 1)[-1] for view in views]) if views else None
        if not views:
            obs["notes"].append("aucune adresse d'image trouvée par les stratégies génériques : lire le corps enregistré, "
                                "puis relancer avec --suivre " + step.case + "=<adresse> si une adresse y figure")
            return
        quota = min(step.images, IMAGES_PER_CASE - len(self._images_in_case(step.case)))
        for view in extraction.choose_views(views, quota):
            best = view.best()
            image_chain = self._chain(best.url, f"images/{step.case}/{safe_name(best.url)}")
            final = image_chain["sauts"][-1] if image_chain["sauts"] else {}
            image_body = self._body(final)
            if image_chain["etat"] == "ok" and image_body is not None and extraction.sniff(image_body, final.get("type")) == "image":
                record = self._image_record(best.url, final, view.position + 1, len(views))
                record["sauts"] = image_chain["sauts"]
                obs["images"].append(record)
            else:
                obs["notes"].append(f"vue {view.position + 1} : {mask_session(best.url)} n'a pas donné une image "
                                    f"({image_chain['etat']}, type déclaré {final.get('type')})")
                obs["suivis"].append({"url": mask_session(best.url), "raison": "adresse d'image candidate",
                                      "sauts": image_chain["sauts"], "etat": image_chain["etat"]})

    def _compare_export(self, url: str, body: bytes, obs: dict) -> None:
        identifier = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query).get("irId", [""])[0]
        directory = self.settings.local_exports
        if not identifier or directory is None or not re.fullmatch(r"FRAN_IR_\d{6}", identifier):
            return
        local = directory / f"{identifier}.xml"
        if not local.exists():
            obs["notes"].append(f"pas de copie locale de {identifier} à comparer")
            return
        data = local.read_bytes()
        same = hashlib.sha256(data).digest() == hashlib.sha256(body).digest()
        obs["comparaison_locale"] = {"fichier": str(local), "octets_locaux": len(data), "octets_recus": len(body),
                                     "identique": same}

    def _write_sidecars(self) -> None:
        """One ``decret.json`` per image folder: which decree each downloaded image belongs to."""
        by_case: dict[str, dict] = {}
        for obs in self.observations["etapes"].values():
            for image in obs.get("images", []):
                if not str(image.get("fichier", "")).startswith("images/"):
                    continue
                entry = by_case.setdefault(obs["cas"], {"format": "decretas-an-images-decret/1", "cas": obs["cas"], "images": {}})
                entry["images"][Path(image["fichier"]).name] = {
                    "inventaire": (obs.get("decret") or [None, None])[0], "notice": (obs.get("decret") or [None, None])[1],
                    "url": image["url"], "vue": image.get("vue"), "vues_du_decret": image.get("vues_du_decret")}
        for case, entry in by_case.items():
            write_json(self.settings.root / "images" / case / "decret.json", entry)

    # ------------------------------------------------------------------ the run
    def run(self) -> int:
        now = self.clock()
        refused = self.refusal(now)
        if refused:
            self.message = refused[1]
            self.say(self.message)
            return refused[0]
        if self.settings.lift_block:
            self.state["blocage"] = None
            write_host_stop(self.settings.stop_path, normalised_host(self.settings.base), blocage=None)
        used_today = self.requests_today(now)
        budget = min(self.settings.cap, self.settings.day_cap - used_today)
        if budget <= 0:
            self.message = (f"Plafond du jour atteint ({used_today} requêtes sur {self.settings.day_cap}) : rien n'est envoyé. "
                            "Reprendre demain.")
            self.say(self.message)
            return EXIT_CAP
        self.client = make_client(self.settings, self.state["temoins"], clock=self.clock, sleep=self.sleep, budget=budget)
        code = EXIT_DONE
        current: plan.Step | None = None
        reached: set[str] = set()
        manual_steps = [plan.Step(id=f"M{rank}", case=case, path=address, kind="images",
                                  question="Adresse donnée à la main (--suivre) après lecture d'un corps enregistré.",
                                  images=1)
                        for rank, (case, address) in enumerate(((case, address) for case, addresses in
                                                                sorted(self.settings.manual.items()) for address in addresses), 1)]
        try:
            for step in self.steps + manual_steps:
                current = step
                address = None
                if step.id.startswith("M") and step in manual_steps:
                    address = urllib.parse.urljoin(self.settings.base.rstrip("/") + "/", step.path)
                before = self.sent
                self._process(step, address)
                reached.add(step.id)
                obs = self.observations["etapes"][step.id]
                self.say(f"  {step.id:<3} {obs['etat']:<22} {self.sent - before} requête(s) envoyée(s), "
                         f"{len(obs.get('images', []))} image(s) — {mask_session(obs['url'])}")
        except (net.TransportError, net.ServerUnavailable) as error:
            del error                      # the manifest line of the failing address says it all
            code, self.message = self._record_failure(current.id if current else "?", self._requesting, self.clock())
            if current:
                self.observations["etapes"].setdefault(current.id, {})["etat"] = "interrompue"
        except net.Blocked as error:
            self.state["blocage"] = f"{local_time(self.clock())} — {error}"
            code, self.message = EXIT_BLOCKED, (f"REFUS du site : {error}. Tout est arrêté ; ne pas relancer sans décision "
                                               "humaine (voir docs/decrets-en-images.md).")
            if current:
                self.observations["etapes"].setdefault(current.id, {})["etat"] = "refus"
        except net.BudgetExhausted:
            code, self.message = EXIT_CAP, (f"Plafond de {budget} requêtes atteint pour ce passage : plan inachevé. "
                                           "Relancer plus tard ; ce qui est acquis ne sera pas redemandé.")
            if current:
                self.observations["etapes"].setdefault(current.id, {})["etat"] = "plafond"
        finally:
            for step in self.steps:
                if step.id not in reached and step.id not in self.observations["etapes"]:
                    self.observations["etapes"][step.id] = {
                        "id": step.id, "cas": step.case, "genre": step.kind, "question": step.question, "palier": step.tier,
                        "url": step.url(self.settings.base), "etat": "non-atteinte", "sauts": [], "images": [], "suivis": [],
                        "notes": []}
            if code == EXIT_DONE:
                self.state["pause_jusqu_a"] = None
                self.message = f"Plan parcouru : {self.sent} requête(s) envoyée(s) pendant ce passage."
            self.observations["passages"].append({"a": local_time(self.clock()), "requetes": self.sent, "code": code,
                                                  "message": self.message})
            self.observations["ordre"] = [step.id for step in self.steps + manual_steps]
            write_json(self.state_path, self.state, private=True)
            # what stops this command stops every command on the host
            write_host_stop(self.settings.stop_path, normalised_host(self.settings.base),
                            blocage=self.state.get("blocage"), pause_jusqu_a=self.state.get("pause_jusqu_a"),
                            arret_du_jour=self.state.get("arret_du_jour"))
            write_json(self.observations_path, self.observations)
            self._write_sidecars()
        self.say(self.message)
        return code


def describe_plan(steps: Sequence[plan.Step], missing: Sequence[str], settings: Settings) -> str:
    """The dry-run text: every starting request, its question, and the request arithmetic."""
    lines = ["PLAN DE REPRISE — simulation : rien n'est envoyé, rien n'est écrit.", "",
             f"Hôte : {urllib.parse.urlsplit(settings.base).hostname}   délai entre deux requêtes : {settings.delay:g} s au moins   "
             f"plafond : {settings.cap} requêtes par passage, {settings.day_cap} par jour",
             f"Arrêt de {int(settings.pause_seconds // 60)} min au premier 5xx ou délai dépassé ; arrêt pour la journée au "
             f"{settings.failures_per_day}ᵉ ; arrêt complet sur 403, 429 ou page anti-robot.", ""]
    case = None
    for step in steps:
        if step.case != case:
            case = step.case
            lines.append(f"[{case}] {plan.CASES.get(case, case)}")
        lines.append(f"  {step.id:<3} palier {step.tier}  GET {step.url(settings.base)}")
        lines.append(f"       → {step.question}" + (f" (jusqu'à {step.images} image(s))" if step.images else ""))
    for sentence in missing:
        lines.append(f"  NON PLANIFIÉ : {sentence}")
    for case, addresses in sorted(settings.manual.items()):
        for address in addresses:
            lines.append(f"  M   [{case}] GET {urllib.parse.urljoin(settings.base.rstrip('/') + '/', address)}   (adresse donnée à la main)")
    starts = len(steps)
    images = 0
    for case_name in {step.case for step in steps}:
        images += min(IMAGES_PER_CASE, sum(step.images for step in steps if step.case == case_name))
    image_steps = sum(1 for step in steps if step.kind == "images")
    minimum = starts
    maximum = starts * 2 + images + image_steps * settings.follow_pages
    lines += ["", f"Requêtes de départ : {starts}. Estimation : {minimum} si rien ne redirige et qu'aucune image n'est trouvée ; "
                  f"environ {maximum} avec une redirection par adresse, {images} image(s) et {settings.follow_pages} page(s) de "
                  f"visionneuse par lien d'images.",
              f"Durée au rythme minimal : de {minimum * settings.delay / 60:.0f} à {maximum * settings.delay / 60:.0f} minutes, "
              "plus le temps de réponse du site (20 à 40 s par page les mauvais jours).",
              f"Si l'estimation haute dépasse le plafond ({settings.cap}), le passage s'arrête au plafond et un second "
              "passage, plus tard, reprend où le premier s'est arrêté."]
    return "\n".join(lines)
