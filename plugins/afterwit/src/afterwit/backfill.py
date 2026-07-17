"""`afterwit backfill` — queue sessions from before afterwit was installed.

The SessionEnd hook only captures sessions that end AFTER the plugin is
installed, so a fresh install starts with an empty queue even on a machine
with weeks of history. That history still exists in Claude Code's transcript
store (~/.claude/projects/<encoded-cwd>/<session-id>.jsonl) until the host's
retention cleanup purges it (cleanupPeriodDays, default 30) — backfill scans
it newest-first and enqueues eligible sessions for `afterwit sync`.

Design notes:
  - The queue record is shaped exactly like the hook's, with why="backfill".
    Project/cwd come from the transcript's own `cwd` fields (the encoded
    directory name is ambiguous — dashes — so it is never decoded).
  - Idempotent: already-queued and already-processed sessions are skipped
    (and don't consume the limit), so re-running is always safe.
  - Eligibility mirrors sync's own bar (message/char minimums) so the picked
    sessions are worth an LLM call each.
  - A transcript modified in the last FRESH_SECONDS is treated as a live
    session and skipped — the SessionEnd hook will capture it properly.
  - Afterwit's own extraction runs use --no-session-persistence and leave no
    transcript, but any that slipped through (or came from another tool) are
    recognized by the extraction prompt in their first user message.
  - Only top-level <encoded-cwd>/<session>.jsonl files are scanned; subagent
    sidecar transcripts live deeper (<session-id>/subagents/**) and are
    fragments of a parent session, not sessions.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from typing import Any

from . import capture, parser, paths, store
from .store import utcnow

DEFAULT_LIMIT = 10
FRESH_SECONDS = 120
# Opening words of synth.EXTRACTION_PROMPT (kept literal here so importing
# this module never pulls in the inference stack).
_EXTRACTION_MARKER = (
    "You are analyzing the transcript of one Claude Code development session"
)


def run(
    *,
    limit: int = DEFAULT_LIMIT,
    days: int | None = None,
    project: str | None = None,
    dry_run: bool = False,
    out=sys.stdout,
) -> dict[str, Any]:
    from .sync import MIN_MESSAGES, MIN_RENDER_CHARS

    summary = {"scanned": 0, "picked": 0, "enqueued": 0, "already": 0,
               "fresh": 0, "extraction": 0, "filtered": 0, "trivial": 0,
               "errors": 0}
    projects_dir = paths.claude_projects_dir()
    if not projects_dir.is_dir():
        print(f"afterwit backfill: no Claude Code session store at "
              f"{projects_dir} — nothing to do.", file=out)
        return summary

    def mtime_or_zero(p) -> float:
        try:
            return p.stat().st_mtime
        except OSError:  # purged between glob and stat
            return 0.0

    candidates = sorted(
        projects_dir.glob("*/*.jsonl"), key=mtime_or_zero, reverse=True
    )
    queued_ids = {r.get("session_id") for r in capture.read_queue()}
    now = datetime.now(timezone.utc).timestamp()
    cutoff = now - days * 86400 if days else None
    limit = max(0, limit)

    picked: list[tuple[Any, str, str, Any]] = []
    conn = store.connect()
    try:
        for path in candidates:
            if len(picked) >= limit:
                break
            mtime = mtime_or_zero(path)
            if mtime == 0.0:
                continue
            if cutoff and mtime < cutoff:
                break  # sorted newest-first: the rest is older still
            summary["scanned"] += 1
            sid = path.stem
            if sid in queued_ids or store.is_processed(conn, sid):
                summary["already"] += 1
                continue
            if now - mtime < FRESH_SECONDS:
                summary["fresh"] += 1  # probably live; the hook will get it
                continue
            try:
                t = parser.parse_file(path)
            except OSError:
                summary["errors"] += 1
                continue
            first_user = next((m for m in t.messages if m.role == "user"), None)
            if first_user and _EXTRACTION_MARKER in parser.render_message(first_user):
                summary["extraction"] += 1
                continue
            proj = t.project or "unknown"
            if project and proj != project:
                summary["filtered"] += 1
                continue
            if (len(t.messages) < MIN_MESSAGES
                    or len(parser.render_transcript(t)) < MIN_RENDER_CHARS):
                summary["trivial"] += 1
                continue
            picked.append((path, sid, proj, t))
    finally:
        conn.close()
    summary["picked"] = len(picked)

    for path, sid, proj, t in picked:
        when = (t.last_ts or t.first_ts or "")[:10]
        if dry_run:
            print(f"  would enqueue {proj}/{sid[:8]} (last active {when})", file=out)
            continue
        if capture.enqueue({
            "session_id": sid,
            "transcript_path": str(path),
            "cwd": t.cwd or "",
            "project": proj,
            "why": "backfill",
            "enqueued_at": utcnow(),
        }):
            summary["enqueued"] += 1
            print(f"  enqueued {proj}/{sid[:8]} (last active {when})", file=out)

    skips = [(summary[k], label) for k, label in
             [("already", "already queued/processed"), ("fresh", "possibly live"),
              ("extraction", "extraction runs"), ("filtered", "other projects"),
              ("trivial", "too small"), ("errors", "unreadable")] if summary[k]]
    detail = ("; skipped " + ", ".join(f"{n} {label}" for n, label in skips)) if skips else ""
    verb = "would enqueue" if dry_run else "enqueued"
    print(f"afterwit backfill: {verb} {summary['picked'] if dry_run else summary['enqueued']}"
          f" session(s) from {summary['scanned']} scanned{detail}.", file=out)
    if picked and not dry_run:
        print("Run `afterwit sync` soon — Claude Code purges old transcripts "
              "on its own retention schedule.", file=out)
    return summary
