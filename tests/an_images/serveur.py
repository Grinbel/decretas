"""A local, fictitious reading room for the tests: an http.server on 127.0.0.1.

Routes are declared by the test. A route is one answer or a list of answers served in turn
(the last one repeats). Every request is recorded with its Cookie header.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


@dataclass
class Answer:
    status: int = 200
    body: bytes = b""
    headers: dict[str, str] = field(default_factory=dict)
    cookies: tuple[str, ...] = ()
    delay: float = 0.0


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args) -> None:
        return

    def do_GET(self) -> None:  # noqa: N802 (name imposed by http.server)
        site: Site = self.server.site  # type: ignore[attr-defined]
        site.requests.append((self.path, self.headers.get("Cookie"), self.headers.get("User-Agent")))
        route = site.routes.get(self.path)
        if route is None:
            answer = Answer(404, b"<html><title>absent</title></html>", {"Content-Type": "text/html"})
        elif isinstance(route, list):
            index = min(site.served.get(self.path, 0), len(route) - 1)
            answer = route[index]
        else:
            answer = route
        site.served[self.path] = site.served.get(self.path, 0) + 1
        if answer.delay:
            time.sleep(answer.delay)
        try:
            self.send_response(answer.status)
            for key, value in answer.headers.items():
                self.send_header(key, value)
            for cookie in answer.cookies:
                self.send_header("Set-Cookie", cookie)
            self.send_header("Content-Length", str(len(answer.body)))
            self.end_headers()
            self.wfile.write(answer.body)
        except (BrokenPipeError, ConnectionResetError):
            pass                                  # the client gave up (time-out test)


class _QuietServer(ThreadingHTTPServer):
    daemon_threads = True

    def handle_error(self, request, client_address) -> None:  # silence the traceback of an abandoned request
        return


class Site:
    def __init__(self) -> None:
        self.routes: dict[str, Answer | list[Answer]] = {}
        self.requests: list[tuple[str, str | None, str | None]] = []
        self.served: dict[str, int] = {}
        self._server = _QuietServer(("127.0.0.1", 0), _Handler)
        self._server.site = self  # type: ignore[attr-defined]
        self._thread = threading.Thread(target=self._server.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True)
        self._thread.start()

    @property
    def base(self) -> str:
        return f"http://127.0.0.1:{self._server.server_address[1]}"

    def html(self, path: str, text: str, **kwargs) -> None:
        self.routes[path] = Answer(200, text.encode("utf-8"), {"Content-Type": "text/html;charset=UTF-8"}, **kwargs)

    def image(self, path: str, data: bytes) -> None:
        self.routes[path] = Answer(200, data, {"Content-Type": "image/jpeg"})

    def redirect(self, path: str, location: str, status: int = 302, cookies: tuple[str, ...] = ()) -> None:
        self.routes[path] = Answer(status, b"", {"Location": location}, cookies)

    def paths(self) -> list[str]:
        return [path for path, _cookie, _agent in self.requests]

    def close(self) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=5)


class FakeClock:
    """A clock the tests move by hand; `sleep` advances it instead of waiting."""

    def __init__(self, start: float = 1_800_000_000.0) -> None:
        self.now = start
        self.slept: list[float] = []

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.now += seconds
