"""The capture queue — a plain JSONL file in the data dir.

SessionEnd appends one record per finished session; `afterwit sync` drains
it. A flat file (rather than the DB) keeps the hook path trivial, auditable,
and immune to DB locking; appends up to PIPE_BUF are atomic on POSIX.
"""

from __future__ import annotations

import json
from typing import Any

from . import paths


def enqueue(record: dict[str, Any]) -> bool:
    """Append a session record unless its session_id is already queued.
    Returns True if appended. Must stay cheap — it runs in the hook path."""
    session_id = record.get("session_id")
    if not session_id:
        return False
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
    q = paths.queue_path()
    q.parent.mkdir(parents=True, exist_ok=True)
    tmp = q.with_suffix(".jsonl.tmp")
    with tmp.open("w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    tmp.replace(q)
