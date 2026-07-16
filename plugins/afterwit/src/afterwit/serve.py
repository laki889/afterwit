"""`afterwit serve` — the local dashboard server.

Privacy/security posture:
  - Binds to 127.0.0.1 ONLY (hard-coded; not configurable) — never reachable
    from the network.
  - Opens the database strictly read-only, per request (no shared write
    handle, no cross-thread connection reuse).
  - Serves exactly two things: the inline-asset dashboard page and a JSON
    endpoint. No filesystem paths are ever served, so there is no traversal
    surface. Everything else is 404.
  - Sends a restrictive CSP so the page cannot load or contact anything
    beyond itself even if a rendering bug slipped in.
"""

from __future__ import annotations

import json
import sqlite3
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from . import paths, store, webui
from .store import utcnow

HOST = "127.0.0.1"  # loopback only — do not make configurable
DEFAULT_PORT = 8377
MAX_LESSONS = 5000

_CSP = (
    "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; "
    "connect-src 'self'; img-src data:; base-uri 'none'; form-action 'none'"
)


def gather_data() -> dict:
    """Everything the dashboard needs, in one payload. Read-only, and it never
    raises: a missing, truncated, or foreign database degrades to an empty
    payload instead of killing the request (or `afterwit report`)."""
    data = {
        "generated_at": utcnow(),
        "db_path": str(paths.db_path()),
        "db_exists": True,
        "lessons": [],
        "stats": {},
    }
    try:
        conn = store.connect(readonly=True)
    except sqlite3.Error:
        data["db_exists"] = False
        return data
    try:
        data["lessons"] = store.list_lessons(conn, limit=MAX_LESSONS)
        data["stats"] = store.stats(conn)
    except sqlite3.Error as e:
        data["db_exists"] = False
        data["lessons"] = []
        data["stats"] = {}
        data["error"] = f"database unreadable: {str(e)[:120]}"
    finally:
        conn.close()
    return data


_ALLOWED_HOSTNAMES = {"127.0.0.1", "localhost", "[::1]", "::1"}


class Handler(BaseHTTPRequestHandler):
    server_version = "afterwit"
    sys_version = ""

    def _host_allowed(self) -> bool:
        """Reject any Host header that isn't loopback. This is the standard
        DNS-rebinding defense for localhost servers: a malicious site that
        rebinds its hostname to 127.0.0.1 still sends `Host: attacker.com`,
        so its scripts can never read /api/data."""
        host = (self.headers.get("Host") or "").strip().lower()
        if host.startswith("["):  # [::1] or [::1]:port
            hostname = host.split("]")[0] + "]"
            port_part = host.split("]", 1)[1].lstrip(":")
        else:
            hostname, _, port_part = host.partition(":")
        if hostname not in _ALLOWED_HOSTNAMES:
            return False
        server_port = self.server.server_address[1]
        return port_part in ("", str(server_port))

    def do_GET(self):  # noqa: N802 (http.server API)
        if not self._host_allowed():
            self._respond(403, "text/plain; charset=utf-8", b"forbidden host")
            return
        path = urlparse(self.path).path
        if path == "/":
            body = webui.render_page("null").encode("utf-8")
            self._respond(200, "text/html; charset=utf-8", body)
        elif path == "/api/data":
            body = json.dumps(gather_data(), ensure_ascii=False).encode("utf-8")
            self._respond(200, "application/json; charset=utf-8", body)
        else:
            self._respond(404, "text/plain; charset=utf-8", b"not found")

    def _respond(self, status: int, ctype: str, body: bytes) -> None:
        try:
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Content-Security-Policy", _CSP)
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass  # client went away mid-response — not our problem

    def log_message(self, format, *args):  # noqa: A002
        pass  # keep the terminal quiet; this is a local single-user tool


def run(port: int = DEFAULT_PORT, open_browser: bool = False) -> None:
    try:
        httpd = ThreadingHTTPServer((HOST, port), Handler)
    except OSError as e:
        raise SystemExit(
            f"cannot bind {HOST}:{port} ({e.strerror or e}). "
            f"Is another afterwit serve running? Try --port {port + 1}."
        )
    url = f"http://{HOST}:{port}/"
    print(f"afterwit dashboard: {url}  (local only — Ctrl+C to stop)")
    if open_browser:
        webbrowser.open(url)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped.")
    finally:
        httpd.server_close()
