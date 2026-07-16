"""`afterwit report` — a self-contained HTML snapshot of the lessons DB.

Same dashboard page as `afterwit serve`, but with the full dataset inlined
into the document, so the file works from file:// with zero requests —
double-click it, mail it to yourself, archive it with the weekly notes.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import serve, webui


def _stats_for(lessons: list[dict]) -> dict:
    """Stats recomputed over a filtered subset, so the snapshot's tiles never
    contradict its feed (a --project report must not show global counts)."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    projects = Counter(l.get("project") or "unknown" for l in lessons)
    tags = Counter(t for l in lessons for t in l.get("tags", []))
    months = Counter((l.get("created_at") or "")[:7] for l in lessons)
    return {
        "total_lessons": len(lessons),
        "processed_sessions": len({l.get("session_id") for l in lessons if l.get("session_id")}),
        "lessons_last_30_days": sum(1 for l in lessons if (l.get("created_at") or "") >= cutoff),
        "by_project": [{"project": p, "count": c} for p, c in projects.most_common()],
        "top_tags": [{"tag": t, "count": c} for t, c in tags.most_common(20)],
        "by_month": [{"month": m, "count": c} for m, c in sorted(months.items()) if m],
    }


def write(out: str = "lessons.html", project: str | None = None) -> Path:
    data = serve.gather_data()
    if project:
        data["lessons"] = [l for l in data["lessons"] if l.get("project") == project]
        data["stats"] = _stats_for(data["lessons"])
        data["filtered_project"] = project
    html = webui.render_page(webui.boot_json(data))
    path = Path(out).expanduser().resolve()
    path.write_text(html, encoding="utf-8")
    return path
