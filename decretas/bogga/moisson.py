"""Harvest of the BOGGA text files from the Internet Archive (three small files per volume).

For each volume of the catalogue: read `/metadata/<item>` (once per item), check that the
document prefix really exists in the item's file list, then fetch from one of the item's
`workable_servers` the search text, the page index and the page numbers. Page images and
PDFs are never requested. All requests go through `decretas.net.PoliteClient`.
"""
from __future__ import annotations

import hashlib
import json
import urllib.parse
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path

from decretas import net
from decretas.bogga import catalogue

IA_FAMILY = "archive.org"
METADATA_FILE = "_metadata.json"


class HarvestError(Exception):
    """The Internet Archive record does not have the shape the harvest relies on."""


@dataclass(frozen=True)
class VolumeFiles:
    """Where the three files of a volume are on disk (None when not downloaded)."""

    volume: catalogue.Volume
    doc: str
    searchtext: Path | None
    pageindex: Path | None
    page_numbers: Path | None

    @property
    def complete(self) -> bool:
        return None not in (self.searchtext, self.pageindex, self.page_numbers)


@dataclass
class HarvestReport:
    fetched: list[str] = field(default_factory=list)
    cached: list[str] = field(default_factory=list)
    planned: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    stopped: str | None = None


def ia_policy(delay: float = 5.5, budget: int = 150) -> dict[str, net.HostPolicy]:
    """Policy for the whole archive.org family: 5 s minimum, 403/429 stop, one 60 s back-off."""
    return {IA_FAMILY: net.HostPolicy(min_delay=max(delay, 5.0), budget=budget, backoff_seconds=60.0,
                                      max_backoffs=1, timeout=90.0)}


def metadata_url(item: str) -> str:
    return catalogue.METADATA_URL.format(item=urllib.parse.quote(item, safe=""))


def load_metadata(root: Path, item: str) -> dict | None:
    path = root / item / METADATA_FILE
    if not path.exists():
        return None
    with path.open(encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict) or not isinstance(data.get("files"), list):
        raise HarvestError(f"notice inattendue pour {item} : pas de liste de fichiers")
    return data


def doc_prefixes(metadata: dict) -> list[str]:
    """Every document prefix of an item that has the three files we need."""
    names = {entry.get("name", "") for entry in metadata["files"] if isinstance(entry, dict)}
    first = catalogue.FILE_SUFFIXES[0]
    prefixes = [name[: -len(first)] for name in names if name.endswith(first)]
    return sorted(p for p in prefixes if all(p + suffix in names for suffix in catalogue.FILE_SUFFIXES))


def resolve_doc(volume: catalogue.Volume, metadata: dict) -> str:
    """The exact file prefix of a volume, checked against (or read from) the item's file list."""
    available = doc_prefixes(metadata)
    if volume.doc is not None:
        if volume.doc not in available:
            raise HarvestError(f"{volume.item} : le document « {volume.doc} » n'a pas les trois fichiers attendus")
        return volume.doc
    if len(available) != 1:
        raise HarvestError(f"{volume.item} : {len(available)} documents trouvés, un seul attendu")
    return available[0]


def file_url(metadata: dict, name: str) -> str:
    """Direct address of a file on the first workable server (never the redirecting /download/)."""
    servers = metadata.get("workable_servers") or []
    directory = metadata.get("dir")
    if not servers or not isinstance(directory, str):
        raise HarvestError("notice sans « workable_servers » ou sans « dir »")
    return catalogue.FILE_URL.format(server=servers[0], dir=directory, file=urllib.parse.quote(name))


def expected_md5(metadata: dict, name: str) -> str | None:
    for entry in metadata["files"]:
        if isinstance(entry, dict) and entry.get("name") == name:
            return entry.get("md5")
    return None


def md5_of(path: Path) -> str:
    digest = hashlib.md5(usedforsecurity=False)
    digest.update(path.read_bytes())
    return digest.hexdigest()


def local_files(root: Path, volume: catalogue.Volume) -> VolumeFiles | None:
    """Files of a volume already on disk, or None when its item metadata is not there yet."""
    metadata = load_metadata(root, volume.item)
    if metadata is None:
        return None
    doc = resolve_doc(volume, metadata)
    paths = [root / volume.item / (doc + suffix) for suffix in catalogue.FILE_SUFFIXES]
    found = [path if path.exists() else None for path in paths]
    return VolumeFiles(volume, doc, found[0], found[1], found[2])


def adopt_earlier_downloads(client: net.PoliteClient, log: Path, base: Path, wanted: dict[str, str]) -> int:
    """Register bodies fetched by the earlier sampling session, so no URL is asked twice.

    `log` is that session's request log (one JSON object per line with `url`, `status`,
    `saved_as`), `base` the directory its `saved_as` paths are relative to, `wanted` maps
    the URLs this harvest needs to their cache path. Returns how many were adopted.
    """
    if not log.exists():
        return 0
    adopted = 0
    with log.open(encoding="utf-8") as handle:
        for line in handle:
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            url = row.get("url")
            if url not in wanted or row.get("status") != 200 or row.get("range") or client.cached(url):
                continue
            source = base / str(row.get("saved_as", ""))
            if source.is_file() and source.stat().st_size == row.get("bytes"):
                client.adopt(url, source, wanted[url], note="repris de l'échantillonnage du 2026-11-11")
                adopted += 1
    return adopted


def harvest(client: net.PoliteClient, volumes: Iterable[catalogue.Volume], *,
            earlier_log: Path | None = None, earlier_base: Path | None = None,
            say: Callable[[str], None] = print) -> HarvestReport:
    """Fetch what is missing for `volumes`. Stops everything on a refusal (403/429/anti-bot)."""
    report = HarvestReport()
    root = client.root
    abandoned_items: set[str] = set()

    def get(url: str, save_as: str, prefixes: tuple[bytes, ...]) -> net.FetchResult | None:
        if earlier_log is not None and earlier_base is not None:
            adopt_earlier_downloads(client, earlier_log, earlier_base, {url: save_as})
        result = client.fetch(url, save_as, expect_prefix=prefixes)
        if result.dry_run:
            report.planned.append(url)
            say(f"simulation   {url}")
            return None
        (report.cached if result.from_cache else report.fetched).append(url)
        say(f"{'déjà là     ' if result.from_cache else 'reçu        '} {save_as} ({result.size} octets)")
        return result

    for volume in volumes:
        if volume.item in abandoned_items:
            report.skipped.append(f"{volume.year} : item {volume.item} abandonné plus tôt dans ce passage")
            continue
        try:
            if get(metadata_url(volume.item), f"{volume.item}/{METADATA_FILE}", (b"{",)) is None:
                report.skipped.append(f"{volume.year} : notice non lue (simulation), fichiers inconnus")
                continue
            metadata = load_metadata(root, volume.item)
            if metadata is None:
                raise HarvestError(f"notice absente du cache pour {volume.item}")
            doc = resolve_doc(volume, metadata)
            for suffix in catalogue.FILE_SUFFIXES:
                name = doc + suffix
                prefixes = (b"\x1f\x8b",) if name.endswith(".gz") else (b"{", b"[")
                result = get(file_url(metadata, name), f"{volume.item}/{name}", prefixes)
                wanted = expected_md5(metadata, name)
                if result is not None and result.path is not None and wanted and md5_of(result.path) != wanted:
                    raise HarvestError(f"{name} : empreinte md5 différente de celle de la notice")
        except net.Blocked as exc:
            report.stopped = str(exc)
            say(f"REFUS        {exc}")
            break
        except net.BudgetExhausted as exc:
            report.stopped = str(exc)
            say(f"PLAFOND      {exc}")
            break
        except (net.ServerUnavailable, net.TransportError, net.HttpError, net.PreviouslyFailed,
                net.CrossDomainRedirect, HarvestError) as exc:
            abandoned_items.add(volume.item)
            report.skipped.append(f"{volume.year} : {exc}")
            say(f"ABANDON      {volume.year} : {exc}")
    return report
