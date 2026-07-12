"""Store tests — run against a temp data dir via AFTERWIT_DATA_DIR."""

import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "plugins" / "afterwit" / "src"))


class StoreTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        os.environ["AFTERWIT_DATA_DIR"] = self._tmp.name
        # paths reads the env var at call time, so no reload needed
        from afterwit import store
        self.store = store

    def tearDown(self):
        os.environ.pop("AFTERWIT_DATA_DIR", None)
        self._tmp.cleanup()

    def test_self_init_creates_db_and_schema(self):
        conn = self.store.connect()
        try:
            tables = {
                r["name"]
                for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            self.assertLessEqual(
                {"meta", "lessons", "tags", "processed_sessions"}, tables
            )
            version = conn.execute(
                "SELECT value FROM meta WHERE key='schema_version'"
            ).fetchone()["value"]
            self.assertEqual(version, str(self.store.SCHEMA_VERSION))
            mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
            self.assertEqual(mode.lower(), "wal")
        finally:
            conn.close()

    def test_self_init_is_idempotent(self):
        self.store.connect().close()
        self.store.connect().close()  # second init must not raise

    def test_readonly_never_creates_file(self):
        from afterwit import paths
        with self.assertRaises(sqlite3.OperationalError):
            self.store.connect(readonly=True)
        self.assertFalse(paths.db_path().exists())

    def test_readonly_rejects_writes(self):
        self.store.connect().close()  # create
        ro = self.store.connect(readonly=True)
        try:
            with self.assertRaises(sqlite3.OperationalError):
                ro.execute("INSERT INTO meta (key, value) VALUES ('x', 'y')")
        finally:
            ro.close()

    def test_insert_and_recent(self):
        conn = self.store.connect()
        try:
            lid = self.store.insert_lesson(
                conn,
                title="Always await async setup in tests",
                problem="Tests flaked because setup wasn't awaited",
                lesson="Await every async fixture before assertions.",
                confidence=0.9,
                project="proj-a",
                session_id="s1",
                tags=["Testing", "async", "testing"],  # dup+case collapse
            )
            conn.commit()
            self.assertIsNotNone(lid)
            rows = self.store.recent_lessons(conn, 5, project="proj-a")
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["tags"], ["async", "testing"])
        finally:
            conn.close()

    def test_dedup_same_pattern_different_wording(self):
        conn = self.store.connect()
        try:
            a = self.store.insert_lesson(
                conn, title="Always await async setup",
                problem="p", lesson="l", project="proj-a",
            )
            b = self.store.insert_lesson(
                conn, title="always awaiting the async setup",
                problem="p2", lesson="l2", project="proj-a",
            )
            self.assertIsNotNone(a)
            self.assertIsNone(b)
        finally:
            conn.close()

    def test_distinct_lessons_not_deduped(self):
        conn = self.store.connect()
        try:
            a = self.store.insert_lesson(
                conn, title="N+1 query from lazy-loading in a loop",
                problem="p", lesson="l", project="proj-a",
            )
            b = self.store.insert_lesson(
                conn, title="SQLite WAL needed for concurrent readers",
                problem="p", lesson="l", project="proj-a",
            )
            self.assertIsNotNone(a)
            self.assertIsNotNone(b)
        finally:
            conn.close()

    def test_search_fts_or_like(self):
        conn = self.store.connect()
        try:
            self.store.insert_lesson(
                conn, title="SQLite WAL for concurrency",
                problem="database is locked errors",
                lesson="Enable WAL so readers and writers coexist.",
                project="proj-a",
            )
            conn.commit()
            hits = self.store.search_lessons(conn, "locked database")
            self.assertEqual(len(hits), 1)
            # Queries with FTS syntax characters must not raise
            self.store.search_lessons(conn, 'wal AND "locked" (x OR y)*')
        finally:
            conn.close()

    def test_processed_sessions(self):
        conn = self.store.connect()
        try:
            self.assertFalse(self.store.is_processed(conn, "s1"))
            self.store.mark_processed(conn, "s1", 3)
            self.assertTrue(self.store.is_processed(conn, "s1"))
        finally:
            conn.close()

    def test_stats_shape(self):
        conn = self.store.connect()
        try:
            self.store.insert_lesson(
                conn, title="t", problem="p", lesson="l",
                project="proj-a", tags=["x"],
            )
            s = self.store.stats(conn)
            self.assertEqual(s["total_lessons"], 1)
            self.assertEqual(s["by_project"][0]["project"], "proj-a")
            self.assertEqual(s["top_tags"][0]["tag"], "x")
        finally:
            conn.close()


class QueueTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        os.environ["AFTERWIT_DATA_DIR"] = self._tmp.name
        from afterwit import capture
        self.capture = capture

    def tearDown(self):
        os.environ.pop("AFTERWIT_DATA_DIR", None)
        self._tmp.cleanup()

    def test_enqueue_and_read(self):
        rec = {"session_id": "s1", "transcript_path": "/tmp/x.jsonl", "cwd": "/p"}
        self.assertTrue(self.capture.enqueue(rec))
        self.assertEqual(self.capture.read_queue(), [rec])

    def test_enqueue_idempotent(self):
        rec = {"session_id": "s1"}
        self.assertTrue(self.capture.enqueue(rec))
        self.assertFalse(self.capture.enqueue({"session_id": "s1", "other": 1}))
        self.assertEqual(len(self.capture.read_queue()), 1)

    def test_enqueue_rejects_missing_session_id(self):
        self.assertFalse(self.capture.enqueue({"transcript_path": "/tmp/x"}))

    def test_read_tolerates_corrupt_lines(self):
        from afterwit import paths
        self.capture.enqueue({"session_id": "s1"})
        with paths.queue_path().open("a") as f:
            f.write("{corrupt\n\n[1,2]\n")
        self.capture.enqueue({"session_id": "s2"})
        ids = [r["session_id"] for r in self.capture.read_queue()]
        self.assertEqual(ids, ["s1", "s2"])

    def test_remove(self):
        self.capture.enqueue({"session_id": "s1"})
        self.capture.enqueue({"session_id": "s2"})
        self.capture.remove({"s1"})
        ids = [r["session_id"] for r in self.capture.read_queue()]
        self.assertEqual(ids, ["s2"])


if __name__ == "__main__":
    unittest.main()
