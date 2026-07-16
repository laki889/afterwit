"""Tests for the dashboard: report snapshot self-containment + escaping,
and the serve HTTP surface (binding, endpoints, headers, read-only)."""

import http.client
import json
import os
import re
import sys
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "plugins" / "afterwit" / "src"))


def _seed(title="Zombie process holds port", lesson="Check stale listeners."):
    from afterwit import store
    conn = store.connect()
    store.insert_lesson(
        conn, title=title, problem="502s after release", lesson=lesson,
        root_cause="no pre-start cleanup", resolution="ExecStartPre kill",
        confidence=0.9, project="acme-app", session_id="s1",
        source_ts="2026-07-10T14:00:01Z", tags=["deploy"],
    )
    conn.commit()
    conn.close()


class ReportTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        os.environ["AFTERWIT_DATA_DIR"] = self._tmp.name

    def tearDown(self):
        os.environ.pop("AFTERWIT_DATA_DIR", None)
        self._tmp.cleanup()

    def test_snapshot_is_self_contained(self):
        _seed()
        from afterwit import report
        out = Path(self._tmp.name) / "lessons.html"
        path = report.write(out=str(out))
        html = path.read_text(encoding="utf-8")
        # data inlined
        self.assertIn("Zombie process holds port", html)
        self.assertIn('"db_exists": true', html.replace("&quot;", '"').lower()
                      .replace('"db_exists":true', '"db_exists": true'))
        # no external resource references anywhere
        for pattern in ("http://", "https://", "//cdn", "@import", "url("):
            for m in re.finditer(re.escape(pattern), html):
                ctx = html[max(0, m.start() - 60): m.start() + 80]
                # the only allowed URL-ish text is the SVG xmlns namespace
                self.assertIn("w3.org", ctx, f"external reference? …{ctx}…")

    def test_script_breakout_is_escaped(self):
        _seed(title="</script><script>alert(1)</script>",
              lesson="<!--sneaky--> <img src=x onerror=alert(2)>")
        from afterwit import report
        out = Path(self._tmp.name) / "lessons.html"
        html = report.write(out=str(out)).read_text(encoding="utf-8")
        # the raw closing tag from lesson content must never appear;
        # every '<' in the payload is < so the script can't be terminated
        self.assertEqual(html.count("</script>"), 1)   # the template's own
        self.assertIn("\\u003c/script>", html)
        self.assertNotIn("<img src=x", html)

    def test_report_on_empty_db(self):
        from afterwit import report
        out = Path(self._tmp.name) / "empty.html"
        html = report.write(out=str(out)).read_text(encoding="utf-8")
        self.assertIn('"db_exists"', html)

    def test_project_filter(self):
        _seed()
        _seed(title="Other project lesson", lesson="x")
        from afterwit import store
        conn = store.connect()
        store.insert_lesson(conn, title="From proj B", problem="p", lesson="l",
                            project="proj-b")
        conn.commit(); conn.close()
        from afterwit import report
        out = Path(self._tmp.name) / "one.html"
        html = report.write(out=str(out), project="proj-b").read_text(encoding="utf-8")
        self.assertIn("From proj B", html)
        self.assertNotIn("Zombie process", html)


class ServeTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        os.environ["AFTERWIT_DATA_DIR"] = self._tmp.name
        _seed()
        from afterwit import serve
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), serve.Handler)
        self.port = self.httpd.server_address[1]
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        os.environ.pop("AFTERWIT_DATA_DIR", None)
        self._tmp.cleanup()

    def _get(self, path):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        conn.request("GET", path)
        resp = conn.getresponse()
        body = resp.read()
        headers = dict(resp.getheaders())
        conn.close()
        return resp.status, headers, body

    def test_index_serves_dashboard(self):
        status, headers, body = self._get("/")
        self.assertEqual(status, 200)
        self.assertIn("text/html", headers["Content-Type"])
        self.assertIn(b"afterwit", body)
        self.assertIn(b"var BOOT = null", body)

    def test_api_data(self):
        status, headers, body = self._get("/api/data")
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertTrue(data["db_exists"])
        self.assertEqual(len(data["lessons"]), 1)
        self.assertEqual(data["lessons"][0]["title"], "Zombie process holds port")
        self.assertEqual(data["stats"]["total_lessons"], 1)

    def test_security_headers(self):
        _, headers, _ = self._get("/")
        csp = headers["Content-Security-Policy"]
        self.assertIn("default-src 'none'", csp)
        self.assertIn("connect-src 'self'", csp)
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(headers["Referrer-Policy"], "no-referrer")

    def test_no_filesystem_serving(self):
        for path in ("/etc/passwd", "/../etc/passwd", "/static/x.css",
                     "/api/../__init__.py", "/favicon.ico"):
            status, _, _ = self._get(path)
            self.assertEqual(status, 404, path)

    def test_api_data_with_missing_db(self):
        os.environ["AFTERWIT_DATA_DIR"] = str(Path(self._tmp.name) / "nowhere")
        try:
            status, _, body = self._get("/api/data")
            self.assertEqual(status, 200)
            self.assertFalse(json.loads(body)["db_exists"])
        finally:
            os.environ["AFTERWIT_DATA_DIR"] = self._tmp.name

    def test_binds_loopback_only(self):
        from afterwit import serve
        self.assertEqual(serve.HOST, "127.0.0.1")
        self.assertEqual(self.httpd.server_address[0], "127.0.0.1")

    def test_dns_rebinding_host_rejected(self):
        """A rebound hostname still sends its own Host header — must be 403."""
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        conn.request("GET", "/api/data", headers={"Host": f"attacker.com:{self.port}"})
        self.assertEqual(conn.getresponse().status, 403)
        conn.close()
        # legitimate loopback Hosts (with and without port) still pass
        for host in (f"127.0.0.1:{self.port}", "localhost", f"localhost:{self.port}"):
            conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
            conn.request("GET", "/api/data", headers={"Host": host})
            self.assertEqual(conn.getresponse().status, 200, host)
            conn.close()

    def test_corrupt_db_degrades_instead_of_crashing(self):
        from afterwit import paths
        paths.db_path().write_text("this is not a sqlite database at all")
        status, _, body = self._get("/api/data")
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertFalse(data["db_exists"])
        self.assertEqual(data["lessons"], [])


if __name__ == "__main__":
    unittest.main()
