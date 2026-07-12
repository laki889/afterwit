"""The capture queue — a plain JSONL file in the data dir.

SessionEnd appends one record per finished session; `afterwit sync` drains
it. A flat file (rather than the DB) keeps the hook path trivial and
auditable. A tiny advisory lock (queue.lock) serializes appends against the
drain-time rewrite, so a session ending WHILE sync runs can't be lost to the
rewrite's replace(). On platforms without fcntl (Windows) the lock degrades
to best-effort; the enqueue side stays idempotent either way.
"""

from __future__ import annotations

import contextlib
import json
from typing import Any

from . import paths

try:
    import fcntl
except ImportError:  # Windows
    fcntl = None


@contextlib.contextmanager
def queue_lock():
    """Advisory exclusive lock over queue mutations (blocking, short-lived)."""
    lock_path = paths.data_dir() / "queue.lock"
    with lock_path.open("a") as fh:
        if fcntl is not None:
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            if fcntl is not None:
                fcntl.flock(fh.fileno(), fcntl.LOCK_UN)


def enqueue(record: dict[str, Any]) -> bool:
    """Append a session record unless its session_id is already queued.
    Returns True if appended. Must stay cheap — it runs in the hook path."""
    session_id = record.get("session_id")
    if not session_id:
        return False
    with queue_lock():
        q = paths.queue_path()
        if q.exists():
            for existing in read_queue():
                if existing.get("session_id") == session_id:
                    return False
        line = json.dumps(record, ensure_ascii=False)
        with q.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    return True


def read_queue() -> list[dict[str, Any]]:
    """All pending records, tolerating blank/corrupt lines."""
    q = paths.queue_path()
    if not q.exists():
        return []
    records = []
    for line in q.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(rec, dict):
            records.append(rec)
    return records


def remove(session_ids: set[str]) -> None:
    """Rewrite the queue without the given sessions (they were processed
    or found permanently unprocessable)."""
    if not session_ids:
        return
    rewrite([r for r in read_queue() if r.get("session_id") not in session_ids])


def rewrite(records: list[dict[str, Any]]) -> None:
    """Atomically replace the queue contents (used to drop processed entries
    and persist per-record attempt counters)."""
    with queue_lock():
        q = paths.queue_path()
        q.parent.mkdir(parents=True, exist_ok=True)
        tmp = q.with_suffix(".jsonl.tmp")
        with tmp.open("w", encoding="utf-8") as f:
            for rec in records:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        tmp.replace(q)


def drop_and_update(done_ids: set[str], updated: dict[str, dict[str, Any]]) -> None:
    """Single locked read-filter-write: drop processed sessions and apply
    per-record updates, preserving any records enqueued in the meantime."""
    with queue_lock():
        remaining = []
        for rec in read_queue():
            sid = rec.get("session_id")
            if sid in done_ids:
                continue
            remaining.append(updated.get(sid, rec))
        q = paths.queue_path()
        q.parent.mkdir(parents=True, exist_ok=True)
        tmp = q.with_suffix(".jsonl.tmp")
        with tmp.open("w", encoding="utf-8") as f:
            for rec in remaining:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        tmp.replace(q)
