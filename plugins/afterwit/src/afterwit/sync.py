"""`afterwit sync` — drain the capture queue into distilled lessons.

For each queued session not yet in processed_sessions:
  parse JSONL -> render clean text -> LLM extraction -> validate ->
  insert with dedup -> mark processed -> drop from queue.

Failure policy: backend/parse failures leave the entry queued with an
incremented `attempts` counter (retried on the next sync); after
MAX_ATTEMPTS it is dropped and remembered as processed-with-0-lessons.
Transcripts that are missing (already purged) or trivial are dropped
immediately. The run itself never raises on a single bad session.
"""

from __future__ import annotations

import sys
from typing import Any

from . import capture, config, parser, store, synth

MAX_ATTEMPTS = 3
MIN_MESSAGES = 3        # sessions smaller than this can't contain a lesson
MIN_RENDER_CHARS = 500


def run(
    *,
    backend: str | None = None,
    project: str | None = None,
    since: str | None = None,
    dry_run: bool = False,
    limit: int | None = None,
    out=sys.stdout,
) -> dict[str, Any]:
    cfg = config.load()
    backend_name = backend or cfg.get("backend", "claude")
    if backend_name not in synth.BACKENDS:
        raise SystemExit(f"unknown backend '{backend_name}' (use claude or ollama)")
    infer = synth.BACKENDS[backend_name]

    queue = capture.read_queue()
    todo = [
        r
        for r in queue
        if (not project or r.get("project") == project)
        and (not since or str(r.get("enqueued_at", "")) >= since)
    ]
    if limit:
        todo = todo[: max(0, limit)]
    summary = {"queued": len(queue), "eligible": len(todo), "sessions": 0,
               "lessons_new": 0, "lessons_duplicate": 0, "failed": 0, "skipped": 0}
    if not todo:
        print("afterwit sync: queue is empty — nothing to do.", file=out)
        return summary

    conn = store.connect()
    done_ids: set[str] = set()
    updated: dict[str, dict] = {}
    try:
        for rec in todo:
            sid = rec.get("session_id", "")
            label = f"{rec.get('project', '?')}/{sid[:8]}"
            if store.is_processed(conn, sid):
                done_ids.add(sid)
                continue

            transcript_path = rec.get("transcript_path", "")
            try:
                t = parser.parse_file(transcript_path)
            except OSError:
                print(f"  {label}: transcript gone (purged?) — dropping.", file=out)
                if not dry_run:
                    store.mark_processed(conn, sid, 0)
                    conn.commit()
                    done_ids.add(sid)
                summary["skipped"] += 1
                continue

            rendered = parser.render_transcript(
                t, max_chars=int(cfg.get("max_transcript_chars", 200_000))
            )
            if len(t.messages) < MIN_MESSAGES or len(rendered) < MIN_RENDER_CHARS:
                print(f"  {label}: trivial session — no lessons to mine.", file=out)
                if not dry_run:
                    store.mark_processed(conn, sid, 0)
                    conn.commit()
                    done_ids.add(sid)
                summary["skipped"] += 1
                continue

            proj = rec.get("project") or t.project
            if dry_run:
                print(
                    f"  {label}: would distill {len(t.messages)} messages "
                    f"({len(rendered)} chars) via {backend_name}.",
                    file=out,
                )
                summary["sessions"] += 1
                continue

            prompt = synth.build_prompt(store.existing_titles(conn, proj))
            try:
                raw = infer(prompt, rendered, cfg)
            except synth.BackendError as e:
                _note_failure(rec, updated, done_ids, conn, out, label, str(e), summary, dry_run)
                continue

            lessons, err = synth.parse_lessons(raw)
            if err:
                _note_failure(rec, updated, done_ids, conn, out, label, err, summary, dry_run)
                continue

            inserted = duplicates = 0
            min_conf = float(cfg.get("min_confidence", 0.0))
            for les in lessons:
                if les["confidence"] is not None and les["confidence"] < min_conf:
                    continue
                new_id = store.insert_lesson(
                    conn,
                    title=les["title"],
                    problem=les["problem"],
                    root_cause=les["root_cause"],
                    resolution=les["resolution"],
                    lesson=les["lesson"],
                    confidence=les["confidence"],
                    project=proj,
                    session_id=sid,
                    source_ts=t.first_ts,
                    tags=les["tags"],
                )
                if new_id is None:
                    duplicates += 1
                else:
                    inserted += 1
            store.mark_processed(conn, sid, inserted)
            conn.commit()
            done_ids.add(sid)
            summary["sessions"] += 1
            summary["lessons_new"] += inserted
            summary["lessons_duplicate"] += duplicates
            print(
                f"  {label}: {inserted} new lesson(s)"
                + (f", {duplicates} duplicate(s) skipped" if duplicates else "")
                + ".",
                file=out,
            )
    finally:
        conn.close()

    if not dry_run:
        remaining = []
        for rec in capture.read_queue():
            sid = rec.get("session_id")
            if sid in done_ids:
                continue
            remaining.append(updated.get(sid, rec))
        capture.rewrite(remaining)

    print(
        f"afterwit sync: {summary['sessions']} session(s) processed, "
        f"{summary['lessons_new']} new lesson(s), {summary['failed']} failed, "
        f"{summary['skipped']} skipped.",
        file=out,
    )
    return summary


def _note_failure(rec, updated, done_ids, conn, out, label, msg, summary, dry_run):
    summary["failed"] += 1
    attempts = int(rec.get("attempts", 0)) + 1
    if dry_run:
        return
    if attempts >= MAX_ATTEMPTS:
        print(f"  {label}: FAILED ({msg}) — giving up after {attempts} attempts.", file=out)
        store.mark_processed(conn, rec.get("session_id", ""), 0)
        conn.commit()
        done_ids.add(rec.get("session_id"))
    else:
        print(f"  {label}: FAILED ({msg}) — will retry on next sync.", file=out)
        updated[rec.get("session_id")] = {**rec, "attempts": attempts}
