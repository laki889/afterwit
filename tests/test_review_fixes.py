"""Regression tests for defects found in the adversarial review pass."""

import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "plugins" / "afterwit" / "src"))

from afterwit import synth  # noqa: E402

FIXTURE = Path(__file__).parent / "fixtures" / "sample_transcript.jsonl"


class SynthFixesTestCase(unittest.TestCase):
    def test_bare_lesson_object_accepted(self):
        item = {"title": "T", "problem": "p", "lesson": "L"}
        lessons, err = synth.parse_lessons(json.dumps(item))
        self.assertIsNone(err)
        self.assertEqual(len(lessons), 1)

    def test_missing_binary_is_backend_unavailable(self):
        os.environ["AFTERWIT_CLAUDE_BIN"] = "/nonexistent/claude-binary"
        try:
            with self.assertRaises(synth.BackendUnavailable):
                synth.call_claude("p", "t", {})
        finally:
            os.environ.pop("AFTERWIT_CLAUDE_BIN", None)


class DedupKeyFixesTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        os.environ["AFTERWIT_DATA_DIR"] = self._tmp.name
        from afterwit import store
        self.store = store

    def tearDown(self):
        os.environ.pop("AFTERWIT_DATA_DIR", None)
        self._tmp.cleanup()

    def test_non_latin_titles_get_distinct_keys(self):
        k1 = self.store.dedup_key("Проблема са портом после деплоја", "лекција један")
        k2 = self.store.dedup_key("Кеш инвалидација у Редису", "лекција два")
        self.assertNotEqual(k1, k2)
        self.assertTrue(k1 and k2)

    def test_symbol_only_titles_never_collide(self):
        k1 = self.store.dedup_key("!!!", "???")
        k2 = self.store.dedup_key("###", "$$$")
        self.assertNotEqual(k1, k2)

    def test_query_queries_collide(self):
        self.assertEqual(
            self.store.dedup_key("N+1 query in loop", "x"),
            self.store.dedup_key("N+1 queries in loops", "x"),
        )

    def test_unique_index_backstop(self):
        conn = self.store.connect()
        try:
            # Bypass the check-then-insert guard to hit the index directly.
            conn.execute(
                "INSERT INTO lessons (title, problem, lesson, created_at, dedup_key, project)"
                " VALUES ('a', 'p', 'l', '2026-01-01T00:00:00Z', 'k1', 'proj')"
            )
            lid = self.store.insert_lesson(
                conn, title="whatever", problem="p", lesson="l", project="proj"
            )
            self.assertIsNotNone(lid)  # different key inserts fine
            import sqlite3
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute(
                    "INSERT INTO lessons (title, problem, lesson, created_at, dedup_key, project)"
                    " VALUES ('b', 'p', 'l', '2026-01-01T00:00:00Z', 'k1', 'proj')"
                )
        finally:
            conn.close()

    def test_readonly_uri_with_hostile_dir_name(self):
        weird = Path(self._tmp.name) / "100% weird?dir#name"
        os.environ["AFTERWIT_DATA_DIR"] = str(weird)
        from afterwit import paths
        import sqlite3
        self.store.connect().close()  # create DB inside the weird dir
        self.assertTrue(paths.db_path().exists())
        ro = self.store.connect(readonly=True)  # must open the RIGHT file, ro
        try:
            with self.assertRaises(sqlite3.OperationalError):
                ro.execute("INSERT INTO meta (key, value) VALUES ('x', 'y')")
        finally:
            ro.close()


class SyncFixesTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        os.environ["AFTERWIT_DATA_DIR"] = self._tmp.name
        from afterwit import capture
        self.capture = capture
        capture.enqueue(
            {
                "session_id": "11111111-2222-3333-4444-555555555555",
                "transcript_path": str(FIXTURE),
                "cwd": "/Users/dev/projects/acme-app",
                "project": "acme-app",
                "enqueued_at": "2026-07-10T14:02:00Z",
            }
        )

    def tearDown(self):
        os.environ.pop("AFTERWIT_DATA_DIR", None)
        os.environ.pop("AFTERWIT_CLAUDE_BIN", None)
        self._tmp.cleanup()

    def _run(self, **kw):
        from afterwit import sync
        return sync.run(out=io.StringIO(), **kw)

    def test_limit_zero_processes_nothing(self):
        summary = self._run(limit=0)
        self.assertEqual(summary["eligible"], 0)
        self.assertEqual(len(self.capture.read_queue()), 1)

    def test_backend_unavailable_aborts_without_charging_attempts(self):
        os.environ["AFTERWIT_CLAUDE_BIN"] = "/nonexistent/claude-binary"
        for _ in range(4):  # would exceed MAX_ATTEMPTS if attempts were charged
            summary = self._run()
            self.assertTrue(summary.get("aborted"))
        queue = self.capture.read_queue()
        self.assertEqual(len(queue), 1)                  # nothing dropped
        self.assertNotIn("attempts", queue[0])           # nothing charged

    def test_drop_and_update_preserves_concurrent_enqueue(self):
        # simulate: a new session lands in the queue between sync's read and
        # its final rewrite — drop_and_update must keep it.
        self.capture.enqueue({"session_id": "late-arrival"})
        self.capture.drop_and_update(
            {"11111111-2222-3333-4444-555555555555"}, {}
        )
        ids = [r["session_id"] for r in self.capture.read_queue()]
        self.assertEqual(ids, ["late-arrival"])


if __name__ == "__main__":
    unittest.main()
