"""Tests of decretas.net against a local http.server fixture (no outside network)."""
from __future__ import annotations

import gzip
import json
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from decretas import net


class _Handler(BaseHTTPRequestHandler):
    """Routes of the fixture server. `hits` counts requests per path; `agents` keeps User-Agents."""

    hits: dict[str, int] = {}
    agents: list[str] = []
    other_base = ""

    def log_message(self, *_args) -> None:  # silence the test output
        return

    def _send(self, status: int, body: bytes, headers: dict[str, str] | None = None) -> None:
        self.send_response(status)
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802 (name imposed by http.server)
        cls = type(self)
        cls.hits[self.path] = cls.hits.get(self.path, 0) + 1
        cls.agents.append(self.headers.get("User-Agent", ""))
        count = cls.hits[self.path]
        if self.path == "/ok.txt":
            self._send(200, b"bonjour")
        elif self.path == "/data.gz":
            self._send(200, gzip.compress(b"texte synthetique"))
        elif self.path == "/fake.gz":
            self._send(200, b"ceci n'est pas du gzip")
        elif self.path == "/interdit":
            self._send(403, b"non")
        elif self.path == "/trop":
            self._send(429, b"doucement", {"Retry-After": "120"})
        elif self.path == "/antibot":
            self._send(200, b"<!DOCTYPE html><html><title>Just a moment...</title></html>")
        elif self.path == "/panne-puis-ok":
            self._send(503, b"") if count == 1 else self._send(200, b"revenu")
        elif self.path == "/panne":
            self._send(500, b"")
        elif self.path == "/absent":
            self._send(404, b"rien")
        elif self.path == "/vers-ok":
            self._send(302, b"", {"Location": "/ok.txt"})
        elif self.path == "/vers-ailleurs":
            self._send(302, b"", {"Location": cls.other_base + "/ok.txt"})
        else:
            self._send(404, b"")


class FakeTime:
    """A clock that only moves when `sleep` is called: tests never really wait."""

    def __init__(self) -> None:
        self.now = 1_000_000.0
        self.sleeps: list[float] = []

    def clock(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


class NetTestCase(unittest.TestCase):
    def setUp(self) -> None:
        _Handler.hits = {}
        _Handler.agents = []
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        self.port = self.server.server_address[1]
        self.base = f"http://127.0.0.1:{self.port}"
        _Handler.other_base = f"http://localhost:{self.port}"
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
        self.thread.start()
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.time = FakeTime()
        self.policy = net.HostPolicy(min_delay=5.0, budget=10, allow_http=True, backoff_seconds=60.0)

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        self.tmp.cleanup()

    def client(self, **kwargs) -> net.PoliteClient:
        policies = kwargs.pop("policies", {"127.0.0.1": self.policy})
        return net.PoliteClient(root=self.root, policies=policies, clock=self.time.clock,
                                sleep=self.time.sleep, **kwargs)

    def manifest(self) -> list[dict]:
        path = self.root / "manifest.jsonl"
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()] if path.exists() else []

    # ---------------------------------------------------------------- basics
    def test_fetch_saves_body_and_writes_one_manifest_line(self) -> None:
        result = self.client().fetch(self.base + "/ok.txt", "a/ok.txt")
        self.assertEqual(result.status, 200)
        self.assertFalse(result.from_cache)
        self.assertEqual((self.root / "a/ok.txt").read_bytes(), b"bonjour")
        rows = self.manifest()
        self.assertEqual(len(rows), 1)
        row = rows[0]
        for key in ("url", "status", "bytes", "sha256", "at"):
            self.assertIn(key, row)
        self.assertEqual(row["bytes"], 7)
        self.assertEqual(row["sha256"], net.sha256_of(self.root / "a/ok.txt"))
        self.assertEqual(row["file"], "a/ok.txt")

    def test_user_agent_is_the_fixed_honest_one(self) -> None:
        self.client().fetch(self.base + "/ok.txt", "ok.txt")
        self.assertEqual(_Handler.agents, [net.USER_AGENT])
        self.assertNotIn("@", net.USER_AGENT)
        self.assertNotIn("Mozilla", net.USER_AGENT)

    def test_same_url_is_never_requested_twice_even_by_a_new_client(self) -> None:
        self.client().fetch(self.base + "/ok.txt", "ok.txt")
        again = self.client().fetch(self.base + "/ok.txt", "ok.txt")
        self.assertTrue(again.from_cache)
        self.assertEqual(_Handler.hits["/ok.txt"], 1)
        self.assertEqual(len(self.manifest()), 1)

    def test_corrupted_cache_file_is_reported_not_silently_refetched(self) -> None:
        self.client().fetch(self.base + "/ok.txt", "ok.txt")
        (self.root / "ok.txt").write_bytes(b"modifie")
        with self.assertRaises(net.CacheCorrupt):
            self.client().fetch(self.base + "/ok.txt", "ok.txt")
        self.assertEqual(_Handler.hits["/ok.txt"], 1)

    def test_host_without_policy_is_refused_before_any_request(self) -> None:
        with self.assertRaises(net.HostNotAllowed):
            self.client(policies={"exemple.invalid": self.policy}).fetch(self.base + "/ok.txt", "ok.txt")
        self.assertEqual(_Handler.hits, {})

    def test_plain_http_needs_an_explicit_permission(self) -> None:
        strict = net.HostPolicy(allow_http=False)
        with self.assertRaises(net.HostNotAllowed):
            self.client(policies={"127.0.0.1": strict}).fetch(self.base + "/ok.txt", "ok.txt")

    def test_save_path_cannot_leave_the_cache_root(self) -> None:
        with self.assertRaises(net.NetError):
            self.client().fetch(self.base + "/ok.txt", "../dehors.txt")
        self.assertEqual(_Handler.hits, {})

    # ---------------------------------------------------------------- pacing and budget
    def test_minimum_delay_between_two_requests_of_a_family(self) -> None:
        client = self.client()
        client.fetch(self.base + "/ok.txt", "ok.txt")
        client.fetch(self.base + "/data.gz", "data.gz")
        self.assertEqual(self.time.sleeps, [5.0])

    def test_delay_is_kept_across_runs_through_the_manifest(self) -> None:
        self.client().fetch(self.base + "/ok.txt", "ok.txt")
        self.time.now += 2.0
        self.client().fetch(self.base + "/data.gz", "data.gz")
        self.assertEqual(self.time.sleeps, [3.0])

    def test_no_delay_for_a_cache_hit(self) -> None:
        client = self.client()
        client.fetch(self.base + "/ok.txt", "ok.txt")
        client.fetch(self.base + "/ok.txt", "ok.txt")
        self.assertEqual(self.time.sleeps, [])

    def test_budget_stops_the_family(self) -> None:
        tight = net.HostPolicy(min_delay=0.0, budget=2, allow_http=True)
        client = self.client(policies={"127.0.0.1": tight})
        client.fetch(self.base + "/ok.txt", "ok.txt")
        client.fetch(self.base + "/data.gz", "data.gz")
        with self.assertRaises(net.BudgetExhausted):
            client.fetch(self.base + "/absent", "absent")
        self.assertNotIn("/absent", _Handler.hits)

    def test_budget_counts_earlier_runs_unless_told_otherwise(self) -> None:
        tight = net.HostPolicy(min_delay=0.0, budget=1, allow_http=True)
        self.client(policies={"127.0.0.1": tight}).fetch(self.base + "/ok.txt", "ok.txt")
        with self.assertRaises(net.BudgetExhausted):
            self.client(policies={"127.0.0.1": tight}).fetch(self.base + "/data.gz", "data.gz")
        per_run = self.client(policies={"127.0.0.1": tight}, count_manifest_in_budget=False)
        self.assertEqual(per_run.fetch(self.base + "/data.gz", "data.gz").status, 200)

    # ---------------------------------------------------------------- stop rules
    def test_403_stops_the_family_and_is_never_retried(self) -> None:
        client = self.client()
        with self.assertRaises(net.Blocked):
            client.fetch(self.base + "/interdit", "x.bin")
        with self.assertRaises(net.Blocked):
            client.fetch(self.base + "/ok.txt", "ok.txt")
        self.assertEqual(_Handler.hits, {"/interdit": 1})
        self.assertTrue(self.manifest()[0]["stop"])
        self.assertTrue((self.root / "x.bin.refus").exists())
        self.assertFalse((self.root / "x.bin").exists())

    def test_stop_persists_for_later_runs_until_a_human_lifts_it(self) -> None:
        with self.assertRaises(net.Blocked):
            self.client().fetch(self.base + "/trop", "x.bin")
        with self.assertRaises(net.Blocked):
            self.client().fetch(self.base + "/ok.txt", "ok.txt")
        self.assertEqual(_Handler.hits, {"/trop": 1})
        self.assertEqual(self.manifest()[0]["retry_after"], "120")
        resumed = self.client(resume_after_stop=True).fetch(self.base + "/ok.txt", "ok.txt")
        self.assertEqual(resumed.status, 200)

    def test_antibot_page_with_status_200_is_a_stop(self) -> None:
        with self.assertRaises(net.Blocked):
            self.client().fetch(self.base + "/antibot", "page.html")
        self.assertFalse((self.root / "page.html").exists())
        self.assertTrue(self.manifest()[0]["stop"])

    def test_unexpected_body_is_a_stop_when_a_format_is_expected(self) -> None:
        client = self.client()
        good = client.fetch(self.base + "/data.gz", "data.gz", expect_prefix=(b"\x1f\x8b",))
        self.assertEqual(gzip.decompress(good.read_bytes()), b"texte synthetique")
        with self.assertRaises(net.Blocked):
            client.fetch(self.base + "/fake.gz", "fake.gz", expect_prefix=(b"\x1f\x8b",))

    def test_5xx_backs_off_once_then_succeeds(self) -> None:
        result = self.client().fetch(self.base + "/panne-puis-ok", "p.txt")
        self.assertEqual(result.read_bytes(), b"revenu")
        self.assertIn(60.0, self.time.sleeps)
        self.assertEqual(_Handler.hits["/panne-puis-ok"], 2)
        self.assertEqual([row["status"] for row in self.manifest()], [503, 200])

    def test_5xx_twice_abandons_the_item_but_not_the_family(self) -> None:
        client = self.client()
        with self.assertRaises(net.ServerUnavailable):
            client.fetch(self.base + "/panne", "p.txt")
        self.assertEqual(_Handler.hits["/panne"], 2)
        self.assertEqual(client.fetch(self.base + "/ok.txt", "ok.txt").status, 200)

    def test_failed_url_is_not_retried_in_a_later_run_unless_asked(self) -> None:
        with self.assertRaises(net.ServerUnavailable):
            self.client().fetch(self.base + "/panne", "p.txt")
        with self.assertRaises(net.PreviouslyFailed):
            self.client().fetch(self.base + "/panne", "p.txt")
        self.assertEqual(_Handler.hits["/panne"], 2)
        with self.assertRaises(net.ServerUnavailable):
            self.client(retry_failed=True).fetch(self.base + "/panne", "p.txt")
        self.assertEqual(_Handler.hits["/panne"], 4)

    def test_404_is_definitive_and_cached(self) -> None:
        client = self.client()
        with self.assertRaises(net.HttpError) as caught:
            client.fetch(self.base + "/absent", "a.txt")
        self.assertEqual(caught.exception.status, 404)
        with self.assertRaises(net.HttpError):
            self.client().fetch(self.base + "/absent", "a.txt")
        self.assertEqual(_Handler.hits["/absent"], 1)

    def test_no_answer_is_logged_with_status_zero(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        with self.assertRaises(net.TransportError):
            self.client().fetch(self.base + "/ok.txt", "ok.txt")
        self.assertEqual(self.manifest()[0]["status"], 0)
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
        self.thread.start()

    # ---------------------------------------------------------------- redirects
    def test_same_domain_redirect_is_followed_and_every_hop_is_logged(self) -> None:
        result = self.client().fetch(self.base + "/vers-ok", "ok.txt")
        self.assertEqual(result.read_bytes(), b"bonjour")
        self.assertEqual(result.final_url, self.base + "/ok.txt")
        rows = self.manifest()
        self.assertEqual([row["status"] for row in rows], [302, 200])
        self.assertFalse(rows[0]["cross_domain"])
        self.assertEqual(self.time.sleeps, [5.0])

    def test_cross_domain_redirect_is_recorded_and_not_followed_by_default(self) -> None:
        with self.assertRaises(net.CrossDomainRedirect):
            self.client().fetch(self.base + "/vers-ailleurs", "ok.txt")
        rows = self.manifest()
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0]["cross_domain"])
        self.assertTrue(rows[0]["location"].startswith("http://localhost:"))
        self.assertNotIn("/ok.txt", _Handler.hits)

    def test_cross_domain_redirect_followed_only_when_policy_allows_and_target_has_a_policy(self) -> None:
        open_policy = net.HostPolicy(min_delay=0.0, budget=5, allow_http=True, follow_cross_domain=True)
        with self.assertRaises(net.HostNotAllowed):
            self.client(policies={"127.0.0.1": open_policy}).fetch(self.base + "/vers-ailleurs", "a.txt")
        both = {"127.0.0.1": open_policy, "localhost": open_policy}
        result = self.client(policies=both).fetch(self.base + "/vers-ailleurs", "a.txt")
        self.assertEqual(result.read_bytes(), b"bonjour")
        self.assertTrue(any(row.get("cross_domain") for row in self.manifest()))

    # ---------------------------------------------------------------- dry run, adoption
    def test_dry_run_sends_nothing_and_lists_what_it_would_fetch(self) -> None:
        client = self.client(dry_run=True)
        result = client.fetch(self.base + "/ok.txt", "ok.txt")
        self.assertTrue(result.dry_run)
        self.assertIsNone(result.path)
        self.assertEqual(client.planned, [self.base + "/ok.txt"])
        self.assertEqual(_Handler.hits, {})
        self.assertEqual(self.manifest(), [])

    def test_dry_run_still_serves_the_cache(self) -> None:
        self.client().fetch(self.base + "/ok.txt", "ok.txt")
        result = self.client(dry_run=True).fetch(self.base + "/ok.txt", "ok.txt")
        self.assertTrue(result.from_cache)
        self.assertFalse(result.dry_run)

    def test_adopt_registers_an_earlier_download_without_any_request(self) -> None:
        source = self.root / "ailleurs.bin"
        source.write_bytes(b"deja la")
        client = self.client()
        client.adopt(self.base + "/ok.txt", source, "b/ok.txt", note="repris d'une session antérieure")
        result = client.fetch(self.base + "/ok.txt", "b/ok.txt")
        self.assertTrue(result.from_cache)
        self.assertEqual(result.read_bytes(), b"deja la")
        self.assertEqual(_Handler.hits, {})
        self.assertFalse(self.manifest()[0]["network"])
        self.assertEqual(client.requests_used("127.0.0.1"), 0)


    def test_dry_run_adopts_in_memory_only_and_writes_nothing(self) -> None:
        # regression: « --simulation » copied the earlier downloads into the cache and wrote their manifest lines
        earlier = self.root.parent / (self.root.name + "-ancien.txt")
        earlier.write_bytes(b"ancien")
        try:
            client = self.client(dry_run=True)
            adopted = client.adopt(self.base + "/ok.txt", earlier, "a/ok.txt", note="essai")
            self.assertEqual(adopted.read_bytes(), b"ancien")
            planned = client.fetch(self.base + "/ok.txt", "a/ok.txt")
            self.assertTrue(planned.from_cache)                      # the plan shows it as already there
            self.assertEqual(client.planned, [])
            self.assertEqual(list(self.root.iterdir()), [])          # no file, no manifest
            self.assertEqual(_Handler.hits, {})
        finally:
            earlier.unlink()

    def test_fragment_is_not_part_of_the_cache_key(self) -> None:
        # regression: « /ok.txt#a » and « /ok.txt#b » were two requests for the same resource
        client = self.client()
        client.fetch(self.base + "/ok.txt#page=3", "a/ok.txt")
        again = client.fetch(self.base + "/ok.txt#page=9", "a/ok.txt")
        self.assertTrue(again.from_cache)
        self.assertEqual(_Handler.hits, {"/ok.txt": 1})
        self.assertEqual([row["url"] for row in self.manifest()], [self.base + "/ok.txt"])


class PureFunctionsTestCase(unittest.TestCase):
    def test_registrable_domain(self) -> None:
        self.assertEqual(net.registrable_domain("ia601506.us.archive.org"), "archive.org")
        self.assertEqual(net.registrable_domain("archive.org"), "archive.org")
        self.assertEqual(net.registrable_domain("www.siv.archives-nationales.culture.gouv.fr"), "culture.gouv.fr")
        self.assertEqual(net.registrable_domain("127.0.0.1"), "127.0.0.1")
        self.assertEqual(net.registrable_domain("localhost"), "localhost")

    def test_policy_lookup_uses_the_longest_matching_suffix(self) -> None:
        slow = net.HostPolicy(min_delay=30.0)
        fast = net.HostPolicy(min_delay=5.0)
        client = net.PoliteClient(root=Path(tempfile.gettempdir()) / "decretas-inexistant",
                                  policies={"archive.org": fast, "us.archive.org": slow}, dry_run=True)
        self.assertIs(client.policy_for("https://ia601506.us.archive.org/x")[1], slow)
        self.assertIs(client.policy_for("https://archive.org/metadata/x")[1], fast)
        self.assertEqual(client.policy_for("https://ia601506.us.archive.org/x")[0], "archive.org")

    def test_antibot_detection_ignores_binary_and_plain_bodies(self) -> None:
        markers = net.DEFAULT_ANTIBOT_MARKERS
        self.assertTrue(net.looks_like_antibot(b"<html><body>Please solve this CAPTCHA</body></html>", markers))
        self.assertFalse(net.looks_like_antibot(b"\x1f\x8b captcha", markers))
        self.assertFalse(net.looks_like_antibot(b'{"note": "captcha"}', markers))


if __name__ == "__main__":
    unittest.main()
