"""The polite client of the project, extended for the reading-room probe.

`SessionClient` is `decretas.net.PoliteClient` (same User-Agent, pacing, manifest, hard stop
on 403/429/anti-bot page) with three additions the probe needs:

- the anonymous session cookie the application sets on its first answer is sent back, as a
  browser would (the base client sends none). The value is kept in memory and in the state
  file of the probe; it is never printed and never written to the manifest;
- every body is kept, error pages and redirect bodies included (the base client keeps only
  2xx bodies), next to the planned file name with the suffix ``.http<status>``;
- one hop at a time: `hop()` sends a single request and returns its manifest line, so that
  the caller records every redirect itself. Answers already in the manifest are reused.

Nothing here retries: on a 5xx or a missing answer the caller's stop rules decide.
"""
from __future__ import annotations

import hashlib
import http.client
import shutil
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

from decretas import net

KEPT_HEADERS = ("server", "via", "content-type", "content-length", "content-disposition", "location",
                "last-modified", "etag", "cache-control", "expires", "retry-after", "x-frame-options",
                "content-security-policy", "www-authenticate", "accept-ranges", "content-encoding")


def mask_cookie(header: str) -> str:
    """'JSESSIONID=abc; Path=/siv/' -> 'JSESSIONID=***; Path=/siv/' (the value is never stored in logs)."""
    first, separator, rest = header.partition(";")
    name, equals, _value = first.partition("=")
    return f"{name.strip()}{equals}***{separator}{rest}"


def mask_session(url: str) -> str:
    """Hide a session identifier carried in a URL (';jsessionid=…')."""
    head, marker, tail = url.partition(";jsessionid=")
    if not marker:
        return url
    end = min((tail.find(ch) for ch in "?#&/" if ch in tail), default=len(tail))
    return head + ";jsessionid=***" + tail[end:]


def strip_session(url: str) -> str:
    """Remove ';jsessionid=…' from a URL: the cookie carries the session."""
    head, marker, tail = url.partition(";jsessionid=")
    if not marker:
        return url
    end = min((tail.find(ch) for ch in "?#&/" if ch in tail), default=len(tail))
    return head + tail[end:]


@dataclass
class SessionClient(net.PoliteClient):
    """See the module docstring. `jar` maps a cookie name to {value, host, path, secure}."""

    jar: dict[str, dict] = field(default_factory=dict)

    def __post_init__(self) -> None:
        super().__post_init__()
        self._exchange: dict = {}

    # ------------------------------------------------------------------ cookies
    def _cookie_header(self, url: str) -> str | None:
        parts = urllib.parse.urlsplit(url)
        host = (parts.hostname or "").lower()
        path = parts.path or "/"
        pairs = [f"{name}={cookie['value']}" for name, cookie in sorted(self.jar.items())
                 if cookie.get("host") == host and path.startswith(cookie.get("path") or "/")
                 and (parts.scheme == "https" or not cookie.get("secure"))]
        return "; ".join(pairs) or None

    def _store_cookies(self, url: str, headers: list[str]) -> None:
        host = (urllib.parse.urlsplit(url).hostname or "").lower()
        for header in headers:
            first, _separator, rest = header.partition(";")
            name, equals, value = first.partition("=")
            name = name.strip()
            if not equals or not name:
                continue
            attributes = {key.strip().lower(): val.strip() for key, _eq, val in
                          (item.partition("=") for item in rest.split(";") if item.strip())}
            self.jar[name] = {"value": value.strip(), "host": host, "path": attributes.get("path", "/"),
                              "secure": "secure" in attributes}

    # ------------------------------------------------------------------ transport
    def _http_get(self, url: str, part: Path, policy: net.HostPolicy) -> net._Answer:
        headers = {"User-Agent": net.USER_AGENT, "Accept": "*/*"}
        cookie = self._cookie_header(url)
        if cookie:
            headers["Cookie"] = cookie
        opener = urllib.request.build_opener(net._NoRedirect)
        request = urllib.request.Request(url, method="GET", headers=headers)
        began = time.monotonic()
        self._exchange = {"cookie_sent": bool(cookie)}
        try:
            response = opener.open(request, timeout=policy.timeout)
        except urllib.error.HTTPError as error:
            response = error
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
        headers_in = {key.lower(): value for key, value in response.headers.items()}
        status = int(getattr(response, "status", None) or response.code)
        set_cookies = response.headers.get_all("Set-Cookie") or []
        self._store_cookies(url, set_cookies)
        side = None
        if not 200 <= status < 300 and size:
            side = part.with_name(part.name[: -len(".part")] + f".http{status}")
            shutil.copyfile(part, side)
        self._exchange.update(
            headers={name: mask_session(headers_in[name]) for name in KEPT_HEADERS if name in headers_in},
            cookies_set=[mask_cookie(header) for header in set_cookies],
            side=side)
        return net._Answer(status=status, headers=headers_in, body_path=part, size=size, sha256=digest.hexdigest(),
                           head=head, elapsed_ms=int((time.monotonic() - began) * 1000))

    def _send(self, url: str, save_as: str, family: str, policy: net.HostPolicy, expect_prefix: tuple[bytes, ...]) -> dict:
        self._exchange = {}
        row = super()._send(url, save_as, family, policy, expect_prefix)
        exchange = self._exchange
        if row.get("location"):
            # a session identifier written in the redirect address is dropped: the cookie carries the
            # session, and the manifest must not hold it
            row["session_dans_adresse"] = ";jsessionid=" in row["location"]
            row["location"] = strip_session(row["location"])
        if exchange.get("headers"):
            row["en_tetes"] = exchange["headers"]
        if exchange.get("cookies_set"):
            row["temoins_poses"] = exchange["cookies_set"]
        if exchange.get("cookie_sent"):
            row["temoin_envoye"] = True
        if exchange.get("side") is not None:
            row["corps_hors_2xx"] = str(Path(exchange["side"]).resolve().relative_to(self.root.resolve()))
        return row

    # ------------------------------------------------------------------ one hop
    def hop(self, url: str, save_as: str, *, force: bool = False) -> tuple[dict, bool]:
        """Send one GET (no redirect following) or reuse its manifest line.

        `force`: send even when the manifest already holds an answer (availability checks).

        Returns (manifest line, sent now?). Raises `net.Blocked` (403/429/anti-bot),
        `net.TransportError` (no answer), `net.ServerUnavailable` (5xx), `net.BudgetExhausted`,
        `net.HostNotAllowed`.
        """
        url = net._without_fragment(url)
        family, policy = self.policy_for(url)
        row = self.cached(url)
        if not force and row is not None and self._usable(row):
            return row, False
        if self.dry_run:
            self.planned.append(url)
            return {"url": url, "status": None, "simulation": True}, False
        try:
            return self._request(url, save_as, family, policy, ()), True
        except (http.client.HTTPException, OSError) as error:  # defensive: _send already maps these
            raise net.TransportError(f"{url} : pas de réponse ({type(error).__name__})") from error
