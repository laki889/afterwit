"""Tests for `afterwit backfill` — first-install import of pre-existing
Claude Code session transcripts from the host's store."""

import io
import json
import os
import shutil
import sys
import tempfile
import time
import unittest
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "plugins" / "afterwit" / "src"))

FIXTURE = Path(__file__).parent / "fixtures" / "sample_transcript.jsonl"
FILLER = "the deploy failed with a 502 and the root cause took a while " * 3


def _sid() -> str:
    return str(uuid.uuid4())


def _write_transcript(project_dir: Path, sid: str, *, cwd="/Users/dev/projects/acme-app",
                      n_msgs=6, age_hours=24.0, first_user_text=None) -> Path:
    """A minimal but structurally valid transcript: alternating user/assistant
    lines, assistant content as blocks with a message id, shared metadata."""
    project_dir.mkdir(parents=True, exist_ok=True)
    lines = []
    for i in range(n_msgs):
        ts = f"2026-07-10T14:{i:02d}:00.000Z"
        common = {"sessionId": sid, "cwd": cwd, "timestamp": ts, "uuid": f"u{i}",
                  "version": "2.1.207", "gitBranch": "main"}
        if i % 2 == 0:
            text = first_user_text if (i == 0 and first_user_text) else f"user message {i}: {FILLER}"
            rec = dict(common, type="user", message={"role": "user", "content": text})
        else:
            rec = dict(common, type="assistant", message={
                "role": "assistant", "id": f"m{i}",
                "content": [{"type": "text", "text": f"assistant reply {i}: {FILLER}"}],
            })
        lines.append(json.dumps(rec))
    p = project_dir / f"{sid}.jsonl"
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    ts = time.time() - age_hours * 3600
    os.utime(p, (ts, ts))
    return p


class BackfillTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        os.environ["AFTERWIT_DATA_DIR"] = str(root / "data")
        os.environ["AFTERWIT_CLAUDE_DIR"] = str(root / "claude")
        self.projects = root / "claude" / "projects"
        self.enc = self.projects / "-Users-dev-projects-acme-app"

    def tearDown(self):
        os.environ.pop("AFTERWIT_DATA_DIR", None)
        os.environ.pop("AFTERWIT_CLAUDE_DIR", None)
        self._tmp.cleanup()

    def _run(self, **kw):
        from afterwit import backfill
        kw.setdefault("out", io.StringIO())
        return backfill.run(**kw)

    def _queued_ids(self):
        from afterwit import capture
        return [r["session_id"] for r in capture.read_queue()]

    def test_missing_store_is_not_an_error(self):
        s = self._run()
        self.assertEqual(s["scanned"], 0)
        self.assertEqual(self._queued_ids(), [])

    def test_enqueues_newest_first_up_to_limit(self):
        sids = [_sid() for _ in range(4)]
        for i, sid in enumerate(sids):
            _write_transcript(self.enc, sid, age_hours=1.0 + i)
        s = self._run(limit=2)
        self.assertEqual(s["enqueued"], 2)
        self.assertEqual(self._queued_ids(), sids[:2])  # the two newest

    def test_default_limit_is_ten(self):
        for i in range(12):
            _write_transcript(self.enc, _sid(), age_hours=1.0 + i)
        s = self._run()
        self.assertEqual(s["enqueued"], 10)

    def test_skips_queued_and_processed_without_consuming_limit(self):
        from afterwit import capture, store
        newest, mid, old = _sid(), _sid(), _sid()
        _write_transcript(self.enc, newest, age_hours=1)
        _write_transcript(self.enc, mid, age_hours=2)
        _write_transcript(self.enc, old, age_hours=3)
        capture.enqueue({"session_id": newest, "transcript_path": "x"})
        conn = store.connect()
        store.mark_processed(conn, mid, 1)
        conn.commit(); conn.close()
        s = self._run(limit=1)
        self.assertEqual(s["already"], 2)
        self.assertEqual(s["enqueued"], 1)
        self.assertIn(old, self._queued_ids())

    def test_days_filter(self):
        recent, stale = _sid(), _sid()
        _write_transcript(self.enc, recent, age_hours=2)
        _write_transcript(self.enc, stale, age_hours=100)
        s = self._run(days=1)
        self.assertEqual(self._queued_ids(), [recent])
        self.assertEqual(s["enqueued"], 1)

    def test_project_filter(self):
        acme, other = _sid(), _sid()
        _write_transcript(self.enc, acme, age_hours=2)
        _write_transcript(self.projects / "-Users-dev-projects-other", other,
                          cwd="/Users/dev/projects/other", age_hours=1)
        s = self._run(project="acme-app")
        self.assertEqual(self._queued_ids(), [acme])
        self.assertEqual(s["filtered"], 1)

    def test_dry_run_enqueues_nothing(self):
        _write_transcript(self.enc, _sid())
        out = io.StringIO()
        s = self._run(dry_run=True, out=out)
        self.assertEqual(s["picked"], 1)
        self.assertEqual(s["enqueued"], 0)
        self.assertEqual(self._queued_ids(), [])
        self.assertIn("would enqueue", out.getvalue())

    def test_trivial_fresh_and_extraction_sessions_skipped(self):
        good = _sid()
        _write_transcript(self.enc, good, age_hours=2)
        _write_transcript(self.enc, _sid(), n_msgs=2, age_hours=3)     # trivial
        _write_transcript(self.enc, _sid(), age_hours=0)               # live
        _write_transcript(self.enc, _sid(), age_hours=4, first_user_text=(
            "You are analyzing the transcript of one Claude Code development "
            "session (provided as input). Extract only genuinely REUSABLE lessons"))
        s = self._run()
        self.assertEqual(self._queued_ids(), [good])
        self.assertEqual(s["trivial"], 1)
        self.assertEqual(s["fresh"], 1)
        self.assertEqual(s["extraction"], 1)

    def test_subagent_sidecars_ignored(self):
        parent = _sid()
        _write_transcript(self.enc, parent, age_hours=2)
        sidecar_dir = self.enc / parent / "subagents"
        _write_transcript(sidecar_dir, _sid(), age_hours=1)
        s = self._run()
        self.assertEqual(self._queued_ids(), [parent])
        self.assertEqual(s["scanned"], 1)

    def test_rerun_is_idempotent(self):
        _write_transcript(self.enc, _sid())
        self.assertEqual(self._run()["enqueued"], 1)
        again = self._run()
        self.assertEqual(again["enqueued"], 0)
        self.assertEqual(again["already"], 1)
        self.assertEqual(len(self._queued_ids()), 1)

    def test_extraction_marker_matches_synth_prompt(self):
        # backfill keeps a literal copy so it never imports the inference
        # stack — this pins it to the real prompt so edits can't drift.
        from afterwit import backfill, synth
        self.assertIn(backfill._EXTRACTION_MARKER, synth.EXTRACTION_PROMPT)

    def test_real_fixture_recovers_cwd_and_project(self):
        sid = "11111111-2222-3333-4444-555555555555"
        self.enc.mkdir(parents=True, exist_ok=True)
        dest = self.enc / f"{sid}.jsonl"
        shutil.copy(FIXTURE, dest)
        ts = time.time() - 3600
        os.utime(dest, (ts, ts))
        s = self._run()
        self.assertEqual(s["enqueued"], 1)
        from afterwit import capture
        rec = capture.read_queue()[0]
        self.assertEqual(rec["session_id"], sid)
        self.assertEqual(rec["project"], "acme-app")          # from transcript cwd,
        self.assertEqual(rec["cwd"], "/Users/dev/projects/acme-app")  # not the dir name
        self.assertEqual(rec["why"], "backfill")


if __name__ == "__main__":
    unittest.main()
