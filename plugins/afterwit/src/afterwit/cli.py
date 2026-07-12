"""The `afterwit` command-line interface (stdlib argparse only)."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys

from . import __version__, capture, paths, store


def _open_readonly() -> sqlite3.Connection:
    try:
        return store.connect(readonly=True)
    except sqlite3.OperationalError:
        raise SystemExit(
            "No lessons database yet. Finish a Claude Code session, then run `afterwit sync`."
        )


def _print_lessons(lessons: list[dict], verbose: bool = False) -> None:
    if not lessons:
        print("(no lessons)")
        return
    for les in lessons:
        date = (les.get("created_at") or "")[:10]
        tags = " ".join(f"#{t}" for t in les.get("tags", []))
        conf = les.get("confidence")
        conf_s = f" ({conf:.0%})" if isinstance(conf, float) else ""
        print(f"[{les['id']:>4}] {date}  {les.get('project') or '-'}  {tags}")
        print(f"       {les['title']}{conf_s}")
        if verbose:
            for field in ("problem", "root_cause", "resolution"):
                if les.get(field):
                    print(f"       {field.replace('_', ' ')}: {les[field]}")
        print(f"       → {les['lesson']}")
        print()


def cmd_sync(args) -> None:
    from . import sync

    sync.run(
        backend=args.backend,
        project=args.project,
        since=args.since,
        dry_run=args.dry_run,
        limit=args.limit,
    )


def cmd_list(args) -> None:
    conn = _open_readonly()
    try:
        lessons = store.list_lessons(
            conn, project=args.project, tag=args.tag, since=args.since, limit=args.limit
        )
    finally:
        conn.close()
    _print_lessons(lessons, verbose=args.verbose)


def cmd_search(args) -> None:
    conn = _open_readonly()
    try:
        lessons = store.search_lessons(conn, " ".join(args.query), limit=args.limit)
    finally:
        conn.close()
    _print_lessons(lessons, verbose=args.verbose)


def cmd_stats(args) -> None:
    conn = _open_readonly()
    try:
        s = store.stats(conn)
    finally:
        conn.close()
    if args.json:
        print(json.dumps(s, indent=2))
        return
    print(f"lessons:            {s['total_lessons']}")
    print(f"sessions processed: {s['processed_sessions']}")
    print(f"lessons (30 days):  {s['lessons_last_30_days']}")
    if s["by_project"]:
        print("\nby project:")
        for row in s["by_project"][:10]:
            print(f"  {row['project']:<30} {row['count']}")
    if s["top_tags"]:
        print("\ntop tags:")
        for row in s["top_tags"][:10]:
            print(f"  #{row['tag']:<29} {row['count']}")
    if s["by_month"]:
        print("\nlessons over time:")
        peak = max(r["count"] for r in s["by_month"])
        for row in s["by_month"]:
            bar = "█" * max(1, round(row["count"] / peak * 30))
            print(f"  {row['month']}  {bar} {row['count']}")


def cmd_queue(args) -> None:
    records = capture.read_queue()
    if not records:
        print("queue is empty.")
        return
    for r in records:
        attempts = f" attempts={r['attempts']}" if r.get("attempts") else ""
        print(
            f"{r.get('enqueued_at', '?'):<21} {r.get('project', '?'):<24} "
            f"{r.get('session_id', '?')[:8]}  why={r.get('why', '?')}{attempts}"
        )
    print(f"\n{len(records)} session(s) pending. Run `afterwit sync` to distill.")


def cmd_delete(args) -> None:
    conn = store.connect()
    try:
        if store.delete_lesson(conn, args.id):
            conn.commit()
            print(f"deleted lesson {args.id}.")
        else:
            raise SystemExit(f"no lesson with id {args.id}.")
    finally:
        conn.close()


def cmd_paths(args) -> None:
    print(f"data dir: {paths.data_dir(create=False)}")
    print(f"database: {paths.db_path()}")
    print(f"queue:    {paths.queue_path()}")
    print(f"config:   {paths.config_path()}")


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(
        prog="afterwit",
        description="Lessons learned from your own Claude Code sessions — 100% local.",
    )
    ap.add_argument("--version", action="version", version=f"afterwit {__version__}")
    sub = ap.add_subparsers(dest="command", required=True)

    p = sub.add_parser("sync", help="distill queued sessions into lessons")
    p.add_argument("--backend", choices=["claude", "ollama"], help="inference backend")
    p.add_argument("--project", help="only sessions from this project")
    p.add_argument("--since", help="only sessions enqueued on/after this ISO date")
    p.add_argument("--limit", type=int, help="process at most N sessions")
    p.add_argument("--dry-run", action="store_true", help="show what would happen")
    p.set_defaults(func=cmd_sync)

    p = sub.add_parser("list", help="list stored lessons")
    p.add_argument("--project")
    p.add_argument("--tag")
    p.add_argument("--since", help="ISO date lower bound")
    p.add_argument("--limit", type=int, default=20)
    p.add_argument("-v", "--verbose", action="store_true", help="show problem/cause/resolution")
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("search", help="full-text search lessons")
    p.add_argument("query", nargs="+")
    p.add_argument("--limit", type=int, default=20)
    p.add_argument("-v", "--verbose", action="store_true")
    p.set_defaults(func=cmd_search)

    p = sub.add_parser("stats", help="counts, top tags, trends")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_stats)

    p = sub.add_parser("queue", help="show sessions waiting for sync")
    p.set_defaults(func=cmd_queue)

    p = sub.add_parser("delete", help="delete one lesson by id (explicit user action)")
    p.add_argument("id", type=int)
    p.set_defaults(func=cmd_delete)

    p = sub.add_parser("paths", help="show where afterwit keeps its data")
    p.set_defaults(func=cmd_paths)

    args = ap.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
