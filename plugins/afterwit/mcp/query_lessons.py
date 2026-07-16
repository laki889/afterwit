#!/usr/bin/env python3
"""Afterwit MCP server — read-only tools over the local lessons database.

Lets Claude ask, mid-session, "what have I learned about async retries?"
and get an answer from the local SQLite DB. Speaks the Model Context
Protocol over stdio (newline-delimited JSON-RPC 2.0), stdlib only.

Hard guarantees: opens the database strictly read-only, never writes,
never makes a network call, and never crashes on malformed input —
protocol errors get JSON-RPC errors, tool failures get isError results,
and garbage lines are skipped.
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys

sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
)

from afterwit import __version__, store  # noqa: E402

PROTOCOL_FALLBACK = "2024-11-05"

TOOLS = [
    {
        "name": "query_lessons",
        "description": (
            "Full-text search the developer's local lessons-learned database "
            "(distilled from their past Claude Code sessions). Use before "
            "re-deriving a fix for an error that may have occurred before, or "
            "when the user asks what they've learned about a topic. Provide "
            "at least one of query/tag/project."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search terms (title, problem, lesson, resolution)"},
                "tag": {"type": "string", "description": "Restrict to one lowercase topic tag, e.g. 'sqlite'"},
                "project": {"type": "string", "description": "Restrict to one project name"},
                "limit": {"type": "integer", "description": "Max results (default 10, max 50)"},
            },
        },
    },
    {
        "name": "recent_lessons",
        "description": (
            "The developer's most recent lessons learned, most relevant first "
            "(lessons from the given project are preferred). Good for a quick "
            "'anything I should keep in mind?' at the start of a task."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "n": {"type": "integer", "description": "How many lessons (default 5, max 20)"},
                "project": {"type": "string", "description": "Prefer lessons from this project"},
            },
        },
    },
    {
        "name": "lesson_stats",
        "description": (
            "Counts and trends over the lessons database: totals, lessons per "
            "project, top tags (recurring themes), lessons per month."
        ),
        "inputSchema": {"type": "object", "properties": {}},
    },
]


# ---------------------------------------------------------------------------
# Tool implementations

def _format_lesson(les: dict) -> str:
    parts = [f"### {les['title']}"]
    meta = [les.get("project") or "unknown project", (les.get("source_ts") or les.get("created_at") or "")[:10]]
    if les.get("tags"):
        meta.append(" ".join("#" + t for t in les["tags"]))
    if isinstance(les.get("confidence"), float):
        meta.append(f"confidence {les['confidence']:.0%}")
    parts.append("_" + " · ".join(m for m in meta if m) + "_")
    parts.append(f"**Lesson:** {les['lesson']}")
    for key, label in (("problem", "Problem"), ("root_cause", "Root cause"), ("resolution", "Resolution")):
        if les.get(key):
            parts.append(f"**{label}:** {les[key]}")
    return "\n".join(parts)


def _no_db_message() -> str:
    return (
        "No lessons database exists yet on this machine. Lessons appear after "
        "the developer runs `afterwit sync` (or /afterwit:sync) on captured sessions."
    )


def tool_query_lessons(args: dict) -> str:
    query = str(args.get("query") or "").strip()
    tag = str(args.get("tag") or "").strip().lower() or None
    project = str(args.get("project") or "").strip() or None
    if not (query or tag or project):
        raise ValueError("provide at least one of: query, tag, project")
    limit = max(1, min(int(args.get("limit") or 10), 50))
    conn = store.connect(readonly=True)
    try:
        if query:
            lessons = store.search_lessons(conn, query, limit=200)
            if tag:
                lessons = [l for l in lessons if tag in l.get("tags", [])]
            if project:
                lessons = [l for l in lessons if l.get("project") == project]
            lessons = lessons[:limit]
        else:
            lessons = store.list_lessons(conn, tag=tag, project=project, limit=limit)
    finally:
        conn.close()
    if not lessons:
        return "No matching lessons. (This only means nothing was recorded — not that the topic is problem-free.)"
    header = f"{len(lessons)} matching lesson(s):\n\n"
    return header + "\n\n".join(_format_lesson(l) for l in lessons)


def tool_recent_lessons(args: dict) -> str:
    n = max(1, min(int(args.get("n") or 5), 20))
    project = str(args.get("project") or "").strip() or None
    conn = store.connect(readonly=True)
    try:
        lessons = store.recent_lessons(conn, n, project=project)
    finally:
        conn.close()
    if not lessons:
        return "The lessons database is empty so far."
    return f"{len(lessons)} recent lesson(s):\n\n" + "\n\n".join(
        _format_lesson(l) for l in lessons
    )


def tool_lesson_stats(args: dict) -> str:
    conn = store.connect(readonly=True)
    try:
        s = store.stats(conn)
    finally:
        conn.close()
    lines = [
        f"Total lessons: {s['total_lessons']} (last 30 days: {s['lessons_last_30_days']})",
        f"Sessions distilled: {s['processed_sessions']}",
    ]
    if s["by_project"]:
        lines.append("Per project: " + ", ".join(f"{r['project']} ({r['count']})" for r in s["by_project"][:10]))
    if s["top_tags"]:
        lines.append("Top tags: " + ", ".join(f"#{r['tag']} ({r['count']})" for r in s["top_tags"][:12]))
        recurring = [r for r in s["top_tags"] if r["count"] >= 3]
        if recurring:
            lines.append(
                "Recurring themes (3+ lessons): "
                + ", ".join(f"#{r['tag']}" for r in recurring)
            )
    if s["by_month"]:
        lines.append("Per month: " + ", ".join(f"{r['month']}: {r['count']}" for r in s["by_month"]))
    return "\n".join(lines)


HANDLERS = {
    "query_lessons": tool_query_lessons,
    "recent_lessons": tool_recent_lessons,
    "lesson_stats": tool_lesson_stats,
}


# ---------------------------------------------------------------------------
# JSON-RPC / MCP plumbing

def _send(msg: dict) -> None:
    sys.stdout.write(json.dumps(msg, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def _result(mid, result: dict) -> None:
    _send({"jsonrpc": "2.0", "id": mid, "result": result})


def _error(mid, code: int, message: str) -> None:
    _send({"jsonrpc": "2.0", "id": mid, "error": {"code": code, "message": message}})


def handle(msg: dict) -> None:
    method = msg.get("method")
    mid = msg.get("id")
    is_request = "id" in msg

    if method == "initialize":
        params = msg.get("params") or {}
        version = params.get("protocolVersion")
        _result(mid, {
            "protocolVersion": version if isinstance(version, str) else PROTOCOL_FALLBACK,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": "afterwit-lessons", "version": __version__},
        })
    elif method == "tools/list":
        _result(mid, {"tools": TOOLS})
    elif method == "tools/call":
        params = msg.get("params") or {}
        name = params.get("name")
        handler = HANDLERS.get(name)
        if handler is None:
            _error(mid, -32602, f"unknown tool: {name}")
            return
        try:
            text = handler(params.get("arguments") or {})
            _result(mid, {"content": [{"type": "text", "text": text}], "isError": False})
        except sqlite3.OperationalError:
            _result(mid, {"content": [{"type": "text", "text": _no_db_message()}], "isError": False})
        except Exception as e:  # tool failure -> isError result, never a crash
            _result(mid, {"content": [{"type": "text", "text": f"tool failed: {e}"}], "isError": True})
    elif method == "ping":
        _result(mid, {})
    elif is_request:
        _error(mid, -32601, f"method not found: {method}")
    # notifications (initialized, cancelled, ...) need no response


def main() -> None:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            _error(None, -32700, "parse error")
            continue
        if isinstance(msg, dict):
            try:
                handle(msg)
            except Exception as e:  # belt and suspenders: keep serving
                print(f"afterwit-mcp internal error: {e}", file=sys.stderr)
                if "id" in msg:
                    _error(msg.get("id"), -32603, "internal error")


if __name__ == "__main__":
    main()
