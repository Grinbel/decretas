"""The project's single polite HTTP client (urllib only).

Every program of this project that talks to a remote host goes through `PoliteClient`.
The rules it enforces, per *host family* (registrable domain, e.g. every
`*.archive.org` node is the family `archive.org`):

- a fixed, honest User-Agent, no cookie, no browser disguise;
- a minimum delay between two requests to the same family, kept across runs;
- an on-disk cache keyed by URL (without its #fragment, which is never sent): a URL that
  was answered is never requested again;
- one manifest line (JSON) per request actually sent: url, status, bytes, sha256, at;
- a hard stop of the family on 403, 429 or an anti-bot page (never retried, never worked
  around; the stop persists in the manifest until a human lifts it);
- on 5xx, one bounded back-off then the item is abandoned;
- redirects are followed by hand, each hop is a logged request; a redirect to another
  registrable domain is always recorded and only followed when the policy allows it;
- a request budget per family;
- a dry-run mode that sends nothing and writes nothing (neither file nor manifest line).

Downloaded bodies are untrusted data: they are written to disk, never executed.
"""
from __future__ import annotations

import datetime
import hashlib
import http.client
import ipaddress
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path

USER_AGENT = "decretas/0.2 (recherche genealogique non commerciale; projet libre et gratuit)"

REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})

# Public suffixes made of two labels that this project meets. A full public-suffix list
# is not needed: the registrable domain is only used to group hosts under one policy.
_TWO_LABEL_SUFFIXES = frozenset({
    "gouv.fr", "asso.fr", "co.uk", "ac.uk", "org.uk", "com.au", "co.jp", "com.br",
})

# Markers of an anti-bot interstitial, searched (lower-cased) in the head of an answer.
DEFAULT_ANTIBOT_MARKERS: tuple[bytes, ...] = (
    b"just a moment",
    b"cf-chl",
    b"captcha",
    b"/sorry/index",
    b"unusual traffic",
    b"access denied",
    b"attention required",
)


class NetError(Exception):
    """Base class of every error raised by this module."""


class HostNotAllowed(NetError):
    """The URL's host has no policy (or uses a scheme the policy forbids)."""


class BudgetExhausted(NetError):
    """The request budget of the host family is spent."""


class Blocked(NetError):
    """The host refused (403, 429, anti-bot page, unexpected body): the family is stopped."""


class ServerUnavailable(NetError):
    """5xx again after the single back-off: this item is abandoned."""


class TransportError(NetError):
    """No HTTP answer at all (DNS, connection, TLS, timeout)."""


class HttpError(NetError):
    """A definitive non-2xx answer that is not a stop condition (e.g. 404)."""

    def __init__(self, url: str, status: int) -> None:
        super().__init__(f"HTTP {status} pour {url}")
        self.url = url
        self.status = status


class CrossDomainRedirect(NetError):
    """A redirect leaves the registrable domain and the policy does not allow following it."""


class PreviouslyFailed(NetError):
    """The URL failed in an earlier run (5xx or no answer) and retrying was not requested."""


class CacheCorrupt(NetError):
    """A cached file is missing or no longer matches the sha256 recorded in the manifest."""


@dataclass(frozen=True)
class HostPolicy:
    """What the client may do to one host family. All durations are in seconds."""

    min_delay: float = 5.0
    budget: int = 60
    stop_statuses: frozenset[int] = frozenset({403, 429})
    antibot_markers: tuple[bytes, ...] = DEFAULT_ANTIBOT_MARKERS
    backoff_seconds: float = 60.0
    max_backoffs: int = 1
    timeout: float = 60.0
    max_bytes: int = 64 * 1024 * 1024
    max_redirects: int = 4
    allow_http: bool = False
    follow_cross_domain: bool = False


@dataclass(frozen=True)
class FetchResult:
    """Outcome of `PoliteClient.fetch`. `path` is None only in dry-run for an uncached URL."""

    url: str
    final_url: str
    status: int | None
    path: Path | None
    size: int
    sha256: str | None
    from_cache: bool
    dry_run: bool = False
    hops: tuple[str, ...] = ()

    def read_bytes(self) -> bytes:
        if self.path is None:
            raise NetError(f"aucun fichier pour {self.url} (simulation)")
        return self.path.read_bytes()


def registrable_domain(host: str) -> str:
    """Return the family of a host: 'ia601506.us.archive.org' -> 'archive.org'.

    IP addresses and single-label hosts (localhost) are their own family.
    """
    host = host.lower().rstrip(".")
    try:
        ipaddress.ip_address(host.strip("[]"))
        return host
    except ValueError:
        pass
    labels = host.split(".")
    if len(labels) <= 2:
        return host
    if ".".join(labels[-2:]) in _TWO_LABEL_SUFFIXES:
        return ".".join(labels[-3:])
    return ".".join(labels[-2:])


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 16), b""):
            digest.update(chunk)
    return digest.hexdigest()


def looks_like_antibot(head: bytes, markers: tuple[bytes, ...]) -> bool:
    """True when the first bytes of a body look like an HTML challenge page."""
    probe = head[:4096].lstrip().lower()
    if not probe.startswith((b"<!doctype html", b"<html", b"<head", b"<body")):
        return False
    return any(marker in probe for marker in markers)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Make urllib return 3xx answers instead of following them: each hop is ours to log."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D102, PLR0913
        return None


@dataclass
class _Answer:
    status: int
    headers: Mapping[str, str]
    body_path: Path | None
    size: int
    sha256: str | None
    head: bytes
    elapsed_ms: int


@dataclass
class PoliteClient:
    """Cached, paced, logged HTTP GET client. See the module docstring for the rules.

    `root` is the cache directory; every saved file and the manifest live under it.
    `policies` maps a host suffix ('archive.org', '127.0.0.1') to its `HostPolicy`; a host
    without a matching entry is refused.
    `count_manifest_in_budget`: when True, requests already recorded in the manifest count
    against the budget (a budget for the whole life of the cache, not for one run).
    `resume_after_stop`: a human decision that an earlier refusal (403/429) is lifted.
    """

    root: Path
    policies: Mapping[str, HostPolicy]
    dry_run: bool = False
    count_manifest_in_budget: bool = True
    resume_after_stop: bool = False
    retry_failed: bool = False
    manifest_name: str = "manifest.jsonl"
    clock: Callable[[], float] = time.time
    sleep: Callable[[float], None] = time.sleep
    planned: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.root = Path(self.root)
        self._last_by_url: dict[str, dict] = {}
        self._used: dict[str, int] = {}
        self._last_epoch: dict[str, float] = {}
        self._stopped: dict[str, str] = {}
        self._run_used: dict[str, int] = {}
        for row in self._read_manifest():
            self._remember(row, from_disk=True)
        if self.resume_after_stop:
            self._stopped.clear()

    # ------------------------------------------------------------------ manifest
    @property
    def manifest_path(self) -> Path:
        return self.root / self.manifest_name

    def _read_manifest(self) -> list[dict]:
        if not self.manifest_path.exists():
            return []
        rows = []
        with self.manifest_path.open(encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise CacheCorrupt(f"ligne illisible dans {self.manifest_path}: {exc}") from exc
                if isinstance(row, dict) and "url" in row:
                    rows.append(row)
        return rows

    def _remember(self, row: dict, *, from_disk: bool) -> None:
        family = row.get("family", "")
        self._last_by_url[row["url"]] = row
        if not row.get("network", True):
            return
        self._used[family] = self._used.get(family, 0) + 1
        if not from_disk:
            self._run_used[family] = self._run_used.get(family, 0) + 1
        self._last_epoch[family] = max(self._last_epoch.get(family, 0.0), float(row.get("epoch", 0.0)))
        if row.get("stop"):
            self._stopped[family] = f"HTTP {row.get('status')} le {row.get('at')} pour {row['url']}"
        else:
            self._stopped.pop(family, None)

    def _append(self, row: dict) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        with self.manifest_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        self._remember(row, from_disk=False)

    # ------------------------------------------------------------------ policy helpers
    def policy_for(self, url: str) -> tuple[str, HostPolicy]:
        """Return (family, policy) for a URL, or raise HostNotAllowed."""
        parts = urllib.parse.urlsplit(url)
        host = (parts.hostname or "").lower()
        if not host:
            raise HostNotAllowed(f"adresse sans hôte : {url}")
        match = max(
            (key for key in self.policies if host == key or host.endswith("." + key)),
            key=len,
            default=None,
        )
        if match is None:
            raise HostNotAllowed(f"hôte sans règle de politesse : {host}")
        policy = self.policies[match]
        if parts.scheme != "https" and not (parts.scheme == "http" and policy.allow_http):
            raise HostNotAllowed(f"schéma refusé pour {host} : {parts.scheme}")
        return registrable_domain(host), policy

    def requests_used(self, family: str) -> int:
        """Requests counted against the budget of a family."""
        return self._used.get(family, 0) if self.count_manifest_in_budget else self._run_used.get(family, 0)

    def requests_left(self, family: str, policy: HostPolicy) -> int:
        return max(0, policy.budget - self.requests_used(family))

    def stopped_reason(self, family: str) -> str | None:
        return self._stopped.get(family)

    def _target(self, save_as: str) -> Path:
        target = (self.root / save_as).resolve()
        root = self.root.resolve()
        if root != target and root not in target.parents:
            raise NetError(f"chemin hors du cache : {save_as}")
        return target

    # ------------------------------------------------------------------ cache
    def cached(self, url: str) -> dict | None:
        """The last manifest line of a URL, if any."""
        return self._last_by_url.get(url)

    def _result(self, url: str, row: dict, hops: tuple[str, ...], *, from_cache: bool = True) -> FetchResult:
        path = self.root / row["file"] if row.get("file") else None
        if path is None or not path.exists():
            raise CacheCorrupt(f"fichier de cache absent pour {url} : {row.get('file')}")
        if row.get("sha256") and sha256_of(path) != row["sha256"]:
            raise CacheCorrupt(f"le fichier {path} ne correspond plus à son empreinte sha256")
        return FetchResult(url=hops[0] if hops else url, final_url=url, status=row["status"], path=path,
                           size=row.get("bytes", 0), sha256=row.get("sha256"), from_cache=from_cache, hops=hops)

    def adopt(self, url: str, source: Path, save_as: str, note: str) -> FetchResult:
        """Register a body obtained earlier for `url` (another tool, an earlier session).

        The file is copied into the cache and a manifest line marked `network: false` is
        written, so that the URL is never requested again. Nothing is sent.
        """
        url = _without_fragment(url)
        family, _policy = self.policy_for(url)
        known = self.cached(url)
        if known and 200 <= int(known.get("status") or 0) < 300 and known.get("file"):
            return self._result(url, known, ())
        target = self._target(save_as)
        data = Path(source).read_bytes()
        row = {
            "url": url, "method": "GET", "status": 200, "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(), "at": _now_iso(self.clock()),
            "epoch": self.clock(), "host": urllib.parse.urlsplit(url).hostname, "family": family,
            "file": str(target.relative_to(self.root.resolve())), "network": False, "note": note,
        }
        if self.dry_run:
            # nothing is written in a dry run: the body is served from where it already is,
            # so that the plan still shows this URL as "not to be requested"
            row["file"] = str(Path(source).resolve())
            self._remember(row, from_disk=True)
            return self._result(url, row, ())
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        self._append(row)
        return self._result(url, row, ())

    # ------------------------------------------------------------------ fetch
    def fetch(self, url: str, save_as: str, *, expect_prefix: tuple[bytes, ...] = ()) -> FetchResult:
        """GET `url` politely and save the body as `root/save_as`.

        `expect_prefix`: accepted first bytes of a good body (e.g. the gzip magic number);
        a 200 answer that starts otherwise is treated as a refusal in disguise (Blocked).
        Returns a FetchResult; raises a NetError subclass on every stop condition.
        """
        url = _without_fragment(url)
        hops: list[str] = []
        current = url
        while True:
            hops.append(current)
            family, policy = self.policy_for(current)
            row = self.cached(current)
            fresh = False
            if row is None or not self._usable(row):
                if self.dry_run:
                    self.planned.append(current)
                    return FetchResult(url=url, final_url=current, status=None, path=None, size=0,
                                       sha256=None, from_cache=False, dry_run=True, hops=tuple(hops))
                row = self._request(current, save_as, family, policy, expect_prefix)
                fresh = True
            status = int(row["status"])
            if status in REDIRECT_STATUSES and row.get("location"):
                if len(hops) > policy.max_redirects:
                    raise NetError(f"trop de redirections depuis {url}")
                target = _without_fragment(urllib.parse.urljoin(current, row["location"]))
                if row.get("cross_domain") and not policy.follow_cross_domain:
                    raise CrossDomainRedirect(
                        f"{current} redirige vers un autre domaine ({target}) : noté au manifeste, non suivi")
                current = target
                continue
            if 200 <= status < 300:
                return self._result(current, row, tuple(hops), from_cache=not fresh)
            raise HttpError(current, status)

    def _usable(self, row: dict) -> bool:
        """Can this manifest line answer for its URL without a new request?"""
        status = int(row.get("status") or 0)
        if row.get("stop"):
            if self.resume_after_stop:
                return False
            raise Blocked(f"refus enregistré pour {row['url']} (HTTP {status}, {row.get('at')}) ; "
                          "aucune nouvelle tentative sans décision humaine")
        if 200 <= status < 300:
            return True
        if status in REDIRECT_STATUSES or 400 <= status < 500:
            return True
        if self.retry_failed:
            return False
        raise PreviouslyFailed(f"{row['url']} a échoué lors d'un passage précédent "
                               f"(statut {status}, {row.get('at')})")

    def _request(self, url: str, save_as: str, family: str, policy: HostPolicy,
                 expect_prefix: tuple[bytes, ...]) -> dict:
        attempts = 0
        while True:
            if family in self._stopped:
                raise Blocked(f"famille {family} arrêtée : {self._stopped[family]}")
            if self.requests_left(family, policy) <= 0:
                raise BudgetExhausted(f"plafond de {policy.budget} requêtes atteint pour {family}")
            self._wait(family, policy)
            row = self._send(url, save_as, family, policy, expect_prefix)
            self._append(row)
            status = int(row["status"])
            if row.get("stop"):
                raise Blocked(f"{url} : {row.get('note') or 'refus'} (HTTP {status}) — arrêt de la famille {family}")
            if status == 0:
                raise TransportError(f"{url} : pas de réponse ({row.get('error')})")
            if 500 <= status < 600:
                if attempts < policy.max_backoffs:
                    attempts += 1
                    self.sleep(policy.backoff_seconds)
                    continue
                raise ServerUnavailable(f"{url} : HTTP {status} après {attempts} attente(s) — abandon de cet élément")
            return row

    def _wait(self, family: str, policy: HostPolicy) -> None:
        last = self._last_epoch.get(family)
        if last is None:
            return
        remaining = policy.min_delay - (self.clock() - last)
        if remaining > 0:
            self.sleep(remaining)

    def _send(self, url: str, save_as: str, family: str, policy: HostPolicy,
              expect_prefix: tuple[bytes, ...]) -> dict:
        target = self._target(save_as)
        target.parent.mkdir(parents=True, exist_ok=True)
        part = target.with_name(target.name + ".part")
        host = urllib.parse.urlsplit(url).hostname
        row: dict = {"url": url, "method": "GET", "host": host, "family": family, "network": True}
        try:
            answer = self._http_get(url, part, policy)
        except (urllib.error.URLError, http.client.HTTPException, TimeoutError, OSError) as exc:
            part.unlink(missing_ok=True)
            row.update(status=0, bytes=0, sha256=None, file=None, error=type(exc).__name__)
            row.update(at=_now_iso(self.clock()), epoch=self.clock())
            return row
        row.update(status=answer.status, bytes=answer.size, sha256=answer.sha256,
                   elapsed_ms=answer.elapsed_ms, at=_now_iso(self.clock()), epoch=self.clock())
        for name in ("content-type", "retry-after", "location", "cf-mitigated"):
            if answer.headers.get(name):
                row[name.replace("-", "_")] = answer.headers[name]
        refusal = self._refusal(answer, policy, expect_prefix)
        if answer.status in REDIRECT_STATUSES and answer.headers.get("location"):
            destination = urllib.parse.urljoin(url, answer.headers["location"])
            dest_host = urllib.parse.urlsplit(destination).hostname or ""
            row["location"] = destination
            row["cross_domain"] = registrable_domain(dest_host) != family
            part.unlink(missing_ok=True)
            row["file"] = None
        elif refusal:
            refused = target.with_name(target.name + ".refus")
            os.replace(part, refused)
            row.update(stop=True, note=refusal, file=str(refused.relative_to(self.root.resolve())))
        elif 200 <= answer.status < 300:
            os.replace(part, target)
            row["file"] = str(target.relative_to(self.root.resolve()))
        else:
            part.unlink(missing_ok=True)
            row["file"] = None
        return row

    def _refusal(self, answer: _Answer, policy: HostPolicy, expect_prefix: tuple[bytes, ...]) -> str | None:
        """Why this answer must stop the family, or None."""
        if answer.status in policy.stop_statuses:
            return f"statut d'arrêt {answer.status}"
        if answer.headers.get("cf-mitigated"):
            return "défi anti-robot (en-tête cf-mitigated)"
        if 200 <= answer.status < 300:
            if looks_like_antibot(answer.head, policy.antibot_markers):
                return "page anti-robot"
            if expect_prefix and not answer.head.startswith(expect_prefix):
                return "contenu inattendu (ni le format demandé, ni une erreur déclarée)"
        return None

    def _http_get(self, url: str, part: Path, policy: HostPolicy) -> _Answer:
        opener = urllib.request.build_opener(_NoRedirect)
        request = urllib.request.Request(url, method="GET", headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
        began = time.monotonic()
        try:
            response = opener.open(request, timeout=policy.timeout)
        except urllib.error.HTTPError as exc:
            response = exc
        digest = hashlib.sha256()
        size = 0
        head = b""
        try:
            with part.open("wb") as out:
                while True:
                    chunk = response.read(1 << 16)
                    if not chunk:
                        break
                    size += len(chunk)
                    if size > policy.max_bytes:
                        raise OSError(f"réponse de plus de {policy.max_bytes} octets")
                    if len(head) < 4096:
                        head += chunk[: 4096 - len(head)]
                    digest.update(chunk)
                    out.write(chunk)
        finally:
            response.close()
        headers = {key.lower(): value for key, value in response.headers.items()}
        status = getattr(response, "status", None) or response.code
        return _Answer(status=int(status), headers=headers, body_path=part, size=size,
                       sha256=digest.hexdigest(), head=head,
                       elapsed_ms=int((time.monotonic() - began) * 1000))


def _without_fragment(url: str) -> str:
    """The URL as it is sent: a #fragment never reaches the server, so it is not part of the cache key."""
    return urllib.parse.urldefrag(url)[0]


def _now_iso(epoch: float) -> str:
    return datetime.datetime.fromtimestamp(epoch, datetime.timezone.utc).isoformat(timespec="seconds")
