"""SQLite storage for lessons.

Design constraints (see README / spec):
  - No prebuilt .db ships with the plugin: the schema self-initializes
    idempotently on every entry point, and sqlite creates the file on first
    connect (we create the parent dir first — sqlite won't).
  - WAL mode so one writer (`sync`) and many readers (SessionStart hook,
    web UI, MCP) coexist without "database is locked".
  - Readers open read-only via a file: URI so they can never mutate or
    accidentally create a database.
  - Lessons are never auto-deleted; they outlive the ~30-day transcript
    purge window. Deletion is an explicit user action only.
"""

from __future__ import annotations

import re
import sqlite3
import unicodedata
from datetime import datetime, timezone
from typing import Any, Iterable

from . import paths

SCHEMA_VERSION = 1

_SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (
  key   TEXT PRIMARY KEY,
  value TEXT
);

CREATE TABLE IF NOT EXISTS lessons (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  title       TEXT NOT NULL,
  problem     TEXT NOT NULL,
  root_cause  TEXT,
  resolution  TEXT,
  lesson      TEXT NOT NULL,
  confidence  REAL,
  project     TEXT,
  session_id  TEXT,
  source_ts   TEXT,
  created_at  TEXT NOT NULL,
  dedup_key   TEXT
);

CREATE TABLE IF NOT EXISTS tags (
  lesson_id INTEGER NOT NULL REFERENCES lessons(id) ON DELETE CASCADE,
  tag       TEXT NOT NULL,
  PRIMARY KEY (lesson_id, tag)
);

CREATE TABLE IF NOT EXISTS processed_sessions (
  session_id   TEXT PRIMARY KEY,
  processed_at TEXT NOT NULL,
  lesson_count INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_lessons_created ON lessons(created_at);
CREATE INDEX IF NOT EXISTS idx_lessons_project ON lessons(project);
CREATE INDEX IF NOT EXISTS idx_lessons_dedup   ON lessons(dedup_key);
CREATE INDEX IF NOT EXISTS idx_tags_tag        ON tags(tag);
"""

_FTS_SCHEMA = """
CREATE VIRTUAL TABLE IF NOT EXISTS lessons_fts USING fts5(
  title, problem, lesson, resolution,
  content='lessons', content_rowid='id'
);
CREATE TRIGGER IF NOT EXISTS lessons_ai AFTER INSERT ON lessons BEGIN
  INSERT INTO lessons_fts(rowid, title, problem, lesson, resolution)
  VALUES (new.id, new.title, new.problem, new.lesson, new.resolution);
END;
CREATE TRIGGER IF NOT EXISTS lessons_ad AFTER DELETE ON lessons BEGIN
  INSERT INTO lessons_fts(lessons_fts, rowid, title, problem, lesson, resolution)
  VALUES ('delete', old.id, old.title, old.problem, old.lesson, old.resolution);
END;
"""


def utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def connect(readonly: bool = False) -> sqlite3.Connection:
    """Open the DB. Writers self-init the schema; readers never write."""
    db = paths.db_path()
    if readonly:
        # Never creates the file; raises OperationalError if it doesn't exist.
        conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        return conn
    db.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    _init_schema(conn)
    return conn


def has_fts(conn: sqlite3.Connection) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='lessons_fts'"
    ).fetchone()
    return row is not None


def _init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(_SCHEMA)
    try:
        conn.executescript(_FTS_SCHEMA)
    except sqlite3.OperationalError:
        pass  # sqlite built without FTS5 — search falls back to LIKE
    cur = conn.execute("SELECT value FROM meta WHERE key='schema_version'")
    row = cur.fetchone()
    if row is None:
        conn.execute(
            "INSERT INTO meta (key, value) VALUES ('schema_version', ?)",
            (str(SCHEMA_VERSION),),
        )
    else:
        version = int(row["value"])
        if version < SCHEMA_VERSION:
            _migrate(conn, version)
    conn.commit()


def _migrate(conn: sqlite3.Connection, from_version: int) -> None:
    # Future migrations run here, stepwise: if from_version < 2: ...
    conn.execute(
        "UPDATE meta SET value=? WHERE key='schema_version'", (str(SCHEMA_VERSION),)
    )


# ---------------------------------------------------------------------------
# Dedup

_STOPWORDS = frozenset(
    "a an and are as at be by for from in into is it of on or that the to use using when with".split()
)


def _stem(word: str) -> str:
    """Crude suffix stripping — only has to be consistent, not linguistic,
    so "await"/"awaiting" and "query"/"queries" collide."""
    for suffix in ("ing", "ies", "es", "ed", "s"):
        if word.endswith(suffix) and len(word) - len(suffix) >= 3:
            return word[: -len(suffix)]
    return word


def dedup_key(title: str, lesson: str) -> str:
    """Normalized key for near-duplicate detection: significant stemmed words
    of the title (order-insensitive), so "Always await async setup" and
    "always awaiting async setup" collide."""
    text = unicodedata.normalize("NFKD", title.lower())
    words = re.findall(r"[a-z0-9]+", text)
    sig = sorted({_stem(w) for w in words if w not in _STOPWORDS})
    if not sig:  # degenerate title — fall back to the lesson body
        words = re.findall(r"[a-z0-9]+", lesson.lower())
        sig = sorted({_stem(w) for w in words if w not in _STOPWORDS})[:12]
    return "-".join(sig)


# ---------------------------------------------------------------------------
# Writes

def insert_lesson(
    conn: sqlite3.Connection,
    *,
    title: str,
    problem: str,
    lesson: str,
    root_cause: str | None = None,
    resolution: str | None = None,
    confidence: float | None = None,
    project: str | None = None,
    session_id: str | None = None,
    source_ts: str | None = None,
    tags: Iterable[str] = (),
) -> int | None:
    """Insert a lesson unless a near-duplicate exists for the same project.
    Returns the new lesson id, or None if skipped as a duplicate."""
    key = dedup_key(title, lesson)
    dup = conn.execute(
        "SELECT id FROM lessons WHERE dedup_key=? AND (project=? OR project IS NULL OR ?='')",
        (key, project, project or ""),
    ).fetchone()
    if dup is not None:
        return None
    cur = conn.execute(
        """INSERT INTO lessons
           (title, problem, root_cause, resolution, lesson, confidence,
            project, session_id, source_ts, created_at, dedup_key)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            title.strip(),
            problem.strip(),
            (root_cause or "").strip() or None,
            (resolution or "").strip() or None,
            lesson.strip(),
            confidence,
            project,
            session_id,
            source_ts,
            utcnow(),
            key,
        ),
    )
    lesson_id = cur.lastrowid
    for tag in {t.strip().lower() for t in tags if t and t.strip()}:
        conn.execute(
            "INSERT OR IGNORE INTO tags (lesson_id, tag) VALUES (?, ?)",
            (lesson_id, tag),
        )
    return lesson_id


def mark_processed(conn: sqlite3.Connection, session_id: str, lesson_count: int) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO processed_sessions (session_id, processed_at, lesson_count) VALUES (?, ?, ?)",
        (session_id, utcnow(), lesson_count),
    )


def is_processed(conn: sqlite3.Connection, session_id: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM processed_sessions WHERE session_id=?", (session_id,)
    ).fetchone()
    return row is not None


def delete_lesson(conn: sqlite3.Connection, lesson_id: int) -> bool:
    cur = conn.execute("DELETE FROM lessons WHERE id=?", (lesson_id,))
    return cur.rowcount > 0


# ---------------------------------------------------------------------------
# Reads

def _attach_tags(conn: sqlite3.Connection, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not rows:
        return rows
    ids = [r["id"] for r in rows]
    marks = ",".join("?" * len(ids))
    tag_rows = conn.execute(
        f"SELECT lesson_id, tag FROM tags WHERE lesson_id IN ({marks})", ids
    ).fetchall()
    by_id: dict[int, list[str]] = {}
    for tr in tag_rows:
        by_id.setdefault(tr["lesson_id"], []).append(tr["tag"])
    for r in rows:
        r["tags"] = sorted(by_id.get(r["id"], []))
    return rows


def existing_titles(conn: sqlite3.Connection, project: str | None, limit: int = 100) -> list[str]:
    """Titles already stored (this project first) — fed to the extraction
    prompt so the model dedups at the source."""
    rows = conn.execute(
        """SELECT title FROM lessons
           ORDER BY (project=?) DESC, created_at DESC LIMIT ?""",
        (project, limit),
    ).fetchall()
    return [r["title"] for r in rows]


def recent_lessons(
    conn: sqlite3.Connection,
    n: int = 5,
    project: str | None = None,
    min_confidence: float = 0.0,
) -> list[dict[str, Any]]:
    """N most recent lessons, preferring the given project over others."""
    rows = conn.execute(
        """SELECT * FROM lessons
           WHERE COALESCE(confidence, 1.0) >= ?
           ORDER BY (project=?) DESC, created_at DESC, id DESC LIMIT ?""",
        (min_confidence, project, n),
    ).fetchall()
    return _attach_tags(conn, [dict(r) for r in rows])


def list_lessons(
    conn: sqlite3.Connection,
    *,
    project: str | None = None,
    tag: str | None = None,
    since: str | None = None,
    until: str | None = None,
    limit: int = 200,
    offset: int = 0,
) -> list[dict[str, Any]]:
    where, params = ["1=1"], []
    if project:
        where.append("project = ?")
        params.append(project)
    if tag:
        where.append("id IN (SELECT lesson_id FROM tags WHERE tag = ?)")
        params.append(tag.lower())
    if since:
        where.append("created_at >= ?")
        params.append(since)
    if until:
        where.append("created_at <= ?")
        params.append(until)
    params.extend([limit, offset])
    rows = conn.execute(
        f"""SELECT * FROM lessons WHERE {' AND '.join(where)}
            ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?""",
        params,
    ).fetchall()
    return _attach_tags(conn, [dict(r) for r in rows])


def search_lessons(
    conn: sqlite3.Connection, query: str, limit: int = 50
) -> list[dict[str, Any]]:
    """FTS5 search when available, LIKE fallback otherwise."""
    query = query.strip()
    if not query:
        return []
    if has_fts(conn):
        # Quote each term to keep FTS syntax characters from breaking the query.
        terms = re.findall(r"[^\s\"']+", query)
        fts_query = " ".join('"{}"'.format(t.replace('"', "")) for t in terms)
        try:
            rows = conn.execute(
                """SELECT l.* FROM lessons_fts f JOIN lessons l ON l.id = f.rowid
                   WHERE lessons_fts MATCH ? ORDER BY rank LIMIT ?""",
                (fts_query, limit),
            ).fetchall()
            return _attach_tags(conn, [dict(r) for r in rows])
        except sqlite3.OperationalError:
            pass
    like = f"%{query}%"
    rows = conn.execute(
        """SELECT * FROM lessons
           WHERE title LIKE ? OR problem LIKE ? OR lesson LIKE ? OR COALESCE(resolution,'') LIKE ?
           ORDER BY created_at DESC LIMIT ?""",
        (like, like, like, like, limit),
    ).fetchall()
    return _attach_tags(conn, [dict(r) for r in rows])


def stats(conn: sqlite3.Connection) -> dict[str, Any]:
    total = conn.execute("SELECT COUNT(*) c FROM lessons").fetchone()["c"]
    sessions = conn.execute("SELECT COUNT(*) c FROM processed_sessions").fetchone()["c"]
    by_project = [
        dict(r)
        for r in conn.execute(
            """SELECT COALESCE(project,'unknown') project, COUNT(*) count
               FROM lessons GROUP BY project ORDER BY count DESC"""
        ).fetchall()
    ]
    top_tags = [
        dict(r)
        for r in conn.execute(
            "SELECT tag, COUNT(*) count FROM tags GROUP BY tag ORDER BY count DESC LIMIT 20"
        ).fetchall()
    ]
    by_month = [
        dict(r)
        for r in conn.execute(
            """SELECT substr(created_at, 1, 7) month, COUNT(*) count
               FROM lessons GROUP BY month ORDER BY month"""
        ).fetchall()
    ]
    recent = conn.execute(
        "SELECT COUNT(*) c FROM lessons WHERE created_at >= datetime('now', '-30 days')"
    ).fetchone()["c"]
    return {
        "total_lessons": total,
        "processed_sessions": sessions,
        "lessons_last_30_days": recent,
        "by_project": by_project,
        "top_tags": top_tags,
        "by_month": by_month,
    }
