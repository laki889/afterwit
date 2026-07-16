"""MCP server tests — drive mcp/query_lessons.py as a real subprocess over
stdio, exactly as Claude Code's MCP client would."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "plugins" / "afterwit" / "src"))

SERVER = Path(__file__).resolve().parents[1] / "plugins" / "afterwit" / "mcp" / "query_lessons.py"


class McpServerTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        os.environ["AFTERWIT_DATA_DIR"] = self._tmp.name
        from afterwit import store
        conn = store.connect()
        store.insert_lesson(
            conn, title="SQLite WAL needed for concurrent readers",
            problem="database is locked under parallel access",
            root_cause="rollback journal blocks readers during writes",
            resolution="PRAGMA journal_mode=WAL",
            lesson="Enable WAL so one writer and many readers coexist.",
            confidence=0.9, project="acme-app", session_id="s1",
            source_ts="2026-07-10T14:00:01Z", tags=["sqlite", "concurrency"],
        )
        store.insert_lesson(
            conn, title="Zombie process holds port after failed deploy",
            problem="502s after release", lesson="Check stale listeners first.",
            confidence=0.8, project="other-proj", session_id="s2",
            tags=["deploy"],
        )
        conn.commit()
        conn.close()

    def tearDown(self):
        os.environ.pop("AFTERWIT_DATA_DIR", None)
        self._tmp.cleanup()

    def _run_session(self, requests, data_dir=None):
        """Send JSON-RPC lines to a fresh server process; return responses."""
        env = dict(os.environ)
        env["AFTERWIT_DATA_DIR"] = data_dir or self._tmp.name
        stdin = "\n".join(json.dumps(r) if isinstance(r, dict) else r for r in requests) + "\n"
        proc = subprocess.run(
            [sys.executable, str(SERVER)],
            input=stdin, capture_output=True, text=True, timeout=30, env=env,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return [json.loads(line) for line in proc.stdout.splitlines() if line.strip()]

    def _handshake(self):
        return [
            {"jsonrpc": "2.0", "id": 0, "method": "initialize",
             "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                        "clientInfo": {"name": "test", "version": "0"}}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
        ]

    def test_initialize_and_list_tools(self):
        out = self._run_session(
            self._handshake() + [{"jsonrpc": "2.0", "id": 1, "method": "tools/list"}]
        )
        init = next(r for r in out if r.get("id") == 0)
        self.assertEqual(init["result"]["protocolVersion"], "2025-06-18")
        self.assertEqual(init["result"]["serverInfo"]["name"], "afterwit-lessons")
        tools = next(r for r in out if r.get("id") == 1)["result"]["tools"]
        self.assertEqual(
            {t["name"] for t in tools},
            {"query_lessons", "recent_lessons", "lesson_stats"},
        )
        # the initialized notification must not receive a response
        self.assertEqual(len(out), 2)

    def test_query_lessons(self):
        out = self._run_session(self._handshake() + [
            {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
             "params": {"name": "query_lessons", "arguments": {"query": "locked database"}}},
        ])
        result = next(r for r in out if r.get("id") == 1)["result"]
        self.assertFalse(result["isError"])
        text = result["content"][0]["text"]
        self.assertIn("SQLite WAL", text)
        self.assertIn("Root cause:", text)
        self.assertNotIn("Zombie", text)

    def test_query_by_tag_only(self):
        out = self._run_session(self._handshake() + [
            {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
             "params": {"name": "query_lessons", "arguments": {"tag": "deploy"}}},
        ])
        text = next(r for r in out if r.get("id") == 1)["result"]["content"][0]["text"]
        self.assertIn("Zombie", text)
        self.assertNotIn("SQLite WAL", text)

    def test_query_requires_some_filter(self):
        out = self._run_session(self._handshake() + [
            {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
             "params": {"name": "query_lessons", "arguments": {}}},
        ])
        result = next(r for r in out if r.get("id") == 1)["result"]
        self.assertTrue(result["isError"])

    def test_recent_lessons_prefers_project(self):
        out = self._run_session(self._handshake() + [
            {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
             "params": {"name": "recent_lessons", "arguments": {"n": 1, "project": "acme-app"}}},
        ])
        text = next(r for r in out if r.get("id") == 1)["result"]["content"][0]["text"]
        self.assertIn("SQLite WAL", text)

    def test_lesson_stats(self):
        out = self._run_session(self._handshake() + [
            {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
             "params": {"name": "lesson_stats", "arguments": {}}},
        ])
        text = next(r for r in out if r.get("id") == 1)["result"]["content"][0]["text"]
        self.assertIn("Total lessons: 2", text)
        self.assertIn("#sqlite", text)

    def test_missing_db_is_friendly(self):
        empty = tempfile.mkdtemp()
        out = self._run_session(self._handshake() + [
            {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
             "params": {"name": "recent_lessons", "arguments": {}}},
        ], data_dir=empty)
        result = next(r for r in out if r.get("id") == 1)["result"]
        self.assertFalse(result["isError"])
        self.assertIn("No lessons database", result["content"][0]["text"])

    def test_protocol_errors(self):
        out = self._run_session(self._handshake() + [
            "this is not json",
            {"jsonrpc": "2.0", "id": 7, "method": "no/such/method"},
            {"jsonrpc": "2.0", "id": 8, "method": "tools/call",
             "params": {"name": "no_such_tool", "arguments": {}}},
            {"jsonrpc": "2.0", "id": 9, "method": "ping"},
        ])
        parse_err = next(r for r in out if r.get("id") is None and "error" in r)
        self.assertEqual(parse_err["error"]["code"], -32700)
        self.assertEqual(next(r for r in out if r.get("id") == 7)["error"]["code"], -32601)
        self.assertEqual(next(r for r in out if r.get("id") == 8)["error"]["code"], -32602)
        self.assertEqual(next(r for r in out if r.get("id") == 9)["result"], {})

    def test_server_never_writes_db(self):
        from afterwit import paths
        db = Path(self._tmp.name) / "afterwit.db"
        before = db.read_bytes()
        self._run_session(self._handshake() + [
            {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
             "params": {"name": "lesson_stats", "arguments": {}}},
        ])
        self.assertEqual(db.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
