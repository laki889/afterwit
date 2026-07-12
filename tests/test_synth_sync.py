"""Synthesis + sync tests.

The sync pipeline is tested end-to-end against a STUB `claude` binary
(via AFTERWIT_CLAUDE_BIN) that replays canned CLI envelopes — exercising the
real subprocess invocation, envelope unwrapping, JSON validation, dedup,
processed-session bookkeeping, and queue lifecycle without network or auth.
"""

import io
import json
import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "plugins" / "afterwit" / "src"))

from afterwit import synth  # noqa: E402

FIXTURE = Path(__file__).parent / "fixtures" / "sample_transcript.jsonl"

LESSON = {
    "title": "Zombie process holds port after failed deploy",
    "problem": "502s after a release because the old process still held port 3000",
    "root_cause": "systemd unit had no pre-start cleanup, so a crashed release left a listener behind",
    "resolution": "Killed the stale process and added ExecStartPre cleanup",
    "lesson": "When a fresh deploy 502s, check for stale listeners on the app port before blaming new code.",
    "tags": ["deploy", "systemd"],
    "confidence": 0.9,
}


class ParseLessonsTestCase(unittest.TestCase):
    def test_plain_array(self):
        lessons, err = synth.parse_lessons(json.dumps([LESSON]))
        self.assertIsNone(err)
        self.assertEqual(lessons[0]["title"], LESSON["title"])

    def test_fenced_array(self):
        text = "```json\n" + json.dumps([LESSON]) + "\n```"
        lessons, err = synth.parse_lessons(text)
        self.assertIsNone(err)
        self.assertEqual(len(lessons), 1)

    def test_array_with_prose_around_it(self):
        text = "Here are the lessons I found:\n" + json.dumps([LESSON]) + "\nHope this helps!"
        lessons, err = synth.parse_lessons(text)
        self.assertIsNone(err)
        self.assertEqual(len(lessons), 1)

    def test_object_with_lessons_key(self):
        lessons, err = synth.parse_lessons(json.dumps({"lessons": [LESSON]}))
        self.assertIsNone(err)
        self.assertEqual(len(lessons), 1)

    def test_empty_array_is_valid(self):
        lessons, err = synth.parse_lessons("[]")
        self.assertIsNone(err)
        self.assertEqual(lessons, [])

    def test_garbage_reports_error(self):
        lessons, err = synth.parse_lessons("I could not find anything.")
        self.assertEqual(lessons, [])
        self.assertIsNotNone(err)

    def test_invalid_items_dropped_valid_kept(self):
        data = [LESSON, {"title": "", "lesson": ""}, "not a dict", {"no": "fields"}]
        lessons, err = synth.parse_lessons(json.dumps(data))
        self.assertIsNone(err)
        self.assertEqual(len(lessons), 1)

    def test_confidence_clamped_and_tags_normalized(self):
        item = {**LESSON, "confidence": 7, "tags": "Deploy, SYSTEMD"}
        lessons, _ = synth.parse_lessons(json.dumps([item]))
        self.assertEqual(lessons[0]["confidence"], 1.0)
        self.assertEqual(lessons[0]["tags"], ["deploy", "systemd"])

    def test_prompt_includes_known_titles(self):
        p = synth.build_prompt(["Known lesson A"])
        self.assertIn("Known lesson A", p)
        self.assertIn("STRICT JSON", p)

    def test_ollama_refuses_non_loopback(self):
        with self.assertRaises(synth.BackendError):
            synth.call_ollama("p", "t", {"ollama_url": "http://example.com:11434"})


def _write_stub(dirpath: Path, envelope: dict) -> Path:
    """A fake `claude` CLI: ignores args, prints the given envelope."""
    stub = dirpath / "claude-stub"
    stub.write_text(
        "#!/usr/bin/env python3\nimport json,sys\n"
        "sys.stdin.read()\n"
        f"print(json.dumps({envelope!r}))\n"
    )
    stub.chmod(stub.stat().st_mode | stat.S_IEXEC)
    return stub


class SyncPipelineTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        os.environ["AFTERWIT_DATA_DIR"] = str(self.tmp / "data")
        from afterwit import capture
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

    def _run_sync(self, **kwargs):
        from afterwit import sync
        return sync.run(out=io.StringIO(), **kwargs)

    def test_end_to_end_with_stub_claude(self):
        envelope = {
            "type": "result", "subtype": "success", "is_error": False,
            "result": "```json\n" + json.dumps([LESSON]) + "\n```",
        }
        os.environ["AFTERWIT_CLAUDE_BIN"] = str(_write_stub(self.tmp, envelope))
        summary = self._run_sync()
        self.assertEqual(summary["sessions"], 1)
        self.assertEqual(summary["lessons_new"], 1)

        from afterwit import capture, store
        self.assertEqual(capture.read_queue(), [])          # queue drained
        conn = store.connect(readonly=True)
        try:
            rows = store.list_lessons(conn)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["project"], "acme-app")
            self.assertEqual(rows[0]["session_id"], "11111111-2222-3333-4444-555555555555")
            self.assertEqual(rows[0]["source_ts"], "2026-07-10T14:00:01.000Z")
            self.assertEqual(rows[0]["tags"], ["deploy", "systemd"])
            self.assertTrue(
                store.is_processed(conn, "11111111-2222-3333-4444-555555555555")
            )
        finally:
            conn.close()

        # second sync: already processed -> no new lessons, still clean
        summary2 = self._run_sync()
        self.assertEqual(summary2["sessions"], 0)
        self.assertEqual(summary2["lessons_new"], 0)

    def test_backend_failure_keeps_queued_and_counts_attempts(self):
        envelope = {"type": "result", "subtype": "success", "is_error": True,
                    "result": "Failed to authenticate"}
        os.environ["AFTERWIT_CLAUDE_BIN"] = str(_write_stub(self.tmp, envelope))
        from afterwit import capture, store

        summary = self._run_sync()
        self.assertEqual(summary["failed"], 1)
        queue = capture.read_queue()
        self.assertEqual(len(queue), 1)
        self.assertEqual(queue[0]["attempts"], 1)

        self._run_sync()
        summary3 = self._run_sync()  # third failure -> give up
        self.assertEqual(summary3["failed"], 1)
        self.assertEqual(capture.read_queue(), [])
        conn = store.connect(readonly=True)
        try:
            self.assertTrue(
                store.is_processed(conn, "11111111-2222-3333-4444-555555555555")
            )
            self.assertEqual(store.list_lessons(conn), [])
        finally:
            conn.close()

    def test_missing_transcript_dropped(self):
        from afterwit import capture
        capture.rewrite(
            [{"session_id": "gone-1", "transcript_path": "/nonexistent/x.jsonl",
              "project": "p", "enqueued_at": "2026-07-10T00:00:00Z"}]
        )
        summary = self._run_sync()
        self.assertEqual(summary["skipped"], 1)
        self.assertEqual(capture.read_queue(), [])

    def test_dry_run_touches_nothing(self):
        envelope = {"type": "result", "subtype": "success", "is_error": False,
                    "result": json.dumps([LESSON])}
        os.environ["AFTERWIT_CLAUDE_BIN"] = str(_write_stub(self.tmp, envelope))
        from afterwit import capture, paths
        summary = self._run_sync(dry_run=True)
        self.assertEqual(summary["sessions"], 1)
        self.assertEqual(summary["lessons_new"], 0)
        self.assertEqual(len(capture.read_queue()), 1)      # still queued

    def test_project_filter(self):
        summary = self._run_sync(project="not-this-project")
        self.assertEqual(summary["eligible"], 0)


if __name__ == "__main__":
    unittest.main()
