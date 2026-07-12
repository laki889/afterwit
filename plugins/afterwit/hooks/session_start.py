#!/usr/bin/env python3
"""SessionStart hook — quietly surface recent lessons in the new session.

Reads the lessons DB read-only and emits:
  {"hookSpecificOutput": {"hookEventName": "SessionStart",
                          "additionalContext": "<short markdown block>"}}

No-ops (exit 0, no output) when: the DB doesn't exist yet, it has no
lessons, injection is disabled in config, or anything at all goes wrong.
The block is kept small — a handful of lessons, each clipped — so it costs
only a few hundred tokens of context.
"""

import json
import os
import sys

sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
)

_LESSON_CHARS = 300   # per-lesson clip
_BLOCK_CHARS = 2400   # hard cap for the whole injected block


def build_context(payload: dict) -> str | None:
    from afterwit import config, paths, store

    cfg = config.load()
    if not cfg.get("inject_enabled", True):
        return None
    n = max(1, min(int(cfg.get("inject_count", 4)), 10))

    conn = store.connect(readonly=True)  # raises if DB doesn't exist yet
    try:
        project = paths.project_name_from_cwd(payload.get("cwd") or "")
        lessons = store.recent_lessons(
            conn, n, project=project,
            min_confidence=float(cfg.get("inject_min_confidence", 0.0)),
        )
    finally:
        conn.close()
    if not lessons:
        return None

    lines = [
        "Lessons learned from this developer's past Claude Code sessions"
        " (via the afterwit plugin). Keep them in mind when relevant; no"
        " need to mention them unless they apply:",
        "",
    ]
    for les in lessons:
        text = (les.get("lesson") or "").strip()
        if len(text) > _LESSON_CHARS:
            text = text[:_LESSON_CHARS] + "…"
        origin = les.get("project") or "unknown project"
        date = (les.get("source_ts") or les.get("created_at") or "")[:10]
        lines.append(f"- **{les['title']}** — {text} _({origin}, {date})_")
    block = "\n".join(lines)
    return block[:_BLOCK_CHARS]


def main() -> None:
    payload = json.load(sys.stdin)
    if not isinstance(payload, dict):
        return
    context = build_context(payload)
    if context:
        print(
            json.dumps(
                {
                    "hookSpecificOutput": {
                        "hookEventName": "SessionStart",
                        "additionalContext": context,
                    }
                }
            )
        )


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass  # injection is best-effort; never disturb session start
    sys.exit(0)
